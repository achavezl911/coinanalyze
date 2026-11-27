"""SEGUIMIENTO R2: con una posicion abierta en Bybit, el bot sigue SU activo y avisa con la especificacion MEDIDA de Fable I18.

I18 (entregas/fable/fable-i18, 08-18..11-26, dos mitades y nulo emparejado): ninguna senal da DIRECCION (el retorno a 15 min
no se separa del nulo); casi todas anuncian MAS MOVIMIENTO en 15 min (x1.3-2.4); el precio NO respeta ningun nivel mas que
una linea al azar. Por eso los textos dicen «sin lado medido» y nunca «soporte» ni «resistencia». AVISOS R1 (Fable v6, H2):
tampoco «A FAVOR / EN CONTRA de tu LARGO|CORTO»: I18 midio ese lado NULO. El estado del OI («entran largos») se queda:
dice quien entra, no adonde va el precio.

AVISAN (la TABLA de I18): LIQ, GRA (perpetuo), OI, RUPTURA de ayer / 24 h / 7 dias y DIV. SOLO REGISTRO (journal, nunca al
dueno): ABS (absorcion), GRA_CONT (grandes de contado) y RNG4 (ruptura del rango de 4 h). El nivel CERCA (<= 0.5 ATR) es una
linea de contexto dentro del mensaje, nunca un aviso. Antiruido de I18: aviso = el estado pasa de NO a SI y han pasado >= 30
min del anterior del mismo activo, senal y lado (ruptura: 60 min por nivel y sentido). AVISOS R1 (H4): un aviso sale en el
tic en que nace; si su activo tuvo mensaje hace menos de 10 min, espera a cumplirlos y se junta con lo que coincida (antes,
30 min: un aviso podia esperar 29 y su efecto medido dura 15). Percentiles sobre los 30 d anteriores (grandes: 10 d), fijados a las 00:00Z.

Trampas de los datos (I18, REGLAS COMUNES): liquidations y open_interest de 5 min llevan el ts de APERTURA (el bloque se
conoce 5 min despues; sin fila = 0); oi_close va en USD, asi que el cambio se mide NETO del precio; spot_trades_agg y
futures_trades_agg traen un exchange `combined` = binance + bybit que no se suma con los demas.

Lee la base de 140 que el bot ya lee, SOLO lectura. Aproximaciones: el delta de 5 min va por bloques alineados (I18 lo
mide al cierre de cada minuto) y el tramo viejo del nivel de 7 d se relee cada hora (puede incluir hasta 59 min de mas).
BOT_SEGUIMIENTO=apagado|sombra|enviar, por defecto sombra.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

MODOS = ("apagado", "sombra", "enviar")

# ---------- la especificacion de Fable I18 (TABLA DE ESPECIFICACION) ----------
LIQ_Q = 0.995  # LIQ: USD liquidados de un lado en el bloque de 5 min >= p99.5 de los bloques de 30 d (sin fila = 0)
GRA_Q = 0.999  # GRA: USD de grandes de perpetuo (venues sin _spot) de un lado en 1 min >= p99.9 de TODOS los minutos de 10 d
OI_Q = 0.99  # OI: |dOI| >= p99 de 30 d, dOI = dln(oi_close) - dln(precio) del bloque de 5 min
DIV_Q = 0.90  # DIV: delta de 5 min de contado y de perpetuo con signos opuestos, cada uno >= su p90 de 30 d
ABS_Q = 0.95  # ABS (solo registro): |delta de 5 min| >= p95 de 30 d ...
ABS_QUIETO_ATR = 0.1  # ... y signo(delta) x (cierre - cierre de hace 5 min) <= 0.1 ATR
RUPTURA_ATR = 0.25  # cierre de vela de 5 min mas alla del nivel + 0.25 ATR, sin cierre asi en los 15 min previos
CERCA_ATR = 0.5  # linea de contexto
MISMO_NIVEL_ATR = 0.25  # dos niveles a menos de esto son el mismo: se nombra el mas ancho (7 dias, 24 h, ayer)
ATR_VELAS, ATR_MIN = 14, 15  # ATR = 14 velas de 15 min cerradas
DIAS, DIAS_GRA = 30, 10
ENFRIA_MIN, ENFRIA_RUPTURA_MIN = 30, 60
MENSAJE_MIN = 10  # un mensaje por activo cada 10 min como mucho: el retraso maximo de un aviso (AVISOS R1, H4)
VELAS_LEIDAS = 1500  # 24 h + la hora que el nivel de 24 h deja fuera + el ATR
AVISAN = ("LIQ", "GRA", "OI", "RUPTURA", "DIV")
NIVELES = ("7 dias", "24 h", "ayer")  # del mas ancho al mas estrecho

SQL_VELAS = """
SELECT (extract(epoch FROM ts)::bigint / 60)::int, high, low, close, buy_volume, volume
  FROM ohlcv
 WHERE interval = '1min' AND symbol = $1
   AND ts >= to_timestamp($2::bigint * 60) AND ts < to_timestamp($3::bigint * 60)
 ORDER BY ts
