# Signal Backtesting

## Objective

PR7 adds a **read-only research backtester** over the durable research chain:

```text
signal_replay_frame
        +
signal_observation
        +
signal_outcome
        ↓
gross signal-performance report
```

It does not rebuild historical market state from later data and does not
recompute old signals with current database rows.

The backtester evaluates what CoinAnalyze **actually decided live** and what PR5
later observed after that decision.

## Source cohort

The primary cohort is deliberately restricted to:

```text
signal_family = scalp
is_periodic = true
```

Transition-only observations are excluded from the regular statistical grid.
They remain valuable for event/episode analysis, but adding them to the periodic
grid would oversample moments where the decision changed.

Every included observation must have a `signal_replay_frame`. This means
pre-PR6 observations remain visible in corpus diagnostics but are excluded from
the replayable PR7 cohort. PR7 never backfills their missing decision-time
context.

## Version isolation

PR7 filters explicitly on all research contracts:

- `logic_version`;
- `evidence_version`;
- `sampling_version`;
- `context_version`;
- `outcome_version`.

The PR7 report spec keeps its default evidence cohort pinned to `evidence_version=1`. The live writer may advance independently; newer evidence versions must be selected explicitly until a new research spec/manifest is registered. Sampling/context/outcome remain independently version-filtered.

A future v2 corpus is not silently mixed with v1. Reports record the exact
version tuple they used and count periodic observations excluded by incompatible
versions.

## Mature outcomes only

A row enters performance statistics only when its requested PR5 job satisfies:

```text
signal_outcome.due_at <= report generated_at
```

This prevents the newest observations from lowering apparent outcome coverage
merely because their forward horizon plus PR5 settlement lag has not matured.

Mature jobs can still be:

- `evaluated`;
- `pending` because the exact path is awaiting recovery/grace;
- `not_evaluable`.

All three remain in coverage denominators. Performance metrics use evaluated
rows only and the report exposes pending/not-evaluable counts rather than
silently dropping them.

## Two sampling views

PR7 intentionally reports two views.

### `dense_periodic`

Uses every periodic observation.

This is the highest-information descriptive view, but forward windows overlap.
A 15-minute signal observed every minute produces strongly overlapping 15-minute
paths.

Therefore these rows are **observations, not independent trades**.

PR7 does not compute an equity curve, Sharpe ratio, drawdown, compounded return
or portfolio PnL from this view.

### `utc_nonoverlap`

For each horizon `N`, PR7 keeps periodic observations where:

```text
Unix-epoch UTC minute index mod N = 0
```

The selection depends only on the clock and horizon, never on state, confidence,
return, MFE or MAE.

For a given symbol/horizon, selected PR5 forward windows do not overlap. This
provides a lower-overlap robustness view without using outcome-dependent or
signal-dependent episode selection.

It is still not a claim of full statistical independence: crypto assets and
adjacent market regimes can remain correlated.

## Gross performance metrics

For actionable `long`/`short` observations with evaluated PR5 outcomes, PR7
reports:

- sample count and outcome coverage;
- gross hit rate (`directional_return_pct > 0`);
- gross expectancy = mean `directional_return_pct`;
- p10/p25/median/p75/p90 directional return;
- min/max and sample standard deviation;
- average winner / average loser;
- payoff ratio;
- observation-level profit factor;
- MFE mean/median/p75/p90;
- MAE mean/median/p75/p90.

These are **gross signal returns**.

PR7 deliberately does not apply:

- fees;
- spread;
- slippage;
- order-book walking;
- latency;
- position sizing.

Execution costs belong to PR10. Calling PR7 values net PnL would be incorrect.

## Neutral observations

`No Trade` is not converted into a fake long or short.

For evaluated neutral observations PR7 reports only direction-independent
counterfactual market movement:

- neutral sample count;
- mean absolute market return;
- median absolute market return;
- p90 absolute market return.

Directional return, MFE and MAE remain PR5 `NULL` and are never synthesized.

## Data-integrity counters

Every aggregate exposes:

- mature/evaluated/pending/not-evaluable outcome counts;
- decision evaluable/not-evaluable counts;
- actionable outcome coverage;
- actionable evaluated rows missing directional metrics;
- neutral/unavailable rows that unexpectedly contain directional metrics.

At corpus level PR7 also reports:

- periodic observations;
- pre-PR6 periodic rows without replay frames;
- version-incompatible periodic rows;
- expected vs actual requested outcome rows;
- missing/wrong-version outcome rows;
- maximum observation/outcome IDs used by the read snapshot.

A non-zero integrity-anomaly count is a data-quality problem, not a losing
strategy.

## Minimum group size

`--min-group-n` defaults to 30.

PR7 does not hide smaller groups. Instead it emits:

```text
actionable_meets_min_group_n
neutral_meets_min_group_n
```

The threshold is a reporting guardrail, not a claim that `n=30` establishes
statistical significance.

PR11 walk-forward analysis will address out-of-sample stability.

## Grouping

The CLI can group by any combination of:

- symbol;
- state;
- confidence;
- direction;
- decision_status;
- regime_label;
- reference_price_source;
- coverage_band.

`horizon_minutes` is always a grouping dimension so returns from different
forward horizons are never mixed implicitly.

The default is:

```text
symbol,state,confidence,direction
```

plus the mandatory horizon.

## Consistent database snapshot

`scripts/backtest_signals.py` runs the report inside a PostgreSQL:

```text
REPEATABLE READ READ ONLY
```

transaction.

Collectors can continue writing while the report runs, but every query in one
report sees one consistent MVCC snapshot. `generated_at` is captured once from
the database clock and becomes the maturity/window boundary for that report.

PR7 performs no INSERT, UPDATE, DELETE, schema mutation or retention action.

## Usage

Default 30-day report, both sampling views and all PR5 horizons:

```bash
python scripts/backtest_signals.py
```

BTC only:

```bash
python scripts/backtest_signals.py --symbol BTCUSDT_PERP.A
```

15m and 60m only:

```bash
python scripts/backtest_signals.py --horizon 15 --horizon 60
```

Regime analysis view:

```bash
python scripts/backtest_signals.py \
  --group-by symbol,state,direction,regime_label
```

JSON + CSV:

```bash
python scripts/backtest_signals.py \
  --output signal_backtest_report.json \
  --csv signal_backtest_groups.csv
```

## Relationship to `calibrate_signals.py`

`scripts/calibrate_signals.py` is left unchanged for compatibility, but it is
not PR7's research source of truth. It reads the short-lived operational
`scalp_signal_snapshot` and looks up later OHLCV directly.

PR7 instead uses the immutable/versioned PR4+PR5+PR6 research corpus and should
be preferred for new signal-performance work.

## No persistence yet

PR7 produces report files but does not create a database table of backtest
runs.

That is deliberate: first validate the metric contract and operational cost.
Walk-forward runs, model-selection records and calibrated probabilities are
separate later roadmap items.

## Rollback

PR7 adds only application/research code and documentation.

No database migration is required. Rolling back the application removes the CLI
from the active release but leaves PR4/PR5/PR6 data untouched.

## Next

PR8 signal attribution is implemented in
[`SIGNAL_ATTRIBUTION.md`](SIGNAL_ATTRIBUTION.md).

It uses the same version-isolated periodic corpus and frozen decision-time
evidence/context to measure component/outcome associations without changing live
weights or making causal claims.
