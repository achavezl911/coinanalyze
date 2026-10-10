"""C4 de la campana 136 · EL REGISTRO ESPERA AL SPOT, contra Postgres de verdad.

EL ACTOR es un colector de mentira que escribe los dos ultimos minutos de spot y de futuros de la
vela CON RETRASO, como el de produccion: cada minuto aparece cuando ya no puede llegarle un trade
tardio. El retraso es el MEDIDO en 140 (RETRASO_S), ni exacto ni cero, y un brazo cae en el borde
del ultimo intento. Al cerrar la vela la base tiene, como en produccion, hasta el minuto T - 3.

LOS RELOJES son los del reglamento del arbol (v1 y v2 de verdad). El generador los lee de ahi, asi
que el banco solo los mueve: cada segundo x pasa a desfase + x / ESCALA, lo que deja arrancar el
test a mitad de una vela real y comprimir la espera conservando el orden y las proporciones
(entradas_banco.doc_de_prueba). ENTRADAS_ESCALA_ESPERA=1 los corre A TIEMPO REAL (minutos).

Lo que se promete, cada cosa con su control y su plantado:
  a  la vela de v2 cuyo spot llega con su retraso se decide con el spot COMPLETO: DISPARADO si todo
     cumple, SOMBRA de filtro si el spot va en contra; ya no «hueco». Y los futuros, igual.
  b  si el spot NO esta en el ultimo intento: SOMBRA de datos con su motivo. Y un DISPARADO por
     encima del tope lo rechaza LA BASE (EN001) y queda SOMBRA «tardio».
  c  v1 no cambia de reloj: registra en su primer intento aunque v2 espere.
  d  funcion de T: ningun insumo de la foto es posterior a T, y la huella no depende de cuando
     ni de cuantos intentos.
  e  no estorba: la recoleccion mantiene su cadencia mientras la pasada espera.
  f  la recuperacion ni espera ni dispara, y no repite lo que la pasada muerta ya registro.
  plantados: un generador que decide v2 SIN esperar (cae contra a) y otro que hace esperar tambien
  a v1 (cae contra c).
"""

from __future__ import annotations

import asyncio
import copy
import json
import os
import random
import time
from datetime import datetime, timedelta
from types import SimpleNamespace

import asyncpg
import entradas_banco as B
import pytest
from test_entradas_registro_postgres import (  # noqa: F401 - `conn` es la base desechable
    SIMBOLOS,
    _ahora_T,
    _dsn,
    conn,
)
from test_entradas_servicio import _con_recolector

from app.entradas import codigo as C
from app.entradas import foto as F
from app.entradas import insumos as I
from app.entradas import motor as M
from app.entradas import registro as G
from app.entradas import reglamento as R
from app.entradas import servicio as S

# EL RETRASO MEDIDO, en segundos desde que el minuto CIERRA hasta que esta con las dos venues y
# 60 s (spot y futuros de BTC, ETH y SOL, los seis). Produccion (140, release 191c2fb), solo
# lectura, un sondeo cada ~4 s durante 80 minutos, 2026-10-09 23:06Z a 2026-10-10 00:26Z:
# /srv/coinanalyze/x1-tmp/l1-c4-mide.sh y l1-c4-analiza.py (entrega de la campana 136, C4).
RETRASO_S = {"min": 126.9, "mediana": 129.8, "max": 132.6}
ESCALA = float(os.environ.get("ENTRADAS_ESCALA_ESPERA", "10"))
RAPIDA = ESCALA * 4  # los brazos en que no se juzga un margen de tiempo, solo el orden
DOS = ("v1", "v2")
BTC, ETH, SOL = (s for s, _ in SIMBOLOS)
VELA_S = 900


def _espera(doc: dict, version: str) -> dict:
    """Los relojes de una version del doc de prueba, en segundos REALES desde el cierre de T."""
    c = R.valores(R.version(doc, version)["bloques"]["comun"])
    return {**c["espera_datos_s"], "tope": c["tope_retraso_s"]}


async def _escenario(conn, *, escala: float, mercados: dict) -> tuple[datetime, dict, float, dict]:  # noqa: F811
    """Siembra la vela T actual SIN sus dos ultimos minutos de flujo (la base llega hasta T - 3,
    como en produccion al cerrar la vela) y devuelve (T, doc, desfase, reloj): el doc lleva los
    relojes del arbol movidos a `desfase` segundos del cierre real de T."""
    T = await _ahora_T(conn)
    bases = dict(SIMBOLOS)
    for symbol, ins in mercados.items():
        await B.sembrar(conn, T, ins(T), symbol, bases[symbol], minutos_de_flujo=58)
    ahora = await conn.fetchval("SELECT clock_timestamp()")
    desfase = (ahora - T).total_seconds() + 0.3
    doc = B.doc_de_prueba(T, *DOS, desfase_s=desfase, escala=escala)
    return T, doc, desfase, {v: _espera(doc, v) for v in DOS}


