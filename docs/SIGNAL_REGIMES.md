# Signal Regime Analysis

## Objective

PR9 measures whether signal and component behavior changes across the **market
regime that CoinAnalyze actually knew at decision time**.

The source is not a retrospective reconstruction. PR4 already froze, on every
research observation:

```text
metrics_snapshot_ts
regime_score
regime_label
price_cutoff_at
metrics_cutoff_at
```

using the latest `metrics_snapshot` satisfying:

```text
metrics_snapshot.ts <= signal_observation.observed_at
```

PR9 consumes those immutable columns together with PR5 outcomes and the PR6
replayable periodic cohort.

## Why this is different from simply grouping PR7

PR7 can group gross signal performance by `regime_label`, and PR8 can group
component attribution by `regime_label`. PR9 adds a dedicated, consistent
regime contract:

- provenance integrity checks for the frozen metrics snapshot/cutoffs;
- fixed versioned score bands;
- signal performance and lift by semantic regime label;
- signal performance and lift by numeric regime score band;
- final-signal alignment versus the sign of the regime score;
- continuous regime-alignment-strength correlation;
- PR8 component attribution conditioned on the stored regime;
- explicit regime coverage and snapshot-age diagnostics.

It still does not change the live model.

## Research cohort

The regular cohort remains:

```text
signal_family = scalp
is_periodic = true
signal_replay_frame exists
```

Transition-only rows are excluded from the regular grid.

Pre-PR6 observations without a replay frame remain diagnostics only.

All research versions are isolated explicitly:

```text
logic_version
evidence_version
sampling_version
context_version
outcome_version
```

PR9 spec v1 supports the current `scalp-summary-v1` / PR8 attribution spec v1
contract only. A future material kernel requires an explicit new regime-analysis
spec.

## Frozen regime availability

A regime is `available` only if all of the following were frozen on the
observation:

- `regime_score` is present;
- `regime_label` is present and is not `Sin datos suficientes`;
- `metrics_snapshot_ts` is present and not later than `observed_at`;
- `price_cutoff_at` is present and not later than `observed_at`;
- `metrics_cutoff_at` is present and not later than `observed_at`.

Missing provenance becomes `unavailable`.

Any frozen timestamp/cutoff from the future becomes
`invalid_future_provenance` and is reported as an integrity anomaly.

PR9 never looks up a newer `metrics_snapshot` to repair an old observation.

## No arbitrary post-hoc freshness cutoff

PR9 reports:

```text
regime_snapshot_age_median_seconds
regime_snapshot_age_p90_seconds
```

but does not invent a new maximum age after seeing outcomes.

The regime stored by PR4 is what the live system knew. If later research
demonstrates that a freshness threshold is needed, that threshold must become a
prospective/versioned rule and ultimately be validated out of sample.

## Score bands

The numeric regime score is classified with fixed PR9-v1 bands:

```text
strong_bearish   score < -60
bearish          -60 <= score < -20
balanced         -20 <= score <= 20
bullish          20 < score <= 60
strong_bullish   score > 60
```

These are analysis buckets, not new trading thresholds.

They are fixed in the PR9 spec so repeated reports do not move bucket boundaries
based on the same outcomes being analyzed.

## Signal/regime alignment

For actionable long/short observations, PR9 derives regime direction from the
stored score:

```text
score > +20  bullish
score < -20  bearish
otherwise    balanced
```

Then:

```text
Long  + bullish = aligned
Short + bearish = aligned

Long  + bearish = contrarian
Short + bullish = contrarian

abs(score) <= 20 = balanced_regime
missing/invalid regime = unavailable
```

PR9 also stores the analytical quantity:

```text
regime_alignment_strength =
    decision_sign * regime_score / 100
```

so positive means regime agrees with the final actionable signal, negative means
it disagrees, and magnitude represents stored regime-score intensity.

Correlation with PR5 `directional_return_pct` is descriptive association only.

## Signal regime views

For each sampling mode PR9 reports:

### `signal_by_regime_label`

Signal outcomes by:

```text
symbol
regime_label
horizon_minutes
```

### `signal_by_regime_score_band`

Signal outcomes by:

```text
symbol
regime_score_band
horizon_minutes
```

Both include:

- mature/evaluated/pending/not-evaluable counts;
- actionable evaluated count;
- gross expectancy;
- gross hit rate;
- median directional return;
- mean and p90 MFE;
- mean and p90 MAE;
- neutral absolute market movement;
- regime snapshot age diagnostics.

Each group also gets a **lift versus the same symbol/horizon sampling-mode
baseline**:

```text
group expectancy - symbol/horizon expectancy
group hit rate   - symbol/horizon hit rate
```

The baseline includes all compatible actionable observations, including ones
whose regime is unavailable. This avoids making the reference benchmark look
better by silently deleting bad/missing-regime rows.

## Alignment view

`signal_regime_alignment` compares:

```text
aligned
contrarian
balanced_regime
unavailable
```

for actionable observations.

This is one of the most useful future PR9 questions:

> does a scalp signal perform differently when the slower 24h regime agrees
> with it versus when the signal is contrarian?

No answer is considered reliable merely because it is positive in a small
sample.

## Continuous alignment-strength view

`alignment_strength` reports, by symbol/horizon:

- available actionable sample count;
- correlation of `regime_alignment_strength` with directional return;
- mean alignment strength;
- mean absolute alignment strength.

No p-value is emitted because the dense series is serially dependent and the
UTC non-overlapping series can still have cross-asset/regime dependence.

## Component behavior by regime

