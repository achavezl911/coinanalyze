"""DIARIO DE ENTRADAS (fase 2): libro encadenado, resolucion, fuentes y marcador. Datos sinteticos, sin red ni base."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.bot import calc
from app.diario import libro as lb
from app.diario import resuelve as rs


def _prop(i: str = "x:1", **kw) -> dict:
    p = {"fuente": "rejilla", "id": i, "activo": "BTC", "lado": "largo", "orden": "limite", "entrada": 98.0, "stop": 95.06,
         "objetivo": 103.88, "caduca": 1000 + 5 * 86400, "plazo_s": 10 * 86400, "riesgo_usd": 5.0, "sello": 1000,
         "porque": "prueba"}
    p.update(kw)
    return p


def test_r0_perdida_max_sigue_a_5():
    assert calc.PERDIDA_MAX == 5.0


def test_libro_intacto_y_cabeza(tmp_path):
    r = str(tmp_path / "d" / "e.jsonl")
    L = lb.Libro(r)
    for k in range(4):
        L.anade("propuesta", _prop(f"x:{k}"), ahora=1000 + k)
    assert lb.verifica(r) == []
    cab = L.cabeza()
    assert cab["n"] == 3 and lb.verifica(r, cab) == []
    assert [o["n"] for o in L.lee()] == [0, 1, 2, 3]
    assert L.lee()[0]["prev"] == lb.GENESIS


def test_libro_rechaza_una_linea_tocada(tmp_path):
    r = str(tmp_path / "e.jsonl")
    L = lb.Libro(r)
    for k in range(4):
        L.anade("propuesta", _prop(f"x:{k}"), ahora=1000 + k)
    cab = L.cabeza()
    lineas = Path(r).read_bytes().splitlines()
    o = json.loads(lineas[1])
    o["entrada"] = 97.0  # se toca el nivel de una propuesta ya sellada, en forma canonica
    lineas[1] = lb.canon(o)
    Path(r).write_bytes(b"\n".join(lineas) + b"\n")
    p = lb.verifica(r)
    assert any(x.startswith("linea 2: prev") for x in p), p
    with pytest.raises(ValueError, match="libro tocado"):
        L.lee()
    # la cola: tocar la ULTIMA linea solo la delata la cabeza publicada
    lineas = Path(r).read_bytes().splitlines()
    lineas[1] = lb.canon({**o, "entrada": 98.0})
    o3 = json.loads(lineas[3])
    lineas[3] = lb.canon({**o3, "stop": 1.0})
    Path(r).write_bytes(b"\n".join(lineas) + b"\n")
    assert lb.verifica(r) == []
    assert any("cabeza" in x for x in lb.verifica(r, cab))


def test_libro_quitar_una_linea_y_resultados(tmp_path):
    r = str(tmp_path / "e.jsonl")
    L = lb.Libro(r)
    for k in range(3):
        L.anade("propuesta", _prop(f"x:{k}"), ahora=1000)
    lineas = Path(r).read_bytes().splitlines()
    Path(r).write_bytes(lineas[0] + b"\n" + lineas[2] + b"\n")
    assert any("n=2" in x for x in lb.verifica(r))
    r2 = str(tmp_path / "f.jsonl")
    L2 = lb.Libro(r2)
    res = {"id": "x:9", "llenada": False, "px_llenado": None, "t_llenado": None, "salida": "caducada", "px_salida": None,
           "t_salida": None, "r_neto": 0.0, "usd_neto": 0.0, "coste": {}}
    L2.anade("resultado", res, ahora=1)
    assert any("sin propuesta" in x for x in lb.verifica(r2))
    with pytest.raises(ValueError, match="faltan"):
        L2.anade("propuesta", {"id": "y"})


# ---------- la resolucion ----------
T0 = 28800 * 100  # un sello de funding exacto: las velas de abajo no cruzan otro salvo que se diga


def _v(*filas, t0=T0 + 300):
    """velas de 5 min seguidas desde t0: cada fila (o, h, l, c)."""
    return {t0 + 300 * k: f for k, f in enumerate(filas)}


def _p(**kw) -> dict:
    base = {"id": "r:1", "lado": "largo", "orden": "limite", "entrada": 100.0, "stop": 97.0, "objetivo": 106.0,
            "caduca": T0 + 3600, "plazo_s": 7200, "riesgo_usd": 5.0, "sello": T0 + 10}
    base.update(kw)
    return base


def test_resuelve_llenado_y_objetivo_coste_a_mano():
    v = _v((101, 101.5, 100.5, 101), (100.8, 101, 99.5, 100.2), (100.2, 104, 100, 103), (103, 106.5, 102, 106))
    r = rs.resuelve(_p(), v, T0 + 10**6)
    assert r["estado"] == "resuelta"
    x = r["resultado"]
    assert x["llenada"] and x["t_llenado"] == T0 + 600 and x["px_llenado"] == 100.0
    assert x["salida"] == "objetivo" and x["px_salida"] == 106.0 and x["t_salida"] == T0 + 1500
    # a mano: 6 % - 2 pb maker - 5.5 pb taker, sin funding -> 0.05925; R = 0.05925 / 0.03; nominal = 5 / 0.03175
    assert x["r_neto"] == pytest.approx(1.975)
    assert x["usd_neto"] == pytest.approx(0.05925 * 5 / 0.03175)
    assert x["coste"]["sellos_funding"] == 0


def test_resuelve_misma_vela_gana_el_stop_y_funding():
    # llena y, en otra vela posterior, toca stop Y objetivo: stop a 97 servido 10 pb peor
    v = _v((100.5, 100.6, 99.9, 100.2), (100, 107, 96, 100))
    x = rs.resuelve(_p(), v, T0 + 10**6)["resultado"]
    assert x["salida"] == "stop" and x["px_salida"] == pytest.approx(97 * 0.999)
    assert x["r_neto"] == pytest.approx((97 * 0.999 / 100 - 1 - 0.0002 - 0.00055) / 0.03)
    # cruzando un sello de funding: 1 pb mas en contra
    v2 = {T0 + 28800 - 600: (100.5, 100.6, 99.9, 100.2), T0 + 28800 - 300: (100, 100.5, 99.8, 100),
          T0 + 28800: (100, 107, 96, 100)}
    p2 = _p(sello=T0 + 28800 - 700, caduca=T0 + 10**5, plazo_s=10**5)
    x2 = rs.resuelve(p2, v2, T0 + 10**6)["resultado"]
    assert x2["coste"]["sellos_funding"] == 1
    assert x2["r_neto"] == pytest.approx((97 * 0.999 / 100 - 1 - 0.0002 - 0.00055 - 0.0001) / 0.03)


def test_resuelve_en_la_vela_del_llenado_cuenta_el_stop_no_el_objetivo():
    x = rs.resuelve(_p(), _v((100.5, 106.5, 99.0, 100)), T0 + 10**6)
    assert x["estado"] == "pendiente"  # llenada; el objetivo de esa vela no cuenta y no hay mas velas
    x = rs.resuelve(_p(), _v((100.5, 106.5, 96.0, 100)), T0 + 10**6)["resultado"]
    assert x["salida"] == "stop"


def test_resuelve_mercado_corto_abre_mas_alla_del_stop():
    p = _p(lado="corto", orden="mercado", entrada=100.3, stop=103.0, objetivo=94.0)
    v = _v((100, 100.5, 99.5, 100.2), (104, 104.5, 103.5, 104))
    x = rs.resuelve(p, v, T0 + 10**6)["resultado"]
    assert x["px_llenado"] == 100 and x["px_salida"] == pytest.approx(104 * 1.001)
    assert x["r_neto"] == pytest.approx(-0.04214 / 0.03)
    assert x["coste"]["deslizamiento_stop_pb"] == pytest.approx(110.4)


def test_resuelve_caducada_sin_llenar_y_plazo():
    v = {T0 + 300 * k: (101, 101.5, 100.5, 101) for k in range(1, 14)}
    x = rs.resuelve(_p(), v, T0 + 10**6)["resultado"]
    assert not x["llenada"] and x["salida"] == "caducada" and x["r_neto"] == 0.0 and x["t_salida"] == T0 + 3600
    v = {T0 + 300 * k: (100, 100.5, 99.5, 100.1) for k in range(1, 40)}
    x = rs.resuelve(_p(), v, T0 + 10**6)["resultado"]
    assert x["salida"] == "plazo" and x["t_salida"] == T0 + 300 + 7200 and x["px_salida"] == 100.1


def test_resuelve_hueco_deja_pendiente_y_lo_dice():
    v = _v((101, 101.5, 100.5, 101), (100.8, 101, 99.5, 100.2), (100.2, 104, 100, 103), (103, 106.5, 102, 106))
    del v[T0 + 900]
    r = rs.resuelve(_p(), v, T0 + 10**6)
    assert r == {"estado": "pendiente", "hueco": T0 + 900, "hasta": T0 + 1200}
    # una vela que aun no ha cerrado no cuenta
    r = rs.resuelve(_p(), _v((101, 101.5, 100.5, 101)), T0 + 400)
    assert r["estado"] == "pendiente" and r["hueco"] is None


# ---------- fuentes ----------
def _fable_be():
    """El guion de claude/fable-be tal cual, como modulo (sin ejecutar su main)."""
    import subprocess
    import types
    r = subprocess.run(["git", "-C", str(Path(__file__).resolve().parents[1]), "show",
                        "claude/fable-be:scripts/fable_be_tendencia.py"], capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip("sin la rama claude/fable-be")
    m = types.ModuleType("fable_be_tendencia")
    exec(compile(r.stdout, "fable_be_tendencia.py", "exec"), m.__dict__)
    return m, r.stdout


def _bloque(texto: str) -> str:
    return texto[texto.index("def indicadores("):texto.index("# ---------- fin de la copia") if "# ---------- fin" in
                 texto else texto.index("def sim(")].strip()


def test_paridad_copia_literal_y_sintetica():
    import random

    from app.diario import fuentes as fu
    fb, src = _fable_be()
    assert _bloque(Path(fu.__file__).read_text()) == _bloque(src)
    az = random.Random(7)
    bs, c = [], 100.0
    for k in range(400):
        o = c
        c = o * (1 + az.gauss(0, 0.02) + (0.08 if k % 37 == 0 else 0))
        bs.append((k * 86400, o, max(o, c) * (1 + az.random() * 0.01), min(o, c) * (1 - az.random() * 0.01), c, 86400))
    rng, med, _ = fb.indicadores(bs, 20)
    for celda in fu.REGLAS:
        regla, v = fu.REGLAS[celda]["regla"], fu.REGLAS[celda]["filtro"]
        st = [fb.estado(regla, bs, rng, i) if i >= fb.CALENTAMIENTO - 1 else 0 for i in range(len(bs))]
        suyos = {i for i in range(fb.CALENTAMIENTO, len(bs))
                 if st[i] and st[i] != st[i - 1] and not (v and rng[i] < med[i])}
        mios = {i for i in range(fb.CALENTAMIENTO, len(bs)) if fu.aviso(celda, bs, i)}
        assert suyos == mios and suyos
        # en vivo solo hay `minimo_barras`: el aviso de la ultima barra es el mismo que con la serie entera
        m = fu.minimo_barras(celda)
        assert all(bool(fu.aviso(celda, bs[i - m + 1:i + 1], m - 1)) == (i in suyos)
                   for i in range(fb.CALENTAMIENTO, len(bs)))


def test_paridad_banco():
    from app.diario import fuentes as fu
    fb, _ = _fable_be()
    if not Path(fb.BANCO).is_dir():
        pytest.skip("sin el banco de fable-be")
    for act in fb.ACTIVOS:
        datos = fb.carga(act)
        for celda, r in fu.REGLAS.items():
            bs = datos[r["marco"]]
            rng, med, _ = fb.indicadores(bs, fb.MARCOS[r["marco"]]["sma"])
            st = [fb.estado(r["regla"], bs, rng, i) if i >= fb.CALENTAMIENTO - 1 else 0 for i in range(len(bs))]
            suyos = {i for i in range(fb.CALENTAMIENTO, len(bs))
                     if st[i] and st[i] != st[i - 1] and not (r["filtro"] and rng[i] < med[i])}
            ind = fu.indicadores(bs, 1)
            mios = {i for i in range(fb.CALENTAMIENTO, len(bs)) if fu.aviso(celda, bs, i, ind)}
            assert suyos == mios, (act, celda)
            m = fu.minimo_barras(celda)
            assert all(bool(fu.aviso(celda, bs[i - m + 1:i + 1], m - 1)) == (i in suyos)
                       for i in range(fb.CALENTAMIENTO, len(bs), 5)), (act, celda)


def _v4(n: int, t0: int, sube_al_final: float = 0.0) -> dict:
    """n velas de 4 h planas con un rango de 1 % y un salto en la ultima."""
    v = {}
    for k in range(n):
        c = 100.0 * (1 + sube_al_final if k == n - 1 else 1)
        v[t0 + k * 14400] = (100.0, max(100.5, c), 99.5, c)
    return v


def test_reglas_sellan_el_aviso_fresco_y_solo_el():
    from app.diario import fuentes as fu
    t0 = 1_700_006_400 - 1_700_006_400 % 86400
    v = {"BTC": _v4(6 * 40, t0, 0.05)}
    fin = t0 + 6 * 40 * 14400
    props, notas = fu.reglas(v, fin + 320, set())
    ids = {p["id"] for p in props}
    assert ids == {f"regla:D:imp1:v0:A:BTC:{fin}", f"regla:H:imp6:v1:D:BTC:{fin}"}, (ids, notas)
    p = next(p for p in props if p["fuente"] == "regla:D:imp1:v0:A")
    assert p["lado"] == "largo" and p["orden"] == "mercado" and p["stop"] == pytest.approx(105 * 0.97)
    assert p["objetivo"] == pytest.approx(105 * 1.06) and p["plazo_s"] == 10 * 86400
    assert fu.reglas(v, fin + 2 * 3600, set())[0] == []          # aviso viejo: no se sella tarde
    assert fu.reglas(v, fin + 320, {("D:imp1:v0:A", "BTC"), ("H:imp6:v1:D", "BTC")})[0] == []  # sin solape


def test_rejilla_dieciocho_al_dia():
    from app.diario import fuentes as fu
    t0 = 1_700_006_400 - 1_700_006_400 % 86400
    v = {a: _v4(12, t0) for a in ("BTC", "ETH", "SOL")}
    ps = fu.rejilla(v, t0 + 2 * 86400 + 60)
    assert len(ps) == 18
    lc = next(p for p in ps if p["id"].startswith("rejilla:BTC:C:0.04"))
    assert lc["entrada"] == pytest.approx(104) and lc["stop"] == pytest.approx(104 * 1.03)
    assert lc["objetivo"] == pytest.approx(104 * 0.94) and lc["caduca"] == t0 + 7 * 86400 + 60
    assert fu.rejilla(v, t0 + 4 * 86400) == []                    # dia viejo: no se sella tarde


def test_buzon_sella_rechaza_y_mueve(tmp_path):
    from app.diario import fuentes as fu
    ahora = 1_800_000_000
    bz = tmp_path / "buzon"
    bz.mkdir()
    base = {"activo": "BTC", "lado": "largo", "orden": "limite", "entrada": 95.0, "stop": 92.0, "objetivo": 101.0,
            "caduca": "2027-01-20T08:00:00Z", "porque": "soporte"}
    props = [dict(base, id="ok"),
             dict(base, id="llena", entrada=100.5),                       # largo por encima del precio: ya llena
             {k: x for k, x in dict(base, id="sin-stop").items() if k != "stop"},
             {k: x for k, x in dict(base, id="sin-caduca").items() if k != "caduca"},
             dict(base, id="ok"),                                          # repetida
             dict(base, id="corto-mal", lado="corto"),                     # geometria al reves
             dict(base, id="riesgo", riesgo_usd=6)]
    (bz / "a.json").write_text(json.dumps({"formato": fu.FORMATO, "corrida": "prueba", "propuestas": props}))
    (bz / "b.json").write_text("{no es json")
    L = lb.Libro(str(tmp_path / "e.jsonl"))
    precios = {"BTC": 100.0, "ETH": 3000.0, "SOL": 150.0}
    assert fu.sella_buzon(L, str(bz), dict(precios, SOL=None), ahora, set())["ficheros"] == 0   # sin precio: espera
    n = fu.sella_buzon(L, str(bz), precios, ahora, set())
    assert n == {"selladas": 1, "rechazadas": 7, "ficheros": 2}
    assert sorted(x.name for x in bz.iterdir()) == ["leidos"] and len(list((bz / "leidos").iterdir())) == 2
    filas = L.lee()
    assert [f["id"] for f in filas if f["tipo"] == "propuesta"] == ["fable:ok"]
    mot = {f["id"]: f["motivo"] for f in filas if f["tipo"] == "rechazo"}
    assert mot["fable:llena"].startswith("ya llena al sellar") and mot["fable:sin-stop"].startswith("falta stop")
    assert mot["fable:sin-caduca"].startswith("falta caduca") and mot["fichero:b.json"].startswith("JSONDecodeError")
    assert mot["fable:corto-mal"].startswith("geometria") and mot["fable:riesgo"].startswith("riesgo")
    assert lb.verifica(str(tmp_path / "e.jsonl")) == []
