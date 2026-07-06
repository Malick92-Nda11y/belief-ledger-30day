# 30-DAY PUBLIC MACRO BELIEF-LEDGER — PROOF-ARTIFACT PRE-REGISTRATION

**Status: LOCKED — v1.1** (Research-authored; Codex feasibility review COMPLETE — "GO conditional,
not lockable as written"; all 11 pins integrated per §12. Ratified by Malick 2026-07-06.
After lock: no edits to §§1-10 except append-only corrections per §7.)
**Author:** Claude (Research Authority) · **Date:** 2026-07-06 · **Directed by:** Malick (Capital
& Product Authority). Engineering heart (template resolver + adapters + scorer) = Codex.

**What this is (one line):** the belief-accountability machine — the same discipline that honestly
killed five strategies — applied to itself, in public, on **template-constrained, mechanically-
resolvable** macro/markets claims, for 30 days. The **scarred public wedge**, not The Referee, not
a horizontal Audit-Layer SaaS.

**Governance / home:** a NEW, dedicated, public, append-only store (a fresh public git repo — commit
history *is* the provenance). This document is its founding pre-registration. It is NOT part of the
Trading Copilot research apparatus (dormant, L-118/L-130) and inherits none of its authorizations;
it borrows only its discipline. No trading, no money, no product — see §10.

**Load-bearing design decision (unchanged):** *the product is the honest machine, not the accuracy.*
A publicly-scored "I was poorly calibrated, here is the proof, nothing hidden" is a SUCCESS. The
thing being proven is whether Malick can operate a belief-accountability machine that resolves and
scores its own claims for 30 days **without hiding a miss or drifting a criterion.** Being a bad
forecaster is not a failure of the artifact; being a dishonest or inoperable one is.

**Codex's core correction, adopted (the spine of v1.1):** *no arbitrary claim normalization.* The
resolver accepts claims ONLY from strict templates backed by whitelisted source adapters.
`statement_text` is **display-only**; **`machine_condition` is the law.** A claim that cannot be
expressed as a `machine_condition` over a whitelisted adapter is inadmissible — not arbitrated.

---

## 1. Claim schema (template-first)

Every claim is: a resolvable binary predicate (`machine_condition`) over a **whitelisted adapter**,
plus a stated `probability` that it resolves TRUE. Registered (committed to the public store)
**before** `resolve_after_utc`. Fields:

- `claim_id` — sequential + registration timestamp. Immutable.
- `registered_at_utc` — UTC = git commit time. Immutable.
- `domain` — one of the **v1-admissible** set (§2): `rates`, `equity_index`, `volatility`, `fx`,
  `commodity` (WTI-only), `cb_event` (target-rate-only). `macro_release` is **excluded from v1**.
- `statement_text` — plain-language, **DISPLAY ONLY. Never the resolution authority.**
- `machine_condition` — the law:
  - `source_adapter` — from the **whitelist only** (§6): `FRED_DAILY` | `FRED_MONTHLY` |
    `VIX_DAILY` | `ECB_FX_DAILY` | `EIA_WTI_DAILY` | `FRED_FED_TARGET`. No free-form URLs.
  - `series_id` — the adapter's series key (e.g., `DGS10`, `SP500`, `VIXCLS`, `DFEDTARU`).
  - `observation_date` — the date whose value is observed (distinct from resolution timing).
  - `value_transform` — `raw` | `change_from_prior` | `pct_change_from_prior` (prior = the adapter's
    previous valid observation per `calendar_policy`).
  - `operator` — `GT` | `GTE` | `LT` | `LTE` | `EQ` | `BETWEEN`.
  - `threshold` — a value, or `[a, b]` for `BETWEEN`.
  - `resolve_after_utc` — earliest UTC we may pull (accounts for publish lag).
  - `missing_policy` — default `wait_72h_then_void` (retry until 72h after `resolve_after_utc`,
    then VOID with public reason).
  - `revision_policy` — `resolution_snapshot_committed` (default) | `official_vintage` (ALFRED-style
    vintage key pinned). **No silent latest-value pulls.**
  - `rounding_policy` — `exact_raw_decimal` (compare the raw source decimal exactly; no hand
    rounding).
  - `calendar_policy` — `exact_date` (source must carry that observation_date) | `next_valid_source_date`
    (predeclared fallback). Whichever is chosen is pinned now.
- `probability` — **required for EVERY claim**, in `[0.01, 0.99]` (no degenerate certainties; every
  claim is scored by calibration).
- `rationale` — 1-3 sentences, display only (enables later "right for the right reason" reading). An
  LLM may draft `statement_text`/`rationale`; it touches NOTHING in resolution or scoring.
- `provenance_hash` — SHA-256 of the claim record; git commit anchors the timestamp.

**Admissibility gate:** a claim registers only if it is a valid `machine_condition` over a
whitelisted adapter with all policies pinned. Invalid claims are made *impossible by the form*, not
resolved by judgment.

## 2. Resolution schema (adapter-mechanical, snapshot-committed)

