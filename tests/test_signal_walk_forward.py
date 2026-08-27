from __future__ import annotations

import inspect
import math
from datetime import UTC, datetime, timedelta

import pytest

from app.signal_confirmatory import (
    BLOCK_BOOTSTRAP_INFERENCE_VERSION,
    BLOCK_UNCONDITIONAL_DIRECTION_MATCHED_BASELINE_VERSION,
    CONFIRMATORY_DECISION_POLICY_V1,
    CONFIRMATORY_PRIMARY_ENDPOINT_VERSION,
    CONFIRMATORY_STATE_NOT_READY,
    ConfirmatoryContract,
    confirmatory_contract_from_dict,
    confirmatory_contract_to_dict,
)
from app.signal_execution import DENSE_PERIODIC, UTC_NONOVERLAP
from app.signal_outcomes import OUTCOME_HORIZONS_MINUTES, OUTCOME_SETTLEMENT_LAG, outcome_window
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
    WALK_FORWARD_REPORT_VERSION_V3,
    WALK_FORWARD_SPEC_VERSION,
    WALK_FORWARD_SPEC_VERSION_V2,
    WALK_FORWARD_SPEC_VERSION_V3,
    WalkForwardManifestOptions,
    _actionable_evaluated,
    _all_periodic_evaluated,
    _base_verdict_gate,
    _build_gross_views,
    _count_execution_oos_gates,
    _count_oos_gates,
    _classify_generalization,
    _compute_confirmatory_result,
    _confirmatory_outcome_integrity_for_fold,
    _execution_measure,
    _expected_utc_nonoverlap_slot_count,
    _fetch_confirmatory_primary_rows,
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
    options = WalkForwardManifestOptions(spec_version=99)
    with pytest.raises(ValueError):
        validate_manifest_options(options)


def test_supported_spec_versions_are_exactly_one_two_and_three() -> None:
    assert SUPPORTED_WALK_FORWARD_SPEC_VERSIONS == (1, 2, 3)
    assert WALK_FORWARD_SPEC_VERSION == 1
    assert WALK_FORWARD_SPEC_VERSION_V2 == 2
    assert WALK_FORWARD_SPEC_VERSION_V3 == 3


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


def _grid_rows(
    returns: list[float],
    *,
    symbol: str,
    horizon_minutes: int,
) -> list[dict]:
    """Filas de rejilla con reloj: una observacion por minuto, que es la cadencia
    real de produccion y la que produce el solapamiento."""
    return [
        {
            "symbol": symbol,
            "observed_minute": datetime.fromtimestamp(index * 60, tz=UTC),
            "horizon_minutes": horizon_minutes,
            "state": "s",
            "direction": "long",
            "regime_label": "r",
            "actionable": True,
            "usable": True,
            "status": "evaluated",
            "directional_return_pct": value,
            "mfe_pct": abs(value),
            "mae_pct": -abs(value),
        }
        for index, value in enumerate(returns)
    ]


def test_effective_n_counts_nonoverlapping_slots_not_rows() -> None:
    # 60 observaciones por minuto con horizonte 15: 60 ventanas solapadas que
    # ocupan solo 4 huecos independientes.
    stats = _group_stats(
        _grid_rows([1.0] * 60, symbol="BTCUSDT_PERP.A", horizon_minutes=15),
        min_group_n=30,
    )
    assert stats["n"] == 60
    assert stats["n_effective"] == 4

    # Con horizonte 1 no hay solapamiento: la n efectiva es la n.
    stats_h1 = _group_stats(
        _grid_rows([1.0] * 60, symbol="BTCUSDT_PERP.A", horizon_minutes=1),
        min_group_n=30,
    )
    assert stats_h1["n_effective"] == stats_h1["n"] == 60


def test_std_error_uses_effective_n_so_overlap_cannot_inflate_it() -> None:
    returns = [1.0, -1.0] * 30
    solapado = _group_stats(
        _grid_rows(returns, symbol="BTCUSDT_PERP.A", horizon_minutes=15),
        min_group_n=30,
    )
    sin_solapar = _group_stats(
        _grid_rows(returns, symbol="BTCUSDT_PERP.A", horizon_minutes=1),
        min_group_n=30,
    )
    # Misma muestra, misma desviacion; el solapado tiene MENOS informacion, asi
    # que su error estandar tiene que ser MAYOR, no menor.
    assert solapado["expectancy_std_error_pct"] > sin_solapar["expectancy_std_error_pct"]


