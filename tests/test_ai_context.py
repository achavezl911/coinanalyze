from app.ai_context import compact_dict, normalize_profile, quality_score, rough_token_estimate


def test_normalize_profile():
    assert normalize_profile("lite") == "lite"
    assert normalize_profile("DEFAULT") == "default"


def test_compact_dict_filters_and_rounds():
    row = {"price": 1234.56789, "unused": "x", "none": None}
    assert compact_dict(row, {"price"}) == {"price": 1234.57}


def test_compact_dict_preserves_boolean_types():
    assert compact_dict({"complete": True, "stale": False}) == {
        "complete": True,
        "stale": False,
    }


def test_quality_score_degraded_when_feeds_missing():
    complete = {
        "snapshot_lag_seconds": 20,
        "spot_venues_live": 2,
        "futures_venues_live": 2,
        "book_venues_live": 2,
        "combined_book_lag_seconds": 1,
    }
    one_book = {**complete, "book_venues_live": 1}
    assert quality_score(complete) == 100
    assert quality_score(one_book) == 85
    assert (
        quality_score(
            {
                "snapshot_lag_seconds": 400,
                "spot_venues_live": 1,
                "futures_venues_live": 1,
                "book_venues_live": 0,
                "combined_book_lag_seconds": 100,
            }
        )
        < 40
    )


def test_spot_venue_confidence_uses_fresh_rows_for_the_selected_symbol() -> None:
    from pathlib import Path

    ai_source = (Path(__file__).resolve().parents[1] / "app" / "ai_context.py").read_text()
    api_source = (Path(__file__).resolve().parents[1] / "app" / "api.py").read_text()
    assert "FROM spot_trades_realtime" in ai_source
    assert "WHERE symbol=$2 AND exchange IN ('binance','bybit')" in ai_source
    assert "service IN ('ws-binance','ws-bybit') AND status='ok'" not in ai_source
    assert "await data_confidence_row(conn, selected)" in api_source
    schema = (Path(__file__).resolve().parents[1] / "sql" / "schema.sql").read_text()
    assert "'ws-binance','ws-bybit'" in schema


def test_rough_token_estimate_positive():
    assert rough_token_estimate({"a": "b"}) > 0


def test_daily_data_selects_cumulative_diff() -> None:
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "app" / "ai_context.py").read_text()
    assert "SUM(cvd_diff_usd) OVER" in source
    assert "SUM(cvd_spot_usd) OVER" in source


def test_ai_context_includes_the_cvd_90_session_read() -> None:
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "app" / "ai_context.py").read_text()
    assert '"cvd_swing_90d": cvd_swing_read(daily_rows)' in source


def test_ai_context_includes_price_barriers() -> None:
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "app" / "ai_context.py").read_text()
    assert '"price_barriers": await price_barriers(conn, symbol)' in source


def test_ai_context_includes_external_macro_filter() -> None:
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "app" / "ai_context.py").read_text()
    prompt = (Path(__file__).resolve().parents[1] / "app" / "analysis_prompt.py").read_text()
    assert '"external_macro_context": external' in source
    assert "align_with_internal" in source
    assert "nunca como gatillo de entrada" in prompt


def test_scalp_context_uses_first_chronological_price() -> None:
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "app" / "scalp_logic.py").read_text()
    assert "array_agg(last_px ORDER BY ts ASC))[1] AS first_px" in source