- **Mechanical only, adapter-bound.** At `resolve_after_utc`, a deterministic resolver pulls the
  pinned `source_adapter`/`series_id` for `observation_date` (and the prior observation if
  `value_transform` needs it, per `calendar_policy`), applies the transform, evaluates
  `operator` vs `threshold`, and marks `RESOLVED_TRUE` / `RESOLVED_FALSE` / `VOID`. No arbitration.
- **Snapshot commit (the revision fix).** The raw adapter response used to resolve is **committed to
  the immutable store at resolution time**, and scoring is computed off that snapshot. Later
  revisions to the series can never retroactively change a resolved outcome
  (`revision_policy=resolution_snapshot_committed`). `official_vintage` pins an explicit vintage key
  instead. This is what makes even revision-prone series safe.
- **`missing_policy`** governs unavailability: retry to 72h past `resolve_after_utc`, then VOID
  (published reason). VOIDs are rare, pre-defined, counted, and shown — never an escape hatch.
- **`calendar_policy`** governs date mismatches (holiday/no-print): `exact_date` VOIDs if the source
  lacks that date; `next_valid_source_date` uses the predeclared fallback. Pinned per claim.
- **`rounding_policy=exact_raw_decimal`** — no hand rounding, ever.
- **Third-party reproducible** from the committed snapshot + pinned adapter alone.
- **v1-admissible domains and their clean sources** (Codex cleanliness map):
  - `rates` — FRED daily (e.g., `DGS10`, `DFEDTARU/L`). Green.
  - `equity_index` — **daily close only** via FRED `SP500`. No intraday, no ETF adjusted close,
    no "market rallied." Green.
  - `volatility` — daily close via `VIXCLS`/Cboe. Green.
  - `fx` — ECB daily reference rates (EUR pairs) / FRED H.10. Green.
  - `commodity` — **WTI only** via FRED/EIA (lagged; `resolve_after_utc` must respect the lag). Amber.
  - `cb_event` — **target-rate facts only** (Fed upper/lower bound via `DFEDTARU/DFEDTARL`). NOT
    statement tone, dot-plot, or press-conference language. Amber.
  - `macro_release` — **excluded from v1** (revision/first-print/vintage hazard). Re-admissible only
    later via a stricter `official_vintage` template — a future version, not this one.

## 3. Scoring rules

Computed by a **locked deterministic script** from the immutable ledger + committed snapshots —
never by hand:

- **Brier** per resolved claim: `(p - outcome)^2`; aggregate **mean Brier**, overall and per domain.
- **Calibration: 5 buckets** (0-20 / 20-40 / 40-60 / 60-80 / 80-100%), curve + **ECE**
  (sample-weighted mean |bucket_pred − bucket_realized|). *(Deciles are too sparse at ~30 resolved
  claims — Codex pin.)*
- **Baseline: 0.5 coin-flip is mandatory** (report mean Brier vs it). **Climatology/base-rate is
  OPTIONAL and only where a template defines it cleanly** — it is not built as a hidden research
  project (Codex pin).
- **Hit rate** as a descriptive companion only; Brier + calibration are the headline.
- TRUE/FALSE/VOID only, no partial credit. A scoring-script bug → fix → **re-run over ALL claims** →
  public note (§7). Never selective.

## 4. Public scorecard format

- **Public from registration.** Each claim is committed to the public store *when registered*,
  before resolution — no claim can be quietly dropped for going wrong. Open claims are visible.
- The generated public page shows: every claim (OPEN/RESOLVED/VOID) with full schema,
  `registered_at_utc`, provenance hash; running aggregate (N registered/resolved/void, **mean Brier,
  5-bucket calibration curve, ECE, hit rate, vs 0.5 baseline**), per-domain breakdown; a mandatory
  **"Biggest Misses"** section shown as prominently as any win; an update log for every scoring-fix.
- Store = git; every state change (registration, resolution snapshot, scoring) is a commit.

## 5. Cadence and minimum sample size

- **Window:** 30 consecutive calendar days from LOCK + first claim.
- **Sample floor (all must hold to count as "operated"):** **≥ 40 claims registered**, **≥ 30
  resolved in-window**, spread across **≥ 4 of the 6 v1-admissible domains**, **100% carrying an
  explicit `probability`** (Codex pin — no BINARY-without-probability). The 4 green domains alone
  guarantee the spread is reachable.
- **Cadence:** register in a fixed daily window (~2 claims/trading day).
- **Horizons:** bias short (same-day close to ~1 week) so claims resolve in-window.

## 6. Source / provenance rules

- **`source_adapter` from the whitelist ONLY** (§1). No free-form source URLs as resolution
  authority. Adding an adapter to the whitelist is a versioned change, never mid-window.
- All policy fields (`resolution` timing, `revision`, `missing`, `rounding`, `calendar`,
  `value_transform`) pinned at registration and **immutable**.
- Data: **public, free, third-party-checkable only** (FRED, ECB, EIA, Cboe). No private/paid/
  privileged data — a discipline test, not a data-edge test; reproducible by anyone.
- Claim record + resolution snapshot both committed (resolution is auditable, not asserted). No
  back-dating: claim time = commit time.

## 7. No-retrofit / no-edit rules

