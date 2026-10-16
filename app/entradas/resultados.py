"""LOS RESULTADOS, GUARDADOS Y SERVIDOS (campana 139, C2).

resolutor.py decide como acabo un plan; este modulo le da lo que necesita de la base (las velas de 1 min de su
simbolo en su vida, los cobros de funding y los huecos de data_gap sin resolver) y GUARDA lo FINAL en
entrada_resultado, solo-anadir: el resultado de un DISPARADO tiene que poder leerse y auditarse cuando sus
velas ya se hayan podado. Lo provisional no se guarda: se recalcula en cada peticion con las velas que haya,
asi que un DISPARADO que ya acabo no se sirve VIVO en ninguna respuesta posterior a la llegada de la vela que
lo acaba.

QUIEN GUARDA. Quien sirve (ruta.py, vista.py) guarda lo FINAL que calcula, y la API lo hace ademas en
segundo plano (app/api.py, cada RESULTADOS_CADA_S) para que se guarde aunque nadie mire. Dos escritores no
se pisan: la clave es (registro_id, resolutor) y se inserta con ON CONFLICT DO NOTHING; y la base rechaza
una fila no asentada (EN003).

EL BARRIDO EMPAREJADO (hipotesis de v2, descriptivo fijado ANTES de su registro): para cada DISPARADO de v2
que toca su stop, la SOMBRA de v1 del MISMO episodio -misma clave, mismo inicio de episodio y misma vela,
P136-10- y si su plan (mismo T1, stop con cascada) habria cruzado T1. Se sirve plan a plan: no es una
prueba, y con n < 30 no lleva ningun «n de m».
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from app.data_gaps import BLOCKING_GAP_STATUSES
from app.entradas import reglamento as R
from app.entradas import resolutor as RES

RESULTADOS_CADA_S = 300
CONVENCIONES_DOC = {"version": RES.RESOLUTOR_VERSION, "convenciones": RES.CONVENCIONES}
BARRIDO = {"version": "v2", "contra": "v1", "salidas": (RES.STOP, RES.MISMA_VELA)}
_CINCO = timedelta(minutes=5)

_VELAS = """
SELECT ts, open, high, low, close FROM ohlcv
WHERE symbol = $1 AND interval = '1min' AND ts >= $2 AND ts <= $3
ORDER BY ts
"""
_FUNDING = """
SELECT ts, fr_high, fr_low FROM funding_rate
WHERE symbol = $1 AND interval = '5min' AND ts = ANY($2::timestamptz[])
"""
_HUECOS = """
SELECT start_ts, end_ts FROM data_gap
WHERE feed = 'ohlcv_1min' AND exchange = 'binance' AND market = 'perpetual' AND symbol = $1
  AND status = ANY($4::text[]) AND start_ts < $3 AND end_ts > $2
"""
_GUARDADOS = """
SELECT registro_id, resultado::text AS resultado FROM entrada_resultado
WHERE registro_id = ANY($1::bigint[]) AND resolutor = $2
"""
_GUARDA = """
INSERT INTO entrada_resultado (registro_id, resolutor, huella_convenciones, hipotetico, salida, instante,
                               asentado_en, huella_resultado, resultado, convenciones)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::json, $10::json)
ON CONFLICT (registro_id, resolutor) DO NOTHING
"""
_SIN_GUARDAR = """
SELECT *, foto::text AS foto FROM entrada_registro r
WHERE estado = 'DISPARADO' AND NOT EXISTS (
    SELECT 1 FROM entrada_resultado x WHERE x.registro_id = r.registro_id AND x.resolutor = $1)
ORDER BY registro_id LIMIT $2
"""
_PAREJA = """
SELECT *, foto::text AS foto FROM entrada_registro
WHERE version = $1 AND estado = 'SOMBRA' AND symbol = $2 AND familia = $3 AND perfil = $4 AND lado = $5
  AND clave = $6 AND inicio_episodio = $7 AND vela_cierre = $8
ORDER BY registro_id LIMIT 1
"""
CUENTAS_SQL = """
SELECT g.familia, g.perfil, g.lado, g.version, count(*)::int AS resueltos,
       count(*) FILTER (WHERE x.salida = 'sin_entrada')::int AS sin_entrada,
       count(*) FILTER (WHERE x.salida = 'no_evaluable')::int AS no_evaluables
