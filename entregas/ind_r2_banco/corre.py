"""Banco IND R2: indicadores de 6/12/24 h sobre ind_r2 con el codigo de <raiz>; tiempos y JSON a out/<etiqueta>-<h>.json.
uso: python corre.py <raiz> <etiqueta> [vueltas] | python corre.py <raiz> explain"""
import asyncio
import hashlib
import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

RAIZ = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(RAIZ))
import app  # noqa: E402

assert Path(app.__file__).resolve().is_relative_to(RAIZ), app.__file__
import asyncpg  # noqa: E402

from app import orderflow_lectura as lec  # noqa: E402

AHORA = datetime(2026, 11, 25, 6, 0, tzinfo=UTC)
OUT = Path(__file__).parent / "out"


async def main() -> None:
    lec._ahora = lambda: AHORA
    conn = await asyncpg.connect(host="/var/run/postgresql", database="ind_r2")
    await conn.execute("SET TIME ZONE 'UTC'")
    if sys.argv[2] == "explain":
        for h in (6, 12, 24):
            await conn.execute("SET jit = off")
            plan = await conn.fetch(
                "EXPLAIN (ANALYZE, BUFFERS) " + lec.SUELTAS_SQL, "BTCUSDT_PERP.A", AHORA - timedelta(hours=h), AHORA,
                lec.TOPE_SUELTAS + 1, "BTC", "binance_usdm", "bybit_linear", lec.VENTANA_EJECUCION)
            print(f"--- {h} h")
            print("\n".join(r[0] for r in plan))
        return
    etiqueta, vueltas = sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 2
    OUT.mkdir(exist_ok=True)
    for h in (6, 12, 24):
        ts = []
        for _ in range(vueltas):
            t = time.perf_counter()
            d = await lec.indicadores(conn, symbol="BTC", desde=lec.iso(AHORA - timedelta(hours=h)),
                                      hasta=lec.iso(AHORA), marco="1h")
            ts.append(time.perf_counter() - t)
        b = json.dumps(d, sort_keys=True, ensure_ascii=False).encode()
        (OUT / f"{etiqueta}-{h}.json").write_bytes(b)
        ev = d["sueltas"]["eventos"]
        print(f"{etiqueta} {h:2d} h  eventos={len(ev)} cinta={sum(e['ejecucion_fuente'] == 'cinta' for e in ev)} "
              f"sin_dato={sum(e['ejecucion_fuente'] == 'sin_dato' for e in ev)}  "
              f"s={' '.join(f'{x:.3f}' for x in ts)}  sha={hashlib.sha256(b).hexdigest()[:16]}")
    await conn.close()


asyncio.run(main())
