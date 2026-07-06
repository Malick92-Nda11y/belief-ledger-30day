from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


BUCKETS = [
    ("0-20", Decimal("0.0"), Decimal("0.2")),
    ("20-40", Decimal("0.2"), Decimal("0.4")),
    ("40-60", Decimal("0.4"), Decimal("0.6")),
    ("60-80", Decimal("0.6"), Decimal("0.8")),
    ("80-100", Decimal("0.8"), Decimal("1.0")),
]


def fmt_decimal(value: Decimal) -> str:
    if value == value.to_integral():
        return str(value.quantize(Decimal("1")))
    return format(value.normalize(), "f")


def bucket_label(probability: Decimal) -> str:
    for idx, (label, lo, hi) in enumerate(BUCKETS):
        if idx == 0 and lo <= probability <= hi:
            return label
        if lo < probability <= hi:
            return label
    raise ValueError(f"probability outside [0,1]: {probability}")


def brier(probability: Decimal, outcome: int) -> Decimal:
    return (probability - Decimal(outcome)) ** 2


def score_claims(claims: list[dict[str, Any]], resolutions: list[dict[str, Any]]) -> dict[str, Any]:
    by_claim = {claim["claim_id"]: claim for claim in claims}
    resolved = []
    void = []
    for resolution in resolutions:
        status = resolution["status"]
        if status == "VOID":
            void.append(resolution)
            continue
        if status not in {"RESOLVED_TRUE", "RESOLVED_FALSE"}:
            continue
        claim = by_claim[resolution["claim_id"]]
        p = Decimal(str(claim["probability"]))
        outcome = int(resolution["outcome"])
        score = brier(p, outcome)
        resolved.append({
            "claim_id": claim["claim_id"],
            "domain": claim["domain"],
            "probability": p,
            "outcome": outcome,
            "brier": score,
            "statement_text": claim["statement_text"],
        })

    mean_brier = None
    coin_brier = None
    if resolved:
        mean_brier = sum(row["brier"] for row in resolved) / Decimal(len(resolved))
        coin_brier = Decimal("0.25")

    buckets: dict[str, dict[str, Any]] = {
        label: {"n": 0, "probability_sum": Decimal("0"), "outcome_sum": 0}
        for label, _, _ in BUCKETS
    }
    for row in resolved:
        label = bucket_label(row["probability"])
        buckets[label]["n"] += 1
        buckets[label]["probability_sum"] += row["probability"]
        buckets[label]["outcome_sum"] += row["outcome"]

    ece = Decimal("0")
    calibration = []
    total = len(resolved)
    for label, data in buckets.items():
        n = data["n"]
        avg_p = None if n == 0 else data["probability_sum"] / Decimal(n)
        realized = None if n == 0 else Decimal(data["outcome_sum"]) / Decimal(n)
        abs_error = None if n == 0 else abs(avg_p - realized)
        if n and total:
            ece += Decimal(n) / Decimal(total) * abs_error
        calibration.append({
            "bucket": label,
            "n": n,
            "avg_probability": None if avg_p is None else fmt_decimal(avg_p),
            "realized_frequency": None if realized is None else fmt_decimal(realized),
            "abs_error": None if abs_error is None else fmt_decimal(abs_error),
        })

    by_domain = {}
    for row in resolved:
        by_domain.setdefault(row["domain"], []).append(row)
    domain_scores = {}
    for domain, rows in by_domain.items():
        domain_scores[domain] = {
            "n_resolved": len(rows),
            "mean_brier": fmt_decimal(sum(row["brier"] for row in rows) / Decimal(len(rows))),
            "hit_rate": fmt_decimal(Decimal(sum(row["outcome"] for row in rows)) / Decimal(len(rows))),
        }

    misses = sorted(resolved, key=lambda row: row["brier"], reverse=True)[:10]
    return {
        "n_claims": len(claims),
        "n_resolved": len(resolved),
        "n_void": len(void),
        "mean_brier": None if mean_brier is None else fmt_decimal(mean_brier),
        "coin_flip_mean_brier": None if coin_brier is None else fmt_decimal(coin_brier),
        "ece": None if not resolved else fmt_decimal(ece),
        "hit_rate": None if not resolved else fmt_decimal(Decimal(sum(row["outcome"] for row in resolved)) / Decimal(len(resolved))),
        "calibration": calibration,
        "domains": domain_scores,
        "biggest_misses": [
            {
                "claim_id": row["claim_id"],
                "domain": row["domain"],
                "probability": fmt_decimal(row["probability"]),
                "outcome": row["outcome"],
                "brier": fmt_decimal(row["brier"]),
                "statement_text": row["statement_text"],
            }
            for row in misses
        ],
    }
