"""Baja las velas de 140 que uso Fable V3 (5 min x 2000 y 4 h x 400) por harness/bin/api (GET)."""
import os
import subprocess
import sys
from pathlib import Path

API = "/srv/coinanalyze/harness/bin/api"
D = Path(__file__).resolve().parent
for s in ("BTCUSDT_PERP.A", "ETHUSDT_PERP.A", "SOLUSDT_PERP.A"):
    for nombre, iv, lim in (("v5", "5min", 2000), ("v4h", "4hour", 400)):
        r = subprocess.run(["bash", API, f"/api/ohlcv?symbol={s}&interval={iv}&limit={lim}"],
                           capture_output=True, text=True, env={**os.environ, "TODO": "1"}, check=False)
        (D / f"{nombre}-{s}.json").write_text(r.stdout)
        print(nombre, s, r.returncode, len(r.stdout), r.stderr[:120], file=sys.stderr)
