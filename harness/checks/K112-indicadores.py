"""K112 · ayudante: abre /flujo en un Chromium de verdad y juzga LOS INDICADORES PINTADOS contra LOS SERVIDOS, y lo
servido contra las TABLAS (OF-5a, campana 146). No importa nada de app/ ni de static/: los cubos de 5 min, su estado,
el cero certificado de las liquidaciones, el CVD, el cambio del OI, la orden agregada y la vela de cada grande se
recalculan aqui con su propia aritmetica. De otros checks toma lo puro: el Chromium y el cliente CDP de K102-mesa.py y
la lectura de una cifra escrita de K109-footprint.py.

LO PINTADO se lee por los CONTRATOS que declara la pagina (window.FLUJO_INDICADORES: por panel su cabecera, su caja, su
escala y sus puntos, huecos y marcas; FLUJO_PINTADO.grandes; la cinta es el propio DOM: texto y data-* de cada fila). Y
no se los cree a pies juntillas: la cabecera de cada panel tiene que estar en el registro de fillText de SU lienzo, el
eje de tiempo se recalcula de la geometria del footprint y del DOM, y lo que hay encima del footprint lo dice el
navegador (elementFromPoint), no la pagina.

LAS VISTAS, RELATIVAS A AHORA (no caducan: las series se guardan 90 dias, la cinta 48 h, las sueltas su retencion);
`h` es la hora entera que acabo hace una hora (K112_HASTA la fija), y se declara en la salida:
  (vacio)                                            LA VISTA POR OMISION (en vivo), en 1920x1080 y en 1280x720 con DPR 2
  #BTC/1m/perp/hasta=<h>/ver=60/ind=<todos>          1 h con todos los paneles: los de 5 min, escalones de 5 velas
  #ETH/15m/perp/hasta=<h>/ver=96/ind=<todos>         24 h: un cubo por vela, y las sueltas solo en su retencion
  #SOL/5m/spot/hasta=<h>/ind=...cinta/cinta=20000    otra familia (las series de Coinalyze siguen siendo de Binance:
                                                     lo tiene que decir) y otro filtro de la cinta, en 1280x720

LOS BRAZOS (cualquiera pone ROJO; uno sin canal es NO MEDIDO y un ROJO de otro manda sobre el):
  (P) la pagina   carga su vista sin excepciones, la pinta y pide lo de SU hash: los indicadores de la ventana y el
                  marco del footprint, las grandes de esa ventana, y la cinta con su filtro; en vivo, SOLO LO NUEVO
                  (cada peticion empieza donde acabo lo servido la vez anterior)
  (V) la familia  las grandes y la cinta piden y sirven los venues de UNA familia, la de su hash
  (S) lo servido  /indicadores == lo recalculado de las seis tablas de Coinalyze (cubos, estado, cero certificado) y de
                  liquidations_realtime; /ordenes == la suma de sus operaciones en orderflow_cinta, y son las del
                  filtro y las mas recientes; /grandes == orderflow_grande (en las vistas del pasado)
  (F) lo pintado  cada panel: su cabecera (fuente y alcance, tal como manda el encargo), cada punto en su vela o en su
                  hora y con su valor, cada HUECO como hueco (nunca un cero, tampoco en el CVD, que empieza en la
                  primera vela y tras un hueco vuelve a 0), el cambio del OI, las liquidaciones y sus sueltas; cada
                  grande en SU vela, a su hora y a su precio; cada fila de la cinta, la orden servida
  (G) la geometria  ningun panel tapa el footprint (lo que hay encima de cada punto suyo es el footprint), los paneles
                  van debajo y con el MISMO eje de tiempo (su eje == el del footprint, en el lienzo y en la pantalla),
                  y la cinta a la derecha
NO MEDIDO: sin la pagina o sin las rutas de OF-5a (404: «FALTA DESPLEGAR») · sin Chromium · sin dato en la ventana ·
sin canal a las tablas.
Uso: K112-indicadores.py juzga (el entorno lo pone K112-los-indicadores-pintados-son-los-servidos.sh)
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
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from decimal import Decimal

AQUI = pathlib.Path(__file__).resolve().parent
H = os.environ.get("K112_HARNESS", "/srv/coinanalyze/harness")
BASE = os.environ.get("K112_BASE", "")  # sin ella: PRODUCCION
DB = os.environ.get("K112_DB", "")  # con K112_BASE: la base del banco
HASTA = os.environ.get("K112_HASTA", "")
ESPERA_VIVO_S = float(os.environ.get("K112_ESPERA_VIVO", "7"))
RUTA_FP, RUTA_IND = "/api" + "/orderflow/footprint", "/api" + "/orderflow/indicadores"
RUTA_ORD, RUTA_GR = "/api" + "/orderflow/ordenes", "/api" + "/orderflow/grandes"
EJE_P = 76  # el margen del eje de precios del footprint (flujo-dibujo.js LZ.EJE_P), escrito aqui y no leido
# Lo DECIDIDO por el encargo, por OF-2 y por P2 de la campana, escrito aqui y no leido de la pagina:
FAMILIAS = {"perp": ("perpetuos USDT", ["binance_usdm", "bybit_linear", "okx_swap", "bitget_usdt"]),
            "spot": ("spot USDT", ["binance_spot", "bybit_spot", "okx_spot"]),
            "coinbase": ("Coinbase spot (USD)", ["coinbase_spot"]),
            "deribit": ("Deribit perpetuo (USD; SOL en USDC)", ["deribit_perp"])}
MARCOS = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}
CIERRE_S, FILAS_CINTA, TOPE_GRANDES = 90, 200, 5000
FILTRO = {"BTC": "200000", "ETH": "200000", "SOL": "50000"}
INDICADORES = ["delta", "cvd", "oi", "oib", "funding", "ls", "liq", "grandes", "cinta"]
DEFECTO = ["delta", "cvd", "grandes", "cinta"]
PANELES = ["delta", "cvd", "oi", "oib", "funding", "ls", "liq"]
SERIE = {"oi": ["oi_binance"], "oib": ["oi_bybit"], "funding": ["funding", "funding_predicho"], "ls": ["largos_cortos"],
         "liq": ["liquidaciones"]}
CAMPO = {"oi": "oi", "oib": "oi", "funding": "funding", "ls": "largos"}
# lo que cada panel tiene que decir de su fuente (el encargo: «interes abierto: Binance (Coinalyze, cada 5 min)»)
FUENTES = {"oi_binance": "interes abierto · Binance (Coinalyze, cada 5 min)",
           "oi_bybit": "interes abierto · Bybit (Coinalyze, cada 5 min)",
           "funding": "funding · Binance (Coinalyze, cada 5 min)",
           "funding_predicho": "funding predicho · Binance (Coinalyze, cada 5 min)",
           "largos_cortos": "largos/cortos · Binance (Coinalyze, cada 5 min)",
           "liquidaciones": "liquidaciones · Binance (Coinalyze, cada 5 min)"}
FUENTE_SUELTAS = "liquidaciones sueltas · binance y bybit perpetuos (colector propio: cada liquidacion)"
# (tabla, {lo servido: columna}, como llega a un cubo)
TABLAS = {"oi_binance": ("open_interest", {"oi": "oi_close"}, "ultimo"),
          "oi_bybit": ("oi_bybit", {"oi": "oi_close"}, "ultimo"),
          "funding": ("funding_rate", {"funding": "fr_close"}, "ultimo"),
          "funding_predicho": ("predicted_funding_rate", {"funding": "pfr_close"}, "ultimo"),
          "largos_cortos": ("long_short_ratio", {"largos": "long_pct", "cortos": "short_pct", "ratio": "ratio"}, "ultimo"),
          "liquidaciones": ("liquidations", {"largos": "long_liq", "cortos": "short_liq"}, "suma")}
COINALYZE = {"BTC": "BTCUSDT_PERP.A", "ETH": "ETHUSDT_PERP.A", "SOL": "SOLUSDT_PERP.A"}
ABREVIA = {"binance_usdm": "BIN-F", "bybit_linear": "BYB-F", "okx_swap": "OKX-F", "bitget_usdt": "BGT-F",
           "binance_spot": "BIN-S", "bybit_spot": "BYB-S", "okx_spot": "OKX-S", "coinbase_spot": "CB",
           "deribit_perp": "DRB"}
ESPERA_PUNTO_S, CADENCIA_S = 15 * 60, 300
ORIGEN = datetime(2000, 1, 1, tzinfo=UTC)
TOL = 1.01


def _modulo(nombre: str, fichero: str):
    spec = importlib.util.spec_from_file_location(nombre, AQUI / fichero)
    m = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stderr(io.StringIO()):
        spec.loader.exec_module(m)
    return m


class Canal(Exception):
    pass


def ms(iso: str) -> int:
    return round(datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp() * 1000)


def isoz(t_ms: int) -> str:
    return datetime.fromtimestamp(t_ms / 1000, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def D(x) -> Decimal:
    return Decimal(str(x))


def txt(d: Decimal) -> str:
    return "0" if d == 0 else format(d.normalize(), "f")


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
    p = [x for x in h.lstrip("#").split("/") if x]
    e = {"activo": p[0] if p else "BTC", "marco": p[1] if len(p) > 1 else "1m",
         "familia": p[2] if len(p) > 2 else "perp", "hasta": None, "ver": 40, "ind": list(DEFECTO), "cinta": None}
    for x in p[3:]:
        k, _, v = x.partition("=")
        if k == "hasta":
            e["hasta"] = v
        elif k == "ver":
            e["ver"] = int(v)
        elif k == "ind":
            e["ind"] = [] if v == "ninguno" else [c for c in INDICADORES if c in v.split(",")] or list(DEFECTO)
        elif k == "cinta":
            e["cinta"] = v
    e["filtro"] = e["cinta"] or FILTRO[e["activo"]]
    return e


def estado_vela(v: dict, as_of: int, marco: str) -> tuple:
    """(estado, faltan) de una vela servida contra el reloj de su respuesta (la regla de OF-2, aqui con su aritmetica)."""
    c = v.get("cobertura") or {}
    if ms(v["ts"]) + MARCOS[marco] * 60000 + CIERRE_S * 1000 > as_of:
        return "abierta", None
    if not c.get("minutos_con_fila"):
        return "hueco", c.get("minutos_esperados")
    if not c.get("completa"):
        return "incompleta", c["minutos_esperados"] - c["minutos_completos"]
    return ("vacia", 0) if not v.get("niveles") else ("completa", 0)


def modelo(respuestas: list[dict], marco: str) -> list[dict]:
    """Las velas que tiene la pagina despues de aplicar, en orden, la historia y cada latido (como flujo-app.js)."""
    velas: list[dict] = []
    for k, d in enumerate(respuestas):
        a = ms(d["as_of"])
        nuevas = [dict(v, _est=estado_vela(v, a, marco)) for v in d["velas"]]
        if k == 0:
            velas = nuevas
            continue
        por = {ms(v["ts"]): i for i, v in enumerate(velas)}
        for v in nuevas:
            t = ms(v["ts"])
            if t in por:
                velas[por[t]] = v
            elif velas and t > ms(velas[-1]["ts"]):
                velas.append(v)
        for v in velas:
            if v["_est"][0] == "abierta":
                v["_est"] = estado_vela(v, a, marco)
    return velas


def cvd(velas: list[dict]) -> list[tuple]:
    """(valor, origen) por vela: desde la primera y, tras un HUECO, otra vez desde 0. None en el hueco."""
    out, acum, origen = [], Decimal(0), None
    for v in velas:
        if v["_est"][0] == "hueco":
            out.append((None, None))
            origen = None
            continue
        if origen is None:
            origen, acum = v["ts"], Decimal(0)
        acum += D(v["delta"])
        out.append((acum, origen))
    return out


def titulo(clave: str, d: dict | None, e: dict, origen: str) -> str:
    """Lo que tiene que decir la cabecera de cada panel: su fuente y su alcance."""
    rotulo = FAMILIAS[e["familia"]][0]
    esc = f"escalon de {d['cubo_minutos']} min" if d else ""
    if clave == "delta":
        return (f"delta por vela · {rotulo} (celdas de OF-1) · compra - venta del agresor, en "
                f"{'USD' if e.get('unidad') == 'usd' else e['activo']}")
    if clave == "cvd":
        return f"CVD · {rotulo} · desde {origen} (inicio de la ventana) · tras un hueco vuelve a 0"
    if clave in ("oi", "oib"):
        return f"{FUENTES[SERIE[clave][0]]} · {esc} · en USD · barras: su cambio"
    if clave == "funding":
        return f"{FUENTES['funding']} · y el predicho (discontinuo) · {esc} · % por periodo de funding"
    if clave == "ls":
        return f"{FUENTES['largos_cortos']} · % de cuentas en largo · {esc}"
    return (f"{FUENTES['liquidaciones']} · largos abajo, cortos arriba · {esc} · puntos: sueltas de binance y bybit "
            f"perpetuos (colector propio: cada liquidacion), desde {d['sueltas']['desde_dato'][11:16]}Z")


def es_miles(x: str) -> str:
    """Como escribe la pagina el filtro (toLocaleString('es-ES') de un entero): 200000 -> 200.000."""
    d = D(x)
    return f"{int(d):,}".replace(",", ".") if d == d.to_integral_value() else str(x)


# --------------------------------------------------------------------------------------------- mirar
INTERCEPTA = r"""
(() => {
  const orig = CanvasRenderingContext2D.prototype.fillText;
  window.__K112_TEXTOS = [];
  CanvasRenderingContext2D.prototype.fillText = function (t, x, y) {
    const m = this.getTransform();
    if (window.__K112_TEXTOS.length < 400000) {
      window.__K112_TEXTOS.push([String(t), m.a * x + m.e, m.d * y + m.f, this.canvas ? this.canvas.id : null]);
    }
    return orig.apply(this, arguments);
  };
})();
"""
COSECHA = r"""
(() => {
  window.__K112_TEXTOS = [];
  const h = window.FLUJO_HITOS || {};
  if (h.repinta) h.repinta();
  const caja = (id) => { const e = document.getElementById(id); if (!e) return null; const r = e.getBoundingClientRect();
    return {x: r.left, y: r.top, w: r.width, h: r.height, oculto: !!e.closest('[hidden]')}; };
  const fp = document.getElementById('lienzo').getBoundingClientRect();
  const encima = [];
  for (let i = 1; i < 10; i++) for (let j = 1; j < 6; j++) {
    const x = fp.left + (fp.width * i) / 10; const y = fp.top + (fp.height * j) / 6;
    if (y < 0 || y >= innerHeight || x < 0 || x >= innerWidth) continue;
    const el = document.elementFromPoint(x, y);
    encima.push([Math.round(x), Math.round(y), el ? (el.id || el.tagName.toLowerCase()) : null]);
  }
  const filas = [...document.querySelectorAll('#cinta-tabla tbody tr[data-ts]')].map((tr) => ({d: Object.assign({}, tr.dataset),
    t: [...tr.children].map((td) => td.textContent), cls: tr.className}));
  return {pintado: window.FLUJO_PINTADO || null, ind: window.FLUJO_INDICADORES || null, cinta: window.FLUJO_CINTA || null,
          hitos: {listo: h.listo, indicadores: h.indicadores, vista: h.vista, aplicadas: h.aplicadas || []}, filas,
          fuente_cinta: (document.getElementById('cinta-fuente') || {}).textContent || null,
          cajas: {lienzo: caja('lienzo'), ind: caja('lienzo-ind'), cinta: caja('cinta')}, encima,
          textos: window.__K112_TEXTOS, pr: window.devicePixelRatio, hash: location.hash};
})()
"""
LISTO = ("!!(window.FLUJO_HITOS && FLUJO_HITOS.listo && FLUJO_HITOS.indicadores && window.FLUJO_CINTA && "
         "(FLUJO_CINTA.apagada || (FLUJO_CINTA.aplicadas || []).length))")


async def mira(K, vista: str, cab: dict, vivo: bool, ancho: int, alto: int, dpr: float) -> dict:
    out = {"vista": vista, "excepciones": [], "red": [], "pantalla": [ancho, alto, dpr]}
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
            await s.pide("Page.addScriptToEvaluateOnNewDocument", source=INTERCEPTA)
            await s.pide("Page.navigate", url=f"{raiz()}/flujo{vista}")
            listo = False
            for _ in range(300):
                await s.drena(0.2)
                with contextlib.suppress(K.SystemExit2):
                    listo = await s.evalua(LISTO)
                if listo:
                    break
            if vivo and listo:  # que lata: el footprint, los indicadores y la cinta, que tiene que pedir solo lo nuevo
                await s.drena(ESPERA_VIVO_S)
            with contextlib.suppress(K.SystemExit2):  # lo que llegue despues no se aplica (y se ve en la red)
                await s.evalua("window.FLUJO_HITOS && FLUJO_HITOS.congela && FLUJO_HITOS.congela()")
            await s.drena(1.5)
            out["listo"] = listo
            out.update(await s.evalua(COSECHA))
            porid: dict = {}
            for e in s.eventos:
                p, m = e.get("params", {}), e.get("method")
                if m == "Runtime.exceptionThrown":
                    out["excepciones"].append(json.dumps(p.get("exceptionDetails", {}))[:300])
                elif m == "Network.requestWillBeSent" and "/api" + "/orderflow/" in p["request"]["url"]:
                    porid[p["requestId"]] = {"url": p["request"]["url"], "estado": None, "t": p.get("timestamp")}
                elif m == "Network.responseReceived" and p.get("requestId") in porid:
                    porid[p["requestId"]]["estado"] = p["response"]["status"]
            for rid, x in porid.items():
                if x["estado"] == 200:
                    try:
                        r = await s.pide("Network.getResponseBody", requestId=rid)
                        x["cuerpo"] = json.loads(base64.b64decode(r["body"]) if r.get("base64Encoded") else r["body"])
                    except (K.SystemExit2, ValueError, KeyError):
                        x["cuerpo"] = None
                x["ruta"] = urllib.parse.urlparse(x["url"]).path
                x["q"] = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(x["url"]).query).items()}
                out["red"].append(x)
            out["red"].sort(key=lambda x: x.get("t") or 0)
            await s.cierra()
    return out


def aplicadas(vio: dict, ruta: str) -> list[dict]:
    """Los cuerpos que la pagina APLICO de una ruta, en orden (casados por su as_of con lo que llego por la red)."""
    por = {(x["ruta"], (x.get("cuerpo") or {}).get("as_of")): x for x in vio["red"] if x.get("cuerpo")}
    if ruta == RUTA_ORD:
        claves = [a.get("as_of") for a in (vio.get("cinta") or {}).get("aplicadas") or []]
    else:
        claves = [a.get("as_of") for a in (vio.get("hitos") or {}).get("aplicadas") or [] if a.get("ruta") == ruta]
    return [por[(ruta, k)] for k in claves if (ruta, k) in por]


# --------------------------------------------------------------------------------------------- el juicio
def juzga_vista(vista: str, vio: dict, rojos: list, nomed: list, info: list, casa) -> dict:
    e = lee_vista(vista)
    vivo = not e["hasta"]
    pref = f"[{e['activo']} {e['marco']} {e['familia']}{' VIVO' if vivo else ''} {vio['pantalla'][0]}x{vio['pantalla'][1]}" \
           f"{'@' + str(vio['pantalla'][2]) if vio['pantalla'][2] != 1 else ''}]"
    pin, ind, malos = vio.get("pintado") or {}, vio.get("ind") or {}, {"P": [], "V": [], "F": [], "G": []}
    if vio["excepciones"]:
        rojos.append(f"(P) {pref} la pagina lanzo {len(vio['excepciones'])} excepcion(es): {vio['excepciones'][0]}")
    if not vio.get("listo") or not pin.get("velas"):
        rojos.append(f"(P) {pref} la pagina no pinto su vista (listo={vio.get('listo')}, {len(pin.get('velas') or [])} "
                     "velas): no hay nada que comparar")
        return {}
    fps = aplicadas(vio, RUTA_FP)
    if not fps:
        rojos.append(f"(P) {pref} la pagina no aplico ninguna respuesta buena de {RUTA_FP}")
        return {}
    fam_rotulo, fam = FAMILIAS[e["familia"]]
    w = fps[0]["q"]  # la ventana del footprint (la de su historia)
    wd, wh = ms(w["desde"]), ms(w["hasta"])
    marco_ms = MARCOS[e["marco"]] * 60000
    velas = modelo([x["cuerpo"] for x in fps], e["marco"])
    por_ts = {ms(v["ts"]): (i, v) for i, v in enumerate(velas)}
    # la geometria del footprint (flujo-dibujo.js: ancho = W - EJE_P, bs = ancho / ver, x(i) = ancho - (fin - i + .5) bs)
    ancho = pin["ancho"] - EJE_P
    bs = ancho / pin["ver"]
    x_de = lambda i: ancho - (pin["fin"] - i + 0.5) * bs  # noqa: E731
    t0 = ms(velas[0]["ts"])
    xT = lambda t: x_de(0) - bs / 2 + (t - t0) / marco_ms * bs  # noqa: E731
    visibles = []
    for r in pin["velas"]:
        i, v = por_ts.get(ms(r["ts"]), (None, None))
        if v is None:
            malos["F"].append(f"vela {r['ts']} pintada en el footprint y no aplicada de lo servido")
            continue
        if abs(r["x0"] + r["ancho"] / 2 - x_de(i)) > 1.01:
            malos["G"].append(f"vela {r['ts']}: su centro {r['x0'] + r['ancho'] / 2} no es el del eje ({x_de(i):.1f})")
        visibles.append((i, v, r))
    # ---------------------------------------------------------------- (P) y (V): lo pedido
    paneles_pedidos = [c for c in PANELES if c in e["ind"]]
    red = {r: [x for x in vio["red"] if x["ruta"] == r] for r in (RUTA_IND, RUTA_GR, RUTA_ORD)}
    if any(c in SERIE for c in paneles_pedidos):
        if not red[RUTA_IND]:
            malos["P"].append(f"no pide {RUTA_IND} y su hash enciende {[c for c in paneles_pedidos if c in SERIE]}")
        for x in red[RUTA_IND]:
            q = x["q"]
            if q.get("symbol") != e["activo"] or q.get("marco") != e["marco"] or ms(q.get("desde", "1970-01-01T00:00:00Z")) != wd \
                    or ms(q.get("hasta", "1970-01-01T00:00:00Z")) < wh:
                malos["P"].append(f"pide {RUTA_IND} {q} y la ventana del footprint es {w['desde']} - {w['hasta']}, "
                                  f"{e['marco']}")
                break
    if "grandes" in e["ind"]:
        if not red[RUTA_GR]:
            malos["P"].append(f"enciende las grandes y no pide {RUTA_GR}")
        for x in red[RUTA_GR]:
            q = x["q"]
            if q.get("symbol") != e["activo"] or ms(q.get("desde", "1970-01-01T00:00:00Z")) != wd:
                malos["P"].append(f"pide {RUTA_GR} {q} y la ventana del footprint empieza en {w['desde']}")
            if sorted(q.get("venues", "").split(",")) != sorted(fam):
                malos["V"].append(f"pide las grandes de {q.get('venues')}: no es UNA familia, la {e['familia']}")
            if x.get("cuerpo") and sorted(x["cuerpo"].get("venues") or []) != sorted(fam):
                malos["V"].append(f"le sirven las grandes de {x['cuerpo'].get('venues')}")
    if "cinta" in e["ind"]:
        cin = red[RUTA_ORD]
        if not cin:
            malos["P"].append(f"enciende la cinta y no pide {RUTA_ORD}")
        for k, x in enumerate(cin):
            q = x["q"]
            if q.get("symbol") != e["activo"] or D(q.get("min_usd", "-1")) != D(e["filtro"]):
                malos["P"].append(f"la cinta pide {q} y su hash dice {e['activo']} con filtro {e['filtro']}")
                break
            if sorted(q.get("venues", "").split(",")) != sorted(fam):
                malos["V"].append(f"la cinta pide {q.get('venues')}: no es UNA familia, la {e['familia']}")
                break
            if not vivo and (ms(q.get("hasta", "1970-01-01T00:00:00Z")) != ms(e["hasta"]) or
                             ms(q.get("desde", "1970-01-01T00:00:00Z")) != ms(e["hasta"]) - 3600000):
                malos["P"].append(f"la cinta de la ventana fija pide {q.get('desde')} - {q.get('hasta')} y su hash dice "
                                  f"la hora anterior a {e['hasta']}")
            if vivo and k and (not q.get("desde") or not cin[k - 1].get("cuerpo")
                               or ms(q["desde"]) != ms(cin[k - 1]["cuerpo"]["hasta"])):
                malos["P"].append(f"el vivo de la cinta no pide SOLO lo nuevo: la peticion {k + 1} pide desde "
                                  f"{q.get('desde')} y lo servido antes acabo en "
                                  f"{(cin[k - 1].get('cuerpo') or {}).get('hasta')}")
                break
        if vivo and len(cin) < 2:
            nomed.append(f"(P) {pref} el vivo de la cinta no latio en {ESPERA_VIVO_S:.0f} s ({len(cin)} peticion): no se "
                         "pudo ver si pide solo lo nuevo")
    # ---------------------------------------------------------------- (F) los paneles
    cajas = {p["clave"]: p for p in ind.get("paneles") or []}
    if [p["clave"] for p in ind.get("paneles") or []] != paneles_pedidos:
        malos["F"].append(f"pinta los paneles {[p['clave'] for p in ind.get('paneles') or []]} y su hash pide "
                          f"{paneles_pedidos}")
    textos_ind = [(t, y) for t, _, y, cv in vio.get("textos") or [] if cv == "lienzo-ind"]
    pr = vio.get("pr") or 1
    di = aplicadas(vio, RUTA_IND)
    d = di[-1]["cuerpo"] if di else None
    origen = velas[0]["ts"][11:16] + "Z"
    puntos_ok = 0
    for clave in paneles_pedidos:
        caja = cajas.get(clave)
        if caja is None:
            continue
        if SERIE.get(clave) and d is None:
            malos["F"].append(f"{clave}: no se aplico ninguna respuesta de {RUTA_IND} y el panel esta encendido")
            continue
        quiero = titulo(clave, d, e, origen)
        if caja.get("titulo") != quiero:
            malos["F"].append(f"{clave}: su cabecera dice «{caja.get('titulo')}» y tiene que decir «{quiero}»")
        elif not any(t == quiero and abs(y / pr - (caja["y0"] + 8)) <= TOL for t, y in textos_ind):
            malos["F"].append(f"{clave}: el contrato dice «{quiero[:50]}…» y el lienzo de los paneles no lo escribio")
        esc = caja.get("escala") or {}
        if not esc or esc.get("hi") == esc.get("lo"):
            malos["F"].append(f"{clave}: sin escala")
            continue
        y_de = lambda v, c=caja, s=esc: c["arriba"] + (s["hi"] - float(v)) / (s["hi"] - s["lo"]) * (c["abajo"] - c["arriba"])  # noqa: E731
        if clave == "delta":
            puntos_ok += juzga_delta(caja, visibles, y_de, malos["F"])
        elif clave == "cvd":
            puntos_ok += juzga_cvd(caja, visibles, cvd(velas), y_de, malos["F"])
        elif clave == "liq":
            puntos_ok += juzga_liq(caja, d, xT, ancho, y_de, malos["F"])
        else:
            puntos_ok += juzga_serie(clave, caja, d, xT, ancho, y_de, malos["F"])
    # las grandes, en su vela, a su hora y a su precio
    grandes_ok = 0
    if "grandes" in e["ind"]:
        dg = aplicadas(vio, RUTA_GR)
        if not dg:
            malos["F"].append("las grandes estan encendidas y no se aplico ninguna respuesta de las grandes")
        else:
            grandes_ok = juzga_grandes(pin, dg[-1]["cuerpo"], visibles, t0, marco_ms, malos["F"])
    # la cinta
    filas_ok = 0
    if "cinta" in e["ind"]:
        filas_ok = juzga_cinta(vio, e, fam, casa, malos["F"])
    # ---------------------------------------------------------------- (G) la geometria
    cj = vio.get("cajas") or {}
    debajo = [x for x in vio.get("encima") or [] if x[2] != "lienzo"]
    if debajo:
        malos["G"].append(f"en ({debajo[0][0]}, {debajo[0][1]}) del footprint lo que hay encima es «{debajo[0][2]}», no el "
                          f"footprint ({len(debajo)} de {len(vio.get('encima') or [])} puntos)")
    if paneles_pedidos:
        a, b = cj.get("lienzo") or {}, cj.get("ind") or {}
        if not a or not b or b.get("oculto"):
            malos["G"].append("los paneles estan encendidos y su lienzo no se ve")
        elif abs(a["x"] - b["x"]) > TOL or abs(a["w"] - b["w"]) > TOL or b["y"] < a["y"] + a["h"] - TOL:
            malos["G"].append(f"el lienzo de los paneles ({b['x']:.0f}, {b['y']:.0f}, {b['w']:.0f} de ancho) no va DEBAJO "
                              f"del footprint ({a['x']:.0f}, {a['y'] + a['h']:.0f}, {a['w']:.0f}) con su mismo ancho")
        eje = ind.get("eje") or {}
        if abs((eje.get("x0") or 0) - x_de(0)) > TOL or abs((eje.get("bs") or 0) - bs) > 0.01 or \
                ms(eje.get("t0") or "1970-01-01T00:00:00Z") != t0:
            malos["G"].append(f"el eje de los paneles {eje} no es el del footprint (x0 {x_de(0):.1f}, bs {bs:.3f})")
    if "cinta" in e["ind"]:
        a, c = cj.get("lienzo") or {}, cj.get("cinta") or {}
        if not c or c.get("oculto") or c["x"] < a["x"] + a["w"] - TOL:
            malos["G"].append(f"la cinta no esta a la derecha del footprint ({c})")
    for brazo, lista in malos.items():
        if lista:
            rojos.append(f"({brazo}) {pref} " + {"P": "pide lo que su hash no dice: ", "V": "dos familias: ",
                                                 "F": "lo pintado no es lo servido: ", "G": "la geometria: "}[brazo]
                         + lista[0] + (f" (y {len(lista) - 1} mas)" if len(lista) > 1 else ""))
    info.append(f"(F)(G) {pref} {len(visibles)} velas a la vista · paneles {paneles_pedidos or 'ninguno'} · "
                f"{puntos_ok} puntos y huecos en su sitio · {grandes_ok} grandes en su vela · {filas_ok} filas de la cinta"
                + (f" · {len(red[RUTA_ORD])} peticiones de la cinta" if vivo and "cinta" in e["ind"] else ""))
    return {"e": e, "w": w, "d": d, "vio": vio, "pref": pref} if not vivo else {}


def juzga_delta(caja: dict, visibles: list, y_de, malos: list) -> int:
    pts = {p["ts"]: p for p in caja["puntos"]}
    huecos = {h["ts"] for h in caja["huecos"]}
    n = 0
    for _i, v, r in visibles:
        hueco = v["_est"][0] == "hueco"
        p = pts.pop(r["ts"], None)
        if hueco:
            if p is not None:
                malos.append(f"delta {r['ts'][11:16]}: la vela es un HUECO y se pinta una barra de {p['valor']}")
            elif r["ts"] not in huecos:
                malos.append(f"delta {r['ts'][11:16]}: la vela es un HUECO y no se dice")
            else:
                n += 1
            continue
        if p is None:
            malos.append(f"delta {r['ts'][11:16]}: servida ({v['delta']}) y no pintada")
            continue
        dd = D(v["delta"])
        if D(p["valor"]) != dd:
            malos.append(f"delta {r['ts'][11:16]}: pinta {p['valor']} y se sirvio {v['delta']}")
        elif abs(p["y0"] - round(y_de(max(dd, 0)))) > TOL or abs(p["y1"] - max(p["y0"] + 1, round(y_de(min(dd, 0))))) > TOL:
            malos.append(f"delta {r['ts'][11:16]}: la barra va de {p['y0']} a {p['y1']} y su valor {v['delta']} la pone en "
                         f"{y_de(max(dd, 0)):.1f}-{y_de(min(dd, 0)):.1f}")
        elif p["x0"] != r["x0"] or p["ancho"] != r["ancho"]:
            malos.append(f"delta {r['ts'][11:16]}: la barra en x {p['x0']}+{p['ancho']} y su vela en {r['x0']}+{r['ancho']}")
        else:
            n += 1
    if pts:
        malos.append(f"delta: pinta barras de velas que no se ven o no se sirvieron: {sorted(pts)[:2]}")
    return n


def juzga_cvd(caja: dict, visibles: list, serie: list, y_de, malos: list) -> int:
    pts = {p["ts"]: p for p in caja["puntos"]}
    n = 0
    for i, v, r in visibles:
        valor, origen = serie[i]
        p = pts.pop(r["ts"], None)
        if valor is None:
            if p is not None:
                malos.append(f"CVD {r['ts'][11:16]}: la vela es un HUECO y se pinta un punto ({p['valor']})")
            else:
                n += 1
            continue
        if p is None:
            malos.append(f"CVD {r['ts'][11:16]}: tiene valor ({txt(valor)}) y no se pinta")
        elif D(p["valor"]) != valor or p.get("origen") != origen:
            malos.append(f"CVD {r['ts'][11:16]}: pinta {p['valor']} (desde {p.get('origen')}) y lo servido da "
                         f"{txt(valor)} (desde {origen}): el CVD empieza en la primera vela y tras un hueco vuelve a 0")
        elif abs(p["y"] - y_de(valor)) > TOL or abs(p["x"] - (r["x0"] + r["ancho"] / 2)) > TOL:
            malos.append(f"CVD {r['ts'][11:16]}: el punto esta en ({p['x']}, {p['y']}) y su vela y su valor lo ponen en "
                         f"({r['x0'] + r['ancho'] / 2}, {y_de(valor):.1f})")
        else:
            n += 1
    if pts:
        malos.append(f"CVD: pinta puntos de velas que no se ven: {sorted(pts)[:2]}")
    return n


def _visible(xT, t: int, fin: int, ancho: float, holgura: float) -> bool:
    return xT(fin) > -holgura and xT(t) < ancho + holgura


def juzga_serie(clave: str, caja: dict, d: dict, xT, ancho: float, y_de, malos: list) -> int:
    c_ms = d["cubo_minutos"] * 60000
    campo, n = CAMPO[clave], 0
    pintados = {(p["serie"], p["ts"]): p for p in caja["puntos"]}
    huecos = {h["ts"]: h for h in caja["huecos"]}
    for k, serie in enumerate(SERIE[clave]):
        for c in d["series"][serie]["cubos"]:
            t = ms(c["ts"])
            seguro, posible = _visible(xT, t, t + c_ms, ancho, -0.5), _visible(xT, t, t + c_ms, ancho, 0.5)
            p = pintados.pop((serie, c["ts"]), None)
            if not posible:
                if p is not None:
                    malos.append(f"{serie} {c['ts'][11:16]}: pintado y no se ve")
                continue
            if c["valores"] is None:
                if p is not None:
                    malos.append(f"{serie} {c['ts'][5:16]}: el cubo es {c['estado'].upper()} (valor null) y se pinta "
                                 f"{p['valor']}: un hueco no es un cero")
                elif k == 0 and seguro and (c["ts"] not in huecos or huecos[c["ts"]]["estado"] != c["estado"]):
                    malos.append(f"{serie} {c['ts'][5:16]}: el cubo es {c['estado']} y no se dice "
                                 f"({huecos.get(c['ts'])})")
                else:
                    n += 1
                continue
            if p is None:
                if seguro:
                    malos.append(f"{serie} {c['ts'][5:16]}: servido ({c['valores'][campo]}) y no pintado")
                continue
            if D(p["valor"]) != D(c["valores"][campo]):
                malos.append(f"{serie} {c['ts'][5:16]}: pinta {p['valor']} y se sirvio {c['valores'][campo]}")
            elif abs(p["x0"] - xT(t)) > TOL or abs(p["x1"] - xT(t + c_ms)) > TOL:
                malos.append(f"{serie} {c['ts'][5:16]}: el escalon va de x {p['x0']} a {p['x1']} y su hora lo pone de "
                             f"{xT(t):.1f} a {xT(t + c_ms):.1f}: no esta en el eje de tiempo del footprint")
            elif abs(p["y"] - y_de(c["valores"][campo])) > TOL:
                malos.append(f"{serie} {c['ts'][5:16]}: el escalon esta en y {p['y']} y su valor lo pone en "
                             f"{y_de(c['valores'][campo]):.1f}")
            else:
                n += 1
    if pintados:
        malos.append(f"{clave}: pinta puntos que no se sirvieron: {sorted(pintados)[:2]}")
    if clave in ("oi", "oib"):  # el cambio, de cubo a cubo con dato
        cubos = d["series"][SERIE[clave][0]]["cubos"]
        quiero = {}
        for a, b in zip(cubos, cubos[1:], strict=False):
            t = ms(b["ts"])
            if a["valores"] and b["valores"] and _visible(xT, t, t + c_ms, ancho, -0.5):
                quiero[b["ts"]] = D(b["valores"]["oi"]) - D(a["valores"]["oi"])
        pint = {x["ts"]: D(x["valor"]) for x in caja["cambios"]}
        faltan = [t for t in quiero if pint.get(t) != quiero[t]]
        sobran = [t for t in pint if t not in quiero and not any(c["ts"] == t and c["valores"] for c in cubos)]
        if faltan or sobran:
            t = (faltan or sobran)[0]
            malos.append(f"{clave}: el cambio del OI en {t[5:16]} se pinta {pint.get(t)} y lo servido da {quiero.get(t)}")
        n += len(quiero)
    return n


def juzga_liq(caja: dict, d: dict, xT, ancho: float, y_de, malos: list) -> int:
    c_ms = d["cubo_minutos"] * 60000
    pts = {p["ts"]: p for p in caja["puntos"]}
    huecos = {h["ts"]: h for h in caja["huecos"]}
    n = 0
    esc = caja["escala"]
    for c in d["series"]["liquidaciones"]["cubos"]:
        t = ms(c["ts"])
        seguro, posible = _visible(xT, t, t + c_ms, ancho, -0.5), _visible(xT, t, t + c_ms, ancho, 0.5)
        p = pts.pop(c["ts"], None)
        if not posible:
            continue
        if c["valores"] is None:
            if p is not None:
                malos.append(f"liquidaciones {c['ts'][5:16]}: el cubo es {c['estado'].upper()} y se pintan barras: un hueco "
                             "no es un cero")
            elif seguro and (c["ts"] not in huecos or huecos[c["ts"]]["estado"] != c["estado"]):
                malos.append(f"liquidaciones {c['ts'][5:16]}: el cubo es {c['estado']} y no se dice")
            else:
                n += 1
            continue
        if p is None:
            if seguro:
                malos.append(f"liquidaciones {c['ts'][5:16]}: servidas y no pintadas")
            continue
        largos, cortos = D(c["valores"]["largos"]), D(c["valores"]["cortos"])
        if (D(p["largos"]), D(p["cortos"])) != (largos, cortos):
            malos.append(f"liquidaciones {c['ts'][5:16]}: pinta {p['largos']}/{p['cortos']} y se sirvio {largos}/{cortos}")
        elif abs(p["y_cortos"] - round(y_de(cortos))) > TOL or abs(p["y_largos"] - round(y_de(-largos))) > TOL:
            malos.append(f"liquidaciones {c['ts'][5:16]}: las barras en y {p['y_cortos']}/{p['y_largos']} y sus valores las "
                         f"ponen en {y_de(cortos):.0f}/{y_de(-largos):.0f}")
        elif max(largos, cortos) > Decimal(str(esc["hi"])):
            malos.append(f"liquidaciones {c['ts'][5:16]}: su valor se sale de la escala del panel")
        else:
            n += 1
    if pts:
        malos.append(f"liquidaciones: pinta cubos que no se sirvieron: {sorted(pts)[:2]}")
    # las sueltas: un punto por cada una que cae a la vista, a su hora
    quiero = {(ev["ts"], ev["exchange"], ev["lado"], ev["usd"]) for ev in d["sueltas"]["eventos"]
              if -0.5 < xT(ms(ev["ts"])) < ancho + 0.5}
    pint = {(m["ts"], m["exchange"], m["lado"], m["usd"]) for m in caja["marcas"]}
    seguras = {q for q in quiero if 0.5 < xT(ms(q[0])) < ancho - 0.5}
    if not seguras <= pint or not pint <= quiero:
        dif = sorted((seguras - pint) | (pint - quiero))[:1]
        malos.append(f"sueltas: {len(pint)} puntos pintados y {len(quiero)} servidas a la vista (la primera distinta {dif})")
    for m in caja["marcas"]:
        if abs(m["x"] - xT(ms(m["ts"]))) > TOL:
            malos.append(f"sueltas {m['ts'][11:19]}: el punto esta en x {m['x']} y su hora lo pone en {xT(ms(m['ts'])):.1f}")
            break
    return n + len(pint & quiero)


def juzga_grandes(pin: dict, dg: dict, visibles: list, t0: int, marco_ms: int, malos: list) -> int:
    esc = pin.get("escala") or {}
    y = lambda p: esc["arriba"] + (esc["hi"] - float(p)) / (esc["hi"] - esc["lo"]) * (esc["abajo"] - esc["arriba"])  # noqa: E731
    por_i = {i: r for i, _v, r in visibles}
    marcas = {(m["ts"], m["venue"], m.get("id")): m for m in (pin.get("grandes") or {}).get("marcas") or []}
    n = 0
    for o in dg.get("operaciones") or []:
        t = ms(o["ts"])
        i = (t - t0) // marco_ms
        m = marcas.pop((o["ts"], o["venue"], o["id"]), None)
        r = por_i.get(i)
        if r is None:
            if m is not None:
                malos.append(f"grande {o['ts'][11:19]} {o['venue']}: pintada y su vela ({isoz(t0 + i * marco_ms)}) no se ve")
            continue
        if m is None:
            malos.append(f"grande {o['ts'][11:19]} {o['venue']} {o['usd']} USD: servida en una vela a la vista y no pintada")
            continue
        x = r["x0"] + r["ancho"] * (t - (t0 + i * marco_ms)) / marco_ms
        if m["vela"] != r["ts"] or not r["x0"] - TOL <= m["x"] <= r["x0"] + r["ancho"] + TOL or abs(m["x"] - x) > TOL:
            malos.append(f"grande {o['ts'][11:19]} {o['venue']}: su marca esta en x {m['x']} (vela {m['vela'][11:16]}) y "
                         f"es de la vela {r['ts'][11:16]}, en x {x:.1f}")
        elif abs(m["y"] - y(o["precio"])) > TOL or D(m["precio"]) != D(o["precio"]) or m["agresor"] != o["agresor"]:
            malos.append(f"grande {o['ts'][11:19]} {o['venue']}: su marca esta en y {m['y']} y su precio {o['precio']} la "
                         f"pone en {y(o['precio']):.1f}")
        else:
            n += 1
    if marcas:
        malos.append(f"grandes: pinta marcas que no se sirvieron: {sorted(marcas)[:1]}")
    return n


def juzga_cinta(vio: dict, e: dict, fam: list, casa, malos: list) -> int:
    lista: list[dict] = []
    for x in aplicadas(vio, RUTA_ORD):
        lista = (x["cuerpo"].get("ordenes") or []) + lista
        lista = lista[:FILAS_CINTA]
    filas = vio.get("filas") or []
    fuente = vio.get("fuente_cinta") or ""
    quiero = (f"órdenes agregadas · {FAMILIAS[e['familia']][0]} ({', '.join(fam)}) · mismo venue, milisegundo y lado · "
              f"≥ {es_miles(e['filtro'])} USD")
    if fuente != quiero:
        malos.append(f"la cinta dice «{fuente}» y tiene que decir «{quiero}»")
    if len(filas) != len(lista):
        malos.append(f"la cinta pinta {len(filas)} filas y lo aplicado son {len(lista)} ordenes")
    n = 0
    for f, o in zip(filas, lista, strict=False):
        dd = f["d"]
        if (dd.get("ts"), dd.get("venue"), dd.get("agresor"), dd.get("operaciones")) != \
                (o["ts"], o["venue"], o["agresor"], str(o["operaciones"])) or \
                any(D(dd.get(k, "-1")) != D(o[v]) for k, v in (("usd", "usd"), ("base", "base"), ("pmin", "precio_min"),
                                                               ("pmax", "precio_max"))):
            malos.append(f"la fila {n + 1} de la cinta es {dd} y la orden aplicada {o}")
            break
        precio = o["precio_max"] if o["agresor"] == "compra" else o["precio_min"]
        if o["precio_min"] != o["precio_max"]:
            precio += "↑" if o["agresor"] == "compra" else "↓"
        t = f["t"]
        if len(t) != 6 or t[0] != o["ts"][11:23] or t[1] != ABREVIA[o["venue"]] or \
                t[2] != ("C" if o["agresor"] == "compra" else "V") or not casa(t[3], o["usd"]) or t[4] != precio or \
                t[5] != str(o["operaciones"]):
            malos.append(f"la fila {n + 1} de la cinta escribe {t} y la orden es {o['ts'][11:23]} {o['venue']} "
                         f"{o['agresor']} {o['usd']} USD a {precio} ({o['operaciones']} operaciones)")
            break
        n += 1
    return n


# --------------------------------------------------------------------------------------------- (S) lo servido
def juzga_servido(x: dict, rojos: list, nomed: list, info: list) -> None:
    e, d, vio, pref = x["e"], x["d"], x["vio"], x["pref"]
    malos = []
    if d is not None:
        malos += servido_indicadores(e, d)
    for o in aplicadas(vio, RUTA_ORD):
        malos += servido_ordenes(o["q"], o["cuerpo"])
    for g in aplicadas(vio, RUTA_GR)[-1:]:
        malos += servido_grandes(g["q"], g["cuerpo"])
    if malos:
        rojos.append(f"(S) {pref} lo servido no es lo de las tablas: {malos[0]}"
                     + (f" (y {len(malos) - 1} mas)" if len(malos) > 1 else ""))
    else:
        info.append(f"(S) {pref} indicadores ({len(d['series']) if d else 0} series, "
                    f"{len(d['sueltas']['eventos']) if d else 0} sueltas), "
                    f"{sum(len(o['cuerpo']['ordenes']) for o in aplicadas(vio, RUTA_ORD))} ordenes y "
                    f"{sum(len(g['cuerpo']['operaciones']) for g in aplicadas(vio, RUTA_GR)[-1:])} grandes servidas == "
                    "recalculadas de las tablas")


def servido_indicadores(e: dict, d: dict) -> list[str]:
    malos = []
    simbolo = COINALYZE[e["activo"]]
    a, b = ms(d["desde"]), ms(d["hasta"])
    cubo = max(5, MARCOS[d["marco"]]) * 60000
    ahora = ms(d["as_of"])
    primero = a - (a - int(ORIGEN.timestamp() * 1000)) % cubo
    inicios = list(range(primero, b, cubo))
    bar = d.get("liquidaciones_barrido") or {}
    hb = sql("SELECT status, detail FROM pipeline_heartbeat WHERE service = 'ingest:liquidations_history'")
    if hb:
        try:
            det = json.loads("|".join(hb[0][1:]))
            if bar.get("estado") == "ok" and (hb[0][0] != "ok" or ms(bar["hasta"]) > det["source_cutoff_ts"] * 1000):
                malos.append(f"el barrido servido {bar} no es el del latido de la ingesta ({hb[0][0]}, hasta "
                             f"{isoz(det['source_cutoff_ts'] * 1000)})")
        except (ValueError, KeyError):
            pass
    cert = (ms(bar["desde"]), ms(bar["hasta"])) if bar.get("estado") == "ok" and bar.get("desde") else None
    for clave, (tabla, cols, como) in TABLAS.items():
        s = d["series"].get(clave)
        if s is None:
            malos.append(f"no sirve la serie {clave}")
            continue
        if s.get("fuente") != FUENTES[clave]:
            malos.append(f"{clave}: sirve la fuente «{s.get('fuente')}» y es «{FUENTES[clave]}»")
        lista = ", ".join(f"{c}" for c in cols.values())
        filas = sql(f"SELECT (extract(epoch FROM ts) * 1000)::bigint, {lista} FROM {tabla} WHERE symbol = '{simbolo}' "
                    f"AND interval = '5min' AND ts >= '{isoz(primero)}' AND ts < '{isoz(inicios[-1] + cubo)}'")
        por = {int(f[0]): dict(zip(cols, f[1:], strict=True)) for f in filas}
        mio = []
        for t in inicios:
            pts = list(range(t, t + cubo, CADENCIA_S * 1000))
            presentes = [por[p] for p in pts if p in por]
            ceros = faltan = pend = 0
            for p in pts:
                if p in por:
                    continue
                if como == "suma" and cert and cert[0] <= p and p + CADENCIA_S * 1000 <= cert[1]:
                    ceros += 1
                elif p + CADENCIA_S * 1000 > ahora - ESPERA_PUNTO_S * 1000:
                    pend += 1
                else:
                    faltan += 1
            con = len(presentes) + ceros
            est = ("hueco" if faltan else "pendiente") if not con else \
                ("incompleto" if faltan else "en_curso" if pend else "completo")
            if presentes and como == "ultimo":
                val = {k: txt(D(presentes[-1][k])) for k in cols}
            elif con and como == "suma":
                val = {k: txt(sum((D(x[k]) for x in presentes), Decimal(0))) for k in cols}
            else:
                val = None
            mio.append({"ts": t, "estado": est, "puntos": len(presentes), "ceros": ceros, "faltan": faltan,
                        "pendientes": pend, "valores": val})
        servidos = [{**c, "ts": ms(c["ts"]), "valores": c["valores"] and {k: txt(D(v)) for k, v in c["valores"].items()}}
                    for c in s["cubos"]]
        if servidos != mio:
            par = next(((p, q) for p, q in zip(servidos, mio, strict=False) if p != q), (None, None))
            malos.append(f"{clave}: los cubos servidos no son los de {tabla} ({len(servidos)} y {len(mio)}; el primero "
                         f"distinto: servido {par[0]} y recalculado {par[1]})")
    sw = d["sueltas"]
    if sw.get("fuente") != FUENTE_SUELTAS:
        malos.append(f"sueltas: sirve la fuente «{sw.get('fuente')}»")
    borde = max(a, ahora - int(sw["retencion_h"]) * 3600000)
    if abs(ms(sw["desde_dato"]) - min(borde, b)) > 2000:
        malos.append(f"sueltas: dice tener dato desde {sw['desde_dato']} y su retencion de {sw['retencion_h']} h lo pone "
                     f"en {isoz(min(borde, b))}")
    filas = sql(f"SELECT to_char(ts AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.MS\"Z\"'), exchange, side, notional_usd, "
                f"price, qty FROM liquidations_realtime WHERE symbol = '{simbolo}' AND ts >= '{sw['desde_dato']}' "
                f"AND ts < '{d['hasta']}' ORDER BY ts, exchange, event_id LIMIT 5001")
    mias = [(f[0], f[1], f[2], D(f[3]), D(f[4]), D(f[5])) for f in filas]
    suyas = [(ev["ts"], ev["exchange"], ev["lado"], D(ev["usd"]), D(ev["precio"]), D(ev["cantidad"]))
             for ev in sw["eventos"]]
    if mias[:5000] != suyas:
        dif = next((p for p in zip(suyas, mias, strict=False) if p[0] != p[1]), None)
        malos.append(f"sueltas: {len(suyas)} servidas y {len(mias)} en liquidations_realtime (la primera distinta {dif})")
    return malos


def servido_ordenes(q: dict, o: dict) -> list[str]:
    """Cada orden servida == la suma de SUS operaciones en la cinta (con la aritmetica de aqui), todas pasan el filtro,
    y son las `limit` mas recientes de la ventana (el recuento y la mas vieja, por SQL)."""
    malos = []
    if not o["ordenes"]:
        return malos
    vs = ",".join(f"'{v}'" for v in o["venues"] if re.fullmatch(r"[a-z_]+", v))
    claves = " OR ".join(f"(venue = '{x['venue']}' AND compra = {'true' if x['agresor'] == 'compra' else 'false'} "
                         f"AND ts >= '{x['ts']}' AND ts < timestamptz '{x['ts']}' + interval '1 millisecond')"
                         for x in o["ordenes"] if re.fullmatch(r"[a-z_]+", x["venue"]))
    filas = sql(f"SELECT to_char(date_trunc('milliseconds', ts) AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.MS\"Z\"'), "
                f"venue, compra, precio, base, usd FROM orderflow_cinta WHERE symbol = '{o['symbol']}' AND ({claves})")
    suma: dict = {}
    for ts, venue, compra, precio, base, usd in filas:
        z = suma.setdefault((ts, venue, "compra" if compra == "t" else "venta"), [0, Decimal(0), Decimal(0), None, None])
        z[0] += 1
        z[1] += D(base)
        z[2] += D(usd)
        z[3] = D(precio) if z[3] is None else min(z[3], D(precio))
        z[4] = D(precio) if z[4] is None else max(z[4], D(precio))
    for x in o["ordenes"]:
        z = suma.get((x["ts"], x["venue"], x["agresor"]))
        mia = z and (z[0], z[1], z[2], z[3], z[4])
        suya = (x["operaciones"], D(x["base"]), D(x["usd"]), D(x["precio_min"]), D(x["precio_max"]))
        if mia != suya:
            malos.append(f"la orden {x['ts'][11:23]} {x['venue']} {x['agresor']}: servida {suya} y sus operaciones suman "
                         f"{mia}")
            break
        if suya[2] < D(o["min_usd"]):
            malos.append(f"la orden {x['ts'][11:23]} {x['venue']}: {x['usd']} USD no pasa el filtro {o['min_usd']}")
            break
    if not malos:
        r = sql(f"""SELECT count(*), to_char(min(ms) AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"') FROM (
                      SELECT date_trunc('milliseconds', ts) AS ms FROM orderflow_cinta
                       WHERE symbol = '{o['symbol']}' AND venue IN ({vs}) AND ts > '{o['desde']}' AND ts <= '{o['hasta']}'
                       GROUP BY 1, venue, compra HAVING sum(usd) >= {D(o['min_usd'])}
                       ORDER BY 1 DESC LIMIT {int(o['limit'])}) x""")
        n, mas_vieja = int(r[0][0]), r[0][1]
        if n != len(o["ordenes"]) or (n and mas_vieja != min(x["ts"] for x in o["ordenes"])):
            malos.append(f"sirve {len(o['ordenes'])} ordenes (la mas vieja {min(x['ts'] for x in o['ordenes'])}) y las "
                         f"{n} mas recientes de la cinta que pasan el filtro empiezan en {mas_vieja}")
    return malos


def servido_grandes(q: dict, g: dict) -> list[str]:
    vs = ",".join(f"'{v}'" for v in g["venues"] if re.fullmatch(r"[a-z_]+", v))
    filas = sql(f"SELECT to_char(ts AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.MS\"Z\"'), venue, precio, usd, compra, id "
                f"FROM orderflow_grande WHERE symbol = '{g['symbol']}' AND venue IN ({vs}) AND ts >= '{g['desde']}' "
                f"AND ts < '{g['hasta']}' ORDER BY ts DESC, venue, id LIMIT {int(g['limit'])}")
    mias = [(f[0], f[1], D(f[2]), D(f[3]), "compra" if f[4] == "t" else "venta", f[5]) for f in filas]
    suyas = [(x["ts"], x["venue"], D(x["precio"]), D(x["usd"]), x["agresor"], x["id"]) for x in g["operaciones"]]
    if mias != suyas:
        dif = next((p for p in zip(suyas, mias, strict=False) if p[0] != p[1]), None)
        return [f"grandes: {len(suyas)} servidas y {len(mias)} en orderflow_grande (la primera distinta {dif})"]
    return []


# --------------------------------------------------------------------------------------------- juzga
def juzga() -> int:
    K = _modulo("k102_mesa", "K102-mesa.py")
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            K.binario_chromium()
    except SystemExit:
        print("NO MEDIDO: sin Chromium (o sin websockets) en 143 no se puede mirar la pagina")
        return 2
    casa = _modulo("k109", "K109-footprint.py").casa
    sujeto = f"el ARBOL servido en {BASE} (tablas de {DB})" if BASE else "PRODUCCION (tablas por bin/prodsql)"
    ahora = datetime.now(UTC)
    hasta = datetime.fromisoformat(HASTA.replace("Z", "+00:00")) if HASTA else \
        ahora.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    h = hasta.strftime("%Y-%m-%dT%H:%M:%SZ")
    todos = "ind=delta,cvd,oi,oib,funding,ls,liq,grandes,cinta"
    # (vista, pantalla en px CSS, devicePixelRatio): la vista POR OMISION en dos pantallas y tres del pasado
    vistas = [("", 1920, 1080, 1), ("", 1280, 720, 2),
              (f"#BTC/1m/perp/hasta={h}/ver=60/{todos}", 1920, 1080, 1),
              (f"#ETH/15m/perp/hasta={h}/ver=96/{todos}", 1920, 1080, 1),
              (f"#SOL/5m/spot/hasta={h}/ind=delta,cvd,oi,liq,grandes,cinta/cinta=20000", 1280, 720, 1)]
    declara = f"ventana del pasado hasta {h} ({'fijada por K112_HASTA' if HASTA else 'la hora entera que acabo hace una hora'})"
    # LO DECIDIBLE ANTES QUE LO QUE FALTA: sin puntos de 5 min en la ventana no hay sujeto (y no se abre Chromium)
    try:
        n = sql(f"SELECT count(*) FROM open_interest WHERE symbol = 'BTCUSDT_PERP.A' AND ts >= '{(hasta - timedelta(hours=4)).isoformat()}' "
                f"AND ts < '{hasta.isoformat()}'")
    except Canal as exc:
        print(f"NO MEDIDO (CANAL): no se pudo contar open_interest · sujeto: {sujeto} · {str(exc)[:160]}")
        return 2
    if not n or not n[0] or n[0][0] in ("", "0"):
        print(f"NO MEDIDO: sin dato en la ventana · {declara} · sujeto: {sujeto}: open_interest no tiene ni un punto de BTC "
              "en sus 4 h (las series de 5 min se guardan 90 dias)")
        return 2
    try:
        cab = cabecera()
        pagina = estado_http(f"{raiz()}/flujo", cab)
        rutas = estado_http(f"{raiz()}{RUTA_IND}?symbol=BTC&desde={isoz(int(hasta.timestamp() * 1000) - 300000)}"
                            f"&hasta={h}&marco=5m", cab)
    except (Canal, OSError, KeyError) as exc:
        print(f"NO MEDIDO (CANAL): no se pudo preguntar por la pagina · sujeto: {sujeto} · {str(exc)[:160]}")
        return 2
    if pagina == 404:
        print(f"NO MEDIDO: FALTA DESPLEGAR · {sujeto} no sirve /flujo (404). El codigo no esta mal: no esta desplegado")
        return 2
    if rutas == 404:
        print(f"NO MEDIDO: FALTA DESPLEGAR · {sujeto} no sirve {RUTA_IND} (404): es anterior a OF-5a, y su /flujo no tiene "
              "indicadores que juzgar")
        return 2
    if pagina != 200 or rutas != 200:
        print(f"NO MEDIDO (CANAL): /flujo contesto {pagina} y {RUTA_IND} {rutas} · sujeto: {sujeto}")
        return 2
    rojos: list[str] = []
    nomed: list[str] = []
    info: list[str] = [declara]
    huella = hashlib.sha256()
    for vista, ancho, alto, dpr in vistas:
        vivo = "hasta=" not in vista
        try:
            vio = asyncio.run(asyncio.wait_for(mira(K, vista, cab, vivo, ancho, alto, dpr), timeout=200))
        except (K.SystemExit2, TimeoutError, OSError) as exc:
            nomed.append(f"(P) {vista or '(por omision)'}: la sonda no pudo mirar la pagina ({str(exc)[:120]})")
            continue
        try:
            x = juzga_vista(vista, vio, rojos, nomed, info, casa)
        except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError) as exc:  # un contrato roto no tumba al resto
            rojos.append(f"(F) [{vista or '(por omision)'}] el contrato de la pagina no se deja leer: "
                         f"{type(exc).__name__}: {str(exc)[:120]}")
            x = {}
        # LA HUELLA: de las vistas del pasado, lo pintado y lo servido; del vivo, solo lo que no se mueve con el mercado
        ind = vio.get("ind") or {}
        if not vivo:
            huella.update(json.dumps([vista, [{k: v for k, v in p.items()} for p in ind.get("paneles") or []],
                                      (vio.get("pintado") or {}).get("grandes"), vio.get("filas"), vio.get("fuente_cinta"),
                                      [(r["ruta"], sorted(r["q"].items())) for r in vio["red"]],
                                      [r.get("cuerpo") and {k: v for k, v in r["cuerpo"].items() if k != "as_of"}
                                       for r in vio["red"] if r["ruta"] != RUTA_FP],
                                      vio.get("cajas"), vio.get("encima")], sort_keys=True, default=str).encode())
        else:
            huella.update(json.dumps([vista, [p.get("clave") for p in ind.get("paneles") or []], vio.get("cajas"),
                                      vio.get("encima"), vio.get("pantalla")], sort_keys=True, default=str).encode())
        if not x:
            continue
        try:
            juzga_servido(x, rojos, nomed, info)
        except (Canal, IndexError, KeyError, ValueError) as exc:
            nomed.append(f"(S) [{vista}] sin canal a las tablas: {type(exc).__name__}: {str(exc)[:160]}")
    cola = f" · sujeto: {sujeto} · {declara} · huella {huella.hexdigest()[:16]}"
    if rojos:
        print(f"ROJO  K112 · los indicadores pintados no son los servidos, o lo servido no es lo de las tablas · "
              f"{len(rojos)} hallazgo(s)" + cola)
    elif nomed:
        print(f"NO MEDIDO: K112 · {nomed[0]}" + cola)
    else:
        print("VERDE  K112 · los indicadores pintan lo que sirven y lo servido es lo de las tablas: cada panel con su "
              "fuente, sus puntos en su vela y su hora, los huecos como huecos (tambien en el CVD), las grandes en su "
              "vela y la cinta con las ordenes agregadas (en vivo, solo lo nuevo); ningun panel tapa el footprint, en "
              "la vista por omision y en dos pantallas" + cola)
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
        print(f"NO MEDIDO: la sonda de K112 fallo y no juzgo nada ({type(exc).__name__}: {str(exc)[:160]})")
        sys.exit(2)
