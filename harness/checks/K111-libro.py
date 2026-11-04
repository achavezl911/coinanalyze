"""K111 · ayudante: abre el LIBRO en un Chromium de verdad y juzga LO PINTADO contra LO SERVIDO, y lo servido contra
libro_foto (OF-4b, campana 145). No importa nada de app/ ni de static/: lo que conoce cada venue, la suma por familia,
cuantos la conocen, la escala de color, la escalera y su acumulada se recalculan aqui con su propia aritmetica. De
otros checks toma lo puro: la reagregacion de K110-libro.py, la lectura de una cifra escrita de K109-footprint.py y el
Chromium y el cliente CDP de K102-mesa.py.

LO PINTADO se lee por el CONTRATO que declara la pagina (window.LIBRO_PINTADO: el mapa, con su eje y sus celdas; la
escalera, con sus venues) y por el propio DOM de la escalera (cada fila: su texto y sus data-*). Y no se lo cree a pies
juntillas: lee los PIXELES del lienzo del mapa en cada cuadrito de cada celda.

LAS VISTAS, RELATIVAS A AHORA para que no caduquen (las fotos se guardan 3 dias); `hasta` es la hora entera que acabo
hace una hora (K111_HASTA la fija; K111_HASTA_R1, la de las dos de R1), y se declara en la salida. En 1920x1080:
  #BTC/perp/hasta=<h>/ver=90                     1 h de perpetuos a una foto cada 10 s; los ultimos 15 min a la vista
  #ETH/okx_swap/1/30m/unidad=usd/hasta=<h>/ver=90  un venue solo, al paso 1 (2x el guardado), en USD
  #BTC/perp/ver=90                               el VIVO: la escalera de los ultimos avisos y el canal por el que van
  #BTC/binance_usdm/hasta=<h>                    R1: un venue solo, 1 h a cada 5 s = 720 columnas, y caben 710
y en 1280x720:
  #BTC/perp/4h/hasta=<h>                         R1: 4 h de perpetuos a cada 30 s = 480 columnas, y caben 382
  #BTC/coinbase/30m/hasta=<h> con DPR 0.5        R1 en los dos ejes (el zoom del navegador al 50 %): 360 columnas y
                                                 ~170 niveles conocidos, y caben 191 y 110 (con DPR 1 caben 220
                                                 niveles, y la retencion no ha dado mas de 204)
R1 · CADA PIXEL DEL MAPA ES DE UNA CELDA: lo que cabe lo mide K111 (el lienzo y su devicePixelRatio): una celda, al
menos 2x2 pixeles de pantalla; lo que no cabe, la pagina no lo aleja (las columnas mas nuevas que caben; en vertical,
una banda en la mejor compra) y lo dice debajo del mapa. Y lee TODOS los pixeles del mapa: cada uno, del color del
cuadrito que le da la geometria declarada. Una vista de R1 que deja de recortar es NO MEDIDO (ya no ejercita el caso).

LOS BRAZOS (cualquiera pone ROJO; uno sin canal es NO MEDIDO y un ROJO de otro manda sobre el):
  (P) la pagina   carga su vista sin excepciones, la pinta, y pide la historia de SU hash: activo, venues, paso, la
                  ventana y el `cada` de la regla (el menor multiplo de 5 s con el que caben 2000 fotos)
  (V) la familia  pide, sirve y pinta los venues de UNA familia (o un venue): nunca dos sumadas
  (S) lo servido  /api/libro/fotos == lo recalculado de libro_foto (lo ya escrito)
  (F) lo pintado  el mapa: sus columnas y su estado (foto, HUECO, sin escribir), cada celda con la suma de los que la
                  conocen y cuantos son, ningun desconocido pintado (ni como cero), el color del percentil de la
                  ventana, los pixeles de sus cuatro cuadritos y la mejor compra y venta de cada instante; la escalera:
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
HASTA_R1 = os.environ.get("K111_HASTA_R1", "")  # el final de las vistas de R1 (por omision, el de las otras)
ESPERA_VIVO_S = float(os.environ.get("K111_ESPERA_VIVO", "25"))
RATON_S = float(os.environ.get("K111_RATON", "20"))  # (149 r1) el raton quieto sobre la escalera, en vivo
ANCHO, ALTO = 1920, 1080
# (149 B) lo que no es mapa: a la derecha «ahora» 28, el perfil de lo negociado 64, el del libro 64 y los precios 76;
# debajo el volumen por minuto 40 y las horas 20
AHORA_PX, VOLUMEN_PX, PERFIL_PX, BAJO_PX = 28, 64, 64, 40
EJE_P, EJE_T = AHORA_PX + VOLUMEN_PX + PERFIL_PX + 76, BAJO_PX + 20
RUTA_CINTA = "/api" + "/orderflow/cinta"
RUTA_HONDA, RUTA_HUELLA = "/api" + "/libro/honda", "/api" + "/orderflow/footprint"
HONDA_RANCIA_MS = 75_000  # app/libro_honda.py RANCIA_S
PERCENTILES = (20, 98)  # los cortes de lo visible por omision (el mando de intensidad los mueve; K111 no lo toca)
RUTA_PERFIL = "/api" + "/orderflow/perfil"
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
FONDO, DESCONOCIDO, PENDIENTE = (10, 13, 18), (26, 26, 26), (30, 36, 46)
HUECO, HUECO_RAYA = (34, 29, 22), (52, 42, 26)  # rayas: (columna + nivel) % 3 == 0
COMPRA, VENTA, REFERENCIA = (0x60, 0xA5, 0xFA), (0xE0, 0x5A, 0x5A), (0xF2, 0xCC, 0x60)
SUB = [(0, 0), (1, 1), (1, 0), (0, 1)]  # los cuatro cuadritos de una celda (desde 149 B, todos del mismo color)


def _lut(b: tuple) -> list[tuple]:
    """Del fondo (0) al color lleno del lado (255) en linea recta; Math.round de JS es floor(x + 0.5)."""
    return [tuple(math.floor(c + (b[j] - c) * i / 255 + 0.5) for j, c in enumerate(FONDO)) for i in range(256)]


LUT_C, LUT_V = _lut(COMPRA), _lut(VENTA)


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


def cortes(cols: list[dict], j0: int, j1: int, lo: int, hi: int, paso: str, u: str, pc=PERCENTILES):
    """(149 B) LOS DOS CORTES DE LO VISIBLE: las cantidades > 0 de las celdas conocidas de las columnas j0..j1 con foto y
    los niveles lo..hi; el percentil p es el de puesto floor(p / 100 * (n - 1)). Debajo del bajo, el fondo (-1); entre
    los dos, lineal 0..255; encima del alto, 255. -> (indice, (a, b), n)."""
    xs = sorted(q for c in cols[max(0, j0):j1 + 1] if c["estado"] == "foto" and c["suma"]
                for k in c["suma"]["n"] if lo <= k <= hi
                for q in [unidad(c["suma"]["c"][k] + c["suma"]["v"][k], k, paso, u)] if q > 0)
    a, b = ((xs[min(len(xs) - 1, math.floor(p / 100 * (len(xs) - 1)))] for p in pc) if xs else (None, None))

    def indice(q: float) -> int:
        if not q > 0 or not xs or q < a:
            return -1
        if q >= b:
            return 255
        return min(255, math.floor(255 * (q - a) / (b - a)))

    return indice, (a, b), len(xs)


def honda_por_venue(fotos: list) -> dict:
    por: dict = {}
    for x in fotos:
        por.setdefault(x["venue"], []).append((epoch_ms(x["ts"]), x))
    for xs in por.values():
        xs.sort(key=lambda y: y[0])
    return por


def extras_honda(por: dict, venues: list, t: int, alcance: dict, paso: str, guardado: str) -> list:
    """La regla de la capa honda para UNA columna en t: por venue, su ultima foto con ts <= t, de no mas de 75 s, no
    rancia y con niveles; sus niveles (por suelo al paso de la vista) solo fuera del alcance vivo de ese venue
    (alcance[venue] = (lo, hi), o ninguno). -> [(venue, edad_s, {k: [compra, venta]})]"""
    s_, m_ = float(guardado), round(float(paso) / float(guardado))
    extras = []
    for venue in venues:
        ant = [y for y in por.get(venue, []) if y[0] <= t]
        if not ant:
            continue
        t_, f = ant[-1]
        if t - t_ > HONDA_RANCIA_MS or f.get("rancia") or (not f.get("compras") and not f.get("ventas")):
            continue
        L = alcance.get(venue)
        niv: dict = {}
        for lado, campo, sig in ((0, "compras", -1), (1, "ventas", 1)):
            if not f.get(campo):
                continue
            k0 = round(float(f[campo]["desde"]) / s_)
            for i, q in enumerate(f[campo]["cantidades"]):
                k = (k0 + sig * i) // m_
                if L and (k >= L[0] if lado == 0 else k <= L[1]):
                    continue
                niv.setdefault(k, [0.0, 0.0])[lado] += float(q)
        if niv:
            extras.append((venue, (t - t_) / 1000, niv))
    return extras


def junta_honda(cols: list[dict], d: dict | None, e: dict, paso: str) -> dict:
    """(149 B) LA CAPA HONDA, recalculada aqui: por venue de la familia, su ULTIMA foto honda con ts <= t, de no mas de
    75 s, no rancia y con niveles; sus niveles (al paso guardado, por suelo al de la vista) solo ANADEN fuera del alcance
    vivo de ESE venue en esa columna (compras por debajo de su lo, ventas por encima de su hi); cuenta en n y en h."""
    guardado = PASO_GUARDADO[e["activo"]]
    if not d or d.get("fotos") is None:
        return {"pinta": False, "columnas": 0}
    if Decimal(paso) % Decimal(guardado):
        return {"pinta": False, "columnas": 0}
    por = honda_por_venue(d["fotos"])
    cuantas = 0
    for c in cols:
        s = c["suma"]
        if c["estado"] != "foto" or not s:
            continue
        alc = {}
        for y in c["fotos"]:
            L = libro(y["venue"], y["compra"], y["venta"], y["compras"], y["ventas"], paso)
            alc[y["venue"]] = (L["lo"], L["hi"])
        extras = extras_honda(por, e["venues"], c["ts"], alc, paso, guardado)
        if not extras:
            continue
        cuantas += 1
        h: dict = {}
        for _, _, niv in extras:
            for k, (qc, qv) in niv.items():
                s["c"][k] = s["c"].get(k, 0.0) + qc
                s["v"][k] = s["v"].get(k, 0.0) + qv
                s["n"][k] = s["n"].get(k, 0) + 1
                h[k] = h.get(k, 0) + 1
        s["lo"], s["hi"] = min([s["lo"], *s["n"]]), max([s["hi"], *s["n"]])
        s["h"], s["honda"] = h, [{"venue": v, "edad_s": a} for v, a, _ in extras]
    return {"pinta": True, "columnas": cuantas}


# --------------------------------------------------------------------------------------------- mirar
COSECHA = r"""
(() => {
  const h = window.LIBRO_HITOS || {};
  if (h.repinta) h.repinta();
  // (149 B r1, P4) las celdas del contrato se declaran fuera del gesto: se piden enteras antes de leerlo
  if (typeof EL_MAPA !== 'undefined' && EL_MAPA && EL_MAPA.declara) EL_MAPA.declara();
  const filas = [...document.querySelectorAll('#esc-filas tbody tr')].map((tr) => {
    const r = tr.getBoundingClientRect();
    return {cls: tr.className, d: Object.assign({}, tr.dataset), t: [...tr.children].map((td) => td.textContent),
            c: [...tr.children].map((td) => ({cl: td.className, d: Object.assign({}, td.dataset),
                                              f: td.style.getPropertyValue('--f')})), m: (r.top + r.bottom) / 2};
  });
  const caja = document.querySelector('#escalera .esc-tabla');
  const thd = document.querySelector('#esc-filas thead');
  const cr = caja ? caja.getBoundingClientRect() : null;
  const zona = caja ? {lo: cr.top + caja.clientTop + (thd ? thd.getBoundingClientRect().height : 0),
                       hi: cr.top + caja.clientTop + caja.clientHeight} : null;
  const tot = document.getElementById('esc-totales');
  const av = document.getElementById('esc-aviso');
  const ven = [...document.querySelectorAll('#esc-venues tbody tr')].map((tr) => Object.assign({}, tr.dataset,
    {t: tr.children[1] ? tr.children[1].textContent : ''}));
  const canal = document.querySelector('#estado p[data-estado="canal"]');
  const cv = document.getElementById('mapa');
  const r = cv ? cv.getBoundingClientRect() : null;
  const encaje = document.getElementById('encaje');
  return {listo: h.listo, vivo_listo: h.vivo_listo, vista: h.vista, recibidos: h.recibidos, hash: location.hash,
          pintado: window.LIBRO_PINTADO || null, filas, ven, canal: canal ? {texto: canal.textContent,
          dice: canal.dataset.canal} : null, lienzo: r ? {w: r.width, h: r.height, pr: window.devicePixelRatio} : null,
          encaje: encaje ? encaje.textContent : null, zona,
          totales: tot ? Object.assign({t: tot.textContent}, tot.dataset) : null,
          aviso: av ? Object.assign({t: av.textContent}, av.dataset) : null};
})()
"""
# todos los pixeles de un rectangulo del lienzo (en pixeles de pantalla), en RGB y en base64
RGB = r"""
(([w, h]) => {
  const d = document.getElementById('mapa').getContext('2d').getImageData(0, 0, w, h).data;
  const out = new Uint8Array(w * h * 3);
  for (let i = 0, o = 0; i < d.length; i += 4, o += 3) { out[o] = d[i]; out[o + 1] = d[i + 1]; out[o + 2] = d[i + 2]; }
  let s = '';
  for (let i = 0; i < out.length; i += 32768) s += String.fromCharCode.apply(null, out.subarray(i, i + 32768));
  return btoa(s);
})
"""
PIXELES = r"""
((puntos) => {
  const cv = document.getElementById('mapa');
  const img = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height);
  return puntos.map(([x, y]) => { const o = (y * cv.width + x) * 4; return [img.data[o], img.data[o + 1], img.data[o + 2]]; });
})
"""


# (149 r1) la fila bajo un raton QUIETO: cada segundo, que fila hay bajo el puntero, a que altura esta la del principio,
# y los bordes del libro que la pagina declara (si no se mueven, no se juzga nada)
RATON = r"""
(([x, y]) => {
  const e = document.elementFromPoint(x, y), tr = e && e.closest('#esc-filas tbody tr');
  const r = (window.LIBRO_PINTADO || {}).escalera || {};
  if (!tr) return null;
  if (!window.__k111h) window.__k111h = tr;
  const h = window.__k111h;
  return {k: tr.dataset.k, k0: h.dataset.k, top: Math.round(h.getBoundingClientRect().top * 10) / 10, misma: tr === h,
          vivo: h.isConnected, hover: h.matches(':hover'), hi: r.libro_hi === undefined ? null : r.libro_hi,
          lo: r.libro_lo === undefined ? null : r.libro_lo, sc: Math.round(tr.closest('.esc-tabla').scrollTop),
          nf: tr.parentNode.children.length, k1: tr.parentNode.firstElementChild.dataset.k,
          kn: tr.parentNode.lastElementChild.dataset.k};
})
"""


async def raton_quieto(K, s) -> list:
    xy = await s.evalua("(() => { const b = document.querySelector('.esc-tabla').getBoundingClientRect();"
                        " return [Math.round(b.left + b.width / 2), Math.round(b.top + b.height / 2 + 40)]; })()")
    await s.pide("Input.dispatchMouseEvent", type="mouseMoved", x=xy[0], y=xy[1])
    await s.drena(0.3)
    muestras = []
    for i in range(int(RATON_S) + 1):
        with contextlib.suppress(K.SystemExit2):
            muestras.append(await s.evalua(f"{RATON}({json.dumps(xy)})"))
        if i < int(RATON_S):
            await s.drena(1.0)
    await s.pide("Input.dispatchMouseEvent", type="mouseMoved", x=1, y=1)
    return muestras


def juzga_raton(vio: dict, rojos: list, info: list, pref: str) -> None:
    """Con el raton encima, un nivel no cambia de y (+-1 px) aunque el libro crezca o encoja por arriba o por abajo."""
    m = vio.get("raton")
    if m is None:
        return
    ok = [x for x in m if x]
    if len(ok) < 2:
        rojos.append(f"(F) {pref} raton quieto: no hay fila de la escalera bajo el puntero ({len(ok)} de {len(m)} muestras)")
        return
    bordes = len({(x["hi"], x["lo"]) for x in ok})
    # (149 B r1, P5) solo el borde de ARRIBA (el nivel mas alto) corre las filas de una rejilla sin ancla: uno de abajo
    # anade o quita filas por debajo del raton. La vista la ejercita si cambia el de arriba, no si cambia cualquiera
    arriba = len({x["hi"] for x in ok})
    a = ok[0]
    # (149 B r1, P5) la rejilla en cada muestra distinta: filas, primera..ultima y scroll; dice POR QUE un nivel no se movio
    rej = " · rejilla " + " ".join(dict.fromkeys(f"{x.get('nf')}f {x.get('k1')}..{x.get('kn')} sc{x.get('sc')}"
                                                 for x in ok))[:400]
    malo = next((x for x in ok if x["k"] != a["k"] or not x["misma"] or not x["vivo"] or not x["hover"]
                 or abs(x["top"] - a["top"]) > 1), None)
    if malo:
        rojos.append(f"(F) {pref} la fila se mueve bajo el raton quieto: nivel {a['k']} a y {a['top']} y luego bajo el "
                     f"puntero {malo['k']} (la de antes a y {malo['top']}, {'en' if malo['hover'] else 'sin'} :hover) · "
                     f"{bordes} bordes del libro ({arriba} de arriba) en {RATON_S:.0f} s" + rej)
    else:
        info.append(f"(F) {pref} raton quieto {RATON_S:.0f} s: el nivel {a['k']} no se movio · {bordes} bordes del libro"
                    f" ({arriba} de arriba)" + ("" if arriba > 1 else " (el borde de ARRIBA no se movio: no ejercita la "
                                                "rejilla)") + rej)


def piezas(vista: str, pieza: str) -> None:
    """(149 B) Con K111_PIEZAS=<fichero>, cada pieza de la huella, entera, a ese fichero: dos corridas se comparan con diff."""
    if os.environ.get("K111_PIEZAS"):
        with open(os.environ["K111_PIEZAS"], "a") as f:
            f.write(f"{vista}\t{pieza}\n")


async def mira(K, vista: str, cab: dict, vivo: bool, ancho: int = ANCHO, alto: int = ALTO, dpr: float = 1) -> dict:
    out = {"vista": vista, "excepciones": [], "fotos": [], "ultimo": [], "cinta": [], "perfil": [], "honda": [], "huella": [], "ws": [], "ws_abiertos": 0,
           "pantalla": [ancho, alto, dpr]}
    with K.Chromium(ancho, alto) as c:
        req = urllib.request.Request(f"http://127.0.0.1:{c.puerto}/json/new?about:blank", method="PUT")
        with urllib.request.urlopen(req, timeout=10) as r:
            destino = json.load(r)
        async with K.websockets.connect(destino["webSocketDebuggerUrl"], max_size=300 * 1024 * 1024) as ws:
            s = K.Sesion(ws)
            for metodo in ("Page.enable", "Runtime.enable", "Network.enable"):
                await s.pide(metodo)
            await s.pide("Network.setCacheDisabled", cacheDisabled=True)
            await s.pide("Emulation.setDeviceMetricsOverride", width=ancho, height=alto, deviceScaleFactor=dpr,
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
            if vivo and listo and RATON_S > 0:
                out["raton"] = await raton_quieto(K, s)
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
                elif m == "Network.requestWillBeSent" and any(r in p["request"]["url"] for r in (
                        "/api" + "/libro/", RUTA_CINTA, RUTA_PERFIL, RUTA_HUELLA)):
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
                (out["fotos"] if RUTA_FOTOS in x["url"] else out["ultimo"] if RUTA_ULTIMO in x["url"]
                 else out["cinta"] if RUTA_CINTA in x["url"] else out["perfil"] if RUTA_PERFIL in x["url"]
                 else out["honda"] if RUTA_HONDA in x["url"] else out["huella"] if RUTA_HUELLA in x["url"] else []).append(x)
            out["pixeles"] = {}
            pedir = juez_puntos(out) if not vivo else []
            if pedir:
                vals = await s.evalua(PIXELES + "(" + json.dumps(pedir) + ")")
                out["pixeles"] = {tuple(p): tuple(v) for p, v in zip(pedir, vals, strict=True)}
            # y TODOS los pixeles del lienzo (el mapa, «ahora», los perfiles y el volumen de debajo; los ejes de texto no
            # se juzgan): el tamano medido aqui, no lo que declara la pagina
            lz = out.get("lienzo") or {}
            if not vivo and lz.get("w"):
                pr = lz.get("pr") or 1
                tam = [math.floor(math.floor(lz["w"]) * pr), math.floor(math.floor(lz["h"]) * pr)]
                if min(tam) > 0:
                    out["rgb"] = base64.b64decode(await s.evalua(RGB + "(" + json.dumps(tam) + ")"))
                    out["rgb_tam"] = tam
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
    # (149 B) la capa honda se junta a las columnas de la primera respuesta (las que se recuperan despues no la llevan:
    # la pagina tampoco); la respuesta, la ultima con cuerpo
    hr = [p for p in vio.get("honda") or [] if p.get("cuerpo")]
    honda = junta_honda(cols, hr[-1 if e["hasta"] else 0]["cuerpo"] if hr else None, e, d0["paso"])
    for p in resp[1:]:
        d = p["cuerpo"]
        nuevas = {x["ts"]: x for x in columnas(d, e, [x["ts"] for x in cols if x["estado"] == "pendiente"],
                                               epoch_ms(d["as_of"]))}
        cols = [nuevas.get(x["ts"], x) if x["estado"] == "pendiente" else x for x in cols]
    for j, x in enumerate(cols):
        x["j"] = j
    # (149 B r1) el footprint: cada respuesta sustituye las velas de su desde en adelante (la de la carga, y en el vivo
    # las de cada minuto cerrado)
    velas, hay = [], False
    for p in vio.get("huella") or []:
        if not p.get("cuerpo"):
            continue
        hd = epoch_ms(urllib.parse.parse_qs(urllib.parse.urlparse(p["url"]).query)["desde"][0])
        velas = [x for x in velas if epoch_ms(x["ts"]) < hd] + list(p["cuerpo"].get("velas") or [])
        hay = True
    return {"q": q, "d": d0, "cols": cols, "honda": honda, "huella": {"velas": velas} if hay else None}


def juez_puntos(vio: dict) -> list[list[int]]:
    """Los pixeles que hay que leer: los cuatro cuadritos de cada celda visible (y tres puntos de cada columna HUECO o
    sin escribir), lejos de las lineas del precio."""
    m = ((vio.get("pintado") or {}).get("mapa")) or {}
    eje = m.get("eje")
    if not eje:
        return []
    pr = (vio.get("lienzo") or {}).get("pr") or 1  # el lienzo esta en pixeles de PANTALLA: CSS x devicePixelRatio
    out = []
    for c in m.get("columnas") or []:
        x0, w, fh = c["x0"], eje["columna"], eje["fila"]
        if x0 < 0 or x0 + w > eje["ancho"]:
            continue
        for k in range(eje["lo"], eje["hi"] + 1):
            y0 = (eje["hi"] - k) * fh
            for sx, sy in SUB:
                out.append([math.floor((x0 + (sx + 0.5) * w / 2) * pr), math.floor((y0 + (sy + 0.5) * fh / 2) * pr)])
    return out


def banda(lo: int, hi: int, cy: int, kb: int) -> tuple[int, int]:
    """Los niveles a la vista: todos [lo, hi] si caben; si no, `cy` alrededor de kb, dentro de [lo, hi]."""
    if hi - lo + 1 <= cy:
        return lo, hi
    a = min(hi - cy + 1, max(lo, kb - cy // 2))
    return a, a + cy - 1


def juzga_encaje(vio: dict, e: dict, eje: dict, cols: list[dict], paso: str, malos: list) -> dict:
    """R1 · LO QUE CABE lo mide K111, no la pagina: el lienzo del DOM y su devicePixelRatio, menos los ejes; una celda,
    al menos 2x2 pixeles de pantalla (uno por cuadrito). A la vista, min(n, caben, max(10, ver)) columnas, las ultimas;
    en vertical, los niveles que conocen (+-2) o, si no caben, la banda de la mejor compra de la columna mas nueva a la
    vista con libro. La linea de debajo del mapa lo dice y el contrato tambien."""
    lz = vio.get("lienzo") or {}
    pr = lz.get("pr") or 1
    ancho, alto = math.floor(lz.get("w") or 0) - EJE_P, math.floor(lz.get("h") or 0) - EJE_T
    cx, cy = max(1, math.floor(ancho * pr / 2)), max(1, math.floor(alto * pr / 2))
    n = len(cols)
    quiere = min(n, max(10, e["ver"] or n))
    ver = max(1, min(cx, quiere))
    if (eje["ancho"], eje["alto"]) != (ancho, alto):
        malos.append(f"R1: el mapa declara {eje['ancho']}x{eje['alto']} px y su lienzo mide {ancho}x{alto} sin los ejes")
    if eje["ver"] != ver or eje["fin"] != n - 1:
        malos.append(f"R1: ensena {eje['ver']} columnas en {ancho} px y caben {cx} (2 px por columna): tenian que ser "
                     f"{ver}, las ultimas")
    vis = [c["suma"] for c in cols[n - ver:] if c["suma"]] or [c["suma"] for c in cols if c["suma"]]
    lo_d, hi_d = min(s["lo"] for s in vis) - 2, max(s["hi"] for s in vis) + 2
    nuevo = next((c["suma"] for c in reversed(cols[n - ver:]) if c["suma"]), None)
    kb = math.floor(float(nuevo["compra"]) / float(paso) + 1e-9) if nuevo else (lo_d + hi_d) // 2
    lo, hi = banda(lo_d, hi_d, cy, kb)
    if (eje["lo"], eje["hi"]) != (lo, hi):
        malos.append(f"R1: ensena los niveles {eje['lo']}..{eje['hi']} y tenian que ser {lo}..{hi} (conocidos "
                     f"{lo_d}..{hi_d}, caben {cy})")
    if eje.get("caben") != [cx, cy]:
        malos.append(f"R1: el contrato dice que caben {eje.get('caben')} y caben {[cx, cy]}")
    txt = vio.get("encaje") or ""
    dice = [f"{ver} de {n} columnas y {hi - lo + 1} de {hi_d - lo_d + 1} niveles"]
    dice += [f"caben {cx} columnas"] if ver < quiere else []
    dice += [f"caben {cy} niveles"] if hi - lo + 1 < hi_d - lo_d + 1 else []
    falta = [x for x in dice if x not in txt]
    if falta:
        malos.append(f"R1: la pantalla no dice lo que ensena del mapa («{txt[:90]}»): le falta «{falta[0]}»")
    return {"ancho": ancho, "alto": alto, "pr": pr, "cx": cx, "cy": cy, "n": n, "ver": ver, "quiere": quiere,
            "filas": hi - lo + 1, "conocidos": hi_d - lo_d + 1}


QIX = {sub: q for q, sub in enumerate(SUB)}  # (x, y) de un cuadrito -> su numero


def cada_pixel(vio: dict, eje: dict, cols: list[dict], bien_de, tramos: list, paso: str) -> tuple[int, int, list]:
    """R1 · CADA PIXEL DEL MAPA (el rectangulo que midio K111): el pixel fuente que le toca por el vecino mas cercano
    con la geometria declarada (2 pixeles fuente por celda; en el centro del pixel de pantalla; a menos de 0.05 px fuente
    de un borde vale cualquiera de los dos) es un cuadrito de una celda A LA VISTA, y el pixel es de su color. Bajo las
    lineas del precio (a menos de 4 px de su trazo) no se lee. -> (de su celda, bajo el precio, malos, los 3 primeros)."""
    rgb, tam = vio.get("rgb"), vio.get("rgb_tam")
    if not rgb or not tam:
        return 0, 0, 1, ["R1: no se pudieron leer los pixeles del mapa"]
    lz = vio.get("lienzo") or {}
    pr = lz.get("pr") or 1
    S = tam[0]  # el buffer es el lienzo entero: el mapa es su rectangulo de arriba a la izquierda
    W, H = min(S, math.floor((math.floor(lz["w"]) - EJE_P) * pr)), min(tam[1], math.floor((math.floor(lz["h"]) - EJE_T) * pr))
    filas = eje["hi"] - eje["lo"] + 1
    ex, ey = 2 * eje["ver"] / (eje["ancho"] * pr), 2 * filas / (eje["alto"] * pr)
    x0 = 2 * (eje["fin"] - eje["ver"] + 1)
    j0, j1 = math.floor(eje["fin"] - eje["ver"] + 1), math.ceil(eje["fin"])

    def fuente(u: float) -> tuple:
        i = math.floor(u)
        return (i - 1, i) if u - i < 0.05 else (i, i + 1) if u - i > 0.95 else (i,)

    porx = [tuple((i // 2, i % 2) for i in fuente(x0 + (X + 0.5) * ex) if j0 <= i // 2 <= min(j1, len(cols) - 1))
            for X in range(W)]
    pory = [tuple((eje["hi"] - i // 2, i % 2) for i in fuente((Y + 0.5) * ey) if 0 <= i < 2 * filas) for Y in range(H)]
    excl: list[list] = [[] for _ in range(W)]
    for (xa, ya), (xb, yb) in tramos:
        t = 4 * math.hypot(1, (yb - ya) / max(1e-9, xb - xa))
        for X in range(max(0, math.floor((xa - 4) * pr)), min(W, math.ceil((xb + 4) * pr))):
            yl = ya + (yb - ya) * min(1.0, max(0.0, ((X + 0.5) / pr - xa) / max(1e-9, xb - xa)))
            excl[X].append((max(min(ya, yb) - 4, yl - t) * pr, min(max(ya, yb) + 4, yl + t) * pr))
    cache: dict = {}

    def acepta(j: int, k: int, qx: int, qy: int) -> list[bytes]:
        if (j, k, qx, qy) not in cache:
            cache[(j, k, qx, qy)] = [bytes(c) for c in bien_de(cols[j], k, QIX[(qx, qy)])]
        return cache[(j, k, qx, qy)]

    # por fila de cuadritos, la fila de pantalla que tiene que salir (el color exacto del primer candidato de cada
    # pixel): una fila igual se da por buena de una vez; donde difiere, se mira pixel a pixel (el precio, el +-1, el borde)
    esperadas: dict = {}
    for cand in set(pory):
        if cand:
            k, qy = cand[0]
            esperadas[cand] = b"".join(acepta(c[0][0], k, c[0][1], qy)[0] if c else b"\0\0\1" for c in porx)
    bien, bajo, n_malos, malos = 0, 0, 0, []
    for Y in range(H):
        base, yc, cand_y = Y * S * 3, Y + 0.5, pory[Y]
        fila, exp = rgb[base:base + 3 * W], esperadas.get(cand_y, b"")
        if fila == exp:
            bien += W
            continue
        for X in range(W):
            v = fila[3 * X:3 * X + 3]
            if v == exp[3 * X:3 * X + 3]:
                bien += 1
                continue
            if excl[X] and any(a <= yc <= b for a, b in excl[X]):
                bajo += 1
                continue
            vale = any(v in acepta(j, k, qx, qy) or any(all(abs(a - b) <= 1 for a, b in zip(v, c, strict=True))
                                                        for c in acepta(j, k, qx, qy))
                       for j, qx in porx[X] for k, qy in cand_y)
            if vale:
                bien += 1
                continue
            n_malos += 1
            if len(malos) >= 3:
                continue
            if not porx[X] or not cand_y:
                malos.append(f"R1: el pixel ({X}, {Y}) del mapa no cae en ninguna celda a la vista")
            else:
                (j, qx), (k, qy) = porx[X][0], cand_y[0]
                malos.append(f"R1: el pixel ({X}, {Y}) es {tuple(v)} y es de la columna {isoz(cols[j]['ts'])} nivel "
                             f"{k * float(paso):g} cuadrito {QIX[(qx, qy)]}: tenia que ser "
                             f"{tuple(bien_de(cols[j], k, QIX[(qx, qy)])[0])}")
    return bien, bajo, n_malos, malos


def jsround(x: float) -> int:
    return math.floor(x + 0.5)


def juzga_alrededor(vio: dict, e: dict, esp: dict, eje: dict, m: dict, cols: list[dict], j0: int, j1: int,
                    bien_de) -> tuple[list, int]:
    """(149 B) LO DE ALREDEDOR DEL MAPA, recalculado de lo servido y leido en los pixeles del lienzo: las lineas de la
    mejor compra / venta y la del ultimo precio, la banda «ahora» (la ultima columna estirada), el perfil del libro de
    ahora, el de lo negociado en lo visible (footprint 1m) y el volumen por minuto de debajo. -> (malos, pixeles leidos)."""
    malos: list = []
    leidos = 0
    rgb, tam = vio.get("rgb"), vio.get("rgb_tam") or [0, 0]
    pr = (vio.get("lienzo") or {}).get("pr") or 1
    paso = esp["d"]["paso"]
    P = float(paso)
    ancho, alto, fh, lo, hi, bs = eje["ancho"], eje["alto"], eje["fila"], eje["lo"], eje["hi"], eje["columna"]
    n, cada_ms = len(cols), int(esp["q"].get("cada") or 0) * 1000

    def pix(x: float, y: float):
        X, Y = math.floor(x * pr), math.floor(y * pr)
        if not rgb or not (0 <= X < tam[0] and 0 <= Y < tam[1]):
            return None
        o = 3 * (Y * tam[0] + X)
        return tuple(rgb[o:o + 3])

    def igual(v, c, tol: int = 2) -> bool:
        return v is not None and all(abs(a - b) <= tol for a, b in zip(v, c, strict=True))

    def cerca(a, b) -> bool:
        return abs(a - b) <= 1e-9 * max(1.0, abs(b)) + 1e-6

    def y_de(k: int) -> float:
        return (hi - k) * fh

    def y_precio(p) -> float:
        return jsround((hi + 1 - float(p) / P) * fh) + 0.5

    def x_de(j: int) -> float:
        return ancho - (eje["fin"] - j + 1) * bs

    def corrida(Y: int, xa: float, xb: float, color) -> int:
        """Cuantos pixeles de la fila de pantalla Y, entre xa y xb (CSS), son del color."""
        return sum(1 for X in range(math.floor(xa * pr), math.floor(xb * pr))
                   if igual(pix((X + 0.5) / pr, (Y + 0.5) / pr), color))

    entero = abs(pr - round(pr)) < 1e-9  # con un DPR fraccionario las lineas de 1 px se reparten: no se leen
    # el ultimo precio: el cierre de la ultima vela del footprint
    velas = ((esp.get("huella") or {}).get("velas")) or []
    u = m.get("ultimo")
    if velas:
        v_ = velas[-1]
        if not u or u.get("precio") != v_["cierre"] or u.get("ts") != v_["ts"] or u.get("y") != y_precio(v_["cierre"]):
            malos.append(f"el ultimo precio pintado {u} y la ultima vela servida cierra en {v_['cierre']} ({v_['ts']})")
        elif entero and 0 <= u["y"] < alto:
            for x in (ancho * 0.25, ancho * 0.75, ancho + AHORA_PX / 2):
                leidos += 1
                if not igual(pix(x, u["y"]), REFERENCIA):
                    malos.append(f"la linea del ultimo precio no esta en y={u['y']} x={x:.0f}: el pixel es {pix(x, u['y'])}")
                    break
    elif u:
        malos.append(f"pinta un ultimo precio {u} y no hay velas servidas")
    # las lineas de la mejor compra y venta, en el centro de cada escalon
    uy = (u or {}).get("y")
    for pc in (m.get("columnas") or []) if entero and bs * pr >= 4 else []:
        if pc["estado"] != "foto" or pc.get("y_compra") is None or pc["x0"] < 0 or pc["x0"] + bs > ancho:
            continue
        for campo in ("y_compra", "y_venta"):
            y = pc[campo]
            if not 0 <= y < alto:
                continue
            col = REFERENCIA if y == uy else VENTA if campo == "y_venta" or y == pc["y_venta"] else COMPRA
            leidos += 1
            if not igual(pix(pc["x0"] + bs / 2, y), col):
                malos.append(f"columna {pc['ts']}: la linea de {campo[2:]} en y={y} no se ve (el pixel es "
                             f"{pix(pc['x0'] + bs / 2, y)})")
                break
    # la banda «ahora»
    # (149 B r1) las «sin escribir aun» del final se saltan: la banda es la mas nueva CONOCIDA, y la declara
    jn = n - 1
    while jn > 0 and cols[jn]["estado"] == "pendiente":
        jn -= 1
    c_n = cols[jn] if cols else None
    ja = jn if c_n and j1 == n - 1 and c_n["estado"] == "foto" and c_n["suma"] else None
    ah = m.get("ahora") or {}
    vieja = ja is not None and ah.get("j") is None and not e.get("hasta") and "vieja" in str(ah.get("motivo"))
    if vieja:
        ja = None
    if ah.get("j") != ja:
        malos.append(f"«ahora» estira la columna {ah.get('j')} ({ah.get('motivo')}) y le toca la {ja}")
    elif ja is not None and ja < n - 1 and isoz(cols[ja]["ts"]) not in str(ah.get("motivo")):
        malos.append(f"«ahora» estira la conocida {isoz(cols[ja]['ts'])} con {n - 1 - ja} sin escribir detras y no "
                     f"lo dice ({ah.get('motivo')})")
    lineas = [y for y in (uy, c_n and (c_n["suma"] or {}).get("compra") and y_precio(c_n["suma"]["compra"]),
                          c_n and (c_n["suma"] or {}).get("venta") and y_precio(c_n["suma"]["venta"])) if y]
    for k in range(lo, hi + 1):
        y = y_de(k) + fh / 2
        if any(abs(y - z) < 4 for z in lineas):
            continue
        bien = bien_de(cols[ja], k, 0) if ja is not None else [FONDO]
        for x in (ancho + 7, ancho + 21):
            leidos += 1
            v = pix(x, y)
            if not any(igual(v, b, 1) for b in bien):
                malos.append(f"«ahora» nivel {k * P:g}: el pixel es {v} y tenia que ser {bien[0]}"
                             + (f" (la columna {isoz(cols[ja]['ts'])})" if ja is not None else " (el fondo)"))
                break
    # el perfil del libro de ahora
    x_perf = ancho + AHORA_PX + VOLUMEN_PX
    pf = m.get("perfil") or {}
    esperado = []
    if ja is not None:
        s = cols[ja]["suma"]
        fs = [(k, unidad(s["c"][k] + s["v"][k], k, paso, e["unidad"]), "v" if s["v"][k] > s["c"][k] else "c")
              for k in range(max(lo, s["lo"]), min(hi, s["hi"]) + 1) if k in s["n"]]
        tope = max([0.0] + [q for _, q, _ in fs])
        esperado = [(k, q, lado, (PERFIL_PX - 4) * q / tope if tope > 0 else 0) for k, q, lado in fs]
    decl = pf.get("barras") or []
    if len(decl) != len(esperado) or any(a[0] != b[0] or a[2] != b[2] or not cerca(a[1], b[1]) or not cerca(a[3], b[3])
                                         for a, b in zip(decl, esperado, strict=False)):
        malos.append(f"el perfil del libro declara {len(decl)} barras ({decl[:1]}) y de la columna «ahora» salen "
                     f"{len(esperado)} ({esperado[:1]})")
    for k, _, lado, largo in esperado if fh * pr >= 2 else []:
        Y = math.floor((y_de(k) + fh / 2) * pr)
        vistos = corrida(Y, x_perf + 2, x_perf + PERFIL_PX - 1, VENTA if lado == "v" else COMPRA)
        leidos += 1
        if abs(vistos - largo * pr) > 1.5:
            malos.append(f"el perfil del libro, nivel {k * P:g}: {vistos} pixeles de su lado y la barra mide "
                         f"{largo * pr:.1f}")
            break
    # lo negociado en lo visible: las velas 1m que tocan [ts j0, ts j1 + cada)
    vol = m.get("volumen") or {}
    if velas and cols and j0 <= j1:
        tA, tB = cols[j0]["ts"], cols[j1]["ts"] + cada_ms
        dentro = [x for x in velas if not (epoch_ms(x["ts"]) + 60000 <= tA or epoch_ms(x["ts"]) >= tB)]
        niv: dict = {}
        for x in dentro:
            for y in x.get("niveles") or []:
                z = niv.setdefault(jsround(float(y["nivel"]) / P), [0.0, 0.0])
                z[0] += float(y["compra"])
                z[1] += float(y["venta"])
        fs = [(k, *niv[k]) for k in range(lo, hi + 1) if k in niv]
        tope = max([0.0] + [max(c, v) for _, c, v in fs])
        r_ = (VOLUMEN_PX - 4) / tope if tope > 0 else 0
        esperado = [(k, c, v, r_ * c, r_ * v) for k, c, v in fs]
        decl = vol.get("barras") or []
        if (vol.get("desde"), vol.get("hasta")) != (isoz(tA), isoz(tB)) or len(decl) != len(esperado) or any(
                a[0] != b[0] or not all(cerca(a[i], b[i]) for i in range(1, 5)) for a, b in zip(decl, esperado, strict=False)):
            malos.append(f"el perfil de lo negociado declara {vol.get('desde')}-{vol.get('hasta')} y {len(decl)} barras "
                         f"({decl[:1]}); lo visible es {isoz(tA)}-{isoz(tB)} con {len(esperado)} ({esperado[:1]})")
        x_vol = ancho + AHORA_PX
        for k, _, _, lc, lv in esperado if fh * pr >= 4 else []:
            for dy, largo_, color in ((fh / 4, lc, COMPRA), (3 * fh / 4, lv, VENTA)):
                vistos = corrida(math.floor((y_de(k) + dy) * pr), x_vol + 2, x_vol + VOLUMEN_PX - 1, color)
                leidos += 1
                if abs(vistos - largo_ * pr) > 1.5:
                    malos.append(f"el perfil de lo negociado, nivel {k * P:g}: {vistos} pixeles de "
                                 f"{'compra' if color == COMPRA else 'venta'} y la barra mide {largo_ * pr:.1f}")
                    break
        # el volumen por minuto, debajo, alineado con el tiempo del mapa
        bt = max([0.0] + [float(x["compra"]) + float(x["venta"]) for x in dentro])
        xt0 = x_de(j0)
        esperado = []
        for x in dentro:
            t_ = epoch_ms(x["ts"])
            esperado.append((x["ts"], float(x["compra"]), float(x["venta"]), xt0 + (t_ - tA) / cada_ms * bs,
                             xt0 + (t_ + 60000 - tA) / cada_ms * bs))
        decl = (m.get("bajo") or {}).get("velas") or []
        if len(decl) != len(esperado) or any(isoz(epoch_ms(a[0])) != isoz(epoch_ms(b[0])) or not all(
                cerca(a[i], b[i]) for i in range(1, 5)) for a, b in zip(decl, esperado, strict=False)):
            malos.append(f"el volumen de debajo declara {len(decl)} velas ({decl[:1]}) y lo visible da {len(esperado)} "
                         f"({esperado[:1]})")
        hb, base = BAJO_PX - 4, alto + BAJO_PX
        for ts_, c, v, x0, x1 in esperado:
            wb = max(1, x1 - x0 - 1)
            if wb * pr < 2 or x0 + 0.5 < 0 or x0 + 0.5 + wb > ancho:
                continue
            X = (x0 + 0.5 + wb / 2)
            nc = sum(1 for Y in range(math.floor(alto * pr), math.floor(base * pr)) if igual(pix(X, (Y + 0.5) / pr), COMPRA))
            nv = sum(1 for Y in range(math.floor(alto * pr), math.floor(base * pr)) if igual(pix(X, (Y + 0.5) / pr), VENTA))
            leidos += 1
            hc, hv = (hb * c / bt, hb * v / bt) if bt > 0 else (0, 0)

            def filas(y0: float, y1: float) -> tuple:  # (enteras, tocadas): un borde fraccionario se mezcla
                a_, b_ = y0 * pr, y1 * pr
                return max(0, math.floor(b_) - math.ceil(a_)), max(0, math.ceil(b_) - math.floor(a_))
            fc, fv = filas(base - hc, base), filas(base - hc - hv, base - hc)
            if not (fc[0] <= nc <= fc[1] and fv[0] <= nv <= fv[1]):
                malos.append(f"el volumen de debajo, minuto {ts_}: {nc} pixeles de compra y {nv} de venta; tocan "
                             f"{hc * pr:.1f} y {hv * pr:.1f} (entre {fc} y {fv})")
                break
    elif vol.get("barras") or (m.get("bajo") or {}).get("velas"):
        malos.append("pinta volumen y no hay velas servidas a la vista")
    return malos, leidos


def juzga_mapa(vio: dict, e: dict, esp: dict, rojos: list, info: list, pref: str) -> None:
    m = (vio.get("pintado") or {}).get("mapa") or {}
    eje, pintadas = m.get("eje"), m.get("columnas") or []
    if not eje or not pintadas:
        rojos.append(f"(F) {pref} el mapa no declara lo que pinto (sin eje o sin columnas)")
        return
    cols = esp["cols"]
    por_ts = {c["ts"]: (j, c) for j, c in enumerate(cols)}
    # los hallazgos, en seis cubos del mas grave al menos: lo que no cabe (R1) mueve todos los pixeles, y una columna en
    # otro estado tapa los colores que mueve
    m_r1, m_col, m_celda, m_color, m_pix, m_todo = [], [], [], [], [], []
    pix_ok, pix_saltados, celdas = 0, 0, 0
    j0, j1 = max(0, math.floor(eje["fin"] - eje["ver"] + 1)), min(len(cols) - 1, math.ceil(eje["fin"]))
    # (149 B) los cortes de lo VISIBLE (columnas j0..j1, niveles del eje), recalculados aqui
    indice, corte, n_corte = cortes(cols, j0, j1, eje["lo"], eje["hi"], esp["d"]["paso"], e["unidad"])
    esc = m.get("escala") or {}
    if esc.get("tipo") != "cortes de lo visible" or esc.get("celdas") != n_corte or any(
            (x is None) != (y is None) or (x is not None and abs(x - y) > 1e-9 * max(1, abs(y)))
            for x, y in zip(esc.get("corte") or [None, None], corte, strict=False)):
        m_color.append(f"la escala declara {esc.get('tipo')} cortes {esc.get('corte')} sobre {esc.get('celdas')} celdas "
                       f"y los de lo visible son {list(corte)} sobre {n_corte}")
    hd = m.get("honda") or {}
    if bool(hd.get("pinta")) != esp["honda"]["pinta"] or (esp["honda"]["pinta"] and hd.get("columnas")
                                                         != esp["honda"]["columnas"]):
        m_col.append(f"capa honda: la pagina dice {hd.get('pinta')} en {hd.get('columnas')} columnas y lo servido da "
                     f"{esp['honda']['pinta']} en {esp['honda']['columnas']}")
    px = vio.get("pixeles") or {}
    vistas_ts = [epoch_ms(c["ts"]) for c in pintadas if c.get("origen") != "vivo"]
    if vistas_ts != [c["ts"] for c in cols[j0:j1 + 1]][:len(vistas_ts)]:
        m_col.append(f"columnas pintadas {len(vistas_ts)} ({isoz(vistas_ts[0]) if vistas_ts else '-'} ...) y las "
                     f"de la ventana a la vista son {j1 - j0 + 1} ({isoz(cols[j0]['ts'])} ...)")
    paso, fh, w = esp["d"]["paso"], eje["fila"], eje["columna"]
    pr = (vio.get("lienzo") or {}).get("pr") or 1
    r1 = vio["_r1"] = juzga_encaje(vio, e, eje, cols, paso, m_r1)

    def bien_de(c: dict, k: int, q_: int) -> list[tuple]:
        """Los colores que puede tener el cuadrito q_ del nivel k en la columna c (su color: el percentil +-1)."""
        s = c["suma"]
        if c["estado"] == "hueco":
            return [HUECO_RAYA if (c["j"] + k) % 3 == 0 else HUECO]
        if c["estado"] != "foto":
            return [PENDIENTE]
        if not (s and k in s["n"]):
            return [DESCONOCIDO]  # (149 B) un parcial lleva el color entero (P2: a); lo dice el tooltip
        ix = indice(unidad(s["c"][k] + s["v"][k], k, paso, e["unidad"]))
        lut = LUT_V if s["v"][k] > s["c"][k] else LUT_C  # el lado mayor manda; empate, compra
        return [FONDO] if ix < 0 else [lut[i] for i in (ix, ix - 1, ix + 1) if 0 <= i <= 255]  # el exacto, primero

    # (149 B) las lineas del precio, en escalones de 1 px sin halo: por columna con foto, un tramo horizontal de x0 a
    # x0 + w y uno vertical desde la anterior con foto; y el ultimo precio de lado a lado. A menos de 4 px no se lee.
    tramos = []
    for campo in ("y_compra", "y_venta"):
        ant = None
        for pc in pintadas:
            y_ = pc.get(campo)
            if y_ is None or pc["estado"] != "foto":
                ant = None
                continue
            tramos.append(((pc["x0"], y_), (pc["x0"] + w, y_)))
            if ant is not None and ant != y_:
                tramos.append(((pc["x0"], min(ant, y_)), (pc["x0"], max(ant, y_))))
            ant = y_
    if (m.get("ultimo") or {}).get("y") is not None:
        tramos.append(((0.0, m["ultimo"]["y"]), (float(eje["ancho"]), m["ultimo"]["y"])))

    cerca: dict = {}  # los tramos por la x entera que tocan (con 710 columnas son ~1400: recorrerlos todos tarda)
    for tr in tramos:
        for x_ in range(math.floor(tr[0][0] - 4), math.floor(tr[1][0] + 4) + 1):
            cerca.setdefault(x_, []).append(tr)

    def bajo_el_precio(x_: float, y_: float) -> bool:
        for (xa, ya), (xb, yb) in cerca.get(math.floor(x_), ()):
            if xa - 4 <= x_ <= xb + 4:
                yl = ya + (yb - ya) * min(1.0, max(0.0, (x_ - xa) / max(1e-9, xb - xa)))
                if abs(y_ - yl) <= 4 + abs(yb - ya) * 4 / max(1e-9, xb - xa):
                    return True
        return False

    for pc in pintadas:
        if pc.get("origen") == "vivo":
            continue
        t = epoch_ms(pc["ts"])
        if t not in por_ts:
            m_col.append(f"columna {pc['ts']} pintada y fuera de la ventana")
            continue
        j, c = por_ts[t]
        if abs(pc["x0"] - (eje["ancho"] - (eje["fin"] - j + 1) * w)) > 0.01:
            m_col.append(f"columna {pc['ts']}: x0 {pc['x0']:.2f} no es la de su instante")
        if pc["estado"] != c["estado"]:
            m_col.append(f"columna {pc['ts']}: pintada {pc['estado']} y lo servido dice {c['estado']}")
            continue
        s = c["suma"]
        if c["estado"] == "foto" and s:
            if sorted(pc["venues"]) != sorted(s["venues"]):
                m_col.append(f"columna {pc['ts']}: venues con foto pintados {pc['venues']} y servidos {s['venues']}")
            if (pc["mejor_compra"], pc["mejor_venta"]) != (s["compra"], s["venta"]):
                m_col.append(f"columna {pc['ts']}: mejores pintadas {pc['mejor_compra']}/{pc['mejor_venta']} y servidas "
                             f"{s['compra']}/{s['venta']}")
            for campo, precio in (("y_compra", s["compra"]), ("y_venta", s["venta"])):
                yy = (eje["hi"] + 1 - float(precio) / float(paso)) * fh
                if abs((pc.get(campo) or -1e9) - yy) > 1.01:
                    m_col.append(f"columna {pc['ts']}: la linea de {campo[2:]} esta en y={pc.get(campo)} y su precio en {yy:.1f}")
        cortas = [x for x in pc.get("celdas") or [] if len(x) != 7]
        if cortas:  # un contrato viejo (o roto) se condena; no tumba la sonda
            m_celda.append(f"columna {pc['ts']}: {len(cortas)} celdas declaradas sin las 7 piezas [k, c, v, n, ix, "
                           f"lado, h] ({cortas[0]})")
            continue
        decl = {x[0]: x for x in pc.get("celdas") or []}
        for k in range(eje["lo"], eje["hi"] + 1):
            conocida = bool(c["estado"] == "foto" and s and k in s["n"])
            if conocida != (k in decl):
                m_celda.append(f"columna {pc['ts']} nivel {k * float(paso):g}: "
                             + ("conocido y no pintado" if conocida else "DESCONOCIDO pintado como conocido"))
                continue
            esperado_q = None
            if conocida:
                celdas += 1
                cc, vv, n = s["c"][k], s["v"][k], s["n"][k]
                _, pc_c, pc_v, pc_n, pc_i, pc_l, pc_h = decl[k]
                if pc_l != ("v" if vv > cc else "c") or pc_h != (s.get("h") or {}).get(k, 0):
                    m_celda.append(f"columna {pc['ts']} nivel {k * float(paso):g}: lado {pc_l} y {pc_h} de capa honda; "
                                 f"lo servido da {'v' if vv > cc else 'c'} y {(s.get('h') or {}).get(k, 0)}")
                if abs(pc_c - cc) > 1e-9 * max(1, abs(cc)) or abs(pc_v - vv) > 1e-9 * max(1, abs(vv)) or pc_n != n:
                    m_celda.append(f"columna {pc['ts']} nivel {k * float(paso):g}: pinta compra {pc_c} venta {pc_v} "
                                 f"({pc_n} de {s['N']}) y lo servido da {cc} / {vv} ({n} de {s['N']})")
                ix = indice(unidad(cc + vv, k, paso, e["unidad"]))
                if abs(pc_i - ix) > 1:
                    m_color.append(f"columna {pc['ts']} nivel {k * float(paso):g}: color {pc_i} y el percentil de la "
                                 f"ventana da {ix}")
                esperado_q = (ix, 4)
            # los pixeles de sus cuatro cuadritos (en pixeles de pantalla: CSS x devicePixelRatio)
            y0 = (eje["hi"] - k) * fh
            for q_, (sx, sy) in enumerate(SUB):
                p = (math.floor((pc["x0"] + (sx + 0.5) * w / 2) * pr), math.floor((y0 + (sy + 0.5) * fh / 2) * pr))
                if p not in px:
                    continue
                if bajo_el_precio((p[0] + 0.5) / pr, (p[1] + 0.5) / pr) or (p[1] + 0.5) / pr >= eje["alto"]:
                    pix_saltados += 1
                    continue
                v = px[p]
                bien = bien_de(c, k, q_)
                if any(all(abs(a - b) <= 1 for a, b in zip(v, x, strict=True)) for x in bien):
                    pix_ok += 1
                else:
                    m_pix.append(f"columna {pc['ts']} nivel {k * float(paso):g} cuadrito {q_}: el pixel es {v} y tenia "
                                 f"que ser {bien[0]} ({'HUECO' if c['estado'] == 'hueco' else 'sin escribir' if c['estado'] == 'pendiente' else 'DESCONOCIDO' if esperado_q is None or q_ >= esperado_q[1] else 'su color'})")
    todos_bien, todos_bajo, n_todo, m_todo = cada_pixel(vio, eje, cols, bien_de, tramos, paso)
    m_alr, alr_leidos = juzga_alrededor(vio, e, esp, eje, m, cols, j0, j1, bien_de)
    malos = m_r1 + m_col + m_celda + m_color + m_pix + m_alr + m_todo
    cuantos = len(malos) - len(m_todo) + n_todo
    if malos:
        rojos.append(f"(F) {pref} el mapa no pinta lo servido: {malos[0]}" + (f" (y {cuantos - 1} mas)" if cuantos > 1 else ""))
    estados = {}
    for pc in pintadas:
        estados[pc["estado"]] = estados.get(pc["estado"], 0) + 1
    info.append(f"(F) {pref} mapa: {len(pintadas)} columnas a la vista ({', '.join(f'{k} {v}' for k, v in sorted(estados.items()))}), "
                f"{celdas} celdas conocidas, {pix_ok} pixeles leidos del lienzo y en su color ({pix_saltados} bajo el precio)")
    ancho_, alto_, dpr_ = vio.get("pantalla") or ["?", "?", 1]
    info.append(f"(F) {pref} R1 en {ancho_}x{alto_}{f' con DPR {dpr_}' if dpr_ != 1 else ''}: "
                f"{eje['ver']} de {r1['n']} columnas a la vista (caben {r1['cx']} en {r1['ancho']} px"
                f"{', el recorte se ejercita' if r1['ver'] < r1['quiere'] else ''}) y {eje['hi'] - eje['lo'] + 1} de "
                f"{r1['conocidos']} niveles (caben {r1['cy']}); cada pixel del mapa "
                f"({'x'.join(str(z) for z in vio.get('rgb_tam') or ['?', '?'])} de pantalla): {todos_bien} de su celda, "
                f"{todos_bajo} bajo el precio, {n_todo} de otra cosa; alrededor (ahora, perfiles, volumen, lineas): "
                f"{alr_leidos} lecturas, {len(m_alr)} malas; capa honda en {esp['honda']['columnas']} columnas")


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
                   casa, nomed: list | None = None) -> None:
    """La escalera pintada (el DOM) contra la recalculada de los libros que la pagina tenia (los vivos)."""
    vivos = [libros_por_venue[v] for v in e["venues"] if estados.get(v) == "vivo"]
    esp = escalera(vivos, len(e["venues"]), e["paso"], e["unidad"])
    filas, malos = vio.get("filas") or [], []
    todas = filas
    # (149 r1) el RELLENO: niveles fuera del libro por encima y por debajo, VACIOS, para que la rejilla tenga scroll
    no_rel = [i for i, f in enumerate(filas) if "relleno" not in f["cls"].split()]
    i0, i1 = (no_rel[0], no_rel[-1] + 1) if no_rel else (0, 0)
    relleno, filas = filas[:i0] + filas[i1:], filas[i0:i1]
    ks = [int(f["d"].get("k", "0")) for f in todas]
    if relleno and ks != list(range(ks[0], ks[0] - len(ks), -1)):
        malos.append(f"las filas no son niveles seguidos ({ks[0]} .. {ks[-1]}, {len(ks)} filas)")
    for f in relleno:
        d, t, c = f["d"], f["t"], f.get("c") or []
        if (d.get("n") != "0" or any(t[i] for i in (0, 2, 4, 6, 7)) or d.get("compra") is not None
                or d.get("venta") is not None or any(c[i]["d"].get("barra") is not None for i in (2, 4))):
            malos.append(f"fila {d.get('nivel')} (relleno, fuera del libro) no esta vacia: «{'|'.join(t)}»")
            break
    ven = {x.get("venue"): x for x in vio.get("ven") or []}
    for v in e["venues"]:
        if (ven.get(v) or {}).get("estado") != estados.get(v):
            malos.append(f"venue {v}: la escalera dice {(ven.get(v) or {}).get('estado')} y su ultimo mensaje "
                         f"{estados.get(v)}")
    if len(filas) != len(esp):
        malos.append(f"{len(filas)} filas pintadas y {len(esp)} recalculadas")
    cortas = [f for f in filas if len(f["t"]) != 8 or len(f.get("c") or []) != 8]
    if cortas:  # una pagina sin las 8 columnas (la de e0fb3fb) es ROJO de este brazo y no tumba a los demas
        malos.append(f"fila {cortas[0]['d'].get('nivel')}: {len(cortas[0]['t'])} columnas y la escalera tiene 8")
        filas = []
    for f, x in zip(filas, esp, strict=False):
        d, t = f["d"], f["t"]
        if int(d.get("k", "0")) != x["k"] or int(d.get("n", "-1")) != x["n"]:
            malos.append(f"fila {d.get('nivel')}: nivel/conocen {d.get('k')}/{d.get('n')} y recalculados {x['k']}/{x['n']}")
            continue
        if not x["n"]:
            if "desconocido" not in f["cls"] or t[2] or t[4] or d.get("compra") is not None:
                malos.append(f"fila {d.get('nivel')}: lo ausente (DESCONOCIDO) se pinta «{t[2]}» / «{t[4]}», no vacio")
            elif t[7] != f"0/{len(e['venues'])}":
                malos.append(f"fila {d.get('nivel')}: escribe conocen «{t[7]}» y son 0/{len(e['venues'])}")
            continue
        for campo, clave, col in (("compra", "c", 2), ("venta", "v", 4)):
            val = float(d.get(campo, "nan"))
            if not abs(val - x[clave]) <= 1e-9 * max(1.0, abs(x[clave])):
                malos.append(f"fila {d.get('nivel')}: {campo} pintada {d.get(campo)} y recalculada {x[clave]}")
            elif not (t[col] == "" if x[clave] == 0 else casa(t[col], repr(x[clave]))):  # un 0 se pinta vacio
                malos.append(f"fila {d.get('nivel')}: escribe {campo} «{t[col]}» y vale {x[clave]}")
        for campo, clave, parcial, col in (("acumCompra", "ac", "pc", 0), ("acumVenta", "av", "pv", 6)):
            if (d.get(campo) is None) != (x[clave] is None):
                malos.append(f"fila {d.get('nivel')}: acumulada {campo} pintada {d.get(campo)} y recalculada {x[clave]}")
            elif x[clave] is not None and (not abs(float(d[campo]) - x[clave]) <= 1e-9 * max(1.0, abs(x[clave]))
                                           or t[col].startswith("≥") != x[parcial] or not casa(t[col].lstrip("≥"), repr(x[clave]))):
                malos.append(f"fila {d.get('nivel')}: acumulada «{t[col]}» y recalculada {'≥' if x[parcial] else ''}{x[clave]}")
        if ("mejor-compra" in f["cls"]) != x["mc"] or ("mejor-venta" in f["cls"]) != x["mv"]:
            malos.append(f"fila {d.get('nivel')}: marcas {f['cls']} y la mejor compra/venta recalculada {x['mc']}/{x['mv']}")
        nn = "" if x["n"] == len(e["venues"]) else f"{x['n']}/{len(e['venues'])}"
        if t[7] != nn:
            malos.append(f"fila {d.get('nivel')}: escribe conocen «{t[7]}» y le toca «{nn}»")
    if filas and len(filas) == len(esp) and not (filas[0]["c"][4]["d"].get("rotulo") and filas[-1]["c"][2]["d"].get("rotulo")):
        malos.append("la frontera de lo conocido no lleva su rotulo")
    if malos:
        rojos.append(f"(F) {pref} la escalera no pinta lo servido: {malos[0]}" + (f" (y {len(malos) - 1} mas)" if len(malos) > 1 else ""))
    if len(filas) == len(esp):
        try:  # una pagina sin la forma profesional es ROJO de este brazo y no tumba a los demas (el R1 de e0fb3fb)
            juzga_pro(vio, e, esp, rojos, nomed if nomed is not None else [], info, pref, casa,
                      suma(vivos, len(e["venues"])), filas, todas)
        except (KeyError, TypeError, AttributeError, IndexError, ValueError) as exc:
            rojos.append(f"(F) {pref} la escalera no tiene la forma profesional: {type(exc).__name__} {str(exc)[:80]}")
    info.append(f"(F) {pref} escalera: {len(filas)} filas, {sum(1 for x in esp if x['n'])} niveles conocidos, "
                f"{len(vivos)} de {len(e['venues'])} venues sumando ({', '.join(f'{v} {estados.get(v)}' for v in e['venues'])})")


# --------------------------------------------------------------------------------------------- la escalera profesional
# (campana 149, ronda A) Recalculado aqui, sin creer a la pagina: las barras (p95 de lo visible, una escala), las
# grandes (3x la media del lado), los totales visibles, el volumen reciente de la cinta que la pagina uso (las primeras
# recibidos.cinta respuestas capturadas), la ultima operacion y el maximo / minimo de la sesion UTC.
RECIENTE_VUELVE_MS, RECIENTE_HUECO_MS, RECIENTE_OLVIDO_MS, GRANDE_X = 2500, 55000, 180000, 3


def ms_de(ts: str) -> int:
    d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return (d - datetime(1970, 1, 1, tzinfo=UTC)) // timedelta(milliseconds=1)


def p95(xs: list[float]) -> float | None:
    return sorted(xs)[math.ceil(0.95 * len(xs)) - 1] if xs else None


def reciente_vacio() -> dict:
    return {"primado": False, "corte": None, "vistos": {}, "niveles": {}, "ultimoK": None, "ultima": None,
            "falta": None, "paginas": 0, "asOf": None, "dia": None, "kmin": None, "kmax": None, "maxMs": None}


def suma_reciente(prev: dict, pag: dict, paso: str) -> dict:
    """El mismo calculo que sumaReciente de libro-calculo.js, escrito aparte."""
    P = float(paso)
    s = dict(prev, primado=True, vistos=dict(prev["vistos"]), paginas=prev["paginas"] + 1,
             niveles={k: dict(x) for k, x in prev["niveles"].items()})
    ops = [(o, ms_de(o["ts"]), f"{o['venue']}|{o['id']}") for o in pag.get("operaciones") or []]
    nuevas = [x for x in ops if x[2] not in s["vistos"]]
    as_of = ms_de(pag["as_of"])
    if prev["primado"] and not s["falta"]:
        if pag.get("truncada") and len(nuevas) == len(ops):
            s["falta"] = {"motivo": "truncada", "pagina": s["paginas"]}
        elif prev["asOf"] is not None and as_of - prev["asOf"] > RECIENTE_HUECO_MS:
            s["falta"] = {"motivo": "hueco", "pagina": s["paginas"]}
    s["asOf"] = as_of
    nuevas.sort(key=lambda x: (x[1], x[0]["venue"], str(x[0]["id"])))
    for o, ms, clave in nuevas:
        s["vistos"][clave] = ms
        if s["maxMs"] is None or ms > s["maxMs"]:
            s["maxMs"] = ms
        k = math.floor(float(o["precio"]) / P + 1e-9)
        dia = o["ts"][:10]
        if s["dia"] is None or dia > s["dia"]:
            s.update(dia=dia, kmin=k, kmax=k)
        elif dia == s["dia"]:
            s.update(kmin=min(s["kmin"], k), kmax=max(s["kmax"], k))
        if not s["ultima"] or ms >= s["ultima"]["ms"]:
            s["ultima"] = {"k": k, "ms": ms}
        if prev["primado"] and (s["corte"] is None or ms > s["corte"]):
            x = s["niveles"].get(k)
            if x and s["ultimoK"] != k and ms - x["ultMs"] > RECIENTE_VUELVE_MS:
                x.update(b=0.0, bu=0.0, a=0.0, au=0.0)
            if not x:
                x = s["niveles"][k] = {"b": 0.0, "bu": 0.0, "a": 0.0, "au": 0.0, "nb": 0, "na": 0, "ultMs": ms}
            lado = "b" if o.get("agresor") == "venta" else "a" if o.get("agresor") == "compra" else None
            if lado:
                x[lado] += float(o["base"])
                x[lado + "u"] += float(o["usd"])
                x["n" + lado] += 1
            x["ultMs"] = max(x["ultMs"], ms)
        s["ultimoK"] = k
    if not prev["primado"]:
        s["corte"] = s["maxMs"]
    if s["maxMs"] is not None:
        s["vistos"] = {c: m for c, m in s["vistos"].items() if m >= s["maxMs"] - RECIENTE_OLVIDO_MS}
    return s


def _igual(a, b: float) -> bool:
    try:
        return abs(float(a) - b) <= 1e-9 * max(1.0, abs(b))
    except (TypeError, ValueError):
        return False


def juzga_pro(vio: dict, e: dict, esp: list[dict], rojos: list, nomed: list, info: list, pref: str, casa,
              s: dict | None, filas: list, todas: list) -> None:
    """`filas` las del libro (con su frontera), parejas de `esp`; `todas`, con el relleno (lo reciente y las marcas)."""
    z = vio.get("zona")
    if not z:
        rojos.append(f"(F) {pref} la escalera no deja ver su caja: no se sabe que filas son visibles")
        return
    vis = [x for f, x in zip(filas, esp, strict=True) if z["lo"] < f["m"] < z["hi"]]
    qc = [x["c"] for x in vis if x["n"] and x["c"] > 0]
    qv = [x["v"] for x in vis if x["n"] and x["v"] > 0]
    tope = p95(qc + qv)
    medias = {"c": sum(qc) / len(qc) if qc else None, "v": sum(qv) / len(qv) if qv else None}
    barras, grandes = [], []
    for f, x in zip(filas, esp, strict=True):
        for lado, col in (("c", 2), ("v", 4)):
            cel, niv = f["c"][col], f["d"].get("nivel")
            b = cel["d"].get("barra")
            if not x["n"]:
                if b is not None or "grande" in cel["cl"].split():
                    barras.append(f"fila {niv} (desconocida) lleva barra {b}")
                continue
            fr = min(1.0, x[lado] / tope) if tope else 0.0
            if not (_igual(b, fr) and _igual(cel["f"], fr)):
                barras.append(f"fila {niv} {lado}: data-barra {b} y --f {cel['f']!r}, y le toca {fr} (tope p95 {tope})")
            g = medias[lado] is not None and x[lado] > 0 and x[lado] >= GRANDE_X * medias[lado]
            if ("grande" in cel["cl"].split()) != g:
                grandes.append(f"fila {niv} {lado}: {x[lado]} {'es' if g else 'no es'} >= {GRANDE_X}x la media "
                               f"{medias[lado]} y la pagina dice {'grande' if not g else 'normal'}")
    for nombre, malos in (("la barra no es su tamaño", barras), ("una orden grande con otro umbral", grandes)):
        if malos:
            rojos.append(f"(F) {pref} {nombre}: {malos[0]}" + (f" (y {len(malos) - 1} mas)" if len(malos) > 1 else ""))
    # los totales de lo visible
    tot, conocidas = vio.get("totales") or {}, [x for x in vis if x["n"]]
    c, v = sum(x["c"] for x in conocidas), sum(x["v"] for x in conocidas)
    mc, mv = (s or {}).get("compra"), (s or {}).get("venta")  # las mejores de la suma recalculada
    spread = None if mc is None or mv is None else Decimal(str(mv)) - Decimal(str(mc))
    mal = []
    if str(len(conocidas)) != tot.get("filas"):
        mal.append(f"filas {tot.get('filas')} y visibles conocidas {len(conocidas)}")
    if conocidas and not (_igual(tot.get("compra"), c) and _igual(tot.get("venta"), v)):
        mal.append(f"compra/venta {tot.get('compra')}/{tot.get('venta')} y lo visible suma {c}/{v}")
    if conocidas and c + v > 0 and not _igual(tot.get("pct"), 100 * c / (c + v)):
        mal.append(f"proporcion {tot.get('pct')} % y le toca {100 * c / (c + v)}")
    if spread is not None and (tot.get("spread") is None or Decimal(tot["spread"]) != spread):
        mal.append(f"spread {tot.get('spread')} y le toca {spread}")
    if mal:
        rojos.append(f"(F) {pref} los totales son de otra cosa: {mal[0]}")
    # lo reciente, la ultima operacion y la sesion
    reg = (vio.get("pintado") or {}).get("escalera") or {}  # el modo que declara; lo que pidio lo dice la red
    cinta, rec_t = reg.get("cinta"), [(f, i) for f in todas for i in (1, 5)]
    rcb = vio.get("recibidos") or {}
    pintado = [f"{f['d'].get('nivel')}:«{f['t'][i]}»" for f, i in rec_t if f["t"][i] or "rec" in f["c"][i]["d"]]
    if cinta == "fija":
        if rcb.get("cinta"):
            rojos.append(f"(F) {pref} se declara vista fija y uso {rcb.get('cinta')} respuestas de la cinta")
        if pintado:
            rojos.append(f"(F) {pref} una vista fija pinta volumen reciente: {pintado[0]}")
        info.append(f"(F) {pref} pro: {len(vis)} filas visibles, tope {tope}; vista fija: sin volumen reciente")
        return
    n, resp, npf, resp_p = rcb.get("cinta", 0), vio.get("cinta") or [], rcb.get("perfil", 0), vio.get("perfil") or []
    if not n:
        nomed.append(f"(C) {pref} la pagina no uso ninguna respuesta de la cinta: el volumen reciente no se juzga")
        return
    if len(resp) < n:
        nomed.append(f"(C) {pref} la pagina uso {n} respuestas de la cinta y se capturaron {len(resp)}: no se juzga")
        return
    rec, estado = reciente_vacio(), "pendiente"
    for x in resp[:n]:
        if x.get("estado") == 200 and x.get("cuerpo"):
            rec, estado = suma_reciente(rec, x["cuerpo"], e["paso"]), "ok"
        else:
            estado = "caida"
    if estado == "caida":
        if pintado or (vio.get("aviso") or {}).get("cinta") != "caida" or cinta != "caida":
            rojos.append(f"(F) {pref} la cinta caída se pinta como cifras o no se dice: "
                         f"{pintado[0] if pintado else 'aviso ' + str((vio.get('aviso') or {}).get('cinta'))}")
    else:
        mal, usd = [], e["unidad"] == "usd"
        for f, i in rec_t:
            x = rec["niveles"].get(int(f["d"]["k"]))
            esp_v = None if x is None else (x["bu"] if usd else x["b"]) if i == 1 else (x["au"] if usd else x["a"])
            d, tx = f["c"][i]["d"].get("rec"), f["t"][i]
            lado = "@bid" if i == 1 else "@ask"
            if (d is None) != (esp_v is None) or (esp_v is not None and not _igual(d, esp_v)):
                mal.append(f"fila {f['d'].get('nivel')} {lado}: pinta {d} y la cinta da {esp_v}")
            elif esp_v is not None and (casa(tx, repr(esp_v)) if esp_v > 0 else tx == "") is False:
                mal.append(f"fila {f['d'].get('nivel')} {lado}: escribe «{tx}» y vale {esp_v}")
            elif esp_v is None and tx:
                mal.append(f"fila {f['d'].get('nivel')} {lado}: escribe «{tx}» sin ninguna operacion")
        if mal:
            rojos.append(f"(F) {pref} el volumen reciente no es el de la cinta: {mal[0]}"
                         + (f" (y {len(mal) - 1} mas)" if len(mal) > 1 else ""))
        if (rec["falta"] or {}).get("motivo") != reg.get("falta_cinta"):
            rojos.append(f"(F) {pref} faltan operaciones: la pagina dice {reg.get('falta_cinta')} y la cinta "
                         f"{(rec['falta'] or {}).get('motivo')}")
        ult = {int(f["d"]["k"]) for f in todas if "ultima" in f["c"][3]["cl"].split()}
        ku = rec["ultima"]["k"] if rec["ultima"] else None
        if ult != ({ku} & {int(f["d"]["k"]) for f in todas}):
            rojos.append(f"(F) {pref} la ultima operacion se marca en {sorted(ult)} y fue en el nivel {ku}")
    if len(resp_p) < npf:
        nomed.append(f"(C) {pref} la pagina uso {npf} respuestas del perfil y se capturaron {len(resp_p)}: la sesion no se juzga")
    else:
        P, lo, hi, dia = float(e["paso"]), None, None, None
        for x in resp_p[:npf]:
            if x.get("estado") == 200 and x.get("cuerpo"):
                ks = [math.floor(float(nv["nivel"]) / P + 0.5) for nv in x["cuerpo"].get("niveles") or []]
                q = urllib.parse.parse_qs(x["url"].split("?", 1)[-1])
                lo, hi, dia = (min(ks), max(ks), q["desde"][0][:10]) if ks else (lo, hi, dia)
        if rec["dia"] is not None and (dia is None or rec["dia"] >= dia):
            if dia is not None and rec["dia"] > dia:
                lo = hi = None
            lo = rec["kmin"] if lo is None else min(lo, rec["kmin"])
            hi = rec["kmax"] if hi is None else max(hi, rec["kmax"])
        for clase, kx in (("max-sesion", hi), ("min-sesion", lo)):
            mar = {int(f["d"]["k"]) for f in todas if clase in f["c"][3]["cl"].split()}
            if mar != ({kx} & {int(f["d"]["k"]) for f in todas}):
                rojos.append(f"(F) {pref} el {clase} de la sesion UTC se marca en {sorted(mar)} y es el nivel {kx}")
    info.append(f"(F) {pref} pro: {len(vis)} filas visibles, tope {tope}, {n} paginas de cinta ({estado}), "
                f"{len(rec['niveles'])} niveles con reciente, faltan {(rec['falta'] or {}).get('motivo')}")


# --------------------------------------------------------------------------------------------- una vista
def juzga_vista(vista: str, vio: dict, rojos: list, nomed: list, info: list, casa, K110) -> dict | None:
    e = lee_vista(vista)
    vivo = not e["hasta"]
    pan = vio.get("pantalla") or [ANCHO, ALTO, 1]
    pref = f"[{e['activo']} {e['familia']}{' vivo' if vivo else ''}" \
        + (f" {pan[0]}x{pan[1]}" if vivo and pan[:2] != [ANCHO, ALTO] else "") + "]"
    pin = vio.get("pintado") or {}
    if vio["excepciones"]:
        rojos.append(f"(P) {pref} la pagina lanzo {len(vio['excepciones'])} excepcion(es): {vio['excepciones'][0]}")
    falta = [n for n, x in (("#esc-totales", vio.get("totales")), ("#esc-aviso", vio.get("aviso"))) if x is None]
    cortas = [f for f in vio.get("filas") or [] if len(f["t"]) != 8]
    if falta or cortas:  # de su html, no de lo que pinto: se condena aunque la pagina no llegue a listo
        rojos.append(f"(F) {pref} la escalera no tiene la forma profesional: "
                     + (f"falta {', '.join(falta)}" if falta else f"{len(cortas[0]['t'])} columnas y son 8"))
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
    # (149 B r1) EL FOOTPRINT CON EL CONTRATO DE LA RUTA REAL: desde y hasta, los dos, en borde de minuto; y la respuesta,
    # 200 (en produccion, un desde al borde de 10 s daba 422 y el perfil de volumen salia vacio sin que nada lo dijera)
    for p in vio.get("huella") or []:
        hq = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(p["url"]).query).items()}
        fuera = [k for k in ("desde", "hasta") if k not in hq or epoch_ms(hq[k]) % 60000]
        if fuera or p.get("estado") not in (200, None):  # None: en vuelo al congelar
            rojos.append(f"(P) {pref} pide el footprint fuera del contrato de la ruta: "
                         f"{', '.join(f'{k}={hq.get(k)}' for k in fuera) or 'desde-hasta en borde'} y le responde "
                         f"{p.get('estado')}")
            break
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
            juzga_escalera(vio, e, libros, estados, rojos, info, pref, casa, nomed)
    else:
        juzga_vivo(vio, e, rojos, nomed, info, pref, casa)
        juzga_honda_vivo(vio, e, rojos, info, pref)
        juzga_raton(vio, rojos, info, pref)
    return {"e": e, "q": q, "d": esp["d"], "K110": K110}


def juzga_honda_vivo(vio: dict, e: dict, rojos: list, info: list, pref: str) -> None:
    """(149 B r1) LA CAPA HONDA DEL VIVO con la regla de la historia: las fotos de la respuesta de la carga y de las
    primeras recibidos.honda del vivo (por venue|ts, manda la ultima); por columna con foto a la vista, la honda que
    declara (venue y edad) y, en cada nivel que no conoce el libro vivo de NINGUN venue (su alcance declarado), compra,
    venta y h son la suma de la capa honda; y un nivel hondo a la vista que no declara, falta."""
    m = (vio.get("pintado") or {}).get("mapa") or {}
    if not (m.get("honda") or {}).get("pinta"):
        return
    hr = [p for p in vio.get("honda") or [] if p.get("cuerpo")][: 1 + (vio.get("recibidos") or {}).get("honda", 0)]
    fotos: dict = {}
    for p in hr:
        for x in p["cuerpo"].get("fotos") or []:
            fotos[(x["venue"], x["ts"])] = x
    por = honda_por_venue(list(fotos.values()))
    eje, guardado, paso = m.get("eje") or {}, PASO_GUARDADO[e["activo"]], e["paso"]
    malos, ncol, nviv, nceldas = [], 0, 0, 0
    for c in m.get("columnas") or []:
        if c["estado"] != "foto":
            continue
        t, alc = epoch_ms(c["ts"]), c.get("alcance") or {}
        ex = extras_honda(por, e["venues"], t, alc, paso, guardado)
        dice = sorted((h["venue"], round(h["edad_s"], 3)) for h in c.get("honda") or [])
        quiere = sorted((v, round(a, 3)) for v, a, _ in ex)
        ncol += 1 if quiere else 0
        nviv += 1 if quiere and c["origen"] == "vivo" else 0
        if dice != quiere:
            malos.append(f"{c['ts']} ({c['origen']}) declara honda {dice} y la regla da {quiere}")
            continue
        fuera = lambda k, alc=alc: all(not (lo <= k <= hi) for lo, hi in alc.values())  # noqa: E731
        esp: dict = {}
        for _, _, niv in ex:
            for k, (qc, qv) in niv.items():
                if fuera(k):
                    x = esp.setdefault(k, [0.0, 0.0, 0])
                    x[0], x[1], x[2] = x[0] + qc, x[1] + qv, x[2] + 1
        dec = {x[0]: x for x in c.get("celdas") or []}
        for k, (qc, qv, h) in esp.items():
            if not (eje.get("lo", k) <= k <= eje.get("hi", k)):
                continue
            nceldas += 1
            x = dec.get(k)
            if x is None or abs(x[1] - qc) > 1e-6 * max(1, qc) or abs(x[2] - qv) > 1e-6 * max(1, qv) or x[6] != h:
                malos.append(f"{c['ts']} ({c['origen']}) nivel {k}: declara "
                             f"{'nada' if x is None else [x[1], x[2], x[6]]} y la capa honda da {[qc, qv, h]}")
                break
        for k, x in dec.items():
            if fuera(k) and k not in esp and x[6]:
                malos.append(f"{c['ts']} ({c['origen']}) nivel {k}: declara h={x[6]} y la capa honda no lo conoce")
                break
    if malos:
        rojos.append(f"(F) {pref} la capa honda del vivo no es la servida ({len(malos)} columna(s)): {malos[0]}")
    info.append(f"(F) {pref} capa honda del vivo: {len(hr)} respuesta(s), {ncol} columna(s) a la vista con honda "
                f"({nviv} del vivo), {nceldas} nivel(es) solo hondos comparados")


def juzga_vivo(vio: dict, e: dict, rojos: list, nomed: list, info: list, pref: str, casa) -> None:
    """(C) el canal que dice == el de la red; y la escalera == la de los mensajes que la pagina proceso: los primeros N
    marcos del websocket o las primeras N respuestas del sondeo (N lo cuenta la propia pagina al congelarse)."""
    rec = vio.get("recibidos") or {}
    # lo que dice es lo que se LEE en la pantalla («vivo por WEBSOCKET» / «vivo por SONDEO»), y su data-canal lo repite
    texto = (vio.get("canal") or {}).get("texto") or ""
    dice = "websocket" if "vivo por WEBSOCKET" in texto else "sondeo" if "vivo por SONDEO" in texto else None
    if dice != (vio.get("canal") or {}).get("dice"):
        rojos.append(f"(C) {pref} escribe «{texto[:70]}» y declara data-canal={(vio.get('canal') or {}).get('dice')!r}")
        return
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
    vio["ultimos_tipos"] = [(v, m.get("tipo")) for v, m in ultimo.items()]
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
    juzga_escalera(vio, e, libros, estados, rojos, info, pref, casa, nomed)
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
    h1 = datetime.fromisoformat(HASTA_R1.replace("Z", "+00:00")).strftime("%Y-%m-%dT%H:%M:%SZ") if HASTA_R1 else h
    # (vista, su pantalla en px CSS, su devicePixelRatio, lo que su pagina TIENE que recortar por R1: las columnas "x" y
    # los niveles "y", porque no caben a 2 px de pantalla por celda; DPR 0.5 es el zoom del navegador al 50 %)
    vistas = [(f"#BTC/perp/hasta={h}/ver=90", ANCHO, ALTO, 1, ""),
              (f"#ETH/okx_swap/1/30m/unidad=usd/hasta={h}/ver=90", ANCHO, ALTO, 1, ""),
              ("#BTC/perp/ver=90", ANCHO, ALTO, 1, ""),
              # (149 r2) el raton quieto tambien en la pantalla chica: alli la cabecera pasaba de 3 a 4 lineas y la fila bajaba
              # 18 px. En vivo, BTC: el banco solo trae avisos de BTC; contra produccion esta vista puede ser de ETH
              ("#BTC/perp/ver=90", 1366, 768, 1, ""),
              (f"#BTC/binance_usdm/hasta={h1}", ANCHO, ALTO, 1, "x"),
              (f"#BTC/perp/4h/hasta={h1}", 1280, 720, 1, "x"),
              (f"#BTC/coinbase/30m/hasta={h1}", 1280, 720, 0.5, "xy")]
    declara = f"ventana del pasado hasta {h} ({'fijada por K111_HASTA' if HASTA else 'la hora entera que acabo hace una hora'})" \
        + (f"; las de R1, hasta {h1} (fijada por K111_HASTA_R1)" if HASTA_R1 else "")
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
    for vista, ancho, alto, dpr, recorta in vistas:
        try:
            vio = asyncio.run(asyncio.wait_for(mira(K, vista, cab, "hasta=" not in vista, ancho, alto, dpr), timeout=180))
        except (K.SystemExit2, TimeoutError, OSError) as exc:
            nomed.append(f"(P) {vista}: la sonda no pudo mirar la pagina ({str(exc)[:120]})")
            continue
        x = juzga_vista(vista, vio, rojos, nomed, info, casa, K110)
        r1 = vio.get("_r1")
        if r1 and "x" in recorta and not r1["ver"] < r1["quiere"]:
            nomed.append(f"(F) [{vista}] R1: la vista ya no ejercita el recorte en {ancho}x{alto} (DPR {dpr}): caben "
                         f"{r1['cx']} columnas y pide {r1['quiere']}")
        if r1 and "y" in recorta and not r1["filas"] < r1["conocidos"]:
            nomed.append(f"(F) [{vista}] R1: la vista ya no ejercita el recorte vertical en {ancho}x{alto} (DPR {dpr}): "
                         f"caben {r1['cy']} niveles y conoce {r1['conocidos']}")
        # LA HUELLA: lo pintado y lo servido de las vistas del pasado (reproducibles), con TODOS los pixeles del mapa; del
        # vivo, solo por que canal dice ir y el estado de cada venue (sus cantidades cambian con cada aviso)
        pin = vio.get("pintado") or {}
        if "hasta=" in vista:
            mapa = {k: v for k, v in (pin.get("mapa") or {}).items() if k != "cuadro"}
            # (149 r3) sin «piezas»: son los ms de cada pieza de pinta() (U7b), cambian en cada corrida
            esc = {k: v for k, v in (pin.get("escalera") or {}).items() if k not in ("cuadro", "ahora_ms", "ms", "piezas")}
            pieza = json.dumps([vista, mapa, esc, vio.get("filas"), [p["url"].split("?", 1)[-1] for p in vio["fotos"]],
                                      [p.get("cuerpo") and {k: v for k, v in p["cuerpo"].items() if k != "as_of"}
                                       for p in vio["fotos"]], sorted((vio.get("pixeles") or {}).items()),
                                      vio.get("pantalla"), vio.get("lienzo"), vio.get("encaje"),
                                      hashlib.sha256(vio.get("rgb") or b"").hexdigest()],
                                     sort_keys=True, default=str)
            huella.update(pieza.encode())
            piezas(vista, pieza)
        elif [ancho, alto] == [ANCHO, ALTO]:  # (149 r2) la vista viva chica solo esta por el raton: no repite el vivo
            # (149 r3) del vivo, solo lo que no depende de la hora del aviso reproducido: el canal y QUE venues. El
            # estado de cada uno y el tipo de su ultimo mensaje si dependen, y movian la huella de un escenario igual
            # (escenario_restaurado, K111-control); lo que condenan ya entra por los rotulos de lo condenado
            pieza = json.dumps([vista, (vio.get("canal") or {}).get("dice"),
                                sorted(str(x.get("venue")) for x in vio.get("ven") or [])])
            huella.update(pieza.encode())
            piezas(vista, pieza)
        if not x or "hasta=" not in vista:
            continue
        try:
            juzga_servido(x, rojos, nomed, info)
        except (Canal, IndexError) as exc:
            nomed.append(f"(S) [{vista}] sin canal a libro_foto: {str(exc)[:160]}")
    # el vivo no entra en la huella (no se repite): entran los rotulos de lo condenado, que si
    piezas("rotulos", json.dumps(sorted({r.split(":", 1)[0] for r in rojos})))
    huella.update(json.dumps(sorted({r.split(":", 1)[0] for r in rojos})).encode())
    cola = f" · sujeto: {sujeto} · {declara} · huella {huella.hexdigest()[:16]}"
    if rojos:
        print(f"ROJO  K111 · el libro pintado no es el servido, o lo servido no es libro_foto · {len(rojos)} hallazgo(s)" + cola)
    elif nomed:
        print(f"NO MEDIDO: K111 · {nomed[0]}" + cola)
    else:
        print("VERDE  K111 · el libro pinta lo que sirve y lo servido es libro_foto: el mapa (cada celda, cuantos la "
              "conocen, lo desconocido, los huecos, el color, y cada pixel de una celda a la vista: lo que no cabe, "
              "recortado y dicho), la escalera (niveles, cantidades, acumuladas, mejores, venues sin libro) y el canal "
              "del vivo" + cola)
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
