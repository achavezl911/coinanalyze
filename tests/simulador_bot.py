"""EL SIMULADOR de la vida de las posiciones (remates 6 y 7 de BOT-2). Solo la biblioteca estandar (random con SEMILLA fija).

Genera secuencias de VIDAS reales de posiciones -abrir, anadir, parcial, cerrar (en ordenes de una o varias ejecuciones),
reabrir en el mismo minuto, el mismo simbolo y lado, otro simbolo a la vez, cobertura- y lo que el bot VE de ellas:
position/list cada minuto (con listas vacias falsas, el updatedTime que cambia con el stop, con cada ejecucion o solo con
la apertura y el funding), closed-pnl (UNA fila por orden, con sus dos horas y fillCount, retrasos y el reloj de Bybit
desfasado) y CAIDAS del bot (antes del tic, entre el tic y el veredicto, entre el veredicto y el latido, despues del latido).
Hace correr el Bot REAL (app/bot/servicio.py) con Bybit, Anthropic, Telegram y la base de mentira, en memoria, sin red, y
comprueba contra la verdad, en cada secuencia:
 I1 cada vida real se evalua (paga) COMO MUCHO una vez; y al menos una si es identificable -la anterior de su clave no tuvo
    un anadido sin ver antes de cerrar, sus filas ya estaban en closed-pnl mientras esta se veia y no reabrio a la misma
    entrada- y el bot estaba arriba (sin condicion de duracion);
 I2 toda puntuacion que el bot emite es la REAL de esa vida (pnl y ACIERTO/FALLO);
 I3 toda vida que el bot ve sin stop recibe el aviso sin_stop en esa lectura o en la siguiente;
 I4 nunca «CERRADA» de una vida que sigue abierta, y una sola por id;
 I5 nada pagado (evaluacion, ESCALADO, /evalua) sobre una posicion que la ultima lectura del bot no ensena;
 I6 sin anadidos, parciales ni caidas, toda vida cerrada evaluada se puntua (salvo la A2 tras una vida invisible, contada);
 I7 VIVACIDAD: todo id evaluado cuya clave quedo vacia con tiempo recibe UNA CERRADA (cifra, «ambigua: motivo» o «sin
    puntuar: motivo"), tambien en las no simples;
 I8 la seguridad no se cae: con excepciones inyectadas en la identidad, I3 sigue (y nada revienta);
 y «ninguna mas» ESTRICTA: cada «ambigua» lo es por un motivo VERDAD con lo que el bot conserva (A1: un anadido seguido de
 un cierre entre dos lecturas conservadas; A2: cierres a otra entrada entre la ultima lectura de la anterior -o la ultima
 racha de vacias sin vida abierta- y su primera lectura; A6: un cierre total a la entrada que se ve despues; A7: se fue sin
 filas que la cubran y volvio distinta).
LAS VARIANTES (fuera de S1-S4 de app/bot/vidas.py) piden 0 GRAVES (I2, I4, I1 doble, I3, reventon); lo que no se pueda
separar sale ambigua o sin puntuar, y se cuenta. Ver tests/test_bot_simulador.py. Suelto: python tests/simulador_bot.py
[semilla] [n] [variante]."""

from __future__ import annotations

import asyncio
import json
import math
import random
import sys
import zlib
from dataclasses import dataclass, field
from unittest import mock

M = 60_000
BASE = 1_793_000_000_000 // M * M  # un minuto cualquiera (2026-10-26), solo para que las horas parezcan de verdad
ESPERA = 35 * M  # lo que el bot espera a closed-pnl (vidas.ESPERA_MS): marca cuanto hay que dejarle para cerrar (I7)
FEE = 0.00055
IP = "138.186.31.141"
VARIANTES = ("s1_desfase", "s1_ordenes", "s1_updated", "s2_retraso", "s3_vacias", "s4_tick", "s4_misma", "cobertura",
             "migracion", "base_cierre", "excepciones")
GRAVES = ("I2", "I4", "I1 doble", "I3", "el bot revento")


# ------------------------------------------------------------------------------------------------------------- la verdad
@dataclass
class Vida:
    n: int
    clave: str
    lado: int
    eventos: list = field(default_factory=list)  # (t, tipo, q, precio, orden): abre, anade, parcial, cierra, stop
    filas: list = field(default_factory=list)
    us: set = field(default_factory=set)  # updatedTime (reloj de Bybit) que ensena: identifica la vida en lo que ve el bot
    oculta_e: float | None = None

    @property
    def inicio(self):
        return self.eventos[0][0]

    @property
    def fin(self):
        return next((t for t, tipo, *_ in self.eventos if tipo == "cierra"), math.inf)

    @property
    def pnl(self):
        return sum(f["pnl"] for f in self.filas)

    def estado(self, t, u_parcial: bool = True, funding: tuple = ()):
        """(tamano, entrada, updatedTime verdad, stop) a la hora t, o None si no esta abierta."""
        if not (self.inicio <= t < self.fin):
            return None
        q = e = 0.0
        u = stop = None
        for te, tipo, dq, px, _o in self.eventos:
            if te > t:
                break
            if tipo in ("abre", "anade"):
                e, q = (q * e + dq * px) / (q + dq), q + dq
            elif tipo == "parcial":
                q -= dq
            elif tipo == "stop":
                stop = px
            if u_parcial or tipo in ("abre", "stop"):
                u = te
        u = max([u] + [f for f in funding if self.inicio <= f <= t])
        return q, e, u, stop


@dataclass
class Secuencia:
    nombre: str
    vidas: list
    desfase: int  # ms: reloj de Bybit = verdad + desfase
    minutos: int  # lecturas 0..minutos-1, mas EXTRA para dejar puntuar
    vacias: set = field(default_factory=set)  # minutos en que position/list da la lista vacia (retCode 0)
    caida: tuple | None = None  # (minuto, minutos abajo, punto: antes_tic | antes_veredicto | antes_latido | tras_latido)
    base_caida: tuple | None = None  # (desde, hasta) ms en que la base no contesta
    cierre_caida: tuple | None = None  # (desde, hasta) ms en que la base no apunta un cierre
    rafagas: set = field(default_factory=set)  # minutos con una rafaga fresca (ESCALADO de la posicion de ese simbolo)
    evaluas: set = field(default_factory=set)  # minutos con un /evalua a mano
    simple: bool = False  # sin anadidos, parciales ni caidas (I6)
    u_parcial: bool = True  # el updatedTime cambia con cada ejecucion (S1) o solo con la apertura, el stop y el funding
    funding: tuple = ()  # horas (verdad) del funding: cambian el updatedTime de lo abierto
    excepciones: float = 0.0  # probabilidad de una excepcion inyectada en la identidad por clave y tic (I8)
    migracion: dict | None = None  # despliegue desde R5: {minuto, estado R5, veredictos, avisos}
    variante: str | None = None
    esperado: dict = field(default_factory=dict)  # (casos fijos) vida -> "cifra" | "ambigua" | "sin evaluar"

    EXTRA = 40

    def lectura(self, m: int) -> int:
        return BASE + m * M + 20_000

    def arriba(self, m: int) -> bool:
        """El bot lee en el minuto m. La caida pasa DENTRO del minuto c (segun su punto) y sigue abajo hasta c + largo."""
        if self.migracion and m < self.migracion["minuto"]:
            return False
        if not self.caida:
            return True
        c, largo, punto = self.caida
        return not (c < m <= c + largo or (m == c and punto == "antes_tic"))


def construye(vida: Vida, desfase: int, retrasos, off: int = 0, funding: tuple = ()) -> Vida:
    """Las filas de closed-pnl (UNA por orden: sus ejecuciones juntas, createdTime la primera, updatedTime la ultima) y los
    updatedTime de una vida a partir de sus eventos. retrasos: una funcion n -> ms; off: closed-pnl contra updatedTime."""
    q = e = 0.0
    ordenes: dict = {}
    for t, tipo, dq, px, orden in vida.eventos:
        if tipo in ("abre", "anade"):
            e, q = (q * e + dq * px) / (q + dq), q + dq
        elif tipo in ("parcial", "cierra"):
            dq = q if tipo == "cierra" else dq
            o = ordenes.setdefault(orden, {"t": [], "q": 0.0, "e": e, "x": px})
            o["t"].append(t)
            o["q"] += dq
            q -= dq
        vida.us.add(t + desfase)
    for f in funding:
        if vida.inicio <= f < vida.fin:
            vida.us.add(f + desfase)
    for k, (orden, o) in enumerate(ordenes.items()):
        pnl = vida.lado * (o["x"] - o["e"]) * o["q"] - FEE * (o["e"] + o["x"]) * o["q"]
        vida.filas.append({"orden": f"o{vida.n}-{orden}", "t": max(o["t"]), "c": min(o["t"]) + desfase + off,
                           "b": max(o["t"]) + desfase + off, "q": o["q"], "e": o["e"], "x": o["x"], "pnl": pnl,
                           "visible": max(o["t"]) + retrasos(k), "fills": len(o["t"]), "symbol": vida.clave.split(":")[0]})
    return vida


