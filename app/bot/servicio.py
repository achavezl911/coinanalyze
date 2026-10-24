"""El bot de Telegram (BOT-2) de 140: el centinela (C1), la evaluacion de la operacion de Bybit (C2), la calculadora
(C3), las entradas APAGADAS (C4), las preguntas (C5) y las cuentas (C6). `python -m app.bot`; la unidad es
deploy/140/coinalyze-bot.service.

Entorno (EnvironmentFile de systemd; el bot recibe las claves y no las imprime: limpia() las borra de cada mensaje y
de cada linea de log): ANTHROPIC_API_KEY, BYBIT_API_KEY, BYBIT_API_SECRET, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
API_INTERNAL_TOKEN (el de la API local: la API pide X-Internal-Token tambien desde 127.0.0.1). Opcionales:
BOT_TOPE_USD_DIA (3), BOT_IP_SALIDA (138.186.31.141), BOT_PG_DSN (rol coinalyze-ai por el socket, sin contrasena:
pg_hba de 140 tiene `local all all peer`), BOT_API (http://127.0.0.1:8000).

Datos: los sobres del laboratorio por la API local; las velas de 1 min y el registro (tablas bot_*), por la base.
Nada de app.db.create_pool: escribe en tablas de la app y crea particiones.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
import time
from datetime import UTC, datetime

import asyncpg
import httpx

from app.bot import bybit as bb
from app.bot import calc
from app.bot import centinela as cen
from app.bot import llm

log = logging.getLogger("app.bot")
SECRETOS = ("ANTHROPIC_API_KEY", "BYBIT_API_KEY", "BYBIT_API_SECRET", "TELEGRAM_BOT_TOKEN", "API_INTERNAL_TOKEN")
VEREDICTOS = ("A FAVOR", "EN CONTRA", "NO EVALUABLE")
COMUN = """Eres el asistente de mesa de Alejandro (perpetuos BTC/ETH/SOL en Bybit). Reglas que no se rompen:
1. Cada cifra que escribas sale de los DATOS de este mensaje y lleva su fuente entre corchetes: la ruta de la clave
   (p. ej. [decide.bias.value], [cvd_matrix...]). Si un dato falta o esta marcado no evaluable, escribe «no evaluable».
