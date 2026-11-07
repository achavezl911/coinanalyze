#!/usr/bin/env python3
"""K120-banco · liquidaciones sembradas para K120 y /libro con su ruta de indicadores (campana 150).

    siembra <dsn> <hasta ISO> flujo|libro   en una base de K112-banco (flujo) o de K111-banco (libro): crea las tablas de
                                            las liquidaciones si faltan y siembra, en las 3 h antes de `hasta`, sueltas
                                            alrededor del precio de esa base (orderflow_celda o libro_foto de BTC), mas
                                            un racimo de 6 grandes en un minuto (la ficha «y 2 mas»), una cascada de 5
                                            cortos en 48 s, un grupo de 4 largos (no es cascada), un hueco irrecuperable
                                            de bybit (10 min) y uno recuperado (5 min). Determinista (semilla 120).
    libro --puerto P --db DSN [--sobre D] [--plantado F] [--avisos A]
                                            K111-banco tal cual, y ademas /api/orderflow/indicadores calculada con
                                            app/orderflow_lectura.py sobre la MISMA base (K112-banco._sirve_ruta).
                                            Plantado `retencion_de_12h`: la ruta sirve como si retuviera 12 h.
"""

import importlib.util
import math
import random
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SIMBOLO = "BTCUSDT_PERP.A"
TABLAS = ("liquidations_realtime", "data_gap", "pipeline_heartbeat", "open_interest", "oi_bybit", "funding_rate",
          "predicted_funding_rate", "long_short_ratio", "liquidations")
MID = {"flujo": "SELECT floor(extract(epoch FROM ts) / 60)::bigint * 60, avg(nivel)::float8 FROM orderflow_celda "
                "WHERE symbol = 'BTC' AND ts >= '{a}' AND ts < '{b}' GROUP BY 1 ORDER BY 1",
       "libro": "SELECT floor(extract(epoch FROM ts) / 60)::bigint * 60, avg((compra + venta) / 2)::float8 FROM libro_foto "
                "WHERE symbol = 'BTC' AND ts >= '{a}' AND ts < '{b}' GROUP BY 1 ORDER BY 1"}


def _modulo(nombre: str, fichero: str):
    spec = importlib.util.spec_from_file_location(nombre, AQUI / fichero)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _psql(dsn: str, guion: str, *op: str) -> str:
    r = subprocess.run(["psql", dsn, "-X", "-q", "-v", "ON_ERROR_STOP=1", *op], input=guion, text=True,
                       capture_output=True, timeout=300)
    if r.returncode:
        raise SystemExit(f"psql rc={r.returncode}: {r.stderr[:300]}")
    return r.stdout


def _iso(t: float) -> str:
    return datetime.fromtimestamp(t, UTC).isoformat(timespec="milliseconds")


