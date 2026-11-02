"""EL CRITERIO del mapa de valor (campana BOT-3c), escrito y commiteado ANTES de mirar la prueba. Biblioteca estandar.

LA PREGUNTA: de cada FAMILIA de informacion, ¿una operacion abierta cuando la familia dice algo gana dinero tras
comision y funding, y mas que una abierta al azar? Lo usan `scripts/mapa_estudio.py` (el barrido, numpy y
scikit-learn en el venv aparte) y `tests/test_mapa_medida.py` (reproduce operaciones con biblioteca estandar).

LOS DATOS: la historia de `zonas_historia.py` (perpetuo USD-M de 1 min: o h l c qv qb, funding liquidado) y la de
`mapa_datos.py` (spot 1 min, premiumIndex 1 min, metrics de 5 min). BTCUSDT, ETHUSDT, SOLUSDT.

LA REJILLA: se decide al cierre de cada vela de 4 h UTC (minuto T multiplo de 240); todo lo que entra en la decision
sale de minutos < T. Entrada al precio o[T] (la apertura del minuto T); el camino empieza en el minuto T. Las senales
DIARIAS (velas de 1 d, 3 d, 9 d) se deciden solo en T multiplo de 1440. Los primeros 30 dias de cada activo no deciden.

LOS ESQUEMAS (objetivo, stop, tope en minutos), comision 5.5 bps por lado (FEE = 0.11 % ida y vuelta):
    a 1/0.6 (1 d)   b 2/0.6 (1 d)   c 3/1.5 (5 d)   d 6/3 (14 d)   e 10/5 (30 d)
    Empate en un minuto: gana el stop. Sin tocar ninguno en el tope: sale al cierre del ultimo minuto (VENCE).
    FUNDING REAL: cada liquidacion f con T < f <= minuto de salida se cobra o se paga: neto -= lado * tasa(f)
    (se aplica a todas, dure lo que dure: con topes de 1 d o mas casi todas cruzan una). Los stops de 3 % y 5 %
    (d, e) no caben en la cuenta de Alejandro a 50x (-2 % liquida): se miden igual, y se dice.
    Liston sobre el azar en tasa de acierto: FEE / (tp + sl).

LAS FAMILIAS y sus CONDICIONES (cada una es una celda con cada esquema, activo y lado; pN y pM son percentiles del
AJUSTE de ESE activo, calculados solo con decisiones de antes de 2023-12-30):
  F1 ESTRUCTURA MULTIDIA (velas de D = 3 y 9 dias; vela k = dias [A + kD, A + (k+1)D) contados desde 2020-01-01;
     anclaje principal A = 0; se repite con A = 1..D-1 y se dice si el veredicto cambia). Al cierre de la vela X
     con la anterior Y:  ruptura_alc c_X > h_Y   ruptura_baj c_X < l_Y
     mecha_inf (min(o,c) - l) >= 0.5 (h - l) de X     mecha_sup (h - max(o,c)) >= 0.5 (h - l) de X
     barre_min l_X < l_Y y c_X > l_Y                  barre_max h_X > h_Y y c_X < h_Y           (12 condiciones)
  F2 MOMENTO: RSI(14) de Wilder sobre cierres de 4 h (cada 4 h) y de 1 d (a las 00:00): rsi_bajo < 30,
     rsi_alto > 70, div_alc: c_j < min(c[j-20..j-1]) y rsi_j > min(rsi[j-20..j-1]); div_baj: el espejo. (8)
  F3 VOLUMEN (4 h): delta = 2 qb - qv; en las 6 velas ultimas D24 = suma delta, V24 = suma qv, R24 = retorno.
     acomp_alc R24 > 0 y D24/V24 > p75(|D24/V24|); acomp_baj R24 < 0 y D24/V24 < -p75; contra_alc R24 < 0 y
     D24/V24 > p75; contra_baj R24 > 0 y D24/V24 < -p75. relvol = qv_j / media(qv de las 180 velas anteriores):
     vol_alto_alc relvol > 2.5 y vela verde; vol_alto_baj relvol > 2.5 y roja; climax_alc / climax_baj relvol > 4 y
     |r_j| > 3 desviaciones de r en las 180 velas anteriores, con su signo.                      (8)
  F4 AGOTAMIENTO: z = (c - media20) / desv20 sobre cierres de 4 h (ext4h_sobre z > 2, ext4h_bajo z < -2) y de 1 d
     (ext1d_*); racha_alc / racha_baj >= 5 cierres diarios seguidos al alza / a la baja; rango diario (h-l)/c contra
     la media de los 20 anteriores: rango_exp_alc > 2x y c > o, rango_exp_baj > 2x y c < o, rango_comp < 0.5x. (9)
  F5 POSICIONAMIENTO (metrics, la fila de 5 min de T-5): doi24 = OI/OI 24 h antes - 1 (sum_open_interest).
     oi_sube_precio_sube doi24 > p90 y R24 > 0; oi_sube_precio_baja doi24 > p90 y R24 < 0; oi_baja_precio_sube
     doi24 < p10 y R24 > 0; oi_baja_precio_baja doi24 < p10 y R24 < 0; top_alto / top_bajo
     sum_toptrader_long_short_ratio > p90 / < p10; cuentas_alto / cuentas_bajo count_long_short_ratio;
     taker_alto / taker_bajo media 24 h de sum_taker_long_short_vol_ratio.                        (10)
  F6 DERIVADOS: fun_alto / fun_bajo la ultima tasa liquidada antes de T > p95 / < p5; prima_alta / prima_baja la
     media del premiumIndex de 1 min de las 8 h anteriores > p90 / < p10.                         (4)
  F7 SPOT CONTRA PERPETUO (24 h): lidera_spot_alc / _baj (Rspot24 - Rperp24) > p90 / < p10; flujo_spot_alc / _baj
     (Dspot24/Vspot24 - D24/V24) > p90 / < p10; spot_pesa / spot_ligero Vspot24/V24 > p90 / < p10. (6)
  F0 RUIDO (control negativo): una columna N(0,1) por decision (semilla fija): ruido_alto > p90, ruido_bajo < p10.
  F8 LO QUE NO SE VE: HistGradientBoostingClassifier (learning_rate 0.05, max_iter 200, max_leaf_nodes 15,
     min_samples_leaf 200, l2 1.0, sin ajuste de hiperparametros) con las 26 columnas continuas de F0..F7 + activo,
     los tres activos juntos, un modelo por esquema y lado; etiqueta neto > 0. Walk-forward: el ano Y (2022..2026)
     se predice con un modelo entrenado en las decisiones con T + tope < 1-ene-Y (embargo = horizonte). Senal: la
     probabilidad >= p95 de las predicciones fuera de muestra de los 365 dias anteriores (>= 90 dias de ellas).
     Control: el mismo esquema con las etiquetas de entrenamiento barajadas dentro de cada mes (F8_barajado).

LA CELDA = (familia, condicion, esquema, activo, lado). Sus operaciones: las decisiones donde la condicion es
    cierta, UNA abierta a la vez (una decision con la anterior aun abierta se salta). Su AZAR: todas las decisiones
    de la misma rejilla (4 h o diaria), activo, esquema, lado y tramo, sin condicion.
EL CORTE: AJUSTE decisiones antes de 2023-12-30 cuya salida tambien lo es; PRUEBA decisiones desde 2024-01-01.
LA ESTADISTICA: remuestreo de Poisson en bloques de semana ISO (B = 2000, semilla fija), el MISMO peso por semana
    para la celda y su azar: se de la media neta y de la diferencia celda - azar.
EL JUICIO:
    CANDIDATA si en el AJUSTE n >= 100 y neto medio > azar medio. m = candidatas de TODO el estudio (F0..F8).
    En la PRUEBA, n < 100: «sin medir». z = Phi^-1(1 - 0.05/m) (Bonferroni, una cola).
    PASA      cota baja neto (media - z se) > 0  Y  cota baja de (celda - azar) > 0.
    CONTEXTO  cota baja de (celda - azar) > 0, pero no la del neto.
    RUIDO     el resto.
    F8 ademas: su media en la prueba por encima de la de F8_barajado en la misma celda.
    Un PASA se dice con su activo y con su neto medio por ano de la prueba.
VEREDICTO DE FAMILIA: PAGA si alguna celda PASA; si no, CONTEXTO si alguna lo es; si no, SIN MEDIR si ninguna celda
    llega a n >= 100 en el AJUSTE y en la PRUEBA; si no, RUIDO.
CONTROL POSITIVO (en una copia en memoria, misma tuberia): (1) en cada decision de 4 h con rsi4h < 30 (calculado
    sobre la serie original) todos los precios desde el minuto T+1, perpetuo Y spot, se multiplican por 1.005: un
    salto alcista de 0.5 % justo despues de la entrada, acumulado; (2) una columna «oraculo» para F8:
    signo(c[T+1440]/o[T] - 1) + N(0, 1).
    ENMIENDA tras la primera corrida (control fallido; el resumen por familia de la real ya se habia impreso, y la
    medida real no cambia: solo el control): con 1.5 % el empuje sube
    el RSI y rompe las rachas, y rsi4h_bajo largo caia a n < 100 en el ajuste (sin medir); y sin empujar el spot,
    F7 lidera_spot_baj pasaba por el hueco perp-spot plantado. El 0.5 % se eligio SOLO por potencia (el mayor de
    {0, 0.5, 0.75, 1} % con n >= 100 en ajuste y prueba en los tres activos, esquema a; x-probe), por recuento.
    SEGUNDA ENMIENDA (control fallido otra vez, solo F2: sus celdas iban +0.1 % sobre el azar, F0 RUIDO, F8 PAGA,
    ninguna PASA sin explicar): repartido en 12 h, el empuje apenas ha llegado cuando los esquemas de 1 d tocan
    objetivo o stop. Se deja el 0.5 % y la rampa pasa a salto (EMPUJE_MIN = 1). Lo que eso dice del estudio: con
    m ~ 480 y n ~ 100-200 solo ve ventajas de ~0.3 % neto por operacion o mas; RUIDO no es «no aporta nada».
    Debe salir: F2 rsi4h_bajo largo PASA y F8 PAGA; F0 RUIDO; y toda celda que pase en el control y no en la
    medida real ha de ser larga y compartir >= 50 % de sus decisiones con rsi4h < 30. Si no: el estudio esta roto.
LIQUIDACIONES: SIN MEDIR por construccion (no hay historia fina publica: liquidationSnapshot 404).
"""

