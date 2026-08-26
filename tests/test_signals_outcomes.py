"""K22 · /api/signals/outcomes, el resultado por horizonte.

Los bordes se prueban aqui; que las derivadas salgan de los precios lo mide
harness/checks/K22-resultado-por-horizonte.sh recalculando fila a fila contra 140.
"""

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

import app.api as api_module
from app.api import signals_ledger, signals_outcomes
from app.config import SUPPORTED_SYMBOLS

DESDE = "2026-08-12T12:00:00Z"
HASTA = "2026-08-12T13:00:00Z"


class _Peticion:
    """Lo unico que la ruta usa de Request es query_params."""

    def __init__(self, **params):
        self.query_params = params


def _fila(outcome_id: int, horizonte: int) -> dict[str, object]:
    momento = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
    return {
        "outcome_id": outcome_id,
        "observation_id": 1,
        "symbol": SUPPORTED_SYMBOLS[0],
        "direction": "long",
        "observed_at": momento,
        "horizon_minutes": horizonte,
        "window_start": momento,
        "window_end": momento,
        "due_at": momento,
        "status": "evaluated",
        "outcome_version": 1,
        "attempts": 1,
        "bars_expected": horizonte,
        "bars_found": horizonte,
        "finalized_at": None,
        "final_reason": None,
        "entry_reference_price": 100.0,
        "end_price": 101.0,
        "max_high": 102.0,
        "min_low": 99.0,
        "market_return_pct": 1.0,
        "up_excursion_pct": 2.0,
        "down_excursion_pct": -1.0,
        "directional_return_pct": 1.0,
        "mfe_pct": 2.0,
        "mae_pct": 1.0,
        "created_at": momento,
    }


class _Pool:
    def __init__(self, filas):
        self.filas = filas
        self.limite = None
        self.horizonte = "no se llamo"

    def acquire(self):
        pool = self

        class Conn:
            async def fetch(self, _q, _sym, _start, _end, horizon, limit):
                pool.limite = limit
                pool.horizonte = horizon
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
    peticion = _Peticion(symbol=SUPPORTED_SYMBOLS[0], since=DESDE, until=HASTA, **{
        k: str(v) for k, v in kwargs.items()
    })
    try:
        r = await signals_outcomes(
            request=peticion, symbol=SUPPORTED_SYMBOLS[0], since=DESDE, until=HASTA, **kwargs
        )
        return r, pool
    finally:
        api_module.app.state.pool = original


@pytest.mark.asyncio
async def test_la_direccion_viaja_en_cada_fila() -> None:
    """Sin direction, mfe_pct y mae_pct no se pueden ni leer ni recalcular."""
    respuesta, _ = await _llamar([_fila(1, 15)])
    assert respuesta["outcomes"][0]["direction"] == "long"


@pytest.mark.asyncio
async def test_los_nulos_se_sirven_y_la_clave_no_se_borra() -> None:
    respuesta, _ = await _llamar([_fila(1, 15)])
    fila = respuesta["outcomes"][0]
    for clave in ("finalized_at", "final_reason"):
        assert clave in fila and fila[clave] is None


@pytest.mark.asyncio
async def test_las_marcas_de_tiempo_salen_en_utc_con_z() -> None:
    respuesta, _ = await _llamar([_fila(1, 15)])
    assert respuesta["outcomes"][0]["window_start"] == "2026-08-12T12:00:00Z"


@pytest.mark.asyncio
async def test_un_corte_se_declara_en_vez_de_pasar_en_silencio() -> None:
    respuesta, pool = await _llamar([_fila(i, 15) for i in range(5)], limit=3)
    assert pool.limite == 4
    assert respuesta["truncated"] is True
    assert respuesta["count"] == 3


@pytest.mark.asyncio
async def test_el_horizonte_llega_a_la_consulta() -> None:
    respuesta, pool = await _llamar([_fila(1, 30)], horizon=30)
    assert pool.horizonte == 30
    assert respuesta["horizon"] == 30


@pytest.mark.asyncio
async def test_un_horizonte_que_no_existe_se_rechaza() -> None:
    """horizon_minutes lleva un CHECK en schema.sql; 7 devolveria una lista vacia."""
    original = getattr(api_module.app.state, "pool", None)
    api_module.app.state.pool = _Pool([])
    try:
        with pytest.raises(HTTPException) as error:
            await signals_outcomes(
                request=_Peticion(symbol=SUPPORTED_SYMBOLS[0], horizon="7"),
                symbol=SUPPORTED_SYMBOLS[0],
                horizon=7,
            )
    finally:
        api_module.app.state.pool = original
    assert error.value.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("ruta", [signals_outcomes, signals_ledger])
async def test_un_parametro_que_nadie_reconoce_no_pasa_en_silencio(ruta) -> None:
    """FastAPI lo ignoraria y la ruta serviria OTRA ventana sin decir nada."""
    original = getattr(api_module.app.state, "pool", None)
    api_module.app.state.pool = _Pool([])
    try:
        with pytest.raises(HTTPException) as error:
            await ruta(
                request=_Peticion(symbol=SUPPORTED_SYMBOLS[0], hour="15"),
                symbol=SUPPORTED_SYMBOLS[0],
            )
    finally:
        api_module.app.state.pool = original
    assert error.value.status_code == 422
    assert "hour" in error.value.detail