- Once committed, a claim's `statement_text`, `machine_condition` (every field), `probability`, and
  all policies are **immutable. No edits. No deletions.**
- Corrections are **append-only**: a new timestamped annotation referencing the original.
- A claim registered is a claim scored, unless it hits a pre-defined §2 VOID (published reason).
- **Scoring rules + script locked at day 0.** A bug is fixed, re-run over **all** claims, noted
  publicly — never applied selectively.
- No "I didn't really mean that one." Registration is the commitment. No criteria drift.

## 8. Kill criteria (STOP — walk away from the BeliefOps direction)

- **Operability failure:** the §5 floor is missed (can't sustain ≥30 resolved across ≥4 domains in
  30 days). Primary test: can Malick *operate the machine*, not can he forecast.
- **Integrity failure:** any retrofit, silent edit, hidden/deleted miss, back-date, criteria drift,
  free-form-source resolution, or selective scoring-fix that occurs and is not caught-and-publicly-
  corrected. A single such breach voids the artifact's value → kill.
- **Explicitly NOT a kill:** bad forecasts. High Brier, worse-than-baseline calibration, an ugly
  Biggest-Misses section — that is the machine *working.* Do not confuse being wrong with being
  dishonest.

## 9. What would justify continuing (graduation — a separate future decision)

All of: operated the full 30 days; §5 floor met; **zero integrity breaches**; every miss public;
criteria never drifted; resolution + scoring reproducible by an independent third party from the
public store alone. Only then does the NEXT fork open (not authorized now): extend to 90 days /
add adapters+domains (incl. a proper `macro_release` vintage template); open the machine to score
*others'* claims (the Referee on-ramp — earned, not declared); package as the career artifact; or
generalize the resolver into reusable tooling. A fresh decision with evidence in hand.

## 10. What is explicitly NOT authorized

- **No trading, no real money, no paper trading tied to these claims.** Claims are falsifiable
  statements — not positions, not sized.
- **No recommendations or advice.** A claim is a testable statement, never a call to action.
- **No paid product, subscription, customers, SaaS, or public API** for others.
- **No horizontal Audit-Layer build** — scores **only Malick's own public claims**, nobody else's.
- **No natural-language / free-form claim resolution** — `machine_condition` over a whitelisted
  adapter only. **No free-form source URLs as resolution authority.**
- **No `macro_release` domain in v1.** No silent latest-value pulls (snapshot/vintage only).
- **No declaring neutrality or "Referee" status** — earned later, never self-asserted.
- **No LLM in resolution or scoring** — deterministic scripts only (Nexus's law). LLM may only draft
  `statement_text`/`rationale`.
- **No private/paid data, no edge-seeking, no alpha claims** — the alpha hunt is dead (five kills);
  this proves *accountability*, not edge.
- **No post-lock edits to §§1-10** except append-only corrections per §7.

---

## 11. Roles & sequence

- **Malick (Capital & Product):** ratifies; operates (registers claims — human judgment lives only
  in *what to claim* + `rationale`, never in resolution/scoring).
- **Codex (Engineering):** builds the mechanical heart — the whitelisted **source adapters**, the
  **template-first resolver** (form that makes invalid claims impossible), snapshot committer,
  deterministic Brier/5-bucket-calibration scorer, public-scorecard generator. A short **resolver
  probe** on the amber sources (WTI via FRED/EIA; Fed target via `DFEDTARU/L`) before admitting them.
- **Claude (Research):** authored this; adjudicates the 30-day result against §§8-9; no role in daily
  claims (independence preserved).
- **Sequence:** ✅ Codex feasibility (GO-conditional; 11 pins integrated) → ✅ **Malick ratifies → LOCK**
  → Codex builds adapters+resolver+scorer + creates the public repo → first claim starts the 30-day
  clock → daily operation → day-30 Research adjudication → graduation fork (§9) or kill (§8).

## 12. Amendment log

- **v1.0 · 2026-07-06:** initial pre-registration, PROPOSED. Scope per Malick's directive: public
  macro/markets belief ledger; mechanically-resolvable claims; scarred public wedge (not The Referee,
  not a horizontal SaaS).
- **v1.1 · 2026-07-06:** integrated Codex's feasibility review ("GO conditional, not lockable as
  written"). Core change: **template-first resolver, `machine_condition` is the law, `statement_text`
  display-only, whitelisted source adapters** — no arbitrary claim normalization. Pins added:
  `source_adapter` whitelist (no free-form URLs); `probability` required on 100% of scored claims;
  `observation_date` separate from resolution timing; `resolve_after_utc`; `missing_policy`;
  `revision_policy` (snapshot/vintage, no silent latest-value); `rounding_policy` (exact raw decimal);
  `value_transform`; `calendar_policy`; **5 calibration buckets** (was 10); climatology baseline
  optional (0.5 mandatory). Domain scope tightened for v1: 4 green (`rates`, `equity_index`-daily-close,
  `volatility`-daily-close, `fx`-reference) + amber `commodity`=WTI-only + amber `cb_event`=target-rate-
  only; **`macro_release` excluded from v1**. No change to §7 (no-retrofit), §8 (kill), or the
  "product = honest machine, not accuracy" spine.
