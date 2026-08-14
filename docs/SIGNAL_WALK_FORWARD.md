# Signal Walk-Forward / Out-of-Sample Engine

## Objective

PR11 adds a **walk-forward / out-of-sample (OOS) evaluation engine** on top
of the immutable PR4-PR10 research corpus. It answers one question honestly:
*does an edge that showed up in discovery still show up in data the system
had not yet seen when discovery closed?*

It does not recompute PR4-PR10 math, does not change live scoring, and does
not select a "best" model after seeing OOS results. Its own selection policy
is fixed and declared: `fixed_kernel_no_selection_v1`.

## Two stages

```text
Stage A (Freeze)                 Stage B (Evaluate)
signal_walk_forward_manifest  →  read-only paired report
immutable, hash-verified         REPEATABLE READ READ ONLY
```

### Stage A: Freeze

Freeze creates one immutable manifest row and nothing else. It may read
only:

- the PostgreSQL clock (`clock_timestamp()`);
- the earliest compatible periodic `signal_observation` (to anchor
  `discovery_start`);
- the matching `signal_replay_frame` version.

Freeze **never reads** `signal_outcome`, PR7 backtest performance, PR8
attribution, PR9 regime performance, or PR10 execution performance. A model
that could see any of those before its first OOS cutoff would not be
out-of-sample by construction.

Production default:

```text
name=pr11-fixed-kernel-v1
warmup_days=7
test_days=7
fold_count=4
min_group_n=30
horizons=1,3,5,15,30,60,120,240 (all 8 PR5 horizons)
sampling_modes=dense_periodic,utc_nonoverlap
symbols=all compatible
execution_exchanges=binance,bybit
execution_sizes_usd=1000,10000,50000,100000
fee_bps_per_side=(empty)
funding=excluded (PR10 does not model it either)
```

The first OOS cutoff is always **the next UTC minute after
`manifest.created_at + warmup_days`**. There is no CLI flag that accepts a
caller-supplied or retroactive cutoff — `WalkForwardManifestOptions` has no
`cutoff_at`/`created_at` field at all; the cutoff can only come from the live
database clock inside `freeze_walk_forward_manifest()`.

### Stage B: Evaluate

Evaluate runs strictly inside a PostgreSQL `REPEATABLE READ READ ONLY`
transaction. It performs no `INSERT`/`UPDATE`/`DELETE`/DDL and makes no
model, config or live-scoring change of any kind.

## `signal_walk_forward_manifest`

A new ordinary, append-only table:

```text
manifest_id        bigint identity primary key
manifest_version    smallint
manifest_name       text unique, ^[a-z][a-z0-9_-]{0,63}$
created_at          timestamptz
cutoff_at           timestamptz   (created_at < cutoff_at, enforced by CHECK)
warmup_days         int
test_days           int
fold_count          int
min_group_n         int
selection_policy    text = 'fixed_kernel_no_selection_v1'
manifest_hash       text unique, ^[0-9a-f]{64}$
spec                jsonb (full canonical spec, including fold boundaries)
```

`UPDATE`, `DELETE` and `TRUNCATE` are rejected with SQLSTATE `55000` by
dedicated triggers, matching the pattern already used for
`signal_observation`, `signal_replay_frame` and `signal_execution_snapshot`.

**Deploying `sql/schema.sql` never creates a manifest row.** There is no
`INSERT ... SELECT` backfill in the PR11 schema block, matching the pattern
used by every prior append-only research table in this codebase.

## Manifest hash and idempotency

`manifest_hash` is the SHA-256 of the canonical JSON (`sort_keys=True`,
compact separators, ISO-8601 timestamps, NaN/Infinity rejected) of the full
spec, which covers: spec/manifest versions, name, `created_at`,
`discovery_start`, `cutoff_at`, warmup/test/fold configuration, the exact
fold boundaries, the PR4/5/6/10 version tuple, horizons, symbol restriction,
sampling modes, the three frozen gross views, execution exchanges/sizes, the
optional frozen fee scenario, `min_group_n`, the selection policy and the
PR5 settlement-lag contract (`OUTCOME_SETTLEMENT_LAG`, imported from
`app.signal_outcomes`, never re-hardcoded as a bare 42-minute constant).

`evaluate_walk_forward()` always reloads the manifest, recomputes this hash
from the stored spec, and **fails closed** if it does not match the stored
`manifest_hash`. A directly tampered or corrupted row is rejected rather
than silently trusted.

