"""P0: el dashboard no debe publicar como fiable un dato que no lo es.

Dos defectos medidos sobre la instalacion viva del 2026-08-06:

1. El basis se calculaba con el ultimo precio negociado de cada pata SIN mirar el reloj.
   Si el feed de spot se caia, el panel seguia mostrando un numero que era la deriva del
   perp contra un precio congelado.
2. La cobertura de una ventana se decidia con MIN(ts)/MAX(ts), asi que una ventana que
   atravesaba una caida del collector salia `complete`. Medido: `ohlcv` 1min acumula 3
   huecos en 14 dias y el mayor es de 2 h 44 min.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.scalp_logic import (
    REALTIME_STALE_SECONDS,
    _gap_too_large,
    basis_quality,
)

ROOT = Path(__file__).resolve().parents[1]
NOW_MS = 1_786_056_654_685.0


def test_basis_valid_con_ambas_patas_frescas() -> None:
    out = basis_quality(64_400.0, 64_350.0, NOW_MS - 8_000, NOW_MS - 8_200, NOW_MS)
    assert out["status"] == "VALID"
    assert out["basis_bps"] == pytest.approx((64_400 - 64_350) / 64_350 * 10_000)


@pytest.mark.parametrize("leg", ["fut", "spot"])
def test_basis_no_se_publica_con_una_pata_desfasada(leg: str) -> None:
    """El caso que motiva el P0: una pata congelada y la otra viva."""
    old = NOW_MS - (REALTIME_STALE_SECONDS + 5) * 1000
    fresh = NOW_MS - 8_000
    fut_ms, spot_ms = (old, fresh) if leg == "fut" else (fresh, old)
    out = basis_quality(64_400.0, 64_350.0, fut_ms, spot_ms, NOW_MS)
    assert out["status"] == "STALE"
    assert out["basis_bps"] is None, "un basis desfasado no puede publicarse como numero"


@pytest.mark.parametrize(
    ("fut_px", "spot_px", "fut_ms", "spot_ms"),
    [
        (None, 64_350.0, NOW_MS, NOW_MS),
        (64_400.0, None, NOW_MS, NOW_MS),
        (64_400.0, 64_350.0, None, NOW_MS),
        (64_400.0, 64_350.0, NOW_MS, None),
    ],
)
def test_basis_unavailable_cuando_falta_una_pata(fut_px, spot_px, fut_ms, spot_ms) -> None:
    out = basis_quality(fut_px, spot_px, fut_ms, spot_ms, NOW_MS)
    assert out["status"] == "UNAVAILABLE"
    assert out["basis_bps"] is None


def test_el_skew_entre_patas_no_invalida_el_basis() -> None:
    """Medido: el skew esta acotado por la rejilla de 5 s (p50 0.4-0.8 s, maximo 4.8 s).

    Usarlo de umbral marcaria como sospechoso el 6-19 % de las muestras sanas. La puerta
    es la edad de cada pata, no la distancia entre ellas.
    """
    out = basis_quality(64_400.0, 64_350.0, NOW_MS - 500, NOW_MS - 4_800, NOW_MS)
    assert out["status"] == "VALID"
    assert out["basis_bps"] is not None
    assert out["skew_ms"] == 4_300


def test_basis_nunca_devuelve_cero_por_falta_de_dato() -> None:
    """Regla del proyecto: ausencia de dato es None, jamas 0."""
    for out in (
        basis_quality(None, None, None, None, NOW_MS),
        basis_quality(64_400.0, 64_350.0, NOW_MS - 60_000, NOW_MS - 60_000, NOW_MS),
    ):
        assert out["basis_bps"] is None
        assert out["basis_bps"] != 0


@pytest.mark.parametrize(
    ("gap", "esperado"),
    [
        (None, False),      # ventana sin filas suficientes para medir
        (5.0, False),        # cadencia normal
        (20.0, False),       # el maximo sano observado en 2 h y 6 feeds
        (REALTIME_STALE_SECONDS, False),
        (REALTIME_STALE_SECONDS + 0.1, True),
        (9_840.0, True),     # el hueco de 2 h 44 min medido en ohlcv 1min
    ],
)
def test_puerta_de_huecos(gap, esperado: bool) -> None:
    assert _gap_too_large(gap) is esperado


def test_la_cobertura_no_se_decide_solo_con_los_extremos() -> None:
    """Guarda contra reintroducir el bug: `complete` tiene que mirar el hueco interno."""
    source = (ROOT / "app" / "scalp_logic.py").read_text(encoding="utf-8")
    assert "max_internal_gap" in source
    assert 'item["complete"] = bool(item.get("span_ok")) and not _gap_too_large(' in source
    # La pata spot de la matriz tambien tiene que pasar por la puerta. El baremo dejo de
    # ser una constante y la llamada lleva ahora la cadencia medida, asi que se busca el
    # primer argumento y no el texto exacto: lo que se guarda es que spot_gap PASE por la
    # puerta, no como se escribe la linea.
    matrix = source.split("async def delta_matrix")[1]
    assert re.search(r"_gap_too_large\(\s*spot_gap\b", matrix)
    # K84 · Y LA PATA DE FUTUROS DE LA OTRA RUTA, POR LA MISMA. cvd_matrix no aplicaba
    # NINGUNA guarda de hueco, asi que publicaba la cifra que delta_matrix blanqueaba --
    # las dos dentro del mismo /api/ai/context. Volver a quitarla las hace divergir otra vez
    # en cuanto haya una caida de verdad.
    cvd = source.split("async def cvd_matrix")[1].split("\nasync def ")[0]
    assert "_gap_too_large(" in cvd
    assert "internal_gap" in cvd


def test_el_borde_de_entrada_cuenta_como_hueco() -> None:
    """Un collector caido al PRINCIPIO de la ventana no lo ve un lag() a secas."""
    source = (ROOT / "app" / "scalp_logic.py").read_text(encoding="utf-8")
    consulta = source.split("async def max_internal_gap")[1].split("async def ")[0]
    # El ::timestamptz no es adorno: sin el, PostgreSQL resuelve "$4 - interval" como
    # interval-interval, fija $4 como interval y la consulta entera revienta con
    # "operator does not exist: timestamp with time zone >= interval". Reproducido en
    # el espejo el 2026-08-25 con un PREPARE a pelo. Esta misma linea, sin la marca,
    # es la que tumbaba /api/flow/spot-vs-perp, /api/range/validate y /api/zone/analysis.
    assert "UNION ALL SELECT $4::timestamptz-($3::int*interval '1 second')" in consulta
    assert "AND ts <= $4" in consulta
