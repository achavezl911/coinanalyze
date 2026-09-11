"""El TIPO de una transicion, contra Postgres de verdad.

POR QUE EXISTE. `is_transition` es un booleano, y bajo ese unico bit conviven poblaciones que
miden cosas distintas y estan medidas (COLA.md 110): el giro long<->short son 2 170 casos en el
arco 2026-08-10..2026-09-11 y COLA 110 §3 fila A le mide +9.28 pp de ventaja sobre una moneda,
mientras que la oscilacion alrededor de neutral son 161 621 casos a los que ese mismo bloque
atribuye un RANGO, +0.94..+4.24 pp, sobre la oscilacion ENTERA -y no un punto a cada mitad: su
§3 tiene fila para «toma opinion» y NO la tiene para «abandona op.»-. Quien lee «transicion» no
puede saber cual tiene delante. La ruta deriva ahora el TIPO, sin tocar `is_transition` ni el
fingerprint.

LO QUE ESTAS PRUEBAS FIJAN, y la segunda es la que no podia cazar ningun control de tabla:

  1 · el vocabulario es CERRADO y viaja DENTRO de la respuesta. Un tipo que hay que adivinar
      desde fuera no es un vocabulario: es una convencion no escrita.
  2 · EL TIPO NO DEPENDE DE LA VENTANA PEDIDA. La misma observacion tiene que salir con el mismo
      tipo caiga la primera de la respuesta o caiga por el medio. Con un `LAG` acotado a la
      ventana la primera fila de CADA respuesta pierde su predecesora, y eso NO es una rareza:
      medido en 140 el 2026-09-11 sobre 189 ventanas de 1 h, le pasaria al 100 % de ellas.
  3 · una fila sin predecesora se DECLARA `no_predecessor` en vez de adivinarse.
  4 · una fila con is_transition=false no recibe tipo de transicion.

No reimplementan el SELECT: llaman a `api.signals_ledger` con un pool de pega, asi que si el
SELECT de la ruta deja de arrastrar la fila anterior, estas pruebas no pueden ponerse verdes.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest

import app.api as api

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")

SIMBOLO = "BTCUSDT_PERP.A"
BASE = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


@pytest.fixture
async def conn():
    schema = f"tipotr_{uuid.uuid4().hex}"
    connection = await asyncpg.connect(_dsn())
    await connection.execute(f'CREATE SCHEMA "{schema}"')
    await connection.execute(f'SET search_path TO "{schema}", public')
    await connection.execute("SET TIME ZONE 'UTC'")
    await connection.execute(SCHEMA_SQL)
    try:
        yield connection
    finally:
        await connection.execute("SET search_path TO public")
        await connection.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await connection.close()


class _Adquisicion:
    def __init__(self, conexion) -> None:
        self._conexion = conexion

    async def __aenter__(self):
        return self._conexion

    async def __aexit__(self, *_exc) -> bool:
        return False


class _PoolDePega:
    def __init__(self, conexion) -> None:
        self._conexion = conexion

    def acquire(self) -> _Adquisicion:
        return _Adquisicion(self._conexion)


async def _observacion(
    conn, n: int, direction: str, *, transicion: bool, state: str = "range"
) -> datetime:
    """Una fila del ledger. `n` es el minuto desde BASE y tambien el observation_id.

    LAS RESTRICCIONES DE LA TABLA MANDAN, no lo que a este test le venga bien: schema.sql:467
    ata `direction` a `decision_status` y a `actionable` -unavailable exige not_evaluable y no
    accionable; long/short exigen evaluable y accionable; neutral exige evaluable y NO
    accionable-, y schema.sql:466 exige `is_periodic OR is_transition`. Se derivan aqui en vez
    de pasarlas a mano: un fixture que las falsee estaria probando una fila que produccion no
    puede escribir.
    """
    ts = BASE + timedelta(minutes=n)
    if direction == "unavailable":
        estado, accionable, confianza = "not_evaluable", False, "baja"
    elif direction == "neutral":
        estado, accionable, confianza = "evaluable", False, "baja"
    else:
        estado, accionable, confianza = "evaluable", True, "media"
    await conn.execute(
        "INSERT INTO signal_observation("
        "  observation_id, observed_at, observed_minute, symbol, signal_family,"
        "  is_periodic, is_transition, logic_version, evidence_version, sampling_version,"
        "  decision_status, direction, actionable, state, confidence, reason,"
        "  long_score, short_score, evidence_coverage_pct,"
        "  collector_shard_index, collector_shard_count, decision_fingerprint, evidence"
        # observation_id es GENERATED ALWAYS: aqui se fija a proposito para poder nombrar
        # las filas en las aserciones sin depender de que secuencia le toque.
        ") OVERRIDING SYSTEM VALUE VALUES($1,$2,$2,$3,'scalp',true,$4,'v1',1,1,"
        "  $5,$6,$7,$8,$9,'x',50,50,100,0,1,$10,'{}'::jsonb)",
        n, ts, SIMBOLO, transicion, estado, direction, accionable, state, confianza,
        f"{n:064d}",   # el fingerprint es CHECK length()=64; aqui solo hace falta que sea unico
    )
    return ts


async def _pide(conn, since: datetime, until: datetime) -> dict:
    api.app.state.pool = _PoolDePega(conn)
    return await api.signals_ledger(
        request=_Peticion(), symbol=SIMBOLO,
        since=since.isoformat(), until=until.isoformat(), limit=1000,
    )


class _Peticion:
    query_params = {"symbol": SIMBOLO, "since": "x", "until": "y", "limit": "1000"}


def _tipo(payload: dict, observation_id: int) -> str:
    for fila in payload["observations"]:
        if fila["observation_id"] == observation_id:
            return fila["transition_type"]
    raise AssertionError(f"{observation_id} no vino en la respuesta")


@pytest.mark.asyncio
async def test_el_tipo_es_el_mismo_se_pida_la_ventana_que_se_pida(conn) -> None:
    """EL CONTROL QUE NINGUN CONTROL DE TABLA PODIA HACER.

    La observacion 3 es un giro long->short. Se pide en dos ventanas: en una queda la PRIMERA
    de la respuesta y en la otra queda por el medio. Si el tipo dependiera de la ventana, la
    primera saldria `no_predecessor` y la otra `direction_flip`.
    """
    await _observacion(conn, 0, "neutral", transicion=False)
    await _observacion(conn, 1, "long", transicion=True)
    await _observacion(conn, 2, "long", transicion=False)
    giro = await _observacion(conn, 3, "short", transicion=True)
    await _observacion(conn, 4, "neutral", transicion=True)

    fin = BASE + timedelta(minutes=30)
    primera = await _pide(conn, giro, fin)
    enmedio = await _pide(conn, BASE, fin)

    assert primera["observations"][0]["observation_id"] == 3, "el montaje no dejo la fila la 1a"
    assert [f["observation_id"] for f in enmedio["observations"]][:4] == [0, 1, 2, 3]

    assert _tipo(primera, 3) == "direction_flip"
    assert _tipo(enmedio, 3) == "direction_flip"
    assert _tipo(primera, 3) == _tipo(enmedio, 3)


@pytest.mark.asyncio
async def test_los_cuatro_tipos_de_la_medida_salen_donde_tienen_que_salir(conn) -> None:
    await _observacion(conn, 0, "neutral", transicion=False)
    await _observacion(conn, 1, "long", transicion=True)          # neutral -> long
    await _observacion(conn, 2, "short", transicion=True)         # long -> short
    await _observacion(conn, 3, "neutral", transicion=True)       # short -> neutral
    await _observacion(conn, 4, "unavailable", transicion=True)   # neutral -> unavailable
    # misma direccion, cambia el state: es el cubo que la medida de COLA 110 no desgloso
    await _observacion(conn, 5, "unavailable", transicion=True, state="trend")

    d = await _pide(conn, BASE, BASE + timedelta(minutes=30))
    assert _tipo(d, 0) == "not_a_transition"
    assert _tipo(d, 1) == "opinion_taken"
    assert _tipo(d, 2) == "direction_flip"
    assert _tipo(d, 3) == "opinion_dropped"
    assert _tipo(d, 4) == "availability_change"
    assert _tipo(d, 5) == "same_direction"


@pytest.mark.asyncio
async def test_unavailable_a_unavailable_cae_en_UN_solo_cubo_y_se_puede_predecir(conn) -> None:
    """EL SOLAPE QUE HABIA EN LAS DESCRIPCIONES, y son 13 filas de verdad.

    `unavailable -> unavailable` con is_transition cumple «la direccion NO cambio» Y cumplia
    «uno de los dos lados es unavailable», asi que las dos descripciones publicadas valian para
    la misma fila y lo unico que desempataba era el orden de los WHEN, que el consumidor no ve.
    Medido en 140 sobre 270 697 filas del arco 2026-08-10T15:20:16Z..2026-09-11T05:24:00Z: son
    13 filas en los 3 simbolos, y de los 15 pares (previa -> actual) que existen con transicion
    es el UNICO que se solapaba -se enumeraron los 15, no se comparo un conteo-.

    El reparto NO cambia: sigue siendo `same_direction`. Lo que cambia es que ahora la
    descripcion de `availability_change` exige que la direccion CAMBIE, asi que se puede
    predecir sin leer el SQL.
    """
    await _observacion(conn, 0, "neutral", transicion=False)
    await _observacion(conn, 1, "unavailable", transicion=True)
    await _observacion(conn, 2, "unavailable", transicion=True, state="trend")

    d = await _pide(conn, BASE, BASE + timedelta(minutes=30))
    assert _tipo(d, 1) == "availability_change", "neutral -> unavailable si cambia de direccion"
    assert _tipo(d, 2) == "same_direction", "unavailable -> unavailable NO cambia de direccion"

    # Y LA DESAMBIGUACION TIENE QUE SEGUIR PUBLICADA. Es un criterio sobre TEXTO y por eso es
    # debil (A3): no caza una reescritura que diga lo mismo con otras palabras. Esta para que
    # nadie la borre por descuido, no para probar el reparto -eso lo prueban las dos lineas de
    # arriba, que son comportamiento-.
    assert "CAMBIO" in d["transition_types"]["availability_change"], \
        "sin exigir que la direccion cambie, esta descripcion vuelve a solaparse con same_direction"
    assert "unavailable" in d["transition_types"]["same_direction"]


@pytest.mark.asyncio
async def test_sin_predecesora_se_declara_y_no_se_adivina(conn) -> None:
    """La primerisima observacion de un simbolo no tiene anterior.

    Si ademas viniera marcada como transicion -que en produccion no pasa: las tres primeras
    filas de los tres simbolos son is_transition=false-, el tipo no se puede determinar y se
    DICE, que es lo contrario de meterla en un cubo cualquiera.
    """
    await _observacion(conn, 0, "long", transicion=True)
    d = await _pide(conn, BASE, BASE + timedelta(minutes=30))
    assert _tipo(d, 0) == "no_predecessor"


@pytest.mark.asyncio
async def test_una_fila_que_no_es_transicion_nunca_recibe_tipo_de_transicion(conn) -> None:
    """EL NEGATIVO. Sin el, lo de arriba seria una maquina de repartir tipos."""
    await _observacion(conn, 0, "neutral", transicion=False)
    await _observacion(conn, 1, "long", transicion=False)   # cambia la direccion y NO es transicion
    await _observacion(conn, 2, "short", transicion=False)  # giro que NO es transicion
    d = await _pide(conn, BASE, BASE + timedelta(minutes=30))
    for fila in d["observations"]:
        assert fila["transition_type"] == "not_a_transition", fila["observation_id"]


@pytest.mark.asyncio
async def test_el_vocabulario_es_CERRADO_y_viaja_con_el_dato(conn) -> None:
    await _observacion(conn, 0, "neutral", transicion=False)
    await _observacion(conn, 1, "long", transicion=True)
    d = await _pide(conn, BASE, BASE + timedelta(minutes=30))

    assert "transition_types" in d, "el vocabulario no viaja con la respuesta"
    vocabulario = set(d["transition_types"])
    assert vocabulario == {
        "direction_flip", "opinion_taken", "opinion_dropped",
        "availability_change", "same_direction", "not_a_transition", "no_predecessor",
    }
    # CERRADO: ningun tipo servido puede quedarse fuera de lo declarado.
    for fila in d["observations"]:
        assert fila["transition_type"] in vocabulario, fila["transition_type"]

    # Y NO SE VENDE COMO SENAL DE ENTRADA. Esta medido que no paga (COLA.md 110): al mejor tipo
    # le falta un factor 2.3 contra la comision maker. Este brazo existe para que nadie lo
    # convierta en un rotulo de operar sin darse cuenta.
    #
    # EL SUJETO SON LOS ROTULOS, NO LA ADVERTENCIA, y esto lo cazo el propio control: la primera
    # version prohibia la palabra «entrada» en TODO el bloque y saltaba contra la nota, que dice
    # «no una senal de entrada». Un control que se mueve ante la NEGACION del fenomeno ademas de
    # ante el fenomeno no distingue los dos (A36). Lo que puede leerse como un rotulo de operar
    # son las CLAVES y sus descripciones; la nota es justo lo contrario y se comprueba aparte.
    rotulos = " ".join(d["transition_types"]) + " " + " ".join(d["transition_types"].values())
    for palabra in ("entrada", "oportunidad", "comprar", "vender", "entry", "buy", "sell"):
        assert palabra not in rotulos.lower(), f"el vocabulario invita a operar: «{palabra}»"
    # y la advertencia SI tiene que estar, con las dos palabras que la hacen inequivoca
    nota = d["transition_types_nota"].lower()
    assert "contexto" in nota and "no una senal de entrada" in nota, d["transition_types_nota"]