**Idempotent reuse:** a repeated freeze with the same `manifest_name` and the
same *static* configuration (everything the caller controls: warmup/test/
fold/min-group-n, horizons, symbols, sampling modes, execution grid, fee
scenario, and the version tuple) returns the existing manifest unchanged —
same `manifest_id`, same `manifest_hash`, no new row, `reused_existing=true`.
This comparison deliberately excludes the server-computed, wall-clock-derived
fields (`created_at`, `discovery_start`, `cutoff_at`, the fold boundaries),
because those legitimately differ between two calls made at different real
times even when the caller's configuration is byte-identical. Those
time-derived fields are still part of the persisted `manifest_hash` (so a
row-level tamper is still caught), just not part of the idempotency
comparison.

**Fails closed on conflict:** a repeated freeze with the same `manifest_name`
but a *different* static configuration raises `ValueError` and creates no
row. A concurrent double-freeze race is handled with
`INSERT ... ON CONFLICT (manifest_name) DO NOTHING` followed by the same
idempotent-or-fail-closed comparison against whichever row won.

## Folds

Expanding-discovery, contiguous non-overlapping test windows:

```text
Fold 1: [discovery_start, cutoff_1)              -> [cutoff_1, cutoff_1+7d)
Fold 2: [discovery_start, cutoff_2)              -> [cutoff_2, cutoff_2+7d)
        where cutoff_2 = fold_1.test_end
Fold N: [discovery_start, cutoff_N)              -> [cutoff_N, cutoff_N+7d)
        where cutoff_N = fold_(N-1).test_end
```

Each fold stores `fold_index`, `discovery_start`, `discovery_end`,
`test_start`, `test_end`, `test_maturity_at` inside the manifest's frozen
`spec.folds` array (there is no separate SQL folds table; the folds are
deterministic given the manifest's own frozen configuration, so recomputing
them from the spec is exact and auditable).

```text
test_maturity_at = test_end + max(horizons) + OUTCOME_SETTLEMENT_LAG
```

`OUTCOME_SETTLEMENT_LAG` is imported directly from `app.signal_outcomes`
(PR5), never duplicated as a bare constant.

## Fold states

```text
discovery_collecting     now < discovery_end
test_collecting          discovery_end <= now < test_end
test_settling             test_end <= now < test_maturity_at
ready_by_clock            now >= test_maturity_at, no blocker
outcome_recovery_pending  clock-mature, but PR5 rows in the test window
                          are still status='pending'
integrity_blocked         reserved for a data-integrity blocker
```

`evaluation_ready=true` only when the final state is `ready_by_clock`. A
fold stuck on `outcome_recovery_pending` never silently reports as if it
were mature.

## Knowledge-time rules

PR5 separates scheduling time from publication time: `due_at` means an
outcome may be attempted, while `finalized_at` records when its final
`evaluated` or `not_evaluable` state actually became known. Therefore
`due_at != finalized_at`; due-ness alone never proves that final metrics
were available.

**Discovery** (rule applied against `discovery_end`): a PR5 outcome is
usable only if `out.window_end <= discovery_end` AND
`out.due_at <= discovery_end`, for the exact matching PR4/5/6 version tuple.
PR5 schedules its 42-minute settlement lag without any awareness of PR11
folds, so a row whose *price path* finished before `discovery_end` can still
have `due_at` land after it — that row was not yet knowledge-eligible at the
discovery cutoff and PR11 excludes it. `evaluate_walk_forward()` never uses
`report generated_at` to gate discovery; it uses `min(generated_at,
discovery_end)`, so a still-collecting discovery window cannot leak future
rows early.

**Test/OOS** (rule applied against `test_end` and the live report clock): an
outcome is usable only if `out.window_end <= test_end` (no forward path may
ever cross the frozen test boundary) AND `out.due_at <= report generated_at`
(it must have actually matured by the time the report runs). Unlike
discovery, the OOS knowledge cutoff is the live evaluation clock, not
`test_end`, because a test-window outcome's settlement can legitimately land
after `test_end` while its price path stayed inside the window.

For both periods, PR11 projects the row state **as of the closed
`knowledge_cutoff`**. Observation, replay-frame, and outcome rows whose
`created_at` is later than that cutoff are invisible. A current final row is
preserved as final only when `finalized_at <= knowledge_cutoff` (equality is
known). If `due_at <= knowledge_cutoff < finalized_at`, the historical row is
usable but projected to `status='pending'`; `end_price`, return, MFE, MAE, and
all other selected final metrics are cleared before downstream builders see
it. It is counted as `pending_outcome_rows`, never evaluated,
not-evaluable, or missing. Test/OOS keeps `knowledge_cutoff=generated_at`.

## Gross views

Three views, frozen before OOS and never re-derived from performance:

