#!/usr/bin/env python3
"""K120-liq · el juez de K120 (las liquidaciones sobre el precio, campana 150). Lo llama K120-las-liquidaciones-en-el-precio.sh.

Por pagina (/flujo 1m y /libro, del pasado, con las liquidaciones encendidas), contra la ruta /api/orderflow/indicadores
que la pagina pidio (se vuelve a pedir, igual) y la regla escrita AQUI, no la de la pagina:
  (P) LIQ_PINTADAS = las sueltas de la ruta con usd >= 10 000: mismo ts, exchange, lado, precio y USD, y LIQ_REGLA dice 10 000
  (X) cada pintada en su x/y del eje vigente (FLUJO_PINTADO / LIBRO_PINTADO, +-1.5 px), su radio min(18, max(3, 3 sqrt(usd/1e4)))
      y el color de su lado (largo liquidado = venta forzada, corto = compra forzada)
  (F) la ficha de hasta 4 celdas (la del racimo, una en un hueco irrecuperable, una con una, una vacia con dato): sus
      lineas `liq` son las de la regla (y N mas, SIN DATO, ninguna, cascada)
  (C) LIQ_CASCADAS = la cascada M8 recalculada aqui con n y s de la ruta, y n, s = CASCADA_N, CASCADA_S de app/anatomia.py
  (R) el raton (12 movimientos) no cambia LIQ_PINTADAS ni LIQ_CASCADAS ni pide nada a /api
  (T) la ruta retiene >= 720 h y, con base (K120_*_DB), sirve todas las filas de la tabla en su ventana
  (D) 140, solo lectura: con la retencion desplegada hace >= 13 h, hay liquidaciones de mas de 12 h. Sin desplegar: lo dice.
"""

import asyncio
import contextlib
import importlib.util
import io
import json
import math
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

AQUI = pathlib.Path(__file__).resolve().parent
REPO = AQUI.parent.parent
FLUJO = os.environ.get("K120_FLUJO", "")  # banco de /flujo; sin el, PRODUCCION
LIBRO = os.environ.get("K120_LIBRO", "")
os.environ["K114_BASE"] = ""
os.environ["K111_BASE"], os.environ["K113_BASE"] = LIBRO, FLUJO
UMBRAL = 10000.0
PROD = REPO.parent / "harness" / "bin"


def _modulo(nombre: str, fichero: str):
    spec = importlib.util.spec_from_file_location(nombre, AQUI / fichero)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


K114 = _modulo("k114", "K114-raton-libro.py")
K113, K111 = K114.K113, K114.K111


def ms(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)


def hhmmss(t: int) -> str:
    return datetime.fromtimestamp(t / 1000, UTC).strftime("%H:%M:%S")


def jsnum(x: float) -> str:
    return str(int(x)) if x == int(x) and abs(x) < 1e21 else repr(x)


def usd_txt(v: float) -> str:
    return f"{v / 1e6:.2f} M" if v >= 1e6 else f"{v / 1e3:.1f} k" if v >= 1e3 else f"{v:.0f}"


def radio(usd: float) -> float:
    return min(18.0, max(3.0, 3 * math.sqrt(max(0.0, usd) / 1e4)))


def eventos(s: dict) -> list[dict]:
    return [{"ts": e["ts"], "t": ms(e["ts"]), "exchange": e["exchange"], "lado": e["lado"], "precio": float(e["precio"]),
             "usd": float(e["usd"])} for e in (s or {}).get("eventos", [])]


def sin_dato(s: dict, a: int, b: int) -> list[dict]:
    out = []
    dd = ms(s["desde_dato"]) if s.get("desde_dato") else None
    if dd is not None and dd > a:
        out.append({"desde": a, "hasta": min(dd, b), "motivo": f"antes de la retención ({s['retencion_h']} h): sin dato"})
    if s.get("truncada"):
        ev = s.get("eventos") or []
        out.append({"desde": ms(ev[-1]["ts"]) if ev else a, "hasta": b,
                    "motivo": f"la ruta cortó en {len(ev)} eventos: lo de después no está"})
    for h in s.get("huecos") or []:
        if h["estado"] != "recovered":
            out.append({"desde": max(ms(h["desde"]), a), "hasta": min(ms(h["hasta"]), b),
                        "motivo": f"hueco de {h['exchange']} ({h['estado']}): sin dato"})
    return [x for x in out if x["hasta"] > x["desde"]]


