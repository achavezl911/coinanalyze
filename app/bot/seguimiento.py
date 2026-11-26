"""SEGUIMIENTO R1: con una posicion abierta en Bybit, el bot sigue SU activo minuto a minuto y avisa solo cuando cambia algo.

Pedido del dueno (11-26): liquidaciones, absorciones, un participante grande que entra, rupturas de soporte/resistencia y
niveles cercanos mientras tiene una operacion abierta. Lo que el bot ya hace NO se repite aqui: las rafagas CASCADA/BARRIDO
y los avisos de sin stop / stop cerca / liquidacion cerca son del centinela (centinela.py), y los giros de estructura de
estructura.py. Este modulo es por POSICION y por el ACTIVO de la posicion.

Lee la base de 140 que el bot ya lee (ohlcv 1min, liquidations_realtime, open_interest 5min, orderflow_grande), SOLO
lectura. Los textos describen y no predicen; cada uno dice si va A FAVOR o EN CONTRA de la posicion. Antiruido: un aviso
solo al cambiar de estado, enfriamiento por senal, activo y subclave, tope por hora (lo que pasa del tope se cuenta en el
resumen) y un resumen cada 30 min si hubo avisos. BOT_SEGUIMIENTO=apagado|sombra|enviar, por defecto sombra.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

MODOS = ("apagado", "sombra", "enviar")

# ---------- UMBRALES PROVISIONALES (R1, sin calibrar: la pasada de medicion I18 dira que senales y con que cifra) ----------
ATR_VELAS = 60  # el ATR de 1 min de la ultima hora: la vara de «cerca», del margen de ruptura y del «precio quieto»
VELAS_LEIDAS = 1500  # 24 h + la hora del ATR y los 5 min del delta: los niveles del dia y de 24 h salen de aqui
LIQ_VENTANA = 5  # min: la rafaga se mide en la suma de 5 min (liquidations, la vela agregada, tambien es de 5)
LIQ_COLA = 0.99  # percentil de 30 d de las sumas de 5 min CON liquidaciones, por lado (sin los ceros: la cola es mas alta)
LIQ_SUELO = {"BTC": 1_000_000.0, "ETH": 500_000.0, "SOL": 250_000.0}  # USD: una cola de dias tranquilos no avisa de migajas
ABS_VENTANA = 5  # min del delta agresivo
ABS_COLA = 0.99  # percentil de |delta de 5 min| en las ultimas 24 h
ABS_SUELO = {"BTC": 2_000_000.0, "ETH": 800_000.0, "SOL": 200_000.0}  # USD
ABS_QUIETO_ATR = 1.0  # el precio de esos 5 min se movio menos de 1 ATR: el delta no lo arrastro
GRANDE_USD = {"BTC": 5_000_000.0, "ETH": 2_000_000.0, "SOL": 1_000_000.0}  # una operacion o el racimo de 1 min
OI_COLA = 0.98  # percentil de |cambio de OI de 5 min| en 7 d
OI_SUELO_PCT = 0.3  # %: con un OI plano la cola es casi cero
CERCA_ATR = 3.0  # un nivel a menos de 3 ATR del precio esta «cerca»
RUPTURA_ATR = 0.5  # ruptura: un CIERRE de 1 min mas alla del nivel y de medio ATR (una mecha no rompe)
MISMO_NIVEL_ATR = 0.25  # dos niveles a menos de esto son el mismo (se nombra el mas ancho: 7 d, 24 h, dia)
R_HITOS = (-0.5, 0.5, 1.0, 2.0, 3.0)  # avance en R de la posicion: se avisa al cruzar uno
ENFRIA = {"liquidaciones": 15, "absorcion": 15, "grande": 5, "oi": 15, "cerca": 60, "ruptura": 30, "avance": 10}  # min
TOPE_HORA = 6  # mensajes por hora; los de mas, al resumen
RESUMEN_MIN = 30
CACHE_S = 3600  # las colas de 30 d / 7 d y el rango de 7 d se releen cada hora
DEFECTO = "_"  # la clave de un activo que no esta en las tablas de arriba (usa el umbral de SOL)

SQL_VELAS = """
SELECT (extract(epoch FROM ts)::bigint / 60)::int, high, low, close, buy_volume, volume
  FROM ohlcv
 WHERE interval = '1min' AND symbol = $1 AND ts >= to_timestamp($2::bigint * 60) AND ts < to_timestamp($3::bigint * 60)
 ORDER BY ts
"""
SQL_RANGO = """
SELECT max(high), min(low)
  FROM ohlcv
 WHERE interval = '1min' AND symbol = $1 AND ts >= to_timestamp($2::bigint * 60) AND ts < to_timestamp($3::bigint * 60)
