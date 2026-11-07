"""LA DEFINICION COMPARTIDA de la anatomia (BOT-5): lo que el estudio (scripts/anatomia_*.py) y la sombra del bot
(app/bot/sombra.py) usan para decidir y etiquetar UNA candidata, escrito UNA vez. Biblioteca estandar y sin imports de
app/: anatomia_extrae corre en el nodo y anatomia_comun lo reexporta tal cual.

  cinta_fila      una fila de orderflow_cinta -> el minuto de la base (flujos por venue y tamano, precio de VENUE_REF)
  es_decision     la rejilla: decision al cierre del minuto t con (t+1) multiplo de REJILLA
  suma_ventana    la suma de los ultimos w minutos (incluido t), None con menos de cob*w validos (= rsum del estudio)
  cumple          la cola: bajo x <= u (x < u si estricto), alto x >= u (x > u)
  recorre         el camino desde la entrada o[t+1]: primer toque, el stop gana si un minuto toca ambos
  etiqueta_entera la etiqueta del estudio vectorizado: exige los HORIZONTE minutos del camino, aunque toque antes
  sin_solape      una abierta a la vez

El estudio conserva sus gemelos numpy (rsum, etiquetas, la capa B) porque calcula cien variables a la vez; los fija a
estas funciones tests/test_anatomia.py, y a la sombra, K119.
"""
from __future__ import annotations

from datetime import UTC, datetime

# ---------------------------------------------------------------- universo
VENUES_PERP = ("binance_usdm", "bybit_linear", "okx_swap", "bitget_usdt", "deribit_perp")
VENUES_SPOT = ("binance_spot", "bybit_spot", "okx_spot", "coinbase_spot")
VENUE_REF = "binance_usdm"          # precio de referencia, libro de referencia
VENUE_PRIMA = "coinbase_spot"       # la prima de contado
PERP, SPOT = frozenset(VENUES_PERP), frozenset(VENUES_SPOT)


def _ts(s: str) -> int:
    return int(datetime.fromisoformat(s).replace(tzinfo=UTC).timestamp())


CAPA_B_DESDE = _ts("2026-10-18")
FUENTE_CINTA, FUENTE_FUTUROS, FUENTE_L1 = 1, 2, 3     # columna `fuente` de la base; 0 = sin precio
GRANDE_100K = 100_000.0             # flujo de ordenes grandes: impresos >= 100 mil USD
GRANDE_1M = 1_000_000.0
# M8 · CASCADA: >= CASCADA_N liquidaciones del MISMO lado (binance y bybit juntos, sin umbral de USD) en CASCADA_S
# segundos. La usan el estudio (anatomia_extrae, liq_{l,s}_casc) y la pagina (/flujo y /libro, por las sueltas de
# /api/orderflow/indicadores): una sola definicion (campana 150).
CASCADA_N, CASCADA_S = 5, 60.0

# columnas de base-<SIM>.tsv.gz, en este orden, con cabecera. Vacio = no hay dato.
COLUMNAS_BASE = (
    "ts", "fuente", "o", "h", "l", "c", "vol_ref",
    "vol_perp", "dp", "dp100k", "dp1m", "np", "mp",          # perp: delta agresor USD, >=100k, >=1M, conteo, mayor
    "vol_spot", "ds", "ds100k", "ds1m", "ns", "ms",           # contado
    "c_cb",                                                   # cierre de coinbase_spot
    "liq_l", "liq_s", "liq_l_n", "liq_s_n",                   # al segundo, agregados al minuto
    "liq_l_ult", "liq_s_ult", "liq_l_casc", "liq_s_casc",     # epoch s del ultimo evento; 1 si cerro cascada
    "liq_l_gr_ult", "liq_s_gr_ult",                           # epoch s del ultimo evento grande
    "deseq01", "deseq05", "deseq05_todos", "alc_c", "alc_v", "mayor_med", "muro_c", "muro_v",
    "liq5_l", "liq5_s", "oi", "oi_ag", "fr", "pfr", "ls", "sa_delta", "sa_vol",
)
COL = {n: i for i, n in enumerate(COLUMNAS_BASE)}
FLUJO_CINTA = ("vol_perp", "dp", "dp100k", "dp1m", "np", "vol_spot", "ds", "ds100k", "ds1m", "ns", "vol_ref")

