"""BOT-4a «TU HISTORIAL»: la descarga del historial de Bybit a un fichero, con un Bybit falso (sin red, sin base).
Las filas son inventadas: ningun dato de la cuenta entra en el repo."""

from __future__ import annotations

import ast
import asyncio
import inspect
import json
import os
import pathlib
import stat
import textwrap

import pytest

from app.bot import historial as hi
from app.bot import servicio as sv

DIA = 86400 * 1000
H = 1_800_000_000_000  # un «ahora» fijo en ms


class Falso:
    """get(ruta, **params) -> responde(ruta, params, n); guarda cada peticion."""

    def __init__(self, responde=None):
        self.responde = responde or (lambda ruta, p, n: {"retCode": 0, "result": {"list": []}})
        self.pedidas: list = []

    async def get(self, ruta, **p):
        self.pedidas.append((ruta, dict(p)))
        return self.responde(ruta, p, len(self.pedidas))


async def nada(_s):
    return None


def _baja(f, dias=21, **kw):
    return hi.descarga(f, ahora_ms=H, dias=dias, dormir=kw.pop("dormir", nada), **kw)


def test_ventanas_de_7_dias_como_mucho_cubren_730_sin_hueco():
    vs = hi.ventanas(H)
    assert vs[0][1] == H and vs[-1][0] == H - 730 * DIA
    assert all(0 <= fin - ini <= 7 * DIA for ini, fin in vs)
    assert all(vs[i + 1][1] == vs[i][0] - 1 for i in range(len(vs) - 1))  # contiguas: ni hueco ni solape
    assert len(vs) == 105


async def test_pagina_hasta_el_final_con_el_cursor():
    def responde(ruta, p, n):
        if ruta == hi.RUTAS["cierres"] and p["startTime"] == H - 7 * DIA:
            pag = {None: ("c1", [{"orderId": "a"}]), "c1": ("c2", [{"orderId": "b"}]), "c2": ("", [{"orderId": "c"}])}
            sig, filas = pag[p.get("cursor")]
            return {"retCode": 0, "result": {"list": filas, "nextPageCursor": sig}}
        return {"retCode": 0, "result": {"list": []}}
    f = Falso(responde)
    d = await _baja(f)
    assert [x["orderId"] for x in d["cierres"]] == ["a", "b", "c"] and d["n_cierres"] == 3
    assert all(p["category"] == "linear" and p["limit"] == 100 and p["endTime"] - p["startTime"] <= 7 * DIA for _, p in f.pedidas)
    assert d["ventanas_fallidas"] == [] and d["permiso_ejecuciones"] == "ok"


async def test_sin_permiso_en_ejecuciones_no_tira_los_cierres():
    def responde(ruta, p, n):
        if ruta == hi.RUTAS["ejecuciones"]:
            return {"retCode": 10005, "retMsg": "Permission denied"}
        return {"retCode": 0, "result": {"list": [{"orderId": str(p["startTime"])}]}}
    f = Falso(responde)
    d = await _baja(f)
    assert d["n_cierres"] == 3 and d["n_ejecuciones"] == 0 and d["ventanas_fallidas"] == []
    assert d["permiso_ejecuciones"].startswith("sin permiso")
    assert sum(r == hi.RUTAS["ejecuciones"] for r, _ in f.pedidas) == 1  # no se insiste en cada ventana


async def test_una_ventana_fallida_se_apunta_y_se_sigue():
    def responde(ruta, p, n):
        if ruta == hi.RUTAS["cierres"] and p["endTime"] == H - 7 * DIA - 1:
            return {"retCode": 10001, "retMsg": "params error"}
        return {"retCode": 0, "result": {"list": [{"execId": str(n), "execTime": str(p["endTime"])}]}}
    d = await _baja(Falso(responde))
    assert [(v["ruta"], v["hasta"]) for v in d["ventanas_fallidas"]] == [(hi.RUTAS["cierres"], H - 7 * DIA - 1)]
    assert d["n_cierres"] == 2 and d["n_ejecuciones"] == 3


async def test_un_fallo_pasajero_se_reintenta_corto_y_limitado():
    esperas: list = []

    async def dormir(s):
        esperas.append(s)

    def una_vez(ruta, p, n):
        return {"retCode": 10006, "retMsg": "too many"} if n == 1 else {"retCode": 0, "result": {"list": [{"x": n}]}}
    d = await _baja(Falso(una_vez), dias=1, dormir=dormir)
    assert d["ventanas_fallidas"] == [] and d["n_cierres"] == 1
    assert 1.0 in esperas and hi.PAUSA in esperas and max(esperas) <= 4.0

    siempre = Falso(lambda ruta, p, n: {"retCode": 10016, "retMsg": "server error"})
    d = await _baja(siempre, dias=1)
    assert len(siempre.pedidas) == 2 * (len(hi.ESPERAS) + 1)  # cada ruta: 1 + 3 reintentos, y se sigue
    assert len(d["ventanas_fallidas"]) == 2


async def test_una_clave_rechazada_para_sin_escribir():
    with pytest.raises(hi.ClaveRechazada):
        await _baja(Falso(lambda ruta, p, n: {"retCode": 10003, "retMsg": "invalid"}))


def _datos(n_c, n_e, desde=H - 730 * DIA, **kw):
    return {"generado": "x", "desde": desde, "hasta": H, "n_cierres": n_c, "n_ejecuciones": n_e, "ventanas_fallidas": [],
            "permiso_ejecuciones": "ok", "cierres": [{"updatedTime": str(H - i)} for i in range(n_c)],
            "ejecuciones": [{"execTime": str(H - i)} for i in range(n_e)]} | kw


def _lee(ruta):
    return json.loads(pathlib.Path(ruta).read_text())


