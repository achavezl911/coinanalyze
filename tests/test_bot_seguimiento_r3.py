"""SEGUIMIENTO R3: las grandes de contado y los racimos con la medida de Fable I19 (39 meses de Binance), en sombra.

I19 (entregas/fable/fable-i19, P1 y P3): el GRA_CONT de R2 («cualquier grande de contado en el minuto») salta ~10 veces por
dia y activo y casi no mueve; CONT = USD de contado de un lado en 1 min >= p99.9 de 10 dias (la regla de GRA sobre *_spot)
sigue en SOLO REGISTRO. Al mensaje de GRA se le anade una linea de GRADO, sin lado: AMBOS (GRA y CONT del mismo lado y
minuto, rango15 x3.3 / x2.9) y RACIMO (>= 3 minutos en estado GRA del mismo lado en 15 min, x3.5 / x2.8). Todo con dobles.
"""

from __future__ import annotations

from test_bot_avisos_r1 import _prohibidas
from test_bot_seguimiento import GRA_HIST, M0, Base, mensajes, montado, registro, textos, tic

from app.bot import seguimiento as seg
from app.bot import servicio as sv

CONT_HIST = [(M0 - 4000 - k, "binance_spot", c, 1e6) for k in range(20) for c in (True, False)]  # p99.9 de 10 d: 1 M$
AMBOS = "Coincide con contado grande del mismo lado: despues el movimiento ha sido aun mayor (unas 3 veces lo normal)."
RACIMO = "Es el minuto {} de una racha en 15 min: despues el movimiento ha sido aun mayor (unas 3 veces lo normal)."


# ---------- (a) CONT: la cola p99.9 de 10 dias, no «cualquier grande»; solo registro ----------
async def test_a_una_grande_de_contado_sola_ya_no_registra_y_la_de_la_cola_si():
    sola = await tic(Base(M0, grandes=CONT_HIST + [(M0 - 1, "coinbase_spot", True, 3e5)]), seg.nuevo(), {}, M0)
    assert not registro(sola) & {"CONT", "GRA_CONT"} and not mensajes(sola), sola
    cola = await tic(Base(M0, grandes=CONT_HIST + [(M0 - 1, "binance_spot", True, 0.6e6), (M0 - 1, "coinbase_spot", True, 0.6e6)]),
                     seg.nuevo(), {}, M0)
    assert "CONT" in registro(cola) and not mensajes(cola), cola
    t = next(x["texto"] for x in cola if x.get("senal") == "CONT")
    assert "1.20 M$" in t and "contado" in t and not _prohibidas(t), t
    # sin historia de contado no hay cola con la que comparar: nada
    nada = await tic(Base(M0, grandes=[(M0 - 1, "binance_spot", True, 5e6)]), seg.nuevo(), {}, M0)
    assert not registro(nada) & {"CONT", "GRA_CONT"}, nada


# ---------- (b) AMBOS: GRA y CONT del mismo lado y minuto ----------
async def test_b_gra_y_cont_del_mismo_lado_llevan_la_linea_de_ambos_y_de_lado_contrario_no():
    gra = [(M0 - 1, "binance_usdm", True, 2e6)]
    mismo = await tic(Base(M0, grandes=GRA_HIST + CONT_HIST + gra + [(M0 - 1, "binance_spot", True, 1.5e6)]), seg.nuevo(), {}, M0)
    t = textos(mismo)
    assert "operaciones grandes de perpetuo" in t and AMBOS in t, t
    assert "CONT" in registro(mismo) and "contado de" not in t.split(AMBOS)[0], mismo  # CONT sigue sin mensaje propio
    assert not _prohibidas(t), t
    contra = await tic(Base(M0, grandes=GRA_HIST + CONT_HIST + gra + [(M0 - 1, "binance_spot", False, 1.5e6)]), seg.nuevo(), {}, M0)
    t2 = textos(contra)
    assert "operaciones grandes de perpetuo" in t2 and "Coincide con contado" not in t2, t2
    assert "CONT" in registro(contra), contra


# ---------- (c) RACIMO: >= 3 minutos en estado GRA del mismo lado en 15 min ----------
async def test_c_tres_minutos_gra_del_mismo_lado_en_15_min_llevan_la_linea_de_racimo_en_el_tercero():
    """Aviso en M0; el antiruido de 30 min calla M0+21 y M0+26 (siguen en estado GRA); M0+31 avisa y es el 3.º en 15 min."""
    b, estado, cache, msgs = Base(M0, grandes=list(GRA_HIST)), seg.nuevo(), {}, []
    for minuto, grande in ((M0, True), (M0 + 1, False), (M0 + 21, True), (M0 + 22, False), (M0 + 26, True), (M0 + 27, False),
                           (M0 + 31, True)):
        if grande:
            b.esc["grandes"] = GRA_HIST + [(minuto - 1, "bybit_linear", False, 2e6)]
        else:
            b.esc["grandes"] = list(GRA_HIST)
        msgs.append(textos(await tic(b, estado, cache, minuto)))
    avisos = [t for t in msgs if t]
    assert len(avisos) == 2, msgs
    assert "racha" not in avisos[0], avisos[0]  # el primero es un minuto suelto
    assert RACIMO.format(3) in avisos[1] and not _prohibidas(avisos[1]), avisos[1]
    # el lado contrario no suma a la racha
    b2, e2, c2, ult = Base(M0, grandes=list(GRA_HIST)), seg.nuevo(), {}, ""
    for minuto, compra in ((M0, False), (M0 + 1, None), (M0 + 21, True), (M0 + 22, None), (M0 + 26, True), (M0 + 27, None),
                           (M0 + 31, False)):
        b2.esc["grandes"] = GRA_HIST + ([] if compra is None else [(minuto - 1, "bybit_linear", compra, 2e6)])
        ult = textos(await tic(b2, e2, c2, minuto)) or ult
    assert "venta agresiva" in ult and "racha" not in ult, ult


# ---------- (d) en sombra nada se envia; en enviar, CONT tampoco ----------
async def test_d_en_sombra_nada_se_envia_y_cont_nunca(monkeypatch, caplog):
    grandes = GRA_HIST + CONT_HIST + [(M0 - 1, "binance_usdm", True, 2e6), (M0 - 1, "binance_spot", True, 1.5e6)]
    bot, mandados = montado(None, Base(M0, grandes=grandes))
    monkeypatch.setattr(sv.time, "time", lambda: M0 * 60 + 20)
    with caplog.at_level("INFO"):
        await bot.tic_seguimiento()
    assert bot.seguimiento_c.modo == "sombra" and mandados == []
    log = [r.getMessage() for r in caplog.records if r.getMessage().startswith("SEGUIMIENTO ")]
    assert any("tipo=registro senal=CONT " in x for x in log) and any(AMBOS in x for x in log), log
    bot2, mandados2 = montado("enviar", Base(M0, grandes=grandes))
    await bot2.tic_seguimiento()
    assert len(mandados2) == 1 and AMBOS in mandados2[0] and "de contado en 1 min" not in mandados2[0], mandados2


def test_el_estado_de_la_racha_se_guarda_y_se_restaura():
    e = seg.nuevo()
    e["racha"]["SOL|-1"] = [M0 - 3, M0 - 1]
    assert seg.restaura(sv.json.loads(sv.js(e)))["racha"] == {"SOL|-1": [M0 - 3, M0 - 1]}
    assert seg.restaura({"racha": {"SOL|1": ["x", 3]}})["racha"] == {"SOL|1": [3]}
