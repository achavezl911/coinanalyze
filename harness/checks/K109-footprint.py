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
from datetime import UTC as ZONA
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
    # OF-6a (campana 148): 18 velas y no 20: con la fila fija de 12 px (fuente de 10 px) y la semicelda de F-09
    # (el texto + 4 px), «0.123» cabe con 18 velas a 1920 px y no con 20; y la de las 11:13 sigue a la vista
    "#BTC/1m/perp/5/hasta=2026-10-17T11:30:00Z/ver=18",  # paso fijado y numeros; la 11:13 sin un minuto entero
    "#ETH/1m/deribit/hasta=2026-10-17T11:50:00Z/ver=40",  # paso automatico; minutos vacios e incompletos
    "#SOL/5m/spot/unidad=usd/hasta=2026-10-17T12:00:00Z/ver=60",  # en USD; huecos de antes del servicio
    # OF-3 (campana 143): una vista fija MAS por capa, del 2026-10-17 como las de arriba: caducan con ellas, hacia el
    # 2026-11-16 (las celdas se guardan 30 dias), y se mueven igual.
    "#BTC/5m/perp/hasta=2026-10-17T11:30:00Z/ver=60/capas=perfil,vwap",  # la sesion del dia en curso y sin su noche
    "#BTC/15m/perp/hasta=2026-10-17T11:30:00Z/sesion=12:00-11:00/compuesto=2",  # cruza la medianoche; una sin dato
    "#SOL/5m/spot/unidad=usd/hasta=2026-10-17T12:00:00Z/ver=60/capas=dinamico",  # lo visible, en USD
    "#ETH/1m/deribit/hasta=2026-10-17T11:50:00Z/ver=120/fijo=2026-10-17T10:00:00Z,2026-10-17T11:00:00Z",
    "#BTC/1m/perp/hasta=2026-10-17T14:00:00Z/modo=tpo/sesiones=1",  # el TPO del dia: letras de la P a la b
    "#BTC/1m/perp/hasta=2026-10-17T12:00:00Z/sesion=08:00-12:00/modo=tpo/sesiones=2",  # balance inicial; una hueca
]
ANCHO, ALTO = 1920, 1080
# Lo DECIDIDO por el encargo y por P2/P3 de la campana, escrito aqui y no leido de la pagina:
FAMILIAS = {"perp": {"binance_usdm", "bybit_linear", "okx_swap", "bitget_usdt"},
            "spot": {"binance_spot", "bybit_spot", "okx_spot"}, "coinbase": {"coinbase_spot"},
            "deribit": {"deribit_perp"}}
MARCOS = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}
RAZON, APILADO, CIERRE_S, OBJETIVO = Decimal(3), 3, 90, 20
ANTERIORES_OF6A: set = set()  # las vistas cuya pagina es anterior a OF-6a: su F-05, SIN JUZGAR

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
          tpo: window.FLUJO_TPO || null,
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
        elif k in ("unidad", "hasta", "sesion", "capas", "compuesto", "fijo", "modo", "sesiones"):
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


