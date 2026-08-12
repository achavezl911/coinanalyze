from __future__ import annotations

import inspect
import math
from datetime import UTC, datetime, timedelta

import pytest

from app.signal_execution import DENSE_PERIODIC, UTC_NONOVERLAP
from app.signal_outcomes import OUTCOME_HORIZONS_MINUTES, OUTCOME_SETTLEMENT_LAG
from app.signal_replay import SCALP_SIGNAL_LOGIC_VERSION
from app.signal_walk_forward import (
    DEFAULT_MANIFEST_NAME,
    SELECTION_POLICY,
    SPEC_V2_SUPPORTED_CONTEXT_VERSION,
    SPEC_V2_SUPPORTED_EVIDENCE_VERSION,
    SPEC_V2_SUPPORTED_EXECUTION_SNAPSHOT_VERSION,
    SPEC_V2_SUPPORTED_LOGIC_VERSION,
    SPEC_V2_SUPPORTED_OUTCOME_VERSION,
    SPEC_V2_SUPPORTED_RESEARCH_VISIBILITY_VERSION,
    SPEC_V2_SUPPORTED_SAMPLING_VERSION,
    SUPPORTED_WALK_FORWARD_SPEC_VERSIONS,
    WALK_FORWARD_SPEC_VERSION,
    WALK_FORWARD_SPEC_VERSION_V2,
    WalkForwardManifestOptions,
    _classify_generalization,
    _execution_measure,
    _group_stats,
    _next_minute_strictly_after,
    _options_from_spec,
    _percentile,
    _sample_grid,
    _spec_hash,
    _static_options_spec,
    compute_folds,
    evaluate_walk_forward,
    freeze_walk_forward_manifest,
    validate_manifest_options,
)


def test_default_manifest_name_is_the_fixed_production_program() -> None:
    assert DEFAULT_MANIFEST_NAME == "pr11-fixed-kernel-v1"


def test_selection_policy_is_fixed_kernel_no_selection() -> None:
    assert SELECTION_POLICY == "fixed_kernel_no_selection_v1"


def test_valid_default_options_pass_validation() -> None:
    validate_manifest_options(WalkForwardManifestOptions())


@pytest.mark.parametrize(
    "kwargs",
    [
        {"name": "PR11-Bad-Name"},
        {"name": "1-starts-with-digit"},
        {"name": "has spaces"},
        {"warmup_days": 0},
        {"test_days": 0},
        {"fold_count": 0},
        {"min_group_n": 0},
        {"horizons": ()},
        {"horizons": (1, 1)},
        {"horizons": (7,)},
        {"sampling_modes": ()},
        {"exchanges": ()},
        {"exchanges": ("okx",)},
        {"sizes_usd": ()},
        {"sizes_usd": (123.0,)},
        {"symbols": ("BTC", "BTC")},
        {"fee_bps_per_side": (("binance", -1.0),)},
        {"fee_bps_per_side": (("okx", 5.0),)},
        {"logic_version": "scalp-summary-v2"},
        {"evidence_version": 0},
    ],
)
def test_invalid_options_fail_closed(kwargs: dict) -> None:
    options = WalkForwardManifestOptions(**kwargs)
    with pytest.raises(ValueError):
        validate_manifest_options(options)


def test_no_cli_option_can_request_a_retroactive_cutoff() -> None:
    field_names = WalkForwardManifestOptions.__dataclass_fields__.keys()
    assert "cutoff_at" not in field_names
    assert "created_at" not in field_names


def test_evaluator_has_no_external_options_override() -> None:
    signature = inspect.signature(evaluate_walk_forward)
    assert list(signature.parameters) == ["conn", "manifest_name"]


