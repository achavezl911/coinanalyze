"""LO QUE CUESTA ESTAR DENTRO · el coste de carry de los perpetuos, por simbolo y por dia.

POR QUE EXISTE ESTA RUTA Y NO SE REUSA OTRA. Se comprobo antes de escribirla, contra las 67
rutas que ya hay (ARQUITECTURA/rutas):

  /api/funding-context   UN simbolo. Da el actual, el predicho, el anualizado y medias de 8h,
                         24h y 7d. NO da serie por dia y NO da 30 dias.
  /api/daily             UN simbolo (api.py:2125). Trae el rollup diario entero.
  /api/oi                UN simbolo, serie de 5min/15min.
  /api/oi-context        UN simbolo.
  /api/liquidation-map   ya sirve las liquidaciones AGREGADAS POR PRECIO; no se toca ni se
                         duplica -es el tercer heatmap del diseño y ya existia-.

Ninguna sirve LA MATRIZ: los tres simbolos a la vez, por dia. Pedirla como tres llamadas por
simbolo y por dia son decenas de peticiones para pintar dos tarjetas.

NO HAY CRITERIO NUEVO AQUI. Solo lectura y aritmetica de unidades:
  · `fr_close`/`fr_avg` ya vienen en PORCENTAJE por periodo de 8 h. No se multiplica por cien.
    Esa fue la ultima vez que alguien lo hizo y costo publicar 302 % anuales (COLA.md 77).
  · 3 pagos al dia. 7 dias = fr x 21 · 30 dias = fr x 90 · anual = fr x 3 x 365.
    Es la MISMA convencion que ya usa app/scalp_logic.py:3447, no una nueva.
  · «quien paga»: funding positivo, pagan los largos. Tambien es la convencion de la casa
    (scalp_logic.py:3451-3456), copiada y no reinventada.

Y LO QUE SE PIDE NO ES LO QUE SE SIRVE. Un panel que pida mas historia de la que hay no se
pinta: se DECLARA. Aqui se devuelve `dias_pedidos` y `dias_servidos`, cada celda con SU numero
de muestras, y las que no existen viajan como `null` -nunca como cero- con el recuento aparte.
"""

from datetime import UTC, date, datetime
from typing import Any

import asyncpg

PAGOS_POR_DIA = 3
# Un funding medido sobre menos de un tercio del dia no describe el dia: son 288 cubos de 5 min
# en 24 h, asi que por debajo de 96 la media es de otra cosa y la celda se declara incompleta.
MUESTRAS_MINIMAS_DIA = 96


def _pct(v: Any) -> float | None:
    return None if v is None else float(v)


def coste_de_carry(fr_8h: float | None) -> dict[str, float | None]:
    """De la tasa por periodo de 8 h a lo que se paga en 7 dias, 30 y un anio.

    Sin componer: el funding se cobra sobre el NOCIONAL, no sobre el beneficio acumulado, asi
    que multiplicar es lo correcto y componer inflaria. Es la misma cuenta que hace
    scalp_logic.py:3447 para su `annualized_pct`.
    """
    if fr_8h is None:
        return {"por_8h": None, "a_7d": None, "a_30d": None, "anual": None}
    return {
        "por_8h": round(fr_8h, 6),
        "a_7d": round(fr_8h * PAGOS_POR_DIA * 7, 4),
        "a_30d": round(fr_8h * PAGOS_POR_DIA * 30, 4),
        "anual": round(fr_8h * PAGOS_POR_DIA * 365, 3),
    }


def quien_paga(fr_8h: float | None) -> str:
    """La convencion de la casa, copiada de scalp_logic.py:3451-3456."""
    if fr_8h is None:
        return "NO MEDIDO"
    if fr_8h > 0:
        return "pagan los largos"
    if fr_8h < 0:
        return "pagan los cortos"
    return "no paga nadie"