2. NUNCA una probabilidad, un porcentaje de acierto ni un nivel que no este en los datos.
3. NO das entradas: no hay ventaja medida (BOT-1). Si te piden una, lo dices.
4. Corto: como mucho 8 lineas, en espanol, texto plano."""
EVALUA = COMUN + """
Evalua la POSICION contra el laboratorio (DECIDE; el flujo: CVD, delta, grandes, liquidaciones, OI, funding, el libro;
los marcos superiores). La primera linea es exactamente «VEREDICTO: A FAVOR», «VEREDICTO: EN CONTRA» o
«VEREDICTO: NO EVALUABLE»; despues, hasta 6 razones «- ... [fuente]»."""
ESCALA = COMUN + """
Ha saltado una ALERTA con la POSICION abierta. Explica en 3-5 lineas que pasa y PROPON (no es una orden: el bot no
opera) si ajustar el stop o el objetivo y a que nivel, con la fuente de ese nivel."""
PREGUNTA = COMUN + "\nContesta la PREGUNTA con los DATOS."
ENTRADAS = ("Entradas APAGADAS. La regla acordada el 10-20: el bot no da entradas mientras no haya una ventaja MEDIDA."
            " Las encenderia una frecuencia de acierto medida con n >= 30 por encima del equilibrio, con comision."
            " Hoy: ninguna (BOT-1: ninguna fila de BTC/ETH/SOL con ventaja medida tras una rafaga).")
AYUDA = ("/calc [btc|eth|sol] entrada [stop] [objetivo] [10$] [50x] [corto] · /evalua [btc|eth|sol] · /entrada ·"
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
        elif re.fullmatch(r"\d+(\.\d+)?x", t):
            a["apalancamiento"] = float(t[:-1])
        elif re.fullmatch(r"\d+(\.\d+)?\$", t):
            a["margen"] = float(t[:-1])
        elif re.fullmatch(r"\d+(\.\d+)?", t):
            a["numeros"].append(float(t))
        else:
            raise ValueError(f"no entiendo «{t}»: {AYUDA.split(' · ')[0]}")
    return a


def ahora_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class Telegram:
    def __init__(self, token: str, chat: str, http: httpx.AsyncClient):
        self.url, self.chat, self.http, self.offset, self.ajenos = f"https://api.telegram.org/bot{token}", str(chat), http, 0, 0

    async def manda(self, texto: str) -> bool:
        r = await self.http.post(f"{self.url}/sendMessage", json={"chat_id": self.chat, "text": limpia(texto)[:4000]}, timeout=20)
        return r.status_code == 200

    async def recibe(self) -> list[str]:
        """Los textos nuevos del chat de Alejandro; los de cualquier otro chat se cuentan y se tiran sin leer."""
        r = await self.http.get(f"{self.url}/getUpdates", params={"offset": self.offset, "timeout": 50}, timeout=70)
        if r.status_code == 409:
            raise RuntimeError("Telegram 409: otro servicio lee este bot")
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
        self.tg = Telegram(e["TELEGRAM_BOT_TOKEN"], e["TELEGRAM_CHAT_ID"], http) if e.get("TELEGRAM_BOT_TOKEN") and e.get("TELEGRAM_CHAT_ID") else None
        self.bybit = bb.Bybit(e["BYBIT_API_KEY"], e["BYBIT_API_SECRET"], http) if e.get("BYBIT_API_KEY") and e.get("BYBIT_API_SECRET") else None
        self.candado = asyncio.Lock()
        self.vistos: set = set()
        self.pos: dict = {}
        self.evaluadas: dict = {}  # posicion -> veredicto, sin cierre todavia
        self.avisados: set = set()
        self.clave_leida = 0.0
        self.semana = None
        self.estado = {
            "arranque": ahora_iso(), "version": os.path.basename(os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))),
            "telegram": "ok" if self.tg else "sin Telegram (faltan TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID)",
            "bybit": {"activo": False, "solo_lectura": None, "ip_ok": None, "ips": None,
                      "error": None if self.bybit else "sin BYBIT_API_KEY/BYBIT_API_SECRET"},
            "anthropic": {"clave": bool(e.get("ANTHROPIC_API_KEY")), "tope_usd": self.tope},
            "datos": None, "api": None,
        }

    # ---------- registro ----------
    async def evento(self, tipo: str, activo: str | None, minuto: int | None, enviada: bool, *, lado=None, clase=None, detalle=None):
        await self.db.execute(
            "INSERT INTO bot_evento (tipo, symbol, minuto, lado, clase, enviada, detalle)"
            " VALUES ($1, $2, to_timestamp($3::bigint * 60), $4, $5, $6, $7::jsonb) ON CONFLICT DO NOTHING",
            tipo, activo, minuto, lado, clase, enviada, json.dumps(detalle or {}))

    async def gastado_hoy(self) -> float:
        return float(await self.db.fetchval(
            "SELECT coalesce(sum(coste_usd), 0) FROM bot_llamada WHERE ts >= date_trunc('day', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'"))

    async def carga(self):
        for t, a, m in await self.db.fetch(
                "SELECT tipo, symbol, (extract(epoch FROM minuto)::bigint / 60)::int FROM bot_evento"
                " WHERE tipo IN ('rafaga', 'clase') AND minuto >= now() - interval '2 days'"):
            self.vistos.add((t, a, m))
        for p, v in await self.db.fetch(
                "SELECT posicion, veredicto FROM bot_evaluacion e WHERE tipo = 'veredicto' AND ts >= now() - interval '30 days'"
                " AND NOT EXISTS (SELECT 1 FROM bot_evaluacion c WHERE c.tipo = 'cierre' AND c.posicion = e.posicion)"):
            self.evaluadas[p] = v

    async def latido(self):
        self.estado["anthropic"]["gastado_hoy_usd"] = round(await self.gastado_hoy(), 4)
        await self.db.execute(
            "INSERT INTO bot_estado (clave, ts, estado) VALUES ('bot', now(), $1::jsonb)"
            " ON CONFLICT (clave) DO UPDATE SET ts = excluded.ts, estado = excluded.estado", json.dumps(self.estado))

    async def manda(self, texto: str) -> bool:
        if not self.tg:
            return False
        try:
            return await self.tg.manda(texto)
        except httpx.HTTPError as e:
            log.warning("Telegram no envia: %s", type(e).__name__)
            return False

    # ---------- laboratorio y Opus ----------
    async def api(self, ruta: str) -> dict:
        r = await self.http.get(self.api_base + ruta, headers={"X-Internal-Token": self.e.get("API_INTERNAL_TOKEN", "")}, timeout=60)
        if r.status_code != 200:
            self.estado["api"] = f"HTTP {r.status_code} en {ruta.split('?')[0]} a las {ahora_iso()}"
            raise LookupError(f"no evaluable: la API del laboratorio da HTTP {r.status_code} en {ruta.split('?')[0]}")
        self.estado["api"] = "ok"
        return r.json()

    async def sobre(self, activo: str) -> tuple[dict, dict]:
        s = cen.SIMBOLO.get(activo)
        if not s:
            raise LookupError(f"no evaluable: el laboratorio no cubre {activo}")
        ctx = await self.api(f"/api/ai/context?symbol={s}")
        ctx.pop("interpretation_prompt", None)  # sus reglas no son las del bot (rol, planes): las del bot van en system
        return ctx, await self.api(f"/api/mesa/decide?symbol={s}&frame=scalp")

    async def opus(self, motivo: str, system: str, texto: str) -> dict:
        if not self.e.get("ANTHROPIC_API_KEY"):
            return {"texto": None, "error": "sin ANTHROPIC_API_KEY"}
        async with self.candado:
            r = await llm.llama(self.http, self.e["ANTHROPIC_API_KEY"], system, texto, await self.gastado_hoy(), self.tope)
            if r["llamada"]:
                await self.db.execute(
                    "INSERT INTO bot_llamada (motivo, modelo, effort, tokens_entrada, tokens_salida, coste_usd, tope_usd, estimado)"
                    " VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
                    motivo, llm.MODELO, llm.EFFORT, r["entrada"], r["salida"], r["coste"], self.tope, r["estimado"])
            return r

    # ---------- C1 ----------
    async def tic_centinela(self):
        ahora = int(time.time() // 60)
        dias = sorted({(ahora - 15) // 1440 * 1440, ahora // 1440 * 1440})
        filas: dict = {a: {} for a in cen.ACTIVOS}
        for a, m, *x in await self.db.fetch(cen.SQL_VELAS, list(cen.SIMBOLO.values()), dias[0] - cen.CALIENTA, ahora):
            filas[a][m] = tuple(x)
        if not all(filas.values()):
            self.estado["datos"] = f"sin velas de 1 min de {[a for a in cen.ACTIVOS if not filas[a]]}"
            return
        hasta = min(max(f) for f in filas.values()) + 1
        self.estado["datos"] = {"ultima_vela": datetime.fromtimestamp((hasta - 1) * 60, UTC).strftime("%H:%MZ"),
                                "retraso_min": ahora - hasta}
        for dia in dias:
            for r in cen.rafagas_del_dia(filas, dia, hasta):
                await self.rafaga(r, ahora)

    async def rafaga(self, r: dict, ahora: int):
        a, m = r["activo"], r["minuto"]
        det = {k: round(r[k], 4) for k in ("z", "v", "imb")} | {"precio": r["precio"]}
        if ("rafaga", a, m) not in self.vistos:
            fresca = ahora - m <= 10  # tras una caida se registra, pero no se manda tarde
            await self.evento("rafaga", a, m, fresca and await self.manda(cen.texto_rafaga(r)), lado=r["lado"], detalle=det)
            self.vistos.add(("rafaga", a, m))
            p = next((p for p in self.pos.values() if p["symbol"] == a), None)
            if fresca and p:
                await self.escala(p, cen.texto_rafaga(r))
        if r["clase"] and ("clase", a, m) not in self.vistos:
            fresca = ahora - m <= 10 + cen.UMBRALES.DECIDE
            await self.evento("clase", a, m, fresca and await self.manda(cen.texto_clase(r)), lado=r["lado"], clase=r["clase"], detalle=det)
            self.vistos.add(("clase", a, m))

    async def escala(self, p: dict, alerta: str):
        try:
            ctx, dec = await self.sobre(p["symbol"])
        except LookupError as e:
            return await self.manda(f"ESCALADO {p['symbol']}: {e}")
        r = await self.opus("escala", ESCALA, f"ALERTA: {alerta}\nPOSICION: {json.dumps(p)}\nDATOS DECIDE: {json.dumps(dec)}"
                                              f"\nDATOS SOBRE: {json.dumps(ctx, separators=(',', ':'))}")
        await self.manda(f"ESCALADO {p['symbol']} (propuesta, no orden):\n{r['texto'] or r['error']}")

    # ---------- C2 ----------
    async def lee_clave(self):
        """Los permisos de la clave, al arrancar, cada hora y tras un rechazo. Se avisa al CAMBIAR (y la primera vez)."""
        primera, antes = self.clave_leida == 0.0, self.estado["bybit"].get("activo")
        self.clave_leida = time.time()
        b = self.estado["bybit"] = bb.juzga_clave(await self.bybit.get("/v5/user/query-api"), self.ip) | {"leida": ahora_iso()}
        if b["activo"] != antes or (primera and not b["activo"]):
            txt = "Bybit ACTIVO: clave de solo lectura atada a la IP de 140" if b["activo"] else \
                f"Bybit APAGADO en el bot: {b['error']}. No leo posiciones hasta que se arregle."
            await self.evento("bybit", None, None, await self.manda(txt), detalle=b)

    async def tic_bybit(self):
        if self.bybit is None:
            return
        if time.time() - self.clave_leida > 3600:
            await self.lee_clave()
        if not self.estado["bybit"]["activo"]:
            return
        d = await self.bybit.get("/v5/position/list", category="linear", settleCoin="USDT")
        if bb.error(d):
            self.estado["bybit"]["error"] = bb.error(d)
            if d.get("retCode") in (10003, 10010, 33004):
                self.clave_leida = 0.0  # se vuelve a juzgar la clave en el proximo tic, y si cae se avisa
            return
        abiertas = {p["id"]: p for p in bb.posiciones(d)}
        for i, p in abiertas.items():
            self.pos[i] = p
            if i not in self.evaluadas:
                await self.evalua(p, "posicion nueva")
            for tipo, txt in cen.alertas_posicion(p):
                if (i, tipo) not in self.avisados:
                    self.avisados.add((i, tipo))
                    await self.evento(tipo, p["symbol"], int(time.time() // 60), await self.manda(f"{cen.LEYENDA.split(' · ')[0]} · {txt}"), detalle={"posicion": i, "texto": txt})
                    if tipo != "sin_stop":
                        await self.escala(p, txt)
        for i in [i for i in self.pos if i not in abiertas]:
            del self.pos[i]
        for i in [i for i in self.evaluadas if i not in abiertas]:
            await self.puntua(i)

    async def evalua(self, p: dict, motivo: str):
        v_dec, dec, texto, liq = "NO EVALUABLE", {}, None, ""
        try:
            ctx, dec = await self.sobre(p["symbol"])
            v_dec = veredicto_decide(dec, p["lado"])
            r = await self.opus("evalua", EVALUA, f"POSICION: {json.dumps(p)}\nDATOS DECIDE: {json.dumps(dec)}"
                                                  f"\nDATOS SOBRE: {json.dumps(ctx, separators=(',', ':'))}")
            texto = r["texto"] or r["error"]
            v, fuente = (lee_veredicto(r["texto"]), "opus") if r["texto"] else (v_dec, f"DECIDE ({r['error']})")
        except LookupError as e:
            v, fuente, texto = "NO EVALUABLE", str(e), str(e)
        if v is None:
            v, fuente = "NO EVALUABLE", "opus sin veredicto legible"
        try:
            t = (await self.bybit.get("/v5/market/risk-limit", category="linear", symbol=p["symbol"]))["result"]["list"]
            f, _ = calc.liquidacion(p["entrada"], p["cantidad"], p["apalancamiento"], p["lado"], t)
            liq = f"\nliquidacion Bybit {p['liquidacion']:g} · formula {f:.6g} ({(f / p['liquidacion'] - 1) * 1e4:+.0f} bps)" if p.get("liquidacion") else ""
        except (KeyError, TypeError, ValueError, httpx.HTTPError):
            liq = "\nliquidacion: la formula no se pudo contrastar"
        await self.db.execute(
            "INSERT INTO bot_evaluacion (tipo, posicion, veredicto, veredicto_decide, detalle)"
            " VALUES ('veredicto', $1, $2, $3, $4::jsonb)",
            p["id"], v, v_dec, json.dumps({"motivo": motivo, "fuente": fuente, "posicion": p}))
        self.evaluadas[p["id"]] = v
        sesgo = ((dec.get("decide") or {}).get("bias") or {}).get("value")
        await self.manda(f"EVALUACION {p['symbol']} {'LARGO' if p['lado'] > 0 else 'CORTO'} ({motivo})\nVEREDICTO: {v} ({fuente})"
                         f"\nDECIDE: {sesgo} -> {v_dec}{liq}\n{texto or ''}")

    async def puntua(self, i: str):
        activo, _, creada = i.split(":")
        d = await self.bybit.get("/v5/position/closed-pnl", category="linear", symbol=activo, limit=50)
        if bb.error(d):
            return
        cierres = [c for c in (d.get("result") or {}).get("list") or [] if int(c.get("updatedTime") or 0) >= int(creada or 0)]
        if not cierres:
            return  # todavia no aparece: se vuelve a mirar en el proximo tic
        pnl = sum(float(c["closedPnl"]) for c in cierres)
        v = self.evaluadas.pop(i)
        acierto = None if v == "NO EVALUABLE" else (pnl > 0) == (v == "A FAVOR")
        await self.db.execute(
            "INSERT INTO bot_evaluacion (tipo, posicion, veredicto, pnl_usd, acierto, detalle) VALUES ('cierre', $1, $2, $3, $4, $5::jsonb)",
            i, v, pnl, acierto, json.dumps({"cierres": len(cierres)}))
        await self.manda(f"CERRADA {activo}: {pnl:+.2f} USD · el veredicto era {v} -> {'sin puntuar' if acierto is None else ('ACIERTO' if acierto else 'FALLO')}")

    # ---------- C3, C5, C6 ----------
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
        return calc.texto(r, s) + ("" if n else f"\n(entrada = marca actual {entrada:g})")

    async def pregunta(self, texto: str) -> str:
        activo = activo_de(texto, next((p["symbol"] for p in self.pos.values()), "BTCUSDT"))
        ctx, dec = await self.sobre(activo)
        r = await self.opus("pregunta", PREGUNTA, f"PREGUNTA: {texto}\nDATOS DECIDE: {json.dumps(dec)}"
                                                 f"\nDATOS SOBRE: {json.dumps(ctx, separators=(',', ':'))}")
        return r["texto"] or f"no contesto: {r['error']}"

    async def gasto(self) -> str:
        filas = await self.db.fetch(
            "SELECT (ts AT TIME ZONE 'UTC')::date d, count(*) n, sum(tokens_entrada) e, sum(tokens_salida) s, sum(coste_usd) c"
            " FROM bot_llamada WHERE ts >= now() - interval '7 days' GROUP BY 1 ORDER BY 1")
        dias = "\n".join(f"{f['d']}: {f['n']} llamadas, {f['e']} + {f['s']} tokens, {f['c']:.2f} USD" for f in filas)
        return f"gasto de hoy {await self.gastado_hoy():.2f} de {self.tope:.2f} USD (tope)\n{dias or 'sin llamadas en 7 dias'}"

    async def informe(self) -> str:
        ev = await self.db.fetch("SELECT tipo, coalesce(clase, '') c, count(*) n FROM bot_evento WHERE ts >= now() - interval '7 days' GROUP BY 1, 2 ORDER BY 1, 2")
        pu = await self.db.fetchrow(
            "SELECT count(*) FILTER (WHERE tipo = 'veredicto') v, count(*) FILTER (WHERE tipo = 'cierre') c,"
            " count(*) FILTER (WHERE acierto) a, count(*) FILTER (WHERE acierto IS NOT NULL) p, coalesce(sum(pnl_usd), 0) pnl"
            " FROM bot_evaluacion WHERE ts >= now() - interval '7 days'")
        alertas = ", ".join(" ".join(str(x) for x in (e["tipo"], e["c"], e["n"]) if x != "") for e in ev)
        return (f"INFORME 7 dias\nalertas: {alertas or 'ninguna'}"
                f"\nevaluaciones {pu['v']}, cerradas {pu['c']}: {pu['a']} aciertos de {pu['p']} puntuadas, pnl {pu['pnl']:+.2f} USD\n"
                + await self.gasto())

    def texto_estado(self) -> str:
        e, b = self.estado, self.estado["bybit"]
        return (f"bot {e['version'][:7]} desde {e['arranque']}\ndatos: {e['datos']}\nAPI: {e['api']}\nTelegram: {e['telegram']}"
                f"\nBybit: {'ACTIVO (solo lectura, IP ok)' if b['activo'] else 'APAGADO: ' + str(b['error'])}"
                f"\nAnthropic: clave {'si' if e['anthropic']['clave'] else 'NO'}, gastado hoy {e['anthropic'].get('gastado_hoy_usd')} de {self.tope} USD")

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
                return self.texto_estado()
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
            except Exception as e:  # un bucle que cae no tumba el servicio: se dice y se sigue
                log.warning("%s: %s %s", nombre, type(e).__name__, limpia(str(e))[:300])
            # los de minuto, al segundo 20 (la vela ya cerro y la ingesta la ha escrito)
            await asyncio.sleep((20 * (periodo == 60) - time.time()) % periodo or periodo)

    async def tic_minuto(self):
        await self.tic_centinela()
        n = datetime.now(UTC)
        if n.weekday() == 0 and n.hour == 8 and self.semana != n.isocalendar()[1]:
            self.semana = n.isocalendar()[1]
            await self.manda(await self.informe())
        await self.latido()

    async def tic_telegram(self):
        if not self.tg:
            return await asyncio.sleep(3600)
        try:
            textos = await self.tg.recibe()
            self.estado["telegram"] = "ok"
        except RuntimeError as e:
            self.estado["telegram"] = str(e)
            return await asyncio.sleep(60)
        for t in textos:
            respuesta = await self.atiende(t)
            if respuesta:
                await self.manda(respuesta)

    async def corre(self):
        await self.carga()
        await self.manda(f"bot arriba · {self.texto_estado()}")
        await asyncio.gather(self.cada("centinela", 60, self.tic_minuto), self.cada("bybit", 60, self.tic_bybit),
                             self.cada("telegram", 1, self.tic_telegram))


async def principal():
    dsn = os.environ.get("BOT_PG_DSN") or "postgresql:///coinalyze?host=/var/run/postgresql&user=coinalyze-ai"
    db = await asyncpg.create_pool(dsn, min_size=1, max_size=2, server_settings={"application_name": "coinalyze-bot"})
    async with httpx.AsyncClient() as http:
        await Bot(dict(os.environ), db, http).corre()


def main():
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(Formato("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[h], force=True)
    logging.getLogger("httpx").setLevel(logging.WARNING)  # su INFO lleva la URL, y la de Telegram lleva el token
    asyncio.run(principal())