"""
SQL_RANGO = """
SELECT max(high), min(low)
  FROM ohlcv
 WHERE interval = '1min' AND symbol = $1
   AND ts >= to_timestamp($2::bigint * 60) AND ts < to_timestamp($3::bigint * 60)
"""
SQL_CIERRES5 = """
SELECT (extract(epoch FROM ts)::bigint / 60)::int, close
  FROM ohlcv
 WHERE interval = '1min' AND symbol = $1
   AND ts >= to_timestamp($2::bigint * 60) AND ts < to_timestamp($3::bigint * 60)
   AND extract(epoch FROM ts)::bigint / 60 % 5 = 4
"""
SQL_DELTA_OHLCV = """
SELECT (extract(epoch FROM ts)::bigint / 300 * 5)::int, sum((2 * buy_volume - volume) * close)
  FROM ohlcv
 WHERE interval = '1min' AND symbol = $1
   AND ts >= to_timestamp($2::bigint * 60) AND ts < to_timestamp($3::bigint * 60)
 GROUP BY 1
"""
SQL_LIQ5 = """
SELECT (extract(epoch FROM ts)::bigint / 60)::int, long_liq, short_liq
  FROM liquidations
 WHERE interval = '5min' AND symbol = $1
   AND ts >= to_timestamp($2::bigint * 60) AND ts < to_timestamp($3::bigint * 60)
"""
SQL_OI = """
SELECT (extract(epoch FROM ts)::bigint / 60)::int, oi_close
  FROM open_interest
 WHERE interval = '5min' AND symbol = $1
   AND ts >= to_timestamp($2::bigint * 60) AND ts < to_timestamp($3::bigint * 60)
"""
SQL_GRANDES = """
SELECT (extract(epoch FROM ts)::bigint / 60)::int, venue, compra, usd::float8
  FROM orderflow_grande
 WHERE symbol = $1
   AND ts >= to_timestamp($2::bigint * 60) AND ts < to_timestamp($3::bigint * 60)
"""
SQL_GRANDES_COLA = """
SELECT (extract(epoch FROM ts)::bigint / 60)::int, compra, sum(usd)::float8
  FROM orderflow_grande
 WHERE symbol = $1 AND right(venue, 5) <> '_spot'
   AND ts >= to_timestamp($2::bigint * 60) AND ts < to_timestamp($3::bigint * 60)
 GROUP BY 1, 2
"""
# por bloque de 5 min y exchange: el `combined` se descarta en Python (_por_bloque), donde lo ve la prueba
SQL_FLUJO_PERP = """
SELECT (extract(epoch FROM ts)::bigint / 300 * 5)::int, exchange, sum(buy_vol_usd - sell_vol_usd)
  FROM futures_trades_agg
 WHERE interval = '1min' AND symbol = $1
   AND ts >= to_timestamp($2::bigint * 60) AND ts < to_timestamp($3::bigint * 60)
 GROUP BY 1, 2
