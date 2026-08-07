"""El perfil por nivel reparte, no inventa: lo que se comprueba aquí es el reparto."""

from app.delta_profile import (
    MIN_BARS,
    THIN_NODE_RATIO,
    bucket_index,
    bucket_size,
    profile_read,
)


def bars(count: int, low: float, high: float, volume: float, buy: float, close: float | None = None):
    return [
        {
            "ts": f"2026-08-{(index % 28) + 1:02d}T00:00:00Z",
            "low": low,
            "high": high,
            "close": close if close is not None else (low + high) / 2,
            "volume": volume,
            "buy_volume": buy,
        }
        for index in range(count)
    ]


def test_bucket_size_lands_on_readable_steps():
    assert bucket_size(0, 720) in (10.0, 20.0)
    assert bucket_size(100, 102) in (0.02, 0.05)
    assert bucket_size(50, 50) == 0.0


def test_exact_bucket_edges_do_not_fall_one_level_below():
    # 104 / 0.2 se representa como 519.9999999999999: sin tolerancia el volumen de una vela
    # que empieza justo en 104 se etiquetaba en el cubo 103.8.
    assert bucket_index(104.0, 0.2) == 520
    assert bucket_index(102.0, 0.05) == 2040
    assert bucket_index(103.9, 0.2) == 519


def test_bucket_prices_do_not_carry_float_noise():
    # 388 * 0.2 = 77.60000000000001 en coma flotante; el borde del cubo es exacto.
    result = profile_read(bars(40, 70, 80, 5, 3), "4hour", None)
    for row in result["rows"]:
        assert row["price"] == round(row["price"], 8)
        assert len(str(row["price"]).split(".")[-1]) <= 8


def test_a_short_window_is_refused_instead_of_drawn():
    result = profile_read(bars(MIN_BARS - 1, 100, 102, 10, 5), "4hour", None)
    assert result["available"] is False
    assert "se necesitan" in result["reason"]


def test_a_flat_price_has_no_profile():
    result = profile_read(bars(MIN_BARS + 5, 100, 100, 10, 5), "4hour", None)
    assert result["available"] is False


def test_volume_is_split_across_every_bucket_the_bar_crosses():
    result = profile_read(bars(40, 100, 102, 10, 10), "4hour", None)
    assert result["available"] is True
    # Nada se pierde ni se duplica al repartir: el total sigue siendo el notional de las velas.
    expected = 40 * 10 * 101
    assert abs(result["total_volume_usd"] - expected) < expected * 1e-9
    # Un rango constante reparte por igual: ningún cubo destaca sobre otro.
    volumes = {round(row["volume_usd"], 6) for row in result["rows"]}
    assert len(volumes) == 1


def test_delta_follows_the_aggressor_side():
    buying = profile_read(bars(40, 100, 102, 10, 10), "4hour", None)
    selling = profile_read(bars(40, 100, 102, 10, 0), "4hour", None)
    assert buying["net_delta_usd"] > 0
    assert selling["net_delta_usd"] < 0
    assert all(row["delta_usd"] > 0 for row in buying["rows"])
    assert all(row["delta_usd"] < 0 for row in selling["rows"])
    # Delta completo de un lado = 100% del volumen de su cubo.
    assert buying["net_delta_share_pct"] == 100.0
    assert selling["net_delta_share_pct"] == -100.0


def test_poc_is_the_busiest_level_and_the_value_area_covers_seventy_percent():
    wide = bars(40, 100, 110, 1, 0.5)
    narrow = bars(40, 104, 104.5, 40, 20)
    result = profile_read(wide + narrow, "4hour", None)
    assert result["available"] is True
    assert 104 <= result["poc"] <= 104.5
    inside = sum(row["volume_usd"] for row in result["rows"] if row["in_value_area"])
    assert inside >= result["total_volume_usd"] * 0.70
    assert result["value_area_low"] <= result["poc"] <= result["value_area_high"]


def test_thin_nodes_are_flagged_against_the_median():
    result = profile_read(bars(40, 100, 110, 1, 0.5) + bars(40, 104, 104.5, 40, 20), "4hour", None)
    median = result["median_bucket_volume_usd"]
    for row in result["rows"]:
        assert row["thin"] is (row["volume_usd"] < median * THIN_NODE_RATIO)


def test_the_reading_declares_its_approximation_and_its_venue():
    result = profile_read(bars(40, 100, 102, 10, 6), "4hour", 101.0)
    assert result["price"] == 101.0
    assert "aproximación" in result["method"]["reparto"]
    # v1.3.4: .A es Binance. Llamar a esto "compra" a secas volvería a borrar la procedencia.
    assert "futuros Binance" in result["warning"]
    assert "contado" in result["warning"]
    assert any("sesión NYSE" in item for item in result["sources"]["no_disponible"])