def desequilibrios(niveles: list, s: Decimal, cero_cuenta: bool = False) -> list:
    """[(nivel, compra, venta)] ascendente, al paso s -> [(dc, dv, ac, av)]: la regla de la campana, en Decimal.
    OF-6a (campana 148, F-05): un lado contrario a CERO (o sin celda) no da desequilibrio; `cero_cuenta` es la regla de
    OF-2 (el vecino vacio vale 0), la de una pagina anterior a OF-6a."""
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
        abajo, arriba = V.get(n - s, Decimal(0)), C.get(n + s, Decimal(0))
        dc = n - s >= lo and (abajo > 0 or cero_cuenta and C[n] > 0) and C[n] * N >= media_n and C[n] >= RAZON * abajo
        dv = n + s <= hi and (arriba > 0 or cero_cuenta and V[n] > 0) and V[n] * N >= media_n and V[n] >= RAZON * arriba
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
                try:  # OF-3: y las capas, si la pagina las tiene (una de antes de OF-3 no dice `capas`)
                    # OF-6a: y el arranque del CVD de sesion (sin el, las filas de resumen del contrato dependen
                    # de quien llegue antes; una pagina anterior no lo tiene: undefined !== false)
                    listo = await s.evalua("!!(window.FLUJO_HITOS && window.FLUJO_HITOS.listo && "
                                           "window.FLUJO_HITOS.capas !== false && window.FLUJO_HITOS.arranques !== false)")
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
                elif m == "Network.requestWillBeSent" and "/api" + "/orderflow/" in p["request"]["url"]:
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
    if e.get("modo") == "tpo":  # OF-3: el TPO es otra vista, con su contrato
        juzga_tpo(e, vio, rojos, info)
        return {}
    pref = f"[{e['activo']} {e['marco']} {e['familia']}]"
    pin = vio.get("pintado")
    # (P) la pagina
    if vio["excepciones"]:
        rojos.append(f"(P) {pref} la pagina lanzo {len(vio['excepciones'])} excepcion(es): {vio['excepciones'][0]}")
    if not vio.get("listo") or not pin or not pin.get("velas"):
        rojos.append(f"(P) {pref} la pagina no pinto la vista (listo={vio.get('listo')}, contrato "
                     f"{'sin velas' if pin else 'ausente'}): no hay nada que comparar")
        return {}
    pets = [p for p in vio["peticiones"] if p.get("cuerpo") and RUTA in p["url"]]
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
    # OF-6a (F-05): una pagina anterior (sin `of6a` en su contrato) pinta con la regla de OF-2 y con esa se la juzga
    regla_of2 = not pin.get("of6a")
    if regla_of2:
        ANTERIORES_OF6A.add(vista)
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
                                                  paso, cero_cuenta=regla_of2), strict=True))
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
        # OF-6a: E-04 escribe las operaciones como cualquier cifra (1.2K): se releen a su precision, como las demas
        if res.get("operaciones") is not None and not casa(res["operaciones"], str(v["operaciones"])):
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
    if e.get("capas") or e.get("compuesto") or e.get("fijo"):  # OF-3: las capas de la vista
        juzga_capas(e, vio, q, sv, pin, y, textos, rojos, info, pref)
    return {"e": e, "q": q, "sv": sv}


# --------------------------------------------------------------------------------------------- OF-3 (campana 143)
# LAS CAPAS y EL TPO: lo pintado (FLUJO_PINTADO.capas, FLUJO_TPO) == lo servido por /sesiones, /vwap, /perfil y /tpo,
# y lo pedido == lo que dice el hash. Donde empiezan las sesiones, el estado de cada capa y lo que escribe se cuentan
# AQUI, con su propia aritmetica (no se lee nada de static/). Lo servido contra las celdas lo juzga K108 (d).
RUTAS_OF3 = {"sesiones": "/api" + "/orderflow/sesiones", "vwap": "/api" + "/orderflow/vwap",
             "perfil": "/api" + "/orderflow/perfil", "tpo": "/api" + "/orderflow/tpo"}
PLANTILLAS = {"dia": ("00:00", "24:00"), "asia": ("00:00", "08:00"), "europa": ("07:00", "16:00"),
              "eeuu": ("13:30", "20:00")}
DIA_S, SESIONES_MAXIMO = 86400, 7


def inicio_n(hasta: int, nombre: str, n: int) -> int:
    """El inicio (epoch) de la n-esima sesion hacia atras de las que empiezan ANTES de `hasta`."""
    i = PLANTILLAS.get(nombre, tuple(nombre.split("-")))[0]
    ini = int(i[:2]) * 3600 + int(i[3:]) * 60
    return (hasta - 1 - ini) // DIA_S * DIA_S + ini - (n - 1) * DIA_S


def iso_s(t: int) -> str:
    return datetime.fromtimestamp(t, tz=ZONA).strftime("%Y-%m-%dT%H:%M:%SZ")


def estado_sesion(s: dict) -> tuple:
    """(estado, en curso, faltan, esperados) de una sesion servida: su cobertura hasta su corte."""
    c = s.get("cobertura") or {}
    esp = c.get("minutos_esperados")
    if esp == 0 or (c.get("minutos_con_fila") and c.get("completa")):
        return "completa", bool(s.get("en_curso")), 0, esp
    if not c.get("minutos_con_fila"):
        return "hueco", bool(s.get("en_curso")), esp, esp
    return "incompleta", bool(s.get("en_curso")), esp - c.get("minutos_completos", 0), esp


