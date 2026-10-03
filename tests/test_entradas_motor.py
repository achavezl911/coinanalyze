"""C2, C3 y los controles MC de la campana 135 · el motor de las entradas, sin base.

Cada promesa con un plantado que TIENE que fallar y su gemelo correcto, sobre el banco sintetico
de tests/entradas_banco.py (zonas conocidas en 90, 95, 105 y 110):

C2 a  funcion de T: el mismo T da la misma huella de foto; un now() plantado en la foto la mueve.
C2 b  la zona se congela al pasar a VIGILANDO: un pivote nuevo despues no la cambia.
C2 c  un minuto ausente en la vela que dispara: NO EVALUABLE, sin transiciones.
C2 d  entrada en el cierre de la vela que dispara: condenada (foto.validar_fila).
C2 e  dos vivos en una clave: el motor no abre un segundo episodio sobre una zona ocupada.
C3    la decision se reproduce leyendo SOLO la foto; el resolutor de juguete rechaza una foto sin
      p* o sin los mids de las dos venues.
MC    un largo valido y su REFLEJO dan el corto reflejado; spot negativo con futuros positivos es
      SOMBRA «solo perpetuo»; dentro de un soporte, la zona es la tocada; una ruptura vieja en la
      ventana no invalida el episodio nuevo; un evento dentro de la vida es SOMBRA; el calendario
      vencido es SOMBRA «calendario sin cubrir».
"""

from __future__ import annotations

import ast
import copy
import inspect
import re
from datetime import datetime, timedelta
from pathlib import Path

import entradas_banco as B
import pytest

from app import interpretation
from app.entradas import foto as F
from app.entradas import motor as M
from app.entradas.backtest import simular

ROOT = Path(__file__).resolve().parents[1]


def _gatillo(resultado: dict, familia: str = "F1", lado: str = "largo") -> dict:
    filas = [t for t in B.elige(resultado["transiciones"], familia=familia, lado=lado)
             if t["estado"] in ("DISPARADO", "SOMBRA")]
    assert len(filas) == 1, [(t["estado"], t["motivo"]) for t in resultado["transiciones"]]
    return filas[0]


def _fila_registrada(t: dict, retraso: float = 30.0) -> dict:
    return {
        **t,
        "registered_at": t["vela_cierre"] + timedelta(seconds=retraso),
        "retraso_s": retraso,
        "foto": copy.deepcopy(t["foto"]),
    }


# --------------------------------------------------------------------------- el escenario base


def test_el_rechazo_limpio_de_soporte_dispara_y_su_foto_cumple_c3():
    res = B.paso(B.insumos())
    assert res["evaluacion"]["estado"] == "ok", res["evaluacion"]
    t = _gatillo(res)
    foto = t["foto"]
    assert t["estado"] == "DISPARADO", (t["motivo"], foto["filtros"])
    assert foto["zona"]["low"] == pytest.approx(94.74) and foto["zona"]["high"] == pytest.approx(95.26)
    assert foto["plan"]["stop"]["precio"] == pytest.approx(95.1 - 1.3)
    assert foto["plan"]["objetivos"][0] == pytest.approx(104.74)
    assert foto["plan"]["p_equilibrio"] is not None and 0 < foto["plan"]["p_equilibrio"] < 1
    assert t["caduca_en"] == B.T0 + timedelta(minutes=240)
    assert F.validar_fila(_fila_registrada(t)) == []
    # la VIGILANDO de su episodio se registra antes, con la misma clave
    vig = B.elige(res["transiciones"], familia="F1", lado="largo", estado="VIGILANDO")
    assert [v["clave"] for v in vig] == [t["clave"]]


# --------------------------------------------------------------------------- C2 a


