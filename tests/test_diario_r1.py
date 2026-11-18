"""DIARIO R1: el hueco que congela el diario (D2), la rejilla que no sella (D3), el stop saltado en la apertura (D4),
el SIN N por dias (D5). Todo con dobles: sin red ni 140."""
from __future__ import annotations

import csv
import hashlib
import io
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
    L.anade("propuesta", _prop(id="rejilla:2", sello=D0 + 10 * 86400 + 600), ahora=D0 + 10 * 86400 + 600)
    n, huecos = cli.resuelve_todo(L, L.lee(), v5, hueco + 300 + 3 * 86400 - 1)
    assert n == 0 and len(huecos) == 1
    n, huecos = cli.resuelve_todo(L, L.lee(), v5, hueco + 300 + 3 * 86400)
    assert n == 1 and huecos == []
    r = mc.operaciones(L.lee())[1]["rejilla:1"]
    assert r["salida"] == "indecidible" and r["r_neto"] is None and r["hueco"] == hueco
    m = mc.calcula(L.lee())["rejilla"]
    assert (m["propuestas"], m["resueltas"], m["indecidibles"], m["pendientes"]) == (2, 0, 1, 1)
    assert "1 indecidibles por hueco (aparte)" in mc.texto(L.lee(), L.cabeza(), D0 + 20 * 86400)
    assert rs.INDECIDIBLE_S == 3 * 86400  # el plazo del encargo, con nombre