"""
SQL_FLUJO_CONT = """
SELECT (extract(epoch FROM ts)::bigint / 300 * 5)::int, exchange, sum(buy_vol_usd - sell_vol_usd)
  FROM spot_trades_agg
 WHERE interval = '1min' AND symbol = $1
   AND ts >= to_timestamp($2::bigint * 60) AND ts < to_timestamp($3::bigint * 60)
 GROUP BY 1, 2
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
    """El estado (va a bot_estado): SI/NO de cada senal, el ultimo aviso de cada una, lo que espera al mensaje de su activo
    ([t, senal, texto, lado]), la hora del ultimo mensaje por activo y los mensajes de 24 h ([t, enviado, «LIQ+OI»])."""
    return {"vivo": {}, "enfria": {}, "pend": {}, "msg_t": {}, "avisos": []}


def restaura(g) -> dict | None:
    """Lo guardado, si se entiende; si no, None (se empieza de cero). Lo de R1 se entiende a medias: solo sus avisos."""
    if not isinstance(g, dict):
        return None
    num = (int, float)
    d = {k: x if isinstance(x := g.get(k), dict) else {} for k in ("vivo", "enfria", "pend", "msg_t")}
    return {"vivo": {str(k): v for k, v in d["vivo"].items() if isinstance(v, bool)},
            "enfria": {str(k): float(v) for k, v in d["enfria"].items() if isinstance(v, num)},
            "pend": {str(a): [list(x) for x in v if isinstance(x, list) and len(x) == 4] for a, v in d["pend"].items()
                     if isinstance(v, list)},
            "msg_t": {str(a): float(v) for a, v in d["msg_t"].items() if isinstance(v, num)},
            "avisos": [list(x) for x in g.get("avisos") or [] if isinstance(x, list) and len(x) == 3 and isinstance(x[0], num)]}


def cuenta(estado: dict, ahora_s: float, senales: list, enviado: bool):
    estado["avisos"] = [x for x in estado["avisos"] if ahora_s - x[0] < 86400] + [[ahora_s, enviado, "+".join(senales)]]


def por_senal(avisos: list) -> dict:
    """Cuantas veces entro cada senal en un mensaje (para /estado)."""
    n: dict = {}
    for x in avisos:
        for s in str(x[2]).split("+"):
            n[s] = n.get(s, 0) + 1
    return n


# ---------- lectura ----------
def _pctl(xs: list, q: float) -> float:
    """El percentil q; sin historia, infinito (no se avisa de nada que no se pueda comparar)."""
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else math.inf


def _pctl0(xs: list, n: int, q: float) -> float:
    """El percentil q de n casillas donde las que faltan valen 0 (bloque o minuto sin fila)."""
    xs = [x for x in xs if x > 0]
    if not xs:
        return math.inf
    xs = [0.0] * max(0, n - len(xs)) + sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))]


def _por_bloque(filas) -> dict:
    """{bloque: delta} sumando los exchanges SIN `combined` (= binance + bybit: sumarlo cuenta doble)."""
    out: dict = {}
    for b, ex, x in filas:
        if ex != "combined":
            out[int(b)] = out.get(int(b), 0.0) + float(x)
    return out


def _doi(oi: dict, px: dict, b: int) -> tuple[float, float] | None:
    """(dOI, dln precio) del bloque que abre en b: oi_close de b frente al de b-5 y el cierre del minuto b+4 frente al b-1."""
    xs = (oi.get(b), oi.get(b - 5), px.get(b + 4), px.get(b - 1))
    if not all(xs):
        return None
    dp = math.log(xs[2] / xs[3])
    return math.log(xs[0] / xs[1]) - dp, dp


def _rng(filas) -> tuple:
    return tuple(filas[0]) if filas else (None, None)


