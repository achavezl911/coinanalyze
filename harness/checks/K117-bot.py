"""K117 · el bot (BOT-2) en produccion. Lo llama K117-el-bot.sh (ver su cabecera); salida y rc del arnes.

Nueve brazos, cada uno en su try (uno que cae no tumba a los demas):
  servicio   systemctl show coinalyze-bot por bin/prod: active/running; no instalada -> NO MEDIDO
  latido     bot_estado: el ultimo latido hace <= LATIDO_MAX s
  bybit      el estado que el bot PUBLICA (no la clave): solo_lectura y la IP; sin juzgar -> NO MEDIDO
  vigia      (remate 1) el interruptor: su .timer active, su ultima pasada success, su fila de bot_estado de hace
             <= VIGIA_PASA_MAX s, y que si el bot no latia cuando paso, lo dio por problema y pudo avisar
  parte      (remate 1) pasadas las 13:30Z, el parte de hoy; antes, el de ayer
  journal    (remate 1) ninguna linea de 24 h del journal del bot ni del interruptor con la FORMA de una clave (se cuentan
             en 140; nunca se imprimen)
  alertas    las rafagas y clases de bot_evento en [max(ahora - HORAS, dia del primer arranque), ahora - MARGEN) ==
             las que da el detector de app/rafagas.py (Z = 4, el resto congelado) sobre el ohlcv 1min de 140, con el
             dia UTC anclado a CALIENTA min: el pegamento (series, huecos, ancla) es de ESTE fichero, no el del bot
  gasto      bot_llamada: la suma de cada dia UTC de los ultimos 7 <= su tope
  codigo     ni una ruta de ordenes, retiros ni transferencias en app/bot del arbol NI en el release de 140
"""

from __future__ import annotations

import dataclasses
import json
import os
import pathlib
import re
import subprocess
import sys
from datetime import UTC, datetime

REPO, B = os.environ["K117_REPO"], os.environ["K117_HARNESS"]
HORAS, MARGEN, CALIENTA, LATIDO_MAX = int(os.environ.get("K117_HORAS", "24")), 45, 180, 180
ACTIVOS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
RUTAS = r"/v5/(order|asset|position/(set|trading-stop|switch|add-margin|confirm)|account/(set|upgrade))|/v5/[^ ]*(withdraw|transfer)"
condenas: list[str] = []
faltas: list[str] = []
dichos: list[str] = []


def corre(prog: str, orden: str) -> tuple[int, str, str]:
    # UTF-8 explicito: la base de 140 es SQL_ASCII y psql devuelve los bytes UTF-8 del bot tal cual (tildes en el estado);
    # con text=True a secas la decodificacion dependeria del locale de quien corra el check
    r = subprocess.run(["sh", f"{B}/bin/{prog}", orden], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=120, env={**os.environ, "TODO": "1"})
    return r.returncode, r.stdout, r.stderr


def sql(q: str, que: str) -> list[list[str]] | None:
    """Filas, o None con la falta apuntada (la tabla que no existe es «sin el servicio»)."""
    rc, out, err = corre("prodsql", q)
    if rc != 0:
        no_existe = "does not exist" in err
        faltas.append(f"{que}: " + ("la tabla no existe en 140 (FALTA DESPLEGAR)" if no_existe
                                    else f"prodsql rc={rc} {err.strip()[-120:]}"))
        return None
    return [ln.split("|") for ln in out.splitlines() if ln.strip()]


def brazo(fn):
    try:
        fn()
    except Exception as e:  # un brazo que revienta no midio
        faltas.append(f"{fn.__name__} cayo: {type(e).__name__} {str(e)[:120]}")


def servicio():
    rc, out, _ = corre("prod", "systemctl show coinalyze-bot -p LoadState -p ActiveState -p SubState; echo FIN-K117")
    if "FIN-K117" not in out or "LoadState=" not in out:
        return faltas.append(f"servicio: bin/prod sin su marco ({out.strip()[:80]!r})")
    p = dict(ln.split("=", 1) for ln in out.splitlines() if "=" in ln)
    if p.get("LoadState") == "not-found":
        return faltas.append("servicio: coinalyze-bot no esta instalada en 140")
    if (p.get("ActiveState"), p.get("SubState")) != ("active", "running"):
        return condenas.append(f"coinalyze-bot {p.get('ActiveState')}/{p.get('SubState')} en 140")
    dichos.append("coinalyze-bot active/running")