# ---------------------------------------------------------------- etiquetas
REJILLA = 5
HORIZONTE = 240
COMISION = 0.00055                  # 5.5 bps por lado
ESQUEMAS = {"E1": (0.01, 0.006), "E2": (0.02, 0.006)}
LADOS = {"largo": 1, "corto": -1}


# ---------------------------------------------------------------- la cinta, fila a fila
def minuto_vacio() -> list:
    """Un minuto de una hora PRESENTE de la cinta: flujos a cero, precios vacios."""
    f = [None] * len(COLUMNAS_BASE)
    for c in FLUJO_CINTA:
        f[COL[c]] = 0.0
    return f


def cinta_fila(f: list, bordes: dict, ts: str, venue: str, precio: float, usd: float, compra: bool) -> None:
    """Suma una fila de la cinta al minuto f. `bordes`: {VENUE_REF: [ts apertura, ts cierre], VENUE_PRIMA: ts} del
    minuto. Las filas llegan en el orden del fichero: con ts empatado, la apertura es la PRIMERA y el cierre la ULTIMA."""
    sg = usd if compra else -usd
    if venue in PERP:
        k = "p"
    elif venue in SPOT:
        k = "s"
    else:
        return
    f[COL["vol_" + ("perp" if k == "p" else "spot")]] += usd
    f[COL["d" + k]] += sg
    if usd >= GRANDE_100K:
        f[COL["d" + k + "100k"]] += sg
        if usd >= GRANDE_1M:
            f[COL["d" + k + "1m"]] += sg
    f[COL["n" + k]] += 1
    im = COL["m" + k]
    if f[im] is None or usd > f[im]:
        f[im] = usd
    if venue == VENUE_REF:
        io, ih, il, ic = COL["o"], COL["h"], COL["l"], COL["c"]
        f[COL["vol_ref"]] += usd
        f[COL["fuente"]] = FUENTE_CINTA
        oc = bordes.get(VENUE_REF)
        if oc is None:
            bordes[VENUE_REF] = [ts, ts]
            f[io] = f[ih] = f[il] = f[ic] = precio
        else:
            if ts < oc[0]:
                oc[0], f[io] = ts, precio
            if ts >= oc[1]:
                oc[1], f[ic] = ts, precio
            if precio > f[ih]:
                f[ih] = precio
            if precio < f[il]:
                f[il] = precio
    elif venue == VENUE_PRIMA:
        oc = bordes.get(VENUE_PRIMA)
        if oc is None or ts >= oc:
            bordes[VENUE_PRIMA] = ts
            f[COL["c_cb"]] = precio


