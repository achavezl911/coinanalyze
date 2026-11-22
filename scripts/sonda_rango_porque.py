"""Sonda Z-05 · ¿el «porque» del veredicto de rango afirma un voto que su tabla no tiene?

Uso:  python3 scripts/sonda_rango_porque.py [--horas 6] [--ventanas 40] [--salida DIR]

Solo lectura: pide `/api/rango/estructura` a PRODUCCION por `harness/bin/api` (GET) para BTC, ETH y
SOL en ventanas CERRADAS consecutivas de `--horas`, alineadas al ultimo borde multiplo de `--horas`
en UTC (asi dos corridas dentro del mismo tramo piden las mismas ventanas). En cada respuesta busca
las frases que afirman un voto -«el precio cae», «el spot vende», «el interes abierto aguanta»...- y
cuenta los veredictos en los que alguna afirma un lado que su prueba NO voto.

rc=0  todos los veredictos dicen solo lo que se voto.
rc=1  hay al menos uno que afirma un voto que no hubo (los imprime).
rc=2  ningun veredicto leido (ruta caida, 404 sin desplegar...): NO es un cero.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

API = "/srv/coinanalyze/harness/bin/api"
SIMBOLOS = ("BTCUSDT_PERP.A", "ETHUSDT_PERP.A", "SOLUSDT_PERP.A")

# Cada frase que AFIRMA un voto, con la prueba y el lado que la sostendrian.
AFIRMA = (
    ("el precio cae", "progreso_precio", "bajista"),
    ("el precio sube", "progreso_precio", "alcista"),
    ("el spot vende", "cvd_spot", "bajista"),
    ("el spot compra", "cvd_spot", "alcista"),
    ("el interes abierto cae", "interes_abierto", "cierre"),
    ("el interes abierto aguanta", "interes_abierto", "traspaso"),
    ("se rompen los largos", "liquidaciones", "bajista"),
    ("se rompen los cortos", "liquidaciones", "alcista"),
)


def afirmaciones_sin_voto(veredicto: dict, pruebas: list[dict]) -> list[str]:
    """Las frases del «porque» que afirman un lado que su prueba no voto (o que no voto)."""
    porque = (veredicto.get("porque") or "").lower()
    lado = {p["prueba"]: p["vota"] for p in pruebas}
    return [f"«{frase}» y {prueba} vota {lado.get(prueba)}"
            for frase, prueba, esperado in AFIRMA
            if frase in porque and lado.get(prueba) != esperado]


def pide(ruta: str, salida: Path | None, nombre: str) -> dict:
    r = subprocess.run(["sh", API, ruta], capture_output=True, text=True,
                       env={**os.environ, "TODO": "1"}, check=False)
    if salida is not None:
        (salida / f"{nombre}.json").write_text(r.stdout)
    try:
        d = json.loads(r.stdout)
    except ValueError:
        return {"_error": f"rc={r.returncode} {r.stdout[:120]!r} {r.stderr[:120]!r}"}
    return d if isinstance(d, dict) else {"_error": f"no es un objeto: {r.stdout[:120]!r}"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--horas", type=int, default=6)
    ap.add_argument("--ventanas", type=int, default=40)
    ap.add_argument("--salida", type=Path, default=None, help="guarda cada respuesta entera")
    a = ap.parse_args()
    if a.salida is not None:
        a.salida.mkdir(parents=True, exist_ok=True)

    ahora = datetime.now(UTC)
    fin = ahora.replace(hour=ahora.hour - ahora.hour % a.horas, minute=0, second=0, microsecond=0) \
        if 24 % a.horas == 0 else ahora.replace(minute=0, second=0, microsecond=0)
    trabajos = []
    for s in SIMBOLOS:
        for i in range(a.ventanas):
            hasta = fin - timedelta(hours=a.horas * i)
            desde = hasta - timedelta(hours=a.horas)
            q = urlencode({"symbol": s, "desde": desde.isoformat(), "hasta": hasta.isoformat()})
            trabajos.append((s, desde, f"/api/rango/estructura?{q}", f"{s[:3]}-{desde:%Y%m%dT%H}"))

    with ThreadPoolExecutor(max_workers=4) as ex:
        respuestas = list(ex.map(lambda t: pide(t[2], a.salida, t[3]), trabajos))

    total = malos = 0
    errores: list[str] = []
    reparto: dict[str, int] = {}
    for (s, desde, _ruta, nombre), r in zip(trabajos, respuestas, strict=True):
        ver, pruebas = r.get("veredicto"), r.get("pruebas")
        if not ver or pruebas is None:
            errores.append(f"{nombre}: {r.get('_error') or r.get('detail') or 'sin veredicto'}")
            continue
        total += 1
        reparto[ver["estructura"]] = reparto.get(ver["estructura"], 0) + 1
        falsas = afirmaciones_sin_voto(ver, pruebas)
        if falsas:
            malos += 1
            print(f"  AFIRMA SIN VOTO {s[:3]} {desde:%Y-%m-%dT%H}Z +{a.horas}h · {ver['estructura']} · "
                  + " · ".join(falsas))
    for e in errores[:5]:
        print(f"  ERROR {e}")
    print(f"sonda rango-porque · {fin:%Y-%m-%dT%H:%M}Z hacia atras · {a.horas} h x {a.ventanas} ventanas x "
          f"{len(SIMBOLOS)} simbolos: {malos} de {total} veredictos con un «porque» que afirma un voto "
          f"que su tabla no tiene · {len(errores)} sin respuesta · reparto {reparto}")
    if total == 0:
        return 2
    return 1 if malos else 0


if __name__ == "__main__":
    sys.exit(main())
