from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adapters import adapter_registry
from .paths import CONFIG_PATH, PROBE_RESULTS_DIR


AMBER_PROBES = {
    "EIA_WTI_DAILY": {"series_ids": ["DCOILWTICO"], "required_min_observations": 10},
    "FRED_FED_TARGET": {"series_ids": ["DFEDTARU", "DFEDTARL"], "required_min_observations": 10},
}


def run_amber_probe(*, write: bool = True) -> dict[str, Any]:
    registry = adapter_registry()
    results: dict[str, Any] = {
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "adapters": {},
    }
    for adapter_name, probe in AMBER_PROBES.items():
        try:
            series_results = []
            for series_id in probe["series_ids"]:
                snapshot = registry[adapter_name].fetch_snapshot(series_id)
                latest = max(snapshot.observations, key=lambda obs: obs.observation_date)
                series_results.append({
                    "series_id": series_id,
                    "n_observations": len(snapshot.observations),
                    "latest_observation_date": latest.observation_date.isoformat(),
                    "latest_value": str(latest.value),
                    "raw_sha256": snapshot.raw_sha256,
                    "source_url": snapshot.source_url,
                    "passed": len(snapshot.observations) >= probe["required_min_observations"],
                })
            passed = all(row["passed"] for row in series_results)
            results["adapters"][adapter_name] = {
                "passed": passed,
                "series": series_results,
            }
        except Exception as exc:  # pragma: no cover - exercised by live probe, not unit tests
            results["adapters"][adapter_name] = {
                "passed": False,
                "series_ids": probe["series_ids"],
                "error": repr(exc),
            }
    if write:
        PROBE_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = PROBE_RESULTS_DIR / "amber_source_probe.json"
        out_path.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        for adapter_name, result in results["adapters"].items():
            config[adapter_name]["active"] = bool(result["passed"])
            config[adapter_name]["status"] = "admitted_by_probe" if result["passed"] else "probe_failed"
        CONFIG_PATH.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return results