async def _colector(esquema: str, T: datetime, desfase: float, escala: float, entregas: list) -> None:
    """EL ACTOR. Cada entrega: (segundos tras el cierre de la vela, simbolo, insumos, minuto,
    patas). Escribe por su propia conexion, como el colector de verdad."""
    bases = dict(SIMBOLOS)
    c = await asyncpg.connect(_dsn())
    try:
        await c.execute(f'SET search_path TO "{esquema}", public')
        for llegada, symbol, ins, minuto, patas in sorted(entregas, key=lambda e: e[0]):
            cuando = T + timedelta(seconds=desfase + llegada / escala)
            falta = (cuando - await c.fetchval("SELECT clock_timestamp()")).total_seconds()
            if falta > 0:
                await asyncio.sleep(falta)
            await B.sembrar_flujos(c, T, ins, symbol, bases[symbol], minutos=[minuto], patas=patas)
    finally:
        await c.close()


def _entregas(T: datetime, symbol: str, ins, llegada: float | None,
              patas: tuple[str, ...] = ("spot", "futuros")) -> list:
    """Los dos minutos que faltan al cerrar la vela: T - 2 min (cerro 60 s antes) y T - 1 min.
    `llegada` = retraso del colector desde el cierre del ultimo minuto; None = ese no llega."""
    entregas = [(RETRASO_S["mediana"] - 60, symbol, ins(T), 58, patas)]
    if llegada is not None:
        entregas.append((llegada, symbol, ins(T), 59, patas))
    return entregas


async def _filas(conn, version: str | None = None) -> list[dict]:  # noqa: F811
    filas = await conn.fetch(
        "SELECT registro_id, version, symbol, familia, lado, perfil, estado, motivo, retraso_s, "
        "tope_retraso_s, registered_at, vela_cierre, huella_foto, foto::text AS foto "
        "FROM entrada_registro WHERE perfil = 'intradia' AND ($1::text IS NULL OR version = $1) "
        "ORDER BY registro_id", version)
    return [dict(f) for f in filas]


def _gatillo(filas: list[dict], version: str, symbol: str) -> dict:
    """La fila terminal del rechazo de soporte (F1 largo) de un simbolo en una version."""
    suyas = [f for f in filas if (f["version"], f["symbol"], f["familia"], f["lado"]) ==
             (version, symbol, "F1", "largo") and f["estado"] in ("DISPARADO", "SOMBRA")]
    assert len(suyas) == 1, [(f["version"], f["symbol"], f["estado"], f["motivo"]) for f in filas]
    return {**suyas[0], "foto": json.loads(suyas[0]["foto"])}


def _cuenta(filas: list[dict], desfase: float, escala: float) -> str:
    """Para leer con -s: cada candidato, lo que salio y a cuantos segundos DEL REGLAMENTO (los
    del arbol, deshecho el movimiento del banco) del cierre de la vela se registro."""
    partes = []
    for f in filas:
        if (f["familia"], f["lado"]) == ("F1", "largo") and f["estado"] in ("DISPARADO", "SOMBRA"):
            tipo = json.loads(f["foto"])["decision"]["tipo_sombra"]
            salida = "DISPARADO" if f["estado"] == "DISPARADO" else (
                "SOMBRA tardio" if f["motivo"] == "tardio" else f"SOMBRA {tipo}")
            partes.append(f"{f['version']} {f['symbol'][:3]} {salida} a "
                          f"{(float(f['retraso_s']) - desfase) * escala:.1f} s")
    return " · ".join(partes)


def _fallos_a(filas: list[dict], esperado: dict[str, str]) -> list[str]:
    """EL CONTROL de C4 a: cada candidato de v2 se decidio con el spot COMPLETO (y los futuros),
    dentro de su tope, y salio lo que tenia que salir."""
    fallos = []
    for symbol, salida in esperado.items():
        f = _gatillo(filas, "v2", symbol)
        foto = f["foto"]
        nombre = symbol.split("USDT")[0]
        for pata in ("spot", "futuros"):
            for ventana in ("vela", "ultima_hora"):
                tramo = foto["flujos"][pata][ventana]
                if not tramo["completo"]:
                    fallos.append(f"{nombre}: {pata}.{ventana} incompleto al decidir "
                                  f"({tramo['minutos']} de {tramo['esperados']})")
        huecos = [n for n in ("spot_vela", "spot_hora") if foto["filtros"][n]["estado"] == "no_evaluable"]
        if huecos:
            fallos.append(f"{nombre}: {', '.join(huecos)} NO EVALUABLE "
                          f"(«{foto['filtros'][huecos[0]]['motivo']}»)")
        obtenido = f["estado"] if f["estado"] == "DISPARADO" else f"SOMBRA {foto['decision']['tipo_sombra']}"
        if f["motivo"] == "tardio":
            obtenido = "SOMBRA tardio"
        if obtenido != salida:
            fallos.append(f"{nombre}: salio {obtenido} ({f['motivo']}) y tenia que salir {salida}")
        if f["estado"] == "DISPARADO" and float(f["retraso_s"]) > float(f["tope_retraso_s"]):
            fallos.append(f"{nombre}: DISPARADO a {f['retraso_s']} s sobre su tope {f['tope_retraso_s']}")
    return fallos


