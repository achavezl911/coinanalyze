"""OF-1 · EL DATO DEL ORDER-FLOW (campana 140): `python -m app.orderflow`.

Cada operacion de nueve mercados -spot y perpetuos de Binance, Bybit y OKX, Coinbase spot, Bitget USDT y Deribit-
para BTC, ETH y SOL, guardada de cuatro formas:

  orderflow_celda      por minuto (hora de la OPERACION), venue, activo y nivel de precio: volumen del agresor
                       comprador y del vendedor, en base y en USD, y sus conteos. El dato base del footprint.
  orderflow_cinta      cada operacion, 48 h.
  orderflow_grande     las operaciones de al menos un umbral en USD por activo (config/orderflow.json), 365 dias.
  orderflow_cobertura  por minuto, venue y activo: segundos que la conexion ESTUVO entregando, operaciones,
                       tardias, fuera de plazo y reconexiones. Un minuto con menos de 60 s se declara en data_gap
                       y nunca se rellena.

Es un servicio APARTE de ws_collector y scalp_collector, de los que dependen las senales, DECIDE y el registro de
entradas: si este cae, aquellos no se enteran.

EL NIVEL SE CALCULA CON ARITMETICA DECIMAL EXACTA desde el TEXTO del precio: floor(precio/paso)*paso con Decimal.
En float, 2400.1 / 0.1 da 24000.999999999996 y la operacion cae en el nivel de abajo; medido el 2026-10-17, le pasa
a 400 de los 1000 precios de ETH entre 2400.0 y 2499.9 a paso 0.1, y a 3 de los 1000 de SOL entre 100.00 y 109.99
a paso 0.01 (109.32). Por eso el JSON se lee con parse_float=Decimal: Deribit manda los precios como numero.

UN MINUTO SE ESCRIBE a los ESCRIBE_S de cerrarse y se REESCRIBE (DELETE + INSERT: sustituye, no suma) a los
REESCRIBE_S si llegaron tardias; despues, una tardia solo se cuenta (`fuera`) y no entra ni en las celdas ni en la
cinta. Asi, las celdas de un minuto COMPLETO (60 s cubiertos) son exactamente la agregacion de su cinta. En el
minuto de una parada o un arranque no: la cinta va a la base cada segundo y puede guardar operaciones del proceso
que se fue, cuyas celdas se perdieron con el; ese minuto sale incompleto y declarado.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import random
import signal
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import ROUND_FLOOR, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import asyncpg
from websockets.asyncio.client import connect

from app.config import _PROJECT_ROOT, get_settings
from app.db import (
    ServiceOwnership,
    ServiceOwnershipLost,
    acquire_service_lock,
    create_pool,
    fenced_transaction,
    heartbeat_owned,
    monitor_service_lock,
    wait_for_stop_or_lock_loss,
)
from app.logging_setup import configure_logging
from app.partitioning import apply_temporal_retention

LOGGER = logging.getLogger(__name__)
SERVICIO = "orderflow"
ACTIVOS = ("BTC", "ETH", "SOL")
CONFIG_PATH = _PROJECT_ROOT / "config" / "orderflow.json"

ESCRIBE_S = 10.0  # primera escritura de un minuto, desde su cierre
REESCRIBE_S = 70.0  # reescritura (si llegaron tardias) y cierre definitivo
SILENCIO_S = 60.0  # sin una sola operacion en la conexion (3 activos) durante esto: se da por muerta
FUTURO_MAX_S = 3600  # una operacion fechada mas alla de esto es basura, no un reloj adelantado
CINTA_TOPE = 300_000  # filas de cinta retenidas en memoria si la base no acepta; el resto se cuenta
ZERO = Decimal(0)
BASE_INVERSO = Decimal("1e-12")  # base derivada de un inverso (amount en USD / precio)
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


# --------------------------------------------------------------------------------------------- mercados
@dataclass(frozen=True)
class Mercado:
    """Un venue: como se conecta y que significa cada campo. Todo lo de unidades, tick y agresor se midio el
    2026-10-17 contra el endpoint publico de instrumentos de cada venue y contra 15 min de flujo real
    (entregas/<sello>-orderflow-dato.md, P1)."""

    venue: str
    mercado: str  # spot | perp
    url: str
    instrumentos: dict[str, str]  # activo -> instrumento como lo nombra el venue
    cotiza: str
    unidad: str
    agresor: str
    suscribir: str | None = None
    ping: str | None = None
    cada: float = 20.0
    multiplicador: dict[str, Decimal] = field(default_factory=dict)  # contratos -> base


def _streams_binance(base: str) -> str:
    return base + "/".join(f"{a.lower()}usdt@aggTrade" for a in ACTIVOS)


MERCADOS: dict[str, Mercado] = {
    m.venue: m
    for m in (
        Mercado(
            "binance_spot", "spot", _streams_binance("wss://stream.binance.com:9443/stream?streams="),
            {a: f"{a}USDT" for a in ACTIVOS}, "USDT", "q en base",
            "aggTrade m=true: el comprador es el MAKER, luego el agresor VENDE",
        ),
        Mercado(
            # SOLO por /market/stream: por /stream conecta y no entrega aggTrade (medido por el operador 10-17).
            "binance_usdm", "perp", _streams_binance("wss://fstream.binance.com/market/stream?streams="),
            {a: f"{a}USDT" for a in ACTIVOS}, "USDT", "q en base",
            "aggTrade m=true: el comprador es el MAKER, luego el agresor VENDE",
        ),
        Mercado(
            "bybit_spot", "spot", "wss://stream.bybit.com/v5/public/spot", {a: f"{a}USDT" for a in ACTIVOS},
            "USDT", "v en base", "publicTrade S = lado del TAKER",
            suscribir=json.dumps({"op": "subscribe", "args": [f"publicTrade.{a}USDT" for a in ACTIVOS]}),
            ping='{"op":"ping"}', cada=20,
        ),
        Mercado(
            "bybit_linear", "perp", "wss://stream.bybit.com/v5/public/linear", {a: f"{a}USDT" for a in ACTIVOS},
            "USDT", "v en base", "publicTrade S = lado del TAKER",
            suscribir=json.dumps({"op": "subscribe", "args": [f"publicTrade.{a}USDT" for a in ACTIVOS]}),
            ping='{"op":"ping"}', cada=20,
        ),
        Mercado(
            "okx_spot", "spot", "wss://ws.okx.com:8443/ws/v5/public", {a: f"{a}-USDT" for a in ACTIVOS},
            "USDT", "sz en base", "trades side = lado del TAKER",
            suscribir=json.dumps({"op": "subscribe", "args": [
                {"channel": "trades", "instId": f"{a}-USDT"} for a in ACTIVOS]}),
            ping="ping", cada=20,
        ),
        Mercado(
            # ponytail: ctVal fijo, leido de /api/v5/public/instruments el 2026-10-17; si OKX lo cambiara, el
            # volumen de okx_swap saldria multiplicado. Leerlo al arrancar si algun dia se mueve.
            "okx_swap", "perp", "wss://ws.okx.com:8443/ws/v5/public", {a: f"{a}-USDT-SWAP" for a in ACTIVOS},
            "USDT", "sz en CONTRATOS x ctVal (BTC 0.01, ETH 0.1, SOL 1)", "trades side = lado del TAKER",
            suscribir=json.dumps({"op": "subscribe", "args": [
                {"channel": "trades", "instId": f"{a}-USDT-SWAP"} for a in ACTIVOS]}),
            ping="ping", cada=20,
            multiplicador={"BTC": Decimal("0.01"), "ETH": Decimal("0.1"), "SOL": Decimal("1")},
        ),
        Mercado(
            "coinbase_spot", "spot", "wss://ws-feed.exchange.coinbase.com", {a: f"{a}-USD" for a in ACTIVOS},
            "USD", "size en base", "match side = lado del MAKER, luego el agresor es el CONTRARIO",
            suscribir=json.dumps({"type": "subscribe", "product_ids": [f"{a}-USD" for a in ACTIVOS],
                                  "channels": ["matches"]}),
        ),
        Mercado(
            "bitget_usdt", "perp", "wss://ws.bitget.com/v2/ws/public", {a: f"{a}USDT" for a in ACTIVOS},
            "USDT", "size en base", "trade side = lado del TAKER",
            suscribir=json.dumps({"op": "subscribe", "args": [
                {"instType": "USDT-FUTURES", "channel": "trade", "instId": f"{a}USDT"} for a in ACTIVOS]}),
            ping="ping", cada=25,
        ),
        Mercado(
            "deribit_perp", "perp", "wss://www.deribit.com/ws/api/v2",
            {"BTC": "BTC-PERPETUAL", "ETH": "ETH-PERPETUAL", "SOL": "SOL_USDC-PERPETUAL"},
            "USD (BTC, ETH) / USDC (SOL)",
            "amount en USD en los inversos BTC-PERPETUAL y ETH-PERPETUAL (base = amount / precio); en base en "
            "SOL_USDC-PERPETUAL",
            "trades direction = lado del TAKER",
            suscribir=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "public/subscribe", "params": {
                "channels": [f"trades.{i}.100ms" for i in
                             ("BTC-PERPETUAL", "ETH-PERPETUAL", "SOL_USDC-PERPETUAL")]}}),
            ping='{"jsonrpc":"2.0","id":9,"method":"public/test","params":{}}', cada=25,
        ),
    )
}
INVERSOS = {"BTC-PERPETUAL", "ETH-PERPETUAL"}


@dataclass(frozen=True, slots=True)
class Op:
    activo: str
    ts_ms: int
    precio: Decimal
    base: Decimal
    usd: Decimal
    compra: bool  # True = el agresor compro
    id: str


def _d(valor: object) -> Decimal:
    """Decimal desde el TEXTO (o desde el Decimal que ya dejo json con parse_float). Nunca desde un float."""
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, (str, int)) and not isinstance(valor, bool):
        return Decimal(valor)
    raise InvalidOperation(f"cantidad sin texto exacto: {valor!r}")


def _ms_iso(texto: str) -> int:
    momento = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    return (momento - EPOCH) // timedelta(milliseconds=1)


def interpreta(venue: str, raw: str | bytes) -> list[Op]:
    """Un mensaje crudo -> sus operaciones. Lo que no es una operacion (acks, pongs, la foto de Bitget al
    suscribirse, el last_match de Coinbase) devuelve []."""
    if raw in ("pong", b"pong"):
        return []
    m = MERCADOS[venue]
    msg = json.loads(raw, parse_float=Decimal)
    if not isinstance(msg, dict):
        return []
    activo_de = {inst: a for a, inst in m.instrumentos.items()}
    out: list[Op] = []
    if venue in ("binance_spot", "binance_usdm"):
        x = msg.get("data")
        if not isinstance(x, dict) or x.get("e") != "aggTrade" or x.get("s") not in activo_de:
            return []
        precio, base = _d(x["p"]), _d(x["q"])
        out.append(Op(activo_de[x["s"]], int(x["T"]), precio, base, precio * base, not x["m"], str(x["a"])))
    elif venue in ("bybit_spot", "bybit_linear"):
        if not str(msg.get("topic", "")).startswith("publicTrade."):
            return []
        for x in msg.get("data") or []:
            if x.get("s") not in activo_de:
                continue
            precio, base = _d(x["p"]), _d(x["v"])
            out.append(Op(activo_de[x["s"]], int(x["T"]), precio, base, precio * base, x["S"] == "Buy", str(x["i"])))
    elif venue in ("okx_spot", "okx_swap"):
        if (msg.get("arg") or {}).get("channel") != "trades":
            return []
        for x in msg.get("data") or []:
            activo = activo_de.get(x.get("instId"))
            if activo is None:
                continue
            precio = _d(x["px"])
            base = _d(x["sz"]) * m.multiplicador.get(activo, Decimal(1))
            out.append(Op(activo, int(x["ts"]), precio, base, precio * base, x["side"] == "buy", str(x["tradeId"])))
    elif venue == "coinbase_spot":
        # last_match es la ultima operacion ANTERIOR a la suscripcion: no es de esta conexion.
        if msg.get("type") != "match" or msg.get("product_id") not in activo_de:
            return []
        precio, base = _d(msg["price"]), _d(msg["size"])
        # side es el lado del MAKER: un maker que vende es un agresor que compra.
        out.append(Op(activo_de[msg["product_id"]], _ms_iso(msg["time"]), precio, base, precio * base,
                      msg["side"] == "sell", str(msg["trade_id"])))
    elif venue == "bitget_usdt":
        # La foto ("snapshot") al suscribirse trae operaciones de ANTES de esta conexion: se ignora.
        if msg.get("action") != "update":
            return []
        activo = activo_de.get((msg.get("arg") or {}).get("instId"))
        if activo is None:
            return []
        for x in msg.get("data") or []:
            precio, base = _d(x["price"]), _d(x["size"])
            out.append(Op(activo, int(x["ts"]), precio, base, precio * base, x["side"] == "buy", str(x["tradeId"])))
    elif venue == "deribit_perp":
        if msg.get("method") != "subscription":
            return []
        for x in (msg.get("params") or {}).get("data") or []:
            inst = x.get("instrument_name")
            activo = activo_de.get(inst)
            if activo is None:
                continue
            precio, cantidad = _d(x["price"]), _d(x["amount"])
            if inst in INVERSOS:
                usd, base = cantidad, (cantidad / precio).quantize(BASE_INVERSO)
            else:
                base, usd = cantidad, cantidad * precio
            out.append(Op(activo, int(x["timestamp"]), precio, base, usd, x["direction"] == "buy",
                          str(x["trade_id"])))
    return out


def nivel_de(precio: Decimal, paso: Decimal) -> Decimal:
    """Borde inferior del nivel que contiene `precio`: floor(precio/paso)*paso, exacto en Decimal."""
    return (precio / paso).to_integral_value(rounding=ROUND_FLOOR) * paso


def carga_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    datos = json.loads(path.read_text(encoding="utf-8"))
    umbral = {a: Decimal(str(datos["grandes_usd"][a])) for a in ACTIVOS}
    if any(v <= 0 for v in umbral.values()):
        raise ValueError("config/orderflow.json: un umbral de grandes no es positivo")
    return {"grandes_usd": umbral, "fuente": datos.get("fuente", "")}


# --------------------------------------------------------------------------------------------- cobertura
class Cobertura:
    """Los tramos en que la conexion de UN venue estuvo entregando. Un minuto esta completo (60) solo si un tramo
    lo cubre entero; si no, son los segundos enteros cubiertos (0-59). A diferencia de segundos_cubiertos() de
    ws_collector/scalp_collector, aqui una reconexion a mitad de minuto SI descuenta."""

    def __init__(self) -> None:
        self.tramos: list[list[float | None]] = []  # [desde, hasta|None]
        self.aperturas: list[float] = []
        self.primera = True

    def abre(self, t: float) -> None:
        if self.tramos and self.tramos[-1][1] is None:
            return
        self.tramos.append([t, None])
        if not self.primera:
            self.aperturas.append(t)
        self.primera = False

    def cierra(self, t: float) -> None:
        if self.tramos and self.tramos[-1][1] is None:
            desde = self.tramos[-1][0]
            self.tramos[-1][1] = max(t, desde)  # type: ignore[type-var]

    def abierta(self) -> bool:
        return bool(self.tramos) and self.tramos[-1][1] is None

    def segundos(self, minuto: int, ahora: float) -> int:
        fin = minuto + 60
        total = 0.0
        for desde, hasta in self.tramos:
            h = ahora if hasta is None else hasta
            if desde <= minuto and h >= fin:  # type: ignore[operator]
                return 60
            total += max(0.0, min(h, fin) - max(desde, minuto))  # type: ignore[type-var,arg-type]
        return min(59, int(total))

    def reconexiones(self, minuto: int) -> int:
        return sum(1 for t in self.aperturas if minuto <= t < minuto + 60)

    def poda(self, antes_de: float) -> None:
        self.tramos = [t for t in self.tramos if t[1] is None or t[1] >= antes_de]  # type: ignore[operator]
        self.aperturas = [t for t in self.aperturas if t >= antes_de]


# --------------------------------------------------------------------------------------------- almacen
@dataclass
class Minuto:
    celdas: dict[Decimal, list[Any]] = field(default_factory=dict)  # nivel -> [cb, vb, cu, vu, nc, nv]
    ids: set[str] = field(default_factory=set)
    ops: int = 0
    tardias: int = 0
    escrito: bool = False
    sucio: bool = False
    segundos: int | None = None


class Almacen:
    """Solo los minutos ABIERTOS (hasta REESCRIBE_S tras su cierre) viven en memoria; la cinta, hasta su lote."""

    def __init__(self, pasos: dict[str, Decimal], umbral: dict[str, Decimal], inicio: float) -> None:
        self.pasos = pasos
        self.umbral = umbral
        self.minutos: dict[tuple[str, str, int], Minuto] = {}
        self.cinta: list[tuple[Any, ...]] = []
        self.grandes: list[tuple[Any, ...]] = []
        self.fuera: dict[tuple[str, str, int], int] = defaultdict(int)
        self.coberturas = {v: Cobertura() for v in MERCADOS}
        # El primer minuto con fila de cobertura es el del arranque (sale incompleto y se declara).
        self.primer_minuto = int(inicio) // 60 * 60
        self.proximo_primera = self.primer_minuto
        self.proximo_final = self.primer_minuto
        self.duplicadas = 0
        self.descartadas = 0
        self.perdidas_cinta = 0

    def anade(self, venue: str, ops: list[Op], ahora: float) -> None:
        for op in ops:
            if op.precio <= 0 or op.base <= 0 or op.usd <= 0 or not op.precio.is_finite():
                self.descartadas += 1
                continue
            minuto = op.ts_ms // 60_000 * 60
            if minuto > ahora + FUTURO_MAX_S or minuto < ahora - 86_400:
                self.descartadas += 1
                continue
            clave = (venue, op.activo, minuto)
            if minuto < self.primer_minuto:
                self.descartadas += 1  # es de antes de este proceso: su minuto lo declara el arranque
                continue
            if minuto < self.proximo_final or ahora >= minuto + 60 + REESCRIBE_S:
                # Su minuto ya se cerro: no entra en las celdas ni en la cinta, solo se cuenta.
                self.fuera[clave] += 1
                continue
            mi = self.minutos.get(clave)
            if mi is None:
                mi = self.minutos[clave] = Minuto()
            if op.id in mi.ids:
                self.duplicadas += 1
                continue
            mi.ids.add(op.id)
            nivel = nivel_de(op.precio, self.pasos[op.activo])
            c = mi.celdas.get(nivel)
            if c is None:
                c = mi.celdas[nivel] = [ZERO, ZERO, ZERO, ZERO, 0, 0]
            if op.compra:
                c[0] += op.base
                c[2] += op.usd
                c[4] += 1
            else:
                c[1] += op.base
                c[3] += op.usd
                c[5] += 1
            mi.ops += 1
            if mi.escrito:
                mi.tardias += 1
                mi.sucio = True
            fila = (EPOCH + timedelta(milliseconds=op.ts_ms), venue, op.activo, op.precio, op.base, op.usd,
                    op.compra, op.id)
            if len(self.cinta) < CINTA_TOPE:
                self.cinta.append(fila)
            else:
                self.perdidas_cinta += 1
            if op.usd >= self.umbral[op.activo]:
                self.grandes.append((*fila, self.umbral[op.activo]))


# --------------------------------------------------------------------------------------------- escritura
GAP_SQL = """
WITH ext AS (
  UPDATE data_gap SET end_ts=$6
   WHERE feed='orderflow' AND exchange=$1 AND market=$2 AND symbol=$3 AND granularity='event'
     AND evidence_type=$4 AND detection_source='app.orderflow' AND status='unrecoverable' AND end_ts=$5
  RETURNING id
)
INSERT INTO data_gap(feed,feed_class,exchange,market,symbol,granularity,start_ts,end_ts,evidence_type,
                     detection_reason,detection_source,status,resolved_at,resolution_reason,recovery_metadata)