def estado_rango(sv: dict) -> tuple:
    """El de un rango servido por /perfil: en curso si no ha cerrado (hasta + CIERRE_S despues de as_of)."""
    c = sv.get("cobertura") or {}
    esp = c.get("minutos_esperados")
    if epoch(sv["hasta"]) + CIERRE_S > epoch(sv["as_of"]):
        return "abierta", True, None, esp
    if not c.get("minutos_con_fila"):
        return "hueco", False, esp, esp
    if not c.get("completa"):
        return "incompleta", False, esp - c["minutos_completos"], esp
    return "completa", False, 0, esp


def marca_de(quien: str | None, st: tuple) -> str | None:
    estado, en_curso, faltan, esp = st
    partes = (["en curso"] if en_curso else []) + (["hueco"] if estado == "hueco" else
                                                   [f"faltan {faltan}/{esp}"] if faltan else [])
    return ((quien + " · ") if quien else "") + " · ".join(partes) if partes else None


def qs(p: dict) -> dict:
    return {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(p["url"]).query).items()}


def juzga_perfil(quien: str, r: dict, sv: dict, st: tuple, paso: Decimal, y, textos: dict) -> list:
    """Un perfil pintado (de sesion, compuesto, dinamico o fijo) contra el servido: sus barras, POC/VAH/VAL en su
    fila y con su numero escrito, y la marca de su cobertura."""
    malos = []
    if {D(b["nivel"]): D(b["total"]) for b in r.get("barras") or []} != \
            {D(n["nivel"]): D(n["total"]) for n in sv.get("niveles") or []}:
        malos.append(f"{quien}: barras pintadas != niveles servidos")
    for b in r.get("barras") or []:
        if not b.get("fuera") and (abs(b["y0"] - y(D(b["nivel"]) + paso)) > 1.01 or abs(b["y1"] - y(D(b["nivel"]))) > 1.01):
            malos.append(f"{quien}: la barra de {b['nivel']} no esta en la fila de su precio")
            break
    va = sv.get("value_area") if (sv.get("value_area") or {}).get("val") is not None else None  # /perfil: val null
    for nombre, nivel, donde in (("POC", sv.get("poc"), lambda n: y(n + paso / 2)),
                                 ("VAH", va and va["vah"], lambda n: y(n + paso)), ("VAL", va and va["val"], y)):
        p = r.get(nombre.lower())
        if (D(p["nivel"]) if p else None) != (D(nivel) if nivel is not None else None):
            malos.append(f"{quien}: {nombre} pintado en {p and p['nivel']} y servido {nivel}")
        elif p and abs(p["y"] - 0.5 - round(donde(D(nivel)))) > 1.01:
            malos.append(f"{quien}: la linea del {nombre} {nivel} esta en y={p['y']} y su fila en {donde(D(nivel)):.1f}")
        elif p and p.get("texto") is not None and (p["texto"] != f"{nombre} {nivel}" or not any(
                abs(b - (p["y"] - 1.5)) <= 1.01 for _, b in textos.get(p["texto"], ()))):
            malos.append(f"{quien}: junto a la linea del {nombre} {nivel} escribe «{p['texto']}»")
    marca = marca_de(quien.split(" ")[0] if not quien.startswith("compuesto") else quien, st)
    if r.get("marca") != marca:
        malos.append(f"{quien}: su marca dice «{r.get('marca')}» y su cobertura servida «{marca}»")
    elif marca and not textos.get(marca):
        malos.append(f"{quien}: la marca «{marca}» no esta escrita en el lienzo")
    return malos


