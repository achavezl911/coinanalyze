"""OF-4a · LA LECTURA del libro: lo que sirve /api/libro/* desde las tablas que escribe app/libro.py (la foto agregada de
un rango, para el mapa de liquidez) y el libro VIVO por websocket desde el relevo NOTIFY del colector (para la
escalera).

Cada respuesta dice QUE es, con que paso, en que unidad y de que venues. Cantidades y niveles en TEXTO decimal exacto:
asi lo servido se compara con lo guardado (K110 d). Los topes no recortan en silencio: 422 diciendo cual.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

import asyncpg
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.libro import BANDA, CANAL, FOTO_S, PASOS, RELEVO_NIVELES, RELEVO_S, VENUES
from app.orderflow import nivel_de
from app.orderflow_lectura import Peticion, activo_de, instante, iso, pasos, texto

LOGGER = logging.getLogger(__name__)
TOPE_FOTOS = 2000
TOPE_HUECOS = 200
RANGO_FOTOS = timedelta(days=7)
# P3 (campana 144): con 3 clientes de los nueve venues (~32 avisos/s cada uno) la API gasto 12.8 % de un nucleo, ~4 %
# por cliente con parametros distintos (los que comparten symbol, paso y niveles comparten la transformacion).
TOPE_CLIENTES = 10
LATIDO_S = 15.0  # sin avisos, el websocket manda un latido: dice el estado del relevo y descubre a quien se fue
NIVELES_VIVO = 50  # por omision, por lado
NIVEL = "borde INFERIOR del nivel: floor(precio / paso) * paso, en aritmetica decimal exacta (como OF-1)"
ORDEN = ("compras.cantidades[i] es el nivel compras.desde - i * paso (de la mejor compra hacia abajo); "
         "ventas.cantidades[i] es ventas.desde + i * paso (de la mejor venta hacia arriba); 0 = nivel sin ordenes")
ALCANCE = ("hasta donde el libro se conoce de verdad: en los venues que lo mantienen por websocket, su nivel mas "
           "profundo; en Binance, el de su foto REST. Un nivel que el alcance corta por la mitad no se guarda ni se "
           "sirve: nunca un nivel a medio conocer, y lo que no se conoce no se rellena")
AVISO = ("el libro tiene poca memoria: mas de ~30 minutos atras, el mapa es un REGISTRO de donde estuvo la "
         "liquidez, no la que hay; sumar venues mezcla USD (Coinbase, Deribit), USDT y USDC sin convertir")


def venues_de(valor: str | None) -> list[str]:
    if not valor:
        return list(VENUES)
    pedidos = [v.strip() for v in valor.split(",") if v.strip()]
    desconocidos = sorted(set(pedidos) - set(VENUES))
    if desconocidos or not pedidos:
        raise Peticion(f"venues desconocidos: {', '.join(desconocidos) or '(vacio)'}. Admitidos: {', '.join(VENUES)}")
    return [v for v in VENUES if v in set(pedidos)]


def paso_de(valor: str | None, guardado: Decimal) -> Decimal:
    if not valor:
        return guardado
    try:
        paso = Decimal(valor)
    except InvalidOperation as exc:
        raise Peticion(f"paso no es un numero: {valor!r}") from exc
    if not paso.is_finite() or paso <= 0 or paso % guardado != 0:
        raise Peticion(f"paso tiene que ser un multiplo entero positivo de {texto(guardado)}")
    return paso


def reagrega(desde: Decimal, cantidades: list[Decimal], fino: Decimal, paso: Decimal,
             abajo: bool) -> tuple[Decimal, list[Decimal]] | None:
    """Los niveles de `fino` (desde, desde -+ i*fino) sumados a niveles de `paso` (multiplo de fino). Un nivel grueso
    del borde que los finos no cubren entero NO sale: la compra sigue hasta el ultimo nivel grueso cuyo borde inferior
    esta dentro de lo conocido; la venta, hasta el ultimo cuyo borde superior lo esta. Del lado del mejor precio, la
    parte del nivel grueso que queda al otro lado del mejor se sabe vacia."""
    if paso == fino:
        return desde, cantidades
    suma: dict[Decimal, Decimal] = {}
    for i, q in enumerate(cantidades):
        n = nivel_de(desde - i * fino if abajo else desde + i * fino, paso)
        suma[n] = suma.get(n, Decimal(0)) + q
    ultimo = desde - (len(cantidades) - 1) * fino if abajo else desde + (len(cantidades) - 1) * fino
    enteros = sorted((n for n in suma if (n >= ultimo if abajo else n + paso <= ultimo + fino)), reverse=abajo)
    if not enteros:
        return None
    return enteros[0], [suma[n] for n in enteros]


FOTOS_SQL = """
SELECT ts, venue, ts_libro, compra, venta, paso, compra_nivel, compras, venta_nivel, ventas, alcance_compra,
       alcance_venta
  FROM libro_foto
 WHERE symbol = $1 AND venue = ANY($2::text[]) AND ts >= $3 AND ts < $4
   AND extract(epoch FROM ts)::bigint % $5 = 0
 ORDER BY ts, venue
 LIMIT $6
