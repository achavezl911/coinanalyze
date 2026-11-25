"""M-03 paso 2 (P08, SOBRE R2): el sobre deja de decir clean/complete cuando va atrasado.

SOBRE R1 anadio la edad y la ventana PEDIDA, pero `status` y `complete` seguian saliendo de lo
SERVIDO: un proveedor parado 8 h seguia diciendo clean. Ahora, si la ventana pedida trae mas
cubos sin fila que el retraso normal de su feed (`api.RETRASO_TOLERADO`, medido en 140 el
2026-11-24/25), el sobre no dice clean ni complete. Las edades de estos casos son las medidas:
ohlcv p50 34 s, cvd/spot p50 154 s (2 cubos sin declarar).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

import app.api as api

MIN = timedelta(minutes=1)
HORA = timedelta(hours=1)
T = datetime(2026, 11, 20, 12, tzinfo=UTC)
S = timedelta(seconds=1)


def filas(desde: datetime, hasta: datetime, paso: timedelta = MIN) -> list[dict[str, Any]]:
    return [{"bucket": desde + i * paso, "close": 100.0} for i in range(int((hasta - desde) / paso))]


def huecos(*tramos: tuple[datetime, datetime]):
    async def declarados(_conn, *, start, end, **_kwargs):
        return [
            {"start": a.isoformat(), "end": b.isoformat(), "status": "unresolved"}
            for a, b in tramos
            if a < end and b > start
        ]

    return declarados


async def sobre(monkeypatch, rows, *, feed="ohlcv_1min", ahora=T, limit=600, bucket=MIN, tramos=()):
    monkeypatch.setattr(api, "declared_gap_windows", huecos(*tramos))
    return await api.declared_series_response(
        object(),  # type: ignore[arg-type]
        rows,
        interval="1min",
        bucket=bucket,
        feed=feed,
        exchanges=("binance",),
        market="perpetual",
        symbol="BTCUSDT_PERP.A",
        limit=limit,
        ahora=ahora,
    )


def veredicto(payload: dict[str, Any]) -> tuple[str, bool | None]:
    servida = payload["coverage"]["served_window"]
    return payload["data_gaps"]["status"], servida and servida["complete"]


@pytest.mark.asyncio
async def test_m03_prop_proveedor_parado_8_h_no_dice_clean_ni_complete(monkeypatch) -> None:
    payload = await sobre(monkeypatch, filas(T - 10 * HORA, T - 8 * HORA))
    assert payload["data_gaps"]["age_seconds"] == 8 * 3600
    assert veredicto(payload) == ("undeclared", False)


@pytest.mark.asyncio
async def test_m03_parado_8_h_con_su_hueco_declarado_dice_declared(monkeypatch) -> None:
    """El hueco declarado cae FUERA de la ventana servida: antes ni se veia."""
    payload = await sobre(
        monkeypatch, filas(T - 10 * HORA, T - 8 * HORA), tramos=((T - 8 * HORA, T),)
    )
    assert payload["data_gaps"]["requested_window"]["undeclared_buckets"] == 0
    assert veredicto(payload) == ("declared", False)


@pytest.mark.asyncio
async def test_control_ohlcv_sano_con_34_s_es_clean(monkeypatch) -> None:
    payload = await sobre(monkeypatch, filas(T - 10 * HORA, T), ahora=T + 34 * S)
    assert payload["data_gaps"]["age_seconds"] == 34
    assert veredicto(payload) == ("clean", True)


@pytest.mark.asyncio
async def test_control_ohlcv_con_su_maximo_94_s_y_un_cubo_sin_fila_es_clean(monkeypatch) -> None:
    payload = await sobre(monkeypatch, filas(T - 10 * HORA, T - MIN), ahora=T + 34 * S)
    assert payload["data_gaps"]["requested_window"]["undeclared_buckets"] == 1
    assert veredicto(payload) == ("clean", True)


@pytest.mark.asyncio
async def test_ohlcv_con_tres_cubos_sin_fila_no_es_clean(monkeypatch) -> None:
    payload = await sobre(monkeypatch, filas(T - 10 * HORA, T - 3 * MIN), ahora=T + 34 * S)
    assert veredicto(payload) == ("undeclared", False)


@pytest.mark.asyncio
async def test_control_cvd_spot_con_154_s_y_2_cubos_es_clean(monkeypatch) -> None:
    payload = await sobre(
        monkeypatch, filas(T - 10 * HORA, T - 2 * MIN), feed="spot_trades", ahora=T + 34 * S
    )
    assert payload["data_gaps"]["age_seconds"] == 154
    assert payload["data_gaps"]["requested_window"]["undeclared_buckets"] == 2
    assert veredicto(payload) == ("clean", True)


@pytest.mark.asyncio
async def test_cvd_spot_con_400_s_no_es_clean(monkeypatch) -> None:
    payload = await sobre(
        monkeypatch, filas(T - 10 * HORA, T - 6 * MIN), feed="spot_trades", ahora=T + 40 * S
    )
    assert payload["data_gaps"]["age_seconds"] == 400
    assert veredicto(payload) == ("undeclared", False)


@pytest.mark.asyncio
async def test_sin_filas_como_hoy(monkeypatch) -> None:
    payload = await sobre(monkeypatch, [], limit=180, tramos=((T - 2 * HORA, T),))
    assert payload["coverage"]["served_window"] is None
    assert payload["data_gaps"]["status"] == "no_data"
    assert payload["data_gaps"]["requested_window"]["undeclared_buckets"] == 60


@pytest.mark.asyncio
async def test_oi_pedido_a_1min_se_juzga_en_su_cubo_nativo_de_5_min(monkeypatch) -> None:
    """Una fila cada 5 min no es una perdida de 4 de cada 5 minutos (49 de 60 en 140)."""
    paso = 5 * MIN
    sano = filas(T - 10 * HORA, T - paso, paso)  # 574 s tras cerrar falta el ultimo nativo
    payload = await sobre(
        monkeypatch, sano, feed="open_interest_5min", limit=60, ahora=T + 274 * S
    )
    gaps = payload["data_gaps"]
    assert gaps["requested_window"]["undeclared_buckets"] == 1  # cubos de 5 min
    assert gaps["requested_window"]["limit"] == 60
    assert veredicto(payload) == ("clean", True)
    assert payload["coverage"]["served_window"]["expected_buckets"] == len(sano)
    parado = filas(T - 10 * HORA, T - HORA, paso)
    payload = await sobre(
        monkeypatch, parado, feed="open_interest_5min", limit=60, ahora=T + 274 * S
    )
    assert veredicto(payload) == ("undeclared", False)


def test_tolerancias_en_un_sitio() -> None:
    assert api.cubos_tolerados("ohlcv_1min", MIN) == 2
    assert api.cubos_tolerados("spot_trades", MIN) == 5
    assert api.cubos_tolerados("spot_trades", 5 * MIN) == 1
    assert api.cubos_tolerados("liquidations", HORA) == 1
    assert api.cubos_tolerados("open_interest_5min", 5 * MIN) == 2
    assert api.cubos_tolerados("feed_que_no_existe", MIN) is None
