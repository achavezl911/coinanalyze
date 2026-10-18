"""K111 · ayudante: abre el LIBRO en un Chromium de verdad y juzga LO PINTADO contra LO SERVIDO, y lo servido contra
libro_foto (OF-4b, campana 145). No importa nada de app/ ni de static/: lo que conoce cada venue, la suma por familia,
cuantos la conocen, la escala de color, la escalera y su acumulada se recalculan aqui con su propia aritmetica. De
otros checks toma lo puro: la reagregacion de K110-libro.py, la lectura de una cifra escrita de K109-footprint.py y el
Chromium y el cliente CDP de K102-mesa.py.

LO PINTADO se lee por el CONTRATO que declara la pagina (window.LIBRO_PINTADO: el mapa, con su eje y sus celdas; la
escalera, con sus venues) y por el propio DOM de la escalera (cada fila: su texto y sus data-*). Y no se lo cree a pies
juntillas: lee los PIXELES del lienzo del mapa en cada cuadrito de cada celda.

LAS VISTAS, RELATIVAS A AHORA para que no caduquen (las fotos se guardan 3 dias); `hasta` es la hora entera que acabo
hace una hora (K111_HASTA la fija), y se declara en la salida:
  #BTC/perp/hasta=<h>/ver=90                     1 h de perpetuos a una foto cada 10 s; los ultimos 15 min a la vista
  #ETH/okx_swap/1/30m/unidad=usd/hasta=<h>/ver=90  un venue solo, al paso 1 (2x el guardado), en USD
  #BTC/perp/ver=90                               el VIVO: la escalera de los ultimos avisos y el canal por el que van

LOS BRAZOS (cualquiera pone ROJO; uno sin canal es NO MEDIDO y un ROJO de otro manda sobre el):
  (P) la pagina   carga su vista sin excepciones, la pinta, y pide la historia de SU hash: activo, venues, paso, la
                  ventana y el `cada` de la regla (el menor multiplo de 5 s con el que caben 2000 fotos)
  (V) la familia  pide, sirve y pinta los venues de UNA familia (o un venue): nunca dos sumadas
  (S) lo servido  /api/libro/fotos == lo recalculado de libro_foto (lo ya escrito)
  (F) lo pintado  el mapa: sus columnas y su estado (foto, HUECO, sin escribir), cada celda con la suma de los que la
                  conocen y cuantos son, ningun desconocido pintado (ni como cero), el color del percentil de lo
                  visible, los pixeles de sus cuatro cuadritos y la mejor compra y venta de cada instante; la escalera:
                  sus niveles, cantidades, acumuladas (y si son un minimo), las mejores, cuantos conocen cada nivel y el
                  estado de cada venue (un venue sin libro valido se dice y no suma)
  (C) el canal    el que la pagina dice (websocket o sondeo) == el de la red, y la hora del ultimo libro que escribe ==
                  la del ultimo libro que recibio
NO MEDIDO: sin la pagina (404: «FALTA DESPLEGAR») · sin Chromium · sin fotos en la ventana · sin canal a libro_foto.
Uso: K111-libro.py juzga (el entorno lo pone K111-el-libro-pintado-es-el-servido.sh)
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import importlib.util
import io
import json
import math
import netrc
import os
import pathlib
import re
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from decimal import Decimal

AQUI = pathlib.Path(__file__).resolve().parent
H = os.environ.get("K111_HARNESS", "/srv/coinanalyze/harness")
BASE = os.environ.get("K111_BASE", "")  # sin ella: PRODUCCION
DB = os.environ.get("K111_DB", "")  # con K111_BASE: la base de las fotos del banco
HASTA = os.environ.get("K111_HASTA", "")
ESPERA_VIVO_S = float(os.environ.get("K111_ESPERA_VIVO", "25"))
ANCHO, ALTO = 1920, 1080
RUTA_FOTOS, RUTA_ULTIMO, RUTA_VIVO = "/api" + "/libro/fotos", "/api" + "/libro/ultimo", "/api" + "/libro/vivo"
# Lo DECIDIDO por el encargo y por P1/P2 de la campana, escrito aqui y no leido de la pagina:
FAMILIAS = {"perp": ["binance_usdm", "bybit_linear", "okx_swap", "bitget_usdt"],
            "spot": ["binance_spot", "bybit_spot", "okx_spot"], "coinbase": ["coinbase_spot"],
            "deribit": ["deribit_perp"]}
VENUES = ("binance_usdm", "binance_spot", "bybit_linear", "bybit_spot", "okx_swap", "okx_spot", "bitget_usdt",
          "deribit_perp", "coinbase_spot")
PASO_GUARDADO = {"BTC": "10", "ETH": "0.5", "SOL": "0.02"}
VENTANAS = {"30m": 30, "1h": 60, "4h": 240, "12h": 720, "1d": 1440, "3d": 4320}
TOPE_FOTOS, FOTO_S, ESCRITO_S = 2000, 5, 62
FONDO, DESCONOCIDO, HUECO, PENDIENTE = (10, 13, 18), (46, 46, 46), (70, 48, 20), (30, 36, 46)
RAMPA = [(28, 30, 72), (86, 30, 110), (190, 50, 70), (245, 140, 40), (255, 245, 180)]
SUB = [(0, 0), (1, 1), (1, 0), (0, 1)]  # el orden en que se colorean los cuadritos de una celda


def _lut() -> list[tuple]:
    out = []
    for i in range(256):
        x = i / 255 * (len(RAMPA) - 1)
        a = min(len(RAMPA) - 2, math.floor(x))
        f = x - a
        out.append(tuple(math.floor(c + (RAMPA[a + 1][j] - c) * f + 0.5) for j, c in enumerate(RAMPA[a])))
    return out


LUT = _lut()


def _modulo(nombre: str, fichero: str):
    spec = importlib.util.spec_from_file_location(nombre, AQUI / fichero)
    m = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stderr(io.StringIO()):
        spec.loader.exec_module(m)
    return m


class Canal(Exception):
    pass


def epoch_ms(iso: str) -> int:
    return round(datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp() * 1000)


def isoz(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def raiz() -> str:
    if BASE:
        return BASE.rstrip("/")
    env = dict(re.findall(r"^(\w+)=(\S+)", pathlib.Path(f"{H}/env").read_text(), re.M))
    return env["API_PROD"].rstrip("/")


def cabecera() -> dict:
    if BASE:
        return {}
    env = dict(re.findall(r"^(\w+)=(\S+)", pathlib.Path(f"{H}/env").read_text(), re.M))
    n = netrc.netrc(env["NETRC"])
    cred = next((n.authenticators(h) for h in n.hosts if n.authenticators(h)), None)
    if not cred:
        raise Canal("el netrc no da credencial")
    return {"Authorization": "Basic " + base64.b64encode(f"{cred[0]}:{cred[2]}".encode()).decode()}


def estado_http(url: str, cab: dict) -> int:
    ctx = ssl.create_default_context()
    ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE  # el certificado de 140 es propio
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=cab), timeout=30, context=ctx) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


# --------------------------------------------------------------------------------------------- la vista
def lee_vista(h: str) -> dict:
    p = h.lstrip("#").split("/")
    e = {"activo": p[0], "familia": p[1], "paso": PASO_GUARDADO[p[0]], "ventana": "1h", "unidad": "base", "hasta": None,
         "ver": None}
    for x in p[2:]:
        k, _, v = x.partition("=")
        if not v and k in VENTANAS:
            e["ventana"] = k
        elif not v:
            e["paso"] = k
        elif k in ("unidad", "hasta"):
            e[k] = v
        elif k == "ver":
            e["ver"] = int(v)
    e["venues"] = FAMILIAS.get(e["familia"]) or [e["familia"]]
    return e


def cada_para(n: int, s: int) -> int:
    c = FOTO_S
    while n * math.ceil(s / c) > TOPE_FOTOS:
        c += FOTO_S
    return c


def k_de(t, p: float) -> int:
    return round(float(t) / p)


def libro(venue: str, compra: str, venta: str, compras, ventas, paso: str) -> dict:
    """Lo que conoce un libro al paso: la compra desde su nivel mas profundo, la venta hasta el suyo; por encima de la
    mejor compra (y por debajo de la mejor venta) un cero CONOCIDO. `compras`/`ventas`: {desde, cantidades} (foto) o
    [[nivel, cantidad], ...] (aviso); vacio si ni el mejor nivel se conoce entero: entonces, desde el siguiente."""
    p = float(paso)

    def lado(x):
        if not x:
            return None
        if isinstance(x, list):
            return (k_de(x[0][0], p), [float(q) for _, q in x]) if x else None
        return (k_de(x["desde"], p), [float(q) for q in x["cantidades"]]) if x.get("cantidades") else None

    c, v = lado(compras), lado(ventas)
    kc = c[0] if c else math.floor(float(compra) / p + 1e-9)
    kv = v[0] if v else math.floor(float(venta) / p + 1e-9)
    return {"venue": venue, "compra": compra, "venta": venta, "kc": kc, "qc": c[1] if c else [], "kv": kv,
            "qv": v[1] if v else [], "lo": kc - len(c[1]) + 1 if c else kc + 1, "hi": kv + len(v[1]) - 1 if v else kv - 1}


def suma(libros: list[dict], n_familia: int) -> dict | None:
    """Por nivel, la suma de los que lo conocen (en el orden servido) y cuantos son; None si nadie conoce nada."""
    if not libros:
        return None
    lo, hi = min(x["lo"] for x in libros), max(x["hi"] for x in libros)
    if hi < lo:
        return None
    c, v, n = {}, {}, {}
    for x in libros:
        for k in range(max(lo, x["lo"]), x["hi"] + 1):
            c[k] = c.get(k, 0.0) + (0.0 if k > x["kc"] else (x["qc"][x["kc"] - k] if x["kc"] - k < len(x["qc"]) else 0.0))
            v[k] = v.get(k, 0.0) + (0.0 if k < x["kv"] else (x["qv"][k - x["kv"]] if k - x["kv"] < len(x["qv"]) else 0.0))
            n[k] = n.get(k, 0) + 1
    mc = max((x["compra"] for x in libros), key=float)
    mv = min((x["venta"] for x in libros), key=float)
    return {"lo": lo, "hi": hi, "c": c, "v": v, "n": n, "N": n_familia, "venues": [x["venue"] for x in libros],
            "compra": mc, "venta": mv}


def unidad(q: float, k: int, paso: str, u: str) -> float:
    return q * (k + 0.5) * float(paso) if u == "usd" else q


def columnas(d: dict, e: dict, instantes: list[int], as_of: int) -> list[dict]:
    por = {}
    for f in d.get("fotos") or []:
        if f["venue"] in e["venues"]:
            por.setdefault(epoch_ms(f["ts"]), []).append(f)
    out = []
    for t in instantes:
        fs = por.get(t, [])
        estado = "foto" if fs else ("pendiente" if t // 60000 * 60000 + 60000 + ESCRITO_S * 1000 > as_of else "hueco")
        out.append({"ts": t, "estado": estado, "fotos": fs,
                    "suma": suma([libro(f["venue"], f["compra"], f["venta"], f["compras"], f["ventas"], d["paso"])
                                  for f in fs], len(e["venues"]))})
    return out


def percentil(cols: list[dict], paso: str, u: str):
    xs = sorted(q for c in cols if c["estado"] == "foto" and c["suma"]
                for k in c["suma"]["n"] for q in [unidad(c["suma"]["c"][k] + c["suma"]["v"][k], k, paso, u)] if q > 0)

    def indice(q: float) -> int:
        if not q > 0 or not xs:
            return -1
        a, b = 0, len(xs)
        while a < b:
            m = (a + b) // 2
            if xs[m] < q:
                a = m + 1
            else:
                b = m
        return min(255, math.floor(256 * a / len(xs)))

    return indice


def cuadritos(n: int, N: int) -> int:
    return 4 if n >= N else max(1, math.floor(4 * n / N + 0.5))


# --------------------------------------------------------------------------------------------- mirar
COSECHA = r"""
(() => {
  const h = window.LIBRO_HITOS || {};
  if (h.repinta) h.repinta();
  const filas = [...document.querySelectorAll('#esc-filas tbody tr')].map((tr) => ({cls: tr.className,
    d: Object.assign({}, tr.dataset), t: [...tr.children].map((td) => td.textContent)}));
  const ven = [...document.querySelectorAll('#esc-venues tbody tr')].map((tr) => Object.assign({}, tr.dataset,
    {t: tr.children[1] ? tr.children[1].textContent : ''}));
  const canal = document.querySelector('#estado p[data-estado="canal"]');
  return {listo: h.listo, vivo_listo: h.vivo_listo, vista: h.vista, recibidos: h.recibidos, hash: location.hash,
          pintado: window.LIBRO_PINTADO || null, filas, ven, canal: canal ? {texto: canal.textContent,
          dice: canal.dataset.canal} : null};
})()
"""
PIXELES = r"""
((puntos) => {
  const cv = document.getElementById('mapa');
  const img = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height);
  return puntos.map(([x, y]) => { const o = (y * cv.width + x) * 4; return [img.data[o], img.data[o + 1], img.data[o + 2]]; });
})
"""


async def mira(K, vista: str, cab: dict, vivo: bool) -> dict:
    out = {"vista": vista, "excepciones": [], "fotos": [], "ultimo": [], "ws": [], "ws_abiertos": 0}
    with K.Chromium(ANCHO, ALTO) as c:
        req = urllib.request.Request(f"http://127.0.0.1:{c.puerto}/json/new?about:blank", method="PUT")
        with urllib.request.urlopen(req, timeout=10) as r:
            destino = json.load(r)
        async with K.websockets.connect(destino["webSocketDebuggerUrl"], max_size=300 * 1024 * 1024) as ws:
            s = K.Sesion(ws)
            for metodo in ("Page.enable", "Runtime.enable", "Network.enable"):
                await s.pide(metodo)
            await s.pide("Network.setCacheDisabled", cacheDisabled=True)
            await s.pide("Emulation.setDeviceMetricsOverride", width=ANCHO, height=ALTO, deviceScaleFactor=1,
                         mobile=False)
            if cab:
                await s.pide("Network.setExtraHTTPHeaders", headers=cab)
            await s.pide("Page.navigate", url=f"{raiz()}/libro{vista}")
            listo = False
            for _ in range(int((ESPERA_VIVO_S if vivo else 30) * 5)):
                await s.drena(0.2)
                with contextlib.suppress(K.SystemExit2):
                    listo = await s.evalua("!!(window.LIBRO_HITOS && window.LIBRO_HITOS.listo && (" +
                                           ("window.LIBRO_HITOS.vivo_listo" if vivo else "true") + "))")
                if listo:
                    break
            if vivo:  # lo que llegue despues no lo usa la pantalla: se congela, y se cuenta lo que proceso
                await s.drena(2.0)
                with contextlib.suppress(K.SystemExit2):
                    await s.evalua("window.LIBRO_HITOS && window.LIBRO_HITOS.congela && window.LIBRO_HITOS.congela()")
                await s.drena(1.0)
            else:
                await s.drena(0.5)
            out["listo"] = listo
            out.update(await s.evalua(COSECHA))
            # los pixeles del lienzo en los puntos que pedira el juez (se piden despues, con la geometria declarada)
            out["_s"] = s
            porid: dict = {}
            for e in s.eventos:
                p, m = e.get("params", {}), e.get("method")
                if m == "Runtime.exceptionThrown":
                    out["excepciones"].append(json.dumps(p.get("exceptionDetails", {}))[:300])
                elif m == "Network.requestWillBeSent" and "/api" + "/libro/" in p["request"]["url"]:
                    porid[p["requestId"]] = {"url": p["request"]["url"], "estado": None, "t": p.get("timestamp")}
                elif m == "Network.responseReceived" and p.get("requestId") in porid:
                    porid[p["requestId"]]["estado"] = p["response"]["status"]
                elif m == "Network.webSocketCreated" and RUTA_VIVO in p.get("url", ""):
                    out["ws_abiertos"] += 1
                    out.setdefault("ws_ids", {})[p["requestId"]] = {"abierto": True, "apreton": None, "marcos": []}
                elif m == "Network.webSocketHandshakeResponseReceived" and p.get("requestId") in out.get("ws_ids", {}):
                    out["ws_ids"][p["requestId"]]["apreton"] = p.get("response", {}).get("status")
                    out["ws_ids"][p["requestId"]]["t_apreton"] = p.get("timestamp")
                elif m == "Network.webSocketClosed" and p.get("requestId") in out.get("ws_ids", {}):
                    out["ws_ids"][p["requestId"]]["abierto"] = False
                elif m == "Network.webSocketFrameReceived" and p.get("requestId") in out.get("ws_ids", {}):
                    out["ws_ids"][p["requestId"]]["marcos"].append(p.get("response", {}).get("payloadData", ""))
            for rid, x in porid.items():
                if x["estado"] == 200:
                    try:
                        r = await s.pide("Network.getResponseBody", requestId=rid)
                        x["cuerpo"] = json.loads(base64.b64decode(r["body"]) if r.get("base64Encoded") else r["body"])
                    except (K.SystemExit2, ValueError, KeyError):
                        x["cuerpo"] = None
                (out["fotos"] if RUTA_FOTOS in x["url"] else out["ultimo"] if RUTA_ULTIMO in x["url"] else []).append(x)
            out["pixeles"] = {}
            pedir = juez_puntos(out) if not vivo else []
            if pedir:
                vals = await s.evalua(PIXELES + "(" + json.dumps(pedir) + ")")
                out["pixeles"] = {tuple(p): tuple(v) for p, v in zip(pedir, vals, strict=True)}
            del out["_s"]
            await s.cierra()
    return out


# --------------------------------------------------------------------------------------------- el juicio del mapa
def esperado_mapa(vio: dict, e: dict) -> dict | None:
    """Las columnas que tiene que pintar la pagina, recalculadas de lo que recibio: la primera respuesta de la
    historia y, encima, las que la recuperan (el «sin escribir aun» que se vuelve a pedir)."""
    resp = [p for p in vio["fotos"] if p.get("cuerpo")]
    if not resp:
        return None
    d0 = resp[0]["cuerpo"]
    q = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(resp[0]["url"]).query).items()}
    c = int(q.get("cada", "0") or 0)
    a, b = epoch_ms(q["desde"]), epoch_ms(q["hasta"])
    inst = list(range(-(-a // (c * 1000)) * c * 1000, b, c * 1000)) if c else []
    cols = columnas(d0, e, inst, epoch_ms(d0["as_of"]))
    for p in resp[1:]:
        d = p["cuerpo"]
        nuevas = {x["ts"]: x for x in columnas(d, e, [x["ts"] for x in cols if x["estado"] == "pendiente"],
                                               epoch_ms(d["as_of"]))}
        cols = [nuevas.get(x["ts"], x) if x["estado"] == "pendiente" else x for x in cols]
    return {"q": q, "d": d0, "cols": cols}


def juez_puntos(vio: dict) -> list[list[int]]:
    """Los pixeles que hay que leer: los cuatro cuadritos de cada celda visible (y tres puntos de cada columna HUECO o
    sin escribir), lejos de las lineas del precio."""
    m = ((vio.get("pintado") or {}).get("mapa")) or {}
    eje = m.get("eje")
    if not eje:
        return []
    out = []
    for c in m.get("columnas") or []:
        x0, w, fh = c["x0"], eje["columna"], eje["fila"]
        if x0 < 0 or x0 + w > eje["ancho"]:
            continue
        for k in range(eje["lo"], eje["hi"] + 1):
            y0 = (eje["hi"] - k) * fh
            for sx, sy in SUB:
                out.append([math.floor(x0 + (sx + 0.5) * w / 2), math.floor(y0 + (sy + 0.5) * fh / 2)])
    return out


def juzga_mapa(vio: dict, e: dict, esp: dict, rojos: list, info: list, pref: str) -> None:
    m = (vio.get("pintado") or {}).get("mapa") or {}
    eje, pintadas = m.get("eje"), m.get("columnas") or []
    if not eje or not pintadas:
        rojos.append(f"(F) {pref} el mapa no declara lo que pinto (sin eje o sin columnas)")
        return
    cols = esp["cols"]
    por_ts = {c["ts"]: (j, c) for j, c in enumerate(cols)}
    malos, pix_ok, pix_saltados, celdas = [], 0, 0, 0
    j0, j1 = max(0, math.floor(eje["fin"] - eje["ver"] + 1)), min(len(cols) - 1, math.ceil(eje["fin"]))
    indice = percentil(cols[j0:j1 + 1], esp["d"]["paso"], e["unidad"])
    px = vio.get("pixeles") or {}
    vistas_ts = [epoch_ms(c["ts"]) for c in pintadas if c.get("origen") != "vivo"]
    if vistas_ts != [c["ts"] for c in cols[j0:j1 + 1]][:len(vistas_ts)]:
        malos.append(f"columnas pintadas {len(vistas_ts)} ({isoz(vistas_ts[0]) if vistas_ts else '-'} ...) y las "
                     f"de la ventana a la vista son {j1 - j0 + 1} ({isoz(cols[j0]['ts'])} ...)")
    paso, fh, w = esp["d"]["paso"], eje["fila"], eje["columna"]
    # las lineas del precio: por los centros de las columnas con foto, de una a la siguiente (un hueco las corta); un
    # pixel a menos de 4 px de una de ellas (su halo es de 4 px) no se lee
    tramos = []
    for campo in ("y_compra", "y_venta"):
        ant = None
        for pc in pintadas:
            y_ = pc.get(campo)
            p_ = (pc["x0"] + w / 2, y_) if y_ is not None and pc["estado"] == "foto" else None
            if ant and p_:
                tramos.append((ant, p_))
            ant = p_

    def bajo_el_precio(x_: float, y_: float) -> bool:
        for (xa, ya), (xb, yb) in tramos:
            if xa - 4 <= x_ <= xb + 4:
                yl = ya + (yb - ya) * min(1.0, max(0.0, (x_ - xa) / (xb - xa)))
                if abs(y_ - yl) <= 4 + abs(yb - ya) * 4 / max(1e-9, xb - xa):
                    return True
        return False

    for pc in pintadas:
        if pc.get("origen") == "vivo":
            continue
        t = epoch_ms(pc["ts"])
        if t not in por_ts:
            malos.append(f"columna {pc['ts']} pintada y fuera de la ventana")
            continue
        j, c = por_ts[t]
        if abs(pc["x0"] - (eje["ancho"] - (eje["fin"] - j + 1) * w)) > 0.01:
            malos.append(f"columna {pc['ts']}: x0 {pc['x0']:.2f} no es la de su instante")
        if pc["estado"] != c["estado"]:
            malos.append(f"columna {pc['ts']}: pintada {pc['estado']} y lo servido dice {c['estado']}")
            continue
        s = c["suma"]
        if c["estado"] == "foto" and s:
            if sorted(pc["venues"]) != sorted(s["venues"]):
                malos.append(f"columna {pc['ts']}: venues con foto pintados {pc['venues']} y servidos {s['venues']}")
            if (pc["mejor_compra"], pc["mejor_venta"]) != (s["compra"], s["venta"]):
                malos.append(f"columna {pc['ts']}: mejores pintadas {pc['mejor_compra']}/{pc['mejor_venta']} y servidas "
                             f"{s['compra']}/{s['venta']}")
            for campo, precio in (("y_compra", s["compra"]), ("y_venta", s["venta"])):
                yy = (eje["hi"] + 1 - float(precio) / float(paso)) * fh
                if abs((pc.get(campo) or -1e9) - yy) > 1.01:
                    malos.append(f"columna {pc['ts']}: la linea de {campo[2:]} esta en y={pc.get(campo)} y su precio en {yy:.1f}")
        decl = {x[0]: x for x in pc.get("celdas") or []}
        for k in range(eje["lo"], eje["hi"] + 1):
            conocida = bool(c["estado"] == "foto" and s and k in s["n"])
            if conocida != (k in decl):
                malos.append(f"columna {pc['ts']} nivel {k * float(paso):g}: "
                             + ("conocido y no pintado" if conocida else "DESCONOCIDO pintado como conocido"))
                continue
            esperado_q = None
            if conocida:
                celdas += 1
                cc, vv, n = s["c"][k], s["v"][k], s["n"][k]
                _, pc_c, pc_v, pc_n, pc_i = decl[k]
                if abs(pc_c - cc) > 1e-9 * max(1, abs(cc)) or abs(pc_v - vv) > 1e-9 * max(1, abs(vv)) or pc_n != n:
                    malos.append(f"columna {pc['ts']} nivel {k * float(paso):g}: pinta compra {pc_c} venta {pc_v} "
                                 f"({pc_n} de {s['N']}) y lo servido da {cc} / {vv} ({n} de {s['N']})")
                ix = indice(unidad(cc + vv, k, paso, e["unidad"]))
                if abs(pc_i - ix) > 1:
                    malos.append(f"columna {pc['ts']} nivel {k * float(paso):g}: color {pc_i} y el percentil de lo "
                                 f"visible da {ix}")
                esperado_q = (ix, cuadritos(n, s["N"]))
            # los pixeles de sus cuatro cuadritos
            y0 = (eje["hi"] - k) * fh
            for q_, (sx, sy) in enumerate(SUB):
                p = (math.floor(pc["x0"] + (sx + 0.5) * w / 2), math.floor(y0 + (sy + 0.5) * fh / 2))
                if p not in px:
                    continue
                if bajo_el_precio(p[0] + 0.5, p[1] + 0.5) or p[1] >= eje["alto"]:
                    pix_saltados += 1
                    continue
                v = px[p]
                if c["estado"] == "hueco":
                    bien = [HUECO]
                elif c["estado"] == "pendiente":
                    bien = [PENDIENTE]
                elif esperado_q is None:
                    bien = [DESCONOCIDO]
                else:
                    ix, sub = esperado_q
                    if q_ >= sub:
                        bien = [DESCONOCIDO]
                    elif ix < 0:
                        bien = [FONDO]
                    else:
                        bien = [LUT[i] for i in (ix - 1, ix, ix + 1) if 0 <= i <= 255]
                if any(all(abs(a - b) <= 1 for a, b in zip(v, x, strict=True)) for x in bien):
                    pix_ok += 1
                else:
                    malos.append(f"columna {pc['ts']} nivel {k * float(paso):g} cuadrito {q_}: el pixel es {v} y tenia "
                                 f"que ser {bien[len(bien) // 2]} ({'HUECO' if c['estado'] == 'hueco' else 'sin escribir' if c['estado'] == 'pendiente' else 'DESCONOCIDO' if esperado_q is None or q_ >= esperado_q[1] else 'su color'})")
    if malos:
        rojos.append(f"(F) {pref} el mapa no pinta lo servido: {malos[0]}" + (f" (y {len(malos) - 1} mas)" if len(malos) > 1 else ""))
    estados = {}
    for pc in pintadas:
        estados[pc["estado"]] = estados.get(pc["estado"], 0) + 1
    info.append(f"(F) {pref} mapa: {len(pintadas)} columnas a la vista ({', '.join(f'{k} {v}' for k, v in sorted(estados.items()))}), "
                f"{celdas} celdas conocidas, {pix_ok} pixeles leidos del lienzo y en su color ({pix_saltados} bajo el precio)")


# --------------------------------------------------------------------------------------------- la escalera
def escalera(libros: list[dict], N: int, paso: str, u: str) -> list[dict]:
    s = suma(libros, N)
    if not s:
        return []
    p = float(paso)
    kb, ka = math.floor(float(s["compra"]) / p + 1e-9), math.floor(float(s["venta"]) / p + 1e-9)
    filas = {k: {"k": k, "n": s["n"].get(k, 0), "c": unidad(s["c"][k], k, paso, u) if k in s["n"] else None,
                 "v": unidad(s["v"][k], k, paso, u) if k in s["n"] else None, "mc": k == kb, "mv": k == ka,
                 "ac": None, "av": None, "pc": False, "pv": False} for k in range(s["lo"], s["hi"] + 1)}
    for lado, k0, paso_k in (("c", kb, -1), ("v", ka, 1)):
        acc, parcial, k = 0.0, False, k0
        while k in filas and filas[k]["n"]:
            acc += filas[k][lado]
            parcial = parcial or filas[k]["n"] < N
            filas[k]["a" + lado], filas[k]["p" + lado] = acc, parcial
            k += paso_k
    return [{"k": s["hi"] + 1, "n": 0}] + [filas[k] for k in range(s["hi"], s["lo"] - 1, -1)] + [{"k": s["lo"] - 1, "n": 0}]


def juzga_escalera(vio: dict, e: dict, libros_por_venue: dict, estados: dict, rojos: list, info: list, pref: str,
                   casa) -> None:
    """La escalera pintada (el DOM) contra la recalculada de los libros que la pagina tenia (los vivos)."""
    vivos = [libros_por_venue[v] for v in e["venues"] if estados.get(v) == "vivo"]
    esp = escalera(vivos, len(e["venues"]), e["paso"], e["unidad"])
    filas, malos = vio.get("filas") or [], []
    ven = {x.get("venue"): x for x in vio.get("ven") or []}
    for v in e["venues"]:
        if (ven.get(v) or {}).get("estado") != estados.get(v):
            malos.append(f"venue {v}: la escalera dice {(ven.get(v) or {}).get('estado')} y su ultimo mensaje "
                         f"{estados.get(v)}")
    if len(filas) != len(esp):
        malos.append(f"{len(filas)} filas pintadas y {len(esp)} recalculadas")
    for f, x in zip(filas, esp, strict=False):
        d, t = f["d"], f["t"]
        if int(d.get("k", "0")) != x["k"] or int(d.get("n", "-1")) != x["n"]:
            malos.append(f"fila {d.get('nivel')}: nivel/conocen {d.get('k')}/{d.get('n')} y recalculados {x['k']}/{x['n']}")
            continue
        if not x["n"]:
            if "desconocido" not in f["cls"] or "desconocido" not in " ".join(t) or d.get("compra") is not None:
                malos.append(f"fila {d.get('nivel')}: DESCONOCIDO y se pinta {t}")
            continue
        for campo, clave, col in (("compra", "c", 1), ("venta", "v", 3)):
            val = float(d.get(campo, "nan"))
            if not abs(val - x[clave]) <= 1e-9 * max(1.0, abs(x[clave])):
                malos.append(f"fila {d.get('nivel')}: {campo} pintada {d.get(campo)} y recalculada {x[clave]}")
            elif not casa(t[col], repr(x[clave])):
                malos.append(f"fila {d.get('nivel')}: escribe {campo} «{t[col]}» y vale {x[clave]}")
        for campo, clave, parcial, col in (("acumCompra", "ac", "pc", 0), ("acumVenta", "av", "pv", 4)):
            if (d.get(campo) is None) != (x[clave] is None):
                malos.append(f"fila {d.get('nivel')}: acumulada {campo} pintada {d.get(campo)} y recalculada {x[clave]}")
            elif x[clave] is not None and (not abs(float(d[campo]) - x[clave]) <= 1e-9 * max(1.0, abs(x[clave]))
                                           or t[col].startswith("≥") != x[parcial] or not casa(t[col].lstrip("≥"), repr(x[clave]))):
                malos.append(f"fila {d.get('nivel')}: acumulada «{t[col]}» y recalculada {'≥' if x[parcial] else ''}{x[clave]}")
        if ("mejor-compra" in f["cls"]) != x["mc"] or ("mejor-venta" in f["cls"]) != x["mv"]:
            malos.append(f"fila {d.get('nivel')}: marcas {f['cls']} y la mejor compra/venta recalculada {x['mc']}/{x['mv']}")
        if t[5] != f"{x['n']}/{len(e['venues'])}":
            malos.append(f"fila {d.get('nivel')}: escribe conocen «{t[5]}» y son {x['n']}/{len(e['venues'])}")
    if malos:
        rojos.append(f"(F) {pref} la escalera no pinta lo servido: {malos[0]}" + (f" (y {len(malos) - 1} mas)" if len(malos) > 1 else ""))
    info.append(f"(F) {pref} escalera: {len(filas)} filas, {sum(1 for x in esp if x['n'])} niveles conocidos, "
                f"{len(vivos)} de {len(e['venues'])} venues sumando ({', '.join(f'{v} {estados.get(v)}' for v in e['venues'])})")


# --------------------------------------------------------------------------------------------- una vista
def juzga_vista(vista: str, vio: dict, rojos: list, nomed: list, info: list, casa, K110) -> dict | None:
    e = lee_vista(vista)
    vivo = not e["hasta"]
    pref = f"[{e['activo']} {e['familia']}{' vivo' if vivo else ''}]"
    pin = vio.get("pintado") or {}
    if vio["excepciones"]:
        rojos.append(f"(P) {pref} la pagina lanzo {len(vio['excepciones'])} excepcion(es): {vio['excepciones'][0]}")
    if not vio.get("listo") or not pin.get("mapa"):
        rojos.append(f"(P) {pref} la pagina no pinto su vista (listo={vio.get('listo')}, contrato "
                     f"{'sin mapa' if pin else 'ausente'})")
        return None
    esp = esperado_mapa(vio, e)
    if esp is None:
        rojos.append(f"(P) {pref} la pagina no trajo ninguna respuesta buena de {RUTA_FOTOS}")
        return None
    q = esp["q"]
    s = VENTANAS[e["ventana"]] * 60
    cada = cada_para(len(e["venues"]), s)
    hasta = epoch_ms(e["hasta"]) if e["hasta"] else None
    malos = []
    for k, v in (("symbol", e["activo"]), ("paso", e["paso"]), ("cada", str(cada))):
        if q.get(k) != v:
            malos.append(f"{k}={q.get(k)} (su hash dice {v})")
    if hasta is not None and (epoch_ms(q["hasta"]) != hasta or epoch_ms(q["desde"]) != hasta - s * 1000):
        malos.append(f"desde-hasta {q.get('desde')} - {q.get('hasta')} y su hash pide {e['ventana']} hasta {e['hasta']}")
    if malos:
        rojos.append(f"(P) {pref} pide lo que su hash no dice: {'; '.join(malos)}")
    fam = sorted(e["venues"])
    pedidos, servidos, pintados = sorted(q.get("venues", "").split(",")), sorted(esp["d"].get("venues") or []), \
        sorted(pin["mapa"].get("venues") or [])
    if not (pedidos == servidos == pintados == fam):
        otras = [f for f, vs in FAMILIAS.items() if set(vs) & set(pedidos)]
        rojos.append(f"(V) {pref} pide {pedidos} ({len(otras)} familia(s): {', '.join(otras)}), sirve {servidos} y pinta "
                     f"{pintados}: tiene que ser UNA, la de su hash")
    if vivo:  # sus columnas vivas salen de los avisos, no de lo servido: el mapa del vivo no se juzga aqui
        info.append(f"(F) {pref} el mapa del vivo no se juzga celda a celda (sus columnas nuevas salen de los avisos); "
                    "si su escalera y su canal")
    else:
        juzga_mapa(vio, e, esp, rojos, info, pref)
    # LA ESCALERA: en la vista fija, la de su ultima foto; en el vivo, la de los mensajes que proceso
    if not vivo:
        col = next((c for c in reversed(esp["cols"]) if c["estado"] == "foto"), None)
        if col is not None:
            libros = {f["venue"]: libro(f["venue"], f["compra"], f["venta"], f["compras"], f["ventas"], esp["d"]["paso"])
                      for f in col["fotos"]}
            estados = {v: "vivo" if v in libros else "sin_dato" for v in e["venues"]}
            juzga_escalera(vio, e, libros, estados, rojos, info, pref, casa)
    else:
        juzga_vivo(vio, e, rojos, nomed, info, pref, casa)
    return {"e": e, "q": q, "d": esp["d"], "K110": K110}


def juzga_vivo(vio: dict, e: dict, rojos: list, nomed: list, info: list, pref: str, casa) -> None:
    """(C) el canal que dice == el de la red; y la escalera == la de los mensajes que la pagina proceso: los primeros N
    marcos del websocket o las primeras N respuestas del sondeo (N lo cuenta la propia pagina al congelarse)."""
    rec = vio.get("recibidos") or {}
    dice = (vio.get("canal") or {}).get("dice")
    abiertos = [x for x in (vio.get("ws_ids") or {}).values() if x["abierto"] and x["apreton"] == 101 and x["marcos"]]
    sondeos = [x for x in vio.get("ultimo") or []]
    mensajes: list[dict] = []
    if dice == "websocket":
        if len(abiertos) != 1:
            rojos.append(f"(C) {pref} dice que va por WEBSOCKET y en la red hay {len(abiertos)} websocket(s) abiertos con "
                         f"mensajes ({len(sondeos)} peticiones de sondeo)")
            return
        t_ws = abiertos[0].get("t_apreton") or 0
        despues = sum(1 for x in sondeos if (x.get("t") or 0) > t_ws + 1.5)
        if despues > 1:  # la que estaba en vuelo al abrir el websocket se tolera
            rojos.append(f"(C) {pref} dice que va por WEBSOCKET y siguio sondeando: {despues} peticiones a {RUTA_ULTIMO} "
                         "despues de abrirse")
        for crudo in abiertos[0]["marcos"][: rec.get("websocket", 0)]:
            with contextlib.suppress(ValueError):
                mensajes.append(json.loads(crudo))
    elif dice == "sondeo":
        if abiertos:
            rojos.append(f"(C) {pref} dice que va por SONDEO y hay un websocket abierto con mensajes")
            return
        if len(sondeos) < 3:
            rojos.append(f"(C) {pref} dice que va por SONDEO y solo hubo {len(sondeos)} peticion(es) a {RUTA_ULTIMO}")
            return
        for x in sondeos[: rec.get("sondeo", 0)]:
            mensajes += (x.get("cuerpo") or {}).get("libros") or []
    else:
        rojos.append(f"(C) {pref} no dice por que canal va el vivo ({dice!r})")
        return
    ultimo: dict = {}
    for m in mensajes:
        if m.get("tipo") in ("libro", "sin_libro", "sin_dato") and m.get("venue") in e["venues"]:
            ultimo[m["venue"]] = m
    if not ultimo:
        nomed.append(f"(C) {pref} el vivo no trajo ningun mensaje en {ESPERA_VIVO_S:.0f} s: no hay escalera que juzgar")
        return
    pv = {x["venue"]: x for x in ((vio.get("pintado") or {}).get("escalera") or {}).get("venues") or []}
    estados, libros = {}, {}
    for v in e["venues"]:
        m = ultimo.get(v)
        tipo = (m or {}).get("tipo", "sin_dato")
        estados[v] = {"libro": "vivo", "sin_libro": "sin_libro"}.get(tipo, "sin_dato")
        if pv.get(v, {}).get("estado") == "rancio" and tipo == "libro":
            estados[v] = "rancio"  # su edad no se juzga aqui: no suma, y se dice
        if tipo == "libro":
            if pv.get(v, {}).get("emitido_ms") != m.get("emitido_ms"):
                rojos.append(f"(F) {pref} {v}: la escalera usa el aviso emitido {pv.get(v, {}).get('emitido_ms')} y el "
                             f"ultimo que proceso es {m.get('emitido_ms')}")
            libros[v] = libro(v, m["compra"], m["venta"], m["compras"], m["ventas"], e["paso"])
    juzga_escalera(vio, e, libros, estados, rojos, info, pref, casa)
    hora = re.search(r"ltimo libro (\d\d:\d\d:\d\d\.\d{3})Z", (vio.get("canal") or {}).get("texto") or "")
    mx = max((m["ts_libro_ms"] for m in ultimo.values() if m.get("tipo") == "libro"), default=None)
    if mx is not None and (not hora or hora.group(1) != datetime.fromtimestamp(mx / 1000, UTC).strftime("%H:%M:%S.%f")[:12]):
        rojos.append(f"(C) {pref} escribe «{(vio.get('canal') or {}).get('texto', '')[:80]}» y el ultimo libro recibido es de "
                     f"{datetime.fromtimestamp(mx / 1000, UTC).strftime('%H:%M:%S.%f')[:12]}Z")
    info.append(f"(C) {pref} vivo por {dice}: {rec.get('websocket', 0)} marcos y {rec.get('sondeo', 0)} respuestas de sondeo "
                f"procesadas; ultimo libro {datetime.fromtimestamp(mx / 1000, UTC).strftime('%H:%M:%S.%f')[:12] if mx else '-'}Z")


def juzga_servido(x: dict, rojos: list, nomed: list, info: list) -> None:
    """(S) lo servido == lo recalculado de libro_foto para la peticion de la pagina (solo lo ya escrito)."""
    e, q, d, K110 = x["e"], x["q"], x["d"], x["K110"]
    pref = f"[{e['activo']} {e['familia']}]"
    as_of = epoch_ms(d["as_of"])
    escrito = (as_of - ESCRITO_S * 1000) // 60000 * 60000  # lo anterior a este minuto ya estaba escrito al servirse
    hasta = min(epoch_ms(q["hasta"]), escrito)
    vs = ",".join(f"'{v}'" for v in sorted(set(q["venues"].split(","))) if re.fullmatch(r"[a-z_]+", v))
    filas = sql(f"""SELECT to_char(ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'), venue,
                           to_char(ts_libro AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'), compra, venta, paso,
                           compra_nivel, array_to_string(compras, ','), venta_nivel, array_to_string(ventas, ','),
                           alcance_compra, alcance_venta
                      FROM libro_foto WHERE symbol = '{e['activo']}' AND venue IN ({vs}) AND ts >= '{q['desde']}'
                       AND ts < '{isoz(hasta)}' AND extract(epoch FROM ts)::bigint % {int(q['cada'])} = 0
                     ORDER BY ts, venue""")
    paso = Decimal(q["paso"])
    mias = []
    for ts, venue, ts_libro, compra, venta, fino, cn, cs, vn, vv, ac, av in filas:
        c = K110.reagrega(Decimal(cn), [Decimal(z) for z in cs.split(",")], Decimal(fino), paso, True)
        v = K110.reagrega(Decimal(vn), [Decimal(z) for z in vv.split(",")], Decimal(fino), paso, False)
        t = K110.texto
        mias.append({"ts": ts, "venue": venue, "ts_libro": ts_libro, "compra": t(Decimal(compra)),
                     "venta": t(Decimal(venta)),
                     "compras": {"desde": t(c[0]), "cantidades": [t(z) for z in c[1]]} if c else None,
                     "ventas": {"desde": t(v[0]), "cantidades": [t(z) for z in v[1]]} if v else None,
                     "alcance": {"compra": t(Decimal(ac)), "venta": t(Decimal(av))}})
    servidas = [{k: f.get(k) for k in mias[0]} for f in d.get("fotos") or [] if epoch_ms(f["ts"]) < hasta] if mias else \
        [f for f in d.get("fotos") or [] if epoch_ms(f["ts"]) < hasta]
    if not mias and not servidas:
        nomed.append(f"(S) {pref} sin fotos en la ventana {q['desde']} - {q['hasta']}: nada que comparar")
        return
    if len(servidas) != len(mias):
        rojos.append(f"(S) {pref} lo servido no es libro_foto: {len(servidas)} fotos servidas y {len(mias)} guardadas "
                     f"(hasta {isoz(hasta)})")
        return
    for s_, m_ in zip(servidas, mias, strict=True):
        if s_ != m_:
            campo = next(k for k in m_ if s_.get(k) != m_[k])
            rojos.append(f"(S) {pref} lo servido no es libro_foto: foto {m_['ts']} {m_['venue']}: {campo} servido "
                         f"{str(s_.get(campo))[:70]} y guardado {str(m_[campo])[:70]}")
            return
    info.append(f"(S) {pref} {len(mias)} fotos servidas == libro_foto ({q['desde']} - {isoz(hasta)}, paso {q['paso']}, "
                f"cada {q['cada']} s)")


def juzga() -> int:
    K = _modulo("k102_mesa", "K102-mesa.py")
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            K.binario_chromium()
    except SystemExit:
        print("NO MEDIDO: sin Chromium (o sin websockets) en 143 no se puede mirar la pagina")
        return 2
    casa = _modulo("k109", "K109-footprint.py").casa
    K110 = _modulo("k110", "K110-libro.py")
    sujeto = f"el ARBOL servido en {BASE} (fotos de {DB})" if BASE else "PRODUCCION (fotos por bin/prodsql)"
    ahora = datetime.now(UTC)
    hasta = datetime.fromisoformat(HASTA.replace("Z", "+00:00")) if HASTA else \
        ahora.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    h = hasta.strftime("%Y-%m-%dT%H:%M:%SZ")
    vistas = [f"#BTC/perp/hasta={h}/ver=90", f"#ETH/okx_swap/1/30m/unidad=usd/hasta={h}/ver=90", "#BTC/perp/ver=90"]
    declara = f"ventana del pasado hasta {h} ({'fijada por K111_HASTA' if HASTA else 'la hora entera que acabo hace una hora'})"
    # LO DECIDIBLE ANTES QUE LO QUE FALTA: si la ventana no tiene fotos, no hay sujeto (y no se abre Chromium)
    try:
        n = sql(f"SELECT count(*) FROM libro_foto WHERE ts >= '{(hasta - timedelta(hours=1)).isoformat()}' "
                f"AND ts < '{hasta.isoformat()}' AND symbol IN ('BTC', 'ETH')")
    except Canal as exc:
        print(f"NO MEDIDO (CANAL): no se pudo contar libro_foto · sujeto: {sujeto} · {str(exc)[:160]}")
        return 2
    if not n or not n[0] or n[0][0] in ("", "0"):
        print(f"NO MEDIDO: sin fotos en la ventana · {declara} · sujeto: {sujeto}: libro_foto no tiene ni una de BTC o "
              "ETH (las fotos se guardan 3 dias)")
        return 2
    try:
        cab = cabecera()
        estado_pagina = estado_http(f"{raiz()}/libro", cab)
    except (Canal, OSError, KeyError) as exc:
        print(f"NO MEDIDO (CANAL): no se pudo preguntar por la pagina · sujeto: {sujeto} · {str(exc)[:160]}")
        return 2
    if estado_pagina == 404:
        print(f"NO MEDIDO: FALTA DESPLEGAR · {sujeto} no sirve /libro (404). El codigo no esta mal: no esta desplegado")
        return 2
    if estado_pagina != 200:
        print(f"NO MEDIDO (CANAL): /libro contesto {estado_pagina} · sujeto: {sujeto}")
        return 2
    rojos: list[str] = []
    nomed: list[str] = []
    info: list[str] = [declara]
    huella = hashlib.sha256()
    for vista in vistas:
        try:
            vio = asyncio.run(asyncio.wait_for(mira(K, vista, cab, "hasta=" not in vista), timeout=180))
        except (K.SystemExit2, TimeoutError, OSError) as exc:
            nomed.append(f"(P) {vista}: la sonda no pudo mirar la pagina ({str(exc)[:120]})")
            continue
        x = juzga_vista(vista, vio, rojos, nomed, info, casa, K110)
        # LA HUELLA: lo pintado y lo servido de las vistas del pasado (reproducibles); del vivo, solo por que canal
        # dice ir y el estado de cada venue (sus cantidades cambian con cada aviso)
        pin = vio.get("pintado") or {}
        if "hasta=" in vista:
            mapa = {k: v for k, v in (pin.get("mapa") or {}).items() if k != "cuadro"}
            esc = {k: v for k, v in (pin.get("escalera") or {}).items() if k not in ("cuadro", "ahora_ms")}
            huella.update(json.dumps([vista, mapa, esc, vio.get("filas"), [p["url"].split("?", 1)[-1] for p in vio["fotos"]],
                                      [p.get("cuerpo") and {k: v for k, v in p["cuerpo"].items() if k != "as_of"}
                                       for p in vio["fotos"]]], sort_keys=True, default=str).encode())
        else:
            huella.update(json.dumps([vista, (vio.get("canal") or {}).get("dice"),
                                      [(x.get("venue"), x.get("estado")) for x in vio.get("ven") or []]]).encode())
        if not x or "hasta=" not in vista:
            continue
        try:
            juzga_servido(x, rojos, nomed, info)
        except (Canal, IndexError) as exc:
            nomed.append(f"(S) [{vista}] sin canal a libro_foto: {str(exc)[:160]}")
    cola = f" · sujeto: {sujeto} · {declara} · huella {huella.hexdigest()[:16]}"
    if rojos:
        print(f"ROJO  K111 · el libro pintado no es el servido, o lo servido no es libro_foto · {len(rojos)} hallazgo(s)" + cola)
    elif nomed:
        print(f"NO MEDIDO: K111 · {nomed[0]}" + cola)
    else:
        print("VERDE  K111 · el libro pinta lo que sirve y lo servido es libro_foto: el mapa (cada celda, cuantos la "
              "conocen, lo desconocido, los huecos, el color y sus pixeles), la escalera (niveles, cantidades, "
              "acumuladas, mejores, venues sin libro) y el canal del vivo" + cola)
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
        print(f"NO MEDIDO: la sonda de K111 fallo y no juzgo nada ({type(exc).__name__}: {str(exc)[:160]})")
        sys.exit(2)