async def matriz_de_carry(
    conn: asyncpg.Connection, simbolos: list[str], dias: int
) -> dict[str, Any]:
    filas = await conn.fetch(
        """
        SELECT symbol, session_date, fr_avg, funding_5m_samples,
               oi_open, oi_close, oi_5m_samples
        FROM daily_session_agg
        WHERE symbol = ANY($1::text[]) AND session_date > current_date - $2::int
        ORDER BY session_date, symbol
        """,
        simbolos, dias,
    )
    # `fr_avg` de la sesion mas reciente COMPLETA por simbolo: la de hoy va a medias por
    # definicion, y usarla haria que el coste publicado cambiase a lo largo del dia.
    por_dia: dict[date, dict[str, dict[str, Any]]] = {}
    for f in filas:
        por_dia.setdefault(f["session_date"], {})[f["symbol"]] = dict(f)

    fechas = sorted(por_dia)
    esperadas = len(fechas) * len(simbolos)
    sin_funding = sin_oi = 0

    funding_por_dia, oi_por_dia = [], []
    for fecha in fechas:
        fila_f: dict[str, Any] = {}
        fila_o: dict[str, Any] = {}
        for s in simbolos:
            d = por_dia[fecha].get(s) or {}
            fr = _pct(d.get("fr_avg"))
            n_fr = int(d.get("funding_5m_samples") or 0)
            if fr is None:
                sin_funding += 1
                fila_f[s] = None
            else:
                fila_f[s] = {"pct_8h": round(fr, 6), "muestras": n_fr,
                             "completo": n_fr >= MUESTRAS_MINIMAS_DIA}
            oi_i, oi_f = _pct(d.get("oi_open")), _pct(d.get("oi_close"))
            n_oi = int(d.get("oi_5m_samples") or 0)
            if oi_i is None or oi_f is None or oi_i == 0:
                sin_oi += 1
                fila_o[s] = None
            else:
                fila_o[s] = {"chg_pct": round(100.0 * (oi_f / oi_i - 1.0), 3),
                             "muestras": n_oi, "completo": n_oi >= MUESTRAS_MINIMAS_DIA}
        funding_por_dia.append({"fecha": fecha.isoformat(), "valores": fila_f})
        oi_por_dia.append({"fecha": fecha.isoformat(), "valores": fila_o})

    # EL COSTE que se publica arriba sale de la media de los dias SERVIDOS, no de los pedidos:
    # promediar sobre los pedidos repartiria el gasto entre dias que no se midieron y lo dejaria
    # mas bajo de lo que es.
    coste = []
    for s in simbolos:
        vals = [v["valores"][s]["pct_8h"] for v in funding_por_dia if v["valores"].get(s)]
        media = sum(vals) / len(vals) if vals else None
        coste.append({
            "symbol": s,
            **coste_de_carry(media),
            "dias_promediados": len(vals),
            "quien_paga": quien_paga(media),
        })

    return {
        "simbolos": simbolos,
        "dias_pedidos": dias,
        "dias_servidos": len(fechas),
        "desde": fechas[0].isoformat() if fechas else None,
        "hasta": fechas[-1].isoformat() if fechas else None,
        "coste": coste,
        "funding_por_dia": funding_por_dia,
        "oi_por_dia": oi_por_dia,
        "cobertura": {
            "celdas_esperadas": esperadas,
            "celdas_sin_funding": sin_funding,
            "celdas_sin_oi": sin_oi,
            # Se dice con letras y no solo con numeros: la tarjeta tiene que poder rotularlo sin
            # volver a razonar. Un hueco NO es un cero y no se pinta como tal.
            "nota": (
                f"servidos {len(fechas)} de {dias} dias pedidos; "
                f"{sin_funding} de {esperadas} celdas sin funding y {sin_oi} sin interes abierto. "
                "Las celdas sin dato van vacias, NUNCA a cero."
            ),
        },
        "unidades": "funding en % por periodo de 8 h, sin multiplicar por cien (COLA.md 77)",
        "as_of": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
