from app.interpretation import (
    cvd_swing_read,
    daily_flow_read,
    evaluate_setups,
    market_memory_read,
    price_barrier_read,
)


def _flow_row(
    session_date: str,
    spot: float,
    futures: float,
    price: float,
    percentile: float,
    response: str,
) -> dict:
    return {
        "session_date": session_date,
        "cvd_spot_usd": spot,
        "cvd_fut_usd": futures,
        "price_chg_pct": price,
        "cvd_spot_percentile": percentile,
        "price_response": response,
        "oi_chg_usd": 0.0,
    }


def test_daily_flow_read_does_not_call_a_selloff_a_bottom():
    result = daily_flow_read(
        [_flow_row("2026-06-24", -107_100_000, -783_700_000, -2.62, 19, "venta_con_caida")]
    )
    assert result["headline"] == "Venta spot fuerte con caída"
    assert result["state"] == "oferta"
    assert "NO ANTICIPAR SUELO" in result["action"]


def test_daily_flow_read_requires_defense_then_buying_to_flag_a_possible_reversal():
    rows = [
        _flow_row("2026-07-01", -125_800_000, -50_500_000, 0.52, 16, "venta_sin_caida"),
        _flow_row("2026-07-02", 166_400_000, 614_500_000, 4.90, 97, "compra_con_subida"),
    ]
    result = daily_flow_read(rows)
    assert result["headline"] == "Posible reversión: compra spot fuerte"
    assert result["state"] == "confirmando"
    assert result["confluence"] == "alta"
    assert "2026-07-01" in result["interpretation"]

    current_only = daily_flow_read(rows[-1:])
    assert current_only["headline"] == "Se está comprando fuerte en spot"
    assert current_only["state"] == "demanda"


def test_daily_flow_read_warns_when_strong_buying_cannot_lift_price():
    result = daily_flow_read(
        [_flow_row("2026-06-27", 33_100_000, 213_000_000, -0.12, 80, "compra_sin_subida")]
    )
    assert result["headline"] == "Compran fuerte, pero el precio no sube"
    assert result["state"] == "oferta"
    assert "NO PERSEGUIR LONG" in result["action"]


def test_daily_flow_read_keeps_direction_when_flow_misses_the_quartile_by_one_point():
    result = daily_flow_read(
        [_flow_row("2026-06-25", -92_500_000, -182_700_000, -2.10, 26, "venta_con_caida")]
    )
    assert result["headline"] == "Venden y el precio cae, sin intensidad extrema"
    assert result["state"] == "oferta"


def test_distribution_setup_becomes_primary_and_active():
    snapshot = {
        "price_dir_1h": 1,
        "oi_chg_24h_pct": 3.0,
        "fr_avg": 0.04,
        "liq_ratio_24h": 1.2,
        "oi_vol_24h_ratio": 0.8,
        "btr_15m": 0.48,
        "btr_1h": 0.50,
        "btr_24h": 0.51,
        "cvd_spot_24h": -10_000_000,
    }
    daily = [
        {"cvd_spot_usd": -i * 1_000_000, "cumulative_spot": -i * 1_000_000} for i in range(1, 7)
    ]
    result = evaluate_setups(snapshot, daily)
    assert result["primary"]["id"] == "A"
    assert result["primary"]["state"] == "activo"
    assert result["daily_streak"] == -6
    assert result["daily_slope"] < 0


def test_empty_daily_context_is_supported():
    result = evaluate_setups({}, [])
    assert result["daily_streak"] == 0
    assert result["daily_slope"] == 0
    assert len(result["setups"]) == 5
    assert all(setup["confidence"] == 0 for setup in result["setups"])


def _daily_rows(last_spot: float, falling_price: bool) -> list[dict]:
    rows = [
        {
            "session_date": f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}",
            "cvd_spot_usd": float((i % 11) - 5) * 1_000_000,
            "cvd_fut_usd": float((i % 13) - 6) * 2_000_000,
            "price_close": 100.0 + i * 0.1,
        }
        for i in range(100)
    ]
    for offset in range(3):
        rows[-3 + offset]["cvd_spot_usd"] = last_spot
        rows[-3 + offset]["price_close"] = 111.0 - offset if falling_price else 109.0 + offset
    return rows


def test_cvd_swing_detects_spot_strength_not_reflected_in_price():
    result = cvd_swing_read(_daily_rows(12_000_000, falling_price=True))
    assert result["available"] is True
    assert result["signal"] == "LONG"
    assert result["score"] >= 30
    assert result["method"]["lookback_sessions"] == 90
    assert result["horizon"] == "2 sesiones"


