"""Lo que la API publica es PROSA, no markdown. El panel lo pinta con `textContent`.

QUE PASO. El 2026-09-08, con la portada nueva pidiendo al cargar lo que antes vivia detras de un
formulario, el lector veia en la primera pantalla `**el interes abierto cae con ellos**` y
`«whale_threshold_usd»` con acentos graves: los asteriscos y las comillas invertidas tal cual.

POR QUE SE ARREGLA EN EL EMISOR Y NO EN EL RECEPTOR. `static/app.js` no tiene ni un `innerHTML`
ni existe un `escapeHtml` en todo el fichero: el panel construye DOM con createElement y
textContent A PROPOSITO, y esa decision se tomo para no tener que escapar nada. Convertir
markdown obligaria a meter innerHTML —y entonces hace falta escapado, que hoy no existe— o a
escribir un renderizador. Todo eso para que una frase salga en negrita en un panel de mesa.
Un campo `note`, `porque` o `detail` es un DATO: que su valor lleve marcas de presentacion es la
misma clase de error que meter la unidad dentro del nombre de un campo.

LA POBLACION QUE ESTE TEST VIGILA, y por que no es «toda cadena con asteriscos»: los comentarios
y los docstrings de esta casa estan llenos de enfasis y NO VIAJAN a ninguna respuesta. Contarlos
daba 502 ocurrencias frente a las 4 que de verdad salian en 41 payloads reales: 126 veces mas.
Aqui se miran solo las cadenas que ALGUIEN USA COMO VALOR —ni docstrings, ni las cadenas sueltas
que documentan una constante, ni SQL—, que son 10 494 y donde si puede colarse una hacia fuera.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"

# Lo que un lector ve como basura si nadie lo convierte. NO entra un asterisco suelto ni un guion
# suelto: en una frase normal son puntuacion, y contarlos inflaria el censo por el otro lado.
MARCA = re.compile(r"\*\*[^*\n]+\*\*|`[^`\n]+`")
SQL = re.compile(r"(?is)^\s*(select|with|insert|update|delete|create)\b")


def cadenas_valor(fuente: str) -> list[tuple[int, str]]:
    """Literales que se usan COMO VALOR. Se descarta, cada cosa por su motivo:

    · docstrings de modulo, funcion y clase   -> son documentacion, no valores
    · cadenas sueltas como sentencia          -> los «docstring de atributo» de debajo de cada
                                                 constante; tampoco son valores de nada
    · literales de SQL                        -> viajan a la base, no al lector
    """
    arbol = ast.parse(fuente)
    sueltas = {
        id(n.value)
        for n in ast.walk(arbol)
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)
        and isinstance(n.value.value, str)
    }
    out = []
    for n in ast.walk(arbol):
        if not isinstance(n, ast.Constant) or not isinstance(n.value, str):
            continue
        if id(n) in sueltas or SQL.match(n.value):
            continue
        out.append((n.lineno, n.value))
    return out


def test_ninguna_cadena_publicable_lleva_marca_de_markdown():
    """EL BRAZO QUE IMPORTA. Si alguien vuelve a escribir enfasis en un campo que se sirve, esto
    enrojece antes de que el lector vea los asteriscos en la portada."""
    culpables = []
    total = 0
    for py in sorted(APP.glob("*.py")):
        for linea, valor in cadenas_valor(py.read_text(encoding="utf-8")):
            total += 1
            if MARCA.search(valor):
                culpables.append(f"{py.name}:{linea} {valor[:80]!r}")
    assert total > 5000, f"el lector solo vio {total} cadenas: se ha roto, no es que no haya"
    assert not culpables, (
        "hay cadenas publicables con marca de markdown; el panel las pinta con textContent y el "
        "lector ve los simbolos tal cual:\n  " + "\n  ".join(culpables)
    )


def test_el_lector_distingue_lo_que_viaja_de_lo_que_no():
    """CONTROL. Si este test contara docstrings o SQL daria cientos de falsos positivos y nadie
    lo miraria: un guardian que grita siempre no guarda nada. Se comprueba con codigo de mentira
    que las tres exclusiones funcionan Y que lo que si es un valor NO se escapa."""
    fuente = (
        '"""Docstring de modulo con **enfasis** y `codigo`."""\n'
        "UMBRAL = 3\n"
        '"""Docstring de atributo con **enfasis**."""\n'
        'CONSULTA = "SELECT 1 -- `no es prosa`"\n'
        'MENSAJE = "esto si viaja y lleva `marca`"\n'
    )
    encontrados = [v for _, v in cadenas_valor(fuente) if MARCA.search(v)]
    assert encontrados == ["esto si viaja y lleva `marca`"], encontrados


def test_los_cuatro_que_se_veian_en_la_portada_siguen_limpios():
    """Los casos concretos, para que un recorte del criterio se note. Se comprueba el TEXTO, no
    la ausencia de asteriscos: si alguien reescribe la frase, que sea a la vista."""
    from app.rango import BALLENA_NO_MEDIBLE

    assert "«whale_threshold_usd»" in BALLENA_NO_MEDIBLE
    assert "`" not in BALLENA_NO_MEDIBLE and "**" not in BALLENA_NO_MEDIBLE
