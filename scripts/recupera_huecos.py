#!/usr/bin/env python3
"""Recuperador: pedirle a la fuente lo que falta de los huecos de cadencia MIENTRAS aun lo sirve.

POR QUE HACE FALTA. La fuente sirve ohlcv 1min unas 24 h hacia atras (long_short_ratio 5min, 200 h).
El repaso (resweep_cadence_gaps.py) se lanza a mano: un apagon de la ingesta de una noche se queda en
huecos 'unresolved' que nadie pide hasta que el reloj de la fuente se los lleva (fable-f6, R2).

QUE HACE, cada vez que lo lanza coinalyze-recupera.timer:
  1. Lee los huecos de cadencia sin resolver que aun estan dentro del horizonte de su fuente, y funde
     los de la misma identidad (dos detectores apuntan la misma ausencia como dos filas).
  2. Recorta cada hueco al horizonte y pide SOLO lo que falta en el almacen, en trozos cortados del
     propio hueco (nunca de una rejilla fija: ese era el defecto del repaso). Lo mas viejo, primero:
     es lo que antes se pierde. Con un tope de peticiones por corrida.
  3. Guarda lo devuelto y corre UN reconcile sobre el hueco entero, con lo que hay guardado.
  4. Escribe un latido (hora, pedidas, pendientes y el pendiente con menos reloj) que lee la vigia.

LO QUE NO HACE, a proposito: no archiva y no marca irrecuperable. Que la fuente no conteste ahora no
prueba nada (puede estar caida); eso sigue siendo cosa del repaso con --archive-exhausted y su control.
La excepcion es --parte, a mano y nunca en el timer: ver el bloque "--parte" (recupera-r1).

    scripts/recupera_huecos.py                         # una corrida; el latido en $RECUPERA_LATIDO
    scripts/recupera_huecos.py --parte --seco [--gap ID ... | --desde T --hasta T]   # cuenta, no escribe
    scripts/recupera_huecos.py --parte [--gap ID ... | --desde T --hasta T]          # parte, concilia, cierra
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.coinalyze import CoinalyzeClient, PostgresSlidingWindowRateLimiter  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.data_gaps import (  # noqa: E402
    BLOQUEA_SQL,
    PARTITION_DETECTION_SOURCE,
    archive_beyond_source_horizon,
    close_partitioned_gap,
    expected_buckets,
    missing_cadence_windows,
    partition_runs,
    record_data_gap,
)
from app.db import create_pool  # noqa: E402
from app.ingest import source_response_buckets  # noqa: E402
from scripts.resweep_cadence_gaps import PLANS, _control, reconcilia_hueco_entero  # noqa: E402

RECUPERA_DETECTION_SOURCE = "recupera_v1"
# Hasta donde contesta la fuente, por plan. El de ohlcv 1min es el SUELO medido (24-48 h, ver el
# docstring del repaso): pedir mas atras no devuelve nada y solo gasta cupo.
# El de ohlcv 5min NO esta medido: es CITA. harness/hechos.tsv:261 (2026-08-25) dice que el 1min
# «NO son 8-9 dias como en 5min», y el dueno lo relleno con backfill_ohlcv.py en esa misma
# ventana tras el apagon de 11-16. Se toma el SUELO de esos 8-9 dias: pedir dentro de 192 h no
# gasta cupo en vano, y lo que quede entre 192 h y el borde real lo coge la ingesta o --parte.
HORIZONTE_OHLCV_5MIN = timedelta(hours=192)
HORIZONTE: dict[tuple[str, str], timedelta] = {
    ("ohlcv_1min", "1min"): timedelta(hours=24),
    ("long_short_ratio", "5min"): timedelta(hours=200),
    ("ohlcv_5min", "5min"): HORIZONTE_OHLCV_5MIN,
}
# Lo de los ultimos minutos es de la ingesta en vivo: no se le disputa.
FRESCO = timedelta(minutes=10)
LIMITE_PETICIONES = 60
LATIDO = Path(os.environ.get("RECUPERA_LATIDO", "/var/lib/coinalyze-recupera/latido.json"))


def _techo(t: datetime, cadence: timedelta) -> datetime:
    """El primer bucket >= t (los buckets van alineados a la cadencia desde la epoca)."""
    paso = int(cadence.total_seconds())
    s = int(t.timestamp())
    return datetime.fromtimestamp(-(-s // paso) * paso, UTC)


async def _huecos(conn, plan_key, desde: datetime, permitidos) -> list[dict]:
    """Huecos sin resolver de un plan que aun tocan el horizonte, fundidos por identidad."""
    filas = await conn.fetch(
        """
        SELECT feed, exchange, market, symbol, granularity, start_ts, end_ts FROM data_gap
        WHERE status='unresolved' AND feed_class='cadence' AND evidence_type='missing_interval'
          AND feed=$1 AND granularity=$2 AND end_ts > $3 AND symbol = ANY($4::text[])
        ORDER BY exchange, market, symbol, start_ts, end_ts
        """,
        plan_key[0], plan_key[1], desde, sorted(permitidos),
    )
    uniones: list[dict] = []
    for f in filas:
        ident = {k: f[k] for k in ("feed", "exchange", "market", "symbol", "granularity")}
        if uniones and uniones[-1]["ident"] == ident and f["start_ts"] <= uniones[-1]["fin"]:
            uniones[-1]["fin"] = max(uniones[-1]["fin"], f["end_ts"])
        else:
            uniones.append({"ident": ident, "ini": f["start_ts"], "fin": f["end_ts"]})
    return uniones


async def _faltan(conn, plan, u) -> list[tuple[datetime, datetime]]:
    if u["lo"] >= u["hi"]:
        return []
    guardado = await plan.almacenado(conn, u["ident"], u["lo"], u["hi"])
    return missing_cadence_windows(guardado, start=u["lo"], end=u["hi"], cadence=plan.cadence)


async def cierra_padres_teselados(conn, permitidos, ids: list[int] | None = None) -> dict:
    """Cierra cada padre sin resolver que ya tiene hijos de particion encima (huecos-r1, H-01 y N2). Que cierre o no lo
    decide close_partitioned_gap contra la tabla: si los hijos lo TESELAN se cierra, aunque alguno siga abierto (ese
    bloquea su tramo solo). No pide nada a la fuente ni archiva nada: por eso va tambien en el timer."""
    filas = await conn.fetch(
        """
        SELECT g.id FROM data_gap g
        WHERE g.status='unresolved' AND g.feed_class='cadence' AND g.detection_source <> $1
          AND g.symbol = ANY($2::text[]) AND ($3::bigint[] IS NULL OR g.id = ANY($3::bigint[]))
          AND EXISTS (SELECT 1 FROM data_gap h
                       WHERE h.detection_source=$1 AND h.feed=g.feed AND h.exchange=g.exchange AND h.market=g.market
                         AND h.symbol=g.symbol AND h.granularity=g.granularity
                         AND h.start_ts < g.end_ts AND h.end_ts > g.start_ts)
        ORDER BY g.id
        """,
        PARTITION_DETECTION_SOURCE, sorted(permitidos), ids,
    )
    cerrados, abiertos = 0, 0
    for f in filas:
        try:
            if await close_partitioned_gap(conn, gap_id=f["id"], proof_source=PARTE_PROOF) == "unrecoverable":
                cerrados += 1
        except ValueError:
            abiertos += 1
    return {"padres_cerrados": cerrados, "padres_abiertos": abiertos}


async def recupera(conn, client, *, ahora: datetime, permitidos, limite: int = LIMITE_PETICIONES) -> dict:
    resumen: dict = {"pedidas": 0, "filas": 0, "recuperados": 0, "cortado_por_tope": False}
    resumen.update(await cierra_padres_teselados(conn, permitidos))
    # Buckets que la fuente NO trae en una respuesta que SI trae otros: es su salto, no un pendiente nuestro. No se
    # archivan (eso pide la prueba del repaso), pero tampoco cuentan como recuperables para el reloj de la vigia.
    saltados: set[tuple] = set()
    uniones: list[dict] = []
    for key, plan in PLANS.items():
        h = HORIZONTE.get(key)
        if h is None:
            continue
        desde = _techo(ahora - h, plan.cadence)
        for u in await _huecos(conn, key, desde, permitidos):
            u.update(plan=plan, horizonte=h, lo=max(u["ini"], desde), hi=min(u["fin"], ahora - FRESCO))
            uniones.append(u)
    uniones.sort(key=lambda u: u["lo"])  # lo mas viejo se pierde antes

    for u in uniones:
        plan, ident = u["plan"], u["ident"]
        mapa = {ident["symbol"]: ident["symbol"]}
        guardo = False
        for a, b in await _faltan(conn, plan, u):
            cursor = a
            while cursor < b:
                if resumen["pedidas"] >= limite:
                    resumen["cortado_por_tope"] = True
                    break
                fin = min(cursor + plan.chunk, b)
                s, e = int(cursor.timestamp()), int(fin.timestamp())
                resumen["pedidas"] += 1
                payload = await client.history(plan.endpoint, [ident["symbol"]], interval=plan.interval, start_ts=s, end_ts=e)
                devueltos = source_response_buckets(payload, mapa, s, e).get(ident["symbol"], set())
                if devueltos:
                    resumen["filas"] += await plan.store(conn, payload, mapa, s, e, {})
                    guardo = True
                    t = cursor
                    while t < fin:
                        if t not in devueltos:
                            saltados.add((tuple(ident.values()), t))
                        t += plan.cadence
                cursor = fin
            if resumen["cortado_por_tope"]:
                break
        if guardo:
            cobertura = await reconcilia_hueco_entero(conn, plan, ident, u["ini"], u["fin"], RECUPERA_DETECTION_SOURCE)
            resumen["recuperados"] += cobertura.recovered_gaps
        if resumen["cortado_por_tope"]:
            break

    # Lo que sigue pendiente y aun se puede pedir, y cuanto reloj le queda: lo que vigila la vigia.
    pendientes, urgente = 0, None
    for u in uniones:
        primero = None
        for a, b in await _faltan(conn, u["plan"], u):
            t = a
            while t < b and primero is None:
                if (tuple(u["ident"].values()), t) not in saltados:
                    primero = t
                t += u["plan"].cadence
            if primero is not None:
                break
        if primero is None:
            continue
        pendientes += 1
        vence = primero + u["horizonte"]
        if urgente is None or vence < urgente["vence"]:
            urgente = {"feed": u["ident"]["feed"], "symbol": u["ident"]["symbol"], "inicio": u["ini"], "fin": u["fin"], "vence": vence}
    resumen["pendientes"] = pendientes
    resumen["saltados_por_la_fuente"] = len(saltados)
    resumen["urgente"] = None if urgente is None else {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in urgente.items()}
    return resumen


# --- --parte: el hueco que CRUZA el reloj de la fuente (recupera-r1) -------------------------------------------------
# El apagon del 2026-11-16 dejo padres de 34 h con las ultimas ~24 h ya en la base. reconcile solo recupera una fila con
# TODOS sus buckets, asi que el padre no se recupera nunca y tapa los minutos que si estan. Este modo lo PARTE: hijos
# sobre una rejilla COMUN a todas las filas anidadas de la union (si cada padre se partiese por su cuenta los hijos se
# solaparian y K04 condenaria), cortada en los bordes de cada fila, donde cambia la presencia en la base y en el borde
# del reloj. Los hijos presentes se recuperan con la base; los ausentes se piden a la fuente; los ausentes MAS ALLA del
# reloj que vuelven vacios pasan a 'unrecoverable' con provider_horizon_exhausted y su control (la prueba que K04
# re-deriva), y SOLO con control positivo: sin el, se quedan 'unresolved' y bloquean SU tramo, nada mas (huecos-r1).
# El padre se cierra con close_partitioned_gap, que lo verifica contra la tabla. PARTIR no va en el timer: archiva
# 'unrecoverable', y eso es una decision que se toma mirando primero el modo en seco. CERRAR un padre ya teselado si va.
PARTE_PROOF = "recupera_huecos --parte"


async def _uniones_parte(conn, plan_key, permitidos, gaps, desde, hasta) -> list[dict]:
    """Uniones de filas sin resolver de un plan, con sus filas. Se filtra DESPUES de fundir: pedir un gap id trae
    tambien las filas anidadas de otros detectores, que tienen que entrar en la misma rejilla."""
    filas = await conn.fetch(
        """
        SELECT id, feed, exchange, market, symbol, granularity, start_ts, end_ts FROM data_gap
        WHERE status='unresolved' AND feed_class='cadence' AND evidence_type='missing_interval'
          AND feed=$1 AND granularity=$2 AND symbol = ANY($3::text[])
        ORDER BY exchange, market, symbol, start_ts, end_ts
        """,
        plan_key[0], plan_key[1], sorted(permitidos),
    )
    uniones: list[dict] = []
    for f in filas:
        ident = {k: f[k] for k in ("feed", "exchange", "market", "symbol", "granularity")}
        fila = (int(f["id"]), f["start_ts"], f["end_ts"])
        if uniones and uniones[-1]["ident"] == ident and f["start_ts"] <= uniones[-1]["fin"]:
            uniones[-1]["fin"] = max(uniones[-1]["fin"], f["end_ts"])
            uniones[-1]["filas"].append(fila)
        else:
            uniones.append({"ident": ident, "ini": f["start_ts"], "fin": f["end_ts"], "filas": [fila]})

    def elegida(u) -> bool:
        if gaps and not any(i in gaps for i, _, _ in u["filas"]):
            return False
        if desde is not None and u["fin"] <= desde:
            return False
        return hasta is None or u["ini"] < hasta

    return [u for u in uniones if elegida(u)]


def _cuenta(presentes: set[datetime], ini: datetime, fin: datetime, cadence: timedelta) -> tuple[int, int]:
    """(esperados, presentes) de [ini, fin)."""
    esperados = expected_buckets(ini, fin, cadence)
    return esperados, sum(1 for t in presentes if ini <= t < fin)


async def parte(
    conn, client, *, ahora: datetime, permitidos, limite: int = LIMITE_PETICIONES, seco: bool = True,
    gaps: frozenset[int] = frozenset(), desde: datetime | None = None, hasta: datetime | None = None,
) -> dict:
    resumen: dict = {"seco": seco, "pedidas": 0, "cortado_por_tope": False, "uniones": []}
    controles: dict[tuple, tuple[int, datetime, datetime]] = {}
    for key, plan in PLANS.items():
        h = HORIZONTE.get(key)
        if h is None:
            continue
        borde = _techo(ahora - h, plan.cadence)
        for u in await _uniones_parte(conn, key, permitidos, gaps, desde, hasta):
            ident, ini, fin = u["ident"], u["ini"], u["fin"]
            info: dict = {"feed": ident["feed"], "symbol": ident["symbol"], "inicio": ini.isoformat(),
                          "fin": fin.isoformat(), "filas": len(u["filas"]), "borde_reloj": borde.isoformat()}
            resumen["uniones"].append(info)
            if ini >= borde:
                info["salta"] = "dentro_del_reloj"  # eso lo pide la corrida normal
                continue
            if fin > ahora - FRESCO:
                info["salta"] = "en_vivo"
                continue
            presentes = await plan.almacenado(conn, ident, ini, fin)
            tramos = partition_runs(ini, fin, plan.cadence, presentes)
            esperados, hay = _cuenta(presentes, ini, fin, plan.cadence)
            mixtos = [i for i, s, e in u["filas"] if 0 < _cuenta(presentes, s, e, plan.cadence)[1] < expected_buckets(s, e, plan.cadence)]
            viejos = sum(expected_buckets(a, min(b, borde), plan.cadence) for a, b, x in tramos if not x and a < borde)
            info.update(minutos_en_base=hay, minutos_sin_dato=esperados - hay, sin_dato_fuera_del_reloj=viejos,
                        padres_mixtos=mixtos)
            if not mixtos:
                info["salta"] = "sin_padre_mixto"  # todo presente lo recupera la corrida normal; todo ausente no se parte
                continue
            if seco:
                # Lo que destaparia si todos los padres cierran: lo presente que no tapa NINGUNA otra fila que bloquee.
                otras = await conn.fetch(
                    f"SELECT start_ts, end_ts FROM data_gap WHERE feed=$1 AND exchange=$2 AND market=$3 AND symbol=$4"
                    f" AND granularity=$5 AND {BLOQUEA_SQL} AND start_ts < $7 AND end_ts > $6"  # noqa: S608 -- constante
                    " AND NOT id = ANY($8::bigint[])",
                    *ident.values(), ini, fin, [i for i, _, _ in u["filas"]],
                )
                info["destaparia"] = sum(1 for t in presentes if not any(r["start_ts"] <= t < r["end_ts"] for r in otras))
                resumen["destaparia"] = resumen.get("destaparia", 0) + info["destaparia"]
                continue

            cortes = {ini, fin, borde} | {s for _, s, _ in u["filas"]} | {e for _, _, e in u["filas"]}
            cortes |= {a for a, _, _ in tramos}
            cortes = sorted(c for c in cortes if ini <= c <= fin)
            hijos = [(a, b, a in presentes) for a, b in zip(cortes, cortes[1:], strict=False)]
            previos = {
                (r["start_ts"], r["end_ts"]) for r in await conn.fetch(
                    "SELECT start_ts, end_ts FROM data_gap WHERE feed=$1 AND exchange=$2 AND market=$3 AND symbol=$4"
                    " AND granularity=$5 AND detection_source=$6 AND start_ts < $8 AND end_ts > $7",
                    *ident.values(), PARTITION_DETECTION_SOURCE, ini, fin,
                )
            }
            if previos and previos != {(a, b) for a, b, _ in hijos}:
                # Partir otra vez solaparia hijos (K04 condena); saltarlo sin mas lo dejaba abierto PARA SIEMPRE (N2).
                info["salta"] = "particion_previa_distinta"
                info.update(await cierra_padres_teselados(conn, permitidos, [i for i, _, _ in u["filas"]]))
                continue
            async with conn.transaction():
                for a, b, x in hijos:
                    await record_data_gap(
                        conn, feed=ident["feed"], feed_class="cadence", exchange=ident["exchange"],
                        market=ident["market"], symbol=ident["symbol"], granularity=ident["granularity"],
                        start=a, end=b, evidence_type="missing_interval",
                        detection_reason=(
                            f"{PARTE_PROOF}: coverage measured in the store, {'present' if x else 'absent'} run; "
                            f"source horizon border {borde.isoformat()}; parents {mixtos}"
                        ),
                        detection_source=PARTITION_DETECTION_SOURCE, expected_cadence=plan.cadence,
                    )
            info["hijos"] = len(hijos)
            await reconcilia_hueco_entero(conn, plan, ident, ini, fin, RECUPERA_DETECTION_SOURCE)

            # Los ausentes, a la fuente, en tramos que no cruzan el borde: el de fuera vacio es la prueba de horizonte.
            ausentes: list[list] = []
            for a, b, x in hijos:
                if x:
                    continue
                if ausentes and ausentes[-1][1] == a and (a < borde) == (ausentes[-1][0] < borde):
                    ausentes[-1][1] = b
                else:
                    ausentes.append([a, b, 0, True])  # inicio, fin, filas devueltas, pedido entero
            mapa = {ident["symbol"]: ident["symbol"]}
            for run in ausentes:
                cursor = run[0]
                while cursor < run[1]:
                    if resumen["pedidas"] >= limite:
                        resumen["cortado_por_tope"] = True
                        run[3] = False
                        break
                    tope = min(cursor + plan.chunk, run[1])
                    s, e = int(cursor.timestamp()), int(tope.timestamp())
                    resumen["pedidas"] += 1
                    payload = await client.history(plan.endpoint, [ident["symbol"]], interval=plan.interval, start_ts=s, end_ts=e)
                    devueltos = source_response_buckets(payload, mapa, s, e).get(ident["symbol"], set())
                    if devueltos:
                        await plan.store(conn, payload, mapa, s, e, {})
                        run[2] += len(devueltos)
                    cursor = tope
            if any(run[2] for run in ausentes):
                await reconcilia_hueco_entero(conn, plan, ident, ini, fin, RECUPERA_DETECTION_SOURCE)

            archivados = 0
            for a, b, devueltas, entero in ausentes:
                if b > borde or devueltas or not entero:
                    continue
                clave = tuple(ident.values())
                if clave not in controles:
                    resumen["pedidas"] += 1
                    controles[clave] = await _control(client, plan, ident["symbol"])
                filas_control, c_ini, c_fin = controles[clave]
                if filas_control <= 0:
                    info["fuente_muda"] = True  # sin control no hay prueba: se queda unresolved
                    continue
                archivados += await archive_beyond_source_horizon(
                    conn, **ident, window_start=a, window_end=b,
                    control_start=c_ini, control_end=c_fin, control_returned_rows=filas_control,
                )
            info["archivados_fuera_del_reloj"] = archivados

            cerrados, abiertos = 0, 0
            for gap_id in mixtos:
                try:
                    if await close_partitioned_gap(conn, gap_id=gap_id, proof_source=PARTE_PROOF) == "unrecoverable":
                        cerrados += 1
                except ValueError:
                    abiertos += 1
            info.update(padres_cerrados=cerrados, padres_abiertos=abiertos)
            tapan = await conn.fetch(
                f"SELECT start_ts, end_ts FROM data_gap WHERE feed=$1 AND exchange=$2 AND market=$3 AND symbol=$4"
                f" AND granularity=$5 AND {BLOQUEA_SQL} AND start_ts < $7 AND end_ts > $6",  # noqa: S608 -- constante
                *ident.values(), ini, fin,
            )
            presentes = await plan.almacenado(conn, ident, ini, fin)
            info["minutos_destapados"] = sum(1 for t in presentes if not any(r["start_ts"] <= t < r["end_ts"] for r in tapan))
            resumen["destapados"] = resumen.get("destapados", 0) + info["minutos_destapados"]
    return resumen


def escribe_latido(path: Path, datos: dict) -> None:
    """Entero o nada: la vigia nunca lee un latido a medio escribir."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(datos, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


