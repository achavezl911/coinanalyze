#!/usr/bin/env python3
"""K123-espacio · el ayudante de K123-el-espacio-de-varios-graficos.sh (campana OF-6b). Uso: K123-espacio.py juzga

No importa nada de app/ ni de static/: lo que espera lo dice el encargo y se lee de cada marco por contentWindow
(FLUJO_PINTADO, location.hash) y del espacio (location.hash, la clase `foco`). De otros checks toma lo puro: el
Chromium y el CDP de K102-mesa.py y los gestos de K113-raton.py (Input.dispatchMouseEvent / dispatchKeyEvent).
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
import shutil
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta

AQUI = pathlib.Path(__file__).resolve().parent
H = os.environ.get("K123_HARNESS", "/srv/coinanalyze/harness")
BASE = os.environ.get("K123_BASE", "")  # sin ella: PRODUCCION
HASTA = os.environ.get("K123_HASTA", "")
ANCHO, ALTO = 1366, 768
PLAZO = 1.0  # s: un cambio en un marco sale en los otros (trazos) y en el hash del espacio
MARCOS = (("BTC", "1m"), ("BTC", "5m"), ("ETH", "5m"), ("BTC", "1h"))
NOMBRE = [f"{a} {m}" for a, m in MARCOS]
CERRADA = "frame-ancestors 'none'"
ABIERTA = "frame-ancestors 'self'"


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


def _env() -> dict:
    return dict(re.findall(r"^(\w+)=(\S+)", pathlib.Path(f"{H}/env").read_text(), re.M))


def raiz() -> str:
    return BASE.rstrip("/") if BASE else _env()["API_PROD"].rstrip("/")


def cabecera() -> dict:
    if BASE:
        return {}
    n = netrc.netrc(_env()["NETRC"])
    cred = next((n.authenticators(h) for h in n.hosts if n.authenticators(h)), None)
    if not cred:
        raise Canal("el netrc no da credencial")
    return {"Authorization": "Basic " + base64.b64encode(f"{cred[0]}:{cred[2]}".encode()).decode()}


def trae(ruta: str, cab: dict) -> tuple[int, dict]:
    ctx = ssl.create_default_context()
    ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE  # el certificado de 140 es propio
    try:
        with urllib.request.urlopen(urllib.request.Request(raiz() + ruta, headers=cab), timeout=30, context=ctx) as r:
            return r.status, dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers)


class Juez:
    def __init__(self):
        self.mal_: list[tuple[str, str]] = []

    def mal(self, brazo: str, texto: str):
        self.mal_.append((brazo, texto))


# Lo que se lee del espacio y de cada marco. La esquina del lienzo va en pixeles del espacio (el marco + su borde).
LEE = """(() => { const fs = [...document.querySelectorAll('iframe.marco')];
 return {top: location.hash, n: fs.length, act: fs.indexOf(document.activeElement),
  bordes: fs.map((f) => f.classList.contains('foco')),
  m: fs.map((f) => { const r = f.getBoundingClientRect(); const o = {hash: null, listo: false};
   try { const w = f.contentWindow, d = w.document, p = w.FLUJO_PINTADO, c = d.getElementById('lienzo');
    o.hash = w.location.pathname === '/flujo' ? w.location.hash : null;
    o.listo = !!(w.FLUJO_HITOS && w.FLUJO_HITOS.listo && p && p.n > 0);
    if (p) { o.marco = p.marco; o.fin = p.fin; o.ver = p.ver; o.ancho = p.ancho; o.escala = p.escala;
     o.trazos = p.trazos ? p.trazos.map((z) => ({tipo: z.tipo, id: z.id, puntos: z.puntos, y: z.y, sel: z.sel})) : null; }
    if (c) { const k = c.getBoundingClientRect(); o.lz = [r.left + f.clientLeft + k.left, r.top + f.clientTop + k.top]; }
    o.barras = [d.documentElement.scrollWidth - d.documentElement.clientWidth,
                d.documentElement.scrollHeight - d.documentElement.clientHeight];
    const b = d.querySelector('#sel-trazo button[data-trazo="nivel"]');
    if (b) { const k = b.getBoundingClientRect(); o.nivel = [r.left + f.clientLeft + k.left + k.width / 2,
                                                             r.top + f.clientTop + k.top + k.height / 2]; }
   } catch (e) { o.error = String(e).slice(0, 120); }
   return o; })}; })()"""


async def lee(s) -> dict:
    await s.drena(0.05)
    return await s.evalua(LEE)


async def hasta(s, pred, tope: float) -> tuple[bool, dict, float]:
    """Lee cada 0.1 s hasta que pred(foto) o el tope; devuelve (cumple, la ultima foto, segundos)."""
    t0 = time.monotonic()
    while True:
        f = await lee(s)
        dt = time.monotonic() - t0
        if pred(f) or dt >= tope:
            return bool(pred(f)), f, dt
        await s.drena(0.1)


def vistas_top(top: str) -> list[str]:
    partes = top.lstrip("#").split("&")
    return [urllib.parse.unquote(p[2:]) for p in partes if p.startswith("v=")]


def huella(m: dict):
    e = m.get("escala") or {}
    return (m.get("hash"), m.get("fin"), m.get("ver"), e.get("lo"), e.get("hi"))


def ids(m: dict, tipo: str = "nivel") -> dict:
    return {z["id"]: z for z in (m.get("trazos") or []) if z["tipo"] == tipo}


async def recorrido(K, T, url: str, cab: dict, J: Juez, out: dict) -> None:  # noqa: C901 - el guion entero
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
            v = T.Vista(K, s)
            listos = lambda f: f["n"] == 4 and all(m["listo"] for m in f["m"])  # noqa: E731

            async def abre(como: str) -> dict:
                ok, f, _ = await hasta(s, listos, 90)
                if not ok:
                    raise NoMedido(f"{como}: los 4 marcos no quedaron pintados en 90 s "
                                   f"({[(m.get('hash'), m.get('listo'), m.get('error')) for m in f['m']]})")
                await s.drena(1.0)
                return await lee(s)

            try:
                await s.pide("Page.navigate", url=url)
                f = await abre("al abrir")
                if any(m.get("trazos") is None for m in f["m"]):
                    raise NoMedido("FALTA DESPLEGAR · los marcos no publican FLUJO_PINTADO.trazos")
                if any(m["trazos"] for m in f["m"]):
                    raise NoMedido("los marcos abrieron con trazos en un perfil nuevo")
                for i, (a, mm) in enumerate(MARCOS):
                    h = f["m"][i]["hash"] or ""
                    if not h.startswith(f"#{a}/{mm}/") or f["m"][i]["marco"] != mm:
                        J.mal("P", f"al abrir el marco {i} es {h[:40]} ({f['m'][i]['marco']}) y se pidio {a} {mm}")
                    if max(f["m"][i]["barras"]) > 0:
                        J.mal("P", f"el marco {i} ({NOMBRE[i]}) tiene barra de desplazamiento: le sobran {f['m'][i]['barras']} px")
                out["momentos"].append("abierto")

                async def gesto(nombre: str, k: int, accion, cambia: bool = True) -> dict:
                    antes = await lee(s)
                    await accion()
                    ok, f, dt = await hasta(s, lambda g: all(vistas_top(g["top"])[i:i + 1] == [(m["hash"] or "#")[1:]]
                                                             for i, m in enumerate(g["m"])), PLAZO + 0.3)
                    if not ok:
                        malos = [i for i, m in enumerate(f["m"]) if vistas_top(f["top"])[i:i + 1] != [(m["hash"] or "#")[1:]]]
                        J.mal("H", f"{nombre} en {NOMBRE[k]}: a los {dt:.1f} s el hash del espacio no lleva la vista de "
                                   f"los marcos {malos} ({f['top'][:160]})")
                    for i in range(4):
                        a, d = huella(antes["m"][i]), huella(f["m"][i])
                        if i == k and cambia and a == d:
                            J.mal("M", f"{nombre} en {NOMBRE[k]} no cambio ese marco (fin {a[1]}, ver {a[2]})")
                        if i != k and a != d:
                            J.mal("M", f"{nombre} en {NOMBRE[k]} cambio el marco {i} ({NOMBRE[i]}): "
                                       f"fin {a[1]} -> {d[1]}, ver {a[2]} -> {d[2]}, hash {a[0]} -> {d[0]}")
                    out["momentos"].append(f"{nombre} {k}")
                    return f

                # cada marco, arrastrado al pasado: los demas no se mueven (y Fin tendra adonde ir en todos)
                for k in (0, 2, 3, 1):
                    lx, ly = f["m"][k]["lz"]
                    w = f["m"][k]["ancho"]
                    yy = ly + (f["m"][k]["escala"]["arriba"] + f["m"][k]["escala"]["abajo"]) / 2
                    f = await gesto("el arrastre", k, lambda lx=lx, w=w, yy=yy: v.arrastra(lx + w * 0.3, yy, lx + w * 0.6, yy))
                # el foco: un clic en el marco 1 se lo da, y el borde va con el
                lx, ly = f["m"][1]["lz"]
                cx, cy = lx + f["m"][1]["ancho"] * 0.4, ly + (f["m"][1]["escala"]["arriba"] + f["m"][1]["escala"]["abajo"]) / 2
                await v.clic(cx, cy)
                ok, f, dt = await hasta(s, lambda g: g["act"] == 1 and g["bordes"] == [False, True, False, False], PLAZO)
                if not ok:
                    J.mal("F", f"un clic en {NOMBRE[1]}: a los {dt:.1f} s el foco esta en {f['act']} y el borde en {f['bordes']}")
                f = await gesto("la rueda", 1, lambda: v.rueda(cx, cy, -240))
                f = await gesto("Fin", 1, lambda: v.tecla("End"))

                # los trazos: un NIVEL en BTC 1m sale en los BTC y no en ETH; borrado en BTC 5m no vuelve
                # BTC 1m tambien al presente: los dos rangos de precio contienen el ultimo cierre, y el nivel se pone en
                # un precio que BTC 5m tiene a la vista (para borrarlo alli con un clic)
                m0 = f["m"][0]
                await v.clic(m0["lz"][0] + m0["ancho"] * 0.4, m0["lz"][1] + (m0["escala"]["arriba"] + m0["escala"]["abajo"]) / 2)
                f = await gesto("Fin", 0, lambda: v.tecla("End"))
                m0, e0, e1 = f["m"][0], f["m"][0]["escala"], f["m"][1]["escala"]
                lo, hi = max(e0["lo"], e1["lo"]), min(e0["hi"], e1["hi"])
                if lo > hi:
                    raise NoMedido(f"con BTC 1m y BTC 5m al presente sus rangos no se tocan ({e0['lo']}-{e0['hi']} y {e1['lo']}-{e1['hi']})")
                yy = e0["arriba"] + (e0["hi"] - (lo + hi) / 2) / (e0["hi"] - e0["lo"]) * (e0["abajo"] - e0["arriba"])
                await v.clic(*m0["nivel"])
                y1 = m0["lz"][1] + yy
                await v.clic(m0["lz"][0] + m0["ancho"] * 0.5, y1)
                await v.tecla("Escape")
                f = await lee(s)
                puesto = list(ids(f["m"][0]).values())
                if len(puesto) != 1:
                    raise NoMedido(f"el nivel no quedo puesto en {NOMBRE[0]} ({len(puesto)} niveles)")
                z = puesto[0]
                ok, f, dt = await hasta(s, lambda g: all(z["id"] in ids(g["m"][i]) for i in (1, 3)), PLAZO)
                for i in (1, 3):
                    o = ids(f["m"][i]).get(z["id"])
                    if not o:
                        J.mal("T", f"el nivel puesto en {NOMBRE[0]} no sale en {NOMBRE[i]} en {PLAZO:.0f} s")
                    elif o["puntos"] != z["puntos"]:
                        J.mal("T", f"el nivel de {NOMBRE[0]} sale en {NOMBRE[i]} en {o['puntos']} y se puso en {z['puntos']}")
                if ids(f["m"][2]):
                    J.mal("T", f"el nivel puesto en {NOMBRE[0]} sale en {NOMBRE[2]}")
                out["momentos"].append(f"nivel a {dt:.1f} s")
                m1 = f["m"][1]
                o = ids(m1).get(z["id"])
                if o and not e1["arriba"] <= o["y"] <= e1["abajo"]:
                    raise NoMedido(f"el nivel cae en y={o['y']} de {NOMBRE[1]}, fuera de su zona de precio {e1['arriba']}-{e1['abajo']}")
                if o:
                    await v.clic(m1["lz"][0] + m1["ancho"] * 0.4, m1["lz"][1] + o["y"])
                    await v.tecla("Delete")
                    ok, f, dt = await hasta(s, lambda g: all(z["id"] not in ids(m) for m in g["m"]), PLAZO)
                    for i in (0, 1, 3):
                        if z["id"] in ids(f["m"][i]):
                            J.mal("T", f"el nivel borrado en {NOMBRE[1]} sigue en {NOMBRE[i]} a los {dt:.1f} s (en "
                                       f"{NOMBRE[1]} se pulso y={o['y']} con escala {m1['escala']} y quedo sel="
                                       f"{ids(f['m'][1]).get(z['id'], {}).get('sel')}; foco {f['act']})")
                    out["momentos"].append(f"borrado a {dt:.1f} s")
                    m0 = f["m"][0]
                    await v.clic(*m0["nivel"])
                    await v.clic(m0["lz"][0] + m0["ancho"] * 0.5, m0["lz"][1] + e0["arriba"] + (e0["abajo"] - e0["arriba"]) * 0.2)
                    await v.tecla("Escape")
                    ok, f, dt = await hasta(s, lambda g: all(len(ids(g["m"][i])) == 1 and z["id"] not in ids(g["m"][i])
                                                             for i in (0, 1, 3)), PLAZO + 0.3)
                    for i in (0, 1, 3):
                        if z["id"] in ids(f["m"][i]):
                            J.mal("T", f"el nivel borrado en {NOMBRE[1]} volvio en {NOMBRE[i]} cuando {NOMBRE[0]} puso otro")
                        elif len(ids(f["m"][i])) != 1:
                            J.mal("T", f"tras poner otro en {NOMBRE[0]}, {NOMBRE[i]} tiene {len(ids(f['m'][i]))} niveles y no 1")
                    out["momentos"].append(f"otro a {dt:.1f} s")

                # recargar: las cuatro vistas vuelven
                await s.drena(PLAZO)
                antes = await lee(s)
                await s.pide("Page.reload", ignoreCache=True)
                await s.drena(1.0)
                f = await abre("tras recargar")
                for i in range(4):
                    a, d = antes["m"][i], f["m"][i]
                    if a["hash"] != d["hash"] or a["marco"] != d["marco"]:
                        J.mal("R", f"tras recargar el marco {i} volvio con {d['hash']} ({d['marco']}) y era {a['hash']} ({a['marco']})")
                out["momentos"].append("recargado")
                out["finales"] = [m["hash"] for m in f["m"]]
                for e in v.excepciones():
                    J.mal("P", f"excepcion {e[:200]}")
            finally:
                await s.cierra()


def juzga() -> int:  # noqa: C901 - los NO MEDIDO van uno a uno
    if not (shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
            or shutil.which("google-chrome-stable")):
        print("NO MEDIDO: sin Chromium en 143 no se puede mirar /espacio")
        return 2
    try:
        K = _modulo("k102_mesa", "K102-mesa.py")
    except SystemExit:
        print("NO MEDIDO: sin websockets no se habla CDP con el Chromium")
        return 2
    T = _modulo("k113_raton", "K113-raton.py")
    sujeto = f"el ARBOL servido en {BASE}" if BASE else "PRODUCCION"
    fin = datetime.fromisoformat(HASTA.replace("Z", "+00:00")) if HASTA else \
        datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    h = fin.strftime("%Y-%m-%dT%H:%M:%SZ")
    vistas = [f"{a}/{m}/perp/hasta={h}" for a, m in MARCOS]
    ruta = "/espacio#d=4" + "".join(f"&v={x}" for x in vistas)
    declara = f"{ruta} a {ANCHO}x{ALTO}"
    J = Juez()
    try:
        cab = cabecera()
        st, _ = trae("/espacio", cab)
        if st == 404:
            print(f"NO MEDIDO: FALTA DESPLEGAR · {sujeto} no sirve /espacio (404). El codigo no esta mal: no esta desplegado")
            return 2
        vistos = []
        for r, abierta in (("/flujo", True), ("/espacio", False), ("/mesa", False), ("/libro", False),
                           ("/api/orderflow/footprint", False)):
            st, hd = trae(r, cab)
            hd = {k.lower(): x for k, x in hd.items()}
            csp, xfo = hd.get("content-security-policy", ""), hd.get("x-frame-options", "")
            vistos.append(f"{r} {st}")
            quiere = (ABIERTA, "SAMEORIGIN") if abierta else (CERRADA, "DENY")
            if quiere[0] not in csp or xfo != quiere[1] or (ABIERTA if not abierta else CERRADA) in csp:
                J.mal("C", f"{r} ({st}) da «{(re.search(r'frame-ancestors [^;]*', csp) or [''])[0]}» + X-Frame-Options "
                           f"«{xfo}» y tiene que dar «{quiere[0]}» + «{quiere[1]}»")
    except (Canal, OSError, KeyError) as exc:
        print(f"NO MEDIDO (CANAL): no se pudo preguntar por las paginas · sujeto: {sujeto} · {str(exc)[:160]}")
        return 2
    out = {"momentos": []}
    try:
        asyncio.run(asyncio.wait_for(recorrido(K, T, raiz() + ruta, cab, J, out), 400))
    except NoMedido as exc:
        msg = str(exc)
        pre = "NO MEDIDO: FALTA DESPLEGAR" if msg.startswith("FALTA DESPLEGAR") else "NO MEDIDO"
        print(f"{pre} · {msg.removeprefix('FALTA DESPLEGAR · ')[:300]} · sujeto: {sujeto} · {declara}")
        return 2
    except (K.SystemExit2, T.Canal, OSError, TimeoutError) as exc:
        print(f"NO MEDIDO (CANAL): {type(exc).__name__}: {str(exc)[:200]} · sujeto: {sujeto}")
        return 2
    hu = hashlib.sha256(json.dumps([J.mal_, out.get("finales")], sort_keys=True).encode()).hexdigest()[:12]
    cola = f"huella {hu} · sujeto: {sujeto} · {declara} · cabeceras de {', '.join(vistos)} · momentos: {'; '.join(out['momentos'])}"
    if J.mal_:
        brazos = sorted({b for b, _ in J.mal_})
        print(f"ROJO  K123 · el espacio de varios graficos · {len(J.mal_)} hallazgo(s) en {','.join(brazos)} · {cola}")
        cuenta: dict[str, int] = {}
        for b, t in J.mal_:
            cuenta[b] = cuenta.get(b, 0) + 1
            if cuenta[b] <= 6:
                print(f"   · ({b}) {t[:400]}")
        return 1
    print(f"VERDE  K123 · el espacio de varios graficos: 4 marcos sin barras, arrastre/rueda/Fin solo en su marco, foco con "
          f"borde, hash en {PLAZO:.0f} s, un nivel entre los BTC y no en ETH, el borrado no vuelve, la recarga devuelve "
          f"las 4 vistas, cabeceras por ruta · {cola}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "juzga":
        sys.exit(juzga())
    print("uso: K123-espacio.py juzga", file=sys.stderr)
    sys.exit(2)