- `overall` — `(symbol, horizon)`
- `state` — `(symbol, state, direction, horizon)`
- `regime` — `(symbol, regime_label, direction, horizon)`

For each paired discovery/OOS group PR11 reports: `n` (actionable evaluated,
knowledge-eligible), gross expectancy, hit rate, median, p10/p90, mean
MFE/MAE, the discovery-vs-OOS expectancy difference, a retention ratio, the
hit-rate difference, sign preservation, and the `min_group_n` gate for both
sides independently.

No group is ever ranked by OOS performance and no "winner" is chosen after
seeing OOS — PR11 has exactly one fixed kernel and one fixed set of
pre-declared groupings.

### Labels

```text
positive_generalization_observed   discovery > 0 and OOS > 0
failed_to_generalize               discovery > 0 and OOS <= 0
oos_positive_without_discovery_edge discovery <= 0 and OOS > 0
non_positive_both                  discovery <= 0 and OOS <= 0
not_ready                          fold not evaluation_ready
insufficient_sample                either side below min_group_n
```

These labels are diagnostic text only. They never mutate live trading, live
scoring, or any PR4-PR10 table.

## Execution-adjusted OOS

PR11 consumes **only** immutable PR10 `signal_execution_snapshot` rows. It
never reads current `orderbook_depth` during historical evaluation.

The fixed execution dimensions are:

```text
symbol
× exchange
× size_usd
× horizon
```

with the frozen v1 execution grid:

```text
Binance / Bybit
×
$1k / $10k / $50k / $100k
```

Sampling is evaluated independently for both frozen modes:

```text
dense_periodic
utc_nonoverlap
```

`utc_nonoverlap` is clock-only:

```text
floor(epoch(observed_minute)/60) mod horizon_minutes = 0
```

Signal direction, return, regime and execution cost never affect sampling
membership.

### PR10-equivalent execution math

PR11 does **not** approximate execution-adjusted return as:

```text
PR5 gross return - 2 × cost_vs_mid
```

because PR5 gross return starts from immutable PR4 `reference_price`, while
the executable venue fill can differ from that reference before book walking
is considered.

For every cost-evaluable row PR11 preserves:

- immutable PR4 `reference_price`;
- immutable PR5 `end_price`;
- frozen PR10 directional venue `avg_price`;
- frozen `market_cost_bps_vs_mid`;
- directional insufficient-depth state.

For long:

```text
entry = frozen BUY avg_price
```

For short:

```text
entry = frozen SELL avg_price
```

PR11 reports entry implementation shortfall relative to the PR4 reference and
recomputes entry-only directional return directly from the frozen venue entry
fill and PR5 end price.

The modeled round-trip market return remains exactly the PR10 convention:

```text
symmetric_entry_book_v1
```

where the exit market cost is modeled from the frozen entry-side market-cost
evidence. It is explicitly a modeled research quantity, not realized PnL.

### Fee scenarios

Fees are never looked up or invented.

If a fee scenario was explicitly frozen into the manifest for a venue:

```text
modeled_net_after_fees_bps
=
symmetric_market_net_bps
-
2 × frozen_fee_bps_per_side
```

If no fee was frozen for that venue, fee-adjusted metrics remain `NULL`.

Funding remains excluded.

### Execution coverage semantics

Missing evidence, non-valid evidence and valid-but-insufficient depth are
different conditions and are reported separately:

```text
snapshot_missing_n
snapshot_nonvalid_n
insufficient_depth_n
n_cost_evaluable
cost_evaluable_pct
```

A stale/unavailable/missing snapshot is never relabeled as insufficient depth.

PR11 v1 does not invent a minimum execution-coverage percentage. Coverage is
reported explicitly and the minimum sample gate uses cost-evaluable rows.

## Integrity counters

## Integrity counters

Per fold, per period (discovery/test):

```text
periodic_observations
expected_outcome_rows
requested_outcome_rows
missing_or_wrong_version_outcome_rows
boundary_purged_outcome_rows
not_yet_knowledge_eligible_outcome_rows
knowledge_eligible_outcome_rows
evaluated_outcome_rows
pending_outcome_rows
not_evaluable_outcome_rows
directional_metric_anomalies
```

`expected_outcome_rows` is computed as `periodic_observations x
len(horizons)` from a single query that cross-joins the periodic cohort with
the requested horizon set and left-joins `signal_outcome`, so a horizon with
no scheduled row at all is visible as missing, not silently absent from the
denominator.

Global/fold-scoped PR10 execution integrity is also rechecked:

