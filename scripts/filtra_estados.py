"""Los estados del mapa para FILTRA (campana BOT-3d): datos publicos, en 143 con el venv aparte.

USO: python scripts/filtra_estados.py HIST scripts/filtra_estados.json
Recalcula la regla de scripts/mapa_sesgo.py (comprueba que da las mismas condiciones, signos y k que mapa_sesgo.json) y
escribe, por activo y por cada decision de 4 h desde 2026-01-01 hasta el fin de la historia: el minuto de epoch de la
entrada, S y el RSI(14) de 4 h de esa decision. Lo lee scripts/filtra.py en 140.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mapa_sesgo as ms  # noqa: E402

DESDE = "2026-01-01"


def main(argv: list[str]) -> int:
    hist, outp = Path(argv[1]), Path(argv[2])
    ref = json.loads((outp.parent / "mapa_sesgo.json").read_text())
    _, acts, _, p2, ent, _, _, S, k, _ = ms.mide(hist)
    if k != ref["k"] or {n: p2[n]["signo"] for n in ent} != {n: v["signo"] for n, v in ref["entran"].items()}:
        print("NO CUADRA con mapa_sesgo.json: no escribo")
        return 1
    d0 = ms.me.minuto(DESDE)
    sims = {}
    for a in acts:
        j = a.Eabs >= d0
        rs = a.col["rsi4"][j]
        sims[a.s] = {"minuto": [int(x) for x in a.Eabs[j]], "S": [int(x) for x in S[a.s][j]],
                     "rsi4h": [None if not math.isfinite(x) else round(float(x), 2) for x in rs]}
    out = {"campana": "BOT-3d", "regla": "scripts/mapa_sesgo.py", "huella_sesgo": ref["huella"], "k": k,
           "entran": ref["entran"], "desde": DESDE, "paso_min": 240,
           "nota": "estado de una operacion: la ultima decision con minuto <= su entrada", "simbolos": sims}
    outp.write_text(json.dumps(out, separators=(",", ":")) + "\n")
    print(f"FIN {outp} {outp.stat().st_size} B · k={k} · " +
          " ".join(f"{s}:{len(v['minuto'])}" for s, v in sims.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