def test_c2a_mismo_T_misma_huella_y_un_now_plantado_la_mueve(monkeypatch):
    ins = B.insumos()
    primera = [t["huella_foto"] for t in B.paso(copy.deepcopy(ins))["transiciones"]]
    segunda = [t["huella_foto"] for t in B.paso(copy.deepcopy(ins))["transiciones"]]
    assert primera == segunda and primera

    original = M._foto_base

    def con_reloj(**kw):
        foto = original(**kw)
        foto["generada"] = datetime.now().isoformat()  # el plantado: un now() en la foto
        return foto

    monkeypatch.setattr(M, "_foto_base", con_reloj)
    plantada_1 = [t["huella_foto"] for t in B.paso(copy.deepcopy(ins))["transiciones"]]
    plantada_2 = [t["huella_foto"] for t in B.paso(copy.deepcopy(ins))["transiciones"]]
    assert plantada_1 != plantada_2, "el control de la misma huella no ve un now() en la foto"


def _codigo_sin_prosa(ruta: Path) -> str:
    """El codigo sin docstrings ni comentarios: lo que se ejecuta, SQL incluido."""
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        cuerpo = getattr(nodo, "body", None)
        if (isinstance(cuerpo, list) and cuerpo and isinstance(cuerpo[0], ast.Expr)
                and isinstance(cuerpo[0].value, ast.Constant) and isinstance(cuerpo[0].value.value, str)):
            cuerpo.pop(0)
    return ast.unparse(arbol)


def test_c2a_el_motor_no_lee_el_reloj():
    for ruta in (ROOT / "app/entradas/motor.py", ROOT / "app/entradas/insumos.py"):
        codigo = _codigo_sin_prosa(ruta)
        for prohibido in ("datetime.now", "time.time", "time.monotonic", "clock_timestamp",
                          "now()", "CURRENT_TIMESTAMP", "date.today", "statement_timestamp",
                          "transaction_timestamp", "LOCALTIMESTAMP"):
            assert prohibido not in codigo, (ruta.name, prohibido)


def test_c2a_el_control_del_reloj_ve_un_now_plantado_en_una_consulta():
    plantado = _codigo_sin_prosa(ROOT / "app/entradas/insumos.py").replace(
        "ts < $4", "ts < now()", 1
    )
    assert "now()" in plantado  # la adulteracion ocurrio (A67: se prueba en la salida)


# --------------------------------------------------------------------------- C2 b


def test_c2b_la_zona_congelada_no_la_mueve_un_pivote_del_propio_episodio():
    T1 = B.T0
    ins1 = B.insumos(T1, gatillo=(96.0, 96.2, 95.6, 95.7))  # arma sin tocar (a 0.46 % del borde)
    res1 = B.paso(ins1)
    vig = B.elige(res1["transiciones"], familia="F1", lado="largo", estado="VIGILANDO")
    assert len(vig) == 1 and vig[0]["foto"]["zona"]["high"] == pytest.approx(95.26)
    previos = [{**t, "orden": i} for i, t in enumerate(res1["transiciones"])]
    # Tras el inicio, el episodio hunde una barra de 4 h que crea un pivote NUEVO en 93.5: con
    # zonas recalculadas, el soporte cambiaria. El episodio sigue juzgandose contra SU zona.
    T2 = T1 + timedelta(minutes=15)
    ins2 = B.insumos(T2, gatillo=(95.7, 95.9, 95.0, 95.6), previas=[(96.0, 96.2, 95.6, 95.7)],
                     precio_corte=95.7)
    ins2["h4"] = ins2["h4"][:-3] + [
        {**ins2["h4"][-3], "low": 93.5}, ins2["h4"][-2], ins2["h4"][-1]
    ]
    res2 = B.paso(ins2, previos=previos)
    t = _gatillo(res2)
    assert t["episodio"] == vig[0]["episodio"]
    assert t["foto"]["zona"] == vig[0]["foto"]["zona"]
    assert t["foto"]["corte_zonas"] == vig[0]["foto"]["corte_zonas"] == M.iso(T1 - timedelta(minutes=15))


# --------------------------------------------------------------------------- C2 c


def test_c2c_un_minuto_ausente_es_no_evaluable_y_su_gemelo_no():
    res = B.paso(B.insumos(minutos_gatillo=14))
    assert res["transiciones"] == []
    assert res["evaluacion"]["estado"] == "no_evaluable"
    assert "14 de 15 minutos" in res["evaluacion"]["motivo"]
    assert B.paso(B.insumos())["evaluacion"]["estado"] == "ok"


