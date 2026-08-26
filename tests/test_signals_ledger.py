"""K21 · /api/signals/ledger, el ledger de senales.

Lo que se prueba aqui es lo que un check contra produccion NO puede probar barato: los
bordes. La correccion del contenido -que las filas servidas son las de la ventana- la
mide harness/checks/K21-ledger-de-senales.sh recalculando contra signal_observation.
"""

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

import app.api as api_module
from app.api import signals_ledger
from app.config import SUPPORTED_SYMBOLS

DESDE = "2026-08-12T12:00:00Z"
HASTA = "2026-08-12T13:00:00Z"


class _Peticion:
    """Lo unico que la ruta usa de Request es query_params."""

    def __init__(self, **params):
        self.query_params = params


def _fila(observation_id: int, minuto: int) -> dict[str, object]:
    return {
        "observation_id": observation_id,
        "observed_at": datetime(2026, 8, 12, 12, minuto, 0, tzinfo=UTC),
        "observed_minute": datetime(2026, 8, 12, 12, minuto, 0, tzinfo=UTC),
        "symbol": SUPPORTED_SYMBOLS[0],
        "signal_family": "scalp",
        "is_periodic": True,
        "is_transition": False,
        "logic_version": "v1",
        "evidence_version": 6,
        "sampling_version": 1,
        "decision_status": "evaluable",
        "direction": "neutral",
        "actionable": False,
        "state": "No Trade",
        "confidence": "baja",
        "reason": "sin sesgo",
        "reference_price": 100.0,
        "reference_price_source": "futures",
        "reference_price_at": datetime(2026, 8, 12, 12, minuto, 0, tzinfo=UTC),
        "long_score": 10.0,
        "short_score": 20.0,
        "evidence_coverage_pct": 90.0,
        "metrics_snapshot_ts": None,
        "regime_score": None,
        "regime_label": None,
        "regime_logic_version": None,
    }


class _Pool:
    def __init__(self, filas: list[dict[str, object]]) -> None:
        self.filas = filas
        self.limite: int | None = None

    def acquire(self):
        pool = self

        class Conn:
            async def fetch(self, _query, _symbol, _start, _end, limit):
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
        peticion = _Peticion(symbol=SUPPORTED_SYMBOLS[0], since=DESDE, until=HASTA)
        return await signals_ledger(
            request=peticion, symbol=SUPPORTED_SYMBOLS[0], since=DESDE, until=HASTA, **kwargs
        ), pool
    finally:
        api_module.app.state.pool = original


@pytest.mark.asyncio
async def test_los_nulos_se_sirven_y_la_clave_no_se_borra() -> None:
    """Ausente y null no pueden ser la misma respuesta: es la ley que persigue K48."""
    respuesta, _ = await _llamar([_fila(1, 0)])
    observacion = respuesta["observations"][0]
    for clave in ("metrics_snapshot_ts", "regime_score", "regime_label"):
        assert clave in observacion, f"{clave} desaparecio en vez de valer null"
        assert observacion[clave] is None


@pytest.mark.asyncio
async def test_las_marcas_de_tiempo_salen_en_utc_con_z() -> None:
    """El ledger no filtra la zona horaria del servidor."""
    respuesta, _ = await _llamar([_fila(1, 30)])
    observacion = respuesta["observations"][0]
    assert observacion["observed_at"] == "2026-08-12T12:30:00Z"
    assert respuesta["since"] == DESDE
    assert respuesta["until"] == HASTA


@pytest.mark.asyncio
async def test_un_corte_se_declara_en_vez_de_pasar_en_silencio() -> None:
    """Se piden limit+1 filas justo para poder decir truncated sin volver a contar."""
    respuesta, pool = await _llamar([_fila(i, i) for i in range(5)], limit=3)
    assert pool.limite == 4, "no se pidio la fila de mas que detecta el corte"
    assert respuesta["truncated"] is True
    assert respuesta["count"] == 3
    assert len(respuesta["observations"]) == 3


@pytest.mark.asyncio
async def test_sin_corte_lo_dice_igual() -> None:
    respuesta, _ = await _llamar([_fila(i, i) for i in range(3)], limit=10)
    assert respuesta["truncated"] is False
    assert respuesta["count"] == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("since", "until", "motivo"),
    [
        ("2026-08-12T13:00:00Z", "2026-08-12T12:00:00Z", "until anterior a since"),
        ("2026-08-12T12:00:00Z", "2026-08-12T12:00:00Z", "ventana vacia"),
        ("2026-08-10T12:00:00Z", "2026-08-12T12:00:00Z", "ventana de 48 h"),
        ("2026-08-12T12:00:00", "2026-08-12T13:00:00Z", "sin zona horaria"),
        ("no-es-una-fecha", "2026-08-12T13:00:00Z", "no es ISO-8601"),
    ],
)
async def test_la_ventana_invalida_se_rechaza(since, until, motivo) -> None:
    original = getattr(api_module.app.state, "pool", None)
    api_module.app.state.pool = _Pool([])
    try:
        with pytest.raises(HTTPException) as error:
            await signals_ledger(
                request=_Peticion(symbol=SUPPORTED_SYMBOLS[0], since=since, until=until),
                symbol=SUPPORTED_SYMBOLS[0],
                since=since,
                until=until,
            )
    finally:
        api_module.app.state.pool = original
    assert error.value.status_code == 422, motivo
