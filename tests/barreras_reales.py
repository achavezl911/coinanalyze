"""Barreras salidas del productor REAL (`price_barrier_read`), no escritas a mano (dz4 N1).

Las diarias son las del doble de fable-dz4 (`scripts/fable_dz4_setups.py`): zonas de 0.30 de
ancho en 99.35-99.65, 103.35-103.65, 109.35-109.65, 110.35-110.65 y 120.35-120.65. Una barrera
escrita a mano puede describir lo que el productor nunca emite (una resistencia bajo el precio,
una zona activa que no contiene el precio) y asi se escondio Z-01.
"""

from __future__ import annotations

from app.interpretation import price_barrier_read


def _diarias() -> list[dict]:
    puntos = [100, 110, 104, 120, 110, 120, 100, 110, 100, 120, 110, 116]
    cierres = [float(puntos[0])]
    for a, b in zip(puntos, puntos[1:], strict=False):
        pasos = max(2, round(abs(b - a) / 2.5))
        cierres += [a + (b - a) * (i + 1) / pasos for i in range(pasos)]
    return [{"session_date": f"d{i:03d}", "price_high": c + 0.5, "price_low": c - 0.5,
             "price_close": c, "volume_usd": 1e9, "cvd_spot_usd": None} for i, c in enumerate(cierres)]


DIARIAS = _diarias()


def barreras(precio: float, volumen: float = 2.0) -> dict:
    return price_barrier_read(DIARIAS, [], precio, live={"volume_multiple_15m": volumen})
