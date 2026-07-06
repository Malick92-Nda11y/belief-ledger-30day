from __future__ import annotations

from datetime import date
from decimal import Decimal

import json

from belief_ledger.adapters import Observation, Snapshot
from belief_ledger import probes


class FakeProbeAdapter:
    def __init__(self, adapter, series_ids):
        self.adapter = adapter
        self.series_ids = set(series_ids)

    def fetch_snapshot(self, series_id: str) -> Snapshot:
        assert series_id in self.series_ids
        return Snapshot(
            adapter=self.adapter,
            source_url=f"https://example.test/{series_id}.csv",
            series_id=series_id,
            raw_sha256="hash",
            observations=[
                Observation(series_id=series_id, observation_date=date(2026, 1, day), value=Decimal(day))
                for day in range(1, 12)
            ],
        )


def test_amber_probe_admits_only_cleanly_parsed_sources(monkeypatch, tmp_path):
    config_path = tmp_path / "adapters.json"
    config_path.write_text(
        json.dumps({
            "EIA_WTI_DAILY": {"active": False, "status": "amber_probe_required", "domains": ["commodity"]},
            "FRED_FED_TARGET": {"active": False, "status": "amber_probe_required", "domains": ["cb_event"]},
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(probes, "CONFIG_PATH", config_path)
    monkeypatch.setattr(probes, "PROBE_RESULTS_DIR", tmp_path / "probe_results")
    monkeypatch.setattr(
        probes,
        "adapter_registry",
        lambda: {
            "EIA_WTI_DAILY": FakeProbeAdapter("EIA_WTI_DAILY", ["DCOILWTICO"]),
            "FRED_FED_TARGET": FakeProbeAdapter("FRED_FED_TARGET", ["DFEDTARU", "DFEDTARL"]),
        },
    )
    result = probes.run_amber_probe(write=True)
    assert result["adapters"]["EIA_WTI_DAILY"]["passed"] is True
    assert result["adapters"]["FRED_FED_TARGET"]["passed"] is True
    assert {row["series_id"] for row in result["adapters"]["FRED_FED_TARGET"]["series"]} == {"DFEDTARU", "DFEDTARL"}
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config["EIA_WTI_DAILY"]["active"] is True
    assert config["FRED_FED_TARGET"]["status"] == "admitted_by_probe"