def _fallos_c(filas: list[dict], reloj: dict) -> list[str]:
    """EL CONTROL de C4 c: las filas de v1 se registran en SU primer intento (los ~20 s de hoy),
    no cuando v2 termina de esperar. Margen para evaluar los tres simbolos: 2 s reales, o la mitad
    de lo que separa su primer intento del de v2 si eso es menos."""
    de_v1 = [f for f in filas if f["version"] == "v1"]
    if not de_v1:
        return ["v1 no registro nada"]
    primer_v1, primer_v2 = reloj["v1"]["primer_intento"], reloj["v2"]["primer_intento"]
    limite = primer_v1 + min(2.0, (primer_v2 - primer_v1) / 2)
    return [
        f"v1 registro {f['estado']} {f['symbol']} a {float(f['retraso_s']) - primer_v1:+.2f} s de su "
        "primer intento" + (" (despues del primer intento de v2)" if float(f["retraso_s"]) >= primer_v2 else "")
        for f in de_v1 if float(f["retraso_s"]) > limite
    ]


# --------------------------------------------------------------------------- a, c y d


def test_los_relojes_de_v2_salen_del_retraso_medido():
    """Lo que ata el actor al reglamento: v2 empieza a buscar justo despues del maximo medido, y
    su ultimo intento deja sitio antes del tope. v1 no espera flujos: con su tope no llegaria."""
    doc = R.cargar_valido()
    v1, v2 = (R.valores(R.version(doc, v)["bloques"]["comun"]) for v in DOS)
    assert RETRASO_S["min"] <= RETRASO_S["mediana"] <= RETRASO_S["max"]
    assert RETRASO_S["max"] < v2["espera_datos_s"]["primer_intento"] <= RETRASO_S["max"] + 10
    assert v2["espera_datos_s"]["ultimo_intento"] < v2["tope_retraso_s"] == 240
    assert v2["espera_flujos"] == ["spot", "futuros"] and "espera_flujos" not in v1
    assert v1["espera_datos_s"]["ultimo_intento"] < v1["tope_retraso_s"] < RETRASO_S["min"]


async def test_a_c_d_la_vela_de_v2_se_decide_con_el_spot_completo_y_v1_no_cambia_de_reloj(conn):  # noqa: F811
    mercados = {BTC: B.insumos, ETH: lambda T: B.insumos(T, spot_vela=-1e6), SOL: B.insumos}
    T, doc, desfase, reloj = await _escenario(conn, escala=ESCALA, mercados=mercados)
    esquema = await conn.fetchval("SELECT current_schema()")
    # EL BORDE: el ultimo minuto de SOL llega medio reintento ANTES del ultimo intento de v2 (los
    # segundos del reglamento del arbol, sin mover). BTC llega con un retraso de los medidos y ETH
    # con el maximo medido.
    del_arbol = B.comun("v2")["espera_datos_s"]
    borde = del_arbol["ultimo_intento"] - 0.5 * del_arbol["reintento"]
    azar = random.Random(136)
    entregas = (
        _entregas(T, BTC, mercados[BTC], azar.uniform(RETRASO_S["min"], RETRASO_S["mediana"]))
        + _entregas(T, ETH, mercados[ETH], RETRASO_S["max"])
        + _entregas(T, SOL, mercados[SOL], borde)
    )
    actor = asyncio.create_task(_colector(esquema, T, desfase, ESCALA, entregas))
    salida = await S.evaluar_vela(conn, T=T, doc=doc, huella_codigo="c" * 64, esperar=True)
    await actor
    filas = await _filas(conn)
    print(f"a/c (escala {ESCALA:g}): {_cuenta(filas, desfase, ESCALA)}")

    # a · v2 decide con el spot COMPLETO: las tres salidas, cada una con su nombre
    assert _fallos_a(filas, {BTC: "DISPARADO", ETH: "SOMBRA filtro", SOL: "DISPARADO"}) == []
    eth = _gatillo(filas, "v2", ETH)
    assert eth["foto"]["filtros"]["spot_vela"]["estado"] == "falla"
    assert "solo perpetuo" in eth["foto"]["decision"]["etiquetas"]  # exige los futuros completos
    sol = _gatillo(filas, "v2", SOL)
    llego = desfase + borde / ESCALA  # cuando el colector escribio su ultimo minuto
    assert llego <= float(sol["retraso_s"]) <= reloj["v2"]["tope"], (sol["retraso_s"], llego, reloj["v2"])
    assert float(sol["retraso_s"]) > float(eth["retraso_s"])
    intentos = {v["symbol"]: v["espera"] for v in salida if v["versiones"] == ["v2"] and v["perfil"] == "intradia"}
    assert all(e["listos"] for e in intentos.values()) and intentos[SOL]["intentos"] > intentos[BTC]["intentos"]
    for symbol in (BTC, ETH, SOL):
        assert F.validar_fila(_gatillo(filas, "v2", symbol)) == [], symbol

    # c · v1 no cambia de reloj, y con su reloj no ve el spot: sigue en SOMBRA de datos «hueco»
    assert _fallos_c(filas, reloj) == []
    for symbol in (BTC, ETH, SOL):
        v1 = _gatillo(filas, "v1", symbol)
        assert v1["estado"] == "SOMBRA" and v1["foto"]["decision"]["tipo_sombra"] == "datos", symbol
        assert "hueco de spot: 13 de 15" in v1["foto"]["filtros"]["spot_vela"]["motivo"]
        assert float(v1["retraso_s"]) < reloj["v2"]["primer_intento"] <= float(
            _gatillo(filas, "v2", symbol)["retraso_s"])

    # d · funcion de T: nada de la foto es posterior a T aunque se decidiera minutos despues, y
    # la misma vela evaluada MAS TARDE y de un solo intento da la misma huella
    v2 = R.version(doc, "v2")
    for symbol, base in SIMBOLOS:
        f = _gatillo(filas, "v2", symbol)
        tardias = [(que, hora) for que, hora in F.horas_de_insumos(f["foto"]) if F._instante(hora) > T]
        assert tardias == [], (symbol, tardias)
        cargados = await I.cargar(conn, symbol=symbol, base_asset=base, T=T, perfil="intradia",
                                  comun=R.valores(v2["bloques"]["comun"]),
                                  calendario=R.valores(v2["bloques"]["calendario"]), modo=M.PROSPECTIVO)
        otra_vez = M.paso(T=T, symbol=symbol, perfil="intradia", modo=M.PROSPECTIVO, versiones=[v2],
                          insumos=cargados, previos=[], revision=R.revision_vigente(doc, T),
                          codigo="c" * 64)
        huellas = {t["huella_foto"] for t in otra_vez["transiciones"]
                   if (t["familia"], t["lado"]) == ("F1", "largo") and t["estado"] != "VIGILANDO"}
        assert huellas == {f["huella_foto"]}, symbol


