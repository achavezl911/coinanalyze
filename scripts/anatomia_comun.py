"""EL CRITERIO de la anatomia (campana BOT-3e): «que pasa antes de un movimiento». Escrito y commiteado ANTES de
medir nada. Biblioteca estandar. Lo usan `anatomia_extrae.py` (nodo, stdlib), `anatomia_estudio.py` (143, numpy y
scikit-learn) y `tests/test_anatomia.py`.

LA PREGUNTA: las huellas que el mapa (BOT-3c) no vio -liquidaciones finas, cinta, libro, horario- ¿se ajustan a los
movimientos reales? Una huella vale si, cuando aparece, una operacion abierta en el minuto siguiente toca su objetivo
mas a menudo que el azar de la misma rejilla, y lo sigue haciendo en dias que nadie miro al elegirla.

LA REJILLA BASE (anatomia_extrae): 1 minuto por simbolo. Minuto m = [m, m+60 s). Lo que ocurre en m se sabe al
CERRAR m. Una fila de 5 min de coinalyze con ts T cubre [T, T+5) y se coloca en el minuto T+4 (su cierre); una de
1 min, en T. Nada se rellena hacia delante en la base: el relleno (ffill) lo hace el estudio, solo hacia el pasado.

LA DECISION: en la rejilla de 5 min, al cierre del minuto t con (t+1) multiplo de 5. Todo lo que entra sale de
minutos <= t. Entrada: la apertura del minuto t+1. Camino: minutos t+1 .. t+240.

LA ETIQUETA (esquema = objetivo % / stop %): primer toque con maximos y minimos de 1 min; si un minuto toca ambos,
gana el stop. Sin toque: sale al cierre del minuto t+240 (VENCE). Un minuto del camino sin precio anula la etiqueta.
Neto = resultado - 2 * COMISION. Exito (la «tasa de toque») = toco el objetivo.

LAS CAPAS: A desde 2026-08-05 (5 min de coinalyze + precio de lo que haya + tecnico + horario); B desde 2026-10-18
(cinta, libro, liquidaciones al segundo; precio SOLO de la cinta de binance_usdm). DESCUBRIMIENTO: decisiones con
t + 240 < 2026-11-03 00:00Z. CONFIRMACION: decisiones con t >= la fecha de --confirma (por defecto 2026-11-03).
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

# ---------------------------------------------------------------- universo
SIMBOLOS = ("BTC", "ETH", "SOL")
VENUES_PERP = ("binance_usdm", "bybit_linear", "okx_swap", "bitget_usdt", "deribit_perp")
VENUES_SPOT = ("binance_spot", "bybit_spot", "okx_spot", "coinbase_spot")
VENUE_REF = "binance_usdm"          # precio de referencia, libro de referencia
VENUE_PRIMA = "coinbase_spot"       # la prima de contado

# ---------------------------------------------------------------- calendario (UTC)
def _ts(s: str) -> int:
    return int(datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp())

ARCHIVO_DESDE = "2026-08-04"
CAPA_A_DESDE = _ts("2026-08-05")
CAPA_B_DESDE = _ts("2026-10-18")
CINTA_DESDE = "2026-10-18"
LIQ_RT_DESDE = "2026-10-20"
CONFIRMACION_DESDE = "2026-11-03"
CORTE_DESCUBRIMIENTO = _ts(CONFIRMACION_DESDE)

# ---------------------------------------------------------------- el archivo
# dir -> (prefijo del fichero, columnas del COPY). Las 5 min de coinalyze llevan `interval` y su simbolo es tipo
# BTCUSDT_PERP.A: se asigna por prefijo y, si un activo trae varios, gana el que acaba en _PERP.A (los demas se
# cuentan en huecos.json, «simbolos_ignorados»).
TABLAS = {
    "cinta": ("orderflow_cinta", ("ts", "venue", "symbol", "precio", "base", "usd", "compra", "id")),
    "libro": ("libro_foto", ("ts", "venue", "symbol", "ts_libro", "compra", "venta", "paso", "compra_nivel",
                             "compras", "venta_nivel", "ventas", "alcance_compra", "alcance_venta")),
    "liquidaciones-realtime": ("liquidations_realtime", ("ts", "symbol", "exchange", "side", "notional_usd",
                                                         "price", "qty", "event_id")),
    "liquidaciones-5min": ("liquidations", ("ts", "symbol", "interval", "long_liq", "short_liq")),
    "oi-bybit": ("oi_bybit", ("ts", "symbol", "interval", "oi_open", "oi_high", "oi_low", "oi_close")),
    "oi": ("open_interest", ("ts", "symbol", "interval", "oi_open", "oi_high", "oi_low", "oi_close")),
    "funding": ("funding_rate", ("ts", "symbol", "interval", "fr_open", "fr_high", "fr_low", "fr_close")),
    "funding-previsto": ("predicted_funding_rate", ("ts", "symbol", "interval", "pfr_open", "pfr_high",
                                                   "pfr_low", "pfr_close")),
    "largos-cortos": ("long_short_ratio", ("ts", "symbol", "interval", "long_pct", "short_pct", "ratio")),
    "spot-agregado": ("spot_trades_agg", ("ts", "symbol", "exchange", "interval", "buy_vol_usd", "sell_vol_usd",
                                          "inst_buy_usd", "inst_sell_usd", "mid_buy_usd", "mid_sell_usd",
                                          "retail_buy_usd", "retail_sell_usd", "trade_count")),
    # precio de respaldo ANTES de la cinta (solo capa A), por este orden: el ultimo precio de futures_trades_realtime
    # de binance (muestras de ~5 s: su maximo y minimo se quedan cortos) y el medio del libro L1 de binance.
    "futuros-realtime": ("futures_trades_realtime", ("ts", "symbol", "exchange", "buy_vol_usd", "sell_vol_usd",
                                                     "large_buy_usd", "large_sell_usd", "trade_count", "last_px",
                                                     "last_event_ms", "x")),
    "libro-l1": ("orderbook_snapshot", ("ts", "symbol", "exchange", "bid_px", "ask_px", "mid_px")),
}
# desde cuando se espera cada dir (para contar huecos): antes no es hueco, es que no existia
ESPERADO_DESDE = {"cinta": CINTA_DESDE, "libro": CINTA_DESDE, "liquidaciones-realtime": LIQ_RT_DESDE,
                  "liquidaciones-5min": ARCHIVO_DESDE, "oi-bybit": ARCHIVO_DESDE, "funding": ARCHIVO_DESDE,
                  "funding-previsto": ARCHIVO_DESDE, "largos-cortos": ARCHIVO_DESDE,
                  "spot-agregado": ARCHIVO_DESDE}
FUENTE_CINTA, FUENTE_FUTUROS, FUENTE_L1 = 1, 2, 3     # columna `fuente` de la base; 0 = sin precio

# ---------------------------------------------------------------- umbrales de la extraccion
GRANDE_100K = 100_000.0             # flujo de ordenes grandes: impresos >= 100 mil USD
GRANDE_1M = 1_000_000.0
LIQ_GRANDE_USD = {"BTC": 250_000.0, "ETH": 100_000.0, "SOL": 50_000.0}   # «evento grande» de liquidacion
CASCADA_N, CASCADA_S, CASCADA_CALMA_S = 5, 60.0, 120.0                   # M8
LIBRO_BANDAS = (0.001, 0.005)       # desequilibrio a +-0.1 % y +-0.5 % del medio
MURO_DIST, MURO_VECES, MURO_QUEDA = 0.003, 5.0, 0.2   # M3: <= 0.3 %, >= 5x la mediana del lado, queda < 20 %

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

# ---------------------------------------------------------------- etiquetas
REJILLA = 5
HORIZONTE = 240
COMISION = 0.00055                  # 5.5 bps por lado
ESQUEMAS = {"E1": (0.01, 0.006), "E2": (0.02, 0.006)}
LADOS = {"largo": 1, "corto": -1}


def empate(esquema: str) -> float:
    """Tasa de toque que deja el neto en cero con comision: (sl + 2c) / (tp + sl). E1 44.4 %, E2 27.3 %."""
    tp, sl = ESQUEMAS[esquema]
    return (sl + 2 * COMISION) / (tp + sl)


def azar(esquema: str) -> float:
    """Tasa de toque de un paseo sin deriva: sl / (tp + sl). E1 37.5 %, E2 23.1 %."""
    tp, sl = ESQUEMAS[esquema]
    return sl / (tp + sl)


def etiqueta(o, h, l, c, t: int, lado: int, esquema: str):
    """Operacion decidida al cierre del minuto t: (exito, neto, minuto de salida) o None si falta un minuto.
    o h l c: secuencias por minuto (None = sin precio)."""
    tp, sl = ESQUEMAS[esquema]
    if t + HORIZONTE >= len(o) or o[t + 1] is None:
        return None
    e = o[t + 1]
    obj = e * (1 + tp) if lado > 0 else e * (1 - tp)
    stop = e * (1 - sl) if lado > 0 else e * (1 + sl)
    for m in range(t + 1, t + HORIZONTE + 1):
        if h[m] is None or l[m] is None or c[m] is None:
            return None
        toca_stop = l[m] <= stop if lado > 0 else h[m] >= stop
        toca_obj = h[m] >= obj if lado > 0 else l[m] <= obj
        if toca_stop:
            return (0, -sl - 2 * COMISION, m)
        if toca_obj:
            return (1, tp - 2 * COMISION, m)
    return (0, lado * (c[t + HORIZONTE] / e - 1) - 2 * COMISION, t + HORIZONTE)


def sin_solape(decisiones):
    """decisiones: (t, salida) en orden de t, ya filtradas por la condicion. Una abierta a la vez: se toma la
    primera y se salta toda decision con t < salida de la abierta. Devuelve los indices tomados."""
    tomadas, libre = [], -1
    for i, (t, salida) in enumerate(decisiones):
        if t >= libre:
            tomadas.append(i)
            libre = salida
    return tomadas


# ---------------------------------------------------------------- estadistica
Z_DIAS = 7                          # z y percentiles: contra los 7 dias anteriores, SIN el presente
Z_MIN_MIN = 2 * 1440                # minimo de minutos validos en la ventana para dar un z
PCT_MIN = 2 * 288                   # minimo de puntos de rejilla para dar un percentil
DECIL = 0.10                        # cola alta: x >= p90; baja: x <= p10 (umbral sobre el DESCUBRIMIENTO de la capa
                                    # y simbolo). Si la cola recoge > 15 % de las decisiones (empates) se usa >
                                    # estricto; si recoge < 1 %, la celda es DEGENERADA y no se mide.
COLA_MAX, COLA_MIN = 0.15, 0.01
DESPLAZAMIENTOS = 2000              # p por desplazamiento circular de la condicion contra las etiquetas
DESPL_MIN_MIN = 360                 # minimo 6 h (en minutos; en la rejilla, 72 pasos)
SEMILLA = 20261102
FDR_Q = 0.10                        # Benjamini-Hochberg sobre TODAS las celdas de una corrida
N_MIN_MECANISMO = 10                # n sin solape < 10 = SIN N
N_MIN_CONFIRMA = 30
WILSON_Z = 1.6448536269514722       # 90 % bilateral
MAX_CANDIDATAS, SOLO_MIRAR = 10, 5
RUIDOS = 20                         # columnas N(0,1) de control negativo, en cada corrida: ninguna debe pasar
# todo junto: HistGradientBoosting por lado y capa, simbolos juntos (el simbolo es una columna)
HGB = dict(learning_rate=0.05, max_iter=150, max_leaf_nodes=15, min_samples_leaf=200, l2_regularization=1.0)
HGB_TRAMOS, HGB_PURGA_MIN, HGB_BARAJADOS, HGB_MEJOR = 5, 240, 20, 0.05
# control positivo (--control): tras cada M1 largo, el precio sube EMPUJE en EMPUJE_MIN minutos y se queda;
# y una columna `oraculo` = exito largo E1 + N(0, ORACULO_RUIDO). Ve el estudio si: M1 largo E1 pasa FDR en algun
# simbolo, oraculo alto largo E1 pasa FDR en algun simbolo, y NINGUNA columna de ruido pasa FDR.
EMPUJE, EMPUJE_MIN, ORACULO_RUIDO = 0.015, 30, 0.5


def wilson_inferior(exitos: int, n: int, z: float = WILSON_Z) -> float:
    if n <= 0:
        return 0.0
    p = exitos / n
    d = 1 + z * z / n
    centro = p + z * z / (2 * n)
    margen = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centro - margen) / d


def benjamini_hochberg(ps):
    """q de BH en el orden de entrada (None se respeta y no cuenta en m)."""
    idx = [i for i, p in enumerate(ps) if p is not None]
    m = len(idx)
    q = [None] * len(ps)
    orden = sorted(idx, key=lambda i: ps[i])
    previo = 1.0
    for rango in range(m, 0, -1):
        i = orden[rango - 1]
        previo = min(previo, ps[i] * m / rango)
        q[i] = previo
    return q


def veredicto_confirma(exitos: int, n: int, esquema: str) -> str:
    """CONFIRMA: n >= 30 y la cota inferior Wilson 90 % supera el empate. CONTEXTO: supera el azar teorico pero no
    el empate. RUIDO: ni eso. SIN N: n < 30 (n sin solape)."""
    if n < N_MIN_CONFIRMA:
        return "SIN N"
    w = wilson_inferior(exitos, n)
    if w > empate(esquema):
        return "CONFIRMA"
    if w > azar(esquema):
        return "CONTEXTO"
    return "RUIDO"


# ---------------------------------------------------------------- variables
# nombre estable -> (capa, tipo, definicion). tipo: cont (deciles), bin (cola «si»), cat (una celda por valor).
# Notacion: S_w(x) suma de los ultimos w minutos (incluido t); z(.) contra los 7 d anteriores sin t; pct(.) rango
# percentil contra los puntos de rejilla de los 7 d anteriores; r_w = c_t / c_{t-w} - 1.
VARIABLES: dict[str, tuple[str, str, str]] = {}


def _v(nombre, capa, tipo, definicion):
    VARIABLES[nombre] = (capa, tipo, definicion)


for _w in (1, 5, 15, 60):
    _v(f"liq_l_{_w}", "B", "cont", f"S_{_w}(USD liquidado de largos, al segundo)")
    _v(f"liq_s_{_w}", "B", "cont", f"S_{_w}(USD liquidado de cortos, al segundo)")
    _v(f"liq_l_{_w}_z", "B", "cont", f"z(liq_l_{_w})")
    _v(f"liq_s_{_w}_z", "B", "cont", f"z(liq_s_{_w})")
_v("liq_l_n60s", "B", "cont", "eventos de liquidacion de largos en el minuto t (60 s)")
_v("liq_s_n60s", "B", "cont", "eventos de liquidacion de cortos en el minuto t")
_v("liq_l_seg_grande", "B", "cont", "segundos desde el ultimo evento de largos >= LIQ_GRANDE_USD hasta el cierre de t")
_v("liq_s_seg_grande", "B", "cont", "lo mismo con cortos")
for _w in (5, 15, 60):
    _v(f"liq5_l_{_w}", "A", "cont", f"S_{_w}(liquidaciones de largos de 5 min de coinalyze)")
    _v(f"liq5_s_{_w}", "A", "cont", f"S_{_w}(liquidaciones de cortos de 5 min)")
    _v(f"liq5_l_{_w}_z", "A", "cont", f"z(liq5_l_{_w})")
    _v(f"liq5_s_{_w}_z", "A", "cont", f"z(liq5_s_{_w})")
for _m, _nom in (("p", "perp"), ("s", "contado")):
    for _w in (1, 5, 15, 60):
        _v(f"d{_m}_{_w}", "B", "cont", f"S_{_w}(delta agresor {_nom}: compra - venta USD, todas sus venues)")
        _v(f"d{_m}_{_w}_z", "B", "cont", f"z(d{_m}_{_w})")
        _v(f"d{_m}100k_{_w}", "B", "cont", f"S_{_w}(delta {_nom} solo impresos >= 100 mil USD)")
        _v(f"d{_m}1m_{_w}", "B", "cont", f"S_{_w}(delta {_nom} solo impresos >= 1 M USD)")
    _v(f"m{_m}_5", "B", "cont", f"mayor impreso {_nom} USD en los ultimos 5 min")
    _v(f"n{_m}_5", "B", "cont", f"S_5(conteo de impresos {_nom})")
    _v(f"n{_m}_5_z", "B", "cont", f"z(n{_m}_5)")
_v("absorcion", "B", "cont", "|z(dp_5)| si pct(|r_5|) <= 1/3, si no 0")
_v("absorcion_firmada", "B", "cont", "z(dp_5) si pct(|r_5|) <= 1/3, si no 0")
_v("deseq01", "B", "cont", "binance_usdm: (compra - venta) / (compra + venta) en USD a +-0.1 % del medio")
_v("deseq05", "B", "cont", "lo mismo a +-0.5 %")
_v("deseq05_todos", "B", "cont", "deseq05 sumando las nueve venues")
_v("d_deseq05_5", "B", "cont", "deseq05_t - deseq05_{t-5}")
_v("alcance_c", "B", "cont", "1 - alcance_compra / medio (binance_usdm)")
_v("alcance_v", "B", "cont", "alcance_venta / medio - 1")
_v("mayor_mediana", "B", "cont", "mayor nivel / mediana de niveles, ambos lados, binance_usdm")
_v("d_oi_1h", "A", "cont", "oi bybit: oi_t / oi_{t-60} - 1 (oi rellenado hacia el pasado)")
_v("d_oi_4h", "A", "cont", "oi bybit a 240 min")
_v("d_oiag_1h", "A", "cont", "open_interest agregado de coinalyze a 60 min")
_v("d_oiag_4h", "A", "cont", "open_interest agregado a 240 min")
_v("cuadrante_oi", "A", "cat", "0 oi+ precio+, 1 oi+ precio-, 2 oi- precio+, 3 oi- precio- (60 min)")
_v("funding", "A", "cont", "ultima tasa de funding (fr_close)")
_v("funding_previsto", "A", "cont", "pfr_close")
_v("ratio_lc", "A", "cont", "long_short_ratio.ratio")
_v("spot_agg_15", "A", "cont", "S_15(compra - venta de spot_trades_agg combined)")
_v("spot_agg_15_z", "A", "cont", "z(spot_agg_15)")
for _w in (5, 15, 60):
    _v(f"dsp_{_w}", "B", "cont", f"ds_{_w} - dp_{_w}")
_v("prima_cb", "B", "cont", "c(coinbase_spot) / c(binance_usdm) - 1")
_v("lider_15", "B", "cont", "corr(r1 contado_{m-1}, r1 perp_m) - corr(r1 perp_{m-1}, r1 contado_m), 15 min; > 0 "
   "manda el contado")
_v("btc_r5", "A", "cont", "r_5 de BTC (solo ETH y SOL)")
_v("btc_r15", "A", "cont", "r_15 de BTC (solo ETH y SOL)")
_v("fuerza_15", "A", "cont", "r_15 - r_15 de BTC (solo ETH y SOL)")
_v("fuerza_60", "A", "cont", "r_60 - r_60 de BTC (solo ETH y SOL)")
for _w in (5, 15, 60):
    _v(f"r_{_w}", "A", "cont", f"r_{_w}")
for _k, _n in (("15m", 15), ("1h", 60), ("4h", 240), ("1d", 1440)):
    _v(f"rsi_{_k}", "A", "cont", f"RSI 14 de Wilder sobre velas de {_n} min que CIERRAN en t (fase movil)")
_v("atr_1h_pct", "A", "cont", "pct(media de 60 min del rango verdadero de 1 min / c)")
_v("dist_max_24h", "A", "cont", "c / max(h, 1440 min) - 1")
_v("dist_min_24h", "A", "cont", "c / min(l, 1440 min) - 1")
_v("dist_max_sem", "A", "cont", "c / max(h, 10080 min) - 1")
_v("dist_min_sem", "A", "cont", "c / min(l, 10080 min) - 1")
for _d in (3, 9):
    _v(f"dist_max_{_d}d", "A", "cont", f"c / maximo de la vela de {_d} d ANTERIOR - 1 (velas ancladas a dia Unix "
       f"multiplo de {_d})")
    _v(f"dist_min_{_d}d", "A", "cont", f"c / minimo de la vela de {_d} d anterior - 1")
_v("dist_vwap_dia", "A", "cont", "c / VWAP desde las 00Z con vol_ref - 1")
_v("sesion", "A", "cat", "0 Asia 00-08Z, 1 Europa 08-13Z, 2 EEUU 13-21Z, 3 resto 21-24Z (hora del minuto t+1)")
_v("min_a_funding", "A", "cont", "minutos hasta la proxima liquidacion de funding (00, 08, 16Z) desde t+1")
_v("min_desde_apertura_eeuu", "A", "cont", "minutos desde las 09:30 de Nueva York (13:30Z en verano, 14:30Z en "
   "invierno), solo de lunes a viernes y si ya abrio; si no, vacio")
_v("viernes_08z", "A", "bin", "t+1 cae en viernes 08:00-08:59Z")
_v("lunes_00z", "A", "bin", "t+1 cae en lunes 00:00-00:59Z")
_v("hora_semana", "A", "cont", "hora de la semana de t+1, 0 = lunes 00Z")
for _i in range(RUIDOS):
    _v(f"ruido_{_i:02d}", "A", "cont", "N(0,1) por decision, semilla fija: control negativo")

# ---------------------------------------------------------------- mecanismos (parametros fijos)
# nombre -> (lado, capas, definicion). Cada uno con su espejo (nombre + "e", lado contrario).
MECANISMOS = {
    "M1": ("largo", "AB", "minimo nuevo de 240 min en los ultimos 15 (min(l, t-14..t) < min(l, t-254..t-15)), "
           "z(liquidaciones de largos 15 min) >= 3 (B: al segundo; A: 5 min) y c_t >= ese minimo * 1.0015"),
    "M1e": ("corto", "AB", "espejo: maximo nuevo, z(liq. de cortos 15 min) >= 3, c_t <= maximo * 0.9985"),
    "M2": ("largo", "B", "z(dp_5) <= -2 y r_5 >= -0.05 %"),
    "M2e": ("corto", "B", "z(dp_5) >= 2 y r_5 <= 0.05 %"),
    "M3": ("corto", "B", "en los ultimos 5 min, un nivel de compra a <= 0.3 % del medio con >= 5x la mediana del "
           "lado desaparece (queda < 20 %) de un minuto al siguiente sin que el minimo llegue a el (binance_usdm)"),
    "M3e": ("largo", "B", "espejo con un nivel de venta"),
    "M4": ("largo", "B", "z(ds_15) >= 2 y z(dp_15) <= 0"),
    "M4e": ("corto", "B", "z(ds_15) <= -2 y z(dp_15) >= 0"),
    "M5": ("largo", "A", "pct(d_oi_4h) >= 0.9, pct(funding) <= 0.1 y r_15 > 0"),
    "M5e": ("corto", "A", "pct(d_oi_4h) >= 0.9, pct(funding) >= 0.9 y r_15 < 0"),
    "M6": ("largo", "B", "atr_1h_pct <= 0.1, c_t > max(h, t-240..t-1) y z(vol_ref 5 min) >= 2"),
    "M6e": ("corto", "B", "atr_1h_pct <= 0.1, c_t < min(l, t-240..t-1) y z(vol_ref 5 min) >= 2"),
    "M7": ("largo", "A", "solo ETH y SOL: z(btc_r5) >= 2 y r_5 < 0.5 * btc_r5"),
    "M7e": ("corto", "A", "solo ETH y SOL: z(btc_r5) <= -2 y r_5 > 0.5 * btc_r5"),
    "M8": ("largo", "B", "el ultimo evento de liquidacion de largos L cerro una racha de >= 5 en 60 s y "
           "120 <= cierre_t - L < 120 + 300 s (dispara una vez, en la primera decision tras la calma)"),
    "M8e": ("corto", "B", "espejo con cortos"),
}
M1_MIN_NUEVO, M1_VENTANA, M1_Z, M1_REBOTE = 240, 15, 3.0, 0.0015
M2_Z, M2_RET = 2.0, 0.0005
M4_Z = 2.0
M5_OI, M5_FUND = 0.9, 0.1
M6_ATR, M6_VOL_Z = 0.1, 2.0
M7_Z, M7_FRAC = 2.0, 0.5


# ---------------------------------------------------------------- horario
def apertura_eeuu_utc(dia: datetime) -> int:
    """Minuto del dia (UTC) de las 09:30 de Nueva York: horario de verano del segundo domingo de marzo al primer
    domingo de noviembre (13:30Z), si no 14:30Z."""
    y = dia.year
    mar = datetime(y, 3, 8, tzinfo=timezone.utc)
    ini = mar.replace(day=8 + (6 - mar.weekday()) % 7)
    nov = datetime(y, 11, 1, tzinfo=timezone.utc)
    fin = nov.replace(day=1 + (6 - nov.weekday()) % 7)
    d = dia.replace(hour=12, minute=0, second=0, microsecond=0)
    return 13 * 60 + 30 if ini <= d < fin else 14 * 60 + 30
