"""OF-4a · EL DATO DEL LIBRO (campana 144): `python -m app.libro`.

El libro de ordenes de nueve mercados -spot y perpetuos de Binance, Bybit y OKX, Coinbase spot, Bitget USDT y Deribit-
para BTC, ETH y SOL, reconstruido en local con la NUMERACION de cada venue, y guardado de dos formas:

  libro_foto       cada FOTO_S segundos (rejilla UTC), por venue y activo con libro VALIDO: la mejor compra y la mejor
                   venta EXACTAS, la hora del venue del ultimo cambio aplicado y las cantidades (en unidades del activo)
                   por nivel al paso de agregacion PASOS, desde el mejor nivel hacia fuera, hasta BANDA niveles por lado
                   o hasta el ALCANCE del libro, lo que llegue antes. Nunca cada cambio.
  libro_cobertura  por minuto, venue y activo: segundos con libro valido, fotos, saltos de numeracion,
                   resincronizaciones y reconexiones. Un minuto con menos de 60 s se declara en data_gap y nunca se
                   rellena.

Y lo publica EN VIVO por NOTIFY (canal CANAL) para que la API lo sirva por websocket: la escalera de cada libro valido
al paso base de OF-1, hasta RELEVO_NIVELES niveles por lado, como mucho cada RELEVO_S.

UN LIBRO ES VALIDO cuando esta sincronizado con su numeracion (foto + diferencias, sin un salto desde entonces), su
conexion entrega y no esta cruzado. Un salto, un libro cruzado o un libro que se sale de su alcance lo INVALIDAN: deja
de fotografiarse y de publicarse, ese tiempo no cuenta como cobertura y se resincroniza (foto REST nueva en Binance,
suscribirse otra vez en los demas, reconectar en Coinbase, cuya numeracion es de la conexion). Las reglas de cada
venue se midieron el 2026-10-17 sobre 5 min de los nueve flujos (entregas/<sello>-libro-dato.md, P1).

EL ALCANCE de un lado es hasta donde el libro se conoce de verdad. En los que el venue mantiene por websocket (los N
mejores niveles, o el libro entero) es su nivel mas profundo. En Binance, que da una foto REST y diferencias de TODO el
libro, es el nivel mas profundo de la FOTO, fijo en precio: mas alla solo se conocerian los niveles que hayan cambiado,
asi que las diferencias de fuera se ignoran. Una foto REST nueva lo vuelve a centrar sin dejar de servir el libro viejo.
Un nivel que el alcance corta por la mitad no se guarda: nunca un nivel a medio conocer.

EL NIVEL es el borde INFERIOR, floor(precio / paso) * paso en Decimal, como en OF-1 (app/orderflow.py: nivel_de).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import random
import signal
import time
from bisect import bisect_left, insort
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import asyncpg
import httpx
from websockets.asyncio.client import connect

from app.config import get_settings
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
from app.orderflow import Cobertura, nivel_de
from app.partitioning import apply_temporal_retention

LOGGER = logging.getLogger(__name__)
SERVICIO = "libro"
CANAL = "libro"  # NOTIFY: el relevo en vivo hacia la API
ACTIVOS = ("BTC", "ETH", "SOL")

# P2 (campana 144): lo decide lo que ocupa una foto medida contra los flujos reales. Ver la entrega.
FOTO_S = 5  # una foto por venue y activo cada FOTO_S segundos, en la rejilla UTC
PASOS = {"BTC": Decimal("10"), "ETH": Decimal("0.5"), "SOL": Decimal("0.02")}  # multiplos del paso base de OF-1
BANDA = {"BTC": 80, "ETH": 50, "SOL": 50}  # niveles por lado, como mucho: ~ +-1 % del precio del 2026-10-17

RELEVO_S = 0.25
RELEVO_NIVELES = 100  # por lado, al paso BASE de OF-1
CARGA_MAX = 7900  # bytes de un NOTIFY: el tope de postgres es 8000
SILENCIO_S = 30.0  # la conexion que no entrega ni un mensaje en esto se da por muerta
CIERRE_S = 2.0  # un minuto se escribe (fotos + cobertura + huecos, juntos) a los CIERRE_S de cerrarse
RETRASO_MAX_S = 1.0  # el fotografo que despierta mas tarde que esto no fotografia: ese tiempo no se cubre
MINUTOS_TOPE = 30  # minutos sin escribir que se guardan en memoria si la base no acepta; el resto se declara
REFRESCO_S, REFRESCO_MIN_S = 600.0, 30.0  # Binance: foto REST nueva cada 10 min, o antes si el alcance se gasta
BUFFER_TOPE = 3000  # diferencias de Binance esperando su foto REST
BASE_INVERSO = Decimal("1e-12")  # base derivada de un inverso de Deribit (cantidad en USD / precio)
ZERO = Decimal(0)
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


# --------------------------------------------------------------------------------------------- mercados
@dataclass(frozen=True)
class Venue:
    """Un venue: como se conecta, su canal de libro, su numeracion y la unidad de sus cantidades."""

    venue: str
    mercado: str  # spot | perp
    familia: str  # binance | bybit | okx | bitget | deribit | coinbase
    url: str
    instrumentos: dict[str, str]
    canal: str
    numeracion: str
    unidad: str
    ping: str | None = None
    cada: float = 20.0
    rest: str | None = None  # Binance: la foto REST, con {inst}
    multiplicador: dict[str, Decimal] = field(default_factory=dict)  # contratos -> base


def _binance(dominio: str, ruta: str) -> str:
    return f"wss://{dominio}/{ruta}?streams=" + "/".join(f"{a.lower()}usdt@depth@100ms" for a in ACTIVOS)


VENUES: dict[str, Venue] = {
    v.venue: v
    for v in (
        Venue("binance_usdm", "perp", "binance", _binance("fstream.binance.com", "public/stream"),
              {a: f"{a}USDT" for a in ACTIVOS},
              "<s>@depth@100ms por /public/stream (por /market/stream no llega) + foto REST /fapi/v1/depth limit=1000",
              "descartar u < lastUpdateId; la primera cumple U <= lastUpdateId <= u; despues pu == u anterior",
              "cantidad en base", rest="https://fapi.binance.com/fapi/v1/depth?symbol={inst}&limit=1000"),
        Venue("binance_spot", "spot", "binance", _binance("stream.binance.com:9443", "stream"),
              {a: f"{a}USDT" for a in ACTIVOS},
              "<s>@depth@100ms por /stream + foto REST /api/v3/depth limit=5000",
              "descartar u <= lastUpdateId; la primera cumple U <= lastUpdateId + 1 <= u; despues U == u anterior + 1",
              "cantidad en base", rest="https://api.binance.com/api/v3/depth?symbol={inst}&limit=5000"),
        Venue("bybit_linear", "perp", "bybit", "wss://stream.bybit.com/v5/public/linear",
              {a: f"{a}USDT" for a in ACTIVOS}, "orderbook.1000.<s> (foto y deltas, ~5 mensajes/s, 1000 niveles)",
              "snapshot reinicia; cada delta u == u anterior + 1", "cantidad en base",
              ping='{"op":"ping"}', cada=20),
        Venue("bybit_spot", "spot", "bybit", "wss://stream.bybit.com/v5/public/spot",
              {a: f"{a}USDT" for a in ACTIVOS}, "orderbook.1000.<s> (foto y deltas, ~4-5 mensajes/s, 1000 niveles)",
              "snapshot reinicia; cada delta u == u anterior + 1", "cantidad en base",
              ping='{"op":"ping"}', cada=20),
        Venue("okx_swap", "perp", "okx", "wss://ws.okx.com:8443/ws/v5/public",
              {a: f"{a}-USDT-SWAP" for a in ACTIVOS}, "books (foto y updates, 400 niveles, ~10 mensajes/s)",
              "snapshot reinicia; cada update prevSeqId == seqId anterior (el checksum llega a 0: no se usa)",
              "CONTRATOS x ctVal (BTC 0.01, ETH 0.1, SOL 1)", ping="ping", cada=20,
              # ponytail: ctVal fijo, el mismo que app/orderflow.py leyo de /api/v5/public/instruments el 2026-10-17
              multiplicador={"BTC": Decimal("0.01"), "ETH": Decimal("0.1"), "SOL": Decimal("1")}),
        Venue("okx_spot", "spot", "okx", "wss://ws.okx.com:8443/ws/v5/public",
              {a: f"{a}-USDT" for a in ACTIVOS}, "books (foto y updates, 400 niveles, ~6-7 mensajes/s)",
              "snapshot reinicia; cada update prevSeqId == seqId anterior (el checksum llega a 0: no se usa)",
              "cantidad en base", ping="ping", cada=20),
        Venue("bitget_usdt", "perp", "bitget", "wss://ws.bitget.com/v2/ws/public",
              {a: f"{a}USDT" for a in ACTIVOS}, "books USDT-FUTURES (foto y updates; 500 niveles BTC/ETH, 200 SOL)",
              "snapshot reinicia; cada update pseq == seq anterior", "cantidad en base", ping="ping", cada=25),
        Venue("deribit_perp", "perp", "deribit", "wss://www.deribit.com/ws/api/v2",
              {"BTC": "BTC-PERPETUAL", "ETH": "ETH-PERPETUAL", "SOL": "SOL_USDC-PERPETUAL"},
              "book.<inst>.100ms (foto y cambios del libro entero, ~3 mensajes/s)",
              "snapshot reinicia; cada change prev_change_id == change_id anterior",
              "USD en los inversos BTC-PERPETUAL y ETH-PERPETUAL (base = cantidad / precio del nivel); SOL en base",
              ping='{"jsonrpc":"2.0","id":9,"method":"public/test","params":{}}', cada=25),
        Venue("coinbase_spot", "spot", "coinbase", "wss://advanced-trade-ws.coinbase.com",
              {a: f"{a}-USD" for a in ACTIVOS},
              "level2 de Advanced Trade, sin autenticacion (el level2 de ws-feed.exchange la pide); libro entero",
              "sequence_num de la CONEXION: cada mensaje == anterior + 1; un salto invalida los tres libros",
              "cantidad en base"),
    )
}
INVERSOS = {"BTC-PERPETUAL", "ETH-PERPETUAL"}


# --------------------------------------------------------------------------------------------- el libro local
class Lado:
    """Un lado del libro: precio -> cantidad, y los precios ordenados (ascendente) para no ordenar en cada foto."""

    __slots__ = ("p", "q")

    def __init__(self) -> None:
        self.q: dict[Decimal, Decimal] = {}
        self.p: list[Decimal] = []

    def carga(self, pares: dict[Decimal, Decimal]) -> None:
        self.q = {p: c for p, c in pares.items() if c > 0}
        self.p = sorted(self.q)

    def pon(self, precio: Decimal, cantidad: Decimal) -> None:
        if cantidad < 0 or precio <= 0:
            raise ValueError(f"nivel imposible: {precio} {cantidad}")
        if cantidad == 0:
            if self.q.pop(precio, None) is not None:
                del self.p[bisect_left(self.p, precio)]
            return
        if precio not in self.q:
            insort(self.p, precio)
        self.q[precio] = cantidad


class Libro:
    """El libro de UN venue y activo, con su estado de sincronizacion y su cobertura."""

    def __init__(self, venue: str, activo: str) -> None:
        self.venue, self.activo = venue, activo
        self.compras, self.ventas = Lado(), Lado()
        self.valido = False
        self.motivo = "sin sincronizar"
        self.seq: int | None = None
        self.ts_ms = 0  # hora del VENUE del ultimo cambio aplicado
        self.rx_ms = 0  # hora de recepcion de ese cambio (reloj del colector)
        self.alcance: tuple[Decimal, Decimal] | None = None  # FIJO (foto REST): la compra y la venta mas profundas
        self.cob = Cobertura()
        self.saltos: defaultdict[int, int] = defaultdict(int)  # minuto -> saltos de numeracion
        self.resyncs: defaultdict[int, int] = defaultdict(int)  # minuto -> invalidaciones
        self.causas: defaultdict[int, set[str]] = defaultdict(set)  # minuto -> evidencias
        self.cambiado = True  # para el relevo: algo que publicar
        self.resuscribir = False
        # Binance: diferencias a la espera de su foto REST, y el refresco del alcance
        self.buffer: list[dict[str, Any]] = []
        self.foto_rest: dict[str, Any] | None = None
        self.refresco: list[dict[str, Any]] | None = None
        self.foto_refresco: dict[str, Any] | None = None
        self.pidiendo = False
        self.refrescado = 0.0
        self.alcance_inicial: tuple[Decimal, Decimal] = (ZERO, ZERO)  # lo que quedaba de cada lado al casar la foto

    def valida(self, ahora: float) -> None:
        if not self.valido:
            self.valido, self.motivo = True, ""
            self.cob.abre(ahora)
        self.cambiado = True

    def invalida(self, ahora: float, motivo: str, evidencia: str) -> None:
        minuto = int(ahora) // 60 * 60
        if self.valido:
            self.cob.cierra(ahora)
            self.resyncs[minuto] += 1
        if evidencia == "sequence_discontinuity":
            self.saltos[minuto] += 1
        self.causas[minuto].add(evidencia)
        self.valido, self.motivo = False, motivo[:200]
        self.seq, self.alcance = None, None
        self.compras, self.ventas = Lado(), Lado()
        self.buffer, self.foto_rest, self.refresco, self.foto_refresco = [], None, None, None
        self.cambiado = self.resuscribir = True  # Binance pide otra foto REST; los demas, suscribirse otra vez
        LOGGER.warning("libro_invalido venue=%s activo=%s motivo=%s", self.venue, self.activo, self.motivo)

    def carga(self, compras: dict[Decimal, Decimal], ventas: dict[Decimal, Decimal], seq: int | None, ts_ms: int,
              rx_ms: int) -> None:
        self.compras.carga(compras)
        self.ventas.carga(ventas)
        self.seq, self.ts_ms, self.rx_ms = seq, ts_ms, rx_ms
        self.cambiado = True

    def pon(self, lado: str, precio: Decimal, cantidad: Decimal) -> None:
        if self.alcance is not None and (  # Binance: fuera de la foto REST no se conoce el libro
                (lado == "b" and precio < self.alcance[0]) or (lado == "a" and precio > self.alcance[1])):
            return
        (self.compras if lado == "b" else self.ventas).pon(precio, cantidad)

    def mejores(self) -> tuple[Decimal, Decimal] | None:
        if not self.compras.p or not self.ventas.p:
            return None
        return self.compras.p[-1], self.ventas.p[0]

    def alcances(self) -> tuple[Decimal, Decimal]:
        """(precio mas bajo hasta el que se conoce la compra, precio mas alto hasta el que se conoce la venta)."""
        if self.alcance is not None:
            return self.alcance
        return self.compras.p[0], self.ventas.p[-1]

    def comprueba(self, ahora: float) -> None:
        """Un libro valido que se cruza o que se sale de su alcance deja de serlo."""
        if not self.valido:
            return
        m = self.mejores()
        if m is None:
            self.invalida(ahora, "un lado vacio", "source_failure")
        elif m[0] >= m[1]:
            self.invalida(ahora, f"cruzado: compra {m[0]} >= venta {m[1]}", "source_failure")
        elif self.alcance is not None and (m[0] < self.alcance[0] or m[1] > self.alcance[1]):
            self.invalida(ahora, "el precio salio del alcance de la foto REST", "source_failure")


def niveles(lado: Lado, desde: Decimal, paso: Decimal, n: int, abajo: bool) -> list[Decimal]:
    """Cantidades de los n niveles de `paso` que empiezan en el nivel `desde` (hacia abajo en la compra, hacia arriba
    en la venta), sumando los precios de cada nivel. Un nivel sin cantidad sale 0."""
    out = [ZERO] * n
    if n <= 0:
        return out
    p, q = lado.p, lado.q
    # Los precios ya estan ordenados: se recorren desde el mejor y el nivel avanza al cruzar su borde. Sin una division
    # por precio (el relevo hace esto cuatro veces por segundo en cada libro) y exacto en Decimal.
    k = 0
    if abajo:  # el nivel k es [desde - k*paso, desde - (k-1)*paso)
        borde = desde
        for i in range(len(p) - 1, bisect_left(p, desde - (n - 1) * paso) - 1, -1):
            while p[i] < borde:
                k, borde = k + 1, borde - paso
            out[k] += q[p[i]]
    else:  # el nivel k es [desde + k*paso, desde + (k+1)*paso)
        techo = desde + paso
        for i in range(bisect_left(p, desde), bisect_left(p, desde + n * paso)):
            while p[i] >= techo:
                k, techo = k + 1, techo + paso
            out[k] += q[p[i]]
    return out


def escalera(lib: Libro, paso: Decimal, banda: int) -> tuple[Decimal, list[Decimal], Decimal, list[Decimal]] | None:
    """(nivel de la mejor compra, cantidades hacia abajo, nivel de la mejor venta, cantidades hacia arriba), hasta
    `banda` niveles por lado y sin pasar del alcance: un nivel de compra L se conoce entero si L >= alcance de la
    compra; uno de venta si L + paso <= alcance de la venta. None si el mejor nivel de un lado no se conoce entero."""
    m = lib.mejores()
    if m is None:
        return None
    alc_c, alc_v = lib.alcances()
    nc, nv = nivel_de(m[0], paso), nivel_de(m[1], paso)
    n_c = min(banda, int((nc - alc_c) / paso) + 1) if nc >= alc_c else 0
    n_v = min(banda, int((alc_v - nv) / paso)) if nv + paso <= alc_v else 0
    if n_c < 1 or n_v < 1:
        return None
    return nc, niveles(lib.compras, nc, paso, n_c, True), nv, niveles(lib.ventas, nv, paso, n_v, False)


def foto(lib: Libro, ts: int) -> tuple[Any, ...] | None:
    paso = PASOS[lib.activo]
    e = escalera(lib, paso, BANDA[lib.activo])
    if e is None:
        return None
    (compra, venta), (alc_c, alc_v) = lib.mejores(), lib.alcances()  # type: ignore[misc]
    return (datetime.fromtimestamp(ts, UTC), lib.venue, lib.activo, datetime.fromtimestamp(lib.ts_ms / 1000, UTC),
            compra, venta, paso, e[0], e[1], e[2], e[3], alc_c, alc_v)


def _quedan(lib: Libro) -> tuple[Decimal, Decimal]:
    """Lo que queda de alcance a cada lado de los mejores precios."""
    m, alc = lib.mejores(), lib.alcances()
    return (m[0] - alc[0], alc[1] - m[1]) if m else (ZERO, ZERO)


# --------------------------------------------------------------------------------------------- los mensajes
class SaltoDeConexion(Exception):
    """Coinbase numera la CONEXION: un salto invalida sus tres libros y se reconecta."""


def _d(valor: object) -> Decimal:
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, (str, int)) and not isinstance(valor, bool):
        return Decimal(valor)
    raise ValueError(f"cantidad sin texto exacto: {valor!r}")


def _ms_iso(texto: str) -> int:
    """'2026-10-17T22:51:07.730498Z' (o con nanosegundos) -> ms de epoch."""
    base, _, frac = texto.rstrip("Z").partition(".")
    segundos = datetime.fromisoformat(base + "+00:00").timestamp()
    return int(segundos) * 1000 + int((frac + "000")[:3])


def _binance_aplica(lib: Libro, x: dict[str, Any], rx_ms: int) -> None:
    for p, q in x.get("b") or []:
        lib.pon("b", _d(p), _d(q))
    for p, q in x.get("a") or []:
        lib.pon("a", _d(p), _d(q))
    lib.seq, lib.ts_ms, lib.rx_ms, lib.cambiado = int(x["u"]), int(x["E"]), rx_ms, True


def _binance_desde(snap: dict[str, Any], buffer: list[dict[str, Any]], usdm: bool) -> tuple[str, Any]:
    """La regla de Binance para casar una foto REST con las diferencias que llegaron mientras. Devuelve ('espera',
    None) si aun no llego la diferencia que la cruza, ('vieja', None) si la foto es anterior a lo guardado, o
    ('ok', (compras, ventas, diferencias a aplicar en orden))."""
    L = int(snap["lastUpdateId"])
    corte = L if usdm else L + 1
    evs = [x for x in buffer if int(x["u"]) >= corte]
    if not evs:
        return "espera", None
    if not int(evs[0]["U"]) <= corte <= int(evs[0]["u"]):
        return "vieja", None
    for p, q in zip(evs, evs[1:], strict=False):
        if (int(q["pu"]) != int(p["u"])) if usdm else (int(q["U"]) != int(p["u"]) + 1):
            return "vieja", None
    compras = {_d(p): _d(q) for p, q in snap["bids"]}
    ventas = {_d(p): _d(q) for p, q in snap["asks"]}
    return "ok", (compras, ventas, evs)


def binance(v: Venue, libros: dict[str, Libro], msg: dict[str, Any], ahora: float) -> list[Libro]:
    x = msg.get("data")
    if not isinstance(x, dict) or x.get("e") != "depthUpdate":
        return []
    activo = next((a for a, i in v.instrumentos.items() if i == x.get("s")), None)
    if activo is None:
        return []
    lib, usdm, rx_ms = libros[activo], v.venue == "binance_usdm", int(ahora * 1000)
    if not lib.valido:
        lib.buffer.append(x)
        if len(lib.buffer) > BUFFER_TOPE:
            del lib.buffer[: BUFFER_TOPE // 2]
        binance_sincroniza(v, lib, ahora)
        return [lib]
    ok = (int(x["pu"]) == lib.seq) if usdm else (int(x["U"]) == (lib.seq or 0) + 1)
    if not ok:
        lib.invalida(ahora, f"salto: u {lib.seq} -> U {x['U']} pu {x.get('pu')}", "sequence_discontinuity")
        lib.buffer = [x]
        return [lib]
    _binance_aplica(lib, x, rx_ms)
    if lib.refresco is not None:
        lib.refresco.append(x)
        binance_refresca(v, lib, ahora)
    return [lib]


def binance_sincroniza(v: Venue, lib: Libro, ahora: float) -> None:
    if lib.foto_rest is None:
        return
    estado, r = _binance_desde(lib.foto_rest, lib.buffer, v.venue == "binance_usdm")
    if estado == "espera":
        return
    if estado == "vieja":  # hubo un hueco entre la foto y lo guardado: otra foto
        lib.foto_rest = None
        return
    compras, ventas, evs = r
    lib.alcance = (min(compras), max(ventas))
    lib.carga(compras, ventas, None, int(evs[0]["E"]), int(ahora * 1000))
    for x in evs:
        _binance_aplica(lib, x, int(ahora * 1000))
    lib.buffer, lib.foto_rest, lib.refrescado, lib.resuscribir = [], None, ahora, False
    lib.alcance_inicial = _quedan(lib)
    lib.valida(ahora)


def binance_refresca(v: Venue, lib: Libro, ahora: float) -> None:
    """La foto REST nueva se casa con las diferencias guardadas DESDE que se pidio; si casa, sustituye al libro y su
    alcance sin que el libro deje de ser valido (la numeracion es la misma)."""
    if lib.foto_refresco is None or lib.refresco is None:
        return
    estado, r = _binance_desde(lib.foto_refresco, lib.refresco, v.venue == "binance_usdm")
    if estado == "espera":
        return
    lib.foto_refresco, lib.refresco = None, None
    if estado == "vieja":
        return
    compras, ventas, evs = r
    nuevo = Libro(lib.venue, lib.activo)
    nuevo.alcance = (min(compras), max(ventas))
    nuevo.carga(compras, ventas, None, int(evs[0]["E"]), lib.rx_ms)
    for x in evs:
        _binance_aplica(nuevo, x, lib.rx_ms)
    if nuevo.seq != lib.seq:
        return
    lib.compras, lib.ventas, lib.alcance = nuevo.compras, nuevo.ventas, nuevo.alcance
    lib.alcance_inicial, lib.refrescado, lib.cambiado = _quedan(lib), ahora, True


def _carga_niveles(niveles_: list[Any], mult: Decimal = Decimal(1)) -> dict[Decimal, Decimal]:
    return {_d(n[0]): _d(n[1]) * mult for n in niveles_}


def bybit(v: Venue, libros: dict[str, Libro], msg: dict[str, Any], ahora: float) -> list[Libro]:
    topic = str(msg.get("topic", ""))
    if not topic.startswith("orderbook.1000."):  # la profundidad suscrita: cada una numera aparte
        return []
    activo = next((a for a, i in v.instrumentos.items() if i == topic.rsplit(".", 1)[-1]), None)
    if activo is None:
        return []
    lib, x, rx_ms = libros[activo], msg.get("data") or {}, int(ahora * 1000)
    if msg.get("type") == "snapshot":
        if lib.valido:  # el venue reinicia el libro (u = 1 tras reiniciar su servicio): se sustituye, sin hueco
            lib.resyncs[int(ahora) // 60 * 60] += 1
        lib.carga(_carga_niveles(x.get("b") or []), _carga_niveles(x.get("a") or []), int(x["u"]), int(msg["ts"]),
                  rx_ms)
        lib.valida(ahora)
        return [lib]
    if msg.get("type") != "delta" or not lib.valido:
        return [lib]
    if int(x["u"]) != (lib.seq or 0) + 1:
        lib.invalida(ahora, f"salto: u {lib.seq} -> {x['u']}", "sequence_discontinuity")
        lib.resuscribir = True
        return [lib]
    for p, q in x.get("b") or []:
        lib.pon("b", _d(p), _d(q))
    for p, q in x.get("a") or []:
        lib.pon("a", _d(p), _d(q))
    lib.seq, lib.ts_ms, lib.rx_ms, lib.cambiado = int(x["u"]), int(msg["ts"]), rx_ms, True
    return [lib]


def okx_bitget(v: Venue, libros: dict[str, Libro], msg: dict[str, Any], ahora: float) -> list[Libro]:
    """OKX (seqId / prevSeqId) y Bitget (seq / pseq): la misma forma de mensaje con otros nombres."""
    arg = msg.get("arg") or {}
    if arg.get("channel") != "books":
        return []
    activo = next((a for a, i in v.instrumentos.items() if i == arg.get("instId")), None)
    if activo is None:
        return []
    lib, rx_ms = libros[activo], int(ahora * 1000)
    seq, prev = ("seqId", "prevSeqId") if v.familia == "okx" else ("seq", "pseq")
    mult = v.multiplicador.get(activo, Decimal(1))
    for x in msg.get("data") or []:
        if msg.get("action") == "snapshot":
            lib.carga(_carga_niveles(x.get("bids") or [], mult), _carga_niveles(x.get("asks") or [], mult),
                      int(x[seq]), int(x["ts"]), rx_ms)
            lib.valida(ahora)
            continue
        if msg.get("action") != "update" or not lib.valido:
            continue
        if int(x[prev]) != lib.seq:
            lib.invalida(ahora, f"salto: {seq} {lib.seq} -> {prev} {x[prev]}", "sequence_discontinuity")
            lib.resuscribir = True
            break
        for n in x.get("bids") or []:
            lib.pon("b", _d(n[0]), _d(n[1]) * mult)
        for n in x.get("asks") or []:
            lib.pon("a", _d(n[0]), _d(n[1]) * mult)
        lib.seq, lib.ts_ms, lib.rx_ms, lib.cambiado = int(x[seq]), int(x["ts"]), rx_ms, True
    return [lib]


def deribit(v: Venue, libros: dict[str, Libro], msg: dict[str, Any], ahora: float) -> list[Libro]:
    if msg.get("method") != "subscription":
        return []
    x = (msg.get("params") or {}).get("data") or {}
    inst = x.get("instrument_name")
    activo = next((a for a, i in v.instrumentos.items() if i == inst), None)
    if activo is None:
        return []
    lib, rx_ms = libros[activo], int(ahora * 1000)

    def base(precio: Decimal, cantidad: Decimal) -> Decimal:
        return (cantidad / precio).quantize(BASE_INVERSO) if inst in INVERSOS else cantidad

    if x.get("type") == "snapshot":
        lib.carga({_d(p): base(_d(p), _d(q)) for _, p, q in x.get("bids") or []},
                  {_d(p): base(_d(p), _d(q)) for _, p, q in x.get("asks") or []},
                  int(x["change_id"]), int(x["timestamp"]), rx_ms)
        lib.valida(ahora)
        return [lib]
    if x.get("type") != "change" or not lib.valido:
        return [lib]
    if x.get("prev_change_id") != lib.seq:
        lib.invalida(ahora, f"salto: change_id {lib.seq} -> prev {x.get('prev_change_id')}", "sequence_discontinuity")
        lib.resuscribir = True
        return [lib]
    for lado, clave in (("b", "bids"), ("a", "asks")):
        for accion, p, q in x.get(clave) or []:
            precio = _d(p)
            lib.pon(lado, precio, ZERO if accion == "delete" else base(precio, _d(q)))
    lib.seq, lib.ts_ms, lib.rx_ms, lib.cambiado = int(x["change_id"]), int(x["timestamp"]), rx_ms, True
    return [lib]


def coinbase(v: Venue, libros: dict[str, Libro], msg: dict[str, Any], ahora: float,
             conexion: dict[str, Any]) -> list[Libro]:
    n = msg.get("sequence_num")
    if n is not None:
        if conexion.get("seq") is not None and int(n) != conexion["seq"] + 1:
            raise SaltoDeConexion(f"sequence_num {conexion['seq']} -> {n}")
        conexion["seq"] = int(n)
    if msg.get("channel") != "l2_data":
        return []
    ts_ms, rx_ms, tocados = _ms_iso(str(msg["timestamp"])), int(ahora * 1000), []
    for ev in msg.get("events") or []:
        activo = next((a for a, i in v.instrumentos.items() if i == ev.get("product_id")), None)
        if activo is None:
            continue
        lib = libros[activo]
        tocados.append(lib)
        if ev.get("type") == "snapshot":
            compras, ventas = {}, {}
            for u in ev.get("updates") or []:
                (compras if u["side"] == "bid" else ventas)[_d(u["price_level"])] = _d(u["new_quantity"])
            lib.carga(compras, ventas, None, ts_ms, rx_ms)
            lib.valida(ahora)
            continue
        if ev.get("type") != "update" or not lib.valido:
            continue
        for u in ev.get("updates") or []:
            lib.pon("b" if u["side"] == "bid" else "a", _d(u["price_level"]), _d(u["new_quantity"]))
        lib.ts_ms, lib.rx_ms, lib.cambiado = ts_ms, rx_ms, True
    return tocados


def procesa(v: Venue, libros: dict[str, Libro], raw: str | bytes, ahora: float,
            conexion: dict[str, Any]) -> list[Libro]:
    """Un mensaje crudo -> los libros que toco, ya comprobados. Lo que no es libro (acks, pongs) no toca nada."""
    if raw in ("pong", b"pong"):
        return []
    msg = json.loads(raw, parse_float=Decimal)
    if not isinstance(msg, dict):
        return []
    if v.familia == "binance":
        tocados = binance(v, libros, msg, ahora)
    elif v.familia == "bybit":
        tocados = bybit(v, libros, msg, ahora)
    elif v.familia in ("okx", "bitget"):
        tocados = okx_bitget(v, libros, msg, ahora)
    elif v.familia == "deribit":
        tocados = deribit(v, libros, msg, ahora)
    else:
        tocados = coinbase(v, libros, msg, ahora, conexion)
    for lib in tocados:
        lib.comprueba(ahora)
    return tocados


def suscripciones(v: Venue, activos: tuple[str, ...], baja: bool = False) -> list[str]:
    insts = [v.instrumentos[a] for a in activos]
    op = "unsubscribe" if baja else "subscribe"
    if v.familia == "bybit":
        return [json.dumps({"op": op, "args": [f"orderbook.1000.{i}" for i in insts]})]
    if v.familia == "okx":
        return [json.dumps({"op": op, "args": [{"channel": "books", "instId": i} for i in insts]})]
    if v.familia == "bitget":
        return [json.dumps({"op": op, "args": [{"instType": "USDT-FUTURES", "channel": "books", "instId": i}
                                               for i in insts]})]
    if v.familia == "deribit":
        return [json.dumps({"jsonrpc": "2.0", "id": 2 if baja else 1, "method": f"public/{op}",
                            "params": {"channels": [f"book.{i}.100ms" for i in insts]}})]
    if v.familia == "coinbase":
        return [json.dumps({"type": op, "product_ids": insts, "channel": "level2"})] + (
            [] if baja else [json.dumps({"type": op, "product_ids": insts, "channel": "heartbeats"})])
    return []


# --------------------------------------------------------------------------------------------- la conexion
class Silencio(Exception):
    pass


async def _pinga(ws: Any, texto: str, cada: float) -> None:
    with contextlib.suppress(Exception):  # si la conexion muere, la cierra el bucle de lectura, no este
        while True:
            await asyncio.sleep(cada)
            await ws.send(texto)


async def _foto_rest(cliente: httpx.AsyncClient, v: Venue, lib: Libro, refresco: bool) -> None:
    """La marca `pidiendo` la pone quien crea la tarea, ANTES: si no, el mensaje siguiente pediria otra foto."""
    try:
        r = await cliente.get(v.rest.format(inst=v.instrumentos[lib.activo]), timeout=15)  # type: ignore[union-attr]
        r.raise_for_status()
        snap = r.json()
        ahora = time.time()
        if refresco:
            if lib.refresco is not None and lib.valido:
                lib.foto_refresco = snap
                binance_refresca(v, lib, ahora)
        elif not lib.valido:
            lib.foto_rest = snap
            binance_sincroniza(v, lib, ahora)
            lib.comprueba(ahora)
    except Exception as exc:  # noqa: BLE001 - se reintenta en la vuelta siguiente
        LOGGER.warning("libro_foto_rest_fallo venue=%s activo=%s error=%s", v.venue, lib.activo, exc)
        if refresco:
            lib.refresco = None
        await asyncio.sleep(2)
    finally:
        lib.pidiendo = False


def _refresco_toca(lib: Libro, ahora: float) -> bool:
    """Binance: foto REST nueva cada REFRESCO_S, o antes (nunca a menos de REFRESCO_MIN_S de la anterior) si a un lado
    le queda menos de la mitad del alcance que tenia al casar la foto: el precio se esta yendo hacia su borde."""
    if not lib.valido or lib.refresco is not None or lib.pidiendo or ahora - lib.refrescado < REFRESCO_MIN_S:
        return False
    if ahora - lib.refrescado > REFRESCO_S:
        return True
    queda, ini = _quedan(lib), lib.alcance_inicial
    return queda[0] < ini[0] / 2 or queda[1] < ini[1] / 2


async def escucha(v: Venue, libros: dict[str, Libro], salud: dict[str, Any], cliente: httpx.AsyncClient) -> None:
    """Una conexion por venue con sus tres activos. Reconecta con espera exponencial y jitter. Al caer la conexion, sus
    tres libros dejan de ser validos hasta que se vuelvan a sincronizar."""
    intento = 0
    tareas: set[asyncio.Task[None]] = set()
    while True:
        conectado = time.time()
        conexion: dict[str, Any] = {"seq": None}
        try:
            async with connect(v.url, open_timeout=30, close_timeout=5, ping_interval=20, ping_timeout=20,
                               max_size=64_000_000, max_queue=2048) as ws:
                for s in suscripciones(v, ACTIVOS):
                    await ws.send(s)
                for lib in libros.values():
                    lib.resuscribir = False  # la suscripcion de esta conexion trae su foto
                salud["reconexiones"][(v.venue, int(time.time()) // 60 * 60)] += 1
                pinger = asyncio.create_task(_pinga(ws, v.ping, v.cada)) if v.ping else None
                LOGGER.info("libro_connected venue=%s", v.venue)
                ultimo = time.time()
                try:
                    while True:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=1)
                        except TimeoutError:
                            raw = None
                        ahora = time.time()
                        if raw is not None:
                            ultimo = ahora
                            try:
                                procesa(v, libros, raw, ahora, conexion)
                            except SaltoDeConexion:
                                raise
                            except Exception as exc:  # noqa: BLE001 - un mensaje que no se entiende
                                # puede haberse quedado a medio aplicar: ningun libro de este venue se da por bueno
                                salud["mal_formados"][v.venue] += 1
                                LOGGER.warning("libro_mal_formado venue=%s error=%s", v.venue, exc)
                                for lib in libros.values():
                                    if lib.valido or lib.buffer:
                                        lib.invalida(ahora, f"mensaje que no se entiende: {exc}", "source_failure")
                        if ahora - ultimo > SILENCIO_S:
                            raise Silencio(f"{v.venue} sin un mensaje en {SILENCIO_S:.0f} s")
                        for lib in libros.values():
                            if lib.resuscribir:
                                lib.resuscribir = False
                                for s in suscripciones(v, (lib.activo,), baja=True) + suscripciones(v, (lib.activo,)):
                                    await ws.send(s)
                            if v.rest and not lib.pidiendo:
                                if not lib.valido and lib.foto_rest is None and lib.buffer:
                                    lib.pidiendo = True
                                    tareas.add(t := asyncio.create_task(_foto_rest(cliente, v, lib, False)))
                                    t.add_done_callback(tareas.discard)
                                elif _refresco_toca(lib, ahora):
                                    lib.refresco, lib.pidiendo = [], True
                                    tareas.add(t := asyncio.create_task(_foto_rest(cliente, v, lib, True)))
                                    t.add_done_callback(tareas.discard)
                finally:
                    if pinger is not None:
                        pinger.cancel()
        except asyncio.CancelledError:
            for t in tareas:
                t.cancel()
            raise
        except SaltoDeConexion as exc:
            ahora = time.time()
            for lib in libros.values():
                lib.invalida(ahora, f"salto de la conexion: {exc}", "sequence_discontinuity")
            LOGGER.warning("libro_salto_conexion venue=%s %s", v.venue, exc)
        except Silencio as exc:
            LOGGER.warning("libro_silencio venue=%s %s", v.venue, exc)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("libro_disconnected venue=%s error=%s code=%s", v.venue, type(exc).__name__,
                           getattr(exc, "code", None))
        ahora = time.time()
        for lib in libros.values():
            if lib.valido or lib.buffer:
                lib.invalida(ahora, "la conexion se cerro", "disconnect")
        for t in tareas:
            t.cancel()
        salud["caidas"][v.venue] += 1
        intento = 0 if time.time() - conectado > 60 else intento + 1
        await asyncio.sleep(min(60.0, 2.0 ** intento) * random.uniform(0.5, 1.0))


# --------------------------------------------------------------------------------------------- la foto y su minuto
class Almacen:
    """Las fotos de los minutos que aun no se escribieron; se escriben juntas con su cobertura y sus huecos."""

    def __init__(self, inicio: float) -> None:
        self.fotos: dict[int, list[tuple[Any, ...]]] = defaultdict(list)
        self.n_fotos: defaultdict[tuple[str, str, int], int] = defaultdict(int)
        self.proximo = int(inicio) // 60 * 60  # el primer minuto que falta escribir: el del arranque
        self.descartados: list[int] = []  # minutos tirados porque la base no aceptaba: se declaran al volver
        self.escrito = time.time()


def fotografia(libros: list[Libro], alm: Almacen, g: int) -> None:
    for lib in libros:
        if not lib.valido:
            continue
        f = foto(lib, g)
        if f is None:
            lib.invalida(float(g), "el alcance no cubre el mejor nivel al paso de la foto", "source_failure")
            continue
        alm.fotos[g // 60 * 60].append(f)
        alm.n_fotos[(lib.venue, lib.activo, g // 60 * 60)] += 1


async def fotografo(libros: list[Libro], alm: Almacen) -> None:
    """Cada segundo en punto. Si despierta tarde, ese tiempo no se cubre en NINGUN libro (cada libro cierra su tramo
    en el segundo que tocaba y lo reabre ahora) y no fotografia: un libro que nadie estaba atendiendo no se fotografia
    como si estuviera al dia."""
    siguiente = int(time.time()) + 1
    while True:
        await asyncio.sleep(max(0.0, siguiente + 0.02 - time.time()))
        ahora = time.time()
        g, siguiente = siguiente, int(ahora) + 1
        if ahora - g > RETRASO_MAX_S:
            for lib in libros:
                if lib.valido:
                    lib.cob.cierra(float(g))
                    lib.cob.abre(ahora)
            LOGGER.warning("libro_fotografo_tarde retraso=%.2fs", ahora - g)
            continue
        if g % FOTO_S == 0:
            fotografia(libros, alm, g)


GAP_SQL = """
WITH ext AS (
  UPDATE data_gap SET end_ts=$6
   WHERE feed='libro' AND exchange=$1 AND market=$2 AND symbol=$3 AND granularity='event'
     AND evidence_type=$4 AND detection_source='app.libro' AND status='unrecoverable' AND end_ts=$5
  RETURNING id
)
INSERT INTO data_gap(feed,feed_class,exchange,market,symbol,granularity,start_ts,end_ts,evidence_type,
                     detection_reason,detection_source,status,resolved_at,resolution_reason,recovery_metadata)