async def test_d_un_generador_que_apunta_su_espera_en_la_foto_cambia_la_huella(conn, monkeypatch):  # noqa: F811
    """El plantado de d: si el intento (o la hora) de la espera entrara en la foto, la misma vela
    daria otra huella segun cuando se evaluara. Aqui la base esta quieta y completa."""
    T = await _ahora_T(conn)
    await B.sembrar(conn, T, B.insumos(T), BTC, "BTC")
    doc = B.doc_de_prueba(T, *DOS, tope_s=900)
    v2 = R.version(doc, "v2")
    kw = {"symbol": BTC, "base_asset": "BTC", "T": T, "perfil": "intradia", "modo": M.PROSPECTIVO,
          "comun": R.valores(v2["bloques"]["comun"]), "calendario": R.valores(v2["bloques"]["calendario"])}

    async def huella() -> str:
        res = M.paso(T=T, symbol=BTC, perfil="intradia", modo=M.PROSPECTIVO, versiones=[v2],
                     insumos=await I.cargar(conn, **kw), previos=[], revision=R.revision_vigente(doc, T),
                     codigo="c" * 64)
        return next(t["huella_foto"] for t in res["transiciones"] if t["estado"] == "DISPARADO")

    assert await huella() == await huella()
    original = I.cargar
    veces = iter(range(1, 10))

    async def con_intento(conn_, **kwargs):
        insumos = await original(conn_, **kwargs)
        insumos["flujos"]["spot"]["vela"]["intento"] = next(veces)  # el plantado
        return insumos

    monkeypatch.setattr(I, "cargar", con_intento)
    assert await huella() != await huella(), "el control de la misma huella no ve la espera en la foto"


# --------------------------------------------------------------------------- b


