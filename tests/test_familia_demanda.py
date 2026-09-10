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
    level_breakout_endpoint,
    range_validate_endpoint,
    scalp_signals,
    signals_execution,
    signals_ledger,
    signals_replay,
    signals_visibility,
    zone_analysis_endpoint,
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

            # 2026-09-10 · `fetchrow` y `fetchval` se anaden al doble porque las tres rutas
            # destapadas en COLA 106 los usan. El doble tiene que modelar la conexion, no la
            # parte de la conexion que hacia falta el dia que se escribio: sin esto, el brazo
            # de zone/analysis fallaba con AttributeError y no por lo que quiere medir.
            # Devuelven vacio a proposito: aqui se mide el SOBRE, no el contenido.
            async def fetchrow(self, *_a, **_k):
                return None

            async def fetchval(self, *_a, **_k):
                return None

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


# ── LAS TRES QUE APARECIERON AL ASIGNAR LAS HUERFANAS (COLA 106), arregladas el 2026-09-10 ─────
# Llevaban tapadas detras de la salida temprana de K43 por «sin familia». Ninguna publicaba el
# instante en que contestaba, y las tres estan en DEMANDA porque su contenido depende de lo que
# elige quien pregunta: un nivel, un rango, una zona.
LAS_TRES = (
    ("zone/analysis", zone_analysis_endpoint,
     {"symbol": SIM, "low": 77000.0, "high": 80000.0}),
    ("range/validate", range_validate_endpoint,
     {"symbol": SIM, "low": 77000.0, "high": 80000.0}),
    ("level/breakout", level_breakout_endpoint,
     {"symbol": SIM, "level": 78800.0}),
)


@pytest.mark.asyncio
@pytest.mark.parametrize("nombre,fn,kwargs", LAS_TRES)
async def test_las_tres_destapadas_traen_su_as_of(nombre, fn, kwargs) -> None:
    d = await _llamar(fn, **kwargs)
    assert any(k in d for k in CLAVES_DEMANDA), f"{nombre} no cumple DEMANDA"


@pytest.mark.asyncio
async def test_el_as_of_de_las_tres_es_el_INSTANTE_y_no_la_VENTANA() -> None:
    """LA TRAMPA DE ESTE PUNTO, y por eso tiene brazo propio.

    `/api/range/validate` ya traia `from` y `to` -las fechas del tramo que valida- y era muy
    facil subir el `to` y llamarlo `as_of`. No vale: medido el 2026-09-10, ese `to` era
    2026-09-09, la ultima sesion CERRADA, o sea que el sello habria nacido con un dia de
    atraso. El instante de la respuesta se toma del reloj, y se comprueba contra el reloj.
    """
    antes = datetime.now(UTC)
    d = await _llamar(range_validate_endpoint, symbol=SIM, low=77000.0, high=80000.0)
    despues = datetime.now(UTC)
    visto = datetime.fromisoformat(d["as_of"].replace("Z", "+00:00"))
    assert antes <= visto <= despues, f"as_of={d['as_of']} fuera de [{antes}, {despues}]"
    if d.get("to"):
        assert d["as_of"][:10] >= str(d["to"]), (
            "el as_of no puede ser anterior al fin de la ventana que dice haber mirado"
        )
