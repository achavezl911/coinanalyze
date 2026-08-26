"""Perfil de volumen y delta por nivel de precio.

Responde a "en esta zona, ¿hubo más compra o más venta?" sin obligar a teclear los bordes:
reparte el volumen de cada vela entre los cubos de precio que cruza su rango low-high y suma
por cubo. Publica además el POC y el área de valor del 70%, que son las dos referencias
estándar de un perfil.

DOS LÍMITES QUE EL PANEL DECLARA, porque cambian lo que se puede concluir:

1. **El reparto dentro de la vela es uniforme y por tanto aproximado.** No guardamos la
   distribución de trades dentro de la barra: sabemos que se operaron N contratos entre low y
   high, no en qué punto. Con velas de 5 min el rango es estrecho y el error es pequeño; con
   4 h una sola vela puede abarcar varios cubos y el reparto es una hipótesis. Por eso el
   perfil sirve para leer la FORMA (dónde se concentró y dónde no) y no para afirmar que en un
   precio exacto se cruzaron X contratos.

2. **El delta es de futuros de Binance (`.A`), no del contado.** `buy_volume` viene del OHLCV
   de Coinalyze para el perpetuo. El CVD spot histórico solo existe agregado por sesión NYSE
   (`daily_session_agg`), que no tiene resolución de precio y por tanto no puede alimentar un
   perfil. Etiquetar esto como "compra" a secas repetiría el error de v1.3.4.

El delta neto se publica también como fracción del volumen de su propio cubo: en términos
absolutos un cubo con mucho volumen domina siempre, y lo informativo es el desequilibrio
relativo.

NO SUSTITUYE a `scalp_logic.volume_profile`, que sigue alimentando el contexto de IA. Aquel
resuelve otro problema: la sesión UTC en curso con velas de 1 min, asignando cada vela entera
al cubo de su cierre. Con velas de 1 min esa asignación es razonable; con 4 h metería cuatro
horas de negocio en un único precio, y por eso aquí se reparte por el rango.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg

from app.data_gaps import coverage_entry, expected_buckets

# Nº de cubos objetivo. Con menos el perfil pierde el detalle de los nodos delgados; con más,
# cada cubo recibe tan pocas velas que el reparto uniforme domina la forma.
TARGET_BUCKETS = 72
# Fracción del volumen total que define el área de valor. 70% es la convención del perfil.
VALUE_AREA_SHARE = 0.70
# Un cubo es "delgado" por debajo de esta fracción de la mediana: el precio lo atravesó rápido
# y no hay negocio que defender ahí.
THIN_NODE_RATIO = 0.30
# Por debajo de esto no se publica perfil: la forma sería ruido de unas pocas velas.
MIN_BARS = 30

INTERVAL_LABEL = {"4hour": "velas de 4 h", "5min": "velas de 5 min"}


def bucket_size(low: float, high: float) -> float:
    """Ancho de cubo redondeado a 1/2/5 x 10^n, para que las etiquetas de precio sean legibles."""
    span = high - low
    if span <= 0:
        return 0.0
    raw = span / TARGET_BUCKETS
    exponent = 10 ** int(_floor_log10(raw))
    for step in (1, 2, 5, 10):
        if raw <= step * exponent:
            return float(step * exponent)
    return float(10 * exponent)


def bucket_index(price: float, step: float) -> int:
    """Cubo al que cae un precio.

    El `//` a secas se equivoca en los bordes exactos: `104 // 0.2` da 519 porque 104/0.2 se
    representa como 519.9999999999999, y entonces el volumen de una vela que arranca justo en
    104 se etiqueta un cubo por debajo. La tolerancia corrige el borde sin mover nada más.
    """
    return math.floor(price / step + 1e-9)


def _floor_log10(value: float) -> int:
    exponent = 0
    if value >= 1:
        while value >= 10:
            value /= 10
            exponent += 1
    else:
        while value < 1:
            value *= 10
            exponent -= 1
    return exponent


def value_area(rows: list[dict[str, Any]], poc_index: int) -> tuple[float, float]:
    """Crece desde el POC hacia el vecino con más volumen hasta cubrir el 70%.

    Es el procedimiento clásico: el área de valor no es simétrica porque el mercado tampoco lo
    es, y partirla por la mitad inventaría un equilibrio que no existe.
    """
    total = sum(row["volume_usd"] for row in rows)
    if total <= 0:
        return rows[poc_index]["price"], rows[poc_index]["price"]
    low_index = high_index = poc_index
    covered = rows[poc_index]["volume_usd"]
    while covered < total * VALUE_AREA_SHARE and (low_index > 0 or high_index < len(rows) - 1):
        below = rows[low_index - 1]["volume_usd"] if low_index > 0 else -1.0
        above = rows[high_index + 1]["volume_usd"] if high_index < len(rows) - 1 else -1.0
        if above >= below:
            high_index += 1
            covered += rows[high_index]["volume_usd"]
        else:
            low_index -= 1
            covered += rows[low_index]["volume_usd"]
    return rows[low_index]["price"], rows[high_index]["price"]


def profile_read(bars: list[dict[str, Any]], interval: str, price: float | None) -> dict[str, Any]:
    """Construye el perfil. `bars` necesita low, high, volume, buy_volume y close."""
    usable = [
        bar
        for bar in bars
        if bar.get("low") and bar.get("high") and bar["high"] >= bar["low"] and bar.get("volume")
    ]
    if len(usable) < MIN_BARS:
        return {
            "available": False,
            "reason": (
                f"Solo {len(usable)} {INTERVAL_LABEL.get(interval, 'velas')} con volumen; "
                f"se necesitan {MIN_BARS} para que la forma del perfil signifique algo."
            ),
            "bars": len(usable),
        }

    low = min(bar["low"] for bar in usable)
    high = max(bar["high"] for bar in usable)
    step = bucket_size(low, high)
    if step <= 0:
        return {"available": False, "reason": "El rango de precios es nulo.", "bars": len(usable)}

    volume_by_bucket: dict[int, float] = {}
    delta_by_bucket: dict[int, float] = {}
    for bar in usable:
        # El notional se calcula con el cierre de la vela, igual que en el resto del proyecto.
        close = bar.get("close") or bar["high"]
        volume_usd = bar["volume"] * close
        delta_usd = ((2 * (bar.get("buy_volume") or 0.0)) - bar["volume"]) * close
        first = bucket_index(bar["low"], step)
        last = bucket_index(bar["high"], step)
        spans = last - first + 1
        for index in range(first, last + 1):
            volume_by_bucket[index] = volume_by_bucket.get(index, 0.0) + volume_usd / spans
            delta_by_bucket[index] = delta_by_bucket.get(index, 0.0) + delta_usd / spans

    total_volume = sum(volume_by_bucket.values())
    rows = [
        {
            # index*step arrastra el error del float (77.60000000000001); el cubo es exacto.
            "price": round(index * step, 8),
            "volume_usd": volume,
            "delta_usd": delta_by_bucket.get(index, 0.0),
            "share_pct": round(100 * volume / total_volume, 3) if total_volume else 0.0,
            "delta_share_pct": round(100 * delta_by_bucket.get(index, 0.0) / volume, 2)
            if volume
            else 0.0,
        }
        for index, volume in sorted(volume_by_bucket.items())
    ]
    volumes = sorted(row["volume_usd"] for row in rows)
    middle = len(volumes) // 2
    median_volume = (
        volumes[middle] if len(volumes) % 2 else (volumes[middle - 1] + volumes[middle]) / 2
    )
    poc_index = max(range(len(rows)), key=lambda i: rows[i]["volume_usd"])
    va_low, va_high = value_area(rows, poc_index)
    for row in rows:
        row["in_value_area"] = va_low <= row["price"] <= va_high
        row["thin"] = bool(median_volume) and row["volume_usd"] < median_volume * THIN_NODE_RATIO

    net_delta = sum(row["delta_usd"] for row in rows)
    return {
        "available": True,
        "interval": interval,
        "bars": len(usable),
        "from": str(usable[0].get("ts") or "")[:10],
        "to": str(usable[-1].get("ts") or "")[:10],
        "bucket_usd": step,
        "price": price,
        "rows": list(reversed(rows)),
        "total_volume_usd": total_volume,
        "net_delta_usd": net_delta,
        "net_delta_share_pct": round(100 * net_delta / total_volume, 2) if total_volume else 0.0,
        "poc": rows[poc_index]["price"],
        "value_area_low": va_low,
        "value_area_high": va_high,
        "median_bucket_volume_usd": median_volume,
        "method": {
            "reparto": (
                "El volumen de cada vela se reparte por igual entre los cubos que cruza su "
                "rango low-high. Es una aproximación: no guardamos dónde ocurrió cada trade "
                "dentro de la barra."
            ),
            "area_valor": f"{int(VALUE_AREA_SHARE * 100)}% del volumen creciendo desde el POC.",
            "nodo_delgado": f"Volumen bajo el {int(THIN_NODE_RATIO * 100)}% de la mediana del cubo.",
        },
        "sources": {
            "volumen_y_delta": "ohlcv (buy_volume real del perpetuo Binance vía Coinalyze)",
            "no_disponible": [
                "CVD spot con resolución de precio (solo existe agregado por sesión NYSE)",
                "distribución de trades dentro de la vela",
            ],
        },
        "warning": (
            "Delta de futuros Binance, no del contado. La forma del perfil es fiable; el "
            "importe exacto de un cubo concreto es una estimación."
        ),
    }


# La cadencia de cada intervalo servido. Es la misma que codifica el CASE de la consulta de
# abajo, y vive aqui arriba porque ahora tambien la necesita la cobertura.
DELTA_PROFILE_BUCKET = {"4hour": timedelta(hours=4), "5min": timedelta(minutes=5)}


async def delta_profile(
    conn: asyncpg.Connection,
    symbol: str,
    interval: str,
    days: int,
    price: float | None = None,
) -> dict[str, Any]:
    """Perfil por nivel de precio sobre la ventana pedida.

    La cobertura real manda: 4h llega a ~300 días y 5min a ~9 (Coinalyze no sirve más 5min
    hacia atrás). Se pide lo que se pueda y la respuesta declara cuántas velas entraron.
    """
    as_of = datetime.now(UTC)
    since = as_of - timedelta(days=days)
    rows = await conn.fetch(
        "SELECT ts, low, high, close, volume, buy_volume FROM ohlcv "
        "WHERE symbol=$1 AND interval=$2 AND ts >= $3 "
        "AND ts + CASE WHEN $2='4hour' THEN interval '4 hours' "
        "                 WHEN $2='5min' THEN interval '5 minutes' END <= $4 "
        "ORDER BY ts",
        symbol, interval, since, as_of,
    )
    result = profile_read([dict(row) for row in rows], interval, price)
    # K43 · es una SERIE y su ventana es su coverage. Hasta el 2026-08-26 declaraba from/to
    # y bars, que dicen QUE se sirvio pero no cuanto FALTA: con 90 dias de velas de 4 h se
    # sirvieron 539 de las 540 que caben en la ventana y no habia forma de verlo. La ventana
    # es la de las velas que ENTRARON, no la pedida: pedir 90 dias cuando el historico tiene
    # 9 no es un hueco, es un historico mas corto, y medirlo contra lo pedido daria
    # incompletos falsos -el mismo motivo por el que /api/daily no lo hace (api.py:1990)-.
    # observed son las velas traidas; `bars` es el subconjunto que ademas tiene rango de
    # precio utilizable, que es otra cuenta y por eso no se mezclan.
    cobertura = None
    if rows:
        paso = DELTA_PROFILE_BUCKET[interval]
        ventana_ini = rows[0]["ts"]
        ventana_fin = rows[-1]["ts"] + paso
        cobertura = coverage_entry(
            ventana_ini,
            ventana_fin,
            sources=((f"ohlcv_{interval}", expected_buckets(ventana_ini, ventana_fin, paso),
                      len(rows)),),
        )
    return {
        "symbol": symbol,
        "requested_days": days,
        "coverage": {"served_window": cobertura},
        **result,
    }
