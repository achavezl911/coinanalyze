"""K121 · ayudante: abre /flujo en un Chromium de verdad, pone los cuatro trazos de la campana 146-D (nivel, linea,
Fibonacci y canal de regresion) con GESTOS REALES (Input.dispatchMouseEvent por CDP) y juzga, tras ponerlos, tras un
arrastre sin herramienta, tras la rueda, tras cambiar de marco y tras recargar, que cada trazo esta DONDE SE PUSO.

No importa nada de app/ ni de static/: la x de un instante, el tramo de un canal, su regresion (minimos cuadrados de
los cierres con x = indice de la vela en el tramo, sigma = sqrt(suma res^2 / n)) y los siete precios de Fibonacci se
recalculan aqui. De otros checks toma lo puro: el Chromium y el CDP de K102-mesa.py, los gestos de K113-raton.py y
modelo() de K112-indicadores.py (las velas que la pagina tiene tras aplicar lo que recibio).

EL HUECO LO PONE EL CHECK. El servidor rellena cada intervalo (una vela sin dato llega como «hueco», en su sitio), asi
que una x por indice ((t - t0) / marco) no se distingue de la buena con lo que sirve. La red intercepta cada respuesta
del footprint (Fetch, fase de respuesta) y le QUITA una vela por marco, siempre la misma; las velas del juicio son las
que la pagina recibio de verdad, ya sin ella.

Brazos:  (X) cada punto en la x de su instante y la y de su precio, 1 px     (F) Fibonacci: sus siete razones y precios
         (C) el canal: pendiente, sigma (1e-6 relativo), n y los extremos de sus tres rectas
         (G) lo guardado: los mismos trazos tras cambiar de marco y tras recargar
         (H) sin herramienta, un arrastre mueve el grafico y no pone nada     (P) la pagina: excepciones
         (K) al poner, cada punto guardado cae en el pixel de SU clic (1 px), con la escala y las velas de la pagina
             leidas justo antes de ese clic: (X) solo mira que lo pintado siga al punto guardado, y un punto guardado
             12 px a la derecha del clic se pinta donde dice su instante
"""

from __future__ import annotations

import asyncio
import base64
import bisect
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
import shutil
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta

AQUI = pathlib.Path(__file__).resolve().parent
H = os.environ.get("K121_HARNESS", "/srv/coinanalyze/harness")
BASE = os.environ.get("K121_BASE", "")  # sin ella: PRODUCCION
DB = os.environ.get("K121_DB", "")
HASTA = os.environ.get("K121_HASTA", "")
RUTA_FP = "/api" + "/orderflow/footprint"
EJE_P = 76
RAZONES = (0, 0.236, 0.382, 0.5, 0.618, 0.786, 1)
SIGMAS = 2
MARCO_MS = {"1m": 60000, "5m": 300000, "15m": 900000, "1h": 3600000, "4h": 14400000, "1d": 86400000}
TOL_PX = 1.0
TOL_REL = 1e-6
ANCHO, ALTO = 1366, 768


def _modulo(nombre: str, fichero: str):
    spec = importlib.util.spec_from_file_location(nombre, AQUI / fichero)
    m = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stderr(io.StringIO()):
        spec.loader.exec_module(m)
    return m


class Canal(Exception):
    pass


class NoMedido(Exception):
    pass


def ms(iso: str) -> int:
    return round(datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp() * 1000)


def isoz(t: float) -> str:
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


# --------------------------------------------------------------------------------------------- la especificacion
def x_de(t: float, ts: list, marco_ms: int, x0: float, bs: float) -> float:
    """La x de un instante sobre las velas que hay: dentro de una vela, su fraccion desde el borde izquierdo; en lo que
    falta entre dos velas, el borde derecho de la anterior; antes de la primera o despues de la ultima, extrapolado con
    la duracion del marco. x0 es el centro de la vela 0 y bs el ancho de una vela."""
    i = bisect.bisect_right(ts, t) - 1
    if i < 0:
        return x0 - bs / 2 + (t - ts[0]) / marco_ms * bs
    frac = (t - ts[i]) / marco_ms
    if i < len(ts) - 1:
        frac = min(1.0, frac)
    return x0 + (i - 0.5) * bs + frac * bs


