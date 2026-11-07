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
import sys
from datetime import UTC, datetime
from pathlib import Path

# LA DEFINICION que la sombra del bot comparte (BOT-5) vive en app/anatomia.py: aqui se reexporta con su nombre de
# siempre (C.ESQUEMAS, C.etiqueta...). app/__init__.py no importa nada: el nodo solo necesita el arbol.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.anatomia import (  # noqa: E402,F401
    CAPA_B_DESDE,
    COLUMNAS_BASE,
    COMISION,
    ESQUEMAS,
    FUENTE_CINTA,
    FUENTE_FUTUROS,
    FUENTE_L1,
    GRANDE_1M,
    GRANDE_100K,
    HORIZONTE,
    LADOS,
    REJILLA,
    VENUE_PRIMA,
    VENUE_REF,
    VENUES_PERP,
    VENUES_SPOT,
    _ts,
    azar,
    empate,
    etiqueta,
    sin_solape,
)

# ---------------------------------------------------------------- universo
SIMBOLOS = ("BTC", "ETH", "SOL")
# ---------------------------------------------------------------- calendario (UTC)
ARCHIVO_DESDE = "2026-08-04"
CAPA_A_DESDE = _ts("2026-08-05")
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
# ---------------------------------------------------------------- umbrales de la extraccion
LIQ_GRANDE_USD = {"BTC": 250_000.0, "ETH": 100_000.0, "SOL": 50_000.0}   # «evento grande» de liquidacion
CASCADA_N, CASCADA_S, CASCADA_CALMA_S = 5, 60.0, 120.0                   # M8
LIBRO_BANDAS = (0.001, 0.005)       # desequilibrio a +-0.1 % y +-0.5 % del medio
MURO_DIST, MURO_VECES, MURO_QUEDA = 0.003, 5.0, 0.2   # M3: <= 0.3 %, >= 5x la mediana del lado, queda < 20 %

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
P_COLA_NORMAL = 10                  # p = (1 + k) / (1 + S), k = desplazamientos con tasa >= la observada. Si
                                    # k < 10, 2000 desplazamientos no resuelven p < 5e-4 y BH sobre miles de
                                    # celdas no puede pasar ninguna: entonces p = cola normal de z frente a la
                                    # media y la desviacion de los desplazamientos (decidido antes de medir).
P_COLA_DISTINTOS = 20               # REMATE 2: la cola normal SOLO si los desplazamientos dan >= 20 valores
                                    # distintos; si no (distribucion degenerada, muy asimetrica), p = (1 + k) /
                                    # (1 + S). Cada celda dice que via dio su p: p_via = "normal" o "conteo".
SEMILLA = 20261102
FDR_Q = 0.10                        # Benjamini-Hochberg sobre TODAS las celdas de una corrida
N_MIN_MECANISMO = 10                # n sin solape < 10 = SIN N
N_MIN_CONFIRMA = 30
WILSON_Z = 1.6448536269514722       # 90 % bilateral
MAX_CANDIDATAS, SOLO_MIRAR = 10, 5
RUIDOS = 10                         # columnas N(0,1) de control negativo, en cada corrida
# todo junto: HistGradientBoosting por lado y capa, simbolos juntos (el simbolo es una columna)
HGB = dict(learning_rate=0.05, max_iter=150, max_leaf_nodes=15, min_samples_leaf=200, l2_regularization=1.0)
HGB_TRAMOS, HGB_PURGA_MIN, HGB_BARAJADOS, HGB_MEJOR = 5, 240, 20, 0.05
# control positivo (--control): tras cada M1 largo, el precio sube EMPUJE en EMPUJE_MIN minutos y se queda;
# y una columna `oraculo` = exito largo E1 + N(0, ORACULO_RUIDO). Ve el estudio si: M1 largo E1 pasa FDR en algun
# simbolo, oraculo alto largo E1 pasa FDR en algun simbolo, y las celdas de ruido que pasan FDR no son mas que
# FDR_Q x todas las que pasan (los nulos conocidos se comportan como BH promete; «ninguna» fallaria por azar).
# Las celdas planteadas arrastran a las que comparten insumos con M1 (liquidaciones, retornos): eso no cuenta.
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


