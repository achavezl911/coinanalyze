"""K114 · el raton, la pantalla y su red en /libro (campana 149, ronda C). Lo invoca K114-el-raton-del-libro.sh.

Gestos REALES por CDP (Input.dispatchMouseEvent / dispatchKeyEvent) en un Chromium sin cabeza sobre la pagina servida;
tras cada gesto se lee el contrato (window.LIBRO_PINTADO.mapa.eje, LIBRO_CRUZ, EL_MAPA.estado()) y se contrasta con lo
que llego por la red (las respuestas de /api/libro/*, juntadas con el esperado_mapa de K111) y con el DOM. Las partes
puras salen de K102 (Chromium, Sesion), K111 (la vista, las columnas, la capa honda) y K113 (los gestos, el juez, el
color): se importan, no se copian.

Vistas: la de por omision en vivo a 1920x1080 (todos los gestos) y a 1366x768; BTC perp 1 h del pasado (hasta=); ETH en
USD del pasado (K114_ETH, por omision `spot`; el banco de K111 no trae spot de ETH y su control usa `okx_swap`).
Brazos (cualquiera = ROJO; sin canal = NO MEDIDO):
  (P) sin excepciones; 0 peticiones a fotos u honda por gestos dentro de lo cargado (la vista del pasado)
  (C) la celda bajo el cursor, recalculada de las respuestas crudas, = LIBRO_CRUZ, la ficha del DOM y #lectura; las
      etiquetas de los ejes al paso; la escalera resalta ese precio y solo ese
  (R) cada gesto mueve lo que debe y nada mas: I-01 (ancla en tiempo y en precio), I-02, I-03 (MANUAL), I-04, cada
      opcion del menu del eje (y con Ninguno no recentra), I-05 y H-10 con columnas vivas llegando, I-06
  (E) E-01, E-02 (el comprador de /flujo y la mesa, dE2000 >= 20 entre lados, tambien con las tres simulaciones), E-03,
      E-04
  (A) la ayuda se abre y se cierra; cada gesto que nombra lo ejerce (R), y cada gesto de (R) lo nombra; los parrafos
      del pie ya no estan en la vista
Salida: 0 VERDE · 1 ROJO · 2 NO MEDIDO.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from decimal import Decimal

AQUI = pathlib.Path(__file__).resolve().parent
for _k in ("K111_BASE", "K113_BASE"):
    os.environ.setdefault(_k, os.environ.get("K114_BASE", ""))
HASTA = os.environ.get("K114_HASTA", "")
ETH = os.environ.get("K114_ETH", "spot")
ESPERA_VIVA_S = float(os.environ.get("K114_ESPERA_VIVA", "45"))


def _modulo(nombre: str, fichero: str):
    spec = importlib.util.spec_from_file_location(nombre, AQUI / fichero)
    m = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stderr(io.StringIO()):
        spec.loader.exec_module(m)
    return m


K111 = _modulo("k111", "K111-libro.py")
K113 = _modulo("k113", "K113-raton.py")
RUTAS = {"fotos": K111.RUTA_FOTOS, "honda": K111.RUTA_HONDA, "huella": K111.RUTA_HUELLA}
# lo que la ayuda puede nombrar (el texto de cada <b>) -> el gesto de (R) que lo ejerce; None: no es un gesto
VOCABULARIO = {"rueda": "rueda", "mayús + rueda": "mayus", "ctrl + rueda": "ctrl", "manual": None,
               "rueda o arrastre sobre el eje de precio": "eje_precio", "rueda o arrastre sobre el eje de tiempo": "eje_tiempo",
               "arrastrar el mapa": "arrastre", "doble clic en el eje de precio": "doble_clic",
               "clic derecho en el eje de precio": "menu", "← →": "flechas", "re pág / av pág": "paginas",
               "inicio": "inicio", "fin": "fin", "presente": "presente", "c": "c", "?": "ayuda", "esc": "esc"}

LEE = r"""(() => { const m = (window.LIBRO_PINTADO || {}).mapa || null; const cv = document.getElementById('mapa');
  const r = cv.getBoundingClientRect(); const st = (typeof EL_MAPA !== 'undefined' && EL_MAPA) ? EL_MAPA.estado() : null;
  return {cv: [cv.width, cv.height, cv.style.height], e: m ? m.eje : null, pres: m ? m.presente : null, st, r: [r.left, r.top, r.width, r.height],
          menu: !document.getElementById('menu-eje').hidden, ayuda: document.getElementById('ayuda').open,
          guardado: (() => { try { return localStorage.getItem('libro.recentrado'); } catch (x) { return 'x'; } })()}; })()"""
CRUZ = r"""(() => { const c = window.LIBRO_CRUZ || null; const fi = document.getElementById('ficha');
  const caja = document.querySelector('#escalera .esc-tabla'); const th = document.querySelector('#esc-filas thead');
  const filas = [...document.querySelectorAll('#esc-filas tbody tr')];
  const en = (tr) => { if (!caja || !tr) return false; const a = caja.getBoundingClientRect(); const r = tr.getBoundingClientRect();
    const m = (r.top + r.bottom) / 2; return m > a.top + (th ? th.getBoundingClientRect().height : 0) && m < a.bottom; };
  return {c, dom: fi && !fi.hidden ? [...fi.querySelectorAll('div[data-campo]')].map((d) => [d.dataset.campo, d.textContent,
          d.className]) : null, lectura: (document.getElementById('lectura') || {}).textContent || '',
          marcadas: filas.filter((tr) => tr.classList.contains('cruz-fila')).map((tr) => tr._k),
          fila_en_vista: c ? en(filas.find((tr) => tr._k === c.nivel)) : false}; })()"""
AYUDA = r"""(() => { const d = document.getElementById('ayuda'); const h = [...d.querySelectorAll('h2')]
  .find((x) => /rat/.test(x.textContent)); const p = h ? h.nextElementSibling : null;
  return {b: p ? [...p.querySelectorAll('b')].map((x) => x.textContent.replace(/\s+/g, ' ').trim()) : null,
          pie: !!document.querySelector('footer.leyenda'), cuerpo: document.body.innerText}; })()"""
COLOR = r"""(() => { const s = getComputedStyle(document.documentElement); const g = (k) => s.getPropertyValue(k).trim();
  const c = document.createElement('canvas').getContext('2d'); c.font = '10px ui-monospace, monospace';
  const f = getComputedStyle(document.getElementById('ficha'));
  return {bg: g('--bg'), tx: g('--tx'), comprador: g('--comprador'), vendedor: g('--vendedor'), compra: MAPA_COLOR.compra,
          venta: MAPA_COLOR.venta, digitos: '0123456789'.split('').map((d) => c.measureText(d).width),
          ficha: [f.fontVariantNumeric, f.fontFamily],
          e04: (typeof cifraE04 === 'function') ? [cifraE04(999, 0), cifraE04(10000, 0), cifraE04(1234567, 0)] : null}; })()"""


class Vista(K113.Vista):
    """La de K113 con la red de /libro: las respuestas de fotos, honda y footprint con su cuerpo, en orden."""

    async def recoge_red(self):
        for ev in self.s.eventos[self.vistos:]:
            p, m = ev.get("params", {}), ev.get("method")
            if m == "Network.requestWillBeSent":
                u = p["request"]["url"]
                tipo = next((t for t, r in RUTAS.items() if r in u), None)
                if tipo:
                    self.red[p["requestId"]] = {"url": u, "tipo": tipo, "estado": None, "cuerpo": None}
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

    async def lee(self) -> dict:
        for _ in range(50):
            await self.s.drena(0.1)
            a = await self.evalua(LEE)
            if a.get("e"):
                return a
        m = await self.evalua("JSON.stringify(Object.keys((window.LIBRO_PINTADO || {}).mapa || {}))")
        raise K113.Canal(f"LIBRO_PINTADO.mapa sin eje en 5 s: {m} · {str(a)[:200]}")

    async def en(self, x, y, accion, *a, **kw):
        """un gesto en coordenadas del LIENZO"""
        r = (await self.evalua("(() => { const r = document.getElementById('mapa').getBoundingClientRect(); "
                               "return [r.left, r.top]; })()"))
        if accion == self.arrastra:  # el destino del arrastre tambien va en coordenadas del lienzo
            a = (r[0] + a[0], r[1] + a[1]) + tuple(a[2:])
        await accion(r[0] + x, r[1] + y, *a, **kw)


async def abre(K, vista: str, ancho: int, alto: int, cab: dict, vivo: bool, recorrido) -> dict:
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
            await s.pide("Page.navigate", url=f"{K111.raiz()}/libro{vista}")
            v = Vista(K, s)
            listo = False
            for _ in range(250):
                await s.drena(0.2)
                with contextlib.suppress(K.SystemExit2):
                    listo = await s.evalua("!!(window.LIBRO_HITOS && LIBRO_HITOS.listo" + (" && LIBRO_HITOS.vivo_listo" if vivo else "") + ")")
                if listo:
                    break
            await s.drena(1.0)
            for _ in range(int(ESPERA_VIVA_S * 2) if listo and vivo else 0):  # sin fotos, el mapa espera a la primera viva
                if await s.evalua("!!((window.LIBRO_PINTADO || {}).mapa || {}).eje"):
                    break
                await s.drena(1.0)
            out = {"vista": vista, "pantalla": [ancho, alto], "listo": listo}
            if listo:
                await recorrido(v, out)
            out["excepciones"] = v.excepciones()
            await s.cierra()
    return out


# --------------------------------------------------------------------------------------------- (C) la celda
def esperado(v: Vista, vista: str) -> tuple[dict, dict | None]:
    e = K111.lee_vista(vista)
    vio = {t: [{"url": x["url"], "cuerpo": x["cuerpo"]} for x in v.red.values() if x["tipo"] == t and x["cuerpo"]]
           for t in RUTAS}
    return e, K111.esperado_mapa(vio, e)


def blancos(esp: dict, e: dict) -> list[tuple[str, int, int]]:
    """Las celdas a las que se lleva el raton: una con capa honda, una solo del vivo, una desconocida, una columna sin
    foto, y el centro de la ultima columna (la escalera la tiene a la vista)."""
    cols = esp["cols"]
    j1 = min(int(e["fin"]), len(cols) - 1)
    j0 = max(0, int(-(-(e["fin"] + 1 - e["ancho"] / e["columna"]) // 1)))
    quiero: dict = {}
    for j in range(j1, j0 - 1, -1):
        c, s = cols[j], cols[j]["suma"]
        if c["estado"] != "foto":
            quiero.setdefault("sin_foto", (j, (e["lo"] + e["hi"]) // 2))
            continue
        if not s:
            continue
        for k in range(e["hi"], e["lo"] - 1, -1):
            n, h = s["n"].get(k, 0), (s.get("h") or {}).get(k, 0)
            if h and n:
                quiero.setdefault("honda", (j, k))
            elif n and not h:
                quiero.setdefault("vivo", (j, k))
            elif not n:
                quiero.setdefault("desconocida", (j, k))
    quiero["escalera"] = (j1, (e["lo"] + e["hi"]) // 2)
    return [(q, j, k) for q, (j, k) in quiero.items()]


def num(t: str) -> Decimal:
    return Decimal(re.sub(r"[^\d.\-]", "", t or "") or "NaN")


def cerca(a, b) -> bool:
    return a is not None and b is not None and abs(float(a) - float(b)) <= 1e-9 * max(1.0, abs(float(b)))


def juzga_servido(J, p: str, f: dict, j: int, k: int, esp: dict, ve: dict) -> None:
    """la ficha contra lo servido: la columna j de las respuestas crudas, juntadas como K111"""
    col = esp["cols"][j]
    s, paso, u = col["suma"], esp["d"]["paso"], ve["unidad"]
    if K111.epoch_ms(f["ts"]) != col["ts"]:
        J.mal("C", p, f"la ficha es de {f['ts']} y la columna {j} servida es de {K111.isoz(col['ts'])}")
    n = s["n"].get(k, 0) if s and col["estado"] == "foto" else 0
    if col["estado"] != "foto" and f["estado"] != col["estado"]:
        J.mal("C", p, f"la columna servida es «{col['estado']}» y la ficha dice «{f['estado']}»")
    elif col["estado"] == "foto" and not n and (f["estado"] != "desconocido" or f["compra"] is not None or f["venta"] is not None):
        J.mal("C", p, f"ningun venue conoce el nivel {k} y la ficha dice estado «{f['estado']}», compra {f['compra']}, "
                      f"venta {f['venta']} (tiene que ser desconocido, sin cifras)")
    elif n:
        qc, qv = K111.unidad(s["c"][k], k, paso, u), K111.unidad(s["v"][k], k, paso, u)
        if not cerca(f["compra"], qc) or not cerca(f["venta"], qv) or f["n"] != n:
            J.mal("C", p, f"la ficha dice compra {f['compra']} venta {f['venta']} de {f['n']} venues y lo servido da "
                          f"{qc} / {qv} de {n}")
        hs = {(h["venue"], round(h["edad_s"])) for h in (s.get("honda") or [])}
        fh = f.get("honda") or []
        if len(fh) != (s.get("h") or {}).get(k, 0):
            J.mal("C", p, f"la ficha trae {len(fh)} venues de la capa honda y lo servido {(s.get('h') or {}).get(k, 0)}")
        for h in fh:
            if not isinstance(h.get("edad_s"), (int, float)) or (h["venue"], round(h["edad_s"])) not in hs \
                    or f"{h['venue']} {round(h['edad_s'])} s" not in f["texto"]:
                J.mal("C", p, f"la capa honda de {h.get('venue')} sale con edad {h.get('edad_s')} y lo servido dice "
                              f"{sorted(hs)}; el texto: «{f['texto'][:160]}»")


def juzga_celda(J, pref: str, q: str, j: int, k: int, x: float, y: float, e: dict, esp: dict, vis: dict, info: dict,
                ve: dict) -> None:
    c = info["c"]
    p = f"{pref} [{q} j={j} k={k}]"
    if not c:
        J.mal("C", p, f"el raton en ({x:.0f}, {y:.0f}) del lienzo y no hay LIBRO_CRUZ")
        return
    f = c["ficha"]
    if (c["columna"], c["nivel"], f["columna"], f["nivel"]) != (j, k, j, k):
        J.mal("C", p, f"la cruz dice columna {c['columna']} nivel {c['nivel']} y la ficha columna {f['columna']} nivel "
                      f"{f['nivel']}: bajo el cursor esta la columna {j} nivel {k}")
        return
    paso = esp["d"]["paso"] if esp else ve["paso"]
    for h in f.get("honda") or []:  # la edad de la capa honda: un numero, y dicha en el texto
        if not isinstance(h.get("edad_s"), (int, float)) or f"{h['venue']} {round(h['edad_s'])} s" not in f["texto"]:
            J.mal("C", p, f"la capa honda de {h.get('venue')} sale con edad {h.get('edad_s')}; el texto: «{f['texto'][:160]}»")
    if esp:
        juzga_servido(J, p, f, j, k, esp, ve)
    if num(c["precio"]) != Decimal(k) * Decimal(paso) or c["ejes"]["precio"] != c["precio"] \
            or abs(c["ejes"]["y"] - y) > e["fila"] / 2 + 1 or abs(c["ejes"]["x"] - x) > e["columna"] / 2 + 1:
        J.mal("C", p, f"la etiqueta del eje de precio dice {c['ejes']['precio']} en y={c['ejes']['y']} y el nivel {k} al "
                      f"paso {paso} es {Decimal(k) * Decimal(paso)} en y={y:.1f}")
    if c["ejes"]["hora"] != f["ts"][11:19]:
        J.mal("C", p, f"la etiqueta del eje de tiempo dice {c['ejes']['hora']} y la columna es de {f['ts']}")
    lineas = [[a, b] for a, b in f["lineas"]]
    if info["dom"] is None or [d[:2] for d in info["dom"]] != lineas:
        J.mal("C", p, f"la ficha del DOM no es la del contrato: {str(info['dom'])[:160]}")
    elif f["lado"] and not any(d[0] == f["lado"] and "domina" in d[2] for d in info["dom"]):
        J.mal("C", p, f"la ficha no marca el lado mayor «{f['lado']}»")
    if info["lectura"] != f["texto"]:
        J.mal("C", p, f"#lectura dice «{info['lectura'][:100]}» y la ficha «{f['texto'][:100]}»")
    if [m for m in info["marcadas"] if m != k] or (info["fila_en_vista"] and k not in info["marcadas"]):
        J.mal("C", p, f"la escalera resalta los niveles {info['marcadas']} con la cruz en {k} "
                      f"(su fila {'esta' if info['fila_en_vista'] else 'no esta'} a la vista)")


async def celdas(v: Vista, J, pref: str, vista: str) -> int:
    await v.recoge_red()
    ve, esp = esperado(v, vista)
    e = (await v.lee())["e"]
    if not esp:  # sin fotos (el banco en vivo): la columna mas nueva barrida, contra el contrato y el DOM
        j, hechas, honda = e["n"] - 1, 0, 0
        for k in range(e["hi"], e["lo"] - 1, -max(1, (e["hi"] - e["lo"]) // 40)):
            x, y = e["ancho"] - (e["fin"] - j + 0.5) * e["columna"], (e["hi"] - k + 0.5) * e["fila"]
            await v.en(x, y, v.mueve)
            info = await v.evalua(CRUZ)
            if info["c"] and (info["c"]["ficha"].get("honda") or hechas < 3):
                juzga_celda(J, pref, "vivo", j, k, x, y, e, None, {}, info, ve)
                hechas += 1
                honda += bool(info["c"]["ficha"].get("honda"))
        J.info.append(f"{pref} (C) sin fotos servidas: {hechas} celdas de la columna viva contra el contrato y el DOM, "
                      f"{honda} con capa honda")
        return hechas
    hechas, escalera = 0, False
    for q, j, k in blancos(esp, e):
        for _ in range(3):  # en vivo llegan columnas: si la geometria se movio durante el gesto, se repite
            e = (await v.lee())["e"]
            x, y = e["ancho"] - (e["fin"] - j + 0.5) * e["columna"], (e["hi"] - k + 0.5) * e["fila"]
            await v.en(x, y, v.mueve)
            await v.s.drena(0.2)
            info = await v.evalua(CRUZ)
            d = (await v.lee())["e"]
            if (d["fin"], d["n"], d["lo"], d["hi"]) == (e["fin"], e["n"], e["lo"], e["hi"]):
                break
        juzga_celda(J, pref, q, j, k, x, y, e, esp, {}, info, ve)
        hechas += 1
        escalera = escalera or info["fila_en_vista"]
    J.info.append(f"{pref} (C) {hechas} celdas: {', '.join(q for q, _, _ in blancos(esp, e))}"
                  + ("" if escalera else "; ninguna con su fila de la escalera a la vista"))
    return hechas


# --------------------------------------------------------------------------------------------- (R) los gestos
def kc(e: dict, y: float) -> float:
    return e["hi"] + 1 - y / e["fila"]


def fil(e: dict) -> float:
    return e["vertical"].get("filas") or (e["hi"] - e["lo"] + 1)


def cen(e: dict) -> float:
    c = e["vertical"].get("centro")
    return c if c is not None else (e["lo"] + e["hi"]) / 2


def ja(e: dict, x: float) -> float:
    return e["fin"] + 1 - (e["ancho"] - x) / e["columna"]


async def gestos(v: Vista, J, pref: str, hechos: set, vivo: bool) -> None:  # noqa: C901 - un juicio por gesto
    a = await v.lee()
    e = a["e"]
    W, H = a["r"][2], a["r"][3]
    xm, ym, xp, yt = e["ancho"] / 2, e["alto"] / 2, W - 38, H - 10

    def mal(g: str, t: str):
        J.mal("R", pref, f"{g}: {t}")
    await v.en(xm, ym, v.clic)
    # I-01 en tiempo: la columna bajo el cursor se queda donde esta
    x0 = e["ancho"] * 0.25
    await v.en(x0, ym, v.rueda, -120)
    b = (await v.lee())["e"]
    hechos.add("rueda")
    if b["ver"] == e["ver"] or abs(ja(b, x0) - ja(e, x0)) > 1:
        mal("I-01 rueda", f"ver {e['ver']} -> {b['ver']}; la columna bajo x={x0:.0f} {ja(e, x0):.2f} -> {ja(b, x0):.2f}")
    e = b
    await v.en(xm, ym, v.rueda, -120, "shift")
    b = (await v.lee())["e"]
    hechos.add("mayus")
    paso = max(1, round(e["ver"] / 10))
    if b["ver"] != e["ver"] or b["fin"] != max(e["ver"] - 1, e["fin"] - paso):
        mal("Mayus + rueda", f"fin {e['fin']} -> {b['fin']} y ver {e['ver']} -> {b['ver']} (tiene que retroceder {paso} "
                             "con ver quieto)")
    e = b
    # I-01 en precio: el precio bajo el cursor quieto, MANUAL, el tiempo quieto
    y0 = e["alto"] * 0.3
    await v.en(xm, y0, v.rueda, -120, "ctrl")
    b = (await v.lee())["e"]
    hechos.add("ctrl")
    if b["vertical"]["modo"] != "manual" or abs(kc(b, y0) - kc(e, y0)) > 1 or (b["fin"], b["ver"]) != (e["fin"], e["ver"]) \
            or fil(b) >= fil(e) or "MANUAL" not in (b["vertical"].get("texto") or ""):
        mal("I-01 Ctrl + rueda", f"modo {b['vertical']['modo']} «{b['vertical'].get('texto')}»; filas {fil(e)} -> {fil(b)}; "
                                 f"el precio bajo y={y0:.0f} {kc(e, y0):.2f} -> {kc(b, y0):.2f}; fin {e['fin']} -> {b['fin']}")
    # I-04: doble clic en el eje de precio vuelve al modo de antes
    await v.en(xp, ym, v.clic, "left", 2)
    b = (await v.lee())["e"]
    hechos.add("doble_clic")
    if b["vertical"]["modo"] == "manual":
        mal("I-04 doble clic", f"sigue en MANUAL: {b['vertical']}")
    e = b
    # I-02: rueda y arrastre en el eje de precio escalan con el centro quieto y el tiempo quieto
    await v.en(xp, ym, v.rueda, -120)
    b = (await v.lee())["e"]
    if fil(b) >= fil(e) or abs(cen(b) - cen(e)) > 1 or (b["fin"], b["ver"]) != (e["fin"], e["ver"]) \
            or b["vertical"]["modo"] == "manual":
        mal("I-02 rueda en el eje", f"filas {fil(e)} -> {fil(b)}, centro {cen(e)} -> {cen(b)}, fin {e['fin']} -> {b['fin']}, "
                                    f"modo {b['vertical']['modo']}")
    e = b
    await v.en(xp, ym, v.arrastra, xp, ym - 60)
    b = (await v.lee())["e"]
    hechos.add("eje_precio")
    if fil(b) == fil(e) or (b["fin"], b["ver"]) != (e["fin"], e["ver"]):
        mal("I-02 arrastre en el eje", f"filas {fil(e)} -> {fil(b)}, fin {e['fin']} -> {b['fin']}")
    e = b
    H2 = (await v.lee())["r"][3]  # en vivo el lienzo cambia de alto cuando #lectura cambia de lineas
    if abs(H2 - H) > 1:
        J.info.append(f"{pref} el lienzo paso de {H:.0f} a {H2:.0f} px de alto durante los gestos")
    H, yt = H2, H2 - 10
    await v.en(xm, yt, v.rueda, -120)
    b = (await v.lee())["e"]
    quien = await v.evalua(f"(() => {{ const r = document.getElementById('mapa').getBoundingClientRect(); "
                           f"const q = document.elementFromPoint(r.left + {xm}, r.top + {yt}); "
                           f"return q ? (q.id || q.className || q.tagName) : null; }})()")
    await v.en(xm, yt, v.arrastra, xm + 100, yt)
    c = (await v.lee())["e"]
    alto2 = await v.evalua("[document.getElementById('mapa').getBoundingClientRect().height, "
                           "document.getElementById('lectura').getBoundingClientRect().height]")
    hechos.add("eje_tiempo")
    if not c["ver"] < b["ver"] < e["ver"] or fil(c) != fil(e):
        mal("eje de tiempo", f"ver {e['ver']} -> {b['ver']} (rueda) -> {c['ver']} (arrastre a la derecha en y={yt:.0f} de "
                             f"{H:.0f}, el lienzo {a['cv']}, bajo el punto {quien}, despues lienzo y lectura {alto2}); fin {b['fin']} -> {c['fin']}; filas {fil(e)} -> {fil(c)}")
    e = c
    # I-03: el mapa en vertical pasa a MANUAL y se mueve lo arrastrado; en horizontal, el tiempo y nada del precio
    await v.en(xm, ym, v.arrastra, xm, ym + 80)
    b = (await v.lee())["e"]
    d = cen(b) - (e["lo"] + e["hi"]) / 2  # el arrastre parte del centro PINTADO
    if b["vertical"]["modo"] != "manual" or abs(d - 80 / e["fila"]) > 1.5 or b["ver"] != e["ver"]:
        mal("I-03 arrastre vertical", f"modo {b['vertical']['modo']}, el centro se movio {d:.1f} filas (80 px son "
                                      f"{80 / e['fila']:.1f}), ver {e['ver']} -> {b['ver']}, [{e['lo']}, {e['hi']}] -> "
                                      f"[{b['lo']}, {b['hi']}] en datos {e.get('datos')}")
    e = b
    await v.en(xm, ym, v.arrastra, xm + 200, ym)
    b = (await v.lee())
    st, b = b["st"], b["e"]
    hechos.add("arrastre")
    quiere = max(e["ver"] - 1, e["fin"] - 200 * e["ver"] / e["ancho"])
    if abs(b["fin"] - quiere) > 1.5 or fil(b) != fil(e) or b["vertical"]["modo"] != "manual" or st["sigue"]:
        mal("I-03 arrastre horizontal", f"fin {e['fin']} -> {b['fin']} (200 px llevan a {quiere:.1f}), centro {cen(e)} -> "
                                        f"{cen(b)}, filas {fil(e)} -> {fil(b)}, sigue {st['sigue']}")
    await v.en(xp, ym, v.clic, "left", 2)
    # I-06 y I-05: el teclado con el foco en el mapa; Fin y PRESENTE siguen el presente; sin seguir, la linea H-10
    await v.en(xm, ym, v.clic)
    pasos = [("End", "fin", lambda a0, a1: a1["st"]["sigue"] and a1["e"]["fin"] == a1["e"]["n"] - 1),
             ("ArrowLeft", "flechas", lambda a0, a1: a1["e"]["fin"] == a0["e"]["fin"] - 1 and not a1["st"]["sigue"]),
             ("ArrowRight", "flechas", lambda a0, a1: a1["e"]["fin"] == a0["e"]["fin"] + 1),
             ("PageUp", "paginas", lambda a0, a1: a1["e"]["fin"] == max(a0["e"]["ver"] - 1, a0["e"]["fin"] - a0["e"]["ver"])),
             ("PageDown", "paginas", lambda a0, a1: a1["e"]["fin"] == min(a0["e"]["n"] - 1, a0["e"]["fin"] + a0["e"]["ver"])),
             ("Home", "inicio", lambda a0, a1: a1["e"]["fin"] == a1["e"]["ver"] - 1 and not a1["st"]["sigue"]),
             ("End", "fin", lambda a0, a1: a1["st"]["sigue"] and a1["e"]["fin"] == a1["e"]["n"] - 1)]
    for tecla, g, bien in pasos:
        a0 = await v.lee()
        await v.tecla(tecla)
        a1 = await v.lee()
        hechos.add(g)
        if not bien(a0, a1):
            mal(f"I-06 {tecla}", f"fin {a0['e']['fin']} -> {a1['e']['fin']} (ver {a0['e']['ver']}, n {a1['e']['n']}), "
                                 f"sigue {a1['st']['sigue']}")
        await presente_ok(J, pref, a1, f"tras {tecla}")
    for _ in range(3):
        await v.tecla("ArrowLeft")
    a0 = await v.lee()
    await presente_ok(J, pref, a0, "parado tres columnas atras")
    if vivo:  # lo vivo que llega no mueve la vista parada, y la linea del presente se corre con ello
        a1 = await espera_columna(v, a0["e"]["n"])
        if a1 is None:
            J.info.append(f"{pref} no llego ninguna columna viva en {ESPERA_VIVA_S:.0f} s: I-05/H-10 en vivo sin medir")
        else:
            dn = a1["e"]["n"] - a0["e"]["n"]
            if a1["e"]["fin"] != a0["e"]["fin"] or a1["st"]["sigue"] or a1["pres"] is None \
                    or abs(a1["pres"]["x"] - a0["pres"]["x"] - dn * a0["e"]["columna"]) > 1.5:
                mal("I-05/H-10 parado", f"llegaron {dn} columnas: fin {a0['e']['fin']} -> {a1['e']['fin']}, sigue "
                                        f"{a1['st']['sigue']}, la linea del presente {a0['pres']} -> {a1['pres']}")
            await presente_ok(J, pref, a1, "parado con columnas llegando")
    await v.clic_en("#b-presente")
    a1 = await v.lee()
    hechos.add("presente")
    if not a1["st"]["sigue"] or a1["e"]["fin"] != a1["e"]["n"] - 1:
        mal("I-05 PRESENTE", f"fin {a1['e']['fin']} de n {a1['e']['n']}, sigue {a1['st']['sigue']}")
    await presente_ok(J, pref, a1, "tras PRESENTE")
    if vivo:
        a2 = await espera_columna(v, a1["e"]["n"])
        if a2 is not None and (a2["e"]["fin"] != a2["e"]["n"] - 1 or not a2["st"]["sigue"]):
            mal("I-05 siguiendo", f"llego una columna y fin {a2['e']['fin']} de n {a2['e']['n']}, sigue {a2['st']['sigue']}")
    await menu(v, J, pref, hechos, xp, ym)


async def presente_ok(J, pref: str, a: dict, cuando: str) -> None:
    e, p = a["e"], a["pres"]
    if a["st"]["sigue"]:
        if p is not None:
            J.mal("R", pref, f"H-10 {cuando}: siguiendo el presente se pinta su linea {p}")
        return
    x = e["ancho"] - (e["fin"] - e["n"] + 1) * e["columna"]
    if p is None or abs(p["x"] - x) > 1.5:
        J.mal("R", pref, f"H-10 {cuando}: sin seguir, la linea del presente {p} y el borde de la columna mas nueva esta en "
                         f"x={x:.1f}")


async def espera_columna(v: Vista, n0: int) -> dict | None:
    fin = time.monotonic() + ESPERA_VIVA_S
    while time.monotonic() < fin:
        await v.s.drena(1.0)
        a = await v.lee()
        if a["e"]["n"] > n0:
            await v.s.drena(0.5)
            return await v.lee()
    return None


async def menu(v: Vista, J, pref: str, hechos: set, xp: float, ym: float) -> None:
    async def elige(valor: str) -> dict:
        await v.en(xp, ym, v.clic, "right")
        abierto = (await v.lee())["menu"]
        await v.clic_en(f"#menu-eje input[value={valor}]")
        a = await v.lee()
        if not abierto or a["menu"] or a["guardado"] != valor or a["st"]["vertical"]["recentra"] != valor:
            J.mal("R", pref, f"menu del eje, «{valor}»: se abrio {abierto}, queda abierto {a['menu']}, guardado "
                             f"{a['guardado']}, el mapa recentra con «{a['st']['vertical']['recentra']}»")
        return a
    hechos.add("menu")
    await v.en(xp, ym, v.clic, "right")
    await v.tecla("Escape")
    if (await v.lee())["menu"]:
        J.mal("R", pref, "Esc no cierra el menu del eje")
    hechos.add("esc")
    await elige("bbo")
    await elige("ninguno")
    for _ in range(25):  # la banda estrecha: la referencia sale de su 20 % en cuanto se mueve
        await v.en(xp, ym, v.rueda, -120)
    resultado = {}
    for modo in ("ninguno", "ultimo"):
        if modo == "ultimo":
            await elige("ultimo")
        await v.en(10, ym, v.clic)
        a0 = await v.lee()
        bandas = {(a0["e"]["lo"], a0["e"]["hi"], fil(a0["e"]))}
        for t in ("Home", "PageDown", "PageDown", "End"):
            await v.tecla(t)
            a = await v.lee()
            bandas.add((a["e"]["lo"], a["e"]["hi"], fil(a["e"])))
        resultado[modo] = sorted(bandas)
    if len(resultado["ninguno"]) > 1:
        J.mal("R", pref, f"con «Ninguno» el precio se movio al recorrer el tiempo: bandas {resultado['ninguno'][:4]}")
    if len(resultado["ultimo"]) == 1:
        J.info.append(f"{pref} con «Último» la banda tampoco se movio: la prueba de «Ninguno» no discrimina aqui")


# --------------------------------------------------------------------------------------------- (E) y (A)
async def aspecto(v: Vista, J, pref: str) -> dict:
    t = await v.evalua(COLOR)
    bg, tx, co, ve = (K113.hex_rgb(t[k]) for k in ("bg", "tx", "compra", "venta"))
    if K113.luminancia(bg) > 0.02 or K113.contraste(tx, bg) < 7:
        J.mal("E", pref, f"E-01: el fondo {t['bg']} y el texto {t['tx']}: luminancia {K113.luminancia(bg):.4f}, contraste "
                         f"{K113.contraste(tx, bg):.2f}:1 (<= 0.02 y >= 7:1)")
    des = {"normal": K113.de2000(K113._lab(co), K113._lab(ve))}
    des.update({k: K113.de2000(K113._lab(K113.simula(co, m)), K113._lab(K113.simula(ve, m))) for k, m in K113.MACHADO.items()})
    if min(des.values()) < 20:
        J.mal("E", pref, "E-02: compra y venta del mapa se separan dE2000 " + ", ".join(f"{k} {x:.1f}" for k, x in des.items()))
    for ruta in ("/static/flujo/flujo.css", "/static/mesa/mesa.css"):
        try:
            with urllib.request.urlopen(urllib.request.Request(K111.raiz() + ruta, headers=K111.cabecera()), timeout=20) as r:
                m = re.search(r"--comprador:\s*(#[0-9a-fA-F]{6})", r.read().decode("utf-8", "replace"))
        except OSError as exc:
            raise K113.Canal(f"no se pudo leer {ruta}: {exc}") from exc
        if not m or m.group(1).lower() != t["compra"].lower() or t["comprador"].lower() != t["compra"].lower():
            J.mal("E", pref, f"E-02: el mapa pinta el comprador {t['compra']}, la pagina lo llama {t['comprador']} y {ruta} "
                             f"{m.group(1) if m else 'no lo dice'}")
    if len({round(x, 4) for x in t["digitos"]}) != 1 or not ("tabular-nums" in t["ficha"][0] or "mono" in t["ficha"][1]):
        J.mal("E", pref, f"E-03: las cifras no van alineadas: anchos {sorted(set(t['digitos']))}, la ficha «{t['ficha']}»")
    if t["e04"] != ["999", "10.0K", "1.2M"] or [K113.cifra_e04(x, 0) for x in (999, 10000, 1234567)] != t["e04"]:
        J.mal("E", pref, f"E-04: la pagina escribe {t['e04']} para 999, 10000 y 1234567")
    return {k: round(x, 1) for k, x in des.items()}


async def ayuda(v: Vista, J, pref: str, hechos: set) -> None:
    estados = []
    for g in ("?", "Escape", "#b-ayuda", "?"):
        await (v.clic_en(g) if g.startswith("#") else v.tecla(g))
        estados.append((await v.lee())["ayuda"])
    hechos.add("ayuda")
    if estados != [True, False, True, False]:
        J.mal("A", pref, f"la ayuda abierta tras ?, Esc, el boton y ?: {estados} (tiene que ser abierta, cerrada, abierta, "
                         "cerrada)")
    t = await v.evalua(AYUDA)
    if t["b"] is None:
        J.mal("A", pref, "la ayuda no tiene «El raton y el teclado»")
        return
    nombra = {VOCABULARIO.get(b.lower(), "?" + b) for b in t["b"]} - {None}
    for g in sorted(nombra):
        if g.startswith("?") and g != "?" or g not in hechos:
            J.mal("A", pref, f"la ayuda nombra «{g.lstrip('?') if g != '?' else g}» y (R) no lo ejerce")
    for g in sorted(hechos - nombra):
        J.mal("A", pref, f"(R) ejerce «{g}» y la ayuda no lo nombra")
    vistos = [p for p in ("Las familias no se suman", "La escalera:", "El vivo") if p in t["cuerpo"]]
    if t["pie"] or vistos:
        J.mal("A", pref, f"los parrafos del pie siguen en la vista: footer {t['pie']}, a la vista {vistos}")


async def tecla_c(v: Vista, J, pref: str, hechos: set) -> None:
    lee = "(() => document.querySelector('#escalera .esc-tabla').scrollTop)()"
    s0 = await v.evalua(lee)
    r = await v.evalua("(() => { const r = document.querySelector('#escalera .esc-tabla').getBoundingClientRect(); "
                       "return [r.left + r.width / 2, r.top + r.height / 2]; })()")
    for _ in range(4):
        await v.rueda(r[0], r[1], 120)
    s1 = await v.evalua(lee)
    await v.tecla("c")
    await v.s.drena(0.5)
    s2 = await v.evalua(lee)
    hechos.add("c")
    if s1 != s0 and abs(s2 - s0) > abs(s1 - s0) / 2:
        J.mal("R", pref, f"C no centra la escalera: scrollTop {s0} -> {s1} (rueda) -> {s2} (C)")


# --------------------------------------------------------------------------------------------- juzga
def red_tras(v: Vista, antes: set) -> list[str]:
    return [x["url"] for rid, x in v.red.items() if rid not in antes and x["tipo"] in ("fotos", "honda")]


async def todo(K, J, vistas: dict) -> dict:
    cab = K111.cabecera()
    hechos: set = set()
    res = {}

    async def viva(v, out):
        pref = "[vivo 1920x1080]"
        await celdas(v, J, pref, vistas["viva"])
        await gestos(v, J, pref, hechos, True)
        await tecla_c(v, J, pref, hechos)
        out["dE"] = await aspecto(v, J, pref)
        await ayuda(v, J, pref, hechos)
        await celdas(v, J, pref + "{tras los gestos}", vistas["viva"])

    async def chica(v, out):
        pref = "[vivo 1366x768]"
        await celdas(v, J, pref, vistas["viva"])
        a = await v.lee()
        e = a["e"]
        x0 = e["ancho"] * 0.3
        await v.en(x0, e["alto"] / 2, v.rueda, -120)
        b = (await v.lee())["e"]
        if abs(ja(b, x0) - ja(e, x0)) > 1:
            J.mal("R", pref, f"I-01 rueda: la columna bajo x={x0:.0f} {ja(e, x0):.2f} -> {ja(b, x0):.2f}")

    async def pasado(v, out):
        pref = "[BTC perp 1 h, pasado]"
        await celdas(v, J, pref, vistas["pasado"])
        await v.recoge_red()
        antes = set(v.red)
        await gestos(v, J, pref, hechos, False)
        await v.s.drena(2.0)
        await v.recoge_red()
        pedidas = red_tras(v, antes)
        out["pedidas"] = len(pedidas)
        if pedidas:
            J.mal("P", pref, f"los gestos dentro de lo cargado pidieron {len(pedidas)} veces: {pedidas[0][:160]}")

    async def eth(v, out):
        await celdas(v, J, "[ETH en USD, pasado]", vistas["eth"])

    for nombre, (vista, w, h, vivo, rec) in {"viva": (vistas["viva"], 1920, 1080, True, viva),
                                              "chica": (vistas["viva"], 1366, 768, True, chica),
                                              "pasado": (vistas["pasado"], 1920, 1080, False, pasado),
                                              "eth": (vistas["eth"], 1920, 1080, False, eth)}.items():
        out = await abre(K, vista, w, h, cab, vivo, rec)
        res[nombre] = out
        if not out["listo"]:
            J.mal("P", f"[{nombre}]", f"la pagina {vista} no llego a listo")
        for x in out["excepciones"][:2]:
            J.mal("P", f"[{nombre}]", f"excepcion: {x[:200]}")
    res["hechos"] = sorted(hechos)
    return res


def juzga() -> int:
    K = K111._modulo("k102_mesa", "K102-mesa.py")
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            K.binario_chromium()
    except SystemExit:
        print("NO MEDIDO: sin Chromium (o sin websockets) en 143 no se puede mirar la pagina")
        return 2
    ahora = datetime.now(UTC)
    hasta = datetime.fromisoformat(HASTA.replace("Z", "+00:00")) if HASTA else \
        ahora.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    h = hasta.strftime("%Y-%m-%dT%H:%M:%SZ")
    vistas = {"viva": "#BTC/perp", "pasado": f"#BTC/perp/hasta={h}", "eth": f"#ETH/{ETH}/unidad=usd/hasta={h}"}
    sujeto = f"el ARBOL servido en {K111.BASE}" if K111.BASE else "PRODUCCION"
    try:
        st = K111.estado_http(K111.raiz() + "/libro", K111.cabecera())
    except (K111.Canal, OSError) as exc:
        print(f"NO MEDIDO (CANAL): {str(exc)[:160]} · sujeto: {sujeto}")
        return 2
    if st != 200:
        print(f"NO MEDIDO: FALTA DESPLEGAR /libro (HTTP {st}) · sujeto: {sujeto}")
        return 2
    J = K113.Juez()
    J.malos["A"] = []
    try:
        res = asyncio.run(todo(K, J, vistas))
    except (K113.Canal, K111.Canal, K.SystemExit2, OSError) as exc:
        print(f"NO MEDIDO (CANAL): {str(exc)[:200]} · sujeto: {sujeto}")
        return 2
    malos = [(b, m) for b in "PCREA" for m in J.malos.get(b, [])]
    cab = (f"K114 el raton del libro · sujeto: {sujeto} · vistas {vistas['viva']}, {vistas['pasado']}, {vistas['eth']} · "
           f"gestos {len(res.get('hechos', []))} · peticiones por gestos {res.get('pasado', {}).get('pedidas')} · "
           f"dE {res.get('viva', {}).get('dE')}")
    print(("ROJO  " if malos else "VERDE  ") + cab)
    for b, m in malos[:40]:
        print(f"  ROJO ({b}) {m[:400]}")
    for i in J.info:
        print(f"  {i[:300]}")
    return 1 if malos else 0


if __name__ == "__main__":
    sys.exit(juzga() if sys.argv[1:] == ["juzga"] else 2)