def test_effective_n_is_not_establishable_without_a_clock() -> None:
    # Trap 7 de la casa: si no se puede situar la fila, el porton se cierra, no
    # se abre con una n inventada.
    stats = _group_stats(
        [{"directional_return_pct": 1.0, "mfe_pct": 1.0, "mae_pct": -1.0}] * 40,
        min_group_n=30,
    )
    assert stats["n"] == 40
    assert stats["n_effective"] is None
    assert stats["expectancy_std_error_pct"] is None
    assert _base_verdict_gate(1.0, None) == (None, "base_std_error_not_establishable")


def test_base_verdict_gate_declares_its_threshold_in_both_directions() -> None:
    bajo_t, motivo = _base_verdict_gate(1.0, 1.0)
    assert bajo_t == 1.0
    assert motivo == "base_not_distinguishable_from_zero"

    alto_t, sin_motivo = _base_verdict_gate(10.0, 1.0)
    assert alto_t == 10.0
    assert sin_motivo is None

    assert _base_verdict_gate(None, 1.0) == (None, "base_absent")


def test_null_base_yields_no_ratio_and_a_strong_base_still_does() -> None:
    test_grid = _grid_rows([1.0] * 120, symbol="BTCUSDT_PERP.A", horizon_minutes=1)

    # Base de puro ruido: media ~0 con dispersion. No puede sostener una razon.
    ruido = [1.0, -1.0] * 60
    nula = _build_gross_views(
        discovery_grid=_grid_rows(ruido, symbol="BTCUSDT_PERP.A", horizon_minutes=1),
        test_grid=test_grid,
        min_group_n=30,
        fold_state="ready_by_clock",
    )["overall"][0]
    assert nula["expectancy_retention_ratio"] is None
    assert nula["sign_preserved"] is None
    assert nula["base_inconclusive_reason"] == "base_not_distinguishable_from_zero"
    # La diferencia sobrevive: es legitima contra una base nula.
    assert nula["expectancy_diff_pct"] is not None

    # CONTROL POSITIVO: una base que SI se distingue de cero produce un numero.
    solida = [2.0] * 119 + [1.9]
    viva = _build_gross_views(
        discovery_grid=_grid_rows(solida, symbol="BTCUSDT_PERP.A", horizon_minutes=1),
        test_grid=test_grid,
        min_group_n=30,
        fold_state="ready_by_clock",
    )["overall"][0]
    assert viva["base_inconclusive_reason"] is None
    assert viva["expectancy_retention_ratio"] == pytest.approx(1.0 / 1.99917, rel=1e-3)
    assert viva["sign_preserved"] is True


def _gate_fold(gross: list, execution: list | None = None) -> dict:
    return {
        "gross_views": {"dense_periodic": {"overall": [
            {"positive_oos_gate_passed": v} for v in gross
        ]}},
        "execution_views": {"dense_periodic": [
            {"positive_market_cost_oos_gate_passed": v}
            for v in (execution or [])
        ]},
    }


def test_gate_count_separates_did_not_pass_from_could_not_be_measured() -> None:
    passed, evaluable, not_evaluable = _count_oos_gates(
        [_gate_fold([True, True, False, None])]
    )
    assert (passed, evaluable, not_evaluable) == (2, 3, 1)


def test_gate_count_is_none_not_zero_when_nothing_is_evaluable() -> None:
    # K60: el defecto era sumar "is True", con lo que un None contaba igual que un
    # False y el total salia 0. Un 0 se lee como "evaluado, sin ventaja".
    passed, evaluable, not_evaluable = _count_oos_gates(
        [_gate_fold([None, None, None])]
    )
    assert passed is None
    assert (evaluable, not_evaluable) == (0, 3)

    # Un cero HONESTO sigue siendo un cero: hubo medicion y ninguna paso.
    honesto, evaluable_h, _ = _count_oos_gates([_gate_fold([False, False])])
    assert honesto == 0
    assert evaluable_h == 2


def test_execution_gate_count_behaves_like_its_twin() -> None:
    assert _count_execution_oos_gates(
        [_gate_fold([], [True, False, None])]
    ) == (1, 2, 1)
    assert _count_execution_oos_gates([_gate_fold([], [None])]) == (None, 0, 1)


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