def p_desplazado(t0: float, st, S: int) -> tuple[float, str]:
    """p de una tasa observada t0 frente a las tasas desplazadas st (finitas), de S desplazamientos. Devuelve (p, via)."""
    k = int(sum(1 for v in st if v >= t0 - 1e-12))
    p, via = (1 + k) / (1 + S), "conteo"
    if k < P_COLA_NORMAL and len(set(float(v) for v in st)) >= P_COLA_DISTINTOS:
        m = sum(st) / len(st)
        sd = math.sqrt(sum((v - m) ** 2 for v in st) / len(st))
        if sd > 0:
            p, via = 0.5 * math.erfc((t0 - m) / sd / math.sqrt(2)), "normal"
    return p, via


def gana(tasa, neto, empate_, azar_=None) -> bool:
    """REMATE 2: PASA exige ademas el signo, sobre las operaciones SIN solape: tasa >= empate (y >= azar si se da)
    y neto > 0. Un q bajo con tasa bajo el empate o neto <= 0 es NO."""
    if tasa is None or neto is None or empate_ is None or not math.isfinite(neto):
        return False
    return tasa >= empate_ and neto > 0 and (azar_ is None or tasa >= azar_)


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
    mar = datetime(y, 3, 8, tzinfo=UTC)
    ini = mar.replace(day=8 + (6 - mar.weekday()) % 7)
    nov = datetime(y, 11, 1, tzinfo=UTC)
    fin = nov.replace(day=1 + (6 - nov.weekday()) % 7)
    d = dia.replace(hour=12, minute=0, second=0, microsecond=0)
    return 13 * 60 + 30 if ini <= d < fin else 14 * 60 + 30


# ================================================================ REMATE 1 · gestion y rangos (BOT-3e r1)
# Escrito y commiteado ANTES de medir nada. Lo usan `anatomia_gestion.py` y `anatomia_rangos.py` (143, numpy).
#
# GESTION. Entradas: GESTION_ENTRADAS y las candidatas de candidatas.json, por simbolo y lado, en la rejilla de 5 min
# con la capa del estudio; descubrimiento = salida antes de CORTE_DESCUBRIMIENTO.
# A MERCADO: entrada a la apertura de t+1 (taker), camino t+1..t+240, primer toque, si un minuto toca los dos gana el
# stop; sin toque, cierre de t+240. TAKER al entrar y al salir.
# MAE/MFE, sin solape a 240 min: MAE = mayor excursion en contra en t+1 .. el minuto que toca +MAE_OBJ (incluido), o
# t+240 si no toca; MFE = mayor a favor en t+1..t+240. p50 p75 p90 de las que tocan y de todas, % de la entrada.
# STOPS DEL MERCADO, solo con minutos <= t: «mecha» largo = min(l, t-14..t) * (1 - 0.1 %) (corto: max(h) * 1.001);
# distancia = |1 - stop / entrada|; si la entrada ya esta al otro lado del stop, no hay operacion. «atr05» / «atr1» =
# 0.5 / 1 x ATR 1 h = media de los 14 rangos verdaderos de las velas de 60 min que cierran en t, t-60, .. t-780
# (contra el cierre de la vela anterior), / c_t.
# LIMITE (sin mecanismo, capa A): niveles largos = min(l) de 1440 y de 10080 min hasta t y el minimo de la vela de
# 3 d y de 9 d ANTERIOR (como dist_min_3d / 9d); cortos, los maximos. Se ARMA en t si 0 <= c_t / nivel - 1 <= LIM_ARMA
# (corto: espejo). Limite = nivel * (1 - LIM_MAS_ALLA) (corto: 1 +). Se LLENA en el primer minuto f de t+1..t+240 con
# l_f <= limite * (1 - LIM_CRUCE) (corto: h_f >= limite * (1 + LIM_CRUCE)), al precio del limite: tocar sin cruzar
# no llena. Sin llenado, CADUCA (armada no llenada; no es operacion). Desde f la misma rejilla: en f solo cuenta el
# stop (no se sabe el orden dentro del minuto), despues f+1..f+240; sin toque, cierre de f+240. MAKER al entrar,
# TAKER al salir. Una orden a la vez por nivel, simbolo y lado (la siguiente, cuando la anterior caduca o sale).
# EMPATE de una celda = empate_g(stop, objetivo, entrada, salida), con el stop medio de sus operaciones si el stop es
# del mercado; AZAR = stop / (objetivo + stop).
# p: desplazamiento circular como el estudio (DESPLAZAMIENTOS, DESPL_MIN_MIN, P_COLA_NORMAL) de la mascara de entrada
# contra el exito de TODAS las decisiones validas con la misma regla de salida. LIMITE: el exito de todas las
# decisiones es el de una orden fija a la distancia mediana (c_t -> limite) de las armadas de la celda bajo c_t; la
# tasa observada, aciertos / llenadas de las ordenes del nivel; la de un desplazamiento, aciertos / llenadas de la
# orden fija. BH (FDR_Q) sobre TODAS las celdas de gestion de la corrida.
# PASA (REMATE 2) = q <= FDR_Q Y n >= N_MIN_CONFIRMA Y gana(): tasa >= empate y neto > 0 sobre las operaciones SIN
# solape. Si falta el signo, NO. Mismo hueco en el estudio: alli gana() con empate(esquema) y azar_tasa.
# LA MEJOR = entre celdas con n >= N_MIN_CONFIRMA, mayor tasa - empate (empate a eso: menor q). NO es un resultado:
# va a congeladas.json con su definicion exacta; solo vale su --confirma en dias >= la fecha, con veredicto_con.
GESTION_ENTRADAS = (("M1", "A"), ("M1e", "A"), ("M1", "B"), ("M1e", "B"), ("M2", "B"), ("M2e", "B"),
                    ("M8", "B"), ("M8e", "B"))