FROM entrada_resultado x JOIN entrada_registro g USING (registro_id)
WHERE NOT x.hipotetico AND g.estado = 'DISPARADO' AND x.resolutor = $1
GROUP BY 1, 2, 3, 4
"""


async def resolver_fila(conn, fila: dict[str, Any], ahora: datetime) -> dict[str, Any]:
    """El resultado de una fila con lo que la base tiene AHORA. Un DISPARADO lleva sus cobros de funding; el
    hipotetico de una SOMBRA, ninguno."""
    desde, hasta = RES.ventana(fila)
    velas = [dict(v) for v in await conn.fetch(_VELAS, fila["symbol"], desde, hasta)]
    funding = None
    if fila["estado"] == "DISPARADO":
        cobros = RES.cobros_funding(RES.entrada_t(fila), hasta)
        filas = await conn.fetch(_FUNDING, fila["symbol"], [c - _CINCO for c in cobros]) if cobros else []
        funding = {f["ts"] + _CINCO: {"fr_high": f["fr_high"], "fr_low": f["fr_low"]} for f in filas}
    huecos = [(h["start_ts"], h["end_ts"]) for h in await conn.fetch(
        _HUECOS, fila["symbol"], desde, hasta + RES.MINUTO, sorted(BLOCKING_GAP_STATUSES))]
    return RES.resolver(fila, velas, ahora, funding, huecos)


async def guardar(conn, resultado: dict[str, Any]) -> bool:
    """Guarda un resultado FINAL. False si ya habia uno de esta version (gana el primero)."""
    if resultado["firmeza"] != RES.FINAL or resultado["salida"] is None:
        raise ValueError("solo se guarda un resultado FINAL")
    texto = R.canonico(resultado)
    hecho = await conn.execute(
        _GUARDA, resultado["registro_id"], resultado["resolutor"], resultado["huella_convenciones"],
        resultado["hipotetico"], resultado["salida"],
        RES._t(resultado["instante"]) if resultado["instante"] else None, RES._t(resultado["asentado_en"]),
        R.huella(resultado), texto, R.canonico(CONVENCIONES_DOC))
    return hecho.endswith(" 1")


async def de_filas(conn, filas: list[dict[str, Any]], ahora: datetime, guarda: bool = True) -> dict[int, dict]:
    """El resultado de cada fila: el GUARDADO de esta version si lo hay; si no, se resuelve ahora y, si sale
    FINAL, se guarda. Lo provisional se devuelve sin guardar."""
    ya = {f["registro_id"]: json.loads(f["resultado"]) for f in await conn.fetch(
        _GUARDADOS, [f["registro_id"] for f in filas], RES.RESOLUTOR_VERSION)}
    salida: dict[int, dict] = {}
    for f in filas:
        r = ya.get(f["registro_id"])
        if r is None:
            if "foto" not in f:  # una fila sin su foto (ruta._DISPARADOS): solo se lee la de lo que se resuelve
                f = {**f, "foto": await conn.fetchval(
                    "SELECT foto::text FROM entrada_registro WHERE registro_id = $1", f["registro_id"])}
            r = await resolver_fila(conn, f, ahora)
            if guarda and r["firmeza"] == RES.FINAL and r["salida"] is not None:
                await guardar(conn, r)
        salida[f["registro_id"]] = r
    return salida


async def barrido(conn, disparados: list[dict[str, Any]], resultados: dict[int, dict],
                  ahora: datetime, guarda: bool = True) -> list[dict[str, Any]]:
    """El barrido emparejado de los DISPARADOS de BARRIDO['version'] que tocaron su stop, plan a plan."""
    lista = []
    for f in sorted(disparados, key=lambda x: x["registro_id"]):
        r = resultados.get(f["registro_id"]) or {}
        if f["version"] != BARRIDO["version"] or r.get("salida") not in BARRIDO["salidas"]:
            continue
        par = await conn.fetchrow(_PAREJA, BARRIDO["contra"], f["symbol"], f["familia"], f["perfil"], f["lado"],
                                  f["clave"], f["inicio_episodio"], f["vela_cierre"])
        item = {"registro_id": f["registro_id"], "symbol": f["symbol"], "vela_cierre": RES.iso(f["vela_cierre"]),
                "salida": r["salida"], "pareja": None,
                "motivo": f"{BARRIDO['contra']} no tiene una SOMBRA del mismo episodio en esa vela (sus episodios "
                "pueden ir desfasados, P136-10)"}
        if par is not None:
            h = (await de_filas(conn, [dict(par)], ahora, guarda))[par["registro_id"]]
            item["pareja"] = {"registro_id": par["registro_id"], "salida_hipotetica": h["salida"],
                              "instante": h["instante"], "firmeza": h["firmeza"],
                              "t1_antes_que_el_stop": None if h["salida"] is None else h["salida"] == RES.OBJETIVO}
            item["motivo"] = None
        lista.append(item)
    return lista


_PAREJA_SIN_GUARDAR = """
SELECT d.*, d.foto::text AS foto FROM entrada_registro d
JOIN entrada_resultado x ON x.registro_id = d.registro_id AND x.resolutor = $1
WHERE d.version = $2 AND d.estado = 'DISPARADO' AND x.salida = ANY($3::text[]) AND EXISTS (
    SELECT 1 FROM entrada_registro p
    WHERE p.version = $4 AND p.estado = 'SOMBRA' AND p.symbol = d.symbol AND p.familia = d.familia
      AND p.perfil = d.perfil AND p.lado = d.lado AND p.clave = d.clave AND p.inicio_episodio = d.inicio_episodio
      AND p.vela_cierre = d.vela_cierre AND NOT EXISTS (
          SELECT 1 FROM entrada_resultado y WHERE y.registro_id = p.registro_id AND y.resolutor = $1))
ORDER BY d.registro_id LIMIT $5
"""


async def asentar_pendientes(conn, limite: int = 200) -> dict[str, int]:
    """Lo que la API hace en segundo plano: resolver los DISPARADOS sin resultado FINAL guardado de esta version
    y guardar lo que ya es final; y lo mismo con la SOMBRA del barrido emparejado de los que ya lo tienen."""
    ahora = await conn.fetchval("SELECT clock_timestamp()")
    filas = [dict(f) for f in await conn.fetch(_SIN_GUARDAR, RES.RESOLUTOR_VERSION, limite)]
    filas += [dict(f) for f in await conn.fetch(
        _PAREJA_SIN_GUARDAR, RES.RESOLUTOR_VERSION, BARRIDO["version"], list(BARRIDO["salidas"]),
        BARRIDO["contra"], limite)]
    resultados = await de_filas(conn, filas, ahora)
    await barrido(conn, filas, resultados, ahora)
    return {"mirados": len(filas), "finales": sum(r["firmeza"] == RES.FINAL for r in resultados.values())}
