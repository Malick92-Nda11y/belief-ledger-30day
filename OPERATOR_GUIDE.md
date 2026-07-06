# OPERATOR GUIDE - how to run the 30-day belief ledger (to the dot)

You are the operator. Your job: register ~2 claims per trading day and resolve them when their
dates arrive, for 30 days, hiding nothing. That's the whole test. This guide is your reference.

Rule of thumb for the whole month: **~40 claims registered, >=30 resolved, across >=4 domains.**

---

## 0. Open the terminal (every time, first)

1. Windows key -> type `PowerShell` -> Enter.
2. Paste and Enter:
   ```
   cd "C:\Users\lalli\Documents\Day Trading\belief-ledger-30day"
   ```

---

## 1. THE DAILY RITUAL (~5 min, once a day, evening is fine)

Do this for 1-2 claims each trading day. A claim is a forecast about a FUTURE date.

### Step 1 - make the claim file
- In File Explorer, go to the repo folder, copy `claim_001.json`, paste, rename the copy to the
  next number: `claim_002.json` (then `claim_003.json`, etc.).
- Open it in Notepad (right-click -> Open with -> Notepad) and change the fields per the CHEAT
  SHEET in section 3. Save.

### Step 2 - check it is legal (optional but smart)
```
python -m belief_ledger.cli validate-claim claim_002.json
```
Expect `"status": "VALID"`. If it errors, it tells you which field is wrong -> fix -> re-check.

### Step 3 - register it (this commits your forecast)
```
python -m belief_ledger.cli register-claim claim_002.json
```
Expect `"status": "CLAIM_REGISTERED"`.

### Step 4 - update the public scorecard
```
python -m belief_ledger.cli generate-scorecard
```

### Step 5 - publish immediately (mandatory - every claim, right away)
```
git add -A
git commit -m "Register claim 002"
git push
```

Done. The claim is now public, timestamped, and un-editable.

---

## 2. THE RESOLVE RITUAL (~5 min, once or twice a WEEK)

When a claim's `resolve_after_utc` date has passed, resolve it. Batch several at once.

