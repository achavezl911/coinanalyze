"""OF-1 · LA LECTURA del order-flow: lo que sirve /api/orderflow/* desde las tablas que escribe app/orderflow.py.

Cada respuesta dice QUE es, con que paso, en que unidad y de que venues. Volumenes y niveles salen en TEXTO
decimal exacto, no en float: asi lo servido se compara byte a byte con lo recalculado desde las celdas (K108 d).
Los topes no recortan en silencio: si una peticion los pasa, 422 diciendo cual.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import ROUND_FLOOR, ROUND_HALF_EVEN, Decimal, InvalidOperation, localcontext
from typing import Any

from app.config import WS_SYMBOL_MAP, get_settings
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


# =====================================================================================================================
# OF-3 (campana 143) · LOS PERFILES: el perfil de cada SESION y su COMPUESTO, el TPO y el VWAP de la sesion con sus
# bandas. Solo se ANADE: nada de lo de OF-1/OF-2 cambia. POC y value area son poc_de() y value_area() de arriba,
# tambien en el TPO (sobre {nivel: numero de TPO}).
# =====================================================================================================================
SESIONES = {"dia": ("00:00", "24:00"), "asia": ("00:00", "08:00"), "europa": ("07:00", "16:00"),
            "eeuu": ("13:30", "20:00")}
REGLA_SESION = (
    "Una sesion es una ventana diaria de HH:MM a HH:MM UTC (dia 00:00-24:00, asia 00:00-08:00, europa 07:00-16:00, "
    "eeuu 13:30-20:00, o una propia). Si su fin no es posterior a su inicio, CRUZA la medianoche y es UNA sola, de un "
    "dia al siguiente. Cada sesion que toca la ventana pedida se calcula ENTERA desde su inicio y se corta en hasta: "
    "una ventana del pasado se repite igual y una sesion viva crece. La cobertura cuenta los minutos-venue de "
    "[inicio, corte), con corte = el menor de su fin, hasta y el ultimo minuto que cerro hace 90 s; en_curso: el "
    "corte queda antes de su fin."
)
CIERRE = timedelta(seconds=90)  # un minuto se da por escuchado 90 s despues de cerrarse (el colector lo reescribe a 70)
PERIODO_TPO = 30  # minutos
LETRAS_TPO = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuv"  # 48 periodos: un dia UTC
REGLA_TPO = (
    "Periodos de 30 min desde el inicio de la sesion, con letra A-Z y luego a-v (48: un dia). Un periodo TOCA todos "
    "los niveles del de su celda mas baja al de su celda mas alta (la misma definicion de «toca» que paso=auto): un "
    "TPO por nivel tocado. POC y value area del 70 % son las del perfil sobre el numero de TPO de cada nivel. Balance "
    "inicial: los niveles que tocan los periodos de la primera hora. Single prints: los niveles con UN solo TPO, en "
    "tramos de niveles seguidos; extremo dice si el tramo toca el nivel mas alto o el mas bajo de la sesion (una cola)."
)
REGLA_PASO_TPO = (
    "paso=auto: el menor de la escalera 1, 2, 5, 10, 20, 50... veces el paso base con el que el periodo de 30 min "
    "MEDIANO de las sesiones pedidas (de los que tienen celdas; el elemento n // 2 de la lista ordenada) toca como "
    f"mucho {OBJETIVO_NIVELES} niveles: la regla de paso=auto del footprint, sobre periodos en vez de velas."
)
REGLA_VWAP = (
    "VWAP = suma de usd / suma de base de todas las operaciones de la sesion hasta el final de cada vela: el precio "
    "medio de cada operacion pesado por su cantidad, EXACTO. Las bandas son VWAP +- k desviaciones (k = 1, 2, 3). La "
    "varianza se calcula al PRECIO DE CADA NIVEL base, que es el precio medio de sus operaciones en la sesion (suma "
    "usd / suma base del nivel): el primer momento sigue exacto y, como la varianza dentro de un nivel de ancho "
    "paso_base no pasa de paso_base^2/4, sigma servida <= sigma real <= sigma servida + paso_base/2. VWAP, sigma y "
    "bandas en texto decimal redondeado (mitad al par) a paso_base/100."
)
BANDAS = (1, 2, 3)
# P1 de la campana 143 (x1-tmp/c143/p1_banco_mide.py): en un banco con celdas reales de 140 replicadas 10 dias, las
# sesiones de BTC perpetuos tardan 0.6 s con 5 dias, 1.6 s con 7 y 2.2 s con 10, casi todo SQL (barrer las celdas), al
# ritmo de un sabado; 30 dias pasarian de 5 s (y de 15 al ritmo medio que proyecto OF-1). El tope: 7 dias.
RANGO_SESIONES = timedelta(days=7)
POR_QUE_SESIONES = ("las sesiones son caras: barrer 30 dias de celdas pasa de 5 s (medido en la campana 143), asi que "
                    "de la primera sesion a hasta caben 7 dias")


def _minuto(hhmm: str) -> int:
    if len(hhmm) != 5 or hhmm[2] != ":" or not (hhmm[:2] + hhmm[3:]).isdigit():
        raise Peticion(f"sesion: {hhmm!r} no es HH:MM")
    h, m = int(hhmm[:2]), int(hhmm[3:])
    if m > 59 or h * 60 + m > 1440:
        raise Peticion(f"sesion: {hhmm!r} no es una hora del dia (00:00-24:00)")
    return h * 60 + m


def sesion_de(valor: str | None) -> dict[str, Any]:
    """La plantilla: {nombre, inicio, fin, minutos, cruza_medianoche}, y su minuto del dia de inicio en `_ini`."""
    nombre = valor or "dia"
    partes = SESIONES.get(nombre) or tuple(nombre.split("-"))
    if len(partes) != 2:
        raise Peticion(f"sesion tiene que ser {', '.join(SESIONES)} o HH:MM-HH:MM (UTC)")
    ini, fin = _minuto(partes[0]), _minuto(partes[1])
    if ini == 1440:
        raise Peticion("sesion: no puede empezar a las 24:00")
    minutos = (fin - ini) % 1440 or 1440
    return {"nombre": nombre, "inicio": partes[0], "fin": partes[1], "minutos": minutos,
            "cruza_medianoche": ini + minutos > 1440, "regla": REGLA_SESION, "_ini": ini}


def instancias(ses: dict[str, Any], a: datetime, b: datetime) -> list[tuple[datetime, datetime]]:
    """Las sesiones [inicio, fin) que tocan [a, b), en orden. Una que cruza la medianoche es UNA."""
    s = datetime(a.year, a.month, a.day, tzinfo=UTC) + timedelta(days=-1, minutes=ses["_ini"])
    out = []
    while s < b:
        e = s + timedelta(minutes=ses["minutos"])
        if e > a:
            out.append((s, e))
        s += timedelta(days=1)
    return out


def _cerrado(ahora: datetime) -> datetime:
    return (ahora - CIERRE).replace(second=0, microsecond=0)


async def _ventana_de_sesiones(conn: Any, symbol: str, desde: str | None, hasta: str | None, sesion: str | None,
                               venues: str | None, minutos: int = 1) -> tuple:
    activo = activo_de(symbol)
    a, b = instante(desde, "desde"), instante(hasta, "hasta")
    ventana(a, b, RANGO_SESIONES, minutos)
    ses, vs = sesion_de(sesion), venues_de(venues)
    inst = instancias(ses, a, b)
    if inst and b - inst[0][0] > RANGO_SESIONES:
        raise Peticion(f"la primera sesion que toca la ventana empieza el {iso(inst[0][0])} y de ahi a hasta pasa de "
                       f"{RANGO_SESIONES.days} dias: {POR_QUE_SESIONES}")
    base = (await pasos(conn))[activo]
    origen = ORIGEN + timedelta(minutes=ses["_ini"])
    return activo, a, b, ses, vs, inst, base, origen, timedelta(minutes=ses["minutos"])


def _sesion_publica(ses: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in ses.items() if not k.startswith("_")}


EN_SESION = "AND ts < date_bin(interval '1 day', ts, $5::timestamptz) + $6::interval"
SESIONES_SQL = f"""
SELECT date_bin(interval '1 day', ts, $5::timestamptz) AS s, floor(nivel / $7) * $7 AS n,
       sum(compra_base) AS cb, sum(venta_base) AS vb, sum(compra_usd) AS cu, sum(venta_usd) AS vu,
       sum(compras)::bigint AS nc, sum(ventas)::bigint AS nv
  FROM orderflow_celda
 WHERE symbol = $1 AND venue = ANY($2::text[]) AND ts >= $3 AND ts < $4 {EN_SESION}
 GROUP BY 1, 2 ORDER BY 1, 2
 LIMIT {{tope}}