@pytest.mark.asyncio
async def test_freeze_runtime_sql_reads_no_outcomes_or_performance() -> None:
    """Verify the SQL actually executed by Stage A, not comments/docstrings."""

    created_at = datetime(2026, 8, 10, 20, 0, 30, tzinfo=UTC)
    discovery_start = created_at - timedelta(hours=2)

    class RecordingConnection:
        def __init__(self) -> None:
            self.sql: list[str] = []

        async def fetchrow(self, query: str, *args):
            self.sql.append(query)
            normalized = " ".join(query.lower().split())

            if normalized.startswith(
                "select * from signal_walk_forward_manifest "
                "where manifest_name=$1"
            ):
                return None

            if "insert into signal_walk_forward_manifest" in normalized:
                (
                    manifest_version,
                    manifest_name,
                    row_created_at,
                    cutoff_at,
                    warmup_days,
                    test_days,
                    fold_count,
                    min_group_n,
                    selection_policy,
                    manifest_hash,
                    spec_json,
                ) = args
                return {
                    "manifest_id": 1,
                    "manifest_version": manifest_version,
                    "manifest_name": manifest_name,
                    "created_at": row_created_at,
                    "cutoff_at": cutoff_at,
                    "warmup_days": warmup_days,
                    "test_days": test_days,
                    "fold_count": fold_count,
                    "min_group_n": min_group_n,
                    "selection_policy": selection_policy,
                    "manifest_hash": manifest_hash,
                    "spec": spec_json,
                }

            raise AssertionError(f"unexpected fetchrow SQL: {query}")

        async def fetchval(self, query: str, *args):
            self.sql.append(query)
            normalized = " ".join(query.lower().split())

            if normalized == "select clock_timestamp()":
                assert not args
                return created_at

            if "select min(obs.observed_at)" in normalized:
                return discovery_start

            raise AssertionError(f"unexpected fetchval SQL: {query}")

    conn = RecordingConnection()
    manifest = await freeze_walk_forward_manifest(
        conn,  # type: ignore[arg-type]
        WalkForwardManifestOptions(
            name="freeze-runtime-sql-test",
            warmup_days=7,
            test_days=7,
            fold_count=1,
            horizons=(15,),
        ),
    )

    assert manifest["manifest_name"] == "freeze-runtime-sql-test"
    assert manifest["created_at"] == created_at
    assert manifest["cutoff_at"] > created_at

    executed_sql = "\n".join(conn.sql).lower()

    # Stage A may persist/read its own manifest and read the immutable
    # observation/replay anchors. It must never query performance/outcome
    # sources. This assertion intentionally examines runtime SQL only, so
    # documentation that says "never read signal_outcome" cannot false-positive.
    for forbidden in (
        "signal_outcome",
        "signal_execution_snapshot",
        "gross_expectancy",
        "signal_attribution",
        "signal_regime",
    ):
        assert forbidden not in executed_sql

    assert "signal_walk_forward_manifest" in executed_sql
    assert "signal_observation" in executed_sql
    assert "signal_replay_frame" in executed_sql


def test_next_minute_strictly_after_always_moves_forward() -> None:
    exact_minute = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    assert _next_minute_strictly_after(exact_minute) == exact_minute + timedelta(
        minutes=1
    )

    mid_minute = datetime(2026, 1, 1, 0, 0, 30, 500000, tzinfo=UTC)
    result = _next_minute_strictly_after(mid_minute)
    assert result > mid_minute
    assert result.second == 0 and result.microsecond == 0


def test_compute_folds_are_expanding_discovery_contiguous_nonoverlapping_test() -> None:
    discovery_start = datetime(2026, 1, 1, tzinfo=UTC)
    cutoff_at = datetime(2026, 1, 8, tzinfo=UTC)
    folds = compute_folds(
        discovery_start=discovery_start,
        cutoff_at=cutoff_at,
        test_days=7,
        fold_count=4,
        horizons=OUTCOME_HORIZONS_MINUTES,
    )
    assert len(folds) == 4

    for fold in folds:
        assert fold["discovery_start"] == discovery_start
        assert fold["discovery_end"] == fold["test_start"]
        assert fold["test_end"] == fold["test_start"] + timedelta(days=7)
        expected_maturity = (
            fold["test_end"]
            + timedelta(minutes=max(OUTCOME_HORIZONS_MINUTES))
            + OUTCOME_SETTLEMENT_LAG
        )
        assert fold["test_maturity_at"] == expected_maturity

    for previous, current in zip(folds, folds[1:], strict=False):
        assert current["test_start"] == previous["test_end"]
        assert current["discovery_end"] == previous["test_end"]
        assert previous["test_end"] <= current["test_start"]

    assert folds[0]["test_start"] == cutoff_at


