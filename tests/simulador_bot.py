"""EL SIMULADOR de la vida de las posiciones (remate 6 de BOT-2). Solo la biblioteca estandar (random con SEMILLA fija).

Genera secuencias de VIDAS reales de posiciones -abrir, anadir, parcial, cerrar, reabrir en el mismo minuto, el mismo
simbolo y lado, y otro simbolo a la vez- y lo que el bot VE de ellas: position/list cada minuto (con la lista vacia
pasajera y el updatedTime que cambia al poner o quitar el stop), closed-pnl (con retraso de 0 a 6 min y el reloj de Bybit
desfasado hasta 8 s en los dos sentidos) y CAIDAS del bot (antes del tic, entre el tic y el veredicto, entre el veredicto y
el latido, despues del latido). Hace correr el Bot REAL (app/bot/servicio.py) con Bybit, Anthropic, Telegram y la base de
mentira, en memoria, sin red, y comprueba contra la verdad, en cada secuencia, las invariantes:
 I1 cada vida real se evalua (paga) como mucho una vez; y al menos una si es identificable (la anterior de su clave no
    tuvo un anadido sin ver antes de cerrar), el bot estuvo arriba y ella duro lo bastante (ESPERA + 1 min);
 I2 toda puntuacion que el bot emite es la REAL de esa vida (pnl y ACIERTO/FALLO); si no, «sin puntuar (ambigua: ...)»;
 I3 toda vida que el bot ve sin stop recibe el aviso sin_stop en esa lectura o en la siguiente;
 I4 nunca «CERRADA» de una vida que sigue abierta, y una sola por vida;
 I5 nada pagado (evaluacion, ESCALADO, /evalua) sobre una posicion que la ultima lectura del bot no ensena;
 I6 sin anadidos, parciales ni caidas, el 100 % de las vidas cerradas evaluadas se puntua;
 y una ambigua solo si su motivo es VERDAD en esa secuencia (A1: un anadido seguido de un cierre entre dos lecturas; A2:
 cierres a otra entrada antes de su primera lectura): ni el bot se escapa diciendo «ambigua» de lo que si sabe.
Ver tests/test_bot_simulador.py. Uso suelto: python tests/simulador_bot.py [semilla] [n]."""

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
ESPERA = 10 * M
FEE = 0.00055
IP = "138.186.31.141"


# ------------------------------------------------------------------------------------------------------------- la verdad
@dataclass
class Vida:
    n: int
    clave: str
    lado: int
    eventos: list = field(default_factory=list)  # (t, tipo, q, precio): abre, anade, parcial, cierra; stop: precio o None
    filas: list = field(default_factory=list)
    us: set = field(default_factory=set)  # updatedTime (reloj de Bybit) de cada cambio: identifica la vida en lo que ve el bot

    @property
    def inicio(self):
        return self.eventos[0][0]

    @property
    def fin(self):
        return self.eventos[-1][0] if self.eventos[-1][1] == "cierra" else math.inf

    @property
    def pnl(self):
        return sum(f["pnl"] for f in self.filas)

    def estado(self, t):
        """(tamano, entrada, updatedTime, stop) a la hora t (verdad), o None si no esta abierta."""
        if not (self.inicio <= t < self.fin):
            return None
        q = e = 0.0
        u = stop = None
        for te, tipo, dq, px in self.eventos:
            if te > t:
                break
            if tipo in ("abre", "anade"):
                e, q = (q * e + dq * px) / (q + dq), q + dq
            elif tipo == "parcial":
                q -= dq
            elif tipo == "stop":
                stop = px
            u = te
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
    rafagas: set = field(default_factory=set)  # minutos con una rafaga fresca (ESCALADO de la posicion de ese simbolo)
    evaluas: set = field(default_factory=set)  # minutos con un /evalua a mano
    simple: bool = False  # sin anadidos, parciales ni caidas (I6)

    EXTRA = 16

    def lectura(self, m: int) -> int:
        return BASE + m * M + 20_000

    def arriba(self, m: int) -> bool:
        """El bot lee en el minuto m. La caida pasa DENTRO del minuto c (segun su punto) y sigue abajo hasta c + largo."""
        if not self.caida:
            return True
        c, largo, punto = self.caida
        return not (c < m <= c + largo or (m == c and punto == "antes_tic"))


