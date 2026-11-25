"""M-03: el sobre de las series dice su EDAD y los cubos sin declarar de lo PEDIDO.

La ventana servida sale de las filas, asi que una serie que se paro hace 8 h salia `clean`:
el hueco del final quedaba fuera de lo que se miraba. El paso 1 anadio `as_of`,
`age_seconds` y `requested_window` a `data_gaps`; el veredicto de P08 (SOBRE R2) vive en
tests/test_sobre_r2_retraso.py.
"""

from __future__ import annotations

import ast
import inspect
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

import app.api as api

MIN = timedelta(minutes=1)
HORA = timedelta(hours=1)
T = datetime(2026, 11, 20, 12, tzinfo=UTC)


def filas(desde: datetime, hasta: datetime, paso: timedelta = MIN) -> list[dict[str, Any]]:
    return [{"bucket": desde + i * paso, "close": 100.0} for i in range(int((hasta - desde) / paso))]


def huecos(*tramos: tuple[datetime, datetime]):
    """Un data_gap de mentira que, como el de verdad, solo devuelve lo que cae en [start,end)."""
    llamadas: list[tuple[datetime, datetime]] = []

    async def declarados(_conn, *, start, end, **_kwargs):
        llamadas.append((start, end))
        return [
            {"start": a.isoformat(), "end": b.isoformat(), "status": "unresolved"}
            for a, b in tramos
            if a < end and b > start
        ]

    return declarados, llamadas


async def sobre(rows, *, limit=600, ahora=T, bucket=MIN, **extra):
    return await api.declared_series_response(
        object(),  # type: ignore[arg-type]
        rows,
        interval="1min",
        bucket=bucket,
        feed="ohlcv_1min",
        exchanges=("binance",),
        market="perpetual",
        symbol="BTCUSDT_PERP.A",
        limit=limit,
        ahora=ahora,
        **extra,
    )


@pytest.mark.asyncio
async def test_m03_serie_parada_hace_8_h_dice_su_edad_y_sus_cubos_sin_declarar(monkeypatch) -> None:
    """El caso M-03 del banco de fable-dz2: «undeclared 480 cubos, edad 28800 s»."""
    declarados, _ = huecos()
    monkeypatch.setattr(api, "declared_gap_windows", declarados)
    gaps = (await sobre(filas(T - 10 * HORA, T - 8 * HORA)))["data_gaps"]
    assert gaps["requested_window"]["undeclared_buckets"] == 480
    assert gaps["age_seconds"] == 28800
    assert gaps["as_of"] == (T - 8 * HORA).isoformat()
    assert gaps["requested_window"]["window_start"] == (T - 10 * HORA).isoformat()
    assert gaps["requested_window"]["window_end"] == T.isoformat()
    # La ventana servida sigue siendo la de las filas; el veredicto ya no (P08).
    assert gaps["status"] == "undeclared"
    assert gaps["undeclared_buckets"] == 0
    assert gaps["window_end"] == (T - 8 * HORA).isoformat()


@pytest.mark.asyncio
async def test_m03_con_el_hueco_declarado_quedan_sin_declarar_solo_60(monkeypatch) -> None:
    declarados, _ = huecos((T - 8 * HORA, T - HORA))
    monkeypatch.setattr(api, "declared_gap_windows", declarados)
    gaps = (await sobre(filas(T - 10 * HORA, T - 8 * HORA)))["data_gaps"]
    assert len(gaps["requested_window"]["declared"]) == 1
    assert gaps["requested_window"]["undeclared_buckets"] == 60
    assert gaps["declared"] == []  # la ventana servida no lo ve, igual que antes
    assert gaps["status"] == "undeclared"  # 60 sin declarar, tolerados 2 (P08)


@pytest.mark.asyncio
async def test_control_serie_entera_edad_cero_y_nada_sin_declarar(monkeypatch) -> None:
    declarados, _ = huecos()
    monkeypatch.setattr(api, "declared_gap_windows", declarados)
    gaps = (await sobre(filas(T - 10 * HORA, T)))["data_gaps"]
    assert (gaps["status"], gaps["age_seconds"]) == ("clean", 0)
    assert gaps["requested_window"]["undeclared_buckets"] == 0