async def _colas(db, activo: str, sym: str, dia: int) -> dict:
    a30, n5 = dia - DIAS * 1440, DIAS * 288
    liq = await db.fetch(SQL_LIQ5, sym, a30, dia)
    gra = await db.fetch(SQL_GRANDES_COLA, activo, dia - DIAS_GRA * 1440, dia)
    oi = {int(m): float(x) for m, x in await db.fetch(SQL_OI, sym, a30, dia)}
    px = {int(m): float(x) for m, x in await db.fetch(SQL_CIERRES5, sym, a30, dia)}
    doi = [abs(r[0]) for b in oi if (r := _doi(oi, px, b))]
    perp = _por_bloque(await db.fetch(SQL_FLUJO_PERP, sym, a30, dia))
    cont = _por_bloque(await db.fetch(SQL_FLUJO_CONT, activo, a30, dia))
    ohl = [abs(float(x)) for _, x in await db.fetch(SQL_DELTA_OHLCV, sym, a30, dia)]
    return {"liq": {"long": _pctl0([float(r[1]) for r in liq], n5, LIQ_Q), "short": _pctl0([float(r[2]) for r in liq], n5, LIQ_Q)},
            "gra": {c: _pctl0([float(s) for _, cc, s in gra if bool(cc) is c], DIAS_GRA * 1440, GRA_Q) for c in (True, False)},
            "oi": _pctl(doi, OI_Q),
            "div_perp": _pctl([abs(x) for x in perp.values()], DIV_Q), "div_cont": _pctl([abs(x) for x in cont.values()], DIV_Q),
            "abs_perp": _pctl(ohl, ABS_Q), "abs_cont": _pctl([abs(x) for x in cont.values()], ABS_Q)}


async def lee(db, activo: str, ahora: int, cache: dict) -> dict:
    """Las colas y el nivel de ayer se fijan a las 00:00Z; el tramo viejo del nivel de 7 d, cada hora; lo vivo, cada minuto.
    b = el ultimo bloque de 5 min CERRADO (ts de apertura: [b, b + 5) se conoce a b + 5)."""
    sym, c = f"{activo}USDT_PERP.A", cache.setdefault(activo, {})
    dia, h, b = ahora // 1440 * 1440, ahora // 60 * 60, ahora // 5 * 5 - 5
    if c.get("dia") != dia:
        c.update(dia=dia, colas=await _colas(db, activo, sym, dia), ayer=_rng(await db.fetch(SQL_RANGO, sym, dia - 1440, dia)))
    if c.get("h") != h:
        c.update(h=h, viejo7=_rng(await db.fetch(SQL_RANGO, sym, h - 7 * 1440, h - 1440)))
    return c | {"b": b, "velas": await db.fetch(SQL_VELAS, sym, ahora - VELAS_LEIDAS, ahora),
                "liq": await db.fetch(SQL_LIQ5, sym, b, b + 5), "oi": await db.fetch(SQL_OI, sym, b - 5, b + 5),
                "grandes": await db.fetch(SQL_GRANDES, activo, ahora - 1, ahora),
                "perp": await db.fetch(SQL_FLUJO_PERP, sym, b, b + 5), "cont": await db.fetch(SQL_FLUJO_CONT, activo, b, b + 5)}


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


def _atr(v: dict, i: int) -> float:
    """La media del rango verdadero de las 14 velas de 15 min cerradas antes del minuto i."""
    fin, trs = i // ATR_MIN * ATR_MIN, []
    for t in range(fin - ATR_MIN * ATR_VELAS, fin, ATR_MIN):
        if t - 1 not in v or t + ATR_MIN - 1 not in v:
            return 0.0
        ms, pc = [v[m] for m in range(t, t + ATR_MIN)], v[t - 1][2]
        trs.append(max(pc, *(x[0] for x in ms)) - min(pc, *(x[1] for x in ms)))
    return sum(trs) / len(trs)


def _c(sen: str, clave: str, on: bool, lado: int | None, texto: str, registro: bool = False, enfria: int = ENFRIA_MIN):
    return {"senal": sen, "clave": clave, "valor": bool(on), "lado": lado, "texto": texto, "registro": registro, "enfria": enfria}