# ---------------------------------------------------------------- la decision
def es_decision(ts: int) -> bool:
    """ts: epoch s del INICIO del minuto t. Se decide a su cierre si (t+1) es multiplo de REJILLA."""
    return ((ts // 60) + 1) % REJILLA == 0


def suma_ventana(valores, cob: float = 0.8):
    """valores: los w minutos de la ventana (None = sin dato). La suma de los validos, o None si son menos de cob*w."""
    w = len(valores)
    v = [x for x in valores if x is not None]
    return sum(v) if len(v) >= cob * w - 1e-9 else None


def cumple(x, cola: str, u, estricto: bool = False) -> bool:
    if x is None:
        return False
    if cola == "alto":
        return x > u if estricto else x >= u
    if cola == "bajo":
        return x < u if estricto else x <= u
    raise ValueError(f"cola {cola!r}: la sombra solo cuenta variables continuas")


# ---------------------------------------------------------------- el camino
def niveles(e: float, lado: int, esquema: str):
    tp, sl = ESQUEMAS[esquema]
    obj = e * (1 + tp) if lado > 0 else e * (1 - tp)
    stop = e * (1 - sl) if lado > 0 else e * (1 + sl)
    return obj, stop


def toque(h: float, lo: float, obj: float, stop: float, lado: int):
    """(exito, neto) si el minuto toca; el stop gana si toca ambos. None si no toca."""
    toca_stop = lo <= stop if lado > 0 else h >= stop
    toca_obj = h >= obj if lado > 0 else lo <= obj
    if toca_stop:
        return 0
    if toca_obj:
        return 1
    return None


def recorre(e: float, lado: int, esquema: str, barras):
    """barras: (h, l) de los minutos t+1, t+2, ... que se tengan, todos con precio. (exito, neto, k) del primer toque,
    k = indice en barras; None si no toca en ellas."""
    tp, sl = ESQUEMAS[esquema]
    obj, stop = niveles(e, lado, esquema)
    for k, (h, lo) in enumerate(barras):
        r = toque(h, lo, obj, stop, lado)
        if r == 0:
            return (0, -sl - 2 * COMISION, k)
        if r == 1:
            return (1, tp - 2 * COMISION, k)
    return None


def vence(e: float, c_final: float, lado: int) -> float:
    return lado * (c_final / e - 1) - 2 * COMISION


def etiqueta(o, h, lo, c, t: int, lado: int, esquema: str):
    """Operacion decidida al cierre del minuto t: (exito, neto, minuto de salida) o None si falta un minuto ANTES
    de salir. o h l c: secuencias por minuto (None = sin precio)."""
    tp, sl = ESQUEMAS[esquema]
    if t + HORIZONTE >= len(o) or o[t + 1] is None:
        return None
    e = o[t + 1]
    obj, stop = niveles(e, lado, esquema)
    for m in range(t + 1, t + HORIZONTE + 1):
        if h[m] is None or lo[m] is None or c[m] is None:
            return None
        r = toque(h[m], lo[m], obj, stop, lado)
        if r == 0:
            return (0, -sl - 2 * COMISION, m)
        if r == 1:
            return (1, tp - 2 * COMISION, m)
    return (0, vence(e, c[t + HORIZONTE], lado), t + HORIZONTE)


def etiqueta_entera(o, h, lo, c, t: int, lado: int, esquema: str):
    """La etiqueta de `etiquetas` del estudio en el punto t: (exito, neto, minuto de salida), o None si falta la
    entrada o CUALQUIER minuto t+1 .. t+HORIZONTE (aunque el toque llegue antes)."""
    if t + HORIZONTE >= len(o) or o[t + 1] is None:
        return None
    camino = range(t + 1, t + HORIZONTE + 1)
    if any(h[m] is None or lo[m] is None or c[m] is None for m in camino):
        return None
    e = o[t + 1]
    r = recorre(e, lado, esquema, [(h[m], lo[m]) for m in camino])
    if r is None:
        return (0, vence(e, c[t + HORIZONTE], lado), t + HORIZONTE)
    return (r[0], r[1], t + 1 + r[2])


def sin_solape(decisiones):
    """decisiones: (t, salida) en orden de t, ya filtradas por la condicion. Una abierta a la vez: se toma la
    primera y se salta toda decision con t < salida de la abierta. Devuelve los indices tomados."""
    tomadas, libre = [], -1
    for i, (t, salida) in enumerate(decisiones):
        if t >= libre:
            tomadas.append(i)
            libre = salida
    return tomadas


def empate(esquema: str) -> float:
    """Tasa de toque que deja el neto en cero con comision: (sl + 2c) / (tp + sl). E1 44.4 %, E2 27.3 %."""
    tp, sl = ESQUEMAS[esquema]
    return (sl + 2 * COMISION) / (tp + sl)


def azar(esquema: str) -> float:
    """Tasa de toque de un paseo sin deriva: sl / (tp + sl). E1 37.5 %, E2 23.1 %."""
    tp, sl = ESQUEMAS[esquema]
    return sl / (tp + sl)


def esquema_de(objetivo: float, stop: float) -> str:
    """El esquema de una candidata congelada (que trae objetivo y stop, no el nombre)."""
    for k, v in ESQUEMAS.items():
        if v == (objetivo, stop):
            return k
    raise ValueError(f"objetivo {objetivo} / stop {stop}: ningun esquema")