AHORA: list[int] = []
FILAS: dict = {}  # bot_estado por clave: (ts, estado)
VIGIA_LATIDO, VIGIA_PASA_MAX, PARTE_HORA_UTC = 300, 900, 13  # app/bot/vigia.py LATIDO_MIN, su timer x3, servicio.PARTE_HORA_UTC
# las FORMAS de las claves (nunca sus valores): Anthropic, el token de un bot de Telegram, y una clave de Bybit u otra
# pegada a su nombre. Sin comillas: viaja dentro de un grep entre comillas simples por bin/prod.
FORMAS = r"sk-ant-[A-Za-z0-9_-]{20,}|[0-9]{8,10}:[A-Za-z0-9_-]{35}|(api_key|apikey|api-key|secret|token)[^A-Za-z0-9]{1,4}[A-Za-z0-9_-]{16,}"


def latido_y_bybit():
    f = sql("SELECT extract(epoch FROM now())::bigint", "ahora")
    if f is None:
        return
    if not f or not f[0][0].isdigit():
        return faltas.append("ahora: 140 no dijo su hora")
    AHORA.append(int(f[0][0]))
    f = sql("SELECT clave, extract(epoch FROM ts)::bigint, estado::text FROM bot_estado", "latido")
    if f is None:
        return
    for clave, ts, *resto in f:
        FILAS[clave] = (int(ts), json.loads("|".join(resto)))
    if "bot" not in FILAS:
        return faltas.append("latido: el bot no ha latido nunca")
    edad = AHORA[0] - FILAS["bot"][0]
    estado = FILAS["bot"][1]
    if edad > LATIDO_MAX:
        condenas.append(f"el ultimo latido del bot es de hace {edad} s (tope {LATIDO_MAX})")
    else:
        dichos.append(f"latido hace {edad} s")
    b = estado.get("bybit") or {}
    if b.get("solo_lectura") is False:
        condenas.append(f"el bot publica que la clave de Bybit PUEDE OPERAR ({b.get('error')})")
    elif b.get("solo_lectura") is True and b.get("ip_ok") is False:
        condenas.append(f"el bot publica que la clave de Bybit no esta atada a la IP ({b.get('ips')})")
    elif b.get("solo_lectura") is True and b.get("ip_ok") is True:
        dichos.append("Bybit de solo lectura y atada a la IP (estado del bot)")
    else:
        faltas.append(f"bybit: el bot no pudo juzgar la clave ({b.get('error')})")


def vigia():
    """El interruptor: su temporizador vivo, su ultima pasada bien, su latido, y que AVISE cuando el bot no late."""
    rc, out, _ = corre("prod", "systemctl show coinalyze-bot-vigia.timer -p LoadState -p ActiveState; echo SERVICIO-K117;"
                               " systemctl show coinalyze-bot-vigia.service -p Result; echo FIN-K117")
    if "FIN-K117" not in out or "SERVICIO-K117" not in out:
        return faltas.append(f"vigia: bin/prod sin su marco ({out.strip()[:80]!r})")
    temporizador, servicio_ = (dict(ln.split("=", 1) for ln in trozo.splitlines() if "=" in ln) for trozo in out.split("SERVICIO-K117", 1))
    if temporizador.get("LoadState") == "not-found":
        return faltas.append("vigia: el interruptor (coinalyze-bot-vigia.timer) no esta instalado en 140")
    if temporizador.get("ActiveState") != "active":
        condenas.append(f"el temporizador del interruptor esta {temporizador.get('ActiveState')}: nadie avisa si el bot cae")
    if servicio_.get("Result") not in (None, "success"):
        condenas.append(f"la ultima pasada del interruptor fallo ({servicio_.get('Result')})")
    if not AHORA or "vigia" not in FILAS:
        return faltas.append("vigia: el interruptor no ha publicado nunca en bot_estado")
    ts, e = FILAS["vigia"]
    if AHORA[0] - ts > VIGIA_PASA_MAX:
        return condenas.append(f"el interruptor no pasa desde hace {AHORA[0] - ts} s (tope {VIGIA_PASA_MAX})")
    if "bot" in FILAS and ts - FILAS["bot"][0] > VIGIA_LATIDO and "latido" not in (e.get("problemas") or {}):
        return condenas.append(f"el interruptor no avisa: el bot no late desde hace {ts - FILAS['bot'][0]} s cuando paso, y no lo da por problema")
    sin_avisar = set(e.get("problemas") or {}) - set(e.get("notificados") or {})
    if sin_avisar and (e.get("envio") or {}).get("ok") is False:
        return condenas.append(f"el interruptor no pudo avisar de {sorted(sin_avisar)} (canal: {e.get('canal')})")
    dichos.append(f"interruptor vivo (paso hace {AHORA[0] - ts} s, {len(e.get('problemas') or {})} problema(s) avisados)")


