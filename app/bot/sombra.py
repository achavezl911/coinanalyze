"""LA SOMBRA (BOT-5): el bot cuenta EN VIVO una candidata congelada de la anatomia, sin avisar de nada por defecto.

Cada tic de minuto (Bot.tic_sombra), sobre la cinta de 140 (orderflow_cinta, 48 h):
  - el minuto m se da por CERRADO a m + 60 + CIERRE_S (la cinta re-escribe tardias hasta 70 s tras el cierre,
    app/orderflow.py REESCRIBE_S);
  - en cada punto de la rejilla t cerrado (y t+1 cerrado: la entrada es su apertura) se calcula la variable con la
    DEFINICION COMPARTIDA del estudio (app/anatomia.py: cinta_fila, suma_ventana, cumple) y se decide como el estudio;
  - un disparo abre una fila en bot_sombra si no hay otra ocupando el hueco (sin_solape: el hueco se libera en el minuto
    de salida, aunque el camino siga mirandose);
  - cada fila se resuelve a los HORIZONTE minutos, o antes si toca (estado «tocada» hasta tener el camino entero, como
    exige la etiqueta del estudio): exito, fracaso o SIN DATO. SIN DATO = falta un minuto de precio de VENUE_REF en el
    camino o la entrada: no es ni exito ni fracaso, y nunca se rellena de otra fuente.
  - la tabla manda: el cursor (bot_sombra_candidata.hasta) y las filas se escriben en la MISMA transaccion; un
    reinicio sigue desde el cursor, sin duplicar (clave primaria) ni perder abiertas.

Una hora de la cinta sin ninguna fila es una hora que FALTA (sus minutos no cuentan en la ventana), como en el
archivo, donde esa hora no tendria fichero. Una diferencia conocida con el estudio: una fila que acaba SIN DATO ocupo
su hueco hasta su salida; en el estudio esa decision no existe y no bloquea a nadie.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import pathlib
import re
from datetime import UTC, datetime

from app import anatomia as A

RAIZ = pathlib.Path(__file__).resolve().parent.parent.parent
CANDIDATAS = RAIZ / "config" / "anatomia" / "congeladas-20261103.json"
CANDIDATAS_SHA = "be13350c09e7c993687a7bbc961a9038ae8c09ae19d5a72fbbfb304f970f7844"
CIERRE_S = 90
LOTE_S = 6 * 3600           # decisiones por tic como mucho (un arranque tras horas parado se pone al dia por tramos)
FINALES = ("exito", "fracaso", "sin_dato")
VARIABLE = re.compile(r"^d([ps])(100k|1m)_(\d+)$")
MIN = 60


class Candidata:
    def __init__(self, sha: str, indice: int, d: dict):
        if d.get("tipo") != "variable" or d.get("capa") != "B":
            raise ValueError(f"candidata {indice}: la sombra solo cuenta variables de la capa B")
        v = VARIABLE.match(d["nombre"])
        if not v:
            raise ValueError(f"candidata {indice}: {d['nombre']} no es un flujo de la cinta")
        if d["comision_entrada"] != A.COMISION or d["comision_salida"] != A.COMISION:
            raise ValueError(f"candidata {indice}: comision distinta de la del estudio")
        self.sha, self.indice, self.d = sha, indice, d
        self.columna = A.COL["d" + v.group(1) + v.group(2)]
        self.venues = A.VENUES_SPOT if v.group(1) == "s" else A.VENUES_PERP
        self.minimo = A.GRANDE_100K if v.group(2) == "100k" else A.GRANDE_1M
        self.w = int(v.group(3))
        self.simbolo, self.cola, self.umbral = d["simbolo"], d["cola"], float(d["umbral"])
        self.estricto = bool(d.get("estricto"))
        self.lado = A.LADOS[d["lado"]]
        self.esquema = A.esquema_de(d["objetivo"], d["stop"])
        if abs(A.empate(self.esquema) - d["empate"]) > 1e-12:
            raise ValueError(f"candidata {indice}: empate {d['empate']} no es el de {self.esquema}")

    def nombre(self) -> str:
        return f"{self.simbolo} {self.d['lado']} si {self.d['nombre']} {'<' if self.estricto else '<='} {self.umbral:.2f}"


def carga(ruta=None, sha=CANDIDATAS_SHA) -> list[Candidata]:
    """Las candidatas del fichero congelado; ValueError si su sha256 no es el congelado (no se reescribe a mano)."""
    b = pathlib.Path(ruta or CANDIDATAS).read_bytes()
    h = hashlib.sha256(b).hexdigest()
    if h != sha:
        raise ValueError(f"candidatas: sha256 {h[:20]} no es el congelado {sha[:20]}")
    return [Candidata(h, i, d) for i, d in enumerate(json.loads(b)["congeladas"])]


def ultimo_cerrado(ahora: float) -> int:
    """Epoch del inicio del ultimo minuto cerrado."""
    return int((ahora - MIN - CIERRE_S) // MIN) * MIN


# ---------------------------------------------------------------- la logica pura (la usa tambien K119)
def avanza(fila: dict, barra, ultimo: int) -> None:
    """Mira el camino de una fila abierta o tocada con lo cerrado hasta `ultimo`. barra(m) -> (o, h, l, c) o None."""
    t, H = fila["minuto"], A.HORIZONTE
    fin = min(t + H * MIN, ultimo)
    barras = []
    for m in range(t + MIN, fin + MIN, MIN):
        b = barra(m)
        if b is None:
            fila.update(estado="sin_dato", exito=None, neto=None, motivo=f"sin precio {_hm(m)}")
            if fila.get("salida") is None:
                fila["salida"] = m
            return
        barras.append(b)
    if not barras:
        return
    if fin == t + H * MIN:   # el camino entero: la etiqueta del estudio, tal cual
        o = [None] + [b[0] for b in barras]
        r = A.etiqueta_entera(o, [None] + [b[1] for b in barras], [None] + [b[2] for b in barras],
                              [None] + [b[3] for b in barras], 0, fila["lado_n"], fila["esquema"])
        fila.update(estado="exito" if r[0] else "fracaso", exito=r[0], neto=r[1], salida=t + r[2] * MIN,
                    motivo="objetivo" if r[0] else ("vence" if r[2] == H else "stop"))
        return
    r = A.recorre(fila["entrada"], fila["lado_n"], fila["esquema"], [(b[1], b[2]) for b in barras])
    if r is not None and fila["estado"] == "abierta":
        fila.update(estado="tocada", exito=r[0], neto=r[1], salida=t + (1 + r[2]) * MIN,
                    motivo="objetivo" if r[0] else "stop")


def libre_desde(filas: list) -> float:
    """El primer minuto en que puede abrirse otra: la salida de la ultima, o nunca si sigue abierta sin tocar."""
    if not filas:
        return -math.inf
    f = max(filas, key=lambda x: x["minuto"])
    return math.inf if f["estado"] == "abierta" else f["salida"]


def decide(c: Candidata, t: int, flujo):
    """(cumple, valor) en el punto t. flujo(m) -> la columna de la candidata en el minuto m, o None si su hora falta."""
    s = A.suma_ventana([flujo(m) for m in range(t - (c.w - 1) * MIN, t + MIN, MIN)])
    return (t >= A.CAPA_B_DESDE and A.cumple(s, c.cola, c.umbral, c.estricto)), s


def paso(c: Candidata, filas: list, hasta: int, ultimo: int, flujo, barra, lote: int = LOTE_S):
    """Avanza las filas vivas y decide los puntos (hasta, ultimo - 1 min]. Devuelve (filas nuevas, nuevo hasta)."""
    for f in filas:
        if f["estado"] in ("abierta", "tocada"):
            avanza(f, barra, ultimo)
    nuevas, libre = [], libre_desde(filas)
    t = hasta + MIN
    tope = min(ultimo - MIN, hasta + lote)
    while t <= tope:
        if A.es_decision(t):
            ok, s = decide(c, t, flujo)
            if ok and t >= libre:
                f = fila_nueva(c, t, s)
                b = barra(t + MIN)
                if b is None:
                    f.update(estado="sin_dato", salida=t + MIN, motivo=f"sin precio de entrada {_hm(t + MIN)}")
                else:
                    f["entrada"] = b[0]
                    avanza(f, barra, ultimo)
                nuevas.append(f)
                libre = libre_desde([f])
        t += MIN
    return nuevas, max(hasta, tope)


def fila_nueva(c: Candidata, t: int, s: float) -> dict:
    return {"candidata": c.sha, "indice": c.indice, "minuto": t, "simbolo": c.simbolo, "lado": c.d["lado"],
            "lado_n": c.lado, "esquema": c.esquema, "valor": s, "umbral": c.umbral, "entrada": None,
            "estado": "abierta", "exito": None, "neto": None, "salida": None, "motivo": None}


def pliega(filas_cinta, minutos: dict) -> None:
    """Pliega filas de la cinta (ts, venue, precio, usd, compra), en orden (ts, id), con cinta_fila. ts: datetime de
    asyncpg o el texto de psql ('2026-10-21 04:00:00.123+00'); todas del mismo tipo."""
    bordes = {}
    for ts, venue, precio, usd, compra in filas_cinta:
        m = int(ts.timestamp()) // MIN * MIN if isinstance(ts, datetime) else A._ts(ts[:19]) // MIN * MIN
        if m not in minutos:
            minutos[m] = A.minuto_vacio()
        A.cinta_fila(minutos[m], bordes.setdefault(m, {}), ts, venue, float(precio), float(usd), bool(compra))


@contextlib.asynccontextmanager
async def _transaccion(db):
    """Un pool de asyncpg (el bot) o una conexion suelta (las pruebas)."""
    if hasattr(db, "acquire"):
        async with db.acquire() as cx, cx.transaction():
            yield cx
    else:
        async with db.transaction():
            yield db


def _hm(m: int) -> str:
    return datetime.fromtimestamp(m, UTC).strftime("%m-%d %H:%MZ")


def _dt(m: int) -> datetime:
    return datetime.fromtimestamp(m, UTC)


# ---------------------------------------------------------------- la base
FLUJO_SQL = ("SELECT ts, venue, precio, usd, compra FROM orderflow_cinta WHERE symbol = $1 AND ts >= $2 AND ts < $3"
             " AND venue = ANY($4::text[]) AND usd >= $5 ORDER BY ts, id COLLATE \"C\"")
PRECIO_SQL = ("SELECT ts, venue, precio, usd, compra FROM orderflow_cinta WHERE symbol = $1 AND ts >= $2 AND ts < $3"
              " AND venue = $4 ORDER BY ts, id COLLATE \"C\"")
HORA_SQL = "SELECT EXISTS (SELECT 1 FROM orderflow_cinta WHERE ts >= $1 AND ts < $2)"
COLUMNAS = ("candidata", "indice", "minuto", "simbolo", "lado", "valor", "umbral", "entrada", "estado", "exito", "neto",
            "salida", "motivo")


class Sombra:
    """El estado vivo: las candidatas y un cache de minutos CERRADOS de la cinta. Lo que cuenta esta en la base."""

    def __init__(self, db, entorno: dict):
        self.db = db
        self.candidatas = carga(entorno.get("BOT_SOMBRA_CANDIDATAS") or None)
        self.horas: set = set()       # horas con filas (solo se recuerda el si)
        self.minutos: dict = {}       # (simbolo, venues, minimo) | (simbolo, REF) -> {minuto: fila de la base}
        self.cargado: dict = {}       # la misma clave -> hasta donde esta cargado (exclusivo)

    async def hora(self, m: int) -> bool:
        h = m // 3600 * 3600
        if h not in self.horas and await self.db.fetchval(HORA_SQL, _dt(h), _dt(h + 3600)):
            self.horas.add(h)
        return h in self.horas

    async def carga_minutos(self, clave, sql, args, a: int, b: int) -> dict:
        """Los minutos [a, b] de una consulta, con cache de lo ya cargado (todo cerrado)."""
        mm = self.minutos.setdefault(clave, {})
        a0, fin = self.cargado.get(clave, (None, None))
        if a0 is None or a < a0 or fin < a:
            mm.clear()
            fin = a
        if fin <= b:
            pliega(await self.db.fetch(sql, clave[0], _dt(fin), _dt(b + MIN), *args), mm)
            fin = b + MIN
        for m in [m for m in mm if m < a]:
            del mm[m]
        self.cargado[clave] = (a, fin)
        return mm

    async def tic(self, ahora: float | None = None) -> list:
        """Un tic: devuelve las filas NUEVAS (para avisar si el interruptor lo pide)."""
        ultimo = ultimo_cerrado(ahora if ahora is not None else datetime.now(UTC).timestamp())
        todas = []
        for c in self.candidatas:
            todas += await self.tic_candidata(c, ultimo)
        return todas

    async def tic_candidata(self, c: Candidata, ultimo: int) -> list:
        r = await self.db.fetchrow("SELECT hasta FROM bot_sombra_candidata WHERE candidata = $1 AND indice = $2",
                                   c.sha, c.indice)
        if r is None:
            await self.db.execute(
                "INSERT INTO bot_sombra_candidata (candidata, indice, definicion, desde, hasta) VALUES ($1, $2, $3,"
                " $4, $5) ON CONFLICT DO NOTHING", c.sha, c.indice, json.dumps(c.d), _dt(ultimo), _dt(ultimo - MIN))
            hasta = ultimo - MIN
        else:
            hasta = int(r["hasta"].timestamp())
        vivas = [dict(x) for x in await self.db.fetch(
            "SELECT * FROM bot_sombra WHERE candidata = $1 AND indice = $2 AND estado IN ('abierta', 'tocada')"
            " ORDER BY minuto", c.sha, c.indice)]
        ult = await self.db.fetchrow("SELECT minuto, estado, salida FROM bot_sombra WHERE candidata = $1 AND indice = $2"
                                     " ORDER BY minuto DESC LIMIT 1", c.sha, c.indice)
        for f in vivas:
            f.update(minuto=int(f["minuto"].timestamp()), lado_n=c.lado, esquema=c.esquema,
                     salida=int(f["salida"].timestamp()) if f["salida"] else None)
        previas = list(vivas)
        if ult is not None and ult["estado"] not in ("abierta", "tocada"):
            previas.append({"minuto": int(ult["minuto"].timestamp()), "estado": ult["estado"],
                            "salida": int(ult["salida"].timestamp())})
        tope = min(ultimo - MIN, hasta + LOTE_S)
        if tope <= hasta and not vivas:
            return []
        a = min([hasta - c.w * MIN] + [f["minuto"] for f in vivas])
        b = min(ultimo, tope + (A.HORIZONTE + 1) * MIN)
        flu = await self.carga_minutos((c.simbolo, c.venues, c.minimo), FLUJO_SQL, (list(c.venues), c.minimo),
                                       a, b)
        pre = await self.carga_minutos((c.simbolo, A.VENUE_REF), PRECIO_SQL, (A.VENUE_REF,), a, b)
        horas = {m: await self.hora(m) for m in range(a // 3600 * 3600, b + 1, 3600)}

        def flujo(m):
            if not horas.get(m // 3600 * 3600):
                return None
            f = flu.get(m)
            return f[c.columna] if f is not None else 0.0

        def barra(m):
            f = pre.get(m) if m <= ultimo else None
            return None if f is None or f[A.COL["o"]] is None else tuple(f[A.COL[k]] for k in ("o", "h", "l", "c"))

        antes = {f["minuto"]: dict(f) for f in vivas}
        nuevas, hasta2 = paso(c, previas, hasta, ultimo, flujo, barra)
        async with _transaccion(self.db) as cx:
            for f in vivas:
                if f != antes[f["minuto"]]:
                    await cx.execute(
                        "UPDATE bot_sombra SET estado = $4, exito = $5, neto = $6, salida = $7, motivo = $8,"
                        " ts_cambio = now() WHERE candidata = $1 AND indice = $2 AND minuto = $3",
                        c.sha, c.indice, _dt(f["minuto"]), f["estado"], f["exito"], f["neto"],
                        _dt(f["salida"]) if f["salida"] else None, f["motivo"])
            for f in nuevas:
                await cx.execute(
                    f"INSERT INTO bot_sombra ({', '.join(COLUMNAS)}) VALUES ({', '.join(f'${i + 1}' for i in range(len(COLUMNAS)))})"
                    " ON CONFLICT DO NOTHING",
                    *[_dt(f[k]) if k in ("minuto", "salida") and f[k] is not None else f[k] for k in COLUMNAS])
            await cx.execute("UPDATE bot_sombra_candidata SET hasta = $3 WHERE candidata = $1 AND indice = $2",
                             c.sha, c.indice, _dt(hasta2))
        return nuevas


# ---------------------------------------------------------------- la cuenta
def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / d
    margen = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return centro - margen, centro + margen


async def cuenta(db, c: Candidata) -> dict:
    r = await db.fetchrow(
        "SELECT k.desde, count(s.minuto) disparos, count(*) FILTER (WHERE s.estado IN ('exito', 'fracaso')) resueltas,"
        " count(*) FILTER (WHERE s.estado = 'exito') exitos, count(*) FILTER (WHERE s.estado = 'sin_dato') sin_dato"
        " FROM bot_sombra_candidata k LEFT JOIN bot_sombra s USING (candidata, indice)"
        " WHERE k.candidata = $1 AND k.indice = $2 GROUP BY k.desde", c.sha, c.indice)
    return dict(r) if r else {"desde": None, "disparos": 0, "resueltas": 0, "exitos": 0, "sin_dato": 0}


def texto_cuenta(c: Candidata, k: dict, corto: bool = False) -> str:
    n, e = k["resueltas"], k["exitos"]
    w = wilson(e, n)
    tasa = f"{e / n:.1%} (IC95 {w[0]:.1%}-{w[1]:.1%})" if n else "sin resueltas"
    desde = f"{k['desde']:%Y-%m-%d %H:%MZ}" if k.get("desde") else "aun no arranco"
    cal = " · SIN CALIBRAR (resueltas < 30)" if n < 30 else ""
    t = (f"{c.nombre()} · desde {desde}: {k['disparos']} disparos, {n} resueltas, {e} exitos, tasa {tasa},"
         f" sin dato {k['sin_dato']} · equilibrio {A.empate(c.esquema):.1%} · azar {A.azar(c.esquema):.1%}{cal}")
    return ("SOMBRA " + t) if corto else ("En sombra (se cuenta, no se avisa ni se opera): " + t)


NO_MEDIDA = ("No es una ventaja medida: es la cuenta en sombra de una hipotesis del estudio (regla del 10-20: entradas"
             " apagadas mientras no haya ventaja MEDIDA con n >= 30).")
APALANCAMIENTO = 10


def orden_calc(c: Candidata, f: dict) -> str:
    """El /calc del disparo: el precio de referencia (apertura del minuto siguiente), el stop y el objetivo de la
    candidata, y el margen que arriesga 1 USD al stop con la comision de los dos lados."""
    stop_pct = A.ESQUEMAS[c.esquema][1]
    obj, stop = A.niveles(f["entrada"], c.lado, c.esquema)
    margen = 1 / (stop_pct + 2 * A.COMISION) / APALANCAMIENTO
    return (f"/calc {c.simbolo.lower()} {f['entrada']:.6g} {stop:.6g} {obj:.6g} {margen:.2f}$ {APALANCAMIENTO}x"
            f" {'largo' if c.lado > 0 else 'corto'}")


def activa(entorno: dict) -> bool:
    return (entorno.get("BOT_SOMBRA_AVISA") or "").strip().lower() in ("1", "si", "on", "true")


def lee_entorno() -> dict:
    return dict(os.environ)