# --------------------------------------------------------------------------- C2 d


def test_c2d_entrada_en_el_cierre_de_la_vela_que_dispara_condenada():
    t = _gatillo(B.paso(B.insumos()))
    correcta = _fila_registrada(t)
    assert F.validar_fila(correcta) == []
    plantada = _fila_registrada(t)
    cierre = plantada["foto"]["episodio"]["velas"][-1]["close"]
    plantada["foto"]["plan"]["entrada"]["precio"] = cierre
    plantada["foto"]["plan"]["entrada"]["regla_codigo"] = "cierre_vela_gatillo"
    errores = F.validar_fila(plantada)
    assert any("precio fijado" in e for e in errores), errores
    assert any("regla" in e for e in errores), errores
    tarde = _fila_registrada(t, retraso=121.0)
    assert any("sobre el tope" in e for e in F.validar_fila(tarde))


def test_c2d_un_insumo_posterior_al_registro_condenado():
    t = _gatillo(B.paso(B.insumos()))
    plantada = _fila_registrada(t)
    plantada["foto"]["libro_bybit"]["ts"] = M.iso(t["vela_cierre"] + timedelta(minutes=5))
    errores = F.validar_fila(plantada)
    assert any("libro_bybit.ts" in e and "POSTERIOR" in e for e in errores), errores


# --------------------------------------------------------------------------- C2 e


def test_c2e_no_abre_un_segundo_episodio_sobre_una_zona_ocupada():
    T1 = B.T0
    res1 = B.paso(B.insumos(T1, gatillo=(96.0, 96.2, 95.6, 95.7)))
    previos = [{**t, "orden": i} for i, t in enumerate(res1["transiciones"])]
    T2 = T1 + timedelta(minutes=15)
    ins2 = B.insumos(T2, gatillo=(95.7, 95.8, 95.5, 95.6), previas=[(96.0, 96.2, 95.6, 95.7)],
                     precio_corte=95.7)
    res2 = B.paso(ins2, previos=previos)
    nuevos = [t for t in res2["transiciones"] if t["estado"] == "VIGILANDO" and t["familia"] == "F1"
              and t["lado"] == "largo"]
    assert nuevos == [], "abrio un segundo VIGILANDO en una clave ocupada"


# --------------------------------------------------------------------------- C3


def test_c3_la_decision_se_reproduce_leyendo_solo_la_foto():
    for ins in (B.insumos(), B.insumos(spot_vela=-1e6), B.insumos(mid_binance=95.81)):
        t = _gatillo(B.paso(ins))
        foto = copy.deepcopy(t["foto"])
        guardado = {k: foto.pop(k) for k in ("plan", "filtros", "decision")}
        assert M.decidir(foto) == guardado


def resolutor_de_juguete(fila: dict, minutos: list[dict]) -> str:
    """Lee SOLO la fila del registro y velas de 1 min: entra a la apertura del minuto siguiente
    al registro, y mira que toca antes, T1 o el stop (los dos en el mismo minuto cuentan stop)."""
    foto = fila["foto"]
    plan = foto["plan"]
    if plan.get("p_equilibrio") is None:
        raise ValueError("foto sin p*: no se puede juzgar contra su equilibrio")
    mids = foto.get("mids") or {}
    if not (mids.get("binance") and mids.get("bybit")):
        raise ValueError("foto sin los mids de las dos venues")
    errores = F.validar_fila(fila)
    if errores:
        raise ValueError(errores)
    largo = foto["lado"] == "largo"
    stop, t1 = plan["stop"]["precio"], plan["objetivos"][0]
    caduca = M.de_iso(plan["caducidad"]["caduca_en"])
    entrada = fila["registered_at"].replace(second=0, microsecond=0) + timedelta(minutes=1)
    for m in minutos:
        ts = M.de_iso(m["ts"])
        if ts < entrada:
            continue
        if ts >= caduca:
            return "caducado"
        toca_stop = m["low"] <= stop if largo else m["high"] >= stop
        toca_t1 = m["high"] >= t1 if largo else m["low"] <= t1
        if toca_stop:
            return "stop"
        if toca_t1:
            return "exito"
    return "abierto"