MAE_OBJ = 0.01
G_STOPS = (0.004, 0.006, 0.008, 0.010, 0.015, 0.020)
G_OBJETIVOS = (0.01, 0.015, 0.02, 0.03)
STOP_MECHA_MIN, STOP_MECHA_MARGEN = 15, 0.001
STOP_ATR = {"atr05": 0.5, "atr1": 1.0}
ATR1H_VELAS = 14
TAKER, MAKER = COMISION, 0.0002     # 5.5 y 2 bps por lado
LIM_NIVELES = ("24h", "sem", "3d", "9d")
LIM_ARMA, LIM_MAS_ALLA, LIM_CRUCE, LIM_CADUCA = 0.005, 0.0005, 0.0001, 240
# CUENTA, celdas con n >= N_MIN_CONFIRMA: R = neto / (stop de la operacion + comision de ida y vuelta). Remuestreo
# por SEMANAS (ts // 604800): semanas con reemplazo, sus operaciones en orden, hasta CUENTA_OPS; CUENTA_CAMINOS
# caminos, semilla SEMILLA; riesgo fijo f: cuenta *= 1 + f * R. Da: neto medio en R, suma de R por camino (mediana),
# peor racha de perdidas (historia; p90 de caminos), caida maxima (mediana, p90) y P(cuenta <= CUENTA_RUINA).
# APALANCAMIENTO: nocional = APAL_RIESGO / (stop + ida y vuelta); apal = nocional / APAL_MARGEN; liquidacion = 1 /
# apal - APAL_MANT (fraccion en contra). NO_CABE si liquidacion < stop + APAL_COLCHON. Se cuentan las operaciones
# cuya excursion en contra hasta su salida llega a la liquidacion. No cambia ninguna etiqueta: solo el nocional.
CUENTA_RIESGOS = (0.01, 0.02, 0.05, 0.10)
CUENTA_CAMINOS, CUENTA_OPS, CUENTA_RUINA = 5000, 100, 0.5
APAL_MARGEN, APAL_RIESGO, APAL_MANT, APAL_COLCHON = 10.0, 3.55, 0.005, 0.003

