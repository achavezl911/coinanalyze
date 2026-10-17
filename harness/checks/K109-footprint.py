"""K109 · ayudante: abre el FOOTPRINT en un Chromium de verdad y juzga LO PINTADO contra LO SERVIDO, y lo servido
contra las CELDAS (OF-2, campana 142). No importa nada de app/ ni de static/: el estado de cada vela, la value area,
el POC, el paso automatico y los desequilibrios se recalculan aqui con su propia aritmetica decimal.

LO PINTADO se lee por el CONTRATO que declara static/flujo/flujo-dibujo.js: `window.FLUJO_PINTADO` (por vela visible su
estado y su marca, el POC y la value area con sus pixeles, el resumen, y por nivel su fila, el texto que se paso a
fillText, el color, el filtro y los desequilibrios). Y no se cree a pies juntillas: cada numero que el contrato dice
pintado tiene que estar en el registro de fillText del lienzo, que esta sonda intercepta antes de que cargue la pagina.

LOS BRAZOS (cualquiera pone ROJO; uno sin canal es NO MEDIDO y un ROJO de otro manda sobre el):
  (P) la pagina   pinta la vista, sin excepciones de JS, y pide el footprint de SU hash
  (V) la familia  pide exactamente los venues de UNA familia, la de su hash; nunca dos sumadas
  (S) lo servido  == lo recalculado desde las celdas: niveles, compra, venta, operaciones, totales, POC, value area de
                  cada vela, cobertura y, con paso=auto, el paso que sale de la regla
  (F) lo pintado  == lo servido: cada nivel con su fila en su precio, sus numeros (a la precision con que se
                  escriben), el color del delta, el POC y la value area en sus filas, el resumen, y el ESTADO de cada
                  vela (abierta, hueco, incompleta con cuantos le faltan, vacia, completa) recalculado de la cobertura
  (D) los desequilibrios pintados == los recalculados con la regla de la campana (diagonal, x3, minimo la media por
                  nivel de la vela, apilado de 3), que la pagina tiene que declarar igual
Uso: K109-footprint.py juzga (el entorno lo pone K109-lo-pintado-es-lo-servido.sh)
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import importlib.util
import io
import json
import netrc
import os
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from decimal import ROUND_FLOOR, Decimal

AQUI = pathlib.Path(__file__).resolve().parent
H = os.environ.get("K109_HARNESS", "/srv/coinanalyze/harness")
BASE = os.environ.get("K109_BASE", "")  # sin ella: PRODUCCION
DB = os.environ.get("K109_DB", "")  # con K109_BASE: la base de las celdas del banco
RUTA = "/api" + "/orderflow/footprint"
# LAS VISTAS FIJAS, del pasado para que sean reproducibles. Las celdas se guardan 30 dias: en produccion estas caducan
# hacia el 2026-11-16 (desde entonces, NO MEDIDO «sin dato»; se mueven cambiando estas tres lineas).
VISTAS = [
    "#BTC/1m/perp/5/hasta=2026-10-17T11:30:00Z/ver=20",  # paso fijado y numeros; la 11:13 sin un minuto entero
    "#ETH/1m/deribit/hasta=2026-10-17T11:50:00Z/ver=40",  # paso automatico; minutos vacios e incompletos
    "#SOL/5m/spot/unidad=usd/hasta=2026-10-17T12:00:00Z/ver=60",  # en USD; huecos de antes del servicio
]
ANCHO, ALTO = 1920, 1080
# Lo DECIDIDO por el encargo y por P2/P3 de la campana, escrito aqui y no leido de la pagina:
FAMILIAS = {"perp": {"binance_usdm", "bybit_linear", "okx_swap", "bitget_usdt"},
            "spot": {"binance_spot", "bybit_spot", "okx_spot"}, "coinbase": {"coinbase_spot"},
            "deribit": {"deribit_perp"}}
MARCOS = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}
RAZON, APILADO, CIERRE_S, OBJETIVO = Decimal(3), 3, 90, 20

INTERCEPTA = r"""
(() => {
  const orig = CanvasRenderingContext2D.prototype.fillText;
  window.__K109_TEXTOS = [];
  CanvasRenderingContext2D.prototype.fillText = function (t, x, y) {
    const m = this.getTransform();
    if (window.__K109_TEXTOS.length < 400000) window.__K109_TEXTOS.push([String(t), m.a * x + m.e, m.d * y + m.f]);
    return orig.apply(this, arguments);
  };
})();
"""
COSECHA = r"""
(() => {
  window.__K109_TEXTOS = [];
  if (window.FLUJO_HITOS && window.FLUJO_HITOS.repinta) window.FLUJO_HITOS.repinta();
  return {pintado: window.FLUJO_PINTADO || null, textos: window.__K109_TEXTOS, hash: location.hash,
          hitos: window.FLUJO_HITOS ? {listo: window.FLUJO_HITOS.listo, vista: window.FLUJO_HITOS.vista} : null};
})()
"""


class Canal(Exception):
    pass


def D(x) -> Decimal:
    return Decimal(str(x))


def txt(d: Decimal) -> str:
    return "0" if d == 0 else format(d.normalize(), "f")


def epoch(iso: str) -> int:
    return int(datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp())


def lee_vista(h: str) -> dict:
    p = h.lstrip("#").split("/")
    e = {"activo": p[0], "marco": p[1], "familia": p[2], "paso": "auto", "unidad": "base"}
    for x in p[3:]:
        k, _, v = x.partition("=")
        if not v:
            e["paso"] = k
        elif k in ("unidad", "hasta"):
            e[k] = v
    return e


# --------------------------------------------------------------------------------------------- canales
def sql(q: str) -> list[list[str]]:
    if BASE:
        cmd, env = ["psql", DB, "-X", "-A", "-F|", "-t", "-q", "-v", "ON_ERROR_STOP=1", "-c", "SET TIME ZONE 'UTC'",
                    "-c", q], dict(os.environ)
    else:
        cmd, env = ["sh", f"{H}/bin/prodsql", q], {**os.environ, "TODO": "1"}
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=180)
    if r.returncode:
        raise Canal(f"{'psql' if BASE else 'prodsql'} rc={r.returncode}: {(r.stderr or r.stdout).strip()[:160]}")
    return [x.split("|") for x in r.stdout.splitlines() if x.strip()]


def cabecera() -> dict:
    if BASE:
        return {}
    env = dict(re.findall(r"^(\w+)=(\S+)", pathlib.Path(f"{H}/env").read_text(), re.M))
    n = netrc.netrc(env["NETRC"])
    cred = next((n.authenticators(h) for h in n.hosts if n.authenticators(h)), None)
    if not cred:
        raise Canal("el netrc no da credencial")
    return {"Authorization": "Basic " + base64.b64encode(f"{cred[0]}:{cred[2]}".encode()).decode()}


def raiz() -> str:
    if BASE:
        return BASE.rstrip("/")
    env = dict(re.findall(r"^(\w+)=(\S+)", pathlib.Path(f"{H}/env").read_text(), re.M))
    return env["API_PROD"].rstrip("/")


def hay_pagina(url: str, cab: dict) -> int:
    import ssl

    ctx = ssl.create_default_context()
    ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE  # el certificado de 140 es propio
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=cab), timeout=30, context=ctx) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


# --------------------------------------------------------------------------------------------- recalculo propio
def poc_de(tot: dict) -> Decimal | None:
    if not tot:
        return None
    m = max(tot.values())
    return min(n for n, t in tot.items() if t == m)


def value_area(tot: dict) -> tuple | None:
    poc = poc_de(tot)
    if poc is None:
        return None
    orden = sorted(tot)
    meta = sum(tot.values()) * Decimal("0.70")
    lo = hi = orden.index(poc)
    vol = tot[poc]
    while vol < meta and (lo > 0 or hi < len(orden) - 1):
        sube = tot[orden[hi + 1]] if hi < len(orden) - 1 else None
        baja = tot[orden[lo - 1]] if lo > 0 else None
        if baja is None or (sube is not None and sube >= baja):
            hi += 1
            vol += tot[orden[hi]]
        else:
            lo -= 1
            vol += tot[orden[lo]]
    return orden[lo], orden[hi], vol


def piso(x: Decimal, p: Decimal) -> Decimal:
    return (x / p).to_integral_value(rounding=ROUND_FLOOR)


def paso_auto(rangos: list, base: Decimal) -> tuple:
    for e in range(12):
        for m in (1, 2, 5):
            p = base * m * 10**e
            n = sorted(int(piso(hi, p) - piso(lo, p)) + 1 for lo, hi in rangos)[len(rangos) // 2]
            if n <= OBJETIVO:
                return p, n
    return p, n


def desequilibrios(niveles: list, s: Decimal) -> list:
    """[(nivel, compra, venta)] ascendente, al paso s -> [(dc, dv, ac, av)]: la regla de la campana, en Decimal."""
    if not niveles:
        return []
    P = [n for n, _, _ in niveles]
    C = {n: c for n, c, _ in niveles}
    V = {n: v for n, _, v in niveles}
    media_n = sum(C.values()) + sum(V.values())
    N = len(niveles)
    lo, hi = P[0], P[-1]
    out = []
    for n in P:
        dc = n - s >= lo and C[n] > 0 and C[n] * N >= media_n and C[n] >= RAZON * V.get(n - s, Decimal(0))
        dv = n + s <= hi and V[n] > 0 and V[n] * N >= media_n and V[n] >= RAZON * C.get(n + s, Decimal(0))
        out.append([dc, dv, False, False])
    for lado, marca in ((0, 2), (1, 3)):
        ini = 0
        for i in range(1, N + 1):
            if i < N and out[i][lado] and out[i - 1][lado] and P[i] - P[i - 1] == s:
                continue
            if out[i - 1][lado] and i - ini >= APILADO:
                for k in range(ini, i):
                    out[k][marca] = True
            ini = i
    return [tuple(x) for x in out]


def estado(v: dict, as_of: int, marco: str) -> tuple:
    c = v.get("cobertura") or {}
    if epoch(v["ts"]) + MARCOS[marco] * 60 + CIERRE_S > as_of:
        return "abierta", None
    if not c.get("minutos_con_fila"):
        return "hueco", c.get("minutos_esperados")
    if not c.get("completa"):
        return "incompleta", c["minutos_esperados"] - c["minutos_completos"]
    return ("vacia", 0) if not v["niveles"] else ("completa", 0)


def casa(texto: str | None, servido: str) -> bool:
    """El texto pintado dice el valor servido a la precision con que se escribio; un no-cero nunca se escribe «0»."""
    m = re.fullmatch(r"([+-]?)(\d+)(?:\.(\d+))?(?:e([+-]?\d+))?([KM]?)", texto or "")
    if not m:
        return False
    s = D(servido)
    if m.group(2) + (m.group(3) or "") == "0" * len(m.group(2) + (m.group(3) or "")):
        return s == 0
    mult = Decimal({"": 1, "K": 1000, "M": 1000000}[m.group(5)]) * Decimal(10) ** int(m.group(4) or 0)
    num = D(m.group(1) + m.group(2) + ("." + m.group(3) if m.group(3) else "")) * mult
    unidad = Decimal(10) ** -len(m.group(3) or "") * mult
    return abs(num - s) <= unidad / 2 + unidad / 1000


# --------------------------------------------------------------------------------------------- una vista
async def mira(K, vista: str, cab: dict) -> dict:
    out = {"vista": vista, "excepciones": [], "peticiones": []}
    with K.Chromium(ANCHO, ALTO) as c:
        req = urllib.request.Request(f"http://127.0.0.1:{c.puerto}/json/new?about:blank", method="PUT")
        with urllib.request.urlopen(req, timeout=10) as r:
            destino = json.load(r)
        async with K.websockets.connect(destino["webSocketDebuggerUrl"], max_size=200 * 1024 * 1024) as ws:
            s = K.Sesion(ws)
            for metodo in ("Page.enable", "Runtime.enable", "Network.enable"):
                await s.pide(metodo)
            await s.pide("Network.setCacheDisabled", cacheDisabled=True)
            await s.pide("Emulation.setDeviceMetricsOverride", width=ANCHO, height=ALTO, deviceScaleFactor=1,
                         mobile=False)
            if cab:
                await s.pide("Network.setExtraHTTPHeaders", headers=cab)
            await s.pide("Page.addScriptToEvaluateOnNewDocument", source=INTERCEPTA)
            await s.pide("Page.navigate", url=f"{raiz()}/flujo{vista}")
            listo = False
            for _ in range(200):
                await s.drena(0.2)
                try:
                    listo = await s.evalua("!!(window.FLUJO_HITOS && window.FLUJO_HITOS.listo)")
                except K.SystemExit2:
                    listo = False
                if listo:
                    break
            await s.drena(0.5)
            out["listo"] = listo
            out.update(await s.evalua(COSECHA))
            porid = {}
            for e in s.eventos:
                p, m = e.get("params", {}), e.get("method")
                if m == "Runtime.exceptionThrown":
                    out["excepciones"].append(json.dumps(p.get("exceptionDetails", {}))[:300])
                elif m == "Network.requestWillBeSent" and RUTA in p["request"]["url"]:
                    porid[p["requestId"]] = {"url": p["request"]["url"], "estado": None}
                elif m == "Network.responseReceived" and p.get("requestId") in porid:
                    porid[p["requestId"]]["estado"] = p["response"]["status"]
            for rid, x in porid.items():
                if x["estado"] == 200:
                    try:
                        r = await s.pide("Network.getResponseBody", requestId=rid)
                        x["cuerpo"] = json.loads(base64.b64decode(r["body"]) if r.get("base64Encoded") else r["body"])
                    except (K.SystemExit2, ValueError, KeyError):
                        x["cuerpo"] = None
                out["peticiones"].append(x)
            await s.cierra()
    return out


# --------------------------------------------------------------------------------------------- el juicio
def juzga_vista(vista: str, vio: dict, rojos: list, nomed: list, info: list) -> dict:
    e = lee_vista(vista)
    pref = f"[{e['activo']} {e['marco']} {e['familia']}]"
    pin = vio.get("pintado")
    # (P) la pagina
    if vio["excepciones"]:
        rojos.append(f"(P) {pref} la pagina lanzo {len(vio['excepciones'])} excepcion(es): {vio['excepciones'][0]}")
    if not vio.get("listo") or not pin or not pin.get("velas"):
        rojos.append(f"(P) {pref} la pagina no pinto la vista (listo={vio.get('listo')}, contrato "
                     f"{'sin velas' if pin else 'ausente'}): no hay nada que comparar")
        return {}
    pets = [p for p in vio["peticiones"] if p.get("cuerpo")]
    if not pets:
        rojos.append(f"(P) {pref} la pagina no trajo ninguna respuesta buena de {RUTA}")
        return {}
    pet = pets[-1]
    q = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(pet["url"]).query).items()}
    sv = pet["cuerpo"]
    pedido = {"symbol": e["activo"], "marco": e["marco"], "paso": e["paso"], "unidad": e["unidad"], "hasta": e["hasta"]}
    malos = [f"{k}={q.get(k)} (su hash dice {v})" for k, v in pedido.items()
             if (q.get(k) or "") != v and not (k == "hasta" and q.get(k) and epoch(q[k]) == epoch(v))]
    if malos:
        rojos.append(f"(P) {pref} pide lo que su hash no dice: {'; '.join(malos)}")
    # (V) la familia
    venues = set((q.get("venues") or "").split(","))
    if venues != FAMILIAS[e["familia"]] or set(sv.get("venues") or ()) != FAMILIAS[e["familia"]] or \
            set(pin.get("venues") or ()) != FAMILIAS[e["familia"]]:
        otras = [f for f, vs in FAMILIAS.items() if vs & venues]
        rojos.append(f"(V) {pref} pide {sorted(venues)} ({len(otras)} familia(s): {', '.join(otras)}), sirve "
                     f"{sv.get('venues')} y pinta {pin.get('venues')}: tiene que ser UNA, la de su hash")
    paso = D(sv["paso"])
    as_of = epoch(sv["as_of"])
    servidas = {epoch(v["ts"]): v for v in sv["velas"]}
    # (F) lo pintado == lo servido, y (D) los desequilibrios
    if str(pin.get("umbrales", {}).get("razon")) != str(RAZON) or pin.get("umbrales", {}).get("apilado") != APILADO \
            or pin.get("umbrales", {}).get("cierre_s") != CIERRE_S:
        rojos.append(f"(D) {pref} la pagina declara otra regla que la de la campana: {pin.get('umbrales')}")
    esc = pin.get("escala") or {}

    def y(p: Decimal) -> float:
        return esc["arriba"] + (esc["hi"] - float(p)) / (esc["hi"] - esc["lo"]) * (esc["abajo"] - esc["arriba"])

    textos = {}
    for t, xx, yy in vio.get("textos") or []:
        textos.setdefault(t, []).append((xx, yy))
    f_malos, d_malos, numeros = [], [], 0
    for r in pin["velas"]:
        v = servidas.get(epoch(r["ts"]))
        if v is None:
            f_malos.append(f"vela {r['ts']} pintada y no servida")
            continue
        st, faltan = estado(v, as_of, e["marco"])
        if (r["estado"], r.get("faltan")) != (st, faltan):
            f_malos.append(f"vela {r['ts']}: pintada {r['estado']} (faltan {r.get('faltan')}) y su cobertura "
                           f"servida dice {st} (faltan {faltan})")
        marca = {"abierta": "en curso", "hueco": "hueco", "vacia": "0 ops",
                 "incompleta": f"faltan {faltan}/{(v.get('cobertura') or {}).get('minutos_esperados')}"}.get(st)
        if r.get("marca") is not None and r["marca"] != marca:
            f_malos.append(f"vela {r['ts']}: su marca dice «{r['marca']}» y su estado es «{marca}»")
        sn = {D(n["nivel"]): n for n in v["niveles"]}
        pn = {D(n["nivel"]): n for n in r["niveles"]}
        if set(sn) != set(pn):
            f_malos.append(f"vela {r['ts']}: niveles pintados {len(pn)} != servidos {len(sn)} "
                           f"(sobran {sorted(set(pn) - set(sn))[:3]}, faltan {sorted(set(sn) - set(pn))[:3]})")
            continue
        des = dict(zip(sorted(sn), desequilibrios([(n, D(sn[n]["compra"]), D(sn[n]["venta"])) for n in sorted(sn)],
                                                  paso), strict=True))
        for n, f in pn.items():
            s_ = sn[n]
            if any(D(f[k]) != D(s_[k]) for k in ("venta", "compra", "delta", "total")):
                f_malos.append(f"vela {r['ts']} nivel {txt(n)}: pinta venta {f['venta']} compra {f['compra']} delta "
                               f"{f['delta']} y se sirvio {s_['venta']} / {s_['compra']} / {s_['delta']}")
            signo = "compra" if D(s_["delta"]) > 0 else "venta" if D(s_["delta"]) < 0 else "neutro"
            if f["color"] != signo:
                f_malos.append(f"vela {r['ts']} nivel {txt(n)}: color {f['color']} con delta servido {s_['delta']}")
            if f["filtro"] != "escondida" and (abs(f["y0"] - y(n + paso)) > 1.01 or abs(f["y1"] - y(n)) > 1.01):
                f_malos.append(f"vela {r['ts']} nivel {txt(n)}: su fila {f['y0']}-{f['y1']} no es la de su precio "
                               f"({y(n + paso):.1f}-{y(n):.1f})")
            for lado in ("venta", "compra"):
                t = f.get("texto_" + lado)
                if t is None:
                    continue
                numeros += 1
                if not casa(t, s_[lado]):
                    f_malos.append(f"vela {r['ts']} nivel {txt(n)}: escribe {lado} «{t}» y se sirvio {s_[lado]}")
                if not any(abs(yy - (f["y0"] + f["y1"]) / 2) <= 1.01 for _, yy in textos.get(t, ())):
                    f_malos.append(f"vela {r['ts']} nivel {txt(n)}: el contrato dice «{t}» y el lienzo no lo escribio")
            if (f["dc"], f["dv"], f["ac"], f["av"]) != des[n]:
                d_malos.append(f"vela {r['ts']} nivel {txt(n)}: pinta (comprador, vendedor, apilados) "
                               f"{(f['dc'], f['dv'], f['ac'], f['av'])} y la regla da {des[n]}")
        poc = D(v["poc"]) if v.get("poc") is not None else None
        if (D(r["poc"]["nivel"]) if r.get("poc") else None) != poc:
            f_malos.append(f"vela {r['ts']}: POC pintado en {r['poc'] and r['poc']['nivel']} y servido {v.get('poc')}")
        elif poc is not None and (abs(r["poc"]["y0"] - y(poc + paso)) > 1.01 or abs(r["poc"]["y1"] - y(poc)) > 1.01):
            f_malos.append(f"vela {r['ts']}: el marco del POC no esta en la fila de {txt(poc)}")
        va = v.get("value_area")
        if (r.get("va") and (D(r["va"]["val"]), D(r["va"]["vah"]))) != (va and (D(va["val"]), D(va["vah"]))):
            f_malos.append(f"vela {r['ts']}: value area pintada {r.get('va')} y servida {va}")
        elif va and (abs(r["va"]["y0"] - y(D(va["vah"]) + paso)) > 1.01 or abs(r["va"]["y1"] - y(D(va["val"]))) > 1.01):
            f_malos.append(f"vela {r['ts']}: la barra de la value area no va de {va['val']} a {va['vah']}")
        res = r.get("resumen") or {}
        for k in ("delta", "total"):
            if res.get(k) is not None and not casa(res[k].lstrip("+"), v[k]):
                f_malos.append(f"vela {r['ts']}: el resumen escribe {k} «{res[k]}» y se sirvio {v[k]}")
        if res.get("operaciones") is not None and res["operaciones"] != str(v["operaciones"]):
            f_malos.append(f"vela {r['ts']}: el resumen escribe {res['operaciones']} operaciones y se sirvieron "
                           f"{v['operaciones']}")
    for etiqueta, lista, brazo in (("(F)", f_malos, "lo pintado != lo servido"), ("(D)", d_malos, "desequilibrios")):
        if lista:
            rojos.append(f"{etiqueta} {pref} {brazo}: {lista[0]}" + (f" (y {len(lista) - 1} mas)" if len(lista) > 1 else ""))
    if e["paso"] != "auto" and numeros == 0 and not f_malos and any(r["niveles"] for r in pin["velas"]):
        nomed.append(f"(F) {pref} la vista con numeros no escribio ninguno: no se pudo comparar ni una cifra")
    estados = {}
    for r in pin["velas"]:
        estados[r["estado"]] = estados.get(r["estado"], 0) + 1
    info.append(f"(F)(D) {pref} {len(pin['velas'])} velas pintadas ({', '.join(f'{k} {n}' for k, n in sorted(estados.items()))}), "
                f"{sum(len(r['niveles']) for r in pin['velas'])} niveles, {numeros} numeros releidos del lienzo, "
                f"{sum(1 for r in pin['velas'] for f in r['niveles'] if f['dc'] or f['dv'])} desequilibrios")
    return {"e": e, "q": q, "sv": sv}


def juzga_celdas(x: dict, rojos: list, nomed: list, info: list) -> None:
    """(S) lo servido == lo recalculado desde las celdas del sujeto, para la peticion que hizo la pagina."""
    e, q, sv = x["e"], x["q"], x["sv"]
    pref = f"[{e['activo']} {e['marco']} {e['familia']}]"
    a, b = q["desde"], q["hasta"]
    vs = ",".join(f"'{v}'" for v in sorted(set(q["venues"].split(","))) if re.fullmatch(r"[a-z_]+", v))
    w = f"symbol='{e['activo']}' AND venue IN ({vs}) AND ts >= '{a}' AND ts < '{b}'"
    celdas = sql("SELECT extract(epoch FROM ts)::bigint, nivel, compra_base, venta_base, compra_usd, venta_usd, "
                 f"compras, ventas FROM orderflow_celda WHERE {w}")
    cob = sql(f"SELECT extract(epoch FROM ts)::bigint, segundos FROM orderflow_cobertura WHERE {w}")
    base = D(sql(f"SELECT paso FROM orderflow_paso WHERE symbol='{e['activo']}'")[0][0])
    if not celdas:
        nomed.append(f"(S) {pref} sin dato en la ventana fija {a} - {b}: ni una celda (se guardan 30 dias)")
        return
    m = MARCOS[e["marco"]] * 60
    malos = []
    if q.get("paso") == "auto":
        rangos = {}
        for ts, nivel, *_ in celdas:
            k = int(ts) - int(ts) % m
            lo, hi = rangos.get(k, (D(nivel), D(nivel)))
            rangos[k] = (min(lo, D(nivel)), max(hi, D(nivel)))
        p, n = paso_auto(list(rangos.values()), base)
        if D(sv["paso"]) != p or (sv.get("paso_auto") or {}).get("niveles_vela_mediana") != n:
            malos.append(f"paso automatico servido {sv['paso']} ({(sv.get('paso_auto') or {}).get('niveles_vela_mediana')} "
                         f"niveles) y la regla da {txt(p)} ({n})")
    paso = D(sv["paso"])
    velas: dict = {}
    for ts, nivel, cb, vb, cu, vu, nc, nv in celdas:
        k = int(ts) - int(ts) % m
        c, v = (D(cb), D(vb)) if e["unidad"] == "base" else (D(cu), D(vu))
        z = velas.setdefault(k, {}).setdefault(piso(D(nivel), paso) * paso, [Decimal(0), Decimal(0), 0])
        z[0] += c
        z[1] += v
        z[2] += int(nc) + int(nv)
    cobs: dict = {}
    for ts, seg in cob:
        z = cobs.setdefault(int(ts) - int(ts) % m, [0, 0, 0])
        z[0] += 1
        z[1] += int(seg) == 60
        z[2] += int(seg)
    n_venues = len(set(q["venues"].split(",")))
    for v in sv["velas"]:
        k = epoch(v["ts"])
        mio = velas.get(k, {})
        serv = {D(n["nivel"]): (D(n["compra"]), D(n["venta"]), int(n["operaciones"])) for n in v["niveles"]}
        if serv != {n: tuple(z) for n, z in mio.items()}:
            dif = sorted(set(serv.items()) ^ {(n, tuple(z)) for n, z in mio.items()})[:1]
            malos.append(f"vela {v['ts']}: niveles servidos != celdas ({len(serv)} vs {len(mio)}; primero distinto {dif})")
            continue
        tot = {n: z[0] + z[1] for n, z in mio.items()}
        compra, venta = sum((z[0] for z in mio.values()), Decimal(0)), sum((z[1] for z in mio.values()), Decimal(0))
        if (D(v["compra"]), D(v["venta"]), D(v["delta"]), D(v["total"]), v["operaciones"]) != (
                compra, venta, compra - venta, compra + venta, sum(z[2] for z in mio.values())):
            malos.append(f"vela {v['ts']}: totales servidos != celdas")
        if (D(v["poc"]) if v.get("poc") is not None else None) != poc_de(tot):
            malos.append(f"vela {v['ts']}: POC servido {v.get('poc')} != celdas {poc_de(tot)}")
        va = value_area(tot)
        sva = v.get("value_area")
        if (sva and (D(sva["val"]), D(sva["vah"]), D(sva["volumen"]))) != va:
            malos.append(f"vela {v['ts']}: value area servida {sva} != celdas "
                         f"{va and (txt(va[0]), txt(va[1]), txt(va[2]))}")
        z = cobs.get(k, [0, 0, 0])
        c = v.get("cobertura") or {}
        if (c.get("minutos_esperados"), c.get("minutos_con_fila"), c.get("minutos_completos"), c.get("segundos")) != (
                MARCOS[e["marco"]] * n_venues, z[0], z[1], z[2]):
            malos.append(f"vela {v['ts']}: cobertura servida {c} != la de las celdas ({z[0]} con fila, {z[1]} "
                         f"completos de {MARCOS[e['marco']] * n_venues})")
    if malos:
        rojos.append(f"(S) {pref} lo servido != las celdas: {malos[0]}" + (f" (y {len(malos) - 1} mas)" if len(malos) > 1 else ""))
    else:
        info.append(f"(S) {pref} {len(sv['velas'])} velas servidas de {a} a {b} == recalculadas de {len(celdas)} celdas "
                    f"(paso {sv['paso']}{' automatico' if q.get('paso') == 'auto' else ''}, en {e['unidad']})")


def juzga() -> int:
    _spec = importlib.util.spec_from_file_location("k102_mesa", AQUI / "K102-mesa.py")
    K = importlib.util.module_from_spec(_spec)
    try:
        with contextlib.redirect_stderr(io.StringIO()):  # K102 lo dice por stderr; aqui lo dice la primera linea
            _spec.loader.exec_module(K)
            K.binario_chromium()
    except SystemExit:
        print("NO MEDIDO: sin Chromium (o sin websockets) en 143 no se puede mirar la pagina")
        return 2
    sujeto = f"el ARBOL servido en {BASE} (celdas de {DB})" if BASE else f"PRODUCCION ({raiz()}, celdas por bin/prodsql)"
    try:
        cab = cabecera()
        estado_pagina = hay_pagina(f"{raiz()}/flujo", cab)
    except (Canal, OSError, KeyError) as exc:
        print(f"NO MEDIDO (CANAL): no se pudo preguntar por la pagina · sujeto: {sujeto} · {str(exc)[:160]}")
        return 2
    if estado_pagina == 404:
        print(f"NO MEDIDO: FALTA DESPLEGAR · {sujeto} no sirve /flujo (404). El codigo no esta mal: no esta desplegado")
        return 2
    if estado_pagina != 200:
        print(f"NO MEDIDO (CANAL): /flujo contesto {estado_pagina} · sujeto: {sujeto}")
        return 2
    rojos: list[str] = []
    nomed: list[str] = []
    info: list[str] = []
    huella = hashlib.sha256()
    for vista in VISTAS:
        try:
            vio = asyncio.run(asyncio.wait_for(mira(K, vista, cab), timeout=150))
        except (K.SystemExit2, TimeoutError, OSError) as exc:
            nomed.append(f"(P) {vista}: la sonda no pudo mirar la pagina ({str(exc)[:120]})")
            continue
        x = juzga_vista(vista, vio, rojos, nomed, info)
        pin = vio.get("pintado") or {}
        huella.update(json.dumps([vista, pin.get("velas"), pin.get("venues"), pin.get("umbrales"),
                                  [p["url"].split("?", 1)[-1] for p in vio["peticiones"]],
                                  [p.get("cuerpo") and p["cuerpo"].get("velas") for p in vio["peticiones"]]],
                                 sort_keys=True, default=str).encode())
        if not x:
            continue
        try:
            juzga_celdas(x, rojos, nomed, info)
        except (Canal, IndexError) as exc:
            nomed.append(f"(S) [{vista}] sin canal a las celdas: {str(exc)[:160]}")
    cola = f" · sujeto: {sujeto} · huella {huella.hexdigest()[:16]}"
    if rojos:
        print(f"ROJO  K109 · lo pintado no es lo servido, o lo servido no es lo de las celdas · {len(rojos)} hallazgo(s)"
              + cola)
    elif nomed:
        print(f"NO MEDIDO: K109 · {nomed[0]}" + cola)
    else:
        print("VERDE  K109 · el footprint pinta lo que sirve, y lo servido es lo de las celdas: niveles, numeros, POC, "
              "value area, desequilibrios, cobertura y una sola familia" + cola)
    for linea in rojos + nomed + info:
        print(f"   · {linea}")
    return 1 if rojos else 2 if nomed else 0


if __name__ == "__main__":
    if sys.argv[1:] != ["juzga"]:
        print(__doc__)
        sys.exit(2)
    try:
        sys.exit(juzga())
    except Exception as exc:  # noqa: BLE001 - un fallo de la sonda no acusa a la pagina
        print(f"NO MEDIDO: la sonda de K109 fallo y no juzgo nada ({type(exc).__name__}: {str(exc)[:160]})")
        sys.exit(2)