"""
COBERTURA_PERIODO_SQL = f"""
SELECT date_bin(interval '{{minutos}} minutes', ts, $5::timestamptz) AS s, count(*) AS filas,
       count(*) FILTER (WHERE segundos = 60) AS completos, coalesce(sum(segundos), 0)::bigint AS segundos,
       coalesce(bool_and(definitivo), false) AS definitiva
  FROM orderflow_cobertura
 WHERE symbol = $1 AND venue = ANY($2::text[]) AND ts >= $3 AND ts < $4 {EN_SESION}
 GROUP BY 1
"""
TPO_SQL = f"""
SELECT date_bin(interval '{PERIODO_TPO} minutes', ts, $5::timestamptz) AS p, min(nivel) AS lo, max(nivel) AS hi
  FROM orderflow_celda
 WHERE symbol = $1 AND venue = ANY($2::text[]) AND ts >= $3 AND ts < $4 {EN_SESION}
 GROUP BY 1 ORDER BY 1
"""
VWAP_SQL = f"""
SELECT date_bin(interval '1 day', ts, $5::timestamptz) AS s,
       date_bin(interval '{{minutos}} minutes', ts, '{ORIGEN.isoformat()}'::timestamptz) AS v, nivel,
       sum(compra_usd) + sum(venta_usd) AS u, sum(compra_base) + sum(venta_base) AS q
  FROM orderflow_celda
 WHERE symbol = $1 AND venue = ANY($2::text[]) AND ts >= $3 AND ts < $4 {EN_SESION}
 GROUP BY 1, 2, 3 ORDER BY 1, 2