def test_cvd_swing_detects_price_strength_without_spot_confirmation():
    result = cvd_swing_read(_daily_rows(-12_000_000, falling_price=False))
    assert result["available"] is True
    assert result["signal"] == "SHORT"
    assert result["score"] <= -30


def test_cvd_swing_requires_full_history():
    result = cvd_swing_read(_daily_rows(1, falling_price=False)[:20])
    assert result["available"] is False


def test_price_barriers_rank_repeated_high_volume_rejections():
    rows = []
    for index in range(40):
        high, low, close, volume, cvd = 101.0, 99.0, 100.0, 1_000.0, 0.0
        if index in (8, 20, 32):
            high, close, volume, cvd = 110.0, 105.0, 2_000.0, 5_000.0
        if index in (12, 24, 36):
            low, close, volume, cvd = 90.0, 95.0, 2_000.0, -5_000.0
        rows.append(
            {
                "session_date": f"s{index:03d}",
                "price_high": high,
                "price_low": low,
                "price_close": close,
                "volume_usd": volume,
                "cvd_spot_usd": cvd,
            }
        )
    result = price_barrier_read(
        rows,
        [],
        100.0,
        {
            "volume_15m_usd": 2_000.0,
            "normal_volume_15m_usd": 1_000.0,
            "volume_multiple_15m": 2.0,
            "delta_ratio_15m": 0.2,
            "price_move_15m_pct": 0.4,
            "imbalance_l5": 0.6,
            "book_status": "ok",
        },
    )
    assert result["available"] is True
    assert result["nearest_support"]["difficulty"] == "fuerte"
    assert result["nearest_resistance"]["difficulty"] == "fuerte"
    assert result["nearest_support"]["touches"] == 3
    assert result["nearest_resistance"]["volume_multiple"] == 2.0
    assert result["live_pressure"]["breakout_up_score"] >= 70


def test_price_barriers_penalize_buy_volume_that_cannot_lift_price():
    rows = []
    for index in range(24):
        high = 110.0 if index in (6, 12, 18) else 101.0
        low = 90.0 if index in (8, 14, 20) else 99.0
        rows.append(
            {
                "session_date": f"s{index:03d}",
                "price_high": high,
                "price_low": low,
                "price_close": 100.0,
                "volume_usd": 1_000.0,
                "cvd_spot_usd": 0.0,
            }
        )
    result = price_barrier_read(
        rows,
        [],
        100.0,
        {
            "volume_multiple_15m": 1.5,
            "delta_ratio_15m": 0.2,
            "price_move_15m_pct": -0.1,
            "imbalance_l5": 0.5,
            "book_status": "ok",
        },
    )
    assert result["live_pressure"]["absorption_15m"] == "compras absorbidas"
    assert result["live_pressure"]["breakout_up_score"] < 70


def test_market_memory_returns_distinct_historical_analogs_without_calling_them_probability():
    rows = []
    for index in range(280):
        cycle = (index % 70) - 35
        close = 100 + index * 0.08 + cycle * 0.18
        rows.append(
            {
                "date": f"d{index:03d}",
                "open": close * 0.998,
                "high": close * 1.015,
                "low": close * 0.985,
                "close": close,
                "volume_usd": 1_000_000 + (index % 17) * 25_000,
            }
        )
    result = market_memory_read(rows)
    assert result["available"] is True
    assert result["coverage"]["days"] == 280
    assert 1 <= len(result["analogs"]) <= 5
    assert len({item["date"] for item in result["analogs"]}) == len(result["analogs"])
    assert "no son probabilidad" in result["warning"].lower()


def test_market_memory_requires_enough_daily_history():
    assert market_memory_read([])["available"] is False
def test_pr20_v7_setup_slope_does_not_reconnect_cumulative_segments() -> None:
    rows = [
        {"cvd_spot_usd": 1.0, "cumulative_spot": 100.0},
        {"cvd_spot_usd": 1.0, "cumulative_spot": None},
        {"cvd_spot_usd": 1.0, "cumulative_spot": -10.0},
        {"cvd_spot_usd": 1.0, "cumulative_spot": -5.0},
    ]
    result = evaluate_setups({}, rows)
    assert result["daily_slope"] == 5.0
    by_id = {item["id"]: item for item in result["setups"]}
    assert "CVD spot acumulado alcista" in by_id["B"]["matched"]
    assert "CVD spot acumulado bajista" not in by_id["A"]["matched"]