# ---------------------------------------------------------------------------
# A4-08: _expected_utc_nonoverlap_slot_count -- the deterministic expected
# research-slot count, using the exact same epoch-alignment rule as
# _sample_grid, but computed purely from the frozen fold window (no DB row).
# ---------------------------------------------------------------------------


def test_expected_utc_nonoverlap_slot_count_matches_a_hand_computed_value() -> None:
    # [epoch, epoch+30min) at a 3-minute horizon: epoch-minute multiples of 3
    # in [0, 30) are 0,3,...,27 -- 10 raw candidates. Each candidate's own
    # outcome window starts ONE MINUTE AFTER it (app.signal_outcomes.
    # outcome_window: start = minute_floor(observed_at) + 1min) and spans
    # horizon_minutes from there, so candidate i's window_end is i+1+3. The
    # trailing candidate (27) then has window_end=31, one minute past
    # test_end=30 -- boundary-purged by construction, leaving 9.
    test_start = datetime.fromtimestamp(0, tz=UTC)
    test_end = datetime.fromtimestamp(30 * 60, tz=UTC)
    assert (
        _expected_utc_nonoverlap_slot_count(
            test_start=test_start, test_end=test_end, horizon_minutes=3
        )
        == 9
    )


def test_expected_utc_nonoverlap_slot_count_excludes_deterministic_boundary_purged_slots() -> None:
    # [epoch, epoch+16min) at a 5-minute horizon: raw candidates are
    # 0,5,10,15. Candidate 10's window_end is 10+1+5=16 -- exactly equal to
    # test_end, so it is boundary-ELIGIBLE (the boundary check is <=, never
    # <). Candidate 15's window_end is 15+1+5=21, one minute past
    # test_end=16 -- boundary-PURGED, never an expected outcome. The count
    # (3: candidates 0, 5, 10) proves the purge drops exactly the trailing
    # candidate, not silently rounds the whole window away.
    test_start = datetime.fromtimestamp(0, tz=UTC)
    test_end = datetime.fromtimestamp(16 * 60, tz=UTC)
    assert (
        _expected_utc_nonoverlap_slot_count(
            test_start=test_start, test_end=test_end, horizon_minutes=5
        )
        == 3
    )


def test_expected_utc_nonoverlap_slot_count_is_zero_for_a_window_shorter_than_the_horizon() -> None:
    test_start = datetime.fromtimestamp(0, tz=UTC)
    test_end = datetime.fromtimestamp(2 * 60, tz=UTC)
    assert (
        _expected_utc_nonoverlap_slot_count(
            test_start=test_start, test_end=test_end, horizon_minutes=15
        )
        == 0
    )


def test_expected_utc_nonoverlap_slot_count_matches_sample_grid_epoch_alignment() -> None:
    # Cross-check against _sample_grid itself: build one synthetic row per
    # whole minute in [test_start, test_end), run it through the SAME
    # utc_nonoverlap sampling _fetch_period_grid_v2 would apply, keep only
    # boundary-eligible rows (window_end <= test_end), and confirm the count
    # matches the deterministic, DB-free calculation exactly.
    horizon_minutes = 5
    test_start = datetime.fromtimestamp(0, tz=UTC)
    test_end = datetime.fromtimestamp(47 * 60, tz=UTC)

    grid = []
    minute = 0
    while minute * 60 < test_end.timestamp():
        observed_minute = datetime.fromtimestamp(minute * 60, tz=UTC)
        grid.append(
            {
                "observed_minute": observed_minute,
                "horizon_minutes": horizon_minutes,
                # Real production window_end (app.signal_outcomes.outcome_window):
                # start is one minute AFTER the observed minute, not the
                # observed minute itself.
                "window_end": outcome_window(observed_minute, horizon_minutes).end,
            }
        )
        minute += 1

    sampled = _sample_grid(grid, UTC_NONOVERLAP)
    boundary_eligible = [row for row in sampled if row["window_end"] <= test_end]

    assert len(boundary_eligible) == _expected_utc_nonoverlap_slot_count(
        test_start=test_start, test_end=test_end, horizon_minutes=horizon_minutes
    )


