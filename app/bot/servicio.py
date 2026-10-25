"""El bot de Telegram (BOT-2) de 140: el centinela (C1), la evaluacion de la operacion de Bybit (C2), la calculadora
(C3), las entradas APAGADAS (C4), las preguntas (C5) y las cuentas (C6); y, del remate 1, lo que deja VIGILARLO: el
parte diario, /estado, cada error con su causa nombrada en el journal (CAUSA=...), las entradas de cada alerta y de cada
llamada en las tablas, su historial cerrado de Bybit, la liquidacion validada contra Bybit y el informe semanal que
redacta Claude Max en 143. `python -m app.bot`; unidad deploy/140/coinalyze-bot.service (el interruptor que avisa si el
bot cae es otro proceso: app/bot/vigia.py).

Entorno (EnvironmentFile de systemd; el bot recibe las claves y no las imprime: limpia() las borra de cada mensaje y
de cada linea de log): ANTHROPIC_API_KEY, BYBIT_API_KEY, BYBIT_API_SECRET, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
API_INTERNAL_TOKEN (el de la API local: la API pide X-Internal-Token tambien desde 127.0.0.1). Opcionales:
BOT_TOPE_USD_DIA (3), BOT_IP_SALIDA (138.186.31.141), BOT_PG_DSN (rol coinalyze-ai por el socket, sin contrasena:
pg_hba de 140 tiene `local all all peer`), BOT_API (http://127.0.0.1:8000), BOT_INFORMES (/var/lib/coinalyze-bot/
informes, donde la tarea semanal de 143 deja el texto), y el ESFUERZO de cada ruta: BOT_EFFORT_ESCALA (low: manda la
latencia), BOT_EFFORT_PREGUNTA (medium), BOT_EFFORT_EVALUA (high); max no se acepta en tiempo real.

Datos: los sobres del laboratorio por la API local; las velas de 1 min y el registro (tablas bot_*), por la base.
Nada de app.db.create_pool: escribe en tablas de la app y crea particiones.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import pathlib
import re
import sys
import time
from datetime import UTC, datetime

import asyncpg
import httpx

from app.bot import bybit as bb
from app.bot import calc, calidad, llm
from app.bot import centinela as cen

log = logging.getLogger("app.bot")
SECRETOS = ("ANTHROPIC_API_KEY", "BYBIT_API_KEY", "BYBIT_API_SECRET", "TELEGRAM_BOT_TOKEN", "API_INTERNAL_TOKEN")
VEREDICTOS = ("A FAVOR", "EN CONTRA", "NO EVALUABLE")
PARTE_HORA_UTC = 13  # 07:00 en America/Mexico_City (UTC-6, la zona de 140 y 143): el parte, antes de que abra Europa
RUTAS = {"escala": "low", "pregunta": "medium", "evalua": "high"}  # de partida (Alejandro, 2026-10-24); se cambia por entorno
ESTABLE = """Eres el asistente de mesa de Alejandro para perpetuos lineales USDT de BTC, ETH y SOL en Bybit. Trabajas dentro
de un bot de Telegram que vive en su laboratorio (Coinalyze). En cada mensaje te llegan DATOS servidos por el laboratorio
(el sobre de contexto de un activo, el veredicto DECIDE de la mesa y, a veces, su posicion abierta y una alerta del
centinela) y una TAREA. Este bloque es fijo: las reglas, el reglamento y su forma de operar.

REGLAS QUE NO SE ROMPEN
1. Cada cifra que escribas sale de los DATOS de ese mensaje y lleva su fuente entre corchetes: la ruta de la clave en los
   datos, con puntos (por ejemplo [decide.bias.value], [funding_context.current], [oi_context.change_1h]). Una cifra
   sin fuente no se escribe.
2. Si un dato falta, esta vacio, viene marcado como no evaluable, es viejo o tiene baja confianza (data_confidence,
   data_quality), lo dices con esas palabras: «no evaluable» y por que. No lo rellenas con lo plausible.
3. NUNCA una probabilidad, un porcentaje de acierto, una esperanza ni un nivel de precio que no este en los datos. Si te
   piden «que probabilidad hay», contestas que el laboratorio no la mide.
4. NO das entradas. La regla acordada con Alejandro el 2026-10-20: el bot no da entradas mientras no haya una ventaja
   MEDIDA (una frecuencia de acierto con n >= 30 por encima del equilibrio, con comision). Hoy no hay ninguna: BOT-1 midio
   fuera de muestra las rafagas de BTC, ETH y SOL y ninguna fila tuvo ventaja. Si te piden una entrada, lo dices y
   ofreces la calculadora (/calc).
5. No ordenas nada: el bot solo lee (la clave de Bybit es de solo lectura). Cuando la tarea pide proponer un ajuste, es
   una PROPUESTA para que Alejandro decida.
6. Escribes en espanol, texto plano (sin markdown), corto: como mucho 8 lineas salvo que la tarea diga otra cosa.

SU FORMA DE OPERAR (para poner en contexto lo que veas)
- Opera a mano perpetuos lineales USDT en margen aislado. Por omision: 10 USD de margen a 50x (unos 500 USD de
  posicion), stop a -0.6 % de la entrada y objetivo a +2 %. Su perdida maxima por operacion es 3 USD.
- Comision taker de Bybit: 5.5 puntos basicos por lado. Con su forma, la perdida al stop con comision ronda 3.5 USD
  (pasa de su maximo) y la comision se come cerca del 6 % del objetivo; el equilibrio de acierto es
  (stop + comision) / (objetivo + stop).
- A 50x la liquidacion queda en torno a -1.7 % (BTC, ETH) o -1.5 % (SOL) de la entrada: el stop a -0.6 % salta antes.
- Mira el flujo de corto plazo: CVD, delta, operaciones grandes, liquidaciones, interes abierto, funding y el libro; y los
  marcos superiores, para no ir contra la estructura.

EL LABORATORIO (como leer los DATOS)
- DECIDE (mesa.decide) da un sesgo (decide.bias.value: LONG, SHORT o NO OPERAR), si es evaluable (decide.evaluable) y sus
  razones. NO OPERAR quiere decir que no sostiene un lado, no que el contrario gane.
- El sobre (ai_context) trae, segun la TAREA, solo los bloques que esa tarea usa: las matrices de delta y CVD por
  ventana, el libro (orderbook), la estructura y sus horizontes, el interes abierto (oi_context), el funding
  (funding_context), el mapa de liquidaciones, barreras y niveles de precio, absorcion y la calidad del dato
  (data_confidence, data_quality). Lo que no viene no lo tienes: «no evaluable». Cada bloque dice su ventana y su hora:
  si dos bloques no casan en hora, lo dices.
- El centinela del bot detecta RAFAGAS (z >= 4 en 5 minutos, con volumen y desequilibrio) y las clasifica en 1-3 minutos
  como CASCADA (sigue), BARRIDO (se da la vuelta) o SIN CLASE. Una alerta NO es una entrada: tras una rafaga no hay
  ventaja medida (BOT-1).

FORMATO SEGUN LA TAREA
- EVALUA: la primera linea es exactamente «VEREDICTO: A FAVOR», «VEREDICTO: EN CONTRA» o «VEREDICTO: NO EVALUABLE» (a
  favor o en contra de SU posicion, no del mercado); despues, hasta 6 razones «- ... [fuente]», empezando por DECIDE.
- ESCALA: 3-5 lineas: que pasa, que dicen los datos de la posicion (distancia al stop y a la liquidacion si vienen) y una
  PROPUESTA de ajuste del stop o del objetivo con la fuente del nivel, o «no propongo ajuste» y por que.