def test_manifest_hash_changes_when_material_fields_change() -> None:
    base_hash = _spec_hash(_static_options_spec(WalkForwardManifestOptions()))
    for kwargs in (
        {"fold_count": 3},
        {"evidence_version": 2},
        {"outcome_version": 2},
        {"context_version": 2},
        {"execution_snapshot_version": 2},
        {"sizes_usd": (1_000.0, 10_000.0)},
        {"exchanges": ("binance",)},
        {"horizons": (1, 3, 5)},
        {"fee_bps_per_side": (("binance", 5.0),)},
        {"sampling_modes": (DENSE_PERIODIC,)},
    ):
        other = _spec_hash(
            _static_options_spec(WalkForwardManifestOptions(**kwargs))
        )
        assert other != base_hash, f"hash did not change for {kwargs}"


# ---------------------------------------------------------------------------
# PR25: spec v1 remains frozen; spec v2 dual support.
# ---------------------------------------------------------------------------


def test_default_options_are_spec_v1_with_no_research_visibility_version() -> None:
    options = WalkForwardManifestOptions()
    assert options.spec_version == WALK_FORWARD_SPEC_VERSION
    assert options.research_visibility_version is None


def test_spec_v1_static_spec_shape_has_no_new_keys() -> None:
    spec = _static_options_spec(WalkForwardManifestOptions())
    assert spec["spec_version"] == 1
    assert set(spec.keys()) == {
        "spec_version",
        "manifest_version",
        "warmup_days",
        "test_days",
        "fold_count",
        "min_group_n",
        "selection_policy",
        "horizons_minutes",
        "symbols",
        "sampling_modes",
        "gross_views",
        "execution_exchanges",
        "execution_sizes_usd",
        "fee_bps_per_side",
        "outcome_settlement_lag_seconds",
        "versions",
    }
    assert set(spec["versions"].keys()) == {
        "logic_version",
        "evidence_version",
        "sampling_version",
        "context_version",
        "outcome_version",
        "execution_snapshot_version",
    }
    assert "research_visibility_version" not in spec["versions"]


def test_spec_v1_hash_is_identical_before_and_after_pr25() -> None:
    # A hand-computed hash of the exact pre-PR25 v1 static spec shape (the
    # dataclass defaults are unchanged, and _static_options_spec's v1 branch
    # never adds a key), pinned so any accidental future v1 shape drift is
    # caught immediately.
    spec = _static_options_spec(WalkForwardManifestOptions())
    assert spec == {
        "spec_version": 1,
        "manifest_version": 1,
        "warmup_days": 7,
        "test_days": 7,
        "fold_count": 4,
        "min_group_n": 30,
        "selection_policy": SELECTION_POLICY,
        "horizons_minutes": sorted(OUTCOME_HORIZONS_MINUTES),
        "symbols": [],
        "sampling_modes": sorted((DENSE_PERIODIC, UTC_NONOVERLAP)),
        "gross_views": ["overall", "regime", "state"],
        "execution_exchanges": ["binance", "bybit"],
        "execution_sizes_usd": [1_000.0, 10_000.0, 50_000.0, 100_000.0],
        "fee_bps_per_side": {},
        "outcome_settlement_lag_seconds": OUTCOME_SETTLEMENT_LAG.total_seconds(),
        "versions": {
            "logic_version": SCALP_SIGNAL_LOGIC_VERSION,
            "evidence_version": 1,
            "sampling_version": 1,
            "context_version": 1,
            "outcome_version": 1,
            "execution_snapshot_version": 1,
        },
    }


def test_spec_v1_rejects_a_set_research_visibility_version() -> None:
    options = WalkForwardManifestOptions(research_visibility_version=1)
    with pytest.raises(ValueError):
        validate_manifest_options(options)


def test_unknown_spec_version_fails_closed() -> None:
    options = WalkForwardManifestOptions(spec_version=3)
    with pytest.raises(ValueError):
        validate_manifest_options(options)


def test_supported_spec_versions_are_exactly_one_and_two() -> None:
    assert SUPPORTED_WALK_FORWARD_SPEC_VERSIONS == (1, 2)
    assert WALK_FORWARD_SPEC_VERSION == 1
    assert WALK_FORWARD_SPEC_VERSION_V2 == 2


def _spec_v2_kwargs() -> dict[str, object]:
    return {
        "spec_version": WALK_FORWARD_SPEC_VERSION_V2,
        "logic_version": SPEC_V2_SUPPORTED_LOGIC_VERSION,
        "evidence_version": SPEC_V2_SUPPORTED_EVIDENCE_VERSION,
        "sampling_version": SPEC_V2_SUPPORTED_SAMPLING_VERSION,
        "context_version": SPEC_V2_SUPPORTED_CONTEXT_VERSION,
        "outcome_version": SPEC_V2_SUPPORTED_OUTCOME_VERSION,
        "execution_snapshot_version": SPEC_V2_SUPPORTED_EXECUTION_SNAPSHOT_VERSION,
        "research_visibility_version": SPEC_V2_SUPPORTED_RESEARCH_VISIBILITY_VERSION,
    }


