from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .paths import CLAIMS_DIR, RESOLUTIONS_DIR, SCORECARDS_DIR, SNAPSHOTS_DIR
from .probes import run_amber_probe
from .resolver import resolution_to_json, resolve_claim
from .scorecard import load_claims_dir, load_json_dir, render_scorecard
from .schema import claim_file_stem, validate_claim


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def cmd_validate(args) -> int:
    claim = validate_claim(_read_json(Path(args.claim)))
    print(json.dumps({"status": "VALID", "claim_id": claim["claim_id"], "provenance_hash": claim["provenance_hash"]}, indent=2))
    return 0


def _write_new_json(path: Path, payload: dict) -> None:
    if path.exists():
        raise FileExistsError(f"append-only guard: refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def cmd_register(args) -> int:
    claim = validate_claim(_read_json(Path(args.claim)))
    out = CLAIMS_DIR / f"{claim_file_stem(claim['claim_id'])}.json"
    _write_new_json(out, claim)
    print(json.dumps({
        "status": "CLAIM_REGISTERED",
        "claim_id": claim["claim_id"],
        "claim_path": str(out),
        "provenance_hash": claim["provenance_hash"],
        "commit_required_immediately": True,
    }, indent=2))
    return 0


def cmd_resolve(args) -> int:
    claim_path = Path(args.claim)
    claim = validate_claim(_read_json(claim_path))
    out = RESOLUTIONS_DIR / f"{claim_file_stem(claim['claim_id'])}.resolution.json"
    if out.exists():
        raise FileExistsError(f"resolve-once guard: refusing to overwrite existing resolution: {out}")
    resolution, _snapshot = resolve_claim(claim, snapshot_dir=SNAPSHOTS_DIR)
    _write_new_json(out, resolution_to_json(resolution))
    print(json.dumps({
        "status": resolution.status,
        "claim_id": resolution.claim_id,
        "resolution_path": str(out),
        "snapshot_path": resolution.snapshot_path,
        "commit_required_immediately": True,
    }, indent=2))
    return 0


def cmd_scorecard(args) -> int:
    claims = load_claims_dir(CLAIMS_DIR)
    resolutions = load_json_dir(RESOLUTIONS_DIR)
    rendered = render_scorecard(claims, resolutions)
    SCORECARDS_DIR.mkdir(parents=True, exist_ok=True)
    out = SCORECARDS_DIR / "README.md"
    out.write_text(rendered, encoding="utf-8")
    print(json.dumps({"status": "SCORECARD_WRITTEN", "path": str(out)}, indent=2))
    return 0


def cmd_probe(args) -> int:
    result = run_amber_probe(write=True)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if all(row["passed"] for row in result["adapters"].values()) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="belief-ledger")
    sub = parser.add_subparsers(required=True)
    validate = sub.add_parser("validate-claim")
    validate.add_argument("claim")
    validate.set_defaults(func=cmd_validate)
    register = sub.add_parser("register-claim")
    register.add_argument("claim")
    register.set_defaults(func=cmd_register)
    resolve = sub.add_parser("resolve-claim")
    resolve.add_argument("claim")
    resolve.set_defaults(func=cmd_resolve)
    scorecard = sub.add_parser("generate-scorecard")
    scorecard.set_defaults(func=cmd_scorecard)
    probe = sub.add_parser("probe-adapters")
    probe.set_defaults(func=cmd_probe)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
