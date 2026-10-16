"""K107 · el ayudante: junta lo del sujeto, lo juzga, y da la VERDAD de cada DISPARADO (campana 139, C5).

RECALCULA DESDE LA BASE Y LAS VELAS, con el resolutor del ARBOL que juzga (app/entradas/resolutor.py, pura), lo
que el sujeto GUARDA (entrada_resultado) y lo que SIRVE (/api/entradas), y condena un resultado que no sale de su
plan. Lo que ya no puede recalcular -sus velas se podaron: empiezan antes que la primera vela de 1 min de su
simbolo que queda en la base- lo dice NO MEDIDO para ese, sin absolver ni condenar.

  A  lo guardado        cada fila de entrada_resultado: sus dos huellas, su plan en el registro, y el resolutor
                        sobre su foto y sus velas da EXACTAMENTE lo guardado
  B  lo servido         cada DISPARADO servido trae su resultado, y es el de su plan con sus velas a la hora de la
                        respuesta (si es FINAL, ademas, el guardado); ninguno servido VIVO ha acabado ya
  C  lo final se guarda todo DISPARADO cuyo resultado es FINAL desde hace mas de 15 min esta guardado
  D  las cuentas        los resueltos de cada celda son los guardados de esa celda
  E  el papel           la cuenta de papel servida es la de app/entradas/papel.py sobre esos resultados
  F  el catalogo        entrada_resultado es solo-anadir por catalogo: sus disparadores, activos y con su funcion

Ordenes:
  junta <dir> (--produccion | --dsn DSN [--esquema E] [--reloj T])   lo del sujeto, en <dir>/sujeto.json
  juzga <dir> <arbol>                                               el veredicto; rc 0 VERDE, 1 ROJO, 2 NO MEDIDO
  verdad (--produccion | --dsn DSN [--esquema E] [--reloj T])       {registro_id: como acabo}, para K106 (E10)
  carga <fixture.json> <dsn> <schema.sql> [--esquema E]              la copia congelada en una base desechable
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

B = Path(os.environ.get("K107_HARNESS", "/srv/coinanalyze/harness"))
HOLGURA_GUARDAR = timedelta(minutes=15)


# --------------------------------------------------------------------------- el canal


class CanalCaido(RuntimeError):
    """No se pudo preguntar: distinto de «se pregunto y no hay nada»."""


class Canal:
    """Una consulta -> su JSON. Produccion por bin/prodsql (solo lectura forzada; TODO=1 porque las fotos pasan
    del corte de 8 KB); una base local por psql, con su esquema y su reloj plantado si los tiene."""

    def __init__(self, a: argparse.Namespace):
        self.a = a

    def sql(self, consulta: str):
        if self.a.produccion:
            orden = ["sh", str(B / "bin" / "prodsql"), consulta]
        else:
            previo = f"SET search_path TO {self.a.esquema}, pg_catalog, public; " if self.a.esquema else ""
            if self.a.reloj:  # un DO no imprime nada: la salida es solo la de la consulta
                previo += ("DO $r$ BEGIN PERFORM set_config('reloj.desfase', ("
                           f"'{self.a.reloj}'::timestamptz - pg_catalog.clock_timestamp())::text, false); END $r$; ")
            orden = ["psql", "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-d", self.a.dsn, "-c",
                     previo + "SET TIME ZONE 'UTC'; " + consulta]
        r = subprocess.run(orden, capture_output=True, text=True, timeout=300,
                           env={**os.environ, "TODO": "1"})
        if r.returncode != 0:
            raise CanalCaido(f"rc={r.returncode} {(r.stderr or r.stdout).strip()[:200]}")
        texto = r.stdout.strip()  # json_agg pone cada elemento en su linea: el valor es la salida entera
        if not texto:
            raise ValueError("el canal contesto sin ninguna fila a una consulta que siempre devuelve una")
        return json.loads(texto)

    def agg(self, consulta: str):
        return self.sql(f"SELECT coalesce(json_agg(x), '[]') FROM ({consulta}) x")


def junta(a: argparse.Namespace) -> dict:
    """Lo del sujeto que hace falta para recalcular: sus DISPARADOS y los planes que guarda, con sus velas, sus
    cobros de funding, sus huecos y el suelo de su poda; lo guardado; y el catalogo de entrada_resultado."""
    c = Canal(a)
    RES = _app(str(Path(__file__).resolve().parents[2]))[0]
    sujeto = c.sql("SELECT json_build_object('ahora', clock_timestamp(), 'resultado', "
                   "to_regclass('entrada_resultado') IS NOT NULL, 'registro', to_regclass('entrada_registro') IS NOT NULL)")
    if not sujeto["registro"]:
        return {**sujeto, "disparados": [], "sombras": [], "guardados": [], "catalogo": []}
    columnas = ("registro_id, version, familia, perfil, lado, symbol, clave, inicio_episodio, estado, vela_cierre, "
                "registered_at, caduca_en, foto")
    disparados = c.agg(f"SELECT {columnas} FROM entrada_registro WHERE estado = 'DISPARADO'")
    guardados, catalogo = [], []
    if sujeto["resultado"]:
        guardados = c.agg("SELECT registro_id, resolutor, huella_convenciones, huella_resultado, hipotetico, salida, "
                          "resultado::text AS resultado, convenciones::text AS convenciones FROM entrada_resultado")
        catalogo = c.agg("SELECT t.tgname, t.tgenabled::text AS tgenabled, p.proname FROM pg_trigger t JOIN pg_proc p "
                         "ON p.oid = t.tgfoid WHERE t.tgrelid = 'entrada_resultado'::regclass AND NOT t.tgisinternal")
    otros = sorted({g["registro_id"] for g in guardados} - {f["registro_id"] for f in disparados})
    sombras = c.agg(f"SELECT {columnas} FROM entrada_registro WHERE registro_id IN ({','.join(map(str, otros))})"
                    ) if otros else []
    vidas: dict[str, list] = {}
    cobros: dict[str, set] = {}
    for f in disparados + sombras:
        desde, hasta = RES.ventana(f)
        vidas.setdefault(f["symbol"], []).append((desde, hasta))
        if f["estado"] == "DISPARADO":
            cobros.setdefault(f["symbol"], set()).update(RES.cobros_funding(RES.entrada_t(f), hasta))
    velas, suelo, funding, huecos = {}, {}, {}, {}
    for s, tramos in vidas.items():
        donde = " OR ".join(f"(ts >= '{x.isoformat()}' AND ts <= '{y.isoformat()}')" for x, y in tramos)
        velas[s] = c.agg(f"SELECT ts, open, high, low, close FROM ohlcv WHERE symbol = '{s}' AND interval = '1min' "
                         f"AND ({donde}) ORDER BY ts")
        suelo[s] = c.sql(f"SELECT json_build_object('m', min(ts)) FROM ohlcv WHERE symbol = '{s}' "
                         "AND interval = '1min'")["m"]
        lista = ",".join(f"'{(x - timedelta(minutes=5)).isoformat()}'" for x in sorted(cobros.get(s, ())))
        funding[s] = c.agg(f"SELECT ts, fr_high, fr_low FROM funding_rate WHERE symbol = '{s}' AND interval = '5min' "
                           f"AND ts IN ({lista})") if lista else []
        huecos[s] = c.agg(f"SELECT start_ts, end_ts FROM data_gap WHERE feed = 'ohlcv_1min' AND exchange = 'binance' "
                          f"AND market = 'perpetual' AND symbol = '{s}' AND status IN ('unresolved', 'unrecoverable')")
    return {**sujeto, "disparados": disparados, "sombras": sombras, "guardados": guardados, "catalogo": catalogo,
            "velas": velas, "suelo": suelo, "funding": funding, "huecos": huecos}


# --------------------------------------------------------------------------- el juicio

LLEGADA = timedelta(minutes=3)  # lo que una vela de 1 min puede tardar en llegar a ohlcv tras su cierre


def _app(arbol: str):
    if arbol not in sys.path:
        sys.path[:0] = [arbol]
    from app.entradas import papel as PAPEL
    from app.entradas import reglamento as R
    from app.entradas import resolutor as RES
    return RES, PAPEL, R


def recalcula(RES, d: dict, fila: dict, ahora) -> dict | None:
    """El resultado de `fila` desde las velas del sujeto a la hora `ahora`, o None si sus velas ya se podaron."""
    desde, _ = RES.ventana(fila)
    suelo = d["suelo"].get(fila["symbol"])
    if suelo is None or desde < RES._t(suelo):
        return None
    funding = None
    if fila["estado"] == "DISPARADO":
        funding = {RES._t(x["ts"]) + timedelta(minutes=5): x for x in d["funding"].get(fila["symbol"], [])}
    huecos = [(h["start_ts"], h["end_ts"]) for h in d["huecos"].get(fila["symbol"], [])]
    return RES.resolver(fila, d["velas"].get(fila["symbol"], []), ahora, funding, huecos)


def _dice(r: dict | None) -> str:
    if not r:
        return "nada"
    return f"{r.get('salida') or r.get('estado')}" + (f" a las {r['instante'][11:16]}Z" if r.get("instante") else "")


def juzga(directorio: Path, arbol: str) -> int:
    d = json.loads((directorio / "sujeto.json").read_text())
    servido_f = directorio / "servido.json"
    servido = json.loads(servido_f.read_text()) if servido_f.exists() else None
    RES, PAPEL, R = _app(arbol)
    if not d["registro"]:
        print("NO MEDIDO: el sujeto no tiene el registro de entradas (entrada_registro)")
        return 2
    if not d["resultado"]:
        sin = [f["registro_id"] for f in d["disparados"]]
        print(f"ROJO  K107 FALTA DESPLEGAR: el sujeto no tiene entrada_resultado (la E3) y el arbol si "
              f"(sql/schema.sql); {len(sin)} DISPARADO(S) sin resultado guardado: {', '.join(map(str, sin)) or '-'}")
        return 1
    if servido is None or "as_of" not in servido:
        print("NO MEDIDO: no llego lo que el sujeto sirve (/api/entradas)")
        return 2
    ahora, as_of = RES._t(d["ahora"]), RES._t(servido["as_of"])
    planes = {f["registro_id"]: f for f in d["disparados"] + d["sombras"]}
    guardados = {g["registro_id"]: g for g in d["guardados"] if g["resolutor"] == RES.RESOLUTOR_VERSION}
    hallazgos: list[str] = []
    no_medidos: list[str] = []
    medidos = 0

    # A · lo guardado sale de su plan
    for g in d["guardados"]:
        rid = g["registro_id"]
        if g["resolutor"] != RES.RESOLUTOR_VERSION:
            no_medidos.append(f"{rid}: guardado por {g['resolutor']}, y este arbol trae {RES.RESOLUTOR_VERSION}")
            continue
        if hashlib.sha256(g["resultado"].encode()).hexdigest() != g["huella_resultado"]:
            hallazgos.append(f"A {rid}: huella_resultado no es el sha256 de lo guardado")
        if hashlib.sha256(g["convenciones"].encode()).hexdigest() != g["huella_convenciones"] \
                or g["huella_convenciones"] != RES.HUELLA_CONVENCIONES:
            hallazgos.append(f"A {rid}: las convenciones guardadas no son las de {RES.RESOLUTOR_VERSION}")
        fila = planes.get(rid)
        if fila is None or (fila["estado"] == "SOMBRA") != g["hipotetico"]:
            hallazgos.append(f"A {rid}: guardado sin su plan en el registro, o hipotetico donde no lo es")
            continue
        r = recalcula(RES, d, fila, ahora)
        if r is None:
            no_medidos.append(f"{rid}: sus velas ya se podaron (la primera de 1 min de {fila['symbol']} es de "
                              f"{d['suelo'].get(fila['symbol'])})")
            continue
        medidos += 1
        if r != json.loads(g["resultado"]):
            hallazgos.append(f"A {rid}: lo guardado dice {_dice(json.loads(g['resultado']))} y su plan, con sus "
                             f"velas, da {_dice(r)}")

    # B · lo servido sale de su plan, y nada servido VIVO ha acabado
    servidos = []
    for lado in (servido.get("por_lado") or {}).values():
        servidos += [(p, True) for p in lado["vivos"]["disparados"]] + [(p, False) for p in lado["ventana"]["disparados"]]
    for p, en_vivos in servidos:
        rid, res = p["registro_id"], p.get("resultado")
        fila = planes.get(rid)
        r = recalcula(RES, d, fila, as_of) if fila else None
        if r is None:
            no_medidos.append(f"{rid}: servido y sin velas con que recalcularlo")
            continue
        medidos += 1
        # LO VIVO QUE YA ACABO. Lo condena solo si la vela que lo acaba cerro con tiempo de haber llegado antes de
        # la respuesta (LLEGADA): una mas reciente pudo llegar despues, y entonces no se sabe.
        if (en_vivos or (res or {}).get("estado") == RES.ABIERTO) and r["estado"] != RES.ABIERTO:
            decide = RES._t(r["instante"]) if r.get("instante") else None
            if decide is not None and decide + RES.MINUTO + LLEGADA > as_of:
                no_medidos.append(f"{rid}: servido vivo y acabo en la vela de las {r['instante'][11:16]}Z, que pudo "
                                  "llegar despues de la respuesta")
            else:
                hallazgos.append(f"B {rid}: servido VIVO y su plan ya acabo: {_dice(r)}")
        if res is None:
            hallazgos.append(f"B {rid}: servido sin su resultado (su plan da {_dice(r)})")
            continue
        if res.get("estado") == RES.ABIERTO or en_vivos:
            continue
        if res.get("firmeza") == RES.FINAL:
            if res != r:
                hallazgos.append(f"B {rid}: servido FINAL {_dice(res)} y su plan, con sus velas, da {_dice(r)}")
            if rid in guardados and json.loads(guardados[rid]["resultado"]) != res:
                hallazgos.append(f"B {rid}: servido FINAL y distinto de lo guardado")
        elif res.get("estado") == RES.ACABADO and any(res.get(k) != r.get(k) for k in ("salida", "instante", "precio")):
            hallazgos.append(f"B {rid}: servido {_dice(res)} (provisional) y su plan, con sus velas, da {_dice(r)}")

    # C · lo final se guarda
    resultados = {}
    for rid, fila in planes.items():
        if fila["estado"] != "DISPARADO":
            continue
        r = json.loads(guardados[rid]["resultado"]) if rid in guardados else recalcula(RES, d, fila, ahora)
        resultados[rid] = r
        if rid not in guardados and r and r["firmeza"] == RES.FINAL \
                and RES._t(r["asentado_en"]) + HOLGURA_GUARDAR <= ahora:
            hallazgos.append(f"C {rid}: FINAL desde las {r['asentado_en']} ({_dice(r)}) y sin guardar")

    # D · las cuentas: los resueltos de cada celda son sus guardados
    celda = {}
    for g in guardados.values():
        f = planes.get(g["registro_id"])
        if f and not g["hipotetico"]:
            clave = (f["familia"], f["perfil"], f["lado"], f["version"])
            celda[clave] = celda.get(clave, 0) + 1
    for c in servido.get("cuentas") or []:
        clave = (c["familia"], c["perfil"], c["lado"], c["version"])
        if c.get("resueltos") != celda.get(clave, 0):
            hallazgos.append(f"D {'/'.join(clave)}: sirve {c.get('resueltos')} resueltos y hay {celda.get(clave, 0)} "
                             "guardados")

    # E · el papel: la cuenta de cada version en curso sobre esos resultados
    doc = R.cargar_valido()
    for v in R.versiones_en_curso(doc):
        esperado = PAPEL.cuenta(v, [f for f in planes.values() if f["estado"] == "DISPARADO"
                                    and f["version"] == v["version"]], resultados)
        dado = (servido.get("papel") or {}).get(v["version"])
        if dado != esperado:
            hallazgos.append(f"E {v['version']}: la cuenta de papel servida (saldo {(dado or {}).get('saldo_usd')}, n "
                             f"{(dado or {}).get('n')}) no es la de sus resultados (saldo {esperado['saldo_usd']}, n "
                             f"{esperado['n']})")

    # F · el catalogo: solo-anadir por sus disparadores, activos y con su funcion
    activos = {(t["tgname"], t["proname"]) for t in d["catalogo"] if t["tgenabled"] in ("O", "A")}
    for falta in (("entrada_resultado_al_insertar", "entrada_resultado_al_insertar"),
                  ("entrada_resultado_no_update_delete", "rechaza_mutacion_entradas"),
                  ("entrada_resultado_no_truncate", "rechaza_mutacion_entradas")):
        if falta not in activos:
            hallazgos.append(f"F entrada_resultado sin su disparador {falta[0]} activo con {falta[1]}()")

    pie = (f"{len(d['disparados'])} DISPARADO(S), {len(d['guardados'])} guardado(s), {len(servidos)} servido(s): "
           f"{medidos} recalculado(s) desde sus velas con {RES.RESOLUTOR_VERSION}"
           + (f" · {len(no_medidos)} NO MEDIDO(S)" if no_medidos else ""))
    hallazgos = list(dict.fromkeys(hallazgos))
    no_medidos = list(dict.fromkeys(no_medidos))
    if hallazgos:
        print(f"ROJO  K107 {hallazgos[0][:150]}")
        print(f"   {pie}")
        for h in hallazgos:
            print(f"   - {h}")
        rc = 1
    elif medidos == 0:
        print(f"NO MEDIDO: ningun resultado se pudo recalcular desde sus velas (catalogo, cuentas y papel cuadran) · {pie}")
        rc = 2
    else:
        print(f"VERDE  K107 · lo guardado y lo servido salen de su plan; cuentas, papel y catalogo cuadran · {pie}")
        rc = 0
    for x in no_medidos:
        print(f"   NO MEDIDO {x}")
    return rc


# --------------------------------------------------------------------------- la verdad para K106, y la copia


def verdad(a: argparse.Namespace) -> dict:
    """Como acabo cada DISPARADO segun la base y sus velas, AHORA: lo que K106 contrasta con lo que se pinta VIVO."""
    d = junta(a)
    RES, _, _ = _app(str(Path(__file__).resolve().parents[2]))
    salida = {}
    for f in d["disparados"]:
        r = recalcula(RES, d, f, RES._t(d["ahora"]))
        if r is not None:
            salida[str(f["registro_id"])] = {"acabado": r["estado"] != RES.ABIERTO, "salida": r["salida"],
                                             "instante": r["instante"], "estado": r["estado"]}
    return {"ahora": d["ahora"], "disparados": salida}


def sirve(arbol: str, dsn: str, esquema: str, reloj: str, salida: str) -> None:
    """Lo que /api/entradas (ruta.construir, todo por defecto) sirve con el ARBOL dado sobre `dsn` con el reloj
    plantado en `reloj`. Se corre con `python -S`: el .venv instala app/ en modo editable y su buscador manda
    `import app` al repo diga lo que diga sys.path; asi se juzga lo que sirve OTRO arbol (main) de verdad."""
    import asyncio

    sys.path[:0] = [arbol]
    vlib = Path(sys.executable).parents[1] / "lib"
    sys.path += [str(d) for d in sorted(vlib.glob("python3*/site-packages"))]  # sin sus .pth: sin el editable
    import app
    if not app.__file__.startswith(arbol.rstrip("/") + "/"):
        raise SystemExit(f"sirve: app viene de {app.__file__}, no de {arbol}: corre con python -S")
    import asyncpg

    from app.entradas import ruta as RUTA

    async def una() -> None:
        c = await asyncpg.connect(dsn)
        await c.execute(f"SET search_path TO {esquema}, pg_catalog, public")
        await c.execute("SET TIME ZONE 'UTC'")
        desfase = await c.fetchval("SELECT ($1::timestamptz - pg_catalog.clock_timestamp())::text",
                                   datetime_de(reloj))
        await c.execute("SELECT set_config('reloj.desfase', $1, false)", desfase)
        r = await RUTA.construir(c, lado="ambos", desde=None, hasta=None, version=None, symbol=None, limite=200,
                                 foto=False)
        Path(salida).write_text(json.dumps(r, ensure_ascii=False, default=str))
        await c.close()

    asyncio.run(una())


def datetime_de(texto: str):
    from datetime import datetime
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


def carga(fixture: str, dsn: str, schema_sql: str, esquema: str) -> None:
    """La copia congelada (K107-copia.json) en `esquema` de la base `dsn`, con el reloj plantable."""
    doc = json.loads(Path(fixture).read_text())
    lineas = [f"CREATE SCHEMA {esquema};",
              f"CREATE FUNCTION {esquema}.clock_timestamp() RETURNS timestamptz LANGUAGE sql VOLATILE AS "
              "$$ SELECT pg_catalog.clock_timestamp() + coalesce(current_setting('reloj.desfase', true), '0')::interval $$;",
              f"SET search_path TO {esquema}, pg_catalog, public;", "SET TIME ZONE 'UTC';",
              Path(schema_sql).read_text(),
              "INSERT INTO market_assets(base_asset) VALUES ('BTC'), ('ETH'), ('SOL') ON CONFLICT DO NOTHING;",
              "INSERT INTO symbols(symbol, base_asset) VALUES ('BTCUSDT_PERP.A', 'BTC'), ('ETHUSDT_PERP.A', 'ETH'), "
              "('SOLUSDT_PERP.A', 'SOL') ON CONFLICT DO NOTHING;",
              "ALTER TABLE entrada_registro DISABLE TRIGGER USER; ALTER TABLE entrada_reglamento DISABLE TRIGGER USER;"
              " ALTER TABLE entrada_latido DISABLE TRIGGER USER;"]

    def q(v):
        return "NULL" if v is None else "'" + str(v).replace("'", "''") + "'"
    for r in doc["reglamento"]:
        lineas.append("INSERT INTO entrada_reglamento (etiqueta, bloque, huella, contenido, registered_at) VALUES "
                      f"({q(r['etiqueta'])}, {q(r['bloque'])}, {q(r['huella'])}, {q(r['contenido'])}::json, "
                      f"{q(r['registered_at'])});")
    for f in doc["registro"]:
        cols = [k for k in f if k != "foto"]
        lineas.append(f"INSERT INTO entrada_registro ({', '.join(cols)}, foto) OVERRIDING SYSTEM VALUE VALUES "
                      f"({', '.join(q(f[k]) for k in cols)}, {q(f['foto'])}::json);")
    for x in sorted(doc["latidos"], key=lambda x: x["registered_at"]):  # en su orden: el ultimo id es el ultimo
        lineas.append("INSERT INTO entrada_latido (vela_cierre, estado, duracion_s, codigo_version, detalle, error, "
                      f"registered_at) VALUES ({q(x['vela_cierre'])}, {q(x['estado'])}, {q(x['duracion_s'])}, "
                      f"{q(x['codigo_version'])}, {q(x['detalle'])}::json, {q(x['error'])}, {q(x['registered_at'])});")
    lineas.append("ALTER TABLE entrada_registro ENABLE TRIGGER USER; ALTER TABLE entrada_reglamento ENABLE TRIGGER USER;"
                  " ALTER TABLE entrada_latido ENABLE TRIGGER USER;")
    lineas.append("SELECT setval(pg_get_serial_sequence('entrada_registro', 'registro_id'), "
                  "(SELECT max(registro_id) FROM entrada_registro));")
    for ts, o, h, lo, c in doc["velas"]:
        lineas.append("INSERT INTO ohlcv (ts, symbol, interval, open, high, low, close, volume, buy_volume, tx, btx) "
                      f"VALUES ({q(ts)}, 'SOLUSDT_PERP.A', '1min', {o}, {h}, {lo}, {c}, 1, 0, 1, 0);")
    for ts, o, h, lo, c in doc["funding"]:
        lineas.append("INSERT INTO funding_rate (ts, symbol, interval, fr_open, fr_high, fr_low, fr_close) "
                      f"VALUES ({q(ts)}, 'SOLUSDT_PERP.A', '5min', {o}, {h}, {lo}, {c});")
    r = subprocess.run(["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-d", dsn], input="\n".join(lineas),
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise SystemExit(f"carga: psql rc={r.returncode}: {r.stderr.strip()[-300:]}")
    print(f"carga: {len(doc['registro'])} planes, {len(doc['velas'])} velas en {esquema} · copia de {doc['T']}")


def main() -> int:
    ap = argparse.ArgumentParser(description="K107 · el ayudante")
    sub = ap.add_subparsers(dest="orden", required=True)
    for nombre in ("junta", "verdad"):
        p = sub.add_parser(nombre)
        if nombre == "junta":
            p.add_argument("dir")
        p.add_argument("--produccion", action="store_true")
        p.add_argument("--dsn")
        p.add_argument("--esquema")
        p.add_argument("--reloj")
    p = sub.add_parser("juzga")
    p.add_argument("dir")
    p.add_argument("arbol")
    p = sub.add_parser("sirve")
    for x in ("arbol", "dsn", "esquema", "reloj", "salida"):
        p.add_argument(x)
    p = sub.add_parser("carga")
    p.add_argument("fixture")
    p.add_argument("dsn")
    p.add_argument("schema_sql")
    p.add_argument("--esquema", default="copia")
    a = ap.parse_args()
    if a.orden == "juzga":
        return juzga(Path(a.dir), a.arbol)
    if a.orden == "carga":
        carga(a.fixture, a.dsn, a.schema_sql, a.esquema)
        return 0
    if a.orden == "sirve":
        sirve(a.arbol, a.dsn, a.esquema, a.reloj, a.salida)
        return 0
    if not a.produccion and not a.dsn:
        ap.error("hace falta --produccion o --dsn")
    try:
        if a.orden == "junta":
            Path(a.dir, "sujeto.json").write_text(json.dumps(junta(a), default=str))
        else:
            print(json.dumps(verdad(a), default=str))
    except CanalCaido as exc:
        print(f"NO MEDIDO (CANAL): {str(exc)[:200]}")
        return 2
    except Exception as exc:  # noqa: BLE001 - lo que no se pudo leer es NO MEDIDO, nunca ROJO
        print(f"NO MEDIDO: {type(exc).__name__}: {str(exc)[:200]}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