def _minutos(desde: datetime, recorrido: list[tuple[float, float]]) -> list[dict]:
    return [{"ts": M.iso(desde + timedelta(minutes=i)), "low": lo, "high": hi}
            for i, (lo, hi) in enumerate(recorrido)]


def test_c3_el_resolutor_de_juguete_resuelve_plantados_leyendo_registro_y_1min():
    t = _gatillo(B.paso(B.insumos()))
    fila = _fila_registrada(t)
    sube = _minutos(B.T0, [(95.7, 96.0)] * 3 + [(96.0, 105.0)])
    baja = _minutos(B.T0, [(95.7, 96.0)] * 3 + [(93.0, 96.0)])
    los_dos = _minutos(B.T0, [(95.7, 96.0)] * 3 + [(93.0, 105.0)])
    antes = _minutos(B.T0 - timedelta(minutes=3), [(93.0, 105.0)] * 3 + [(95.7, 96.0)] * 3)
    assert resolutor_de_juguete(fila, sube) == "exito"
    assert resolutor_de_juguete(fila, baja) == "stop"
    assert resolutor_de_juguete(fila, los_dos) == "stop"
    assert resolutor_de_juguete(fila, antes) == "abierto"  # nada anterior al registro cuenta


def test_c3_el_resolutor_rechaza_una_foto_sin_p_o_sin_los_dos_mids():
    t = _gatillo(B.paso(B.insumos()))
    sin_p = _fila_registrada(t)
    sin_p["foto"]["plan"]["p_equilibrio"] = None
    with pytest.raises(ValueError, match="p\\*"):
        resolutor_de_juguete(sin_p, [])
    sin_mid = _fila_registrada(t)
    sin_mid["foto"]["mids"]["bybit"] = None
    with pytest.raises(ValueError, match="mids"):
        resolutor_de_juguete(sin_mid, [])


# --------------------------------------------------------------------------- MC


def test_mc_el_reflejo_de_un_largo_valido_es_su_corto_reflejado():
    largo = _gatillo(B.paso(B.insumos()), "F1", "largo")
    corto = _gatillo(B.paso(B.refleja(B.insumos())), "F1", "corto")
    assert largo["estado"] == corto["estado"] == "DISPARADO"
    fl, fc = largo["foto"], corto["foto"]
    assert fc["zona"]["low"] == pytest.approx(200 - fl["zona"]["high"])
    assert fc["zona"]["high"] == pytest.approx(200 - fl["zona"]["low"])
    assert fc["plan"]["stop"]["precio"] == pytest.approx(200 - fl["plan"]["stop"]["precio"])
    assert fc["plan"]["objetivos"] == pytest.approx([200 - x for x in fl["plan"]["objetivos"]])
    assert fc["plan"]["r"]["bruto"] == pytest.approx(fl["plan"]["r"]["bruto"])
    assert {n: f["estado"] for n, f in fc["filtros"].items()} == {
        n: f["estado"] for n, f in fl["filtros"].items()
    }


def test_mc_spot_negativo_con_futuros_positivos_es_sombra_solo_perpetuo():
    t = _gatillo(B.paso(B.insumos(spot_vela=-1e6, fut_vela=5e6)))
    assert t["estado"] == "SOMBRA"
    assert "spot_vela" in t["foto"]["decision"]["motivo"]
    assert "solo perpetuo" in t["foto"]["decision"]["etiquetas"]
    assert F.validar_fila(_fila_registrada(t)) == []
    gemelo = _gatillo(B.paso(B.insumos(spot_vela=-1e6, fut_vela=-5e6)))
    assert "solo perpetuo" not in gemelo["foto"]["decision"]["etiquetas"]


def test_mc_dentro_de_un_soporte_la_zona_es_la_tocada():
    res = B.paso(B.insumos(precio_corte=95.0, gatillo=(95.0, 95.6, 94.9, 95.5)))
    t = _gatillo(res)
    zona = t["foto"]["zona"]
    assert zona["low"] <= 95.0 <= zona["high"]
    claves = {x["clave"] for x in B.elige(res["transiciones"], familia="F1", lado="largo")}
    assert claves == {t["clave"]}, "abrio el episodio contra la zona de abajo"


