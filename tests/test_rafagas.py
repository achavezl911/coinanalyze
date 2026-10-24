"""app/rafagas.py: el detector y el clasificador sobre series sinteticas de respuesta conocida."""

from app import rafagas as rf

U = rf.Umbrales(W=3, Z=5.0, M=3.0, D=0.25, G=0.5)
QUIETO = 200  # minutos de base: retornos +-0.05 % alternos, 100 USD por lado


def _serie(rets, compras, ventas, t0=29_000_000):
    c = [100.0]
    for r in rets[1:]:
        c.append(c[-1] * (1 + r))
    return rf.Serie(t0, c, list(c), list(c), list(compras), list(ventas))


def _con_rafaga(despues_r, despues_buy, despues_sell):
    """Base quieta, 3 minutos de +0.5 % con compra x10, y lo que se pida despues."""
    rets = [0.0] + [0.0005 * (-1) ** k for k in range(1, QUIETO)] + [0.005] * 3 + despues_r
    buy = [100.0] * QUIETO + [1000.0] * 3 + despues_buy
    sell = [100.0] * QUIETO + [100.0] * 3 + despues_sell
    return _serie(rets, buy, sell)


def _quieta(n):
    return _serie([0.0] + [0.0005 * (-1) ** k for k in range(1, n)], [100.0] * n, [100.0] * n)


def _z(se):
    return rf.rasgos(se, U.W, U.BASE)[0]


def test_detecta_la_rafaga_una_vez_y_en_su_sentido():
    se = _con_rafaga([0.0] * 10, [100.0] * 10, [100.0] * 10)
    dets = rf.detecta(se, U)
    assert len(dets) == 1
    i, s = dets[0]
    assert s == 1 and QUIETO <= i <= QUIETO + 2


def test_sin_volumen_no_hay_rafaga():
    se = _con_rafaga([0.0] * 10, [100.0] * 10, [100.0] * 10)
    plano = rf.Serie(se.t0, se.c, se.hi, se.lo, [100.0] * len(se.c), [100.0] * len(se.c))
    assert rf.detecta(plano, U) == []


def test_calla_sesenta_minutos():
    rets = [0.0] + [0.0005 * (-1) ** k for k in range(1, QUIETO)]
    buy, sell = [100.0] * QUIETO, [100.0] * QUIETO
    for hueco in (30, 200):  # una a los 30 min (calla) y otra a los 200 (vuelve)
        rets += [0.005] * 3 + [0.0005 * (-1) ** k for k in range(hueco)]
        buy += [1000.0] * 3 + [100.0] * hueco
        sell += [100.0] * 3 + [100.0] * hueco
    rets += [0.005] * 3 + [0.0] * 5
    buy += [1000.0] * 3 + [100.0] * 5
    sell += [100.0] * 8
    dets = rf.detecta(_serie(rets, buy, sell), U)
    assert len(dets) == 2 and dets[1][0] - dets[0][0] > U.CALLA


def test_cascada_con_otro_activo_alineado():
    se = _con_rafaga([0.001] * 5, [500.0] * 5, [100.0] * 5)
    otra = _con_rafaga([0.001] * 5, [500.0] * 5, [100.0] * 5)
    (i, s), = rf.detecta(se, U)
    assert rf.clasifica(se, i, s, U, [_z(otra)]) == (rf.CASCADA, 1)
    # sin el otro activo no hay cascada: sigue, pero nadie la acompana
    assert rf.clasifica(se, i, s, U, [_z(_quieta(len(se.c)))])[0] == rf.SIN_CLASE


def test_barrido_devuelve_y_vende():
    se = _con_rafaga([-0.006, -0.004, 0.0, 0.0], [100.0] * 4, [900.0] * 4)
    (i, s), = rf.detecta(se, U)
    # se detecta en el 2.o minuto (el volumen cruza M), el 3.o aun sube y lo devuelto cruza G en el 5.o
    assert i == QUIETO + 1
    assert rf.clasifica(se, i, s, U, [_z(_quieta(len(se.c)))]) == (rf.BARRIDO, 3)


def test_lo_devuelto_sin_delta_en_contra_no_es_barrido():
    se = _con_rafaga([-0.006, -0.004, 0.0, 0.0], [900.0] * 4, [100.0] * 4)
    (i, s), = rf.detecta(se, U)
    assert rf.clasifica(se, i, s, U, [_z(_quieta(len(se.c)))])[0] == rf.SIN_CLASE


def test_liquidaciones_que_crecen_hacen_cascada_solo_con_liquidaciones():
    se = _con_rafaga([0.001] * 5, [500.0] * 5, [100.0] * 5)
    (i, s), = rf.detecta(se, U)
    cierre = (se.t0 + i + 1) * 60
    t1 = cierre // 300 * 300 - 300
    liq = {t1 - 300: (0.0, 1e5), t1: (0.0, 5e5), t1 + 300: (0.0, 9e5)}
    sola = [_z(_quieta(len(se.c)))]
    assert rf.clasifica(se, i, s, U, sola)[0] == rf.SIN_CLASE
    assert rf.clasifica(se, i, s, U, sola, liq)[0] == rf.CASCADA
    # del lado equivocado (largos en una subida) no cuenta
    al_reves = {k: (v[1], v[0]) for k, v in liq.items()}
    assert rf.clasifica(se, i, s, U, sola, al_reves)[0] == rf.SIN_CLASE


