"""% que cumple «retroceso previo» y «defensa del nivel» con main y con la rama, en las velas de 140.

Uso: .venv/bin/python antes_despues.py REPO SETUPS_MAIN.py
"""
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(REPO))
import app.scalp_logic as SL  # noqa: E402
import app.setups as S  # noqa: E402

assert str(REPO) in S.__file__, S.__file__
spec = importlib.util.spec_from_file_location("setups_main", sys.argv[2])
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
D = Path(__file__).resolve().parent
KW = {"tf": "x", "source": "x", "as_of": "x"}


def velas(nombre, secs):
    cubos = {}
    for x in json.loads((D / nombre).read_text())["rows"]:
        if x.get("close") is None or not x.get("is_closed"):
            continue
        t = int(datetime.fromisoformat(x["bucket"].replace("Z", "+00:00")).timestamp())
        k = t - t % secs
        c = cubos.setdefault(k, {"ts": k, "open": None, "high": x["high"], "low": x["low"], "close": x["close"]})
        c["high"], c["low"], c["close"] = max(c["high"], x["high"]), min(c["low"], x["low"]), x["close"]
    return [c for _, c in sorted(cubos.items())]


for etiqueta, patron, secs in (("15 m", "v5-{}.json", 900), ("4 h", "v4h-{}.json", 14400)):
    c = dict.fromkeys(("medido", "ret_main", "ret_rama", "def_main", "def_rama", "las2_main", "las2_rama"), 0)
    for s in ("BTCUSDT_PERP.A", "ETHUSDT_PERP.A", "SOLUSDT_PERP.A"):
        todas = velas(patron.format(s), secs)
        for i in range(60, len(todas) + 1):
            bars = todas[max(0, i - 400):i]
            sh, sl = SL._swings([b["high"] for b in bars], [b["low"] for b in bars], [b["ts"] for b in bars], k=2)
            piv, atr = {"highs": sh, "lows": sl}, SL._atr(bars)
            for signo in (1, -1):
                r = {}
                for nom, mod in (("main", M), ("rama", S)):
                    pb = mod._pullback(bars, signo, piv, atr, **KW)
                    ld = mod._level_defended(bars, signo, piv, atr, {}, **KW)
                    r[nom] = (pb["value"] is not None and (pb.get("pullback_atr") or 0) >= S.LEVEL_TOL_ATR_MULT,
                              ld["value"] is True, pb["value"] is not None)
                if not r["main"][2]:
                    continue
                c["medido"] += 1
                for nom in ("main", "rama"):
                    c[f"ret_{nom}"] += r[nom][0]
                    c[f"def_{nom}"] += r[nom][1]
                    c[f"las2_{nom}"] += r[nom][0] and r[nom][1]
    n = c["medido"]
    print(f"{etiqueta}: medido {n} · " + " · ".join(
        f"{k} {v} ({100 * v / n:.1f} %)" for k, v in c.items() if k != "medido"))