def t_de(x: float, ts: list, marco_ms: int, x0: float, bs: float) -> float:
    """El instante de una x: la inversa de x_de (dentro de la vela i, su fraccion; fuera de las velas, extrapolado)."""
    u = (x - x0) / bs + 0.5
    i = math.floor(u)
    if i < 0:
        return ts[0] + u * marco_ms
    i = min(i, len(ts) - 1)
    return ts[i] + (u - i) * marco_ms


def tramo(ta: float, tb: float, ts: list, marco_ms: int):
    """Las velas que se solapan con [min, max] de los dos instantes: (primera, ultima) o None."""
    a, b = min(ta, tb), max(ta, tb)
    dentro = [i for i, t in enumerate(ts) if t + marco_ms > a and t <= b]
    return (dentro[0], dentro[-1]) if dentro else None


def regresion(ys: list):
    """Minimos cuadrados con x = posicion en el tramo; None no cuenta pero guarda su x. Menos de 3: None."""
    pts = [(k, y) for k, y in enumerate(ys) if y is not None]
    n = len(pts)
    if n < 3:
        return None
    mx = math.fsum(k for k, _ in pts) / n
    my = math.fsum(y for _, y in pts) / n
    sxx = math.fsum((k - mx) ** 2 for k, _ in pts)
    pend = math.fsum((k - mx) * (y - my) for k, y in pts) / sxx
    orde = my - pend * mx
    sigma = math.sqrt(math.fsum((y - (orde + pend * k)) ** 2 for k, y in pts) / n)
    return {"pendiente": pend, "ordenada": orde, "sigma": sigma, "n": n}


def cerca(a, b, rel=TOL_REL, absoluta=1e-9) -> bool:
    return a is not None and b is not None and abs(a - b) <= max(absoluta, rel * max(abs(a), abs(b)))


# --------------------------------------------------------------------------------------------- el juicio
class Juez:
    def __init__(self):
        self.mal_: list[tuple[str, str]] = []

    def mal(self, brazo: str, pref: str, texto: str):
        self.mal_.append((brazo, f"{pref}: {texto}"))


def geo(pin: dict) -> dict:
    e = pin["escala"]
    ancho = pin["ancho"] - EJE_P
    bs = ancho / pin["ver"]
    alto = e["abajo"] - e["arriba"]
    return {"ancho": ancho, "bs": bs, "x0": ancho - (pin["fin"] + 0.5) * bs, "arriba": e["arriba"], "abajo": e["abajo"],
            "y": lambda p: e["arriba"] + (e["hi"] - float(p)) / (e["hi"] - e["lo"]) * alto}


