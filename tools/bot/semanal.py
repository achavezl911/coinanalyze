"""El INFORME SEMANAL del bot, por Claude Max y NO por la API (remate 1 de BOT-2, punto 9). Corre en 143 (la tarea
deploy/143/coinalyze-bot-semanal.{service,timer}, los lunes a las 12:00Z = 06:00 de Ciudad de Mexico), como root, con el
Claude Code que ya tiene la sesion de Max de Alejandro:

  1 la sesion: `claude auth status` (loggedIn y subscriptionType max) -- sin abrir ninguna credencial
  2 el uso semanal: una sonda minima (haiku, sin herramientas, en un directorio vacio) en stream-json, cuyo
    rate_limit_event trae unifiedWindows.seven_day.utilization; >= TOPE_MAX (0.40, el de Alejandro) -> no sale
  3 las CIFRAS, por el canal de solo lectura (harness/bin/prodsql), con app/bot/calidad.py: las de los 7 dias que acaban
    24 h antes de ahora (para que cada alerta tenga sus 24 h de precio detras)
  4 la REDACCION: `claude -p` con claude-opus-5-5 y --effort xhigh, sin herramientas, que solo puede citar esas cifras;
    detras va el bloque de cifras tal cual
  5 la ENTREGA en 140 por harness/bin/prod (que niega «>» y tee: se escribe con `install -m 644 /dev/stdin`) en
    /var/lib/coinalyze-bot/informes/<AAAA-Wss>.txt, y se comprueba su sha256; el bot lo envia por Telegram.
Si algo falla (sesion caducada, uso >= 40 %, tablas, la redaccion), deja <semana>.falla con la CAUSA: el parte diario y el
interruptor dicen «el informe semanal no llego: <causa>». Ninguna clave cambia de maquina.

  semanal.py                 la tarea
  semanal.py --prueba F.json las cifras de F.json en vez de prodsql, redacta de verdad y NO entrega (imprime)
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)
from app.bot import calidad  # noqa: E402

H = "/srv/coinanalyze/harness/bin"
DESTINO = "/var/lib/coinalyze-bot/informes"
TOPE_MAX = 0.40
MODELO, EFFORT = "claude-opus-5-5", "xhigh"
SIMBOLOS = {"BTCUSDT": "BTCUSDT_PERP.A", "ETHUSDT": "ETHUSDT_PERP.A", "SOLUSDT": "SOLUSDT_PERP.A"}
PIDE = """Redacta el INFORME SEMANAL del bot de Telegram de Alejandro (laboratorio Coinalyze, perpetuos BTC/ETH/SOL en
Bybit) con las CIFRAS de abajo, calculadas por codigo. Reglas: usa solo estas cifras (no inventes ninguna ni la redondees
de otra forma); espanol, texto plano, como mucho 25 lineas. Empieza por si el bot hizo su trabajo (partes diarios,
avisos del interruptor, gasto de la API contra su tope); sigue con la calidad: lo que hizo el precio tras las alertas
segun la regla de BOT-1 (de verdad cascada, de verdad barrido, falsas alarmas por dia), cuanto acerto la clase que dio el
bot y cuanto acertaron sus evaluaciones A FAVOR / EN CONTRA, y su historial cerrado de Bybit. Di lo que NO se puede
concluir con tan pocos casos. Nunca una probabilidad ni una entrada: el bot no las da (no hay ventaja medida).
CIFRAS (JSON):
"""


def corre(args: list[str], timeout: int, cwd: str | None = None, entrada: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, cwd=cwd, input=entrada,
                          env={**os.environ, "TODO": "1"})


def uso_max(lineas: str) -> float | None:
    """La fraccion de uso semanal de Max del rate_limit_event de una salida stream-json (None si no viene)."""
    for ln in lineas.splitlines():
        try:
            e = json.loads(ln)
        except ValueError:
            continue
        if e.get("type") == "rate_limit_event":
            v = ((e.get("rate_limit_info") or {}).get("unifiedWindows") or {}).get("seven_day", {}).get("utilization")
            if isinstance(v, (int, float)):
                return float(v)
    return None


def orden_entrega(nombre: str, texto: str) -> str:
    """El mandato para bin/prod: sin «>» ni tee (los niega); el texto viaja en base64."""
    b = base64.b64encode(texto.encode()).decode()
    return f"printf %s {b} | base64 -d | install -D -m 644 /dev/stdin {DESTINO}/{nombre}"


def entrega(nombre: str, texto: str) -> str:
    r = corre(["sh", f"{H}/prod", orden_entrega(nombre, texto)], 60)
    sha = hashlib.sha256(texto.encode()).hexdigest()
    visto = corre(["sh", f"{H}/prod", f"sha256sum {DESTINO}/{nombre}"], 60).stdout.split()
    if not visto or visto[0] != sha:
        raise RuntimeError(f"la entrega de {nombre} no cuadra (sha {sha[:12]} vs {visto[:1]}; {r.stdout.strip()[:120]})")
    return sha


def sql(q: str) -> list[list[str]]:
    r = corre(["sh", f"{H}/prodsql", q], 120)
    if r.returncode != 0:
        raise RuntimeError(f"prodsql rc={r.returncode}: {r.stderr.strip()[-160:]}")
    return [ln.split("|") for ln in r.stdout.splitlines() if ln.strip()]


def cifras(ahora: int) -> dict:
    """Las cifras de los 7 dias que acaban 24 h antes de `ahora` (minuto), por prodsql."""
    hasta = ahora - calidad.DIA - 1
    desde = hasta - 7 * calidad.DIA
    t = lambda m: f"to_timestamp({m * 60})"  # noqa: E731
    alertas = [{"activo": a, "minuto": int(m), "lado": int(lado), "clase": c or None} for a, m, lado, c in sql(
        "SELECT r.symbol, (extract(epoch FROM r.minuto)::bigint / 60)::int, r.lado, coalesce(c.clase, '') FROM bot_evento r"
        " LEFT JOIN bot_evento c ON c.tipo = 'clase' AND c.symbol = r.symbol AND c.minuto = r.minuto"
        f" WHERE r.tipo = 'rafaga' AND r.minuto >= {t(desde)} AND r.minuto < {t(hasta)}")]
    velas: dict = {a: {} for a in SIMBOLOS}
    for a in sorted({x["activo"] for x in alertas}):
        for i in range(desde, hasta + calidad.DIA + 1, 720):  # doce horas por consulta (A137)
            for m, hi, lo, c in sql(f"SELECT (extract(epoch FROM ts)::bigint / 60)::int, high, low, close FROM ohlcv WHERE interval = '1min'"
                                    f" AND symbol = '{SIMBOLOS[a]}' AND ts >= {t(i)} AND ts < {t(min(i + 720, hasta + calidad.DIA + 1))}"):
                velas[a][int(m)] = (float(hi), float(lo), float(c))
    ev = [{"veredicto": v, "acierto": {"true": True, "false": False}.get(a), "pnl_usd": float(p) if p else None} for v, a, p in sql(
        f"SELECT veredicto, coalesce(acierto::text, ''), coalesce(pnl_usd::text, '') FROM bot_evaluacion WHERE tipo = 'cierre' AND ts >= {t(desde)}")]
    ops = [{"pnl_usd": float(p) if p else None} for (p,) in sql(f"SELECT coalesce(pnl_usd::text, '') FROM bot_operacion WHERE cerrada >= {t(desde)}")]
    ll = [{"dia": d, "coste_usd": float(c), "tope_usd": float(tp)} for d, c, tp in sql(
        f"SELECT (ts AT TIME ZONE 'UTC')::date, coste_usd, tope_usd FROM bot_llamada WHERE ts >= {t(desde)}")]
    partes = [d for (d,) in sql(f"SELECT DISTINCT (ts AT TIME ZONE 'UTC')::date FROM bot_evento WHERE tipo = 'parte' AND ts >= {t(desde)}")]
    r = calidad.resumen(alertas, velas, ev, ops, ll, partes, desde, hasta)
    r["avisos_del_interruptor"] = int(sql(f"SELECT count(*) FROM bot_evento WHERE tipo = 'vigia' AND ts >= {t(desde)}")[0][0])
    return r


def redacta(c: dict, carpeta: str) -> tuple[str, dict]:
    r = corre(["claude", "-p", PIDE + json.dumps(c, ensure_ascii=False, indent=1), "--model", MODELO, "--effort", EFFORT,
               "--max-turns", "1", "--output-format", "json", "--tools", ""], 1800, cwd=carpeta)
    d = json.loads(r.stdout) if r.stdout.strip().startswith("{") else {}
    if r.returncode != 0 or d.get("is_error") or not d.get("result"):
        raise RuntimeError(f"claude -p rc={r.returncode} {str(d.get('result') or r.stderr)[:160]}")
    return d["result"].strip(), {k: d.get(k) for k in ("duration_ms", "usage", "total_cost_usd", "modelUsage")}


def main(argv: list[str]) -> int:
    prueba = argv[1] if argv[:1] == ["--prueba"] and len(argv) > 1 else None
    ahora = datetime.now(UTC)
    semana = f"{ahora.isocalendar()[0]}-W{ahora.isocalendar()[1]:02d}"
    with tempfile.TemporaryDirectory(prefix="bot-semanal-") as vacio:
        try:
            a = json.loads(corre(["claude", "auth", "status"], 60).stdout or "{}")
            if not a.get("loggedIn") or a.get("subscriptionType") != "max":
                raise RuntimeError(f"la sesion de Max no vale (loggedIn={a.get('loggedIn')}, plan={a.get('subscriptionType')})")
            sonda = corre(["claude", "-p", "Responde exactamente: OK", "--model", "claude-haiku-4-5-20251001", "--max-turns", "1",
                           "--output-format", "stream-json", "--verbose", "--tools", ""], 300, cwd=vacio)
            u = uso_max(sonda.stdout)
            if u is None:
                raise RuntimeError("no pude leer el uso semanal de Max (sin rate_limit_event): no gasto sin saberlo")
            if u >= TOPE_MAX:
                raise RuntimeError(f"uso semanal de Max {u:.0%} >= {TOPE_MAX:.0%} (el tope de Alejandro)")
            c = json.loads(pathlib.Path(prueba).read_text()) if prueba else cifras(int(time.time() // 60))
            t0 = time.monotonic()
            texto, medida = redacta(c, vacio)
            texto += "\n\nCIFRAS (calculadas por codigo, no redactadas):\n" + calidad.texto(c)
            print(f"redactado en {time.monotonic() - t0:.0f} s · uso semanal de Max antes {u:.0%} · {json.dumps(medida)[:400]}", flush=True)
        except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as e:
            causa = str(e)[:300]
            print(f"CAUSA=SEMANAL {causa}", flush=True)
            if not prueba:
                entrega(f"{semana}.falla", f"{ahora:%Y-%m-%dT%H:%MZ} {causa}\n")
            return 1
    if prueba:
        print(texto)
        return 0
    print(f"entregado {semana}.txt sha256 {entrega(f'{semana}.txt', texto)[:12]}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