"""
SQL_LIQ = """
SELECT (extract(epoch FROM ts)::bigint / 60)::int, side, sum(notional_usd)
  FROM liquidations_realtime
 WHERE symbol = $1 AND ts >= to_timestamp($2::bigint * 60) AND ts < to_timestamp($3::bigint * 60)
 GROUP BY 1, 2
"""
SQL_LIQ_COLA = """
SELECT side, percentile_cont($4::float8) WITHIN GROUP (ORDER BY s)
  FROM (SELECT side, extract(epoch FROM ts)::bigint / 300 b, sum(notional_usd) s
          FROM liquidations_realtime
         WHERE symbol = $1 AND ts >= to_timestamp($2::bigint * 60) AND ts < to_timestamp($3::bigint * 60)
         GROUP BY 1, 2) x
 GROUP BY side
"""
SQL_OI = """
SELECT (extract(epoch FROM ts)::bigint / 60)::int, oi_close
  FROM open_interest
 WHERE symbol = $1 AND interval = '5min' AND ts >= to_timestamp($2::bigint * 60) AND ts < to_timestamp($3::bigint * 60)
 ORDER BY ts
"""
SQL_GRANDES = """
SELECT (extract(epoch FROM ts)::bigint / 60)::int, venue, compra, usd::float8
  FROM orderflow_grande
 WHERE symbol = $1 AND ts >= to_timestamp($2::bigint * 60) AND ts < to_timestamp($3::bigint * 60)
