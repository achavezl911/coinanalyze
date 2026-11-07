"""K119 · ayudante de K119-la-sombra-es-el-estudio.sh (lo corre con -S; ver alli QUE JUZGA).

Banco: la muestra real (horas 04-05Z del 2026-10-21, solo SOL) + K119-sintetico.tsv.xz en la base desechable
K119_DB. Las filas se insertan segun su ts como si llegaran, y el camino VIVO del bot (app.bot.sombra.Sombra.tic, con
reinicios y una parada de 30 min) recorre los minutos. Lo que dejo en bot_sombra se compara con K119-esperado.json
(lo que dijo el ESTUDIO sobre los mismos TSV: harness/checks/K119-genera.py). Luego el recalculo (el mismo que se
corre contra 140) se ensaya sobre la base del banco: tiene que dar lo mismo que el bot.
Produccion (si no K119_SIN_PRODUCCION): por bin/prodsql, las filas de bot_sombra de 24 h contra el recalculo desde la
cinta de 140. Sin la tabla en 140: SIN DESPLEGAR, SIN JUZGAR. Sin canal: NO MEDIDO.
rc 0 VERDE · 1 ROJO · 2 NO MEDIDO.
"""
from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import lzma
import os
import pathlib
import subprocess
import sys
import sysconfig
import time
from datetime import UTC, datetime
from decimal import Decimal

REPO, B, DSN = os.environ["K119_REPO"], os.environ["K119_HARNESS"], os.environ["K119_DB"]
SIN_PROD = os.environ.get("K119_SIN_PRODUCCION") == "1"
AQUI = pathlib.Path(REPO) / "harness" / "checks"
sys.path.insert(0, REPO)
sys.path.append(os.environ.get("K119_SITE") or sysconfig.get_path("purelib"))  # sin .pth: el editable no manda
try:
    import asyncpg
except ImportError as e:  # sin dependencias no se mide; un rc=1 de Python no puede pasar por ROJO
    print(f"NO MEDIDO: K119 sin asyncpg: {e}")
    sys.exit(2)
try:
    import app
    from app import anatomia as A
    from app.bot import sombra as sb
except Exception as e:  # el sujeto que no importa es un defecto del sujeto
    print(f"ROJO: K119 app.bot.sombra no importa: {type(e).__name__} {str(e)[:200]}")
    sys.exit(1)

MIN = 60
condenas: list[str] = []
faltas: list[str] = []
dichos: list[str] = []


def hm(t: int) -> str:
    return datetime.fromtimestamp(t, UTC).strftime("%m-%d %H:%MZ")


def ts_dt(s: str) -> datetime:
    base, frac = s[:19], s[19:].split("+")[0]
    us = int((frac[1:] + "000000")[:6]) if frac else 0
    return datetime.fromtimestamp(A._ts(base), UTC).replace(microsecond=us)


def filas_banco(esp: dict) -> list[tuple]:
    xs = (AQUI / "K119-sintetico.tsv.xz").read_bytes()
    if hashlib.sha256(xs).hexdigest() != esp["sintetico_sha256"]:
        raise ValueError("K119-sintetico.tsv.xz no es el que genero K119-esperado.json")
    muestra = pathlib.Path(esp["muestra"])
    h = hashlib.sha256()
    lineas = []
    for hh in esp["muestra_horas"]:
        p = muestra / f"orderflow_cinta-20261021T{hh:02d}Z.tsv.gz"
        h.update(p.read_bytes())
        with gzip.open(p, "rt", encoding="utf-8") as f:
            lineas += [x for x in (ln.rstrip("\n").split("\t") for ln in f) if len(x) > 2 and x[2] == "SOL"]
    if h.hexdigest() != esp["muestra_sha256"]:
        raise ValueError(f"la muestra de {muestra} cambio")
    lineas += [ln.split("\t") for ln in lzma.decompress(xs).decode().splitlines() if ln]
    return [(ts_dt(x[0]), x[1], x[2], Decimal(x[3]), Decimal(x[4]), Decimal(x[5]), x[6] == "t", x[7]) for x in lineas]


