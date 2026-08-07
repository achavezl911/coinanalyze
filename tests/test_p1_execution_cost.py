"""P1: coste de ejecucion recorriendo la escalera real del libro.

Bybit entrega 50 niveles (`orderbook.50`) y `LocalBook.stats()` los truncaba a 10 al
persistir, asi que no habia forma de estimar cuanto cuesta ejecutar un tamanio concreto.
"""
from __future__ import annotations

import pytest

from app.scalp_logic import walk_book

# Escalera de asks: 1 unidad a 100, 2 a 101, 3 a 102. Notional por nivel: 100, 202, 306.
ASKS = [[100.0, 1.0], [101.0, 2.0], [102.0, 3.0]]
BIDS = [[99.0, 1.0], [98.0, 2.0], [97.0, 3.0]]


def test_un_solo_nivel_no_tiene_slippage() -> None:
    out = walk_book(ASKS, 100.0)
    assert out["levels_used"] == 1
    assert out["avg_price"] == pytest.approx(100.0)
    assert out["slippage_bps"] == pytest.approx(0.0)
    assert out["insufficient_depth"] is False


def test_el_ultimo_nivel_se_consume_parcialmente() -> None:
    """Ejecutar 201 USD toma los 100 del primer nivel y 101 del segundo = 1 unidad a 101."""
    out = walk_book(ASKS, 201.0)
    assert out["levels_used"] == 2
    # 1 unidad a 100 + 1 unidad a 101 => 2 unidades por 201 USD.
    assert out["avg_price"] == pytest.approx(201.0 / 2.0)
    assert out["slippage_bps"] == pytest.approx((100.5 - 100.0) / 100.0 * 10_000)
    assert out["shortfall_usd"] == 0.0


def test_profundidad_insuficiente_no_se_extrapola() -> None:
    """Pedir mas de lo publicado devuelve el faltante, no un precio inventado."""
    total = sum(p * q for p, q in ASKS)  # 608
    out = walk_book(ASKS, total + 500.0)
    assert out["insufficient_depth"] is True
    assert out["shortfall_usd"] == pytest.approx(500.0)
    assert out["filled_usd"] == pytest.approx(total)
    assert out["levels_used"] == len(ASKS)


def test_el_slippage_de_venta_tambien_es_coste() -> None:
    """En el bid se recorre hacia abajo: el signo se reporta positivo, es coste igual."""
    out = walk_book(BIDS, 99.0 + 98.0)
    assert out["avg_price"] < out["best_price"]
    assert out["slippage_bps"] > 0


def test_niveles_invalidos_se_ignoran_sin_romper() -> None:
    sucia = [[100.0, 1.0], [0.0, 5.0], [-1.0, 5.0], [101.0, 0.0], [101.0, 2.0]]
    out = walk_book(sucia, 201.0)
    assert out["avg_price"] == pytest.approx(100.5)
    assert out["insufficient_depth"] is False


def test_libro_vacio_no_revienta() -> None:
    out = walk_book([], 1000.0)
    assert out["avg_price"] is None
    assert out["slippage_bps"] is None
    assert out["insufficient_depth"] is True
    assert out["shortfall_usd"] == pytest.approx(1000.0)


@pytest.mark.parametrize("size", [0.0, -1.0])
def test_tamanio_no_positivo_es_error(size: float) -> None:
    with pytest.raises(ValueError, match="positive"):
        walk_book(ASKS, size)


def test_un_tamanio_mayor_nunca_cuesta_menos() -> None:
    """Monotonia: el precio medio de compra no puede mejorar al crecer el tamanio."""
    previo = 0.0
    for size in (50.0, 100.0, 150.0, 300.0, 600.0):
        out = walk_book(ASKS, size)
        assert out["avg_price"] >= previo
        previo = out["avg_price"]
