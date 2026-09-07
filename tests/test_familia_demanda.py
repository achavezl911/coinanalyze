"""K43 · las cinco rutas del grupo ENCHUFAR son DEMANDA y tienen que traer su propio `as_of`.

POR QUE ESTE FICHERO EXISTE Y NO BASTA CON MIRAR `app/api.py`. K43 mide contra 140, y 140 corre
el release anterior: hasta que se despliegue, el check seguira ROJO diciendo «sin as_of» y no
habra forma de ver que el arreglo funciona. La API del espejo -que es el camino que la cabecera
de K43 declara para esto- **no esta levantada** (127.0.0.1:8001 no contesta). Asi que la unica
prueba EJECUTADA disponible es esta: llamar a las cinco funciones de ruta con un pool de mentira
y aplicarle a la respuesta **el mismo predicado que usa K43**, copiado de su linea 413.

Lo que esto SI prueba: que el sobre que las cinco construyen satisface a K43.
Lo que NO prueba: que 140 lo sirva. Eso lo dira K43 cuando se despliegue, y no antes.
"""

from datetime import UTC, datetime

import pytest

import app.api as api_module
from app.api import (
    scalp_signals,
    signals_execution,
    signals_ledger,
    signals_replay,
    signals_visibility,
)
from app.config import SUPPORTED_SYMBOLS

SIM = SUPPORTED_SYMBOLS[0]
DESDE = "2026-08-12T12:00:00Z"
HASTA = "2026-08-12T13:00:00Z"

# EL PREDICADO DE K43 PARA LA FAMILIA DEMANDA, copiado de harness/checks/K43-foto-unica.sh:413:
#     elif fam == "DEMANDA" and not any(k in d for k in ("as_of", "generated_at", "snapshot_ts")):
# Se copia y no se importa a proposito: si alguien afloja el check, este test tiene que seguir
# exigiendo lo de antes y que salte la diferencia, no seguirle la corriente.
CLAVES_DEMANDA = ("as_of", "generated_at", "snapshot_ts")


class _Peticion:
    def __init__(self, **params):
        self.query_params = params


class _Pool:
    """Devuelve cero filas. El sobre es lo que se mide, no el contenido."""

    def acquire(self):
        class Conn:
            async def fetch(self, *_a, **_k):
                return []

        class Ctx:
            async def __aenter__(self):
                return Conn()

            async def __aexit__(self, *_):
                return False

        return Ctx()


async def _llamar(fn, **kwargs):
    original = getattr(api_module.app.state, "pool", None)
    api_module.app.state.pool = _Pool()
    try:
        return await fn(**kwargs)
    finally:
        api_module.app.state.pool = original


CON_VENTANA = (
    (signals_ledger, "ledger"),
    (signals_replay, "replay"),
    (signals_execution, "execution"),
    (signals_visibility, "visibility"),
)


@pytest.mark.asyncio
@pytest.mark.parametrize("fn,nombre", CON_VENTANA)
async def test_las_cuatro_con_ventana_traen_as_of(fn, nombre) -> None:
    peticion = _Peticion(symbol=SIM, since=DESDE, until=HASTA)
    d = await _llamar(fn, request=peticion, symbol=SIM, since=DESDE, until=HASTA)
    assert any(k in d for k in CLAVES_DEMANDA), f"{nombre} no cumple DEMANDA"
    # Y el as_of es el instante de la RESPUESTA, no la ventana: tiene que ser posterior a
    # `until`. Sin esta linea, servir `as_of = until` pasaria el predicado sin decir nada nuevo.
    assert d["as_of"] > d["until"], f"{nombre}: as_of no puede ser anterior al fin de la ventana"


@pytest.mark.asyncio
async def test_scalp_signals_tambien_trae_as_of() -> None:
    """No acepta ventana de tiempo, pero el llamante elige `limit`: tambien es DEMANDA."""
    d = await _llamar(scalp_signals, symbol=SIM)
    assert any(k in d for k in CLAVES_DEMANDA)
    assert d["as_of"].endswith("Z")


@pytest.mark.asyncio
async def test_el_as_of_es_de_ahora_y_en_utc_con_z() -> None:
    """Una marca que no se mueve no fecha nada: se comprueba contra el reloj, con holgura."""
    antes = datetime.now(UTC)
    peticion = _Peticion(symbol=SIM, since=DESDE, until=HASTA)
    d = await _llamar(signals_ledger, request=peticion, symbol=SIM, since=DESDE, until=HASTA)
    despues = datetime.now(UTC)
    assert d["as_of"].endswith("Z"), "el as_of tiene que ir en UTC con Z, como el resto del ledger"
    visto = datetime.fromisoformat(d["as_of"].replace("Z", "+00:00"))
    assert antes <= visto <= despues, f"as_of={d['as_of']} fuera de [{antes}, {despues}]"


@pytest.mark.asyncio
async def test_outcomes_sigue_SIN_as_of() -> None:
    """EL BRAZO QUE HACE VALER A LOS OTROS: /api/signals/outcomes se quedo FUERA del grupo.

    Si el `as_of` se hubiera anadido a lo bruto -a todas las rutas de la familia- este test
    fallaria, y con el fallaria la afirmacion de que se toco lo que se dijo y nada mas.
    """
    from app.api import signals_outcomes

    peticion = _Peticion(symbol=SIM, since=DESDE, until=HASTA)
    d = await _llamar(
        signals_outcomes, request=peticion, symbol=SIM, since=DESDE, until=HASTA
    )
    assert not any(k in d for k in CLAVES_DEMANDA), "outcomes no entraba en el grupo ENCHUFAR"