async def test_b_el_spot_que_no_llega_es_sombra_de_datos_en_el_ultimo_intento(conn):  # noqa: F811
    mercados = {BTC: B.insumos, ETH: B.insumos, SOL: B.insumos}
    T, doc, desfase, reloj = await _escenario(conn, escala=ESCALA, mercados=mercados)
    esquema = await conn.fetchval("SELECT current_schema()")
    entregas = (
        _entregas(T, BTC, mercados[BTC], None, patas=("spot",))  # el ultimo minuto de spot NO llega
        + _entregas(T, BTC, mercados[BTC], RETRASO_S["mediana"], patas=("futuros",))
        + _entregas(T, ETH, mercados[ETH], RETRASO_S["mediana"])
        + _entregas(T, SOL, mercados[SOL], RETRASO_S["max"], patas=("spot",))
        + _entregas(T, SOL, mercados[SOL], None, patas=("futuros",))  # y a SOL no le llegan los futuros
    )
    actor = asyncio.create_task(_colector(esquema, T, desfase, ESCALA, entregas))
    await S.evaluar_vela(conn, T=T, doc=doc, huella_codigo="c" * 64, esperar=True)
    await actor
    filas = await _filas(conn)
    print(f"b (escala {ESCALA:g}): {_cuenta(filas, desfase, ESCALA)}")
    ultimo, tope = reloj["v2"]["ultimo_intento"], reloj["v2"]["tope"]

    btc = _gatillo(filas, "v2", BTC)
    assert btc["estado"] == "SOMBRA" and btc["foto"]["decision"]["tipo_sombra"] == "datos"
    assert btc["motivo"] == "spot_vela,spot_hora"
    assert btc["foto"]["filtros"]["spot_vela"]["motivo"] == "hueco de spot: 14 de 15 minutos con las 2 venues"
    assert btc["foto"]["flujos"]["futuros"]["vela"]["completo"] is True
    # ni antes del ultimo intento ni un reintento despues: EN el ultimo intento
    assert ultimo <= float(btc["retraso_s"]) <= ultimo + 1.0, (btc["retraso_s"], ultimo)
    assert _fallos_a(filas, {BTC: "DISPARADO"}) == [
        "BTC: spot.vela incompleto al decidir (14 de 15)",
        "BTC: spot.ultima_hora incompleto al decidir (59 de 60)",
        "BTC: spot_vela, spot_hora NO EVALUABLE («hueco de spot: 14 de 15 minutos con las 2 venues»)",
        "BTC: salio SOMBRA datos (spot_vela,spot_hora) y tenia que salir DISPARADO",
    ]
    # el simbolo atascado NO retrasa a los demas: ETH, que si tiene lo suyo, se decide a su hora
    assert _fallos_a(filas, {ETH: "DISPARADO"}) == []
    eth = _gatillo(filas, "v2", ETH)
    assert reloj["v2"]["primer_intento"] <= float(eth["retraso_s"]) < ultimo - 1.0, (eth["retraso_s"], reloj)
    # a SOL no le llegan los futuros: espera hasta el ultimo intento, la foto lo dice y el
    # DISPARADO sale igual, dentro del tope (los futuros no deciden: solo etiquetan)
    sol = _gatillo(filas, "v2", SOL)
    assert sol["estado"] == "DISPARADO" and sol["foto"]["flujos"]["futuros"]["vela"]["completo"] is False
    assert sol["foto"]["flujos"]["spot"]["vela"]["completo"] is True
    assert ultimo <= float(sol["retraso_s"]) <= tope, (sol["retraso_s"], ultimo, tope)


class _SinRelojPrevio:
    """Una conexion cuyo «SELECT clock_timestamp()» devuelve el cierre de la vela: apaga la
    consulta previa del cliente en registro.insertar para que lo unico que juzgue sea LA BASE."""

    def __init__(self, conexion, T):
        self._c, self._T = conexion, T

    def __getattr__(self, nombre):
        return getattr(self._c, nombre)

    async def fetchval(self, sql, *args):
        if sql.strip() == "SELECT clock_timestamp()":
            return self._T
        return await self._c.fetchval(sql, *args)


async def test_b_un_disparado_por_encima_del_tope_lo_rechaza_la_base_y_queda_tardio(conn):  # noqa: F811
    """El spot llega DESPUES del tope y todo lo demas cumple. Con el ultimo intento dentro del tope
    ningun intento de la pasada normal puede verlo (eso es la SOMBRA de datos del test anterior):
    solo lo ve una pasada que evalua la vela TARDE (un reinicio, una pasada anterior larga). Esa
    intenta el DISPARADO y es LA BASE quien lo rechaza: SOMBRA «tardio»."""
    T = await _ahora_T(conn)
    esquema = await conn.fetchval("SELECT current_schema()")
    for symbol, base in SIMBOLOS[:2]:
        await B.sembrar(conn, T, B.insumos(T), symbol, base, minutos_de_flujo=58)
    # Los relojes del arbol, movidos para que el tope de v2 venciera hace 1 s. La vela real tiene
    # que llevar cerrada lo bastante para que el tope de v1, que es menor, siga siendo positivo
    # (lo exige la base): la diferencia entre los dos topes del arbol, comprimida, y 2.5 s mas.
    topes = {v: B.comun(v)["tope_retraso_s"] for v in DOS}
    sitio = (topes["v2"] - topes["v1"]) / ESCALA + 2.5
    pasado = (await conn.fetchval("SELECT clock_timestamp()") - T).total_seconds()
    if pasado < sitio:
        await asyncio.sleep(sitio - pasado)
        pasado = (await conn.fetchval("SELECT clock_timestamp()") - T).total_seconds()
    doc = B.doc_de_prueba(T, *DOS, desfase_s=pasado - topes["v2"] / ESCALA - 1.0, escala=ESCALA)
    tope = _espera(doc, "v2")["tope"]
    assert 0 < _espera(doc, "v1")["tope"] < tope < pasado
    v2 = R.version(doc, "v2")
    kw = {"symbol": BTC, "base_asset": "BTC", "T": T, "perfil": "intradia", "modo": M.PROSPECTIVO,
          "comun": R.valores(v2["bloques"]["comun"]), "calendario": R.valores(v2["bloques"]["calendario"])}
    # EL COLECTOR LLEGA AHORA, con el tope ya vencido: hasta este instante al spot le faltaban sus
    # dos ultimos minutos
    assert not (await I.cargar(conn, **kw))["flujos"]["spot"]["vela"]["completo"]
    await _colector(esquema, T, pasado, 1.0, [(0.0, s, B.insumos(T), m, ("spot", "futuros"))
                                              for s in (BTC, ETH) for m in (58, 59)])
    assert I.listos(await I.cargar(conn, **kw), kw["comun"])

    # 1 · LA BASE: el DISPARADO de v2 que el motor decide, insertado tal cual, lo rechaza EN001
    res = M.paso(T=T, symbol=BTC, perfil="intradia", modo=M.PROSPECTIVO, versiones=[v2],
                 insumos=await I.cargar(conn, **kw), previos=[], revision=R.revision_vigente(doc, T),
                 codigo="c" * 64)
    disparado = next(t for t in res["transiciones"] if t["estado"] == "DISPARADO")
    assert disparado["tope_retraso_s"] == tope
    with pytest.raises(asyncpg.PostgresError) as exc:
        await conn.fetchrow(G._INSERTA_REGISTRO, *G._argumentos(disparado, "c" * 64))
    assert exc.value.sqlstate == G.TARDIO and "DISPARADO tardio" in str(exc.value)

    # 2 · un generador SIN la consulta previa del cliente: la base lo rechaza y queda SOMBRA «tardio»
    vigilando = next(t for t in res["transiciones"] if t["estado"] == "VIGILANDO"
                     and t["episodio"] == disparado["episodio"])
    await G.insertar(conn, vigilando, "c" * 64)
    r = await G.insertar(_SinRelojPrevio(conn, T), disparado, "c" * 64)
    assert (r["estado"], r["motivo"]) == ("SOMBRA", "tardio") and r["retraso_s"] > tope

    # 3 · y la pasada entera, con el generador de verdad: ETH, que cumple todo, queda «tardio»
    await S.evaluar_vela(conn, T=T, doc=doc, huella_codigo="c" * 64, esperar=True)
    filas = await _filas(conn)
    assert not [f for f in filas if f["estado"] == "DISPARADO"]
    eth = _gatillo(filas, "v2", ETH)
    assert (eth["estado"], eth["motivo"]) == ("SOMBRA", "tardio")
    assert eth["foto"]["decision"]["estado"] == "DISPARADO"  # la foto es la del DISPARADO que no fue
    assert _fallos_a(filas, {ETH: "DISPARADO"}) == ["ETH: salio SOMBRA tardio (tardio) y tenia que salir DISPARADO"]
    btc = _gatillo(filas, "v2", BTC)
    assert btc["huella_foto"] == disparado["huella_foto"] and btc["motivo"] == "tardio"