def juzga_capas(e: dict, vio: dict, q_fp: dict, sv_fp: dict, pin: dict, y, textos: dict, rojos: list, info: list,
                pref: str) -> None:
    capas = pin.get("capas") or {}
    pide = [c for c in (e.get("capas") or "").split(",") if c]
    paso, ses = D(sv_fp["paso"]), e.get("sesion", "dia")
    fam = FAMILIAS[e["familia"]]
    p_malos, f_malos = [], []

    def pedida(ruta: str, quiero: dict, cual: str) -> dict | None:
        todas = [p for p in vio["peticiones"] if ruta in p["url"] and p.get("cuerpo")]
        cands = [p for p in todas if all((epoch(qs(p).get(k, "1970-01-01T00:00:00Z")) == epoch(v)) if k in ("desde", "hasta")
                                         else qs(p).get(k) == v for k, v in quiero.items())]
        if not cands:
            p_malos.append(f"{cual}: no pide lo que su hash dice ({quiero}); pidio {[qs(p) for p in todas][:1]}")
            return None
        if set(qs(cands[-1]).get("venues", "").split(",")) != fam:
            p_malos.append(f"{cual}: pide {qs(cands[-1]).get('venues')}, no la familia {e['familia']}")
        return cands[-1]["cuerpo"]

    m = MARCOS[e["marco"]] * 60
    tope = -(-inicio_n(epoch(q_fp["hasta"]), ses, SESIONES_MAXIMO) // m) * m  # el primer borde de vela que cabe
    w = {"desde": iso_s(max(epoch(q_fp["desde"]), tope)), "hasta": q_fp["hasta"]}
    base = {"symbol": e["activo"], "sesion": ses}
    if "perfil" in pide:
        sv = pedida(RUTAS_OF3["sesiones"], {**w, **base, "paso": txt(paso), "unidad": e["unidad"]}, "perfil de sesion")
        if sv is not None:
            pintadas = {r["inicio"]: r for r in capas.get("sesiones") or []}
            for s in sv["sesiones"]:
                r = pintadas.pop(s["inicio"], None)
                visible = epoch(s["corte"]) > epoch(pin["velas"][0]["ts"]) and epoch(s["inicio"]) < \
                    epoch(pin["velas"][-1]["ts"]) + m
                if r is None and visible:
                    f_malos.append(f"perfil: la sesion {s['inicio']} se ve y no se pinta")
                elif r is not None:
                    f_malos += juzga_perfil(f"perfil {s['inicio'][5:16]}", r, s, estado_sesion(s), paso, y, textos)
            if pintadas:
                f_malos.append(f"perfil: pinta sesiones que no se sirvieron: {sorted(pintadas)[:2]}")
    if e.get("compuesto"):
        n = int(e["compuesto"])
        sv = pedida(RUTAS_OF3["sesiones"], {"desde": iso_s(inicio_n(epoch(q_fp["hasta"]), ses, n)), "hasta": q_fp["hasta"],
                                            **base, "paso": txt(paso), "unidad": e["unidad"]}, f"compuesto de {n}")
        if sv is not None:
            if len(sv["sesiones"]) != n:
                f_malos.append(f"compuesto: {len(sv['sesiones'])} sesiones servidas y el hash pide {n}")
            if sv.get("compuesto") and not capas.get("compuesto"):
                f_malos.append("compuesto: servido y no pintado")
            elif sv.get("compuesto"):
                c = sv["compuesto"]
                f_malos += juzga_perfil(f"compuesto {c['sesiones']}", capas["compuesto"], c, estado_sesion(c), paso, y,
                                        textos)
    rangos = []
    if e.get("fijo"):
        rangos.append(("fijo", "fijo", e["fijo"].split(",")))
    if "dinamico" in pide:
        rangos.append(("dinamico", "dinámico", [pin["velas"][0]["ts"], iso_s(epoch(pin["velas"][-1]["ts"]) + m)]))
    for nombre, rotulo, (a, b) in rangos:
        sv = pedida(RUTAS_OF3["perfil"], {"desde": a, "hasta": b, "symbol": e["activo"], "paso": txt(paso),
                                          "unidad": e["unidad"]}, nombre)
        if sv is not None and not capas.get(nombre):
            f_malos.append(f"{nombre}: servido y no pintado")
        elif sv is not None:
            f_malos += juzga_perfil(rotulo, capas[nombre], sv, estado_rango(sv), paso, y, textos)
    puntos_ok = 0
    if "vwap" in pide:
        sv = pedida(RUTAS_OF3["vwap"], {**w, **base, "marco": e["marco"]}, "vwap")
        if sv is not None:
            visibles = {epoch(v["ts"]): v for v in pin["velas"]}
            por_inicio = {s["inicio"]: s for s in sv["sesiones"]}
            quiero = {s["inicio"] for s in sv["sesiones"] if any(epoch(p["ts"]) in visibles for p in s["puntos"])}
            if {r["inicio"] for r in capas.get("vwap") or []} != quiero:
                f_malos.append(f"vwap: pinta las sesiones {sorted(r['inicio'] for r in capas.get('vwap') or [])} y "
                               f"las servidas con puntos a la vista son {sorted(quiero)}")
            for r in capas.get("vwap") or []:
                s = por_inicio.get(r["inicio"])
                if s is None:
                    continue
                servidos = {p["ts"]: p for p in s["puntos"] if epoch(p["ts"]) in visibles}
                if {p["ts"] for p in r["puntos"]} != set(servidos):
                    f_malos.append(f"vwap {r['inicio'][5:16]}: {len(r['puntos'])} puntos pintados y {len(servidos)} "
                                   "servidos en las velas que se ven")
                for p in r["puntos"]:
                    sp, v = servidos.get(p["ts"]), visibles.get(epoch(p["ts"]))
                    if sp is None:
                        continue
                    if abs(p["x"] - (v["x0"] + v["ancho"] / 2)) > 1.01:
                        f_malos.append(f"vwap {p['ts'][11:16]}: el punto esta en x={p['x']} y su vela en "
                                       f"{v['x0'] + v['ancho'] / 2}")
                    pares = [("VWAP", p["vwap"], sp["vwap"])] + [
                        (f"banda {signo}{k}", p["bandas"][k][lado], sp["bandas"][k][i])
                        for k in ("1", "2", "3") for i, (signo, lado) in enumerate((("-", "abajo"), ("+", "arriba")))]
                    for nombre, pv, servido in pares:
                        if D(pv["valor"]) != D(servido) or abs(pv["y"] - y(D(servido))) > 1.01:
                            f_malos.append(f"vwap {p['ts'][11:16]}: la {nombre} esta pintada en {pv['valor']} "
                                           f"(y={pv['y']}) y se sirvio {servido} (y={y(D(servido)):.1f})")
                            break
                    else:
                        puntos_ok += 1
                marca = marca_de("VWAP", estado_sesion(s))
                if r.get("marca") != marca:
                    f_malos.append(f"vwap {r['inicio'][5:16]}: su marca dice «{r.get('marca')}» y su cobertura «{marca}»")
    for etiqueta, lista, brazo in (("(P)", p_malos, "las capas piden lo que su hash no dice"),
                                   ("(F)", f_malos, "las capas pintan otra cosa que lo servido")):
        if lista:
            rojos.append(f"{etiqueta} {pref} {brazo}: {lista[0]}" + (f" (y {len(lista) - 1} mas)" if len(lista) > 1 else ""))
    info.append(f"(F) {pref} capas: {len(capas.get('sesiones') or [])} perfil(es) de sesion, compuesto "
                f"{'si' if capas.get('compuesto') else 'no'}, dinamico {'si' if capas.get('dinamico') else 'no'}, fijo "
                f"{'si' if capas.get('fijo') else 'no'}, {puntos_ok} puntos de VWAP con sus 6 bandas en su sitio")


def juzga_tpo(e: dict, vio: dict, rojos: list, info: list) -> None:
    pref = f"[{e['activo']} TPO {e['familia']}]"
    t = vio.get("tpo")
    if vio["excepciones"]:
        rojos.append(f"(P) {pref} la pagina lanzo {len(vio['excepciones'])} excepcion(es): {vio['excepciones'][0]}")
    if not vio.get("listo") or not t or not t.get("sesiones"):
        rojos.append(f"(P) {pref} la pagina no pinto el TPO (listo={vio.get('listo')}, contrato "
                     f"{'sin sesiones' if t else 'ausente'})")
        return
    pets = [p for p in vio["peticiones"] if RUTAS_OF3["tpo"] in p["url"] and p.get("cuerpo")]
    if not pets:
        rojos.append(f"(P) {pref} la pagina no trajo ninguna respuesta buena de {RUTAS_OF3['tpo']}")
        return
    q, sv = qs(pets[-1]), pets[-1]["cuerpo"]
    ses, n = e.get("sesion", "dia"), int(e.get("sesiones", "3"))
    desde = inicio_n(epoch(e["hasta"]), ses, n)
    malos = [f"{k}={q.get(k)} (su hash dice {v})" for k, v in (("symbol", e["activo"]), ("sesion", ses), ("paso", "auto"))
             if q.get(k) != v]
    if epoch(q.get("hasta", "1970-01-01T00:00:00Z")) != epoch(e["hasta"]) or \
            epoch(q.get("desde", "1970-01-01T00:00:00Z")) != desde:
        malos.append(f"desde-hasta {q.get('desde')} - {q.get('hasta')}, y sus {n} sesiones van de {iso_s(desde)} a "
                     f"{e['hasta']}")
    if malos:
        rojos.append(f"(P) {pref} pide lo que su hash no dice: {'; '.join(malos)}")
    if set(q.get("venues", "").split(",")) != FAMILIAS[e["familia"]] or set(t.get("venues") or ()) != FAMILIAS[e["familia"]]:
        rojos.append(f"(V) {pref} pide {q.get('venues')} y pinta {t.get('venues')}: tiene que ser UNA familia, la de su hash")
    esc, p = t["escala"], float(D(sv["paso"]))

    def fila(nivel: str) -> tuple:
        n = float(D(nivel))
        return (esc["medio"] - (n + p - esc["centro"]) / p * esc["fila"], esc["medio"] - (n - esc["centro"]) / p * esc["fila"])

    textos = vio.get("textos") or []
    por_inicio = {s["inicio"]: s for s in sv["sesiones"]}
    f_malos, letras = [], 0
    if t.get("paso") != sv["paso"]:
        f_malos.append(f"pinta al paso {t.get('paso')} y se sirvio {sv['paso']}")
    for r in t["sesiones"]:
        s = por_inicio.get(r["inicio"])
        if s is None:
            f_malos.append(f"pinta la sesion {r['inicio']}, que no se sirvio")
            continue
        quien = f"sesion {r['inicio'][5:16]}"
        marca = marca_de(None, estado_sesion(s))
        if r.get("marca") != marca:
            f_malos.append(f"{quien}: su marca dice «{r.get('marca')}» y su cobertura servida «{marca}»")
        if {D(f["nivel"]): f["letras"] for f in r["filas"]} != {D(x["nivel"]): x["letras"] for x in s["niveles"]}:
            f_malos.append(f"{quien}: las filas pintadas no son los niveles servidos con sus letras")
            continue
        for f in r["filas"]:
            y0, y1 = fila(f["nivel"])
            if abs(f["y0"] - y0) > 1.01 or abs(f["y1"] - y1) > 1.01:
                f_malos.append(f"{quien} nivel {f['nivel']}: su fila {f['y0']}-{f['y1']} no es la de su precio "
                               f"({y0:.1f}-{y1:.1f})")
                break
            if f.get("texto") is None:
                continue
            ym = (f["y0"] + f["y1"]) / 2
            leidas = "".join(x for x, _ in sorted(((tx, a) for tx, a, b in textos if len(tx) == 1 and abs(b - ym) <= 1.01
                                                   and r["x0"] <= a <= r["x1"]), key=lambda z: z[1]))
            if f["texto"] != f["letras"] or leidas != f["letras"]:
                f_malos.append(f"{quien} nivel {f['nivel']}: escribe «{f['texto']}» (el lienzo, «{leidas}») y se "
                               f"sirvio «{f['letras']}»")
                break
            letras += len(leidas)
        for nombre, pinto, servido in (
                ("POC", r.get("poc") and (r["poc"]["nivel"],), (s["poc"],) if s.get("poc") is not None else None),
                ("value area", r.get("va") and (r["va"]["val"], r["va"]["vah"]),
                 s.get("value_area") and (s["value_area"]["val"], s["value_area"]["vah"])),
                ("balance inicial", r.get("ib") and (r["ib"]["lo"], r["ib"]["hi"]),
                 s.get("balance_inicial") and (s["balance_inicial"]["lo"], s["balance_inicial"]["hi"]))):
            if (pinto and tuple(D(x) for x in pinto)) != (servido and tuple(D(x) for x in servido)):
                f_malos.append(f"{quien}: {nombre} pintado {pinto} y servido {servido}")
        if r.get("poc") and (abs(r["poc"]["y0"] - fila(r["poc"]["nivel"])[0]) > 1.01):
            f_malos.append(f"{quien}: el marco del POC no esta en la fila de {r['poc']['nivel']}")
        if [(x["desde"], x["hasta"]) for x in r.get("single") or []] != [(x["desde"], x["hasta"])
                                                                         for x in s["single_prints"]]:
            f_malos.append(f"{quien}: single prints pintados != servidos")
    if f_malos:
        rojos.append(f"(F) {pref} el TPO pintado no es el servido: {f_malos[0]}"
                     + (f" (y {len(f_malos) - 1} mas)" if len(f_malos) > 1 else ""))
    info.append(f"(F) {pref} {len(t['sesiones'])} sesion(es) pintadas, {sum(len(r['filas']) for r in t['sesiones'])} "
                f"filas, {letras} letras releidas del lienzo (paso {sv['paso']}, {e.get('sesion', 'dia')})")


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
    # OF-3: un sujeto ANTERIOR a OF-3 (en produccion, hasta desplegar la campana 143) no sirve las rutas de las capas
    # (404): sus vistas no se miran y se dice SIN JUZGAR; las del footprint se juzgan igual que siempre.
    try:
        de_of3 = hay_pagina(f"{raiz()}{RUTAS_OF3['sesiones']}", cab) != 404
    except OSError as exc:
        print(f"NO MEDIDO (CANAL): no se pudo preguntar por {RUTAS_OF3['sesiones']} · sujeto: {sujeto} · {str(exc)[:120]}")
        return 2
    saltadas = [v for v in VISTAS if not de_of3 and any(k in lee_vista(v) for k in ("capas", "compuesto", "fijo", "modo"))]
    if saltadas:
        info.append(f"OF-3 SIN JUZGAR: el sujeto no sirve {RUTAS_OF3['sesiones']} (404: anterior a OF-3, FALTA "
                    f"DESPLEGAR), asi que sus {len(saltadas)} vistas de capas y de TPO no se miran")
        huella.update(json.dumps(saltadas).encode())
    for vista in VISTAS:
        if vista in saltadas:
            continue
        try:
            vio = asyncio.run(asyncio.wait_for(mira(K, vista, cab), timeout=150))
        except (K.SystemExit2, TimeoutError, OSError) as exc:
            nomed.append(f"(P) {vista}: la sonda no pudo mirar la pagina ({str(exc)[:120]})")
            continue
        x = juzga_vista(vista, vio, rojos, nomed, info)
        pin = vio.get("pintado") or {}
        huella.update(json.dumps([vista, pin.get("velas"), pin.get("venues"), pin.get("umbrales"),
                                  [p["url"].split("?", 1)[-1] for p in vio["peticiones"]],
                                  [p.get("cuerpo") and p["cuerpo"].get("velas") for p in vio["peticiones"]],
                                  # OF-3: las capas y el TPO pintados (sin su numero de fotograma, que depende de
                                  # cuantas veces se repinto) y todo lo servido salvo su as_of
                                  pin.get("capas"), {k: v for k, v in (vio.get("tpo") or {}).items() if k != "cuadro"},
                                  [p.get("cuerpo") and {k: v for k, v in p["cuerpo"].items() if k != "as_of"}
                                   for p in vio["peticiones"]]],
                                 sort_keys=True, default=str).encode())
        if not x:
            continue
        try:
            juzga_celdas(x, rojos, nomed, info)
        except (Canal, IndexError) as exc:
            nomed.append(f"(S) [{vista}] sin canal a las celdas: {str(exc)[:160]}")
    if ANTERIORES_OF6A:
        huella.update(b"anterior a OF-6a")
    f05 = (f"; F-05 SIN JUZGAR (el sujeto es anterior a OF-6a: sus desequilibrios, con la regla de OF-2, en "
           f"{len(ANTERIORES_OF6A)} vistas)") if ANTERIORES_OF6A else ""
    cola = f"{f05} · sujeto: {sujeto} · huella {huella.hexdigest()[:16]}"
    if rojos:
        print(f"ROJO  K109 · lo pintado no es lo servido, o lo servido no es lo de las celdas · {len(rojos)} hallazgo(s)"
              + cola)
    elif nomed:
        print(f"NO MEDIDO: K109 · {nomed[0]}" + cola)
    else:
        print("VERDE  K109 · el footprint pinta lo que sirve, y lo servido es lo de las celdas: niveles, numeros, POC, "
              "value area, desequilibrios, cobertura y una sola familia; " + (
                  f"las capas y el TPO, SIN JUZGAR (el sujeto es anterior a OF-3: {len(saltadas)} vistas sin mirar)"
                  if saltadas else "y las capas (sesiones, compuesto, dinamico, fijo, VWAP y bandas) y el TPO pintan "
                  "lo servido") + cola)
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
