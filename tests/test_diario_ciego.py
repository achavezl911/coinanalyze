"""SIMULADOR CIEGO (fase 2b): fotos sin futuro ni fecha ni precio crudo, proponente sin herramientas, sello y resolucion.
Banco sintetico en tmp_path y un proponente doble: sin red ni modelo real."""
from __future__ import annotations

import json
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


# ---------- S2: el proponente ----------
DOBLE = r'''#!/usr/bin/env python3
"""claude doble: apunta lo que recibe y contesta como `claude -p --output-format stream-json`."""
import json, os, sys
a = sys.argv
tools = [] if "--tools" in a and a[a.index("--tools") + 1] == "" else ["Bash", "Read"]
if os.environ.get("DOBLE_HERRAMIENTAS"):
    tools = ["Read"]
if os.environ.get("DOBLE_CUENTA"):
    with open(os.environ["DOBLE_CUENTA"], "a") as f:
        f.write("1\n")
with open(os.environ["DOBLE_SALIDA"], "w") as f:
    json.dump({"argv": a[1:], "cwd": os.getcwd(), "cwd_vacio": os.listdir("."),
               "api_key": "ANTHROPIC_API_KEY" in os.environ, "stdin": sys.stdin.read()}, f)
print(json.dumps({"type": "system", "subtype": "init", "tools": tools, "mcp_servers": [], "model": "doble"}))
print(json.dumps({"type": "result", "is_error": False, "result": os.environ.get("DOBLE_RESPUESTA", "ninguna"),
                  "total_cost_usd": 0.25, "usage": {"input_tokens": 9000, "output_tokens": 400}}))
'''


