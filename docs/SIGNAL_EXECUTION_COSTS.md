# Signal Execution Costs

## Objective

PR10 adds the missing execution layer between **gross research edge** and an
actually executable taker order.

PR7-PR9 deliberately stay gross. PR10 keeps those reports unchanged and adds a
separate execution-cost model based on **venue-specific order-book depth frozen
prospectively at the time a PR4 observation is written**.

The design is forward-only because the existing `orderbook_depth` table is
current-state only: one row per `symbol + exchange`, overwritten every flush.
Historical per-venue depth cannot be reconstructed truthfully after the fact.

## Why a new immutable snapshot is required

The live application already exposes current execution estimates through:

```text
execution_cost()
    -> orderbook_depth
    -> walk_book()
```

Using today's overwritten book against an old observation would create fake
historical slippage.

PR10 instead records:

```text
signal_observation
        ↓
signal_replay_frame
        ↓
signal_execution_snapshot
        ↓
signal_outcome
```

No old observation is backfilled.

## Atomic research chain

For each newly persisted PR4 observation:

```text
INSERT signal_observation
→ persist signal_replay_frame
→ persist 2 signal_execution_snapshot rows
→ schedule signal_outcomes
```

Exactly two execution rows are created:

```text
binance
bybit
```

There is no executable `combined` venue.

Missing or stale depth still creates an explicit row with an empty cost curve.
Missingness is never selected away.

## `signal_execution_snapshot`

PR10 adds an ordinary permanent append-only table keyed by:

```text
observation_id + exchange
```

It freezes:

```text
snapshot_version
captured_at
book_ts
book_age_seconds
status / reason

best bid / ask / mid / spread
reported and valid level counts
bid / ask published depth USD

source_book_hash
cost_curve
```

UPDATE, DELETE and TRUNCATE are rejected by PostgreSQL.

## Book integrity

Capture uses the same realtime clock concepts already used by the application:

```text
future by more than CLOCK_TOLERANCE_SECONDS → error
older than REALTIME_STALE_SECONDS           → stale
otherwise                                   → candidate
```

A candidate becomes `error` if either side is malformed, non-finite,
non-positive, unordered or crossed.

Only `valid` rows contain a cost curve.

## Versioned execution sizes

Snapshot v1 stores exactly:

```text
$1,000
$10,000
$50,000
$100,000
```

USD notional.

This is a research grid, not an inference about the user's position size.

For each size the snapshot stores both `buy` and `sell`, using the existing
`walk_book()` implementation.

If the published depth cannot fill the requested notional:

```text
insufficient_depth = true
```

and PR10 does not extrapolate the missing liquidity.

## Entry market cost

For buys:

```text
(VWAP_fill - venue_mid) / venue_mid × 10,000
```

For sells:

```text
(venue_mid - VWAP_fill) / venue_mid × 10,000
```

This includes spread crossing plus additional book walking.

Long observations use the buy curve. Short observations use the sell curve.

## Signal reference versus executable venue fill

PR5 gross outcomes start from the immutable PR4 `reference_price`, while a real
venue fill can differ from that reference even before book-walk cost is
considered. PR10 therefore never subtracts only `cost_vs_mid` from the PR5
return and calls the result executable.

For every cost-evaluable row it reports the entry implementation shortfall
between the actual frozen venue fill and the PR4 signal reference, and computes
the entry-only directional return directly from:

```text
frozen venue entry VWAP
+
PR5 end_price
```

This preserves venue/reference basis rather than silently assuming the signal
reference was the executable venue mid.

## Measured entry, modeled exit

PR10 measures entry depth only. PR5 has the later price path but does not freeze
a future executable book at each horizon.

Therefore PR10 never claims future exit slippage was observed.

It publishes:

```text
entry-only market overlay:
gross return bps - observed entry market cost

symmetric round-trip market overlay:
gross return bps - 2 × observed entry market cost
```

The second is explicitly:

```text
symmetric_entry_book_v1
```

and assumes exit market cost equals entry market cost.

## Fees

PR10 does not hardcode exchange fees. Fees depend on account tier and can
change.

The CLI accepts explicit taker fee scenarios:

```bash
python scripts/analyze_execution_costs.py \
  --fee-bps-per-side binance=<BPS> \
  --fee-bps-per-side bybit=<BPS>
```

If a venue fee is absent, fee-adjusted statistics stay NULL. Market-cost
statistics remain available.

Round-trip fee cost is `2 × fee_bps_per_side`.

## Funding

Funding/carry is not modeled in PR10 v1. The report says so explicitly.

Thus `modeled_net_after_fees` means gross signal return minus the symmetric
market-cost model and explicit taker fees, not fully realized account PnL.

## Reports

For each symbol/exchange/size/horizon/sampling mode PR10 reports:

- gross expectancy/hit rate;
- cost-evaluable coverage;
- insufficient-depth count;
- entry market-cost median/p90;
- entry-only market net expectancy;
- symmetric-market net expectancy/hit rate;
- optional fee-adjusted net expectancy/hit rate;
- gross-positive observations surviving market cost;
- break-even fee per side p10/median;
- spread and book-age diagnostics;
- minimum sample guardrails.

PR10 also publishes `snapshot_cost_distribution` independently of outcome
maturity so deployment can be validated immediately, before the first
horizon+42m PR5 outcomes mature.

## Research integrity

The performance cohort requires:

```text
signal_family=scalp
is_periodic=true
signal_replay_frame exists
exact versions
exactly 2 execution snapshot rows
mature PR5 outcome
```

Old pre-PR10 observations are expected to have no execution snapshot.

Integrity counters include:

```text
execution_snapshot_cardinality_or_version_anomalies
execution_era_observations_without_two_snapshots
execution_snapshot_error_rows
future_book_timestamp_anomalies
valid_snapshot_shape_anomalies
missing_or_wrong_version_outcome_rows
```

## Sampling

PR10 retains `dense_periodic` and clock-only `utc_nonoverlap`.

No execution result, signal outcome or cost is used to select the UTC sample.

## Read-only analysis

Only capture writes new execution snapshots. The reporting CLI runs in:

```text
REPEATABLE READ READ ONLY
```

## Scope exclusions

PR10 does not:

- change signal weights or thresholds;
- alter `compute_scalp_summary()` or `compute_regime()`;
- change PR5 outcome math;
- change PR6 replay/context version;
- change PR7-PR9 gross research;
- simulate maker fills;
- split orders across venues;
- model latency/adverse selection;
- model funding;
- create an equity curve;
- perform ML/calibration/walk-forward selection.

## Rollback

PR10 is additive. Existing execution snapshots remain immutable research
history after rollback. Observations produced while PR10 capture is absent must
never be backfilled later.

## Next

PR11 performs **walk-forward / out-of-sample model evaluation**, implemented
in [`SIGNAL_WALK_FORWARD.md`](SIGNAL_WALK_FORWARD.md). It consumes this
table's immutable per-venue snapshots to build a paired discovery/OOS
execution-adjusted view; it never reads current `orderbook_depth` and never
backfills execution history for observations that predate PR10.
