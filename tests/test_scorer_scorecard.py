from __future__ import annotations

from belief_ledger.scorecard import render_scorecard
from belief_ledger.scorer import score_claims


def claims():
    return [
        {
            "claim_id": "2026-07-10T14:32:05Z-001",
            "domain": "rates",
            "statement_text": "DGS10 above 4.",
            "probability": "0.80",
        },
        {
            "claim_id": "2026-07-10T14:32:05Z-002",
            "domain": "fx",
            "statement_text": "EURUSD above 1.1.",
            "probability": "0.20",
        },
        {
            "claim_id": "2026-07-10T14:32:05Z-003",
            "domain": "volatility",
            "statement_text": "VIX below 20.",
            "probability": "0.60",
        },
    ]


def resolutions():
    return [
        {"claim_id": "2026-07-10T14:32:05Z-001", "status": "RESOLVED_TRUE", "outcome": 1},
        {"claim_id": "2026-07-10T14:32:05Z-002", "status": "RESOLVED_TRUE", "outcome": 1},
        {"claim_id": "2026-07-10T14:32:05Z-003", "status": "VOID", "outcome": None},
    ]


def test_score_claims_brier_ece_and_void_count():
    score = score_claims(claims(), resolutions())
    assert score["n_claims"] == 3
    assert score["n_resolved"] == 2
    assert score["n_void"] == 1
    # ((0.8 - 1)^2 + (0.2 - 1)^2) / 2 = 0.34
    assert score["mean_brier"] == "0.34"
    assert score["coin_flip_mean_brier"] == "0.25"
    assert score["biggest_misses"][0]["claim_id"] == "2026-07-10T14:32:05Z-002"


def test_scorecard_contains_required_public_sections():
    rendered = render_scorecard(claims(), resolutions())
    assert "## Aggregate" in rendered
    assert "## Calibration" in rendered
    assert "## Per-Domain Breakdown" in rendered
    assert "## Biggest Misses" in rendered
    assert "## Claim Ledger" in rendered
    assert "DGS10 above 4." in rendered
