"""EL CRITERIO de las zonas (campana BOT-3a), escrito y commiteado ANTES de mirar la prueba. Biblioteca estandar.

Lo usan `scripts/zonas_estudio.py` (el barrido, con numpy) y `tests/test_zonas_medida.py` (la reproduccion de una
fila sin numpy). La barra k es el minuto t0 + k de la historia de `scripts/zonas_historia.py`; cierra en t0+k+1.

LAS LINEAS (cada una, en la barra k, sale SOLO de barras cerradas antes de k; dia y semana en UTC, semana ISO):
    dia_ext      maximo y minimo del dia anterior
    semana_ext   maximo y minimo de la semana anterior
    perfil_poc   POC del perfil de volumen del dia anterior    perfil_va  VAH y VAL (70 % del volumen)
                 cubos de 10 bps del cierre del dia anterior; cada vela pone su quote_volume en el cubo de (h+l+c)/3;
                 el area de valor crece desde el POC hacia el vecino de mas volumen
    vwap         VWAP del dia desde 00:00 UTC        vwap_1s, vwap_2s   bandas a +-1 y +-2 desviaciones
                 (ponderadas por volumen); sin definir los primeros 60 min del dia
    rango_3d     maximo y minimo de los tres dias anteriores
    giro_1h      ultimo maximo y minimo de giro confirmado en velas de 1 h (2 velas a cada lado)
    giro_4h      lo mismo en velas de 4 h
    redondo      el numero redondo inmediato por encima y por debajo del cierre anterior; paso 10^(cifras-2):
                 BTC 65000 -> 1000, ETH 3000 -> 100, SOL 150 -> 10
ACERCARSE (distancia y velocidad): el TOQUE de la linea L en la barra k
    desde arriba   c[k-1] > L, l[k] <= L y max(h[k-60..k-1]) >= L * (1 + 0.5 %)
    desde abajo    c[k-1] < L, h[k] >= L y min(l[k-60..k-1]) <= L * (1 - 0.5 %)
    = el precio llega a la linea habiendo recorrido al menos 0.5 % hacia ella en la ultima hora. Rearme: un toque
    no cuenta si la MISMA linea conto otro en las 60 barras anteriores.
LA ENTRADA, tres modos (el lado es el de la operacion: largo o corto):
    toque     orden limite EN la linea: rebote (desde arriba largo, desde abajo corto) al precio L, o a la apertura
              si ya abre mas alla. En la barra del toque solo cuenta el stop (no se sabe si el maximo fue antes).
    reaccion  en las barras k..k+15, el primer cierre a 0.1 % de L del lado del rebote, ANTES que uno a 0.1 % del
              otro lado; la persona lo ve al cierre y entra a mercado: precio c[r+1], el camino empieza en r+2.
    ruptura   lo contrario: el primer cierre a 0.1 % al otro lado de L, antes que el rebote; entra a favor de la
              ruptura en c[r+1].
LOS ESQUEMAS (objetivo, stop), comision 5.5 bps por lado (0.11 % ida y vuelta, taker tambien en el toque: cota
    conservadora; con entrada maker el equilibrio de B baja a 42.2 %). Empate en una barra: gana el stop. Sin tocar
    ninguno en 1440 barras: sale al cierre de la ultima (VENCE), con su neto.
LOS CONTEXTOS, sabidos en k: t1d / t4h (el cierre anterior sobre o bajo la media de 20 velas diarias / de 4 h
    CERRADAS; «favor» si coincide con el lado), ses (hora UTC de k: asia 0-7, europa 7-13, eeuu 13-21, cierre
    21-24), vol (volatilidad realizada de 1 min del dia anterior sobre o bajo su mediana de los 30 dias previos),
    lider (solo ETH y SOL: el retorno de BTC en los 60 min anteriores va con el lado o contra el), fun (la ultima
    financiacion liquidada: «favor» si el lado va contra los que pagan: largo con tasa < 0, corto con tasa > 0).
EL CORTE: AJUSTE toques antes de 2023-12-30; PRUEBA toques desde 2024-01-01 con su camino de 1440 barras entero.
EL AZAR (zonas barajadas): cada linea se multiplica por (1 + u), u uniforme en +-[0.5 %, 3 %], un u por linea,
    dia y repeticion (AZAR_REPS), y pasa por las MISMAS reglas: mismas horas, mismo activo, niveles falsos.
PASA una celda (esquema, modo, clase, activo, lado, contexto) si:
    1. en el AJUSTE n >= 100 y tasa > max(equilibrio, azar del ajuste): CANDIDATA. m = numero de candidatas.
    2. en la PRUEBA n >= 100 y la cota baja de Wilson con z = Phi^-1(1 - 0.05/m) (Bonferroni, una cola) supera el
       equilibrio Y la tasa del azar de la prueba.
    n de la prueba < 100: «sin medir». La cota de Wilson al 95 % se da siempre, sin corregir, solo como lectura.
INFORMACION EXTRA: un contexto ENTRA solo si, eligiendo en el AJUSTE su mejor valor por celda base (n >= 100), la
    tasa de la PRUEBA sube sobre «todos» en media y en mas celdas de las que baja con p < 0.01 (signo, una cola).
LAS RAFAGAS de BOT-1 (app/rafagas.py, umbrales congelados, sin liquidaciones) sobre el periodo comun de los tres
    activos: CASCADA y SIN CLASE a favor, BARRIDO en contra; entrada a c[i+m+1] (decide al cierre i+m), los mismos
    esquemas, el mismo corte y la misma regla de PASA con su propia m; su azar: el mismo minuto del dia, activo y
    lado en un dia sorteado del mismo tramo (AZAR_DIAS sorteos).
"""

