"""Las RAFAGAS: detectar un movimiento grande en <= 60 s y clasificarlo en 1-3 min (campana BOT-1).

QUE ES. La primera pieza del bot. Un detector que, en cada cierre de minuto y por activo, dice si acaba de empezar
una rafaga, y un clasificador que en los tres minutos siguientes la llama CASCADA (sigue) o BARRIDO (se da la vuelta),
o la deja SIN CLASE si ninguna regla se cumple: no se fuerza. Lo que pasa DESPUES de cada clase se mide fuera de aqui
(`scripts/rafagas_estudio.py`, K116): este modulo no promete nada, describe.

FUNCIONES PURAS: sin base, sin red, sin reloj. Entran barras de 1 min CONTIGUAS y ALINEADAS entre activos (mismo
primer minuto, mismo largo; un minuto sin operaciones lleva el ultimo precio y volumen 0) y salen indices de barra.

LA RAFAGA en el cierre de la barra i, con ventana de W minutos:
    r     = ln(c[i] / c[i-W])                        s = signo de r
    sigma = desviacion tipica de los BASE retornos de 1 min ANTERIORES a la ventana
    z     = r / (sigma * sqrt(W))
    v     = volumen de la ventana / (W * volumen medio por minuto de esos BASE minutos)
    imb   = (compra - venta) / (compra + venta) en la ventana   (USD del agresor)
    rafaga si s*z >= Z, v >= M y s*imb >= D; despues el activo calla CALLA minutos.

LA CLASE, en los cierres i+1 .. i+DECIDE (la primera regla que se cumple decide):
    BARRIDO  lo devuelto gb = s*(ext - c) / s*(ext - c[i-W]) >= G (ext: el extremo de la rafaga hasta ese minuto)
             y el delta de ESE minuto va contra la rafaga
    CASCADA  el cierre sigue mas alla de c[i], el delta de CADA minuto desde i va a favor, y al menos otro activo
             alineado (s*z >= ALINEA en algun cierre de i a i+m) o, si se dan liquidaciones, los bloques de 5 min
             CERRADOS del lado que empuja crecen: ultimo > anterior > 0 (cortos si sube, largos si baja)
    SIN CLASE si en i+DECIDE no se cumplio ninguna.

Los umbrales se AJUSTARON en 2026-03-01..08-31 y se CONGELARON antes de mirar la prueba (entrega de la campana).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

CASCADA, BARRIDO, SIN_CLASE = "CASCADA", "BARRIDO", "SIN CLASE"


@dataclass(frozen=True)
class Umbrales:
    W: int  # minutos de la ventana de la rafaga
    Z: float  # retorno en desviaciones de la volatilidad reciente
    M: float  # multiplo de volumen
    D: float  # desequilibrio minimo del delta, con el signo de la rafaga
    G: float  # fraccion devuelta que hace BARRIDO
    BASE: int = 120  # minutos de volatilidad y volumen de referencia
    CALLA: int = 60  # minutos sin otra rafaga en el mismo activo
    ALINEA: float = 2.0  # z de otro activo que cuenta como alineado
    DECIDE: int = 3  # minutos para clasificar


# CONGELADOS el 2026-10-24 antes de mirar la prueba: el punto elegido de 144 en el ajuste 2026-03-01..08-31
# (`scripts/rafagas_estudio.py ajuste`, muestra d62b7618617f8de4): 276 rafagas, 108 CASCADAS, 33 BARRIDOS, la
# politica CASCADA->(a) / BARRIDO->(c) a +0.0131 % neto por operacion. Z=7 es el BORDE de la rejilla.
UMBRALES = Umbrales(W=5, Z=7.0, M=2.0, D=0.25, G=0.5)


@dataclass(frozen=True)
class Serie:
    """Barras de 1 min contiguas: la barra k es el minuto t0 + k (epoch // 60) y cierra en (t0 + k + 1) * 60."""

    t0: int
    c: list[float]
    hi: list[float]
    lo: list[float]
    buy: list[float]
    sell: list[float]


def rasgos(se: Serie, W: int, base: int = 120) -> tuple[list, list, list]:
    """(z, v, imb) por barra; None donde no hay historia o la base es plana."""
    n = len(se.c)
    lr = [0.0] * n
    for k in range(1, n):
        lr[k] = math.log(se.c[k] / se.c[k - 1])
    p1 = [0.0] * (n + 1)
    p2 = [0.0] * (n + 1)
    pv = [0.0] * (n + 1)
    pd = [0.0] * (n + 1)
    for k in range(n):
        p1[k + 1] = p1[k] + lr[k]
        p2[k + 1] = p2[k] + lr[k] * lr[k]
        pv[k + 1] = pv[k] + se.buy[k] + se.sell[k]
        pd[k + 1] = pd[k] + se.buy[k] - se.sell[k]
    z: list = [None] * n
    v: list = [None] * n
    imb: list = [None] * n
    for i in range(W + base, n):
        a, b = i - W - base + 1, i - W + 1  # retornos y volumenes de referencia: [a, b)
        s1, s2 = p1[b] - p1[a], p2[b] - p2[a]
        var = (s2 - s1 * s1 / base) / (base - 1)
        vb = (pv[b] - pv[a]) / base
        vw = pv[i + 1] - pv[b]
        if var <= 0 or vb <= 0 or vw <= 0:
            continue
        z[i] = math.log(se.c[i] / se.c[i - W]) / math.sqrt(var * W)
        v[i] = vw / (W * vb)
        imb[i] = (pd[i + 1] - pd[b]) / vw
    return z, v, imb


def detecta_rasgos(z: list, v: list, imb: list, Z: float, M: float, D: float, calla: int = 60,
                   desde: int = 0, hasta: int | None = None) -> list[tuple[int, int]]:
    """[(i, s)] de las rafagas en [desde, hasta)."""
    out: list[tuple[int, int]] = []
    libre = desde
    for i in range(desde, len(z) if hasta is None else hasta):
        zi = z[i]
        if i < libre or zi is None:
            continue
        s = 1 if zi > 0 else -1
        if s * zi >= Z and v[i] >= M and s * imb[i] >= D:
            out.append((i, s))
            libre = i + calla
    return out


def detecta(se: Serie, u: Umbrales = UMBRALES) -> list[tuple[int, int]]:
    z, v, imb = rasgos(se, u.W, u.BASE)
    return detecta_rasgos(z, v, imb, u.Z, u.M, u.D, u.CALLA)


def bloques_crecen(liq: dict[int, tuple[float, float]], cierre: int, s: int) -> bool:
    """Ultimo bloque de 5 min CERRADO en `cierre` (epoch s) > el anterior > 0, del lado que empuja.

    liq: {inicio del bloque (epoch s): (USD de largos, USD de cortos)}; bloque sin fila = 0.
    """
    t1 = cierre // 300 * 300 - 300
    lado = 1 if s > 0 else 0  # sube: se liquidan cortos; baja: largos
    b1 = liq.get(t1, (0.0, 0.0))[lado]
    b0 = liq.get(t1 - 300, (0.0, 0.0))[lado]
    return b1 > b0 > 0


def clasifica(se: Serie, i: int, s: int, u: Umbrales, z_otras: list[list],
              liq: dict[int, tuple[float, float]] | None = None) -> tuple[str, int] | None:
    """(clase, m) con m los minutos tras la deteccion en que se decidio; None si faltan barras para decidir.

    z_otras: los z de los otros activos con la MISMA W, alineados con `se`. liq=None: variante sin liquidaciones.
    """
    base = se.c[i - u.W]
    ext = base
    for k in range(i - u.W + 1, i + 1):
        ext = max(ext, se.hi[k]) if s > 0 else min(ext, se.lo[k])
    for m in range(1, u.DECIDE + 1):
        k = i + m
        if k >= len(se.c):
            return None
        ext = max(ext, se.hi[k]) if s > 0 else min(ext, se.lo[k])
        c = se.c[k]
        delta = se.buy[k] - se.sell[k]
        if s * (ext - c) >= u.G * s * (ext - base) and s * delta < 0:
            return BARRIDO, m
        if s * (c - se.c[i]) > 0 and all(s * (se.buy[j] - se.sell[j]) > 0 for j in range(i + 1, k + 1)):
            alin = sum(1 for zo in z_otras
                       if any(zo[j] is not None and s * zo[j] >= u.ALINEA for j in range(i, k + 1)))
            if alin >= 1 or (liq is not None and bloques_crecen(liq, (se.t0 + k + 1) * 60, s)):
                return CASCADA, m
    return SIN_CLASE, u.DECIDE