```text
compatible_periodic_observations
periodic_without_execution_snapshot
execution_covered_periodic_observations
execution_snapshot_cardinality_or_version_anomalies
execution_era_start
execution_era_observations_without_two_snapshots
execution_snapshot_version_excluded_rows
execution_snapshot_error_rows
future_book_timestamp_anomalies
valid_snapshot_shape_anomalies
combined_or_unknown_exchange_rows
```

Pre-PR10 rows without snapshots remain expected. Once the execution era starts,
a periodic observation that does not have exactly one compatible Binance row
and one compatible Bybit row blocks a mature OOS fold.

A mature fold is `integrity_blocked` and `evaluation_ready=false` when required
outcome-version/directional-metric integrity fails or when a blocking PR10
execution integrity counter is nonzero. No positive OOS gate can pass while a
fold is integrity-blocked.

## Production behavior expected immediately after deploy

```bash
./.venv/bin/python scripts/freeze_walk_forward_manifest.py \
  --name pr11-fixed-kernel-v1 --warmup-days 7 --test-days 7 --fold-count 4 \
  --output /tmp/pr11-manifest.json
```

No fees. Repeating the exact same command returns `reused_existing=true`,
the same `manifest_id`/`manifest_hash`, and the manifest count stays at 1.

```bash
./.venv/bin/python scripts/evaluate_walk_forward.py \
  --manifest-name pr11-fixed-kernel-v1 \
  --output /tmp/pr11-walk-forward.json --csv /tmp/pr11-walk-forward.csv
```

Immediately after release this must show:

```text
report_version=1
walk_forward_spec_version=1
manifest_version=1

gates.manifest_hash_valid=true
gates.schedule_valid=true
gates.selection_policy_is_fixed_no_selection=true
gates.first_oos_boundary_frozen_before_start=true
gates.automatic_parameter_selection=false
gates.automatic_live_model_changes=false
gates.ready_by_clock_fold_count=0
gates.evaluation_ready_fold_count=0
gates.positive_oos_gate_count=0
gates.positive_execution_oos_gate_count=0

fold1.state=discovery_collecting
```

`first_oos_cutoff_in_future=true` is useful only as an immediate-deploy
informational field. It naturally becomes false once OOS starts; the permanent
anti-look-ahead proof is the hash/schedule validation plus the frozen-boundary
gate above. **That immediate state is success.**
Do not wait 7-14 days to manufacture an OOS conclusion that the data cannot
yet support, and never report "strategy OOS validated" until a frozen fold
has actually matured by the clock.

## Rollback

PR11 is additive: one new append-only table plus read-only application
code. Rolling the application back to pre-PR11 leaves any frozen manifest
untouched (immutable, ordinary table); the older application code simply
stops referencing it. There is no destructive down-migration — the table
is never dropped by rollback, mirroring the PR4-PR10 rollback policy.

## Scope exclusions

PR11 does not: change live scoring, collectors, API/UI, or scores/weights;
alter PR5 outcome math, PR6 replay semantics, or PR7/PR8/PR9/PR10
calculations; read current `orderbook_depth`; rank groups by OOS
performance or pick a winning configuration after seeing OOS results; model
funding; or make any write other than the single explicit
`freeze_walk_forward_manifest()` call.

## PR25 addendum: spec v2 and the research visibility contract

PR25 (`docs/PR25_RESEARCH_KNOWLEDGE_TIME.md`) fixed a P1: `obs.created_at`,
`frame.created_at`, `out.created_at`/`finalized_at` are populated with
`clock_timestamp()` *before* the collector transaction commits, so they are
provenance, never proof of historical visibility. Everything above this
section describes spec v1 (`WALK_FORWARD_SPEC_VERSION = 1`), which is frozen
exactly as documented and remains the only spec version
`pr11-fixed-kernel-v1` uses.

A new `WALK_FORWARD_SPEC_VERSION_V2 = 2` requires a
`signal_research_bundle_visibility` / `signal_outcome_final_visibility`
certificate (see `app/signal_visibility.py`) instead of those created_at/
finalized_at columns, and only ever applies to `evidence_version = 6`. No
spec-v2 production manifest exists yet -- see the PR25 doc for the full
contract, the frozen scientific tuple, and the CLI flags needed to freeze one
in the future.

## PR26 addendum: spec v3 and the confirmatory contract

Everything above (spec v1) and the PR25 addendum immediately above this
section (spec v2) are frozen exactly as documented: PR26 never reinterprets
`pr11-fixed-kernel-v1`, never creates `pr11-fixed-kernel-v2`, and never
touches either spec's hash or behavior.

