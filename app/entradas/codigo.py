"""La version del CODIGO que decide, y su huella (campana 135, C3).

Cada foto lleva la version del codigo que la decidio (motor.CODIGO_VERSION) y su huella: sha256
del JSON canonico de las huellas de cada pieza que decide -el motor, lo que lee (insumos), como
registra y cuando corre (registro, servicio)- y de las funciones reutilizadas de
app/interpretation.py, que fijan los bordes de las zonas.

config/entradas/codigo.json guarda, append-only, la huella de cada version del codigo registrada.
tests/test_entradas_codigo.py la recalcula: un cambio en cualquiera de esas piezas SIN subir
CODIGO_VERSION (y registrar su huella nueva) lo para el CI. En produccion, entrada_reglamento
guarda (CODIGO_VERSION, 'codigo') con UNIQUE: la misma etiqueta con otra huella no emite nada.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
from typing import Any

from app.entradas import reglamento as R

RAIZ = Path(__file__).resolve().parents[2]
REGISTRO = RAIZ / "config" / "entradas" / "codigo.json"
FUENTES = (
    "app/entradas/motor.py",
    "app/entradas/insumos.py",
    "app/entradas/registro.py",
    "app/entradas/servicio.py",
)
REUTILIZADAS = ("_barrier_candidates", "_barrier_zones")


def piezas() -> dict[str, str]:
    from app import interpretation

    partes = {
        ruta: hashlib.sha256((RAIZ / ruta).read_bytes()).hexdigest() for ruta in FUENTES
    }
    for nombre in REUTILIZADAS:
        fuente = inspect.getsource(getattr(interpretation, nombre)).encode("utf-8")
        partes[f"app/interpretation.py:{nombre}"] = hashlib.sha256(fuente).hexdigest()
    partes["app/interpretation.py:BARRIER_PIVOT_WIDTH"] = repr(interpretation.BARRIER_PIVOT_WIDTH)
    return partes


def contenido() -> dict[str, Any]:
    return {"piezas": piezas()}


def huella_codigo() -> str:
    return R.huella(contenido())


def registradas(ruta: str | Path | None = None) -> dict[str, str]:
    """{version del codigo: huella} de config/entradas/codigo.json."""
    datos = json.loads(Path(ruta or REGISTRO).read_text(encoding="utf-8"))
    return dict(datos["versiones"])