# ---------- senales ----------
def senales(d: dict, activo: str, ahora: int) -> tuple[list[dict], list[str]]:
    """(candidatos, lineas de contexto). Un candidato: {senal, clave, valor (SI/NO), lado, texto (dos lineas con « / »),
    registro (True: solo journal), enfria (min)}."""
    out, ctx, co, b = [], [], d["colas"], d["b"]
    # LIQ: el bloque [b, b + 5) por lado (sin fila = 0)
    fila = next((r for r in d["liq"] if int(r[0]) == b), None)
    for lado_liq, i, nombre, lado in (("long", 1, "largos", -1), ("short", 2, "cortos", 1)):
        x = float(fila[i]) if fila else 0.0
        out.append(_c("LIQ", f"LIQ|{lado_liq}", x > 0 and x >= co["liq"][lado_liq], lado,
                      f"{activo}: {x / 1e6:.2f} M$ de {nombre} liquidados en 5 min, mas que el {LIQ_Q * 100:g} % de los bloques"
                      " del ultimo mes. / Tras algo asi el precio se ha movido en 15 min casi el doble de lo normal; sin lado medido."))
    # GRA: grandes de perpetuo del minuto cerrado, por lado; los de contado, solo registro
    perp, cont = {True: 0.0, False: 0.0}, {True: [0.0, 0], False: [0.0, 0]}
    for _, venue, compra, usd in d["grandes"]:
        if str(venue).endswith("_spot"):
            cont[bool(compra)][0] += float(usd)
            cont[bool(compra)][1] += 1
        else:
            perp[bool(compra)] += float(usd)
    for compra in (True, False):
        x, que = perp[compra], "compra" if compra else "venta"
        out.append(_c("GRA", f"GRA|{int(compra)}", x > 0 and x >= co["gra"][compra], 1 if compra else -1,
                      f"{activo}: {x / 1e6:.2f} M$ de {que} agresiva en operaciones grandes de perpetuo en 1 min, de los minutos"
                      " mas cargados de 10 dias. / Dice quien empuja ahora; despues hay mas movimiento del normal, sin lado medido."))
        usd, n = cont[compra]
        out.append(_c("GRA_CONT", f"GRA_CONT|{int(compra)}", n > 0, 1 if compra else -1,
                      f"{activo}: {n} operaciones grandes de {que} de contado en 1 min ({usd / 1e6:.2f} M$)", registro=True))
    # DIV: contado y perpetuo del bloque, sin `combined`
    dc, dpp = _por_bloque(d["cont"]).get(b, 0.0), _por_bloque(d["perp"]).get(b, 0.0)
    out.append(_c("DIV", "DIV", dc * dpp < 0 and abs(dc) >= co["div_cont"] and abs(dpp) >= co["div_perp"], None,
                  f"{activo}: el contado {'compra' if dc > 0 else 'vende'} {abs(dc) / 1e6:.2f} M$ en 5 min y el perpetuo hace lo"
                  f" contrario ({abs(dpp) / 1e6:.2f} M$). / Los dos mercados tiran en sentidos opuestos; despues hay algo mas de"
                  " movimiento, sin lado medido."))
    s = _serie(d["velas"])
    if s is None or ahora - s[1] > 3 or s[1] < b + 4:  # sin velas frescas no se juzga el precio (el centinela avisa del retraso)
        return out, ctx
    v, u = s
    i = b + 5  # el cierre del bloque
    atr = _atr(v, i)
    if atr <= 0 or b - 16 not in v:
        return out, ctx
    c5 = {k: v[k + 4][2] for k in range(b - 15, b + 1, 5)}
    # OI: neto del precio; el estado sale del signo de dOI y del precio
    oi = {int(m): float(x) for m, x in d["oi"]}
    r = _doi(oi, {m: x[2] for m, x in v.items()}, b)
    if r:
        doi, dp = r
        clase, lado = {(1, 1): ("entran largos", 1), (1, -1): ("entran cortos", -1), (-1, 1): ("salen cortos", 1),
                       (-1, -1): ("salen largos", -1)}.get((1 if doi > 0 else -1, 1 if dp > 0 else -1 if dp < 0 else 0), ("", 0))
        out.append(_c("OI", f"OI|{lado}", bool(lado) and abs(doi) >= co["oi"], lado,
                      f"{activo}: el interes abierto {'sube' if doi > 0 else 'baja'} {abs(doi) * 100:.2f} % en 5 min (neto del"
                      f" precio) con el precio {'subiendo' if dp > 0 else 'bajando'}: {clase}. / Cambio de los mayores del mes;"
                      " despues hay mas movimiento del normal, sin lado medido."))
    # ABS (solo registro): perpetuo (ohlcv) y contado (sin combined), con el precio que no sigue al delta
    mov = c5[b] - v[b - 1][2]
    dperp = sum((2 * v[m][3] - v[m][4]) * v[m][2] for m in range(b, b + 5))
    for mercado, dl, um in (("perpetuo", dperp, co["abs_perp"]), ("contado", dc, co["abs_cont"])):
        sg = 1 if dl > 0 else -1
        out.append(_c("ABS", f"ABS|{mercado}|{sg}", dl != 0 and abs(dl) >= um and sg * mov <= ABS_QUIETO_ATR * atr, -sg,
                      f"{activo}: absorcion en {mercado}, delta {dl / 1e6:+.2f} M$ en 5 min y el precio {mov / atr:+.2f} ATR",
                      registro=True))
    # niveles: ayer (dia UTC anterior), 24 h = [i-1440, i-60), 7 dias = [i-10080, i-60); RNG4 = [i-240, i-30), solo registro
    h24 = [v[m] for m in range(i - 1440, i - 60) if m in v]
    hasta60 = [v[m] for m in v if m < i - 60]
    hi7, lo7 = d["viejo7"]
    lv = {"ayer": d["ayer"], "24 h": (max((x[0] for x in h24), default=None), min((x[1] for x in h24), default=None)),
          "7 dias": (max([x for x in (hi7, max((x[0] for x in hasta60), default=None)) if x is not None], default=None),
                     min([x for x in (lo7, min((x[1] for x in hasta60), default=None)) if x is not None], default=None))}
    r4 = [v[m] for m in range(i - 240, i - 30) if m in v]
    rng4 = (max(x[0] for x in r4), min(x[1] for x in r4)) if r4 else (None, None)
    c, mg = v[u][2], RUPTURA_ATR * atr
    for k, es_max in ((0, True), (1, False)):
        sg, vistos = 1 if es_max else -1, []
        for nombre in NIVELES + ("RNG4",):
            nivel = rng4[k] if nombre == "RNG4" else lv[nombre][k]
            if nivel is None:
                continue
            if nombre != "RNG4":
                if any(abs(float(nivel) - x) <= MISMO_NIVEL_ATR * atr for x in vistos):
                    continue
                vistos.append(nivel := float(nivel))
            fuera = [sg * (c5[x] - nivel) > mg for x in (b - 15, b - 10, b - 5)]
            dentro = [sg * (c5[x] - nivel) <= 0 for x in (b - 15, b - 10, b - 5)]
            rompe = sg * (c5[b] - nivel) > mg and not any(fuera) and any(dentro)
            que = "por encima del maximo" if es_max else "por debajo del minimo"
            dist = abs(c5[b] - nivel) / atr
            if nombre == "RNG4":
                out.append(_c("RNG4", f"RNG4|{sg}", rompe, sg, f"{activo}: cierre de 5 min {que} del rango de 4 h ({nivel:g}),"
                                                                f" a {dist:.2f} ATR", registro=True, enfria=ENFRIA_RUPTURA_MIN))
                continue
            out.append(_c("RUPTURA", f"RUPTURA|{nombre}|{sg}", rompe, sg,
                          f"{activo}: cierre de 5 min {que} de {nombre} ({nivel:g}), a {dist:.2f} ATR. / Casi la mitad de estas"
                          " rupturas vuelve a cerrar dentro en 15 min; sin lado medido.", enfria=ENFRIA_RUPTURA_MIN))
            cerca = sg * (nivel - c) / atr
            if 0 <= cerca <= CERCA_ATR:
                ctx.append(f"{'Maximo' if es_max else 'Minimo'} de {nombre} en {nivel:g}, a {cerca:.2f} ATR.")
    return out, ctx


