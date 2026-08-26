"""K24 · /api/signals/replay, los insumos congelados de cada decision.

Que el context sirva para volver a ejecutar el nucleo y salga la misma evidence lo
mide harness/checks/K24-replay-del-contexto.sh contra 140, sobre frames reales.
Aqui van los bordes de la ruta, y uno que no es un borde: que el context llegue
ENTERO y como objeto, porque de eso depende que el hash se pueda recalcular fuera.
"""

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

import app.api as api_module
from app.api import signals_replay
from app.config import SUPPORTED_SYMBOLS
from app.signal_replay import canonical_json_hash

DESDE = "2026-08-12T12:00:00Z"
HASTA = "2026-08-12T13:00:00Z"
CONTEXT = {
    "now_ms": 1786550400000.0,
    "price": 100.5,
    "ohlcv_price": 100.4,
    "ohlcv_price_at": "2026-08-12T12:30:00+00:00",
    "bars_15m": 15,
    "price_move_15m_coverage": "complete",
}
EVIDENCE = {"state": "No Trade", "long_score": 12.0, "short_score": 8.0}


class _Peticion:
    def __init__(self, **params):
        self.query_params = params


def _fila(fid: int, *, context=CONTEXT, evidence=EVIDENCE) -> dict[str, object]:
    momento = datetime(2026, 8, 12, 12, 30, tzinfo=UTC)
    return {
        "frame_id": fid,
        "observation_id": fid * 10,
        "symbol": SUPPORTED_SYMBOLS[0],
        "observed_at": momento,
        "context_version": 1,
        "context_as_of": momento,
        "context_hash": canonical_json_hash(CONTEXT),
        "logic_version": "scalp-summary-v1",
        "evidence_version": 6,
        "context": context,
        "evidence": evidence,
        "created_at": momento,
    }


class _Pool:
    def __init__(self, filas):
        self.filas = filas
        self.limite = None

    def acquire(self):
        pool = self

        class Conn:
            async def fetch(self, _q, _sym, _start, _end, limit):
                pool.limite = limit
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
        r = await signals_replay(
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
async def test_el_context_viaja_entero_y_como_objeto() -> None:
    """Sin el context entero no se puede replicar, y la capacidad no existe."""
    respuesta, _ = await _llamar([_fila(1)])
    frame = respuesta["frames"][0]
    assert isinstance(frame["context"], dict)
    assert frame["context"] == CONTEXT


@pytest.mark.asyncio
async def test_el_hash_se_puede_recalcular_sobre_lo_que_se_sirve() -> None:
    """Es la comprobacion que hace verificable a la ruta: se sirve el JSON tal cual."""
    import json as _json

    respuesta, _ = await _llamar([_fila(1, context=_json.dumps(CONTEXT))])
    frame = respuesta["frames"][0]
    assert canonical_json_hash(frame["context"]) == frame["context_hash"]


@pytest.mark.asyncio
async def test_la_evidence_tambien_llega_si_la_base_la_da_como_texto() -> None:
    import json as _json

    respuesta, _ = await _llamar([_fila(1, evidence=_json.dumps(EVIDENCE))])
    assert respuesta["frames"][0]["evidence"] == EVIDENCE


@pytest.mark.asyncio
async def test_la_version_del_nucleo_viaja() -> None:
    """Sin logic_version el llamante no sabe QUE nucleo tiene que ejecutar."""
    respuesta, _ = await _llamar([_fila(1)])
    assert respuesta["frames"][0]["logic_version"] == "scalp-summary-v1"
    assert respuesta["frames"][0]["context_version"] == 1


@pytest.mark.asyncio
async def test_las_marcas_de_tiempo_salen_en_utc_con_z() -> None:
    respuesta, _ = await _llamar([_fila(1)])
    assert respuesta["frames"][0]["context_as_of"] == "2026-08-12T12:30:00Z"


@pytest.mark.asyncio
async def test_un_corte_se_declara_en_vez_de_pasar_en_silencio() -> None:
    respuesta, pool = await _llamar([_fila(i) for i in range(5)], limit=3)
    assert pool.limite == 4
    assert respuesta["truncated"] is True
    assert respuesta["count"] == 3


@pytest.mark.asyncio
async def test_una_ventana_mayor_que_el_tope_se_rechaza() -> None:
    original = getattr(api_module.app.state, "pool", None)
    api_module.app.state.pool = _Pool([])
    try:
        with pytest.raises(HTTPException) as error:
            await signals_replay(
                request=_Peticion(symbol=SUPPORTED_SYMBOLS[0]),
                symbol=SUPPORTED_SYMBOLS[0],
                since="2026-08-10T00:00:00Z",
                until="2026-08-12T00:00:00Z",
            )
    finally:
        api_module.app.state.pool = original
    assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_una_fecha_sin_zona_horaria_se_rechaza() -> None:
    original = getattr(api_module.app.state, "pool", None)
    api_module.app.state.pool = _Pool([])
    try:
        with pytest.raises(HTTPException) as error:
            await signals_replay(
                request=_Peticion(symbol=SUPPORTED_SYMBOLS[0]),
                symbol=SUPPORTED_SYMBOLS[0],
                since="2026-08-12T12:00:00",
                until=HASTA,
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
            await signals_replay(
                request=_Peticion(symbol=SUPPORTED_SYMBOLS[0], hour=12),
                symbol=SUPPORTED_SYMBOLS[0],
            )
    finally:
        api_module.app.state.pool = original
    assert error.value.status_code == 422
    assert "hour" in error.value.detail