- PREGUNTA: contesta lo que pregunta con los datos y sus fuentes; si los datos no lo contestan, dilo."""
ESTABLE_SHA = hashlib.sha256(ESTABLE.encode()).hexdigest()[:12]
ENTRADAS = ("Entradas APAGADAS. La regla acordada el 10-20: el bot no da entradas mientras no haya una ventaja MEDIDA."
            " Las encenderia una frecuencia de acierto medida con n >= 30 por encima del equilibrio, con comision."
            " Hoy: ninguna (BOT-1: ninguna fila de BTC/ETH/SOL con ventaja medida tras una rafaga).")
AYUDA = ("/calc [btc|eth|sol] entrada [stop] [objetivo] [10$] [50x] [largo|corto] · /evalua [btc|eth|sol] · /entrada ·"
         " /estado · /gasto · /informe · o pregunta lo que quieras (como esta BTC, quien compra, hay muros cerca).")


def limpia(texto: str) -> str:
    for k in SECRETOS:
        v = os.environ.get(k, "")
        if len(v) >= 6:
            texto = texto.replace(v, "***")
    return texto


class Formato(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return limpia(super().format(record))


def _sin_nul(x):
    if isinstance(x, str):
        return x.replace("\x00", "")
    if isinstance(x, dict):
        return {k: _sin_nul(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_sin_nul(v) for v in x]
    return x


def js(x) -> str:
    """El JSON que el bot y el interruptor ESCRIBEN en la base. La de 140 es SQL_ASCII (medido el 2026-10-24): jsonb rechaza
    ahi los escapes \\u de todo lo que no es ASCII (tildes, «·», comillas angulares), que es lo que json.dumps pone por
    omision; los bytes UTF-8 tal cual (ensure_ascii=False) entran y se leen iguales. Y sin NUL, que no entra en ninguna."""
    s = json.dumps(x, ensure_ascii=False)
    return s if "\\u0000" not in s else json.dumps(_sin_nul(x), ensure_ascii=False)


def causa(e: BaseException) -> str:
    """El nombre de la causa de un error, para el journal y /estado."""
    if isinstance(e, (asyncpg.PostgresError, asyncpg.InterfaceError)):
        return "BASE"
    if isinstance(e, httpx.HTTPError):
        try:
            host = e.request.url.host
        except RuntimeError:
            host = ""
        return {"127.0.0.1": "API_140", "api.telegram.org": "TELEGRAM", "api.bybit.com": "BYBIT",
                "api.anthropic.com": "ANTHROPIC"}.get(host, "RED")
    if isinstance(e, OSError):
        return "BASE" if "postgresql" in str(e) or "5432" in str(e) else "SISTEMA"
    return type(e).__name__.upper()


def veredicto_decide(dec: dict, lado: int) -> str:
    """El veredicto determinista de DECIDE para la posicion: el que se registra al lado del de Opus."""
    d = dec.get("decide") or {}
    if (d.get("evaluable") or {}).get("value") is not True:
        return "NO EVALUABLE"
    sesgo = (d.get("bias") or {}).get("value")
    if sesgo not in ("LONG", "SHORT"):
        return "NO EVALUABLE"
    return "A FAVOR" if (sesgo == "LONG") == (lado > 0) else "EN CONTRA"


def lee_veredicto(texto: str | None) -> str | None:
    m = re.search(r"VEREDICTO:\s*(A FAVOR|EN CONTRA|NO EVALUABLE)", texto or "")
    return m.group(1) if m else None


def activo_de(texto: str, defecto: str = "BTCUSDT") -> str:
    m = re.search(r"\b(btc|eth|sol)\b", texto, re.I)
    return f"{m.group(1).upper()}USDT" if m else defecto


def args_calc(texto: str) -> dict:
    """«/calc sol 150 149.1 153 20$ 25x corto» -> argumentos de calc.calcula (sin tramos ni paso)."""
    a: dict = {"activo": activo_de(texto), "numeros": []}
    for t in texto.lower().split()[1:]:
        if t in ("btc", "eth", "sol"):
            continue
        if t in ("corto", "short"):
            a["corto"] = True
        elif t in ("largo", "long"):
            a["corto"] = False
        elif re.fullmatch(r"\d+(\.\d+)?x", t):
            a["apalancamiento"] = float(t[:-1])
        elif re.fullmatch(r"\d+(\.\d+)?\$", t):
            a["margen"] = float(t[:-1])
        elif re.fullmatch(r"\d+(\.\d+)?", t):
            a["numeros"].append(float(t))
        else:
            raise ValueError(f"no entiendo «{t}»: {AYUDA.split(' · ')[0]}")
    return a


# Los bloques del sobre que recibe cada ruta (remate 3, punto 15). La medida del operador en 140 (24 llamadas): ~78-80
# mil tokens de entrada por llamada, solo 1936 en cache, 0.33-0.45 USD por llamada sea cual sea el esfuerzo. Sale de las
# citas de esas 24 respuestas (x1-tmp/bot2/r3-bloques.py): decide, posicion, orderbook, price_barriers, oi_context,
# cvd_matrix, funding, positioning... Ninguna cito wyckoff (12768 tokens cl100k de 47926), field_disambiguation,
# feed_quality, la macro, la memoria de 2 anos, setup ni swing_score: no se mandan a ninguna.
COMUNES = ("symbol", "generated_at", "envelope_cut", "snapshot", "operator_read", "scalp", "data_confidence", "data_quality",
           "volatility", "local_alerts")
FLUJO = ("cvd_matrix", "delta_matrix", "orderbook", "passive_flow", "oi_context", "funding_context", "positioning",
         "liquidation_map", "liquidation_levels", "price_barriers", "reference_levels", "structure_horizons", "structure_detail",
         "market_structure", "trend_matrix", "divergences", "absorption", "basis")
BLOQUES = {
    "ESCALA": COMUNES + ("orderbook", "price_barriers", "reference_levels", "liquidation_map", "liquidation_levels", "market_structure"),
    "EVALUA": COMUNES + FLUJO,
    "PREGUNTA": COMUNES + FLUJO + ("recent_signals", "market_impact", "volume_profile", "cross_asset", "scalp_liquidations"),
}


def mensaje(tarea: str, *, dec: dict, ctx: dict, posicion: dict | None = None, alerta: str | None = None,
            pregunta: str | None = None) -> str:
    """El mensaje de una ruta (lo que va despues de la parte ESTABLE): el bot y app/bot/mide.py lo construyen igual. El
    sobre va recortado a los BLOQUES de la tarea."""
    partes = [f"TAREA: {tarea}"] + ([f"ALERTA: {alerta}"] if alerta else []) + ([f"PREGUNTA: {pregunta}"] if pregunta else [])
    partes += [f"POSICION: {json.dumps(posicion, ensure_ascii=False)}"] if posicion is not None else []
    sobre = {k: v for k, v in ctx.items() if k in BLOQUES.get(tarea, ctx)}
    return "\n".join(partes + [f"DATOS DECIDE: {json.dumps(dec, ensure_ascii=False)}",
                                f"DATOS SOBRE: {json.dumps(sobre, ensure_ascii=False, separators=(',', ':'))}"])


def esfuerzos(entorno: dict) -> tuple[dict, list[str]]:
    """El esfuerzo de cada ruta de tiempo real desde el entorno; un valor invalido o max -> el de partida, y se dice."""
    out, avisos = {}, []
    for ruta, defecto in RUTAS.items():
        v = (entorno.get(f"BOT_EFFORT_{ruta.upper()}") or defecto).strip().lower()
        if v not in llm.ESFUERZOS or v == "max":
            avisos.append(f"BOT_EFFORT_{ruta.upper()}={v!r} no vale en tiempo real: uso {defecto}")
            v = defecto
        out[ruta] = v
    return out, avisos


def ahora_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def semana_iso(t: datetime) -> str:
    a, s, _ = t.isocalendar()
    return f"{a}-W{s:02d}"


def edad(segundos: float | None) -> str:
    if segundos is None:
        return "sin dato"
    s = int(segundos)
    return f"{s} s" if s < 120 else f"{s // 60} min" if s < 7200 else f"{s // 3600} h"


def errores_vigentes(errores: dict, ahora: datetime) -> str:
    """Los errores que ensenan /estado y el parte: los sin resolver, y los resueltos hace menos de una hora con «resuelto
    HH:MMZ». Uno resuelto hace mas de una hora no se ensena (remate 3, punto 14)."""
    out = []
    for k, x in errores.items():
        r = x.get("resuelto")
        if r and (ahora - datetime.fromisoformat(r.replace("Z", "+00:00"))).total_seconds() > 3600:
            continue
        out.append(f"{k} ({x['ultima'][11:16]}Z: {x['texto'][:60]}{f', resuelto {r[11:16]}Z' if r else ''})")
    return ", ".join(out) or "ninguno"


class Telegram:
    def __init__(self, token: str, chat: str, http: httpx.AsyncClient):
        self.url, self.chat, self.http, self.offset, self.ajenos = f"https://api.telegram.org/bot{token}", str(chat), http, 0, 0

    async def manda(self, texto: str) -> bool:
        ok = True
        texto = limpia(texto)
        for i in range(0, max(len(texto), 1), 4000):  # Telegram corta a 4096
            r = await self.http.post(f"{self.url}/sendMessage", json={"chat_id": self.chat, "text": texto[i:i + 4000]}, timeout=20)
            if r.status_code != 200:
                log.warning("CAUSA=TELEGRAM_%s sendMessage no entrego%s", r.status_code,
                            " (token invalido)" if r.status_code == 401 else "")
                ok = False
        return ok

    async def recibe(self) -> list[str]:
        """Los textos nuevos del chat de Alejandro; los de cualquier otro chat se cuentan y se tiran sin leer."""
        r = await self.http.get(f"{self.url}/getUpdates", params={"offset": self.offset, "timeout": 50}, timeout=70)
        if r.status_code == 409:
            raise RuntimeError("Telegram 409: otro servicio lee este bot")
        if r.status_code == 401:
            raise RuntimeError("Telegram 401: el token no vale")
        if r.status_code != 200:
            raise RuntimeError(f"Telegram {r.status_code}: getUpdates no contesto bien")
        out = []
        for u in r.json().get("result") or []:
            self.offset = max(self.offset, u["update_id"] + 1)
            m = u.get("message") or {}
            if str((m.get("chat") or {}).get("id")) == self.chat and m.get("text"):
                out.append(m["text"])
            else:
                self.ajenos += 1
        return out


class Bot:
    def __init__(self, entorno: dict, db, http: httpx.AsyncClient):
        e = entorno
        self.e, self.db, self.http = e, db, http
        self.tope = float(e.get("BOT_TOPE_USD_DIA") or 3)
        self.ip = e.get("BOT_IP_SALIDA") or "138.186.31.141"
        self.api_base = e.get("BOT_API") or "http://127.0.0.1:8000"
        self.informes = e.get("BOT_INFORMES") or "/var/lib/coinalyze-bot/informes"
        self.tg = Telegram(e["TELEGRAM_BOT_TOKEN"], e["TELEGRAM_CHAT_ID"], http) if e.get("TELEGRAM_BOT_TOKEN") and e.get("TELEGRAM_CHAT_ID") else None
        self.bybit = bb.Bybit(e["BYBIT_API_KEY"], e["BYBIT_API_SECRET"], http) if e.get("BYBIT_API_KEY") and e.get("BYBIT_API_SECRET") else None
        self.esfuerzo, avisos = esfuerzos(e)
        self.candado = asyncio.Lock()
        self.vistos: set = set()
        self.pos: dict = {}  # id -> la posicion abierta, tal como se vio por ultima vez
        self.abiertas: dict = {}  # symbol:side -> id de la posicion abierta (remate 3, bug 1)
        self.cerradas: dict = {}  # id -> ms en que el bot la vio cerrada
        self.evaluadas: dict = {}  # id -> {veredicto: el PRIMERO, posicion}, sin cierre todavia
        self.evaluando: set = set()
        self.intentos: dict = {}
        self.avisados: set = set()
        self.validadas: set = set()
        self.tareas: set = set()  # lo que va fuera de los bucles (Opus): que el latido y las alertas no esperen
        self.clave_proxima = self.ops_leidas = 0.0
        self.clave_espera, self.clave_juzgada, self.tg_espera = 30.0, False, 0.0
        self.sin_registrar: dict = {}  # dia -> USD pagados que la base no apunto: cuentan igual para el tope
        self.desde_minuto = None  # el ultimo minuto que el centinela tenia visto (un apagon que cruza la medianoche)
        self.parte_hoy = None
        self.informes_enviados: set = set()
        self.estado = {
            "arranque": ahora_iso(), "version": os.path.basename(os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))),
            "telegram": "ok" if self.tg else "sin Telegram (faltan TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID)",
            "bybit": {"activo": False, "solo_lectura": None, "ip_ok": None, "ips": None, "ip_salida": self.ip,
                      "error": None if self.bybit else "sin BYBIT_API_KEY/BYBIT_API_SECRET"},
            "anthropic": {"clave": bool(e.get("ANTHROPIC_API_KEY")), "tope_usd": self.tope, "esfuerzo": self.esfuerzo},
            "datos": None, "api": None, "validacion": None, "informe": None, "errores": {},
        }
        for a in avisos:
            self.anota("CONFIGURACION", a)

    def anota(self, nombre: str, texto: str):
        """Un error con su causa nombrada: al journal (CAUSA=...) y a /estado y al parte (el ultimo de cada causa)."""
        texto = limpia(texto)[:300]
        log.warning("CAUSA=%s %s", nombre, texto)
        self.estado["errores"][nombre] = {"ultima": ahora_iso(), "texto": texto, "resuelto": None}

    def bien(self, *causas: str):
        """La fuente volvio: sus errores quedan «resueltos a las HH:MM» (remate 3, punto 14: el ConnectError del arranque
        salia en /estado como si fuera de ahora)."""
        for k, v in self.estado["errores"].items():
            if k.startswith(causas) and not v.get("resuelto"):
                v["resuelto"] = ahora_iso()

    def lanza(self, coro, nombre: str):
        """Fuera del bucle (remate 3, bug 6): una llamada a Opus no para el latido ni las alertas de los otros activos."""
        async def seguro():
            try:
                await coro
            except Exception as e:  # una tarea que cae se dice con su causa
                self.anota(causa(e), f"{nombre}: {type(e).__name__} {str(e)[:200]}")
        t = asyncio.create_task(seguro())
        self.tareas.add(t)
        t.add_done_callback(self.tareas.discard)
        return t

    # ---------- registro ----------
    async def evento(self, tipo: str, activo: str | None, minuto: int | None, enviada: bool, *, lado=None, clase=None, detalle=None):
        """Al registro. Si la base no lo apunta se dice (CAUSA=BASE) y no tumba el bucle: quien llama ya marco en memoria
        lo que aviso, y no se repite (remate 3, bug 4)."""
        try:
            await self.db.execute(
                "INSERT INTO bot_evento (tipo, symbol, minuto, lado, clase, enviada, detalle)"
                " VALUES ($1, $2, to_timestamp($3::bigint * 60), $4, $5, $6, $7::jsonb) ON CONFLICT DO NOTHING",
                tipo, activo, minuto, lado, clase, enviada, js(detalle or {}))
        except (OSError, asyncpg.PostgresError, asyncpg.InterfaceError) as e:
            self.anota("BASE", f"no registro el evento {tipo}: {type(e).__name__} {str(e)[:120]}")

    async def gastado_hoy(self) -> float:
        """Lo apuntado en bot_llamada hoy + lo pagado que la base no apunto (remate 3, bug 3). Si la base no contesta,
        esto falla y no se llama a Opus (cerrado por defecto)."""
        apuntado = float(await self.db.fetchval(
            "SELECT coalesce(sum(coste_usd), 0) FROM bot_llamada WHERE ts >= date_trunc('day', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'"))
        return apuntado + self.sin_registrar.get(datetime.now(UTC).date(), 0.0)

    async def carga(self):
        for t, a, m in await self.db.fetch(
                "SELECT tipo, symbol, (extract(epoch FROM minuto)::bigint / 60)::int FROM bot_evento"
                " WHERE tipo IN ('rafaga', 'clase') AND minuto >= now() - interval '2 days'"):
            self.vistos.add((t, a, m))
        # el PRIMER veredicto de cada posicion (el registrado antes del resultado; un /evalua a mano no lo pisa: bug 5)
        for i, v, p in await self.db.fetch(
                "SELECT DISTINCT ON (posicion) posicion, veredicto, detalle->'posicion' FROM bot_evaluacion e"
                " WHERE tipo = 'veredicto' AND ts >= now() - interval '30 days'"
                " AND NOT EXISTS (SELECT 1 FROM bot_evaluacion c WHERE c.tipo = 'cierre' AND c.posicion = e.posicion)"
                " ORDER BY posicion, ts"):
            self.evaluadas[i] = {"veredicto": v, "posicion": json.loads(p) if isinstance(p, str) else p}
        self.avisados = {(i, t) for i, t in await self.db.fetch(
            "SELECT detalle->>'posicion', tipo FROM bot_evento WHERE tipo IN ('stop', 'liquidacion', 'sin_stop')"
            " AND ts >= now() - interval '30 days'") if i}
        latido = await self.db.fetchval("SELECT extract(epoch FROM ts)::bigint FROM bot_estado WHERE clave = 'bot'")
        self.desde_minuto = int(latido) // 60 if latido else None
        self.parte_hoy = await self.db.fetchval("SELECT max((ts AT TIME ZONE 'UTC')::date) FROM bot_evento WHERE tipo = 'parte'")
        self.informes_enviados = {r[0] for r in await self.db.fetch(
            "SELECT detalle->>'semana' FROM bot_evento WHERE tipo = 'informe' AND ts >= now() - interval '60 days'")}
        v = await self.db.fetchrow("SELECT detalle, (ts AT TIME ZONE 'UTC')::date d FROM bot_evento WHERE tipo = 'validacion' ORDER BY ts DESC LIMIT 1")
        if v:
            d = json.loads(v["detalle"])
            self.estado["validacion"] = {"symbol": d["symbol"], "dia": str(v["d"]), "dif_pct": d["dif_pct"]}
        self.validadas = {r[0] for r in await self.db.fetch("SELECT detalle->>'posicion' FROM bot_evento WHERE tipo = 'validacion'")}

    async def latido(self):
        self.estado["anthropic"]["gastado_hoy_usd"] = round(await self.gastado_hoy(), 4)
        await self.db.execute(
            "INSERT INTO bot_estado (clave, ts, estado) VALUES ('bot', now(), $1::jsonb)"
            " ON CONFLICT (clave) DO UPDATE SET ts = excluded.ts, estado = excluded.estado", js(self.estado))
        self.bien("BASE")

    async def manda(self, texto: str) -> bool:
        if not self.tg:
            return False
        try:
            return await self.tg.manda(texto)
        except httpx.HTTPError as e:
            self.anota("TELEGRAM", f"no envia: {type(e).__name__}")
            return False

    # ---------- laboratorio y Opus ----------
    async def api(self, ruta: str) -> dict:
        try:
            r = await self.http.get(self.api_base + ruta, headers={"X-Internal-Token": self.e.get("API_INTERNAL_TOKEN", "")}, timeout=60)
        except httpx.HTTPError as e:
            self.estado["api"] = f"no contesta ({type(e).__name__}) a las {ahora_iso()}"
            self.anota("API_140", f"{ruta.split('?')[0]} no contesta: {type(e).__name__}")
            raise LookupError(f"no evaluable: la API del laboratorio no contesta ({type(e).__name__})") from e
        if r.status_code != 200:
            self.estado["api"] = f"HTTP {r.status_code} en {ruta.split('?')[0]} a las {ahora_iso()}"
            self.anota("API_140", f"HTTP {r.status_code} en {ruta.split('?')[0]}" + (" (token interno?)" if r.status_code == 403 else ""))
            raise LookupError(f"no evaluable: la API del laboratorio da HTTP {r.status_code} en {ruta.split('?')[0]}")
        self.estado["api"] = "ok"
        self.bien("API_140")
        return r.json()

    async def sobre(self, activo: str) -> tuple[dict, dict]:
        s = cen.SIMBOLO.get(activo)
        if not s:
            raise LookupError(f"no evaluable: el laboratorio no cubre {activo}")
        ctx = await self.api(f"/api/ai/context?symbol={s}")
        ctx.pop("interpretation_prompt", None)  # sus reglas no son las del bot (rol, planes): las del bot van en system
        return ctx, await self.api(f"/api/mesa/decide?symbol={s}&frame=scalp")

    async def opus(self, ruta: str, texto: str) -> dict:
        """Una llamada de la ruta (escala, pregunta, evalua) con su esfuerzo; se apunta con lo que se mando y contesto."""
        if not self.e.get("ANTHROPIC_API_KEY"):
            return {"texto": None, "error": "sin ANTHROPIC_API_KEY", "id": None}
        effort = self.esfuerzo[ruta]
        async with self.candado:
            r = await llm.llama(self.http, self.e["ANTHROPIC_API_KEY"], ESTABLE, texto, await self.gastado_hoy(), self.tope, effort)
            r["id"] = None
            if r["llamada"]:
                try:
                    r["id"] = str(await self.db.fetchval(
                        "INSERT INTO bot_llamada (motivo, modelo, effort, tokens_entrada, tokens_salida, coste_usd, tope_usd, estimado, detalle)"
                        " VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb) RETURNING id",
                        ruta, llm.MODELO, effort, r["entrada"], r["salida"], r["coste"], self.tope, r["estimado"],
                        js({"estable": ESTABLE_SHA, "entrada": texto, "respuesta": r["texto"], "error": r["error"],
                            "cache": r["cache"], "ms": r["ms"]})))
                except (OSError, asyncpg.PostgresError, asyncpg.InterfaceError) as e:
                    # lo pagado cuenta igual para el tope aunque la base no lo apunte (remate 3, bug 3)
                    hoy = datetime.now(UTC).date()
                    self.sin_registrar[hoy] = self.sin_registrar.get(hoy, 0.0) + r["coste"]
                    self.anota("BASE", f"no registro la llamada {ruta} ({r['coste']:.3f} USD, cuenta para el tope): {type(e).__name__}")
            if r["error"]:
                self.anota("TOPE" if r["error"].startswith("tope") else "ANTHROPIC", f"{ruta}: {r['error']}")
            elif r["texto"]:
                self.bien("ANTHROPIC", "TOPE")
            return r

    # ---------- C1 ----------
    async def tic_centinela(self):
        ahora = int(time.time() // 60)
        # desde el ultimo minuto visto (el latido de antes de un apagon) y como mucho ayer: un apagon que cruza la
        # medianoche no deja sin registrar las rafagas del dia anterior (remate 3, sospecha S4)
        desde = max(min(ahora - 15, self.desde_minuto or ahora - 15), (ahora // 1440 - 1) * 1440)
        dias = list(range(desde // 1440 * 1440, ahora // 1440 * 1440 + 1, 1440))
        filas: dict = {a: {} for a in cen.ACTIVOS}
        for a, m, *x in await self.db.fetch(cen.SQL_VELAS, list(cen.SIMBOLO.values()), dias[0] - cen.CALIENTA, ahora):
            filas[a][m] = tuple(x)
        if not all(filas.values()):
            self.estado["datos"] = f"sin velas de 1 min de {[a for a in cen.ACTIVOS if not filas[a]]}"
            return self.anota("DATOS", self.estado["datos"])
        hasta = min(max(f) for f in filas.values()) + 1
        self.estado["datos"] = {"ultima_vela": datetime.fromtimestamp((hasta - 1) * 60, UTC).strftime("%H:%MZ"),
                                "retraso_min": ahora - hasta}
        for dia in dias:
            for r in cen.rafagas_del_dia(filas, dia, hasta):
                await self.rafaga(r, ahora, filas)
        self.desde_minuto = ahora - 15
        self.bien("DATOS")

    async def rafaga(self, r: dict, ahora: int, filas: dict):
        a, m, u = r["activo"], r["minuto"], cen.UMBRALES
        tramo = lambda act, t0, t1: [[k, *filas[act][k]] for k in range(t0, t1 + 1) if k in filas[act]]  # noqa: E731
        fuente = {"fuente": "ohlcv 1min de 140", "columnas": "minuto, alto, bajo, cierre, compra, venta", "leidas": ahora_iso()}
        det = {k: round(r[k], 4) for k in ("z", "v", "imb")} | {"precio": r["precio"]}
        if ("rafaga", a, m) not in self.vistos:
            self.vistos.add(("rafaga", a, m))  # marcada ANTES de avisar: si la base no la apunta, no se repite (bug 4)
            fresca = ahora - m <= 10  # tras una caida se registra, pero no se manda tarde
            entradas = fuente | {"velas": {a: tramo(a, m - u.W - u.BASE, m)}}
            await self.evento("rafaga", a, m, fresca and await self.manda(cen.texto_rafaga(r)), lado=r["lado"],
                              detalle=det | {"entradas": entradas})
            p = next((p for p in self.pos.values() if p["symbol"] == a), None)
            if fresca and p:
                self.lanza(self.escala(p, cen.texto_rafaga(r)), f"escala {a}")
        if r["clase"] and ("clase", a, m) not in self.vistos:
            self.vistos.add(("clase", a, m))
            fresca = ahora - m <= 10 + u.DECIDE
            entradas = fuente | {"velas": {o: tramo(o, m - u.W - u.BASE, m + r["clase_min"]) for o in cen.ACTIVOS}}
            await self.evento("clase", a, m, fresca and await self.manda(cen.texto_clase(r)), lado=r["lado"], clase=r["clase"],
                              detalle=det | {"clase_min": r["clase_min"], "entradas": entradas})

    async def escala(self, p: dict, alerta: str):
        try:
            ctx, dec = await self.sobre(p["symbol"])
        except LookupError as e:
            return await self.manda(f"ESCALADO {p['symbol']}: {e}")
        r = await self.opus("escala", mensaje("ESCALA", alerta=alerta, posicion=p, dec=dec, ctx=ctx))
        await self.manda(f"ESCALADO {p['symbol']} (propuesta, no orden):\n{r['texto'] or r['error']}")

    # ---------- C2 y el historial de Bybit ----------
    async def lee_clave(self):
        """Los permisos de la clave, al arrancar, cada hora y tras un rechazo. Se avisa al CAMBIAR (y la primera vez).
        Un fallo PASAJERO (red, HTTP sin JSON, 10002, 10006, 10016) no juzga la clave: se dice la causa y se reintenta con
        espera corta y creciente (30 s, 60 s... hasta 15 min), sin tocar el ultimo veredicto (remate 3, bug 2)."""
        antes = self.estado["bybit"].get("activo")
        try:
            d = await self.bybit.get("/v5/user/query-api")
        except httpx.HTTPError as e:
            d = {"retCode": -1, "retMsg": f"red: {type(e).__name__}"}
        if bb.transitorio(d):
            espera, self.clave_espera = self.clave_espera, min(self.clave_espera * 2, 900.0)
            self.clave_proxima = time.time() + espera
            self.estado["bybit"]["error"] = f"no pude leer la clave ({bb.error(d)}); reintento en {int(espera)} s"
            return self.anota("BYBIT", self.estado["bybit"]["error"])
        primera, self.clave_juzgada = not self.clave_juzgada, True
        self.clave_proxima, self.clave_espera = time.time() + 3600, 30.0
        b = self.estado["bybit"] = bb.juzga_clave(d, self.ip) | {"leida": ahora_iso()}
        if b["activo"]:
            self.bien("BYBIT")
        else:
            self.anota("BYBIT_IP" if "IP" in str(b["error"]) else "BYBIT", f"Bybit apagado: {b['error']}")
        if b["activo"] != antes or (primera and not b["activo"]):
            txt = "Bybit ACTIVO: clave de solo lectura atada a la IP de 140" if b["activo"] else \
                f"Bybit APAGADO en el bot: {b['error']}. No leo posiciones hasta que se arregle."
            await self.evento("bybit", None, None, await self.manda(txt), detalle=b)

    def id_de(self, p: dict) -> str:
        """El id de una posicion que el bot no tenia abierta (remate 3, bug 1): el de su evaluacion pendiente si es la
        MISMA (mismo symbol:side y misma entrada, tras un reinicio), si no symbol:side:<updatedTime al verla abierta>."""
        for i, ev in sorted(self.evaluadas.items(), reverse=True):
            e = (ev.get("posicion") or {}).get("entrada")
            if i.startswith(p["clave"] + ":") and i not in self.abiertas.values() and e and p["entrada"] and abs(e / p["entrada"] - 1) <= 0.002:
                return i
        return f"{p['clave']}:{p.get('actualizada') or int(time.time() * 1000)}"

    async def reabierta(self, i: str, p: dict) -> bool:
        """¿La posicion i se cerro y se volvio a abrir entre dos lecturas? Si su entrada cambio Y closed-pnl trae un cierre
        de su lado con la entrada VIEJA despues de su apertura. ponytail: un cierre parcial seguido de otra entrada en el
        mismo minuto tambien lo parece; se dice al registrar."""
        vieja = (self.pos.get(i) or {}).get("entrada")
        if not vieja or not p["entrada"] or abs(vieja / p["entrada"] - 1) <= 0.002:
            return False
        await self.operaciones()
        return bool(await self.de_la_posicion(i, int(time.time() * 1000), self.pos[i]))

    async def tic_bybit(self):
        if self.bybit is None:
            return
        if time.time() >= self.clave_proxima:
            await self.lee_clave()
        if not self.estado["bybit"]["activo"]:
            return
        try:
            d = await self.bybit.get("/v5/position/list", category="linear", settleCoin="USDT")
        except httpx.HTTPError as e:
            return self.anota("BYBIT", f"position/list no contesta: {type(e).__name__}")
        if bb.error(d):
            self.estado["bybit"]["error"] = bb.error(d)
            self.anota("BYBIT_IP" if d.get("retCode") == 10010 else "BYBIT", f"position/list: {bb.error(d)}")
            if d.get("retCode") in (10003, 10010, 33004):
                self.clave_proxima = 0.0  # se vuelve a juzgar la clave en el proximo tic, y si cae se avisa
            return
        self.bien("BYBIT")
        vistas, ahora_ms = {p["clave"]: p for p in bb.posiciones(d)}, int(time.time() * 1000)
        for clave, i in list(self.abiertas.items()):
            if clave not in vistas or await self.reabierta(i, vistas[clave]):
                self.cerradas[i] = ahora_ms
                del self.abiertas[clave]
        for clave, p in vistas.items():
            i = self.abiertas.get(clave) or self.id_de(p)
            self.abiertas[clave], p["id"] = i, i
            self.pos[i] = p
            if i not in self.validadas:
                await self.valida(p)
            if i not in self.evaluadas and i not in self.evaluando and self.intentos.get(i, 0) < 3:
                self.evaluando.add(i)
                self.intentos[i] = self.intentos.get(i, 0) + 1  # una evaluacion que cae se reintenta, no sin limite (bug 3)
                self.lanza(self.evalua_una(p, "posicion nueva"), f"evalua {i}")
            for tipo, txt in cen.alertas_posicion(p):
                if (i, tipo) not in self.avisados:
                    self.avisados.add((i, tipo))
                    await self.evento(tipo, p["symbol"], int(time.time() // 60), await self.manda(f"{cen.LEYENDA.split(' · ')[0]} · {txt}"),
                                      detalle={"posicion": i, "texto": txt, "entradas": {"posicion": p, "leida": ahora_iso()}})
                    if tipo != "sin_stop":
                        self.lanza(self.escala(p, txt), f"escala {i}")
        self.pos = {i: p for i, p in self.pos.items() if i in self.abiertas.values()}
        pendientes = [i for i in self.evaluadas if i not in self.abiertas.values()]
        if pendientes or time.time() - self.ops_leidas > 900:
            await self.operaciones()
        for i in pendientes:
            await self.puntua(i)

    async def operaciones(self):
        """Las operaciones CERRADAS de Bybit a bot_operacion (una por orden), para BOT-3. ponytail: lo que closed-pnl
        devuelve por omision (la doc dice 7 dias; no contrastado), hasta 10 paginas; el lado no se deduce: va crudo."""
        self.ops_leidas, cursor, n = time.time(), None, 0
        for _ in range(10):
            d = await self.bybit.get("/v5/position/closed-pnl", category="linear", limit=100, **({"cursor": cursor} if cursor else {}))
            if bb.error(d):
                return self.anota("BYBIT", f"closed-pnl: {bb.error(d)}")
            res = d.get("result") or {}
            for c in res.get("list") or []:
                num = lambda k, c=c: float(c[k]) if c.get(k) not in (None, "") else None  # noqa: E731
                n += int((await self.db.execute(
                    "INSERT INTO bot_operacion (orden, symbol, cantidad, entrada, salida, pnl_usd, apalancamiento, cerrada, detalle)"
                    " VALUES ($1, $2, $3, $4, $5, $6, $7, to_timestamp($8::bigint / 1000.0), $9::jsonb) ON CONFLICT DO NOTHING",
                    str(c.get("orderId") or f"{c.get('symbol')}:{c.get('updatedTime')}"), c.get("symbol"), num("closedSize"),
                    num("avgEntryPrice"), num("avgExitPrice"), num("closedPnl"), num("leverage"),
                    int(c.get("updatedTime") or c.get("createdTime") or 0), js(c))).split()[-1])
            cursor = res.get("nextPageCursor")
            if not cursor:
                break
        if n:
            log.info("bot_operacion: %s cerradas nuevas", n)

    async def valida(self, p: dict):
        """La liquidacion de la formula contra la que da Bybit para una posicion real: se registra una vez por posicion."""
        if not p.get("liquidacion") or not p.get("entrada") or not p.get("cantidad") or not p.get("apalancamiento"):
            return
        try:
            t = (await self.bybit.get("/v5/market/risk-limit", category="linear", symbol=p["symbol"]))["result"]["list"]
            f, mmr = calc.liquidacion(p["entrada"], p["cantidad"], p["apalancamiento"], p["lado"], t)
        except (KeyError, TypeError, ValueError, httpx.HTTPError) as e:
            return self.anota("BYBIT", f"risk-limit para validar la liquidacion: {type(e).__name__}")
        dif = abs(f - p["liquidacion"]) / p["entrada"] * 100
        self.estado["validacion"] = {"symbol": p["symbol"], "dia": datetime.now(UTC).strftime("%Y-%m-%d"), "dif_pct": round(dif, 4)}
        self.validadas.add(p["id"])
        await self.evento("validacion", p["symbol"], int(time.time() // 60), False,
                          detalle={"posicion": p["id"], "symbol": p["symbol"], "bybit": p["liquidacion"], "formula": f,
                                   "mmr": mmr, "dif_pct": round(dif, 4)})

    async def evalua(self, p: dict, motivo: str):
        v_dec, dec, texto, liq, horas, llamada = "NO EVALUABLE", {}, None, "", {"posicion": ahora_iso()}, None
        try:
            ctx, dec = await self.sobre(p["symbol"])
            horas |= {"sobre": ctx.get("generated_at"), "decide": dec.get("generated_at")}
            v_dec = veredicto_decide(dec, p["lado"])
            r = await self.opus("evalua", mensaje("EVALUA", posicion=p, dec=dec, ctx=ctx))
            texto, llamada = r["texto"] or r["error"], r["id"]
            v, fuente = (lee_veredicto(r["texto"]), "opus") if r["texto"] else (v_dec, f"DECIDE ({r['error']})")
        except LookupError as e:
            v, fuente, texto = "NO EVALUABLE", str(e), str(e)
        if v is None:
            v, fuente = "NO EVALUABLE", "opus sin veredicto legible"
        if p.get("liquidacion"):
            liq = f"\nliquidacion Bybit {p['liquidacion']:g} · formula: {calc.nota_validacion(self.estado['validacion'])}"
        # en memoria ANTES de registrar (si la base falla no se vuelve a evaluar ni a pagar cada minuto: bug 3), y solo el
        # PRIMER veredicto: es el que se puntua (un /evalua a mano se registra, pero no lo pisa: bug 5)
        self.evaluadas.setdefault(p["id"], {"veredicto": v, "posicion": p})
        self.evaluando.discard(p["id"])
        try:
            await self.db.execute(
                "INSERT INTO bot_evaluacion (tipo, posicion, veredicto, veredicto_decide, detalle)"
                " VALUES ('veredicto', $1, $2, $3, $4::jsonb)",
                p["id"], v, v_dec, js({"motivo": motivo, "fuente": fuente, "posicion": p, "horas": horas,
                                       "llamada": llamada, "decide": dec}))
        except (OSError, asyncpg.PostgresError, asyncpg.InterfaceError) as e:
            self.anota("BASE", f"no registro la evaluacion de {p['id']}: {type(e).__name__}")
        sesgo = ((dec.get("decide") or {}).get("bias") or {}).get("value")
        await self.manda(f"EVALUACION {p['symbol']} {'LARGO' if p['lado'] > 0 else 'CORTO'} ({motivo})\nVEREDICTO: {v} ({fuente})"
                         f"\nDECIDE: {sesgo} -> {v_dec}{liq}\n{texto or ''}")

    async def evalua_una(self, p: dict, motivo: str):
        try:
            await self.evalua(p, motivo)
        finally:
            self.evaluando.discard(p["id"])

    async def de_la_posicion(self, i: str, cierre_ms: int, p: dict | None) -> list:
        """Las operaciones cerradas (bot_operacion) de ESA posicion: su simbolo, cerradas entre su apertura y su cierre
        visto (+5 min), con su misma entrada (closed-pnl da la entrada media de la posicion) y del lado de la posicion
        segun la aritmetica de cada fila (bybit.lado_cierre). Antes: todas las del simbolo desde su PRIMERA posicion."""
        activo, _, apertura = i.split(":")
        filas = await self.db.fetch(
            "SELECT orden, pnl_usd, entrada, salida, cantidad FROM bot_operacion WHERE symbol = $1"
            " AND cerrada >= to_timestamp($2::bigint / 1000.0) AND cerrada <= to_timestamp($3::bigint / 1000.0)",
            activo, int(apertura), cierre_ms + 300_000)
        e, lado = (p or {}).get("entrada"), (p or {}).get("lado")
        return [f for f in filas
                if (not e or not f["entrada"] or abs(f["entrada"] / e - 1) <= 0.002)
                and bb.lado_cierre(f["entrada"], f["salida"], f["cantidad"], f["pnl_usd"]) in (None, lado)]

    async def puntua(self, i: str):
        """La posicion i ya no esta abierta: su pnl, de SUS operaciones; si aun no estan, en el proximo tic, y si en 2 h
        no aparecen, se cierra sin puntuar y se dice."""
        ev = self.evaluadas[i]
        cierre = self.cerradas.get(i) or int(time.time() * 1000)
        self.cerradas.setdefault(i, cierre)
        filas = await self.de_la_posicion(i, cierre, ev.get("posicion"))
        if not filas and time.time() * 1000 - cierre < 2 * 3600 * 1000:
            return
        pnl = sum(float(f["pnl_usd"] or 0) for f in filas) if filas else None
        v = ev["veredicto"]
        del self.evaluadas[i]
        self.cerradas.pop(i, None)
        acierto = None if v == "NO EVALUABLE" or pnl is None else (pnl > 0) == (v == "A FAVOR")
        try:
            await self.db.execute(
                "INSERT INTO bot_evaluacion (tipo, posicion, veredicto, pnl_usd, acierto, detalle) VALUES ('cierre', $1, $2, $3, $4, $5::jsonb)",
                i, v, pnl, acierto, js({"ordenes": [f["orden"] for f in filas], "nota": None if filas else "sin operaciones suyas en closed-pnl en 2 h"}))
        except (OSError, asyncpg.PostgresError, asyncpg.InterfaceError) as e:
            self.anota("BASE", f"no registro el cierre de {i}: {type(e).__name__}")
        activo = i.split(":")[0]
        resultado = "sin operaciones en closed-pnl: sin puntuar" if pnl is None else f"{pnl:+.2f} USD"
        await self.manda(f"CERRADA {activo}: {resultado} · el veredicto era {v} -> {'sin puntuar' if acierto is None else ('ACIERTO' if acierto else 'FALLO')}")

    # ---------- C3, C5 ----------
    async def calcula(self, texto: str) -> str:
        a = args_calc(texto)
        s = a.pop("activo")
        n = a.pop("numeros")
        pub = bb.Bybit("", "", self.http)
        t = (await pub.get("/v5/market/risk-limit", category="linear", symbol=s))["result"]["list"]
        ins = (await pub.get("/v5/market/instruments-info", category="linear", symbol=s))["result"]["list"][0]
        tk = (await pub.get("/v5/market/tickers", category="linear", symbol=s))["result"]["list"][0]
        entrada = n[0] if n else float(tk["markPrice"])
        r = calc.calcula(entrada, *n[1:3], paso=ins["lotSizeFilter"]["qtyStep"], tramos=t,
                         funding=float(tk["fundingRate"]) if tk.get("fundingRate") else None,
                         funding_h=float(ins.get("fundingInterval") or 480) / 60, **a)
        return calc.texto(r, s, self.estado["validacion"]) + ("" if n else f"\n(entrada = marca actual {entrada:g})")

    async def pregunta(self, texto: str) -> str:
        activo = activo_de(texto, next((p["symbol"] for p in self.pos.values()), "BTCUSDT"))
        ctx, dec = await self.sobre(activo)
        r = await self.opus("pregunta", mensaje("PREGUNTA", pregunta=texto, dec=dec, ctx=ctx))
        return r["texto"] or f"no contesto: {r['error']}"

    # ---------- C6: la salud, el parte, el gasto y el informe ----------
    async def salud(self) -> dict:
        """Lo que dicen /estado y el parte: cada fuente con su edad, Bybit, Telegram, gasto, alertas, informe, errores."""
        s: dict = {"latido": ahora_iso(), "arranque": self.estado["arranque"], "datos": self.estado["datos"],
                   "bybit": self.estado["bybit"], "telegram": self.estado["telegram"], "validacion": self.estado["validacion"],
                   "errores": self.estado["errores"], "gasto_hoy": await self.gastado_hoy(), "tope": self.tope}
        try:
            h = await self.api("/api/healthz")
            s["fuentes"] = {x["service"]: x.get("lag_seconds") for x in h.get("services") or []
                            if x.get("service") in ("ingest:ohlcv_1m", "ingest:metrics_5m", "ingest:liquidations_history", "scalp", "ws")}
            s["fuentes"] |= {x["service"]: x.get("lag_seconds") for x in h.get("informative_services") or []}
        except LookupError as e:
            s["fuentes"] = str(e)
        s["gasto_ayer"] = float(await self.db.fetchval(
            "SELECT coalesce(sum(coste_usd), 0) FROM bot_llamada WHERE (ts AT TIME ZONE 'UTC')::date = (now() AT TIME ZONE 'UTC')::date - 1"))
        s["alertas_24h"] = await self.alertas_24h()
        u = await self.db.fetchrow("SELECT symbol, minuto, lado FROM bot_evento WHERE tipo = 'rafaga' ORDER BY minuto DESC LIMIT 1")
        s["ultima_alerta"] = f"{u['symbol'][:3]} {'alcista' if u['lado'] > 0 else 'bajista'} {u['minuto']:%m-%d %H:%MZ}" if u else "ninguna"
        s["informe"] = self.estado_informe()
        return s

    async def alertas_24h(self) -> dict:
        """Las rafagas de las ultimas 24 h por la clase que les dio el bot (SIN CLASIFICAR si aun no tienen)."""
        return {r["c"]: r["n"] for r in await self.db.fetch(
            "SELECT coalesce(c.clase, 'SIN CLASIFICAR') c, count(*) n FROM bot_evento r LEFT JOIN bot_evento c"
            " ON c.tipo = 'clase' AND c.symbol = r.symbol AND c.minuto = r.minuto"
            " WHERE r.tipo = 'rafaga' AND r.minuto >= now() - interval '24 hours' GROUP BY 1 ORDER BY 1")}

    def estado_informe(self) -> str:
        sem = semana_iso(datetime.now(UTC))
        if sem in self.informes_enviados:
            return f"el de {sem} llego y se envio"
        falla = os.path.join(self.informes, f"{sem}.falla")
        if os.path.exists(falla):
            return f"el de {sem} NO llego: {pathlib.Path(falla).read_text(encoding='utf-8').strip()[:200]}"
        return f"el de {sem} todavia no" + (f" (ultimo enviado: {max(self.informes_enviados)})" if self.informes_enviados else "")

    def texto_salud(self, s: dict, titulo: str) -> str:
        b, v, f = s["bybit"], s["validacion"], s["fuentes"]
        fuentes = ", ".join(f"{k} {edad(x)}" for k, x in f.items()) if isinstance(f, dict) else f
        datos = s["datos"]
        velas = f"velas 1 min: la ultima {datos['ultima_vela']} ({datos['retraso_min']} min de retraso)" if isinstance(datos, dict) else f"velas 1 min: {datos}"
        ips = f"IPs de la clave en Bybit: {', '.join(map(str, b['ips'])) if b.get('ips') else 'sin dato'} · 140 sale por {b.get('ip_salida', self.ip)}"
        bybit = (f"solo lectura e IP ok (leida {str(b.get('leida', '?'))[11:16]}Z) · {ips}" if b["activo"] else f"APAGADO: {b['error']} · {ips}")
        al = s["alertas_24h"]
        errores = errores_vigentes(s["errores"], datetime.now(UTC))
        return "\n".join([
            f"{titulo} · vivo desde {s['arranque']} (latido {s['latido'][11:16]}Z)",
            f"datos: {velas}; {fuentes}",
            f"Bybit: {bybit}",
            f"liquidacion de la calculadora: {calc.nota_validacion(v)}",
            f"alertas 24 h: {sum(al.values())} ({', '.join(f'{k} {n}' for k, n in al.items()) or 'ninguna'}) · ultima: {s['ultima_alerta']}",
            f"gasto API: hoy {s['gasto_hoy']:.2f} de {s['tope']:.2f} USD · ayer {s['gasto_ayer']:.2f} · esfuerzo {self.esfuerzo}",
            f"Telegram: {s['telegram']} · informe semanal: {s['informe']}",
            f"errores: {errores}",
        ])

    async def gasto(self) -> str:
        filas = await self.db.fetch(
            "SELECT (ts AT TIME ZONE 'UTC')::date d, motivo, effort, count(*) n, sum(tokens_entrada) e, sum(tokens_salida) s,"
            " sum(coste_usd) c FROM bot_llamada WHERE ts >= now() - interval '7 days' GROUP BY 1, 2, 3 ORDER BY 1, 2")
        dias = "\n".join(f"{f['d']} {f['motivo']}/{f['effort']}: {f['n']} llamadas, {f['e']} + {f['s']} tokens, {f['c']:.2f} USD" for f in filas)
        return f"gasto de hoy {await self.gastado_hoy():.2f} de {self.tope:.2f} USD (tope)\n{dias or 'sin llamadas en 7 dias'}"

    async def cifras_semana(self, hasta: int | None = None) -> dict:
        """Las cifras de calidad de los 7 dias anteriores a `hasta` (minuto; por omision ahora), desde la base."""
        hasta = hasta or int(time.time() // 60)
        desde = hasta - 7 * 1440
        alertas = [dict(r) for r in await self.db.fetch(
            "SELECT r.symbol activo, (extract(epoch FROM r.minuto)::bigint / 60)::int minuto, r.lado, c.clase FROM bot_evento r"
            " LEFT JOIN bot_evento c ON c.tipo = 'clase' AND c.symbol = r.symbol AND c.minuto = r.minuto"
            " WHERE r.tipo = 'rafaga' AND r.minuto >= to_timestamp($1::bigint * 60) AND r.minuto < to_timestamp($2::bigint * 60)", desde, hasta)]
        velas: dict = {a: {} for a in cen.ACTIVOS}
        for a, m, hi, lo, c, _, _ in await self.db.fetch(cen.SQL_VELAS, list(cen.SIMBOLO.values()), desde, hasta + calidad.DIA + 1):
            velas[a][m] = (hi, lo, c)
        ev = [dict(r) for r in await self.db.fetch(
            "SELECT veredicto, acierto, pnl_usd FROM bot_evaluacion WHERE tipo = 'cierre' AND ts >= to_timestamp($1::bigint * 60)", desde)]
        ops = [dict(r) for r in await self.db.fetch("SELECT pnl_usd FROM bot_operacion WHERE cerrada >= to_timestamp($1::bigint * 60)", desde)]
        ll = [dict(r) for r in await self.db.fetch(
            "SELECT (ts AT TIME ZONE 'UTC')::date dia, coste_usd, tope_usd FROM bot_llamada WHERE ts >= to_timestamp($1::bigint * 60)", desde)]
        partes = [str(r[0]) for r in await self.db.fetch(
            "SELECT DISTINCT (ts AT TIME ZONE 'UTC')::date FROM bot_evento WHERE tipo = 'parte' AND ts >= to_timestamp($1::bigint * 60)", desde)]
        return calidad.resumen(alertas, velas, ev, ops, ll, partes, desde, hasta)

    async def informe(self) -> str:
        return "INFORME (cifras, al momento)\n" + calidad.texto(await self.cifras_semana()) + "\n" + await self.gasto()

    async def tic_parte(self):
        n = datetime.now(UTC)
        if n.hour < PARTE_HORA_UTC or self.parte_hoy == n.date():
            return
        self.parte_hoy = n.date()  # marcado ANTES de avisar: si la base no lo apunta, no se repite cada minuto (bug 4)
        s = await self.salud()
        texto = self.texto_salud(s, f"PARTE {n:%Y-%m-%d}")
        enviada = await self.manda(texto)
        await self.evento("parte", None, None, enviada, detalle={"texto": texto, "salud": s})

    async def tic_informe(self):
        """El informe semanal que redacta Claude Max en 143 (tools/bot/semanal.py) y deja en BOT_INFORMES/<semana>.txt."""
        sem = semana_iso(datetime.now(UTC))
        f = os.path.join(self.informes, f"{sem}.txt")
        if sem in self.informes_enviados or not os.path.exists(f):
            return
        self.informes_enviados.add(sem)  # marcado ANTES de avisar (bug 4)
        texto = pathlib.Path(f).read_text(encoding="utf-8").strip()
        enviada = await self.manda(f"INFORME SEMANAL {sem}\n{texto}")
        await self.evento("informe", None, None, enviada, detalle={"semana": sem, "texto": texto, "fichero": f})

    # ---------- las ordenes ----------
    async def atiende(self, texto: str) -> str:
        orden = texto.strip().split()[0].lower() if texto.strip() else ""
        try:
            if orden in ("/calc", "calc"):
                return await self.calcula(texto)
            if orden in ("/evalua", "evalua"):
                if not self.estado["bybit"]["activo"]:
                    return f"no evaluable: Bybit apagado en el bot ({self.estado['bybit']['error']})"
                ps = [p for p in self.pos.values() if p["symbol"] == activo_de(texto, p["symbol"])]
                for p in ps:
                    await self.evalua(p, "a peticion")
                return "" if ps else "no hay posicion abierta que evaluar"
            if orden in ("/entrada", "/entradas", "entrada"):
                return ENTRADAS
            if orden == "/estado":
                return self.texto_salud(await self.salud(), "ESTADO")
            if orden == "/gasto":
                return await self.gasto()
            if orden == "/informe":
                return await self.informe()
            if orden in ("/start", "/ayuda", "/help"):
                return AYUDA
            return await self.pregunta(texto)
        except (LookupError, ValueError, KeyError, httpx.HTTPError) as e:
            return f"no evaluable: {limpia(str(e))[:300]}"

    # ---------- bucles ----------
    async def cada(self, nombre: str, periodo: float, fn):
        while True:
            try:
                await fn()
            except Exception as e:  # un bucle que cae no tumba el servicio: se dice con su causa y se sigue
                self.anota(causa(e), f"bucle {nombre}: {type(e).__name__} {str(e)[:200]}")
            # los de minuto, al segundo 20 (la vela ya cerro y la ingesta la ha escrito)
            await asyncio.sleep((20 * (periodo == 60) - time.time()) % periodo or periodo)

    async def tic_minuto(self):
        # cada paso en su try: el 2026-10-24 un parte que no entraba en la base (SQL_ASCII) cortaba el minuto ANTES del
        # latido, y bot_estado se quedo vacio con el centinela vivo. El latido se escribe siempre.
        for nombre, paso in (("centinela", self.tic_centinela), ("parte", self.tic_parte), ("informe", self.tic_informe)):
            try:
                await paso()
            except Exception as e:
                self.anota(causa(e), f"{nombre}: {type(e).__name__} {str(e)[:200]}")
        await self.latido()

    async def tic_telegram(self):
        if not self.tg:
            return await asyncio.sleep(3600)
        try:
            textos = await self.tg.recibe()
        except (RuntimeError, httpx.HTTPError, ValueError) as e:
            # con espera creciente (5 s .. 5 min) y dicho en el estado: antes reintentaba cada segundo y seguia «ok» (bug 9)
            self.tg_espera = min(max(5.0, self.tg_espera * 2), 300.0)
            nombre = "TELEGRAM_" + str(e).split()[1].rstrip(":") if isinstance(e, RuntimeError) else "TELEGRAM"
            self.estado["telegram"] = f"{str(e)[:80] or type(e).__name__} (reintento en {int(self.tg_espera)} s)"
            self.anota(nombre, self.estado["telegram"])
            return await asyncio.sleep(self.tg_espera)
        self.tg_espera, self.estado["telegram"] = 0.0, "ok"
        self.bien("TELEGRAM")
        for t in textos:  # cada mensaje aparte y fuera del bucle: uno que falla no se lleva el resto del lote (bug 12)
            self.lanza(self.responde(t), "mensaje")

    async def responde(self, texto: str):
        try:
            respuesta = await self.atiende(texto)
        except Exception as e:  # atiende solo captura lo previsto: el resto tambien se contesta, con su causa
            self.anota(causa(e), f"mensaje: {type(e).__name__} {str(e)[:200]}")
            respuesta = f"no pude contestar ({causa(e)}: {type(e).__name__}); el error queda en /estado"
        if respuesta:
            await self.manda(respuesta)

    async def corre(self):
        os.makedirs(self.informes, exist_ok=True)
        await self.carga()
        enviada = await self.manda(f"bot arriba · {self.texto_salud(await self.salud(), 'ARRANQUE')}")
        await self.evento("arranque", None, None, enviada, detalle={"version": self.estado["version"], "esfuerzo": self.esfuerzo})
        await asyncio.gather(self.cada("centinela", 60, self.tic_minuto), self.cada("bybit", 60, self.tic_bybit),
                             self.cada("telegram", 1, self.tic_telegram))


async def principal():
    dsn = os.environ.get("BOT_PG_DSN") or "postgresql:///coinalyze?host=/var/run/postgresql&user=coinalyze-ai"
    # 4: tres bucles y las tareas de Opus y de cada mensaje (remate 3, bug 6) comparten la base; el pool las pone en fila
    db = await asyncpg.create_pool(dsn, min_size=1, max_size=4, server_settings={"application_name": "coinalyze-bot"})
    async with httpx.AsyncClient() as http:
        await Bot(dict(os.environ), db, http).corre()


def main():
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(Formato("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[h], force=True)
    logging.getLogger("httpx").setLevel(logging.WARNING)  # su INFO lleva la URL, y la de Telegram lleva el token
    asyncio.run(principal())
