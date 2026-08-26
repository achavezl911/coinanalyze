"""K23 · /api/signals/execution, el coste real de ejecucion.

Que la curva de coste cuadre consigo misma y con el libro lo mide
harness/checks/K23-coste-de-ejecucion.sh contra 140. Aqui van los bordes.
"""

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

import app.api as api_module
from app.api import signals_execution
from app.config import SUPPORTED_SYMBOLS

DESDE = "2026-08-12T12:00:00Z"
HASTA = "2026-08-12T13:00:00Z"
CURVA = {
    "1000": {
        "buy": {
            "avg_price": 101.0,
            "filled_usd": 1000.0,
            "shortfall_usd": 0.0,
            "insufficient_depth": False,
            "slippage_bps_vs_best": 0.0,
            "market_cost_bps_vs_mid": 49.5,
        }
    }
}


class _Peticion:
    def __init__(self, **params):
        self.query_params = params


def _fila(sid: int, *, curva=CURVA, exchange: str = "binance") -> dict[str, object]:
    momento = datetime(2026, 8, 12, 12, 30, tzinfo=UTC)
    return {
        "execution_snapshot_id": sid,
        "observation_id": 1,
        "symbol": SUPPORTED_SYMBOLS[0],
        "direction": "long",
        "observed_at": momento,
        "snapshot_version": 1,
        "exchange": exchange,
        "captured_at": momento,
        "book_ts": momento,
        "book_age_seconds": 0.2,
        "status": "valid",
        "reason": None,
        "levels_reported": 50,
        "bid_levels_valid": 50,
        "ask_levels_valid": 50,
        "best_bid_px": 100.0,
        "best_ask_px": 101.0,
        "mid_px": 100.5,
        "spread_bps": 99.502,
        "bid_depth_usd": 5000.0,
        "ask_depth_usd": 5000.0,
        "source_book_hash": "a" * 64,
        "cost_curve": curva,
        "created_at": momento,
    }


class _Pool:
    def __init__(self, filas):
        self.filas = filas
        self.limite = None
        self.exchange = "no se llamo"

    def acquire(self):
        pool = self

        class Conn:
            async def fetch(self, _q, _sym, _start, _end, exchange, limit):
                pool.limite = limit
                pool.exchange = exchange
                return pool.filas[:limit]

        class Ctx:
            async def __aenter__(self):
                return Conn()

            async def __aexit__(self, *_):
                return False

        return Ctx()


async def _llamar(filas, **kwargs):
    pool = _Pool(filas)
    original = getattr(api_module.app.state, "pool", None)
    api_module.app.state.pool = pool
    try:
        r = await signals_execution(
            request=_Peticion(symbol=SUPPORTED_SYMBOLS[0]),
            symbol=SUPPORTED_SYMBOLS[0],
            since=DESDE,
            until=HASTA,
            **kwargs,
        )
        return r, pool
    finally:
        api_module.app.state.pool = original


@pytest.mark.asyncio
async def test_la_curva_de_coste_viaja_entera_y_como_objeto() -> None:
    """Compactarla o resumirla haria imposible recalcularla desde fuera."""
    respuesta, _ = await _llamar([_fila(1)])
    curva = respuesta["snapshots"][0]["cost_curve"]
    assert isinstance(curva, dict)
    assert curva["1000"]["buy"]["slippage_bps_vs_best"] == 0.0


@pytest.mark.asyncio
async def test_la_curva_llega_igual_si_la_base_la_da_como_texto() -> None:
    """asyncpg puede devolver el jsonb como str; el llamante quiere la curva."""
    import json as _json

    respuesta, _ = await _llamar([_fila(1, curva=_json.dumps(CURVA))])
    assert respuesta["snapshots"][0]["cost_curve"] == CURVA


@pytest.mark.asyncio
async def test_los_nulos_se_sirven_y_la_clave_no_se_borra() -> None:
    respuesta, _ = await _llamar([_fila(1)])
    fila = respuesta["snapshots"][0]
    assert "reason" in fila and fila["reason"] is None


@pytest.mark.asyncio
async def test_las_marcas_de_tiempo_salen_en_utc_con_z() -> None:
    respuesta, _ = await _llamar([_fila(1)])
    assert respuesta["snapshots"][0]["book_ts"] == "2026-08-12T12:30:00Z"


@pytest.mark.asyncio
async def test_un_corte_se_declara_en_vez_de_pasar_en_silencio() -> None:
    respuesta, pool = await _llamar([_fila(i) for i in range(5)], limit=3)
    assert pool.limite == 4
    assert respuesta["truncated"] is True


@pytest.mark.asyncio
async def test_el_mercado_llega_a_la_consulta() -> None:
    respuesta, pool = await _llamar([_fila(1, exchange="bybit")], exchange="bybit")
    assert pool.exchange == "bybit"
    assert respuesta["exchange"] == "bybit"


@pytest.mark.asyncio
async def test_un_mercado_que_no_existe_se_rechaza() -> None:
    """exchange lleva un CHECK en schema.sql; 'kraken' devolveria una lista vacia."""
    original = getattr(api_module.app.state, "pool", None)
    api_module.app.state.pool = _Pool([])
    try:
        with pytest.raises(HTTPException) as error:
            await signals_execution(
                request=_Peticion(symbol=SUPPORTED_SYMBOLS[0], exchange="kraken"),
                symbol=SUPPORTED_SYMBOLS[0],
                exchange="kraken",
            )
    finally:
        api_module.app.state.pool = original
    assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_un_parametro_que_nadie_reconoce_no_pasa_en_silencio() -> None:
    original = getattr(api_module.app.state, "pool", None)
    api_module.app.state.pool = _Pool([])
    try:
        with pytest.raises(HTTPException) as error:
            await signals_execution(
                request=_Peticion(symbol=SUPPORTED_SYMBOLS[0], venue="binance"),
                symbol=SUPPORTED_SYMBOLS[0],
            )
    finally:
        api_module.app.state.pool = original
    assert error.value.status_code == 422
    assert "venue" in error.value.detail
