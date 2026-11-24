"""DIARIO R1: el hueco que congela el diario (D2), la rejilla que no sella (D3), el stop saltado en la apertura (D4),
el SIN N por dias (D5), el libro que no se rehace (D6). Todo con dobles: sin red ni 140."""
from __future__ import annotations

import csv
import hashlib
import io
import itertools
import zipfile

import pytest

from app.diario import libro as lb
from app.diario import marcador as mc
from app.diario import publico as pb
from app.diario import resuelve as rs

D0 = 1_800_000_000 - 1_800_000_000 % 86400  # un dia UTC entero


def _zip(minutos: dict[int, tuple], nombre: str = "BTCUSDT-1m-x.csv") -> bytes:
    """Un zip diario como el de data.binance.vision: cabecera y open_time en ms."""
    s = io.StringIO()
    w = csv.writer(s)
    w.writerow(["open_time", "open", "high", "low", "close", "volume", "close_time"])
    for t, (o, h, lo, c) in sorted(minutos.items()):
        w.writerow([t * 1000, o, h, lo, c, 1, t * 1000 + 59999])
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr(nombre, s.getvalue())
    return b.getvalue()


def _baja(zips: dict[str, bytes], malos: set[str] = frozenset(), pedidos: list | None = None):
    """Doble de la red: {AAAA-MM-DD: zip}; un dia en `malos` sirve un CHECKSUM que no casa."""
    def baja(url: str) -> bytes:
        dia = url.rsplit("-1m-", 1)[1][:10]
        if pedidos is not None and not url.endswith(".CHECKSUM"):
            pedidos.append(dia)
        if dia not in zips:
            raise OSError("404")
        z = zips[dia]
        if url.endswith(".CHECKSUM"):
            sha = "0" * 64 if dia in malos else hashlib.sha256(z).hexdigest()
            return f"{sha}  {url.rsplit('/', 1)[1][:-9]}\n".encode()
        return z
    return baja


def _dia_plano(d: int, px: float = 100.0) -> dict[int, tuple]:
    return {d + 60 * k: (px, px + 1, px - 1, px) for k in range(1440)}


# ---------- D2 · el volcado publico ----------
def test_zip_con_checksum_bueno_agrega_como_la_ruta():
    m = {D0 + 60 * k: (100 + k, 100.5 + k, 99.5 + k, 100.2 + k) for k in range(5)}
    m.update({D0 + 300 + 60 * k: (1.0, 2.0, 0.5, 1.5) for k in range(4)})  # 4 de 5 minutos: no es vela
    z = _zip(m)
    v = pb.velas_del_zip(z, hashlib.sha256(z).hexdigest() + "  x.zip\n", "x.zip")
    assert v == {D0: (100.0, 104.5, 99.5, 104.2)}


def test_zip_con_checksum_malo_no_entra_y_es_error(tmp_path):
    z = _zip(_dia_plano(D0))
    with pytest.raises(ValueError):
        pb.velas_del_zip(z, "0" * 64 + "  x.zip", "x.zip")
    P, errores, fallos, pedidos = pb.Publico(str(tmp_path)), [], [], []
    baja = _baja({pb.dia_iso(D0): z}, malos={pb.dia_iso(D0)}, pedidos=pedidos)
    assert P.rellena("BTC", [D0 + 3600], D0 + 2 * 86400, errores, fallos, baja) == []
    assert P.lee("BTC") == {} and len(errores) == 1 and "CHECKSUM" in errores[0] and fallos == []
    assert pb.dia_iso(D0) in P.carga("BTC")["malos"]
    P.rellena("BTC", [D0 + 3600], D0 + 2 * 86400 + 60, errores, fallos, baja)  # dentro de REINTENTO_S: no se pide
    assert pedidos == [pb.dia_iso(D0)]