@pytest.mark.asyncio
async def test_el_cubo_en_curso_no_da_una_edad_negativa(monkeypatch) -> None:
    """La ruta sirve el cubo que se esta llenando: su final esta en el futuro."""
    declarados, _ = huecos()
    monkeypatch.setattr(api, "declared_gap_windows", declarados)
    ahora = T + timedelta(seconds=25)
    gaps = (await sobre(filas(T - 10 * HORA, T + MIN), ahora=ahora))["data_gaps"]
    assert gaps["age_seconds"] == 0
    assert gaps["as_of"] == ahora.isoformat()
    # fin = el ultimo cubo CERRADO: el que esta en curso no se pide.
    assert gaps["requested_window"]["window_end"] == T.isoformat()
    assert gaps["requested_window"]["undeclared_buckets"] == 0


@pytest.mark.asyncio
async def test_sin_filas_tambien_se_pregunta_por_huecos(monkeypatch) -> None:
    declarados, llamadas = huecos((T - 2 * HORA, T))
    monkeypatch.setattr(api, "declared_gap_windows", declarados)
    gaps = (await sobre([], limit=180))["data_gaps"]
    assert llamadas == [(T - 3 * HORA, T)]
    assert gaps["status"] == "no_data"
    assert (gaps["as_of"], gaps["age_seconds"]) == (None, None)
    assert gaps["requested_window"]["undeclared_buckets"] == 60


@pytest.mark.asyncio
async def test_sin_limit_no_hay_ventana_pedida_y_si_edad(monkeypatch) -> None:
    declarados, llamadas = huecos()
    monkeypatch.setattr(api, "declared_gap_windows", declarados)
    gaps = (await sobre(filas(T - HORA, T - 30 * MIN), limit=None))["data_gaps"]
    assert gaps["requested_window"] is None
    assert gaps["age_seconds"] == 1800
    assert len(llamadas) == 1  # solo la de la ventana servida, como antes


@pytest.mark.asyncio
async def test_liquidaciones_rala_la_edad_y_los_ceros_los_da_el_latido(monkeypatch) -> None:
    """dz2 N1: en /api/liquidations un cubo sin fila es cero si el barrido ok lo certifica."""
    declarados, _ = huecos()
    monkeypatch.setattr(api, "declared_gap_windows", declarados)
    rows = filas(T - 10 * HORA, T - 9 * HORA, HORA)  # una sola hora con liquidaciones
    ok = {"estado": "ok", "desde": T - 74 * HORA, "hasta": T - 5 * timedelta(minutes=5)}
    latido = {"valor": ok}

    async def barrido(_conn):
        return latido["valor"]

    monkeypatch.setattr(api.orderflow_lectura, "_barrido_liquidaciones", barrido)
    gaps = (await sobre(rows, limit=10, bucket=HORA, rala=True))["data_gaps"]
    assert gaps["as_of"] == ok["hasta"].isoformat()
    assert gaps["age_seconds"] == 1500
    # La ultima hora acaba despues de lo certificado: esa SI falta y nadie la apunto.
    assert gaps["requested_window"]["undeclared_buckets"] == 1
    latido["valor"] = dict(ok, estado="error")
    gaps = (await sobre(rows, limit=10, bucket=HORA, rala=True))["data_gaps"]
    assert gaps["age_seconds"] == 9 * 3600
    assert gaps["requested_window"]["undeclared_buckets"] == 9


def test_los_seis_llamadores_pasan_limit() -> None:
    arbol = ast.parse(inspect.getsource(api))
    llamadas = [
        nodo
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Call)
        and isinstance(nodo.func, ast.Name)
        and nodo.func.id == "declared_series_response"
    ]
    assert len(llamadas) == 6
    for nodo in llamadas:
        claves = {k.arg for k in nodo.keywords}
        assert "limit" in claves, nodo.lineno
        es_liq = any(
            k.arg == "feed" and isinstance(k.value, ast.Constant) and k.value.value == "liquidations"
            for k in nodo.keywords
        )
        assert ("rala" in claves) == es_liq, nodo.lineno
