"""Los INSUMOS del generador de entradas, leidos de la base CORTADOS EN T (campana 135, E1).

Ninguna consulta de este modulo usa now(), clock_timestamp() ni CURRENT_TIMESTAMP: cada ventana
lleva su borde como parametro, y ese borde sale de T. Lo que no se puede saber en T no se lee.

  velas del perfil   ohlcv 1min agrupado con date_bin desde 1970-01-01 UTC, en [T - W, T);
                     un cubo sin filas sale con 0 minutos (VELA CERRADA DE VERDAD: todos o nada)
  zonas              ohlcv 'daily' y '4hour' cerradas antes del corte (= apertura de la vela que
                     arma) y el ultimo cierre de 1 min antes del corte
  flujos             spot_trades_agg y futures_trades_agg 'combined' (las dos venues) por minuto,
                     alineados al cierre de la vela, con su cobertura en minutos (MC10/MC11)
  libro y mids       orderbook_snapshot de Bybit y de Binance en T (ts <= T)
  funding            funding_rate de Binance, ultimo cubo de 5 min cerrado en T
  calendario         macro_event con hora en [T, T + ventana)

En BACKTEST el espejo no tiene libro (orderbook_snapshot dura ~6 h): la referencia del plan es la
apertura de 1 min del minuto siguiente a T y el spread queda NO MEDIDO, declarado en la foto.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

from app.entradas.motor import BACKTEST, de_iso, iso

_VELAS_SQL = """
SELECT date_bin($2::interval, ts, TIMESTAMPTZ '1970-01-01 00:00:00+00') AS inicio,
       (array_agg(open ORDER BY ts))[1] AS open,
       max(high) AS high,
       min(low) AS low,
       (array_agg(close ORDER BY ts DESC))[1] AS close,
       sum(volume) AS volume,
       count(*)::int AS minutos
FROM ohlcv
WHERE symbol = $1 AND interval = '1min' AND ts >= $3 AND ts < $4
GROUP BY 1
ORDER BY 1
"""

_BARRAS_SQL = """
SELECT ts, high, low, close, volume
FROM ohlcv
WHERE symbol = $1 AND interval = $2 AND ts <= $3
ORDER BY ts DESC
LIMIT $4
"""

_PRECIO_CORTE_SQL = """
SELECT ts, close FROM ohlcv
WHERE symbol = $1 AND interval = '1min' AND ts < $2 AND ts >= $3
ORDER BY ts DESC LIMIT 1
"""

_FLUJO_SQL = """
SELECT ts, buy_vol_usd - sell_vol_usd AS delta, covered_seconds
FROM {tabla}
WHERE symbol = $1 AND exchange = 'combined' AND venue_count = $2 AND interval = '1min'
  AND ts >= $3 AND ts < $4