def cascadas(ev: list[dict], n: int, s: float) -> list[dict]:
    """M8: una liquidacion cierra cascada si hay >= n del mismo lado en [t - s, t] (las de su mismo t cuentan);
    el episodio va de la primera a la ultima de esas ventanas, y dos ventanas que comparten una liquidacion son uno."""
    out = []
    for lado in ("long", "short"):
        a = sorted((e for e in ev if e["lado"] == lado), key=lambda e: (e["t"], e["usd"]))
        ventanas = []
        for i, e in enumerate(a):
            hi = max(j for j in range(i, len(a)) if a[j]["t"] == e["t"])
            lo = min(j for j in range(hi + 1) if a[j]["t"] >= e["t"] - s * 1000)
            if hi - lo + 1 >= n:
                ventanas.append((lo, hi))
        cur = None
        for lo, hi in ventanas:
            if cur and lo <= cur[1]:
                cur[1] = max(cur[1], hi)
            else:
                cur and out.append(cur)
                cur = [lo, hi]
        cur and out.append(cur)
        out[:] = [x if isinstance(x, dict) else {"lado": lado, "desde": a[x[0]]["t"], "hasta": a[x[1]]["t"],
                                                  "n": x[1] - x[0] + 1, "usd": sum(e["usd"] for e in a[x[0]:x[1] + 1])}
                  for x in out]
    return sorted(out, key=lambda c: (c["desde"], c["lado"]))


def texto_cascada(c: dict) -> str:
    q = "de largos (venta forzada)" if c["lado"] == "long" else "de cortos (compra forzada)"
    return f"cascada {q} · {hhmmss(c['desde'])}–{hhmmss(c['hasta'])}Z · {c['n']} liq · {usd_txt(c['usd'])} USD"


def ficha(pint: list[dict], sin: list[dict], cas: list[dict], t0: int, t1: int) -> list[str]:
    en = [e for e in pint if t0 <= e["t"] < t1]
    s = [x for x in sin if x["desde"] < t1 and x["hasta"] > t0]
    lado = {"long": "largo liquidado (venta forzada)", "short": "corto liquidado (compra forzada)"}
    out = [f"liq {e['ts'][11:19]}Z · {e['exchange']} · {lado.get(e['lado'], lado['short'])} · {jsnum(e['precio'])} · "
           f"{usd_txt(e['usd'])} USD" for e in en[:4]]
    if len(en) > 4:
        out.append(f"liq: y {len(en) - 4} más")
    if not en and not s:
        out.append(f"liq ≥ {usd_txt(UMBRAL)} USD: ninguna")
    out += [f"liq SIN DATO: {x['motivo']}" for x in s]
    return out + [texto_cascada(c) for c in cas if c["desde"] < t1 and c["hasta"] >= t0]


LEE = r"""(() => { const flujo = !!window.FLUJO_PINTADO; const cv = document.getElementById(flujo ? 'lienzo' : 'mapa');
  const r = cv.getBoundingClientRect(); const g = flujo ? FLUJO_PINTADO : (window.LIBRO_PINTADO || {}).mapa || {};
  const pal = flujo ? {long: JSON.stringify(COLOR.venta), short: JSON.stringify(COLOR.compra)}
                    : {long: JSON.stringify(MAPA_COLOR.venta), short: JSON.stringify(MAPA_COLOR.compra)};
  const col = (x) => JSON.stringify(x);
  return {flujo, r: [r.left, r.top], pal, regla: window.LIQ_REGLA || null,
          pint: (window.LIQ_PINTADAS || null) && LIQ_PINTADAS.map((e) => Object.assign({}, e, {color: col(e.color)})),
          cas: window.LIQ_CASCADAS === undefined ? 'indefinido' : window.LIQ_CASCADAS,
          escala: flujo ? g.escala : null, W: g.ancho, fin: g.fin, ver: g.ver, ejep: flujo ? LZ.EJE_P : null, velas: flujo ? (g.velas || []).map((v) => [v.ts, v.x0, v.ancho]) : null,
          eje: flujo ? null : g.eje, paso: flujo ? null : g.paso, cada: flujo ? null : g.cada,
          columnas: flujo ? null : (g.columnas || []).map((c) => [c.ts, c.x0, c.x1])}; })()"""
