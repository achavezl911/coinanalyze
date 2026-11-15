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

    scripts/recupera_huecos.py            # una corrida; el latido en $RECUPERA_LATIDO
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
from app.data_gaps import missing_cadence_windows  # noqa: E402
from app.db import create_pool  # noqa: E402
from app.ingest import source_response_buckets  # noqa: E402
from scripts.resweep_cadence_gaps import PLANS, reconcilia_hueco_entero  # noqa: E402

RECUPERA_DETECTION_SOURCE = "recupera_v1"
# Hasta donde contesta la fuente, por plan. El de ohlcv 1min es el SUELO medido (24-48 h, ver el
# docstring del repaso): pedir mas atras no devuelve nada y solo gasta cupo.
HORIZONTE: dict[tuple[str, str], timedelta] = {
    ("ohlcv_1min", "1min"): timedelta(hours=24),
    ("long_short_ratio", "5min"): timedelta(hours=200),
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


async def recupera(conn, client, *, ahora: datetime, permitidos, limite: int = LIMITE_PETICIONES) -> dict:
    resumen: dict = {"pedidas": 0, "filas": 0, "recuperados": 0, "cortado_por_tope": False}
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


def escribe_latido(path: Path, datos: dict) -> None:
    """Entero o nada: la vigia nunca lee un latido a medio escribir."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(datos, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


async def run(limite: int) -> dict:
    settings = get_settings()
    pool = await create_pool(settings, application_name="coinalyze-recupera")
    limiter = PostgresSlidingWindowRateLimiter(pool, settings.COINALYZE_RATE_LIMIT_UNITS)
    try:
        async with CoinalyzeClient(settings.COINALYZE_BASE_URL, settings.API_KEY, limiter) as client:
            async with pool.acquire() as conn:
                ahora = datetime.now(UTC)
                resumen = await recupera(conn, client, ahora=ahora, permitidos=frozenset(settings.SYMBOLS), limite=limite)
        resumen["ts"] = ahora.isoformat()
        return resumen
    finally:
        await pool.close()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--limite", type=int, default=LIMITE_PETICIONES, help="peticiones a la fuente por corrida")
    a = p.parse_args()
    resumen = asyncio.run(run(a.limite))
    # El latido solo si la corrida acabo: si falla, la vigia ve que deja de latir.
    escribe_latido(LATIDO, resumen)
    print(json.dumps(resumen, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