from __future__ import annotations

import math

FEE = 0.0011
ESQUEMAS = {"a": (0.01, 0.006, 1440), "b": (0.02, 0.006, 1440), "c": (0.03, 0.015, 7200),
            "d": (0.06, 0.03, 20160), "e": (0.10, 0.05, 43200)}
NOMBRE_ESQ = {"a": "1/0.6 1d", "b": "2/0.6 1d", "c": "3/1.5 5d", "d": "6/3 14d", "e": "10/5 30d"}
LISTON = {k: FEE / (tp + sl) for k, (tp, sl, _) in ESQUEMAS.items()}
PASO, DIA, CALIENTE = 240, 1440, 30
AJUSTE_HASTA, PRUEBA_DESDE = "2023-12-30", "2024-01-01"
N_MIN, B, SEMILLA = 100, 2000, 20261102
EMPUJE, EMPUJE_MIN = 0.005, 1


def resultado(o, h, lo, c, T: int, lado: int, tp: float, sl: float, tope: int,
              fun: list[tuple[int, float]] = ()) -> tuple[str, float, int]:
    """(TP|SL|VENCE, neto, minuto de salida) de entrar en o[T]; indices de minuto; fun = (minuto, tasa) liquidadas."""
    P = o[T]
    obj, stp = (P * (1 + tp), P * (1 - sl)) if lado > 0 else (P * (1 - tp), P * (1 + sl))
    ult = T + tope - 1
    tipo, net, k = "VENCE", None, ult
    for k in range(T, ult + 1):
        if (lo[k] <= stp) if lado > 0 else (h[k] >= stp):
            tipo, net = "SL", -sl - FEE
            break
        if (h[k] >= obj) if lado > 0 else (lo[k] <= obj):
            tipo, net = "TP", tp - FEE
            break
    if net is None:
        net = lado * (c[ult] / P - 1) - FEE
    return tipo, net - lado * sum(r for f, r in fun if T < f <= k), k


def rsi_wilder(x: list[float], n: int = 14) -> list[float]:
    """RSI de Wilder; NaN en las n primeras."""
    out = [math.nan] * len(x)
    if len(x) <= n:
        return out
    d = [x[i] - x[i - 1] for i in range(1, len(x))]
    ag = sum(max(v, 0) for v in d[:n]) / n
    al = sum(max(-v, 0) for v in d[:n]) / n
    for i in range(n, len(x)):
        if i > n:
            v = d[i - 1]
            ag = (ag * (n - 1) + max(v, 0)) / n
            al = (al * (n - 1) + max(-v, 0)) / n
        out[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return out
