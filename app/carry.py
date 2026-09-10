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

from datetime import UTC, date, datetime, timedelta
from typing import Any

import asyncpg

PAGOS_POR_DIA = 3

# EL UMBRAL NO SE ELIGE AQUI: SE HEREDA DE QUIEN DECIDE.
#
# Aqui habia un `MUESTRAS_MINIMAS_DIA = 96` -el 33 % de los 288 cubos de 5 min de un dia- que
# escribi el 2026-09-08 sin mirar que usaba el agregador. El agregador usa
# `SESSION_MIN_COVERAGE_RATIO = 0.95` (daily_agg.py:55) y NO PUBLICA un grupo por debajo de eso,
# asi que toda celda que llega aqui con valor tiene ya >= 274 muestras y mi `n >= 96` ERA
# SIEMPRE CIERTO: no era un umbral laxo, era un umbral MUERTO que daba tranquilidad sin medir
# nada.
#
# Manda el del agregador porque es el unico que decide algo -si el numero existe-; este solo
# ponia una etiqueta sobre un numero que aquel ya habia dejado pasar. Dos criterios para la
# misma pregunta es exactamente como se llega a que uno de los dos no sirva.
from app.daily_agg import SESSION_MIN_COVERAGE_RATIO  # noqa: E402
from app.data_gaps import coverage_entry  # noqa: E402


def celda_completa(muestras: int, esperadas: int) -> bool:
    """La MISMA regla que aplica el agregador para decidir si publica. Un solo sitio."""
    return esperadas > 0 and muestras * 100 >= esperadas * int(SESSION_MIN_COVERAGE_RATIO * 100)


# 288 cubos de 5 min en 24 h. Se pasa como esperadas para que la regla sea la de arriba y no
# otra escrita al lado.
CUBOS_5M_POR_DIA = 288


def _pct(v: Any) -> float | None:
    return None if v is None else float(v)


def _iso(v: Any) -> str | None:
    return None if v is None else v.isoformat()


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
               oi_open, oi_close, oi_5m_samples, updated_at
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
    # LA VENTANA QUE SE PIDIO, no la que se sirvio. `current_date` se lee del motor y no del
    # reloj de este proceso porque es el motor quien la evalua ahi arriba: si los dos no
    # coincidieran, la ventana declarada no seria la consultada.
    # Y las celdas ESPERADAS salen de `dias`, no de `len(fechas)`: si un dia entero falta en la
    # base no aparece en `fechas`, asi que `esperadas` encoge con el hueco y `complete` diria
    # que si. Con la ventana pedida delante, un dia que falta se ve.
    hoy = await conn.fetchval("SELECT current_date")
    fin_ventana = datetime(hoy.year, hoy.month, hoy.day, tzinfo=UTC) + timedelta(days=1)
    ini_ventana = fin_ventana - timedelta(days=dias)
    celdas_pedidas = dias * len(simbolos)
    sin_funding = sin_oi = 0
    # CADA HUECO CON LA FECHA DE SU AFIRMACION. Una celda vacia sigue siendo `null` -no se le
    # cambia la forma, que es lo que consumen el panel y el promedio-, pero aqui al lado queda
    # dicho CUANDO se calculo la fila que la dejo vacia. Sin eso, «no pude medir» se lee como
    # «no hay dato», y a veces el dato existe desde entonces: las tres filas del 2026-08-28
    # decian 219 de 288 con la fuente ya completa.
    sin_dato: list[dict[str, Any]] = []

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
                sin_dato.append({
                    "fecha": fecha.isoformat(), "symbol": s, "grupo": "funding",
                    "medido_el": _iso(d.get("updated_at")),
                    "muestras_cuando_se_calculo": n_fr,
                    "por_que": (
                        f"tenia {n_fr} de {CUBOS_5M_POR_DIA} muestras cuando se calculo, y el "
                        f"agregador no publica por debajo del "
                        f"{int(SESSION_MIN_COVERAGE_RATIO * 100)} %"
                    ),
                })
            else:
                fila_f[s] = {"pct_8h": round(fr, 6), "muestras": n_fr,
                             "completo": celda_completa(n_fr, CUBOS_5M_POR_DIA)}
            oi_i, oi_f = _pct(d.get("oi_open")), _pct(d.get("oi_close"))
            n_oi = int(d.get("oi_5m_samples") or 0)
            if oi_i is None or oi_f is None or oi_i == 0:
                sin_oi += 1
                fila_o[s] = None
                sin_dato.append({
                    "fecha": fecha.isoformat(), "symbol": s, "grupo": "interes_abierto",
                    "medido_el": _iso(d.get("updated_at")),
                    "muestras_cuando_se_calculo": n_oi,
                    "por_que": f"tenia {n_oi} de {CUBOS_5M_POR_DIA} muestras cuando se calculo",
                })
            else:
                fila_o[s] = {"chg_pct": round(100.0 * (oi_f / oi_i - 1.0), 3),
                             "muestras": n_oi, "completo": celda_completa(n_oi, CUBOS_5M_POR_DIA)}
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
        "sin_dato": sin_dato,
        # LA VENTANA, EN EL VOCABULARIO DE LA CASA. `cobertura` de aqui abajo se queda tal
        # cual -el panel la lee y no se le cambia la forma-; esto es lo MISMO dicho como lo
        # dicen las otras series, que es lo que permite compararlas sin traducir a mano.
        # Las dos patas van separadas: un promedio que necesita funding Y open interest no
        # esta completo si le falta una, y `sources` deja dicho cual.
        "coverage": {
            "served_window": coverage_entry(
                ini_ventana,
                fin_ventana,
                sources=(
                    ("funding_dia_simbolo", celdas_pedidas, esperadas - sin_funding),
                    ("oi_dia_simbolo", celdas_pedidas, esperadas - sin_oi),
                ),
            )
        },
        "cobertura": {
            "celdas_esperadas": esperadas,
            "celdas_sin_funding": sin_funding,
            "celdas_sin_oi": sin_oi,
            # Se dice con letras y no solo con numeros: la tarjeta tiene que poder rotularlo sin
            # volver a razonar. Un hueco NO es un cero y no se pinta como tal.
            "nota": (
                f"servidos {len(fechas)} de {dias} dias pedidos; "
                f"{sin_funding} de {esperadas} celdas sin funding y {sin_oi} sin interes abierto. "
                "Las celdas sin dato van vacias, NUNCA a cero, y «sin_dato» dice de "
                "CUANDO es esa afirmacion: la fuente puede haberse completado despues."
            ),
        },
        "unidades": "funding en % por periodo de 8 h, sin multiplicar por cien (COLA.md 77)",
        "as_of": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
