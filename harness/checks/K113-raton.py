"""K113 · ayudante: abre /flujo en un Chromium de verdad, le hace GESTOS REALES (Input.dispatchMouseEvent y
dispatchKeyEvent por CDP) y juzga, tras cada uno, el RATON y el ASPECTO contra la especificacion que la campana 148
toma de entregas/20261018-2130-INVESTIGACION-plataformas.md. No importa nada de app/ ni de static/: la geometria, las
cifras (E-04), la regla del texto (F-09), los pasos de color (F-04), los desequilibrios (los de K109), los POC, el CVD de
sesion y la vela y el nivel bajo el cursor se recalculan aqui. De otros checks toma lo puro: el Chromium y el CDP de
K102-mesa.py; casa(), desequilibrios(), estado_sesion() y juzga_tpo() de K109-footprint.py; modelo() de
K112-indicadores.py (las velas que la pagina tiene tras aplicar la historia y cada latido).

LO PINTADO se lee por los contratos de la pagina (FLUJO_PINTADO, FLUJO_CRUZ, FLUJO_FICHA, FLUJO_REGLA, FLUJO_TPO) y no
se cree a pies juntillas: el registro de fillText de cada lienzo (con su fuente y su color), el DOM (la ficha, el menu,
el hash) y las respuestas que llegaron por la red.

LAS VISTAS, RELATIVAS A AHORA (`h` es la hora entera que acabo hace una hora; K113_HASTA la fija):
  (vacio)                             LA VISTA POR OMISION, en vivo, en 1920x1080 (todos los gestos) y en 1366x768
  #BTC/15m/perp/hasta=<h>             otro marco del pasado: lo pintado, la cruz, los modos de la celda y la regla
  #ETH/5m/perp/unidad=usd/hasta=<h>   otro activo, en USD (sin decimales: E-04), en 1366x768
  #BTC/1m/perp/hasta=<h>/modo=tpo/sesiones=1   el TPO, con el mismo convenio del raton

LOS BRAZOS (cualquiera pone ROJO; uno sin canal es NO MEDIDO y un ROJO de otro manda sobre el):
  (P) la pagina  sin excepciones; NINGUN gesto vuelve a pedir la historia (lo servido no cambia por el raton)
  (F) lo pintado == lo servido tras cada gesto: cada nivel con sus cifras, en la fila de su precio, su color y su paso
                 (F-04), los desequilibrios (F-05: negrita y color, o borde sin cifra), el apilado, los POC con su
                 empate (F-07), el contorno que no tapa ninguna cifra (F-08), bid a la izquierda (F-02) y las filas de
                 resumen (F-10), con el CVD de sesion recalculado exacto desde su arranque servido
  (C) la cruz    y la ficha: la vela y el nivel bajo el cursor (E-05: precio redondeado al paso y hora en los ejes, la
                 vertical tambien por los paneles; F-16: la ficha dice esa celda, y #lectura lo mismo)
  (T) el texto   F-09: cada cifra sale si la fila mide >= 10 px y cabe con 4 px de holgura, y no sale si no
  (R) el raton   cada gesto mueve lo que manda y nada mas (I-01, I-02, I-03, I-04, I-05, I-06, I-07, I-08)
  (E) el aspecto E-01 (fondo y contraste), E-02 (comprador y vendedor con dE2000 >= 20 en vision normal y en las tres
                 simulaciones de Machado 2009; el mismo comprador en /libro y en la mesa), E-03, E-04
NO MEDIDO: sin la pagina, o la pagina anterior a OF-6a («FALTA DESPLEGAR») · sin Chromium · sin dato · sin canal.
Uso: K113-raton.py juzga (el entorno lo pone K113-el-raton-y-el-aspecto.sh)
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
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal

AQUI = pathlib.Path(__file__).resolve().parent
H = os.environ.get("K113_HARNESS", "/srv/coinanalyze/harness")
BASE = os.environ.get("K113_BASE", "")  # sin ella: PRODUCCION
DB = os.environ.get("K113_DB", "")
HASTA = os.environ.get("K113_HASTA", "")
ESPERA_VELA_S = float(os.environ.get("K113_ESPERA_VELA", "75"))
RUTA_FP, RUTA_SES, RUTA_PERFIL = "/api" + "/orderflow/footprint", "/api" + "/orderflow/sesiones", "/api" + "/orderflow/perfil"
# LO DECIDIDO, escrito aqui y no leido de la pagina (la investigacion, P2 de la 148 y OF-2):
EJE_P, EJE_T, CABEZA, FILA_RES = 76, 20, 16, 16
FILA_TEXTO, FILA_DEFECTO, ESPACIADO = 10, 12, 81
PASOS, CORTE = 20, 0.98
DECIMALES = {"BTC": 3, "ETH": 2, "SOL": 1}
FAMILIAS = {"perp": ["binance_usdm", "bybit_linear", "okx_swap", "bitget_usdt"],
            "spot": ["binance_spot", "bybit_spot", "okx_spot"], "coinbase": ["coinbase_spot"],
            "deribit": ["deribit_perp"]}
MARCOS = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}
PLANTILLAS = {"dia": ("00:00", "24:00"), "asia": ("00:00", "08:00"), "europa": ("07:00", "16:00"),
              "eeuu": ("13:30", "20:00")}
PASO_ARRANQUE = 100000
TOL = 1.01
MOD = {"": 0, "shift": 8, "ctrl": 2}
TECLAS = {"ArrowLeft": 37, "ArrowRight": 39, "PageUp": 33, "PageDown": 34, "Home": 36, "End": 35, "Escape": 27}
MACHADO = {
    "protanopia": [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
    "deuteranopia": [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]],
    "tritanopia": [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.303900]],
}


def _modulo(nombre: str, fichero: str):
    spec = importlib.util.spec_from_file_location(nombre, AQUI / fichero)
    m = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stderr(io.StringIO()):
        spec.loader.exec_module(m)
    return m


class Canal(Exception):
    pass


def D(x) -> Decimal:
    return Decimal(str(x))


def ms(iso: str) -> int:
    return round(datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp() * 1000)


def isoz(t: int) -> str:
    return datetime.fromtimestamp(t / 1000, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def trae(ruta: str, cab: dict) -> tuple[int, bytes]:
    ctx = ssl.create_default_context()
    ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE  # el certificado de 140 es propio
    try:
        with urllib.request.urlopen(urllib.request.Request(raiz() + ruta, headers=cab), timeout=30, context=ctx) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""


# --------------------------------------------------------------------------------------------- lo puro, propio
def to_fixed(x: float, f: int) -> str:
    """Number.prototype.toFixed de JavaScript: el decimal EXACTO del double, la mitad hacia arriba."""
    q = Decimal(x).quantize(Decimal(1).scaleb(-f), rounding=ROUND_HALF_UP)
    s = format(q, "f")
    return s if not s.startswith("-") or q != 0 else s[1:]


def to_precision1(x: float) -> str:
    """Number.prototype.toPrecision(1) de JavaScript, para lo que redondea a cero (exponencial por debajo de 1e-6)."""
    a = abs(Decimal(x))
    e = a.adjusted()
    m = (a.scaleb(-e)).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    if m == 10:
        m, e = Decimal(1), e + 1
    signo = "-" if x < 0 else ""
    if e < -6:
        return f"{signo}{m}e{e}"
    return signo + (format(m.scaleb(e), "f") if e >= 0 else "0." + "0" * (-e - 1) + str(m))


def cifra_e04(t, dec: int) -> str:
    """E-04, escrito aqui de nuevo: >= 1 000 «1.2K», >= 1 000 000 «1.2M» con un decimal; por debajo, `dec` decimales,
    uno menos por cada cifra entera de mas; lo que no es cero nunca se escribe «0»."""
    x = float(t)
    a = abs(x)
    if x == 0:
        return "0"

    def mil(d: float, suf: str) -> str:
        s = to_fixed(x / d, 1)
        return mil(1e6, "M") if abs(float(s)) >= 1000 and suf == "K" else s + suf
    if a >= 1e6:
        return mil(1e6, "M")
    if a >= 1e3:
        return mil(1e3, "K")
    s = to_fixed(x, max(0, dec - (0 if a < 10 else 1 if a < 100 else 2)))
    if abs(float(s)) >= 1000:
        return mil(1e3, "K")
    return s if float(s) != 0 else to_precision1(x)


def fuente_de(fila: float) -> int:
    return min(13, max(9, round(fila) - 2))


def referencia(valores: list[float]) -> float:
    xs = sorted(abs(v) for v in valores if v != 0)
    return xs[math.ceil(CORTE * len(xs)) - 1] if xs else 0.0


def paso_color(v: float, ref: float) -> int:
    a = abs(v)
    if not ref > 0 or not a > 0:
        return -1
    return min(PASOS - 1, math.floor(PASOS * min(1.0, a / ref)))


def sesion(nombre: str) -> tuple[int, int]:
    """(inicio en minutos del dia, duracion en minutos) de una plantilla o de HH:MM-HH:MM."""
    i, f = PLANTILLAS.get(nombre, tuple(nombre.split("-")))
    a, b = int(i[:2]) * 60 + int(i[3:]), int(f[:2]) * 60 + int(f[3:])
    return a, ((b - a) % 1440) or 1440


def sesion_de(ts_ms: int, ses: tuple[int, int]) -> int | None:
    ini = (ts_ms - ses[0] * 60000) // 86400000 * 86400000 + ses[0] * 60000
    return ini if ts_ms < ini + ses[1] * 60000 else None


def hex_rgb(h: str) -> list[float]:
    h = h.strip().lstrip("#")
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gam(c: float) -> float:
    c = min(1.0, max(0.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def luminancia(rgb: list[float]) -> float:
    r, g, b = (_lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a: list[float], b: list[float]) -> float:
    la, lb = sorted((luminancia(a), luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _lab(rgb: list[float]) -> tuple:
    r, g, b = (_lin(c) for c in rgb)
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116  # noqa: E731
    return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))


def de2000(c1: tuple, c2: tuple) -> float:
    (L1, a1, b1), (L2, a2, b2) = c1, c2
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2)
    Cm = (C1 + C2) / 2
    G = 0.5 * (1 - math.sqrt(Cm ** 7 / (Cm ** 7 + 25 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p, h2p = math.degrees(math.atan2(b1, a1p)) % 360, math.degrees(math.atan2(b2, a2p)) % 360
    dh = 0 if C1p * C2p == 0 else h2p - h1p - 360 if h2p - h1p > 180 else h2p - h1p + 360 if h2p - h1p < -180 else h2p - h1p
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dh / 2))
    Lpm, Cpm = (L1 + L2) / 2, (C1p + C2p) / 2
    hpm = (h1p + h2p if C1p * C2p == 0 else (h1p + h2p) / 2 if abs(h1p - h2p) <= 180
           else (h1p + h2p + 360) / 2 if h1p + h2p < 360 else (h1p + h2p - 360) / 2)
    T = (1 - 0.17 * math.cos(math.radians(hpm - 30)) + 0.24 * math.cos(math.radians(2 * hpm))
         + 0.32 * math.cos(math.radians(3 * hpm + 6)) - 0.20 * math.cos(math.radians(4 * hpm - 63)))
    Rc = 2 * math.sqrt(Cpm ** 7 / (Cpm ** 7 + 25 ** 7))
    Sl = 1 + 0.015 * (Lpm - 50) ** 2 / math.sqrt(20 + (Lpm - 50) ** 2)
    Sc, Sh = 1 + 0.045 * Cpm, 1 + 0.015 * Cpm * T
    Rt = -math.sin(math.radians(60 * math.exp(-(((hpm - 275) / 25) ** 2)))) * Rc
    dCp = C2p - C1p
    return math.sqrt(((L2 - L1) / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))


def simula(rgb: list[float], m: list) -> list[float]:
    li = [_lin(c) for c in rgb]
    return [_gam(sum(m[i][j] * li[j] for j in range(3))) for i in range(3)]


# --------------------------------------------------------------------------------------------- la sonda
INTERCEPTA = r"""
(() => {
  const orig = CanvasRenderingContext2D.prototype.fillText;
  window.__K113 = [];
  CanvasRenderingContext2D.prototype.fillText = function (t, x, y) {
    const m = this.getTransform();
    if (window.__K113.length < 400000) {
      window.__K113.push([String(t), (m.a * x + m.e) / (window.devicePixelRatio || 1), (m.d * y + m.f) / (window.devicePixelRatio || 1),
                          this.canvas ? this.canvas.id : null, this.font, String(this.fillStyle), this.textAlign]);
    }
    return orig.apply(this, arguments);
  };
})();
"""
COSECHA = r"""
(() => {
  window.__K113 = [];
  const h = window.FLUJO_HITOS || {};
  if (h.repinta) h.repinta();
  const caja = (id) => { const e = document.getElementById(id); if (!e) return null; const r = e.getBoundingClientRect();
    return [r.left, r.top, r.width, r.height]; };
  const menu = document.getElementById('menu-eje');
  return {pin: window.FLUJO_PINTADO || null, cruz: window.FLUJO_CRUZ || null, ficha: window.FLUJO_FICHA || null,
          regla: window.FLUJO_REGLA || null, tpo: window.FLUJO_TPO || null, ind: window.FLUJO_INDICADORES || null,
          hitos: {listo: h.listo, vista: h.vista, aplicadas: h.aplicadas || [], arranques: h.arranques, of6a: h.of6a},
          textos: window.__K113, hash: location.hash, lienzo: caja('lienzo'), ind_caja: caja('lienzo-ind'),
          ficha_dom: (() => { const f = document.getElementById('ficha'); return f && !f.hidden ? f.innerText : null; })(),
          lectura: (document.getElementById('lectura') || {}).textContent || '',
          menu: menu ? !menu.hidden : null, presente: (document.getElementById('b-presente') || {}).className || ''};
})()
"""
LISTO = ("!!(window.FLUJO_HITOS && FLUJO_HITOS.listo && (location.hash.includes('modo=tpo') || "
         "(FLUJO_HITOS.indicadores !== false && FLUJO_HITOS.arranques !== false)))")


class Vista:
    """Una pagina abierta en su Chromium: los gestos, la red y la cosecha."""

    def __init__(self, K, s):
        self.K, self.s, self.red, self.vistos = K, s, {}, 0

    async def evalua(self, expr: str):
        return await self.s.evalua(expr)

    async def raton(self, tipo: str, x: float, y: float, **kw):
        await self.s.pide("Input.dispatchMouseEvent", type=tipo, x=float(x), y=float(y), **kw)

    async def mueve(self, x, y):
        await self.raton("mouseMoved", x, y)
        await self.s.drena(0.15)

    async def rueda(self, x, y, dy, mod=""):
        await self.raton("mouseWheel", x, y, deltaX=0, deltaY=float(dy), modifiers=MOD[mod])
        await self.s.drena(0.25)

    async def arrastra(self, x0, y0, x1, y1, mod="", pasos=10):
        m = MOD[mod]
        await self.raton("mouseMoved", x0, y0, modifiers=m)
        await self.raton("mousePressed", x0, y0, button="left", clickCount=1, modifiers=m)
        for k in range(1, pasos + 1):
            await self.raton("mouseMoved", x0 + (x1 - x0) * k / pasos, y0 + (y1 - y0) * k / pasos, button="left",
                             buttons=1, modifiers=m)
        await self.raton("mouseReleased", x1, y1, button="left", clickCount=1, modifiers=m)
        await self.s.drena(0.3)

    async def clic(self, x, y, boton="left", veces=1):
        for n in range(1, veces + 1):
            await self.raton("mousePressed", x, y, button=boton, clickCount=n)
            await self.raton("mouseReleased", x, y, button=boton, clickCount=n)
        await self.s.drena(0.3)

    async def clic_en(self, selector: str, boton="left"):
        r = await self.evalua(f"(() => {{ const e = document.querySelector({json.dumps(selector)}); if (!e) return null; "
                              "const r = e.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; })()")
        if not r:
            raise Canal(f"no hay {selector} en la pagina")
        await self.clic(r[0], r[1], boton)

    async def tecla(self, nombre: str):
        for t in ("keyDown", "keyUp"):
            await self.s.pide("Input.dispatchKeyEvent", type=t, key=nombre, code=nombre,
                              windowsVirtualKeyCode=TECLAS.get(nombre, 0))
        await self.s.drena(0.3)

    async def cosecha(self) -> dict:
        await self.s.drena(0.2)
        c = await self.evalua(COSECHA)
        await self.recoge_red()
        c["red"] = list(self.red.values())
        return c

    async def recoge_red(self):
        for e in self.s.eventos[self.vistos:]:
            p, m = e.get("params", {}), e.get("method")
            if m == "Network.requestWillBeSent" and "/api" + "/orderflow/" in p["request"]["url"]:
                u = urllib.parse.urlparse(p["request"]["url"])
                self.red[p["requestId"]] = {"ruta": u.path, "q": {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()},
                                            "estado": None, "cuerpo": None, "t": p.get("timestamp")}
            elif m == "Network.loadingFinished" and p.get("requestId") in self.red:
                self.red[p["requestId"]]["fin"] = True
            elif m == "Network.responseReceived" and p.get("requestId") in self.red:
                self.red[p["requestId"]]["estado"] = p["response"]["status"]
        self.vistos = len(self.s.eventos)
        for rid, x in self.red.items():
            if x["estado"] == 200 and x.get("fin") and x["cuerpo"] is None:
                try:
                    r = await self.s.pide("Network.getResponseBody", requestId=rid)
                    x["cuerpo"] = json.loads(base64.b64decode(r["body"]) if r.get("base64Encoded") else r["body"])
                except (self.K.SystemExit2, ValueError, KeyError):
                    x["cuerpo"] = {}

    def excepciones(self) -> list[str]:
        return [json.dumps(e["params"].get("exceptionDetails", {}))[:300] for e in self.s.eventos
                if e.get("method") == "Runtime.exceptionThrown"]


async def abre(K, vista: str, ancho: int, alto: int, cab: dict, recorrido) -> dict:
    """Abre la vista, espera a que este pintada y le pasa el recorrido de gestos; devuelve lo cosechado."""
    with K.Chromium(ancho, alto) as c:
        req = urllib.request.Request(f"http://127.0.0.1:{c.puerto}/json/new?about:blank", method="PUT")
        with urllib.request.urlopen(req, timeout=10) as r:
            destino = json.load(r)
        async with K.websockets.connect(destino["webSocketDebuggerUrl"], max_size=300 * 1024 * 1024) as ws:
            s = K.Sesion(ws)
            for metodo in ("Page.enable", "Runtime.enable", "Network.enable"):
                await s.pide(metodo)
            await s.pide("Network.setCacheDisabled", cacheDisabled=True)
            await s.pide("Emulation.setDeviceMetricsOverride", width=ancho, height=alto, deviceScaleFactor=1, mobile=False)
            if cab:
                await s.pide("Network.setExtraHTTPHeaders", headers=cab)
            await s.pide("Page.addScriptToEvaluateOnNewDocument", source=INTERCEPTA)
            await s.pide("Page.navigate", url=f"{raiz()}/flujo{vista}")
            v = Vista(K, s)
            listo = False
            for _ in range(300):
                await s.drena(0.2)
                with contextlib.suppress(K.SystemExit2):
                    listo = await s.evalua(LISTO)
                if listo:
                    break
            await s.drena(0.8)
            out = {"vista": vista, "pantalla": [ancho, alto], "listo": listo, "pasos": []}
            if listo:
                await recorrido(v, out)
            out["excepciones"] = v.excepciones()
            await s.cierra()
    return out


# --------------------------------------------------------------------------------------------- el juicio
class Juez:
    """Lo que se condena, por brazo; y lo que se dice."""

    def __init__(self):
        self.malos = {b: [] for b in "PFCTRE"}
        self.info: list[str] = []
        self.pasos = 0

    def mal(self, brazo: str, pref: str, texto: str):
        self.malos[brazo].append(f"{pref} {texto}")


def pedidas_historia(red: list) -> list:
    fp = [x for x in red if x["ruta"] == RUTA_FP]
    if not fp:
        return []
    q0 = fp[0]["q"]
    return [x for x in fp if x["q"].get("desde") == q0.get("desde") and x["q"].get("hasta") == q0.get("hasta")]


def velas_aplicadas(c: dict, K112, marco: str) -> list:
    por = {(x["ruta"], (x.get("cuerpo") or {}).get("as_of")): x for x in c["red"] if x.get("cuerpo")}
    cuerpos = [por[(RUTA_FP, a["as_of"])]["cuerpo"] for a in c["hitos"]["aplicadas"]
               if a.get("ruta") == RUTA_FP and (RUTA_FP, a.get("as_of")) in por]
    velas = K112.modelo(cuerpos, marco) if cuerpos else []
    for x in velas:
        x["estado"] = x["_est"][0]
    return velas


def geo(pin: dict) -> dict:
    e = pin["escala"]
    ancho = pin["ancho"] - EJE_P
    bs = ancho / pin["ver"]
    return {"ancho": ancho, "bs": bs, "x": lambda i: ancho - (pin["fin"] - i + 0.5) * bs, "arriba": e["arriba"],
            "abajo": e["abajo"], "lo": e["lo"], "hi": e["hi"],
            "y": lambda p: e["arriba"] + (e["hi"] - float(p)) / (e["hi"] - e["lo"]) * (e["abajo"] - e["arriba"])}


async def anchos(v: Vista, piezas: set) -> dict:
    """El ancho de cada (texto, fuente) medido en la pagina con un lienzo propio (no con el de la pagina)."""
    if not piezas:
        return {}
    lista = sorted(piezas)
    r = await v.evalua("(() => { const c = document.createElement('canvas').getContext('2d'); return "
                       + json.dumps(lista) + ".map(([t, f]) => { c.font = f; return c.measureText(t).width; }); })()")
    return dict(zip(lista, r, strict=True))


def textos_de(c: dict, lienzo: str) -> list:
    return [t for t in c["textos"] if t[3] == lienzo]


def esperado_celda(nv: dict, modo: str, dec: int, des: tuple) -> tuple:
    """Lo que la celda tendria que escribir en su modo: ((texto, fuente, lado)...)."""
    dc, dv = des[0], des[1]
    if modo == "bidask":
        return ((cifra_e04(nv["venta"], dec), dv, "venta"), (cifra_e04(nv["compra"], dec), dc, "compra"))
    if modo == "perfil":
        return ()
    d = float(nv["delta"])
    t = ((("+" if d > 0 else "") + cifra_e04(nv["delta"], dec)) if modo == "delta"
         else cifra_e04(nv["operaciones"], 0) if modo == "trades" else cifra_e04(nv["total"], dec))
    return ((t, modo == "delta" and (dc or dv), "uno"),)


async def juzga_footprint(v: Vista, c: dict, e: dict, K109, K112, J: Juez, pref: str, arranques: dict) -> dict:
    """(F), (T) y (E) de lo que el footprint acaba de pintar, contra lo servido que la pagina aplico."""
    pin = c["pin"]
    if not pin or not pin.get("velas") or not pin.get("escala"):
        J.mal("F", pref, "el contrato no dice lo pintado (sin velas o sin escala)")
        return {}
    velas = velas_aplicadas(c, K112, e["marco"])
    if not velas:
        J.mal("F", pref, "la pagina no aplico ninguna respuesta del footprint")
        return {}
    por_ts = {ms(x["ts"]): (i, x) for i, x in enumerate(velas)}
    g = geo(pin)
    esc = pin["escala"]
    paso = D(pin["paso"])
    pf = float(paso)
    dec = 0 if pin.get("unidad") == "usd" else DECIMALES.get(pin.get("activo"), 2)
    fila = esc["fila"]
    fuente = fuente_de(fila)
    if esc.get("fuente") != fuente:
        J.mal("T", pref, f"la fuente de las celdas es de {esc.get('fuente')} px con filas de {fila:.1f} y tiene que ser de {fuente}")
    if abs((esc["hi"] - esc["lo"]) - (esc["abajo"] - esc["arriba"]) / fila * pf) > 1e-6 * max(1, esc["hi"]) or \
            abs(esc["centro"] - (esc["hi"] + esc["lo"]) / 2) > 1e-6 * max(1, esc["hi"]):
        J.mal("F", pref, f"la escala del precio no es la de su centro y su fila ({esc})")
    if esc.get("modo") == "auto":
        ult = next((por_ts[ms(r["ts"])][1] for r in reversed(pin["velas"]) if ms(r["ts"]) in por_ts
                    and por_ts[ms(r["ts"])][1]["niveles"]), None)
        if ult is not None:
            a_, b_ = float(ult["niveles"][0]["nivel"]), float(ult["niveles"][-1]["nivel"]) + pf
            borde = (esc["hi"] - esc["lo"]) * 0.1
            if not (a_ >= esc["lo"] + borde - 1e-9 and b_ <= esc["hi"] - borde + 1e-9) and \
                    abs(esc["centro"] - (a_ + b_) / 2) > 1e-6 * max(1.0, esc["centro"]):
                J.mal("R", pref, f"escala AUTO y la ultima vela a la vista ({ult['ts'][11:16]}, {a_:g}-{b_:g}) ni cabe lejos "
                                 f"del borde de {esc['lo']:.6g}-{esc['hi']:.6g} ni esta centrada en ella")
    textos = textos_de(c, "lienzo")
    # las referencias del color (F-04), las mias
    campo = "total" if pin.get("color_modo") == "volumen" else "delta"
    vis_idx = [por_ts[ms(r["ts"])][0] for r in pin["velas"] if ms(r["ts"]) in por_ts]
    ref_modo = pin.get("referencia", "vela")
    ses = sesion(e.get("sesion", "dia"))
    if ref_modo == "visible":
        rv = referencia([float(nv[campo]) for i in vis_idx for nv in velas[i]["niveles"]])
    elif ref_modo == "sesion":
        grupos: dict = {}
        for x in velas:
            grupos.setdefault(sesion_de(ms(x["ts"]), ses), []).append(x)
        rses = {s: referencia([float(nv[campo]) for x in xs for nv in x["niveles"]]) for s, xs in grupos.items()}
    # lo que hay que medir (F-09)
    piezas, plan = set(), []
    numeros = pin.get("numeros", True) is not False
    for r in pin["velas"]:
        i, x = por_ts.get(ms(r["ts"]), (None, None))
        if x is None:
            J.mal("F", pref, f"vela {r['ts']} pintada y no servida")
            continue
        w = max(1, math.floor(g["bs"] * 0.86))
        if r["ancho"] != w or abs(r["x0"] - round(g["x"](i) - w / 2)) > TOL:
            J.mal("R", pref, f"vela {r['ts'][11:16]}: su columna {r['x0']}+{r['ancho']} no es la de su espaciado "
                             f"({round(g['x'](i) - w / 2)}+{w})")
        sn = {D(n["nivel"]): n for n in x["niveles"]}
        pn = {D(n["nivel"]): n for n in r["niveles"]}
        if set(sn) != set(pn):
            J.mal("F", pref, f"vela {r['ts'][11:16]}: niveles pintados {len(pn)} != servidos {len(sn)}")
            continue
        orden = sorted(sn)
        des = dict(zip(orden, K109.desequilibrios([(n, D(sn[n]["compra"]), D(sn[n]["venta"])) for n in orden], paso),
                       strict=True))
        ref = (referencia([float(nv[campo]) for nv in x["niveles"]]) if ref_modo == "vela" else rv if ref_modo == "visible"
               else rses.get(sesion_de(ms(x["ts"]), ses), 0.0))
        tot = {n: D(sn[n]["total"]) for n in orden}
        mx = max(tot.values()) if tot else None
        if sorted(D(p["nivel"]) for p in r.get("pocs") or []) != sorted(n for n in orden if tot[n] == mx):
            J.mal("F", pref, f"vela {r['ts'][11:16]}: los POC pintados {[p['nivel'] for p in r.get('pocs') or []]} no son "
                             f"los niveles de mas volumen {[str(n) for n in orden if tot[n] == mx]} (F-07: con empate, todos)")
        for n in orden:
            f, s_ = pn[n], sn[n]
            if any(D(f[k]) != D(s_[k]) for k in ("venta", "compra", "delta", "total")) or str(f.get("operaciones")) != str(s_["operaciones"]):
                J.mal("F", pref, f"vela {r['ts'][11:16]} nivel {n}: pinta {f['venta']}/{f['compra']} y se sirvio "
                                 f"{s_['venta']}/{s_['compra']}")
                continue
            if abs(f["y0"] - g["y"](n + paso)) > TOL or abs(f["y1"] - g["y"](n)) > TOL:
                J.mal("F", pref, f"vela {r['ts'][11:16]} nivel {n}: su fila {f['y0']}-{f['y1']} no es la de su precio "
                                 f"({g['y'](n + paso):.1f}-{g['y'](n):.1f})")
            d = des[n]
            if (f["dc"], f["dv"], f["ac"], f["av"]) != d:
                J.mal("F", pref, f"vela {r['ts'][11:16]} nivel {n}: desequilibrios {(f['dc'], f['dv'], f['ac'], f['av'])} y la "
                                 f"regla (F-05) da {d}")
            dentro = f["filtro"] != "escondida" and not (f["y1"] < esc["arriba"] - 1 or f["y0"] > esc["abajo"] + 1)
            k = paso_color(float(s_[campo]), ref) if dentro else -1
            if f.get("paso_color") != k:
                J.mal("F", pref, f"vela {r['ts'][11:16]} nivel {n}: paso de color {f.get('paso_color')} y su {campo} contra la "
                                 f"referencia ({ref_modo}, {ref:.6g}) da {k} (F-04)")
            exp = esperado_celda(s_, pin.get("celda", "bidask"), dec, d)
            cand = numeros and fila >= FILA_TEXTO and dentro and f["filtro"] != "atenuada" and bool(exp)
            for t, negrita, _lado in exp:
                piezas.add((t, f"{'bold ' if negrita else ''}{fuente}px ui-monospace, monospace"))
            plan.append((r, w, n, f, s_, exp, cand, d))
    medidas = await anchos(v, piezas)
    n_textos = 0
    for r, w, n, f, _s, exp, cand, d in plan:
        quien = f"vela {r['ts'][11:16]} nivel {n}"
        xc = r["x0"] + w / 2
        if exp and exp[0][2] != "uno":
            cabe = cand and all(medidas[(t, f"{'bold ' if ng else ''}{fuente}px ui-monospace, monospace")] + 4 <= w / 2
                                for t, ng, _ in exp)
            pintados = (f.get("texto_venta"), f.get("texto_compra"))
            quiero = (exp[0][0], exp[1][0]) if cabe else (None, None)
        else:
            cabe = cand and all(medidas[(t, f"{'bold ' if ng else ''}{fuente}px ui-monospace, monospace")] + 4 <= w
                                for t, ng, _ in exp)
            pintados = (f.get("texto"),)
            quiero = (exp[0][0],) if cabe and exp else (None,)
        if pintados != quiero:
            J.mal("T", pref, f"{quien}: escribe {pintados} y con fila de {fila:.1f} px y celda de {w} px tiene que escribir "
                             f"{quiero} (F-09: la cifra sale si cabe y no sale si no)")
            continue
        for (t, negrita, lado), p in zip(exp, pintados, strict=False):
            if p is None:
                continue
            n_textos += 1
            alinea = "left" if lado == "compra" else "right"
            reg = [x for x in textos if x[0] == p and abs(x[2] - (f["y0"] + f["y1"]) / 2) <= TOL and
                   r["x0"] - TOL <= x[1] <= r["x0"] + w + TOL and x[6] == alinea]
            if not reg:
                J.mal("F", pref, f"{quien}: el contrato dice «{p}» y el lienzo no lo escribio en su fila")
                continue
            x_ = reg[0]
            ancho_t = medidas[(t, f"{'bold ' if negrita else ''}{fuente}px ui-monospace, monospace")]
            if lado == "venta" and not (x_[6] == "right" and x_[1] <= xc and x_[1] - ancho_t >= r["x0"]):
                J.mal("E", pref, f"{quien}: la venta (bid) no esta a la izquierda del eje de la vela (F-02)")
            if lado == "compra" and not (x_[6] == "left" and x_[1] >= xc and x_[1] + ancho_t <= r["x0"] + w):
                J.mal("E", pref, f"{quien}: la compra (ask) no esta a la derecha del eje de la vela (F-02)")
            izq = x_[1] - (ancho_t if x_[6] == "right" else 0)
            co = r.get("contorno") or {}
            if co and not (co["x0"] < izq and izq + ancho_t < co["x1"]):
                J.mal("E", pref, f"{quien}: el contorno de la vela ({co['x0']}-{co['x1']}) tapa la cifra «{p}» (F-08)")
            fuerte = (lado == "venta" and d[1]) or (lado == "compra" and d[0]) or (lado == "uno" and negrita)
            if fuerte != ("bold" in x_[4]):
                J.mal("F", pref, f"{quien}: «{p}» {'sin' if fuerte else 'en'} negrita y {'es' if fuerte else 'no es'} un "
                                 "desequilibrio de su lado (F-05)")
        if (d[0] or d[1]) and all(p is None for p in pintados) and f["filtro"] not in ("escondida",) and \
                not (f["y1"] < esc["arriba"] - 1 or f["y0"] > esc["abajo"] + 1) and not f.get("borde"):
            J.mal("F", pref, f"{quien}: desequilibrio sin cifra y sin su borde de 1 px (F-05)")
    return {"velas": velas, "n_textos": n_textos, "g": g}


def cvd_sesion(velas: list, ses: tuple, arranques: dict) -> list:
    """F-10, escrito aqui de nuevo (en Decimal): [(valor | None, estado | None)] por vela."""
    t0 = ms(velas[0]["ts"]) if velas else 0
    actual, acum, estado, out = "nada", None, None, []
    for x in velas:
        s = sesion_de(ms(x["ts"]), ses)
        if s != actual:
            actual, acum, estado = s, None, "completa"
            if s is not None and s >= t0:
                acum = Decimal(0)
            elif s is not None:
                a = arranques.get(s)
                if a and a.get("delta") is not None:
                    acum = D(a["delta"])
                    if a["estado"] != "completa":
                        estado = "incompleta"
                elif a and a.get("estado") == "hueco":
                    acum, estado = Decimal(0), "incompleta"
        if s is None or acum is None:
            out.append((None, None))
            continue
        if x["estado"] == "hueco":
            estado = "incompleta"
            out.append((None, None))
            continue
        if x["estado"] == "incompleta":
            estado = "incompleta"
        acum += D(x["delta"])
        out.append((acum, estado))
    return out


def arranques_de(c: dict, K109, e: dict) -> dict:
    """El arranque del CVD de sesion que la pagina pidio (/sesiones con PASO_ARRANQUE veces el paso base)."""
    out = {}
    ses = sesion(e.get("sesion", "dia"))
    for x in c["red"]:
        if x["ruta"] != RUTA_SES or not x.get("cuerpo"):
            continue
        cu = x["cuerpo"]
        if D(x["q"].get("paso", "0")) != D(cu.get("paso_base", "-1")) * PASO_ARRANQUE:
            continue
        hasta = ms(x["q"]["hasta"])
        for s in cu.get("sesiones") or []:
            ini = ms(s["inicio"])
            if ini == sesion_de(hasta - 60000, ses):
                out[ini] = {"delta": s.get("delta"), "estado": K109.estado_sesion(s)[0]}
    return out


async def juzga_resumen(v: Vista, c: dict, e: dict, velas: list, arranques: dict, J: Juez, pref: str) -> int:
    pin = c["pin"]
    filas = pin.get("filas_resumen") or []
    if pin["escala"].get("resumen") != len(filas) * FILA_RES:
        J.mal("F", pref, f"las filas de resumen ocupan {pin['escala'].get('resumen')} px y son {len(filas)} de {FILA_RES}")
    if not filas:
        return 0
    cvd = cvd_sesion(velas, sesion(e.get("sesion", "dia")), arranques)
    por_ts = {ms(x["ts"]): i for i, x in enumerate(velas)}
    dec = 0 if pin.get("unidad") == "usd" else DECIMALES.get(pin.get("activo"), 2)
    plan, piezas = [], set()
    for r in pin["velas"]:
        i = por_ts.get(ms(r["ts"]))
        if i is None:
            continue
        x = velas[i]
        res = r.get("resumen") or {}
        val = res.get("valores") or {}
        hueco = x["estado"] == "hueco"
        tot = float(x["total"])
        quiero = {"vol": None if hueco else x["total"], "delta": None if hueco else x["delta"],
                  "deltap": None if hueco or not tot else (float(x["delta"]) / tot) * 100,
                  "cvd": cvd[i][0], "ops": None if hueco else str(x["operaciones"])}
        for f in filas:
            a, b = val.get(f), quiero[f]
            igual = (a is None and b is None) or (a is not None and b is not None and (
                abs(float(a) - b) <= 1e-9 * max(1.0, abs(b)) if f == "deltap" else D(a) == D(b)))
            if not igual:
                J.mal("F", pref, f"vela {r['ts'][11:16]}: la fila {f} vale {a} y lo servido da {b} (F-10)")
                continue
            if b is None:
                continue
            xv = float(b)
            t = (to_fixed(xv, 1) + "%" if f == "deltap" else cifra_e04(b, 0) if f == "ops" else
                 ("+" if f in ("delta", "cvd") and xv > 0 else "") + cifra_e04(b, dec))
            piezas.add((t, "9px ui-monospace, monospace"))
            plan.append((r, f, t))
        if "cvd" in filas and res.get("cvd_estado") != cvd[i][1]:
            J.mal("F", pref, f"vela {r['ts'][11:16]}: el CVD de sesion se dice {res.get('cvd_estado')} y es {cvd[i][1]}")
    medidas = await anchos(v, piezas)
    clave = {"vol": "total", "ops": "operaciones"}
    escritas = 0
    for r, f, t in plan:
        p = (r.get("resumen") or {}).get(clave.get(f, f))
        cabe = medidas[(t, "9px ui-monospace, monospace")] + 4 <= r["ancho"]
        if p != (t if cabe else None):
            J.mal("T", pref, f"vela {r['ts'][11:16]}: la fila {f} escribe {p} y en {r['ancho']} px tiene que escribir "
                             f"{t if cabe else None}")
        elif p is not None:
            escritas += 1
    return escritas


def bajo(pin: dict, x: float, y: float) -> tuple:
    """La vela (indice) y el nivel (texto) bajo un punto del lienzo del footprint, con mi aritmetica."""
    g = geo(pin)
    i = math.floor(pin["fin"] - (g["ancho"] - x) / g["bs"] + 0.5 + 0.5)
    paso = D(pin["paso"])
    if not g["arriba"] <= y < g["abajo"]:
        return i, None
    precio = D(repr(g["lo"])) + (D(repr(g["abajo"])) - D(repr(y))) / (D(repr(g["abajo"])) - D(repr(g["arriba"]))) * \
        (D(repr(g["hi"])) - D(repr(g["lo"])))
    nivel = (precio / paso + Decimal("1e-9")).to_integral_value(rounding=ROUND_FLOOR) * paso
    return i, format(nivel.quantize(paso), "f")


def juzga_cruz(c: dict, velas: list, x: float, y: float, J: Juez, pref: str, sobre: str = "grafico") -> None:
    """(C): la cruz y la ficha dicen la vela y la celda que hay bajo (x, y) (coordenadas del lienzo)."""
    pin, cruz, ficha = c["pin"], c["cruz"] or {}, c["ficha"] or {}
    i, nivel = bajo(pin, x, y)
    if not 0 <= i < len(velas):
        J.mal("C", pref, f"bajo ({x:.0f}, {y:.0f}) no hay vela y la cruz dice {cruz.get('vela')}")
        return
    v = velas[i]
    g = geo(pin)
    if not cruz.get("visible") or ms(cruz.get("vela") or "1970-01-01T00:00:00Z") != ms(v["ts"]):
        J.mal("C", pref, f"la cruz en ({x:.0f}, {y:.0f}) dice la vela {cruz.get('vela')} y es la de {v['ts'][11:16]}")
        return
    if abs(cruz.get("x_lienzo", -1e9) - g["x"](i)) > TOL:
        J.mal("C", pref, f"la vertical de la cruz esta en x {cruz.get('x_lienzo')} y su vela en {g['x'](i):.1f}")
    hora = v["ts"][5:10] if pin["marco"] == "1d" else v["ts"][5:10] + " " + v["ts"][11:16] if pin["marco"] == "4h" \
        else v["ts"][11:16]
    cr = textos_de(c, "cruz")
    escrita = [round(t[1], 1) for t in cr if t[0] == cruz.get("texto_hora")]
    if cruz.get("texto_hora") != hora or not any(abs(x_ - cruz.get("x", -1e9)) <= TOL for x_ in escrita):
        J.mal("C", pref, f"la etiqueta de hora de la cruz dice «{cruz.get('texto_hora')}» escrita en x {escrita} y su vela es "
                         f"la de {hora}, en x {cruz.get('x')} (E-05: la cruz sobre la vela bajo el cursor)")
    if sobre == "grafico":
        if cruz.get("nivel") != nivel or cruz.get("texto_precio") != nivel or \
                not any(t[0] == nivel and abs(t[2] - cruz.get("y", -1e9)) <= TOL for t in cr):
            J.mal("C", pref, f"la etiqueta de precio de la cruz en y {y:.0f} dice «{cruz.get('texto_precio')}» y la fila es "
                             f"la de {nivel} (E-05: el precio de la fila redondeado al paso)")
        celda = next((n for n in v["niveles"] if D(n["nivel"]) == D(nivel)), None) if nivel else None
        if not ficha.get("visible") or ms(ficha.get("vela") or "1970-01-01T00:00:00Z") != ms(v["ts"]) or \
                (ficha.get("nivel") is None) != (celda is None) or (celda and D(ficha["nivel"]) != D(celda["nivel"])):
            J.mal("C", pref, f"la ficha dice la vela {ficha.get('vela')} nivel {ficha.get('nivel')} y bajo el cursor esta "
                             f"{v['ts'][11:16]} nivel {celda and celda['nivel']} (F-16)")
            return
        lineas = ficha.get("lineas") or []
        if celda and not any(f"venta {celda['venta']} × compra {celda['compra']}" in x_ for x_ in lineas):
            J.mal("C", pref, f"la ficha de {v['ts'][11:16]} nivel {nivel} no dice la venta y la compra servidas "
                             f"({celda['venta']} × {celda['compra']})")
        if celda and not any(f"Δ {celda['delta']} · volumen {celda['total']} · {celda['operaciones']} operaciones" in x_
                             for x_ in lineas):
            J.mal("C", pref, f"la ficha de {v['ts'][11:16]} nivel {nivel} no dice su delta, volumen y operaciones servidos")
        if (c.get("ficha_dom") or "").replace("\n", " · ") != " · ".join(lineas) or c.get("lectura") != " · ".join(lineas):
            J.mal("C", pref, "la ficha del DOM o #lectura no dicen lo que dice el contrato de la ficha")
    elif cruz.get("sobre") != "panel" or not cruz.get("texto_valor") or \
            not any(t[0] == cruz["texto_valor"] for t in cr):
        J.mal("C", pref, f"sobre el panel la cruz dice {cruz.get('sobre')} y su valor «{cruz.get('texto_valor')}» no esta "
                         "escrito (E-05: la cruz sigue por los paneles)")


def estado_ejes(c: dict) -> dict:
    p = c["pin"] or {}
    e = p.get("escala") or {}
    return {"ver": p.get("ver"), "fin": p.get("fin"), "lo": e.get("lo"), "hi": e.get("hi"), "fila": e.get("fila"),
            "centro": e.get("centro"), "modo": e.get("modo"), "sigue": p.get("sigue"), "n": p.get("n"),
            "paso": float(p.get("paso") or 1), "hash": c.get("hash")}


def igual(a, b, tol=1e-6) -> bool:
    return a is not None and b is not None and abs(a - b) <= tol * max(1.0, abs(a), abs(b))


# --------------------------------------------------------------------------------------------- los recorridos
def punto_celda(pin: dict) -> tuple | None:
    """Un punto del lienzo sobre una celda con cifras de una vela del medio (o, sin cifras, sobre una celda)."""
    vel = pin.get("velas") or []
    e = pin["escala"]
    dentro = lambda f: e["arriba"] + 1 < f["y0"] and f["y1"] < e["abajo"] - 1  # noqa: E731 - la fila entera en el grafico
    for r in vel[len(vel) // 2:] + vel[:len(vel) // 2]:
        for f in r["niveles"]:
            if (f.get("texto_venta") or f.get("texto")) and dentro(f):
                return r["x0"] + r["ancho"] * 0.3, (f["y0"] + f["y1"]) / 2
    for r in vel[len(vel) // 2:]:
        for f in r["niveles"]:
            if dentro(f):
                return r["x0"] + r["ancho"] * 0.3, (f["y0"] + f["y1"]) / 2
    return None


async def recorrido_completo(v: Vista, out: dict, ctx: dict) -> None:
    """La vista por omision en la pantalla grande: todos los gestos, cada uno con su juicio."""
    await recorrido(v, out, ctx, completo=True)


async def recorrido_corto(v: Vista, out: dict, ctx: dict) -> None:
    await recorrido(v, out, ctx, completo=False)


async def recorrido(v: Vista, out: dict, ctx: dict, completo: bool) -> None:  # noqa: C901 - el recorrido es largo
    K109, K112, J, e = ctx["K109"], ctx["K112"], ctx["J"], ctx["e"]
    pref = ctx["pref"]
    c0 = await v.cosecha()
    if not (c0["hitos"] or {}).get("of6a"):
        J.mal("P", pref, "la pagina no es la de OF-6a (sin FLUJO_HITOS.of6a): no tiene los ejes ni la cruz que juzgar")
        return
    lz = c0["lienzo"]
    L = lambda x, y: (lz[0] + x, lz[1] + y)  # noqa: E731 - del lienzo a la pagina
    arr = arranques_de(c0, K109, e)

    async def paso(nombre: str, c: dict | None = None) -> dict:
        c = c or await v.cosecha()
        r = await juzga_footprint(v, c, e, K109, K112, J, f"{pref} tras «{nombre}»", arr)
        if r:
            r["escritas_resumen"] = await juzga_resumen(v, c, e, r["velas"], arranques_de(c, K109, e) or arr, J,
                                                        f"{pref} tras «{nombre}»")
        out["pasos"].append({"gesto": nombre, "ejes": estado_ejes(c), "textos": r.get("n_textos") if r else None,
                             "resumen": r.get("escritas_resumen") if r else None})
        J.pasos += 1
        return {"c": c, **r} if r else {"c": c}

    async def medido(nombre: str | None, accion) -> tuple:
        """El estado JUSTO antes del gesto, el gesto y el estado despues (con su juicio, si lleva nombre). En el vivo
        puede llegar una vela nueva entre medias y mover lo que se mide: entonces se vuelve a medir (tres veces como mucho)."""
        for _ in range(3):
            a = estado_ejes(await v.cosecha())
            await accion()
            pr = await paso(nombre) if nombre else {"c": await v.cosecha()}
            b = estado_ejes(pr["c"])
            if a["n"] == b["n"]:
                break
        return a, pr, b

    p0 = await paso("carga", c0)
    if "velas" not in p0:
        return
    pin0 = c0["pin"]
    e0 = estado_ejes(c0)
    # I-05 e I-03 por omision: sigue a la ultima vela, escala AUTO y dicha en la esquina del eje
    if not e0["sigue"] or e0["modo"] != "auto" or e0["fila"] != FILA_DEFECTO:
        J.mal("R", pref, f"por omision tiene que seguir la ultima vela con la escala AUTO y filas de {FILA_DEFECTO} px: {e0}")
    if not any(t[0] == "AUTO" and t[1] >= pin0["ancho"] - EJE_P for t in textos_de(c0, "lienzo")):
        J.mal("E", pref, "la esquina del eje de precio no dice AUTO (I-03)")
    if not e.get("ver") and pin0["ver"] != min(400, max(5, math.floor((pin0["ancho"] - EJE_P) / ESPACIADO))):
        J.mal("R", pref, f"sin `ver` en el hash tiene {pin0['ver']} velas y con {ESPACIADO} px por vela caben "
                         f"{math.floor((pin0['ancho'] - EJE_P) / ESPACIADO)}")
    # E-05 y F-16: la cruz y la ficha sobre una celda con cifras
    pc = punto_celda(pin0)
    if pc is None:
        ctx["nomed"].append(f"(C) {pref} no hay ninguna celda a la vista sobre la que poner el cursor")
    else:
        await v.mueve(*L(*pc))
        c = await v.cosecha()
        juzga_cruz(c, p0["velas"], pc[0], pc[1], J, pref)
        out["pasos"].append({"gesto": "cursor", "cruz": {k: c["cruz"].get(k) for k in ("vela", "nivel", "texto_hora")},
                             "ficha": (c["ficha"] or {}).get("lineas")})
        if completo and c0["ind_caja"] and c0["ind_caja"][3] > 20:
            ic = c0["ind_caja"]
            await v.raton("mouseMoved", lz[0] + pc[0], ic[1] + 30)
            await v.s.drena(0.15)
            c = await v.cosecha()
            juzga_cruz(c, p0["velas"], pc[0], ic[1] + 30 - lz[1], J, pref, sobre="panel")
    g0 = p0["g"]
    xm, ym = g0["ancho"] * 0.55, (g0["arriba"] + g0["abajo"]) / 2
    # I-01: la rueda acerca el tiempo anclada al cursor; el precio no se mueve
    a, pr, b = await medido("rueda", lambda: v.rueda(*L(xm, ym), -300))
    i_antes = a["fin"] - (g0["ancho"] - xm) / (g0["ancho"] / a["ver"]) + 0.5
    x_despues = (g0["ancho"] - (b["fin"] - i_antes + 0.5) * (g0["ancho"] / b["ver"])) if b["ver"] else None
    if igual(a["ver"], b["ver"]) or x_despues is None or abs(x_despues - xm) > TOL or not igual(a["fila"], b["fila"]):
        J.mal("R", pref, f"la rueda: ver {a['ver']} -> {b['ver']}, la fila {a['fila']} -> {b['fila']}, la vela bajo el "
                         f"cursor de x {xm:.1f} a {x_despues} (I-01: acerca el tiempo, anclada al cursor; la escala del precio "
                         "no cambia: en AUTO solo sigue a la ultima vela a la vista)")
    # Mayus+rueda desplaza el tiempo (hacia atras: hacia adelante la vista ya esta en la ultima vela)
    a, pr, b = await medido("mayus+rueda", lambda: v.rueda(*L(xm, ym), -300, "shift"))
    if igual(a["fin"], b["fin"]) or not igual(a["ver"], b["ver"]) or not igual(a["fila"], b["fila"]):
        J.mal("R", pref, f"Mayus+rueda: fin {a['fin']} -> {b['fin']}, ver {a['ver']} -> {b['ver']}, fila {a['fila']} -> "
                         f"{b['fila']} (I-01: desplaza el tiempo y nada mas)")
    # Ctrl+rueda acerca el precio, anclado al cursor; el tiempo no se mueve; pasa a MANUAL
    a, pr, b = await medido("ctrl+rueda", lambda: v.rueda(*L(xm, ym), -200, "ctrl"))
    alto = g0["abajo"] - g0["arriba"]
    precio = lambda s, yy: s["lo"] + (g0["abajo"] - yy) / alto * (s["hi"] - s["lo"])  # noqa: E731
    if igual(a["fila"], b["fila"]) or not igual(a["ver"], b["ver"]) or not igual(a["fin"], b["fin"]) or \
            abs(precio(a, ym) - precio(b, ym)) > (b["hi"] - b["lo"]) / alto * TOL or b["modo"] != "manual":
        J.mal("R", pref, f"Ctrl+rueda: fila {a['fila']} -> {b['fila']}, ver {a['ver']} -> {b['ver']}, fin {a['fin']} -> "
                         f"{b['fin']}, el precio bajo el cursor {precio(a, ym):.6g} -> {precio(b, ym):.6g}, modo {b['modo']} "
                         "(I-01: acerca el precio anclado al cursor; el tiempo quieto; MANUAL)")
    if not any(t[0] == "MANUAL" and t[1] >= pr["c"]["pin"]["ancho"] - EJE_P for t in textos_de(pr["c"], "lienzo")):
        J.mal("E", pref, "tras tocar la escala del precio, la esquina del eje no dice MANUAL (I-03)")
    # en MANUAL, la rueda y Mayus+rueda no mueven el precio NADA
    for nombre, dy, mod in (("rueda en manual", 250, ""), ("mayus+rueda en manual", -300, "shift")):
        a, pr, b = await medido(nombre, lambda dy=dy, mod=mod: v.rueda(*L(xm, ym), dy, mod))
        if not (igual(a["lo"], b["lo"]) and igual(a["hi"], b["hi"])) or b["modo"] != "manual" or \
                (igual(a["ver"], b["ver"]) and igual(a["fin"], b["fin"])):
            J.mal("R", pref, f"«{nombre}»: el precio {a['lo']:.6g}-{a['hi']:.6g} -> {b['lo']:.6g}-{b['hi']:.6g}, modo "
                             f"{b['modo']}, ver {a['ver']} -> {b['ver']}, fin {a['fin']} -> {b['fin']} (con la escala MANUAL, un "
                             "gesto del tiempo no mueve el precio)")
    # I-04: doble clic en el eje de precio, AUTO
    xe = g0["ancho"] + 30
    await v.clic(*L(xe, ym), veces=2)
    pr = await paso("doble clic en el eje")
    b = estado_ejes(pr["c"])
    if b["modo"] != "auto" or b["fila"] != FILA_DEFECTO:
        J.mal("R", pref, f"tras el doble clic en el eje de precio la escala es {b['modo']} con fila {b['fila']} (I-04: AUTO)")
    if completo:
        # I-02: arrastrar el eje de precio 100 px hacia arriba reduce el rango y deja el centro
        a, pr, b = await medido("arrastre del eje de precio", lambda: v.arrastra(*L(xe, ym), *L(xe, ym - 100)))
        if not (b["hi"] - b["lo"] < a["hi"] - a["lo"]) or not igual(a["centro"], b["centro"]) or not igual(a["ver"], b["ver"]):
            J.mal("R", pref, f"arrastrar 100 px arriba el eje de precio: rango {a['hi'] - a['lo']:.6g} -> {b['hi'] - b['lo']:.6g}, "
                             f"centro {a['centro']} -> {b['centro']}, ver {a['ver']} -> {b['ver']} (I-02)")
        await v.clic(*L(xe, ym), veces=2)
        # I-02: arrastrar el eje de tiempo cambia el espaciado y deja el final y el precio
        yt = pin0["alto"] - EJE_T / 2
        a, pr, b = await medido("arrastre del eje de tiempo", lambda: v.arrastra(*L(xm, yt), *L(xm + 60, yt)))
        if igual(a["ver"], b["ver"]) or not igual(a["fin"], b["fin"]) or not igual(a["lo"], b["lo"]):
            J.mal("R", pref, f"arrastrar el eje de tiempo: ver {a['ver']} -> {b['ver']}, fin {a['fin']} -> {b['fin']}, lo "
                             f"{a['lo']} -> {b['lo']} (I-02: el espaciado, y nada mas)")
    # I-03: arrastrar el grafico mueve los dos ejes y el precio pasa a MANUAL; el estado va al hash
    await v.tecla("End")
    dx, dy = 160, 50

    async def arrastre():
        await v.arrastra(*L(xm, ym), *L(xm + dx, ym + dy))
        await v.s.drena(0.3)
    a, pr, b = await medido("arrastre del grafico", arrastre)
    bs = g0["ancho"] / a["ver"]
    if abs(b["fin"] - (a["fin"] - dx / bs)) > 0.02 or abs(b["centro"] - (a["centro"] + dy * b["paso"] / b["fila"])) > \
            b["paso"] * 0.02 or b["modo"] != "manual" or b["sigue"] or "/x=" not in (b["hash"] or "") or \
            "/y=" not in (b["hash"] or ""):
        J.mal("R", pref, f"arrastrar el grafico ({dx}, {dy}) px: fin {a['fin']:.3f} -> {b['fin']:.3f} (tenia que ir a "
                         f"{a['fin'] - dx / bs:.3f}), centro {a['centro']:.6g} -> {b['centro']:.6g}, modo {b['modo']}, sigue "
                         f"{b['sigue']}, hash {b['hash']} (I-03: los dos ejes, MANUAL, y la vista en el hash)")
    if completo:
        # I-06: el teclado
        for tecla, quiero in (("ArrowRight", lambda s: s["fin"] + 1), ("ArrowLeft", lambda s: s["fin"] - 1),
                              ("PageDown", lambda s: s["fin"] + s["ver"]), ("PageUp", lambda s: s["fin"] - s["ver"]),
                              ("Home", lambda s: s["ver"] - 1)):
            a, _, b = await medido(None, lambda tecla=tecla: v.tecla(tecla))
            n = b["n"] or len(p0["velas"])  # las velas de AHORA: en el vivo puede haber llegado una durante la prueba
            esperado = min(n - 1 + b["ver"] * 0.3, max(b["ver"] * 0.3, quiero(a)))
            if abs(b["fin"] - esperado) > 0.01:
                J.mal("R", pref, f"la tecla {tecla}: fin {a['fin']:.2f} -> {b['fin']:.2f} y tenia que ir a {esperado:.2f} (I-06)")
        # I-07: el menu del eje de precio y lo que cambia cada opcion
        await v.clic(*L(xe, ym), boton="right")
        c = await v.cosecha()
        if not c["menu"]:
            J.mal("R", pref, "el clic derecho en el eje de precio no abre su menu (I-07)")
        else:
            await v.clic_en("#menu-escala button[data-valor=manual]")
            if estado_ejes(await v.cosecha())["modo"] != "manual":
                J.mal("R", pref, "en el menu del eje, MANUAL no pone la escala en manual (I-07)")
            await v.clic_en("#menu-escala button[data-valor=auto]")
            if estado_ejes(await v.cosecha())["modo"] != "auto":
                J.mal("R", pref, "en el menu del eje, AUTO no vuelve la escala a auto (I-07)")
            await v.clic_en("#menu-eje input[data-fila=ops]")
            await v.s.drena(0.3)
            c = await v.cosecha()
            if "ops" in (c["pin"].get("filas_resumen") or []) or "filas=" not in c["hash"]:
                J.mal("R", pref, f"en el menu del eje, quitar la fila de operaciones deja {c['pin'].get('filas_resumen')} "
                                 f"(hash {c['hash']}) (I-07)")
            await v.clic_en("#menu-eje input[data-fila=ops]")
            await v.s.drena(0.3)
            await v.clic_en("#menu-eje input[name=rueda][value=desplaza]")
            await v.s.drena(0.3)
            a, _, b = await medido(None, lambda: v.rueda(*L(xm, ym), 200))
            if igual(a["fin"], b["fin"]) or not igual(a["ver"], b["ver"]):
                J.mal("R", pref, f"con «la rueda desplaza» la rueda no desplaza: fin {a['fin']} -> {b['fin']}, ver {a['ver']} -> "
                                 f"{b['ver']} (I-01: reasignable en ajustes)")
            await v.clic(*L(xe, ym), boton="right")
            await v.clic_en("#menu-eje input[name=rueda][value=zoom]")
            await v.tecla("Escape")
            if (await v.cosecha())["menu"]:
                J.mal("R", pref, "Esc no cierra el menu del eje (I-06)")
        await v.tecla("End")
        b = estado_ejes(await v.cosecha())
        if not b["sigue"] or abs(b["fin"] - (len(velas_aplicadas(await v.cosecha(), K112, e["marco"])) - 1)) > 0.01:
            J.mal("R", pref, f"la tecla Fin no vuelve a seguir la ultima vela: sigue {b['sigue']}, fin {b['fin']} (I-05)")
    # F-01: los modos de la celda, sin volver a pedir nada
    for modo in (("delta", "trades", "volumen", "perfil", "bidask") if completo else ("delta", "bidask")):
        await v.clic_en(f"#sel-celda button[data-valor={modo}]")
        await v.s.drena(0.3)
        pr = await paso(f"celda {modo}")
        if pr["c"]["pin"].get("celda") != modo:
            J.mal("E", pref, f"el boton {modo} deja la celda en {pr['c']['pin'].get('celda')} (F-01)")
    if completo:
        await recorrido_color(v, out, ctx, paso, L, g0, xm, ym)
        # F-09: con filas de menos de 10 px no se escribe ninguna cifra
        await v.rueda(*L(xm, ym), 100, "ctrl")
        await v.rueda(*L(xm, ym), 100, "ctrl")
        pr = await paso("filas de menos de 10 px")
        fila = pr["c"]["pin"]["escala"]["fila"]
        celdas = sum(1 for r in pr["c"]["pin"]["velas"] for f in r["niveles"]
                     if f.get("texto_venta") or f.get("texto_compra") or f.get("texto"))
        if fila >= FILA_TEXTO or celdas:
            J.mal("T", pref, f"con filas de {fila:.1f} px el lienzo escribe {celdas} cifras en celdas (F-09: con menos de 10, ninguna)")
        await v.clic(*L(xe, ym), veces=2)
    await recorrido_regla(v, out, ctx, L, xm, ym, g0, pref)
    if completo and not e.get("hasta"):
        await recorrido_sigue(v, out, ctx, L, xm, ym, pref)
    # (P): ningun gesto volvio a pedir la historia
    c = await v.cosecha()
    hist = pedidas_historia(c["red"])
    if len(hist) != 1:
        J.mal("P", pref, f"la historia del footprint se pidio {len(hist)} veces: un gesto volvio a pedir lo servido")


async def recorrido_color(v: Vista, out: dict, ctx: dict, paso, L, g0: dict, xm: float, ym: float) -> None:
    """F-04: con la referencia «lo que se ve», desplazarse cambia la intensidad de una misma celda; con «su sesion», no.
    El paso de cada celda pintada se recalcula en cada cosecha (juzga_footprint); aqui, que el corchete se ejercite."""
    J, pref = ctx["J"], ctx["pref"]
    resultados = {}
    diag = ""
    # el precio, alejado y quieto (Ctrl+rueda lo deja en MANUAL): asi las velas comunes conservan sus celdas a la vista
    await v.tecla("End")
    for _ in range(3):
        await v.rueda(*L(xm, ym), 600, "ctrl")
    for ref in ("visible", "sesion"):
        await v.clic_en("#m-color > summary")
        await v.clic_en(f"#m-color input[name=ref][value={ref}]")
        await v.s.drena(0.3)
        await v.clic_en("#m-color > summary")
        for preparacion in range(3):  # sin celdas comunes, se prepara otra vez (Fin y el precio alejado)
            if preparacion:
                await v.tecla("End")
                for _ in range(3):
                    await v.rueda(*L(xm, ym), 600, "ctrl")
            a = (await paso(f"referencia {ref}"))["c"]["pin"]
            # DOS velas atras (desplaza() de la pagina): las comunes son las recientes, las que caben en la ventana del
            # precio aunque el mercado corra (con media pantalla, una caida de 600 USD en 7 min las dejaba fuera)
            atras = -100 * 2 / max(1.0, a["ver"] / 10)
            for intento in range(4):
                await v.rueda(*L(xm, ym), atras, "shift")
                b = (await paso(f"referencia {ref} y desplazado {intento + 1}"))["c"]["pin"]
                ka = {(r["ts"], f["nivel"]): f["paso_color"] for r in a["velas"] for f in r["niveles"] if f["paso_color"] >= 0}
                kb = {(r["ts"], f["nivel"]): f["paso_color"] for r in b["velas"] for f in r["niveles"] if f["paso_color"] >= 0}
                comunes = set(ka) & set(kb)
                resultados[ref] = (len(comunes), sum(ka[k] != kb[k] for k in comunes))
                diag = (f"antes ver {a['ver']:.1f} fin {a['fin']:.1f} fila {a['escala']['fila']:.1f} modo "
                        f"{a['escala']['modo']} {len(ka)} celdas; despues ver {b['ver']:.1f} fin {b['fin']:.1f} {len(kb)} celdas; "
                        f"preparacion {preparacion + 1}")
                if resultados[ref][1] or not comunes or ref == "sesion":
                    break
                a = b
            if resultados[ref][0]:
                break
        await v.tecla("End")
    if resultados["sesion"][1]:
        J.mal("E", pref, f"con la referencia de la sesion, desplazarse cambio el color de {resultados['sesion'][1]} celdas (F-04)")
    if not resultados["sesion"][0]:
        ctx["nomed"].append(f"(E) {pref} F-04 «su sesion» ({diag}): tras desplazarse no quedo ninguna celda comun, el "
                            f"corchete no se ejercito")
    if not resultados["visible"][1]:
        ctx["nomed"].append(f"(E) {pref} F-04 «lo que se ve» ({diag}): desplazarse no cambio el p98 de lo visible en "
                            f"ninguna de {resultados['visible'][0]} celdas comunes, el corchete no se ejercito")
    await v.clic_en("#m-color > summary")
    await v.clic_en("#m-color input[name=ref][value=vela]")
    await v.clic_en("#m-color > summary")
    await v.clic(*L(g0["ancho"] + 30, ym), veces=2)
    out["pasos"].append({"gesto": "F-04", "resultados": resultados})
    J.info.append(f"{pref} F-04: desplazarse con la referencia «lo que se ve» cambio el color de {resultados['visible'][1]} de "
                  f"{resultados['visible'][0]} celdas comunes; con «su sesion», de {resultados['sesion'][1]} de "
                  f"{resultados['sesion'][0]}")


async def recorrido_regla(v: Vista, out: dict, ctx: dict, L, xm: float, ym: float, g0: dict, pref: str) -> None:
    """I-08: Ctrl+arrastre de una vela a otra: velas, el cambio de precio, y el volumen == el de una consulta directa."""
    J, cab = ctx["J"], ctx["cab"]
    c = await v.cosecha()
    pin = c["pin"]
    bs = g0["ancho"] / pin["ver"]
    x0, x1 = xm - 2.2 * bs, xm + 0.8 * bs
    await v.arrastra(*L(x0, ym - 30), *L(x1, ym + 30), "ctrl")
    c = await v.cosecha()
    rg = c["regla"] or {}
    velas = velas_aplicadas(c, ctx["K112"], ctx["e"]["marco"])
    i0, n0 = bajo(c["pin"], x0, ym - 30)
    i1, n1 = bajo(c["pin"], x1, ym + 30)
    a, b = sorted((i0, i1))
    if not rg.get("visible") or rg.get("velas") != b - a + 1 or ms(rg.get("desde") or "1970-01-01T00:00:00Z") != ms(velas[a]["ts"]):
        J.mal("R", pref, f"la regla de x {x0:.0f} a {x1:.0f} dice {rg.get('velas')} velas desde {rg.get('desde')} y son "
                         f"{b - a + 1} desde {velas[a]['ts'][11:16]} (I-08)")
        return
    dp = None if n0 is None or n1 is None else D(n1) - D(n0)
    if (D(rg["delta_precio"]) if rg.get("delta_precio") is not None else None) != dp:
        J.mal("R", pref, f"la regla dice Δ precio {rg.get('delta_precio')} y de la fila {n0} a la {n1} van {dp} (I-08)")
    suma = sum((D(x["total"]) for x in velas[a:b + 1] if x["estado"] != "hueco"), Decimal(0))
    if D(rg["volumen"]) != suma:
        J.mal("R", pref, f"la regla suma {rg['volumen']} de volumen y lo servido en sus velas es {suma} (I-08)")
    e = ctx["e"]
    q = urllib.parse.urlencode({"symbol": e["activo"], "desde": rg["desde"], "hasta": rg["hasta"], "paso": c["pin"]["paso"],
                                "venues": ",".join(FAMILIAS[e["familia"]]), "unidad": e["unidad"]})
    try:
        st, cuerpo = trae(f"{RUTA_PERFIL}?{q}", cab)
        directo = sum((D(n["total"]) for n in json.loads(cuerpo or b"{}").get("niveles") or []), Decimal(0)) if st == 200 else None
    except (OSError, ValueError) as exc:
        directo, st = None, str(exc)[:80]
    if directo is None:
        ctx["nomed"].append(f"(R) {pref} I-08: la consulta directa del rango de la regla no contesto ({st})")
    elif directo != suma or D(rg["volumen"]) != directo:
        J.mal("R", pref, f"la regla de {rg['desde'][11:16]} a {rg['hasta'][11:16]} dice {rg['volumen']} y una consulta "
                         f"directa del mismo rango ({RUTA_PERFIL}) da {directo} (I-08)")
    out["pasos"].append({"gesto": "regla", "regla": {k: rg.get(k) for k in ("desde", "hasta", "velas", "delta_precio", "volumen")},
                         "directo": str(directo)})
    J.info.append(f"{pref} I-08: la regla de {rg['desde'][11:16]} a {rg['hasta'][11:16]} ({rg['velas']} velas, Δ precio "
                  f"{rg.get('delta_precio')}) suma {rg['volumen']} y la consulta directa del rango da {directo}")
    await v.tecla("Escape")


async def recorrido_sigue(v: Vista, out: dict, ctx: dict, L, xm: float, ym: float, pref: str) -> None:
    """I-05: con el seguimiento parado, llegan velas nuevas y la vista no se mueve; Fin lo reactiva."""
    J = ctx["J"]
    await v.tecla("End")
    await v.arrastra(*L(xm, ym), *L(xm + 120, ym))
    a = estado_ejes(await v.cosecha())
    if a["sigue"]:
        J.mal("R", pref, "desplazarse hacia atras no para el seguimiento de la ultima vela (I-05)")
        return
    fin = time.monotonic() + ESPERA_VELA_S
    b = a
    while time.monotonic() < fin:
        await v.s.drena(2.0)
        b = estado_ejes(await v.cosecha())
        if (b["n"] or 0) > (a["n"] or 0):
            break
    if (b["n"] or 0) <= (a["n"] or 0):
        ctx["nomed"].append(f"(R) {pref} I-05: en {ESPERA_VELA_S:.0f} s no llego ninguna vela nueva: no se pudo ver si la vista "
                            "se queda quieta")
    elif abs(b["fin"] - a["fin"]) > 1e-6 or b["sigue"]:
        J.mal("R", pref, f"con el seguimiento parado llego una vela nueva ({a['n']} -> {b['n']}) y la vista se movio (fin "
                         f"{a['fin']:.2f} -> {b['fin']:.2f}) (I-05)")
    await v.clic_en("#b-presente")
    c = estado_ejes(await v.cosecha())
    if not c["sigue"] or abs(c["fin"] - ((c["n"] or 0) - 1)) > 0.01:
        J.mal("R", pref, f"el boton del presente no vuelve a la ultima vela: sigue {c['sigue']}, fin {c['fin']}, n {c['n']} (I-05)")
    out["pasos"].append({"gesto": "seguir", "n": [a["n"], b["n"]], "fin": [a["fin"], b["fin"]]})
    J.info.append(f"{pref} I-05: con el seguimiento parado llegaron {(b['n'] or 0) - (a['n'] or 0)} vela(s) nueva(s) "
                  f"({a['n']} -> {b['n']}) y el final de la vista {a['fin']:.2f} -> {b['fin']:.2f}; el boton del presente la "
                  "vuelve a seguir")


async def recorrido_tpo(v: Vista, out: dict, ctx: dict) -> None:
    """El TPO, con el mismo convenio: la rueda ensancha las letras, Ctrl+rueda y el eje de precio cambian la fila,
    Mayus+rueda desplaza entre sesiones; y tras cada gesto, K109 dice si lo pintado sigue siendo lo servido."""
    K109, J, pref = ctx["K109"], ctx["J"], ctx["pref"]
    c = await v.cosecha()
    t0 = c["tpo"] or {}
    if not t0.get("sesiones"):
        J.mal("P", pref, "el TPO no pinto ninguna sesion")
        return
    caja = await v.evalua("(() => { const r = document.getElementById('lienzo-tpo').getBoundingClientRect(); "
                          "return [r.left, r.top, r.width, r.height]; })()")
    lz = caja
    xm, ym = lz[0] + lz[2] * 0.4, lz[1] + lz[3] * 0.5
    xe = lz[0] + lz[2] - 30

    def juzga_k109(c, nombre):
        vio = {"excepciones": v.excepciones(), "listo": True, "tpo": c["tpo"],
               "peticiones": [{"url": raiz() + x["ruta"] + "?" + urllib.parse.urlencode(x["q"]), "cuerpo": x.get("cuerpo")}
                              for x in c["red"]],
               "textos": [[t[0], t[1], t[2]] for t in c["textos"] if t[3] == "lienzo-tpo"]}
        rojos: list = []
        K109.juzga_tpo(K109.lee_vista(ctx["vista"]), vio, rojos, [])
        for r in rojos:
            J.mal("F", f"{pref} tras «{nombre}»", r)

    juzga_k109(c, "carga")
    for nombre, gesto, clave, cambia in (("rueda", (xm, ym, -300, ""), "letra", True),
                                         ("ctrl+rueda", (xm, ym, -300, "ctrl"), "fila", True),
                                         ("mayus+rueda", (xm, ym, 200, "shift"), "dx", True),
                                         ("rueda en el eje", (xe, ym, 300, ""), "fila", True)):
        a = (c["tpo"] or {}).get("escala") or {}
        await v.rueda(*gesto)
        c = await v.cosecha()
        b = (c["tpo"] or {}).get("escala") or {}
        otros = {k for k in ("letra", "fila", "dx") if k != clave and a.get(k) != b.get(k)}
        if (a.get(clave) == b.get(clave)) == cambia or otros:
            J.mal("R", pref, f"TPO «{nombre}»: {clave} {a.get(clave)} -> {b.get(clave)} y cambiaron {sorted(otros)} (el mismo "
                             "convenio que el footprint)")
        juzga_k109(c, nombre)
        out["pasos"].append({"gesto": f"tpo {nombre}", "escala": b})


# --------------------------------------------------------------------------------------------- E: el aspecto
async def juzga_aspecto(v: Vista, out: dict, ctx: dict) -> None:
    J, cab, pref = ctx["J"], ctx["cab"], ctx["pref"]
    t = await v.evalua("(() => { const s = getComputedStyle(document.documentElement); const g = (k) => s.getPropertyValue(k).trim(); "
                       "const c = document.createElement('canvas').getContext('2d'); c.font = '10px ui-monospace, monospace'; "
                       "const td = document.querySelector('#cinta-tabla td') || document.querySelector('#cinta-tabla th'); "
                       "return {bg: g('--bg'), tx: g('--tx'), comprador: g('--comprador'), vendedor: g('--vendedor'), "
                       "lienzo_compra: (typeof COLOR !== 'undefined') ? COLOR.compra : null, "
                       "lienzo_venta: (typeof COLOR !== 'undefined') ? COLOR.venta : null, "
                       "digitos: '0123456789'.split('').map((d) => c.measureText(d).width), "
                       "tabular: td ? getComputedStyle(td).fontVariantNumeric : null, "
                       "e04: (typeof cifraE04 === 'function') ? [cifraE04(999, 0), cifraE04(10000, 0), cifraE04(1234567, 0)] : null}; })()")
    bg, tx, co, ve = (hex_rgb(t[k]) for k in ("bg", "tx", "comprador", "vendedor"))
    if luminancia(bg) > 0.02 or contraste(tx, bg) < 7:
        J.mal("E", pref, f"E-01: el fondo {t['bg']} (luminancia {luminancia(bg):.4f}) y el texto {t['tx']} (contraste "
                         f"{contraste(tx, bg):.2f}:1): tienen que ser <= 0.02 y >= 7:1")
    des = {"normal": de2000(_lab(co), _lab(ve))}
    des.update({k: de2000(_lab(simula(co, m)), _lab(simula(ve, m))) for k, m in MACHADO.items()})
    if min(des.values()) < 20:
        J.mal("E", pref, f"E-02: el comprador {t['comprador']} y el vendedor {t['vendedor']} se separan dE2000 "
                         + ", ".join(f"{k} {x:.1f}" for k, x in des.items()) + " (tiene que ser >= 20 en las cuatro)")
    if [round(x * 255) for x in co] != t["lienzo_compra"] or [round(x * 255) for x in ve] != t["lienzo_venta"]:
        J.mal("E", pref, f"E-02: el lienzo pinta el comprador {t['lienzo_compra']} y el vendedor {t['lienzo_venta']}, y los "
                         f"tokens dicen {t['comprador']} y {t['vendedor']}")
    for ruta, patron in (("/static/libro/libro-mapa.js", r"compra:\s*'(#[0-9a-fA-F]{6})'"),
                         ("/static/mesa/mesa.css", r"--comprador:\s*(#[0-9a-fA-F]{6})"),
                         ("/static/flujo/flujo.css", r"--comprador:\s*(#[0-9a-fA-F]{6})")):
        st, cuerpo = trae(ruta, cab)
        m = re.search(patron, cuerpo.decode("utf-8", "replace")) if st == 200 else None
        if not m or m.group(1).lower() != t["comprador"].lower():
            J.mal("E", pref, f"E-02: {ruta} no pinta el comprador con el tono comun {t['comprador']} "
                             f"({m.group(1) if m else 'no lo encuentro'}; HTTP {st})")
    if len(set(round(x, 4) for x in t["digitos"])) != 1 or "tabular-nums" not in (t["tabular"] or ""):
        J.mal("E", pref, f"E-03: las cifras no van alineadas: anchos de 0-9 {sorted(set(t['digitos']))}, la cinta con "
                         f"«{t['tabular']}»")
    quiero = [cifra_e04(999, 0), cifra_e04(10000, 0), cifra_e04(1234567, 0)]
    if t["e04"] != ["999", "10.0K", "1.2M"] or quiero != t["e04"]:
        J.mal("E", pref, f"E-04: la pagina escribe {t['e04']} para 999, 10000 y 1234567 (tiene que ser 999, 10.0K, 1.2M)")
    out["pasos"].append({"gesto": "aspecto", "dE": {k: round(x, 1) for k, x in des.items()},
                         "fondo": round(luminancia(bg), 4), "contraste": round(contraste(tx, bg), 2)})


# --------------------------------------------------------------------------------------------- juzga
def juzga() -> int:
    K = _modulo("k102_mesa", "K102-mesa.py")
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            K.binario_chromium()
    except SystemExit:
        print("NO MEDIDO: sin Chromium (o sin websockets) en 143 no se puede mirar la pagina")
        return 2
    K109 = _modulo("k109", "K109-footprint.py")
    K112 = _modulo("k112", "K112-indicadores.py")
    sujeto = f"el ARBOL servido en {BASE} (celdas de {DB})" if BASE else "PRODUCCION (celdas por bin/prodsql)"
    ahora = datetime.now(UTC)
    hasta = datetime.fromisoformat(HASTA.replace("Z", "+00:00")) if HASTA else \
        ahora.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    h = hasta.strftime("%Y-%m-%dT%H:%M:%SZ")
    declara = f"ventana del pasado hasta {h} ({'fijada por K113_HASTA' if HASTA else 'la hora entera que acabo hace una hora'})"
    # LO DECIDIBLE ANTES QUE LO QUE FALTA: sin celdas de BTC perpetuos en la hora de la vista, no hay sujeto
    try:
        n = sql("SELECT count(*) FROM orderflow_celda WHERE symbol = 'BTC' AND venue IN "
                "('binance_usdm','bybit_linear','okx_swap','bitget_usdt') "
                f"AND ts >= '{(hasta - timedelta(hours=1)).isoformat()}' AND ts < '{hasta.isoformat()}'")
    except Canal as exc:
        print(f"NO MEDIDO (CANAL): no se pudo contar orderflow_celda · sujeto: {sujeto} · {str(exc)[:160]}")
        return 2
    if not n or not n[0] or n[0][0] in ("", "0"):
        print(f"NO MEDIDO: sin dato en la ventana · {declara} · sujeto: {sujeto}: orderflow_celda no tiene ni una celda de BTC "
              "perpetuos en esa hora")
        return 2
    try:
        cab = cabecera()
        st, _ = trae("/flujo", cab)
        st_js, js = trae("/static/flujo/flujo-dibujo.js", cab)
    except (Canal, OSError, KeyError) as exc:
        print(f"NO MEDIDO (CANAL): no se pudo preguntar por la pagina · sujeto: {sujeto} · {str(exc)[:160]}")
        return 2
    if st == 404:
        print(f"NO MEDIDO: FALTA DESPLEGAR · {sujeto} no sirve /flujo (404). El codigo no esta mal: no esta desplegado")
        return 2
    if st != 200 or st_js != 200:
        print(f"NO MEDIDO (CANAL): /flujo contesto {st} y su lienzo {st_js} · sujeto: {sujeto}")
        return 2
    if b"FLUJO_CRUZ" not in js:
        print(f"NO MEDIDO: FALTA DESPLEGAR · {sujeto} sirve un /flujo anterior a OF-6a (su lienzo no tiene la cruz ni los dos "
              "ejes que esta red juzga)")
        return 2
    J = Juez()
    nomed: list[str] = []
    huella = hashlib.sha256()
    vistas = [("", 1920, 1080, recorrido_completo), ("", 1366, 768, recorrido_corto),
              (f"#BTC/15m/perp/hasta={h}", 1920, 1080, recorrido_corto),
              (f"#ETH/5m/perp/unidad=usd/hasta={h}", 1366, 768, recorrido_corto),
              (f"#BTC/1m/perp/hasta={h}/modo=tpo/sesiones=1", 1920, 1080, recorrido_tpo)]
    for i, (vista, ancho, alto, rec) in enumerate(vistas):
        e = K112.lee_vista(vista)
        pref = f"[{e['activo']} {e['marco']} {e['familia']}{' TPO' if e.get('modo') == 'tpo' else ''}" \
               f"{'' if e['hasta'] else ' VIVO'} {ancho}x{alto}]"
        ctx = {"K109": K109, "K112": K112, "J": J, "e": e, "pref": pref, "cab": cab, "nomed": nomed, "vista": vista}

        async def con_aspecto(v, out, ctx=ctx, rec=rec, primera=(i == 0)):
            if primera:
                await juzga_aspecto(v, out, ctx)
            await rec(v, out, ctx)
        antes = {b: len(x) for b, x in J.malos.items()}
        t_vista = time.monotonic()
        try:
            out = asyncio.run(asyncio.wait_for(abre(K, vista, ancho, alto, cab, con_aspecto), timeout=400))
        except (K.SystemExit2, TimeoutError, OSError, Canal) as exc:
            nomed.append(f"(P) {pref}: la sonda no pudo con la pagina ({type(exc).__name__}: {str(exc)[:120]})")
            continue
        except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError, AttributeError) as exc:
            J.mal("F", pref, f"el contrato de la pagina no se deja leer: {type(exc).__name__}: {str(exc)[:140]}")
            continue
        if out["excepciones"]:
            J.mal("P", pref, f"la pagina lanzo {len(out['excepciones'])} excepcion(es): {out['excepciones'][0]}")
        if not out["listo"]:
            J.mal("P", pref, "la pagina no pinto su vista")
        brazos = sorted(b for b, x in J.malos.items() if len(x) > antes[b])
        if e["hasta"]:
            huella.update(json.dumps([vista, out["pasos"], brazos], sort_keys=True, default=str).encode())
        else:  # del vivo, lo que no se mueve con el mercado: QUE gestos (no cuantas veces se desplazo F-04) y los brazos
            nombres = sorted({re.sub(r" \d+$", "", p["gesto"]) for p in out["pasos"]})
            huella.update(json.dumps([vista, nombres, brazos], sort_keys=True).encode())
        J.info.append(f"{pref} {len(out['pasos'])} pasos en {time.monotonic() - t_vista:.0f} s · " + ", ".join(
            f"{p['gesto']}{'' if p.get('textos') is None else ' (' + str(p['textos']) + ' cifras)'}"
            for p in out["pasos"][:6]) + (" …" if len(out["pasos"]) > 6 else ""))
    cola = f" · sujeto: {sujeto} · {declara} · huella {huella.hexdigest()[:16]}"
    rojos = [(b, x) for b in "PFCTRE" for x in J.malos[b]]
    if rojos:
        print(f"ROJO  K113 · el raton o el aspecto de /flujo no hacen lo que la especificacion dice · {len(rojos)} hallazgo(s)"
              + cola)
    elif nomed:
        print(f"NO MEDIDO: K113 · {nomed[0]}" + cola)
    else:
        print(f"VERDE  K113 · /flujo se usa y se ve como un footprint profesional: {J.pasos} gestos juzgados, tras cada uno lo "
              "pintado es lo servido, la cruz y la ficha dicen la celda bajo el cursor, las cifras salen cuando caben y el "
              "eje que se mueve es el que manda el gesto, en la vista por omision y en dos pantallas" + cola)
    vistos = set()
    for b, x in rojos:
        clave = (b, x[:90])
        if clave in vistos:
            continue
        vistos.add(clave)
        print(f"   · ({b}) {x}")
    for linea in nomed + J.info:
        print(f"   · {linea}")
    return 1 if rojos else 2 if nomed else 0


if __name__ == "__main__":
    if sys.argv[1:] != ["juzga"]:
        print(__doc__)
        sys.exit(2)
    try:
        sys.exit(juzga())
    except Exception as exc:  # noqa: BLE001 - un fallo de la sonda no acusa a la pagina
        print(f"NO MEDIDO: la sonda de K113 fallo y no juzgo nada ({type(exc).__name__}: {str(exc)[:160]})")
        sys.exit(2)