def parte():
    """El parte diario: pasadas las 13:30Z, el de hoy; antes, el de ayer (salvo que el bot arrancara despues)."""
    if not AHORA:
        return faltas.append("parte: sin la hora de 140")
    f = sql("SELECT coalesce(max(extract(epoch FROM ts))::bigint, 0), coalesce(min(extract(epoch FROM ts)) FILTER"
            " (WHERE tipo = 'arranque'), 0)::bigint FROM bot_evento WHERE tipo IN ('parte', 'arranque')", "parte")
    if f is None:
        return
    ultimo, primero = int(f[0][0]), int(f[0][1])
    hoy = AHORA[0] // 86400 * 86400
    toca = hoy + PARTE_HORA_UTC * 3600 if AHORA[0] >= hoy + PARTE_HORA_UTC * 3600 + 1800 else hoy - 86400 + PARTE_HORA_UTC * 3600
    if not primero:
        return faltas.append("parte: el bot no ha arrancado nunca")
    if primero > toca:
        return dichos.append("el primer parte aun no tocaba (el bot arranco despues)")
    if ultimo < toca:
        cuando = datetime.fromtimestamp(ultimo, UTC).strftime("%m-%d %H:%MZ") if ultimo else "nunca"
        return condenas.append(f"el parte de {datetime.fromtimestamp(toca, UTC):%m-%d} no salio (el ultimo: {cuando})")
    dichos.append(f"parte de {datetime.fromtimestamp(ultimo, UTC):%m-%d %H:%MZ}")


def journal():
    """Ninguna linea del journal del bot ni del interruptor (24 h) con la FORMA de una clave: se cuentan, no se imprimen."""
    rc, out, _ = corre("prod", "echo LINEAS-K117 $(journalctl -u coinalyze-bot -u coinalyze-bot-vigia --since -24h -q --no-pager | wc -l);"
                               f" echo FORMAS-K117 $(journalctl -u coinalyze-bot -u coinalyze-bot-vigia --since -24h -q --no-pager"
                               f" | grep -c -E '{FORMAS}'); echo FIN-K117")
    m = re.search(r"LINEAS-K117 (\d+)\s+FORMAS-K117 (\d+)\s+FIN-K117", out)
    if not m:
        return faltas.append(f"journal: bin/prod sin su marco ({out.strip()[:80]!r})")
    lineas, formas = int(m.group(1)), int(m.group(2))
    if formas:
        return condenas.append(f"{formas} linea(s) del journal del bot con FORMA de clave en 24 h (no se imprimen: journalctl en 140)")
    if not lineas:
        return faltas.append("journal: coinalyze-bot no tiene lineas en 24 h")
    dichos.append(f"journal sin formas de clave ({lineas} lineas en 24 h)")