def test_rellena_solo_dias_pasados_marca_la_fuente_y_reintenta_si_no_hay(tmp_path):
    P, errores, fallos = pb.Publico(str(tmp_path)), [], []
    baja = _baja({pb.dia_iso(D0): _zip(_dia_plano(D0))})
    assert P.rellena("BTC", [D0 + 3600], D0 + 86400 - 1, errores, fallos, baja) == []  # el dia no ha pasado
    assert P.rellena("BTC", [D0 + 86400 + 60], D0 + 2 * 86400 + 10, errores, fallos, baja) == []  # aun sin volcado
    assert errores == [] and len(fallos) == 1
    assert P.rellena("BTC", [D0 + 3600], D0 + 2 * 86400 + 20, errores, fallos, baja) == [pb.dia_iso(D0)]
    x = P.carga("BTC")
    assert x["fuente"] == pb.FUENTE and len(x["dias"][pb.dia_iso(D0)]) == 64 and len(x["velas"]) == 288
    assert (tmp_path / "velas" / "BTC-5min-publico.json").exists()


def _prop(**kw) -> dict:
    p = {"fuente": "rejilla", "id": "rejilla:1", "activo": "BTC", "lado": "largo", "orden": "limite", "entrada": 100.0,
         "stop": 97.0, "objetivo": 106.0, "caduca": D0 + 3 * 86400, "plazo_s": 3 * 86400, "riesgo_usd": 5.0,
         "sello": D0 + 23 * 3600, "porque": "prueba"}
    p.update(kw)
    return p


def test_hueco_de_dos_dias_se_resuelve_con_el_volcado_y_manda_140(tmp_path, monkeypatch):
    """La propuesta llena el dia D0 a las 23:05; 140 no tiene precio de 23:30 a D0+1 06:00 (cruza el dia) y tiene
    una vela de 23:25 que el volcado da distinta: entra el volcado en el hueco y manda 140 donde hay de las dos."""
    from app.diario import __main__ as cli
    d1 = D0 + 86400
    v5 = {"BTC": {t: (100.5, 101.0, 99.8, 100.4) for t in range(D0 + 23 * 3600, D0 + 23 * 3600 + 1800, 300)}}
    v5["BTC"].update({t: (101.0, 101.5, 100.5, 101.0) for t in range(d1 + 6 * 3600, d1 + 7 * 3600, 300)})
    pub = {**_dia_plano(D0, 100.0), **{t: (100.0, 107.0, 99.0, 100.0) for t in range(d1, d1 + 86400, 60)}}
    zips = {pb.dia_iso(D0): _zip({t: x for t, x in pub.items() if t < d1}),
            pb.dia_iso(d1): _zip({t: x for t, x in pub.items() if t >= d1})}
    real = pb.baja_dia
    monkeypatch.setattr(pb, "baja_dia", lambda a, d, baja=None: real(a, d, _baja(zips)))
    L = lb.Libro(str(tmp_path / "entradas.jsonl"))
    L.anade("propuesta", _prop(), ahora=D0 + 23 * 3600)
    ahora = D0 + 2 * 86400 + 3600
    assert cli.resuelve_todo(L, L.lee(), v5, ahora)[0] == 0  # en main: pendiente por hueco, sin plazo
    errores, est = [], {}
    v5p, publicas = cli.con_publico(str(tmp_path), L.lee(), v5, ahora, True, errores, est)
    assert errores == [] and est["publico"] == {"BTC": [pb.dia_iso(D0), pb.dia_iso(d1)]}  # dos vueltas
    assert v5p["BTC"][D0 + 23 * 3600 + 1500] == (100.5, 101.0, 99.8, 100.4)  # 140, no el volcado
    n, huecos = cli.resuelve_todo(L, L.lee(), v5p, ahora, publicas)
    assert n == 1 and huecos == []
    r = mc.operaciones(L.lee())[1]["rejilla:1"]
    assert r["salida"] == "objetivo" and r["t_salida"] == D0 + 86400 + 300 and r["velas_publicas"] == 7
    m = mc.calcula(L.lee())["rejilla"]
    assert m["con_publicas"] == 1 and "1 con velas publicas" in mc.texto(L.lee(), L.cabeza(), ahora)