ORDER BY ts
"""

_LIBRO_SQL = """
SELECT ts, bid_px, ask_px, mid_px, spread_bps, bid_notional_l1, ask_notional_l1
FROM orderbook_snapshot
WHERE symbol = $1 AND exchange = $2 AND ts <= $3 AND ts > $4
ORDER BY ts DESC LIMIT 1
"""

_FUNDING_SQL = """
SELECT ts, fr_close FROM funding_rate
WHERE symbol = $1 AND interval = '5min' AND ts <= $2::timestamptz - interval '5 minutes' AND ts >= $3
ORDER BY ts DESC LIMIT 1
"""

_EVENTOS_SQL = """
SELECT event_key, event_at, title, importance, source
FROM macro_event
WHERE event_at >= $1 AND event_at < $2 AND importance >= $3
ORDER BY event_at, event_key
"""

_APERTURA_SIGUIENTE_SQL = """
SELECT ts, open FROM ohlcv WHERE symbol = $1 AND interval = '1min' AND ts = $2
"""


def _f(valor: Any) -> float | None:
    if valor is None:
        return None
    numero = float(valor)
    return numero if math.isfinite(numero) else None


def ventana_velas(comun: dict[str, Any], perfil: str) -> int:
    """Cuantas velas del perfil hacen falta en T: base de volumen o de separacion, vida maxima
    de VIGILANDO y ATR del perfil, mas la vela de T."""
    vela_min = comun["perfiles"][perfil]["vela_min"]
    base = max(comun["volumen"]["base_velas"][perfil], comun["separacion_ventana_velas"][perfil])
    vida = math.ceil(comun["vigilando_max_min"][perfil] / vela_min)
    return base + vida + comun["atr"]["n"] + 1


async def velas_perfil(conn, symbol: str, T: datetime, vela_min: int, n: int) -> list[dict[str, Any]]:
    paso = timedelta(minutes=vela_min)
    desde = T - n * paso
    filas = await conn.fetch(_VELAS_SQL, symbol, paso, desde, T)
    por_inicio = {fila["inicio"]: fila for fila in filas}
    velas: list[dict[str, Any]] = []
    inicio = desde
    while inicio < T:
        fila = por_inicio.get(inicio)
        velas.append(
            {
                "inicio": iso(inicio),
                "fin": iso(inicio + paso),
                "open": _f(fila["open"]) if fila else None,
                "high": _f(fila["high"]) if fila else None,
                "low": _f(fila["low"]) if fila else None,
                "close": _f(fila["close"]) if fila else None,
                "volume": _f(fila["volume"]) if fila else None,
                "minutos": fila["minutos"] if fila else 0,
                "esperados": vela_min,
            }
        )
        inicio += paso
    return velas


async def barras(conn, symbol: str, intervalo: str, barra_min: int, corte: datetime,
                 n: int) -> list[dict[str, Any]]:
    """Barras nativas CERRADAS antes del corte: ts + barra <= corte."""
    paso = timedelta(minutes=barra_min)
    filas = await conn.fetch(_BARRAS_SQL, symbol, intervalo, corte - paso, n)
    return [
        {
            "t": iso(fila["ts"]),
            "cierre": iso(fila["ts"] + paso),
            "high": _f(fila["high"]),
            "low": _f(fila["low"]),
            "close": _f(fila["close"]),
            "volume": _f(fila["volume"]),
        }
        for fila in reversed(filas)
    ]


def _tramo(filas: list, desde: datetime, hasta: datetime, minuto_completo_s: int) -> dict[str, Any]:
    dentro = [f for f in filas if desde <= f["ts"] < hasta]
    completos = [
        f for f in dentro
        if f["covered_seconds"] is None or f["covered_seconds"] >= minuto_completo_s
    ]
    esperados = int((hasta - desde).total_seconds() // 60)
    return {
        "delta_usd": sum(float(f["delta"]) for f in dentro),
        "desde": iso(desde),
        "hasta": iso(hasta),
        "minutos": len(completos),
        "esperados": esperados,
        "completo": len(completos) == esperados,
        "ultimo_minuto": iso(max(f["ts"] for f in dentro)) if dentro else None,
        "minutos_cobertura_nula": sum(1 for f in dentro if f["covered_seconds"] is None),
    }


async def flujos(conn, *, tabla: str, simbolo: str, T: datetime, vela_min: int,
                 hora_min: int, hueco: dict[str, Any]) -> dict[str, Any]:
    largo = max(vela_min, hora_min)
    filas = await conn.fetch(
        _FLUJO_SQL.format(tabla=tabla), simbolo, hueco["spot_venues"],
        T - timedelta(minutes=largo), T,
    )
    return {
        "tabla": tabla,
        "simbolo": simbolo,
        "vela": _tramo(filas, T - timedelta(minutes=vela_min), T, hueco["minuto_completo_s"]),
        "ultima_hora": _tramo(filas, T - timedelta(minutes=hora_min), T, hueco["minuto_completo_s"]),
    }


async def libro(conn, symbol: str, exchange: str, T: datetime,
                edad_max_s: float) -> dict[str, Any] | None:
    """La ultima foto de libro con ts <= T y no mas vieja que edad_max_s: si no hay, None
    (ausente o rancio son la misma cosa para la decision: no se puede medir el coste)."""
    fila = await conn.fetchrow(_LIBRO_SQL, symbol, exchange, T, T - timedelta(seconds=edad_max_s))
    if fila is None or fila["mid_px"] is None:
        return None
    return {
        "exchange": exchange,
        "ts": iso(fila["ts"]),
        "edad_s": round((T - fila["ts"]).total_seconds(), 3),
        "bid": _f(fila["bid_px"]),
        "ask": _f(fila["ask_px"]),
        "mid": _f(fila["mid_px"]),
        "spread_bps": _f(fila["spread_bps"]),
        "bid_notional_l1": _f(fila["bid_notional_l1"]),
        "ask_notional_l1": _f(fila["ask_notional_l1"]),
    }


async def cargar(
    conn,
    *,
    symbol: str,
    base_asset: str,
    T: datetime,
    perfil: str,
    comun: dict[str, Any],
    calendario: dict[str, Any],
    modo: str,
) -> dict[str, Any]:
    """Todo lo que el motor necesita para la vela T de un simbolo y un perfil, cortado en T."""
    vela_min = comun["perfiles"][perfil]["vela_min"]
    corte = T - timedelta(minutes=vela_min)
    z = comun["zonas"]
    velas = await velas_perfil(conn, symbol, T, vela_min, ventana_velas(comun, perfil))
    diarias = await barras(conn, symbol, "daily", z["barra_min"]["1d"], corte, z["sesiones_1d"])
    h4 = await barras(conn, symbol, "4hour", z["barra_min"]["4h"], corte, z["velas_4h"])
    fila_corte = await conn.fetchrow(
        _PRECIO_CORTE_SQL, symbol, corte, corte - timedelta(minutes=vela_min)
    )
    hora_min = comun["spot"]["ultima_hora_min"]
    spot = await flujos(conn, tabla="spot_trades_agg", simbolo=base_asset, T=T,
                        vela_min=vela_min, hora_min=hora_min, hueco=comun["hueco"])
    fut = await flujos(conn, tabla="futures_trades_agg", simbolo=symbol, T=T,
                       vela_min=vela_min, hora_min=hora_min, hueco=comun["hueco"])
    bybit = await libro(conn, symbol, "bybit", T, comun["libro_edad_max_s"])
    binance = await libro(conn, symbol, "binance", T, comun["libro_edad_max_s"])
    mid_binance = {"mid": binance["mid"], "ts": binance["ts"], "fuente": "orderbook_snapshot binance"} if binance else None
    mid_bybit = {"mid": bybit["mid"], "ts": bybit["ts"], "fuente": "orderbook_snapshot bybit"} if bybit else None
    if mid_binance is None and modo == BACKTEST:
        siguiente = await conn.fetchrow(_APERTURA_SIGUIENTE_SQL, symbol, T)
        if siguiente is not None:
            mid_binance = {
                "mid": _f(siguiente["open"]),
                "ts": iso(siguiente["ts"]),
                "fuente": "BACKTEST: apertura de ohlcv 1min del minuto que abre en T (sin libro en el espejo)",
            }
    base_bps = None
    if mid_binance and mid_bybit and mid_binance["mid"]:
        base_bps = (mid_bybit["mid"] - mid_binance["mid"]) / mid_binance["mid"] * 10_000
    fila_funding = await conn.fetchrow(_FUNDING_SQL, symbol, T, corte)
    hasta_cal = T + timedelta(minutes=max(calendario["ventana_min"].values()))
    eventos = await conn.fetch(_EVENTOS_SQL, T, hasta_cal, calendario["importancia_minima"])
    return {
        "T": T,
        "symbol": symbol,
        "perfil": perfil,
        "modo": modo,
        "velas": velas,
        "diarias": diarias,
        "h4": h4,
        "precio_corte": _f(fila_corte["close"]) if fila_corte else None,
        "precio_corte_ts": iso(fila_corte["ts"]) if fila_corte else None,
        "flujos": {"spot": spot, "futuros": fut},
        "libro_bybit": bybit,
        "mids": {"binance": mid_binance, "bybit": mid_bybit, "base_bps": base_bps},
        "funding": {"binance": {"fr": _f(fila_funding["fr_close"]), "ts": iso(fila_funding["ts"]),
                                "fuente": "funding_rate 5min, ultimo cubo cerrado en T"}}
        if fila_funding else None,
        "eventos_macro": [
            {
                "clave": e["event_key"],
                "titulo": e["title"],
                "hora_utc": iso(e["event_at"]),
                "importancia": int(e["importance"]),
                "fuente": e["source"],
            }
            for e in eventos
        ],
    }


def vela_de_T_completa(insumos: dict[str, Any]) -> bool:
    velas = insumos["velas"]
    return bool(velas) and de_iso(velas[-1]["fin"]) == insumos["T"] and (
        velas[-1]["minutos"] == velas[-1]["esperados"]
    )
