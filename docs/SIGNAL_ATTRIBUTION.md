# Signal Attribution

## Objective

PR8 adds a **read-only, univariate signal-attribution report** over the same
immutable research chain used by PR7:

```text
signal_replay_frame
        +
signal_observation
        +
signal_outcome
        ↓
component/outcome associations
```

The objective is to determine whether the seven components of
`scalp-summary-v1` show useful, neutral or harmful **associations** with future
price outcomes.

PR8 does **not** claim causality and does not modify a single live score weight.

## Source cohort

The regular attribution grid uses:

```text
signal_family = scalp
is_periodic = true
signal_replay_frame exists
```

Transition-only observations remain excluded for the same reason as PR7: they
oversample moments where the semantic decision changed.

Pre-PR6 observations without a frozen replay frame remain diagnostic exclusions.
PR8 never reconstructs their context retrospectively.

Only requested PR5 outcomes satisfying:

```text
signal_outcome.due_at <= report generated_at
```

enter the attribution cohort.

Mature `pending` and `not_evaluable` jobs remain visible in coverage
denominators. Predictive metrics use only `evaluated` outcomes.

## Version-specific component extractor

PR8 attribution spec v1 is explicitly tied to:

```text
logic_version = scalp-summary-v1
```

and to the requested evidence/sampling/context/outcome versions.

A future material scoring kernel must register a new attribution extractor.
PR8 fails closed rather than applying v1 component semantics to a future v2
kernel.

## Component values

PR8 reconstructs the **normalized signed vote that actually enters
`score_component()`**, after the same `[-1,+1]` clamp.

Semantics:

```text
+1.0  strongly bullish
 0.0  measured neutral
-1.0  strongly bearish
NULL  component not measured
```

The seven v1 components and their current configured weights are:

| Component | Configured weight |
|---|---:|
| `fut_delta` | 20 |
| `spot_fut_divergence` | 15 |
| `book` | 20 |
| `absorption` | 20 |
| `liquidations` | 10 |
| `oi` | 10 |
| `vwap` | 5 |

These weights are provenance from the live v1 model. They are **not**
coefficients fitted by PR8 and PR8 never changes them.

The extractor uses only frozen decision-time material in
`signal_observation.evidence` and `signal_replay_frame.context`. It does not
query OHLCV, realtime trade tables, order books, health tables or `data_gap` to
reconstruct history.

`fut_volume_3m` is read from the frozen replay context because PR4 evidence does
not currently repeat that raw field.

## Missingness remains first-class

PR8 preserves the live distinction:

```text
NULL = not measured
0    = measured neutral
```

Each component report includes measured/missing coverage.

It also compares the reconstructed component missingness against PR4's immutable
`missing_components` array and publishes:

```text
missing_semantics_mismatch_observations
```

A non-zero value means the attribution extractor no longer reproduces the
decision-time v1 missingness contract and must be treated as a research-integrity
failure.

## Lens 1 — standalone component association

For every evaluated periodic observation, regardless of the final signal state,
the component's own bullish/bearish sign is compared with PR5
`market_return_pct`.

For a non-zero component:

```text
component > 0 → standalone directional return =  market_return_pct
component < 0 → standalone directional return = -market_return_pct
```

A zero component is a measured neutral vote and does not become a fake
directional call.

PR8 reports:

- measured/missing component coverage;
- bullish / bearish / measured-neutral counts;
- standalone directional sample count;
- standalone gross directional expectancy;
- standalone hit rate;
- p10 / median / p90 standalone directional return;
- Pearson `corr(component_value, market_return_pct)`.

This asks a narrow question:

> when this component points bullish/bearish, does the subsequent market
> movement tend to agree?

It is an observational association. It is not a simulated strategy.

## Lens 2 — agreement with the final actionable decision

For evaluated actionable `long`/`short` observations PR8 aligns each component
to the final model direction:

```text
long  → aligned_strength =  component_value
short → aligned_strength = -component_value
```

Therefore:

```text
aligned_strength > 0  component supports the final decision
aligned_strength < 0  component opposes the final decision
aligned_strength = 0  component was measured neutral
NULL                  component was unavailable
```

PR8 then reports:

- actionable evaluated count;
- component-measured actionable count;
- correlation between aligned strength and PR5 directional return;
- support count / expectancy / hit rate / mean MFE / mean MAE;
- opposition count / expectancy / hit rate / mean MFE / mean MAE;
- measured-neutral count / expectancy;
- support-minus-opposition expectancy lift;
- support-minus-opposition hit-rate lift in percentage points.

