"""K70 · el barrido ancho de cadencia, contra Postgres de verdad.

EL DEFECTO MEDIDO EN 140 EL 2026-08-30. data_gap contiene DOS pares feed/granularidad en
toda su vida -long_short_ratio/5min y ohlcv_1min/1min-. open_interest, oi_bybit,
funding_rate y predicted_funding_rate suman CERO filas, en cualquier estado, y sin
embargo a los cuatro les faltan 408 buckets cada uno en la ventana del 25 al 30 de
agosto. Contados sobre toda la serie retenida, 2099 buckets de metricas sin ninguna fila
que los cubra.

Y ES PEOR QUE "NO HAY DETECTOR", PORQUE SI LO HAY: ingest.py llama a
_reconcile_response_cadence para los cinco feeds en cada ciclo. Un detector que corre y
nunca dispara no se distingue de un feed sano.

LA CAUSA ES DE MECANISMO Y SON DOS DETECTORES DISTINTOS. El de RESPUESTA compara contra
lo que la fuente devolvio: solo ve lo que ella se salto dentro de un tramo que contesto.
Si estuvimos caidos 37 h y al volver pedimos 26, lo anterior no se le pregunto a nadie,
no esta en la respuesta, no esta en la ventana y NO EXISTE. El PERSISTIDO compara contra
la tabla, y ahi un bucket que no tenemos falta se pregunte lo que se pregunte. La
funcion persistida aceptaba las SEIS tablas de cadencia y se la llamaba con UNA. Es K69
otra vez: una funcion honesta a la que casi nadie llama no protege de casi nada.

LO QUE ESTAS PRUEBAS EXIGEN, y ninguna se contesta citando el codigo:
  · que el barrido DECLARE lo que el detector vivo no alcanza, en las siete series
  · que NO declare dentro del margen que se cura solo, con su control positivo al lado
  · que NO invente huecos antes de que la serie exista ni detras de la retencion
  · que NO duplique lo que otro detector ya declaro -y SI vuelva a apuntar lo suyo,
    porque de eso depende que un tramo recuperado que vuelve a faltar bloquee otra vez-
  · que distinga binance de bybit, que comparten nombre de feed
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest

from app.ingest import (
    PERSISTED_CADENCE_DETECTION_SOURCE,
    barrido_cadencia_persistido,
    ventana_barrido_cadencia,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")
SYMBOL = "BTCUSDT_PERP.A"
SYMBOLS = (SYMBOL,)
HARD_DAYS = 90

# INSERT por tabla de metrica. Las cinco tienen la misma forma -ts, symbol, interval y
# cuatro columnas de valor- pero con prefijos distintos, y long_short_ratio ninguno.
SIEMBRA = {
    "open_interest": "INSERT INTO open_interest(ts,symbol,interval,oi_open,oi_high,oi_low,oi_close)"
    " VALUES($1,$2,'5min',10,11,9,10)",
    "oi_bybit": "INSERT INTO oi_bybit(ts,symbol,interval,oi_open,oi_high,oi_low,oi_close)"
    " VALUES($1,$2,'5min',10,11,9,10)",
    "funding_rate": "INSERT INTO funding_rate(ts,symbol,interval,fr_open,fr_high,fr_low,fr_close)"
    " VALUES($1,$2,'5min',0.01,0.02,0.0,0.01)",
    "predicted_funding_rate": "INSERT INTO predicted_funding_rate"
    "(ts,symbol,interval,pfr_open,pfr_high,pfr_low,pfr_close)"
    " VALUES($1,$2,'5min',0.01,0.02,0.0,0.01)",
    "long_short_ratio": "INSERT INTO long_short_ratio(ts,symbol,interval,long_pct,short_pct,ratio)"
    " VALUES($1,$2,'5min',50,50,1)",
}
FEED = {
    "open_interest": ("open_interest_5min", "binance"),
    "oi_bybit": ("open_interest_5min", "bybit"),
    "funding_rate": ("funding_rate", "binance"),
    "predicted_funding_rate": ("predicted_funding_rate", "binance"),
    "long_short_ratio": ("long_short_ratio", "binance"),
}
CADENCIA = timedelta(minutes=5)
# El margen de autocuracion de las metricas, el mismo que declara BARRIDO_CADENCIA: el
# ciclo pide 26 h en cada pasada y el barrido se para una hora antes de esa frontera.
MARGEN = timedelta(hours=27)


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


@pytest.fixture
async def conn():
    schema = f"barrido_cad_{uuid.uuid4().hex}"
    connection = await asyncpg.connect(_dsn())
    await connection.execute(f'CREATE SCHEMA "{schema}"')
    await connection.execute(f'SET search_path TO "{schema}", public')
    await connection.execute("SET TIME ZONE 'UTC'")
    await connection.execute(SCHEMA_SQL)
    await connection.execute(
        "INSERT INTO market_assets(base_asset) VALUES('BTC') ON CONFLICT DO NOTHING"
    )
    await connection.execute(
        "INSERT INTO symbols(symbol,base_asset) VALUES($1,'BTC') ON CONFLICT DO NOTHING",
        SYMBOL,
    )
    try:
        yield connection
    finally:
        await connection.execute("SET search_path TO public")
        await connection.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await connection.close()


def _piso5(momento: datetime) -> datetime:
    return datetime.fromtimestamp(int(momento.timestamp()) // 300 * 300, tz=UTC)


async def _sembrar(conn, tabla: str, marcas: list[datetime]) -> None:
    for ts in marcas:
        await conn.execute(SIEMBRA[tabla], ts, SYMBOL)


def _corte(ahora: datetime) -> datetime:
    """Donde el barrido se para: el mismo piso que calcula ventana_barrido_cadencia.

    Las series de prueba se anclan AQUI y no "hace cinco dias" por un motivo que la
    primera version de este fichero aprendio fallando: la ventana llega hasta el corte,
    asi que una serie que acaba antes deja TODO lo que va de su ultimo bucket al corte
    como un segundo hueco enorme, y las aserciones miden ese y no el sembrado.
    """
    return _piso5(ahora - MARGEN)


async def _serie_con_hueco(
    conn, tabla: str, ahora: datetime, *, huecos: int = 3, buckets: int = 12
) -> datetime:
    """`buckets` contiguos pegados al corte, con `huecos` arrancados del medio.

    Devuelve el primer ausente. Los buckets de los extremos importan: sin ellos el hueco
    tocaria el borde de la ventana y no se distinguiria de "la serie no habia empezado".
    """
    base = _corte(ahora) - buckets * CADENCIA
    presentes = [base + i * CADENCIA for i in range(buckets) if not 4 <= i < 4 + huecos]
    await _sembrar(conn, tabla, presentes)
    return base + 4 * CADENCIA


async def _huecos(conn, feed: str, exchange: str) -> list[asyncpg.Record]:
    return await conn.fetch(
        "SELECT start_ts,end_ts,status,detection_source FROM data_gap"
        " WHERE feed=$1 AND exchange=$2 AND symbol=$3 ORDER BY start_ts",
        feed, exchange, SYMBOL,
    )


async def _barre(conn, ahora: datetime) -> dict[str, int]:
    return await barrido_cadencia_persistido(
        conn, SYMBOLS, hard_days=HARD_DAYS, ahora=ahora
    )


# ── LO QUE EL DETECTOR VIVO NO ALCANZA ──────────────────────────────────────────────

@pytest.mark.parametrize("tabla", sorted(SIEMBRA))
async def test_declara_el_hueco_viejo_de_cada_serie(conn, tabla):
    """Las CINCO series de metricas, una por una. Es el fallo medido: cuatro de ellas no
    tienen ni una fila en 140 y el barrido tiene que ser capaz de escribirla."""
    ahora = datetime.now(UTC)
    primer_ausente = await _serie_con_hueco(conn, tabla, ahora)
    feed, exchange = FEED[tabla]

    assert await _huecos(conn, feed, exchange) == [], "control: nace sin ninguna fila"

    resumen = await _barre(conn, ahora)

    filas = await _huecos(conn, feed, exchange)
    assert len(filas) == 1, f"{tabla}: se esperaba UNA ventana, no {len(filas)}"
    assert filas[0]["start_ts"] == primer_ausente
    assert filas[0]["end_ts"] == primer_ausente + 3 * CADENCIA
    assert filas[0]["status"] == "unresolved"
    assert filas[0]["detection_source"] == PERSISTED_CADENCE_DETECTION_SOURCE
    assert resumen["ventanas"] >= 1


async def test_bybit_no_se_tapa_con_las_filas_de_binance(conn):
    """open_interest_5min existe DOS veces con exchange distinto. Si la identidad no
    llevara el exchange, el hueco de bybit se daria por declarado con la fila de binance
    y quedaria mudo justo el feed que menos se mira."""
    ahora = datetime.now(UTC)
    ausente_binance = await _serie_con_hueco(conn, "open_interest", ahora)
    # bybit: misma serie completa salvo OTRO tramo, mas adelante.
    base = _corte(ahora) - 12 * CADENCIA
    await _sembrar(conn, "oi_bybit", [base + i * CADENCIA for i in range(12) if i != 9])

    await _barre(conn, ahora)

    binance = await _huecos(conn, "open_interest_5min", "binance")
    bybit = await _huecos(conn, "open_interest_5min", "bybit")
    assert [f["start_ts"] for f in binance] == [ausente_binance]
    assert [f["start_ts"] for f in bybit] == [base + 9 * CADENCIA]


# ── LAS NEGATIVAS, QUE ES DONDE UN DETECTOR SE ESTROPEA ──────────────────────────────

async def test_no_declara_el_hueco_que_cae_despues_del_corte(conn):
    """El ciclo de metricas pide 26 h en CADA pasada, asi que una ausencia mas joven que
    eso todavia va a rellenarse sola. Declararla seria un hueco que nace resuelto.

    La serie EMPIEZA antes del corte -o sea que si hay ventana que barrer, y esto no
    pasa por casualidad de una tabla vacia- y el hueco esta al otro lado."""
    ahora = datetime.now(UTC)
    corte = _corte(ahora)
    antes = [corte - i * CADENCIA for i in range(1, 7)]
    despues = [corte + i * CADENCIA for i in range(12) if i != 5]
    await _sembrar(conn, "open_interest", sorted(antes + despues))

    await _barre(conn, ahora)

    assert await _huecos(conn, "open_interest_5min", "binance") == []


async def test_control_positivo_el_mismo_hueco_antes_del_corte_si_se_declara(conn):
    """El control que hace util a la prueba de arriba: sin el, un barrido roto que no
    declarara NUNCA nada pasaria aquella con nota. Cambia UNA cosa: de que lado del
    corte esta el hueco."""
    ahora = datetime.now(UTC)
    corte = _corte(ahora)
    antes = [corte - i * CADENCIA for i in range(1, 7) if i != 3]
    despues = [corte + i * CADENCIA for i in range(12)]
    await _sembrar(conn, "open_interest", sorted(antes + despues))

    await _barre(conn, ahora)

    filas = await _huecos(conn, "open_interest_5min", "binance")
    assert [f["start_ts"] for f in filas] == [corte - 3 * CADENCIA]


async def test_no_reprocha_ausencias_anteriores_al_primer_dato(conn):
    """Antes de que la serie exista no hay ausencia que reprochar. Sin este limite, una
    tabla que empezo hace una semana saldria con 90 dias de huecos inventados."""
    ahora = datetime.now(UTC)
    base = _corte(ahora) - 12 * CADENCIA
    await _sembrar(conn, "funding_rate", [base + i * CADENCIA for i in range(12)])

    await _barre(conn, ahora)

    assert await _huecos(conn, "funding_rate", "binance") == []


async def test_no_mira_mas_atras_de_la_retencion(conn):
    """Lo que apply_retention borra por politica no es un hueco. La serie empieza mucho
    antes de la retencion, asi que el limite lo pone el tope y no el min(ts)."""
    ahora = datetime.now(UTC)
    viejisimo = _piso5(ahora - timedelta(days=HARD_DAYS + 20))
    await _sembrar(conn, "long_short_ratio", [viejisimo, viejisimo + CADENCIA])
    base = _corte(ahora) - 12 * CADENCIA
    await _sembrar(conn, "long_short_ratio", [base + i * CADENCIA for i in range(12)])

    await _barre(conn, ahora)

    filas = await _huecos(conn, "long_short_ratio", "binance")
    tope = _piso5(ahora - timedelta(days=HARD_DAYS))
    assert len(filas) == 1, "control positivo: el tramo DENTRO de la retencion si se declara"
    assert filas[0]["start_ts"] == tope, "la ventana empieza EN el tope, ni antes ni despues"
    assert filas[0]["end_ts"] == base


def test_la_ventana_se_abstiene_cuando_la_serie_esta_vacia():
    """min(ts) NULL es "no hay serie", no "falta todo". Devolver una ventana aqui haria
    que una tabla vacia -el momento en que mas falta hace mirar- saliera con la
    retencion entera declarada como hueco."""
    ahora = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
    assert ventana_barrido_cadencia(ahora, None, HARD_DAYS, CADENCIA, timedelta(hours=27)) is None


def test_la_ventana_se_abstiene_cuando_la_serie_es_mas_joven_que_el_margen():
    """Una serie que nacio hace una hora esta entera dentro de lo que se cura solo."""
    ahora = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
    primera = ahora - timedelta(hours=1)
    assert ventana_barrido_cadencia(
        ahora, primera, HARD_DAYS, CADENCIA, timedelta(hours=27)
    ) is None


# ── NO DUPLICAR LO QUE OTRO DETECTOR YA VIO ─────────────────────────────────────────

async def _fila_ajena(conn, inicio: datetime, fin: datetime, *, fuente: str) -> None:
    await conn.execute(
        """
        INSERT INTO data_gap(
          feed,feed_class,exchange,market,symbol,granularity,start_ts,end_ts,
          expected_cadence,evidence_type,detection_reason,detection_source,status,
          resolved_at)
        VALUES('long_short_ratio','cadence','binance','perpetual',$1,'5min',$2,$3,
               interval '5 minutes','missing_interval','sembrado por la prueba',$4,
               'unrecoverable',now())
        """,
        SYMBOL, inicio, fin, fuente,
    )


async def test_no_duplica_el_tramo_que_otro_detector_ya_declaro(conn):
    """EL CASO REAL: long_short_ratio tiene 371 filas de historical_ingest_response_
    cadence_v2 en 140. Sin esta guarda, la primera pasada del barrido escribiria 371
    duplicadas y K04 contaria el doble de huecos de los que hubo."""
    ahora = datetime.now(UTC)
    ausente = await _serie_con_hueco(conn, "long_short_ratio", ahora)
    await _fila_ajena(
        conn, ausente, ausente + 3 * CADENCIA, fuente="historical_ingest_response_cadence_v2"
    )

    resumen = await _barre(conn, ahora)

    filas = await _huecos(conn, "long_short_ratio", "binance")
    assert len(filas) == 1, "la fila ajena ya cubria el tramo entero"
    assert filas[0]["detection_source"] == "historical_ingest_response_cadence_v2"
    assert filas[0]["status"] == "unrecoverable", "no se toca lo archivado por otro"
    assert resumen["omitidas"] == 1, "y se dice que se omitio, en vez de callarlo"
    assert resumen["ventanas"] == 0


async def test_una_cobertura_PARCIAL_no_basta_para_omitir(conn):
    """Duplicar de mas es ruido visible; callar de menos es perdida muda otra vez. La
    fila ajena tapa dos de los tres buckets, asi que el barrido apunta igual."""
    ahora = datetime.now(UTC)
    ausente = await _serie_con_hueco(conn, "long_short_ratio", ahora)
    await _fila_ajena(
        conn, ausente, ausente + 2 * CADENCIA, fuente="historical_ingest_response_cadence_v2"
    )

    resumen = await _barre(conn, ahora)

    fuentes = {f["detection_source"] for f in await _huecos(conn, "long_short_ratio", "binance")}
    assert PERSISTED_CADENCE_DETECTION_SOURCE in fuentes
    assert resumen["omitidas"] == 0


async def test_lo_declarado_por_NOSOTROS_si_se_vuelve_a_apuntar(conn):
    """CONTROL NEGATIVO DE LA GUARDA, y es el que impide que sea un tapon. Un tramo que
    se recupero y vuelve a faltar tiene que BLOQUEAR otra vez, y eso solo pasa si el
    barrido vuelve a apuntar la fila propia. Si la guarda mirara tambien nuestra fuente,
    esta prueba caeria y el hueco reaparecido quedaria marcado como recuperado."""
    ahora = datetime.now(UTC)
    ausente = await _serie_con_hueco(conn, "long_short_ratio", ahora)
    await conn.execute(
        """
        INSERT INTO data_gap(
          feed,feed_class,exchange,market,symbol,granularity,start_ts,end_ts,
          expected_cadence,evidence_type,detection_reason,detection_source,status,
          recovered_at,resolved_at)
        VALUES('long_short_ratio','cadence','binance','perpetual',$1,'5min',$2,$3,
               interval '5 minutes','missing_interval','apuntado antes',$4,
               'recovered',now(),now())
        """,
        SYMBOL, ausente, ausente + 3 * CADENCIA, PERSISTED_CADENCE_DETECTION_SOURCE,
    )

    resumen = await _barre(conn, ahora)

    filas = await _huecos(conn, "long_short_ratio", "binance")
    assert len(filas) == 1, "sigue siendo UNA fila: ON CONFLICT, no duplicado"
    assert filas[0]["status"] == "unresolved", "el hueco que vuelve tiene que bloquear"
    assert resumen["omitidas"] == 0


# ── RECUPERAR TAMBIEN ES TRABAJO DEL BARRIDO ────────────────────────────────────────

async def test_recupera_el_hueco_cuyos_buckets_ya_estan_todos(conn):
    """Un hueco que otro detector dejo abierto y cuyo dato ya llego se cierra en el mismo
    barrido. Sin esto el barrido solo sabria acusar, y la cuenta de K04 no bajaria nunca."""
    ahora = datetime.now(UTC)
    base = _corte(ahora) - 12 * CADENCIA
    marcas = [base + i * CADENCIA for i in range(12)]
    await _sembrar(conn, "open_interest", marcas)
    await conn.execute(
        """
        INSERT INTO data_gap(
          feed,feed_class,exchange,market,symbol,granularity,start_ts,end_ts,
          expected_cadence,evidence_type,detection_reason,detection_source,status)
        VALUES('open_interest_5min','cadence','binance','perpetual',$1,'5min',$2,$3,
               interval '5 minutes','missing_interval','lo vio el detector vivo',
               'historical_ingest_response_cadence_v2','unresolved')
        """,
        SYMBOL, marcas[4], marcas[7],
    )

    resumen = await _barre(conn, ahora)

    filas = await _huecos(conn, "open_interest_5min", "binance")
    assert len(filas) == 1
    assert filas[0]["status"] == "recovered"
    assert resumen["recuperadas"] == 1


# ── LAS LIQUIDACIONES NO ENTRAN, Y NO ES UN OLVIDO ──────────────────────────────────

def test_el_barrido_no_le_inventa_cadencia_a_un_feed_de_sucesos():
    """liquidations es un feed de SUCESOS: que no haya filas puede significar que no hubo
    liquidaciones. Meterlo en el barrido fabricaria huecos donde solo hay mercado quieto.
    Se comprueba en la tabla del barrido y no en un comentario."""
    from app.ingest import BARRIDO_CADENCIA

    assert not any(tabla == "liquidations" for tabla, *_ in BARRIDO_CADENCIA)
    assert {tabla for tabla, *_ in BARRIDO_CADENCIA} == {
        "ohlcv", "open_interest", "oi_bybit", "funding_rate",
        "predicted_funding_rate", "long_short_ratio",
    }