def test_spec_v2_with_exact_supported_tuple_passes() -> None:
    validate_manifest_options(WalkForwardManifestOptions(**_spec_v2_kwargs()))


@pytest.mark.parametrize(
    "field",
    [
        "logic_version",
        "evidence_version",
        "sampling_version",
        "context_version",
        "outcome_version",
        "execution_snapshot_version",
        "research_visibility_version",
    ],
)
def test_spec_v2_requires_the_exact_supported_tuple(field: str) -> None:
    kwargs = _spec_v2_kwargs()
    original = kwargs[field]
    kwargs[field] = f"{original}-mutated" if isinstance(original, str) else int(original) + 1
    with pytest.raises(ValueError):
        validate_manifest_options(WalkForwardManifestOptions(**kwargs))


def test_spec_v2_missing_research_visibility_version_fails_closed() -> None:
    kwargs = _spec_v2_kwargs()
    kwargs["research_visibility_version"] = None
    with pytest.raises(ValueError):
        validate_manifest_options(WalkForwardManifestOptions(**kwargs))


def test_spec_v2_static_spec_includes_research_visibility_version() -> None:
    options = WalkForwardManifestOptions(**_spec_v2_kwargs())
    spec = _static_options_spec(options)
    assert spec["spec_version"] == 2
    assert (
        spec["versions"]["research_visibility_version"]
        == SPEC_V2_SUPPORTED_RESEARCH_VISIBILITY_VERSION
    )


def test_options_from_spec_round_trips_spec_v2() -> None:
    options = WalkForwardManifestOptions(**_spec_v2_kwargs())
    spec = _static_options_spec(options)
    restored = _options_from_spec("pr25-spec-v2-round-trip", spec)
    assert restored.spec_version == 2
    assert restored.research_visibility_version == SPEC_V2_SUPPORTED_RESEARCH_VISIBILITY_VERSION
    assert restored.evidence_version == SPEC_V2_SUPPORTED_EVIDENCE_VERSION


def test_options_from_spec_v2_missing_research_visibility_version_key_fails_closed() -> None:
    options = WalkForwardManifestOptions(**_spec_v2_kwargs())
    spec = _static_options_spec(options)
    del spec["versions"]["research_visibility_version"]
    with pytest.raises(ValueError):
        _options_from_spec("pr25-spec-v2-missing-key", spec)


def test_options_from_spec_unknown_spec_version_fails_closed() -> None:
    spec = _static_options_spec(WalkForwardManifestOptions())
    spec["spec_version"] = 99
    with pytest.raises(ValueError):
        _options_from_spec("pr25-unknown-spec-version", spec)


def test_spec_v2_frozen_tuple_has_exact_literal_values() -> None:
    # PR25 independent-review rework: the spec-v2 tuple must be pinned to
    # explicit literals, not derived from any module's "current" constant.
    assert SPEC_V2_SUPPORTED_LOGIC_VERSION == "scalp-summary-v1"
    assert SPEC_V2_SUPPORTED_EVIDENCE_VERSION == 6
    assert SPEC_V2_SUPPORTED_SAMPLING_VERSION == 1
    assert SPEC_V2_SUPPORTED_CONTEXT_VERSION == 1
    assert SPEC_V2_SUPPORTED_OUTCOME_VERSION == 1
    assert SPEC_V2_SUPPORTED_EXECUTION_SNAPSHOT_VERSION == 1
    assert SPEC_V2_SUPPORTED_RESEARCH_VISIBILITY_VERSION == 1