def juzga_momento(J: Juez, pref: str, pin: dict, velas: list) -> None:  # noqa: C901 - un juicio por tipo de trazo
    if len(velas) != pin.get("n"):
        raise NoMedido(f"{pref}: las velas reconstruidas de la red son {len(velas)} y la pagina dice {pin.get('n')}")
    ts = [ms(v["ts"]) for v in velas]
    marco_ms = MARCO_MS[pin["marco"]]
    g = geo(pin)
    X = lambda t: x_de(t, ts, marco_ms, g["x0"], g["bs"])  # noqa: E731
    for z in pin.get("trazos") or []:
        nom = f"{z['tipo']} {z['id']}"
        pts, px = z["puntos"], z["px"]
        for k, (q, c) in enumerate(zip(pts, px, strict=False)):
            ex, ey = X(q["t"]), g["y"](q["p"])
            if abs(c["x"] - ex) > TOL_PX or abs(c["y"] - ey) > TOL_PX:
                J.mal("X", pref, f"{nom}: el punto {k} esta en ({c['x']:.2f}, {c['y']:.2f}) y su instante {isoz(q['t'])} "
                                 f"y su precio {q['p']:.2f} van en ({ex:.2f}, {ey:.2f})")
        if z["tipo"] == "nivel" and abs(z["y"] - g["y"](pts[0]["p"])) > TOL_PX:
            J.mal("X", pref, f"{nom}: la linea esta en y={z['y']} y su precio en {g['y'](pts[0]['p']):.2f}")
        elif z["tipo"] == "fib":
            p0, p1 = pts[0]["p"], pts[1]["p"]
            lin = z.get("lineas") or []
            raz = [ln["razon"] for ln in lin]
            if raz != list(RAZONES):
                J.mal("F", pref, f"{nom}: las razones son {raz} y son {list(RAZONES)}")
            for r in RAZONES:
                precio = p0 + r * (p1 - p0)
                ln = next((x for x in lin if cerca(x["precio"], precio, 1e-9)), None)
                if ln is None:
                    J.mal("F", pref, f"{nom}: falta la linea de {r} (precio {precio:.3f})")
                elif abs(ln["y"] - g["y"](precio)) > TOL_PX:
                    J.mal("F", pref, f"{nom}: la linea de {r} esta en y={ln['y']} y su precio en {g['y'](precio):.2f}")
        elif z["tipo"] == "canal":
            tr = tramo(pts[0]["t"], pts[1]["t"], ts, marco_ms)
            ys = [None if v.get("estado") == "hueco" or v.get("cierre") is None else float(v["cierre"])
                  for v in (velas[tr[0]:tr[1] + 1] if tr else [])]
            reg = regresion(ys)
            z["_mio"] = reg
            if reg is None:
                if z.get("pintado"):
                    J.mal("C", pref, f"{nom}: pinta un canal con {sum(y is not None for y in ys)} velas con cierre (< 3)")
                elif not z.get("motivo"):
                    J.mal("C", pref, f"{nom}: no pinta el canal y no dice por que")
                continue
            if not z.get("pintado"):
                J.mal("C", pref, f"{nom}: no pinta el canal con {reg['n']} velas con cierre ({z.get('motivo')})")
                continue
            for k in ("pendiente", "sigma", "ordenada"):
                if not cerca(z.get(k), reg[k]):
                    J.mal("C", pref, f"{nom}: {k} {z.get(k)!r} y es {reg[k]!r} ({reg['n']} cierres del tramo "
                                     f"{isoz(ts[tr[0]])}..{isoz(ts[tr[1]])})")
            if z.get("n") != reg["n"]:
                J.mal("C", pref, f"{nom}: n {z.get('n')} y son {reg['n']}")
            k = tr[1] - tr[0]
            for nombre, d in (("media", 0), ("alta", SIGMAS * reg["sigma"]), ("baja", -SIGMAS * reg["sigma"])):
                s = (z.get("rectas") or {}).get(nombre) or {}
                exp = (g["x0"] + tr[0] * g["bs"], g["y"](reg["ordenada"] + d),
                       g["x0"] + tr[1] * g["bs"], g["y"](reg["ordenada"] + reg["pendiente"] * k + d))
                got = tuple(s.get(c) for c in ("x0", "y0", "x1", "y1"))
                if None in got or any(abs(a - b) > TOL_PX for a, b in zip(got, exp, strict=True)):
                    J.mal("C", pref, f"{nom}: la recta {nombre} va de {got} y va de "
                                     f"({exp[0]:.2f}, {exp[1]:.2f}, {exp[2]:.2f}, {exp[3]:.2f})")


def juzga_clics(J: Juez, z: dict, vistos: list, velas_de_foto) -> None:
    """(K) cada punto guardado cae en el pixel de SU clic, con la escala y las velas que la pagina tenia al hacerlo."""
    nom = f"{z['tipo']} {z['id']}"
    if len(z["puntos"]) != len(vistos):
        J.mal("K", "al poner", f"{nom}: {len(vistos)} clics dejaron {len(z['puntos'])} puntos")
        return
    for k, ((cx, cy, foto), q) in enumerate(zip(vistos, z["puntos"], strict=True)):
        pin = foto["pin"]
        g = geo(pin)
        e = pin["escala"]
        ts = [ms(v["ts"]) for v in velas_de_foto(foto)]
        if not ts:
            raise NoMedido(f"al poner {nom}: sin velas en la pagina al hacer el clic {k}")
        mm = MARCO_MS[pin["marco"]]
        px, py = cx - foto["lienzo"][0], cy - foto["lienzo"][1]
        t_clic = t_de(px, ts, mm, g["x0"], g["bs"])
        p_clic = e["hi"] - (py - g["arriba"]) / (g["abajo"] - g["arriba"]) * (e["hi"] - e["lo"])
        ex, ey = x_de(q["t"], ts, mm, g["x0"], g["bs"]), g["y"](q["p"])
        if abs(ex - px) > TOL_PX or abs(ey - py) > TOL_PX:
            J.mal("K", "al poner", f"{nom}: el clic {k} fue en ({px:.2f}, {py:.2f}), que es {isoz(t_clic)} a {p_clic:.2f}, "
                                   f"y su punto guardado ({isoz(q['t'])} a {q['p']:.2f}) cae en ({ex:.2f}, {ey:.2f})")