A new `WALK_FORWARD_SPEC_VERSION_V3 = 3` turns PR11's exploratory walk-forward
engine into a genuine confirmatory test. Spec v3 requires spec v2's exact PR25
evidence6/research_visibility1 tuple unchanged (it reuses the same
certificate-gated grid and execution-integrity fetchers), plus a fully hashed
`confirmatory_contract` pinning exactly ONE primary hypothesis: one symbol,
one horizon, one `utc_nonoverlap`-only sampling mode, one exchange, one size,
an explicit taker fee, a versioned, per-block unconditional/direction-matched
baseline (`block_unconditional_direction_matched_baseline_v1`), a frozen
non-negative `unmodeled_execution_stress_bps`, a deterministic block-bootstrap
inference engine (`block_bootstrap_v1`, Python stdlib only), and a fixed
decision policy (`two_sided_block_bootstrap_ci_vs_minimum_effect_v1`). No
field defaults from a current/live constant; every field is caller-required
and fails closed if missing -- including a structural floor on
`bootstrap_repetitions` (`>= 2`), `minimum_primary_blocks` (`>= 2`),
`minimum_execution_data_coverage_pct` (`> 0`), and `minimum_effect_bps`
(`>= 0`, so a wholly-negative CI can never PASS).

The baseline is the mean of `market_return_pct` (PR5, direction-agnostic)
across ALL compatible periodic evaluated observations in the same calendar
block -- not merely the primary row's own return, and not restricted to
actionable/long/short rows -- sign-matched to each primary row's own
direction. `primary_excess_bps = modeled_net_after_fees_bps -
unmodeled_execution_stress_bps - baseline_bps` is what the block bootstrap
actually resamples and what the decision evaluates -- PASS therefore requires
a real excess over an unconditional market control, not merely a positive raw
modeled return.

`confirmatory_state` is `not_ready` until `generated_at` reaches
`confirmatory_knowledge_cutoff` (the manifest's LAST frozen fold's own
`test_maturity_at`, read directly off the hashed fold schedule); only then
can `pass`/`fail`/`inconclusive` be computed, from OOS rows only, pooled
across every matured fold's whole calendar blocks (never raw rows, never
discovery). Every confirmatory fetch always uses that same frozen
`confirmatory_knowledge_cutoff` as its certificate-visibility cutoff, so a
source or certificate that becomes visible after it is permanently excluded
from the experiment, no matter how many times or how much later the manifest
is re-evaluated. There is no adaptive/optional stopping:
`evaluate_walk_forward(conn, manifest_name)`'s signature is unchanged, and
re-evaluating a matured manifest later always returns the identical
`confirmatory_result`. The existing exploratory gross/execution views, other
horizons/exchanges/sizes, and `positive_oos_gate_count` remain exploratory
and are structurally disconnected from the v3 decision -- see
`app/signal_confirmatory.py`.

`WALK_FORWARD_REPORT_VERSION_V3 = 3` adds four additive report keys
(`confirmatory_contract`, `confirmatory_state`, `confirmatory_knowledge_cutoff`,
`confirmatory_result`), never touching any v1/v2 report key. No spec-v3
production manifest is created by this PR. See
`docs/PR26_CONFIRMATORY_WALK_FORWARD.md` for the full contract field
reference, the exact baseline/bootstrap/decision-policy algorithms, and the
CLI flags needed to freeze one in the future.

## PR27 addendum: corrected confirmatory spec v4

Spec v3 remains published exactly as described above. PR27 does not broaden
or reinterpret it even though no production spec-v3 manifest exists. The
corrected economics and reproducibility guarantees live only in additive
`WALK_FORWARD_SPEC_VERSION_V4 = 4` / report v4.

Spec v4 uses a Binance decision-time execution-snapshot mid as the
frictionless control entry, the directional Binance VWAP as the executable
signal entry, and the same Binance outcome close for both exits. It never
uses `signal_observation.reference_price` in the primary calculation and it
fails closed for Bybit until a venue-specific outcome series exists. The
primary claim is a paired, block-resampled conjunction: the lower CI for
absolute stressed return must exceed zero **and** the lower CI for excess
over the direction-matched venue-mid control must exceed the frozen MES.

The manifest also freezes an exact scientific implementation digest,
`funding_semantics=excluded_v1`, a positive caller-supplied certificate
settlement grace, the final knowledge cutoff, and `evaluation_not_before`.
The first matured result is persisted once in an append-only PostgreSQL table;
later evaluation must reproduce it exactly or fails closed. See
`docs/PR27_CONFIRMATORY_ENDPOINT_INTEGRITY.md` for the complete long/short
algebra, decision table, identity surface, persistence transaction and
remaining calibration responsibilities. PR27 chooses no production values
and creates no production manifest.