SELECT 'libro','event_stream',$1,$2,$3,'event',$5,$6,$4,$7,'app.libro','unrecoverable',now(),
       'decision OF-4a: un libro que no se escucho no se rellena; el minuto queda declarado incompleto',
       '{"method": "libro_sin_cobertura", "tabla": "libro_cobertura"}'::jsonb
 WHERE NOT EXISTS (SELECT 1 FROM ext)
ON CONFLICT DO NOTHING
"""
FOTO_SQL = """INSERT INTO libro_foto(ts,venue,symbol,ts_libro,compra,venta,paso,compra_nivel,compras,venta_nivel,ventas,
                                     alcance_compra,alcance_venta)
              VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::numeric[],$10,$11::numeric[],$12,$13)"""
COBERTURA_SQL = """
INSERT INTO libro_cobertura(ts,venue,symbol,segundos,fotos,saltos,resincronizaciones,reconexiones)
SELECT * FROM unnest($1::timestamptz[],$2::text[],$3::text[],$4::smallint[],$5::smallint[],$6::smallint[],
                     $7::smallint[],$8::smallint[])
ON CONFLICT (symbol,ts,venue) DO UPDATE SET
  -- otro proceso escribio ESTE minuto (se reinicio dentro de el): sus tramos no se solapan, se suman, y entre los dos
  -- hubo un hueco, asi que nunca es 60
  segundos=least(59, libro_cobertura.segundos + EXCLUDED.segundos), fotos=libro_cobertura.fotos + EXCLUDED.fotos,
  saltos=libro_cobertura.saltos + EXCLUDED.saltos,
  resincronizaciones=libro_cobertura.resincronizaciones + EXCLUDED.resincronizaciones,
  reconexiones=libro_cobertura.reconexiones + EXCLUDED.reconexiones, escrito=now()