def mismos(J: Juez, pref: str, antes: list, despues: list) -> None:
    a = {z["id"]: (z["tipo"], json.dumps(z["puntos"], sort_keys=True)) for z in antes}
    d = {z["id"]: (z["tipo"], json.dumps(z["puntos"], sort_keys=True)) for z in despues or []}
    if a != d:
        falta = sorted(set(a) - set(d))
        sobra = sorted(set(d) - set(a))
        cambia = sorted(i for i in set(a) & set(d) if a[i] != d[i])
        J.mal("G", pref, f"habia {len(a)} trazos y hay {len(d)}: faltan {falta}, sobran {sobra}, cambian {cambia}")


# --------------------------------------------------------------------------------------------- la pagina
class Red:
    """El portero: contesta cada respuesta del footprint SIN una vela (la misma por marco) y guarda lo que entrego."""

    def __init__(self, s):
        self.s, self.quitada, self.entregado, self.visto, self.fallo = s, {}, [], 0, None

    async def corre(self):
        while True:
            await asyncio.sleep(0.05)
            nuevos, self.visto = self.s.eventos[self.visto:], len(self.s.eventos)
            for ev in nuevos:
                if ev.get("method") == "Fetch.requestPaused":
                    try:
                        await self.atiende(ev["params"])
                    except Exception as e:  # noqa: BLE001 - el juicio lo dice como NO MEDIDO
                        self.fallo = f"{type(e).__name__}: {str(e)[:160]}"

    async def atiende(self, p: dict):
        rid = p["requestId"]
        if p.get("responseStatusCode") != 200:
            await self.s.pide("Fetch.continueRequest", requestId=rid)
            return
        marco = urllib.parse.parse_qs(urllib.parse.urlparse(p["request"]["url"]).query).get("marco", ["?"])[0]
        r = await self.s.pide("Fetch.getResponseBody", requestId=rid)
        cuerpo = json.loads(base64.b64decode(r["body"]) if r.get("base64Encoded") else r["body"])
        velas = cuerpo.get("velas") or []
        if marco not in self.quitada and len(velas) >= 3:
            self.quitada[marco] = velas[len(velas) - 16]["ts"] if len(velas) >= 60 else velas[len(velas) // 2]["ts"]
        cuerpo["velas"] = [v for v in velas if v["ts"] != self.quitada.get(marco)]
        self.entregado.append((marco, cuerpo))
        await self.s.pide("Fetch.fulfillRequest", requestId=rid, responseCode=200,
                          responseHeaders=[{"name": "Content-Type", "value": "application/json"}],
                          body=base64.b64encode(json.dumps(cuerpo).encode()).decode())


LEE = ("(() => { const h = window.FLUJO_HITOS || {}; if (h.repinta) h.repinta(); "
       "const e = document.getElementById('lienzo'); const r = e ? e.getBoundingClientRect() : null; "
       "return {pin: window.FLUJO_PINTADO || null, aplicadas: h.aplicadas || [], listo: !!h.listo, "
       "lienzo: r ? [r.left, r.top] : null, estado: window.FLUJO_TRAZOS || null}; })()")


async def lee(s) -> dict:
    await s.drena(0.3)
    return await s.evalua(LEE)


def velas_de(red: Red, foto: dict, K112) -> list:
    marco = foto["pin"]["marco"]
    por = {c.get("as_of"): c for m, c in red.entregado if m == marco}
    cuerpos = [por[a["as_of"]] for a in foto["aplicadas"] if a.get("ruta") == RUTA_FP and a.get("as_of") in por]
    velas = K112.modelo(cuerpos, marco) if cuerpos else []
    for x in velas:
        x["estado"] = x["_est"][0]
    return velas


async def espera(s, LISTO: str, cond: str, tope: float = 60) -> bool:
    for _ in range(int(tope / 0.2)):
        await s.drena(0.2)
        with contextlib.suppress(Exception):
            if await s.evalua(f"({LISTO}) && ({cond})"):
                await s.drena(0.8)
                return True
    return False


async def recorrido(K, T, K112, vista: str, cab: dict, J: Juez, huella) -> dict:  # noqa: C901 - el guion entero
    out = {"momentos": [], "canal_medido": 0}
    with K.Chromium(ANCHO, ALTO) as c:
        req = urllib.request.Request(f"http://127.0.0.1:{c.puerto}/json/new?about:blank", method="PUT")
        with urllib.request.urlopen(req, timeout=10) as r:
            destino = json.load(r)
        async with K.websockets.connect(destino["webSocketDebuggerUrl"], max_size=300 * 1024 * 1024) as ws:
            s = K.Sesion(ws)
            for metodo in ("Page.enable", "Runtime.enable", "Network.enable"):
                await s.pide(metodo)
            await s.pide("Network.setCacheDisabled", cacheDisabled=True)
            await s.pide("Emulation.setDeviceMetricsOverride", width=ANCHO, height=ALTO, deviceScaleFactor=1, mobile=False)
            if cab:
                await s.pide("Network.setExtraHTTPHeaders", headers=cab)
            await s.pide("Fetch.enable", patterns=[{"urlPattern": "*" + RUTA_FP + "*", "requestStage": "Response"}])
            red = Red(s)
            portero = asyncio.create_task(red.corre())
            try:
                await s.pide("Page.navigate", url=f"{raiz()}/flujo{vista}")
                if not await espera(s, T.LISTO, "window.FLUJO_PINTADO && FLUJO_PINTADO.n > 0", 90):
                    raise NoMedido(f"la vista {vista} no quedo pintada en 90 s" + (f" (red: {red.fallo})" if red.fallo else ""))
                v = T.Vista(K, s)
                f = await lee(s)
                if f["pin"].get("trazos") is None:
                    raise NoMedido("FALTA DESPLEGAR · la pagina no publica FLUJO_PINTADO.trazos")
                if f["pin"]["trazos"]:
                    raise NoMedido(f"la pagina abrio con {len(f['pin']['trazos'])} trazos en un perfil nuevo")
                velas = velas_de(red, f, K112)
                ts = [ms(x["ts"]) for x in velas]
                mm = MARCO_MS[f["pin"]["marco"]]
                hueco = next((i for i in range(1, len(ts)) if ts[i] - ts[i - 1] > mm), None)
                if hueco is None:
                    raise NoMedido(f"no hay vela que falte en las velas de la pagina (red: {red.fallo or 'sin fallo'})")
                pin = f["pin"]
                g = geo(pin)
                lx, ly = f["lienzo"]
                fin = int(pin["fin"])
                if not (pin["fin"] - pin["ver"] + 1 <= hueco - 22 and hueco + 8 <= fin):
                    raise NoMedido(f"la vela que falta (indice {hueco}) no deja sitio en la vista (fin {pin['fin']}, ver {pin['ver']})")
                alto = g["abajo"] - g["arriba"]
                ym = g["arriba"] + alto / 2
                P = lambda i, dy: (lx + g["x0"] + (i + 0.2) * g["bs"], ly + ym + dy * alto)  # noqa: E731
                gestos = [("nivel", [(lx + g["ancho"] * 0.55, ly + ym)]),
                          ("linea", [P(hueco - 12, -0.25), P(hueco + 8, 0.2)]),
                          ("fib", [P(hueco - 20, -0.3), P(hueco + 6, 0.3)]),
                          ("canal", [P(hueco - 4, 0), P(fin, 0)])]
                for tipo, clics in gestos:
                    await v.clic_en(f'#sel-trazo button[data-trazo="{tipo}"]')
                    vistos = []  # (x, y, la pagina justo antes del clic): su escala y sus velas son las de ESE momento
                    for x, y in clics:
                        x, y = round(x), round(y)  # un clientX entero: el pixel del clic es exacto
                        await v.mueve(x, y)
                        vistos.append((x, y, await lee(s)))
                        await v.clic(x, y)
                    antes = {z["id"] for z in vistos[0][2]["pin"]["trazos"] or []}
                    nuevos = [z for z in (await lee(s))["pin"]["trazos"] or [] if z["id"] not in antes]
                    if [z["tipo"] for z in nuevos] != [tipo]:
                        J.mal("K", "al poner", f"{len(clics)} clics con {tipo} dejaron {[z['tipo'] for z in nuevos]}")
                    else:
                        juzga_clics(J, nuevos[0], vistos, lambda foto: velas_de(red, foto, K112))
                    await v.tecla("Escape")
                f = await lee(s)
                tipos = sorted(z["tipo"] for z in f["pin"]["trazos"])
                if tipos != ["canal", "fib", "linea", "nivel"]:
                    J.mal("P", "al poner", f"cuatro gestos dejaron {tipos}")
                if (f["estado"] or {}).get("herramienta"):
                    J.mal("P", "al poner", f"Esc no solto la herramienta ({f['estado']['herramienta']})")
                puestos = f["pin"]["trazos"]

                async def juzga(pref: str, foto: dict):
                    vv = velas_de(red, foto, K112)
                    juzga_momento(J, pref, foto["pin"], vv)
                    for z in foto["pin"]["trazos"] or []:
                        if z["tipo"] == "canal":
                            out["canal_medido"] += 1 if z.get("_mio") else 0
                            out.setdefault("canal_n", []).append(f"{pref}: {z.get('n')} de {(z.get('tramo') or {}).get('velas')}")
                    out["momentos"].append(f"{pref} ({foto['pin']['marco']}, ver {foto['pin']['ver']:.1f}, "
                                           f"{len(foto['pin']['trazos'] or [])} trazos)")
                    sin_id = [{k: x for k, x in z.items() if k not in ("id", "sel")} for z in foto["pin"]["trazos"] or []]
                    huella.update(json.dumps([sin_id, [x["ts"] for x in vv]], sort_keys=True, default=str).encode())

                await juzga("puestos", f)
                # (H) sin herramienta, lejos de todo trazo: el arrastre mueve el grafico y no pone nada
                yn = next(z["y"] for z in puestos if z["tipo"] == "nivel")
                ya = g["arriba"] + 20 if abs(g["arriba"] + 20 - yn) > 15 else g["abajo"] - 20
                await v.arrastra(lx + 15, ly + ya, lx + 15 + 6 * g["bs"], ly + ya)
                f2 = await lee(s)
                if {z["id"] for z in f2["pin"]["trazos"]} != {z["id"] for z in puestos}:
                    J.mal("H", "arrastre sin herramienta", f"habia {len(puestos)} trazos y hay {len(f2['pin']['trazos'])}: "
                                                          "un gesto sin herramienta puso o quito un trazo")
                if abs(f2["pin"]["fin"] - f["pin"]["fin"]) < 1:
                    J.mal("H", "arrastre sin herramienta", f"el grafico no se movio (fin {f['pin']['fin']} -> {f2['pin']['fin']})")
                await juzga("tras el arrastre", f2)
                cx, cy = lx + g["ancho"] * 0.5, ly + ym
                await v.rueda(cx, cy, -240)
                await v.rueda(cx, cy, -240, "ctrl")
                f3 = await lee(s)
                if abs(f3["pin"]["ver"] - f2["pin"]["ver"]) < 0.5:
                    J.mal("P", "tras la rueda", f"la rueda no cambio las velas a la vista (ver {f2['pin']['ver']})")
                await juzga("tras la rueda", f3)
                await v.clic_en('#sel-marco button[data-valor="5m"]')
                if not await espera(s, T.LISTO, "FLUJO_PINTADO && FLUJO_PINTADO.marco === '5m'", 90):
                    raise NoMedido("la vista de 5m no quedo pintada en 90 s")
                f4 = await lee(s)
                mismos(J, "tras cambiar a 5m", puestos, f4["pin"]["trazos"])
                await juzga("en 5m", f4)
                red.entregado.clear()
                await s.pide("Page.reload", ignoreCache=True)
                await s.drena(1.0)
                if not await espera(s, T.LISTO, "FLUJO_PINTADO && FLUJO_PINTADO.n > 0", 90):
                    raise NoMedido("la vista no quedo pintada tras recargar")
                f5 = await lee(s)
                mismos(J, "tras recargar", puestos, f5["pin"]["trazos"])
                await juzga("tras recargar", f5)
                for e in v.excepciones():
                    J.mal("P", "la pagina", f"excepcion {e[:200]}")
                if red.fallo:
                    raise NoMedido(f"el portero de la red fallo: {red.fallo}")
                out["quitada"] = dict(red.quitada)
            finally:
                portero.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await portero
                await s.cierra()
    return out


def juzga() -> int:
    if not (shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
            or shutil.which("google-chrome-stable")):
        print("NO MEDIDO: sin Chromium en 143 no se puede mirar la pagina")
        return 2
    try:
        K = _modulo("k102_mesa", "K102-mesa.py")
    except SystemExit:
        print("NO MEDIDO: sin websockets no se habla CDP con el Chromium")
        return 2
    T = _modulo("k113_raton", "K113-raton.py")
    K112 = _modulo("k112", "K112-indicadores.py")
    sujeto = f"el ARBOL servido en {BASE} (celdas de {DB})" if BASE else "PRODUCCION (celdas por bin/prodsql)"
    hasta = datetime.fromisoformat(HASTA.replace("Z", "+00:00")) if HASTA else \
        datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    h = hasta.strftime("%Y-%m-%dT%H:%M:%SZ")
    vista = f"#BTC/1m/perp/ver=60/hasta={h}"
    declara = (f"vista {vista} a {ANCHO}x{ALTO} ({'K121_HASTA' if HASTA else 'la hora entera que acabo hace una hora'}),"
               " una vela quitada por marco en la red")
    try:
        n = sql("SELECT count(*) FROM orderflow_celda WHERE symbol = 'BTC' AND venue IN "
                "('binance_usdm','bybit_linear','okx_swap','bitget_usdt') "
                f"AND ts >= '{(hasta - timedelta(hours=1)).isoformat()}' AND ts < '{hasta.isoformat()}'")
    except Canal as exc:
        print(f"NO MEDIDO (CANAL): no se pudo contar orderflow_celda · sujeto: {sujeto} · {str(exc)[:160]}")
        return 2
    if not n or not n[0] or n[0][0] in ("", "0"):
        print(f"NO MEDIDO: sin dato · {declara} · sujeto: {sujeto}: ni una celda de BTC perpetuos en la hora de la vista")
        return 2
    try:
        cab = cabecera()
        st, _ = trae("/flujo", cab)
        st_js, js = trae("/static/flujo/flujo-trazos.js", cab)
    except (Canal, OSError, KeyError) as exc:
        print(f"NO MEDIDO (CANAL): no se pudo preguntar por la pagina · sujeto: {sujeto} · {str(exc)[:160]}")
        return 2
    if st == 404 or st_js == 404 or (st_js == 200 and b"pintaTrazos" not in js):
        print(f"NO MEDIDO: FALTA DESPLEGAR · {sujeto} no sirve los trazos (/flujo {st}, flujo-trazos.js {st_js}). "
              "El codigo no esta mal: no esta desplegado")
        return 2
    if st != 200 or st_js != 200:
        print(f"NO MEDIDO (CANAL): /flujo contesto {st} y flujo-trazos.js {st_js} · sujeto: {sujeto}")
        return 2
    J = Juez()
    huella = hashlib.sha256()
    try:
        out = asyncio.run(asyncio.wait_for(recorrido(K, T, K112, vista, cab, J, huella), 600))
    except NoMedido as exc:
        msg = str(exc)
        pre = "NO MEDIDO: FALTA DESPLEGAR" if msg.startswith("FALTA DESPLEGAR") else "NO MEDIDO"
        print(f"{pre} · {msg.removeprefix('FALTA DESPLEGAR · ')[:300]} · sujeto: {sujeto} · {declara}")
        return 2
    except (K.SystemExit2, Canal, T.Canal, OSError, TimeoutError) as exc:
        print(f"NO MEDIDO (CANAL): {type(exc).__name__}: {str(exc)[:200]} · sujeto: {sujeto}")
        return 2
    if not out["canal_medido"]:
        print(f"NO MEDIDO: sin dato · el canal no tuvo 3 velas con cierre en ningun momento ({'; '.join(out.get('canal_n', []))}) · sujeto: {sujeto}")
        return 2
    cola = (f"sujeto: {sujeto} · {declara} · momentos: {'; '.join(out['momentos'])} · velas quitadas {out['quitada']} · "
            f"huella {huella.hexdigest()[:12]}")
    if J.mal_:
        brazos = sorted({b for b, _ in J.mal_})
        print(f"ROJO  K121 · los trazos donde se pusieron · {len(J.mal_)} hallazgo(s) en {','.join(brazos)} · {cola}")
        vistos: dict[str, int] = {}
        for b, t in J.mal_:
            vistos[b] = vistos.get(b, 0) + 1
            if vistos[b] <= 6:
                print(f"   · ({b}) {t[:400]}")
        return 1
    print(f"VERDE  K121 · los trazos donde se pusieron: 7 clics en su pixel, 4 trazos en {len(out['momentos'])} momentos, x/y a 1 px, "
          f"Fibonacci en sus 7 precios, canal a 1e-6 ({out['canal_medido']} juicios) · {cola}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "juzga":
        sys.exit(juzga())
    print("uso: K121-trazos.py juzga", file=sys.stderr)
    sys.exit(2)
