# Deterministic Signal Replay

## Objective

PR6 adds `signal_replay_frame`, an immutable snapshot of the exact
`scalp_context` dictionary that was fed to `compute_scalp_summary()` when a PR4
`signal_observation` was created.

The contract is:

```text
live scalp_context
        ↓
compute_scalp_summary(ctx)
        ↓
signal_observation.evidence

same frozen ctx later
        ↓
same supported logic version
        ↓
same evidence
```

If the replayed evidence differs, the frame is not silently accepted as a new
label. Replay reports the mismatch.

## Why PR6 does not reconstruct arbitrary historical T from today's tables

A naive historical query would not be trustworthy.

Several live decision inputs are intentionally short-lived or current-state:

- `futures_trades_realtime`, `spot_trades_realtime` and order-book snapshots
  have short retention;
- `scalp_context` reads rolling windows relative to `now()`;
- `market_feed_health` stores the current aggregate health row, not a complete
  event-sourced history;
- a `data_gap` can be detected or recovered after the market interval it
  describes;
- OHLCV can be revised during its configured refresh window.

Therefore:

```text
event timestamp <= T
```

does not imply:

```text
CoinAnalyze knew this state at T
```

Reconstructing later would introduce hindsight or would become impossible once
realtime retention expires.

PR6 instead freezes the **knowledge-time input** actually consumed live.

## Scope

This is deterministic **signal-decision replay**, not a tick-by-tick exchange
simulator.

It is sufficient for PR7 backtesting because the decision kernel is pure with
respect to its `ctx` input. Execution simulation, queue position, latency,
slippage and order-book walking remain separate later work.

## Sampling and selection bias

A replay frame exists exactly when PR4 writes a `signal_observation`.

That means:

- every periodic PR4 observation has a frame;
- every semantic transition captured by PR4 has a frame;
- an evaluation that PR4 intentionally did not persist does not get a frame.

PR7 must use `is_periodic=true` as the unbiased regular research grid.
Transition frames may augment event analysis, but must not be treated as an
independent uniform sample.

This keeps replay storage aligned with the research corpus instead of creating
a second high-frequency tick archive.

## No backfill

There is intentionally no replay-frame backfill.

An old PR4 observation contains the output evidence, but not the exact raw
`scalp_context` that produced it. Reconstructing a context now from corrected
OHLCV, recovered gaps or today's health state would violate the purpose of
replay.

Observations created before PR6 remain valid for PR5 outcomes but are marked
implicitly as non-replayable because no `signal_replay_frame` exists.

## Atomic write

The frame is inserted inside `persist_signal_observations()` after the
`signal_observation` row is created and before PR5 outcome jobs are scheduled.

All three research objects therefore share the same ledger savepoint:

```text
signal_observation
        ↓
signal_replay_frame
        ↓
signal_outcome jobs
```

If frame persistence fails, that research savepoint rolls back. The outer
collector still preserves the operational `scalp_signal_snapshot` isolation
introduced in PR4, and `LAST_FLUSH["ledger"]` stops advancing so the fault is
observable.

## Frozen context

The full context object is canonicalized with:

- sorted JSON keys;
- compact separators;
- `datetime/date -> ISO-8601`;
- `None -> null`;
- NaN/Infinity rejected.

`context_hash` is SHA-256 over that canonical representation.

`context_as_of` comes from the live context's own `now_ms`; it is not invented
later from observation timestamps.

The JSON is kept intact rather than selecting only today's feature columns.
If a field is present in the decision input, the frame preserves it.

## Immutability

PostgreSQL rejects:

- `UPDATE`;
- `DELETE`;
- `TRUNCATE`.

There is one frame at most per `observation_id`.

## Versioning

Two independent versions matter:

- `signal_observation.logic_version`: decision-kernel semantics;
- `signal_replay_frame.context_version`: replay-input schema.

PR6 supports:

```text
logic_version   scalp-summary-v1
context_version 1
```

Unsupported versions fail closed.

A future material change to the decision kernel must not silently reuse the v1
label. It must bump/version the kernel and preserve the previous implementation
if old frames still need executable replay.

## Replay verification

`replay_signal_observation()` performs:

1. load immutable observation + frame;
2. require a supported context version;
3. recompute and verify `context_hash`;
4. require a supported logic version;
5. run `compute_scalp_summary(context)`;
6. canonicalize the result;
7. compare its hash with the immutable PR4 `evidence`.

For the same supported logic version:

```text
evidence_match = true
```

is the deterministic-replay invariant.

## Retention

`signal_replay_frame` is permanent initially, like `signal_observation`.

It is not part of PR3 temporal-retention allowlists. Storage growth should be
measured in production before partition/archive decisions.

The periodic baseline is about 4,320 observations/day for three symbols, plus
semantic transitions. That is intentionally much smaller than persisting a new
frame every 10 seconds.

## Rollback

PR6 is additive.

Rolling application code back to PR5 leaves existing frames untouched. During
the rollback interval, new PR4 observations will have no frames because the old
application did not capture their live context. They must remain
non-replayable; PR6 must not manufacture those contexts after redeploy.

## PR7

PR7 is implemented in [`SIGNAL_BACKTESTING.md`](SIGNAL_BACKTESTING.md).

It consumes the replayable periodic PR4 corpus plus PR5 outcomes, isolates all
research versions explicitly, reports both dense and deterministic UTC
non-overlapping sampling views, and never queries later market state to recreate
historical decision input.
