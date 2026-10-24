"""La HERRAMIENTA DE MEDIDA del modelo y su esfuerzo por ruta (remate 1 de BOT-2, punto 7). Corre EN 140, como el
usuario del bot y con su EnvironmentFile (la clave no sale de 140); la lanza el operador tras desplegar:

  python -m app.bot.mide graba <carpeta>    casos GRABADOS de cada ruta desde la API local (sobre y DECIDE de BTC, ETH,
                                            SOL; una posicion con la forma de Alejandro; una alerta; tres preguntas), con
                                            el mismo mensaje que construye el bot (servicio.mensaje)
  python -m app.bot.mide corre <carpeta>    cada caso por cada nivel de esfuerzo de su ruta (NIVELES), MIDE_VECES veces
                                            (1), con su propio tope (MIDE_TOPE_USD, 12): por ruta y nivel, latencia p50 y
                                            p90, tokens de entrada (y cuantos de cache) y de salida, coste, y la CALIDAD
                                            contra los datos: cifras bien citadas, que estan en los datos pero con otra
                                            fuente o sin ella, e INVENTADAS. Deja resultados.json y tabla.txt.

La tabla puede mover UN nivel si lo justifica; se le ensena a Alejandro, que tiene la ultima palabra; el valor se cambia
por configuracion (BOT_EFFORT_ESCALA, _PREGUNTA, _EVALUA), no por codigo. Las llamadas de esta herramienta NO van a
bot_llamada (no comen del tope diario del bot): su gasto queda en resultados.json.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import re
import statistics
import sys
from datetime import UTC, datetime

import httpx

from app.bot import bybit as bb
from app.bot import llm
from app.bot import servicio as sv

NIVELES = {"escala": ("low", "medium"), "pregunta": ("low", "medium", "high"), "evalua": ("medium", "high", "xhigh")}
PREGUNTAS = ("como esta BTC", "quien compra en BTC", "hay muros cerca en BTC")
NUMERO = re.compile(r"(?<![\w.\[])[-+]?\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?(?![\w\]])|(?<![\w.\[])[-+]?\d+(?:[.,]\d+)?(?![\w\]])")
FUENTE = re.compile(r"\[([A-Za-z_][\w.\-]*)\]")


def numero(t: str) -> float:
    """«110.000», «110,000», «-0,6», «1.234,5» -> float (el ultimo separador con 1-2 o >3 decimales es el decimal)."""
    t = t.replace("+", "")
    if "," in t and "." in t:
        dec = "," if t.rfind(",") > t.rfind(".") else "."
        return float(t.replace("." if dec == "," else ",", "").replace(",", "."))
    for sep in (",", "."):
        if sep in t:
            partes = t.split(sep)
            if len(partes) > 2 or (len(partes[-1]) == 3 and len(partes[0].lstrip("-")) <= 3):
                return float(t.replace(sep, ""))  # separador de miles
            return float(t.replace(",", "."))
    return float(t)


def valores(x) -> list[float]:
    if isinstance(x, bool):
        return []
    if isinstance(x, (int, float)):
        return [float(x)]
    if isinstance(x, str):
        try:
            return [float(x)]
        except ValueError:
            return []
    if isinstance(x, dict):
        return [v for y in x.values() for v in valores(y)]
    if isinstance(x, list):
        return [v for y in x for v in valores(y)]
    return []


def resuelve(datos: dict, ruta: str):
    """[decide.bias.value] o [sobre.cvd_matrix.rows.0.value] -> el subarbol (None si no existe). Sin prefijo, se busca
    en cada bloque de datos (sobre, decide, posicion)."""
    for raiz in ([datos] if ruta.split(".")[0] in datos else []) + [v for v in datos.values() if isinstance(v, dict)]:
        x = raiz
        for k in ruta.split("."):
            if isinstance(x, dict) and k in x:
                x = x[k]
            elif isinstance(x, list) and k.isdigit() and int(k) < len(x):
                x = x[int(k)]
            else:
                x = None
                break
        if x is not None:
            return x
    return None


def casa(v: float, candidatos: list[float]) -> bool:
    for c in candidatos:
        for y in (c, c * 100, c / 100):
            if abs(v - y) <= max(0.005 * abs(y), 0.011):
                return True
    return False


def califica(texto: str, datos: dict) -> dict:
    """Cada cifra de la respuesta (sin enteros de 0 a 12, que son listas, horas o ventanas): BIEN si casa con la fuente
    citada en su linea; EN_DATOS si casa con algun valor de los datos pero no con esa fuente (o no la cita); INVENTADA
    si no casa con nada. Una aproximacion explicable, no un juez: los casos raros se leen en resultados.json."""
    todos = valores(datos)
    out = {"bien": 0, "en_datos": 0, "inventadas": 0, "lista": []}
    for ln in (texto or "").splitlines():
        fuentes = FUENTE.findall(ln)
        limpia = FUENTE.sub(" ", ln)
        for t in NUMERO.findall(limpia):
            try:
                v = numero(t)
            except ValueError:
                continue
            if v == int(v) and 0 <= v <= 12:
                continue
            citados = [w for f in fuentes for w in valores(resuelve(datos, f))]
            clase = "bien" if citados and casa(v, citados) else "en_datos" if casa(v, todos) else "inventadas"
            out[clase] += 1
            if clase == "inventadas":
                out["lista"].append(f"{t} ({ln.strip()[:80]})")
    return out


def percentil(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * p
    return xs[int(k)] + (xs[min(int(k) + 1, len(xs) - 1)] - xs[int(k)]) * (k - int(k))


def tabla(filas: list[dict]) -> str:
    out = ["ruta     esfuerzo  n  p50 s  p90 s  entrada (cache)   salida  USD/llamada  bien en_datos inventadas  errores"]
    for ruta, niveles in NIVELES.items():
        for nivel in niveles:
            xs = [f for f in filas if f["ruta"] == ruta and f["esfuerzo"] == nivel]
            ok = [f for f in xs if not f["error"]]
            if not xs:
                continue
            ms = [f["ms"] / 1000 for f in ok] or [0]
            q = {k: sum(f["calidad"][k] for f in ok) for k in ("bien", "en_datos", "inventadas")}
            out.append(f"{ruta:8} {nivel:8} {len(xs):2} {percentil(ms, .5):6.1f} {percentil(ms, .9):6.1f}"
                       f" {statistics.mean([f['entrada'] for f in ok] or [0]):8.0f} ({statistics.mean([f['cache']['leida'] + f['cache']['escrita'] for f in ok] or [0]):5.0f})"
                       f" {statistics.mean([f['salida'] for f in ok] or [0]):8.0f} {statistics.mean([f['coste'] for f in ok] or [0]):10.3f}"
                       f"  {q['bien']:4} {q['en_datos']:8} {q['inventadas']:10}  {len(xs) - len(ok)}")
    out.append(f"gasto total {sum(f['coste'] for f in filas):.2f} USD en {len(filas)} llamadas")
    return "\n".join(out)


async def graba(carpeta: pathlib.Path, http: httpx.AsyncClient, entorno: dict) -> list[dict]:
    bot = sv.Bot(entorno, None, http)
    pub = bb.Bybit("", "", http)
    casos = []
    for activo in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        ctx, dec = await bot.sobre(activo)
        marca = float((await pub.get("/v5/market/tickers", category="linear", symbol=activo))["result"]["list"][0]["markPrice"])
        p = {"id": f"{activo}:Buy:grabado", "symbol": activo, "lado": 1, "cantidad": round(500 / marca, 6), "entrada": marca,
             "marca": marca * 0.997, "apalancamiento": 50.0, "liquidacion": None, "stop": round(marca * 0.994, 6),
             "objetivo": round(marca * 1.02, 6), "margen": 10.0, "pnl_abierto": None}
        alerta = f"{activo[:3]} rafaga BAJISTA z=-4.6 vol x3.1 desequilibrio -0.52 · {marca * 0.997:g} (caso grabado)"
        datos = {"sobre": ctx, "decide": dec, "posicion": p}
        casos.append({"ruta": "evalua", "id": f"evalua-{activo}", "datos": datos, "texto": sv.mensaje("EVALUA", posicion=p, dec=dec, ctx=ctx)})
        casos.append({"ruta": "escala", "id": f"escala-{activo}", "datos": datos,
                      "texto": sv.mensaje("ESCALA", alerta=alerta, posicion=p, dec=dec, ctx=ctx)})
        if activo == "BTCUSDT":
            casos += [{"ruta": "pregunta", "id": f"pregunta-{i}", "datos": {"sobre": ctx, "decide": dec},
                       "texto": sv.mensaje("PREGUNTA", pregunta=q, dec=dec, ctx=ctx)} for i, q in enumerate(PREGUNTAS)]
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "casos.json").write_text(json.dumps({"grabado": datetime.now(UTC).isoformat(), "casos": casos}, ensure_ascii=False))
    return casos


async def corre(carpeta: pathlib.Path, http: httpx.AsyncClient, entorno: dict) -> str:
    casos = json.loads((carpeta / "casos.json").read_text())["casos"]
    veces, tope = int(entorno.get("MIDE_VECES") or 1), float(entorno.get("MIDE_TOPE_USD") or 12)
    filas, gastado = [], 0.0
    for c in casos:
        for nivel in NIVELES[c["ruta"]]:
            for vez in range(veces):
                r = await llm.llama(http, entorno["ANTHROPIC_API_KEY"], sv.ESTABLE, c["texto"], gastado, tope, nivel)
                gastado += r["coste"]
                filas.append({"caso": c["id"], "ruta": c["ruta"], "esfuerzo": nivel, "vez": vez, "ms": r["ms"], "entrada": r["entrada"],
                              "cache": r["cache"], "salida": r["salida"], "coste": r["coste"], "error": r["error"],
                              "calidad": califica(r["texto"], c["datos"]), "texto": r["texto"]})
                print(f"{c['id']} {nivel} {vez}: {r['ms']} ms, {r['coste']:.3f} USD, {filas[-1]['calidad']['inventadas']} inventadas"
                      f"{' · ' + r['error'] if r['error'] else ''}", flush=True)
    t = tabla(filas)
    (carpeta / "resultados.json").write_text(json.dumps({"medido": datetime.now(UTC).isoformat(), "filas": filas}, ensure_ascii=False))
    (carpeta / "tabla.txt").write_text(t + "\n")
    return t


async def principal(argv: list[str]):
    orden, carpeta = argv[0], pathlib.Path(argv[1])
    async with httpx.AsyncClient() as http:
        if orden == "graba":
            print(f"{len(await graba(carpeta, http, dict(os.environ)))} casos en {carpeta / 'casos.json'}")
        elif orden == "corre":
            print(await corre(carpeta, http, dict(os.environ)))
        else:
            raise SystemExit("uso: python -m app.bot.mide graba|corre <carpeta>")


if __name__ == "__main__":
    asyncio.run(principal(sys.argv[1:]))