# ---------------------------------------------------------------------------
# A4-08: _confirmatory_outcome_integrity_for_fold -- pre-filter classification
# of the sampled OOS grid. No category may silently disappear.
# ---------------------------------------------------------------------------


def _integrity_row(
    *,
    status: str | None,
    window_end: datetime,
    outcome_version: int = 1,
    actionable: bool = True,
    direction: str = "long",
    market_return_pct: float | None = 0.01,
) -> dict:
    return {
        "status": status,
        "window_end": window_end,
        "outcome_version": outcome_version,
        "actionable": actionable,
        "direction": direction,
        "market_return_pct": market_return_pct if status == "evaluated" else None,
    }


def test_confirmatory_outcome_integrity_buckets_every_boundary_eligible_row_exactly_once() -> None:
    period_end = datetime(2026, 1, 1, tzinfo=UTC)
    inside = period_end - timedelta(minutes=1)
    rows = [
        _integrity_row(status="evaluated", window_end=inside),
        _integrity_row(status="pending", window_end=inside),
        _integrity_row(status="not_evaluable", window_end=inside),
        _integrity_row(status=None, window_end=inside),  # missing outcome row
        _integrity_row(status="evaluated", window_end=inside, outcome_version=2),  # wrong version
        _integrity_row(
            status="evaluated", window_end=inside, actionable=False, direction="neutral"
        ),
    ]

    counters = _confirmatory_outcome_integrity_for_fold(
        rows, period_end=period_end, outcome_version=1
    )

    assert counters["eligible_sampled_periodic_n"] == 6
    assert counters["evaluated_periodic_n"] == 2
    assert counters["pending_periodic_n"] == 1
    assert counters["not_evaluable_periodic_n"] == 1
    assert counters["missing_or_wrong_version_n"] == 2
    assert counters["evaluated_actionable_n"] == 1
    # actionable (default True) but not evaluated: pending, not_evaluable,
    # missing, and wrong-version -- 4 rows.
    assert counters["unresolved_actionable_n"] == 4


def test_confirmatory_outcome_integrity_excludes_deterministic_boundary_purged_rows() -> None:
    period_end = datetime(2026, 1, 1, tzinfo=UTC)
    beyond = period_end + timedelta(minutes=1)
    rows = [
        _integrity_row(status="pending", window_end=beyond),
        _integrity_row(status=None, window_end=None),
    ]

    counters = _confirmatory_outcome_integrity_for_fold(
        rows, period_end=period_end, outcome_version=1
    )

    # Boundary-purged/window-less rows are never expected outcomes: every
    # counter stays zero, they must not create false incompleteness.
    assert counters == {
        "eligible_sampled_periodic_n": 0,
        "evaluated_periodic_n": 0,
        "pending_periodic_n": 0,
        "not_evaluable_periodic_n": 0,
        "missing_or_wrong_version_n": 0,
        "evaluated_actionable_n": 0,
        "unresolved_actionable_n": 0,
    }


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


# ---------------------------------------------------------------------------
# PR26: spec v3 confirmatory contract.
# ---------------------------------------------------------------------------


def _confirmatory_contract_kwargs() -> dict[str, object]:
    return {
        "primary_endpoint_version": CONFIRMATORY_PRIMARY_ENDPOINT_VERSION,
        "primary_symbol": "BTCUSDT_PERP.A",
        "primary_horizon_minutes": 15,
        "primary_sampling_mode": UTC_NONOVERLAP,
        "primary_exchange": "binance",
        "primary_size_usd": 1_000.0,
        "primary_taker_fee_bps": 2.0,
        "baseline_version": BLOCK_UNCONDITIONAL_DIRECTION_MATCHED_BASELINE_VERSION,
        "unmodeled_execution_stress_bps": 1.5,
        "inference_version": BLOCK_BOOTSTRAP_INFERENCE_VERSION,
        "block_unit": "day",
        "block_length": 1,
        "bootstrap_repetitions": 200,
        "bootstrap_seed": 12345,
        "confidence_level": 0.95,
        "minimum_effect_bps": 0.0,
        "minimum_primary_blocks": 5,
        "minimum_execution_data_coverage_pct": 50.0,
        "minimum_research_data_coverage_pct": 50.0,
        "confirmatory_decision_policy": CONFIRMATORY_DECISION_POLICY_V1,
    }


