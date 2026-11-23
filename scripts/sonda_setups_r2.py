"""Sonda Z-03 + Z-04 · ¿el OI de 15 m se cruza con otro precio, y confirma una continuacion sin retroceso?

Uso:  python3 scripts/sonda_setups_r2.py [--salida DIR]

Solo lectura: pide `/api/hypothesis` a PRODUCCION por `harness/bin/api` (GET) para BTC, ETH y SOL,
los dos perfiles, largo y corto, setups ruptura y continuacion (24 GET), y cuenta:

  Z-03  requisitos de OI EVALUADOS (no `no_evaluable`) cuyo detalle no declara «precio 15 m»: el
        OI es de 15 m (`oi_chg_15m_pct`) y el codigo viejo lo cruzaba con el precio de 3 m sin
        decirlo; el tablero cruza los dos de 15 m. Un requisito que no dice su precio cuenta.
  Z-04  continuaciones CONFIRMADO cuyo retroceso mide menos de LEVEL_TOL_ATR_MULT ATR (o sin ATR),
        o cuya defensa no declara que se midio SOLO en las velas posteriores al extremo del impulso
        (`defense_from_ts` == `pullback_start`) contra un nivel anterior a ellas
        (`defended_level_ts` < `defense_from_ts`). El codigo viejo incluia la vela del pivote
        (`ts >= level_ts`), que toca su propio nivel por construccion: cuenta siempre.

LEVEL_TOL_ATR_MULT se lee de app/setups.py del arbol (no se importa app/).

rc=0  ninguno de los dos.
rc=1  hay al menos uno (los imprime).
rc=2  alguna respuesta no se leyo (ruta caida, error...): NO es un cero.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode

API = "/srv/coinanalyze/harness/bin/api"
SIMBOLOS = ("BTCUSDT_PERP.A", "ETHUSDT_PERP.A", "SOLUSDT_PERP.A")
PERFILES = ("intradia", "swing")
DIRECCIONES = ("long", "short")
SETUPS = ("ruptura", "continuacion")
REQ_OI = ("open interest", "respuesta de futuros (OI)")
SETUPS_PY = Path(__file__).resolve().parent.parent / "app" / "setups.py"


def tolerancia_atr() -> float:
    m = re.search(r"^LEVEL_TOL_ATR_MULT\s*=\s*([0-9.]+)", SETUPS_PY.read_text(), re.M)
    if not m:
        sys.exit(f"no encuentro LEVEL_TOL_ATR_MULT en {SETUPS_PY}")
    return float(m.group(1))


def pide(ruta: str, salida: Path | None, nombre: str) -> dict:
    for _ in range(3):  # la ruta tarda: un curl rc=28 (tiempo) se reintenta, el resto no
        r = subprocess.run(["sh", API, ruta], capture_output=True, text=True,
                           env={**os.environ, "TODO": "1"}, check=False)
        if "curl rc=28" not in r.stderr:
            break
    if salida is not None:
        (salida / f"{nombre}.json").write_text(r.stdout)
    try:
        d = json.loads(r.stdout)
    except ValueError:
        return {"_error": f"rc={r.returncode} {r.stdout[:120]!r} {r.stderr[:120]!r}"}
    if not isinstance(d, dict) or "setup_evaluation" not in d:
        return {"_error": f"sin setup_evaluation: {r.stdout[:120]!r}"}
    return d


def z03(d: dict) -> list[str]:
    return [f"{q['requisito']} {q['estado']}: {q.get('detalle')}"
            for q in d["setup_evaluation"].get("requisitos") or []
            if q.get("requisito") in REQ_OI and q.get("estado") != "no_evaluable"
            and "precio 15 m" not in (q.get("detalle") or "")]


def z04(d: dict, tol: float) -> list[str]:
    if d.get("setup") != "continuacion" or d["setup_evaluation"].get("state") != "CONFIRMADO":
        return []
    obs = d.get("setup_observables") or {}
    pb, ld = obs.get("pullback_pct") or {}, obs.get("level_defended") or {}
    fallos = []
    atr = pb.get("pullback_atr")
    if atr is None or atr < tol:
        fallos.append(f"retroceso {pb.get('value')}% = {atr} ATR < {tol}")
    desde, nivel_ts = ld.get("defense_from_ts"), ld.get("defended_level_ts")
    if desde is None or desde != pb.get("pullback_start") or nivel_ts is None or nivel_ts >= desde:
        propio = ld.get("defended_level_price") in (pb.get("pullback_low"), pb.get("pullback_high"))
        fallos.append(f"defensa sin tramo propio (desde={desde}, nivel_ts={nivel_ts}"
                      f"{', el nivel ES el extremo del retroceso' if propio else ''})")
    return fallos


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", type=Path, default=None, help="guarda cada respuesta entera")
    a = ap.parse_args()
    if a.salida is not None:
        a.salida.mkdir(parents=True, exist_ok=True)
    tol = tolerancia_atr()
    trabajos = [(s, p, d, st) for s in SIMBOLOS for p in PERFILES for d in DIRECCIONES for st in SETUPS]

    def uno(t: tuple[str, str, str, str]) -> tuple[tuple, dict]:
        s, p, d, st = t
        q = urlencode({"symbol": s, "profile": p, "direction": d, "setup": st})
        return t, pide(f"/api/hypothesis?{q}", a.salida, f"{s}-{p}-{d}-{st}")

    # De una en una: la ruta es lenta y con 4 a la vez el transporte cae por tiempo (curl rc=28).
    with ThreadPoolExecutor(max_workers=1) as ex:
        resultados = list(ex.map(uno, trabajos))

    errores = [(t, d["_error"]) for t, d in resultados if "_error" in d]
    n_oi = n03 = n_cont = n04 = 0
    for t, d in resultados:
        if "_error" in d:
            continue
        n_oi += sum(1 for q in d["setup_evaluation"].get("requisitos") or []
                    if q.get("requisito") in REQ_OI and q.get("estado") != "no_evaluable")
        f3 = z03(d)
        n03 += len(f3)
        for x in f3:
            print(f"Z-03 {' '.join(t)} · {x}")
        if t[3] == "continuacion" and d["setup_evaluation"].get("state") == "CONFIRMADO":
            n_cont += 1
        f4 = z04(d, tol)
        n04 += bool(f4)
        for x in f4:
            print(f"Z-04 {' '.join(t)} · {x}")
    for t, e in errores:
        print(f"ERROR {' '.join(t)} · {e}")
    print(f"respuestas {len(resultados) - len(errores)}/{len(resultados)} · "
          f"Z-03 {n03} de {n_oi} requisitos de OI evaluados · "
          f"Z-04 {n04} de {n_cont} continuaciones CONFIRMADO (tolerancia {tol} ATR)")
    if errores:
        return 2
    return 1 if n03 or n04 else 0


if __name__ == "__main__":
    sys.exit(main())