"""


async def _coberturas(conn: Any, activo: str, vs: list[str], inst: list, hasta: datetime, origen: datetime,
                      duracion: timedelta, minutos: int) -> dict[datetime, Any]:
    """{inicio del periodo: fila de cobertura} de los minutos en sesion de [primer inicio, hasta)."""
    if not inst or hasta <= inst[0][0]:
        return {}
    return {f["s"]: f for f in await conn.fetch(COBERTURA_PERIODO_SQL.format(minutos=minutos), activo, vs,
                                                inst[0][0], hasta, origen, duracion)}


def _suma_coberturas(filas: list[Any]) -> dict[str, Any] | None:
    filas = [f for f in filas if f]
    if not filas:
        return None
    return {"filas": sum(int(f["filas"]) for f in filas), "completos": sum(int(f["completos"]) for f in filas),
            "segundos": sum(int(f["segundos"]) for f in filas), "definitiva": all(f["definitiva"] for f in filas)}


def _perfil(niveles: dict[Decimal, list]) -> dict[str, Any]:
    """{nivel: [compra, venta, operaciones]} -> totales, POC, value area y niveles, como el perfil de OF-1."""
    compra = sum((x[0] for x in niveles.values()), Decimal(0))
    venta = sum((x[1] for x in niveles.values()), Decimal(0))
    totales = {n: x[0] + x[1] for n, x in niveles.items()}
    poc, va = poc_de(totales), value_area(totales)
    return {"compra": texto(compra), "venta": texto(venta), "delta": texto(compra - venta),
            "total": texto(compra + venta), "operaciones": sum(x[2] for x in niveles.values()),
            "poc": texto(poc) if poc is not None else None,
            "value_area": {"val": texto(va[0]), "vah": texto(va[1]), "volumen": texto(va[2])} if va else None,
            "niveles": [_nivel_json(n, *niveles[n]) for n in sorted(niveles)]}


async def sesiones(conn: Any, *, symbol: str, desde: str | None, hasta: str | None, sesion: str | None,
                   paso: str | None, venues: str | None, unidad: str | None) -> dict[str, Any]:
    activo, a, b, ses, vs, inst, base, origen, dur = await _ventana_de_sesiones(conn, symbol, desde, hasta, sesion,
                                                                                 venues)
    p, u = paso_de(paso, base), unidad_de(unidad)
    filas = await conn.fetch(SESIONES_SQL.format(tope=TOPE_NIVELES + 1), activo, vs, inst[0][0], b, origen, dur,
                             p) if inst else []
    if len(filas) > TOPE_NIVELES:
        raise Peticion(f"mas de {TOPE_NIVELES} niveles entre todas las sesiones: pide un paso mayor o menos sesiones")
    cerrado = _cerrado(datetime.now(UTC))
    cob = await _coberturas(conn, activo, vs, inst, min(b, cerrado), origen, dur, 1440)
    c, v = ("cb", "vb") if u == "base" else ("cu", "vu")
    por_sesion: dict[datetime, dict[Decimal, list]] = {}
    for f in filas:
        por_sesion.setdefault(f["s"], {})[f["n"]] = [f[c], f[v], int(f["nc"] + f["nv"])]
    salida, todos, esperados = [], {}, 0
    for s, e in inst:
        corte = max(s, min(e, b, cerrado))
        n_esp = int((corte - s) // timedelta(minutes=1)) * len(vs)
        esperados += n_esp
        for n, x in por_sesion.get(s, {}).items():
            t = todos.setdefault(n, [Decimal(0), Decimal(0), 0])
            t[0], t[1], t[2] = t[0] + x[0], t[1] + x[1], t[2] + x[2]
        salida.append({"inicio": iso(s), "fin": iso(e), "corte": iso(corte), "en_curso": corte < e,
                       **_perfil(por_sesion.get(s, {})), "cobertura": _cobertura_json(cob.get(s), n_esp)})
    compuesto = None
    if inst:
        compuesto = {"inicio": iso(inst[0][0]), "corte": salida[-1]["corte"], "sesiones": len(inst),
                     "en_curso": salida[-1]["en_curso"], **_perfil(todos),
                     "cobertura": _cobertura_json(_suma_coberturas([cob.get(s) for s, _ in inst]), esperados)}
    return {**_cabecera("perfiles de sesion: el de cada sesion que toca la ventana, entera desde su inicio y cortada "
                        "en hasta, y el COMPUESTO de todas", activo, p, base, vs, u, a, b),
            "sesion": _sesion_publica(ses),
            "poc": "el nivel de mayor total; a igualdad, el de precio mas bajo",
            "value_area": {"porcentaje": 70, "algoritmo": ALGORITMO_VA},
            "tope_niveles": TOPE_NIVELES, "sesiones": salida, "compuesto": compuesto}


async def tpo(conn: Any, *, symbol: str, desde: str | None, hasta: str | None, sesion: str | None,
              paso: str | None, venues: str | None) -> dict[str, Any]:
    activo, a, b, ses, vs, inst, base, origen, dur = await _ventana_de_sesiones(conn, symbol, desde, hasta, sesion,
                                                                                 venues)
    filas = await conn.fetch(TPO_SQL, activo, vs, inst[0][0], b, origen, dur) if inst else []
    auto = None
    if paso in (None, "auto"):
        p, mediana = paso_automatico([(f["lo"], f["hi"]) for f in filas], base)
        auto = {"regla": REGLA_PASO_TPO, "objetivo_niveles": OBJETIVO_NIVELES, "periodos_con_celdas": len(filas),
                "niveles_periodo_mediano": mediana}
    else:
        p = paso_de(paso, base)
    toques = sum((f["hi"] / p).to_integral_value(ROUND_FLOOR) - (f["lo"] / p).to_integral_value(ROUND_FLOOR) + 1
                 for f in filas)
    if toques > TOPE_CELDAS:
        raise Peticion(f"{toques} TPO pasan el tope de {TOPE_CELDAS}: pide un paso mayor o menos sesiones")
    cerrado = _cerrado(datetime.now(UTC))
    cob = await _coberturas(conn, activo, vs, inst, min(b, cerrado), origen, dur, PERIODO_TPO)
    por_periodo = {f["p"]: f for f in filas}
    salida = []
    for s, e in inst:
        corte = max(s, min(e, b, cerrado))
        periodos, letras, ib = [], {}, []
        k = 0
        while s + timedelta(minutes=PERIODO_TPO * k) < min(e, b):
            ini = s + timedelta(minutes=PERIODO_TPO * k)
            n_esp = max(0, int((min(ini + timedelta(minutes=PERIODO_TPO), corte) - ini) // timedelta(minutes=1)))
            per = {"letra": LETRAS_TPO[k], "inicio": iso(ini), "lo": None, "hi": None,
                   "cobertura": _cobertura_json(cob.get(ini), n_esp * len(vs))}
            f = por_periodo.get(ini)
            if f is not None:
                lo = (f["lo"] / p).to_integral_value(ROUND_FLOOR) * p
                hi = (f["hi"] / p).to_integral_value(ROUND_FLOOR) * p
                per["lo"], per["hi"] = texto(lo), texto(hi)
                n = lo
                while n <= hi:
                    letras.setdefault(n, []).append(LETRAS_TPO[k])
                    n += p
                if k * PERIODO_TPO < 60:
                    ib.append((lo, hi))
            periodos.append(per)
            k += 1
        cuenta = {n: len(x) for n, x in letras.items()}
        poc, va = poc_de(cuenta), value_area(cuenta)
        orden = sorted(cuenta)
        tramos: list[list[Decimal]] = []
        for n in orden:
            if cuenta[n] == 1:
                if tramos and n - tramos[-1][-1] == p:
                    tramos[-1].append(n)
                else:
                    tramos.append([n])
        salida.append({
            "inicio": iso(s), "fin": iso(e), "corte": iso(corte), "en_curso": corte < e,
            "tpo": sum(cuenta.values()),
            "cobertura": _cobertura_json(_suma_coberturas([f for x, f in cob.items() if s <= x < e]),
                                         int((corte - s) // timedelta(minutes=1)) * len(vs)),
            "poc": texto(poc) if poc is not None else None,
            "value_area": {"val": texto(va[0]), "vah": texto(va[1]), "tpo": texto(va[2])} if va else None,
            "balance_inicial": {"lo": texto(min(x for x, _ in ib)), "hi": texto(max(y for _, y in ib))} if ib else None,
            "single_prints": [{"desde": texto(t[0]), "hasta": texto(t[-1]), "niveles": len(t),
                               "extremo": ("los dos" if t[0] == orden[0] and t[-1] == orden[-1] else
                                           "alto" if t[-1] == orden[-1] else "bajo" if t[0] == orden[0] else None)}
                              for t in tramos],
            "periodos": periodos,
            "niveles": [{"nivel": texto(n), "tpo": cuenta[n], "letras": "".join(letras[n])} for n in orden],
        })
    return {**_cabecera("TPO (perfil de mercado): por sesion, los periodos de 30 min que tocaron cada nivel", activo, p,
                        base, vs, None, a, b),
            "sesion": _sesion_publica(ses), "periodo_minutos": PERIODO_TPO, "letras": LETRAS_TPO, "regla": REGLA_TPO,
            **({"paso_auto": auto} if auto else {}), "tope_tpo": TOPE_CELDAS, "sesiones": salida}


def _redondea(x: Decimal, q: Decimal) -> str:
    return texto(x.quantize(q, rounding=ROUND_HALF_EVEN))


async def vwap(conn: Any, *, symbol: str, desde: str | None, hasta: str | None, marco: str, sesion: str | None,
               venues: str | None) -> dict[str, Any]:
    if marco not in MARCOS:
        raise Peticion(f"marco tiene que ser uno de {', '.join(MARCOS)}")
    minutos = MARCOS[marco]
    activo, a, b, ses, vs, inst, base, origen, dur = await _ventana_de_sesiones(conn, symbol, desde, hasta, sesion,
                                                                                 venues, minutos)
    n_velas = (b - a) // timedelta(minutes=minutos)
    if n_velas > TOPE_VELAS:
        raise Peticion(f"{n_velas} velas pasan el tope de {TOPE_VELAS}: pide un marco mayor o un rango menor")
    q = base / 100
    filas = await conn.fetch(VWAP_SQL.format(minutos=minutos), activo, vs, inst[0][0], b, origen, dur) if inst else []
    cerrado = _cerrado(datetime.now(UTC))
    cob = await _coberturas(conn, activo, vs, inst, min(b, cerrado), origen, dur, 1440)
    por_sesion: dict[datetime, list] = {}
    for f in filas:
        por_sesion.setdefault(f["s"], []).append(f)
    salida = []
    with localcontext() as ctx:
        ctx.prec = 50
        for s, e in inst:
            corte = max(s, min(e, b, cerrado))
            filas_s = por_sesion.get(s, [])
            u_n: dict[Decimal, Decimal] = {}
            q_n: dict[Decimal, Decimal] = {}
            suma_u = suma_q = suma_p2 = Decimal(0)  # sum usd, sum base y sum usd_n^2 / base_n por nivel
            i, puntos = 0, []
            for k in range(-1, n_velas):
                limite = a + timedelta(minutes=minutos * (k + 1))
                while i < len(filas_s) and filas_s[i]["v"] < limite:
                    n, du, dq = filas_s[i]["nivel"], filas_s[i]["u"], filas_s[i]["q"]
                    if n in q_n:
                        suma_p2 -= u_n[n] * u_n[n] / q_n[n]
                    u_n[n], q_n[n] = u_n.get(n, Decimal(0)) + du, q_n.get(n, Decimal(0)) + dq
                    suma_p2 += u_n[n] * u_n[n] / q_n[n]
                    suma_u, suma_q = suma_u + du, suma_q + dq
                    i += 1
                inicio_vela = limite - timedelta(minutes=minutos)
                if k < 0 or not suma_q or limite <= s or inicio_vela >= min(e, b):
                    continue
                medio = suma_u / suma_q
                sigma = max(suma_p2 / suma_q - medio * medio, Decimal(0)).sqrt()
                puntos.append({"ts": iso(inicio_vela), "vwap": _redondea(medio, q), "sigma": _redondea(sigma, q),
                               "bandas": {str(k_): [_redondea(medio - k_ * sigma, q), _redondea(medio + k_ * sigma, q)]
                                          for k_ in BANDAS}})
            salida.append({"inicio": iso(s), "fin": iso(e), "corte": iso(corte), "en_curso": corte < e,
                           "cobertura": _cobertura_json(cob.get(s), int((corte - s) // timedelta(minutes=1)) * len(vs)),
                           "puntos": puntos})
    return {**_cabecera("VWAP de la sesion: por vela, el VWAP acumulado desde el inicio de la sesion y sus bandas",
                        activo, base, base, vs, None, a, b),
            "marco": marco, "sesion": _sesion_publica(ses), "regla": REGLA_VWAP, "bandas": list(BANDAS),
            "redondeo": texto(q), "sesiones": salida}


# =====================================================================================================================
# OF-5a (campana 146) · LOS INDICADORES y LA ORDEN AGREGADA. Solo se ANADE: nada de lo de OF-1..OF-4 cambia.
# Las series de 5 min las trae app/ingest.py de Coinalyze (su BTCUSDT_PERP.A es BINANCE; el OI de Bybit, su
# BTCUSDT.6, va aparte) y las liquidaciones sueltas el colector de scalp: aqui solo se leen y se ponen en la rejilla de
# la ventana del footprint. Lo que falta se dice (estado de cada cubo); un cubo sin dato nunca sale como cero.
# =====================================================================================================================
CADENCIA = timedelta(minutes=5)
# Un punto de 5 min que falta y cuyo intervalo acabo hace menos de esto es PENDIENTE, no hueco: en 140 el punto de las
# 14:30Z ya estaba escrito a las 14:35:18Z (latido ingest:metrics_5m, 2026-10-18; P1 de la campana 146).
ESPERA_PUNTO = timedelta(minutes=15)
TOPE_SUELTAS = 5000
COINALYZE = {activo: simbolo for simbolo, activo in WS_SYMBOL_MAP.items()}
# (clave, tabla, {lo que se sirve: columna}, la fuente que escribe la pantalla, unidad, como llega a un cubo mayor)
SERIES_5M = (
    ("oi_binance", "open_interest", {"oi": "oi_close"},
     "interes abierto · Binance (Coinalyze, cada 5 min)", "USD", "ultimo"),
    ("oi_bybit", "oi_bybit", {"oi": "oi_close"},
     "interes abierto · Bybit (Coinalyze, cada 5 min)", "USD", "ultimo"),
    ("funding", "funding_rate", {"funding": "fr_close"},
     "funding · Binance (Coinalyze, cada 5 min)", "% por periodo de funding", "ultimo"),
    ("funding_predicho", "predicted_funding_rate", {"funding": "pfr_close"},
     "funding predicho · Binance (Coinalyze, cada 5 min)", "% por periodo de funding", "ultimo"),
    ("largos_cortos", "long_short_ratio", {"largos": "long_pct", "cortos": "short_pct", "ratio": "ratio"},
     "largos/cortos · Binance (Coinalyze, cada 5 min)", "% de cuentas", "ultimo"),
    ("liquidaciones", "liquidations", {"largos": "long_liq", "cortos": "short_liq"},
     "liquidaciones · Binance (Coinalyze, cada 5 min)", "USD", "suma"),
)
COMO_CUBO = {"ultimo": "el valor de un cubo es el CIERRE de su ultimo punto de 5 min",
             "suma": "el valor de un cubo es la SUMA de sus puntos de 5 min"}
REGLA_CUBO = (
    "Los puntos de Coinalyze son de 5 min: con velas de 1 min un cubo de 5 min abarca 5 velas (se pinta como ESCALON) y "
    "con velas mayores hay un cubo por vela. Estado de cada cubo: completo (todos sus puntos), en_curso (los que faltan "
    "aun no tocan: su intervalo acabo hace menos de 15 min), incompleto (falta alguno que ya tocaba), pendiente (ninguno, "
    "y aun no tocaba) y hueco (ninguno, y ya tocaba). Un hueco no vale cero: su valor es null."
)
REGLA_LIQ = (
    "Coinalyze no publica los cubos de 5 min SIN liquidaciones (medido en 140 el 2026-10-18: 120 de 288 cubos de BTC en "
    "24 h tienen fila, y ninguna con los dos ceros). Un cubo sin fila es un CERO solo si lo cubre el ultimo barrido de la "
    "ingesta (latido ingest:liquidations_history con estado ok, de source_start_ts a source_cutoff_ts); fuera, no se "
    "sabe: falta."
)
FUENTE_SUELTAS = "liquidaciones sueltas · binance y bybit perpetuos (colector propio: cada liquidacion)"


def _ahora() -> datetime:
    return datetime.now(UTC)  # un solo reloj para las dos rutas: los tests lo plantan


def _decimal(x: Any) -> Decimal:
    return Decimal(str(x))  # la representacion mas corta del float de la base: exacta y repetible


async def _barrido_liquidaciones(conn: Any) -> dict[str, Any]:
    """Lo que certifica el ultimo barrido de liquidaciones de la ingesta: [desde, hasta) y su estado."""
    fila = await conn.fetchrow(
        "SELECT status, detail FROM pipeline_heartbeat WHERE service = 'ingest:liquidations_history'")
    if not fila:
        return {"estado": "sin_latido", "desde": None, "hasta": None}
    try:
        d = json.loads(fila["detail"] or "{}")
        a = datetime.fromtimestamp(int(d["source_start_ts"]), UTC)
        b = datetime.fromtimestamp(int(d["source_cutoff_ts"]), UTC)
    except (ValueError, KeyError, TypeError):
        return {"estado": f"{fila['status']} (sin ventana legible)", "desde": None, "hasta": None}
    return {"estado": fila["status"], "desde": a, "hasta": b}


def _cubo(inicio: datetime, cubo: timedelta, por_ts: dict, columnas: dict, como: str, barrido: dict,
          ahora: datetime) -> dict[str, Any]:
    puntos = [inicio + CADENCIA * k for k in range(cubo // CADENCIA)]
    presentes = [por_ts[p] for p in puntos if p in por_ts]
    ceros = faltan = pendientes = 0
    for p in puntos:
        if p in por_ts:
            continue
        if (como == "suma" and barrido["estado"] == "ok" and barrido["desde"] is not None
                and barrido["desde"] <= p and p + CADENCIA <= barrido["hasta"]):
            ceros += 1
        elif p + CADENCIA > ahora - ESPERA_PUNTO:
            pendientes += 1
        else:
            faltan += 1
    con_dato = len(presentes) + ceros
    if not con_dato:
        estado = "hueco" if faltan else "pendiente"
    else:
        estado = "incompleto" if faltan else "en_curso" if pendientes else "completo"
    valores = None
    if presentes and como == "ultimo":
        valores = {n: texto(_decimal(presentes[-1][n])) for n in columnas}
    elif con_dato and como == "suma":
        valores = {n: texto(sum((_decimal(f[n]) for f in presentes), Decimal(0))) for n in columnas}
    return {"ts": iso(inicio), "estado": estado, "puntos": len(presentes), "ceros": ceros, "faltan": faltan,
            "pendientes": pendientes, "valores": valores}


async def indicadores(conn: Any, *, symbol: str, desde: str | None, hasta: str | None,
                      marco: str) -> dict[str, Any]:
    activo = activo_de(symbol)
    if marco not in MARCOS:
        raise Peticion(f"marco tiene que ser uno de {', '.join(MARCOS)}")
    minutos = MARCOS[marco]
    a, b = instante(desde, "desde"), instante(hasta, "hasta")
    ventana(a, b, RANGO_MAXIMO, minutos)
    n_velas = (b - a) // timedelta(minutes=minutos)
    if n_velas > TOPE_VELAS:
        raise Peticion(f"{n_velas} velas pasan el tope de {TOPE_VELAS}: pide un marco mayor o un rango menor")
    cubo = max(CADENCIA, timedelta(minutes=minutos))
    primero = a - (a - ORIGEN) % cubo  # el cubo que contiene `desde`
    inicios = [primero + cubo * k for k in range((b - primero + cubo - timedelta(microseconds=1)) // cubo)]
    ahora = _ahora()
    simbolo = COINALYZE[activo]
    barrido = await _barrido_liquidaciones(conn)
    series = {}
    for clave, tabla, columnas, fuente, unidad, como in SERIES_5M:
        lista = ", ".join(f"{c} AS {n}" for n, c in columnas.items())
        filas = await conn.fetch(
            f"SELECT ts, {lista} FROM {tabla} WHERE symbol = $1 AND interval = '5min' AND ts >= $2 AND ts < $3",
            simbolo, primero, inicios[-1] + cubo)
        por_ts = {f["ts"]: f for f in filas}
        series[clave] = {"fuente": fuente, "tabla": tabla, "unidad": unidad, "como": COMO_CUBO[como],
                         "cubos": [_cubo(t, cubo, por_ts, columnas, como, barrido, ahora) for t in inicios]}
    retencion = timedelta(hours=get_settings().SCALP_TRADE_RETENTION_HOURS)
    borde = max(a, ahora - retencion)
    sueltas = await conn.fetch(
        """SELECT ts, exchange, side, notional_usd, price, qty FROM liquidations_realtime
            WHERE symbol = $1 AND ts >= $2 AND ts < $3 ORDER BY ts, exchange, event_id LIMIT $4""",
        simbolo, borde, b, TOPE_SUELTAS + 1) if borde < b else []
    huecos = await conn.fetch(
        """SELECT exchange, start_ts, end_ts, evidence_type, status FROM data_gap
            WHERE feed = 'liquidations' AND symbol = $1 AND start_ts < $3 AND end_ts > $2
            ORDER BY start_ts, exchange LIMIT $4""", simbolo, a, b, TOPE_HUECOS + 1)
    return {
        "que": "los indicadores de la ventana del footprint: las series de 5 min de Coinalyze y las liquidaciones "
               "sueltas", "symbol": activo, "simbolo_coinalyze": simbolo, "desde": iso(a), "hasta": iso(b),
        "marco": marco, "cadencia_minutos": 5, "cubo_minutos": cubo // timedelta(minutes=1), "regla": REGLA_CUBO,
        "liquidaciones_barrido": {"estado": barrido["estado"],
                                  "desde": iso(barrido["desde"]) if barrido["desde"] else None,
                                  "hasta": iso(barrido["hasta"]) if barrido["hasta"] else None, "regla": REGLA_LIQ},
        "series": series,
        "sueltas": {
            "fuente": FUENTE_SUELTAS, "retencion_h": retencion // timedelta(hours=1),
            "desde_dato": iso(min(borde, b)), "truncada": len(sueltas) > TOPE_SUELTAS,
            "eventos": [{"ts": iso(f["ts"]), "exchange": f["exchange"], "lado": f["side"],
                         "usd": texto(_decimal(f["notional_usd"])), "precio": texto(_decimal(f["price"])),
                         "cantidad": texto(_decimal(f["qty"]))} for f in sueltas[:TOPE_SUELTAS]],
            "huecos": [{"exchange": f["exchange"], "desde": iso(f["start_ts"]), "hasta": iso(f["end_ts"]),
                        "evidencia": f["evidence_type"], "estado": f["status"]} for f in huecos[:TOPE_HUECOS]],
        },
    }


# LA ORDEN AGREGADA (P2 de la campana 146, x1-tmp/c146/p2*). El instante de la cinta se guarda al milisegundo (0 de las
# operaciones de 1 h de los nueve venues con fraccion de ms) y, contra la verdad de suelo de la grabacion de OF-1
# (taker_order_id de coinbase, seq de bybit, starbase_timestamp de deribit), ninguna orden de verdad abarca mas de un
# milisegundo: juntar los milisegundos vecinos solo mezcla agresores distintos.
DEFINICION_ORDEN = (
    "una orden de mercado agregada son las operaciones del MISMO venue, el MISMO milisegundo y el MISMO lado del "
    "agresor; su tamano es la suma, y precio_min/precio_max el rango que barrio. En el mismo milisegundo pueden caer "
    "ordenes de agresores distintos, y salen juntas (no hay con que separarlas en la cinta)"
)
# El hasta servido va MARGEN_ORDENES por detras de ahora: con el, la cinta ya tiene todas las operaciones de lo servido
# (P2: el retraso de lo ultimo en la cinta de 140 tuvo p99 3.965 s en 180 muestras; x 2, redondeado). Asi una orden no
# sale partida entre dos peticiones y el vivo pide SOLO lo nuevo: (desde, hasta], y la siguiente desde ese hasta.
MARGEN_ORDENES = timedelta(seconds=8)
VENTANA_ORDENES = timedelta(minutes=60)
ORDENES_SQL = """
SELECT date_trunc('milliseconds', ts) AS ms, venue, compra, count(*)::int AS n, sum(base) AS base, sum(usd) AS usd,
       min(precio) AS pmin, max(precio) AS pmax
  FROM orderflow_cinta
 WHERE symbol = $1 AND venue = ANY($2::text[]) AND ts > $3 AND ts <= $4
 GROUP BY 1, 2, 3 HAVING sum(usd) >= $5
 ORDER BY 1 DESC, 2, 3
 LIMIT $6
