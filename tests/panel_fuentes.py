"""De que ficheros esta hecho el panel, para los tests que leen su fuente.

POR QUE EXISTE. Nueve ficheros de `tests/` hacen hoy
`(ROOT / "static" / "app.js").read_text()`. El dia que la FASE 2 parta el panel en modulos,
esa linea devuelve la ENTRADA -unas decenas de bytes con los `import`- y **los asserts de
AUSENCIA pasan solos**: `assert "x" not in JS` se cumple porque no hay nada donde mirar. Un
test que aprueba sin ver lo que juzga es peor que uno que falla.

NO LLEVA LA LISTA A MANO: llama a `harness/bin/panel-fuentes`, que la descubre leyendo el
<script> de `static/index.html` y siguiendo los imports. Una sola implementacion para el
arnes, la sonda de jsdom y los tests.

Hoy devuelve UN fichero y `FUENTE` es byte a byte `static/app.js`, asi que ningun test
cambia de resultado. Se comprueba en `tests/test_panel_fuentes.py`.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
_BIN = RAIZ / "harness" / "bin" / "panel-fuentes"


def ficheros() -> list[Path]:
    """Las fuentes del panel, en orden de evaluacion. Revienta si no se pueden descubrir."""
    if not _BIN.is_file():
        raise RuntimeError(f"no existe {_BIN}: sin el no se sabe de que consta el panel")
    r = subprocess.run([sys.executable, str(_BIN), "--repo", str(RAIZ)],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        # NO se cae a `static/app.js`: un respaldo silencioso es justo como se cuela un
        # test que aprueba sin sujeto. Que reviente y se vea.
        raise RuntimeError("no se pudieron descubrir las fuentes del panel: "
                           + (r.stderr or "").strip()[:300])
    return [RAIZ / x.strip() for x in r.stdout.splitlines() if x.strip()]


def fuente() -> str:
    """El panel entero, concatenado en orden de evaluacion."""
    r = subprocess.run([sys.executable, str(_BIN), "--repo", str(RAIZ), "--cat"],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError("no se pudo concatenar el panel: " + (r.stderr or "").strip()[:300])
    return r.stdout


FICHEROS = ficheros()
FUENTE = fuente()