def _vida(rng: random.Random, num: int, clave: str, lado: int, t: int, p0: float, q: float, fin_max: int, paso: float,
          simple: bool, var: str | None) -> Vida:
    v = Vida(n=num, clave=clave, lado=lado)
    v.eventos.append((t, "abre", q, p0, None))
    dur = rng.choice((rng.randint(20_000, 3 * M), rng.randint(3 * M, 14 * M), rng.randint(14 * M, 26 * M)))
    fin = min(t + dur, fin_max)
    if rng.random() < 0.5:
        v.eventos.append((t + rng.randint(1_000, 40_000), "stop", 0, p0 * (1 - 0.006 * lado), None))
    e, n_orden = p0, 0

    def orden(tm, qq, tipo, px):  # una orden de cierre: una ejecucion, o varias (s1_ordenes) a segundos unas de otras
        nonlocal n_orden
        n_orden += 1
        partes = [qq] if var != "s1_ordenes" or rng.random() < 0.4 else None
        if partes is None:
            k = max(1, min(3, round(qq / paso)))
            uno = round(qq / paso)
            cortes = sorted(rng.sample(range(1, uno), k - 1)) if uno > k - 1 and k > 1 else []
            partes = [(b - a) * paso for a, b in zip([0] + cortes, cortes + [uno], strict=True)]
        ts = tm
        for i, parte in enumerate(partes):
            ultima = i == len(partes) - 1
            v.eventos.append((ts, tipo if ultima else "parcial", parte, px, n_orden))
            ts += rng.randint(1_000, 20_000)
        return ts

    tm_lista = sorted(rng.randint(t + 1_000, max(t + 2_000, fin - 1_000)) for _ in range(rng.randint(0, 5)))
    for tm in tm_lista:
        tipo = rng.choice(("stop",) if simple else ("anade", "parcial", "parcial", "anade", "stop"))
        if tipo == "anade" and var == "s4_tick" and rng.random() < 0.5:  # anadido a un tick de la media y parcial de lo de antes
            q0 = q
            px = e + (0.1 if paso < 0.01 else 0.01)
            e, q = (q * e + q0 * px) / (q + q0), q + q0
            v.eventos.append((tm, "anade", q0, px, None))
            orden(tm + rng.randint(2_000, 20_000), q0, "parcial", e * (1 + rng.uniform(-0.01, 0.01)))
            q = round(q - q0, 10)
        elif tipo == "anade":
            px = e * (1 + rng.choice((-1, 1)) * rng.uniform(0.0008, 0.006))
            dq = paso * rng.randint(1, 6)
            e, q = (q * e + dq * px) / (q + dq), q + dq
            v.eventos.append((tm, "anade", dq, px, None))
        elif tipo == "parcial" and q >= 2 * paso - 1e-12:
            dq = paso * rng.randint(1, round(q / paso) - 1)
            orden(tm, dq, "parcial", e * (1 + rng.uniform(-0.01, 0.01)))
            q = round(q - dq, 10)
        elif tipo == "stop":
            v.eventos.append((tm, "stop", 0, None if rng.random() < 0.3 else e * (1 - 0.006 * lado), None))
    v.eventos.sort(key=lambda x: x[0])
    orden(max(fin, v.eventos[-1][0] + 500), q, "cierra", e * (1 + rng.uniform(-0.01, 0.01)))
    v.eventos.sort(key=lambda x: x[0])
    v.oculta_e = e
    return v


def genera(rng: random.Random, n: int, simple: bool, var: str | None = None) -> Secuencia:
    minutos = rng.randint(20, 32)
    desfase = rng.randint(-8000, 8000)
    off = rng.randint(-8000, 8000) if var == "s1_desfase" else 0
    funding = (BASE + rng.randint(2, minutos - 2) * M + rng.randint(0, M - 1),) if var == "s1_updated" else ()
    simbolos = ["BTCUSDT"] + (["ETHUSDT"] if rng.random() < 0.5 else [])
    lados_de = {s: [rng.choice((1, -1))] for s in simbolos}
    if var == "cobertura":
        lados_de["BTCUSDT"] = [1, -1]
    vidas, num = [], 0
    retraso_max = 30 * M if var == "s2_retraso" else None
    for sym in simbolos:
        for lado in lados_de[sym]:
            clave = f"{sym}:{'Buy' if lado > 0 else 'Sell'}"
            paso = 0.001 if sym == "BTCUSDT" else 0.01
            precio = (110_000 if sym == "BTCUSDT" else 3_900) * (1 + rng.uniform(-0.02, 0.02))
            t = BASE + rng.randint(0, 4 * M)
            ultima_e = None
            while t < BASE + (minutos - 4) * M:
                num += 1
                p0 = precio * (1 + rng.uniform(-0.004, 0.004))
                if var == "s4_misma" and ultima_e and rng.random() < 0.6:
                    p0 = ultima_e  # S4 roto: reabre a la entrada media de la que cerro
                else:
                    while ultima_e and abs(p0 / ultima_e - 1) < 0.0005:
                        p0 = precio * (1 + rng.uniform(-0.004, 0.004))
                v = _vida(rng, num, clave, lado, t, p0, paso * rng.randint(2, 10), BASE + (minutos - 1) * M, paso, simple, var)
                if retraso_max:
                    retraso = lambda _k: rng.randint(0, retraso_max)  # noqa: E731
                else:
                    retraso = lambda _k: rng.choice((0, 0, 0, 0, rng.randint(1, 59_000), rng.randint(M, 2 * M), rng.randint(2 * M, 6 * M)))  # noqa: E731
                vidas.append(construye(v, desfase, retraso, off, funding))
                ultima_e, precio = v.oculta_e, precio * (1 + rng.uniform(-0.003, 0.003))
                t = v.fin + (rng.randint(500, 40_000) if rng.random() < 0.35 else rng.randint(M, 8 * M))
    vacias, m = set(), 1
    while m < minutos:
        if rng.random() < 0.05:
            racha = rng.randint(1, 3) if var == "s3_vacias" else 1
            vacias |= set(range(m, m + racha))
            m += racha  # (en el modelo base, S3: la lista vacia falsa dura una lectura)
        m += 1
    caida = None
    if not simple and (rng.random() < 0.3 or var == "base_cierre" and rng.random() < 0.5):
        caida = (rng.randint(2, minutos - 3), rng.randint(1, 8), rng.choice(("antes_tic", "antes_veredicto", "antes_latido", "tras_latido")))
    sec = Secuencia(nombre=f"{var or 'azar'}-{n}", vidas=vidas, desfase=desfase, minutos=minutos, vacias=vacias, caida=caida,
                    rafagas={m for m in range(minutos) if rng.random() < 0.08},
                    evaluas={m for m in range(minutos) if rng.random() < 0.04}, simple=simple and var is None,
                    u_parcial=var != "s1_updated", funding=funding, excepciones=0.15 if var == "excepciones" else 0.0, variante=var)
    if var == "base_cierre":
        d = rng.randint(5, minutos + 20)  # (la base vuelve antes del final: se mira que el cierre llegue UNA vez)
        sec.cierre_caida = (BASE + d * M, BASE + (d + rng.randint(2, max(2, min(30, minutos + Secuencia.EXTRA - 4 - d)))) * M)
    if var == "migracion":
        sec.migracion = _migracion(rng, sec)
        sec.caida = None
    return sec


def _migracion(rng: random.Random, sec: Secuencia) -> dict:
    """Un despliegue R5 -> el bot de la rama en el minuto D, con lo que R5 habria dejado: su estado («vidas» con las lecturas
    de la abierta, «cerradas» con la que cerro sin puntuar todavia), los veredictos de las dos y sus avisos sin_stop. El tipo,
    al azar: abierta, cerrada, las dos o ninguna."""
    d = rng.randint(4, max(5, sec.minutos - 6))
    tipo = rng.choice(("abierta", "cerrada", "las dos", "ninguna"))
    t_d = sec.lectura(d)
    estado: dict = {"vidas": {}, "cerradas": {}}
    veredictos, avisos = [], []
    puntuadas = []  # las que R5 ya habia puntuado antes del despliegue
    for clave in sorted({v.clave for v in sec.vidas}):
        vs = [v for v in sec.vidas if v.clave == clave and v.inicio < t_d]
        if not vs:
            continue
        lecturas = [m for m in range(d) if m not in sec.vacias]

        def vista(v, m):
            return v.estado(sec.lectura(m), sec.u_parcial, sec.funding)
        abierta = vs[-1] if vs[-1].fin > t_d else None
        cerrada = next((v for v in reversed(vs) if v.fin <= t_d and t_d - v.fin < ESPERA), None)
        elegidas = []
        if abierta and tipo in ("abierta", "las dos"):
            elegidas.append(("vida", abierta))
        if cerrada and tipo in ("cerrada", "las dos"):
            elegidas.append(("cerrada", cerrada))
        for papel, v in elegidas:
            ms = [m for m in lecturas if vista(v, m)]
            if not ms:
                continue
            q, e, u, stop = vista(v, ms[0])
            vid = f"{clave}:{u + sec.desfase}"
            p = {"clave": clave, "symbol": clave.split(":")[0], "lado": v.lado, "cantidad": q, "entrada": e,
                 "actualizada": u + sec.desfase, "id": vid}
            veredictos.append((sec.lectura(ms[0]) + 5_000, vid, p))
            if stop is None:
                avisos.append((sec.lectura(ms[0]) + 1_000, vid, p))
            obs, previo = [], None
            for m in ms:
                q, e, _u, _s = vista(v, m)
                if (q, e) != previo:
                    obs.append([sec.lectura(m), q, e])
                    previo = (q, e)
            if papel == "vida":
                estado["vidas"][clave] = {"id": vid, "obs": obs, "reapertura": None}
            else:
                estado["cerradas"][vid] = [v.fin + sec.desfase, obs[0][1], None]
        for v in vs:  # las demas cerradas que R5 vio: puntuadas por R5 (con lo real), con sus ordenes apuntadas
            ms = [m for m in lecturas if vista(v, m)]
            if v.fin <= t_d and ms and not any(v is w for _p, w in elegidas):
                q, e, u, _s = vista(v, ms[0])
                p = {"clave": clave, "symbol": clave.split(":")[0], "lado": v.lado, "cantidad": q, "entrada": e,
                     "actualizada": u + sec.desfase, "id": f"{clave}:{u + sec.desfase}"}
                puntuadas.append((sec.lectura(ms[0]) + 5_000, v.fin + 1_000, p, v))
    return {"minuto": d, "estado": estado, "veredictos": veredictos, "avisos": avisos, "tipo": tipo, "puntuadas": puntuadas}


