from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from belief_ledger.adapters import Observation, Snapshot
from belief_ledger.resolver import ResolutionError, resolve_claim
from belief_ledger.schema import SchemaError, validate_claim


class FakeAdapter:
    def __init__(self, snapshot: Snapshot):
        self.snapshot = snapshot

    def fetch_snapshot(self, series_id: str) -> Snapshot:
        assert series_id == self.snapshot.series_id
        return self.snapshot


def adapter_config(**overrides):
    base = {
        "FRED_DAILY": type("Cfg", (), {"active": True, "domains": ("rates", "equity_index"), "status": "green"})(),
        "VIX_DAILY": type("Cfg", (), {"active": True, "domains": ("volatility",), "status": "green"})(),
        "EIA_WTI_DAILY": type("Cfg", (), {"active": False, "domains": ("commodity",), "status": "amber"})(),
    }
    base.update(overrides)
    return base


def claim(**overrides):
    record = {
        "claim_id": "2026-07-10T14:32:05Z-017",
        "registered_at_utc": "2026-07-10T14:32:05Z",
        "domain": "rates",
        "statement_text": "Display text can be wrong; machine_condition is the law.",
        "machine_condition": {
            "source_adapter": "FRED_DAILY",
            "series_id": "DGS10",
            "observation_date": "2026-07-11",
            "value_transform": "raw",
            "operator": "GT",
            "threshold": "4.00",
            "resolve_after_utc": "2026-07-12T00:30:00Z",
            "missing_policy": "wait_72h_then_void",
            "revision_policy": "resolution_snapshot_committed",
            "rounding_policy": "exact_raw_decimal",
            "calendar_policy": "exact_date",
        },
        "probability": "0.62",
        "rationale": "Short display rationale.",
    }
    for key, value in overrides.items():
        if key == "machine_condition":
            record["machine_condition"].update(value)
        else:
            record[key] = value
    return record


def snapshot(values):
    return Snapshot(
        adapter="FRED_DAILY",
        source_url="https://example.test/fred.csv",
        series_id="DGS10",
        raw_sha256="abc123",
        observations=[
            Observation(
                series_id="DGS10",
                observation_date=date.fromisoformat(day) if isinstance(day, str) else day,
                value=Decimal(str(value)),
            )
            for day, value in values
        ],
    )


def test_validate_claim_rejects_inactive_amber_adapter():
    cfg = adapter_config()
    with pytest.raises(SchemaError, match="inactive pending probe"):
        validate_claim(
            claim(domain="commodity", machine_condition={"source_adapter": "EIA_WTI_DAILY", "series_id": "DCOILWTICO"}),
            adapter_config=cfg,
        )


def test_validate_claim_rejects_macro_release_and_degenerate_probability():
    with pytest.raises(SchemaError, match="domain excluded"):
        validate_claim(claim(domain="macro_release"), adapter_config=adapter_config())
    with pytest.raises(SchemaError, match="probability"):
        validate_claim(claim(probability="1.00"), adapter_config=adapter_config())


def test_validate_claim_rejects_free_form_adapter():
    with pytest.raises(SchemaError, match="not whitelisted"):
        validate_claim(
            claim(machine_condition={"source_adapter": "https://example.test/free-form.csv"}),
            adapter_config=adapter_config(),
        )


def test_resolver_uses_machine_condition_not_statement_text():
    record = validate_claim(claim(statement_text="DGS10 will be below 4.00."), adapter_config=adapter_config())
    snap = snapshot([(record["machine_condition"]["observation_date"], "4.15")])
    resolution, _ = resolve_claim(
        record,
        now_utc=datetime(2026, 7, 12, 1, 0, tzinfo=timezone.utc),
        adapters={"FRED_DAILY": FakeAdapter(snap)},
    )
    assert resolution.status == "RESOLVED_TRUE"
    assert resolution.outcome == 1
    assert resolution.observed_value == "4.15"


def test_resolver_change_from_prior_and_between():
    record = validate_claim(
        claim(
            machine_condition={
                "value_transform": "change_from_prior",
                "operator": "BETWEEN",
                "threshold": ["0.09", "0.11"],
            }
        ),
        adapter_config=adapter_config(),
    )
    snap = snapshot([
        ("2026-07-10", "4.00"),
        ("2026-07-11", "4.10"),
    ])
    resolution, _ = resolve_claim(
        record,
        now_utc=datetime(2026, 7, 12, 1, 0, tzinfo=timezone.utc),
        adapters={"FRED_DAILY": FakeAdapter(snap)},
    )
    assert resolution.status == "RESOLVED_TRUE"
    assert resolution.observed_value == "0.10"
    assert resolution.prior_observation_date == "2026-07-10"


def test_missing_exact_date_retries_then_voids_after_72h():
    record = validate_claim(claim(), adapter_config=adapter_config())
    snap = snapshot([("2026-07-10", "4.00")])
    with pytest.raises(ResolutionError, match="retry window remains"):
        resolve_claim(
            record,
            now_utc=datetime(2026, 7, 13, 0, 0, tzinfo=timezone.utc),
            adapters={"FRED_DAILY": FakeAdapter(snap)},
        )
    resolution, _ = resolve_claim(
        record,
        now_utc=datetime(2026, 7, 16, 1, 0, tzinfo=timezone.utc),
        adapters={"FRED_DAILY": FakeAdapter(snap)},
    )
    assert resolution.status == "VOID"
    assert resolution.outcome is None
    assert resolution.reason == "source lacks required observation_date"


def test_next_valid_source_date_policy_selects_forward_observation():
    record = validate_claim(claim(machine_condition={"calendar_policy": "next_valid_source_date"}), adapter_config=adapter_config())
    snap = snapshot([
        ("2026-07-10", "3.90"),
        ("2026-07-13", "4.20"),
    ])
    resolution, _ = resolve_claim(
        record,
        now_utc=datetime(2026, 7, 14, 1, 0, tzinfo=timezone.utc),
        adapters={"FRED_DAILY": FakeAdapter(snap)},
    )
    assert resolution.status == "RESOLVED_TRUE"
    assert resolution.source_observation_date == "2026-07-13"