def test_sin_precio_a_los_tres_dias_es_indecidible_y_se_cuenta_aparte(tmp_path):
    from app.diario import __main__ as cli
    v5 = {"BTC": {D0 + 23 * 3600 + 300: (100.5, 101.0, 99.8, 100.4), D0 + 2 * 86400: (100, 100, 100, 100)}}
    hueco = D0 + 23 * 3600 + 600
    L = lb.Libro(str(tmp_path / "entradas.jsonl"))
    L.anade("propuesta", _prop(), ahora=D0 + 23 * 3600)
    n, huecos = cli.resuelve_todo(L, L.lee(), v5, hueco + 300 + 3 * 86400 - 1)
    assert n == 0 and len(huecos) == 1
    n, huecos = cli.resuelve_todo(L, L.lee(), v5, hueco + 300 + 3 * 86400)
    assert n == 1 and huecos == []
    L.anade("propuesta", _prop(id="rejilla:2", sello=D0 + 10 * 86400 + 600), ahora=D0 + 10 * 86400 + 600)  # pendiente
    r = mc.operaciones(L.lee())[1]["rejilla:1"]
    assert r["salida"] == "indecidible" and r["r_neto"] is None and r["hueco"] == hueco
    m = mc.calcula(L.lee())["rejilla"]
    assert (m["propuestas"], m["resueltas"], m["indecidibles"], m["pendientes"]) == (2, 0, 1, 1)
    assert "1 indecidibles por hueco (aparte)" in mc.texto(L.lee(), L.cabeza(), D0 + 20 * 86400)
    assert rs.INDECIDIBLE_S == 3 * 86400  # el plazo del encargo, con nombre


# ---------- D3 · el dia sin rejilla deja un ERROR ----------
def test_rejilla_sin_el_dia_de_ayer_es_un_error_que_se_ve(tmp_path):
    from app.diario import __main__ as cli
    from app.diario import fuentes as fu
    ahora = D0 + 86400 + 300  # las 00:05Z del dia siguiente a D0
    e = cli.corre("diario", str(tmp_path), ahora, False, False)  # sin velas de 4 h: en main, rc 0 y nada
    assert e["rc"] == 1 and len(e["rejilla_errores"]) == 3 and e["rejilla"] == (0, 0)
    assert (tmp_path / "marcador.txt").read_text().count("\nERROR rejilla ") == 3
    v4 = {t: (100.0, 101.0, 99.0, 100.0) for t in range(D0 - 86400, D0 + 86400, 4 * 3600)}
    assert len(fu.rejilla({"BTC": v4}, ahora)) == 6
    del v4[D0 + 16 * 3600]  # como el 11-16: falta la vela de 4 h de las 16:00
    errores = []
    assert fu.rejilla({"BTC": v4, "ETH": {}}, ahora, errores) == []
    assert len(errores) == 2 and f"el {pb.dia_iso(D0)} queda sin rejilla" in errores[0] and "ETH" in errores[1]


# ---------- D4 · el stop saltado en la apertura ----------
def test_r1_mercado_que_abre_mas_alla_del_stop_sale_a_la_apertura():
    """Caso R1 de R3b: largo ref 100, stop 99, la vela del llenado abre en 98. En main: «stop» a 98.901, +0.79 R."""
    p = _prop(orden="mercado", entrada=100.0, stop=99.0, objetivo=103.0, sello=D0 + 10, caduca=D0 + 3600)
    x = rs.resuelve(p, {D0 + 300: (98.0, 98.5, 97.5, 98.2)}, D0 + 86400)["resultado"]
    assert x["px_llenado"] == 98.0 and x["salida"] == "stop" and x["px_salida"] == pytest.approx(98 * 0.999)
    assert x["r_neto"] == pytest.approx((-0.001 - 2 * 0.00055) / 0.01) and x["r_neto"] < 0
    # limite: la PRIMERA vela abre bajo el stop -> llega cruzada (llenado-r1): tomador a 96.5 y sale a la apertura
    x = rs.resuelve(_prop(sello=D0 + 10), {D0 + 300: (96.5, 96.8, 96.0, 96.6)}, D0 + 86400)["resultado"]
    assert x["px_llenado"] == 96.5 and x["px_salida"] == pytest.approx(96.5 * 0.999)
    assert x["regla"] == rs.REGLA_CRUZADA and x["coste"]["com_entrada_pb"] == pytest.approx(5.5)
    assert x["r_neto"] == pytest.approx((-0.001 - 2 * 0.00055) / 0.03)


