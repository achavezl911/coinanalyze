"""SIMULADOR CIEGO (fase 2b): fotos sin futuro ni fecha ni precio crudo, proponente sin herramientas, sello y resolucion.
Banco sintetico en tmp_path y un proponente doble: sin red ni modelo real."""
from __future__ import annotations

import random
import re

import pytest

from app.diario import ciego as cg

T0 = 1786406400  # un 00:00Z; los instantes de prueba son cierres de 4 h posteriores


def _escribe(ruta, filas):
    ruta.write_text("".join("|".join(str(x) for x in f) + "\n" for f in filas))


def _banco(tmp_path, act="BTC", px=64000.0, semilla=7):
    """Banco con el formato del real: diarias y 4 h t|o|h|l|c|v, 5 min t|h|l|c|v; 30 dias despues de T0 de sobra."""
    az = random.Random(semilla)
    d = tmp_path / "banco"
    d.mkdir(exist_ok=True)
    for nom, dur, desde, hasta in (("daily-ohlc", 86400, T0 - 130 * 86400, T0 + 30 * 86400),
                                   ("4hour-ohlc", 14400, T0 - 30 * 86400, T0 + 30 * 86400),
                                   ("5m", 300, T0 - 3 * 86400, T0 + 30 * 86400)):
        filas, c = [], px
        for s in range(desde, hasta, dur):
            o = c
            c = round(o * (1 + az.gauss(0, 0.002 * (dur / 300) ** 0.5)), 1)
            h, lo = round(max(o, c) * (1 + az.random() * 0.001), 1), round(min(o, c) * (1 - az.random() * 0.001), 1)
            v = round(az.uniform(50, 500), 3)
            filas.append((s, o, h, lo, c, v) if nom != "5m" else (s, h, lo, c, v))
        _escribe(d / f"{act}-{nom}.txt", filas)
    cg.carga.cache_clear()
    return str(d)


def _crudos(banco, act):
    """Todos los textos de precio del banco (como estan en el fichero y como repr del float)."""
    out = set()
    for nom in ("daily-ohlc", "4hour-ohlc", "5m"):
        with open(f"{banco}/{act}-{nom}.txt") as f:
            for x in f:
                for c in x.strip().split("|")[1:-1]:
                    out |= {c, repr(float(c)), f"{float(c):.6g}"}
    return out


def test_s1_foto_sin_futuro(tmp_path):
    banco = _banco(tmp_path)
    t = T0 + 3 * 14400
    texto, _ = cg.foto(banco, "BTC", t)
    # se toca TODO lo que no ha cerrado en t (la vela en curso incluida): la foto no cambia en un byte
    for nom, dur in (("daily-ohlc", 86400), ("4hour-ohlc", 14400), ("5m", 300)):
        p = tmp_path / "banco" / f"BTC-{nom}.txt"
        filas = [x.split("|") for x in p.read_text().splitlines()]
        _escribe(p, [[f[0]] + (["999999.9"] * (len(f) - 1) if int(f[0]) + dur > t else f[1:]) for f in filas])
    cg.carga.cache_clear()
    assert cg.foto(banco, "BTC", t)[0] == texto
    # y el control: tocar la ULTIMA vela cerrada de 5 min SI la cambia (la prueba no es vacia)
    p = tmp_path / "banco" / "BTC-5m.txt"
    filas = [x.split("|") for x in p.read_text().splitlines()]
    _escribe(p, [[f[0], "1.0", "1.0", "1.0", f[4]] if int(f[0]) == t - 300 else f for f in filas])
    cg.carga.cache_clear()
    assert cg.foto(banco, "BTC", t)[0] != texto


def test_s1_foto_sin_fecha_ni_precio_crudo_y_cabe(tmp_path):
    banco = _banco(tmp_path)
    crudos = _crudos(banco, "BTC")
    for k in range(6):
        t = T0 + k * 14400
        texto, clave = cg.foto(banco, "BTC", t)
        assert str(t) not in texto and not re.search(r"\d{7,}", texto), "un sello de tiempo en la foto"
        assert not re.search(r"20\d\d[-/]\d\d|\d\d:\d\d:\d\d|(?i:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)",
                             texto.replace("UTC ahora: ", "")), "una fecha en la foto"
        assert "BTC" not in texto and clave["letra"] in "ABC" and f"«{clave['letra']}»" in texto
        nums = set(re.findall(r"\d+(?:\.\d+)?", texto))
        assert not nums & crudos, f"precio sin escalar: {sorted(nums & crudos)[:5]}"
        lineas = texto.splitlines()
        assert sum(1 for x in lineas if re.match(r"^\d+\|", x)) == cg.N_D + cg.N_H + cg.N_M
        assert len(texto) <= 75000  # <= 25 mil tokens aun a 3 caracteres por token
        # el ultimo cierre de 4 h escalado es el objetivo sorteado, en [5, 20]
        ult = lineas[next(i for i, x in enumerate(lineas) if x.startswith("5 MINUTOS")) - 1]
        assert ult.startswith("0|")
        assert cg.OBJ_MIN <= float(ult.split("|")[4]) <= cg.OBJ_MAX


def test_s1_sorteo_reproducible_con_su_semilla(tmp_path):
    banco = _banco(tmp_path)
    t = T0 + 2 * 14400
    a, b = cg.foto(banco, "BTC", t, semilla=11), cg.foto(banco, "BTC", t, semilla=11)
    assert a == b
    c = cg.foto(banco, "BTC", t, semilla=12)
    assert c[1]["factor"] != a[1]["factor"]
    letras = {cg.foto(banco, "BTC", T0 + k * 14400, semilla=11)[1]["letra"] for k in range(30)}
    assert letras == {"A", "B", "C"}
    with pytest.raises(ValueError):
        cg.foto(banco, "BTC", t + 300)
