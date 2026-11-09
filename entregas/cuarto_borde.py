"""Reproduce el borde del cuarto de hora en un test de entradas (rama claude/cuarto-borde).

    TEST_DATABASE_URL=... .venv/bin/python entregas/cuarto_borde.py <raiz-del-arbol> [nodeid]

Elige el proximo cambio de cuarto B a >= 9 min con B-15m fuera de un cierre de 4 h (que la T de
antes del borde no meta el perfil swing). Lanza un proceso por desfase d, YA IMPORTADO, que duerme hasta el
instante y corre el test con pytest.main: CONTROL a B - 450 - d (mitad del cuarto) y BORDE a B - d.
Cada linea dice cuando empezo el CUERPO del test respecto de B (hook pytest_runtest_call) y si
fallo. Al final: «borde: X de N fallan · control: Y de N».
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

NODO = "tests/test_entradas_espera.py::test_una_vela_reevaluada_no_registra_dos_veces"
DESFASES = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 6.0)
CUARTO, CUATRO_H = 900, 14400


def _borde(ahora: float) -> int:
    b = (int(ahora) // CUARTO + 1) * CUARTO
    while b - ahora < 540 or (b - CUARTO) % CUATRO_H == 0:
        b += CUARTO
    return b


def uno(raiz: str, nodo: str, instante: float, borde: float) -> None:
    os.chdir(raiz)
    sys.path[:0] = [raiz, os.path.join(raiz, "tests")]
    import pytest  # noqa: F401 - todo importado ANTES de esperar
    import test_entradas_espera  # noqa: F401

    marca: dict[str, float] = {}

    class Reloj:
        @pytest.hookimpl(tryfirst=True)
        def pytest_runtest_call(self, item):
            marca["cuerpo"] = time.time()

    time.sleep(max(0.0, instante - time.time()))
    t0 = time.time()
    rc = pytest.main(["-q", "-p", "no:cacheprovider", "--rootdir", raiz, nodo], plugins=[Reloj()])
    fin = time.time()
    print(f"RES arranque={t0 - borde:+.2f} cuerpo={marca.get('cuerpo', float('nan')) - borde:+.2f} "
          f"fin={fin - borde:+.2f} rc={int(rc)}", flush=True)


def main() -> None:
    raiz = os.path.abspath(sys.argv[1])
    nodo = sys.argv[2] if len(sys.argv) > 2 else NODO
    b = _borde(time.time())
    print(f"arbol={raiz} borde={time.strftime('%H:%M:%SZ', time.gmtime(b))}", flush=True)
    cuenta = {}
    for fase, base in (("control", b - 450), ("borde", b)):
        hijos = []
        for d in DESFASES:
            p = subprocess.Popen([sys.executable, __file__, "--uno", raiz, nodo, str(base - d), str(b)],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            hijos.append((d, p))
            time.sleep(0.3)  # que no importen los diez a la vez
        fallos = 0
        for d, p in hijos:
            salida = p.communicate()[0]
            res = next((ln for ln in salida.splitlines() if ln.startswith("RES ")), "RES sin-resultado rc=9")
            ok = res.endswith("rc=0")
            fallos += not ok
            lineas = salida.splitlines()
            motivo = "" if ok else " | " + next(
                (ln.strip() for ln in lineas if ln.startswith(">") and "assert" in ln),
                next((ln.strip() for ln in reversed(lineas) if ln.startswith("E ")), "?"))[:200]
            if not ok:  # el fallo entero, para no quedarse con un «?»
                with open(f"/srv/coinanalyze/x1-tmp/cb-fallo-{os.path.basename(raiz)}-{fase}-{d}.txt", "w") as f:
                    f.write(salida[-6000:])
            print(f"{fase} d={d:<4} {res[4:]}{motivo}", flush=True)
        cuenta[fase] = fallos
    n = len(DESFASES)
    print(f"borde: {cuenta['borde']} de {n} fallan · control: {cuenta['control']} de {n}", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "--uno":
        uno(sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5]))
    else:
        main()
