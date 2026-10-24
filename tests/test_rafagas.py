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


def test_umbrales_congelados_son_un_punto_de_la_rejilla():
    from scripts.rafagas_estudio import REJILLA

    u = rf.UMBRALES
    assert u.W in REJILLA["W"] and u.Z in REJILLA["Z"] and u.M in REJILLA["M"]
    assert u.D in REJILLA["D"] and u.G in REJILLA["G"]
