from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, DivisionByZero
from pathlib import Path
from typing import Any

from .adapters import Observation, Snapshot, adapter_registry, snapshot_to_json
from .schema import SchemaError, claim_file_stem, parse_date, parse_utc, validate_claim


class ResolutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class Resolution:
    claim_id: str
    status: str
    outcome: int | None
    observed_value: str | None
    source_observation_date: str | None
    prior_observation_date: str | None
    snapshot_path: str | None
    reason: str | None


def _select_observation(snapshot: Snapshot, observation_date, calendar_policy: str) -> Observation | None:
    observations = sorted(snapshot.observations, key=lambda obs: obs.observation_date)
    exact = [obs for obs in observations if obs.observation_date == observation_date]
    if exact:
        return exact[-1]
    if calendar_policy == "exact_date":
        return None
    after = [obs for obs in observations if obs.observation_date > observation_date]
    return after[0] if after else None


def _prior_observation(snapshot: Snapshot, selected: Observation) -> Observation | None:
    before = [obs for obs in snapshot.observations if obs.observation_date < selected.observation_date]
    if not before:
        return None
    return sorted(before, key=lambda obs: obs.observation_date)[-1]


def transformed_value(snapshot: Snapshot, condition: dict[str, Any]) -> tuple[Decimal | None, Observation | None, Observation | None, str | None]:
    observation_date = parse_date(condition["observation_date"])
    selected = _select_observation(snapshot, observation_date, condition["calendar_policy"])
    if selected is None:
        return None, None, None, "source lacks required observation_date"
    transform = condition["value_transform"]
    if transform == "raw":
        return selected.value, selected, None, None
    prior = _prior_observation(snapshot, selected)
    if prior is None:
        return None, selected, None, "source lacks prior observation required for transform"
    if transform == "change_from_prior":
        return selected.value - prior.value, selected, prior, None
    if transform == "pct_change_from_prior":
        if prior.value == 0:
            return None, selected, prior, "prior observation is zero"
        try:
            return (selected.value - prior.value) / prior.value, selected, prior, None
        except DivisionByZero:
            return None, selected, prior, "prior observation is zero"
    raise ResolutionError(f"unsupported value_transform: {transform}")


def evaluate_operator(value: Decimal, operator: str, threshold: Any) -> bool:
    if operator == "BETWEEN":
        lo = Decimal(str(threshold[0]))
        hi = Decimal(str(threshold[1]))
        return lo <= value <= hi
    target = Decimal(str(threshold))
    if operator == "GT":
        return value > target
    if operator == "GTE":
        return value >= target
    if operator == "LT":
        return value < target
    if operator == "LTE":
        return value <= target
    if operator == "EQ":
        return value == target
    raise ResolutionError(f"unsupported operator: {operator}")


def resolve_claim(
    claim: dict[str, Any],
    *,
    now_utc: datetime | None = None,
    adapters=None,
    snapshot_dir: Path | None = None,
) -> tuple[Resolution, dict[str, Any] | None]:
    claim = validate_claim(claim)
    now_utc = datetime.now(timezone.utc) if now_utc is None else now_utc.astimezone(timezone.utc)
    condition = claim["machine_condition"]
    resolve_after = parse_utc(condition["resolve_after_utc"])
    if now_utc < resolve_after:
        raise ResolutionError("claim cannot be resolved before resolve_after_utc")

    snapshot_path = None
    if snapshot_dir is not None:
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = snapshot_dir / f"{claim_file_stem(claim['claim_id'])}.snapshot.json"
        if snapshot_path.exists():
            raise ResolutionError(f"claim already has a committed snapshot: {snapshot_path}")

    adapters = adapter_registry() if adapters is None else adapters
    adapter_name = condition["source_adapter"]
    snapshot = adapters[adapter_name].fetch_snapshot(condition["series_id"])
    snapshot_json = snapshot_to_json(snapshot)
    if snapshot_path is not None:
        snapshot_path.write_text(json.dumps(snapshot_json, indent=2, sort_keys=True), encoding="utf-8")

    value, selected, prior, void_reason = transformed_value(snapshot, condition)
    if void_reason:
        deadline = resolve_after + timedelta(hours=72)
        if now_utc < deadline:
            raise ResolutionError(f"source unavailable but missing_policy retry window remains: {void_reason}")
        return (
            Resolution(
                claim_id=claim["claim_id"],
                status="VOID",
                outcome=None,
                observed_value=None,
                source_observation_date=selected.observation_date.isoformat() if selected else None,
                prior_observation_date=prior.observation_date.isoformat() if prior else None,
                snapshot_path=str(snapshot_path) if snapshot_path else None,
                reason=void_reason,
            ),
            snapshot_json,
        )
    assert value is not None and selected is not None
    outcome = 1 if evaluate_operator(value, condition["operator"], condition["threshold"]) else 0
    status = "RESOLVED_TRUE" if outcome == 1 else "RESOLVED_FALSE"
    return (
        Resolution(
            claim_id=claim["claim_id"],
            status=status,
            outcome=outcome,
            observed_value=str(value),
            source_observation_date=selected.observation_date.isoformat(),
            prior_observation_date=prior.observation_date.isoformat() if prior else None,
            snapshot_path=str(snapshot_path) if snapshot_path else None,
            reason=None,
        ),
        snapshot_json,
    )


def resolution_to_json(resolution: Resolution) -> dict[str, Any]:
    return {
        "claim_id": resolution.claim_id,
        "status": resolution.status,
        "outcome": resolution.outcome,
        "observed_value": resolution.observed_value,
        "source_observation_date": resolution.source_observation_date,
        "prior_observation_date": resolution.prior_observation_date,
        "snapshot_path": resolution.snapshot_path,
        "reason": resolution.reason,
    }