# ---------- antiruido y mensaje ----------
def _decide(cand: dict, estado: dict, ahora_s: float, activo: str) -> bool:
    """I18: aviso = el estado pasa de NO a SI y han pasado >= `enfria` min del anterior del mismo activo, senal y lado."""
    k = f"{activo}|{cand['clave']}"
    prev, estado["vivo"][k] = estado["vivo"].get(k, False), cand["valor"]
    if not cand["valor"] or prev or ahora_s - estado["enfria"].get(k, -math.inf) < cand["enfria"] * 60:
        return False
    estado["enfria"][k] = ahora_s
    return True


def _r(p: dict) -> float | None:
    e, s, m, lado = p.get("entrada"), p.get("stop"), p.get("marca"), p.get("lado")
    if not (e and s and m and lado) or (e - s) * lado <= 0:
        return None
    return (m - e) * lado / abs(e - s)


def _mensaje(activo: str, p: dict, pend: list, ctx: list) -> str:
    pos, r = "LARGO" if p["lado"] > 0 else "CORTO", _r(p)
    lineas = [f"{activo} · seguimiento de tu {pos}" + (f" ({r:+.2f} R)" if r is not None else "")]
    for t, _, texto, _lado in pend:  # el lado de la senal NO se dice (AVISOS R1, H2): I18 lo midio nulo
        uno, _, dos = texto.partition(" / ")
        lineas += [f"{int(t // 60) // 60 % 24:02d}:{int(t // 60) % 60:02d}Z {uno}", f"  {dos}"]
    return "\n".join(lineas + [f"Contexto: {x}" for x in ctx])