def test_spec_v2_frozen_tuple_survives_live_constant_monkeypatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A simulated future/current bump of every live scientific version
    constant must NOT reinterpret the already-frozen spec-v2 contract. The
    SPEC_V2_SUPPORTED_* constants are literals bound at import time, never
    re-read from app.signal_replay / app.signal_outcomes /
    app.signal_execution / app.signal_visibility."""

    import app.signal_execution as signal_execution_module
    import app.signal_outcomes as signal_outcomes_module
    import app.signal_replay as signal_replay_module
    import app.signal_visibility as signal_visibility_module

    monkeypatch.setattr(signal_replay_module, "SCALP_SIGNAL_LOGIC_VERSION", "scalp-summary-v2")
    monkeypatch.setattr(signal_replay_module, "REPLAY_CONTEXT_VERSION", 99)
    monkeypatch.setattr(signal_outcomes_module, "OUTCOME_VERSION", 99)
    monkeypatch.setattr(signal_execution_module, "EXECUTION_SNAPSHOT_VERSION", 99)
    monkeypatch.setattr(signal_visibility_module, "RESEARCH_VISIBILITY_VERSION", 99)

    assert SPEC_V2_SUPPORTED_LOGIC_VERSION == "scalp-summary-v1"
    assert SPEC_V2_SUPPORTED_CONTEXT_VERSION == 1
    assert SPEC_V2_SUPPORTED_OUTCOME_VERSION == 1
    assert SPEC_V2_SUPPORTED_EXECUTION_SNAPSHOT_VERSION == 1
    assert SPEC_V2_SUPPORTED_RESEARCH_VISIBILITY_VERSION == 1

    # An options object built with the historical frozen tuple still
    # validates -- the live bump above must not have broken it.
    validate_manifest_options(WalkForwardManifestOptions(**_spec_v2_kwargs()))

    # An options object that adopted the NEW "live" values instead is
    # rejected: the frozen spec-v2 contract pins the historical tuple, not
    # whatever the live constants currently say.
    kwargs = _spec_v2_kwargs()
    kwargs["logic_version"] = "scalp-summary-v2"
    kwargs["context_version"] = 99
    with pytest.raises(ValueError):
        validate_manifest_options(WalkForwardManifestOptions(**kwargs))


def test_percentile_matches_known_values() -> None:
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert _percentile(values, 0.5) == 30.0
    assert _percentile(values, 0.0) == 10.0
    assert _percentile(values, 1.0) == 50.0
    assert _percentile([], 0.5) is None
    assert _percentile([7.0], 0.9) == 7.0


def _rows(returns: list[float]) -> list[dict]:
    return [
        {
            "directional_return_pct": value,
            "mfe_pct": abs(value),
            "mae_pct": abs(value),
        }
        for value in returns
    ]


def test_group_stats_computes_expectancy_and_hit_rate() -> None:
    stats = _group_stats(_rows([1.0, -0.5, 2.0, -1.0]), min_group_n=2)
    assert stats["n"] == 4
    assert math.isclose(stats["expectancy_gross_pct"], 0.375)
    assert stats["hit_rate_pct"] == 50.0
    assert stats["meets_min_group_n"] is True


@pytest.mark.parametrize(
    ("discovery_expectancy", "test_expectancy", "expected_label", "passed"),
    [
        (1.0, 1.0, "positive_generalization_observed", True),
        (1.0, -1.0, "failed_to_generalize", False),
        (-1.0, 1.0, "oos_positive_without_discovery_edge", False),
        (-1.0, -1.0, "non_positive_both", False),
    ],
)
def test_classify_generalization_labels(
    discovery_expectancy: float,
    test_expectancy: float,
    expected_label: str,
    passed: bool,
) -> None:
    discovery = {
        "expectancy_gross_pct": discovery_expectancy,
        "meets_min_group_n": True,
    }
    test = {
        "expectancy_gross_pct": test_expectancy,
        "meets_min_group_n": True,
    }
    label, gate = _classify_generalization(
        discovery=discovery,
        test=test,
        min_group_n=30,
        fold_state="ready_by_clock",
    )
    assert label == expected_label
    assert gate is passed


def test_integrity_blocked_never_passes_generalization_gate() -> None:
    discovery = {"expectancy_gross_pct": 5.0, "meets_min_group_n": True}
    test = {"expectancy_gross_pct": 5.0, "meets_min_group_n": True}
    label, gate = _classify_generalization(
        discovery=discovery,
        test=test,
        min_group_n=30,
        fold_state="integrity_blocked",
    )
    assert label == "integrity_blocked"
    assert gate is None


def test_sampling_modes_are_distinct_and_utc_nonoverlap_is_clock_only() -> None:
    # epoch minute 9 is aligned to 3m; epoch minute 10 is not.
    aligned = datetime.fromtimestamp(9 * 60, tz=UTC)
    nonaligned = datetime.fromtimestamp(10 * 60, tz=UTC)
    grid = [
        {
            "observed_minute": aligned,
            "horizon_minutes": 3,
            "directional_return_pct": -999.0,
        },
        {
            "observed_minute": nonaligned,
            "horizon_minutes": 3,
            "directional_return_pct": 999.0,
        },
    ]

    assert _sample_grid(grid, DENSE_PERIODIC) == grid
    assert _sample_grid(grid, UTC_NONOVERLAP) == [grid[0]]

    # Changing returns must not change sampling membership.
    grid[0]["directional_return_pct"] = 999_999.0
    grid[1]["directional_return_pct"] = -999_999.0
    assert _sample_grid(grid, UTC_NONOVERLAP) == [grid[0]]


def _execution_row(
    *,
    direction: str = "long",
    reference_price: float = 99.0,
    end_price: float = 101.0,
) -> dict:
    return {
        "direction": direction,
        "reference_price": reference_price,
        "end_price": end_price,
        "directional_return_pct": 2.0202020202,
    }


def _snapshot(
    *,
    status: str = "valid",
    avg_price: float = 100.05,
    market_cost_bps: float = 5.0,
    insufficient_depth: bool = False,
) -> dict:
    return {
        "status": status,
        "cost_curve": {
            "1000": {
                "buy": {
                    "avg_price": avg_price,
                    "market_cost_bps_vs_mid": market_cost_bps,
                    "insufficient_depth": insufficient_depth,
                },
                "sell": {
                    "avg_price": 99.95,
                    "market_cost_bps_vs_mid": market_cost_bps,
                    "insufficient_depth": insufficient_depth,
                },
            }
        },
    }


def test_execution_math_uses_venue_fill_not_gross_minus_cost() -> None:
    row = _execution_row(reference_price=99.0, end_price=101.0)
    measure = _execution_measure(
        row,
        _snapshot(avg_price=100.05, market_cost_bps=5.0),
        size_usd=1000.0,
        fee_bps_per_side=None,
    )

    expected_entry_only = (101.0 / 100.05 - 1.0) * 10_000.0
    expected_symmetric = (
        (101.0 * (1.0 - 5.0 / 10_000.0)) / 100.05 - 1.0
    ) * 10_000.0
    old_wrong_formula = row["directional_return_pct"] * 100.0 - 10.0

    assert measure["cost_evaluable"] is True
    assert measure["entry_only_market_net_bps"] == pytest.approx(
        expected_entry_only
    )
    assert measure["symmetric_market_net_bps"] == pytest.approx(
        expected_symmetric
    )
    assert measure["symmetric_market_net_bps"] != pytest.approx(
        old_wrong_formula
    )
    assert measure["entry_implementation_shortfall_bps"] == pytest.approx(
        (100.05 / 99.0 - 1.0) * 10_000.0
    )


def test_frozen_fee_is_applied_only_when_present() -> None:
    row = _execution_row()
    without_fee = _execution_measure(
        row,
        _snapshot(),
        size_usd=1000.0,
        fee_bps_per_side=None,
    )
    with_fee = _execution_measure(
        row,
        _snapshot(),
        size_usd=1000.0,
        fee_bps_per_side=2.5,
    )

    assert without_fee["modeled_net_after_fees_bps"] is None
    assert with_fee["modeled_net_after_fees_bps"] == pytest.approx(
        with_fee["symmetric_market_net_bps"] - 5.0
    )


def test_missing_nonvalid_and_insufficient_depth_are_distinct() -> None:
    row = _execution_row()

    missing = _execution_measure(
        row,
        None,
        size_usd=1000.0,
        fee_bps_per_side=None,
    )
    assert missing["snapshot_missing"] is True
    assert missing["snapshot_nonvalid"] is False
    assert missing["insufficient_depth"] is False

    stale = _execution_measure(
        row,
        _snapshot(status="stale"),
        size_usd=1000.0,
        fee_bps_per_side=None,
    )
    assert stale["snapshot_missing"] is False
    assert stale["snapshot_nonvalid"] is True
    assert stale["insufficient_depth"] is False

    shallow = _execution_measure(
        row,
        _snapshot(insufficient_depth=True),
        size_usd=1000.0,
        fee_bps_per_side=None,
    )
    assert shallow["snapshot_missing"] is False
    assert shallow["snapshot_nonvalid"] is False
    assert shallow["insufficient_depth"] is True
