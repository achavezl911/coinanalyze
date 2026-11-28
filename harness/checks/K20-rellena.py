"""K20 · rellenar un parametro obligatorio DESDE LA DECLARACION DE LA RUTA.

El barrido de K20 conoce unos pocos valores por NOMBRE (symbol, level, low, high). Para un
parametro obligatorio que no conoce, no se excluye la ruta ni se escribe su valor a mano (una
lista por ruta envejece y es como un check pasa a verde sin probar nada): se le pregunta a la
propia ruta. Se lee el AST de su manejador, se busca la llamada SINCRONA a una funcion del modulo
que recibe ese parametro (su validador: en /api/rango/estructura, `ventana_pedida(desde, hasta,
obligatoria=True)`), y se le ofrecen unas pocas FORMAS genericas -instante ISO-8601 con zona,
fecha, epoch, entero, decimal-. La primera que el validador acepta sin lanzar es el valor.

Si no hay validador que llamar (asincrono, recibe algo que no sea constante o parametro, o no
existe), o ninguna forma le vale, devuelve None y K20 sigue diciendo PARAM: ROJO. Esa es la
mitad que vigila K20-control.bash.
"""
from __future__ import annotations

import ast
import inspect
import textwrap
from datetime import UTC, datetime, timedelta

_NADA = object()


def formas() -> list[str]:
    ahora = datetime.now(UTC).replace(microsecond=0)
    return [
        (ahora - timedelta(hours=1)).isoformat(),
        (ahora - timedelta(days=1)).date().isoformat(),
        str(int(ahora.timestamp()) - 3600),
        "1",
        "1.0",
    ]


def _manejador(app, ruta: str):
    for r in getattr(app, "routes", []):
        if getattr(r, "path", None) == ruta and "GET" in (getattr(r, "methods", None) or ()):
            return r.endpoint
    return None


def _valor(nodo, nombre, candidato, firma, valores):
    if isinstance(nodo, ast.Constant):
        return nodo.value
    if isinstance(nodo, ast.Name):
        if nodo.id == nombre:
            return candidato
        if nodo.id in valores:
            return valores[nodo.id]
        p = firma.parameters.get(nodo.id)
        if p is not None and p.default is not inspect.Parameter.empty:
            return p.default
    return _NADA


def rellenar(app, ruta: str, nombre: str, valores: dict[str, str]) -> str | None:
    """El primer valor que el validador de la ruta acepta para `nombre`, o None."""
    fn = _manejador(app, ruta)
    if fn is None:
        return None
    try:
        arbol = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    except (OSError, TypeError, SyntaxError):
        return None
    firma = inspect.signature(fn)
    globales = getattr(fn, "__globals__", {})
    for nodo in ast.walk(arbol):
        if not (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name)):
            continue
        usa = [a for a in nodo.args if isinstance(a, ast.Name) and a.id == nombre]
        usa += [k for k in nodo.keywords if isinstance(k.value, ast.Name) and k.value.id == nombre]
        if not usa:
            continue
        validador = globales.get(nodo.func.id)
        if not callable(validador) or inspect.iscoroutinefunction(validador):
            continue
        for cand in formas():
            args = [_valor(a, nombre, cand, firma, valores) for a in nodo.args]
            kw = {k.arg: _valor(k.value, nombre, cand, firma, valores) for k in nodo.keywords}
            if _NADA in args or _NADA in kw.values() or None in kw:
                break
            try:
                validador(*args, **kw)
            except Exception:
                continue
            return cand
    return None
