from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .paths import CONFIG_PATH


DOMAINS = {"rates", "equity_index", "volatility", "fx", "commodity", "cb_event"}
EXCLUDED_DOMAINS = {"macro_release"}
VALUE_TRANSFORMS = {"raw", "change_from_prior", "pct_change_from_prior"}
OPERATORS = {"GT", "GTE", "LT", "LTE", "EQ", "BETWEEN"}
MISSING_POLICIES = {"wait_72h_then_void"}
REVISION_POLICIES = {"resolution_snapshot_committed", "official_vintage"}
ROUNDING_POLICIES = {"exact_raw_decimal"}
CALENDAR_POLICIES = {"exact_date", "next_valid_source_date"}
PROB_MIN = Decimal("0.01")
PROB_MAX = Decimal("0.99")
CLAIM_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z-\d{3}$")


class SchemaError(ValueError):
    pass


@dataclass(frozen=True)
class AdapterConfig:
    active: bool
    status: str
    domains: tuple[str, ...]


def load_adapter_config(path: Path = CONFIG_PATH) -> dict[str, AdapterConfig]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        key: AdapterConfig(
            active=bool(value["active"]),
            status=str(value["status"]),
            domains=tuple(value.get("domains", [])),
        )
        for key, value in raw.items()
    }


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def parse_utc(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise SchemaError("UTC datetimes must be ISO-8601 strings ending in Z")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SchemaError(f"invalid UTC datetime: {value}") from exc
    return parsed.astimezone(timezone.utc)


def parse_date(value: str) -> date:
    if not isinstance(value, str):
        raise SchemaError("dates must be ISO YYYY-MM-DD strings")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise SchemaError(f"invalid date: {value}") from exc


def decimal_value(value: Any, *, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise SchemaError(f"{field} must be decimal-compatible") from exc


def _require_keys(obj: dict[str, Any], keys: set[str], label: str) -> None:
    missing = keys - obj.keys()
    if missing:
        raise SchemaError(f"{label} missing required keys: {sorted(missing)}")


def validate_claim(record: dict[str, Any], *, adapter_config: dict[str, AdapterConfig] | None = None) -> dict[str, Any]:
    adapter_config = load_adapter_config() if adapter_config is None else adapter_config
    required = {
        "claim_id",
        "registered_at_utc",
        "domain",
        "statement_text",
        "machine_condition",
        "probability",
        "rationale",
    }
    _require_keys(record, required, "claim")

    claim_id = record["claim_id"]
    if not isinstance(claim_id, str) or not CLAIM_ID_RE.match(claim_id):
        raise SchemaError("claim_id must look like 2026-07-10T14:32:05Z-017")
    parse_utc(record["registered_at_utc"])

    domain = record["domain"]
    if domain in EXCLUDED_DOMAINS:
        raise SchemaError(f"domain excluded from v1: {domain}")
    if domain not in DOMAINS:
        raise SchemaError(f"invalid domain: {domain}")
    if not isinstance(record["statement_text"], str) or not record["statement_text"].strip():
        raise SchemaError("statement_text is required for display")
    if not isinstance(record["rationale"], str) or not record["rationale"].strip():
        raise SchemaError("rationale is required for display")

    probability = decimal_value(record["probability"], field="probability")
    if probability < PROB_MIN or probability > PROB_MAX:
        raise SchemaError("probability must be in [0.01, 0.99]")

    condition = record["machine_condition"]
    if not isinstance(condition, dict):
        raise SchemaError("machine_condition must be an object")
    condition_keys = {
        "source_adapter",
        "series_id",
        "observation_date",
        "value_transform",
        "operator",
        "threshold",
        "resolve_after_utc",
        "missing_policy",
        "revision_policy",
        "rounding_policy",
        "calendar_policy",
    }
    _require_keys(condition, condition_keys, "machine_condition")

    adapter_name = condition["source_adapter"]
    if adapter_name not in adapter_config:
        raise SchemaError(f"source_adapter not whitelisted: {adapter_name}")
    adapter = adapter_config[adapter_name]
    if not adapter.active:
        raise SchemaError(f"source_adapter inactive pending probe: {adapter_name}")
    if domain not in adapter.domains:
        raise SchemaError(f"adapter {adapter_name} is not admitted for domain {domain}")
    if not isinstance(condition["series_id"], str) or not condition["series_id"].strip():
        raise SchemaError("series_id is required")
    if condition["value_transform"] not in VALUE_TRANSFORMS:
        raise SchemaError("invalid value_transform")
    operator = condition["operator"]
    if operator not in OPERATORS:
        raise SchemaError("invalid operator")
    parse_date(condition["observation_date"])
    parse_utc(condition["resolve_after_utc"])
    if condition["missing_policy"] not in MISSING_POLICIES:
        raise SchemaError("invalid missing_policy")
    if condition["revision_policy"] not in REVISION_POLICIES:
        raise SchemaError("invalid revision_policy")
    if condition["rounding_policy"] not in ROUNDING_POLICIES:
        raise SchemaError("invalid rounding_policy")
    if condition["calendar_policy"] not in CALENDAR_POLICIES:
        raise SchemaError("invalid calendar_policy")

    threshold = condition["threshold"]
    if operator == "BETWEEN":
        if not isinstance(threshold, list) or len(threshold) != 2:
            raise SchemaError("BETWEEN threshold must be [lower, upper]")
        lo = decimal_value(threshold[0], field="threshold[0]")
        hi = decimal_value(threshold[1], field="threshold[1]")
        if lo > hi:
            raise SchemaError("BETWEEN lower threshold cannot exceed upper threshold")
    else:
        decimal_value(threshold, field="threshold")

    expected_hash = sha256_json({k: v for k, v in record.items() if k != "provenance_hash"})
    supplied_hash = record.get("provenance_hash")
    if supplied_hash is not None and supplied_hash != expected_hash:
        raise SchemaError("provenance_hash does not match canonical claim record")
    normalized = dict(record)
    normalized["provenance_hash"] = expected_hash
    return normalized