SELECT 'orderflow','event_stream',$1,$2,$3,'event',$5,$6,$4,$7,'app.orderflow','unrecoverable',now(),
       'decision OF-1: un flujo de operaciones no se rellena; el minuto queda declarado incompleto',
       '{"method": "orderflow_sin_cobertura", "tabla": "orderflow_cobertura"}'::jsonb
 WHERE NOT EXISTS (SELECT 1 FROM ext)
ON CONFLICT DO NOTHING
"""


def _ts(segundos: int) -> datetime:
    return datetime.fromtimestamp(segundos, UTC)


async def declara_hueco(conn: asyncpg.Connection, venue: str, activo: str, desde: int, hasta: int,
                        evidencia: str, motivo: str) -> None:
    """[desde, hasta) en segundos de epoch, alineado a minuto. Un hueco contiguo al anterior del mismo tipo lo
    alarga en vez de abrir otra fila: un venue caido un dia es UNA fila por activo, no 1440."""
    await conn.execute(GAP_SQL, venue, MERCADOS[venue].mercado, activo, evidencia, _ts(desde), _ts(hasta),
                       motivo[:500])


async def escribe_minutos(conn: asyncpg.Connection, alm: Almacen, minutos: list[int], ahora: float,
                          final: bool, inicio: float) -> list[tuple[str, str, int, int]]:
    """Celdas (DELETE + INSERT) y cobertura (upsert) de cada (venue, activo) en esos minutos. Devuelve los que
    hay que declarar como huecos: (venue, activo, minuto, segundos)."""
    borrar, celdas, cobertura, huecos = [], [], [], []
    for minuto in minutos:
        for venue, cob in alm.coberturas.items():
            seg = cob.segundos(minuto, ahora)
            rec = cob.reconexiones(minuto)
            for activo in ACTIVOS:
                mi = alm.minutos.get((venue, activo, minuto))
                ts = _ts(minuto)
                if mi is not None and (not final or not mi.escrito or mi.sucio or mi.segundos != seg):
                    borrar.append((activo, ts, venue))
                    for nivel, (cb, vb, cu, vu, nc, nv) in mi.celdas.items():
                        celdas.append((ts, venue, activo, nivel, cb, vb, cu, vu, nc, nv))
                cobertura.append((ts, venue, activo, seg, mi.ops if mi else 0, mi.tardias if mi else 0, rec,
                                  final))
                if final and seg < 60:
                    huecos.append((venue, activo, minuto, seg))
    if borrar:
        await conn.executemany(
            "DELETE FROM orderflow_celda WHERE symbol=$1 AND ts=$2 AND venue=$3", borrar)
    if celdas:
        await conn.execute(
            """INSERT INTO orderflow_celda(ts,venue,symbol,nivel,compra_base,venta_base,compra_usd,venta_usd,
                                           compras,ventas)
               SELECT * FROM unnest($1::timestamptz[],$2::text[],$3::text[],$4::numeric[],$5::numeric[],
                                    $6::numeric[],$7::numeric[],$8::numeric[],$9::int[],$10::int[])""",
            *map(list, zip(*celdas, strict=True)))
    await conn.execute(
        """INSERT INTO orderflow_cobertura(ts,venue,symbol,segundos,operaciones,tardias,reconexiones,definitivo)
           SELECT * FROM unnest($1::timestamptz[],$2::text[],$3::text[],$4::smallint[],$5::int[],$6::int[],
                                $7::smallint[],$8::bool[])
           ON CONFLICT (symbol,ts,venue) DO UPDATE SET
             segundos=EXCLUDED.segundos, operaciones=EXCLUDED.operaciones, tardias=EXCLUDED.tardias,
             reconexiones=EXCLUDED.reconexiones, definitivo=EXCLUDED.definitivo, escrito=now()""",
        *map(list, zip(*cobertura, strict=True)))
    for venue, activo, minuto, seg in huecos:
        evidencia = "collector_outage" if minuto < inicio else "disconnect"
        await declara_hueco(conn, venue, activo, minuto, minuto + 60, evidencia,
                            f"orderflow: minuto con {seg} s de 60 cubiertos por la conexion de {venue}")
    return huecos


async def vuelca(pool: asyncpg.Pool, own: ServiceOwnership | None, alm: Almacen, ahora: float, inicio: float,
                 *, apagando: bool = False) -> None:
    """Un lote: la cinta y las grandes acumuladas, los minutos que tocan (primera escritura a ESCRIBE_S, final a
    REESCRIBE_S; al apagar, todos los cerrados) y las tardias fuera de plazo. Todo o nada: si la base falla,
    nada se da por escrito y el siguiente lote lo reintenta."""
    limite_primera = int(ahora - ESCRIBE_S - 60) // 60 * 60
    limite_final = int(ahora - REESCRIBE_S - 60) // 60 * 60
    if apagando:
        limite_primera = limite_final = int(ahora - 60) // 60 * 60
    primeras = list(range(alm.proximo_primera, limite_primera + 60, 60))
    finales = list(range(alm.proximo_final, limite_final + 60, 60))
    cinta, grandes, fuera = alm.cinta, alm.grandes, dict(alm.fuera)
    alm.cinta, alm.grandes = [], []
    try:
        async with pool.acquire() as conn:
            async with fenced_transaction(conn, own):
                if cinta:
                    await conn.execute(
                        """INSERT INTO orderflow_cinta(ts,venue,symbol,precio,base,usd,compra,id)
                           SELECT * FROM unnest($1::timestamptz[],$2::text[],$3::text[],$4::numeric[],
                                                $5::numeric[],$6::numeric[],$7::bool[],$8::text[])""",
                        *map(list, zip(*cinta, strict=True)))
                if grandes:
                    await conn.execute(
                        """INSERT INTO orderflow_grande(ts,venue,symbol,precio,base,usd,compra,id,umbral_usd)
                           SELECT * FROM unnest($1::timestamptz[],$2::text[],$3::text[],$4::numeric[],
                                                $5::numeric[],$6::numeric[],$7::bool[],$8::text[],$9::numeric[])
                           ON CONFLICT DO NOTHING""",
                        *map(list, zip(*grandes, strict=True)))
                solo_primera = sorted(set(primeras) - set(finales))
                if solo_primera:
                    await escribe_minutos(conn, alm, solo_primera, ahora, final=False, inicio=inicio)
                if finales:
                    await escribe_minutos(conn, alm, finales, ahora, final=True, inicio=inicio)
                if fuera:
                    await conn.executemany(
                        "UPDATE orderflow_cobertura SET fuera=fuera+$4 WHERE symbol=$2 AND ts=$3 AND venue=$1",
                        [(v, a, _ts(m), n) for (v, a, m), n in fuera.items()])
    except ServiceOwnershipLost:
        raise
    except Exception:
        # Nada se dio por escrito: la cinta vuelve delante de lo que llego mientras tanto.
        alm.cinta = cinta + alm.cinta
        alm.grandes = grandes + alm.grandes
        if len(alm.cinta) > CINTA_TOPE:
            alm.perdidas_cinta += len(alm.cinta) - CINTA_TOPE
            del alm.cinta[: len(alm.cinta) - CINTA_TOPE]
        LOGGER.exception("orderflow_flush_failed cinta=%d minutos=%d", len(alm.cinta), len(alm.minutos))
        return
    for clave, n in fuera.items():
        alm.fuera[clave] -= n
        if alm.fuera[clave] <= 0:
            del alm.fuera[clave]
    for minuto in primeras:
        for (v, _a, m), mi in alm.minutos.items():
            if m == minuto:
                mi.escrito, mi.sucio = True, False
                mi.segundos = alm.coberturas[v].segundos(m, ahora)
    if primeras:
        alm.proximo_primera = primeras[-1] + 60
    if finales:
        alm.proximo_final = finales[-1] + 60
        cerrados = set(finales)
        alm.minutos = {k: v for k, v in alm.minutos.items() if k[2] not in cerrados}
        for cob in alm.coberturas.values():
            cob.poda(alm.proximo_final - 120)


async def declara_parada_anterior(pool: asyncpg.Pool, own: ServiceOwnership | None, inicio: float) -> int:
    """Al arrancar, dos cosas que el proceso anterior no pudo cerrar:
    - los minutos que llego a escribir una vez (definitivo=false) pero no a cerrar: ya nadie los va a
      reescribir; se cierran tal como estan y, si estaban incompletos, se declaran;
    - lo que va de su ultimo minuto escrito hasta este arranque no lo escucho nadie: se declara
      (collector_outage), no se rellena. Sin filas previas no hay nada que declarar."""
    primero = int(inicio) // 60 * 60
    declarados = 0
    async with pool.acquire() as conn:
        async with fenced_transaction(conn, own):
            pendientes = await conn.fetch(
                "UPDATE orderflow_cobertura SET definitivo=true WHERE NOT definitivo "
                "RETURNING venue, symbol, ts, segundos")
            # En orden: un hueco contiguo al anterior del mismo tipo lo alarga.
            for fila in sorted(pendientes, key=lambda f: (f["venue"], f["symbol"], f["ts"])):
                if fila["segundos"] < 60 and fila["venue"] in MERCADOS:
                    desde = int(fila["ts"].timestamp())
                    await declara_hueco(conn, fila["venue"], fila["symbol"], desde, desde + 60, "collector_outage",
                                        f"orderflow: minuto con {fila['segundos']} s de 60 que el proceso anterior "
                                        "no llego a cerrar")
                    declarados += 1
        ultimos = await conn.fetch(
            "SELECT venue, symbol, max(ts) AS ultimo FROM orderflow_cobertura GROUP BY 1, 2")
        async with fenced_transaction(conn, own):
            for fila in ultimos:
                if fila["venue"] not in MERCADOS:
                    continue
                desde = int(fila["ultimo"].timestamp()) + 60
                if desde < primero:
                    await declara_hueco(conn, fila["venue"], fila["symbol"], desde, primero, "collector_outage",
                                        "orderflow: el servicio no corria; nadie escucho esos minutos")
                    declarados += 1
    return declarados


# --------------------------------------------------------------------------------------------- conexiones
class Silencio(Exception):
    pass


async def _pinga(ws: Any, texto: str, cada: float) -> None:
    with contextlib.suppress(Exception):  # si la conexion muere, la cierra el bucle de lectura, no este
        while True:
            await asyncio.sleep(cada)
            await ws.send(texto)


async def escucha(venue: str, alm: Almacen, salud: dict[str, Any]) -> None:
    """Una conexion por venue con sus tres activos. Reconecta con espera exponencial y jitter. La cobertura
    empieza con el primer mensaje tras suscribirse y termina al cerrarse la conexion, o -si se queda muda
    SILENCIO_S- en la ultima operacion recibida: una conexion abierta que no entrega no cubre nada."""
    m = MERCADOS[venue]
    cob = alm.coberturas[venue]
    intento = 0
    while True:
        conectado = time.time()
        ultimo = conectado
        try:
            async with connect(m.url, open_timeout=30, close_timeout=5, ping_interval=20, ping_timeout=20,
                               max_size=4_000_000, max_queue=1024) as ws:
                if m.suscribir:
                    await ws.send(m.suscribir)
                pinger = asyncio.create_task(_pinga(ws, m.ping, m.cada)) if m.ping else None
                LOGGER.info("orderflow_connected venue=%s", venue)
                try:
                    while True:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=5)
                        except TimeoutError:
                            raw = None
                        ahora = time.time()
                        if raw is not None:
                            cob.abre(ahora)
                            try:
                                ops = interpreta(venue, raw)
                            except Exception:  # noqa: BLE001
                                salud["mal_formados"][venue] += 1
                                ops = []
                            if ops:
                                ultimo = ahora
                                alm.anade(venue, ops, ahora)
                                salud["ultimo"][venue] = ahora
                        if ahora - ultimo > SILENCIO_S:
                            raise Silencio(f"{venue} sin una operacion en {SILENCIO_S:.0f} s")
                finally:
                    if pinger is not None:
                        pinger.cancel()
        except asyncio.CancelledError:
            cob.cierra(time.time())
            raise
        except Silencio as exc:
            cob.cierra(ultimo)
            LOGGER.warning("orderflow_silencio venue=%s %s", venue, exc)
        except Exception as exc:  # noqa: BLE001
            cob.cierra(time.time())
            LOGGER.warning("orderflow_disconnected venue=%s error=%s code=%s", venue, type(exc).__name__,
                           getattr(exc, "code", None))
        salud["caidas"][venue] += 1
        intento = 0 if time.time() - conectado > 60 else intento + 1
        await asyncio.sleep(min(60.0, 2.0 ** intento) * random.uniform(0.5, 1.0))


# --------------------------------------------------------------------------------------------- bucles
async def escritor(pool: asyncpg.Pool, own: ServiceOwnership | None, alm: Almacen, inicio: float,
                   salud: dict[str, Any]) -> None:
    while True:
        await asyncio.sleep(1.0)
        await vuelca(pool, own, alm, time.time(), inicio)
        salud["escrito"] = time.time()


def estado(alm: Almacen, salud: dict[str, Any], ahora: float) -> tuple[str, str]:
    abajo = [v for v, c in alm.coberturas.items() if not c.abierta()]
    viejo = ahora - salud.get("escrito", 0.0) > 30
    status = "ok" if not abajo and not viejo else "degraded"
    detail = (
        f"venues={len(MERCADOS) - len(abajo)}/{len(MERCADOS)}"
        f"{' abajo=' + ','.join(abajo) if abajo else ''} escritor={'parado' if viejo else 'ok'} "
        f"minutos_abiertos={len(alm.minutos)} cinta_pendiente={len(alm.cinta)} duplicadas={alm.duplicadas} "
        f"descartadas={alm.descartadas} perdidas_cinta={alm.perdidas_cinta} "
        f"caidas={sum(salud['caidas'].values())} mal_formados={sum(salud['mal_formados'].values())}"
    )
    return status, detail[:500]


async def latido(pool: asyncpg.Pool, own: ServiceOwnership, alm: Almacen, salud: dict[str, Any]) -> None:
    while True:
        await asyncio.sleep(20)
        try:
            status, detail = estado(alm, salud, time.time())
            async with pool.acquire() as conn:
                await heartbeat_owned(conn, own, SERVICIO, status=status, detail=detail)
        except ServiceOwnershipLost:
            raise
        except Exception:
            LOGGER.exception("orderflow_heartbeat_failed")


async def poda(pool: asyncpg.Pool, own: ServiceOwnership) -> None:
    """La retencion, cada hora, por el mecanismo que ya existe: las dos tablas particionadas por
    apply_temporal_retention (tira particiones enteras y recorta la del borde); las dos planas con DELETE.
    La cobertura INCOMPLETA no se poda: es la prueba que K04 re-deriva para los huecos declarados."""
    s = get_settings()
    while True:
        await asyncio.sleep(60)
        try:
            async with pool.acquire() as conn:
                async with fenced_transaction(conn, own):
                    await conn.execute("SET LOCAL statement_timeout = '300s'")
                    await apply_temporal_retention(conn, "orderflow_cinta", s.ORDERFLOW_TAPE_RETENTION_HOURS)
                    await apply_temporal_retention(conn, "orderflow_celda", s.ORDERFLOW_CELL_RETENTION_DAYS * 24)
                    await conn.execute("DELETE FROM orderflow_grande WHERE ts < now() - make_interval(days => $1)",
                                       s.ORDERFLOW_LARGE_RETENTION_DAYS)
                    await conn.execute(
                        "DELETE FROM orderflow_cobertura WHERE segundos = 60 AND ts < now() - make_interval(days => $1)",
                        s.ORDERFLOW_CELL_RETENTION_DAYS)
        except ServiceOwnershipLost:
            raise
        except Exception:
            LOGGER.exception("orderflow_retention_failed")
        await asyncio.sleep(3540)


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)
    config = carga_config()
    own = await acquire_service_lock(settings, SERVICIO)
    pool = await create_pool(settings, application_name="coinalyze-orderflow", ownership=own)
    inicio = time.time()
    try:
        async with pool.acquire() as conn:
            pasos = {r["symbol"]: Decimal(r["paso"]) for r in await conn.fetch(
                "SELECT symbol, paso::text AS paso FROM orderflow_paso")}
        faltan = set(ACTIVOS) - set(pasos)
        if faltan:
            raise RuntimeError(f"orderflow_paso no tiene paso para {sorted(faltan)}: falta aplicar el esquema")
        alm = Almacen(pasos, config["grandes_usd"], inicio)
        declarados = await declara_parada_anterior(pool, own, inicio)
        LOGGER.info("orderflow_start pasos=%s umbrales=%s parada_anterior_declarada=%d",
                    {k: str(v) for k, v in pasos.items()}, {k: str(v) for k, v in config["grandes_usd"].items()},
                    declarados)
    except BaseException:
        await pool.close()
        await own.close()
        raise
    salud: dict[str, Any] = {"ultimo": {}, "caidas": defaultdict(int), "mal_formados": defaultdict(int)}
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    lock_monitor = asyncio.create_task(monitor_service_lock(own), name="service-lock")
    tareas = [
        asyncio.create_task(escritor(pool, own, alm, inicio, salud), name="escritor"),
        asyncio.create_task(latido(pool, own, alm, salud), name="latido"),
        asyncio.create_task(poda(pool, own), name="poda"),
        *(asyncio.create_task(escucha(v, alm, salud), name=v) for v in MERCADOS),
    ]
    try:
        await wait_for_stop_or_lock_loss(stop, lock_monitor, critical_tasks=tuple(tareas))
    finally:
        # El instante en que se deja de escuchar, ANTES de cancelar nada: la cobertura acaba aqui.
        parando = time.time()
        for cob in alm.coberturas.values():
            cob.cierra(parando)
        for tarea in tareas:
            tarea.cancel()
        lock_monitor.cancel()
        await asyncio.gather(*tareas, lock_monitor, return_exceptions=True)
        try:
            # Los minutos CERRADOS se escriben con su cobertura final; el que estaba en curso se pierde y lo
            # declara el proximo arranque. Escribirlo seria publicar media muestra como si fuera el minuto.
            await vuelca(pool, own, alm, parando, inicio, apagando=True)
        except Exception:
            LOGGER.exception("orderflow_drain_failed")
        await pool.close()
        await own.close()


if __name__ == "__main__":
    asyncio.run(run())