# --------------------------------------------------------------------------- los plantados


async def test_plantado_un_generador_que_decide_v2_sin_esperar_cae_contra_a(conn, monkeypatch):  # noqa: F811
    """El generador de la campana 135: decide en cuanto tiene su vela de 1 min, sin mirar si el
    colector ya escribio. Con el mismo actor, v2 registra «hueco» y el control a lo condena."""
    T, doc, desfase, reloj = await _escenario(conn, escala=RAPIDA, mercados={BTC: B.insumos})
    esquema = await conn.fetchval("SELECT current_schema()")

    async def sin_dormir(_conn, _momento):
        return None

    monkeypatch.setattr(S, "_hasta", sin_dormir)
    monkeypatch.setattr(I, "listos", lambda insumos, _comun: I.vela_de_T_completa(insumos))
    actor = asyncio.create_task(_colector(esquema, T, desfase, RAPIDA,
                                          _entregas(T, BTC, B.insumos, RETRASO_S["mediana"])))
    await S.evaluar_vela(conn, T=T, doc=doc, huella_codigo="c" * 64, esperar=True)
    filas = await _filas(conn)
    await actor
    print(f"plantado sin esperar (escala {RAPIDA:g}): {_cuenta(filas, desfase, RAPIDA)}")
    fallos = _fallos_a(filas, {BTC: "DISPARADO"})
    assert fallos[-1] == "BTC: salio SOMBRA datos (spot_vela,spot_hora) y tenia que salir DISPARADO", fallos
    assert len(fallos) == 6 and "NO EVALUABLE («hueco de spot:" in fallos[4], fallos
    assert all("incompleto al decidir" in f for f in fallos[:4]), fallos
    assert float(_gatillo(filas, "v2", BTC)["retraso_s"]) < reloj["v2"]["primer_intento"]
    assert _fallos_c(filas, reloj) == []  # contra c no cae: v1 sigue en su sitio


async def test_plantado_un_generador_que_hace_esperar_tambien_a_v1_cae_contra_c(conn, monkeypatch):  # noqa: F811
    """Un generador que arranca todos los grupos en el primer intento MAS TARDIO: v2 decide bien y
    v1 deja de registrar a sus ~20 s."""
    T, doc, desfase, reloj = await _escenario(conn, escala=RAPIDA, mercados={BTC: B.insumos})
    esquema = await conn.fetchval("SELECT current_schema()")
    original = S._hasta
    tardio = T + timedelta(seconds=reloj["v2"]["primer_intento"])

    async def todos_a_la_vez(conn_, _momento):
        await original(conn_, tardio)

    monkeypatch.setattr(S, "_hasta", todos_a_la_vez)
    actor = asyncio.create_task(_colector(esquema, T, desfase, RAPIDA,
                                          _entregas(T, BTC, B.insumos, RETRASO_S["mediana"])))
    await S.evaluar_vela(conn, T=T, doc=doc, huella_codigo="c" * 64, esperar=True)
    await actor
    filas = await _filas(conn)
    print(f"plantado v1 espera (escala {RAPIDA:g}): {_cuenta(filas, desfase, RAPIDA)}")
    assert _fallos_a(filas, {BTC: "DISPARADO"}) == []  # contra a no cae: v2 espero
    fallos = _fallos_c(filas, reloj)
    assert fallos and all("despues del primer intento de v2" in f for f in fallos), fallos