# RANGOS (anatomia_rangos.py, HIST = historia-bot). Barras de 1 h UTC del perpetuo de 1 min: o h l c, qv, delta =
# 2 qb - qv (perp y spot), oi (sum_open_interest) y top (sum_toptrader_long_short_ratio): ultimo valor de la hora.
# AJUSTE: rangos que cumplen y acaban antes de RANGO_CORTE; PRUEBA: cumplen desde RANGO_CORTE. ATR diario = media de
# los rangos verdaderos de los 14 dias UTC completos anteriores al de la barra.
# RANGO en la barra cerrada k, ventana k-W+1..k: alto = max h, bajo = min l, altura <= RANGO_ATR x ATR diario; toques
# altos = barras con h >= alto - RANGO_BANDA x altura (bajos: l <= bajo + banda x altura), dos de cada lado con
# ultimo - primero >= RANGO_SEP barras; y bajo <= c_k <= alto. Se prueba la W mas larga primero; un rango ACTIVO
# bloquea los demas hasta que acaba (quedarse a posteriori con la W larga usaria el futuro del corto: «solape» = en
# el mismo instante).
# FINAL, barras k+1..k+24*RANGO_DIAS: SALE si un cierre queda fuera por >= RANGO_FUERA alturas; si ningun cierre de
# las RANGO_VUELTA barras siguientes vuelve a [bajo, alto], es definitiva y el rango acaba ahi; si vuelve, esa salida
# fue FALSA y se sigue hasta la definitiva (lado_final). Sin definitiva en 7 d: SIN SALIDA (acaba a los 7 d).
# Clase = ARRIBA / ABAJO (la primera salida es la definitiva), FALSA o SIN SALIDA. Y si llega a 1 altura mas alla.
# ESTADO en k, solo barras <= k: dp_bajo, dp_alto (delta perp de las horas de la ventana cuyo cierre cae en el
# tercio bajo / alto, / qv de la ventana), ds_bajo, ds_alto (spot), d_oi (oi_k / oi_{k-W+1} - 1), posicion
# ((c - bajo) / altura), compresion (altura de la ultima mitad / de la primera), toques_alto, toques_bajo (grupos
# separados >= RANGO_SEP), tend_30d (c_k / c_{k-720} - 1), top, ruido (U(0,1), control negativo).
# CELDA = simbolo x estado x tercil (cortes del AJUSTE del simbolo) x lado (lado_final ARRIBA / ABAJO): n, % de cada
# clase, exitos, Wilson 90 % inferior, p = P(X >= exitos | n, 0.5). n < N_MIN_CONFIRMA = SIN CALIBRAR. BH sobre las
# celdas del AJUSTE. PASA: q <= FDR_Q y Wilson > 0.5 en ajuste y en prueba; CONTEXTO: Wilson > 0.5 en uno; RUIDO.
# CONTROL (--control): `planta` U(0,1); un rango con planta > 2/3 recibe en las 24 h siguientes RANGO_PLANTA alturas
# al alza que se quedan. Ve si planta tercil 2 ARRIBA PASA en algun simbolo y ninguna celda de ruido PASA.
RANGO_W = (240, 120, 72)
RANGO_ATR, RANGO_BANDA, RANGO_SEP = 2.0, 0.15, 6
RANGO_DIAS, RANGO_FUERA, RANGO_VUELTA = 7, 0.25, 24
RANGO_ATR_DIAS, RANGO_CORTE, RANGO_PLANTA = 14, "2024-01-01", 1.5


def empate_g(stop: float, objetivo: float, entrada: float = TAKER, salida: float = TAKER) -> float:
    """(stop + 0.11 %) / (objetivo + stop) a mercado; (stop + 0.075 %) / (objetivo + stop) con limite."""
    return (stop + entrada + salida) / (objetivo + stop)


def veredicto_con(exitos: int, n: int, empate_: float, azar_: float) -> str:
    """La regla de veredicto_confirma con el empate y el azar de la celda."""
    if n < N_MIN_CONFIRMA:
        return "SIN N"
    w = wilson_inferior(exitos, n)
    return "CONFIRMA" if w > empate_ else ("CONTEXTO" if w > azar_ else "RUIDO")