def _spec_v3_kwargs() -> dict[str, object]:
    kwargs = _spec_v2_kwargs()
    kwargs["spec_version"] = WALK_FORWARD_SPEC_VERSION_V3
    kwargs["symbols"] = ("BTCUSDT_PERP.A",)
    kwargs["fee_bps_per_side"] = (("binance", 2.0),)
    kwargs["confirmatory_contract"] = ConfirmatoryContract(**_confirmatory_contract_kwargs())
    return kwargs


def test_spec_v3_with_exact_supported_tuple_and_contract_passes() -> None:
    validate_manifest_options(WalkForwardManifestOptions(**_spec_v3_kwargs()))


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
def test_spec_v3_requires_the_exact_supported_v2_tuple(field: str) -> None:
    # Spec v3 inherits spec v2's PR25 evidence6/research_visibility1 tuple
    # exactly -- unchanged, not a new/looser tuple.
    kwargs = _spec_v3_kwargs()
    original = kwargs[field]
    kwargs[field] = f"{original}-mutated" if isinstance(original, str) else int(original) + 1
    with pytest.raises(ValueError):
        validate_manifest_options(WalkForwardManifestOptions(**kwargs))


def test_spec_v3_missing_confirmatory_contract_fails_closed() -> None:
    kwargs = _spec_v3_kwargs()
    kwargs["confirmatory_contract"] = None
    with pytest.raises(ValueError):
        validate_manifest_options(WalkForwardManifestOptions(**kwargs))


def test_confirmatory_contract_forbidden_under_spec_v1() -> None:
    options = WalkForwardManifestOptions(
        confirmatory_contract=ConfirmatoryContract(**_confirmatory_contract_kwargs())
    )
    with pytest.raises(ValueError):
        validate_manifest_options(options)


def test_confirmatory_contract_forbidden_under_spec_v2() -> None:
    kwargs = _spec_v2_kwargs()
    kwargs["confirmatory_contract"] = ConfirmatoryContract(**_confirmatory_contract_kwargs())
    with pytest.raises(ValueError):
        validate_manifest_options(WalkForwardManifestOptions(**kwargs))


@pytest.mark.parametrize(
    "kwargs_override",
    [
        {"primary_symbol": ""},
        {"primary_symbol": "ETHUSDT_PERP.A"},  # not in options.symbols
        {"primary_horizon_minutes": 7},  # not a supported horizon at all
        {"primary_horizon_minutes": 240},  # supported but not in options.horizons subset used below
        {"primary_sampling_mode": DENSE_PERIODIC},  # descriptive only, never primary
        {"primary_exchange": "okx"},
        {"primary_size_usd": 123.0},
        {"primary_taker_fee_bps": 3.0},  # diverges from frozen fee_bps_per_side
        {"baseline_version": 2},
        {"unmodeled_execution_stress_bps": -0.1},
        {"unmodeled_execution_stress_bps": float("nan")},
        {"inference_version": 2},
        {"block_unit": "week"},
        {"block_length": 0},
        {"bootstrap_repetitions": 0},
        {"bootstrap_repetitions": 1},  # P2-01: degenerate, must be >= 2
        {"bootstrap_seed": 12345.5},  # not coercible to a stable int identity below
        {"confidence_level": 0.0},
        {"confidence_level": 1.0},
        {"minimum_effect_bps": float("inf")},
        {"minimum_effect_bps": -100.0},  # P1-03: negative threshold rejected
        {"minimum_primary_blocks": 0},
        {"minimum_primary_blocks": 1},  # P2-01: degenerate, must be >= 2
        {"minimum_execution_data_coverage_pct": -1.0},
        {"minimum_execution_data_coverage_pct": 0.0},  # P2-01: must be > 0
        {"minimum_execution_data_coverage_pct": 101.0},
        {"confirmatory_decision_policy": "some_other_policy_v1"},
    ],
)
def test_confirmatory_contract_invalid_fields_fail_closed(kwargs_override: dict) -> None:
    kwargs = _spec_v3_kwargs()
    contract_kwargs = _confirmatory_contract_kwargs()
    contract_kwargs.update(kwargs_override)
    if kwargs_override.get("primary_horizon_minutes") == 240:
        # Keep 240 a globally supported horizon (so the failure is specifically
        # "not in this manifest's horizons"), but this manifest's options
        # already carries the full OUTCOME_HORIZONS_MINUTES set by default,
        # so exercise the narrower-manifest case explicitly instead.
        kwargs["horizons"] = (15,)
    kwargs["confirmatory_contract"] = ConfirmatoryContract(**contract_kwargs)
    with pytest.raises((ValueError, TypeError)):
        validate_manifest_options(WalkForwardManifestOptions(**kwargs))


