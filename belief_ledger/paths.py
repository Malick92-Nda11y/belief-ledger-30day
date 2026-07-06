from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "adapters.json"
CLAIMS_DIR = ROOT / "claims"
SNAPSHOTS_DIR = ROOT / "snapshots"
RESOLUTIONS_DIR = ROOT / "resolutions"
SCORECARDS_DIR = ROOT / "scorecards"
PROBE_RESULTS_DIR = ROOT / "probe_results"