def _serie_f2(n_viejas: bool) -> list[tuple[datetime, dict]]:
    """Ruptura + retest de [104.74, 105.26] en 4 velas; con n_viejas, una ruptura VIEJA y
    fallida 40 velas antes dentro de la ventana."""
    base = 104.0
    pasos = [
        (104.3, 104.6, 104.2, 104.5),   # arma: a 0.23 % del borde cercano
        (104.5, 105.6, 104.4, 105.5),   # 1er cierre sobre el borde 105.26
        (105.5, 105.9, 105.4, 105.7),   # 2o: ruptura confirmada
        (105.5, 105.9, 105.4, 105.8),   # retest a <= 0.5 ATR del borde y cierre de reaccion
    ]
    secuencia = []
    for k, gatillo in enumerate(pasos):
        T = B.T0 + timedelta(minutes=15 * k)
        previas = [p for p in pasos[:k]]
        cierre_previo = previas[-1][3] if previas else base
        ins = B.insumos(T, gatillo=gatillo, base=base, precio_corte=cierre_previo,
                        previas=previas or None, mid_binance=gatillo[3] + 0.01)
        if n_viejas:
            for j, c in ((40, 105.6), (39, 105.8), (38, 104.2)):
                v = ins["velas"][-j - k]
                v.update({"open": 104.2, "high": max(c, 104.3) + 0.1, "low": 104.1, "close": c})
        secuencia.append((T, ins))
    return secuencia


def test_mc_una_ruptura_vieja_en_la_ventana_no_invalida_el_episodio_nuevo():
    for viejas in (False, True):
        sim = simular(_serie_f2(viejas), symbol="BTCUSDT_PERP.A", perfil="intradia",
                      versiones=B.versiones(), revision=B.revision(cubre_hasta=B.T0 + timedelta(days=30)),
                      codigo=B.CODIGO, modo=M.PROSPECTIVO)
        f2 = [f for f in sim["registro"] if f["familia"] == "F2" and f["lado"] == "largo"]
        assert [f["estado"] for f in f2] == ["VIGILANDO", "DISPARADO"], (
            viejas, [(f["estado"], f["motivo"]) for f in f2]
        )
        assert f2[1]["vela_cierre"] == B.T0 + timedelta(minutes=45)


def test_mc_un_evento_dentro_de_la_vida_es_sombra():
    evento = {"clave": "bls-cpi-plantado", "titulo": "CPI", "importancia": 3, "fuente": "BLS",
              "hora_utc": M.iso(B.T0 + timedelta(minutes=60))}
    t = _gatillo(B.paso(B.insumos(eventos=[evento])))
    assert t["estado"] == "SOMBRA" and "evento" in t["foto"]["decision"]["etiquetas"]
    fuera = {**evento, "hora_utc": M.iso(B.T0 + timedelta(minutes=300))}
    assert _gatillo(B.paso(B.insumos(eventos=[fuera])))["estado"] == "DISPARADO"


def test_mc_el_calendario_vencido_es_sombra_calendario_sin_cubrir():
    corto = B.revision(cubre_hasta=B.T0 + timedelta(minutes=60))
    t = _gatillo(B.paso(B.insumos(), rev=corto))
    assert t["estado"] == "SOMBRA"
    assert "calendario sin cubrir" in t["foto"]["decision"]["etiquetas"]
    assert t["foto"]["decision"]["tipo_sombra"] == "datos"
    assert t["foto"]["huellas"]["calendario_datos"] == corto["huella"]
    # en BACKTEST lo que no cubre el calendario se declara NO MEDIDO y no manda a SOMBRA
    bt = _gatillo(B.paso(B.insumos(), rev=corto, modo=M.BACKTEST))
    assert bt["estado"] == "DISPARADO" and bt["foto"]["filtros"]["calendario"]["estado"] == "no_medido"