def test_confirmatory_primary_fee_missing_fails_closed() -> None:
    kwargs = _spec_v3_kwargs()
    kwargs["fee_bps_per_side"] = ()  # no fee frozen for "binance" at all
    with pytest.raises(ValueError):
        validate_manifest_options(WalkForwardManifestOptions(**kwargs))


def test_confirmatory_contract_fields_are_all_scalars_not_tuples() -> None:
    # Structural guarantee that exactly ONE primary hypothesis can ever be
    # expressed: every primary_* field is a scalar type, never a
    # tuple/list/set, so there is no way to encode more than one symbol,
    # horizon, exchange, size or sampling mode as "primary".
    contract = ConfirmatoryContract(**_confirmatory_contract_kwargs())
    for name in (
        "primary_symbol",
        "primary_horizon_minutes",
        "primary_sampling_mode",
        "primary_exchange",
        "primary_size_usd",
    ):
        value = getattr(contract, name)
        assert isinstance(value, (str, int, float))
        assert not isinstance(value, (tuple, list, set, dict))


def test_confirmatory_contract_to_dict_round_trips_from_dict() -> None:
    contract = ConfirmatoryContract(**_confirmatory_contract_kwargs())
    data = confirmatory_contract_to_dict(contract)
    assert confirmatory_contract_from_dict(data) == contract


@pytest.mark.parametrize("missing_field", list(_confirmatory_contract_kwargs()))
def test_confirmatory_contract_from_dict_missing_key_fails_closed(missing_field: str) -> None:
    data = confirmatory_contract_to_dict(ConfirmatoryContract(**_confirmatory_contract_kwargs()))
    del data[missing_field]
    with pytest.raises(ValueError):
        confirmatory_contract_from_dict(data)


def test_confirmatory_contract_from_dict_unknown_key_fails_closed() -> None:
    data = confirmatory_contract_to_dict(ConfirmatoryContract(**_confirmatory_contract_kwargs()))
    data["unexpected_extra_field"] = 1
    with pytest.raises(ValueError):
        confirmatory_contract_from_dict(data)


def test_spec_v3_static_spec_includes_confirmatory_contract() -> None:
    options = WalkForwardManifestOptions(**_spec_v3_kwargs())
    spec = _static_options_spec(options)
    assert spec["spec_version"] == 3
    assert spec["confirmatory_contract"] == confirmatory_contract_to_dict(
        options.confirmatory_contract
    )
    # v3 also carries the v2 research_visibility_version key -- inherited,
    # not reinvented.
    assert "research_visibility_version" in spec["versions"]


def test_spec_v1_and_v2_static_spec_never_gain_confirmatory_contract_key() -> None:
    v1_spec = _static_options_spec(WalkForwardManifestOptions())
    assert "confirmatory_contract" not in v1_spec

    v2_spec = _static_options_spec(WalkForwardManifestOptions(**_spec_v2_kwargs()))
    assert "confirmatory_contract" not in v2_spec


@pytest.mark.parametrize("field", list(_confirmatory_contract_kwargs()))
def test_confirmatory_contract_hash_covers_every_field(field: str) -> None:
    # "v3 hash covers every confirmatory field" / "one-field mutation
    # changes manifest hash", exercised across all 18 contract fields.
    base_kwargs = _spec_v3_kwargs()
    base_hash = _spec_hash(_static_options_spec(WalkForwardManifestOptions(**base_kwargs)))

    contract_kwargs = _confirmatory_contract_kwargs()
    original = contract_kwargs[field]
    if isinstance(original, str):
        mutated = f"{original}-mutated"
    elif isinstance(original, bool):
        mutated = not original
    elif isinstance(original, int):
        mutated = original + 1
    else:
        mutated = original + 1.0
    contract_kwargs[field] = mutated

    mutated_kwargs = _spec_v3_kwargs()
    # Keep the mutated contract internally self-consistent for the fields
    # that are also cross-checked elsewhere in the options (fee, symbol,
    # horizon) so this test isolates the HASH-sensitivity question from the
    # separate validate_manifest_options cross-checks exercised above.
    if field == "primary_taker_fee_bps":
        mutated_kwargs["fee_bps_per_side"] = (("binance", mutated),)
    if field == "primary_symbol":
        mutated_kwargs["symbols"] = (mutated,)
    if field == "primary_horizon_minutes" and mutated in OUTCOME_HORIZONS_MINUTES:
        pass  # default horizons already include the full supported set
    mutated_kwargs["confirmatory_contract"] = ConfirmatoryContract(**contract_kwargs)

    mutated_hash = _spec_hash(
        _static_options_spec(WalkForwardManifestOptions(**mutated_kwargs))
    )
    assert mutated_hash != base_hash, f"hash did not change for confirmatory.{field}"