@pytest.fixture
def doble(tmp_path, monkeypatch):
    b = tmp_path / "claude-doble"
    b.write_text(DOBLE)
    b.chmod(0o755)
    monkeypatch.setenv("DIARIO_CIEGO_CLAUDE", str(b))
    monkeypatch.setenv("DOBLE_SALIDA", str(tmp_path / "doble.json"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-no-se-pasa")
    return tmp_path / "doble.json"


def test_s2_el_proponente_no_recibe_herramientas(doble):
    from app.diario import proponente as pr
    reg = pr.pide("FOTO-DE-PRUEBA")
    vio = json.loads(doble.read_text())
    a = vio["argv"]
    assert a[a.index("--tools") + 1] == "" and "--safe-mode" in a and "--strict-mcp-config" in a
    assert not {"--allowedTools", "--allowed-tools", "--add-dir", "--mcp-config", "--dangerously-skip-permissions",
                "--permission-mode", "--agents", "--plugin-dir"} & set(a)
    assert a[a.index("--system-prompt") + 1] == pr.SISTEMA and a[a.index("--model") + 1] == pr.MODELO
    assert vio["cwd_vacio"] == [] and "ciego-vacio-" in vio["cwd"] and vio["api_key"] is False
    assert vio["stdin"] == pr.INSTRUCCIONES + "\nFOTO-DE-PRUEBA"
    assert reg["error"] is None and reg["herramientas"] == [] and reg["texto"] == "ninguna" and reg["coste_usd"] == 0.25


def test_s2_con_herramientas_la_respuesta_no_vale(doble, monkeypatch):
    from app.diario import proponente as pr
    monkeypatch.setenv("DOBLE_HERRAMIENTAS", "1")
    assert "TENIA herramientas" in pr.pide("F")["error"]


@pytest.mark.parametrize("texto,motivo", [
    ("", "vacia"), ("Creo que compraria", "no es JSON"), ('{"propuestas": [', "no es JSON"),
    ('{"formato": "otro", "propuestas": []}', "diario-entradas/1"), ('{"formato": "diario-entradas/1"}', "propuestas"),
    ('{"formato": "diario-entradas/1", "propuestas": [{}, {}, {}, {}]}', "como mucho 3")])
def test_s2_json_roto_se_rechaza_con_motivo(texto, motivo):
    from app.diario import proponente as pr
    crudas, m = pr.lee(texto)
    assert crudas == [] and m and motivo in m


def _cruda(clave, px, **k):
    f = clave["factor"]
    return {"id": "1", "activo": clave["letra"], "lado": "largo", "orden": "limite", "entrada": round(0.99 * px / f, 5),
            "stop": round(0.97 * px / f, 5), "objetivo": round(1.03 * px / f, 5), "caduca": 86400, "plazo_h": 48,
            "riesgo_usd": 5, "porque": "rebote en el minimo", **k}


def test_s3_desanonimizacion_exacta(tmp_path):
    from app.diario import fuentes as fu
    banco = _banco(tmp_path)
    t = T0 + 3 * 14400
    _, clave = cg.foto(banco, "BTC", t)
    px = fu.precio(cg.velas5(banco, "BTC"), t)
    c = _cruda(clave, px)
    p, m = cg.desanonimiza(c, clave, "BTC-1")
    assert m is None and fu.valida(p, px, t, set()) is None
    assert p["activo"] == "BTC" and p["fuente"] == "fable-ciego" and p["id"] == "fable-ciego:BTC-1:1"
    for k in ("entrada", "stop", "objetivo"):
        assert p[k] == c[k] * clave["factor"]
    assert p["caduca"] == t + 86400 and p["plazo_s"] == 48 * 3600 and p["sello"] == t and p["riesgo_usd"] == 5
    otra = next(x for x in "ABC" if x != clave["letra"])
    assert "la foto era" in cg.desanonimiza({**c, "activo": otra}, clave, "i")[1]
    assert "caduca" in cg.desanonimiza({**c, "caduca": 432001}, clave, "i")[1]
    assert "plazo_h" in cg.desanonimiza({**c, "plazo_h": 241}, clave, "i")[1]


def test_s3_sello_y_resolucion_como_la_fase_2(tmp_path):
    from app.diario import fuentes as fu
    from app.diario import libro as lb
    from app.diario import resuelve as rs
    banco = _banco(tmp_path)
    t = T0 + 3 * 14400
    px = fu.precio(cg.velas5(banco, "BTC"), t)
    # despues de t, a mano: t+300 toca la entrada (0.99), t+1500 toca el objetivo (1.03) sin tocar el stop (0.97)
    a_mano = {0: (1.001, 0.999, 1.0), 1: (1.0, 0.985, 0.99), 2: (0.996, 0.994, 0.995), 3: (0.996, 0.994, 0.995),
              4: (0.996, 0.994, 0.995), 5: (1.04, 0.995, 1.035)}
    p5 = tmp_path / "banco" / "BTC-5m.txt"
    filas = [x.split("|") for x in p5.read_text().splitlines()]
    _escribe(p5, [[f[0], *(str(px * y) for y in a_mano[(int(f[0]) - t) // 300]), f[4]]
                  if 0 <= int(f[0]) - t < 1800 else f for f in filas])
    cg.carga.cache_clear()
    _, clave = cg.foto(banco, "BTC", t)
    c = _cruda(clave, px)
    texto = json.dumps({"formato": "diario-entradas/1", "propuestas": [c, {**c, "id": "2", "caduca": -5}]})
    L = lb.Libro(str(tmp_path / "diario-ciego.jsonl"))
    n = cg.sella_instante(L, banco, clave, "BTC-1", {"error": None, "texto": texto}, set())
    assert n["selladas"] == 1 and n["rechazadas"] == 1 and n["rejilla"][0] + n["rejilla"][1] == 6
    out = cg.resuelve_y_marca(L, banco, str(tmp_path))
    assert lb.verifica(str(tmp_path / "diario-ciego.jsonl")) == []
    props, res = cg.mc.operaciones(L.lee())
    r, p = res["fable-ciego:BTC-1:1"], props["fable-ciego:BTC-1:1"]
    assert {k: v for k, v in r.items() if k not in ("n", "prev", "tipo", "t")} == \
        rs.resuelve(p, cg.velas5(banco, "BTC"), out["fin_banco"])["resultado"]
    e, d = p["entrada"], (p["entrada"] - p["stop"]) / p["entrada"]
    assert r["salida"] == "objetivo" and r["t_llenado"] == t + 300 and r["t_salida"] == t + 1800
    assert r["r_neto"] == pytest.approx(((p["objetivo"] / e - 1) - rs.COM_MAKER - rs.COM_TAKER) / d, abs=1e-6)
    assert all(i.endswith("@BTC-1") for i in props if i.startswith("rejilla:"))
    assert "fable-ciego: 1 propuestas, 1 resueltas, 1 llenadas, 1 rechazadas" in out["marcador"]


def test_s4_plan_reproducible_y_en_sus_limites():
    p = cg.plan()
    assert p == cg.plan() and p != cg.plan(cg.SEMILLA + 1)
    assert len(p) == cg.N_DIAS + cg.N_DOBLES == 80 and len({x["iid"] for x in p}) == 80
    assert all(cg.DESDE <= x["t"] < cg.HASTA + cg.DIA and x["t"] % cg.H4 == 0 for x in p)
    por_dia = {}
    for x in p:
        por_dia.setdefault(x["t"] // cg.DIA, []).append(x)
    assert len(por_dia) == 64 and sorted({len(v) for v in por_dia.values()}) == [1, 2]
    for v in por_dia.values():
        assert len({x["activo"] for x in v}) == len(v) == len({x["t"] for x in v})
    n = [sum(1 for x in p if x["activo"] == a) for a in cg.ACTIVOS]
    assert max(n) - min(n) <= 3


def test_s4_la_corrida_reanuda_sin_repetir_y_respeta_el_tope(tmp_path, doble, monkeypatch):
    from app.diario import libro as lb
    banco = _banco(tmp_path)
    ins = [{"iid": f"BTC-{T0 + k * 14400}", "activo": "BTC", "t": T0 + k * 14400} for k in (1, 7, 13)]
    monkeypatch.setattr(cg, "plan", lambda semilla=cg.SEMILLA: ins)
    cuenta = tmp_path / "cuenta"
    monkeypatch.setenv("DOBLE_CUENTA", str(cuenta))
    d = str(tmp_path / "ciego")
    e1 = cg.corre(d, tope_usd=0.3, banco=banco)  # 0.25 por llamada: la tercera ya no se hace
    assert e1["llamadas"] == 2 and "tope" in e1["parada"] and len(cuenta.read_text().split()) == 2
    e2 = cg.corre(d, tope_usd=10, maximo=5, banco=banco)
    assert e2["ya_sellados"] == 2 and e2["llamadas"] == 1 and e2["pendientes_del_plan"] == 0
    e3 = cg.corre(d, tope_usd=10, banco=banco)
    assert e3["llamadas"] == 0 and len(cuenta.read_text().split()) == 3 and e3["gasto_previo_usd"] == 0.75
    assert lb.verifica(f"{d}/diario-ciego.jsonl") == []
    for x in ins:
        clave = json.loads((tmp_path / "ciego" / "claves" / f"{x['iid']}.json").read_text())
        foto = (tmp_path / "ciego" / "fotos" / f"{x['iid']}.txt").read_text()
        assert clave["t"] == x["t"] and str(x["t"]) not in foto and f"{clave['factor']:.6g}" not in foto


def test_s2_ninguna_y_json_valido():
    from app.diario import proponente as pr
    assert pr.lee("ninguna") == ([], None) and pr.lee("«Ninguna».") == ([], None)
    j = '{"formato": "diario-entradas/1", "propuestas": [{"id": "1"}]}'
    assert pr.lee(j) == ([{"id": "1"}], None) and pr.lee(f"```json\n{j}\n```") == ([{"id": "1"}], None)
