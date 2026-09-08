"""Que no se pueda volver a decir «lo he corrido todo» habiéndose dejado una suite entera.

QUE PASO. El 2026-09-08 la entrega de «Mesa de posicion» daba el marcador con `verify`, `ruff` y
`pytest`, y afirmaba que todo pasaba. **Faltaban dos pasos que CI si corre** —`compileall` y
`node --test tests/js/`— y el segundo estaba ROJO. No se noto hasta que lo dijo el CI del PR #167.

El arreglo NO es acordarse mejor. Es que la lista de lo que hay que correr salga del workflow y
no de la memoria de nadie: este test LEE `.github/workflows/ci.yml` y exige que cada paso que
ejecuta algo este RECONOCIDO aqui abajo, con el comando equivalente que se corre en local.

Si mañana alguien añade un paso a CI, este test enrojece hasta que se declare —y el que lo
declare tiene que escribir con que se comprueba en local, que es justo el dato que faltaba—.
Si alguien quita un paso, tambien enrojece: una entrada de mas significa que se esta corriendo
en local algo que ya no representa a CI, y eso da una confianza que no corresponde.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CI = RAIZ / ".github" / "workflows" / "ci.yml"

# CADA PASO DE CI QUE EJECUTA ALGO, con lo que hay que correr en 143 para cubrirlo.
# El valor es prosa a proposito: lo que hace falta es que quede ESCRITO el comando, no que este
# test lo ejecute. Ejecutarlo aqui seria correr la suite dentro de la suite.
PASOS_CONOCIDOS = {
    "Create venv and install dependencies": "ya montado en 143: .venv/",
    "Ruff (lint)": ".venv/bin/python -m ruff check .",
    "Compile all (syntax check)": ".venv/bin/python -m compileall -q app",
    "Create disposable test database": "en 143 la base de test la levanta el propio pytest",
    "Pytest": ".venv/bin/pytest -q",
    "Drop disposable test database": "no aplica en local",
    "JavaScript tests": "node --test tests/js/",
    "Checks del arnes (K15)": "harness/bin/verify",
}


def pasos_que_ejecutan() -> list[str]:
    """Los `- name:` del workflow que llevan un `run:` antes del siguiente `- name:`.

    SE RECORRE LINEA A LINEA y no con un regex de bloque. La primera version partia por
    `\\n      - name: ` -seis espacios clavados- y encontraba 3 de 8 pasos: los que tenian otra
    sangria o un `run:` en la misma linea se le escapaban en silencio. Un lector que se deja
    cinco pasos y no lo dice es exactamente el defecto que este fichero existe para impedir,
    cometido dentro del propio fichero.
    """
    encontrados, actual = [], None
    for linea in CI.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*-\s+name:\s*(.+?)\s*$", linea)
        if m:
            actual = m.group(1)
            continue
        if actual and re.match(r"\s*run:\s*", linea):
            encontrados.append(actual)
            actual = None
    return encontrados


def test_todo_paso_de_ci_que_ejecuta_algo_esta_reconocido():
    """EL BRAZO QUE IMPORTA. Un paso nuevo en CI enrojece esto hasta que alguien escriba con que
    se comprueba en local. Es la unica forma de que «lo he corrido todo» signifique algo."""
    pasos = pasos_que_ejecutan()
    assert pasos, "no se pudo leer ningun paso de ci.yml: el instrumento esta roto, no el CI"
    sin_reconocer = [p for p in pasos if p not in PASOS_CONOCIDOS]
    assert not sin_reconocer, (
        f"CI ejecuta pasos que nadie ha declarado como se comprueban en local: {sin_reconocer}. "
        f"Añadelos a PASOS_CONOCIDOS con su comando, o no se puede afirmar que se corrio todo."
    )


def test_no_sobra_ninguno():
    """La otra direccion, y no es simetria por gusto: una entrada de mas significa que en local
    se corre algo que ya no representa a CI, y eso da una confianza que no corresponde."""
    pasos = set(pasos_que_ejecutan())
    sobran = sorted(set(PASOS_CONOCIDOS) - pasos)
    assert not sobran, f"declarados aqui pero ya no en ci.yml: {sobran}"


def test_los_dos_que_se_saltaron_estan_dentro():
    """El caso concreto que costo el rojo del PR #167. Si alguien recorta esta lista, que sea a
    la vista."""
    assert "JavaScript tests" in PASOS_CONOCIDOS
    assert "node --test tests/js/" in PASOS_CONOCIDOS["JavaScript tests"]
    assert "Compile all (syntax check)" in PASOS_CONOCIDOS