def test_options_from_spec_round_trips_spec_v3() -> None:
    options = WalkForwardManifestOptions(**_spec_v3_kwargs())
    spec = _static_options_spec(options)
    restored = _options_from_spec("pr26-spec-v3-round-trip", spec)
    assert restored.spec_version == WALK_FORWARD_SPEC_VERSION_V3
    assert restored.confirmatory_contract == options.confirmatory_contract


def test_options_from_spec_v3_missing_confirmatory_contract_fails_closed() -> None:
    options = WalkForwardManifestOptions(**_spec_v3_kwargs())
    spec = _static_options_spec(options)
    del spec["confirmatory_contract"]
    with pytest.raises(ValueError):
        _options_from_spec("pr26-spec-v3-missing-contract", spec)


@pytest.mark.parametrize("spec_kwargs_fn", [dict, _spec_v2_kwargs])
def test_options_from_spec_confirmatory_contract_forbidden_outside_v3(
    spec_kwargs_fn,
) -> None:
    options = WalkForwardManifestOptions(**spec_kwargs_fn())
    spec = _static_options_spec(options)
    spec["confirmatory_contract"] = confirmatory_contract_to_dict(
        ConfirmatoryContract(**_confirmatory_contract_kwargs())
    )
    with pytest.raises(ValueError):
        _options_from_spec("pr26-contract-forbidden-outside-v3", spec)


def test_walk_forward_report_version_v3_is_three() -> None:
    assert WALK_FORWARD_REPORT_VERSION_V3 == 3


@pytest.mark.asyncio
async def test_confirmatory_not_ready_before_final_fold_matures() -> None:
    options = WalkForwardManifestOptions(**_spec_v3_kwargs())
    contract = options.confirmatory_contract
    assert contract is not None

    # confirmatory_knowledge_cutoff is the LAST fold's own test_maturity_at,
    # read directly off fold_specs -- not derived from any live per-fold
    # clock_state/evaluation_ready summary.
    fold_specs = [
        {"fold_index": 1, "test_maturity_at": datetime(2025, 12, 1, tzinfo=UTC)},
        {"fold_index": 2, "test_maturity_at": datetime(2026, 2, 1, tzinfo=UTC)},
    ]

    class _UnusedConnection:
        async def fetch(self, *args, **kwargs):
            raise AssertionError("not_ready must never touch the database")

    result = await _compute_confirmatory_result(
        _UnusedConnection(),  # type: ignore[arg-type]
        options=options,
        contract=contract,
        fold_specs=fold_specs,
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),  # before fold_specs[-1]
    )
    assert result["confirmatory_state"] == CONFIRMATORY_STATE_NOT_READY
    assert result["confirmatory_knowledge_cutoff"] == fold_specs[-1]["test_maturity_at"]
    assert result["ci_lower_bps"] is None
    assert result["ci_upper_bps"] is None
    assert result["primary_block_count"] == 0


def test_compute_confirmatory_result_has_no_extension_parameters() -> None:
    # "No adaptive/optional stopping": there is no parameter here that could
    # request more repetitions, a longer wait, or any other after-the-fact
    # extension of an already-frozen experiment. Note "folds" (the live,
    # dynamic per-fold clock_state/evaluation_ready summaries) is
    # deliberately NOT a parameter here: the confirmatory gate/sample is a
    # pure function of the frozen fold_specs schedule and generated_at only.
    signature = inspect.signature(_compute_confirmatory_result)
    assert list(signature.parameters) == [
        "conn",
        "options",
        "contract",
        "fold_specs",
        "generated_at",
    ]