async def run(limite: int, opciones: dict | None = None) -> dict:
    settings = get_settings()
    pool = await create_pool(settings, application_name="coinalyze-recupera")
    limiter = PostgresSlidingWindowRateLimiter(pool, settings.COINALYZE_RATE_LIMIT_UNITS)
    try:
        async with CoinalyzeClient(settings.COINALYZE_BASE_URL, settings.API_KEY, limiter) as client:
            async with pool.acquire() as conn:
                ahora = datetime.now(UTC)
                permitidos = frozenset(settings.SYMBOLS)
                if opciones is None:
                    resumen = await recupera(conn, client, ahora=ahora, permitidos=permitidos, limite=limite)
                elif opciones["seco"]:
                    # En seco ni pregunta a la fuente ni escribe: la transaccion de solo lectura lo garantiza.
                    async with conn.transaction(readonly=True):
                        resumen = await parte(conn, client, ahora=ahora, permitidos=permitidos, limite=limite, **opciones)
                else:
                    resumen = await parte(conn, client, ahora=ahora, permitidos=permitidos, limite=limite, **opciones)
        resumen["ts"] = ahora.isoformat()
        return resumen
    finally:
        await pool.close()


def _utc(texto: str) -> datetime:
    t = datetime.fromisoformat(texto)
    if t.tzinfo is None:
        raise argparse.ArgumentTypeError(f"{texto!r} sin zona: escribelo con Z o +00:00")
    return t.astimezone(UTC)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--limite", type=int, default=LIMITE_PETICIONES, help="peticiones a la fuente por corrida")
    p.add_argument("--parte", action="store_true", help="partir los huecos que cruzan el reloj de la fuente (recupera-r1)")
    p.add_argument("--seco", action="store_true", help="con --parte: solo cuenta lo que destaparia; no escribe ni pide")
    p.add_argument("--gap", type=int, action="append", default=[], help="con --parte: solo la union que contiene este id")
    p.add_argument("--desde", type=_utc, help="con --parte: solo uniones que acaban despues (ISO con zona)")
    p.add_argument("--hasta", type=_utc, help="con --parte: solo uniones que empiezan antes (ISO con zona)")
    a = p.parse_args()
    if not a.parte:
        if a.seco or a.gap or a.desde or a.hasta:
            p.error("--seco, --gap, --desde y --hasta van con --parte")
        resumen = asyncio.run(run(a.limite))
        # El latido solo si la corrida acabo: si falla, la vigia ve que deja de latir.
        escribe_latido(LATIDO, resumen)
    else:
        # --parte es a mano y no escribe latido: el de la vigia es el de la corrida normal.
        opciones = {"seco": a.seco, "gaps": frozenset(a.gap), "desde": a.desde, "hasta": a.hasta}
        resumen = asyncio.run(run(a.limite, opciones))
    print(json.dumps(resumen, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
