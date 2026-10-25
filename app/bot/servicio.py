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
from datetime import UTC, datetime, timedelta

import asyncpg
import httpx

from app.bot import bybit as bb
from app.bot import calc, calidad, llm, vidas
from app.bot import centinela as cen

log = logging.getLogger("app.bot")
SECRETOS = ("ANTHROPIC_API_KEY", "BYBIT_API_KEY", "BYBIT_API_SECRET", "TELEGRAM_BOT_TOKEN", "API_INTERNAL_TOKEN")
VEREDICTOS = ("A FAVOR", "EN CONTRA", "NO EVALUABLE")
PARTE_HORA_UTC = calidad.PARTE_HORA_UTC  # 13: 07:00 en Ciudad de Mexico; vive en calidad, que cuenta los partes que tocaban
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


SIN_OPUS = {"/calc", "calc", "/entrada", "/entradas", "entrada", "/estado", "/gasto", "/informe", "/start", "/ayuda", "/help"}


def a_opus(texto: str) -> bool:
    """¿Este mensaje llama a Opus? /evalua y las preguntas libres; las ordenes de SIN_OPUS no (Bot.atiende)."""
    orden = texto.strip().split()[0].lower() if texto.strip() else ""
    return orden not in SIN_OPUS


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
    omision; los bytes UTF-8 tal cual (ensure_ascii=False) entran y se leen iguales. Y sin NUL, que no entra en ninguna.
    Y por limpia(): todo lo que se guarda pasa por aqui, asi que ninguna clave llega a la base (remate 4)."""
    s = json.dumps(x, ensure_ascii=False)
    return limpia(s if "\\u0000" not in s else json.dumps(_sin_nul(x), ensure_ascii=False))


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
# Remate 4: a todas, liq_burst (las liquidaciones de los ultimos 5 min, ~140 caracteres: lo que explica una rafaga) y
# context_metadata (la edad de cada feed, ~1500: la regla 2 pide decir lo viejo; la cito una respuesta de evalua); y
# ESCALA, que sale tras una rafaga o una alerta de stop, recibe el flujo y las liquidaciones para poder explicarla.
COMUNES = ("symbol", "generated_at", "envelope_cut", "snapshot", "operator_read", "scalp", "data_confidence", "data_quality",
           "volatility", "local_alerts", "liq_burst", "context_metadata")
FLUJO = ("cvd_matrix", "delta_matrix", "orderbook", "passive_flow", "oi_context", "funding_context", "positioning",
         "liquidation_map", "liquidation_levels", "price_barriers", "reference_levels", "structure_horizons", "structure_detail",
         "market_structure", "trend_matrix", "divergences", "absorption", "basis")
BLOQUES = {
    "ESCALA": COMUNES + ("orderbook", "price_barriers", "reference_levels", "liquidation_map", "liquidation_levels", "market_structure",
                         "cvd_matrix", "delta_matrix", "oi_context", "funding_context", "scalp_liquidations"),
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


CADUCA_H = 6


def errores_vigentes(errores: dict, ahora: datetime) -> str:
    """Los errores que ensenan /estado y el parte: los sin resolver, y los resueltos hace menos de una hora con «resuelto
    HH:MMZ». Uno resuelto hace mas de una hora no se ensena (remate 3, punto 14). Cada uno lo resuelve SU operacion al
    volver a ir bien (Bot.bien); el que no se repite en CADUCA_H horas sin que su operacion vuelva a correr (una tarea
    que no se repite) CADUCA, y se dice «caducado» durante una hora (remate 4, R6). La configuracion no caduca: sigue
    mal hasta que se arregla y se reinicia (remate 5)."""
    out = []
    for k, x in errores.items():
        r, nota = x.get("resuelto"), "resuelto"
        if not r and x.get("op") != "configuracion" and \
                (ahora - datetime.fromisoformat(x["ultima"].replace("Z", "+00:00"))).total_seconds() > CADUCA_H * 3600:
            r = (datetime.fromisoformat(x["ultima"].replace("Z", "+00:00")) + timedelta(hours=CADUCA_H)).strftime("%Y-%m-%dT%H:%M:%SZ")
            nota = f"sin repetirse en {CADUCA_H} h: caducado"
        if r and (ahora - datetime.fromisoformat(r.replace("Z", "+00:00"))).total_seconds() > 3600:
            continue
        out.append(f"{k} ({x['ultima'][11:16]}Z: {x['texto'][:60]}{f', {nota} {r[11:16]}Z' if r else ''})")
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
        # id -> la posicion que la ULTIMA lectura ensena (remate 6: nada se paga sobre una ausente o cerrada)
        self.pos: dict = {}
        self.libro = vidas.Libro()  # la vida de cada posicion (app/bot/vidas.py); va en el estado (bot_estado)
        self.evaluadas: dict = {}  # id -> {veredicto: el PRIMERO, posicion}, sin cierre todavia
        self.evaluando: set = set()
        self.intentos: dict = {}  # id -> evaluaciones intentadas; proxima_eval: id -> cuando se puede volver a intentar
        self.proxima_eval: dict = {}
        self.avisados: set = set()  # (id, tipo) de stop/liquidacion y (symbol:side:updatedTime, sin_stop)
        self.validadas: set = set()
        self.tareas: set = set()  # lo que va fuera de los bucles (Opus): que el latido y las alertas no esperen
        self.turno = None  # la tarea de la ultima respuesta: la siguiente sale despues (en orden)
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
            self.anota("CONFIGURACION", a, "configuracion")

    def anota(self, nombre: str, texto: str, op: str | None = None):
        """Un error con su causa nombrada y la OPERACION que fallo: al journal (CAUSA=...) y a /estado y al parte (el
        ultimo de cada causa y operacion: «BYBIT closed-pnl», «BASE registro llamada», «KEYERROR bucle bybit»)."""
        texto = limpia(texto)[:300]
        log.warning("CAUSA=%s %s", nombre, texto)
        self.estado["errores"][f"{nombre} {op}" if op else nombre] = {"ultima": ahora_iso(), "texto": texto, "resuelto": None, "op": op}

    def bien(self, *ops: str):
        """Esas operaciones volvieron a ir bien: SUS errores quedan «resueltos a las HH:MM» (remate 3, punto 14). Por la
        operacion exacta, no por el prefijo de la causa (remate 4, R6: position/list resolvia el fallo de closed-pnl, y el
        latido el de un INSERT de bot_llamada)."""
        for v in self.estado["errores"].values():
            if v.get("op") in ops and not v.get("resuelto"):
                v["resuelto"] = ahora_iso()

    def lanza(self, coro, nombre: str):
        """Fuera del bucle (remate 3, bug 6): una llamada a Opus no para el latido ni las alertas de los otros activos.
        `nombre` es la operacion: si cae se anota con el, y si la siguiente del mismo nombre va bien, lo resuelve."""
        async def seguro():
            try:
                await coro
            except Exception as e:  # una tarea que cae se dice con su causa
                self.anota(causa(e), f"{nombre}: {type(e).__name__} {str(e)[:200]}", nombre)
            else:
                self.bien(nombre)
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
            self.anota("BASE", f"no registro el evento {tipo}: {type(e).__name__} {str(e)[:120]}", f"registro {tipo}")
        else:
            self.bien(f"registro {tipo}")

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
        for i, v, p, ms in await self.db.fetch(
                "SELECT DISTINCT ON (posicion) posicion, veredicto, detalle->'posicion', (extract(epoch FROM ts) * 1000)::bigint"
                " FROM bot_evaluacion e WHERE tipo = 'veredicto' AND ts >= now() - interval '30 days'"
                " AND NOT EXISTS (SELECT 1 FROM bot_evaluacion c WHERE c.tipo = 'cierre' AND c.posicion = e.posicion)"
                " ORDER BY posicion, ts"):
            self.evaluadas[i] = {"veredicto": v, "posicion": json.loads(p) if isinstance(p, str) else p, "visto": ms}
        # (id, tipo) de stop/liquidacion; (symbol:side:updatedTime, sin_stop) del aviso de seguridad (remate 6)
        self.avisados = {(i, t) for i, t in await self.db.fetch(
            "SELECT coalesce(detalle->>'visto', detalle->>'posicion'), tipo FROM bot_evento"
            " WHERE tipo IN ('stop', 'liquidacion', 'sin_stop') AND ts >= now() - interval '30 days'") if i}
        e = await self.db.fetchrow("SELECT extract(epoch FROM ts)::bigint t, estado FROM bot_estado WHERE clave = 'bot'")
        self.desde_minuto = int(e["t"]) // 60 if e else None
        try:
            guardado = (json.loads(e["estado"]) if isinstance(e["estado"], str) else e["estado"]) if e else None
        except ValueError:
            guardado = "ilegible"
        filas = [{"orden": o, "symbol": s, "q": q, "e": en, "x": x, "pnl": pnl, "b": ms} for o, s, q, en, x, pnl, ms in await self.db.fetch(
            "SELECT orden, symbol, cantidad, entrada, salida, pnl_usd, (extract(epoch FROM cerrada) * 1000)::bigint FROM bot_operacion"
            " WHERE cerrada >= now() - interval '8 days'")]
        # la vida de cada posicion: del ultimo estado (tolerante: lo que no se entiende se descarta y se dice), lo visto al
        # evaluar cada vida sin cierre (un veredicto posterior al ultimo latido es una lectura mas: remate 6, R-B) y las filas
        self.libro, avisos = vidas.Libro.desde(guardado, self.evaluadas, filas)
        for a in avisos:
            self.anota("ESTADO", a, "carga")
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
        self.estado["libro"] = self.libro.estado()
        # lo que ya no se ensena (resuelto o caducado hace mas de una hora) sale del estado: con una operacion por id
        # (evalua <id>, escala <id>) crecia sin fin (remate 5)
        ahora = datetime.now(UTC)
        self.estado["errores"] = {k: x for k, x in self.estado["errores"].items() if errores_vigentes({k: x}, ahora) != "ninguno"}
        await self.db.execute(
            "INSERT INTO bot_estado (clave, ts, estado) VALUES ('bot', now(), $1::jsonb)"
            " ON CONFLICT (clave) DO UPDATE SET ts = excluded.ts, estado = excluded.estado", js(self.estado))
        self.bien("latido")

    async def manda(self, texto: str) -> bool:
        if not self.tg:
            return False
        try:
            ok = await self.tg.manda(texto)
        except httpx.HTTPError as e:
            self.anota("TELEGRAM", f"no envia: {type(e).__name__}", "sendMessage")
            return False
        if ok:
            self.bien("sendMessage")
        return ok

    # ---------- laboratorio y Opus ----------
    async def api(self, ruta: str) -> dict:
        op = ruta.split("?")[0]
        try:
            r = await self.http.get(self.api_base + ruta, headers={"X-Internal-Token": self.e.get("API_INTERNAL_TOKEN", "")}, timeout=60)
        except httpx.HTTPError as e:
            self.estado["api"] = f"no contesta ({type(e).__name__}) a las {ahora_iso()}"
            self.anota("API_140", f"{op} no contesta: {type(e).__name__}", op)
            raise LookupError(f"no evaluable: la API del laboratorio no contesta ({type(e).__name__})") from e
        if r.status_code != 200:
            self.estado["api"] = f"HTTP {r.status_code} en {op} a las {ahora_iso()}"
            self.anota("API_140", f"HTTP {r.status_code} en {op}" + (" (token interno?)" if r.status_code == 403 else ""), op)
            raise LookupError(f"no evaluable: la API del laboratorio da HTTP {r.status_code} en {op}")
        self.estado["api"] = "ok"
        self.bien(op)
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
                    self.anota("BASE", f"no registro la llamada {ruta} ({r['coste']:.3f} USD, cuenta para el tope): {type(e).__name__}",
                               "registro llamada")
                else:
                    self.bien("registro llamada")
            if r["error"]:
                self.anota("TOPE" if r["error"].startswith("tope") else "ANTHROPIC", f"{ruta}: {r['error']}", f"opus {ruta}")
            elif r["texto"]:
                self.bien(f"opus {ruta}")
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
            return self.anota("DATOS", self.estado["datos"], "velas")
        hasta = min(max(f) for f in filas.values()) + 1
        self.estado["datos"] = {"ultima_vela": datetime.fromtimestamp((hasta - 1) * 60, UTC).strftime("%H:%MZ"),
                                "retraso_min": ahora - hasta}
        for dia in dias:
            for r in cen.rafagas_del_dia(filas, dia, hasta):
                await self.rafaga(r, ahora, filas)
        self.desde_minuto = ahora - 15
        self.bien("velas")

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
            return self.anota("BYBIT", self.estado["bybit"]["error"], "query-api")
        primera, self.clave_juzgada = not self.clave_juzgada, True
        self.clave_proxima, self.clave_espera = time.time() + 3600, 30.0
        b = self.estado["bybit"] = bb.juzga_clave(d, self.ip) | {"leida": ahora_iso()}
        if b["activo"]:
            self.bien("query-api")
        else:
            self.anota("BYBIT_IP" if "IP" in str(b["error"]) else "BYBIT", f"Bybit apagado: {b['error']}", "query-api")
        if b["activo"] != antes or (primera and not b["activo"]):
            txt = "Bybit ACTIVO: clave de solo lectura atada a la IP de 140" if b["activo"] else \
                f"Bybit APAGADO en el bot: {b['error']}. No leo posiciones hasta que se arregle."
            await self.evento("bybit", None, None, await self.manda(txt), detalle=b)

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
            return self.anota("BYBIT", f"position/list no contesta: {type(e).__name__}", "position/list")
        if bb.error(d):
            self.estado["bybit"]["error"] = bb.error(d)
            self.anota("BYBIT_IP" if d.get("retCode") == 10010 else "BYBIT", f"position/list: {bb.error(d)}", "position/list")
            if d.get("retCode") in (10003, 10010, 33004):
                self.clave_proxima = 0.0  # se vuelve a juzgar la clave en el proximo tic, y si cae se avisa
            return
        self.bien("position/list")
        # LA VIDA de cada posicion la lleva el libro (app/bot/vidas.py, remate 6): esta lectura, las filas nuevas, y el
        # decide: que vidas ensena esta lectura, cual es nueva y cuales cerraron ya seguras
        lista, ahora_ms = bb.posiciones(d), int(time.time() * 1000)
        self.libro.lee(ahora_ms, lista)
        if self.libro.abiertas() or self.evaluadas or time.time() - self.ops_leidas > 900:
            try:  # closed-pnl cada minuto con algo abierto o por puntuar
                await self.operaciones()
            except (OSError, asyncpg.PostgresError, asyncpg.InterfaceError, httpx.HTTPError) as e:
                self.anota(causa(e), f"closed-pnl: {type(e).__name__} {str(e)[:120]}", "closed-pnl")
        r = self.libro.decide(ahora_ms)
        vistas = {p["clave"]: p | {"visto": ahora_ms} for p in lista}
        # solo lo que ESTA lectura ensena (remate 6, I5: una ausente o cerrada no recibe nada pagado: ni ESCALADO ni /evalua)
        self.pos = {i: vistas[c] | {"id": i} | ({"reapertura": r["notas"][i]} if i in r["notas"] else {})
                    for i, c in r["presentes"].items() if c in vistas}
        # EL AVISO DE SEGURIDAD NO DEPENDE DE LA IDENTIDAD (remate 6, I3): cada posicion que se ve sin stop, una vez por
        # cada updatedTime (una vida nueva siempre trae otro, y poner o quitar el stop tambien lo cambia)
        for p in vistas.values():
            visto = f"{p['clave']}:{p.get('actualizada')}"
            if not p.get("stop") and (visto, "sin_stop") not in self.avisados:
                self.avisados.add((visto, "sin_stop"))
                i = next((i for i, q in self.pos.items() if q["clave"] == p["clave"]), None)
                txt = f"{p['symbol']} {'LARGO' if p['lado'] > 0 else 'CORTO'} sin stop puesto"
                await self.evento("sin_stop", p["symbol"], int(time.time() // 60), await self.manda(f"{cen.LEYENDA.split(' · ')[0]} · {txt}"),
                                  detalle={"posicion": i, "visto": visto, "texto": txt, "entradas": {"posicion": p, "leida": ahora_iso()}})
        for i, p in self.pos.items():
            if i not in self.validadas:
                await self.valida(p)
            if i not in self.evaluadas and i not in self.evaluando and time.time() >= self.proxima_eval.get(i, 0):
                self.evaluando.add(i)
                self.lanza(self.evalua_una(p, "posicion nueva" + (f" · {p['reapertura']}" if p.get("reapertura") else "")), f"evalua {i}")
            for tipo, txt in cen.alertas_posicion(p):
                if tipo != "sin_stop" and (i, tipo) not in self.avisados:
                    self.avisados.add((i, tipo))
                    await self.evento(tipo, p["symbol"], int(time.time() // 60), await self.manda(f"{cen.LEYENDA.split(' · ')[0]} · {txt}"),
                                      detalle={"posicion": i, "texto": txt, "entradas": {"posicion": p, "leida": ahora_iso()}})
                    self.lanza(self.escala(p, txt), f"escala {i}")
        for i, res in r["resultados"]:
            if i in self.evaluadas:
                await self.cierre(i, res)

    async def operaciones(self) -> set:
        """Las operaciones CERRADAS de Bybit a bot_operacion (una por orden), para BOT-3 y para puntuar. -> los simbolos
        con alguna nueva. Las ya apuntadas no se vuelven a escribir, y se deja de paginar al llegar a ellas (se lee cada
        minuto con algo abierto). ponytail: lo que closed-pnl devuelve por omision (la doc dice 7 dias; no contrastado),
        hasta 10 paginas; el lado no se deduce aqui (bybit.lado_cierre, al puntuar)."""
        self.ops_leidas, cursor, nuevas = time.time(), None, set()  # (las ya apuntadas: self.libro.ordenes)
        for _ in range(10):
            d = await self.bybit.get("/v5/position/closed-pnl", category="linear", limit=100, **({"cursor": cursor} if cursor else {}))
            if bb.error(d):
                self.anota("BYBIT", f"closed-pnl: {bb.error(d)}", "closed-pnl")
                return nuevas
            res, vista = d.get("result") or {}, False
            for c in res.get("list") or []:
                orden = str(c.get("orderId") or f"{c.get('symbol')}:{c.get('updatedTime')}")
                if orden in self.libro.ordenes:
                    vista = True
                    continue
                num = lambda k, c=c: float(c[k]) if c.get(k) not in (None, "") else None  # noqa: E731
                await self.db.execute(
                    "INSERT INTO bot_operacion (orden, symbol, cantidad, entrada, salida, pnl_usd, apalancamiento, cerrada, detalle)"
                    " VALUES ($1, $2, $3, $4, $5, $6, $7, to_timestamp($8::bigint / 1000.0), $9::jsonb) ON CONFLICT DO NOTHING",
                    orden, c.get("symbol"), num("closedSize"), num("avgEntryPrice"), num("avgExitPrice"), num("closedPnl"),
                    num("leverage"), int(c.get("updatedTime") or c.get("createdTime") or 0), js(c))
                self.libro.fila({"orden": orden, "symbol": c.get("symbol"), "b": int(c.get("updatedTime") or c.get("createdTime") or 0),
                                 "q": num("closedSize"), "e": num("avgEntryPrice"), "x": num("avgExitPrice"), "pnl": num("closedPnl")})
                nuevas.add(c.get("symbol"))
            cursor = res.get("nextPageCursor")
            if vista or not cursor:
                break
        self.bien("closed-pnl")
        if nuevas:
            log.info("bot_operacion: cerradas nuevas de %s", sorted(nuevas))
        return nuevas

    async def valida(self, p: dict):
        """La liquidacion de la formula contra la que da Bybit para una posicion real: se registra una vez por posicion."""
        if not p.get("liquidacion") or not p.get("entrada") or not p.get("cantidad") or not p.get("apalancamiento"):
            return
        try:
            t = (await self.bybit.get("/v5/market/risk-limit", category="linear", symbol=p["symbol"]))["result"]["list"]
            f, mmr = calc.liquidacion(p["entrada"], p["cantidad"], p["apalancamiento"], p["lado"], t)
        except (KeyError, TypeError, ValueError, httpx.HTTPError) as e:
            return self.anota("BYBIT", f"risk-limit para validar la liquidacion: {type(e).__name__}", "risk-limit")
        self.bien("risk-limit")
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
            self.anota("BASE", f"no registro la evaluacion de {p['id']}: {type(e).__name__}", "registro veredicto")
        else:
            self.bien("registro veredicto")
        sesgo = ((dec.get("decide") or {}).get("bias") or {}).get("value")
        await self.manda(f"EVALUACION {p['symbol']} {'LARGO' if p['lado'] > 0 else 'CORTO'} ({motivo})\nVEREDICTO: {v} ({fuente})"
                         f"\nDECIDE: {sesgo} -> {v_dec}{liq}\n{texto or ''}")

    async def evalua_una(self, p: dict, motivo: str):
        """La evaluacion de una vida nueva. Si cae (la base, la red...), se reintenta con espera creciente -1, 2, 4... min,
        hasta 1 h entre intentos- y sin tope de intentos: antes, tres seguidos y nunca mas (remate 4, R11). Lo pagado no
        se repite: evalua la da por hecha en cuanto Opus contesta, aunque la base no la apunte (remate 3, bug 3)."""
        i = p["id"]
        n = self.intentos[i] = self.intentos.get(i, 0) + 1
        self.proxima_eval[i] = time.time() + min(60 * 2 ** (n - 1), 3600)
        try:
            await self.evalua(p, motivo)
        finally:
            self.evaluando.discard(i)

    async def cierre(self, i: str, res: dict):
        """El resultado de una vida evaluada que el libro ya da por cerrada y segura: con SUS filas, o sin puntuar y el
        porque (ambigua: <motivo>; closed-pnl no trajo su cierre). Nunca una cifra que no se sabe (remate 6, I2)."""
        v, pnl = self.evaluadas.pop(i)["veredicto"], res["pnl"]
        acierto = None if v == "NO EVALUABLE" or pnl is None else (pnl > 0) == (v == "A FAVOR")
        try:
            await self.db.execute(
                "INSERT INTO bot_evaluacion (tipo, posicion, veredicto, pnl_usd, acierto, detalle) VALUES ('cierre', $1, $2, $3, $4, $5::jsonb)",
                i, v, pnl, acierto, js({"ordenes": res["ordenes"], "nota": res["nota"]}))
        except (OSError, asyncpg.PostgresError, asyncpg.InterfaceError) as e:
            self.anota("BASE", f"no registro el cierre de {i}: {type(e).__name__}", "registro cierre")
        else:
            self.bien("registro cierre")
        sym, lado = i.split(":")[:2]
        resultado = "sin puntuar" if pnl is None else f"{pnl:+.2f} USD"
        await self.manda(f"CERRADA {sym} {'LARGO' if lado == 'Buy' else 'CORTO'}: {resultado} · el veredicto era {v}"
                         f" -> {'sin puntuar' if acierto is None else ('ACIERTO' if acierto else 'FALLO')}"
                         + (f"\n{res['nota']}" if res["nota"] else ""))

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
        s = await self.salud()
        texto = self.texto_salud(s, f"PARTE {n:%Y-%m-%d}")
        enviada = await self.manda(texto)
        if not enviada and self.tg:
            return  # se reintenta al minuto siguiente; el interruptor avisa si a las 13:30Z no ha salido
        # marcado SOLO despues de enviarlo (remate 4, R5: marcado antes, una base que tropezaba en salud() dejaba el dia
        # sin parte) y ANTES de registrarlo (si la base no lo apunta, no se repite cada minuto: remate 3, bug 4)
        self.parte_hoy = n.date()
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
                self.anota(causa(e), f"bucle {nombre}: {type(e).__name__} {str(e)[:200]}", f"bucle {nombre}")
            else:  # y la vuelta siguiente que va bien lo resuelve, tambien las causas genericas (KEYERROR...: R6)
                self.bien(f"bucle {nombre}")
            # los de minuto, al segundo 20 (la vela ya cerro y la ingesta la ha escrito)
            await asyncio.sleep((20 * (periodo == 60) - time.time()) % periodo or periodo)

    async def tic_minuto(self):
        # cada paso en su try: el 2026-10-24 un parte que no entraba en la base (SQL_ASCII) cortaba el minuto ANTES del
        # latido, y bot_estado se quedo vacio con el centinela vivo. El latido se escribe siempre.
        for nombre, paso in (("centinela", self.tic_centinela), ("parte", self.tic_parte), ("informe", self.tic_informe)):
            try:
                await paso()
            except Exception as e:
                self.anota(causa(e), f"{nombre}: {type(e).__name__} {str(e)[:200]}", nombre)
            else:
                self.bien(nombre)
        try:
            await self.latido()
        except Exception as e:
            self.anota(causa(e), f"latido: {type(e).__name__} {str(e)[:200]}", "latido")

    async def tic_telegram(self):
        if not self.tg:
            return await asyncio.sleep(3600)
        try:
            textos = await self.tg.recibe()
        except (RuntimeError, httpx.HTTPError, ValueError) as e:
            # con espera creciente (5 s .. 5 min) y dicho en el estado: antes reintentaba cada segundo y seguia «ok» (bug 9)
            self.tg_espera = min(max(5.0, self.tg_espera * 2), 300.0)
            nombre = "TELEGRAM_" + str(e).split()[1].rstrip(":") if isinstance(e, RuntimeError) else "TELEGRAM"
            # limpia: el estado va a bot_estado y al parte, y el texto de una excepcion de red puede llevar la URL del token
            self.estado["telegram"] = limpia(f"{str(e)[:80] or type(e).__name__} (reintento en {int(self.tg_espera)} s)")
            self.anota(nombre, self.estado["telegram"], "getUpdates")
            return await asyncio.sleep(self.tg_espera)
        self.tg_espera, self.estado["telegram"] = 0.0, "ok"
        self.bien("getUpdates")
        for t in textos:  # cada mensaje aparte y fuera del bucle: uno que falla no se lleva el resto del lote (bug 12)
            if a_opus(t):  # en fila solo lo que va a Opus (remate 5: un /estado esperaba detras de una pregunta)
                self.turno = self.lanza(self.responde(t, self.turno), "mensaje")
            else:
                self.lanza(self.responde(t), "mensaje")

    async def responde(self, texto: str, antes: asyncio.Task | None = None):
        """Se contesta en paralelo; lo que va a Opus se ENVIA en el orden en que llego (remate 4: dos preguntas llegaban al
        reves): cada respuesta espera a la de la pregunta anterior. Lo que no va a Opus (/calc, /estado, /entrada...)
        contesta al momento (remate 5)."""
        try:
            respuesta = await self.atiende(texto)
        except Exception as e:  # atiende solo captura lo previsto: el resto tambien se contesta, con su causa
            self.anota(causa(e), f"mensaje: {type(e).__name__} {str(e)[:200]}", "atiende")
            respuesta = f"no pude contestar ({causa(e)}: {type(e).__name__}); el error queda en /estado"
        else:
            self.bien("atiende")
        if antes is not None and not antes.done():
            await asyncio.wait([antes])
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