def _fila(vida: Vida, n: int, t: int, q: float, e: float, x: float, retraso: int, desfase: int) -> dict:
    pnl = vida.lado * (x - e) * q - FEE * (e + x) * q
    return {"orden": f"o{vida.n}-{n}", "t": t, "b": t + desfase, "q": q, "e": e, "x": x, "pnl": pnl, "visible": t + retraso,
            "symbol": vida.clave.split(":")[0]}


def construye(vida: Vida, desfase: int, retrasos) -> Vida:
    """Las filas de closed-pnl y los updatedTime de una vida a partir de sus eventos; retrasos: una funcion n -> ms."""
    q = e = 0.0
    for n, (t, tipo, dq, px) in enumerate(vida.eventos):
        if tipo in ("abre", "anade"):
            e, q = (q * e + dq * px) / (q + dq), q + dq
        elif tipo == "parcial":
            vida.filas.append(_fila(vida, n, t, dq, e, px, retrasos(n), desfase))
            q -= dq
        elif tipo == "cierra":
            vida.filas.append(_fila(vida, n, t, q, e, px, retrasos(n), desfase))
        vida.us.add(t + desfase)
    return vida


def genera(rng: random.Random, n: int, simple: bool) -> Secuencia:
    minutos = rng.randint(20, 32)
    desfase = rng.randint(-8000, 8000)
    simbolos = ["BTCUSDT"] + (["ETHUSDT"] if rng.random() < 0.5 else [])
    vidas, num = [], 0
    for sym in simbolos:
        lado = rng.choice((1, -1))
        clave = f"{sym}:{'Buy' if lado > 0 else 'Sell'}"
        paso = 0.001 if sym == "BTCUSDT" else 0.01
        precio = (110_000 if sym == "BTCUSDT" else 3_900) * (1 + rng.uniform(-0.02, 0.02))
        t = BASE + rng.randint(0, 4 * M)
        ultima_e = None
        while t < BASE + (minutos - 4) * M:
            num += 1
            v = Vida(n=num, clave=clave, lado=lado)
            p0 = precio * (1 + rng.uniform(-0.004, 0.004))
            while ultima_e and abs(p0 / ultima_e - 1) < 0.0005:  # S4: no reabre a la entrada de la que cerro
                p0 = precio * (1 + rng.uniform(-0.004, 0.004))
            q = paso * rng.randint(2, 10)
            v.eventos.append((t, "abre", q, p0))
            dur = rng.choice((rng.randint(20_000, 3 * M), rng.randint(3 * M, 14 * M), rng.randint(14 * M, 26 * M)))
            fin = min(t + dur, BASE + (minutos - 1) * M)
            if rng.random() < 0.5:
                v.eventos.append((t + rng.randint(1_000, 40_000), "stop", 0, p0 * (1 - 0.006 * lado)))
            e = p0
            for tm in sorted(rng.randint(t + 1_000, max(t + 2_000, fin - 1_000)) for _ in range(rng.randint(0, 5))):
                tipo = rng.choice(("stop",) if simple else ("anade", "parcial", "parcial", "anade", "stop"))
                if tipo == "anade":
                    px = e * (1 + rng.choice((-1, 1)) * rng.uniform(0.0008, 0.006))  # S4: mueve la entrada > 1 pb
                    dq = paso * rng.randint(1, 6)
                    e, q = (q * e + dq * px) / (q + dq), q + dq
                    v.eventos.append((tm, "anade", dq, px))
                elif tipo == "parcial" and q >= 2 * paso - 1e-12:
                    dq = paso * rng.randint(1, round(q / paso) - 1)
                    q = round(q - dq, 10)
                    v.eventos.append((tm, "parcial", dq, e * (1 + rng.uniform(-0.01, 0.01))))
                elif tipo == "stop":
                    v.eventos.append((tm, "stop", 0, None if rng.random() < 0.3 else e * (1 - 0.006 * lado)))
            v.eventos.sort(key=lambda x: x[0])
            v.eventos.append((max(fin, v.eventos[-1][0] + 500), "cierra", 0, e * (1 + rng.uniform(-0.01, 0.01))))
            retraso = lambda _n: rng.choice((0, 0, 0, 0, rng.randint(1, 59_000), rng.randint(M, 2 * M), rng.randint(2 * M, 6 * M)))  # noqa: E731
            vidas.append(construye(v, desfase, retraso))
            ultima_e, precio = e, precio * (1 + rng.uniform(-0.003, 0.003))
            t = v.fin + (rng.randint(500, 40_000) if rng.random() < 0.35 else rng.randint(M, 8 * M))  # reabrir en el mismo minuto
    vacias, m = set(), 1
    while m < minutos:
        if rng.random() < 0.05:
            vacias.add(m)
            m += 1  # S3: la lista vacia falsa dura una lectura
        m += 1
    caida = None
    if not simple and rng.random() < 0.3:
        caida = (rng.randint(2, minutos - 3), rng.randint(1, 8), rng.choice(("antes_tic", "antes_veredicto", "antes_latido", "tras_latido")))
    return Secuencia(nombre=f"azar-{n}", vidas=vidas, desfase=desfase, minutos=minutos, vacias=vacias, caida=caida,
                     rafagas={m for m in range(minutos) if rng.random() < 0.08},
                     evaluas={m for m in range(minutos) if rng.random() < 0.04}, simple=simple)


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
    """La base del bot en memoria: lo que el bot escribe y lee de bot_evento, bot_evaluacion, bot_operacion y bot_estado
    (las consultas de R5 y de R6). Una consulta que no conoce, la dice."""

    def __init__(self, reloj: list, caida=None):
        self.reloj, self.caida = reloj, caida
        self.evento, self.evaluacion, self.operacion, self.estado = [], [], {}, None

    def _mira(self):
        if self.caida and self.caida[0] <= self.reloj[0] < self.caida[1]:
            raise OSError("connection refused (postgresql 5432)")

    async def execute(self, sql, *a):
        self._mira()
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
            orden, sym, q, e, x, pnl, _lev, ms, _det = a
            if orden in self.operacion:
                return "INSERT 0 0"
            self.operacion[orden] = {"orden": orden, "symbol": sym, "q": q, "e": e, "x": x, "pnl": pnl, "ms": int(ms)}
        elif "INSERT INTO bot_estado" in sql:
            self.estado = (ahora, a[0])
        else:
            raise AssertionError(f"consulta no prevista: {sql[:120]}")
        return "INSERT 0 1"

    async def fetchval(self, sql, *a):
        self._mira()
        if "sum(coste_usd)" in sql:
            return 0.0
        if "tipo = 'parte'" in sql:
            return None
        raise AssertionError(f"consulta no prevista: {sql[:120]}")

    async def fetchrow(self, sql, *a):
        self._mira()
        if "FROM bot_estado" in sql:
            return Rec({"t": int(self.estado[0] // 1000), "estado": self.estado[1]}) if self.estado else None
        if "tipo = 'validacion'" in sql:
            return None
        raise AssertionError(f"consulta no prevista: {sql[:120]}")

    async def fetch(self, sql, *a):
        self._mira()
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
            visto = "detalle->>'visto'" in sql
            return [Rec({"k": (e["detalle"].get("visto") if visto else None) or e["detalle"].get("posicion"), "tipo": e["tipo"]})
                    for e in self.evento if e["tipo"] in ("stop", "liquidacion", "sin_stop")]
        if "SELECT orden FROM bot_operacion" in sql:
            return [Rec({"orden": o}) for o in self.operacion]
        if "FROM bot_operacion" in sql and "symbol = $1" in sql:  # R5: de_la_vida
            sym, ap, fin = a
            return [Rec({"orden": f["orden"], "pnl_usd": f["pnl"], "entrada": f["e"], "salida": f["x"], "cantidad": f["q"], "ms": f["ms"]})
                    for f in sorted(self.operacion.values(), key=lambda f: f["ms"]) if f["symbol"] == sym and ap <= f["ms"] <= fin]
        if "FROM bot_operacion" in sql:  # R6: las filas al arrancar
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


class Simulacion:
    def __init__(self, sec: Secuencia, sv):
        self.sec, self.sv = sec, sv
        self.reloj = [BASE]
        self.base = BaseFalsa(self.reloj, sec.base_caida)
        self.reg = Registro()
        self.minuto = 0
        self.a2_simples = 0
        self.por_u = {(v.clave, u): v for v in sec.vidas for u in v.us}

    # --- Bybit
    def lista(self) -> list:
        t, out, vistas = self.reloj[0], [], {}
        if self.minuto not in self.sec.vacias:
            for v in self.sec.vidas:
                e = v.estado(t)
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
        return [{"symbol": f["symbol"], "orderId": f["orden"], "side": "x", "closedSize": repr(f["q"]), "avgEntryPrice": repr(f["e"]),
                 "avgExitPrice": repr(f["x"]), "closedPnl": repr(f["pnl"]), "leverage": "50", "updatedTime": str(f["b"]),
                 "createdTime": str(f["b"])} for f in filas[:100]]

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

    async def corre(self):
        sec = self.sec
        bot = self.bot()
        await bot.carga()
        for m in range(sec.minutos + sec.EXTRA):
            self.minuto = m
            self.reloj[0] = sec.lectura(m)
            if not sec.arriba(m):
                bot = None
                self.reg.lecturas[m] = None
                continue
            if bot is None:  # vuelve de la caida
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
            except Exception as e:  # el bucle real (cada) lo anota y sigue; aqui se cuenta
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
            except Exception as e:
                self.reg.errores.append(f"{m} latido: {type(e).__name__} {e}")
            if punto == "tras_latido":
                bot = None


def simula(sec: Secuencia, sv) -> Simulacion:
    s = Simulacion(sec, sv)
    with mock.patch.object(sv.time, "time", lambda: s.reloj[0] / 1000):
        asyncio.run(s.corre())
    return s


# ------------------------------------------------------------------------------------------------------- las invariantes
def _vida_de(s: Simulacion, p: dict):
    return s.por_u.get((p.get("clave"), p.get("actualizada")))


def comprueba(s: Simulacion) -> list[str]:
    """-> las invariantes que caen en esta secuencia (vacia: todas pasan)."""
    sec, reg, base = s.sec, s.reg, s.base
    fallos: list = [f"el bot revento: {e[:160]}" for e in reg.errores]
    fin_lecturas = sec.minutos + sec.EXTRA
    pagadas: dict = {}
    for ms, tipo, p, ultima in reg.pagos:
        if p.get("clave") not in ultima:  # I5
            fallos.append(f"I5 {tipo} pagado sobre {p.get('clave')} que la ultima lectura no ensena (a las {(ms - BASE) / M:.1f} min)")
        if tipo == "evalua":
            v = _vida_de(s, p)
            pagadas[v.n if v else None] = pagadas.get(v.n if v else None, 0) + 1
    for n, k in pagadas.items():  # I1, cota alta
        if n is None:
            fallos.append(f"I1 {k} evaluacion(es) de algo que no es ninguna vida real")
        elif k > 1:
            fallos.append(f"I1 la vida {n} se evaluo {k} veces")
    veredictos: dict = {}  # el PRIMERO automatico de cada id: el que el bot puntua (un /evalua a mano no cuenta)
    for e in base.evaluacion:
        if e["tipo"] == "veredicto" and str(e["detalle"].get("motivo", "")).startswith("posicion nueva"):
            veredictos.setdefault(e["posicion"], e)
    for e in base.evaluacion:  # (el bot de antes de R6 tambien puntuaba la primera a mano)
        if e["tipo"] == "veredicto":
            veredictos.setdefault(e["posicion"], e)
    vistas: dict = {}  # vida -> minutos en que el bot la vio
    for m, lec in reg.lecturas.items():
        for v, _u, _stop in (lec or {}).values():
            vistas.setdefault(v.n, []).append(m)
    por_n = {v.n: v for v in sec.vidas}
    # I1, cota baja: identificable, bot arriba y vista lo bastante
    for v in sec.vidas:
        ms = sorted(vistas.get(v.n, []))
        if not ms:
            continue
        primera = ms[0]
        antes = [w for w in sec.vidas if w.clave == v.clave and w.fin <= v.inicio and vistas.get(w.n)]
        pred = max(antes, key=lambda w: w.fin) if antes else None
        if pred:
            ultima_p = max(vistas[pred.n])
            t_ult = sec.lectura(ultima_p)
            # sin la clave en dos lecturas seguidas entre medias: la anterior cerro seguro (S3)
            huecos = [m for m in range(ultima_p + 1, primera) if reg.lecturas.get(m) is not None and v.clave not in reg.lecturas[m]]
            hueco = any(m + 1 in huecos for m in huecos)
            if not hueco and any(tipo == "anade" and te > t_ult for te, tipo, _q, _px in pred.eventos):
                continue  # no identificable: un anadido sin ver antes de cerrar la anterior (A1)
            desde = ultima_p
        else:
            desde = 0
        hasta = primera + ESPERA // M + 1
        if hasta >= fin_lecturas or v.fin < sec.lectura(hasta) or not all(sec.arriba(m) for m in range(desde, hasta + 1)):
            continue
        if sec.caida and desde <= sec.caida[0] <= hasta:
            continue
        if pagadas.get(v.n, 0) != 1:
            fallos.append(f"I1 la vida {v.n} ({v.clave}) era identificable, se vio desde el minuto {primera} y se evaluo"
                          f" {pagadas.get(v.n, 0)} veces")
    # I3: el aviso sin_stop
    avisos = [(e["ts"], _vida_de(s, (e["detalle"].get("entradas") or {}).get("posicion") or {})) for e in base.evento if e["tipo"] == "sin_stop"]
    for v in sec.vidas:
        for m in sorted(vistas.get(v.n, [])):
            lec = reg.lecturas[m][v.clave]
            if lec[2] is None:  # sin stop
                siguiente = m + 1 < fin_lecturas and reg.lecturas.get(m + 1) is not None and sec.arriba(m + 1) \
                    and not (sec.caida and sec.caida[0] in (m, m + 1))
                if siguiente and not any(w is v and ts <= sec.lectura(m + 1) for ts, w in avisos):
                    fallos.append(f"I3 la vida {v.n} se vio sin stop en el minuto {m} y no tuvo aviso sin_stop")
                break
    # I2 e I4: cada cierre
    cierres: dict = {}
    for e in base.evaluacion:
        if e["tipo"] != "cierre":
            continue
        cierres[e["posicion"]] = cierres.get(e["posicion"], 0) + 1
        ver = veredictos.get(e["posicion"])
        v = _vida_de(s, ver["detalle"].get("posicion") or {}) if ver else None
        if v is None:
            fallos.append(f"I2 un cierre de {e['posicion']} sin vida real detras")
            continue
        if v.fin > e["ts"]:  # I4
            fallos.append(f"I4 CERRADA de la vida {v.n} a las {(e['ts'] - BASE) / M:.1f} min y cierra a las {(v.fin - BASE) / M:.1f}")
        nota = (e["detalle"] or {}).get("nota") or ""
        if e["pnl"] is not None:
            if abs(e["pnl"] - v.pnl) > 1e-6 * max(1.0, abs(v.pnl)):
                fallos.append(f"I2 la vida {v.n} puntuada {e['pnl']:+.4f} y lo real es {v.pnl:+.4f}")
            elif ver["veredicto"] != "NO EVALUABLE" and e["acierto"] != ((v.pnl > 0) == (ver["veredicto"] == "A FAVOR")):
                fallos.append(f"I2 la vida {v.n}: acierto {e['acierto']} con pnl {v.pnl:+.4f} y veredicto {ver['veredicto']}")
        if e["pnl"] is None:
            motivo = _ambigua_verdad(s, v, nota, vistas)
            if motivo:
                fallos.append(f"ninguna mas: la vida {v.n} sin puntuar por «{nota[:90]}» y {motivo}")
            elif sec.simple and nota.startswith("ambigua: A2"):
                s.a2_simples += 1  # tras una vida entera que el bot no vio: declarada, se cuenta aparte (I6)
            elif sec.simple:  # I6
                fallos.append(f"I6 la vida {v.n} cerrada sin puntuar en una secuencia simple: {nota[:100]}")
    for i, k in cierres.items():
        if k > 1:
            fallos.append(f"I4 {k} cierres de {i}")
    # I6: en una simple, toda vida evaluada que cerro con tiempo para puntuarse, puntuada
    if sec.simple:
        puntuadas = {_vida_de(s, veredictos[i]["detalle"].get("posicion") or {}).n for i in cierres if i in veredictos}  # o A2
        for n in pagadas:
            v = por_n.get(n)
            if v and v.fin + ESPERA + 2 * M < sec.lectura(fin_lecturas - 1) and n not in puntuadas:
                fallos.append(f"I6 la vida {n} se evaluo, cerro y no se puntuo")
    return fallos


def _ambigua_verdad(s: Simulacion, v: Vida, nota: str, vistas: dict) -> str | None:
    """None si el motivo de «sin puntuar» es verdad en esta secuencia; si no, por que no. Con lo que el bot CONSERVA: una
    caida entre el tic y el latido le hace perder la lectura de ese minuto (salvo la de una vida cuyo veredicto llego a la
    base)."""
    sec = s.sec
    perdida = None
    if sec.caida and sec.caida[2] in ("antes_veredicto", "antes_latido"):
        c = sec.caida[0]
        evaluadas = {w.n for w in (_vida_de(s, e["detalle"].get("posicion") or {}) for e in s.base.evaluacion  # EN ese minuto
                                   if e["tipo"] == "veredicto" and sec.lectura(c) <= e["ts"] < sec.lectura(c + 1)) if w}
        vistas = {n: [m for m in ms if m != c or (sec.caida[2] == "antes_latido" and n in evaluadas)] for n, ms in vistas.items()}
        vistas = {n: ms for n, ms in vistas.items() if ms}
        lec = s.reg.lecturas.get(c) or {}
        if not (sec.caida[2] == "antes_latido" and v.clave in lec and lec[v.clave][0].n in evaluadas):
            perdida = c
    lecturas = sorted(m for m, lec in s.reg.lecturas.items() if lec is not None and m not in sec.vacias and m != perdida)
    if nota.startswith("ambigua: A1"):
        # un anadido seguido de un cierre entre dos lecturas que el bot hizo de esa clave (de esa vida o de la que la siguio)
        for w in sec.vidas:
            if w.clave != v.clave or w.fin < v.inicio:
                continue
            for i, (te, tipo, _q, _px) in enumerate(w.eventos):
                if tipo != "anade":
                    continue
                despues = [m for m in lecturas if sec.lectura(m) >= te]
                limite = sec.lectura(despues[0]) if despues else math.inf
                if any(t2 <= limite + abs(sec.desfase) and tp in ("parcial", "cierra") for t2, tp, _a, _b in w.eventos[i + 1:]):
                    return None
        return "no hubo ningun anadido seguido de un cierre entre dos lecturas en esa clave"
    if nota.startswith("ambigua: A2"):
        # un cierre a otra entrada antes de su primera lectura, despues de la ultima lectura de la vida vista antes en su
        # clave: de una vida entera que el bot no vio, suyo antes de un anadido, o de esa anterior tras un anadido sin ver
        # (entonces sus filas no se pueden repartir entre las dos)
        primera = min(vistas.get(v.n, [math.inf]))
        t1 = sec.lectura(primera) if primera != math.inf else v.fin
        ent = v.estado(t1)[1] if v.estado(t1) else None
        antes = [w for w in sec.vidas if w.clave == v.clave and w.fin <= v.inicio and vistas.get(w.n)]
        pred = max(antes, key=lambda w: w.fin) if antes else None
        desde = sec.lectura(max(vistas[pred.n])) if pred else -math.inf
        pred_anade = pred is not None and any(tp == "anade" and te > desde for te, tp, _q, _px in pred.eventos)
        for w in sec.vidas:
            if w.clave == v.clave and w not in antes or (w is pred and pred_anade):
                for f in w.filas:
                    if desde < f["t"] <= t1 + abs(sec.desfase) and (ent is None or abs(f["e"] / ent - 1) > 1e-5):
                        return None
        return "no hubo ningun cierre a otra entrada entre la ultima lectura de la anterior y su primera lectura"
    if s.sec.caida or s.sec.base_caida:  # una caida puede dejar al bot sin lo que necesita: se acepta lo que diga
        return None
    return "no es ninguno de los motivos declarados"


# --------------------------------------------------------------------------------------------------- el lote, y suelto
def lote(sv, semilla: int, n: int) -> dict:
    """n secuencias al azar con esa semilla (un 30 % simples) -> {fallos: [(nombre, [..])], vidas, ambiguas, cerradas}."""
    rng = random.Random(semilla)
    out = {"fallos": [], "secuencias": n, "simples": 0, "cerradas": 0, "ambiguas": 0, "cerradas_simples": 0, "puntuadas_simples": 0}
    for i in range(n):
        simple = rng.random() < 0.3
        sec = genera(rng, i, simple)
        s = simula(sec, sv)
        f = comprueba(s)
        if f:
            out["fallos"].append((sec.nombre, f))
        cierres = [e for e in s.base.evaluacion if e["tipo"] == "cierre"]
        out["simples"] += simple
        out["a2_simples"] = out.get("a2_simples", 0) + s.a2_simples
        if simple:
            out["cerradas_simples"] += len(cierres)
            out["puntuadas_simples"] += sum(e["pnl"] is not None for e in cierres)
        else:
            out["cerradas"] += len(cierres)
            out["ambiguas"] += sum(((e["detalle"] or {}).get("nota") or "").startswith("ambigua") for e in cierres)
    return out


if __name__ == "__main__":
    sys.path.insert(0, ".")
    from app.bot import servicio
    sem, n = int(sys.argv[1]) if len(sys.argv) > 1 else 1, int(sys.argv[2]) if len(sys.argv) > 2 else 200
    r = lote(servicio, sem, n)
    print(f"semilla {sem}: {n} secuencias, {len(r['fallos'])} con fallos")
    for nombre, f in r["fallos"][:10]:
        print(" ", nombre, "·", " | ".join(f)[:400])