This lens asks:

> among trades the current model actually considered actionable, did agreement
> by this component associate with better or worse forward outcomes?

It is still **not causal**. Components are correlated with one another and the
final decision itself is selected using those components.

## Why PR8 does not remove components one by one

A naive leave-one-component-out replay would change the score normalization,
state threshold and sample selection simultaneously. Treating the resulting
difference as the component's causal effect would be misleading.

PR8 first measures the observed component/outcome relationships without changing
the historical decision.

A later controlled model-selection / walk-forward stage can evaluate alternative
weight sets out of sample.

## Two sampling views

PR8 mirrors PR7:

### `dense_periodic`

Every periodic observation. This maximizes descriptive sample size but forward
windows overlap.

### `utc_nonoverlap`

For horizon `N`, retain rows where:

```text
Unix-epoch UTC minute index mod N = 0
```

The selection is based only on clock and horizon. It never looks at component
value, state, confidence or outcome.

This is a lower-overlap robustness view, not a claim of full independence.

## Minimum sample guardrails

`--min-group-n` defaults to `30`.

Rows are never hidden for being small. Instead PR8 publishes explicit flags for:

- standalone component sample;
- component/market correlation sample;
- decision-conditioned measured sample;
- support sample;
- opposition sample;
- support-vs-opposition comparison.

The threshold is only a reporting guardrail.

PR8 deliberately does not compute p-values or declare statistical significance,
because dense observations are serially dependent and even the UTC
non-overlapping view can remain cross-asset/regime correlated.

## Grouping

The default grouping is:

```text
symbol
```

plus mandatory:

```text
component
horizon_minutes
```

The optional grouping dimensions are the same version-safe dimensions exposed by
PR7:

- symbol;
- state;
- confidence;
- direction;
- decision_status;
- regime_label;
- reference_price_source;
- coverage_band.

Do not over-segment early samples. A group with `n=3` remains `n=3`, no matter
how attractive its expectancy appears.

## Read-only snapshot

`scripts/attribute_signals.py` runs in one PostgreSQL:

```text
REPEATABLE READ READ ONLY
```

transaction.

Collectors can continue writing while the report sees one consistent MVCC
snapshot.

PR8 adds no table and performs no INSERT, UPDATE or DELETE.

## Usage

Default 30 days, all components, all horizons, both sampling views:

```bash
python scripts/attribute_signals.py
```

One component:

```bash
python scripts/attribute_signals.py --component book
```

Selected horizons:

```bash
python scripts/attribute_signals.py \
  --horizon 15 \
  --horizon 60
```

Regime split:

```bash
python scripts/attribute_signals.py \
  --group-by symbol,regime_label
```

JSON + CSV:

```bash
python scripts/attribute_signals.py \
  --output signal_attribution_report.json \
  --csv signal_attribution_groups.csv
```

## Interpretation rules

A result such as:

```text
book / BTC / 15m
standalone_directional_n = 240
standalone_expectancy = +0.04%
component_market_return_corr = +0.12
supports_decision_n = 90
support_expectancy = +0.08%
opposes_decision_n = 45
oppose_expectancy = -0.02%
support_minus_oppose_expectancy = +0.10%
```

means only that the book component was **associated** with better outcomes in
that sample.

It does not establish:

- causality;
- an optimal weight;
- stationarity;
- net profitability after costs;
- out-of-sample persistence.

Conversely, a negative association is not enough to delete or invert a
component.

## Scope exclusions

PR8 does not:

- alter `scalp_logic.py`;
- change weights or thresholds;
- change PR4/PR5/PR6/PR7;
- use later market-state tables for features;
- add execution costs;
- create trades or equity curves;
- perform ML;
- perform multivariate feature selection;
- perform probability calibration;
- perform walk-forward model selection.

## Rollback

PR8 is application/research code only. No schema migration is required.

Rolling back removes the attribution CLI from the active release and leaves all
PR4/PR5/PR6 data untouched.

## Next

PR9 regime-dependence analysis is implemented in
[`SIGNAL_REGIMES.md`](SIGNAL_REGIMES.md).

It conditions PR7 signal performance and PR8 component attribution on the
immutable decision-time `regime_score` / `regime_label` provenance captured by
PR4, without changing the live model. PR11 remains the point where alternative
model choices are evaluated out of sample.