def series(filas: dict, t0: int, t1: int):
    import app.rafagas as rf

    out = {}
    for a in ACTIVOS:
        f = filas[a]
        ms = sorted(m for m in f if t0 <= m < t1)
        if not ms:
            return None
        hi, lo, c, buy, sell = cols = ([], [], [], [], [])
        ultimo = f[ms[0]][2]
        for m in range(t0, t1):
            x = f.get(m, (ultimo, ultimo, ultimo, 0.0, 0.0))  # (alto, bajo, cierre, compra, venta)
            ultimo = x[2]
            for col, y in zip(cols, x, strict=True):
                col.append(y)
        out[a] = rf.Serie(t0, c, hi, lo, buy, sell)
    return out


def alertas():
    import app
    import app.rafagas as rf

    if not pathlib.Path(app.__file__).resolve().is_relative_to(pathlib.Path(REPO).resolve()):
        return faltas.append(f"alertas: importe app/ de {app.__file__}, no de {REPO}")
    if not AHORA:
        return faltas.append("alertas: sin la hora de 140")
    u = dataclasses.replace(rf.UMBRALES, Z=4.0)
    ahora = AHORA[0] // 60
    f = sql("SELECT min(extract(epoch FROM ts))::bigint FROM bot_evento WHERE tipo = 'arranque'", "alertas")
    if f is None:
        return
    if not f or not f[0][0]:
        return faltas.append("alertas: el bot no ha arrancado nunca")
    ini, fin = max(ahora - HORAS * 60, int(f[0][0]) // 86400 * 1440), ahora - MARGEN
    if ini >= fin:
        return faltas.append("alertas: el primer arranque es de hace menos de MARGEN min")
    reg = sql("SELECT tipo, symbol, (extract(epoch FROM minuto)::bigint / 60)::int, coalesce(lado::text, ''),"
              f" coalesce(clase, '') FROM bot_evento WHERE tipo IN ('rafaga', 'clase') AND minuto >= to_timestamp({ini * 60})"
              f" AND minuto < to_timestamp({fin * 60})", "alertas")
    if reg is None:
        return
    registradas = {(t, a, int(m), int(lado), cl) for t, a, m, lado, cl in reg if ini <= int(m) < fin}
    d0, d1 = ini // 1440 * 1440, (fin - 1) // 1440 * 1440
    desde, hasta = d0 - CALIENTA, fin + u.DECIDE
    filas: dict = {a: {} for a in ACTIVOS}
    for a in range(desde, hasta, 360):  # seis horas por consulta (A137)
        b = min(a + 360, hasta)
        for s, m, *x in sql("SELECT split_part(symbol, '_', 1), (extract(epoch FROM ts)::bigint / 60)::int, high, low, close,"
                            " buy_volume, volume - buy_volume FROM ohlcv WHERE interval = '1min' AND symbol IN"
                            " ('BTCUSDT_PERP.A', 'ETHUSDT_PERP.A', 'SOLUSDT_PERP.A')"
                            f" AND ts >= to_timestamp({a * 60}) AND ts < to_timestamp({b * 60})", "velas") or []:
            if s in filas and a <= int(m) < b:
                filas[s][int(m)] = tuple(map(float, x))
    esperadas = set()
    for d in range(d0, d1 + 1, 1440):
        se = series(filas, d - CALIENTA, min(d + 1440 + u.DECIDE, hasta))
        if se is None:
            return faltas.append(f"alertas: sin velas de 1 min en 140 para el dia {d // 1440}")
        z = {a: rf.rasgos(se[a], u.W, u.BASE)[0] for a in ACTIVOS}
        for a in ACTIVOS:
            for i, lado in rf.detecta(se[a], u):
                m = d - CALIENTA + i
                if max(ini, d) <= m < min(fin, d + 1440):
                    esperadas.add(("rafaga", a, m, lado, ""))
                    cl = rf.clasifica(se[a], i, lado, u, [z[o] for o in ACTIVOS if o != a])
                    if cl:
                        esperadas.add(("clase", a, m, lado, cl[0]))
    hhmm = lambda k: (f"{k[1][:3]} {datetime.fromtimestamp(k[2] * 60, UTC):%m-%d %H:%MZ} {k[0]}"  # noqa: E731
                      f"{'=' + k[4] if k[4] else ''}")
    sobran, faltan = sorted(registradas - esperadas, key=lambda k: k[2]), sorted(esperadas - registradas, key=lambda k: k[2])
    if sobran:
        condenas.append(f"{len(sobran)} alerta(s) registradas que el detector NO da: {', '.join(map(hhmm, sobran[:4]))}")
    if faltan:
        condenas.append(f"faltan {len(faltan)} alerta(s) que el detector da: {', '.join(map(hhmm, faltan[:4]))}")
    if not sobran and not faltan:
        n = sum(1 for k in esperadas if k[0] == "rafaga")
        dichos.append(f"alertas == detector: {n} rafagas y {len(esperadas) - n} clases en {fin - ini} min")


def gasto():
    f = sql("SELECT (ts AT TIME ZONE 'UTC')::date, sum(coste_usd), min(tope_usd), count(*) FROM bot_llamada"
            " WHERE ts >= now() - interval '7 days' GROUP BY 1 ORDER BY 1", "gasto")
    if f is None:
        return
    pasados = [(d, float(s), float(t)) for d, s, t, _ in f if float(s) > float(t)]
    if pasados:
        return condenas.append("gasto de la API por encima del tope: " + ", ".join(f"{d} {s:.2f} > {t:.2f} USD" for d, s, t in pasados))
    dichos.append(f"gasto 7 d bajo el tope ({sum(int(n) for *_, n in f)} llamadas, max dia {max((float(s) for _, s, _, _ in f), default=0):.2f} USD)")


def codigo():
    pat = re.compile(RUTAS, re.I)
    arbol = sorted(pathlib.Path(REPO, "app", "bot").glob("*.py"))
    if not arbol:
        faltas.append("codigo: el arbol no trae app/bot")
    for p in arbol:
        for n, ln in enumerate(p.read_text().splitlines(), 1):
            if pat.search(ln):
                condenas.append(f"ruta de ordenes/retiros/transferencias en el arbol: app/bot/{p.name}:{n} {pat.search(ln).group(0)}")
    if arbol and not any(c.startswith("ruta de ordenes") for c in condenas):
        dichos.append(f"app/bot del arbol sin rutas de ordenes ({len(arbol)} ficheros)")
    rc, out, _ = corre("prod", "if [ -d /opt/coinalyze/current/app/bot ]; then echo CODIGO-K117;"
                               f" grep -rnoE '{RUTAS}' /opt/coinalyze/current/app/bot; echo FIN-K117; else echo SIN-BOT-K117; fi")
    if "SIN-BOT-K117" in out:
        return faltas.append("codigo: el release de 140 no trae app/bot (FALTA DESPLEGAR)")
    if "CODIGO-K117" not in out or "FIN-K117" not in out:
        return faltas.append(f"codigo: bin/prod sin su marco ({out.strip()[:80]!r})")
    hallado = out.split("CODIGO-K117", 1)[1].split("FIN-K117", 1)[0].strip()
    if hallado:
        return condenas.append(f"ruta de ordenes/retiros/transferencias en el release de 140: {hallado.splitlines()[0][:160]}")
    dichos.append("ni en el release de 140")


sys.path.insert(0, REPO)
for fn in (servicio, latido_y_bybit, vigia, parte, journal, alertas, gasto, codigo):
    brazo(fn)
corta = lambda s: s if len(s) <= 380 else s[:377] + "..."  # noqa: E731
if condenas:
    print(corta(f"ROJO  K117 {condenas[0]}" + (f" (+{len(condenas) - 1} mas)" if len(condenas) > 1 else "")))
    for x in condenas[1:]:
        print(corta(f"  ROJO {x}"))
    for x in faltas:
        print(corta(f"  no medido: {x}"))
    rc = 1
elif faltas:
    print(corta(f"NO MEDIDO: K117 {faltas[0]}" + (f" (+{len(faltas) - 1})" if len(faltas) > 1 else "")))
    for x in faltas[1:]:
        print(corta(f"  no medido: {x}"))
    rc = 2
else:
    print(corta("VERDE  K117 · el bot · " + " · ".join(dichos)))
    rc = 0
for x in dichos if rc else []:
    print(corta(f"  medido: {x}"))
sys.exit(rc)