For each matured claim:
```
python -m belief_ledger.cli resolve-claim claim_002.json
```
- Expect `RESOLVED_TRUE`, `RESOLVED_FALSE`, or `VOID`.
- If it says "cannot be resolved before resolve_after_utc" -> too early, wait.
- If it says "already has a committed snapshot/resolution" -> already resolved, skip (you can't
  redo one - that's the point).

Then update + publish:
```
python -m belief_ledger.cli generate-scorecard
git add -A
git commit -m "Resolve matured claims"
git push
```

To see what's still open: run `generate-scorecard`, open `scorecards\README.md`, look at the
Claim Ledger table - anything marked `OPEN` still needs resolving once its date passes.

---

## 3. THE CHEAT SHEET - what goes in each field

Open a claim file and you'll see these. Here is exactly what is legal.

### Top level
| Field | What to put |
|---|---|
| `claim_id` | Bump the last number each claim: `...Z-002`, `...Z-003`. Keep the format `YYYY-MM-DDTHH:MM:SSZ-NNN`. |
| `registered_at_utc` | Roughly now, same format ending in `Z` (e.g. `2026-07-07T20:00:00Z`). Not critical. |
| `domain` | One of: `rates`, `equity_index`, `volatility`, `fx`, `commodity`, `cb_event`. |
| `statement_text` | Plain English of your claim. Display only. |
| `probability` | YOUR confidence it comes TRUE, between `0.01` and `0.99`. Be honest (avoid 0.9+). |
| `rationale` | 1-3 sentences: why. |

### machine_condition (the part that gets resolved)
| Field | What to put |
|---|---|
| `source_adapter` + `series_id` | A legal PAIR from the table below. |
| `observation_date` | The FUTURE date you're forecasting, `YYYY-MM-DD`. Must be a weekday (markets open). |
| `value_transform` | `raw` (the level itself) / `change_from_prior` (today minus prior day) / `pct_change_from_prior` (percent change). |
| `operator` | `GT` (>) / `GTE` (>=) / `LT` (<) / `LTE` (<=) / `EQ` (=) / `BETWEEN`. |
| `threshold` | A number. For `BETWEEN` use `[low, high]`. |
| `resolve_after_utc` | `observation_date` + 4 days, at `T12:00:00Z` (covers publish lag + weekends). |
| `missing_policy` | Always `wait_72h_then_void`. |
| `revision_policy` | Always `resolution_snapshot_committed`. |
| `rounding_policy` | Always `exact_raw_decimal`. |
| `calendar_policy` | Always `exact_date`. |

### Legal adapter + series pairs (and their domain)
| domain | source_adapter | series_id options | meaning |
|---|---|---|---|
| `rates` | `FRED_DAILY` | `DGS2`, `DGS10`, `DGS30` | 2/10/30-yr US Treasury yield (%) |
| `rates` | `FRED_MONTHLY` | `FEDFUNDS` | effective fed funds rate (monthly) |
| `equity_index` | `FRED_DAILY` | `SP500` | S&P 500 index level (daily close) |
| `volatility` | `VIX_DAILY` | `VIXCLS` | VIX close |
| `fx` | `ECB_FX_DAILY` | `USD`,`GBP`,`JPY`,`CHF`,`CAD`,`AUD`,`NOK`,`SEK` | units of that currency per 1 EUR (e.g. `USD`=EUR/USD rate) |
| `commodity` | `EIA_WTI_DAILY` | `DCOILWTICO` | WTI crude oil price (USD/bbl) |
| `cb_event` | `FRED_FED_TARGET` | `DFEDTARU`, `DFEDTARL` | Fed funds target upper / lower bound (%) |

Anything not in this table is rejected by the machine. `macro_release` (CPI/GDP) is not allowed in
this 30-day version.

---

## 4. READY-MADE TEMPLATES (copy, change the 4 marked bits)

### A. Easiest - directional, no need to know the level
Change: `claim_id`, `observation_date`, `probability`, and the `series_id`/`domain` for variety.
```json
{
  "claim_id": "2026-07-07T20:00:00Z-002",
  "registered_at_utc": "2026-07-07T20:00:00Z",
  "domain": "equity_index",
  "statement_text": "The S&P 500 (FRED SP500) will close higher on 2026-07-09 than the prior trading day.",
  "probability": 0.55,
  "rationale": "Directional call on the S&P 500.",
  "machine_condition": {
    "source_adapter": "FRED_DAILY", "series_id": "SP500",
    "observation_date": "2026-07-09", "value_transform": "change_from_prior",
    "operator": "GT", "threshold": 0,
    "resolve_after_utc": "2026-07-13T12:00:00Z",
    "missing_policy": "wait_72h_then_void", "revision_policy": "resolution_snapshot_committed",
    "rounding_policy": "exact_raw_decimal", "calendar_policy": "exact_date"
  }
}
```

### B. Level threshold - when you have a view on a number
```json
{
  "claim_id": "2026-07-07T20:05:00Z-003",
  "registered_at_utc": "2026-07-07T20:05:00Z",
  "domain": "volatility",
  "statement_text": "The VIX (VIXCLS) will close below 20 on 2026-07-09.",
  "probability": 0.6,
  "rationale": "Expect calm tape.",
  "machine_condition": {
    "source_adapter": "VIX_DAILY", "series_id": "VIXCLS",
    "observation_date": "2026-07-09", "value_transform": "raw",
    "operator": "LT", "threshold": 20,
    "resolve_after_utc": "2026-07-13T12:00:00Z",
    "missing_policy": "wait_72h_then_void", "revision_policy": "resolution_snapshot_committed",
    "rounding_policy": "exact_raw_decimal", "calendar_policy": "exact_date"
  }
}
```

### C. Range (BETWEEN)
```json
  "operator": "BETWEEN", "threshold": [4.0, 4.5]
```
(swap into a machine_condition, e.g. DGS10 will close BETWEEN 4.0 and 4.5.)

To get your >=4 domains: rotate through `equity_index` (SP500), `volatility` (VIXCLS), `rates`
(DGS10), `fx` (USD), `commodity` (DCOILWTICO). Five domains, one series each - easy variety.

---

## 5. THE RULES YOU MUST NEVER BREAK (breaking one kills the whole artifact)

1. **Never edit or delete a claim after registering it.** Made a mistake? Register a NEW claim;
   never touch the old file. (Everything is append-only.)
2. **Never back-date.** Only forecast dates that are still in the FUTURE when you register.
3. **Commit + push every claim the moment you make it.** No batching registrations for "later."
4. **Resolve everything, win or lose.** Never skip a claim because it went wrong. The misses are
   the point - they prove you're honest.
5. **You pick the claims and the probabilities.** That's the human part. (Claude may format JSON
   or word statements, but the forecast and the number are yours.)

---

## 6. TIMING - when, exactly

- **No fixed minute.** The only hard rule: register a claim BEFORE the date it forecasts.
- **Easiest habit:** each evening, make claims about a date 1-2 days out. Then you have all night,
  no deadline pressure.
- **Daily:** ~5 min, 1-2 new claims (section 1).
- **Weekly (or every few days):** ~5-10 min, resolve matured claims (section 2).
- **Day 30:** tell Claude "the 30 days are up" -> Claude adjudicates the result against the
  pre-registration (pass = you operated it honestly; the score itself is not the test).

---

## 7. WHEN TO INVOLVE CLAUDE (optional)

- Stuck on a claim? Say the belief in one line - "SPX down Friday, 55%" - and Claude returns the
  ready JSON file + the commands. You still run them.
- Something errors and you don't understand it? Paste it.
- Day 30? Claude adjudicates.
- Claude will NOT invent your forecasts or pick your probabilities - that would void the test.

---

## 8. ONE-LINE SUMMARY
Evening: copy a claim file, change 4 things, validate, register, scorecard, commit, push. Weekly:
resolve the matured ones, scorecard, commit, push. ~40 claims, >=30 resolved, >=4 domains, nothing
hidden, for 30 days. That's the machine running - and you running it is the proof.