def siembra(dsn: str, hasta: str, fuente: str) -> int:
    K112 = _modulo("k112_banco", "K112-banco.py")
    ddl = [x.strip() for x in K112.DDL.split(";")]
    ddl = [x.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1) + ";\n" for x in ddl
           if any(x.startswith(f"CREATE TABLE {t} ") for t in TABLAS)]
    _psql(dsn, "".join(ddl))
    b = datetime.fromisoformat(hasta.replace("Z", "+00:00"))
    a = b - timedelta(hours=3)
    filas = _psql(dsn, MID[fuente].format(a=a.isoformat(), b=b.isoformat()), "-At", "-F", "|")
    mids = [(int(t), float(p)) for t, p in (x.split("|") for x in filas.split())]
    if len(mids) < 20:
        raise SystemExit(f"siembra: solo {len(mids)} minutos con precio en [{a}, {b})")
    R = random.Random(120)
    # /flujo 1m ensena los ultimos ~20 minutos: alli van las estructuras; /libro, sus 39 minutos de fotos enteros
    fr = {"flujo": (0.8, 0.72, 0.88, 0.95, 0.6), "libro": (0.5, 0.3, 0.7, 0.85, 0.15)}[fuente]
    pos = {k: mids[int(len(mids) * f)] for k, f in zip(("racimo", "cascada", "cuatro", "hueco", "recuperado"), fr, strict=True)}
    fijos = [pos[k][0] for k in ("racimo", "cascada", "cuatro")]
    ev = []  # (t, exchange, lado, usd, precio)

    def px(mid: float) -> float:
        return round(mid * (1 + R.uniform(-0.0008, 0.0008)), 1)

    for t, mid in mids:
        if any(abs(t - f) <= 180 for f in fijos):
            continue
        if R.random() < 0.3:
            ev.append((t + R.uniform(0, 59.9), R.choice(("binance", "bybit")), R.choice(("long", "short")),
                       round(10000 * math.exp(R.uniform(0, 3.5)) + 0.37, 2), px(mid)))
        for _ in range(R.choice((0, 0, 1, 2))):
            ev.append((t + R.uniform(0, 59.9), R.choice(("binance", "bybit")), R.choice(("long", "short")),
                       round(R.uniform(50, 9000), 2), px(mid)))
    t, mid = pos["racimo"]
    ev += [(t + s, "binance" if k % 3 else "bybit", "long" if k % 2 else "short", round(11000 + 7919.3 * k, 2), px(mid))
           for k, s in enumerate((3, 11, 19, 27, 35, 43))]
    t, mid = pos["cascada"]
    ev += [(t + s, "binance", "short", round(2500 + 311.7 * k, 2), px(mid)) for k, s in enumerate((1, 13, 25, 37, 49))]
    t, mid = pos["cuatro"]
    ev += [(t + s, "bybit", "long", round(15000 + 977.1 * k, 2), px(mid)) for k, s in enumerate((2, 14, 26, 38))]
    h0 = pos["hueco"][0]
    ev = [e for e in ev if not (e[1] == "bybit" and h0 <= e[0] < h0 + 600)]
    ev.sort()
    liq = "\n".join(f"{_iso(t)}\t{SIMBOLO}\t{x}\t{lado}\t{usd}\t{p}\t{round(usd / p, 6)}\tk120:{i}"
                    for i, (t, x, lado, usd, p) in enumerate(ev))
    r0 = pos["recuperado"][0]
    gap = (f"liquidations\tbybit\t{SIMBOLO}\t{_iso(h0)}\t{_iso(h0 + 600)}\tk120\tunrecoverable\n"
           f"liquidations\tbinance\t{SIMBOLO}\t{_iso(r0)}\t{_iso(r0 + 300)}\tk120\trecovered")
    _psql(dsn, f"COPY liquidations_realtime FROM STDIN;\n{liq}\n\\.\nCOPY data_gap FROM STDIN;\n{gap}\n\\.\n")
    print(f"siembra {fuente}: {len(ev)} liquidaciones en {len(mids)} minutos ({sum(e[3] >= 10000 for e in ev)} >= 10 k) · "
          + " · ".join(f"{k} {_iso(v[0])}" for k, v in pos.items()))
    return 0


def recorta_12h(d: dict) -> dict:
    """El plantado: la ruta como si liquidations_realtime retuviera 12 h (la poda vieja de 140)."""
    s = d.get("sueltas") or {}
    borde = time.time() - 12 * 3600
    corte = _iso(borde).replace("+00:00", "Z")
    s["retencion_h"] = 12
    s["eventos"] = [e for e in s.get("eventos", []) if e["ts"] >= corte]
    if s.get("desde_dato", "") < corte:
        s["desde_dato"] = min(corte, d.get("hasta") or corte)
    return d


def libro(argv: list[str]) -> int:
    K111 = _modulo("k111_banco", "K111-banco.py")
    K112 = _modulo("k112_banco", "K112-banco.py")
    import argparse

    import uvicorn
    from starlette.concurrency import run_in_threadpool
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    ap = argparse.ArgumentParser()
    for k in ("--puerto", "--db", "--sobre", "--plantado", "--avisos"):
        ap.add_argument(k, type=int if k == "--puerto" else str, required=k in ("--puerto", "--db"))
    a = ap.parse_args(argv)
    a.modo = "sirve"
    corre = uvicorn.run

    async def indicadores(request):
        st, d = await run_in_threadpool(K112._sirve_ruta, a.db, "/api/orderflow/indicadores", dict(request.query_params))
        try:
            p = Path(a.plantado).read_text().strip() if a.plantado else ""
        except OSError:
            p = ""
        if st == 200 and p == "retencion_de_12h":
            d = recorta_12h(d)
        return JSONResponse(d, status_code=st)

    def con_ruta(app, **kw):
        app.router.routes.insert(0, Route("/api/orderflow/indicadores", indicadores, methods=["GET"]))
        return corre(app, **kw)

    uvicorn.run = con_ruta
    return K111.sirve(a)


def main() -> int:
    if len(sys.argv) == 5 and sys.argv[1] == "siembra" and sys.argv[4] in MID:
        return siembra(*sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "libro":
        return libro(sys.argv[2:])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