def test_valida_exige_un_stop_minimo():
    from app.diario import fuentes as fu
    p = _prop(orden="mercado", entrada=100.0, stop=99.9, objetivo=101.0, caduca=D0 + 3600)
    assert "minimo 0.5%" in (fu.valida(p, 100.2, D0, set()) or "")
    assert fu.valida({**p, "stop": 99.5}, 100.2, D0, set()) is None
    assert fu.STOP_MIN == 0.005


# ---------- D5 · SIN N cuenta dias ----------
_SEQ = itertools.count()


def _op(L, fuente: str, i: str, dia: int, r: float):
    t = D0 + dia * 86400 + 3600 + next(_SEQ)  # en orden de sello (D6); el resultado, escrito en el mismo segundo
    L.anade("propuesta", _prop(id=i, fuente=fuente, sello=t), ahora=t)
    L.anade("resultado", {"id": i, "llenada": True, "px_llenado": 100.0, "t_llenado": t + 600,
                          "salida": "stop" if r < 0 else "objetivo", "px_salida": 99.0, "t_salida": t + 7200,
                          "r_neto": r, "usd_neto": 5.0 * r, "coste": {}}, ahora=t)


def test_m1_un_dia_no_da_intervalo_y_sin_n_cuenta_dias(tmp_path):
    L = lb.Libro(str(tmp_path / "e.jsonl"))
    for k, r in enumerate((2.0, 1.0, 1.0)):
        _op(L, "fable", f"fable:{k}", 0, r)
    for k in range(4):
        _op(L, "rejilla", f"rejilla:{k}", 0, 0.0 if k else -1.0)
    t = mc.texto(L.lee(), L.cabeza(), D0 + 86400)
    assert "contra la rejilla +1.58 R · SIN N (1 d, 4 de rejilla)" in t and "[" not in t
    assert "fable: 3 propuestas, 3 resueltas, 3 llenadas (llenado 100%) · SIN N (1 d)" in t
    for k in range(30):  # 30 llenadas en 2 dias siguen siendo 2 dias (en orden de sello: D6)
        _op(L, "regla:D:imp1:v0:A", f"regla:{k}", k // 15, 0.5)
    x = mc.calcula(L.lee())["regla:D:imp1:v0:A"]
    assert x["llenadas"] == 30 and x["sin_n"]
    for k in range(8):
        _op(L, "regla:D:imp1:v0:A", f"regla:b{k}", 2 + k, 0.5)
    assert not mc.calcula(L.lee())["regla:D:imp1:v0:A"]["sin_n"]


# ------------------------------------------------------------------------- D6 (R3b H2)
def _libro_tres(tmp_path):
    L = lb.Libro(str(tmp_path / "entradas.jsonl"))
    for k in range(3):
        _op(L, "fable", f"fable:{k}", k, 1.0)
    return L


def test_l1_un_sello_anterior_a_la_ultima_linea_se_rechaza(tmp_path):
    """L1: con el libro ya en T0 + 1 d, sellar «fable:tramposa» con sello T0 (y resolverla al objetivo) colaba."""
    L = lb.Libro(str(tmp_path / "entradas.jsonl"))
    t0 = D0 + 86400
    _op(L, "fable", "fable:0", 1, 1.0)  # ultima linea en t0 + 1 h
    with pytest.raises(ValueError, match="pasado del libro"):
        L.anade("propuesta", _prop(id="fable:tramposa", fuente="fable", sello=t0), ahora=t0)
    assert [f["id"] for f in L.lee()] == ["fable:0", "fable:0"] and lb.verifica(L.ruta) == []
    t = L.lee()[-1]["t"]
    L.anade("propuesta", _prop(id="fable:misma", fuente="fable", sello=t), ahora=t)  # el mismo segundo, si
    assert lb.Libro(str(tmp_path / "c.jsonl"), monotono=False).anade("rechazo", {  # el simulador ciego, si
        "fuente": "f", "id": "x", "motivo": "m", "cruda": "", "sello": 1}, ahora=1)["n"] == 0


def test_l1_ahora_solo_con_la_variable_de_prueba(tmp_path, monkeypatch, capsys):
    from app.diario import __main__ as cli
    llamadas = []
    monkeypatch.setattr(cli, "corre", lambda *a: llamadas.append(a) or {"rc": 0})
    monkeypatch.delenv("DIARIO_PRUEBA", raising=False)
    assert cli.main(["diario", "--dir", str(tmp_path), "--ahora", str(D0), "--sin-red", "--sin-entrega"]) == 2
    assert llamadas == [] and "DIARIO_PRUEBA" in capsys.readouterr().err
    monkeypatch.setenv("DIARIO_PRUEBA", "1")
    assert cli.main(["diario", "--dir", str(tmp_path), "--ahora", str(D0), "--sin-red", "--sin-entrega"]) == 0
    assert llamadas[0][2] == D0
    assert cli.main(["diario", "--dir", str(tmp_path), "--sin-red", "--sin-entrega"]) == 0  # sin --ahora, sin ella
    assert len(llamadas) == 2


def _historial(tmp_path, cab: dict, dia: str = "2027-01-15"):
    with open(tmp_path / "cabezas.tsv", "ab") as f:
        f.write(f"{dia}\t{D0}\t{cab['n']}\t{cab['sha256']}\n".encode())


def _rehace(ruta: str, filas: list[dict]) -> None:
    """Reescribe el libro con la cadena RECALCULADA (n, prev): por dentro, intacta."""
    prev, out = lb.GENESIS, b""
    for k, o in enumerate(filas):
        ln = lb.canon({**o, "n": k, "prev": prev})
        out += ln + b"\n"
        prev = lb.huella(ln)
    with open(ruta, "wb") as f:
        f.write(out)


def test_l2_quitar_la_cola_o_rehacer_la_cadena_lo_delata_el_historial(tmp_path):
    from app.diario import __main__ as cli
    L = _libro_tres(tmp_path)
    vieja = L.cabeza()
    _op(L, "fable", "fable:3", 3, 1.0)
    assert lb.verifica(L.ruta, vieja) == []  # una cabeza de un dia anterior vale: el libro solo crece
    _historial(tmp_path, vieja)
    _historial(tmp_path, L.cabeza())
    assert cli.corre("cuarto", str(tmp_path), D0 + 9 * 86400, False, False)["rc"] != 2
    filas = L.lee()
    # quitar la ultima linea: la cadena sigue intacta, la cabeza de ayer no
    _rehace(L.ruta, filas[:-1])
    assert lb.verifica(L.ruta) == [] and cli.corre("cuarto", str(tmp_path), D0 + 9 * 86400, False, False)["rc"] == 2
    # rehacer la cadena con un resultado de 9.99: tambien la delata la cabeza vieja
    _rehace(L.ruta, [dict(o, r_neto=9.99) if o["tipo"] == "resultado" and o["id"] == "fable:0" else o for o in filas])
    assert lb.verifica(L.ruta) == []
    est = cli.corre("cuarto", str(tmp_path), D0 + 9 * 86400, False, False)
    assert est["rc"] == 2 and any("se toco o se rehizo" in x for x in est["libro_tocado"])


def test_l2_la_corrida_diaria_guarda_la_cabeza_entera(tmp_path):
    from app.diario import __main__ as cli
    L = _libro_tres(tmp_path)
    cli.corre("diario", str(tmp_path), D0 + 9 * 86400, False, False)
    cli.corre("diario", str(tmp_path), D0 + 10 * 86400, False, False)
    lineas = (tmp_path / "cabezas.tsv").read_text().splitlines()
    assert len(lineas) == 2 and lineas[0].split("\t")[2:] == [str(L.cabeza()["n"]), L.cabeza()["sha256"]]
    assert L.cabeza()["sha256"] in (tmp_path / "marcador.txt").read_text()  # los 64, no 16


def test_l2_el_parte_del_bot_lleva_la_cabeza(tmp_path, monkeypatch):
    import asyncio

    from test_bot_seguridad import _salud, bot

    from app.bot import servicio as sv
    sha = hashlib.sha256(b"x").hexdigest()
    (tmp_path / "diario-entradas.txt").write_text(f"DIARIO DE ENTRADAS en sombra (...) · libro n=41 sha256 {sha}\nfable: ...\n")
    b = bot(monkeypatch, [True])
    b.informes, b.cargado, b.parte_hoy = str(tmp_path), True, None

    async def nada(corto=False):
        return "-"
    monkeypatch.setattr(b, "texto_sombra", nada)
    monkeypatch.setattr(b, "texto_sesgo", nada)
    monkeypatch.setattr(b, "salud", lambda: _salud())
    monkeypatch.setattr(sv, "PARTE_HORA_UTC", 0)
    asyncio.run(b.tic_parte())
    (p,) = [m for m in b.mandados if m.startswith("PARTE ")]
    assert f"DIARIO libro n=41 sha256 {sha}" in p


# ------------------------------------------------------------------------- D7 (R3b H4)
T7 = 1786406400  # un 00:00Z


def _banco_tick(tmp_path, act: str, px: float, tick: float, semilla: int = 3) -> str:
    """Banco como el de test_diario_ciego, con los precios en multiplos de un tick REAL del activo."""
    import random

    from app.diario import ciego as cg
    az, d = random.Random(semilla), tmp_path / f"banco-{act}"
    d.mkdir()
    q = lambda x: round(round(x / tick) * tick, 8)  # noqa: E731
    for nom, dur, desde in (("daily-ohlc", 86400, T7 - 100 * 86400), ("4hour-ohlc", 14400, T7 - 25 * 86400),
                            ("5m", 300, T7 - 2 * 86400)):
        filas, c = [], px
        for s in range(desde, T7 + 3 * 86400, dur):
            o, c = c, q(c * (1 + az.gauss(0, 0.002 * (dur / 300) ** 0.5)))
            h, lo = q(max(o, c) * (1 + az.random() * 0.001)), q(min(o, c) * (1 - az.random() * 0.001))
            filas.append((s, o, h, lo, c, 1.0) if nom != "5m" else (s, h, lo, c, 1.0))
        (d / f"{act}-{nom}.txt").write_text("".join("|".join(str(x) for x in f) + "\n" for f in filas))
    cg.carga.cache_clear()
    return str(d)


def _concentracion(xs, qs):
    import numpy as np
    f = 2 * np.pi * np.asarray(xs)[None, :] / np.asarray(qs)[:, None]
    return np.hypot(np.cos(f).sum(1), np.sin(f).sum(1)) / len(xs)


def _cierre_del_texto(texto: str, tick: float) -> float | None:
    """El metodo de R3b (fable_r3_foto.py), con el texto de la foto y nada mas: el paso comun de los precios de 5 min,
    afinado con todos; si se ve (concentracion >= 0.8), ultimo cierre / paso x tick = el precio real."""
    import numpy as np
    todos, m5, cols, ref = [], [], 4, 0.0
    for ln in texto.splitlines()[2:]:
        if ln.startswith(("DIARIAS", "4 HORAS", "5 MINUTOS")):
            cols = 3 if ln.startswith("5 MINUTOS") else 4
            continue
        c = ln.split("|")
        todos += c[1:1 + cols]
        if cols == 3:
            m5, ref = m5 + c[1:4], float(c[3])
    fino = min(10.0 ** -len(c.split(".")[1]) for c in todos if "." in c)
    xs = sorted({float(c) for c in m5})
    saltos = sorted(b - a for a, b in zip(xs, xs[1:], strict=False) if b - a > 3 * fino)
    if len(saltos) < 20:
        return None
    q, todo = saltos[len(saltos) // 10], sorted({float(c) for c in todos})
    for base, ancho, paso in ((xs, 0.25, 5e-4), (todo, 2e-3, 1e-5), (todo, 2e-5, 1e-6)):
        qs = q * (1 + np.arange(-int(ancho / paso), int(ancho / paso) + 1) * paso)
        cs = _concentracion(base, qs)
        q, conc = float(qs[cs.argmax()]), float(cs.max())
    return round(ref / q) * tick if conc >= 0.8 else None


@pytest.mark.parametrize("act,px,tick,n", [("SOL", 140.0, 0.01, 8), ("SOL", 40.0, 0.01, 8)])
def test_d7_la_foto_no_devuelve_el_precio_real(tmp_path, act, px, tick, n):
    from app.diario import ciego as cg
    banco = _banco_tick(tmp_path, act, px, tick)
    fuera = 0
    for k in range(n):
        t = T7 + 86400 + k * 14400
        texto, clave = cg.foto(banco, act, t, semilla=5)
        real = cg.cerradas(cg.carga(banco, act)["M"], 300, t, 1)[0][3]
        est = _cierre_del_texto(texto, tick)
        fuera += est is None or abs(est - real) > tick / 2
        assert cg.foto(banco, act, t, semilla=5)[0] == texto  # determinista con la semilla
    assert fuera == n, f"{act}: el precio real sale de {n - fuera} de {n} fotos"


# --------------------------------------------------------------------------- D8 (R1 H1)
def test_d8_bybit_apagado_se_reintenta_hasta_entregarse(monkeypatch):
    """Telegram cae justo cuando la clave se apaga: el aviso se reintenta en cada tic hasta salir, una sola vez, y al
    registro van el fallo (una fila) y la entrega. Con el servicio de main el APAGADO se mandaba una vez y se perdia."""
    import asyncio

    from test_bot_seguridad import BB, bot

    entrega = [False]
    b = bot(monkeypatch, entrega)
    b.bybit = BB({"/v5/user/query-api": {"retCode": 0, "result": {"readOnly": 0, "ips": ["*"]}},
                  "/v5/position/list": {"retCode": 0, "result": {"list": []}}})

    async def nada(*a, **k):
        return True
    for n in ("avisa_caducidad", "caduca_veredicto", "crudo_lectura", "recarga", "operaciones"):
        monkeypatch.setattr(b, n, nada)
    asyncio.run(b.tic_bybit())  # juzga la clave: APAGADO, y Telegram no entrega
    assert not b.estado["bybit"]["activo"]
    for _ in range(2):
        asyncio.run(b.tic_bybit())  # sigue caido: se reintenta sin volver a juzgar la clave
    apagado = [m for m in b.mandados if m.startswith("Bybit APAGADO")]
    assert len(apagado) == 3, b.mandados
    entrega[0] = True
    asyncio.run(b.tic_bybit())
    asyncio.run(b.tic_bybit())
    asyncio.run(b.tic_bybit())
    apagado = [m for m in b.mandados if m.startswith("Bybit APAGADO")]
    assert len(apagado) == 4, "entregado una vez y no se repite"
    assert [e for t, _, e, _ in b.eventos if t == "bybit"] == [False, True]

