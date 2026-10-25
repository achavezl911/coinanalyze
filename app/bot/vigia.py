"""El INTERRUPTOR DE HOMBRE MUERTO del bot (remate 1 de BOT-2): un proceso APARTE que dice lo que el bot no puede decir
de si mismo (un bot caido no avisa de que esta caido) y avisa por OTRO canal: el bot de Telegram del puente viejo.
`python -m app.bot.vigia`, lanzado por deploy/140/coinalyze-bot-vigia.service: su .timer cada 5 min y el OnFailure= de
coinalyze-bot (en systemd 257 salta en CADA caida: BOT2.r1.onfailure en hechos.tsv). Mira:
  unidad   systemctl show coinalyze-bot: ActiveState active (y, si lo lanzo un OnFailure, con que resultado cayo)
  base     que la base conteste
  latido   bot_estado 'bot' de hace <= LATIDO_MIN minutos
  parte    el parte del dia, pasada servicio.PARTE_HORA_UTC + 30 min
  informe  el semanal de la semana ISO, pasado su lunes a las 13:30Z (con la causa que dejo 143 si no llego)
  bybit    (remate 7) con Bybit activo y el bot latiendo, el ultimo tic de Bybit COMPLETO de hace <= BYBIT_MIN minutos: si
           la identidad o cualquier paso revienta cada minuto, el latido sigue y sin esto nadie lo veria
Un aviso cuando un problema APARECE y otro cuando se VA (estado en $STATE_DIRECTORY/estado.json), no una rafaga; si el
envio falla, se reintenta en la siguiente pasada. Su latido y lo que ve van a bot_estado 'vigia' (K117 lo juzga) y cada
aviso enviado, a bot_evento 'vigia'.
Entorno: el EnvironmentFile del PUENTE, que systemd carga y nadie lee ni copia: TELEGRAM_BOT_TOKEN y
TELEGRAM_OUTPUT_CHAT_ID o, si no hay, TELEGRAM_CHAT_ID (como el puente: su config.py:172). Opcionales: BOT_PG_DSN,
BOT_INFORMES, VIGIA_LATIDO_MIN (5).
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import subprocess
from datetime import UTC, datetime, timedelta

import asyncpg
import httpx

from app.bot.servicio import PARTE_HORA_UTC, Telegram, js, limpia, semana_iso

LATIDO_MIN = 5
BYBIT_MIN = 5
MARGEN_PARTE = timedelta(minutes=30)


def problemas(ahora: datetime, unidad: dict | None, monitor: str | None, base_error: str | None, latido: datetime | None,
              parte_hoy: bool, informe_semana: bool, falla_informe: str | None, latido_min: int = LATIDO_MIN,
              bybit: dict | None = None) -> dict:
    """{clave: texto} de lo que esta mal AHORA. Pura."""
    out = {}
    if unidad is None:
        out["unidad"] = "no puedo preguntar a systemd por coinalyze-bot"
    elif unidad.get("ActiveState") not in ("active", "reloading"):
        cayo = f", cayo con {monitor}" if monitor else ""
        out["unidad"] = f"coinalyze-bot {unidad.get('ActiveState')}/{unidad.get('SubState')} ({unidad.get('Result')}{cayo})"
    if base_error:
        out["base"] = f"la base no contesta: {base_error}"
        return out  # sin base no se puede mirar ni el latido ni el parte
    if latido is None:
        out["latido"] = "el bot no ha latido nunca"
    elif ahora - latido > timedelta(minutes=latido_min):
        out["latido"] = f"el bot no late desde hace {int((ahora - latido).total_seconds() // 60)} min (ultimo {latido:%H:%MZ})"
    elif isinstance(bybit, dict) and bybit.get("activo") and bybit.get("tic"):  # late, pero ¿lee Bybit entero?
        try:
            tic = datetime.fromisoformat(str(bybit["tic"]).replace("Z", "+00:00"))
        except ValueError:
            tic = None
        if tic and ahora - tic > timedelta(minutes=BYBIT_MIN):
            out["bybit"] = (f"el bot late pero no completa una lectura de Bybit desde hace {int((ahora - tic).total_seconds() // 60)} min"
                            f" (ultima {tic:%H:%MZ}): ni avisos de stop ni evaluaciones")
    if ahora >= ahora.replace(hour=PARTE_HORA_UTC, minute=0, second=0, microsecond=0) + MARGEN_PARTE and not parte_hoy:
        out[f"parte:{ahora:%Y-%m-%d}"] = f"el parte de hoy ({PARTE_HORA_UTC}:00Z) no salio"
    lunes = (ahora - timedelta(days=ahora.weekday())).replace(hour=13, minute=30, second=0, microsecond=0)
    if ahora >= lunes and not informe_semana:
        out[f"informe:{semana_iso(ahora)}"] = "el informe semanal no llego" + (f": {falla_informe}" if falla_informe else "")
    return out


CON_FECHA = ("parte:", "informe:")


def transicion(notificados: dict, actuales: dict, base_caida: bool = False, llegados: frozenset = frozenset()) -> tuple[dict, list, list]:
    """-> (nuevos: los que hay que avisar, resueltos, caducados). Un avisado que ya no sale NO se da por resuelto si no se
    pudo mirar (la base cayo y depende de ella: latido, parte, informe), y uno con fecha que salio de su dia o su semana sin
    llegar (no esta en `llegados`) caduca: se dice «no llego nunca», no «resuelto» (remate 3, bug 7)."""
    nuevos = {k: v for k, v in actuales.items() if k not in notificados}
    resueltos, caducados = [], []
    for k in notificados:
        if k in actuales or (base_caida and (k in ("latido", "bybit") or k.startswith(CON_FECHA))):
            continue
        (caducados if k.startswith(CON_FECHA) and k not in llegados else resueltos).append(k)
    return nuevos, resueltos, caducados


def mensajes(nuevos: dict, resueltos: list, notificados: dict, caducados: list = ()) -> list[tuple[str, str]]:
    out = []
    if nuevos:
        out.append(("alerta", "INTERRUPTOR del bot (coinalyze-bot) · ALERTA\n" + "\n".join(f"- {t}" for t in nuevos.values())
                    + "\n(aviso una vez; aviso otra cuando se arregle)"))
    if resueltos:
        out.append(("resuelto", "INTERRUPTOR del bot · resuelto\n" + "\n".join(f"- {notificados[k]}" for k in resueltos)))
    if caducados:
        out.append(("caducado", "INTERRUPTOR del bot · NO llego nunca (ya no se espera)\n" + "\n".join(f"- {notificados[k]}" for k in caducados)))
    return out


def lee_estado(f: pathlib.Path) -> dict:
    """El estado de la pasada anterior; uno corrupto (un apagon a mitad de escribir) no tumba el interruptor (bug 10)."""
    try:
        e = json.loads(f.read_text(encoding="utf-8"))
        return e if isinstance(e, dict) else {}
    except FileNotFoundError:
        return {}
    except (ValueError, OSError) as e:
        print(f"CAUSA=VIGIA_ESTADO {f.name} ilegible ({type(e).__name__}): empiezo de cero", flush=True)
        return {}


def escribe_estado(f: pathlib.Path, texto: str) -> None:
    """Atomica: a un temporal y os.replace, para que un apagon no deje medio fichero (bug 10)."""
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(texto, encoding="utf-8")
    os.replace(tmp, f)


def unidad_bot() -> dict | None:
    try:
        r = subprocess.run(["systemctl", "show", "coinalyze-bot", "-p", "ActiveState", "-p", "SubState", "-p", "Result"],
                           capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    return dict(ln.split("=", 1) for ln in r.stdout.splitlines() if "=" in ln) or None


async def pasada(entorno: dict, http: httpx.AsyncClient, unidad: dict | None, conecta, estado_f: pathlib.Path,
                 ahora: datetime | None = None) -> dict:
    """Una pasada del interruptor. conecta(): la conexion a la base (o lanza). Devuelve lo que publica."""
    ahora = ahora or datetime.now(UTC)
    previo = lee_estado(estado_f)
    notificados = previo.get("notificados", {}) if isinstance(previo.get("notificados"), dict) else {}
    informes = entorno.get("BOT_INFORMES") or "/var/lib/coinalyze-bot/informes"
    sem = semana_iso(ahora)
    falla = pathlib.Path(informes, f"{sem}.falla")
    db, base_error, latido, parte_hoy, informe_semana, bybit = None, None, None, False, False, None
    try:
        db = await conecta()
        latido = await db.fetchval("SELECT ts FROM bot_estado WHERE clave = 'bot'")
        b = await db.fetchval("SELECT estado->'bybit' FROM bot_estado WHERE clave = 'bot'")
        try:
            bybit = json.loads(b) if isinstance(b, str) else b
        except ValueError:
            bybit = None
        parte_hoy = await db.fetchval("SELECT EXISTS (SELECT 1 FROM bot_evento WHERE tipo = 'parte' AND (ts AT TIME ZONE 'UTC')::date = $1)",
                                      ahora.date())
        informe_semana = await db.fetchval("SELECT EXISTS (SELECT 1 FROM bot_evento WHERE tipo = 'informe' AND detalle->>'semana' = $1)", sem)
    except (TimeoutError, OSError, asyncpg.PostgresError, asyncpg.InterfaceError) as e:
        base_error = f"{type(e).__name__} {limpia(str(e))[:120]}"
    actuales = problemas(ahora, unidad, entorno.get("MONITOR_SERVICE_RESULT"), base_error, latido, parte_hoy, informe_semana,
                         falla.read_text(encoding="utf-8").strip()[:200] if falla.exists() else None,
                         int(entorno.get("VIGIA_LATIDO_MIN") or LATIDO_MIN), bybit)
    llegados = set()  # de los avisados con fecha que ya no salen, cuales llegaron de verdad (tarde)
    for k in [k for k in notificados if k.startswith(CON_FECHA) and k not in actuales]:
        if db is None or base_error:
            break
        try:
            tipo, cuando = k.split(":", 1)
            sql = ("SELECT EXISTS (SELECT 1 FROM bot_evento WHERE tipo = 'parte' AND (ts AT TIME ZONE 'UTC')::date = $1::date)" if tipo == "parte"
                   else "SELECT EXISTS (SELECT 1 FROM bot_evento WHERE tipo = 'informe' AND detalle->>'semana' = $1)")
            if await db.fetchval(sql, datetime.strptime(cuando, "%Y-%m-%d").date() if tipo == "parte" else cuando):
                llegados.add(k)
        except (ValueError, OSError, asyncpg.PostgresError, asyncpg.InterfaceError) as e:
            base_error = f"{type(e).__name__} {limpia(str(e))[:120]}"
    nuevos, resueltos, caducados = transicion(notificados, actuales, base_error is not None, frozenset(llegados))
    token, chat = entorno.get("TELEGRAM_BOT_TOKEN"), entorno.get("TELEGRAM_OUTPUT_CHAT_ID") or entorno.get("TELEGRAM_CHAT_ID")
    envio = previo.get("envio", {"ok": None, "ts": None})
    for tipo_msg, texto in mensajes(nuevos, resueltos, notificados, caducados):
        ok = False
        if token and chat:
            try:
                ok = await Telegram(token, chat, http).manda(texto)
            except httpx.HTTPError as e:
                print(f"CAUSA=VIGIA_TELEGRAM {type(e).__name__}", flush=True)
        else:
            print("CAUSA=VIGIA_SIN_CANAL faltan TELEGRAM_BOT_TOKEN y TELEGRAM_OUTPUT_CHAT_ID/TELEGRAM_CHAT_ID del puente", flush=True)
        envio = {"ok": ok, "ts": ahora.isoformat()}
        print(f"aviso {'enviado' if ok else 'NO enviado'}: {texto.splitlines()[0]}", flush=True)
        if not ok:
            break  # lo no avisado se queda fuera de notificados: se reintenta en la siguiente pasada
        if tipo_msg == "alerta":
            notificados |= nuevos
        else:
            fuera = resueltos if tipo_msg == "resuelto" else caducados
            notificados = {k: v for k, v in notificados.items() if k not in fuera}
        # lo avisado va al fichero ANTES de tocar la base: en 140 (2026-10-24) el registro del aviso no entraba (SQL_ASCII),
        # la pasada moria sin guardar y el aviso se repetia cada 5 min
        escribe_estado(estado_f, js({**previo, "notificados": notificados, "envio": envio}))
        await en_la_base(db, "INSERT INTO bot_evento (tipo, enviada, detalle) VALUES ('vigia', true, $1::jsonb)", js({"texto": texto}))
    publica = {"ts": ahora.isoformat(), "problemas": actuales, "notificados": notificados, "envio": envio,
               "canal": "puente" if token and chat else "sin canal"}
    escribe_estado(estado_f, js(publica))
    if db is not None:
        await en_la_base(db, "INSERT INTO bot_estado (clave, ts, estado) VALUES ('vigia', $1, $2::jsonb)"
                             " ON CONFLICT (clave) DO UPDATE SET ts = excluded.ts, estado = excluded.estado", ahora, js(publica))
        await db.close()
    return publica


async def en_la_base(db, sql: str, *args) -> None:
    """Una escritura del interruptor que, si falla, se dice (CAUSA=VIGIA_BASE) y no lo tumba: su trabajo es avisar."""
    if db is None:
        return
    try:
        await db.execute(sql, *args)
    except (OSError, asyncpg.PostgresError, asyncpg.InterfaceError) as e:
        print(f"CAUSA=VIGIA_BASE {type(e).__name__} {limpia(str(e))[:160]}", flush=True)


async def principal():
    dsn = os.environ.get("BOT_PG_DSN") or "postgresql:///coinalyze?host=/var/run/postgresql&user=coinalyze-ai"
    carpeta = pathlib.Path(os.environ.get("STATE_DIRECTORY") or "/var/lib/coinalyze-bot-vigia")
    async with httpx.AsyncClient() as http:
        p = await pasada(dict(os.environ), http, unidad_bot(), lambda: asyncpg.connect(dsn, timeout=10), carpeta / "estado.json")
    print(f"vigia: {len(p['problemas'])} problema(s) {sorted(p['problemas'])} · avisados {sorted(p['notificados'])}", flush=True)


if __name__ == "__main__":
    asyncio.run(principal())