def test_bloques_crecen_solo_cuenta_bloques_cerrados():
    liq = {600: (0.0, 1.0), 900: (0.0, 2.0)}
    assert rf.bloques_crecen(liq, 1200, 1)  # en 1200 cerro el de 900
    assert not rf.bloques_crecen(liq, 1199, 1)  # en 1199 el ultimo cerrado es el de 600
    assert not rf.bloques_crecen({900: (0.0, 2.0)}, 1200, 1)  # anterior sin fila = 0: un solo golpe


def test_ni_detector_ni_clase_miran_el_futuro():
    se = _con_rafaga([0.001] * 5, [500.0] * 5, [100.0] * 5)
    otra = _con_rafaga([0.001] * 5, [500.0] * 5, [100.0] * 5)
    (i, s), = rf.detecta(se, U)
    clase, m = rf.clasifica(se, i, s, U, [_z(otra)])

    def corta(x, n):
        return rf.Serie(x.t0, x.c[:n], x.hi[:n], x.lo[:n], x.buy[:n], x.sell[:n])

    assert rf.detecta(corta(se, i + 1), U) == [(i, s)]
    assert rf.clasifica(corta(se, i + m + 1), i, s, U, [_z(corta(otra, i + m + 1))]) == (clase, m)
    assert rf.clasifica(corta(se, i + m), i, s, U, [_z(corta(otra, i + m))]) is None


def _mu(p35, ha, la, hb, lb):
    from scripts import rafagas_estudio as es

    n = len(p35)
    s = "BTCUSDT"
    se = rf.Serie(0, list(p35), list(p35), list(p35), [1.0] * n, [1.0] * n)  # hi/lo: el test los toca
    return es, es.Muestra(0, {s: se}, {s: list(p35)}, {s: list(ha)}, {s: list(la)}, {s: list(hb)},
                          {s: list(lb)}, {s: {}}, "x"), s


def test_resultado_objetivo_stop_y_el_medio_minuto_que_toca_los_dos():
    n = 1500
    es, mu, s = _mu([100.0] * n, [100.0] * n, [100.0] * n, [100.0] * n, [100.0] * n)
    mu.hb[s][3] = 101.3  # objetivo +1.2 % en la 2.a mitad de la barra 3
    assert es.resultado(mu, s, 0, 1, 0.012, 0.006, n) == ("TP", 0.012 - es.FEE)
    mu.la[s][2] = 99.3  # antes, el stop
    assert es.resultado(mu, s, 0, 1, 0.012, 0.006, n) == ("SL", -0.006 - es.FEE)
    mu.la[s][2] = 100.0
    mu.lb[s][3] = 99.3  # la misma mitad toca los dos: stop
    assert es.resultado(mu, s, 0, 1, 0.012, 0.006, n)[0] == "SL"
    # en corto, el mismo medio minuto
    assert es.resultado(mu, s, 0, -1, 0.012, 0.006, n)[0] == "SL"
    # la entrada no ve su propia primera mitad
    es2, mu2, _ = _mu([100.0] * n, [200.0] * n, [100.0] * n, [100.0] * n, [100.0] * n)
    mu2.ha[s][1:] = [100.0] * (n - 1)
    assert es2.resultado(mu2, s, 0, 1, 0.012, 0.006, n)[0] == "VENCE"


def test_resultado_vence_a_las_24_h_al_precio_de_ese_segundo():
    n = 1500
    es, mu, s = _mu([100.0] * n, [100.0] * n, [100.0] * n, [100.0] * n, [100.0] * n)
    mu.p35[s][1440] = 100.5
    mu.hb[s][1440] = 101.3  # despues de las 24 h: no cuenta
    estado, neto = es.resultado(mu, s, 0, 1, 0.012, 0.006, n)
    assert estado == "VENCE" and abs(neto - (0.005 - es.FEE)) < 1e-12


def test_recorrido_en_el_sentido_de_la_rafaga():
    es, mu, s = _mu([100.0] * 10, [100.0] * 10, [100.0] * 10, [100.0] * 10, [100.0] * 10)
    mu.series[s].hi[2], mu.series[s].lo[3] = 102.0, 99.0
    mu.ha[s][5] = 103.0  # la primera mitad de e+h entra; la segunda no
    mu.hb[s][5] = 110.0
    assert es.recorrido(mu, s, 0, 1, 5, 10) == (3.0000000000000027, 1.0000000000000009)
    assert es.recorrido(mu, s, 0, -1, 5, 10) == (1.0000000000000009, 3.0000000000000027)
    assert es.recorrido(mu, s, 0, 1, 10, 10) is None


def test_wilson():
    from scripts.rafagas_estudio import wilson

    lo, hi = wilson(10, 40)
    assert round(lo, 4) == 0.1419 and round(hi, 4) == 0.4019
    assert wilson(0, 0) == (0.0, 1.0)


def test_umbrales_congelados_son_un_punto_de_la_rejilla():
    from scripts.rafagas_estudio import REJILLA

    u = rf.UMBRALES
    assert u.W in REJILLA["W"] and u.Z in REJILLA["Z"] and u.M in REJILLA["M"]
    assert u.D in REJILLA["D"] and u.G in REJILLA["G"]