def test_confirmatory_decision_never_reads_exploratory_gate_counts() -> None:
    # Structural proof, not just a runtime test: the confirmatory decision
    # path's own source never even references the exploratory
    # positive_oos_gate_count / positive_execution_oos_gate_count counters or
    # the exploratory gross/execution views.
    source = inspect.getsource(_compute_confirmatory_result)
    for forbidden in (
        "positive_oos_gate_count",
        "positive_execution_oos_gate_count",
        "gross_views",
        "execution_views",
    ):
        assert forbidden not in source


@pytest.mark.asyncio
async def test_confirmatory_primary_rows_query_only_the_test_oos_window() -> None:
    # "primary endpoint uses OOS only": the SQL actually executed queries
    # exactly [test_start, test_end) -- never the fold's discovery window --
    # and reuses spec v2's certificate-gated grid fetcher unchanged.
    fold = {
        "fold_index": 1,
        "discovery_start": datetime(2020, 1, 1, tzinfo=UTC),
        "discovery_end": datetime(2026, 1, 25, tzinfo=UTC),
        "test_start": datetime(2026, 2, 1, tzinfo=UTC),
        "test_end": datetime(2026, 2, 8, tzinfo=UTC),
    }

    class RecordingConnection:
        def __init__(self) -> None:
            self.calls: list[tuple[str, tuple]] = []

        async def fetch(self, query: str, *args):
            self.calls.append((query, args))
            return []

    conn = RecordingConnection()
    options = WalkForwardManifestOptions(**_spec_v3_kwargs())
    contract = options.confirmatory_contract
    assert contract is not None

    fetched = await _fetch_confirmatory_primary_rows(
        conn,  # type: ignore[arg-type]
        fold=fold,
        knowledge_cutoff=datetime(2026, 2, 20, tzinfo=UTC),
        options=options,
        contract=contract,
    )

    assert fetched == {
        "primary_rows": [],
        "baseline_rows": [],
        "outcome_integrity": {
            "eligible_sampled_periodic_n": 0,
            "evaluated_periodic_n": 0,
            "pending_periodic_n": 0,
            "not_evaluable_periodic_n": 0,
            "missing_or_wrong_version_n": 0,
            "evaluated_actionable_n": 0,
            "unresolved_actionable_n": 0,
        },
    }
    assert len(conn.calls) == 1
    query, args = conn.calls[0]
    assert "signal_research_bundle_visibility" in query
    assert "signal_outcome_final_visibility" in query
    assert args[0] == fold["test_start"]
    assert args[1] == fold["test_end"]
    assert fold["discovery_start"] not in args
    assert fold["discovery_end"] not in args


def _grid_row(*, usable: bool, status: str, actionable: bool, direction: str) -> dict[str, object]:
    return {
        "observation_id": 1,
        "usable": usable,
        "status": status,
        "actionable": actionable,
        "direction": direction,
    }


def test_all_periodic_evaluated_includes_non_actionable_and_neutral_rows() -> None:
    # The P1-01 baseline cohort predicate: broader than _actionable_evaluated
    # by construction -- no actionable/direction restriction at all.
    grid = [
        _grid_row(usable=True, status="evaluated", actionable=True, direction="long"),
        _grid_row(usable=True, status="evaluated", actionable=True, direction="short"),
        _grid_row(usable=True, status="evaluated", actionable=False, direction="neutral"),
        _grid_row(usable=True, status="evaluated", actionable=False, direction="unavailable"),
        _grid_row(usable=True, status="pending", actionable=True, direction="long"),
        _grid_row(usable=False, status="evaluated", actionable=True, direction="long"),
    ]

    actionable_only = _actionable_evaluated(grid)
    all_evaluated = _all_periodic_evaluated(grid)

    assert len(actionable_only) == 2
    assert all(row["direction"] in ("long", "short") for row in actionable_only)
    assert len(all_evaluated) == 4
    assert {row["direction"] for row in all_evaluated} == {"long", "short", "neutral", "unavailable"}
    # Every actionable row is itself part of the broader cohort (superset).
    assert all(row in all_evaluated for row in actionable_only)
