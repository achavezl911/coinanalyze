"""Veredicto de estructura sobre una VENTANA ELEGIDA, con su ventana de control.

POR QUE EXISTE. La mesa contesta «que pasa AHORA». Alejandro pregunto «que paso ENTRE ESTOS DOS
INSTANTES» -viernes 03:30 y ahora- y no habia donde escribir esa ventana: de las once rutas
estructurales, siete toman solo `symbol` y cuatro toman un RETROCESO (`days`, `limit`), que es
«hacia atras desde ahora» y no un rango. **Cero aceptan desde/hasta.**

LOS CRITERIOS NO SE INVENTAN AQUI. Son las cinco pruebas que `app/wyckoff.py` ya usa -`cvd_spot`,
`delta_futuros`, `volumen_precio`, `progreso_precio`, `spring_upthrust`- y la regla que esta casa
aprendio y escribio en el README:255-262: un panel etiquetado «Acumulacion / distribucion»
clasificaba por el signo del DIFERENCIAL, y «una sesion con spot vendiendo salia como acumulacion
siempre que los futuros vendieran mas (36 sesiones asi solo en BTC)». La correccion fue clasificar
por el signo de **ambas patas**. Aqui se hereda esa leccion.

LO QUE ESTA CASA NO SABIA NOMBRAR, y por eso se anade una categoria. El vocabulario existente es
`compatible_con_acumulacion` / `compatible_con_distribucion` / `equilibrio_sin_ventaja`. Los tres
suponen que el papel CAMBIA DE MANOS: alguien compra lo que otro vende, y el interes abierto
AGUANTA. Cuando el interes abierto CAE con el precio, no hay traspaso: hay posiciones que se
cierran. Eso no es acumulacion ni distribucion, y forzarlo a una de las dos seria el mismo error
del README. Se nombra **`desapalancamiento`** y se defiende con su prueba: la caida de OI.

NO ES PREDICCION. Es lectura de lo que YA paso. No hay regla de entrada, ni puntuacion, ni
«probabilidad de que continue»: esta medido que la señal no anticipa, y un veredicto de rango que
insinuara direccion futura seria una afirmacion nueva sin una sola medida detras.

CADA PRUEBA DICE SU LADO Y SU CIFRA, y las que no se pueden medir NO VOTAN y se declaran. El
veredicto es legible como cuenta -«4 de 6 votan X»- y no como un numero magico: un peso que no
sale de una medida es un peso inventado.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg

# El tramo «ballena» de spot NO VOTA, y esto no es una omision: esta medido. Ver `whale_no_mide`.
BALLENA_NO_MEDIBLE = (
    "el tramo institucional de spot esta a cero en 0 de 20 116 minutos de BTC porque su umbral "
    "-5 000 000 USD por OPERACION SUELTA, `whale_threshold_usd`- nunca se alcanza en spot. "
    "No es que no haya manos grandes: es que no se pueden ver con este umbral. NO VOTA."
)


async def _escalar(conn: asyncpg.Connection, sql: str, *args) -> float | None:
    v = await conn.fetchval(sql, *args)
    return float(v) if v is not None else None


async def _ventana(conn: asyncpg.Connection, symbol: str, base: str, a: datetime, b: datetime) -> dict[str, Any]:
    """Las cifras crudas de una ventana. Cada una con su DENOMINADOR: sin el, un cero puede ser
    «no paso nada» o «no habia con que mirar», y esta casa lleva doce vueltas separando eso."""
    fila = await conn.fetchrow(
        """
        SELECT
          (SELECT count(*) FROM ohlcv WHERE symbol=$1 AND interval='1min' AND ts>=$3 AND ts<$4) AS velas,
          (SELECT open  FROM ohlcv WHERE symbol=$1 AND interval='1min' AND ts>=$3 AND ts<$4 ORDER BY ts LIMIT 1) AS px_ini,
          (SELECT close FROM ohlcv WHERE symbol=$1 AND interval='1min' AND ts>=$3 AND ts<$4 ORDER BY ts DESC LIMIT 1) AS px_fin,
          (SELECT sum(buy_vol_usd-sell_vol_usd) FROM spot_trades_agg
            WHERE symbol=$2 AND interval='1min' AND exchange<>'combined' AND ts>=$3 AND ts<$4) AS cvd_spot,
          (SELECT count(*) FROM spot_trades_agg
            WHERE symbol=$2 AND interval='1min' AND exchange<>'combined' AND ts>=$3 AND ts<$4) AS n_spot,
          (SELECT sum(inst_buy_usd+inst_sell_usd) FROM spot_trades_agg
            WHERE symbol=$2 AND interval='1min' AND exchange<>'combined' AND ts>=$3 AND ts<$4) AS ballena,
          (SELECT oi_close FROM open_interest WHERE symbol=$1 AND interval='5min' AND ts>=$3 AND ts<$4 ORDER BY ts LIMIT 1) AS oi_ini,
          (SELECT oi_close FROM open_interest WHERE symbol=$1 AND interval='5min' AND ts>=$3 AND ts<$4 ORDER BY ts DESC LIMIT 1) AS oi_fin,
          (SELECT count(*) FROM open_interest WHERE symbol=$1 AND interval='5min' AND ts>=$3 AND ts<$4) AS n_oi,
          (SELECT avg(fr_close) FROM funding_rate WHERE symbol=$1 AND interval='5min' AND ts>=$3 AND ts<$4) AS funding,
          (SELECT count(*) FROM funding_rate WHERE symbol=$1 AND interval='5min' AND ts>=$3 AND ts<$4) AS n_fund,
          (SELECT sum(long_liq)  FROM liquidations WHERE symbol=$1 AND interval='5min' AND ts>=$3 AND ts<$4) AS liq_long,
          (SELECT sum(short_liq) FROM liquidations WHERE symbol=$1 AND interval='5min' AND ts>=$3 AND ts<$4) AS liq_short,
          (SELECT count(*) FROM liquidations WHERE symbol=$1 AND interval='5min' AND ts>=$3 AND ts<$4) AS n_liq
        """,
        symbol, base, a, b,
    )
    d = dict(fila) if fila else {}
    def f(k):
        v = d.get(k)
        return float(v) if v is not None else None
    px_i, px_f = f("px_ini"), f("px_fin")
    oi_i, oi_f = f("oi_ini"), f("oi_fin")
    return {
        "desde": a.isoformat().replace("+00:00", "Z"),
        "hasta": b.isoformat().replace("+00:00", "Z"),
        "horas": round((b - a).total_seconds() / 3600.0, 2),
        "velas_1min": int(d.get("velas") or 0),
        "precio_inicio": px_i, "precio_fin": px_f,
        "precio_pct": None if not (px_i and px_f) else round(100.0 * (px_f / px_i - 1.0), 3),
        "cvd_spot_usd": f("cvd_spot"), "minutos_spot": int(d.get("n_spot") or 0),
        "ballena_spot_usd": f("ballena"),
        "oi_inicio": oi_i, "oi_fin": oi_f,
        "oi_pct": None if not (oi_i and oi_f) else round(100.0 * (oi_f / oi_i - 1.0), 3),
        "muestras_oi": int(d.get("n_oi") or 0),
        "funding_medio_pct": None if f("funding") is None else round(f("funding") * 100.0, 4),
        "muestras_funding": int(d.get("n_fund") or 0),
        "liq_largos_usd": f("liq_long"), "liq_cortos_usd": f("liq_short"),
        "muestras_liq": int(d.get("n_liq") or 0),
    }


def _prueba(clave: str, dice: str, lado: str | None, cifra: str, motivo: str = "") -> dict[str, Any]:
    return {"prueba": clave, "dice": dice, "vota": lado, "cifra": cifra, "no_vota_porque": motivo}


def _pruebas(v: dict[str, Any], c: dict[str, Any]) -> list[dict[str, Any]]:
    """Cada prueba con su lado y su cifra. `vota=None` significa NO SE PUDO MEDIR: no cuenta ni a
    favor ni en contra, y dice por que."""
    out: list[dict[str, Any]] = []

    # 1 · PROGRESO DEL PRECIO. Es el hecho, no una opinion.
    if v["precio_pct"] is None:
        out.append(_prueba("progreso_precio", "sin velas en la ventana", None, "N/D",
                           "no hay ohlcv 1min en el rango pedido"))
    else:
        out.append(_prueba("progreso_precio",
                           "el precio sube" if v["precio_pct"] > 0 else "el precio baja",
                           "alcista" if v["precio_pct"] > 0 else "bajista",
                           f'{v["precio_pct"]:+.2f}% sobre {v["velas_1min"]} velas'))

    # 2 · CVD DE SPOT, CONTRA SU CONTROL. La leccion del README: no se clasifica por el
    # diferencial, se mira la pata de spot POR SI MISMA. Y el control importa: spot vendiendo no
    # significa lo mismo si el tramo anterior compraba que si tambien vendia.
    if v["cvd_spot_usd"] is None or v["minutos_spot"] == 0:
        out.append(_prueba("cvd_spot", "sin minutos de spot en la ventana", None, "N/D",
                           "spot_trades_agg no tiene filas en el rango"))
    else:
        giro = (c.get("cvd_spot_usd") is not None
                and (c["cvd_spot_usd"] > 0) != (v["cvd_spot_usd"] > 0))
        cifra = f'{v["cvd_spot_usd"]/1e6:+.1f} M sobre {v["minutos_spot"]} minutos'
        if c.get("cvd_spot_usd") is not None:
            cifra += f' · control {c["cvd_spot_usd"]/1e6:+.1f} M'
        out.append(_prueba("cvd_spot",
                           ("el spot vende, y en el tramo anterior compraba" if giro and v["cvd_spot_usd"] < 0
                            else "el spot compra, y en el tramo anterior vendia" if giro
                            else "el spot vende" if v["cvd_spot_usd"] < 0 else "el spot compra"),
                           "bajista" if v["cvd_spot_usd"] < 0 else "alcista", cifra))

    # 3 · INTERES ABIERTO. Es la prueba que distingue traspaso de cierre, y por eso su lado no es
    # alcista ni bajista: es «cambia de manos» o «se cierra».
    if v["oi_pct"] is None:
        out.append(_prueba("interes_abierto", "sin muestras de OI", None, "N/D",
                           "open_interest no tiene filas de 5min en el rango"))
    else:
        out.append(_prueba("interes_abierto",
                           "el interes abierto cae: se cierran posiciones" if v["oi_pct"] < 0
                           else "el interes abierto aguanta o sube: el papel cambia de manos",
                           "cierre" if v["oi_pct"] < 0 else "traspaso",
                           f'{v["oi_pct"]:+.2f}% sobre {v["muestras_oi"]} muestras'))

    # 4 · LIQUIDACIONES. Que lado se rompio.
    ll, ls = v.get("liq_largos_usd"), v.get("liq_cortos_usd")
    if ll is None or ls is None or v["muestras_liq"] == 0:
        out.append(_prueba("liquidaciones", "sin muestras de liquidaciones", None, "N/D",
                           "liquidations no tiene filas de 5min en el rango"))
    else:
        out.append(_prueba("liquidaciones",
                           "se rompen los largos" if ll > ls else "se rompen los cortos",
                           "bajista" if ll > ls else "alcista",
                           f'{ll/1e6:.1f} M largos contra {ls/1e6:.1f} M cortos sobre {v["muestras_liq"]} muestras'))

    # 5 · FUNDING. Dice quien PAGA, que es posicionamiento y no direccion. Vota «posicionamiento»
    # y no alcista/bajista a proposito: un funding positivo con el precio cayendo significa que
    # los largos pagan Y pierden, y llamar a eso «alcista» seria leerlo al reves.
    if v["funding_medio_pct"] is None:
        out.append(_prueba("funding", "sin muestras de funding", None, "N/D",
                           "funding_rate no tiene filas de 5min en el rango"))
    else:
        cifra = f'{v["funding_medio_pct"]:+.4f}% sobre {v["muestras_funding"]} muestras'
        if c.get("funding_medio_pct") is not None:
            cifra += f' · control {c["funding_medio_pct"]:+.4f}%'
        out.append(_prueba("funding",
                           "pagan los largos" if v["funding_medio_pct"] > 0 else "pagan los cortos",
                           "posicionamiento", cifra))

    # 6 · BALLENA DE SPOT. NO VOTA, y se dice por que. El cero esta MEDIDO como no medible.
    out.append(_prueba("ballena_spot", "no se puede medir", None,
                       f'{(v.get("ballena_spot_usd") or 0.0)/1e6:.1f} M en {v["minutos_spot"]} minutos',
                       BALLENA_NO_MEDIBLE))
    return out


def _veredicto(pruebas: list[dict[str, Any]]) -> dict[str, Any]:
    """La cuenta, legible. Sin pesos: un peso que no sale de una medida es un peso inventado."""
    votan = [p for p in pruebas if p["vota"] is not None]
    n = len(votan)
    lados = [p["vota"] for p in votan]
    baja = lados.count("bajista")
    alta = lados.count("alcista")
    cierre = "cierre" in lados
    traspaso = "traspaso" in lados

    # LA REGLA, heredada del README:255-262: no se llama acumulacion a un tramo en el que el spot
    # vendio. Se mira la pata de spot POR SI MISMA, no el diferencial.
    spot = next((p for p in pruebas if p["prueba"] == "cvd_spot"), None)
    spot_lado = spot["vota"] if spot else None

    if cierre and baja >= 2:
        nombre = "desapalancamiento"
        porque = ("el precio cae, el spot vende y **el interes abierto cae con ellos**. No es "
                  "distribucion: en una distribucion alguien compra lo que otro vende y el OI "
                  "aguanta. Aqui las posiciones se CIERRAN. Esta casa no tenia nombre para esto "
                  "-su vocabulario era acumulacion, distribucion o equilibrio- y forzarlo a uno "
                  "de los tres seria el mismo error que el README ya cuenta.")
    elif traspaso and baja >= 2 and spot_lado == "bajista":
        nombre = "compatible_con_distribucion"
        porque = "el precio cae y el spot vende, y el interes abierto aguanta: el papel cambia de manos."
    elif traspaso and alta >= 2 and spot_lado == "alcista":
        nombre = "compatible_con_acumulacion"
        porque = "el precio sube y el spot compra, y el interes abierto aguanta."
    else:
        nombre = "ninguna"
        porque = ("las pruebas no apuntan a la misma estructura. Un veredicto que siempre elige "
                  "alguna no es un veredicto.")
    return {
        "estructura": nombre,
        "porque": porque,
        "pruebas_que_votan": n,
        "pruebas_totales": len(pruebas),
        "reparto": {"bajista": baja, "alcista": alta,
                    "cierre": lados.count("cierre"), "traspaso": lados.count("traspaso"),
                    "posicionamiento": lados.count("posicionamiento")},
        "no_es_prediccion": ("Esto es LECTURA de lo que ya paso. No dice que viene despues: "
                             "esta medido que la señal no anticipa."),
    }


async def estructura_de_rango(
    conn: asyncpg.Connection, symbol: str, base: str,
    desde: datetime, hasta: datetime | None,
) -> dict[str, Any]:
    """`hasta=None` significa «hasta ahora». Se ECHA el instante que se uso, para que una ventana
    abierta se pueda volver a pedir cerrada y dar lo mismo: una ventana que acaba en now() da
    cifras distintas cada vez y no se puede auditar."""
    fin = hasta or datetime.now(UTC)
    dur = fin - desde
    v = await _ventana(conn, symbol, base, desde, fin)
    c = await _ventana(conn, symbol, base, desde - dur, desde)
    pruebas = _pruebas(v, c)
    return {
        "symbol": symbol,
        "ventana": v,
        "control": c,
        "fin_abierto": hasta is None,
        "pruebas": pruebas,
        "veredicto": _veredicto(pruebas),
        "as_of": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