# --------------------------------------------------------------------------- e


async def test_e_la_pasada_que_espera_no_mueve_la_cadencia_de_la_recoleccion(conn):  # noqa: F811
    """La pasada dura lo que dura la espera de v2, pero duerme en SU hilo y con SU conexion: un
    recolector con el planificador real de ingest (un tick por segundo) no pierde ninguno, y una
    segunda pasada mientras la primera vive se salta en vez de pisarla."""
    esquema = await conn.fetchval("SELECT current_schema()")
    ajustes = SimpleNamespace(pg_dsn=_dsn())
    marcas: dict[str, float] = {}

    async def plantar() -> None:
        T, doc, desfase, reloj = await _escenario(conn, escala=RAPIDA, mercados={BTC: B.insumos})
        # nadie escribe el ultimo minuto: la pasada espera hasta el ultimo intento de v2
        marcas["dura"] = reloj["v2"]["ultimo_intento"] - desfase

        def en_su_hilo() -> None:
            async def corre() -> None:
                c = await asyncpg.connect(_dsn())
                try:
                    await c.execute(f'SET search_path TO "{esquema}", public')
                    await S.evaluar_vela(c, T=T, doc=doc, huella_codigo="c" * 64, esperar=True)
                finally:
                    await c.close()

            asyncio.run(corre())

        marcas["t0"] = time.monotonic()
        primera = asyncio.create_task(S.pasada(ajustes, objetivo=en_su_hilo, tope_s=600))
        await asyncio.sleep(0.5)
        await S.pasada(ajustes, objetivo=en_su_hilo, tope_s=600)  # la primera sigue viva: se salta
        marcas["segunda"] = time.monotonic() - marcas["t0"]
        await primera
        marcas["primera"] = time.monotonic() - marcas["t0"]

    cuenta, duraciones = await _con_recolector(plantar, (3.0, 0.0, 3.0))
    por_segundo = [c / d for c, d in zip(cuenta, duraciones, strict=True)]
    print(f"espera de v2: filas por fase {cuenta} en {duraciones} s -> {por_segundo}")
    assert marcas["dura"] >= 3, "la espera comprimida es demasiado corta para medir la cadencia"
    assert marcas["primera"] >= marcas["dura"] - 1.0 and marcas["segunda"] < 2.0, marcas
    assert min(por_segundo) >= 0.6 * max(por_segundo), (cuenta, duraciones)
    filas = await _filas(conn, "v2")
    assert len([f for f in filas if f["estado"] == "SOMBRA"]) == 1  # una sola pasada evaluo la vela


# --------------------------------------------------------------------------- f


async def _por_episodio(conn) -> dict[tuple[str, str], int]:  # noqa: F811
    filas = await conn.fetch(
        "SELECT episodio, (estado = 'VIGILANDO') AS vigilando, count(*)::int AS n "
        "FROM entrada_registro GROUP BY 1, 2"
    )
    return {(f["episodio"], "VIGILANDO" if f["vigilando"] else "terminal"): f["n"] for f in filas}


async def test_una_vela_reevaluada_no_registra_dos_veces(conn):  # noqa: F811
    """Una pasada que muere a medias (un reinicio durante la espera) no deja latido: al volver,
    la recuperacion re-evalua esa vela con los mismos previos (< T) y el motor vuelve a emitir
    las mismas transiciones. Lo que ya estaba registrado no se registra otra vez."""
    T = await _ahora_T(conn)
    doc = B.doc_de_prueba(T, tope_s=900)
    await B.sembrar(conn, T, B.insumos(T), BTC, "BTC")
    primera = await S.evaluar_vela(conn, T=T, doc=doc, huella_codigo="c" * 64, esperar=False)
    antes = await _por_episodio(conn)
    assert antes and set(antes.values()) == {1}, antes
    assert any(r["estado"] == "DISPARADO" for v in primera for r in v["registradas"])
    segunda = await S.evaluar_vela(conn, T=T, doc=doc, huella_codigo="c" * 64, esperar=False)
    despues = await _por_episodio(conn)
    assert despues == antes, {k: n for k, n in despues.items() if n != antes.get(k)}
    repetidas = [r for v in segunda for r in v["registradas"]]
    assert repetidas and not any(r["registrado"] for r in repetidas), repetidas
    assert all("ya registrada" in r["rechazo"] for r in repetidas), repetidas