# --------------------------------------------------------------------------------------------- lo de mentira (sin red)
class Rec(tuple):
    """Una fila como las de asyncpg: por posicion y por nombre."""

    def __new__(cls, d: dict):
        r = super().__new__(cls, tuple(d.values()))
        r._k = tuple(d)
        return r

    def __getitem__(self, k):
        return tuple.__getitem__(self, self._k.index(k) if isinstance(k, str) else k)

    def keys(self):
        return self._k


class BaseFalsa:
    """La base del bot en memoria: lo que el bot escribe y lee de bot_evento, bot_evaluacion, bot_operacion, bot_estado y
    bot_crudo (las consultas de R5, R6 y R7). Una consulta que no conoce, la dice."""

    def __init__(self, reloj: list, caida=None, cierre_caida=None):
        self.reloj, self.caida, self.cierre_caida = reloj, caida, cierre_caida
        self.evento, self.evaluacion, self.operacion, self.estado, self.crudo = [], [], {}, None, []

    def _mira(self, sql: str = ""):
        if self.caida and self.caida[0] <= self.reloj[0] < self.caida[1]:
            raise OSError("connection refused (postgresql 5432)")
        if self.cierre_caida and "'cierre'" in sql and "INSERT" in sql and self.cierre_caida[0] <= self.reloj[0] < self.cierre_caida[1]:
            raise OSError("connection reset (postgresql 5432)")

    async def execute(self, sql, *a):
        self._mira(sql)
        ahora = self.reloj[0]
        if "INSERT INTO bot_evento" in sql:
            tipo, sym, minuto, _lado, _clase, enviada, det = a
            if tipo in ("rafaga", "clase") and any((e["tipo"], e["symbol"], e["minuto"]) == (tipo, sym, minuto) for e in self.evento):
                return "INSERT 0 0"
            self.evento.append({"ts": ahora, "tipo": tipo, "symbol": sym, "minuto": minuto, "enviada": enviada, "detalle": json.loads(det)})
        elif "INSERT INTO bot_evaluacion" in sql and "'veredicto'" in sql:
            pos, v, _vd, det = a
            self.evaluacion.append({"ts": ahora, "tipo": "veredicto", "posicion": pos, "veredicto": v, "detalle": json.loads(det)})
        elif "INSERT INTO bot_evaluacion" in sql and "'cierre'" in sql:
            pos, v, pnl, acierto, det = a
            self.evaluacion.append({"ts": ahora, "tipo": "cierre", "posicion": pos, "veredicto": v, "pnl": pnl, "acierto": acierto,
                                    "detalle": json.loads(det)})
        elif "INSERT INTO bot_operacion" in sql:
            orden, sym, q, e, x, pnl, _lev, ms, det = a
            if orden in self.operacion:
                return "INSERT 0 0"
            self.operacion[orden] = {"orden": orden, "symbol": sym, "q": q, "e": e, "x": x, "pnl": pnl, "ms": int(ms),
                                     "c": json.loads(det).get("createdTime")}
        elif "INSERT INTO bot_estado" in sql:
            self.estado = (ahora, a[0])
        elif "INSERT INTO bot_crudo" in sql:
            self.crudo.append((ahora, a[0], a[1], json.loads(a[2])))
        elif "DELETE FROM bot_crudo" in sql:
            return "DELETE 0"
        else:
            raise AssertionError(f"consulta no prevista: {sql[:120]}")
        return "INSERT 0 1"

    async def fetchval(self, sql, *a):
        self._mira(sql)
        if "sum(coste_usd)" in sql:
            return 0.0
        if "tipo = 'parte'" in sql:
            return None
        if "SELECT 1 FROM bot_evaluacion WHERE tipo = 'cierre'" in sql:
            return 1 if any(e["tipo"] == "cierre" and e["posicion"] == a[0] for e in self.evaluacion) else None
        raise AssertionError(f"consulta no prevista: {sql[:120]}")

    async def fetchrow(self, sql, *a):
        self._mira(sql)
        if "FROM bot_estado" in sql:
            return Rec({"t": int(self.estado[0] // 1000), "estado": self.estado[1]}) if self.estado else None
        if "tipo = 'validacion'" in sql:
            return None
        raise AssertionError(f"consulta no prevista: {sql[:120]}")

    async def fetch(self, sql, *a):
        self._mira(sql)
        if "tipo IN ('rafaga', 'clase')" in sql or "detalle->>'semana'" in sql or "WHERE tipo = 'validacion'" in sql:
            return []
        if "DISTINCT ON (posicion)" in sql:
            cerradas = {e["posicion"] for e in self.evaluacion if e["tipo"] == "cierre"}
            primero: dict = {}
            automatica = "LIKE 'posicion nueva%'" in sql
            for e in self.evaluacion:
                if e["tipo"] == "veredicto" and e["posicion"] not in cerradas and \
                        (not automatica or str(e["detalle"].get("motivo", "")).startswith("posicion nueva")):
                    primero.setdefault(e["posicion"], e)
            return [Rec({"posicion": p, "veredicto": e["veredicto"], "p": json.dumps(e["detalle"].get("posicion")), "ms": int(e["ts"])})
                    for p, e in primero.items()]
        if "tipo IN ('stop', 'liquidacion', 'sin_stop')" in sql:
            out = []
            for e in self.evento:
                if e["tipo"] not in ("stop", "liquidacion", "sin_stop"):
                    continue
                d = e["detalle"]
                p = (d.get("entradas") or {}).get("posicion") or {}
                if "entradas" in sql:  # R7: los de R5 por la posicion que guardaron
                    k = d.get("visto") or (f"{p.get('clave')}:{p.get('actualizada')}" if p.get("clave") else None)
                elif "detalle->>'visto'" in sql:  # R6
                    k = d.get("visto") or d.get("posicion")
                else:  # R5
                    k = d.get("posicion")
                out.append(Rec({"k": k, "tipo": e["tipo"]}))
            return out
        if "detalle->'ordenes'" in sql:  # R7: las ordenes de los cierres ya apuntados
            return [Rec({"o": json.dumps((e["detalle"] or {}).get("ordenes") or [])}) for e in self.evaluacion if e["tipo"] == "cierre"]
        if "SELECT orden FROM bot_operacion" in sql:
            return [Rec({"orden": o}) for o in self.operacion]
        if "FROM bot_operacion" in sql and "symbol = $1" in sql:  # R5: de_la_vida
            sym, ap, fin = a
            return [Rec({"orden": f["orden"], "pnl_usd": f["pnl"], "entrada": f["e"], "salida": f["x"], "cantidad": f["q"], "ms": f["ms"]})
                    for f in sorted(self.operacion.values(), key=lambda f: f["ms"]) if f["symbol"] == sym and ap <= f["ms"] <= fin]
        if "FROM bot_operacion" in sql and "createdTime" in sql:  # R7: las filas al arrancar, con sus dos horas
            return [Rec({"orden": f["orden"], "symbol": f["symbol"], "q": f["q"], "e": f["e"], "x": f["x"], "pnl": f["pnl"],
                         "ms": f["ms"], "c": f["c"]}) for f in sorted(self.operacion.values(), key=lambda f: f["ms"])]
        if "FROM bot_operacion" in sql:  # R6
            return [Rec({"orden": f["orden"], "symbol": f["symbol"], "q": f["q"], "e": f["e"], "x": f["x"], "pnl": f["pnl"], "ms": f["ms"]})
                    for f in self.operacion.values()]
        raise AssertionError(f"consulta no prevista: {sql[:120]}")


@dataclass
class Registro:
    lecturas: dict = field(default_factory=dict)  # minuto -> lo que vio el bot: {clave: (vida, u, stop)} (None: no leyo)
    pagos: list = field(default_factory=list)  # (ms, tipo, posicion, claves de la ultima lectura de ESE bot)
    textos: list = field(default_factory=list)
    errores: list = field(default_factory=list)
    ultima: set | None = None
    visibles: dict = field(default_factory=dict)  # minuto -> ordenes que closed-pnl ensenaba en esa lectura


class Simulacion:
    def __init__(self, sec: Secuencia, sv):
        self.sec, self.sv = sec, sv
        self.reloj = [BASE]
        self.base = BaseFalsa(self.reloj, sec.base_caida, sec.cierre_caida)
        self.reg = Registro()
        self.minuto = 0
        self.a2_simples = 0
        self.mirado: dict = {}
        self.previas: dict = {}  # vida -> evaluaciones que hizo R5 antes del despliegue
        self.por_u = {(v.clave, u): v for v in sec.vidas for u in v.us}
        self.rng = random.Random(zlib.crc32(sec.nombre.encode()))

    # --- Bybit
    def lista(self) -> list:
        t, out, vistas = self.reloj[0], [], {}
        if self.minuto not in self.sec.vacias:
            for v in self.sec.vidas:
                e = v.estado(t, self.sec.u_parcial, self.sec.funding)
                if e:
                    q, ent, u, stop = e
                    sym, side = v.clave.split(":")
                    out.append({"symbol": sym, "side": side, "size": repr(round(q, 10)), "avgPrice": repr(ent), "markPrice": repr(ent),
                                "leverage": "50", "liqPrice": "", "stopLoss": repr(stop) if stop else "", "takeProfit": "",
                                "positionIM": "", "unrealisedPnl": "", "createdTime": str(BASE), "updatedTime": str(u + self.sec.desfase)})
                    vistas[v.clave] = (v, u + self.sec.desfase, stop)
        self.reg.lecturas[self.minuto] = vistas
        self.reg.ultima = set(vistas)
        return out

    def cerradas(self) -> list:
        t = self.reloj[0]
        filas = sorted((f for v in self.sec.vidas for f in v.filas if f["visible"] <= t), key=lambda f: -f["b"])
        self.reg.visibles[self.minuto] = {f["orden"] for f in filas}
        return [{"symbol": f["symbol"], "orderId": f["orden"], "side": "x", "closedSize": repr(f["q"]), "avgEntryPrice": repr(f["e"]),
                 "avgExitPrice": repr(f["x"]), "closedPnl": repr(f["pnl"]), "leverage": "50", "updatedTime": str(f["b"]),
                 "createdTime": str(f["c"]), "fillCount": str(f["fills"])} for f in filas[:100]]

    async def get(self, ruta, **kw):
        if ruta == "/v5/user/query-api":
            return {"retCode": 0, "result": {"readOnly": 1, "ips": [IP]}}
        if ruta == "/v5/position/list":
            return {"retCode": 0, "result": {"list": self.lista()}}
        if ruta == "/v5/position/closed-pnl":
            return {"retCode": 0, "result": {"list": self.cerradas(), "nextPageCursor": ""}}
        if ruta == "/v5/market/risk-limit":
            return {"retCode": 0, "result": {"list": []}}
        raise AssertionError(f"ruta no prevista: {ruta}")

    # --- el bot de verdad, con lo de fuera de mentira
    def bot(self):
        sv, reg = self.sv, self.reg
        b = sv.Bot({"BYBIT_API_KEY": "k", "BYBIT_API_SECRET": "s", "ANTHROPIC_API_KEY": "a", "TELEGRAM_BOT_TOKEN": "1:t",
                    "TELEGRAM_CHAT_ID": "42", "BOT_INFORMES": "/tmp"}, self.base, None)
        b.bybit = self
        reg.ultima = None  # un bot que arranca no ha leido nada

        async def manda(texto):
            reg.textos.append((self.reloj[0], texto))
            return True

        async def sobre(activo):
            return {}, {"decide": {"bias": {"value": "LONG"}, "evaluable": {"value": True}}}

        async def opus(ruta, texto):
            return {"texto": "VEREDICTO: " + ("A FAVOR" if zlib.crc32(texto.encode()) % 2 else "EN CONTRA"), "error": None, "id": None}

        evalua = b.evalua

        async def evalua_registrada(p, motivo):
            reg.pagos.append((self.reloj[0], "evalua" if motivo.startswith("posicion nueva") else "a peticion", dict(p),
                              set(reg.ultima or ())))
            await evalua(p, motivo)

        async def escala(p, alerta):
            reg.pagos.append((self.reloj[0], "escala", dict(p), set(reg.ultima or ())))

        b.manda, b.sobre, b.opus, b.evalua, b.escala = manda, sobre, opus, evalua_registrada, escala
        return b

    def pendiente(self) -> bool:
        cerradas = {e["posicion"] for e in self.base.evaluacion if e["tipo"] == "cierre"}
        for e in self.base.evaluacion:
            if e["tipo"] == "veredicto" and e["posicion"] not in cerradas:
                clave = e["posicion"].rsplit(":", 1)[0]
                if all(v.fin <= self.reloj[0] for v in self.sec.vidas if v.clave == clave):
                    return True
        return False

    def _migra(self):
        """Lo que R5 dejo en la base al desplegar (estado, veredictos y avisos)."""
        mg = self.sec.migracion
        self.base.estado = (self.sec.lectura(mg["minuto"] - 1) + 5_000, json.dumps(mg["estado"]))
        for ts, vid, p in mg["veredictos"]:
            self.base.evaluacion.append({"ts": ts, "tipo": "veredicto", "posicion": vid, "veredicto": "A FAVOR",
                                         "detalle": {"motivo": "posicion nueva", "posicion": p}})
            v = self.por_u.get((p["clave"], p["actualizada"]))
            if v:
                self.previas[v.n] = self.previas.get(v.n, 0) + 1
        for ts, ts_c, p, v in mg.get("puntuadas", []):
            self.base.evaluacion.append({"ts": ts, "tipo": "veredicto", "posicion": p["id"], "veredicto": "A FAVOR",
                                         "detalle": {"motivo": "posicion nueva", "posicion": p}})
            self.base.evaluacion.append({"ts": ts_c, "tipo": "cierre", "posicion": p["id"], "veredicto": "A FAVOR", "pnl": v.pnl,
                                         "acierto": v.pnl > 0, "detalle": {"ordenes": [f["orden"] for f in v.filas], "nota": None}})
            for f in v.filas:
                self.base.operacion[f["orden"]] = {"orden": f["orden"], "symbol": f["symbol"], "q": f["q"], "e": f["e"], "x": f["x"],
                                                   "pnl": f["pnl"], "ms": int(f["b"]), "c": f["c"]}
            self.previas[v.n] = self.previas.get(v.n, 0) + 1
        for ts, vid, p in mg["avisos"]:
            self.base.evento.append({"ts": ts, "tipo": "sin_stop", "symbol": p["symbol"], "minuto": None, "enviada": True,
                                     "detalle": {"posicion": vid, "texto": "sin stop", "entradas": {"posicion": p}}})
            self.reg.textos.append((ts, f"{p['symbol']} sin stop puesto"))

    async def corre(self):
        sec = self.sec
        if sec.migracion:
            self._migra()
        bot = None
        m = -1
        while True:  # y, mientras quede una evaluada sin CERRADA con su clave ya vacia, hasta 130 min mas (I7: las 2 h de S3)
            m += 1
            if m >= sec.minutos + sec.EXTRA and (m >= sec.minutos + sec.EXTRA + 130 or not self.pendiente()):
                break
            self.minuto = m
            self.reloj[0] = sec.lectura(m)
            if not sec.arriba(m):
                bot = None
                self.reg.lecturas[m] = None
                continue
            if bot is None:  # arranca o vuelve de la caida
                bot = self.bot()
                await bot.carga()
            punto = sec.caida[2] if sec.caida and sec.caida[0] == m else None
            try:
                await bot.tic_bybit()
                if m in sec.rafagas and bot.pos:
                    sym = next(iter(bot.pos.values()))["symbol"]
                    await bot.rafaga({"activo": sym, "minuto": self.reloj[0] // M, "lado": 1, "z": 5.0, "v": 3.0, "imb": 0.5,
                                      "precio": 1.0, "clase": None, "clase_min": None}, self.reloj[0] // M, {sym: {}})
                if m in sec.evaluas:
                    await bot.atiende("/evalua btc")
            except Exception as e:  # el bucle real (cada) lo anota y sigue; aqui se cuenta (salvo la base caida a proposito)
                if not (isinstance(e, OSError) and sec.base_caida):
                    self.reg.errores.append(f"{m}: {type(e).__name__} {e}")
            if punto == "antes_veredicto":
                for t in list(bot.tareas):
                    t.cancel()
                await asyncio.gather(*list(bot.tareas), return_exceptions=True)
                bot = None
                continue
            while bot.tareas:
                await asyncio.gather(*list(bot.tareas), return_exceptions=True)
            if punto == "antes_latido":
                bot = None
                continue
            try:
                await bot.latido()
            except Exception as e:  # tic_minuto lo anota y sigue; con la base caida a proposito, es lo esperado
                if not (isinstance(e, OSError) and sec.base_caida):
                    self.reg.errores.append(f"{m} latido: {type(e).__name__} {e}")
            if punto == "tras_latido":
                bot = None


def simula(sec: Secuencia, sv) -> Simulacion:
    s = Simulacion(sec, sv)
    parches = [mock.patch.object(sv.time, "time", lambda: s.reloj[0] / 1000)]
    if sec.excepciones and hasattr(sv, "vidas"):  # I8: excepciones inyectadas en la identidad, clave a clave
        original = sv.vidas.Libro._decide_clave

        def con_fallos(libro, clave, k, ahora, out):
            if s.rng.random() < sec.excepciones:
                raise RuntimeError(f"fallo inyectado en {clave}")
            return original(libro, clave, k, ahora, out)
        parches.append(mock.patch.object(sv.vidas.Libro, "_decide_clave", con_fallos))
    for p in parches:
        p.start()
    try:
        asyncio.run(s.corre())
    finally:
        for p in parches:
            p.stop()
    return s


# ------------------------------------------------------------------------------------------------------- las invariantes
def _vida_de(s: Simulacion, p: dict):
    return s.por_u.get((p.get("clave"), p.get("actualizada")))


def _conservadas(s: Simulacion) -> tuple[dict, int | None]:
    """Las lecturas que el bot CONSERVA: una caida entre el tic y el latido le hace perder la de ese minuto (salvo la de una
    vida cuyo veredicto llego a la base en ese minuto). -> (vistas {vida: [minutos]}, minuto perdido)."""
    sec, reg = s.sec, s.reg
    vistas: dict = {}
    for m, lec in reg.lecturas.items():
        for v, _u, _stop in (lec or {}).values():
            vistas.setdefault(v.n, []).append(m)
    perdida = None
    if sec.caida and sec.caida[2] in ("antes_veredicto", "antes_latido"):
        c = sec.caida[0]
        evaluadas = {w.n for w in (_vida_de(s, e["detalle"].get("posicion") or {}) for e in s.base.evaluacion
                                   if e["tipo"] == "veredicto" and sec.lectura(c) <= e["ts"] < sec.lectura(c + 1)) if w}
        vistas = {n: [m for m in ms if m != c or (sec.caida[2] == "antes_latido" and n in evaluadas)] for n, ms in vistas.items()}
        vistas = {n: ms for n, ms in vistas.items() if ms}
        perdida = c
    return vistas, perdida


def comprueba(s: Simulacion) -> list[str]:
    """-> las invariantes que caen en esta secuencia (vacia: todas pasan)."""
    sec, reg, base = s.sec, s.reg, s.base
    fallos: list = [f"el bot revento: {e[:160]}" for e in reg.errores]
    mira = lambda k: s.mirado.__setitem__(k, s.mirado.get(k, 0) + 1)  # noqa: E731
    fin_lecturas = max(reg.lecturas) + 1
    fuera_del_modelo = sec.variante is not None
    pagadas: dict = dict(s.previas)
    for ms, tipo, p, ultima in reg.pagos:
        mira("I5")
        if p.get("clave") not in ultima:  # I5
            fallos.append(f"I5 {tipo} pagado sobre {p.get('clave')} que la ultima lectura no ensena (a las {(ms - BASE) / M:.1f} min)")
        if tipo == "evalua":
            v = _vida_de(s, p)
            pagadas[v.n if v else None] = pagadas.get(v.n if v else None, 0) + 1
    for n, k in pagadas.items():  # I1, cota alta
        if n is None:
            fallos.append(f"I1 doble: {k} evaluacion(es) de algo que no es ninguna vida real")
        elif k > 1:
            fallos.append(f"I1 doble: la vida {n} se evaluo {k} veces")
    veredictos: dict = {}  # el PRIMERO automatico de cada id: el que el bot puntua
    for e in base.evaluacion:
        if e["tipo"] == "veredicto" and str(e["detalle"].get("motivo", "")).startswith("posicion nueva"):
            veredictos.setdefault(e["posicion"], e)
    for e in base.evaluacion:  # (el bot de antes de R6 tambien puntuaba la primera a mano)
        if e["tipo"] == "veredicto":
            veredictos.setdefault(e["posicion"], e)
    vistas_todas: dict = {}
    for m, lec in reg.lecturas.items():
        for v, _u, _stop in (lec or {}).values():
            vistas_todas.setdefault(v.n, []).append(m)
    vistas, perdida = _conservadas(s)
    por_n = {v.n: v for v in sec.vidas}
    # I1, cota baja (en el modelo): identificable, con la evidencia mientras se veia, y el bot arriba (sin condicion de duracion)
    if not fuera_del_modelo:
        for v in sec.vidas:
            ms = sorted(vistas_todas.get(v.n, []))
            if not ms:
                continue
            m_ev = _evidencia(s, v, ms, vistas_todas)
            if m_ev is None:
                continue
            mira("I1 cota baja")
            if pagadas.get(v.n, 0) != 1:
                fallos.append(f"I1 la vida {v.n} ({v.clave}) era identificable desde el minuto {m_ev} y se evaluo {pagadas.get(v.n, 0)} veces")
    # I3 (e I8 con excepciones): el aviso sin_stop, el que SALE (Telegram)
    avisos = [(ts, t) for ts, t in reg.textos if "sin stop" in t]
    for v in sec.vidas:
        for m in sorted(vistas_todas.get(v.n, [])):
            lec = reg.lecturas[m][v.clave]
            if lec[2] is None:  # sin stop
                siguiente = m + 1 < fin_lecturas and reg.lecturas.get(m + 1) is not None and sec.arriba(m + 1) \
                    and not (sec.caida and sec.caida[0] in (m, m + 1))
                if siguiente:
                    mira("I3")
                sym, lado = v.clave.split(":")[0], "LARGO" if v.lado > 0 else "CORTO"
                if siguiente and not any(v.inicio - 2 * M <= ts <= sec.lectura(m + 1) and sym in t
                                         and ("LARGO" not in t and "CORTO" not in t or lado in t) for ts, t in avisos):
                    fallos.append(f"I3 la vida {v.n} se vio sin stop en el minuto {m} y no tuvo aviso sin_stop")
                break
    # I2 e I4: cada cierre
    cierres: dict = {}
    de_cierre: dict = {}
    puntuadas: set = set()
    for e in base.evaluacion:
        if e["tipo"] != "cierre":
            continue
        cierres[e["posicion"]] = cierres.get(e["posicion"], 0) + 1
        ver = veredictos.get(e["posicion"])
        p_ev = ver["detalle"].get("posicion") if ver else next((p for _ms, tipo, p, _u in reg.pagos  # (veredicto sin registrar)
                                                                 if tipo == "evalua" and p.get("id") == e["posicion"]), None)
        v = _vida_de(s, p_ev or {})
        de_cierre[id(e)] = v
        if v is None:
            fallos.append(f"I2 un cierre de {e['posicion']} sin vida real detras")
            continue
        mira("I4")
        if v.fin > e["ts"]:
            fallos.append(f"I4 CERRADA de la vida {v.n} a las {(e['ts'] - BASE) / M:.1f} min y cierra a las {(v.fin - BASE) / M:.1f}")
        nota = (e["detalle"] or {}).get("nota") or ""
        if e["pnl"] is not None:
            mira("I2")
            puntuadas.add(v.n)
            if abs(e["pnl"] - v.pnl) > 1e-6 * max(1.0, abs(v.pnl)):
                fallos.append(f"I2 la vida {v.n} puntuada {e['pnl']:+.4f} y lo real es {v.pnl:+.4f}")
            elif e["veredicto"] != "NO EVALUABLE" and e["acierto"] != ((v.pnl > 0) == (e["veredicto"] == "A FAVOR")):
                fallos.append(f"I2 la vida {v.n}: acierto {e['acierto']} con pnl {v.pnl:+.4f} y veredicto {e['veredicto']}")
        else:
            if not fuera_del_modelo:
                mira("ninguna mas")
                motivo = _ambigua_verdad(s, v, nota, vistas, perdida)
                if motivo:
                    fallos.append(f"ninguna mas: la vida {v.n} sin puntuar por «{nota[:90]}» y {motivo}")
            if sec.simple and nota.startswith(("ambigua: A2", "ambigua: S1")) and not _ambigua_verdad(s, v, nota, vistas, perdida):
                s.a2_simples += 1  # tras una vida entera que el bot no vio, o una fila a caballo (S1): declaradas, aparte (I6)
            elif sec.simple:  # I6
                fallos.append(f"I6 la vida {v.n} cerrada sin puntuar en una secuencia simple: {nota[:100]}")
    for i, k in cierres.items():
        if k > 1:
            fallos.append(f"I4 {k} cierres de {i}")
    # I7: todo id evaluado cuya clave quedo vacia con tiempo recibe UNA CERRADA
    evaluados = {e["posicion"]: e for e in base.evaluacion if e["tipo"] == "veredicto"
                 and str(e["detalle"].get("motivo", "")).startswith("posicion nueva")}
    for _ms, tipo, p, _u in reg.pagos:
        if tipo == "evalua" and p.get("id") and p["id"] not in evaluados:
            evaluados[p["id"]] = {"detalle": {"posicion": p}}
    fin_sim = sec.lectura(fin_lecturas - 1)
    for i in evaluados:
        clave = i.rsplit(":", 1)[0]
        ultima_fin = max([w.fin for w in sec.vidas if w.clave == clave] + [0])
        abierta_al_final = any(w.clave == clave and w.fin > fin_sim for w in sec.vidas)
        vuelta = next((sec.lectura(m) for m in range(fin_lecturas) if sec.lectura(m) >= ultima_fin and reg.lecturas.get(m) is not None),
                      math.inf)  # la primera lectura del bot sin la vida: desde ahi cuenta su ESPERA
        listo = max(vuelta + ESPERA, sec.cierre_caida[1] if sec.cierre_caida else 0, sec.base_caida[1] if sec.base_caida else 0)
        if abierta_al_final or listo + 3 * M > fin_sim:
            continue
        mira("I7")
        if cierres.get(i, 0) != 1:
            fallos.append(f"I7 el id {i} se evaluo, su clave quedo vacia a las {(ultima_fin - BASE) / M:.1f} min y tiene {cierres.get(i, 0)} CERRADA")
    # los casos fijos: la cifra ESPERADA
    for n, que in sec.esperado.items():
        v = por_n[n]
        mios = [e for e in base.evaluacion if e["tipo"] == "cierre" and de_cierre.get(id(e)) is v]
        if que == "cifra" and not (len(mios) == 1 and mios[0]["pnl"] is not None and abs(mios[0]["pnl"] - v.pnl) < 1e-6):
            fallos.append(f"esperado: la vida {n} puntuada {v.pnl:+.4f}; tiene {[(e['pnl'], (e['detalle'] or {}).get('nota')) for e in mios]}")
        elif que == "ambigua" and not (len(mios) == 1 and mios[0]["pnl"] is None):
            fallos.append(f"esperado: la vida {n} ambigua; tiene {[(e['pnl'], (e['detalle'] or {}).get('nota')) for e in mios]}")
        elif que == "sin evaluar" and pagadas.get(n, 0):
            fallos.append(f"esperado: la vida {n} sin evaluar (pegada, declarado); se evaluo {pagadas.get(n)} veces")
    return fallos


def _evidencia(s: Simulacion, v: Vida, ms: list, vistas: dict) -> int | None:
    """El primer minuto en que el bot PUDO saber que v es nueva mientras la veia (None: no identificable en el modelo)."""
    sec, reg = s.sec, s.reg
    antes = [w for w in sec.vidas if w.clave == v.clave and w.fin <= v.inicio and vistas.get(w.n)]
    pred = max(antes, key=lambda w: w.fin) if antes else None
    desde = max(vistas[pred.n]) if pred else 0
    if pred:
        t_ult = sec.lectura(desde)
        if any(tipo == "anade" and te > t_ult for te, tipo, *_ in pred.eventos):
            return None  # un anadido sin ver antes de cerrar la anterior (A1)
        e_pred = pred.estado(t_ult, sec.u_parcial, sec.funding)
        e_v = v.estado(sec.lectura(ms[0]), sec.u_parcial, sec.funding)
        if e_pred and e_v and abs(e_pred[1] / e_v[1] - 1) <= 1e-9:
            return None  # reabierta a la misma entrada (A6)
    if any(not sec.arriba(m) for m in range(desde, ms[-1] + 1)) or (sec.caida and desde <= sec.caida[0] <= ms[-1]):
        return None
    if any(_a_caballo(s, v.clave, f, m) for f in (pred.filas if pred else []) + v.filas for m in range(max(0, desde - 1), ms[-1] + 1)):
        return None  # una fila a caballo de una lectura con dos historias posibles (S1, declarado)
    ordenes_pred = {f["orden"] for f in pred.filas if f["t"] > sec.lectura(desde)} if pred else set()
    for m in ms:  # la primera lectura en que se ve y closed-pnl ya trae el cierre de la anterior
        if ordenes_pred <= reg.visibles.get(m, set()):
            return m
    return None


def _a_caballo(s: Simulacion, clave: str, f: dict, m: int) -> bool:
    """¿La fila f esta a caballo de la lectura m para el bot (S1: b <= max(updatedTime, hora local - 10 s) < h)?"""
    lec = s.reg.lecturas.get(m)
    if not lec:
        return False
    x = lec.get(clave)
    frontera = max(x[1] if x else -math.inf, s.sec.lectura(m) - 10_000)
    return min(f["c"], f["b"]) - 10_000 <= frontera < max(f["c"], f["b"]) + 10_000


def _s4_roto(s: Simulacion, vs: list) -> bool:
    """¿Hay en estas vidas algo fuera de S4 (o de S1 por ordenes de varias ejecuciones)? Una reapertura a la entrada de la que
    cerro, un anadido que no mueve la media (S4: 1e-9), o una fila de varias ejecuciones."""
    sec = s.sec
    for w in vs:
        if any(f["fills"] > 1 for f in w.filas):
            return True
        for te, tipo, dq, px, _o in w.eventos:
            antes = w.estado(te - 1, True)
            if tipo == "anade" and antes and abs(((antes[0] * antes[1] + dq * px) / (antes[0] + dq)) / antes[1] - 1) < 1e-9:
                return True
        e_fin = (w.estado(w.fin - 1, True) or (0, None))[1] if w.fin < math.inf else None
        for x in sec.vidas:
            if e_fin and x.clave == w.clave and x is not w and x.inicio >= w.fin and x.inicio - w.fin < 10 * M \
                    and abs(x.eventos[0][3] / e_fin - 1) <= 1e-9:
                return True
    return False


def _cierra_mas_tras_anadido(s: Simulacion, vs: list, lecturas: list) -> bool:
    """¿Tras un anadido, antes de la lectura conservada siguiente, cierran mas de lo que habia antes de el? (lo que hace
    que el bot no pueda saber si siguio o cerro entera y se reabrio a la misma entrada: A6)"""
    sec = s.sec
    for w in vs:
        for i, (te, tipo, *_r) in enumerate(w.eventos):
            antes = w.estado(te - 1, True)
            if tipo != "anade" or not antes:
                continue
            despues = [m for m in lecturas if sec.lectura(m) >= te]
            limite = sec.lectura(despues[0]) + 20_000 if despues else math.inf
            cerrado = sum(dq if tp == "parcial" else (w.estado(t2 - 1, True) or (0,))[0]
                          for t2, tp, dq, *_x in w.eventos[i + 1:] if t2 <= limite and tp in ("parcial", "cierra"))
            if cerrado > antes[0] + 1e-12:
                return True
    return False


def _limpia(s: Simulacion, v: Vida, pred: Vida | None, primera: int) -> float:
    """La «limpia» del bot antes de la primera lectura de v, de lo que el bot conserva: tras la puntuacion de la anterior
    (o sin registro), la penultima de dos lecturas seguidas sin la clave, menos 10 s."""
    sec, reg = s.sec, s.reg
    if pred is None:
        return sec.lectura(primera - 2) - 10_000 if primera >= 2 and reg.lecturas.get(primera - 2) is not None \
            and reg.lecturas.get(primera - 1) is not None else -math.inf
    ids = {e["posicion"] for e in s.base.evaluacion if e["tipo"] == "veredicto" and _vida_de(s, e["detalle"].get("posicion") or {}) is pred}
    emitida = next((e["ts"] for e in s.base.evaluacion if e["tipo"] == "cierre" and e["posicion"] in ids), None)
    if emitida is None:
        return -math.inf
    out = -math.inf
    for m in range(primera - 1):
        a, b = reg.lecturas.get(m), reg.lecturas.get(m + 1)
        if sec.lectura(m) > emitida and a is not None and b is not None and v.clave not in a and v.clave not in b:
            out = sec.lectura(m) - 10_000
    return out


def _ambigua_verdad(s: Simulacion, v: Vida, nota: str, vistas: dict, perdida: int | None) -> str | None:
    """None si el motivo de «sin puntuar» es verdad en esta secuencia con lo que el bot CONSERVA; si no, por que no."""
    sec = s.sec
    lecturas = sorted(m for m, lec in s.reg.lecturas.items() if lec is not None and m not in sec.vacias and m != perdida)
    misma = [w for w in sec.vidas if w.clave == v.clave]
    siguientes = [w for w in misma if w.inicio >= v.inicio]
    if nota.startswith("ambigua: A1"):
        # un anadido seguido de un cierre entre dos lecturas conservadas, en ella o en la que la siguio pegada
        for w in siguientes[:3]:
            for i, (te, tipo, *_r) in enumerate(w.eventos):
                if tipo != "anade":
                    continue
                despues = [m for m in lecturas if sec.lectura(m) >= te]
                limite = sec.lectura(despues[0]) if despues else math.inf
                if any(t2 <= limite + 20_000 and tp in ("parcial", "cierra") for t2, tp, *_x in w.eventos[i + 1:]):
                    return None
        return "no hubo un anadido seguido de un cierre entre dos lecturas conservadas en ella ni en la siguiente"
    if nota.startswith("ambigua: A2"):
        primera = min(vistas.get(v.n, [math.inf]))
        t1 = sec.lectura(primera) if primera != math.inf else v.fin
        ent = v.estado(t1, sec.u_parcial, sec.funding)
        ent = ent[1] if ent else None
        antes = [w for w in misma if w.fin <= v.inicio and vistas.get(w.n)]
        pred = max(antes, key=lambda w: w.fin) if antes else None
        desde = sec.lectura(max(vistas[pred.n])) - 20_000 if pred else -math.inf
        pred_anade = pred is not None and any(tp == "anade" and te > desde for te, tp, *_ in pred.eventos)
        limpia = _limpia(s, v, pred, primera) if primera != math.inf else -math.inf
        for w in misma:
            if w not in antes or (w is pred and pred_anade):
                for f in w.filas:
                    if not (desde < f["t"] <= t1 + abs(sec.desfase) + 20_000):
                        continue
                    misma_e = ent is not None and abs(f["e"] / ent - 1) <= 1e-9
                    if (not misma_e and f["c"] - 10_000 > limpia - 20_000) or (misma_e and f["c"] - 10_000 <= limpia + 20_000):
                        return None
        return "no hubo cierres a otra entrada tras la anterior y su «limpia», ni a la suya antes, hasta su primera lectura"
    if nota.startswith(("ambigua: A6", "ambigua: X")):
        if _s4_roto(s, siguientes[:3] + [w for w in misma if w.fin <= v.inicio][-1:]):
            return None
        if nota.startswith("ambigua: A6") and _cierra_mas_tras_anadido(s, siguientes[:3], lecturas):
            return None
        return "no hubo una reapertura a la misma entrada, una orden de varias ejecuciones ni cierres de mas tras un anadido"
    if nota.startswith("ambigua: A7"):
        return None if any(len(set(range(a, a + 2)) & sec.vacias) == 2 or sec.u_parcial is False for a in range(fin_m(sec))) \
            else "no hubo dos lecturas vacias seguidas"
    if nota.startswith("ambigua: S1"):  # una fila de ella, de la anterior o de las siguientes a menos de 30 s de una lectura
        cerca = [w for w in misma if w.fin <= v.inicio][-1:] + siguientes[:3]
        return None if any(abs(f["t"] - sec.lectura(m)) <= 30_000 or abs(f["c"] - sec.desfase - sec.lectura(m)) <= 30_000
                           for w in cerca for f in w.filas for m in lecturas) else "ninguna fila a menos de 30 s de una lectura"
    if nota.startswith("ambigua: A5"):
        return None if sec.migracion else "A5 sin un registro anterior (no hubo despliegue)"
    return "no es ninguno de los motivos declarados"


def fin_m(sec: Secuencia) -> int:
    return sec.minutos + sec.EXTRA


# ------------------------------------------------------------------------------------------- los casos FIJOS (validadores)
def _v(n: int, clave: str, eventos: list, desfase: int, retrasos: dict | None = None, off: int = 0) -> Vida:
    """Una vida a mano: eventos [(minuto con decimales, tipo, q, precio[, orden])]; retrasos {indice de la orden: ms}."""
    ev, k = [], 0
    for x in eventos:
        m, t, q, px = x[:4]
        orden = x[4] if len(x) > 4 else None
        if t in ("parcial", "cierra") and orden is None:
            k += 1
            orden = k
        ev.append((BASE + round(m * M), t, q, px, orden))
    v = Vida(n=n, clave=clave, lado=1 if clave.endswith(":Buy") else -1, eventos=ev)
    r = retrasos or {}
    return construye(v, desfase, lambda i: r.get(i, 0), off)


B, S_ = "BTCUSDT:Buy", "BTCUSDT:Sell"


def fijas() -> list[Secuencia]:
    """Los escenarios de los cuatro validadores, con sus horas (las lecturas son a los :20 de cada minuto) y la cifra que
    tienen que dar: «cifra» = puntuada con lo real; «ambigua»; «sin evaluar» (pegada a la anterior, declarado)."""
    out = []

    def sec(nombre, vidas, esperado, desfase=0, minutos=14, **kw):
        out.append(Secuencia(nombre=nombre, vidas=vidas, desfase=desfase, minutos=minutos, esperado=esperado, **kw))

    # R3 (validacion de R3, remate 4)
    sec("R10 parcial y anadido entre dos lecturas", [_v(1, B, [(0.9, "abre", 0.004, 110000), (1.5, "parcial", 0.002, 110450),
                                                           (1.7, "anade", 0.004, 110750), (2.6, "cierra", 0, 110300)], 0)], {1: "cifra"})
    for tarde in (0, 70_000):
        sec(f"R1 cerrada y reabierta a +0.14 % en el mismo minuto (cierre {tarde // 1000} s tarde)",
            [_v(1, B, [(0.9, "abre", 0.004, 110000), (1.6, "cierra", 0, 110300)], 0, {0: tarde}),
             _v(2, B, [(1.8, "abre", 0.004, 110150), (3.5, "cierra", 0, 109550)], 0)], {1: "cifra", 2: "cifra"})
    sec("R2 promediar y despues cerrar", [_v(1, B, [(0.9, "abre", 0.004, 110000), (1.5, "anade", 0.004, 110600),
                                                    (2.6, "cierra", 0, 110800)], 0)], {1: "cifra"})
    sec("R7 reinicio tras promediar con el bot caido", [_v(1, B, [(0.9, "abre", 0.004, 110000), (3.5, "anade", 0.004, 110600),
                                                                  (8.0, "cierra", 0, 110800)], 0)], {1: "cifra"}, caida=(2, 3, "tras_latido"))
    sec("R11 la base cae 3 min al abrir", [_v(1, B, [(1.0, "abre", 0.004, 110000), (10.0, "cierra", 0, 110300)], 0)], {1: "cifra"},
        base_caida=(BASE + round(0.9 * M), BASE + round(3.9 * M)))
    sec("R4b cobertura con entradas a 0.09 % y un cierre sin lado", [
        _v(1, B, [(0.9, "abre", 0.004, 110000), (1.6, "cierra", 0, 110010)], 0),
        _v(2, S_, [(0.9, "abre", 0.004, 110100), (1.7, "cierra", 0, 109600)], 0)], {1: "cifra", 2: "cifra"})
    # R4 (validacion de R4, remate 5)
    sec("R4.1 caida: la evaluada cierra y otra del mismo lado abre y cierra", [
        _v(1, B, [(0.9, "abre", 0.004, 110000), (3.0, "cierra", 0, 110300)], 0),
        _v(2, B, [(4.0, "abre", 0.004, 111000), (6.0, "cierra", 0, 110400)], 0)], {1: "cifra"}, caida=(2, 6, "tras_latido"))
    sec("R4.2 lista vacia una vez y el stop puesto", [_v(1, B, [(0.9, "abre", 0.004, 110000), (2.5, "stop", 0, 109400),
                                                                (6.0, "cierra", 0, 110300)], 0)], {1: "cifra"}, vacias={2})
    sec("R4.4 parcial fechado por Bybit 500 ms despues de la lectura que ya lo mostraba", [
        _v(1, B, [(0.9, "abre", 0.004, 110000), (2 + 19 / 60, "parcial", 0.002, 110450), (6.0, "cierra", 0, 110300)], 1500, {0: 30_000})],
        {1: "cifra"}, desfase=1500)
    # R5 (validacion de R5, remate 6)
    sec("R-A V2 anadido y parcial entre dos lecturas, despues el cierre final (R7: ambigua A6, cierra mas de lo que quedaba:"
        " lo mismo que cerrar entera tras un anadido sin ver y reabrir a la misma entrada)", [
        _v(1, B, [(0.9, "abre", 0.004, 110000), (1.4, "anade", 0.002, 110600), (1.6, "parcial", 0.005, 110420),
                  (3.5, "cierra", 0, 108200)], 0)], {1: "ambigua"})
    sec("R-A V1 parcial antes de la primera lectura (su fila a la hora de su updatedTime)", [
        _v(1, B, [(0.95, "abre", 0.006, 110000), (1.2, "parcial", 0.004, 110400), (3.0, "cierra", 0, 107800)], 0)], {1: "cifra"})
    sec("R-B caida entre el veredicto y el latido, y se pone el stop", [
        _v(1, B, [(0.9, "abre", 0.004, 110000), (2.5, "stop", 0, 109400), (8.0, "cierra", 0, 110300)], 0)], {1: "cifra"},
        caida=(1, 2, "antes_latido"))
    sec("R-C anadido visto <= 5 s antes del cierre total y reapertura en el mismo minuto", [
        _v(1, B, [(0.9, "abre", 0.004, 110000), (2.32, "anade", 0.004, 110600), (2.40, "cierra", 0, 110700)], 0),
        _v(2, B, [(2.6, "abre", 0.003, 111200), (6.0, "cierra", 0, 111000)], 0)], {1: "cifra", 2: "cifra"})
    sec("R-D closed-pnl tarda 90 s, anadido sin ver antes del cierre y se reabre (A1: declarado)", [
        _v(1, B, [(0.9, "abre", 0.004, 110000), (1.5, "anade", 0.004, 110600), (1.7, "cierra", 0, 110700)], 0, {0: 90_000}),
        _v(2, B, [(1.9, "abre", 0.003, 111300), (8.0, "cierra", 0, 111000)], 0)], {1: "ambigua", 2: "sin evaluar"})
    sec("V2b anadido y parcial en el mismo minuto, despues una lista vacia (R7: ambigua A6, como R-A V2)", [
        _v(1, B, [(0.9, "abre", 0.004, 110000), (1.4, "anade", 0.002, 110600), (1.6, "parcial", 0.005, 110500),
                  (6.0, "cierra", 0, 110300)], 0)], {1: "ambigua"}, vacias={2})
    sec("V7 la primera lectura ya ensena el tamano tras un parcial y su fila va 4 s por delante", [
        _v(1, B, [(0.95, "abre", 0.006, 110000), (1.30, "parcial", 0.003, 110500), (4.0, "cierra", 0, 109800)], 4000)], {1: "cifra"},
        desfase=4000)
    sec("sospecha: una rafaga y un /evalua cuando la lectura sale vacia", [
        _v(1, B, [(0.9, "abre", 0.004, 110000), (8.0, "cierra", 0, 110300)], 0)], {1: "cifra"}, vacias={3}, rafagas={3}, evaluas={3})
    # R6 (validacion de R6, este remate)
    sec("F1 TypeError: un registro anterior con otra vida abierta (despliegue R5 con cerrada sin puntuar y abierta)", [
        _v(1, B, [(0.9, "abre", 0.004, 110000), (2.5, "cierra", 0, 110300)], 0),
        _v(2, B, [(3.6, "abre", 0.003, 111000), (12.0, "cierra", 0, 110700)], 0)], {}, minutos=16,
        migracion={"minuto": 5, "tipo": "las dos", "estado": {"vidas": {B: {"id": f"{B}:{BASE + round(3.6 * M)}", "obs": [[BASE + 4 * M + 20_000, 0.003, 111000]]}},
                                                                   "cerradas": {f"{B}:{BASE + round(0.9 * M)}": [BASE + round(2.5 * M), 0.004, None]}},
                   "veredictos": [(BASE + M + 25_000, f"{B}:{BASE + round(0.9 * M)}", {"clave": B, "symbol": "BTCUSDT", "lado": 1, "cantidad": 0.004,
                                                                                        "entrada": 110000.0, "actualizada": BASE + round(0.9 * M)}),
                                  (BASE + 4 * M + 25_000, f"{B}:{BASE + round(3.6 * M)}", {"clave": B, "symbol": "BTCUSDT", "lado": 1, "cantidad": 0.003,
                                                                                           "entrada": 111000.0, "actualizada": BASE + round(3.6 * M)})],
                   "avisos": []})
    out[-1].esperado = {1: "cifra", 2: "cifra"}
    sec("F2 S1: closed-pnl 3 s DETRAS del updatedTime de la misma ejecucion", [
        _v(1, B, [(0.9, "abre", 0.004, 110000), (2.32, "parcial", 0.002, 110500), (5.0, "cierra", 0, 109900)], 0, off=3_000)],
        {1: "cifra"})
    sec("F3 S1: una orden de dos ejecuciones a caballo de una lectura (cierra entera)", [
        _v(1, B, [(0.9, "abre", 0.004, 110000), (2.31, "parcial", 0.002, 110500, 7), (2.36, "cierra", 0, 110500, 7)], 0)], {1: "ambigua"})
    sec("F4 S2: el cierre llega 12 min tarde y la clave se reabre (la segunda, sin evaluar: lo que la separa llega cuando ya"
        " cerro)", [
        _v(1, B, [(0.9, "abre", 0.004, 110000), (2.6, "cierra", 0, 110300)], 0, {0: 12 * M}),
        _v(2, B, [(2.8, "abre", 0.005, 111300), (9.0, "cierra", 0, 110700)], 0)], {1: "cifra", 2: "sin evaluar"})
    sec("F5 S3: dos listas vacias falsas seguidas", [_v(1, B, [(0.9, "abre", 0.004, 110000), (8.0, "cierra", 0, 110300)], 0)],
        {1: "cifra"}, vacias={3, 4})
    sec("F6 S4: anadido del mismo tamano a un tick y parcial del tamano de antes entre dos lecturas", [
        _v(1, B, [(0.9, "abre", 0.004, 110000), (1.4, "anade", 0.004, 110000.1), (1.6, "parcial", 0.004, 110500),
                  (5.0, "cierra", 0, 109900)], 0)], {1: "cifra"})
    sec("F7 S4: reabierta a la misma entrada y tamano en el mismo minuto (ambigua A6; la segunda es la misma para el bot)", [
        _v(1, B, [(0.9, "abre", 0.004, 110000), (1.6, "cierra", 0, 110300)], 0),
        _v(2, B, [(1.8, "abre", 0.004, 110000), (5.0, "cierra", 0, 109600)], 0)], {1: "ambigua", 2: "sin evaluar"})
    sec("F8 cobertura: largo y corto de BTC a la vez con un cierre sin lado", [
        _v(1, B, [(0.9, "abre", 0.004, 110000), (1.2, "anade", 0.002, 110300), (3.6, "cierra", 0, 110110)], 0),
        _v(2, S_, [(1.1, "abre", 0.003, 110050), (4.4, "cierra", 0, 109700)], 0)], {1: "cifra", 2: "cifra"})
    sec("F9 la base no apunta un cierre y el bot se reinicia (CERRADA una vez)", [
        _v(1, B, [(0.9, "abre", 0.004, 110000), (2.0, "cierra", 0, 110300)], 0)], {1: "cifra"},
        cierre_caida=(BASE + 30 * M, BASE + 45 * M), caida=(40, 2, "tras_latido"))
    sec("F10 A2 evitable: una vida invisible y despues dos lecturas sin la clave", [
        _v(1, B, [(0.9, "abre", 0.004, 110000), (2.6, "cierra", 0, 110300)], 0),
        _v(2, B, [(40.4, "abre", 0.002, 111000), (40.9, "cierra", 0, 111100)], 0),
        _v(3, B, [(44.5, "abre", 0.003, 110700), (49.0, "cierra", 0, 110200)], 0)], {1: "cifra", 3: "cifra"}, minutos=52)
    return out


# --------------------------------------------------------------------------------------------------- el lote, y suelto
def lote(sv, semilla: int, n: int, variante: str | None = None) -> dict:
    """n secuencias al azar con esa semilla (en el modelo, un 30 % simples) -> {fallos: [(nombre, [..])], cuentas}."""
    rng = random.Random(semilla * 1000 + (VARIANTES.index(variante) + 1 if variante else 0))
    out = {"fallos": [], "graves": [], "secuencias": n, "simples": 0, "cerradas": 0, "ambiguas": 0, "sin_puntuar": 0,
           "cerradas_simples": 0, "puntuadas_simples": 0, "a2_simples": 0, "mirado": {}}
    for i in range(n):
        simple = variante is None and rng.random() < 0.3
        sec = genera(rng, i, simple, variante)
        s = simula(sec, sv)
        f = comprueba(s)
        if f:
            out["fallos"].append((sec.nombre, f))
            g = [x for x in f if x.startswith(GRAVES)]
            if g:
                out["graves"].append((sec.nombre, g))
        for k, x in s.mirado.items():
            out["mirado"][k] = out["mirado"].get(k, 0) + x
        cierres = [e for e in s.base.evaluacion if e["tipo"] == "cierre"]
        out["simples"] += simple
        out["a2_simples"] += s.a2_simples
        if simple:
            out["cerradas_simples"] += len(cierres)
            out["puntuadas_simples"] += sum(e["pnl"] is not None for e in cierres)
        else:
            out["cerradas"] += len(cierres)
            out["ambiguas"] += sum(((e["detalle"] or {}).get("nota") or "").startswith("ambigua") for e in cierres)
            out["sin_puntuar"] += sum(e["pnl"] is None and not ((e["detalle"] or {}).get("nota") or "").startswith("ambigua") for e in cierres)
    return out


if __name__ == "__main__":
    sys.path.insert(0, ".")
    from app.bot import servicio
    sem = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    var = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "base" else None
    r = lote(servicio, sem, n, var)
    print(f"semilla {sem} {var or 'base'}: {n} secuencias, {len(r['fallos'])} con fallos, {len(r['graves'])} con graves ·"
          f" cierres {r['cerradas']} (ambiguos {r['ambiguas']}, sin puntuar {r['sin_puntuar']}) · simples {r['cerradas_simples']}"
          f" puntuados {r['puntuadas_simples']} a2 {r['a2_simples']}")
    for nombre, f in r["fallos"][:10]:
        print(" ", nombre, "·", " | ".join(f)[:400])
