"""C3 de la campana 135 · la version del CODIGO que decide.

Un cambio en el generador (motor, insumos, registro, servicio) o en lo que reutiliza para decidir
(_barrier_candidates, _barrier_zones y BARRIER_PIVOT_WIDTH de app/interpretation.py) SIN subir
motor.CODIGO_VERSION y registrar su huella en config/entradas/codigo.json, lo para este test.
El plantado: cambiar un byte de una pieza mueve la huella; el gemelo sin cambio no.
"""

from __future__ import annotations

import json

from app.entradas import codigo as C
from app.entradas import motor as M
from app.entradas import reglamento as R


def test_la_huella_del_codigo_actual_esta_registrada_con_su_version():
    registradas = C.registradas()
    assert M.CODIGO_VERSION in registradas, (
        f"{M.CODIGO_VERSION} no esta en config/entradas/codigo.json: sube la version y registra su huella"
    )
    assert registradas[M.CODIGO_VERSION] == C.huella_codigo(), (
        "el codigo que decide cambio sin subir motor.CODIGO_VERSION: una version de codigo no "
        "abarca dos codigos (sube la version y anade su huella)"
    )


def test_cada_version_registrada_tiene_una_sola_huella_valida():
    datos = json.loads(C.REGISTRO.read_text(encoding="utf-8"))
    versiones = datos["versiones"]
    assert isinstance(versiones, dict) and versiones
    for etiqueta, huella in versiones.items():
        assert isinstance(etiqueta, str) and etiqueta
        assert isinstance(huella, str) and len(huella) == 64 and int(huella, 16) >= 0


def test_un_byte_cambiado_en_una_pieza_mueve_la_huella(monkeypatch):
    original = C.piezas()
    assert R.huella({"piezas": original}) == C.huella_codigo()
    plantadas = dict(original)
    plantadas["app/entradas/insumos.py"] = "0" * 64
    monkeypatch.setattr(C, "piezas", lambda: plantadas)
    assert C.huella_codigo() != R.huella({"piezas": original})


def test_las_piezas_cubren_el_motor_lo_que_lee_y_lo_reutilizado():
    piezas = C.piezas()
    for nombre in ("app/entradas/motor.py", "app/entradas/insumos.py", "app/entradas/registro.py",
                   "app/entradas/servicio.py", "app/interpretation.py:_barrier_candidates",
                   "app/interpretation.py:_barrier_zones", "app/interpretation.py:BARRIER_PIVOT_WIDTH"):
        assert nombre in piezas, nombre