async def test_f_la_recuperacion_ni_espera_ni_dispara_ni_repite(conn, monkeypatch):  # noqa: F811
    """La pasada ENTERA (servicio._pasada_async) tras un reinicio. La vela anterior quedo a medias:
    v1 habia registrado y la pasada murio mientras v2 esperaba (sin latido). Al volver se evalua
    esa vela SIN esperar -aunque su ultimo minuto de spot no este- y nada de ella dispara; lo que
    v1 ya tenia no se repite. La vela en curso si espera."""
    # la pasada entera calcula T ella misma: que a la vela real le quede sitio para todo el test
    T = await _ahora_T(conn)
    queda = VELA_S - (await conn.fetchval("SELECT clock_timestamp()") - T).total_seconds()
    if queda < 60 + B.comun("v2")["tope_retraso_s"] / RAPIDA:
        await asyncio.sleep(queda + 0.5)
        T = await _ahora_T(conn)
    anterior = T - timedelta(seconds=VELA_S)
    esquema = await conn.fetchval("SELECT current_schema()")
    await B.sembrar(conn, anterior, B.insumos(anterior), BTC, "BTC")           # todo llego: cumple
    await B.sembrar(conn, anterior, B.insumos(anterior), ETH, "ETH", minutos_de_flujo=59)  # falta 1 min
    # lo que dejo la pasada muerta: un latido ok de DOS velas atras y las filas de v1 de la vela
    # anterior (v1 registro A TIEMPO -aqui, con un tope en el que cabe una vela ya cerrada- y v2
    # esperaba cuando murio)
    await G.latir(conn, vela_cierre=anterior - timedelta(seconds=VELA_S), estado="ok", duracion_s=0.5,
                  detalle={"velas": []}, error=None)
    await S.evaluar_vela(conn, T=anterior, doc=B.doc_de_prueba(anterior, tope_s=2 * VELA_S + 200),
                         huella_codigo=C.huella_codigo(), esperar=False)
    de_v1 = await _por_episodio(conn)
    assert de_v1 and set(de_v1.values()) == {1}

    def terminales(filas: list[dict], version: str, symbol: str) -> list[str]:
        return [f["estado"] for f in filas if (f["version"], f["symbol"], f["familia"], f["lado"]) ==
                (version, symbol, "F1", "largo") and f["estado"] in ("DISPARADO", "SOMBRA")]

    assert terminales(await _filas(conn), "v1", BTC) == ["DISPARADO"]

    ahora = await conn.fetchval("SELECT clock_timestamp()")
    desfase = (ahora - T).total_seconds() + 0.3
    doc = B.doc_de_prueba(T, *DOS, desfase_s=desfase, escala=RAPIDA)
    reloj = {v: _espera(doc, v) for v in DOS}
    monkeypatch.setattr(R, "cargar_valido", lambda ruta=None: copy.deepcopy(doc))
    original = S._conexion_kw

    def al_esquema(ajustes):
        kw = original(ajustes)
        kw["server_settings"] = {**kw["server_settings"], "search_path": f'"{esquema}", public'}
        return kw

    monkeypatch.setattr(S, "_conexion_kw", al_esquema)
    await S._pasada_async(SimpleNamespace(pg_dsn=_dsn()))

    latido = dict(await conn.fetchrow(
        "SELECT estado, vela_cierre, registered_at, error, detalle::text AS detalle FROM entrada_latido "
        "ORDER BY latido_id DESC LIMIT 1"))
    assert latido["estado"] == "ok" and latido["vela_cierre"] == T, latido
    detalle = json.loads(latido["detalle"])
    assert detalle["recuperacion"] == {"velas": 1, "omitidas": 0}
    recuperadas = [v for v in detalle["velas"] if v["vela_cierre"] == M.iso(anterior) and v["perfil"] == "intradia"]
    # NI ESPERA: la vela recuperada se decide al primer intento, tambien la de ETH, a la que le falta spot
    assert recuperadas and all(v["espera"]["intentos"] == 1 for v in recuperadas), recuperadas
    assert any(not v["espera"]["listos"] for v in recuperadas if v["versiones"] == ["v2"])
    filas = [f for f in await _filas(conn) if f["vela_cierre"] == anterior]
    # NI DISPARA: BTC cumple todo tambien en v2 y queda «tardio»; ETH, sin su minuto, SOMBRA de datos
    assert not [f for f in filas if f["estado"] == "DISPARADO" and f["version"] == "v2"]
    btc_v2 = _gatillo(filas, "v2", BTC)
    assert (btc_v2["estado"], btc_v2["motivo"]) == ("SOMBRA", "tardio")
    eth_v2 = _gatillo(filas, "v2", ETH)
    assert eth_v2["estado"] == "SOMBRA" and eth_v2["foto"]["decision"]["tipo_sombra"] == "datos"
    # NI REPITE: el DISPARADO que v1 registro a tiempo sigue siendo su unica fila terminal, y cada
    # episodio tiene una fila VIGILANDO y una terminal
    assert terminales(filas, "v1", BTC) == ["DISPARADO"]
    despues = await _por_episodio(conn)
    assert set(despues.values()) == {1} and set(de_v1) <= set(despues)
    # la vela EN CURSO (sin datos sembrados) SI espero: la pasada acabo despues del ultimo intento de v2
    assert (latido["registered_at"] - T).total_seconds() >= reloj["v2"]["ultimo_intento"], (latido, reloj)
