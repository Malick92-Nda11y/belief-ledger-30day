# Belief Ledger 30-Day Proof Artifact

This repo is the public, append-only home for the 30-day macro/markets belief ledger.

Status: build/pre-claim phase. No claims may be registered until:

1. adapters, resolver, scorer, and scorecard generator pass tests;
2. amber-source probes pass for any amber adapter admitted;
3. Research reviews resolver faithfulness to the locked pre-reg.

The locked founding pre-registration is `BELIEF_LEDGER_30DAY_PREREG.md`.

## Mechanical Law

`statement_text` is display-only. `machine_condition` is the resolution authority.

The resolver accepts only strict templates over whitelisted source adapters. Claims with free-form
sources, missing policy fields, invalid probabilities, excluded domains, or inactive adapters are
rejected before registration.

## Repo Layout

- `belief_ledger/` - deterministic resolver, adapters, scorer, and scorecard generator.
- `claims/` - future immutable claim records. Empty until Research review.
- `snapshots/` - raw source snapshots committed at resolution time.
- `resolutions/` - resolution records.
- `scorecards/` - generated public scorecards.
- `probe_results/` - amber-source probe outputs.
- `config/adapters.json` - active adapter whitelist.
- `tests/` - unit tests for schema, resolver, scorer, scorecard, and probe behavior.

## Commands

Run tests:

```powershell
python -m pytest
```

Run amber-source probe:

```powershell
python -m belief_ledger.cli probe-adapters
```

Generate a scorecard from existing claims/resolutions:

```powershell
python -m belief_ledger.cli generate-scorecard
```

No claim registration command should be used until the pre-claim review gate clears.
