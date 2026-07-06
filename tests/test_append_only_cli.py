from __future__ import annotations

import json
from argparse import Namespace

import pytest

from belief_ledger import cli
from belief_ledger.schema import SchemaError, claim_file_stem, validate_claim
from belief_ledger.scorecard import load_claims_dir


def valid_claim():
    return {
        "claim_id": "2026-07-10T14:32:05Z-017",
        "registered_at_utc": "2026-07-10T14:32:05Z",
        "domain": "rates",
        "statement_text": "DGS10 will be above 4.00 on 2026-07-11.",
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


def test_register_claim_writes_hash_and_refuses_duplicate_claim_id(monkeypatch, tmp_path):
    input_path = tmp_path / "candidate.json"
    input_path.write_text(json.dumps(valid_claim()), encoding="utf-8")
    claims_dir = tmp_path / "claims"
    monkeypatch.setattr(cli, "CLAIMS_DIR", claims_dir)

    assert cli.cmd_register(Namespace(claim=str(input_path))) == 0
    registered = claims_dir / f"{claim_file_stem('2026-07-10T14:32:05Z-017')}.json"
    payload = json.loads(registered.read_text(encoding="utf-8"))
    assert payload["provenance_hash"] == validate_claim(payload)["provenance_hash"]

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        cli.cmd_register(Namespace(claim=str(input_path)))


def test_resolve_claim_cli_refuses_existing_resolution_before_fetch(monkeypatch, tmp_path):
    input_path = tmp_path / "claim.json"
    input_path.write_text(json.dumps(validate_claim(valid_claim())), encoding="utf-8")
    resolutions_dir = tmp_path / "resolutions"
    resolutions_dir.mkdir()
    existing = resolutions_dir / f"{claim_file_stem('2026-07-10T14:32:05Z-017')}.resolution.json"
    existing.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(cli, "RESOLUTIONS_DIR", resolutions_dir)

    with pytest.raises(FileExistsError, match="resolve-once guard"):
        cli.cmd_resolve(Namespace(claim=str(input_path)))


def test_scorecard_load_revalidates_claim_provenance_hash(tmp_path):
    claims_dir = tmp_path / "claims"
    claims_dir.mkdir()
    claim = validate_claim(valid_claim())
    path = claims_dir / f"{claim_file_stem(claim['claim_id'])}.json"
    path.write_text(json.dumps(claim), encoding="utf-8")
    assert load_claims_dir(claims_dir)[0]["claim_id"] == claim["claim_id"]

    tampered = dict(claim)
    tampered["probability"] = "0.61"
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(SchemaError, match="provenance_hash"):
        load_claims_dir(claims_dir)