FICHA_F = "(() => { const f = window.FLUJO_FICHA || {}; return {vela: f.vela || null, lineas: f.lineas || []}; })()"
FICHA_L = ("(() => { const c = window.LIBRO_CRUZ; return c ? {ts: c.ficha.ts, lineas: c.ficha.lineas.filter((x) => x[0] "
           "=== 'liq').map((x) => x[1])} : null; })()")


def trae_url(url: str, cab: dict) -> tuple[int, bytes]:
    ctx = ssl.create_default_context()
    ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE  # el certificado de 140 es propio
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=cab), timeout=60, context=ctx) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""


def pedidas_api(v) -> list[str]:
    return [e["params"]["request"]["url"] for e in v.s.eventos if e.get("method") == "Network.requestWillBeSent"
            and "/api/" in e["params"]["request"]["url"]]


def a_px(J, b: str, pref: str, g: dict) -> tuple:
    """-> (x(t), y(p), [(t0, t1, x, y) celdas candidatas]) en coordenadas del lienzo."""
    if g["flujo"]:
        e, vs = g["escala"], g["velas"]
        if not e or len(vs) < 3:
            J.mal(b, pref, f"sin eje de /flujo (escala {bool(e)}, {len(vs)} velas)")
            return None
        # la geometria de flujo-dibujo.js geo(): bs = (W - EJE_P) / ver y x(i) = ancho - (fin - i + 0.5) bs, con la
        # primera vela pintada en i0 = max(0, ceil(fin - ver + 0.5)); la liquidacion va a x(i) - bs/2 + fraccion bs
        ancho = g["W"] - g["ejep"]
        bs = ancho / g["ver"]
        i0 = max(0, math.ceil(g["fin"] - g["ver"] + 0.5))
        m0 = ms(vs[0][0])
        mm = ms(vs[1][0]) - m0

        def x(t):
            return ancho - (g["fin"] + 1 - i0) * bs + (t - m0) / mm * bs

        def y(p):
            return e["arriba"] + (e["hi"] - p) / (e["hi"] - e["lo"]) * (e["abajo"] - e["arriba"])
        celdas = [(ms(v[0]), ms(v[0]) + mm, v[1] + v[2] / 2, (e["arriba"] + e["abajo"]) / 2) for v in vs]
        return x, y, celdas, 1.5
    eje, cs = g["eje"], g["columnas"]
    if not eje or len(cs) < 2:
        J.mal(b, pref, "sin eje de /libro")
        return None
    bs, fh, paso, cada = eje["columna"], eje["fila"], float(g["paso"]), g["cada"] * 1000

    def x(t):
        return cs[0][1] + (t - ms(cs[0][0])) / cada * bs

    def y(p):
        return (eje["hi"] + 1 - p / paso) * fh
    vistos, celdas = set(), []
    for c in cs:
        t0 = ms(c[0]) // 60000 * 60000
        if t0 not in vistos:
            vistos.add(t0)
            celdas.append((t0, t0 + 60000, (c[1] + c[2]) / 2, eje["alto"] / 2))
    return x, y, celdas, 1.5