"""


async def ordenes(conn: Any, *, symbol: str, venues: str | None, min_usd: str | None, desde: str | None,
                  hasta: str | None, limit: int) -> dict[str, Any]:
    activo, vs = activo_de(symbol), venues_de(venues)
    try:
        minimo = Decimal(min_usd or "0")
    except InvalidOperation as exc:
        raise Peticion(f"min_usd no es un numero: {min_usd!r}") from exc
    if not minimo.is_finite() or minimo < 0:
        raise Peticion("min_usd tiene que ser >= 0")
    cerrado = _ahora() - MARGEN_ORDENES
    cerrado = cerrado.replace(microsecond=cerrado.microsecond // 1000 * 1000)
    b = min(instante(hasta, "hasta"), cerrado) if hasta else cerrado
    a = instante(desde, "desde") if desde else b - VENTANA_ORDENES
    for nombre, t in (("desde", a), ("hasta", b)):
        if t.microsecond % 1000:
            raise Peticion(f"{nombre} tiene que caer en un milisegundo entero")
    if b - a > VENTANA_ORDENES:
        raise Peticion(f"la ventana de ordenes es de {VENTANA_ORDENES // timedelta(minutes=1)} min como mucho: "
                       "agregar mas cinta de una vez es caro; el vivo pide solo lo nuevo")
    filas = await conn.fetch(ORDENES_SQL, activo, vs, a, b, minimo, limit + 1) if b > a else []
    return {"que": "las ordenes de mercado agregadas de la cinta, la mas reciente primero", "definicion": DEFINICION_ORDEN,
            "symbol": activo, "venues": vs, "min_usd": texto(minimo), "desde": iso(a), "hasta": iso(max(a, b)),
            "margen_s": MARGEN_ORDENES // timedelta(seconds=1), "limit": limit, "truncada": len(filas) > limit,
            "retencion_h": get_settings().ORDERFLOW_TAPE_RETENTION_HOURS,
            "ordenes": [{"ts": iso(f["ms"]), "venue": f["venue"], "agresor": "compra" if f["compra"] else "venta",
                         "operaciones": f["n"], "base": texto(f["base"]), "usd": texto(f["usd"]),
                         "precio_min": texto(f["pmin"]), "precio_max": texto(f["pmax"])} for f in filas[:limit]]}