def test_sin_libro_de_bybit_es_sombra_de_datos_con_su_motivo_servido():
    ins = B.insumos()
    ins["libro_bybit"] = None
    ins["mids"]["bybit"] = None
    t = _gatillo(B.paso(ins))
    assert t["estado"] == "SOMBRA" and t["foto"]["decision"]["tipo_sombra"] == "datos"
    assert "libro_bybit" in t["foto"]["decision"]["ausencias"]
    assert F.validar_fila(_fila_registrada(t)) == []


# --------------------------------------------------------------------------- lo que el codigo aplica


def _v2_con(cambio) -> list[dict]:
    from app.entradas import reglamento as R

    versiones = B.versiones()
    v2 = copy.deepcopy(versiones[0])
    v2.update({"version": "v2", "padre": "v1", "ancla": False})
    cambio(v2["bloques"])
    v2["huellas"] = {n: R.huella_bloque(v2["bloques"][n]) for n in R.BLOQUES}
    return versiones + [v2]


@pytest.mark.parametrize(
    "nombre, cambio, rastro",
    [
        ("evento", lambda b: b["F1"]["parametros"]["evento"].update(valor="toque_de_mecha"),
         "F1.evento"),
        ("reloj", lambda b: b["comun"]["parametros"]["invalidacion_reloj"].update(valor="NYSE"),
         "comun.invalidacion_reloj"),
        ("margen", lambda b: b["comun"]["parametros"]["zonas"]["valor"].update(borde_pad_tolerancia=0.3),
         "comun.zonas.borde_pad_tolerancia"),
    ],
)
def test_una_version_que_declara_lo_que_el_codigo_no_aplica_no_corre_y_v1_si(nombre, cambio, rastro):
    versiones = _v2_con(cambio)
    ins = B.insumos()
    res = M.paso(T=ins["T"], symbol=ins["symbol"], perfil=ins["perfil"], modo=M.PROSPECTIVO,
                 versiones=versiones, insumos=ins, previos=[],
                 revision=B.revision(cubre_hasta=B.T0 + timedelta(days=30)), codigo=B.CODIGO)
    assert {t["version"] for t in res["transiciones"]} == {"v1"}, nombre
    assert "v2 NO CORRE" in res["evaluacion"]["motivo"] and rastro in res["evaluacion"]["motivo"]
    assert M.incompatibilidades(B.versiones()[0]) == []


# --------------------------------------------------------------------------- nada en el codigo


def _literales(ruta: Path) -> list[tuple[int, object]]:
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    redondeos = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Call) and getattr(nodo.func, "id", None) == "round":
            redondeos.update(id(a) for a in nodo.args[1:])
    salida = []
    for nodo in ast.walk(arbol):
        if (isinstance(nodo, ast.Constant) and isinstance(nodo.value, (int, float))
                and not isinstance(nodo.value, bool) and id(nodo) not in redondeos):
            salida.append((nodo.lineno, nodo.value))
    return salida


def test_ningun_umbral_vive_en_el_codigo_del_motor_ni_de_los_insumos():
    unidades = {0, 1, 60, 100, 1440, 10_000, -1.0}
    for ruta in (ROOT / "app/entradas/motor.py", ROOT / "app/entradas/insumos.py"):
        sueltos = [(n, v) for n, v in _literales(ruta) if v not in unidades]
        assert sueltos == [], f"{ruta.name}: numeros que no son unidades {sueltos}"


def test_los_valores_fijados_por_el_codigo_reutilizado_son_los_que_declara_el_reglamento():
    zonas = B.comun()["zonas"]
    assert zonas["pivote_anchura"] == interpretation.BARRIER_PIVOT_WIDTH
    zonas_src = inspect.getsource(interpretation._barrier_zones)
    cand_src = inspect.getsource(interpretation._barrier_candidates)
    pad = re.search(r"pad = tolerance \* ([0-9.]+)", zonas_src)
    peso = re.search(r'"touch_weight": ([0-9.]+) if source == "1d"', cand_src)
    assert pad and float(pad.group(1)) == zonas["borde_pad_tolerancia"]
    assert peso and float(peso.group(1)) == zonas["peso_toque_1d"]