def compara(que: str, bot: list[dict], esp: dict):
    """bot: filas {minuto, estado, entrada, exito, neto, salida}. Las finales == las operaciones del estudio; las
    sin_dato, en decisiones que cumplen sin etiqueta; ninguna viva."""
    fin = [f for f in bot if f["estado"] in ("exito", "fracaso")]
    sd = [f for f in bot if f["estado"] == "sin_dato"]
    vivas = [f for f in bot if f["estado"] not in sb.FINALES]
    ops = esp["operaciones"]
    for i in range(max(len(fin), len(ops))):
        a = fin[i] if i < len(fin) else None
        b = ops[i] if i < len(ops) else None
        if a is None or b is None or a["minuto"] != b["minuto"]:
            return condenas.append(f"{que}: disparo {hm(a['minuto']) if a else '-'} ({a and a['estado']}) contra el "
                                   f"estudio {hm(b['minuto']) if b else '-'}")
        if a["entrada"] != b["entrada"] or a["exito"] != b["exito"] or abs(a["neto"] - b["neto"]) > 1e-12 \
                or a["salida"] != b["salida"]:
            return condenas.append(f"{que}: {hm(a['minuto'])} bot (entrada {a['entrada']}, exito {a['exito']}, neto "
                                   f"{a['neto']}, salida {hm(a['salida'])}) contra el estudio (entrada {b['entrada']}, "
                                   f"exito {b['exito']}, neto {b['neto']}, salida {hm(b['salida'])})")
    malas = [hm(f["minuto"]) for f in sd if f["minuto"] not in set(esp["sin_etiqueta"])]
    if malas:
        return condenas.append(f"{que}: sin_dato en {malas}, donde el estudio no dice que falte la etiqueta")
    if vivas:
        return condenas.append(f"{que}: quedan vivas al final {[hm(f['minuto']) for f in vivas]}")
    return f"{len(fin)} operaciones = las del estudio, {len(sd)} sin_dato"