async def mira(J, pagina: str, vista: str, base_db: str) -> dict:
    pref = pagina
    res: dict = {}
    cab = (K113.cabecera() if not FLUJO else {}) if pagina == "/flujo" else (K111.cabecera() if not LIBRO else {})

    async def recorrido(v, out):
        g = await v.evalua(LEE)
        res["g"] = g
        urls = [u for u in pedidas_api(v) if "/api/orderflow/indicadores" in u]
        if not urls:
            J.mal("P", pref, "la pagina no pidio /api/orderflow/indicadores")
            return
        u = urllib.parse.urlparse(urls[-1])
        st, cuerpo = trae_url(urls[-1], cab)
        if st != 200:
            J.mal("P", pref, f"la ruta contesto HTTP {st}")
            return
        d = json.loads(cuerpo)
        res["d"] = d
        s = d.get("sueltas") or {}
        ev = eventos(s)
        esp = [e for e in ev if e["usd"] >= UMBRAL]
        pint = g["pint"] or []
        # (T)
        if (s.get("retencion_h") or 0) < 720:
            J.mal("T", pref, f"la ruta retiene {s.get('retencion_h')} h (< 720): las liquidaciones viejas no llegan")
        if base_db:
            q = urllib.parse.parse_qs(u.query)
            r = subprocess.run(["psql", base_db, "-XAtc", "SELECT count(*) FROM liquidations_realtime WHERE symbol = "
                                f"'{d.get('simbolo_coinalyze')}' AND ts >= '{q['desde'][0]}' AND ts < '{q['hasta'][0]}'"],
                               capture_output=True, text=True, timeout=60)
            n_db = r.stdout.strip()
            if not s.get("truncada") and n_db != str(len(ev)):
                J.mal("T", pref, f"la tabla tiene {n_db} liquidaciones en la ventana y la ruta sirve {len(ev)}")
        # (P)
        if (g["regla"] or {}).get("umbral_usd") != UMBRAL:
            J.mal("P", pref, f"LIQ_REGLA.umbral_usd = {(g['regla'] or {}).get('umbral_usd')}, no {UMBRAL:g}")
        clave = lambda e: (e["ts"], e["exchange"], e["lado"], round(float(e["precio"]), 8), round(float(e["usd"]), 6))  # noqa: E731
        a, b = [clave(e) for e in pint], [clave(e) for e in esp]
        if a != b:
            sa, sb = set(a), set(b)
            J.mal("P", pref, f"pintadas {len(a)} contra {len(b)} de la ruta >= {UMBRAL:g}: de mas {sorted(sa - sb)[:2]} · "
                             f"faltan {sorted(sb - sa)[:2]}")
        # (X)
        px = a_px(J, "X", pref, g)
        if px:
            fx, fy, celdas, tol = px
            malas = []
            for e in pint:
                t, p, u_ = ms(e["ts"]), float(e["precio"]), float(e["usd"])
                dx, dy = abs(e["x"] - fx(t)), abs(e["y"] - fy(p))
                if dx > tol or dy > tol:
                    malas.append(f"{e['ts']} {e['lado']} {p:g}: x {e['x']} (regla {fx(t):.1f}) y {e['y']} (regla {fy(p):.1f})")
                if abs(e["r"] - radio(u_)) > 0.011:
                    malas.append(f"{e['ts']} {u_:g} USD: radio {e['r']}, la regla da {radio(u_):.2f}")
                if e.get("color") != g["pal"].get(e["lado"]):
                    malas.append(f"{e['ts']} {e['lado']}: color {e.get('color')}, el de su lado es {g['pal'].get(e['lado'])}")
            if malas:
                J.mal("X", pref, f"{len(malas)} de {len(pint)} pintadas fuera de la regla · {malas[0]}")
            res["dibujadas"] = sum(1 for e in pint if e.get("dibujada"))
        # (C)
        c = s.get("cascada") or {}
        txt = (REPO / "app" / "anatomia.py").read_text()
        mm = re.search(r"^CASCADA_N, CASCADA_S = (\d+), ([\d.]+)", txt, re.M)
        if not mm or (c.get("n"), c.get("s")) != (int(mm.group(1)), float(mm.group(2))):
            J.mal("C", pref, f"la ruta dice n={c.get('n')} s={c.get('s')} y app/anatomia.py {mm.groups() if mm else None}")
        cas = cascadas(ev, int(c.get("n") or 5), float(c.get("s") or 60))
        res["cascadas"] = len(cas)
        got = g["cas"]
        if not isinstance(got, list):
            J.mal("C", pref, f"LIQ_CASCADAS = {str(got)[:60]}")
        else:
            ka = [(x["lado"], ms(x["desde"]), ms(x["hasta"]), x["n"], round(x["usd"], 2)) for x in got]
            kb = [(x["lado"], x["desde"], x["hasta"], x["n"], round(x["usd"], 2)) for x in cas]
            if ka != kb:
                J.mal("C", pref, f"cascadas pintadas {len(ka)} contra {len(kb)} de la regla: de mas "
                                 f"{[texto_cascada(dict(zip(('lado', 'desde', 'hasta', 'n', 'usd'), k, strict=True))) for k in ka if k not in kb][:1]} · "
                                 f"faltan {[texto_cascada(x) for x in cas if (x['lado'], x['desde'], x['hasta'], x['n'], round(x['usd'], 2)) not in ka][:1]}")
        # (F)
        if px:
            sin = sin_dato(s, ms(d["desde"]), ms(d["hasta"]))
            cuenta = lambda c_: sum(1 for e in esp if c_[0] <= e["t"] < c_[1])  # noqa: E731
            vis = [c_ for c_ in celdas if 4 < c_[2] < (g["eje"] or {}).get("ancho", 1e9) - 4]
            elegir = [max(vis, key=cuenta, default=None),
                      next((c_ for c_ in vis if any(x["desde"] < c_[1] and x["hasta"] > c_[0] and "hueco" in x["motivo"]
                                                    for x in sin)), None),
                      next((c_ for c_ in vis if cuenta(c_) == 1), None),
                      next((c_ for c_ in vis if cuenta(c_) == 0 and not any(x["desde"] < c_[1] and x["hasta"] > c_[0]
                                                                             for x in sin)), None)]
            vistas_f = []
            for c_ in dict.fromkeys(x for x in elegir if x):
                await v.mueve(g["r"][0] + c_[2], g["r"][1] + c_[3])
                await v.s.drena(0.3)
                f = await v.evalua(FICHA_F if g["flujo"] else FICHA_L)
                if not f:
                    J.mal("F", pref, f"la ficha no se abrio en {hhmmss(c_[0])}Z")
                    continue
                if g["flujo"]:
                    t0 = ms(f["vela"]) if f["vela"] else None
                    lin = [x for x in f["lineas"] if x.startswith("liq") or x.startswith("cascada")]
                    t1 = t0 + (c_[1] - c_[0]) if t0 is not None else None
                else:
                    t0 = ms(f["ts"]) // 60000 * 60000
                    lin, t1 = f["lineas"], t0 + 60000
                if t0 != c_[0]:
                    J.mal("F", pref, f"apunte a la celda de {hhmmss(c_[0])}Z y la ficha es de {hhmmss(t0) if t0 else None}Z")
                    continue
                e_ = ficha(esp, sin, cas, t0, t1)
                vistas_f.append(f"{hhmmss(t0)}Z:{cuenta(c_)}")
                if lin != e_:
                    J.mal("F", pref, f"la ficha de {hhmmss(t0)}Z dice {lin[:3]} y la regla {e_[:3]}")
            res["fichas"] = vistas_f
        # (R)
        antes = len(pedidas_api(v))
        g0 = await v.evalua(LEE)
        for k in range(12):
            await v.mueve(g["r"][0] + 40 + k * 37, g["r"][1] + 60 + (k % 4) * 45)
        await v.s.drena(0.6)
        g1 = await v.evalua(LEE)
        geo = lambda h: (json.dumps([[e["ts"], e["x"], e["y"], e["r"]] for e in h["pint"] or []]), json.dumps(h["cas"]))  # noqa: E731
        if geo(g0) != geo(g1):
            J.mal("R", pref, "12 movimientos del raton cambiaron LIQ_PINTADAS o LIQ_CASCADAS")
        nuevas = pedidas_api(v)[antes:]
        if nuevas:
            J.mal("R", pref, f"12 movimientos del raton pidieron {len(nuevas)} a /api: {nuevas[0][:120]}")

    if pagina == "/flujo":
        out = await K113.abre(K102, vista, 1920, 1080, cab, recorrido)
    else:
        out = await K114.abre(K102, vista, 1920, 1080, cab, False, recorrido)
    if not out.get("listo"):
        J.mal("P", pref, f"la pagina {pagina}{vista} no llego a pintarse")
    for x in out.get("excepciones", [])[:1]:
        J.mal("P", pref, f"excepcion en la pagina: {x[:200]}")
    return res