async def tic(db, posiciones: list, estado: dict, cache: dict, ahora_s: float) -> list[dict]:
    """Lo de este minuto: [{tipo: «mensaje», activo, senales, texto}] (lo que iria al dueno) y [{tipo: «registro», senal,
    activo, texto}] (solo journal). Sin posicion abierta no se lee ni se calcula nada y lo de cada activo se olvida."""
    por_activo = {}
    for p in posiciones or []:
        sym = str(p.get("symbol") or "")
        if sym.endswith("USDT") and p.get("lado") in (1, -1):
            por_activo.setdefault(sym[:-4], p)
    for k in ("vivo", "enfria"):
        estado[k] = {x: y for x, y in estado[k].items() if x.split("|")[0] in por_activo}
    for k in ("pend", "msg_t"):
        estado[k] = {x: y for x, y in estado[k].items() if x in por_activo}
    ahora, out = int(ahora_s // 60), []
    for activo, p in por_activo.items():
        cands, ctx = senales(await lee(db, activo, ahora, cache), activo, ahora)
        for cand in cands:
            if not _decide(cand, estado, ahora_s, activo):
                continue
            if cand["registro"]:
                out.append({"tipo": "registro", "senal": cand["senal"], "activo": activo, "texto": cand["texto"]})
            else:
                estado["pend"].setdefault(activo, []).append([ahora_s, cand["senal"], cand["texto"], cand["lado"]])
        pend = estado["pend"].get(activo)
        if pend and ahora_s - estado["msg_t"].get(activo, -math.inf) >= MENSAJE_MIN * 60:
            out.append({"tipo": "mensaje", "activo": activo, "senales": [x[1] for x in pend], "texto": _mensaje(activo, p, pend, ctx)})
            estado["pend"][activo], estado["msg_t"][activo] = [], ahora_s
    return out