"""


@dataclass
class Config:
    modo: str = "sombra"

    @classmethod
    def desde(cls, e: dict) -> tuple[Config, list[str]]:
        modo, avisos = (e.get("BOT_SEGUIMIENTO") or "sombra").strip().lower(), []
        if modo not in MODOS:
            avisos.append(f"BOT_SEGUIMIENTO={modo[:20]!r} no es apagado|sombra|enviar: va en sombra")
            modo = "sombra"
        return cls(modo), avisos


def nuevo() -> dict:
    """El estado (va a bot_estado): el ultimo valor de cada senal, el enfriamiento, los emitidos de la ultima hora, lo
    que lleva el periodo del resumen y los avisos de 24 h ([t, enviada, tipo]) para /estado."""
    return {"vivo": {}, "enfria": {}, "emitidos": [], "periodo": [], "resumen_t": None, "avisos": []}


def restaura(g) -> dict | None:
    """Lo guardado, si se entiende; si no, None (se empieza de cero)."""
    if not isinstance(g, dict) or not all(isinstance(g.get(k), d) for k, d in
                                          (("vivo", dict), ("enfria", dict), ("emitidos", list), ("periodo", list), ("avisos", list))):
        return None
    return {"vivo": dict(g["vivo"]), "enfria": {str(k): float(v) for k, v in g["enfria"].items() if isinstance(v, (int, float))},
            "emitidos": [float(t) for t in g["emitidos"] if isinstance(t, (int, float))],
            "periodo": [list(x) for x in g["periodo"] if isinstance(x, list) and len(x) == 3],
            "resumen_t": g["resumen_t"] if isinstance(g.get("resumen_t"), (int, float)) else None,
            "avisos": [list(x) for x in g["avisos"] if isinstance(x, list) and len(x) == 3]}


def cuenta(estado: dict, ahora_s: float, tipo: str, enviada: bool):
    estado["avisos"] = [x for x in estado["avisos"] if ahora_s - x[0] < 86400] + [[ahora_s, enviada, tipo]]


# ---------- lectura ----------
async def lee(db, activo: str, ahora: int, cache: dict, ahora_s: float) -> dict:
    sym = f"{activo}USDT_PERP.A"
    c = cache.get(activo)
    if c is None or ahora_s - c["t"] >= CACHE_S:
        r7 = await db.fetch(SQL_RANGO, sym, ahora - 7 * 1440, ahora)
        cola = await db.fetch(SQL_LIQ_COLA, sym, ahora - 30 * 1440, ahora, LIQ_COLA)
        oi = await db.fetch(SQL_OI, sym, ahora - 7 * 1440, ahora)
        cambios = [abs(b[1] / a[1] - 1) * 100 for a, b in zip(oi, oi[1:], strict=False) if b[0] - a[0] == 5 and a[1]]
        c = cache[activo] = {"t": ahora_s, "rango7": tuple(r7[0]) if r7 else (None, None),
                             "liq_cola": {s: float(p) for s, p in cola if p is not None}, "oi_cola": _pctl(cambios, OI_COLA)}
    return c | {"velas": await db.fetch(SQL_VELAS, sym, ahora - VELAS_LEIDAS, ahora),
                "liq": await db.fetch(SQL_LIQ, sym, ahora - LIQ_VENTANA, ahora),
                "oi": await db.fetch(SQL_OI, sym, ahora - 20, ahora),
                "grandes": await db.fetch(SQL_GRANDES, activo, ahora - 2, ahora)}


def _pctl(xs: list, q: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else 0.0


def _serie(filas) -> tuple[dict, int] | None:
    """{minuto: (h, l, c, buy, vol)} sin huecos (un minuto sin fila: el cierre anterior y volumen 0) y el ultimo minuto."""
    f = {int(r[0]): tuple(float(x) for x in r[1:6]) for r in filas}
    if not f:
        return None
    out, prev = {}, f[min(f)][2]
    for m in range(min(f), max(f) + 1):
        out[m] = x = f.get(m) or (prev, prev, prev, 0.0, 0.0)
        prev = x[2]
    return out, max(f)


def _usd(x: float) -> str:
    return f"{x / 1e6:.2f} M USD" if x >= 1e6 else f"{x / 1e3:.0f} mil USD"


def _umbral(tabla: dict, activo: str) -> float:
    return tabla.get(activo, tabla["SOL"])


# ---------- senales: cada una da candidatos {clave, tipo, valor, lado, texto (None = no se avisa), no_desde} ----------
def senales(d: dict, activo: str, p: dict, ahora: int) -> list[dict]:
    out: list[dict] = []
    # liquidaciones: la suma de 5 min de cada lado contra su cola de 30 d (con suelo)
    for lado_liq, nombre, lado in (("long", "largos", -1), ("short", "cortos", 1)):
        suma = sum(float(x[2]) for x in d["liq"] if x[1] == lado_liq)
        um = max(d["liq_cola"].get(lado_liq, 0.0), _umbral(LIQ_SUELO, activo))
        alto = suma >= um
        out.append({"clave": f"{activo}|liq|{lado_liq}", "tipo": "liquidaciones", "valor": "alto" if alto else None, "lado": lado,
                    "texto": f"{activo}: liquidaciones de {nombre}, {_usd(suma)} en {LIQ_VENTANA} min (su cola de 30 d:"
                             f" {_usd(d['liq_cola'].get(lado_liq, 0.0))})" if alto else None})
    # grandes: una operacion o el racimo de 1 min (mismo lado y mercado) por encima del umbral del activo
    racimos: dict = {}
    for m, venue, compra, usd in d["grandes"]:
        k = (int(m), "contado" if str(venue).endswith("_spot") else "perpetuo", bool(compra))
        suma, n = racimos.get(k, (0.0, 0))
        racimos[k] = (suma + float(usd), n + 1)
    for (m, mercado, compra), (suma, n) in sorted(racimos.items()):
        if suma >= _umbral(GRANDE_USD, activo):
            out.append({"clave": f"{activo}|grande|{mercado}|{int(compra)}", "tipo": "grande", "valor": m, "lado": 1 if compra else -1,
                        "texto": f"{activo}: {'compra' if compra else 'venta'} grande en {mercado}, {_usd(suma)} en 1 min"
                                 f" ({n} operacion{'es' if n > 1 else ''})"})
    s = _serie(d["velas"])
    if s is None or ahora - s[1] > 3:  # sin velas frescas no se juzga el precio (el centinela ya avisa del retraso)
        return out + _avance(activo, p)
    v, u = s
    c = v[u][2]
    trs = [max(v[m][0], v[m - 1][2]) - min(v[m][1], v[m - 1][2]) for m in range(u - ATR_VELAS + 1, u + 1) if m - 1 in v]
    atr = sum(trs) / len(trs) if trs else 0.0
    if atr <= 0:
        return out + _avance(activo, p)
    # absorcion: |delta agresivo de 5 min| en su cola de 24 h con el precio quieto (menos de ABS_QUIETO_ATR)
    dl = {m: (2 * x[3] - x[4]) * x[2] for m, x in v.items()}
    d5 = {m: sum(dl[k] for k in range(m - ABS_VENTANA + 1, m + 1)) for m in v if m - ABS_VENTANA in v}
    if u in d5 and u - ABS_VENTANA in v:
        ahora_d = d5[u]
        um = max(_pctl([abs(x) for m, x in d5.items() if m <= u - ABS_VENTANA], ABS_COLA), _umbral(ABS_SUELO, activo))
        mov = c - v[u - ABS_VENTANA][2]
        hay = abs(ahora_d) >= um and abs(mov) <= ABS_QUIETO_ATR * atr
        sg = 1 if ahora_d > 0 else -1
        out.append({"clave": f"{activo}|absorcion", "tipo": "absorcion", "valor": sg if hay else None, "lado": -sg,
                    "texto": f"{activo}: absorcion, {'compras' if sg > 0 else 'ventas'} agresivas de {_usd(abs(ahora_d))} en"
                             f" {ABS_VENTANA} min y el precio no las sigue ({mov:+.4g}, {mov / atr:+.1f} ATR): hay"
                             f" {'vendedor' if sg > 0 else 'comprador'} pasivo" if hay else None})
    # OI: el cambio de la ultima barra de 5 min en su cola de 7 d, con el signo del precio de esa barra
    oi = [(int(m), float(x)) for m, x in d["oi"]]
    if len(oi) >= 2 and oi[-1][0] - oi[-2][0] == 5 and oi[-2][1] > 0:
        b, pct = oi[-1][0], (oi[-1][1] / oi[-2][1] - 1) * 100
        fin, ini = v.get(min(b + 4, u)), v.get(b - 1)
        dp = (fin[2] - ini[2]) if fin and ini else 0.0
        if abs(pct) >= max(d["oi_cola"], OI_SUELO_PCT) and dp:
            clase, lado = {(1, 1): ("entran largos", 1), (1, -1): ("entran cortos", -1), (-1, 1): ("salen cortos", 1),
                           (-1, -1): ("salen largos", -1)}[(1 if pct > 0 else -1, 1 if dp > 0 else -1)]
            out.append({"clave": f"{activo}|oi", "tipo": "oi", "valor": f"{clase}@{b}", "lado": lado,
                        "texto": f"{activo}: interes abierto {pct:+.2f} % en 5 min con el precio {'subiendo' if dp > 0 else 'bajando'}:"
                                 f" {clase}"})
    # niveles: maximos y minimos del dia, de 24 h y de 7 d, SIN la ultima vela (la que puede romperlos)
    previas = [m for m in v if u - 1440 <= m < u]
    hoy = [m for m in previas if m >= u // 1440 * 1440]
    hi7, lo7 = d["rango7"]
    for es_max in (True, False):
        f = max if es_max else min
        k = 0 if es_max else 1
        cand = [("7 d", f([x for x in (hi7 if es_max else lo7, f(v[m][k] for m in previas) if previas else None) if x is not None],
                          default=None)),
                ("24 h", f((v[m][k] for m in previas), default=None)), ("dia", f((v[m][k] for m in hoy), default=None))]
        vistos: list = []
        for nombre, nivel in cand:
            if nivel is None or any(abs(nivel - x) <= MISMO_NIVEL_ATR * atr for x in vistos):
                continue
            vistos.append(nivel)
            dist = (nivel - c) if es_max else (c - nivel)  # >0: el nivel aun no se ha cruzado
            estado = "roto" if dist < -RUPTURA_ATR * atr else "cerca" if dist <= CERCA_ATR * atr else "lejos"
            que = "maximo" if es_max else "minimo"
            clave = f"{activo}|nivel|{que}|{nombre}"
            if estado == "roto":
                out.append({"clave": clave, "tipo": "ruptura", "valor": estado, "lado": 1 if es_max else -1,
                            "texto": f"{activo}: ruptura del {que} de {nombre} ({nivel:g}), cierre de 1 min en {c:g}"
                                     f" ({abs(dist) / atr:.1f} ATR mas alla)"})
            else:
                out.append({"clave": clave, "tipo": "cerca", "valor": estado, "lado": -1 if es_max else 1, "no_desde": ("roto",),
                            "texto": None if estado == "lejos" else
                            f"{activo}: {'resistencia' if es_max else 'soporte'} cerca, {que} de {nombre} en {nivel:g},"
                            f" a {dist / atr:.1f} ATR ({abs(dist) / c * 100:.2f} %) del precio {c:g}"})
    return out + _avance(activo, p)


def _r(p: dict) -> float | None:
    e, s, m, lado = p.get("entrada"), p.get("stop"), p.get("marca"), p.get("lado")
    if not (e and s and m and lado) or (e - s) * lado <= 0:
        return None
    return (m - e) * lado / abs(e - s)


def _avance(activo: str, p: dict) -> list[dict]:
    """El avance en R (entrada, stop y objetivo de Bybit): se avisa al cruzar un hito; la primera lectura solo lo fija."""
    r = _r(p)
    if r is None:
        return []
    tramo = max((h for h in R_HITOS if r >= h), default=None)
    e, s, m, o, lado = p["entrada"], p["stop"], p["marca"], p.get("objetivo"), p["lado"]
    obj = f", objetivo {o:g} a {(o - m) * lado / abs(e - s):.1f} R" if o else ""
    que = f"{tramo:+.1f} R" if tramo is not None else f"por debajo de {R_HITOS[0]:+.1f} R"
    return [{"clave": f"{activo}|avance", "tipo": "avance", "valor": "bajo" if tramo is None else tramo,
             "lado": lado if r > 0 else -lado, "no_desde": (None,),
             "texto": f"{activo} {'largo' if lado > 0 else 'corto'}: {que} (precio {m:g}; entrada {e:g}, stop {s:g}{obj})"}]


def _pie(lado: int | None, p: dict, activo: str) -> str:
    pos = "LARGO" if p["lado"] > 0 else "CORTO"
    r = _r(p)
    ahora = f" · ahora {r:+.2f} R" if r is not None else ""
    if not lado:
        return f"tu {pos} en {activo}{ahora}"
    return f"{'A FAVOR' if lado * p['lado'] > 0 else 'EN CONTRA'} de tu {pos} en {activo}{ahora}"


# ---------- antiruido ----------
def _decide(cand: dict, estado: dict, ahora_s: float) -> str | None:
    """None: no se avisa · 'emite' · 'contiene' (pasa del tope por hora: al resumen). Solo al cambiar de estado; el que cae
    en el enfriamiento NO pisa el estado, para que el cambio siga pendiente cuando acabe."""
    vivo, k = estado["vivo"], cand["clave"]
    prev = vivo.get(k)
    if cand["valor"] == prev:
        return None
    if cand["texto"] is None or prev in cand.get("no_desde", ()):
        vivo[k] = cand["valor"]
        return None
    ke = f"{cand['tipo']}|{k}"
    if ahora_s - estado["enfria"].get(ke, -math.inf) < ENFRIA[cand["tipo"]] * 60:
        return None
    vivo[k], estado["enfria"][ke] = cand["valor"], ahora_s
    estado["emitidos"] = [t for t in estado["emitidos"] if ahora_s - t < 3600]
    if len(estado["emitidos"]) >= TOPE_HORA:
        return "contiene"
    estado["emitidos"].append(ahora_s)
    return "emite"


async def tic(db, posiciones: list, estado: dict, cache: dict, ahora_s: float) -> list[dict]:
    """Los avisos de este minuto: [{tipo, activo, lado, texto, contenido}]. Sin posicion abierta no se lee ni se calcula
    nada (y lo vivo se olvida: una posicion nueva empieza de cero)."""
    por_activo = {}
    for p in posiciones or []:
        sym = str(p.get("symbol") or "")
        if sym.endswith("USDT") and p.get("lado") in (1, -1):
            por_activo.setdefault(sym[:-4], p)
    estado["vivo"] = {k: x for k, x in estado["vivo"].items() if k.split("|")[0] in por_activo}
    if not por_activo:
        estado["periodo"], estado["resumen_t"] = [], None
        return []
    ahora, out = int(ahora_s // 60), []
    for activo, p in por_activo.items():
        d = await lee(db, activo, ahora, cache, ahora_s)
        for cand in senales(d, activo, p, ahora):
            que = _decide(cand, estado, ahora_s)
            if que is None:
                continue
            out.append({"tipo": cand["tipo"], "activo": activo, "lado": cand["lado"], "contenido": que == "contiene",
                        "texto": f"{cand['texto']}\n{_pie(cand['lado'], p, activo)}"})
            estado["periodo"].append([cand["tipo"], activo, que == "contiene"])
    if estado["resumen_t"] is None:
        estado["resumen_t"] = ahora_s
    elif ahora_s - estado["resumen_t"] >= RESUMEN_MIN * 60:
        if estado["periodo"]:
            n: dict = {}
            for t, a, _ in estado["periodo"]:
                n[f"{a} {t}"] = n.get(f"{a} {t}", 0) + 1
            cont = sum(1 for x in estado["periodo"] if x[2])
            out.append({"tipo": "resumen", "activo": None, "lado": None, "contenido": False,
                        "texto": f"seguimiento, ultimos {RESUMEN_MIN} min: {len(estado['periodo'])} avisos ("
                                 + ", ".join(f"{k} {x}" for k, x in n.items()) + ")"
                                 + (f"\n{cont} no enviados por el tope de {TOPE_HORA} por hora" if cont else "")})
        estado["periodo"], estado["resumen_t"] = [], ahora_s
    return out
