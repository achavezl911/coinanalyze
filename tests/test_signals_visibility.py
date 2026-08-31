"""K25 · /api/signals/visibility, la prueba de que un resultado ya era visible.

Que el certificado concuerde con la fila viva que certifica, que la cobertura sea
completa y que los relojes vayan en orden lo mide contra 140
harness/checks/K25-visibilidad-de-lo-final.sh. Aqui van los bordes de la ruta.
"""

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

import app.api as api_module
from app.api import signals_visibility
from app.config import SUPPORTED_SYMBOLS

DESDE = "2026-08-12T12:00:00Z"
HASTA = "2026-08-12T13:00:00Z"


class _Peticion:
    def __init__(self, **params):
        self.query_params = params


def _fila(vid: int, *, estado: str = "evaluated") -> dict[str, object]:
    finalizado = datetime(2026, 8, 12, 12, 30, tzinfo=UTC)
    visto = datetime(2026, 8, 12, 12, 30, 1, tzinfo=UTC)
    return {
        "final_visibility_id": vid,
        "outcome_id": vid * 10,
        "observation_id": vid,
        "symbol": SUPPORTED_SYMBOLS[0],
        "horizon_minutes": 15,
        "visibility_version": 1,
        "outcome_version": 1,
        "source_status": estado,
        "source_finalized_at": finalizado,
        "verified_visible_at": visto,
        "created_at": visto,
    }


class _Pool:
    def __init__(self, filas):
        self.filas = filas
        self.limite = None
        self.status = "no se llamo"

    def acquire(self):
        pool = self

        class Conn:
            async def fetch(self, _q, _sym, _start, _end, status, limit):
                pool.limite = limit
                pool.status = status
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
        r = await signals_visibility(
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
async def test_las_tres_horas_del_certificado_viajan() -> None:
    """Sin las tres no se puede comprobar el orden de relojes desde fuera."""
    respuesta, _ = await _llamar([_fila(1)])
    cert = respuesta["certificates"][0]
    assert cert["source_finalized_at"] == "2026-08-12T12:30:00Z"
    assert cert["verified_visible_at"] == "2026-08-12T12:30:01Z"
    assert cert["created_at"] == "2026-08-12T12:30:01Z"


@pytest.mark.asyncio
async def test_el_certificado_dice_a_que_outcome_pertenece() -> None:
    """Un certificado sin su outcome y su horizonte no se puede contrastar."""
    respuesta, _ = await _llamar([_fila(1)])
    cert = respuesta["certificates"][0]
    assert cert["outcome_id"] == 10
    assert cert["horizon_minutes"] == 15
    assert cert["visibility_version"] == 1


@pytest.mark.asyncio
async def test_el_estado_llega_a_la_consulta() -> None:
    respuesta, pool = await _llamar(
        [_fila(1, estado="not_evaluable")], status="not_evaluable"
    )
    assert pool.status == "not_evaluable"
    assert respuesta["status"] == "not_evaluable"


@pytest.mark.asyncio
async def test_un_estado_que_no_es_final_se_rechaza() -> None:
    """La tabla solo certifica evaluated y not_evaluable; 'pending' daria vacio."""
    original = getattr(api_module.app.state, "pool", None)
    api_module.app.state.pool = _Pool([])
    try:
        with pytest.raises(HTTPException) as error:
            await signals_visibility(
                request=_Peticion(symbol=SUPPORTED_SYMBOLS[0], status="pending"),
                symbol=SUPPORTED_SYMBOLS[0],
                status="pending",
            )
    finally:
        api_module.app.state.pool = original
    assert error.value.status_code == 422


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
            await signals_visibility(
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
            await signals_visibility(
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
            await signals_visibility(
                request=_Peticion(symbol=SUPPORTED_SYMBOLS[0], horizon=15),
                symbol=SUPPORTED_SYMBOLS[0],
            )
    finally:
        api_module.app.state.pool = original
    assert error.value.status_code == 422
    assert "horizon" in error.value.detail


# --- K25 v2 · EL CONTRATO SE EJECUTA, Y "NO HAY CONTRATO" NO ES "TODAVIA NO" -------------


def test_el_contrato_responde_para_la_evidencia_congelada_y_None_para_el_resto() -> None:
    """La funcion es lo unico publico a proposito: K25 tiene que EJECUTARLA sobre las
    versiones vivas, no leer un diccionario. Comprobar que existe un mapa no distingue
    este codigo del que daba por bueno cualquier contrato -- leccion de K71."""
    from app.signal_visibility import (
        _CERTIFIED_EVIDENCE_VERSION,
        RESEARCH_VISIBILITY_VERSION,
        visibility_version_for_evidence,
    )

    assert visibility_version_for_evidence(_CERTIFIED_EVIDENCE_VERSION) == (
        RESEARCH_VISIBILITY_VERSION
    )
    # La cabecera del modulo dice "no v1-v5 backfill" y lo dice hacia adelante tambien:
    # una evidencia sin contrato no se certifica sola por mucho que el certificador corra.
    # K75: la 6 entra en esta lista al pasar el contrato a la 7, y NO es un descuido --
    # esta drenada (785684 finales con cero sin certificar) y ya no se escribe, asi que
    # K25 la ve como version PARADA: visible, sin gatear.
    for sin_contrato in (1, 2, 3, 4, 5, 6, 8):
        assert visibility_version_for_evidence(sin_contrato) is None


def test_el_contrato_no_se_puede_ampliar_sin_declarar_una_visibilidad_nueva() -> None:
    """Guarda contra el arreglo tentador del 2026-08-31: meter la evidencia 7 en el
    contrato para que K25 se calle. Ampliar el contrato SIN subir
    RESEARCH_VISIBILITY_VERSION certificaria una forma distinta bajo la misma etiqueta,
    que es justo lo que la cabecera de signal_visibility prohibe por escrito."""
    import app.signal_visibility as v

    assert set(v._CERTIFICATION_CONTRACT) == {v._CERTIFIED_EVIDENCE_VERSION}
    assert set(v._CERTIFICATION_CONTRACT.values()) == {v.RESEARCH_VISIBILITY_VERSION}