# ---------------------------------------------------------------- el recalculo (banco y 140): SQL de texto
def recalcula(sql, c: sb.Candidata, desde: int, hasta: int, previas: list[dict]) -> list[dict]:
    """Rehace con sb.paso las decisiones (desde, hasta] desde la cinta, por consultas de texto. previas: filas de antes
    de `desde` (para el solape). sql(q) -> filas de str."""
    a, b = desde - c.w * MIN, hasta + (A.HORIZONTE + 1) * MIN
    rng = f"ts >= to_timestamp({a}) AND ts < to_timestamp({b + MIN})"
    hora = {int(float(r[0])): r[1] == "t" for r in sql(
        f"SELECT extract(epoch FROM h), EXISTS (SELECT 1 FROM orderflow_cinta WHERE ts >= h AND ts < h + interval '1 hour')"
        f" FROM generate_series(to_timestamp({a // 3600 * 3600}), to_timestamp({b}), interval '1 hour') h")}
    mm: dict = {}
    venues = ",".join(f"'{v}'" for v in c.venues)
    sb.pliega([(r[0], r[1], r[2], r[3], r[4] == "t") for r in sql(
        f"SELECT ts, venue, precio, usd, compra FROM orderflow_cinta WHERE symbol = '{c.simbolo}' AND {rng} AND venue IN"
        f" ({venues}) AND usd >= {c.minimo} ORDER BY ts, id COLLATE \"C\"")], mm)
    ohlc = {int(float(r[0])): tuple(float(x) for x in r[1:]) for r in sql(
        f"SELECT extract(epoch FROM date_trunc('minute', ts)), (array_agg(precio ORDER BY ts, id COLLATE \"C\"))[1],"
        f" max(precio), min(precio), (array_agg(precio ORDER BY ts DESC, id COLLATE \"C\" DESC))[1] FROM orderflow_cinta"
        f" WHERE symbol = '{c.simbolo}' AND venue = '{A.VENUE_REF}' AND {rng} GROUP BY 1")}

    def flujo(m):
        if not hora.get(m // 3600 * 3600):
            return None
        return mm[m][c.columna] if m in mm else 0.0

    def barra(m):
        return ohlc.get(m) if m <= hasta + MIN else None

    previas = [dict(f) for f in previas]
    nuevas, _ = sb.paso(c, previas, desde - MIN, hasta + MIN, flujo, barra, lote=10**9)
    return nuevas


def psql_local(q: str) -> list[list[str]]:
    r = subprocess.run(["psql", "-X", "-q", "-A", "-t", "-F", "|", "-v", "ON_ERROR_STOP=1", "-d", DSN, "-c",
                        "SET TIME ZONE 'UTC'; " + q], capture_output=True, text=True, timeout=300)
    if r.returncode:
        raise RuntimeError(f"psql rc={r.returncode} {r.stderr.strip()[-160:]}")
    return [ln.split("|") for ln in r.stdout.splitlines() if ln.strip() and ln != "SET"]


def prodsql(q: str) -> list[list[str]]:
    r = subprocess.run(["sh", f"{B}/bin/prodsql", q], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300, env={**os.environ, "TODO": "1"})
    if r.returncode:
        raise RuntimeError(f"prodsql rc={r.returncode} {(r.stderr or r.stdout).strip()[-160:]}")
    return [ln.split("|") for ln in r.stdout.splitlines() if ln.strip()]


def filas_sql(sql, c: sb.Candidata, desde: int | None = None) -> tuple[list[dict], int, int]:
    """bot_sombra de la candidata (todas, o las de minuto >= desde y la anterior), con (desde, hasta) del cursor."""
    k = sql(f"SELECT extract(epoch FROM desde), extract(epoch FROM hasta) FROM bot_sombra_candidata WHERE candidata ="
            f" '{c.sha}' AND indice = {c.indice}")
    if not k:
        return [], 0, 0
    filas = [{"minuto": int(float(r[0])), "estado": r[1], "entrada": float(r[2]) if r[2] else None,
              "exito": int(r[3]) if r[3] else None, "neto": float(r[4]) if r[4] else None,
              "salida": int(float(r[5])) if r[5] else None} for r in sql(
        "SELECT extract(epoch FROM minuto), estado, entrada, exito, neto, extract(epoch FROM salida) FROM bot_sombra"
        f" WHERE candidata = '{c.sha}' AND indice = {c.indice} ORDER BY minuto")]
    return filas, int(float(k[0][0])), int(float(k[0][1]))


def coincide(que: str, bot: list[dict], rec: list[dict]):
    clave = lambda f: (f["minuto"], f["estado"], f["entrada"], f["exito"], f["salida"])  # noqa: E731
    if [clave(f) for f in bot] != [clave(f) for f in rec] or any(
            (x["neto"] is None) != (y["neto"] is None) or (x["neto"] is not None and abs(x["neto"] - y["neto"]) > 1e-12)
            for x, y in zip(bot, rec, strict=False)):
        d = next((i for i, (x, y) in enumerate(zip(bot, rec, strict=False)) if clave(x) != clave(y)),
                 min(len(bot), len(rec)))
        x, y = (bot[d] if d < len(bot) else None), (rec[d] if d < len(rec) else None)
        return condenas.append(f"{que}: el bot dice {x and (hm(x['minuto']), x['estado'], x['neto'])} y el recalculo"
                               f" desde la cinta {y and (hm(y['minuto']), y['estado'], y['neto'])}")
    return f"{len(bot)} filas = recalculo"


# ---------------------------------------------------------------- el banco
async def banco(esp: dict):
    c = sb.carga()[0]
    if c.sha != esp["candidata_sha256"]:
        condenas.append(f"banco: la candidata del bot ({c.sha[:12]}) no es la que midio el estudio "
                        f"({esp['candidata_sha256'][:12]})")
    filas = filas_banco(esp)
    T0 = A._ts(esp["dia"])
    cx = await asyncpg.connect(DSN)
    try:
        await cx.execute("SELECT ensure_temporal_partitions($1::timestamptz, 1, 1)", datetime.fromtimestamp(T0 + 43200, UTC))
        await cx.execute("CREATE TEMP TABLE banco (LIKE orderflow_cinta)")
        await cx.copy_records_to_table("banco", records=filas,
                                       columns=["ts", "venue", "symbol", "precio", "base", "usd", "compra", "id"])
        pool = await asyncpg.create_pool(DSN, min_size=1, max_size=2)
        s, tiempos, vistas, previo = sb.Sombra(pool, {}), [], [], T0
        for m in range(59, 1140):
            ahora = T0 + (m + 1) * MIN + sb.CIERRE_S
            await cx.execute("INSERT INTO orderflow_cinta SELECT * FROM banco WHERE ts >= to_timestamp($1) AND ts <"
                             " to_timestamp($2)", float(previo), float(ahora))
            previo = ahora
            if 300 <= m < 330:
                continue                                    # el bot parado 30 min: se pone al dia
            if m in (600, 770, 1000):
                s = sb.Sombra(pool, {})                     # reinicio: el cursor y las vivas salen de la tabla
            t = time.perf_counter()
            vistas += [f["minuto"] for f in await s.tic(ahora)]
            tiempos.append(time.perf_counter() - t)
        await pool.close()
        tiempos.sort()
        p95 = tiempos[int(0.95 * (len(tiempos) - 1))]
        dichos.append(f"tic: {len(tiempos)} tics, p95 {p95 * 1000:.1f} ms, max {tiempos[-1] * 1000:.1f} ms")
        bot, desde, hasta = filas_sql(psql_local, c)
        if [f["minuto"] for f in bot] != vistas:
            condenas.append(f"banco: tic devolvio {[hm(x) for x in vistas]} y la tabla tiene "
                            f"{[hm(f['minuto']) for f in bot]}")
        r = compara("banco", bot, esp)
        if r:
            dichos.append("banco: " + r)
        # el recalculo que se corre contra 140, ensayado aqui: tiene que dar lo que el bot
        r = coincide("banco, recalculo", bot, recalcula(psql_local, c, desde, hasta, []))
        if r:
            dichos.append("banco, recalculo: " + r)
    finally:
        await cx.close()


def produccion():
    c = sb.carga()[0]
    r = prodsql("SELECT to_regclass('bot_sombra') IS NOT NULL")
    if not r or r[0][0] not in ("t", "f"):
        return faltas.append(f"produccion: prodsql sin respuesta legible ({r[:1]!r})")
    if r[0][0] == "f":
        return dichos.append("produccion: bot_sombra no existe en 140 (SIN DESPLEGAR, SIN JUZGAR)")
    todas, desde, hasta = filas_sql(prodsql, c)
    if not desde:
        return dichos.append("produccion: la candidata aun no arranco en 140 (SIN JUZGAR)")
    ini = max(desde, (hasta - 24 * 3600) // MIN * MIN)
    previas = [f for f in todas if f["minuto"] < ini][-1:]
    bot = [f for f in todas if ini <= f["minuto"] <= hasta]
    r = coincide(f"produccion {hm(ini)}..{hm(hasta)}", bot, recalcula(prodsql, c, ini, hasta, previas))
    if r:
        dichos.append(f"produccion {hm(ini)}..{hm(hasta)}: " + r)


def main() -> int:
    if not pathlib.Path(app.__file__).resolve().is_relative_to(pathlib.Path(REPO).resolve()):
        print(f"NO MEDIDO: K119 importe app/ de {app.__file__}, no de {REPO}")
        return 2
    try:
        esp = json.loads((AQUI / "K119-esperado.json").read_text())
    except OSError as e:
        print(f"NO MEDIDO: K119 sin K119-esperado.json ({e})")
        return 2
    try:
        asyncio.run(banco(esp))
    except (OSError, ValueError) as e:
        faltas.append(f"banco: {type(e).__name__} {str(e)[:200]}")
    except Exception as e:  # el camino vivo que revienta es un defecto del sujeto
        condenas.append(f"banco: el bot cayo: {type(e).__name__} {str(e)[:200]}")
    if SIN_PROD:
        dichos.append("produccion: no se mira (K119_SIN_PRODUCCION=1)")
    else:
        try:
            produccion()
        except Exception as e:
            faltas.append(f"produccion: {type(e).__name__} {str(e)[:200]}")
    cola = " | ".join(dichos)
    if condenas:
        print(f"ROJO: K119 {condenas[0]}")
        for x in condenas[1:] + faltas:
            print(f"  {x}")
        print(f"  {cola}")
        return 1
    if faltas:
        print(f"NO MEDIDO: K119 {faltas[0]}")
        for x in faltas[1:]:
            print(f"  {x}")
        print(f"  {cola}")
        return 2
    print(f"VERDE: K119 la sombra es el estudio | {cola}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