PR9 reuses the exact PR8 v1 component extractor. It does **not** duplicate or
reinterpret the seven component formulas.

For each:

```text
symbol
regime_label
component
horizon_minutes
```

PR9 reports:

- component measured count;
- PR8 missing-semantics mismatch count;
- standalone directional n / expectancy / hit rate;
- component/market-return correlation;
- final-decision support and opposition counts/expectancies;
- standalone expectancy lift versus the same component across all available
  regimes.

This asks questions such as:

```text
Does book imbalance work differently in Lateral / Indecisión?
Does fut_delta become less useful during Distribución (Bearish)?
Does a component opposing the final signal become more informative in a
specific regime?
```

These remain associations, not causal effects.

## Regime distribution

`regime_distribution` uses all compatible periodic observations in the report
window, even if their PR5 forward outcomes have not matured yet.

For every symbol it shows:

- regime status;
- semantic label;
- score band;
- observation count/share;
- median/p90 snapshot age.

This separates **what regimes were observed** from **which matured outcomes are
currently available**.

## Integrity counters

The corpus reports:

```text
periodic_without_replay_frame
version_excluded_periodic_observations
regime_available_periodic_observations
regime_unavailable_periodic_observations
regime_invalid_future_provenance_observations
future_metrics_snapshot_anomalies
future_price_cutoff_anomalies
future_metrics_cutoff_anomalies
regime_score_range_anomalies
regime_label_without_score_anomalies
regime_score_without_label_anomalies
missing_or_wrong_version_outcome_rows
```

The following must be treated as research-integrity failures:

```text
future_metrics_snapshot_anomalies > 0
future_price_cutoff_anomalies > 0
future_metrics_cutoff_anomalies > 0
regime_score_range_anomalies > 0
regime_label_without_score_anomalies > 0
regime_score_without_label_anomalies > 0
missing_or_wrong_version_outcome_rows > 0
PR8 missing_semantics_mismatch_observations > 0
```

`regime_unavailable_periodic_observations > 0` is not automatically a defect.
Missing data stays missing.

## Sampling

PR9 uses the same two views as PR7 and PR8.

### `dense_periodic`

Every periodic observation. Forward windows can overlap.

### `utc_nonoverlap`

For horizon `N`:

```text
Unix-epoch UTC minute index mod N = 0
```

Selection depends only on clock and horizon, never on regime, signal,
component or outcome.

## Minimum group size

`--min-group-n` defaults to 30.

Small groups are never hidden. They receive explicit guardrail flags instead.
The threshold does not establish statistical significance.

## Read-only snapshot

`scripts/analyze_signal_regimes.py` runs in:

```text
REPEATABLE READ READ ONLY
```

against one PostgreSQL MVCC snapshot.

PR9 performs no DDL or DML.

## Usage

Default report:

```bash
python scripts/analyze_signal_regimes.py
```

Selected horizon:

```bash
python scripts/analyze_signal_regimes.py \
  --horizon 15 \
  --horizon 60
```

One asset:

```bash
python scripts/analyze_signal_regimes.py \
  --symbol BTCUSDT_PERP.A
```

One PR8 component:

```bash
python scripts/analyze_signal_regimes.py \
  --component book
```

JSON + CSV:

```bash
python scripts/analyze_signal_regimes.py \
  --output signal_regime_report.json \
  --csv signal_regime_report.csv
```

## Interpretation rules

PR9 may show, for example:

```text
BTC / Long / 15m / aligned
n = 240
expectancy = +0.08%

BTC / Long / 15m / contrarian
n = 130
expectancy = -0.01%
```

That is evidence of **regime dependence in the sample**. It is not yet evidence
that the model should block contrarian signals.

Before live behavior changes, the relationship must survive the later
walk-forward/OOS stages and execution-cost analysis.

## Scope exclusions

PR9 does not:

- modify `compute_regime()`;
- modify `compute_scalp_summary()`;
- change live weights or thresholds;
- change signal sampling;
- change PR5 outcomes;
- change PR6 replay;
- change PR7 backtesting;
- change PR8 attribution;
- add fees/slippage;
- create an equity curve;
- perform ML;
- perform probability calibration;
- perform walk-forward selection.

## Rollback

PR9 adds application/research code and documentation only. No schema migration
is required.

Rollback removes the CLI from the active release and leaves PR4/PR5/PR6 data
untouched.

## Next

PR10 execution-cost modeling is implemented in
[`SIGNAL_EXECUTION_COSTS.md`](SIGNAL_EXECUTION_COSTS.md).

It prospectively freezes venue-specific taker cost curves at observation time
because `orderbook_depth` is current-state only, then overlays those measured
entry costs and explicit fee scenarios on PR5 gross outcomes without changing
PR7-PR9 gross research metrics.

## PR25 addendum: frozen evidence -> regime_logic_version map

PR25 (`docs/PR25_RESEARCH_KNOWLEDGE_TIME.md`, A3-03) replaced the live
`REGIME_LOGIC_VERSION` comparison this reader used to make with an explicit,
frozen `FROZEN_EVIDENCE_REGIME_LOGIC_VERSION` map in `app/signal_regime.py`
(`_regime_status_sql()` no longer imports `REGIME_LOGIC_VERSION` at all). A
future bump of that live constant can no longer silently reinterpret
already-published evidence 3/4/5/6; any "modern" (evidence_version >= 3)
value outside the frozen map fails closed as `unavailable` instead of
inheriting whatever the current constant is. The `available_requires`
semantics documented above are unchanged for evidence 1/2 and for evidence
3/4/5/6 whose stored `regime_logic_version` matches the frozen value (2).