def produccion(J) -> str:
    def prod(cmd: str) -> str:
        r = subprocess.run([str(PROD / "prod"), cmd], capture_output=True, text=True, timeout=60)
        return r.stdout

    cur = prod("readlink -f /opt/coinalyze/current").strip().splitlines()
    cur = cur[0] if cur else ""
    if not cur.startswith("/opt/coinalyze/releases/"):
        return f"140 NO MEDIDO (canal: {cur[:80]!r})"
    tiene = prod(f"grep -c LIQ_REALTIME_RETENTION_DAYS {cur}/app/config.py").strip().splitlines()
    if not tiene or tiene[0].strip() in ("", "0") or not tiene[0].strip().isdigit():
        return f"140 SIN DESPLEGAR (el release {cur.rsplit('/', 1)[-1][:12]} no trae LIQ_REALTIME_RETENTION_DAYS): no se juzga"
    st = prod(f"stat -c %Y {cur}").strip().splitlines()
    edad_h = (datetime.now(UTC).timestamp() - int(st[0])) / 3600 if st and st[0].isdigit() else None
    if edad_h is None or edad_h < 13:
        return f"140 desplegado hace {edad_h if edad_h is None else round(edad_h, 1)} h: aun no se juzga la retencion (>= 13 h)"
    r = subprocess.run([str(PROD / "prodsql"), "SELECT count(*), min(ts) FROM liquidations_realtime WHERE ts < now() - "
                        "interval '12 hours'"], capture_output=True, text=True, timeout=120)
    m = re.search(r"(\d+)\s*\|", r.stdout)
    if not m:
        return f"140 NO MEDIDO (prodsql: {r.stdout.strip()[:80]!r})"
    if m.group(1) == "0":
        J.mal("D", "140", f"desplegada la retencion hace {edad_h:.0f} h y no hay ninguna liquidacion de mas de 12 h")
    return f"140: {m.group(1)} liquidaciones de mas de 12 h (desplegado hace {edad_h:.0f} h)"


