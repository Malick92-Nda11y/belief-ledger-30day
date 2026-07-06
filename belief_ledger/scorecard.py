from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .scorer import score_claims


def load_json_dir(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for item in sorted(path.glob("*.json")):
        rows.append(json.loads(item.read_text(encoding="utf-8")))
    return rows


def render_scorecard(claims: list[dict[str, Any]], resolutions: list[dict[str, Any]]) -> str:
    score = score_claims(claims, resolutions)
    lines = [
        "# Public Belief Ledger Scorecard",
        "",
        "Generated deterministically from committed claims and resolutions.",
        "",
        "## Aggregate",
        "",
        f"- Claims registered: {score['n_claims']}",
        f"- Resolved claims: {score['n_resolved']}",
        f"- Void claims: {score['n_void']}",
        f"- Mean Brier: {score['mean_brier']}",
        f"- Coin-flip mean Brier: {score['coin_flip_mean_brier']}",
        f"- ECE: {score['ece']}",
        f"- Hit rate: {score['hit_rate']}",
        "",
        "## Calibration",
        "",
        "| Bucket | N | Avg probability | Realized frequency | Abs error |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in score["calibration"]:
        lines.append(
            f"| {row['bucket']} | {row['n']} | {row['avg_probability']} | "
            f"{row['realized_frequency']} | {row['abs_error']} |"
        )
    lines.extend(["", "## Per-Domain Breakdown", "", "| Domain | N | Mean Brier | Hit rate |", "|---|---:|---:|---:|"])
    for domain, row in sorted(score["domains"].items()):
        lines.append(f"| {domain} | {row['n_resolved']} | {row['mean_brier']} | {row['hit_rate']} |")
    lines.extend(["", "## Biggest Misses", "", "| Claim | Domain | Probability | Outcome | Brier | Statement |", "|---|---|---:|---:|---:|---|"])
    for row in score["biggest_misses"]:
        statement = row["statement_text"].replace("|", "\\|")
        lines.append(
            f"| {row['claim_id']} | {row['domain']} | {row['probability']} | "
            f"{row['outcome']} | {row['brier']} | {statement} |"
        )
    lines.extend(["", "## Claim Ledger", "", "| Claim | Domain | Probability | Status | Statement |", "|---|---|---:|---|---|"])
    resolution_by_claim = {row["claim_id"]: row for row in resolutions}
    for claim in sorted(claims, key=lambda row: row["claim_id"]):
        resolution = resolution_by_claim.get(claim["claim_id"], {"status": "OPEN"})
        statement = claim["statement_text"].replace("|", "\\|")
        lines.append(
            f"| {claim['claim_id']} | {claim['domain']} | {claim['probability']} | "
            f"{resolution['status']} | {statement} |"
        )
    lines.append("")
    return "\n".join(lines)
