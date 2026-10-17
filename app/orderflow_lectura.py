"""OF-1 · LA LECTURA del order-flow: lo que sirve /api/orderflow/* desde las tablas que escribe app/orderflow.py.

Cada respuesta dice QUE es, con que paso, en que unidad y de que venues. Volumenes y niveles salen en TEXTO
decimal exacto, no en float: asi lo servido se compara byte a byte con lo recalculado desde las celdas (K108 d).
Los topes no recortan en silencio: si una peticion los pasa, 422 diciendo cual.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import ROUND_FLOOR, Decimal, InvalidOperation
from typing import Any

from app.config import get_settings
from app.orderflow import ACTIVOS, MERCADOS, carga_config

MARCOS = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}  # minutos por vela
ORIGEN = datetime(2000, 1, 1, tzinfo=UTC)  # date_bin: las velas empiezan en minutos UTC multiplos del marco
TOPE_VELAS = 1500
TOPE_CELDAS = 50_000
TOPE_NIVELES = 20_000
TOPE_HUECOS = 200
RANGO_MAXIMO = timedelta(days=31)
RANGO_GRANDES = timedelta(days=366)
VALUE_AREA = Decimal("0.70")
NIVEL = "borde INFERIOR del nivel: floor(precio / paso) * paso, en aritmetica decimal exacta"
ALGORITMO_VA = (
    "Se parte del POC (el nivel de mayor volumen total; a igualdad, el de precio mas bajo). Mientras el volumen "
    "del area sea menor que el 70 % del total del perfil, se compara el nivel con volumen inmediatamente por "
    "encima del area con el inmediatamente por debajo y se anade el de mas volumen (a igualdad, el de arriba; si "
    "un lado se agota, el otro). VAL y VAH son los bordes inferiores de los niveles extremos: el area cubre "
    "[VAL, VAH + paso)."
)
# OF-2 (campana 142, P3): con OBJETIVO_NIVELES = 20, sobre 30 dias de velas reales de los seis marcos, la vela mediana
# toca 12-17 niveles y menos del 0.1 % pasa de 150.
OBJETIVO_NIVELES = 20
REGLA_PASO = (
    "paso=auto: el menor de la escalera 1, 2, 5, 10, 20, 50... veces el paso base con el que la vela MEDIANA de la "
    "ventana pedida (de las que tienen celdas; la mediana es el elemento n // 2 de la lista ordenada) toca como mucho "
    f"{OBJETIVO_NIVELES} niveles. Una vela toca los niveles que van del de su celda mas baja al de la mas alta. Nunca "
    "por debajo del paso base."
)


class Peticion(ValueError):
    """Un parametro que no se puede honrar: la ruta lo devuelve como 422 con este texto."""


def texto(valor: Decimal | int) -> str:
    if isinstance(valor, int):
        return str(valor)
    return "0" if valor == 0 else format(valor.normalize(), "f")


def iso(momento: datetime) -> str:
    return momento.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def instante(valor: str | None, nombre: str) -> datetime:
    if not valor:
        raise Peticion(f"falta {nombre} (ISO-8601 con zona)")
    try:
        momento = datetime.fromisoformat(valor)
    except ValueError as exc:
        raise Peticion(f"{nombre} no es ISO-8601: {valor!r}") from exc
    if momento.tzinfo is None:
        raise Peticion(f"{nombre} necesita zona horaria explicita")
    return momento.astimezone(UTC)


def activo_de(symbol: str) -> str:
    activo = symbol.upper()
    if activo not in ACTIVOS:
        raise Peticion(f"symbol tiene que ser uno de {', '.join(ACTIVOS)}")
    return activo


def venues_de(valor: str | None) -> list[str]:
    if not valor:
        return list(MERCADOS)
    pedidos = [v.strip() for v in valor.split(",") if v.strip()]
    desconocidos = sorted(set(pedidos) - set(MERCADOS))
    if desconocidos or not pedidos:
        raise Peticion(f"venues desconocidos: {', '.join(desconocidos) or '(vacio)'}. Admitidos: "
                       f"{', '.join(MERCADOS)}")
    return [v for v in MERCADOS if v in set(pedidos)]  # orden canonico, sin repetidos


def unidad_de(valor: str | None) -> str:
    unidad = valor or "base"
    if unidad not in ("base", "usd"):
        raise Peticion("unidad tiene que ser base o usd")
    return unidad


async def pasos(conn: Any) -> dict[str, Decimal]:
    return {r["symbol"]: Decimal(r["paso"]) for r in await conn.fetch(
        "SELECT symbol, paso::text AS paso FROM orderflow_paso")}


def paso_de(valor: str | None, base: Decimal) -> Decimal:
    if not valor:
        return base
    try:
        paso = Decimal(valor)
    except InvalidOperation as exc:
        raise Peticion(f"paso no es un numero: {valor!r}") from exc
    if not paso.is_finite() or paso <= 0 or paso % base != 0:
        raise Peticion(f"paso tiene que ser un multiplo entero positivo del paso base {texto(base)}")
    return paso


def paso_automatico(rangos: list[tuple[Decimal, Decimal]], base: Decimal) -> tuple[Decimal, int | None]:
    """(paso, niveles que toca la vela mediana) segun REGLA_PASO, sobre (nivel minimo, nivel maximo) de cada vela."""
    if not rangos:
        return base, None
    for e in range(12):
        for m in (1, 2, 5):
            p = base * m * 10**e
            n = sorted(int((hi / p).to_integral_value(ROUND_FLOOR) - (lo / p).to_integral_value(ROUND_FLOOR)) + 1
                       for lo, hi in rangos)[len(rangos) // 2]
            if n <= OBJETIVO_NIVELES:
                return p, n
    return p, n


def ventana(desde: datetime, hasta: datetime, maximo: timedelta, minutos: int = 1) -> None:
    if hasta <= desde:
        raise Peticion("hasta tiene que ser posterior a desde")
    if hasta - desde > maximo:
        raise Peticion(f"la ventana maxima es {maximo.days} dias")
    for nombre, momento in (("desde", desde), ("hasta", hasta)):
        if (momento - ORIGEN) % timedelta(minutes=minutos):
            raise Peticion(f"{nombre} tiene que caer en un borde de vela ({minutos} min, UTC)")


def poc_de(totales: dict[Decimal, Decimal]) -> Decimal | None:
    if not totales:
        return None
    mayor = max(totales.values())
    return min(n for n, t in totales.items() if t == mayor)


def value_area(totales: dict[Decimal, Decimal]) -> tuple[Decimal, Decimal, Decimal] | None:
    """(VAL, VAH, volumen del area) segun ALGORITMO_VA, sobre {nivel: volumen total}."""
    poc = poc_de(totales)
    if poc is None:
        return None
    niveles = sorted(totales)
    objetivo = sum(totales.values()) * VALUE_AREA
    i = j = niveles.index(poc)
    volumen = totales[poc]
    while volumen < objetivo:
        arriba = totales[niveles[j + 1]] if j + 1 < len(niveles) else None
        abajo = totales[niveles[i - 1]] if i > 0 else None
        if arriba is None and abajo is None:
            break
        if abajo is None or (arriba is not None and arriba >= abajo):
            j += 1
            volumen += totales[niveles[j]]
        else:
            i -= 1
            volumen += totales[niveles[i]]
    return niveles[i], niveles[j], volumen


CELDAS_SQL = """
SELECT {vela} AS vela, floor(nivel / $5) * $5 AS n,
       sum(compra_base) AS cb, sum(venta_base) AS vb, sum(compra_usd) AS cu, sum(venta_usd) AS vu,
       sum(compras)::bigint AS nc, sum(ventas)::bigint AS nv
  FROM orderflow_celda
 WHERE symbol = $1 AND venue = ANY($2::text[]) AND ts >= $3 AND ts < $4
 GROUP BY 1, 2 ORDER BY 1, 2
 LIMIT {tope}