from __future__ import annotations

import math
from statistics import NormalDist

FEE = 0.0011
ESQUEMAS = {"A": (0.02, 0.006), "B": (0.01, 0.006), "C": (0.02, 0.0049), "D": (0.01, 0.0049)}
EQUILIBRIO = {k: (sl + FEE) / (tp + sl) for k, (tp, sl) in ESQUEMAS.items()}
HORIZONTE = 1440
ACERCA, VENTANA, REARME = 0.005, 60, 60
REACCION, ESPERA = 0.001, 15
MODOS = ("toque", "reaccion", "ruptura")
CLASES = ("dia_ext", "semana_ext", "perfil_poc", "perfil_va", "vwap", "vwap_1s", "vwap_2s", "rango_3d",
          "giro_1h", "giro_4h", "redondo")
CONTEXTOS = ("todos", "t1d:favor", "t1d:contra", "t4h:favor", "t4h:contra", "ses:asia", "ses:europa", "ses:eeuu",
             "ses:cierre", "vol:alta", "vol:baja", "lider:favor", "lider:contra", "fun:favor", "fun:contra")
DIMENSIONES = ("t1d", "t4h", "ses", "vol", "lider", "fun")
AJUSTE_HASTA, PRUEBA_DESDE = "2023-12-30", "2024-01-01"
N_MIN = 100
AZAR_REPS, AZAR_U, AZAR_DIAS = 5, (0.005, 0.03), 50
SEMILLA = 20261102


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return c - r, c + r


def z_bonferroni(m: int, alfa: float = 0.05) -> float:
    return NormalDist().inv_cdf(1 - alfa / max(m, 1))


def resultado(h, lo, c, s: int, P: float, d: int, tp: float, sl: float, toque: bool) -> tuple[str, float, int]:
    """(TP|SL|VENCE, neto, barra donde se decide). El camino empieza en la barra s; en la del toque solo el stop."""
    ult = min(s + HORIZONTE, len(c)) - 1
    obj, stp = (P * (1 + tp), P * (1 - sl)) if d > 0 else (P * (1 - tp), P * (1 + sl))
    for k in range(s, ult + 1):
        if (lo[k] <= stp) if d > 0 else (h[k] >= stp):
            return "SL", -sl - FEE, k
        if (toque and k == s) or not ((h[k] >= obj) if d > 0 else (lo[k] <= obj)):
            continue
        return "TP", tp - FEE, k
    return "VENCE", d * (c[ult] / P - 1) - FEE, ult


def es_toque(h, lo, c, k: int, L: float) -> int:
    """+1 si en k toca L desde arriba, -1 desde abajo, 0 si no (sin el rearme)."""
    if c[k - 1] > L and lo[k] <= L and max(h[k - VENTANA:k]) >= L * (1 + ACERCA):
        return 1
    if c[k - 1] < L and h[k] >= L and min(lo[k - VENTANA:k]) <= L * (1 - ACERCA):
        return -1
    return 0


def confirma(c, k: int, L: float, desde: int) -> tuple[str, int] | None:
    """('reaccion'|'ruptura', r) con el primer cierre a REACCION de L en k..k+ESPERA; desde: +1 arriba, -1 abajo."""
    for r in range(k, min(k + ESPERA + 1, len(c))):
        if c[r] >= L * (1 + REACCION):
            return ("reaccion" if desde > 0 else "ruptura"), r
        if c[r] <= L * (1 - REACCION):
            return ("ruptura" if desde > 0 else "reaccion"), r
    return None


def operacion(o, h, lo, c, k: int, L: float, desde: int, modo: str) -> tuple[int, float, int] | None:
    """(lado, precio de entrada, primera barra del camino) del toque en k, o None si ese modo no entra."""
    if modo == "toque":
        P = min(o[k], L) if desde > 0 else max(o[k], L)
        return desde, P, k
    cf = confirma(c, k, L, desde)
    if cf is None or cf[0] != modo or cf[1] + 2 >= len(c):
        return None
    lado = desde if modo == "reaccion" else -desde
    return lado, c[cf[1] + 1], cf[1] + 2
