# Research Faithfulness Review — belief-ledger mechanical heart

**Reviewer:** Claude (Research Authority) · **Date:** 2026-07-06 · **Against:** locked
`BELIEF_LEDGER_30DAY_PREREG.md` v1.1 §§1-3, §4, §7.
**Build reviewed:** commits `7e38dc7` + `f543b4d`. Read: schema.py, adapters.py, resolver.py,
scorer.py, scorecard.py, cli.py, paths.py, config/adapters.json.

## Verdict: FAITHFUL in substance — ONE required fix + ONE condition before the first claim starts the 30-day clock.

The mechanics, whitelist, scoring math, and domain scope are correct and template-first. The gap is
specifically the *immutability enforcement at the tool layer* — which, for a product whose entire
value is "resolved outcomes cannot be silently changed," is the one thing that must be airtight.

## Confirmed faithful (§§1-3)
- **§1 template-first / whitelist:** `machine_condition` is the resolution law; `statement_text` +
  `rationale` are validated as display-only and never touch resolution. Adapter must be whitelisted,
  active, admitted for the claim's domain, and the series admitted for the adapter. `probability`
  required in [0.01, 0.99]. All policy fields (`value_transform`, `operator`, `missing`, `revision`,
  `rounding`, `calendar`) validated against fixed sets. `provenance_hash` = SHA-256 of the canonical
  record and is verified when supplied.
- **§2 mechanics + scope:** `resolve_after_utc` enforced; exact-Decimal operators (no rounding);
  `calendar_policy` exact-vs-next handled; `missing_policy` 72h-then-VOID path present; snapshot
  written with raw-bytes SHA-256. Config admits exactly the 6 v1 domains (rates/equity_index via
  FRED_DAILY, volatility via VIX_DAILY/VIXCLS, fx via ECB, commodity=WTI via EIA_WTI_DAILY/DCOILWTICO,
  cb_event via FRED_FED_TARGET/DFEDTARU-L); **macro_release has no adapter — structurally excluded.**
- **§3 scoring:** Brier per claim; mean Brier overall + per domain; **5-bucket** calibration + ECE
  (sample-weighted); **mandatory 0.25 coin-flip baseline** present; climatology correctly **omitted**
  (optional per pin 11). Deterministic (Decimal, sorted). Biggest-misses feed present for §4.

## FINDING 1 — REQUIRED FIX (blocks the clock): resolve is not resolve-once
- **Defect:** `cli.cmd_resolve` calls `resolve_claim` (which fetches a **fresh** snapshot every call)
  and then `write_text`s the resolution + snapshot, **silently overwriting** any existing one. Running
  `resolve-claim` a second time after a data revision produces a **different committed outcome**.
- **Why it matters:** this defeats the core §2 guarantee ("the snapshot committed at resolution is
  authoritative; later revisions can never retroactively change a resolved outcome") and §7 ("no
  edits, no deletions; a claim registered is a claim scored"). The entire product thesis is that
  outcomes can't be silently changed; today the tool lets them be.
- **Smallest fix:** make resolution idempotent/resolve-once — if a committed resolution (and snapshot)
  already exists for `claim_id`, **refuse** (raise) rather than re-fetch-and-overwrite; OR re-serve
  the committed resolution and re-score strictly from the committed snapshot. Never re-fetch over an
  existing resolution.

## FINDING 2 — CONDITION (before clock, or an ironclad protocol): append-only is enforced only by git
- **Defect:** there is no `register-claim` command that refuses to overwrite an existing `claim_id`,
  and `scorecard.load_json_dir` does **not** re-run `validate_claim`, so it does not re-verify
  `provenance_hash` on load. An in-place edit or deletion of a claim/resolution file is undetected by
  the tooling; the only immutability backstop is git commit history.
- **Why it matters:** §4 ("public from registration") and §7 (append-only, no-edit, no-delete) are
  currently *operational* (git hygiene), not code-enforced. The pre-reg *does* designate git as the
  provenance layer, so this is acceptable **only** under an ironclad protocol.
- **Smallest fix (any one, ideally both):** (a) add `register-claim` that stamps
  `registered_at_utc`/`provenance_hash`, writes into `claims/`, and **refuses to overwrite** an
  existing `claim_id`; (b) have `load_json_dir`/scorecard re-run `validate_claim` so a
  `provenance_hash` mismatch is caught. **Minimum acceptable:** pin the operating rule "every claim
  and every resolution = an immediate git commit; git history is the immutability record" into the
  run protocol, and never edit/delete a committed file.

## Non-blocking observations
- The 72h `missing_policy` retry window is applied to *structural* VOID reasons too (prior-is-zero,
  lacks-prior), not just unavailability — harmless (still VOIDs) but could short-circuit structural
  voids immediately. Low priority.
- `bucket_label` boundaries are left-open/right-closed (first bucket closed-closed) — deterministic
  and fine for probabilities in [0.01, 0.99].

## Gate to start the clock
Fix FINDING 1 (required) and close FINDING 2 (fix or pinned protocol). Research spot-checks the delta.
Then the first `register-claim` commit starts the 30-day window. Nothing else in §§1-3 blocks.

---

## Delta spot-check — commit `63a1ce9` — PASS (Research, 2026-07-06)
- **FINDING 1 CLOSED (double-guarded):** `cli.cmd_resolve` refuses if the resolution file exists;
  `resolver.resolve_claim` refuses **before the adapter fetch** if a committed snapshot exists; all
  writes go through `_write_new_json` which refuses any overwrite. Re-resolution against revised data
  is now impossible without deleting committed files (which git history records). §2/§7 spine holds
  in code.
- **FINDING 2 CLOSED:** `register-claim` validates + writes-once + refuses duplicate `claim_id`;
  `scorecard.load_claims_dir` revalidates every claim via `validate_claim` (re-verifies
  `provenance_hash`); immediate-commit protocol pinned in README. Git remains the designated
  ultimate provenance layer.
- **Windows-safe stems verified:** `claim_file_stem` maps only time `:`→`-` (injective; fails closed
  on any collision via the write-once guard); the immutable `claim_id` inside the JSON is preserved
  and remains the identity used by the scorer/scorecard.
- Tests: 15 passed (Codex). **Verdict: the mechanical heart is faithful and its immutability
  guarantees are code-enforced. The 30-day clock may start with the first `register-claim` commit.**