"""
RANGOS_SQL = """
SELECT {vela} AS vela, min(nivel) AS lo, max(nivel) AS hi
  FROM orderflow_celda
 WHERE symbol = $1 AND venue = ANY($2::text[]) AND ts >= $3 AND ts < $4
 GROUP BY 1
"""
COBERTURA_SQL = """
SELECT {vela} AS vela, count(*) AS filas, count(*) FILTER (WHERE segundos = 60) AS completos,
       coalesce(sum(segundos), 0)::bigint AS segundos, coalesce(bool_and(definitivo), false) AS definitiva
  FROM orderflow_cobertura
 WHERE symbol = $1 AND venue = ANY($2::text[]) AND ts >= $3 AND ts < $4
 GROUP BY 1
"""


def _nivel_json(n: Decimal, compra: Decimal, venta: Decimal, ops: int) -> dict[str, Any]:
    return {"nivel": texto(n), "compra": texto(compra), "venta": texto(venta), "delta": texto(compra - venta),
            "total": texto(compra + venta), "operaciones": ops}


def _cobertura_json(fila: Any, esperados: int) -> dict[str, Any]:
    return {
        "minutos_esperados": esperados,
        "minutos_con_fila": int(fila["filas"]) if fila else 0,
        "minutos_completos": int(fila["completos"]) if fila else 0,
        "segundos": int(fila["segundos"]) if fila else 0,
        "completa": bool(fila) and int(fila["completos"]) == esperados,
        "definitiva": bool(fila) and bool(fila["definitiva"]) and int(fila["filas"]) == esperados,
    }


def _cabecera(que: str, activo: str, paso: Decimal, base: Decimal, venues: list[str], unidad: str | None,
              desde: datetime | None, hasta: datetime | None) -> dict[str, Any]:
    cab: dict[str, Any] = {"que": que, "symbol": activo, "paso": texto(paso), "paso_base": texto(base),
                           "nivel": NIVEL, "venues": venues}
    if unidad:
        cab["unidad"] = unidad
        cab["volumen"] = ("del AGRESOR: compra = operaciones en que el agresor compro, venta = en que vendio; "
                          f"en {'unidades del activo' if unidad == 'base' else 'USD (precio x base)'}")
    if desde is not None and hasta is not None:
        cab["desde"], cab["hasta"] = iso(desde), iso(hasta)
    return cab


async def footprint(conn: Any, *, symbol: str, desde: str | None, hasta: str | None, marco: str,
                    paso: str | None, venues: str | None, unidad: str | None) -> dict[str, Any]:
    activo = activo_de(symbol)
    if marco not in MARCOS:
        raise Peticion(f"marco tiene que ser uno de {', '.join(MARCOS)}")
    minutos = MARCOS[marco]
    a, b = instante(desde, "desde"), instante(hasta, "hasta")
    ventana(a, b, RANGO_MAXIMO, minutos)
    n_velas = (b - a) // timedelta(minutes=minutos)
    if n_velas > TOPE_VELAS:
        raise Peticion(f"{n_velas} velas pasan el tope de {TOPE_VELAS}: pide un marco mayor o un rango menor")
    base = (await pasos(conn))[activo]
    p, vs, u = paso_de(None if paso == "auto" else paso, base), venues_de(venues), unidad_de(unidad)
    vela = f"date_bin(interval '{minutos} minutes', ts, '{ORIGEN.isoformat()}'::timestamptz)"
    auto: dict[str, Any] | None = None
    if paso == "auto":
        rangos = [(f["lo"], f["hi"]) for f in await conn.fetch(RANGOS_SQL.format(vela=vela), activo, vs, a, b)]
        p, mediana = paso_automatico(rangos, base)
        auto = {"regla": REGLA_PASO, "objetivo_niveles": OBJETIVO_NIVELES, "velas_con_celdas": len(rangos),
                "niveles_vela_mediana": mediana}
    filas = await conn.fetch(CELDAS_SQL.format(vela=vela, tope=TOPE_CELDAS + 1), activo, vs, a, b, p)
    if len(filas) > TOPE_CELDAS:
        raise Peticion(f"mas de {TOPE_CELDAS} celdas: pide un paso mayor o un rango menor")
    cob = {f["vela"]: f for f in await conn.fetch(COBERTURA_SQL.format(vela=vela), activo, vs, a, b)}
    por_vela: dict[datetime, list[Any]] = {}
    for f in filas:
        por_vela.setdefault(f["vela"], []).append(f)
    c, v = ("cb", "vb") if u == "base" else ("cu", "vu")
    velas = []
    for k in range(n_velas):
        inicio = a + timedelta(minutes=minutos * k)
        niveles = por_vela.get(inicio, [])
        compra = sum((f[c] for f in niveles), Decimal(0))
        venta = sum((f[v] for f in niveles), Decimal(0))
        totales = {f["n"]: f[c] + f[v] for f in niveles}
        poc = poc_de(totales)
        va = value_area(totales)
        velas.append({
            "ts": iso(inicio),
            "compra": texto(compra), "venta": texto(venta), "delta": texto(compra - venta),
            "total": texto(compra + venta), "operaciones": sum(int(f["nc"] + f["nv"]) for f in niveles),
            "poc": texto(poc) if poc is not None else None,
            "value_area": {"val": texto(va[0]), "vah": texto(va[1]), "volumen": texto(va[2])} if va else None,
            "cobertura": _cobertura_json(cob.get(inicio), minutos * len(vs)),
            "niveles": [_nivel_json(f["n"], f[c], f[v], int(f["nc"] + f["nv"])) for f in niveles],
        })
    return {**_cabecera("footprint: por vela y nivel, volumen del agresor comprador y vendedor", activo, p, base,
                        vs, u, a, b),
            "marco": marco, "velas_alineadas": "date_bin sobre UTC: cada vela empieza en un multiplo del marco",
            "poc": "por vela, el nivel de mayor total; a igualdad, el de precio mas bajo",
            "value_area": {"porcentaje": 70, "algoritmo": "por vela, el mismo que el perfil: " + ALGORITMO_VA},
            **({"paso_auto": auto} if auto else {}),
            "celdas": len(filas), "tope_celdas": TOPE_CELDAS, "tope_velas": TOPE_VELAS, "velas": velas}


async def perfil(conn: Any, *, symbol: str, desde: str | None, hasta: str | None, paso: str | None,
                 venues: str | None, unidad: str | None) -> dict[str, Any]:
    activo = activo_de(symbol)
    a, b = instante(desde, "desde"), instante(hasta, "hasta")
    ventana(a, b, RANGO_MAXIMO)
    base = (await pasos(conn))[activo]
    p, vs, u = paso_de(paso, base), venues_de(venues), unidad_de(unidad)
    filas = await conn.fetch(CELDAS_SQL.format(vela="0", tope=TOPE_NIVELES + 1), activo, vs, a, b, p)
    if len(filas) > TOPE_NIVELES:
        raise Peticion(f"mas de {TOPE_NIVELES} niveles: pide un paso mayor o un rango menor")
    cob = await conn.fetchrow(COBERTURA_SQL.format(vela="0"), activo, vs, a, b)
    c, v = ("cb", "vb") if u == "base" else ("cu", "vu")
    totales = {f["n"]: f[c] + f[v] for f in filas}
    va = value_area(totales)
    total = sum(totales.values(), Decimal(0))
    poc = poc_de(totales)
    return {**_cabecera("perfil de volumen del rango: por nivel, volumen del agresor comprador y vendedor",
                        activo, p, base, vs, u, a, b),
            "total": texto(total), "poc": texto(poc) if poc is not None else None,
            "value_area": {
                "porcentaje": 70, "algoritmo": ALGORITMO_VA,
                "val": texto(va[0]) if va else None, "vah": texto(va[1]) if va else None,
                "volumen": texto(va[2]) if va else None,
            },
            "cobertura": _cobertura_json(cob, int((b - a) // timedelta(minutes=1)) * len(vs)),
            "tope_niveles": TOPE_NIVELES,
            "niveles": [_nivel_json(f["n"], f[c], f[v], int(f["nc"] + f["nv"])) for f in filas]}


def _operacion(f: Any) -> dict[str, Any]:
    return {"ts": iso(f["ts"]), "venue": f["venue"], "precio": texto(f["precio"]), "base": texto(f["base"]),
            "usd": texto(f["usd"]), "agresor": "compra" if f["compra"] else "venta", "id": f["id"]}


async def cinta(conn: Any, *, symbol: str, venues: str | None, min_usd: str | None, minutos: int,
                limit: int) -> dict[str, Any]:
    activo = activo_de(symbol)
    vs = venues_de(venues)
    try:
        minimo = Decimal(min_usd or "0")
    except InvalidOperation as exc:
        raise Peticion(f"min_usd no es un numero: {min_usd!r}") from exc
    if not minimo.is_finite() or minimo < 0:
        raise Peticion("min_usd tiene que ser >= 0")
    filas = await conn.fetch(
        """SELECT ts, venue, precio, base, usd, compra, id FROM orderflow_cinta
            WHERE symbol = $1 AND venue = ANY($2::text[]) AND ts >= now() - make_interval(mins => $3)
              AND usd >= $4
            ORDER BY ts DESC, venue, id LIMIT $5""", activo, vs, minutos, minimo, limit + 1)
    return {"que": "la cinta: cada operacion, la mas reciente primero", "symbol": activo, "venues": vs,
            "min_usd": texto(minimo), "minutos": minutos, "limit": limit, "truncada": len(filas) > limit,
            "retencion_h": get_settings().ORDERFLOW_TAPE_RETENTION_HOURS,
            "operaciones": [_operacion(f) for f in filas[:limit]]}


async def grandes(conn: Any, *, symbol: str, desde: str | None, hasta: str | None, venues: str | None,
                  limit: int) -> dict[str, Any]:
    activo = activo_de(symbol)
    a, b = instante(desde, "desde"), instante(hasta, "hasta")
    ventana(a, b, RANGO_GRANDES)
    vs = venues_de(venues)
    filas = await conn.fetch(
        """SELECT ts, venue, precio, base, usd, compra, id, umbral_usd FROM orderflow_grande
            WHERE symbol = $1 AND venue = ANY($2::text[]) AND ts >= $3 AND ts < $4
            ORDER BY ts DESC, venue, id LIMIT $5""", activo, vs, a, b, limit + 1)
    return {"que": "las operaciones grandes: al menos el umbral en USD de su activo", "symbol": activo,
            "venues": vs, "desde": iso(a), "hasta": iso(b),
            "umbral_usd_vigente": texto(carga_config()["grandes_usd"][activo]), "limit": limit,
            "truncada": len(filas) > limit,
            "operaciones": [{**_operacion(f), "umbral_usd": texto(f["umbral_usd"])} for f in filas[:limit]]}


async def cobertura(conn: Any, *, symbol: str, desde: str | None, hasta: str | None,
                    venues: str | None) -> dict[str, Any]:
    activo = activo_de(symbol)
    a, b = instante(desde, "desde"), instante(hasta, "hasta")
    ventana(a, b, RANGO_MAXIMO)
    vs = venues_de(venues)
    esperados = int((b - a) // timedelta(minutes=1))
    filas = {f["venue"]: f for f in await conn.fetch(
        """SELECT venue, count(*) AS filas, count(*) FILTER (WHERE segundos = 60) AS completos,
                  sum(segundos)::bigint AS segundos, sum(operaciones)::bigint AS operaciones,
                  sum(tardias)::bigint AS tardias, sum(fuera)::bigint AS fuera,
                  sum(reconexiones)::bigint AS reconexiones
             FROM orderflow_cobertura
            WHERE symbol = $1 AND venue = ANY($2::text[]) AND ts >= $3 AND ts < $4
            GROUP BY venue""", activo, vs, a, b)}
    huecos: dict[str, list[dict[str, Any]]] = {}
    for f in await conn.fetch(
        """SELECT exchange, start_ts, end_ts, evidence_type, status FROM data_gap
            WHERE feed = 'orderflow' AND symbol = $1 AND exchange = ANY($2::text[])
              AND start_ts < $4 AND end_ts > $3
            ORDER BY exchange, start_ts LIMIT $5""", activo, vs, a, b, TOPE_HUECOS + 1):
        huecos.setdefault(f["exchange"], []).append({
            "desde": iso(f["start_ts"]), "hasta": iso(f["end_ts"]), "evidencia": f["evidence_type"],
            "estado": f["status"]})
    por_venue = []
    for venue in vs:
        f = filas.get(venue)
        por_venue.append({
            "venue": venue, "minutos_esperados": esperados,
            **{k: int(f[k]) if f else 0 for k in ("filas", "completos", "segundos", "operaciones", "tardias",
                                                    "fuera", "reconexiones")},
            "huecos_declarados": huecos.get(venue, []),
        })
    return {"que": "la cobertura: por venue, minutos con fila, minutos completos (60 s entregando) y huecos "
                   "declarados en data_gap; un minuto incompleto se declara y no se rellena",
            "symbol": activo, "desde": iso(a), "hasta": iso(b), "tope_huecos": TOPE_HUECOS,
            "venues": por_venue}


async def referencia(conn: Any) -> dict[str, Any]:
    s = get_settings()
    return {
        "que": "la referencia del order-flow: pasos, mercados, unidades, agresor, umbrales, retencion y topes",
        "pasos": {k: texto(v) for k, v in sorted((await pasos(conn)).items())},
        "nivel": NIVEL,
        "mercados": [{"venue": m.venue, "mercado": m.mercado, "instrumentos": m.instrumentos, "cotiza": m.cotiza,
                      "unidad": m.unidad, "agresor": m.agresor} for m in MERCADOS.values()],
        "operaciones": "tal como las publica el venue: Binance (aggTrade) y OKX (trades) agregan las de un mismo "
                       "agresor al mismo precio",
        "grandes_usd": {k: texto(v) for k, v in carga_config()["grandes_usd"].items()},
        "retencion": {"celdas_dias": s.ORDERFLOW_CELL_RETENTION_DAYS, "cinta_horas": s.ORDERFLOW_TAPE_RETENTION_HOURS,
                      "grandes_dias": s.ORDERFLOW_LARGE_RETENTION_DAYS,
                      "cobertura": f"{s.ORDERFLOW_CELL_RETENTION_DAYS} dias los minutos completos; los "
                                   "incompletos no se podan"},
        "marcos": list(MARCOS),
        "topes": {"velas": TOPE_VELAS, "celdas": TOPE_CELDAS, "niveles": TOPE_NIVELES,
                  "rango_dias": RANGO_MAXIMO.days, "rango_grandes_dias": RANGO_GRANDES.days},
        "value_area": {"porcentaje": 70, "algoritmo": ALGORITMO_VA},
        "aviso": "sumar venues mezcla cotizaciones en USD (Coinbase, Deribit), USDT y USDC: el nivel es el precio "
                 "tal como lo publica cada venue, sin convertir",
    }