"""


def _ts(segundos: int) -> datetime:
    return datetime.fromtimestamp(segundos, UTC)


async def declara_hueco(conn: asyncpg.Connection, venue: str, activo: str, desde: int, hasta: int, evidencia: str,
                        motivo: str) -> None:
    """[desde, hasta) en segundos de epoch, alineado a minuto. Un hueco contiguo al anterior del mismo tipo lo
    alarga en vez de abrir otra fila."""
    await conn.execute(GAP_SQL, venue, VENUES[venue].mercado, activo, evidencia, _ts(desde), _ts(hasta), motivo[:500])


def _evidencia(lib: Libro, minuto: int, inicio: float, apagando: bool) -> str:
    if minuto < int(inicio) // 60 * 60 + 60 or apagando:
        return "collector_outage"
    for e in ("sequence_discontinuity", "source_failure", "disconnect"):
        if e in lib.causas.get(minuto, ()):
            return e
    return "disconnect"


async def escribe_minuto(conn: asyncpg.Connection, alm: Almacen, libros: list[Libro], minuto: int, ahora: float,
                         inicio: float, salud: dict[str, Any], *, apagando: bool = False) -> int:
    """Las fotos, la cobertura y los huecos de UN minuto, en la transaccion del que llama. Devuelve los huecos."""
    fotos = alm.fotos.get(minuto, [])
    if fotos:
        await conn.executemany(FOTO_SQL, fotos)
    filas, huecos = [], []
    for lib in libros:
        seg = lib.cob.segundos(minuto, ahora)
        filas.append((_ts(minuto), lib.venue, lib.activo, seg, alm.n_fotos.get((lib.venue, lib.activo, minuto), 0),
                      lib.saltos.get(minuto, 0), lib.resyncs.get(minuto, 0),
                      salud["reconexiones"].get((lib.venue, minuto), 0)))
        if seg < 60:
            huecos.append((lib, seg))
    await conn.execute(COBERTURA_SQL, *map(list, zip(*filas, strict=True)))
    for lib, seg in huecos:
        await declara_hueco(conn, lib.venue, lib.activo, minuto, minuto + 60, _evidencia(lib, minuto, inicio, apagando),
                            f"libro: minuto con {seg} s de 60 con libro valido de {lib.venue} ({lib.motivo or 'ok'})")
    return len(huecos)


def _olvida(alm: Almacen, libros: list[Libro], minuto: int, salud: dict[str, Any]) -> None:
    alm.fotos.pop(minuto, None)
    for lib in libros:
        alm.n_fotos.pop((lib.venue, lib.activo, minuto), None)
        for d in (lib.saltos, lib.resyncs, lib.causas):
            d.pop(minuto, None)
        lib.cob.poda(minuto - 60)
    for clave in [k for k in salud["reconexiones"] if k[1] <= minuto]:
        del salud["reconexiones"][clave]


async def vuelca(pool: asyncpg.Pool, own: ServiceOwnership | None, alm: Almacen, libros: list[Libro], ahora: float,
                 inicio: float, salud: dict[str, Any], *, apagando: bool = False) -> None:
    """Escribe los minutos cerrados (al apagar, tambien el que estaba en curso, con lo que llego a cubrir). Cada minuto
    en SU transaccion: o entra entero (fotos, cobertura y huecos) o no entra y se reintenta."""
    limite = int(ahora) // 60 * 60 if apagando else int(ahora - CIERRE_S - 60) // 60 * 60
    while alm.proximo <= limite:
        minuto = alm.proximo
        try:
            async with pool.acquire() as conn:
                async with fenced_transaction(conn, own):
                    for m in alm.descartados:
                        for lib in libros:
                            await declara_hueco(conn, lib.venue, lib.activo, m, m + 60, "queue_full",
                                                "libro: minuto tirado de la memoria porque la base no aceptaba")
                    await escribe_minuto(conn, alm, libros, minuto, ahora, inicio, salud,
                                         apagando=apagando and minuto == limite)
        except ServiceOwnershipLost:
            raise
        except Exception:
            LOGGER.exception("libro_flush_failed minuto=%s pendientes=%d", _ts(minuto).isoformat(),
                             (limite - minuto) // 60 + 1)
            if (limite - minuto) // 60 + 1 > MINUTOS_TOPE:
                alm.descartados.append(minuto)
                _olvida(alm, libros, minuto, salud)
                alm.proximo = minuto + 60
            return
        alm.descartados = []
        _olvida(alm, libros, minuto, salud)
        alm.proximo = minuto + 60
        alm.escrito = time.time()


async def declara_parada_anterior(pool: asyncpg.Pool, own: ServiceOwnership | None, inicio: float) -> int:
    """Al arrancar: lo que va del ultimo minuto escrito de cada libro hasta este arranque no lo escucho nadie: se
    declara (collector_outage), no se rellena. Sin filas previas no hay nada que declarar."""
    primero = int(inicio) // 60 * 60
    declarados = 0
    async with pool.acquire() as conn:
        ultimos = await conn.fetch("SELECT venue, symbol, max(ts) AS ultimo FROM libro_cobertura GROUP BY 1, 2")
        async with fenced_transaction(conn, own):
            for fila in ultimos:
                if fila["venue"] not in VENUES:
                    continue
                desde = int(fila["ultimo"].timestamp()) + 60
                if desde < primero:
                    await declara_hueco(conn, fila["venue"], fila["symbol"], desde, primero, "collector_outage",
                                        "libro: el servicio no corria; nadie escucho ese libro")
                    declarados += 1
    return declarados


async def escritor(pool: asyncpg.Pool, own: ServiceOwnership | None, alm: Almacen, libros: list[Libro],
                   inicio: float, salud: dict[str, Any]) -> None:
    while True:
        await asyncio.sleep(1.0)
        await vuelca(pool, own, alm, libros, time.time(), inicio, salud)


# --------------------------------------------------------------------------------------------- el relevo en vivo
def texto(valor: Decimal) -> str:
    return "0" if valor == 0 else format(valor.normalize(), "f")


def carga_relevo(lib: Libro, base: Decimal, ahora: float) -> str:
    """El aviso de un libro: su escalera al paso base, hasta RELEVO_NIVELES niveles por lado, o su estado si no es
    valido. Si no cabe en un NOTIFY, se recorta a menos niveles y lo dice (`n`)."""
    e_ms = int(ahora * 1000)
    if not lib.valido:
        return json.dumps({"v": lib.venue, "s": lib.activo, "x": lib.motivo or "sin libro", "e": e_ms},
                          separators=(",", ":"))
    compra, venta = lib.mejores()  # type: ignore[misc]
    n = RELEVO_NIVELES
    while n >= 1:
        e = escalera(lib, base, n)
        if e is None:
            return json.dumps({"v": lib.venue, "s": lib.activo, "x": "sin alcance al paso base", "e": e_ms},
                              separators=(",", ":"))
        nc, cs, nv, vs = e
        # kc / kv: cuantos niveles CONOCIDOS trae cada lado desde el mejor (el alcance puede dar menos que n); dentro
        # de ellos, un nivel que no esta en la lista es un nivel vacio, y mas alla no se sabe. Niveles y cantidades con
        # str(): exacto y Decimal lo relee (la API sirve el texto canonico); normalizarlos aqui era ~1/3 del colector.
        carga = json.dumps({
            "v": lib.venue, "s": lib.activo, "t": lib.ts_ms, "r": lib.rx_ms, "e": e_ms, "p": texto(base),
            "b": texto(compra), "a": texto(venta), "kc": len(cs), "kv": len(vs),
            "c": [[str(nc - i * base), str(q)] for i, q in enumerate(cs) if q],
            "w": [[str(nv + i * base), str(q)] for i, q in enumerate(vs) if q],
        }, separators=(",", ":"))
        if len(carga.encode()) <= CARGA_MAX:
            return carga
        n //= 2
    return json.dumps({"v": lib.venue, "s": lib.activo, "x": "no cabe en un aviso", "e": e_ms}, separators=(",", ":"))


async def relevo(pool: asyncpg.Pool, libros: list[Libro], bases: dict[str, Decimal], salud: dict[str, Any]) -> None:
    """Cada RELEVO_S, un NOTIFY por libro que cambio (su escalera o que dejo de ser valido), en UN viaje a la base."""
    while True:
        await asyncio.sleep(RELEVO_S)
        ahora = time.time()
        cargas = []
        for lib in libros:
            if lib.cambiado:
                lib.cambiado = False
                cargas.append(carga_relevo(lib, bases[lib.activo], ahora))
        if not cargas:
            continue
        try:
            async with pool.acquire() as conn:
                await conn.execute(f"SELECT pg_notify('{CANAL}', x) FROM unnest($1::text[]) AS x", cargas)
            salud["avisos"] += len(cargas)
        except Exception:  # noqa: BLE001 - el relevo no para el colector
            salud["avisos_fallidos"] += len(cargas)
            LOGGER.exception("libro_relevo_fallo avisos=%d", len(cargas))


# --------------------------------------------------------------------------------------------- latido y retencion
def estado(libros: list[Libro], alm: Almacen, salud: dict[str, Any], ahora: float) -> tuple[str, str]:
    sin = [f"{lib.venue}:{lib.activo}" for lib in libros if not lib.valido]
    viejo = ahora - alm.escrito > 60 + CIERRE_S + 60
    status = "ok" if not sin and not viejo else "degraded"
    detail = (
        f"libros={len(libros) - len(sin)}/{len(libros)}{' sin=' + ','.join(sin) if sin else ''} "
        f"escritor={'parado' if viejo else 'ok'} minutos_pendientes={(int(ahora) // 60 * 60 - alm.proximo) // 60} "
        f"avisos={salud['avisos']} avisos_fallidos={salud['avisos_fallidos']} caidas={sum(salud['caidas'].values())} "
        f"mal_formados={sum(salud['mal_formados'].values())}"
    )
    return status, detail[:500]


async def latido(pool: asyncpg.Pool, own: ServiceOwnership, libros: list[Libro], alm: Almacen,
                 salud: dict[str, Any]) -> None:
    while True:
        await asyncio.sleep(20)
        try:
            status, detail = estado(libros, alm, salud, time.time())
            async with pool.acquire() as conn:
                await heartbeat_owned(conn, own, SERVICIO, status=status, detail=detail)
        except ServiceOwnershipLost:
            raise
        except Exception:
            LOGGER.exception("libro_heartbeat_failed")


async def poda(pool: asyncpg.Pool, own: ServiceOwnership) -> None:
    """La retencion, cada hora, por el mecanismo que ya existe: libro_foto por apply_temporal_retention (tira
    particiones enteras y recorta la del borde); libro_cobertura con DELETE de los minutos COMPLETOS. Los incompletos
    no se podan: son la prueba que K04 re-deriva de sus huecos."""
    s = get_settings()
    while True:
        await asyncio.sleep(60)
        try:
            async with pool.acquire() as conn:
                async with fenced_transaction(conn, own):
                    await conn.execute("SET LOCAL statement_timeout = '300s'")
                    await apply_temporal_retention(conn, "libro_foto", s.LIBRO_RETENTION_DAYS * 24)
                    await conn.execute(
                        "DELETE FROM libro_cobertura WHERE segundos = 60 AND ts < now() - make_interval(days => $1)",
                        s.LIBRO_RETENTION_DAYS)
        except ServiceOwnershipLost:
            raise
        except Exception:
            LOGGER.exception("libro_retention_failed")
        await asyncio.sleep(3540)


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)
    own = await acquire_service_lock(settings, SERVICIO)
    pool = await create_pool(settings, application_name="coinalyze-libro", ownership=own)
    inicio = time.time()
    try:
        async with pool.acquire() as conn:
            bases = {r["symbol"]: Decimal(r["paso"]) for r in await conn.fetch(
                "SELECT symbol, paso::text AS paso FROM orderflow_paso")}
        malos = [a for a in ACTIVOS if a not in bases or PASOS[a] % bases[a]]
        if malos:
            raise RuntimeError(f"el paso de la foto de {malos} no es multiplo del paso base de orderflow_paso")
        declarados = await declara_parada_anterior(pool, own, inicio)
        LOGGER.info("libro_start pasos=%s banda=%s foto_s=%d parada_anterior_declarada=%d",
                    {k: str(v) for k, v in PASOS.items()}, BANDA, FOTO_S, declarados)
    except BaseException:
        await pool.close()
        await own.close()
        raise
    libros = {v: {a: Libro(v, a) for a in ACTIVOS} for v in VENUES}
    todos = [lib for por_activo in libros.values() for lib in por_activo.values()]
    alm = Almacen(inicio)
    salud: dict[str, Any] = {"caidas": defaultdict(int), "mal_formados": defaultdict(int),
                             "reconexiones": defaultdict(int), "avisos": 0, "avisos_fallidos": 0}
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    cliente = httpx.AsyncClient(headers={"User-Agent": "coinalyze-libro"})
    lock_monitor = asyncio.create_task(monitor_service_lock(own), name="service-lock")
    tareas = [
        asyncio.create_task(fotografo(todos, alm), name="fotografo"),
        asyncio.create_task(escritor(pool, own, alm, todos, inicio, salud), name="escritor"),
        asyncio.create_task(relevo(pool, todos, bases, salud), name="relevo"),
        asyncio.create_task(latido(pool, own, todos, alm, salud), name="latido"),
        asyncio.create_task(poda(pool, own), name="poda"),
        *(asyncio.create_task(escucha(VENUES[v], libros[v], salud, cliente), name=v) for v in VENUES),
    ]
    try:
        await wait_for_stop_or_lock_loss(stop, lock_monitor, critical_tasks=tuple(tareas))
    finally:
        # El instante en que se deja de escuchar, ANTES de cancelar nada: la cobertura acaba aqui.
        parando = time.time()
        for lib in todos:
            if lib.valido:
                lib.cob.cierra(parando)
        for tarea in tareas:
            tarea.cancel()
        lock_monitor.cancel()
        await asyncio.gather(*tareas, lock_monitor, return_exceptions=True)
        await cliente.aclose()
        try:
            # El minuto en curso se escribe con lo que llego a cubrir y se declara: el proximo arranque declara lo que
            # nadie escucho desde el.
            await vuelca(pool, own, alm, todos, parando, inicio, salud, apagando=True)
        except Exception:
            LOGGER.exception("libro_drain_failed")
        await pool.close()
        await own.close()


if __name__ == "__main__":
    asyncio.run(run())