"""


def _lado(desde: Decimal, cantidades: list[Decimal]) -> dict[str, Any]:
    return {"desde": texto(desde), "cantidades": [texto(q) for q in cantidades]}


async def fotos(conn: Any, *, symbol: str, desde: str | None, hasta: str | None, venues: str | None,
                paso: str | None, cada: int | None) -> dict[str, Any]:
    activo = activo_de(symbol)
    a, b = instante(desde, "desde"), instante(hasta, "hasta")
    if b <= a:
        raise Peticion("hasta tiene que ser posterior a desde")
    if b - a > RANGO_FOTOS:
        raise Peticion(f"la ventana maxima es {RANGO_FOTOS.days} dias")
    vs = venues_de(venues)
    guardado = PASOS[activo]
    p = paso_de(paso, guardado)
    c = cada or FOTO_S
    if c % FOTO_S:
        raise Peticion(f"cada tiene que ser un multiplo de {FOTO_S} s (una foto cada {FOTO_S} s)")
    filas = await conn.fetch(FOTOS_SQL, activo, vs, a, b, c, TOPE_FOTOS + 1)
    if len(filas) > TOPE_FOTOS:
        raise Peticion(f"mas de {TOPE_FOTOS} fotos: pide un cada mayor, menos venues o un rango menor")
    salida = []
    for f in filas:
        compras = reagrega(f["compra_nivel"], list(f["compras"]), f["paso"], p, True)
        ventas = reagrega(f["venta_nivel"], list(f["ventas"]), f["paso"], p, False)
        salida.append({
            "ts": iso(f["ts"]), "venue": f["venue"], "ts_libro": iso(f["ts_libro"]),
            "compra": texto(f["compra"]), "venta": texto(f["venta"]),
            "compras": _lado(*compras) if compras else None, "ventas": _lado(*ventas) if ventas else None,
            "alcance": {"compra": texto(f["alcance_compra"]), "venta": texto(f["alcance_venta"])},
        })
    return {"que": "las fotos del libro: por instante y venue, la cantidad en cada nivel de compra y de venta",
            "symbol": activo, "desde": iso(a), "hasta": iso(b), "venues": vs, "paso": texto(p),
            "paso_guardado": texto(guardado), "cada": c, "nivel": NIVEL, "orden": ORDEN, "unidad": "base",
            "alcance": ALCANCE, "aviso": AVISO, "tope_fotos": TOPE_FOTOS, "fotos": salida}


async def cobertura(conn: Any, *, symbol: str, desde: str | None, hasta: str | None,
                    venues: str | None) -> dict[str, Any]:
    activo = activo_de(symbol)
    a, b = instante(desde, "desde"), instante(hasta, "hasta")
    if b <= a:
        raise Peticion("hasta tiene que ser posterior a desde")
    if b - a > RANGO_FOTOS:
        raise Peticion(f"la ventana maxima es {RANGO_FOTOS.days} dias")
    vs = venues_de(venues)
    esperados = int((b - a) // timedelta(minutes=1))
    filas = {f["venue"]: f for f in await conn.fetch(
        """SELECT venue, count(*) AS filas, count(*) FILTER (WHERE segundos = 60) AS completos,
                  sum(segundos)::bigint AS segundos, sum(fotos)::bigint AS fotos, sum(saltos)::bigint AS saltos,
                  sum(resincronizaciones)::bigint AS resincronizaciones, sum(reconexiones)::bigint AS reconexiones
             FROM libro_cobertura
            WHERE symbol = $1 AND venue = ANY($2::text[]) AND ts >= $3 AND ts < $4
            GROUP BY venue""", activo, vs, a, b)}
    huecos: dict[str, list[dict[str, Any]]] = {}
    for f in await conn.fetch(
        """SELECT exchange, start_ts, end_ts, evidence_type, status FROM data_gap
            WHERE feed = 'libro' AND symbol = $1 AND exchange = ANY($2::text[]) AND start_ts < $4 AND end_ts > $3
            ORDER BY exchange, start_ts LIMIT $5""", activo, vs, a, b, TOPE_HUECOS + 1):
        huecos.setdefault(f["exchange"], []).append({
            "desde": iso(f["start_ts"]), "hasta": iso(f["end_ts"]), "evidencia": f["evidence_type"],
            "estado": f["status"]})
    claves = ("filas", "completos", "segundos", "fotos", "saltos", "resincronizaciones", "reconexiones")
    return {"que": "la cobertura del libro: por venue, minutos con fila, minutos completos (60 s con libro valido), "
                   "fotos, saltos de numeracion y huecos declarados en data_gap; un minuto incompleto se declara y no "
                   "se rellena", "symbol": activo, "desde": iso(a), "hasta": iso(b), "fotos_por_minuto_completo":
            60 // FOTO_S, "tope_huecos": TOPE_HUECOS,
            "venues": [{"venue": v, "minutos_esperados": esperados,
                        **{k: int(filas[v][k]) if v in filas else 0 for k in claves},
                        "huecos_declarados": huecos.get(v, [])} for v in vs]}


async def referencia(conn: Any) -> dict[str, Any]:
    return {
        "que": "la referencia del libro: venues, canales, numeracion, foto, alcance, retencion, topes y relevo en vivo",
        "venues": [{"venue": v.venue, "mercado": v.mercado, "instrumentos": v.instrumentos, "canal": v.canal,
                    "numeracion": v.numeracion, "unidad": v.unidad} for v in VENUES.values()],
        "libro_valido": "sincronizado con su numeracion, con la conexion entregando y sin cruzar; un salto, un libro "
                        "cruzado o fuera de su alcance lo invalida: deja de fotografiarse y de publicarse hasta "
                        "resincronizar, y ese tiempo no cuenta como cobertura",
        "foto": {"cada_s": FOTO_S, "pasos": {k: texto(v) for k, v in PASOS.items()},
                 "paso_base_orderflow": {k: texto(v) for k, v in sorted((await pasos(conn)).items())},
                 "banda_niveles_por_lado": BANDA, "nivel": NIVEL, "orden": ORDEN, "alcance": ALCANCE,
                 "unidad": "base (OKX swap: contratos x ctVal; Deribit BTC/ETH: USD / precio del nivel)"},
        "cobertura": f"por minuto, segundos con libro valido; un minuto completo tiene {60 // FOTO_S} fotos; los "
                     "incompletos se declaran en data_gap (feed libro, metodo libro_sin_cobertura)",
        "retencion_dias": get_settings().LIBRO_RETENTION_DAYS,
        "topes": {"fotos": TOPE_FOTOS, "rango_dias": RANGO_FOTOS.days, "huecos": TOPE_HUECOS,
                  "clientes_vivo": TOPE_CLIENTES, "niveles_vivo": RELEVO_NIVELES},
        "vivo": {"ruta": "/api/libro/vivo (websocket)", "relevo": f"NOTIFY {CANAL} desde el colector, como mucho cada "
                 f"{RELEVO_S} s por libro; la API escucha con una conexion y reparte, siempre lo ultimo de cada venue",
                 "parametros": "symbol, venues, paso (multiplo del paso base), niveles (1-"
                               f"{RELEVO_NIVELES}, por omision {NIVELES_VIVO})",
                 "horas": "ts_libro_ms (hora del venue), recibido_ms (llego al colector), emitido_ms (salio del "
                          "colector), api_ms (llego a la API): epoch en ms"},
        "aviso": AVISO,
    }


# --------------------------------------------------------------------------------------------- el libro vivo
class Cliente:
    """Un websocket: lo ultimo de cada venue que le toca, sin cola. Si va lento, se salta lo viejo (es una escalera)."""

    def __init__(self, activo: str, venues: list[str]) -> None:
        self.activo, self.venues = activo, set(venues)
        self.pendientes: dict[str, dict[str, Any]] = {}
        self.hay = asyncio.Event()

    def pon(self, d: dict[str, Any]) -> None:
        if d.get("s") == self.activo and d.get("v") in self.venues:
            self.pendientes[d["v"]] = d
            self.hay.set()


class Relevo:
    """UNA conexion por proceso que escucha el NOTIFY del colector y reparte a los clientes."""

    def __init__(self) -> None:
        self.clientes: set[Cliente] = set()
        self.ultimo: dict[tuple[str, str], dict[str, Any]] = {}
        self.estado = "sin escuchar"
        self.tarea: asyncio.Task[None] | None = None

    def arranca(self, dsn: str) -> None:
        if self.tarea is None or self.tarea.done():
            self.tarea = asyncio.create_task(self._escucha(dsn), name="libro-relevo")

    def _aviso(self, _conn: Any, _pid: int, _canal: str, carga: str) -> None:
        try:
            d = json.loads(carga)
        except ValueError:
            return
        d["l"] = int(time.time() * 1000)
        self.ultimo[(d.get("v"), d.get("s"))] = d
        for c in list(self.clientes):
            c.pon(d)

    async def _escucha(self, dsn: str) -> None:
        while True:
            conn = None
            try:
                conn = await asyncpg.connect(dsn=dsn, server_settings={"application_name": "coinalyze-api-libro"})
                await conn.add_listener(CANAL, self._aviso)
                self.estado = "escuchando"
                while True:
                    await asyncio.sleep(10)
                    await asyncio.wait_for(conn.fetchval("SELECT 1"), timeout=10)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - se reintenta; mientras, los clientes lo ven en el latido
                self.estado = f"caido: {type(exc).__name__}"
                LOGGER.warning("libro_relevo_caido error=%s", exc)
            finally:
                if conn is not None:
                    with contextlib.suppress(Exception):
                        await conn.close()
            self.ultimo.clear()  # sin escuchar no se sabe que es lo ultimo: nada se sirve como vivo
            await asyncio.sleep(3)


RELEVO = Relevo()


def _escalera(pares: list[list[str]], mejor: Decimal, base: Decimal, n: int, paso: Decimal, niveles: int,
              abajo: bool) -> list[list[str]]:
    """Los niveles del aviso (al paso base, solo los que tienen cantidad; n CONOCIDOS desde el mejor) al `paso` del
    cliente, sin el nivel grueso del borde que el aviso no cubre entero, y como mucho `niveles`."""
    desde = nivel_de(mejor, base)
    denso = [Decimal(0)] * n
    for nivel, q in pares:
        k = int(abs(Decimal(nivel) - desde) / base)
        if k < n:
            denso[k] = Decimal(q)
    r = reagrega(desde, denso, base, paso, abajo)
    if r is None:
        return []
    inicio, qs = r
    return [[texto(inicio - i * paso if abajo else inicio + i * paso), texto(q)] for i, q in enumerate(qs[:niveles])]


def mensaje(d: dict[str, Any], base: Decimal, paso: Decimal, niveles: int) -> dict[str, Any]:
    if "x" in d:
        return {"tipo": "sin_libro", "venue": d.get("v"), "symbol": d.get("s"), "motivo": d["x"],
                "emitido_ms": d.get("e"), "api_ms": d.get("l")}
    compra, venta = Decimal(d["b"]), Decimal(d["a"])
    return {"tipo": "libro", "venue": d["v"], "symbol": d["s"], "ts_libro_ms": d["t"], "recibido_ms": d["r"],
            "emitido_ms": d["e"], "api_ms": d["l"], "compra": d["b"], "venta": d["a"], "paso": texto(paso),
            "compras": _escalera(d["c"], compra, base, int(d["kc"]), paso, niveles, True),
            "ventas": _escalera(d["w"], venta, base, int(d["kv"]), paso, niveles, False)}


def parametros(query: dict[str, str], bases: dict[str, Decimal]) -> tuple[str, list[str], Decimal, int]:
    sobran = sorted(set(query) - {"symbol", "venues", "paso", "niveles"})
    if sobran:
        raise Peticion(f"parametros no reconocidos: {', '.join(sobran)}. Admitidos: symbol, venues, paso, niveles")
    activo = activo_de(query.get("symbol") or "")
    vs = venues_de(query.get("venues"))
    paso = paso_de(query.get("paso"), bases[activo])
    try:
        niveles = int(query.get("niveles") or NIVELES_VIVO)
    except ValueError as exc:
        raise Peticion("niveles tiene que ser un entero") from exc
    if not 1 <= niveles <= RELEVO_NIVELES:
        raise Peticion(f"niveles tiene que estar entre 1 y {RELEVO_NIVELES} (lo que trae el relevo al paso base)")
    return activo, vs, paso, niveles


async def rechaza(ws: WebSocket, status: int, motivo: str) -> None:
    """Un apreton que no se puede honrar: HTTP `status` con su porque (si el servidor no sabe, cierre 1008)."""
    try:
        await ws.send_denial_response(JSONResponse(status_code=status, content={"detail": motivo}))
    except RuntimeError:
        await ws.close(code=1008, reason=motivo[:120])


async def vivo(ws: WebSocket, pool: asyncpg.Pool, dsn: str, prohibido: str | None) -> None:
    """El libro vivo de un activo por websocket: un mensaje `inicio`, despues un `libro` por venue cada vez que el
    colector publica (lo ultimo; si el cliente va lento se salta lo viejo), `sin_libro` cuando un libro deja de ser
    valido y un `latido` cada LATIDO_S sin avisos."""
    if prohibido:
        await rechaza(ws, 403, prohibido)
        return
    async with pool.acquire() as conn:
        bases = await pasos(conn)
    try:
        activo, vs, paso, niveles = parametros(dict(ws.query_params), bases)
    except Peticion as exc:
        await rechaza(ws, 422, str(exc))
        return
    if len(RELEVO.clientes) >= TOPE_CLIENTES:
        await rechaza(ws, 503, f"ya hay {TOPE_CLIENTES} clientes del libro vivo")
        return
    await ws.accept()
    RELEVO.arranca(dsn)
    cliente = Cliente(activo, vs)
    RELEVO.clientes.add(cliente)
    base = bases[activo]
    try:
        await ws.send_json({"tipo": "inicio", "symbol": activo, "venues": vs, "paso": texto(paso),
                            "paso_base": texto(base), "niveles": niveles, "relevo": RELEVO.estado,
                            "as_of": iso(datetime.now(UTC))})
        for (v, s), d in list(RELEVO.ultimo.items()):
            if s == activo and v in vs:
                cliente.pon(d)
        while True:
            try:
                await asyncio.wait_for(cliente.hay.wait(), timeout=LATIDO_S)
            except TimeoutError:
                await ws.send_json({"tipo": "latido", "relevo": RELEVO.estado, "as_of": iso(datetime.now(UTC))})
                continue
            cliente.hay.clear()
            lote, cliente.pendientes = cliente.pendientes, {}
            for d in lote.values():
                # el aviso es UNO para todos los clientes: cada forma (paso, niveles) se calcula una vez
                hecho = d.setdefault("_m", {})
                if (paso, niveles) not in hecho:
                    hecho[(paso, niveles)] = json.dumps(mensaje(d, base, paso, niveles), separators=(",", ":"))
                await ws.send_text(hecho[(paso, niveles)])
    except (WebSocketDisconnect, RuntimeError, ConnectionError):
        pass
    finally:
        RELEVO.clientes.discard(cliente)
