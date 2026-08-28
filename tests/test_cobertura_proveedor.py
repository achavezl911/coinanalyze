"""Un hueco del proveedor no puede degradarnos a nosotros; que nos callemos, si.

Medido contra 140 el 2026-08-25: en 24 h la fuente devolvio 261 de 289 buckets de
long_short_ratio para SOLUSDT_PERP.A y 285 de 289 para BTCUSDT_PERP.A, y nuestra base
tenia EXACTAMENTE 261 y 285. Aceptamos el 100% de lo que llega. Aun asi,
ingest:metrics_5m llevaba semanas en 'degraded' por ese missing=29, y arrastraba a
/api/healthz entero: un indicador encendido por algo que nadie puede apagar.

Lo que estos tests fijan es la distincion, no el numero: se degrada por lo NUESTRO.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

import pytest

import app.data_gaps as data_gaps
from app.data_gaps import CadenceCoverage, reconcile_cadence_coverage
from app.ingest import _coverage_heartbeat_detail


def _cobertura(esperados: int, observados: int) -> CadenceCoverage:
    inicio = datetime(2026, 8, 25, tzinfo=UTC)
    return CadenceCoverage(
        start=inicio,
        end=inicio + timedelta(hours=24),
        cadence=timedelta(minutes=5),
        expected_buckets=esperados,
        observed_buckets=observados,
        missing_buckets=esperados - observados,
        missing_windows=(),
        recovered_gaps=0,
    )


def test_un_hueco_del_proveedor_no_nos_degrada() -> None:
    """El caso real: faltan 28 buckets de 289 y no rechazamos ni una fila."""
    estado, detalle = _coverage_heartbeat_detail(
        feed="metrics_5m",
        cutoff=datetime(2026, 8, 25, tzinfo=UTC),
        rows={"long_short": 261},
        coverages=[("long_short_ratio@binance:response24h", _cobertura(289, 261))],
        rejected=0,
    )
    assert estado == "ok"
    # Pero el hueco NO se esconde: sigue publicado para quien lo quiera mirar.
    assert "missing=28" in detalle
    assert "rejected=0" in detalle


def test_si_tiramos_filas_que_la_fuente_mando_eso_si_degrada() -> None:
    estado, detalle = _coverage_heartbeat_detail(
        feed="metrics_5m",
        cutoff=datetime(2026, 8, 25, tzinfo=UTC),
        rows={"long_short": 260},
        coverages=[("long_short_ratio@binance:response24h", _cobertura(289, 260))],
        rejected=1,
    )
    assert estado == "degraded"
    assert "rejected=1" in detalle


def test_una_fuente_que_se_calla_del_todo_degrada() -> None:
    """Sin esto el arreglo seria una tapadera: cero filas tambien da rejected=0."""
    estado, _ = _coverage_heartbeat_detail(
        feed="metrics_5m",
        cutoff=datetime(2026, 8, 25, tzinfo=UTC),
        rows={"long_short": 0},
        coverages=[("long_short_ratio@binance:response24h", _cobertura(289, 0))],
        rejected=0,
    )
    assert estado == "degraded"


def test_sin_el_dato_de_rechazadas_se_mantiene_el_comportamiento_viejo() -> None:
    """ohlcv sigue llamando sin rejected: no se le cambia el criterio por la espalda."""
    estado, _ = _coverage_heartbeat_detail(
        feed="ohlcv_1m",
        cutoff=datetime(2026, 8, 25, tzinfo=UTC),
        rows=100,
        coverages=[("ohlcv@binance:response24h", _cobertura(289, 261))],
    )
    assert estado == "degraded"


# --------------------------------------------------------------------------------
# SEGUNDA MITAD DE LA MISMA DOCTRINA, medida el 2026-08-25.
#
# Lo de arriba fijo que un hueco de la fuente no nos DEGRADA. Faltaba lo otro: ese
# hueco se seguia apuntando en data_gap como 'unresolved', o sea como deuda nuestra
# pendiente de recuperar, y nunca se cerro ninguno.
#
# Medido contra la fuente desde 140, ventana de 7 dias
# 2026-08-18T19:55Z..2026-08-25T19:45Z, long-short-ratio-history 5min:
#     BTC 2005 buckets, deltas [(5min,1994),(10min,10)]
#     ETH 2005 buckets, deltas [(5min,1994),(10min,10)]
#     SOL 1853 buckets, deltas [(5min,1690),(10min,162)]
# y la MISMA consulta con lag(ts) sobre long_short_ratio en 140 da exactamente
# 1994/10, 1994/10 y 1690/162. 5863 buckets y ni una fila de diferencia.
#
# Tres cosas que eso deja claras, y las tres estan aqui:
#  1. La cadencia de 5 min es CORRECTA tambien para SOL: 1690 de sus 1852 intervalos
#     son de 5 min exactos. No hay una "cadencia por simbolo" que arregle esto; darle
#     10 min a SOL tiraria 1690 observaciones buenas.
#  2. La ausencia es PERMANENTE. Una peticion hecha HOY sobre esos 7 dias devuelve los
#     MISMOS 162 huecos de SOL que apuntamos hace dias: la fuente no rellena despues.
#     Un hueco asi no es una tarea pendiente, es un hecho sobre el dato.
#  3. La prueba es lo que la fuente DEVOLVIO, no lo que nosotros ACEPTAMOS. La
#     diferencia entre las dos cosas es la fila que tiramos al validar, y esa es
#     nuestra. Es la misma distincion returned/accepted de
#     _liquidation_history_observation, que estos feeds no hacian.
#
# La regla que fijan estos tests es la que NO se puede aflojar: solo se archiva la
# ausencia cuando hay PRUEBA de que la respuesta cubria ese bucket, o sea cuando la
# fuente contesto antes y despues del hueco y no lo mando. Si se calla, si trunca, si
# el hueco esta al principio, si la fila la tiramos nosotros, o si la ausencia es de
# nuestro propio almacen, el hueco se queda 'unresolved' y la fuga sigue viendose.
# --------------------------------------------------------------------------------

# La lista negra de harness/checks/K04-huecos.sh: un motivo que case con esto habla de
# NOSOTROS, y el check lo cuenta como archivado en falso.
EXCUSAS_K04 = re.compile(
    r"(no exact historical source|no adapter|sin adaptador|unsupported)", re.I
)

INICIO = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)
FIN = INICIO + timedelta(hours=1)
CADENCIA = timedelta(minutes=5)
REJILLA = [INICIO + CADENCIA * i for i in range(12)]
SALTADO = INICIO + timedelta(minutes=25)


class ConnEspia:
    """Conexion falsa que solo apunta lo que se ejecuta."""

    def __init__(self, pendientes=None) -> None:
        self.ejecutado: list[tuple[str, tuple]] = []
        # Las filas que ya estan en data_gap sin resolver, las haya apuntado el detector
        # que sea. Modelarlas importa: el archivado tiene que alcanzar tambien las de OTRO
        # detection_source, que es donde vive el atraso.
        self.pendientes = list(pendientes or [])

    async def fetch(self, _query: str, *_args):
        return self.pendientes

    async def execute(self, query: str, *args):
        self.ejecutado.append((query, args))
        return "UPDATE 1"

    def archivados(self) -> list[tuple[str, tuple]]:
        return [(q, a) for q, a in self.ejecutado if "unrecoverable" in q]


def _pendiente(idx: int, inicio: datetime, fin: datetime) -> dict:
    return {"id": idx, "start_ts": inicio, "end_ts": fin}


async def _reconciliar(conn, observaciones, *, devueltos=None):
    """devueltos=None es el detector que mira NUESTRO almacen; no prueba nada de la fuente."""
    apuntados: list[datetime] = []

    async def falso_record(_conn, **kw):
        apuntados.append(kw["start"])
        return len(apuntados)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(data_gaps, "record_data_gap", falso_record)
        cobertura = await reconcile_cadence_coverage(
            conn,
            observations=observaciones,
            feed="long_short_ratio",
            exchange="binance",
            market="perpetual",
            symbol="SOLUSDT_PERP.A",
            granularity="5min",
            start=INICIO,
            end=FIN,
            cadence=CADENCIA,
            detection_source="historical_ingest_response_cadence_v2",
            source_response_buckets=devueltos,
        )
    return cobertura, apuntados


@pytest.mark.asyncio
async def test_un_bucket_que_la_fuente_salta_no_queda_como_deuda_nuestra() -> None:
    """El caso real de SOL: la respuesta cubre la ventana y se salta un bucket."""
    conn = ConnEspia([_pendiente(1, SALTADO, SALTADO + CADENCIA)])
    sin_el = [t for t in REJILLA if t != SALTADO]

    cobertura, apuntados = await _reconciliar(conn, sin_el, devueltos=sin_el)

    # El hueco SE SIGUE APUNTANDO: no se esconde, se clasifica.
    assert apuntados == [SALTADO]
    assert cobertura.missing_buckets == 1

    archivados = conn.archivados()
    assert len(archivados) == 1, "la ausencia probada tiene que quedar archivada"
    query, _args = archivados[0]
    # Inmutable: solo toca lo que sigue pendiente, nunca reescribe una clasificacion.
    assert "status='unresolved'" in query


@pytest.mark.asyncio
async def test_el_motivo_habla_del_dato_y_no_de_nuestra_limitacion() -> None:
    """La trampa que K04 cierra: 'no tenemos adaptador' no es un motivo sobre el dato."""
    conn = ConnEspia([_pendiente(1, SALTADO, SALTADO + CADENCIA)])
    sin_el = [t for t in REJILLA if t != SALTADO]

    await _reconciliar(conn, sin_el, devueltos=sin_el)

    _query, args = conn.archivados()[0]
    motivo = next(a for a in args if isinstance(a, str) and " " in a)
    assert "source" in motivo and "publish" in motivo
    assert not EXCUSAS_K04.search(motivo), f"motivo que K04 cuenta como excusa: {motivo}"


@pytest.mark.asyncio
async def test_la_fila_que_TIRAMOS_NOSOTROS_no_se_le_carga_a_la_fuente() -> None:
    """La fuente SI mando ese bucket y lo descartamos al validar: el hueco es nuestro."""
    conn = ConnEspia([_pendiente(1, SALTADO, SALTADO + CADENCIA)])
    aceptados = [t for t in REJILLA if t != SALTADO]

    _cobertura, apuntados = await _reconciliar(conn, aceptados, devueltos=REJILLA)

    assert apuntados == [SALTADO]
    assert conn.archivados() == [], "lo que tiramos nosotros no es ausencia de la fuente"


@pytest.mark.asyncio
async def test_una_fuente_que_se_calla_deja_el_hueco_pendiente() -> None:
    """Sin esto el arreglo seria una tapadera: silencio total no prueba nada."""
    conn = ConnEspia()

    cobertura, apuntados = await _reconciliar(conn, [], devueltos=[])

    assert cobertura.missing_buckets == 12
    assert len(apuntados) == 1  # una sola ventana, la hora entera
    assert conn.archivados() == [], "el silencio de la fuente no archiva nada"


@pytest.mark.asyncio
async def test_una_respuesta_truncada_no_prueba_la_ausencia_de_la_cola() -> None:
    """Si la fuente corta a mitad, lo que falta detras puede ser suyo o nuestro."""
    conn = ConnEspia([_pendiente(1, INICIO + timedelta(minutes=30), FIN)])
    media = [t for t in REJILLA if t < INICIO + timedelta(minutes=30)]

    _cobertura, apuntados = await _reconciliar(conn, media, devueltos=media)

    assert apuntados == [INICIO + timedelta(minutes=30)]
    assert conn.archivados() == [], "la cola que falta no la cubre la respuesta"


@pytest.mark.asyncio
async def test_un_hueco_al_principio_tampoco_esta_probado() -> None:
    """Nada demuestra que la fuente cubriera un bucket anterior a su primera fila."""
    conn = ConnEspia([_pendiente(1, INICIO, INICIO + CADENCIA)])

    await _reconciliar(conn, REJILLA[1:], devueltos=REJILLA[1:])

    assert conn.archivados() == []


@pytest.mark.asyncio
async def test_la_ausencia_en_NUESTRO_almacen_no_dice_nada_de_la_fuente() -> None:
    """_reconcile_persisted_cadence mira nuestras filas: ahi el hueco SI puede ser nuestro."""
    conn = ConnEspia([_pendiente(1, SALTADO, SALTADO + CADENCIA)])
    sin_el = [t for t in REJILLA if t != SALTADO]

    _cobertura, apuntados = await _reconciliar(conn, sin_el, devueltos=None)

    assert apuntados == [SALTADO]
    assert conn.archivados() == [], "nuestro propio hueco sigue siendo deuda nuestra"


# --------------------------------------------------------------------------------
# TERCERA PIEZA: LO QUE LA FUENTE YA NO SIRVE, medido el 2026-08-25.
#
# reconcile_cadence_coverage se ABSTIENE cuando la fuente no contesta, y eso esta
# bien: ausencia de respuesta no es ausencia en la fuente. Pero deja un techo. Medido
# el 2026-08-25 20:32Z sondeando long-short-ratio-history 5min en tramos de 3 h: la
# fuente sirve hasta 2026-08-17 12:30Z -200 h justas, 2400 buckets de 5 min- y ni uno
# mas atras. De los 502 huecos unresolved, 179 caen dentro de ese horizonte y 323 no
# (65 de long_short_ratio del 08-11 al 08-17, y los 258 de ohlcv_1min del 08-14, cuyo
# horizonte son 24-48 h). Esos 323 no los puede clasificar la re-peticion NUNCA.
#
# Para archivarlos hace falta OTRA prueba, y la clave es distinguir "la fuente ya no
# sirve esa ventana" de "la fuente esta caida", porque las dos devuelven vacio. Por eso
# se exige un CONTROL: una ventana reciente de la MISMA identidad que SI devuelve
# serie. Sin control positivo no se archiva nada, y eso es lo que impide que una caida
# del proveedor se convierta en un barrido silencioso de todo el atraso.
# --------------------------------------------------------------------------------

VENTANA_INI = datetime(2026, 8, 14, 0, 0, tzinfo=UTC)
VENTANA_FIN = datetime(2026, 8, 15, 0, 0, tzinfo=UTC)
CONTROL_INI = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)
CONTROL_FIN = datetime(2026, 8, 25, 18, 0, tzinfo=UTC)


async def _archivar(conn, *, filas_de_control: int):
    return await data_gaps.archive_beyond_source_horizon(
        conn,
        feed="ohlcv_1min", exchange="binance", market="perpetual",
        symbol="BTCUSDT_PERP.A", granularity="1min",
        window_start=VENTANA_INI, window_end=VENTANA_FIN,
        control_start=CONTROL_INI, control_end=CONTROL_FIN,
        control_returned_rows=filas_de_control,
    )


@pytest.mark.asyncio
async def test_una_fuente_CALLADA_no_prueba_un_horizonte_agotado() -> None:
    """El guardia que impide que una caida del proveedor barra el atraso entero."""
    conn = ConnEspia()

    with pytest.raises(ValueError, match="control"):
        await _archivar(conn, filas_de_control=0)

    assert conn.ejecutado == [], "sin control positivo no se toca ni una fila"


@pytest.mark.asyncio
async def test_el_horizonte_agotado_se_archiva_con_su_propia_prueba() -> None:
    conn = ConnEspia()

    await _archivar(conn, filas_de_control=71)

    assert len(conn.archivados()) == 1
    query, args = conn.archivados()[0]
    assert "status='unresolved'" in query, "no reescribe lo ya clasificado"
    assert "'provider_horizon_exhausted'" in query
    assert "'window_returned_rows',0" in query.replace(" ", "")
    assert 71 in args, "el numero de filas del control se guarda, no se da por bueno"


@pytest.mark.asyncio
async def test_el_motivo_del_horizonte_es_OTRO_hecho_que_el_de_la_ausencia() -> None:
    """Son dos hechos distintos sobre el dato y no se pueden confundir en la auditoria."""
    assert data_gaps.PROVIDER_HORIZON_REASON != data_gaps.SOURCE_ABSENCE_REASON
    for motivo in (data_gaps.PROVIDER_HORIZON_REASON, data_gaps.SOURCE_ABSENCE_REASON):
        assert not EXCUSAS_K04.search(motivo), f"motivo que K04 cuenta como excusa: {motivo}"
    # El del horizonte habla de la VENTANA; el de la ausencia, del BUCKET.
    assert "window" in data_gaps.PROVIDER_HORIZON_REASON
    assert "bucket" in data_gaps.SOURCE_ABSENCE_REASON


# --- El troceado del repaso. Es logica del script, y se equivoca en silencio: una
# ventana de mas es una peticion tirada, y una de menos es un hueco que nadie repasa.


def test_el_repaso_trocea_sin_dejar_agujeros_ni_solapar() -> None:
    from scripts.resweep_cadence_gaps import _windows

    desde = datetime(2026, 8, 10, tzinfo=UTC)
    hasta = datetime(2026, 8, 12, 6, tzinfo=UTC)
    cadencia = timedelta(minutes=5)
    ventanas = _windows(desde, hasta, timedelta(hours=24), cadencia)

    assert ventanas[0][0] == desde, "la primera no puede empezar antes del atraso"
    assert ventanas[-1][1] == hasta, "la ultima ventana no puede pasarse del final"
    assert len(ventanas) == 3  # 24h + 24h + 6h
    for (_, fin_previa), (ini_siguiente, _) in zip(ventanas[:-1], ventanas[1:], strict=True):
        # SOLAPE hacia atras, no corte limpio: un hueco pegado al principio de su ventana
        # no se puede probar, y sin solape ninguna pasada lo clasificaria nunca.
        assert ini_siguiente == fin_previa - cadencia * 2
        assert ini_siguiente < fin_previa, "sin solape queda un residuo permanente"


@pytest.mark.asyncio
async def test_el_repaso_cuenta_como_presente_lo_que_YA_ESTA_GUARDADO() -> None:
    """K66 · un hueco es un dato que NO TENEMOS, no una respuesta que no llego.

    Medido en 140 el 2026-08-28: de los 1325 buckets que historical_resweep_cadence_v1
    declaraba ausentes, 1312 estaban en long_short_ratio. El 99.0 % de sus huecos eran
    datos que ya teniamos, porque las observaciones salian SOLO de la respuesta de esa
    pasada. Si el proveedor contesta truncado, todo lo demas de la ventana le parece
    ausente aunque este guardado.
    """

    from scripts.resweep_cadence_gaps import PLANS, observaciones_conocidas

    plan = PLANS[("long_short_ratio", "5min")]
    inicio = datetime(2026, 8, 20, tzinfo=UTC)
    guardados = [inicio + timedelta(minutes=5) * i for i in range(6)]
    aceptado = guardados[0]

    class ConexionQueTieneElDato:
        def __init__(self) -> None:
            self.consultas: list[str] = []

        async def fetch(self, sql: str, *args):
            self.consultas.append(" ".join(sql.split()))
            return [{"ts": ts} for ts in guardados[1:]]

    conn = ConexionQueTieneElDato()
    ident = {"symbol": "BTCUSDT_PERP.A"}
    conocidas = await observaciones_conocidas(
        conn, plan, ident, inicio, inicio + timedelta(minutes=30), {aceptado}
    )

    # La union, que es el punto: lo de la pasada MAS lo que ya estaba.
    assert conocidas == set(guardados)
    # Y se le pregunta a la tabla del plan, no a una deducida del feed: una tabla
    # equivocada devolveria el conjunto vacio, que es indistinguible de "no tenemos nada"
    # y volveria a declarar huecos falsos EN SILENCIO.
    assert "FROM long_short_ratio" in conn.consultas[0]
    assert PLANS[("ohlcv_1min", "1min")] is not plan


def test_el_repaso_conoce_los_dos_feeds_con_atraso_y_sus_cadencias() -> None:
    """Un feed sin plan NO se toca: se apunta en 'sin_plan' y se deja como estaba."""
    from scripts.resweep_cadence_gaps import PLANS

    assert PLANS[("long_short_ratio", "5min")].cadence == timedelta(minutes=5)
    assert PLANS[("ohlcv_1min", "1min")].cadence == timedelta(minutes=1)
    assert ("orderbook", "1min") not in PLANS


@pytest.mark.asyncio
async def test_el_archivado_alcanza_el_hueco_QUE_APUNTO_OTRO_DETECTOR() -> None:
    """MEDIDO EN 140 EL 2026-08-25, y es el fallo que este test existe para que no vuelva.

    record_data_gap lleva detection_source en la clave de conflicto, asi que el mismo
    bucket visto por dos detectores son DOS filas. La primera pasada del repaso archivo
    172 filas RECIEN CREADAS por el y dejo las 244 originales intactas: se archivo a si
    mismo. El atraso vive en filas de otro detection_source, asi que el archivado tiene
    que ser ENTRE DETECTORES, igual que ya lo era la recuperacion.
    """
    conn = ConnEspia([_pendiente(77, SALTADO, SALTADO + CADENCIA)])
    sin_el = [t for t in REJILLA if t != SALTADO]

    await _reconciliar(conn, sin_el, devueltos=sin_el)

    ids = [args[0] for _q, args in conn.archivados()]
    assert 77 in ids, "el archivado no alcanza la fila que apunto otro detector"
