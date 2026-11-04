"""151-A · LA CAPA HONDA DEL LIBRO: el dato lejos del precio, guardado aparte del libro vivo.

El libro vivo de los perps llega a +-0.1-0.3 % en BTC (lo que el websocket conoce ENTERO); los muros que se quieren ver
estan a +-2 %. Algunos venues publican por REST una foto mucho mas honda: OKX `books-full` (5000 niveles, sin agrupar) y
Bitget `merge-depth` (100 cubos AGRUPADOS). El servicio del libro (app/libro.py) pide una cada HONDA_S por (venue,
activo) que entra, escalonadas, y guarda en libro_honda, por lado, la escalera AL PASO de libro_foto (PASOS) DESDE EL
BORDE DEL ALCANCE VIVO HACIA FUERA, hasta +-TOPE del precio o el alcance de la foto, lo que llegue antes.

LAS REGLAS (decididas por el operador, 2026-11-03):
  NUNCA UN NIVEL A MEDIO CONOCER. Un nivel L se guarda solo si la foto lo cubre entero: en la compra si L >= el precio
      mas bajo de la foto; en la venta si L + paso <= el mas alto. Un cubo agrupado solo vale si PARTE el paso: el cubo
      (medido en cada foto: el mcd de las diferencias de sus precios) divide al paso, cada precio es multiplo del cubo
      y el cubo es [P, P + cubo) (borde inferior, como el nivel). Bitget agrupa la compra por SUELO, [P, P + c), y la
      venta por TECHO, (P - c, P]: medido el 2026-11-03 reagregando scale0 a scale1 (por techo casan 14/23, 8/10 y
      9/9 cubos de venta de BTC, ETH y SOL; por suelo, 0). Un cubo de techo nunca tiene los bordes de [L, L + paso):
      la venta de Bitget no entra, y la referencia lo dice.
  LO HONDO NO PISA LO VIVO. Dentro del alcance vivo manda el websocket; la capa honda empieza en el primer nivel que
      el vivo no conoce entero (`junta` lo aplica tambien al leer, contra el alcance vivo de ESE momento).
  RANCIA. Una foto honda con mas de RANCIA_S (hora del venue contra el instante que se sirve) no cuenta como conocida:
      se sirve su hora y su alcance, sin niveles.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from math import gcd
from pathlib import Path
from typing import Any

import asyncpg
import httpx

from app.db import ServiceOwnership, ServiceOwnershipLost, fenced_transaction
from app.libro import PASOS, VENUES, Lado, Libro, niveles

LOGGER = logging.getLogger(__name__)
HONDA_S = 30  # una foto honda por (venue, activo) cada HONDA_S, escalonadas dentro del periodo
RANCIA_S = 75  # una foto honda mas vieja no cuenta como conocida
TOPE = Decimal("0.02")  # hasta +-2 % del precio
CRUDOS = "LIBRO_HONDA_CRUDOS"  # si se define, un directorio donde se guarda la respuesta CRUDA de cada foto (evidencia)


@dataclass(frozen=True)
class Fuente:
    venue: str
    activo: str
    url: str
    formato: str  # okx | bitget
    agrupa: dict[str, str]  # lado -> exacto | suelo | techo (como agrupa el venue los precios de ese lado)


def _okx(venue: str, activo: str) -> Fuente:
    inst = VENUES[venue].instrumentos[activo]
    return Fuente(venue, activo, f"https://www.okx.com/api/v5/market/books-full?instId={inst}&sz=5000", "okx",
                  {"b": "exacto", "a": "exacto"})


def _bitget(activo: str, precision: str) -> Fuente:
    return Fuente("bitget_usdt", activo, "https://api.bitget.com/api/v2/mix/market/merge-depth?symbol="
                  f"{VENUES['bitget_usdt'].instrumentos[activo]}&productType=usdt-futures&precision={precision}"
                  "&limit=max", "bitget", {"b": "suelo", "a": "techo"})


# Lo que entra: la foto REST alcanza al menos el DOBLE que el libro vivo (medido el 2026-11-03, entrega 151-A).
FUENTES: tuple[Fuente, ...] = (
    _okx("okx_swap", "BTC"), _okx("okx_swap", "ETH"), _okx("okx_spot", "BTC"), _okx("okx_spot", "ETH"),
    _bitget("BTC", "scale2"),  # cubo 10 = el paso 10
    _bitget("SOL", "scale1"),  # cubo 0.01 parte el paso 0.02
)
FUERA: dict[str, str] = {
    "binance_usdm": "el venue no publica mas: su REST da 1000 niveles, los mismos que ya casa el libro vivo",
    "bybit_linear": "el venue no publica mas: su REST da 500 niveles, menos que los 1000 del websocket",
    "binance_spot": "el venue no publica mas: el libro vivo ya casa la foto REST de 5000 niveles",
    "bybit_spot": "el venue no publica mas: su REST da 200 niveles, menos que los 1000 del websocket",
    "coinbase_spot": "el libro vivo ya es el libro entero",
    "deribit_perp": "el libro vivo ya es el libro entero",
    "okx_swap SOL": "el libro vivo ya pasa de +-2 % (400 niveles a 0.01 son +-4 USD, ~4.3 %)",
    "okx_spot SOL": "el libro vivo ya pasa de +-2 % (400 niveles a 0.01 son +-4 USD, ~4.3 %)",
    "bitget_usdt ETH": "merge-depth scale1 (cubo 0.1) alcanza +-10 USD, menos del doble del vivo (+-12-15); scale2 "
                       "(cubo 1) no parte el paso 0.5",
    "bitget_usdt venta": "Bitget agrupa la venta por techo, (P - c, P]: sus bordes no coinciden con los del nivel",
}


@dataclass
class Foto:
    ts_ms: int
    lados: dict[str, list[tuple[Decimal, Decimal]]]  # b | a -> (precio, cantidad en base), del mejor hacia fuera
    bytes_red: int = 0


def parsea(fuente: Fuente, cuerpo: bytes) -> Foto:
    """La respuesta CRUDA del venue, en Decimal exacto (los numeros JSON de Bitget no pasan por float)."""
    j = json.loads(cuerpo, parse_float=Decimal, parse_int=Decimal)
    if fuente.formato == "okx":
        if j.get("code") != "0":
            raise ValueError(f"okx code={j.get('code')} msg={j.get('msg')}")
        d = j["data"][0]
        mult = VENUES[fuente.venue].multiplicador.get(fuente.activo, Decimal(1))
        return Foto(int(d["ts"]), {k: [(Decimal(x[0]), Decimal(x[1]) * mult) for x in d[campo]]
                                   for k, campo in (("b", "bids"), ("a", "asks"))})
    if j.get("code") != "00000":
        raise ValueError(f"bitget code={j.get('code')} msg={j.get('msg')}")
    d = j["data"]
    return Foto(int(d["ts"]), {k: [(Decimal(x[0]), Decimal(x[1])) for x in d[campo]]
                               for k, campo in (("b", "bids"), ("a", "asks"))})


def cubo(precios: list[Decimal]) -> Decimal | None:
    """El cubo REAL de una foto: el maximo comun divisor de las diferencias entre sus precios."""
    ps = sorted(set(precios))
    if len(ps) < 2:
        return None
    e = min(p.as_tuple().exponent for p in ps)  # type: ignore[type-var]
    esc = Decimal(1).scaleb(-int(e))
    g = 0
    for x, y in zip(ps, ps[1:], strict=False):
        g = gcd(g, int((y - x) * esc))
    return Decimal(g) / esc


def parte(precios: list[Decimal], paso: Decimal, agrupa: str) -> bool:
    """Un lado vale si su cubo PARTE el paso: [P, P + c) (exacto o suelo), c divide al paso y cada P es multiplo de c."""
    c = cubo(precios)
    return agrupa in ("exacto", "suelo") and c is not None and paso % c == 0 and all(p % c == 0 for p in precios)


def _suelo(x: Decimal, paso: Decimal) -> Decimal:
    return (x / paso).to_integral_value(rounding=ROUND_FLOOR) * paso


def _techo(x: Decimal, paso: Decimal) -> Decimal:
    return (x / paso).to_integral_value(rounding=ROUND_CEILING) * paso


def escalera_honda(pares: list[tuple[Decimal, Decimal]], lado: str, paso: Decimal, vivo: Decimal,
                   precio: Decimal) -> tuple[Decimal, list[Decimal], Decimal] | None:
    """(primer nivel hondo, cantidades hacia fuera, alcance de la foto) de un lado, o None si no queda ni un nivel.
    Compra: el vivo conoce entero L >= vivo; lo hondo empieza en techo(vivo) - paso y baja mientras L >= el precio
    mas bajo de la foto y L >= suelo(precio * (1 - TOPE)). Venta: el vivo conoce L + paso <= vivo; lo hondo empieza
    en suelo(vivo) y sube mientras L + paso <= el precio mas alto y L <= suelo(precio * (1 + TOPE))."""
    if not pares:
        return None
    ps = [p for p, _ in pares]
    if lado == "b":
        alcance = min(ps)
        desde = _techo(vivo, paso) - paso
        fin = max(_techo(alcance, paso), _suelo(precio * (1 - TOPE), paso))
        n = int((desde - fin) / paso) + 1
        dentro = {p: q for p, q in pares if p < desde + paso}  # niveles() suma desde el precio mas alto
    else:
        alcance = max(ps)
        desde = _suelo(vivo, paso)
        fin = min(_suelo(alcance - paso, paso), _suelo(precio * (1 + TOPE), paso))
        n = int((fin - desde) / paso) + 1
        dentro = {p: q for p, q in pares if p >= desde}
    if n < 1:
        return None
    ld = Lado()
    ld.carga(dentro)
    return desde, niveles(ld, desde, paso, n, lado == "b"), alcance


def fila(fuente: Fuente, f: Foto, ts: int, vivo: tuple[Decimal, Decimal], precio: Decimal,
         nombre: str) -> tuple[Any, ...] | None:
    """La fila de libro_honda, o None si ningun lado deja un nivel hondo."""
    paso = PASOS[fuente.activo]
    lados: dict[str, tuple[Decimal, list[Decimal], Decimal] | None] = {}
    for k, v in (("b", vivo[0]), ("a", vivo[1])):
        pares = f.lados[k]
        ok = parte([p for p, _ in pares], paso, fuente.agrupa[k])
        lados[k] = escalera_honda(pares, k, paso, v, precio) if ok else None
    if lados["b"] is None and lados["a"] is None:
        return None
    c = cubo([p for p, _ in f.lados["b"] + f.lados["a"]]) or paso
    b, a = lados["b"], lados["a"]
    return (datetime.fromtimestamp(ts, UTC), fuente.venue, fuente.activo, datetime.fromtimestamp(f.ts_ms / 1000, UTC),
            nombre, paso, c, precio, vivo[0], vivo[1], b[0] if b else None, b[1] if b else None,
            a[0] if a else None, a[1] if a else None, b[2] if b else None, a[2] if a else None, f.bytes_red)


HONDA_SQL = """INSERT INTO libro_honda(ts,venue,symbol,ts_libro,fuente,paso,cubo,precio,vivo_compra,vivo_venta,
                                      compra_nivel,compras,venta_nivel,ventas,alcance_compra,alcance_venta,bytes_red)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::numeric[],$13,$14::numeric[],$15,$16,$17)
               ON CONFLICT DO NOTHING"""


def nombre_de(fuente: Fuente) -> str:
    return fuente.url.split("/api/")[1]


async def una(cliente: httpx.AsyncClient, fuente: Fuente, lib: Libro, ts: int, pool: asyncpg.Pool,
              own: ServiceOwnership, crudos: Path | None) -> str:
    """Una foto honda. Sin libro vivo valido no hay borde desde el que empezar: no se pide."""
    m = lib.mejores()
    if not lib.valido or m is None:
        return "sin_vivo"
    r = await cliente.get(fuente.url, timeout=10)
    r.raise_for_status()
    f = parsea(fuente, r.content)
    f.bytes_red = r.num_bytes_downloaded
    m, vivo = lib.mejores(), lib.alcances()  # el vivo del instante en que llega la foto
    if not lib.valido or m is None:
        return "sin_vivo"
    t = fila(fuente, f, ts, vivo, (m[0] + m[1]) / 2, nombre_de(fuente))
    if crudos is not None:
        (crudos / f"{fuente.venue}_{fuente.activo}_{ts}.json").write_bytes(r.content)
    if t is None:
        return "sin_niveles"
    async with pool.acquire() as conn:
        async with fenced_transaction(conn, own):
            await conn.execute(HONDA_SQL, *t)
    return "ok"


async def honda(libros: dict[str, dict[str, Libro]], pool: asyncpg.Pool, own: ServiceOwnership,
                cliente: httpx.AsyncClient) -> None:
    """Cada HONDA_S, una foto por fuente, escalonadas: la fuente i en el segundo i * HONDA_S / len(FUENTES)."""
    crudos = Path(os.environ[CRUDOS]) if os.environ.get(CRUDOS) else None
    hueco = HONDA_S // len(FUENTES)
    siguiente = int(time.time()) // HONDA_S * HONDA_S + HONDA_S
    while True:
        for i, fuente in enumerate(FUENTES):
            ts = siguiente + i * hueco
            await asyncio.sleep(max(0.0, ts - time.time()))
            try:
                res = await una(cliente, fuente, libros[fuente.venue][fuente.activo], ts, pool, own, crudos)
                if res != "ok":
                    LOGGER.info("libro_honda_sin_fila venue=%s activo=%s motivo=%s", fuente.venue, fuente.activo, res)
            except ServiceOwnershipLost:
                raise
            except Exception as exc:  # noqa: BLE001 - la foto siguiente lo vuelve a intentar; lo que falta, falta
                LOGGER.warning("libro_honda_fallo venue=%s activo=%s error=%s", fuente.venue, fuente.activo, exc)
        siguiente += HONDA_S


# --------------------------------------------------------------------------------------------- la lectura
def rancia(ts_libro: datetime, ahora: datetime) -> bool:
    return (ahora - ts_libro).total_seconds() > RANCIA_S


def junta(honda_lado: tuple[Decimal, list[Decimal]] | None, lado: str, paso: Decimal, vivo: Decimal,
          ts_libro: datetime, ahora: datetime) -> tuple[Decimal, list[Decimal]] | None:
    """La capa honda de un lado contra el alcance vivo de AHORA: sin lo que el vivo ya conoce entero (manda el
    websocket) y nada si la foto es rancia. Lo que queda empieza donde acaba lo vivo, o mas lejos."""
    if honda_lado is None or rancia(ts_libro, ahora):
        return None
    desde, qs = honda_lado
    if lado == "b":
        tope = _techo(vivo, paso) - paso  # el primer nivel que el vivo no conoce entero
        quita = max(0, int((desde - tope) / paso))
        return (desde - quita * paso, qs[quita:]) if quita < len(qs) else None
    tope = _suelo(vivo, paso)
    quita = max(0, int((tope - desde) / paso))
    return (desde + quita * paso, qs[quita:]) if quita < len(qs) else None
