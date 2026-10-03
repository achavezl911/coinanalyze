"""Banco sintetico de las entradas (campana 135): un mercado de mentira con zonas CONOCIDAS.

Velas diarias en triangulo entre 90 y 110 (pivotes estrictos en 90 y 110) y de 4 h entre 95 y
105 (pivotes en 95 y 105): con ATR diario 5.2 la tolerancia de racimo es 1.3 y el margen del
borde 0.26, asi que las cuatro zonas son [89.74, 90.26], [94.74, 95.26], [104.74, 105.26] y
[109.74, 110.26]. Las velas de 15 m oscilan en 96.3-96.7 con ATR del perfil 0.4.

El escenario base es un RECHAZO DE SOPORTE limpio en [94.74, 95.26]: la vela de T toca 95.1 y
cierra 95.8 con spot y volumen a favor. refleja() da su espejo exacto (precio -> 200 - precio,
compras <-> ventas): el corto que tiene que salir.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta
from typing import Any

from app.entradas import motor as M
from app.entradas import reglamento as R
from app.entradas.insumos import ventana_velas

T0 = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
TRIANGULO = (-1.0, -0.6, -0.2, 0.2, 0.6, 1.0, 0.6, 0.2, -0.2, -0.6)
CODIGO = "c" * 64


def doc() -> dict[str, Any]:
    return R.cargar()


def versiones() -> list[dict[str, Any]]:
    return R.versiones_en_curso(doc())


def comun() -> dict[str, Any]:
    return R.valores(versiones()[0]["bloques"]["comun"])


def revision(*, cubre_hasta: datetime, eventos: list[dict] | None = None) -> dict[str, Any]:
    r = {
        "revision": "cal-banco",
        "padre": None,
        "fecha": "2026-08-01",
        "autor": "banco",
        "motivo": "banco",
        "vigente_desde": "2026-08-01T00:00:00Z",
        "cubre_hasta": M.iso(cubre_hasta),
        "eventos": eventos or [],
    }
    r["huella"] = R.huella_revision(r)
    return r


def barras(n: int, minutos: int, centro: float, amplitud: float, media: float,
           corte: datetime) -> list[dict[str, Any]]:
    salida = []
    for i in range(n):
        inicio = corte - (n - i) * timedelta(minutes=minutos)
        c = centro + amplitud * TRIANGULO[i % len(TRIANGULO)]
        salida.append(
            {
                "t": M.iso(inicio),
                "cierre": M.iso(inicio + timedelta(minutes=minutos)),
                "high": c + media,
                "low": c - media,
                "close": c,
                "volume": 1000.0,
            }
        )
    return salida


def vela(inicio: datetime, o: float, h: float, l: float, c: float, v: float = 100.0,  # noqa: E741
         minutos: int = 15, esperados: int = 15) -> dict[str, Any]:
    return {
        "inicio": M.iso(inicio),
        "fin": M.iso(inicio + timedelta(minutes=esperados)),
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "volume": v,
        "minutos": minutos,
        "esperados": esperados,
    }


def tramo(desde: datetime, hasta: datetime, delta: float, completo: bool = True) -> dict[str, Any]:
    esperados = int((hasta - desde).total_seconds() // 60)
    return {
        "delta_usd": delta,
        "desde": M.iso(desde),
        "hasta": M.iso(hasta),
        "minutos": esperados if completo else esperados - 1,
        "esperados": esperados,
        "completo": completo,
        "ultimo_minuto": M.iso(hasta - timedelta(minutes=1)),
        "minutos_cobertura_nula": 0,
    }


def insumos(
    T: datetime = T0,
    *,
    gatillo: tuple[float, float, float, float] = (96.0, 96.2, 95.1, 95.8),
    volumen: float = 250.0,
    base: float = 96.5,
    precio_corte: float = 96.0,
    spot_vela: float = 1e6,
    spot_hora: float = 2e6,
    fut_vela: float = 5e6,
    mid_binance: float = 95.81,
    eventos: list[dict] | None = None,
    minutos_gatillo: int = 15,
    previas: list[tuple[float, float, float, float]] | None = None,
) -> dict[str, Any]:
    """Los insumos de una vela T de 15 m. `previas` sustituye las ultimas velas antes de T."""
    c = comun()
    n = ventana_velas(c, "intradia")
    paso = timedelta(minutes=15)
    velas = []
    for i in range(n - 1):
        inicio = T - (n - i) * paso
        centro = base + 0.2 * TRIANGULO[i % len(TRIANGULO)]
        velas.append(vela(inicio, centro, centro + 0.2, centro - 0.2, centro))
    if previas:
        for j, (o, h, l, cc) in enumerate(previas):  # noqa: E741
            k = len(velas) - len(previas) + j
            velas[k] = vela(T - (n - k) * paso, o, h, l, cc)
    else:
        previa = velas[-1]
        previa["close"] = precio_corte
        previa["low"] = min(previa["low"], precio_corte)
        previa["high"] = max(previa["high"], precio_corte)
    o, h, l, cc = gatillo  # noqa: E741
    velas.append(vela(T - paso, o, h, l, cc, v=volumen, minutos=minutos_gatillo))
    corte = T - paso
    return {
        "T": T,
        "symbol": "BTCUSDT_PERP.A",
        "perfil": "intradia",
        "modo": M.PROSPECTIVO,
        "velas": velas,
        "diarias": barras(200, 1440, 100.0, 8.0, 2.0, corte.replace(hour=0, minute=0)),
        "h4": barras(200, 240, 100.0, 3.0, 2.0, corte - timedelta(hours=corte.hour % 4,
                                                                   minutes=corte.minute)),
        "precio_corte": precio_corte,
        "precio_corte_ts": M.iso(corte - timedelta(minutes=1)),
        "flujos": {
            "spot": {"vela": tramo(T - paso, T, spot_vela),
                     "ultima_hora": tramo(T - timedelta(hours=1), T, spot_hora)},
            "futuros": {"vela": tramo(T - paso, T, fut_vela),
                        "ultima_hora": tramo(T - timedelta(hours=1), T, 3e6)},
        },
        "libro_bybit": {
            "exchange": "bybit",
            "ts": M.iso(T - timedelta(seconds=1)),
            "edad_s": 1.0,
            "bid": mid_binance + 0.01,
            "ask": mid_binance + 0.03,
            "mid": mid_binance + 0.02,
            "spread_bps": 0.02 / (mid_binance + 0.02) * 10_000,
            "bid_notional_l1": 1e6,
            "ask_notional_l1": 1e6,
        },
        "mids": {
            "binance": {"mid": mid_binance, "ts": M.iso(T - timedelta(seconds=1)),
                        "fuente": "orderbook_snapshot binance"},
            "bybit": {"mid": mid_binance + 0.02, "ts": M.iso(T - timedelta(seconds=1)),
                      "fuente": "orderbook_snapshot bybit"},
            "base_bps": 0.02 / mid_binance * 10_000,
        },
        "funding": {"binance": {"fr": 0.0001, "ts": M.iso(T - timedelta(minutes=5)),
                                "fuente": "funding_rate"}},
        "eventos_macro": eventos or [],
    }


def refleja(ins: dict[str, Any], eje: float = 100.0) -> dict[str, Any]:
    """El mismo mercado reflejado: precio -> 2*eje - precio, compras <-> ventas."""
    r = copy.deepcopy(ins)

    def f(x):
        return None if x is None else 2 * eje - x

    for v in r["velas"]:
        v["open"], v["close"] = f(v["open"]), f(v["close"])
        v["high"], v["low"] = f(v["low"]), f(v["high"])
    for b in r["diarias"] + r["h4"]:
        b["close"] = f(b["close"])
        b["high"], b["low"] = f(b["low"]), f(b["high"])
    r["precio_corte"] = f(r["precio_corte"])
    for pata in r["flujos"].values():
        for t in pata.values():
            t["delta_usd"] = -t["delta_usd"]
    libro = r["libro_bybit"]
    libro["bid"], libro["ask"] = f(libro["ask"]), f(libro["bid"])
    libro["mid"] = f(libro["mid"])
    libro["bid_notional_l1"], libro["ask_notional_l1"] = libro["ask_notional_l1"], libro["bid_notional_l1"]
    for venue in ("binance", "bybit"):
        r["mids"][venue]["mid"] = f(r["mids"][venue]["mid"])
    return r


def paso(ins: dict[str, Any], *, previos: list[dict] | None = None, rev: dict | None = None,
         modo: str = M.PROSPECTIVO) -> dict[str, Any]:
    T = ins["T"]
    return M.paso(
        T=T,
        symbol=ins["symbol"],
        perfil=ins["perfil"],
        modo=modo,
        versiones=versiones(),
        insumos=ins,
        previos=previos or [],
        revision=rev or revision(cubre_hasta=T + timedelta(days=30)),
        codigo=CODIGO,
    )


def elige(transiciones: list[dict], *, familia: str, lado: str, estado: str | None = None) -> list[dict]:
    return [
        t for t in transiciones
        if t["familia"] == familia and t["lado"] == lado and (estado is None or t["estado"] == estado)
    ]


async def sembrar(conn, T: datetime, ins: dict, symbol: str, base: str) -> None:
    """Pasa los insumos del banco a filas de la base: velas de 15 m -> 15 velas de 1 min, etc."""
    filas = []
    for v in ins["velas"]:
        if v["minutos"] == 0:
            continue
        inicio = M.de_iso(v["inicio"])
        for m in range(v["minutos"]):
            o = v["open"] if m == 0 else (v["open"] + v["close"]) / 2
            c = v["close"] if m == v["minutos"] - 1 else (v["open"] + v["close"]) / 2
            h = v["high"] if m == 1 else max(o, c)
            lo = v["low"] if m == 2 else min(o, c)
            vol = v["volume"] / v["esperados"]
            filas.append((inicio + timedelta(minutes=m), symbol, "1min", o, h, lo, c, vol, vol / 2, 1, 1))
    for intervalo, barras in (("daily", ins["diarias"]), ("4hour", ins["h4"])):
        for b in barras:
            filas.append((M.de_iso(b["t"]), symbol, intervalo, b["close"], b["high"], b["low"],
                          b["close"], b["volume"], b["volume"] / 2, 1, 1))
    await conn.executemany(
        "INSERT INTO ohlcv(ts, symbol, interval, open, high, low, close, volume, buy_volume, tx, btx) "
        "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) ON CONFLICT DO NOTHING",
        filas,
    )
    for tabla, simbolo, pata in (("spot_trades_agg", base, "spot"), ("futures_trades_agg", symbol, "futuros")):
        d_vela = ins["flujos"][pata]["vela"]["delta_usd"]
        d_hora = ins["flujos"][pata]["ultima_hora"]["delta_usd"]
        for m in range(60):
            ts = T - timedelta(minutes=60 - m)
            d = d_vela / 15 if ts >= T - timedelta(minutes=15) else (d_hora - d_vela) / 45
            extra = ("inst_buy_usd, inst_sell_usd, mid_buy_usd, mid_sell_usd, retail_buy_usd, "
                     "retail_sell_usd, " if tabla == "spot_trades_agg" else
                     "large_buy_usd, large_sell_usd, ")
            ceros = "0, 0, 0, 0, 0, 0, " if tabla == "spot_trades_agg" else "0, 0, "
            # como el colector desde 0df80b2: una fila por venue y la combinada con las dos
            for exchange, parte, venues in (("binance", 0.5, 1), ("bybit", 0.5, 1), ("combined", 1.0, 2)):
                await conn.execute(
                    f"INSERT INTO {tabla}(ts, symbol, exchange, interval, buy_vol_usd, sell_vol_usd, "
                    f"{extra}trade_count, covered_seconds, venue_count) "
                    f"VALUES ($1, $2, $3, '1min', $4, $5, {ceros}10, 60, $6)",
                    ts, simbolo, exchange, parte * (1e7 + d / 2), parte * (1e7 - d / 2), venues,
                )
    for exchange, mid in (("bybit", ins["mids"]["bybit"]["mid"]), ("binance", ins["mids"]["binance"]["mid"])):
        await conn.execute(
            "INSERT INTO orderbook_snapshot(ts, symbol, exchange, bid_px, ask_px, mid_px, spread_bps, "
            "bid_notional_l1, ask_notional_l1, venue_count) VALUES ($1,$2,$3,$4,$5,$6,$7,1e6,1e6,1)",
            T - timedelta(seconds=1), symbol, exchange, mid - 0.01, mid + 0.01, mid,
            0.02 / mid * 10_000,
        )
    await conn.execute(
        "INSERT INTO funding_rate(ts, symbol, interval, fr_open, fr_high, fr_low, fr_close) "
        "VALUES ($1, $2, '5min', 0.0001, 0.0001, 0.0001, 0.0001)",
        T - timedelta(minutes=10), symbol,
    )