def test_fichero_600_en_directorio_700_y_atomico(tmp_path, monkeypatch):
    ruta = str(tmp_path / "h" / "historial.json")
    assert hi.guarda(ruta, _datos(2, 3)) == ruta
    assert stat.S_IMODE(os.stat(ruta).st_mode) == 0o600 and stat.S_IMODE(os.stat(tmp_path / "h").st_mode) == 0o700
    assert _lee(ruta)["n_ejecuciones"] == 3 and hi.vigente(ruta)
    assert not hi.vigente(ruta, ahora=os.stat(ruta).st_mtime + hi.CADUCA_S + 1) and not hi.vigente(str(tmp_path / "no"))

    def rompe(*a, **k):
        raise OSError("disco lleno")
    monkeypatch.setattr(hi.json, "dump", rompe)
    with pytest.raises(OSError):
        hi.guarda(ruta, _datos(9, 9))
    assert _lee(ruta)["n_cierres"] == 2  # lo que habia sigue entero
    assert sorted(os.listdir(tmp_path / "h")) == ["historial.json"]  # y sin restos


def test_no_pisa_un_completo_con_uno_menor(tmp_path):
    ruta = str(tmp_path / "historial.json")
    hi.guarda(ruta, _datos(5, 5))
    destino = hi.guarda(ruta, _datos(3, 5))
    assert destino == str(tmp_path / "historial.parcial.json")
    assert _lee(ruta)["n_cierres"] == 5 and _lee(destino)["n_cierres"] == 3
    # lo que la ventana movil deja fuera por viejo no cuenta: con el desde nuevo despues de 2 cierres viejos, 3 bastan
    assert hi.guarda(ruta, _datos(3, 5, desde=H - 2)) == ruta
    # un fichero que no estaba completo si se sustituye
    hi.guarda(ruta, _datos(5, 5, ventanas_fallidas=[{"ruta": "x"}]))
    assert hi.guarda(ruta, _datos(1, 1)) == ruta


def test_el_resumen_no_lleva_dinero():
    d = _datos(2, 1)
    d["cierres"][0] |= {"closedPnl": "123.45", "avgEntryPrice": "67890.1"}
    t = hi.resumen(d, parcial=True)
    assert "2 cierres, 1 ejecuciones" in t and "ventanas fallidas: 0" in t and "parcial" in t
    assert "123" not in t and "67890" not in t


class SinBase:
    def __init__(self):
        self.tocada: list = []

    def __getattr__(self, k):
        self.tocada.append(k)
        raise AssertionError(f"el historial toco la base: {k}")


def _bot(tmp_path, bybit):
    bot = sv.Bot({"BOT_HISTORIAL": str(tmp_path / "historial.json")}, SinBase(), None)
    bot.bybit = bybit
    bot.estado["bybit"]["activo"] = True
    textos: list = []

    async def manda(t):
        textos.append(t)
        return True
    bot.manda = manda
    return bot, textos


async def test_la_tarea_no_se_solapa_y_no_toca_la_base(tmp_path, monkeypatch):
    suelta, llamadas = asyncio.Event(), []

    async def descarga(bybit):
        llamadas.append(1)
        await suelta.wait()
        return _datos(1, 1)
    monkeypatch.setattr(hi, "descarga", descarga)
    bot, textos = _bot(tmp_path, Falso())
    await bot.tic_historial()
    await asyncio.sleep(0)
    bot.historial_proximo = 0.0  # ni el tope de un dia la salva: lo que la para es la tarea viva
    await bot.tic_historial()
    await asyncio.sleep(0)
    assert llamadas == [1] and len(bot.tareas) == 1
    suelta.set()
    await asyncio.wait(bot.tareas)
    assert len(textos) == 1 and "1 cierres" in textos[0] and hi.vigente(str(tmp_path / "historial.json"))
    assert bot.db.tocada == [] and not any("historial" in k for k in bot.estado["errores"])
    bot.historial_proximo = 0.0
    await bot.tic_historial()  # fichero recien hecho: no se baja otra vez
    assert llamadas == [1]


async def test_sin_bybit_activo_o_sin_carga_no_baja(tmp_path, monkeypatch):
    monkeypatch.setattr(hi, "descarga", lambda b: pytest.fail("no debia bajar"))
    bot, _ = _bot(tmp_path, Falso())
    bot.cargado = False
    await bot.tic_historial()
    bot.cargado, bot.estado["bybit"]["activo"] = True, False
    await bot.tic_historial()
    assert bot.tareas == set()


def _llamados(nombre: str) -> set:
    """Los metodos del Bot que `nombre` alcanza por self.X(...), transitivamente."""
    vistos, pila = set(), [nombre]
    while pila:
        m = pila.pop()
        if m in vistos or not hasattr(sv.Bot, m):
            continue
        vistos.add(m)
        arbol = ast.parse(textwrap.dedent(inspect.getsource(getattr(sv.Bot, m))))
        pila += [n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)
                 and isinstance(n.value, ast.Name) and n.value.id == "self"]
    return vistos


def test_control_la_descarga_nunca_sale_de_tic_bybit():
    """R7: la seguridad primero. Cae si tic_bybit (o algo que llama) llegara a la descarga."""
    desde_bybit = _llamados("tic_bybit")
    assert "tic_bybit" in desde_bybit and "seguridad" in desde_bybit  # el recorrido funciona
    assert not desde_bybit & {"tic_historial", "baja_historial"}
    fuentes = "".join(inspect.getsource(getattr(sv.Bot, m)) for m in desde_bybit)
    assert "historial" not in fuentes
    assert "baja_historial" in _llamados("tic_minuto")  # y si sale del minuto