K102 = None


def juzga() -> int:
    global K102
    K102 = K111._modulo("k102_mesa", "K102-mesa.py")
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            K102.binario_chromium()
    except SystemExit:
        print("NO MEDIDO: sin Chromium (o sin websockets) en 143 no se puede mirar la pagina")
        return 2
    ahora = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    hf = os.environ.get("K120_FLUJO_HASTA") or ahora.strftime("%Y-%m-%dT%H:%M:%SZ")
    hl = os.environ.get("K120_LIBRO_HASTA") or ahora.strftime("%Y-%m-%dT%H:%M:%SZ")
    vistas = [("/flujo", f"#BTC/1m/perp/hasta={hf}/ind=delta,cvd,grandes,liqp,cinta", os.environ.get("K120_FLUJO_DB", "")),
              ("/libro", f"#BTC/perp/hasta={hl}/liq=1", os.environ.get("K120_LIBRO_DB", ""))]
    sujeto = f"el ARBOL en {FLUJO} y {LIBRO}" if FLUJO and LIBRO else "PRODUCCION"
    J = K113.Juez()
    J.malos.update({"X": [], "D": []})
    notas = []
    try:
        if not (FLUJO and LIBRO):
            st, _ = K113.trae("/static/flujo/flujo-liq.js", K113.cabecera())
            if st != 200:
                notas.append(f"paginas SIN DESPLEGAR (/static/flujo/flujo-liq.js HTTP {st}): no se juzgan")
                vistas = []
        for pagina, vista, db in vistas:
            r = asyncio.run(mira(J, pagina, vista, db))
            notas.append(f"{pagina}: {len((r.get('g') or {}).get('pint') or [])} pintadas ({r.get('dibujadas')} a la vista), "
                         f"{r.get('cascadas')} cascadas, fichas {r.get('fichas')}")
        if os.environ.get("K120_SIN_PROD") != "1":
            notas.append(produccion(J))
    except (K113.Canal, K111.Canal, K102.SystemExit2, OSError, subprocess.TimeoutExpired) as exc:
        print(f"NO MEDIDO (CANAL): {str(exc)[:200]} · sujeto: {sujeto}")
        return 2
    malos = [(b, m) for b in "PXFCRTD" for m in J.malos.get(b, [])]
    cab = f"K120 las liquidaciones en el precio · sujeto: {sujeto} · " + " · ".join(notas)
    # no condenar no es dar VERDE: sin ninguna pagina mirada ni la retencion de 140 contada, no se midio nada
    if not malos and not vistas and not any(n.startswith("140: ") for n in notas):
        print("NO MEDIDO  " + cab)
        return 2
    print(("ROJO  " if malos else "VERDE  ") + cab)
    for b, m in malos[:40]:
        print(f"  ROJO ({b}) {m[:400]}")
    return 1 if malos else 0


if __name__ == "__main__":
    sys.exit(juzga() if sys.argv[1:] == ["juzga"] else 2)
