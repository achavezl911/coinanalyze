"""Direccion y SETUP como dos cosas distintas, con logica propia por tipo de setup.

Antes existia un unico selector de hipotesis en el que "esperando ruptura", "esperando
rechazo", "esperando reversion" y "esperando continuacion" recorrian exactamente el mismo
codigo: al no tener direccion, todo caia en PENDIENTE y las cuatro opciones producian la
misma salida. Elegir una u otra no cambiaba nada.

Aqui la direccion (long / short / neutral) dice hacia donde mira el operador, y el setup dice
QUE tiene que pasar para que la tesis se confirme. Cada setup declara:

* sus dependencias OBLIGATORIAS: sin ellas el veredicto es NO EVALUABLE, no PENDIENTE;
* sus requisitos, cada uno con su propia lectura sobre los datos publicados;
* que requisitos INVALIDAN la tesis si se incumplen, que es lo que distingue de verdad a un
  rechazo de una ruptura.

Ningun requisito inventa un dato: si el observable no existe, ese requisito queda
`no_evaluable` y se dice cual falta.
"""

from __future__ import annotations

from typing import Any

DIRECTIONS: dict[str, dict[str, Any]] = {
    "long": {"label": "Long", "sign": 1},
    "short": {"label": "Short", "sign": -1},
    "neutral": {"label": "Neutral", "sign": 0},
}

SETUP_LABELS: dict[str, str] = {
    "ninguno": "Ninguno",
    "ruptura": "Ruptura",
    "rechazo": "Rechazo",
    "reversion": "Reversión",
    "continuacion": "Continuación",
}

# Compatibilidad con los valores que ya estan guardados en el navegador del operador y en
# los enlaces antiguos: la hipotesis unica se traduce al par (direccion, setup).
LEGACY_HYPOTHESES: dict[str, tuple[str, str]] = {
    "long": ("long", "ninguno"),
    "short": ("short", "ninguno"),
    "neutral": ("neutral", "ninguno"),
    "esperando_ruptura": ("neutral", "ruptura"),
    "esperando_rechazo": ("neutral", "rechazo"),
    "esperando_reversion": ("neutral", "reversion"),
    "esperando_continuacion": ("neutral", "continuacion"),
}

STATES = ("NO EVALUABLE", "PENDIENTE", "CANDIDATO", "CONFIRMADO", "FALLIDO")

VOLUME_PUSH_MULTIPLE = 1.0
"""Multiplo minimo del volumen de 15 m sobre su mediana para llamarlo empuje.

Es el mismo `flow_requirement` que ya publicaba `price_barrier_read` ("volumen 15m >= 1.0x
normal"): se reutiliza en vez de introducir un umbral nuevo sin medir.
"""

CUMPLE, NO_CUMPLE, PENDIENTE, NO_EVALUABLE = "cumple", "no_cumple", "pendiente", "no_evaluable"

CRITICAL, CONFIRMATION, SECONDARY = "CRITICAL", "CONFIRMATION", "SECONDARY"
"""Jerarquia de requisitos.

CRITICAL      lo que DEFINE el setup. Si uno no se puede evaluar, no hay confirmacion
              posible: se estaria dando por bueno algo que no se ha mirado.
CONFIRMATION  refuerza la tesis. Se exige un minimo, no todos.
SECONDARY     aporta contexto; no decide.

Antes no existia la distincion y `evaluate_setup()` devolvia CONFIRMADO con la aceptacion,
el retest y el regreso al rango en NO EVALUABLE: confirmaba una ruptura por "precio por
encima de la resistencia + delta positivo", que es justo lo que no basta.
"""

MIN_CONFIRMATIONS = 2
"""Confirmaciones que hay que cumplir para pasar de CANDIDATO a CONFIRMADO.

Convencion declarada (se publica en la respuesta), no un resultado backtesteado. Si el setup
tiene menos requisitos de confirmacion que este minimo, se exigen todos los que tenga.
"""

MIN_COVERAGE_PCT = 60.0
"""Fraccion minima de requisitos EVALUABLES para poder confirmar.

Con la mitad de los requisitos mudos, cumplir los que quedan no es una confirmacion.
"""


def split_hypothesis(value: str | None) -> tuple[str, str]:
    """Traduce un valor antiguo al par (direccion, setup). Desconocido -> neutral/ninguno."""
    if value in LEGACY_HYPOTHESES:
        return LEGACY_HYPOTHESES[value]
    return ("neutral", "ninguno")


# PR27_SCIENTIFIC_SIGNAL_OI_HELPERS_V1_BEGIN
def _sign(value: float | None) -> int | None:
    if value is None:
        return None
    return 0 if value == 0 else (1 if value > 0 else -1)


def _flow_check(
    nombre: str, valor: float | None, signo: int, etiqueta: str, nivel: str = CONFIRMATION
) -> dict[str, Any]:
    """Un delta a favor de la direccion cumple; en contra, no; sin dato, no evaluable.

    Vale para DELTAS (flujo ejecutado, que si tiene lado). NO vale para el Open Interest:
    para eso esta `_oi_check`.
    """
    s = _sign(valor)
    if s is None:
        return _req(nombre, NO_EVALUABLE, f"{etiqueta}: sin dato", nivel=nivel)
    if signo == 0:
        return _req(nombre, PENDIENTE, f"{etiqueta} {valor:+.0f}; la direccion es neutral", nivel=nivel)
    if s == 0:
        return _req(nombre, PENDIENTE, f"{etiqueta} plano", nivel=nivel)
    return _req(
        nombre,
        CUMPLE if s == signo else NO_CUMPLE,
        f"{etiqueta} {valor:+.0f}",
        nivel=nivel,
    )


def _req(
    nombre: str,
    estado: str,
    detalle: str,
    invalida: bool = False,
    nivel: str = SECONDARY,
) -> dict[str, Any]:
    return {
        "requisito": nombre,
        "estado": estado,
        "detalle": detalle,
        "invalida": invalida,
        "nivel": nivel,
    }


# ---------------- Open Interest: es un ESTADO, no una direccion ----------------
OI_FLAT_PCT = 0.05
"""|Δ%| de OI por debajo del cual la variacion no se distingue del ruido de la ventana.

Convencion declarada, no medida: se publica junto al veredicto para que se pueda discutir.
"""

OI_EXTREME_MULTIPLE = 6.0
"""Multiplo de `OI_FLAT_PCT` a partir del cual se habla de extremo CUANDO NO hay baseline.

Con baseline medida manda la banda (`oi_band`) o el z robusto, que es lo defendible; esto es
solo la red de seguridad, y la respuesta declara cual de los dos decidio.
"""

EXPANSION = "EXPANSION"
CONTRACTION = "CONTRACTION"
FLAT = "FLAT"
EXTREME_EXPANSION = "EXTREME_EXPANSION"
EXTREME_CONTRACTION = "EXTREME_CONTRACTION"
OI_NO_EVALUABLE = "NO_EVALUABLE"


def classify_oi(
    chg_pct: float | None,
    *,
    band: str | None = None,
    robust_z: float | None = None,
    oi_to_volume: float | None = None,
    timeframe: str | None = None,
) -> dict[str, Any]:
    """Clasifica el Open Interest como ESTADO de posicionamiento, sin direccion.

    El signo de ΔOI NO es long/short: el OI sube cuando se abren contratos, los abra quien
    los abra, y baja cuando se cierran, los cierre quien los cierre. Convertir `ΔOI > 0` en
    un voto LONG era exactamente el mismo error que votar con el diferencial spot-futuros.

    Lo que aporta el OI es si hay posicionamiento NUEVO o cierre; la direccion la tiene que
    poner el precio y el flujo, y eso se compone en `oi_price_reading()`.
    """
    if chg_pct is None:
        return {
            "state": OI_NO_EVALUABLE,
            "chg_pct": None,
            "band": band,
            "robust_z": robust_z,
            "oi_to_volume": oi_to_volume,
            "timeframe": timeframe,
            "basis": "sin lectura de OI",
            "directional": False,
        }
    magnitud = abs(chg_pct)
    if magnitud < OI_FLAT_PCT:
        estado, base = FLAT, f"|Δ| {magnitud:.3f}% por debajo del piso {OI_FLAT_PCT}%"
    else:
        expandiendo = chg_pct > 0
        # El extremo lo decide la distribucion medida si existe; si no, un multiplo del piso,
        # y se dice cual de los dos mando.
        if band in ("alto", "extremo"):
            extremo, base = True, f"banda medida '{band}'"
        elif robust_z is not None and abs(robust_z) >= 3.0:
            extremo, base = True, f"z robusto {robust_z:+.2f}"
        else:
            extremo = magnitud >= OI_FLAT_PCT * OI_EXTREME_MULTIPLE
            base = (
                f"|Δ| {magnitud:.3f}% contra {OI_FLAT_PCT * OI_EXTREME_MULTIPLE:.2f}% "
                "(sin baseline: multiplo declarado del piso)"
            )
        if expandiendo:
            estado = EXTREME_EXPANSION if extremo else EXPANSION
        else:
            estado = EXTREME_CONTRACTION if extremo else CONTRACTION
    return {
        "state": estado,
        "chg_pct": chg_pct,
        "band": band,
        "robust_z": robust_z,
        "oi_to_volume": oi_to_volume,
        "timeframe": timeframe,
        "basis": base,
        # Marca explicita para quien consuma esto: el estado NO lleva direccion.
        "directional": False,
    }


_OI_EXPANDING = (EXPANSION, EXTREME_EXPANSION)
_OI_CONTRACTING = (CONTRACTION, EXTREME_CONTRACTION)


def oi_price_reading(
    price_move_pct: float | None,
    oi: dict[str, Any],
    *,
    fut_delta: float | None = None,
    spot_delta: float | None = None,
    funding_pct: float | None = None,
    basis_bps: float | None = None,
    liq_skew: float | None = None,
) -> dict[str, Any]:
    """Lectura CONTEXTUAL de precio + OI + flujo. No es una relacion causal demostrada.

    Los cuatro cuadrantes clasicos, dichos con el cuidado que permiten los datos:

      precio ↑ + OI ↑  -> expansion: posicionamiento NUEVO en el sentido de la subida
      precio ↓ + OI ↑  -> expansion: posicionamiento NUEVO en el sentido de la bajada
      precio ↑ + OI ↓  -> cierre de cortos / toma de beneficios; NO demuestra compra nueva
      precio ↓ + OI ↓  -> desapalancamiento o cierre de largos; NO demuestra venta nueva

    `supports` dice con QUE direccion es compatible la lectura, y vale None cuando la
    combinacion no sostiene ninguna: un cierre de posiciones no es una tesis direccional.
    """
    estado = oi.get("state", OI_NO_EVALUABLE)
    signo_precio = _sign(price_move_pct)
    if estado == OI_NO_EVALUABLE or signo_precio is None:
        return {
            "quadrant": None,
            "oi_state": estado,
            "price_direction": signo_precio,
            "supports": None,
            "new_positioning": None,
            "reading": "sin OI o sin movimiento de precio: no hay lectura conjunta",
            "caveat": "No se infiere nada de un solo lado del cuadrante.",
        }
    if estado == FLAT or signo_precio == 0:
        return {
            "quadrant": "sin_expansion",
            "oi_state": estado,
            "price_direction": signo_precio,
            "supports": None,
            "new_positioning": False,
            "reading": "el OI no se movio de forma apreciable: no hay posicionamiento nuevo",
            "caveat": "Un OI plano no confirma ni desmiente la direccion del precio.",
        }

    expande = estado in _OI_EXPANDING
    if expande:
        cuadrante = "expansion_alcista" if signo_precio > 0 else "expansion_bajista"
        soporta = signo_precio
        lectura = (
            "precio y OI suben a la vez: expansion compatible con continuacion alcista"
            if signo_precio > 0
            else "el precio baja mientras el OI sube: expansion compatible con presion short"
        )
        aviso = (
            "Compatible, no demostrado: el OI no dice quien abrio el contrato. "
            "La direccion la sostiene el flujo, no el OI."
        )
    else:
        cuadrante = "cierre_en_subida" if signo_precio > 0 else "cierre_en_bajada"
        soporta = None
        lectura = (
            "el precio sube mientras el OI cae: cierre de posiciones cortas o toma de "
            "beneficios; NO demuestra compras nuevas"
            if signo_precio > 0
            else "el precio baja mientras el OI cae: desapalancamiento o cierre/liquidacion "
            "de largos; NO demuestra ventas nuevas"
        )
        aviso = "Un movimiento sostenido por cierres no acredita posicionamiento nuevo."

    confirmacion_flujo = _sign(fut_delta)
    return {
        "quadrant": cuadrante,
        "oi_state": estado,
        "price_direction": signo_precio,
        # Con QUE direccion es compatible. None = con ninguna: no sirve de voto.
        "supports": soporta,
        "new_positioning": expande,
        "flow_agrees": (
            None if confirmacion_flujo is None or soporta is None
            else confirmacion_flujo == soporta
        ),
        "inputs": {
            "price_move_pct": price_move_pct,
            "oi_chg_pct": oi.get("chg_pct"),
            "fut_delta": fut_delta,
            "spot_delta": spot_delta,
            "funding_pct": funding_pct,
            "basis_bps": basis_bps,
            "liq_skew": liq_skew,
        },
        "reading": lectura,
        "caveat": aviso,
    }


# PR27_SCIENTIFIC_SIGNAL_OI_HELPERS_V1_END


def _oi_check(nombre: str, ctx: dict[str, Any], signo: int) -> dict[str, Any]:
    """Requisito de OI: exige POSICIONAMIENTO NUEVO en el sentido de la tesis.

    Sustituye al `_flow_check` que trataba ΔOI como si fuera un delta direccional.
    """
    oi = classify_oi(
        ctx.get("oi_chg_pct"),
        band=ctx.get("oi_band"),
        robust_z=ctx.get("oi_robust_z"),
        oi_to_volume=ctx.get("oi_to_volume"),
        timeframe=ctx.get("oi_timeframe"),
    )
    lectura = oi_price_reading(
        ctx.get("reaction_pct"), oi, fut_delta=ctx.get("fut_delta"),
        spot_delta=ctx.get("spot_delta"), liq_skew=ctx.get("liq_skew"),
    )
    if lectura["quadrant"] is None:
        return _req(nombre, NO_EVALUABLE, lectura["reading"], nivel=CONFIRMATION)
    if signo == 0:
        return _req(nombre, PENDIENTE, f"{lectura['reading']}; la direccion es neutral",
                    nivel=CONFIRMATION)
    if lectura["supports"] is None:
        # Cierre de posiciones o OI plano: no sostiene NINGUNA direccion, tampoco la contraria.
        return _req(nombre, PENDIENTE, lectura["reading"], nivel=CONFIRMATION)
    return _req(
        nombre,
        CUMPLE if lectura["supports"] == signo else NO_CUMPLE,
        f"{oi['state']} · {lectura['reading']}",
        nivel=CONFIRMATION,
    )


def _beyond(price: float | None, level: float | None, signo: int) -> bool | None:
    """¿El precio esta al otro lado del nivel en el sentido de la direccion?"""
    if price is None or level is None or signo == 0:
        return None
    return price > level if signo > 0 else price < level


# ---------------- un evaluador por setup ----------------


def _eval_ruptura(ctx: dict[str, Any], signo: int) -> list[dict[str, Any]]:
    """Ruptura. CRITICOS: la barrera, el cierre al otro lado, la ACEPTACION y no volver
    dentro. Sin aceptacion medida no hay ruptura confirmada: "precio por encima de la
    resistencia + delta positivo" describe un toque, no una ruptura sostenida."""
    price = ctx.get("price")
    level = ctx.get("breakout_boundary")
    mas_alla = _beyond(price, level, signo)

    reqs = [
        _req(
            "barrera relevante",
            CUMPLE if level is not None else NO_EVALUABLE,
            f"frontera {level}" if level is not None else "sin frontera de ruptura identificada",
            nivel=CRITICAL,
        ),
        _req(
            "cierre mas alla de la barrera",
            NO_EVALUABLE if mas_alla is None else (CUMPLE if mas_alla else PENDIENTE),
            (
                "sin precio o sin frontera de ruptura"
                if mas_alla is None
                else f"precio {price} respecto de frontera {level}"
            ),
            nivel=CRITICAL,
        ),
    ]
    # Umbral ya declarado en el propio dashboard (`flow_requirement` de price_barrier_read):
    # volumen de 15 m al menos 1.0x su mediana de 36 h. No es un numero nuevo.
    multiplo = ctx.get("volume_multiple")
    reqs.append(
        _req(
            "volumen de empuje",
            NO_EVALUABLE if multiplo is None else (CUMPLE if multiplo >= VOLUME_PUSH_MULTIPLE else NO_CUMPLE),
            "sin baseline de volumen"
            if multiplo is None
            else f"{multiplo:.2f}x la mediana de 15 m (minimo {VOLUME_PUSH_MULTIPLE:g}x)",
            nivel=CONFIRMATION,
        )
    )
    reqs.append(_flow_check("delta spot", ctx.get("spot_delta"), signo, "delta spot", CONFIRMATION))
    reqs.append(_flow_check("delta futuros", ctx.get("fut_delta"), signo, "delta futuros", CONFIRMATION))
    barras = ctx.get("bars_closed_beyond")
    reqs.append(
        _req(
            "aceptacion fuera del nivel",
            NO_EVALUABLE if barras is None else (CUMPLE if barras >= 2 else PENDIENTE),
            "sin conteo de cierres" if barras is None else f"{barras} cierres al otro lado",
            # CRITICO: sin aceptacion, un cierre al otro lado es un toque, no una ruptura.
            nivel=CRITICAL,
        )
    )
    retest = ctx.get("retest_done")
    reqs.append(
        _req(
            "retest del nivel",
            NO_EVALUABLE if retest is None else (CUMPLE if retest else PENDIENTE),
            "sin observacion de retest" if retest is None else ("retest hecho" if retest else "sin retest todavia"),
            # El retest refuerza, pero hay rupturas validas que no lo hacen.
            nivel=SECONDARY,
        )
    )
    reqs.append(_oi_check("open interest", ctx, signo))
    share = ctx.get("book_bid_share")
    reqs.append(
        _req(
            "libro a favor",
            NO_EVALUABLE
            if share is None or signo == 0
            else (CUMPLE if (share - 0.5) * signo > 0 else NO_CUMPLE),
            "sin libro" if share is None else f"bid share {share:.2f}",
            nivel=SECONDARY,
        )
    )
    # Lo que MATA una ruptura: volver dentro despues de haber cerrado fuera.
    dentro = ctx.get("returned_inside")
    reqs.append(
        _req(
            "no vuelve dentro del rango",
            NO_EVALUABLE if dentro is None else (NO_CUMPLE if dentro else CUMPLE),
            "sin observacion" if dentro is None else ("el precio volvio dentro" if dentro else "sigue fuera"),
            invalida=True,
            nivel=CRITICAL,
        )
    )
    return reqs


def _eval_rechazo(ctx: dict[str, Any], signo: int) -> list[dict[str, Any]]:
    """Rechazo: la direccion apunta EN CONTRA del nivel tocado; se espera que aguante.

    CRITICOS: el contacto, la falta de aceptacion al otro lado, el retorno al rango y que no
    haya cierres aceptados fuera. Sin el retorno medido, "el precio tocó y hay flujo
    contrario" describe una reaccion, no un rechazo consumado.
    """
    price, level = ctx.get("price"), ctx.get("barrier_level")
    tocado = ctx.get("touched_level")
    fuera = _beyond(price, level, -signo) if signo else None
    reaccion = ctx.get("reaction_pct")
    reqs = [
        _req(
            "contacto con el nivel",
            NO_EVALUABLE if tocado is None else (CUMPLE if tocado else PENDIENTE),
            "sin registro de toque" if tocado is None else ("nivel tocado" if tocado else "aun sin tocar"),
            nivel=CRITICAL,
        ),
        _req(
            "sin aceptacion mas alla del nivel",
            NO_EVALUABLE if fuera is None else (NO_CUMPLE if fuera else CUMPLE),
            "sin precio o sin nivel" if fuera is None else (f"precio {price} vs nivel {level}"),
            invalida=True,
            nivel=CRITICAL,
        ),
        _req(
            "reaccion del precio",
            NO_EVALUABLE
            if reaccion is None
            else (CUMPLE if abs(reaccion) > 0 and _sign(reaccion) == signo else PENDIENTE),
            "sin reaccion medida" if reaccion is None else f"{reaccion:+.2f}% desde el toque",
            nivel=CONFIRMATION,
        ),
        # El flujo CONTRARIO al nivel es el que rechaza: en un rechazo bajista de resistencia
        # se espera delta vendedor, o sea del mismo signo que la direccion de la tesis.
        _flow_check("flujo contrario al nivel", ctx.get("fut_delta"), signo, "delta futuros", CONFIRMATION),
    ]
    absorcion = ctx.get("absorption")
    reqs.append(
        _req(
            "absorcion en el nivel",
            NO_EVALUABLE
            if absorcion in (None, "", "No evaluable", "Sin datos")
            else (CUMPLE if "Absorción" in str(absorcion) else NO_CUMPLE),
            str(absorcion or "sin lectura"),
            nivel=SECONDARY,
        )
    )
    dentro = ctx.get("returned_inside")
    reqs.append(
        _req(
            "retorno al rango",
            NO_EVALUABLE if dentro is None else (CUMPLE if dentro else PENDIENTE),
            "sin observacion" if dentro is None else ("volvio al rango" if dentro else "todavia en el borde"),
            nivel=CRITICAL,
        )
    )
    barras = ctx.get("bars_closed_beyond")
    reqs.append(
        _req(
            "sin cierres aceptados fuera",
            NO_EVALUABLE if barras is None else (NO_CUMPLE if barras >= 2 else CUMPLE),
            "sin conteo de cierres" if barras is None else f"{barras} cierres fuera del nivel",
            invalida=True,
            nivel=CRITICAL,
        )
    )
    return reqs


def _eval_reversion(ctx: dict[str, Any], signo: int) -> list[dict[str, Any]]:
    """Reversion. CRITICOS: la tendencia previa CONTRARIA, el evento de estructura y el
    cambio de flujo de futuros. Sin ruptura de estructura esto es un retroceso dentro de la
    tendencia vigente, no un giro. CONFIRMAN spot y el OI; las liquidaciones son contexto."""
    previo = ctx.get("prior_trend")
    contrario = (
        None
        if previo is None or signo == 0
        else ((previo == "bajista" and signo > 0) or (previo == "alcista" and signo < 0))
    )
    evento = ctx.get("structure_event")
    dir_estructura = ctx.get("structure_direction")
    estructura_ok = (
        None
        if evento is None or dir_estructura is None or signo == 0
        else (evento in ("BOS", "CHoCH") and _BIAS_SIGN.get(dir_estructura) == signo)
    )
    reqs = [
        _req(
            "contexto previo contrario",
            NO_EVALUABLE if contrario is None else (CUMPLE if contrario else NO_CUMPLE),
            "sin tendencia previa" if contrario is None else f"tendencia previa {previo}",
            invalida=True,
            nivel=CRITICAL,
        ),
        _req(
            "perdida o recuperacion de estructura",
            NO_EVALUABLE if estructura_ok is None else (CUMPLE if estructura_ok else PENDIENTE),
            "sin evento de estructura"
            if evento is None
            else f"{evento} {dir_estructura or ''}".strip(),
            # Sin ruptura de estructura no hay reversion, solo un retroceso.
            nivel=CRITICAL,
        ),
        _flow_check("cambio de flujo", ctx.get("fut_delta"), signo, "delta futuros", CRITICAL),
        _flow_check("confirmacion spot", ctx.get("spot_delta"), signo, "delta spot", CONFIRMATION),
    ]
    # El OI de una reversion sana muestra posicionamiento NUEVO en el sentido nuevo, no
    # simplemente un signo: eso lo decide `_oi_check` junto con el precio.
    reqs.append(_oi_check("respuesta de futuros (OI)", ctx, signo))
    skew = ctx.get("liq_skew")
    reqs.append(
        _req(
            "liquidaciones del lado contrario",
            NO_EVALUABLE
            if skew is None or signo == 0
            else (CUMPLE if _sign(skew) == signo else NO_CUMPLE),
            "sin liquidaciones medidas" if skew is None else f"skew short-long {skew:+.0f}",
            nivel=SECONDARY,
        )
    )
    return reqs


def _eval_continuacion(ctx: dict[str, Any], signo: int) -> list[dict[str, Any]]:
    """Continuacion. CRITICOS: la tendencia vigente ALINEADA, el retroceso y la defensa del
    nivel. Sin retroceso ni defensa medidos esto no es una continuacion: es una tendencia en
    curso, que no es lo mismo. CONFIRMAN el flujo reanudado y la alineacion multitemporal;
    el VWAP es contexto."""
    previo = ctx.get("prior_trend")
    alineado = (
        None
        if previo is None or signo == 0
        else ((previo == "alcista" and signo > 0) or (previo == "bajista" and signo < 0))
    )
    retroceso = ctx.get("pullback_pct")
    defendido = ctx.get("level_defended")
    vwap = ctx.get("vwap_dist_pct")
    multi = ctx.get("multi_tf_aligned")
    return [
        _req(
            "contexto alineado con la direccion",
            NO_EVALUABLE if alineado is None else (CUMPLE if alineado else NO_CUMPLE),
            "sin tendencia previa" if alineado is None else f"tendencia previa {previo}",
            invalida=True,
            nivel=CRITICAL,
        ),
        _req(
            "retroceso previo",
            NO_EVALUABLE if retroceso is None else (CUMPLE if abs(retroceso) > 0 else PENDIENTE),
            "sin retroceso medido" if retroceso is None else f"{retroceso:+.2f}%",
            nivel=CRITICAL,
        ),
        _req(
            "defensa del nivel",
            NO_EVALUABLE if defendido is None else (CUMPLE if defendido else NO_CUMPLE),
            "sin observacion" if defendido is None else ("nivel defendido" if defendido else "nivel perdido"),
            nivel=CRITICAL,
        ),
        _flow_check("reanudacion del flujo", ctx.get("fut_delta"), signo, "delta futuros", CONFIRMATION),
        _req(
            "VWAP recuperado o defendido",
            NO_EVALUABLE
            if vwap is None or signo == 0
            else (CUMPLE if _sign(vwap) == signo else NO_CUMPLE),
            "sin VWAP" if vwap is None else f"distancia {vwap:+.2f}%",
            nivel=SECONDARY,
        ),
        _req(
            "confirmacion multitemporal",
            NO_EVALUABLE if multi is None else (CUMPLE if multi else PENDIENTE),
            "sin lectura multitemporal" if multi is None else ("capas alineadas" if multi else "capas sin acuerdo"),
            nivel=CONFIRMATION,
        ),
    ]


_BIAS_SIGN = {"alcista": 1, "bajista": -1, "neutral": 0}

SETUP_SPECS: dict[str, dict[str, Any]] = {
    "ruptura": {
        "label": "Ruptura",
        "evaluar": _eval_ruptura,
        # Sin barrera y sin precio no hay ruptura que juzgar: NO EVALUABLE, no PENDIENTE.
        "obligatorios": ("price", "barrier_level"),
        "necesita_direccion": True,
        "tesis": "el precio acepta al otro lado de una barrera relevante",
    },
    "rechazo": {
        "label": "Rechazo",
        "evaluar": _eval_rechazo,
        "obligatorios": ("price", "barrier_level"),
        "necesita_direccion": True,
        "tesis": "el nivel aguanta y el precio vuelve al rango",
    },
    "reversion": {
        "label": "Reversión",
        "evaluar": _eval_reversion,
        "obligatorios": ("prior_trend",),
        "necesita_direccion": True,
        "tesis": "la tendencia previa se rompe y el flujo cambia de lado",
    },
    "continuacion": {
        "label": "Continuación",
        "evaluar": _eval_continuacion,
        "obligatorios": ("prior_trend",),
        "necesita_direccion": True,
        "tesis": "tras un retroceso, la tendencia vigente se reanuda",
    },
}


def _structure_event(horizon: dict[str, Any]) -> tuple[str | None, str | None]:
    """Deriva BOS/CHoCH de los niveles y distancias que `structure_detail` ya publica.

    `distance_to_*_pct` es (close/nivel - 1)*100, asi que su SIGNO dice de que lado cerro el
    precio. No se inventa ningun evento: si no hay estado o no hay distancia, no hay evento.
    """
    estado = horizon.get("state")
    d_bos = horizon.get("distance_to_bos_pct")
    d_inval = horizon.get("distance_to_invalidation_pct")
    if estado == "HH_HL":
        if d_bos is not None and d_bos >= 0:
            return "BOS", "alcista"
        if d_inval is not None and d_inval <= 0:
            return "CHoCH", "bajista"
    elif estado == "LH_LL":
        if d_bos is not None and d_bos <= 0:
            return "BOS", "bajista"
        if d_inval is not None and d_inval >= 0:
            return "CHoCH", "alcista"
    return None, None


# ---------------- observables MEDIDOS sobre velas CERRADAS ----------------
#
# Estos cinco observables estaban fijados a None en `build_setup_context()` (fail-closed
# honesto: sin medida no se inventa). Aqui se miden cuando el llamador aporta un paquete de
# velas YA CERRADAS del timeframe de confirmacion del perfil (`setup_confirmation_bundle()` en
# scalp_logic.py). El helper es PURO: recibe las velas y la estructura, no toca la base.

OBS_MEASURED = "MEASURED"
OBS_PENDING = "PENDING"
OBS_UNAVAILABLE = "UNAVAILABLE"
OBS_PARTIAL = "PARTIAL"
OBS_STALE = "STALE"
OBS_ERROR = "ERROR"
OBS_NO_EVALUABLE = "NO_EVALUABLE"

RETEST_ATR_MULT = 0.5
"""Fraccion de ATR dentro de la cual un regreso al nivel roto cuenta como CONTACTO de retest.

Convencion declarada; se normaliza por ATR (o por anchura de zona / % del precio si no hay
ATR) para no usar una tolerancia monetaria fija universal, como pide la especificacion.
"""

LEVEL_TOL_ATR_MULT = 0.5
"""Fraccion de ATR de tolerancia para decir que un pullback TOCA un nivel estructural."""

FALLBACK_TOL_PCT = 0.15
"""Tolerancia de respaldo (% del precio) cuando no hay ATR ni anchura de zona utilizables."""


def _obs(
    value: Any,
    status: str,
    *,
    source: str | None = None,
    timeframe: str | None = None,
    as_of: str | None = None,
    sample_count: int | None = None,
    coverage: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Un observable medido, con su procedencia. `value` es lo que consume `evaluate_setup`."""
    out = {
        "value": value,
        "status": status,
        "source": source,
        "timeframe": timeframe,
        "as_of": as_of,
        "sample_count": sample_count,
        "coverage": coverage,
    }
    out.update(extra)
    return out


def _breakout_frontier(setup: str, signo: int, zone: dict[str, Any]) -> tuple[float | None, int]:
    """Frontera de ACEPTACION y su signo, NUNCA el centro de la zona (spec 1.1).

    Ruptura larga -> `resistance.high`; ruptura corta -> `support.low`. En un rechazo la
    aceptacion RELEVANTE (la que lo invalida) es al otro lado del nivel apoyado: rechazo largo
    sobre soporte se rompe cerrando por DEBAJO de `support.low`.
    """
    low, high = zone.get("low"), zone.get("high")
    if setup == "ruptura":
        if signo > 0:
            return high, 1
        if signo < 0:
            return low, -1
    elif setup == "rechazo":
        if signo > 0:
            return low, -1
        if signo < 0:
            return high, 1
    return None, 0


def _tolerance(
    atr: float | None, zone: dict[str, Any] | None, ref_price: float | None, atr_mult: float
) -> tuple[float | None, str | None]:
    """Tolerancia normalizada: ATR primero; si no, media anchura de zona; si no, % del precio."""
    if atr is not None and atr > 0:
        return atr * atr_mult, "atr"
    if zone:
        low, high = zone.get("low"), zone.get("high")
        if low is not None and high is not None and high > low:
            return (high - low) * 0.5, "anchura_zona"
    if ref_price:
        return abs(ref_price) * FALLBACK_TOL_PCT / 100.0, "pct_precio"
    return None, None


def _norm_bars(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Velas CERRADAS ascendentes con ts en segundos epoch. La vela abierta ya se excluyo."""
    bars: list[dict[str, Any]] = []
    for raw in bundle.get("bars") or []:
        ts = raw.get("ts")
        close = raw.get("close")
        if ts is None or close is None:
            continue
        bars.append(
            {
                "ts": int(ts),
                "open": raw.get("open"),
                "high": raw.get("high") if raw.get("high") is not None else close,
                "low": raw.get("low") if raw.get("low") is not None else close,
                "close": close,
            }
        )
    bars.sort(key=lambda b: b["ts"])
    return bars


def _gap_in(bars: list[dict[str, Any]], bar_seconds: int | None) -> bool:
    """¿Falta alguna vela en la secuencia? (separacion distinta al paso del timeframe)."""
    if not bar_seconds or len(bars) < 2:
        return False
    return any(bars[i]["ts"] - bars[i - 1]["ts"] != bar_seconds for i in range(1, len(bars)))


def _bars_closed_beyond(
    bars: list[dict[str, Any]], boundary: float | None, bsign: int,
    *, bar_seconds: int | None, tf: str | None, source: str | None, as_of: str | None,
) -> dict[str, Any]:
    """Cuenta la RACHA final de velas cerradas al otro lado de la frontera. No mira mechas."""
    if boundary is None or bsign == 0:
        return _obs(None, OBS_UNAVAILABLE, timeframe=tf, source=source, as_of=as_of,
                    coverage="sin frontera de aceptacion medida")
    if not bars:
        return _obs(None, OBS_UNAVAILABLE, timeframe=tf, source=source, as_of=as_of,
                    sample_count=0, coverage="sin velas cerradas")
    beyond = [(b["close"] - boundary) * bsign > 0 for b in bars]
    # Racha de cierres fuera contando desde la vela cerrada MAS reciente hacia atras.
    run = 0
    for flag in reversed(beyond):
        if flag:
            run += 1
        else:
            break
    idx_beyond = [i for i, f in enumerate(beyond) if f]
    first_i = idx_beyond[0] if idx_beyond else None
    last_i = idx_beyond[-1] if idx_beyond else None
    # Un hueco DENTRO de la racha necesaria rompe la evidencia de aceptacion continua.
    ventana = bars[len(bars) - max(run, 1):]
    if run and _gap_in(ventana, bar_seconds):
        return _obs(None, OBS_NO_EVALUABLE, timeframe=tf, source=source, as_of=as_of,
                    sample_count=len(bars), coverage="hueco en la secuencia de aceptacion",
                    bars_examined=len(bars))
    return _obs(
        run, OBS_MEASURED, timeframe=tf, source=source, as_of=as_of,
        sample_count=len(bars),
        coverage="completa" if not _gap_in(bars, bar_seconds) else "con_huecos_previos",
        bars_examined=len(bars),
        first_close_beyond=bars[first_i]["ts"] if first_i is not None else None,
        last_close_beyond=bars[last_i]["ts"] if last_i is not None else None,
        boundary=boundary,
    )


def _returned_inside(
    bars: list[dict[str, Any]], setup: str, signo: int, boundary: float | None, bsign: int,
    zone: dict[str, Any], *, tf: str | None, source: str | None, as_of: str | None,
) -> dict[str, Any]:
    """¿Volvio el precio al rango tras salir/tocar? None mientras no pueda evaluarse (spec 1.3).

    Nunca se convierte None en False: False solo si SE observo el periodo posterior y NO regreso.
    """
    if boundary is None or bsign == 0 or not bars:
        return _obs(None, OBS_PENDING, timeframe=tf, source=source, as_of=as_of,
                    coverage="sin frontera o sin velas")
    low, high = zone.get("low"), zone.get("high")
    if setup == "ruptura":
        # Solo evaluable tras al menos un cierre fuera de la zona.
        idx = next((i for i, b in enumerate(bars) if (b["close"] - boundary) * bsign > 0), None)
        if idx is None:
            return _obs(None, OBS_PENDING, timeframe=tf, source=source, as_of=as_of,
                        coverage="aun no hay cierre fuera")
        posteriores = bars[idx + 1:]
        if not posteriores:
            return _obs(None, OBS_PENDING, timeframe=tf, source=source, as_of=as_of,
                        coverage="sin periodo posterior al cierre fuera")
        volvio = any((b["close"] - boundary) * bsign <= 0 for b in posteriores)
        return _obs(volvio, OBS_MEASURED, timeframe=tf, source=source, as_of=as_of,
                    sample_count=len(posteriores),
                    coverage="regreso observado" if volvio else "no regreso en el periodo")
    if setup == "rechazo":
        if low is None or high is None:
            return _obs(None, OBS_PENDING, timeframe=tf, source=source, as_of=as_of,
                        coverage="sin bordes de zona para medir el retorno")
        idx = next((i for i, b in enumerate(bars) if low <= b["close"] <= high), None)
        if idx is None:
            return _obs(None, OBS_PENDING, timeframe=tf, source=source, as_of=as_of,
                        coverage="el precio aun no entro en la zona")
        posteriores = bars[idx + 1:]
        if not posteriores:
            return _obs(None, OBS_PENDING, timeframe=tf, source=source, as_of=as_of,
                        coverage="sin periodo posterior al toque")
        # Rechazo largo (soporte): retorno = cerrar de vuelta por encima del borde superior.
        volvio = any(b["close"] > high for b in posteriores) if signo > 0 else any(
            b["close"] < low for b in posteriores)
        return _obs(volvio, OBS_MEASURED, timeframe=tf, source=source, as_of=as_of,
                    sample_count=len(posteriores),
                    coverage="retorno al rango observado" if volvio else "sin retorno todavia")
    return _obs(None, OBS_UNAVAILABLE, timeframe=tf, source=source, as_of=as_of)


def _retest_done(
    bars: list[dict[str, Any]], signo: int, boundary: float | None, bsign: int, atr: float | None,
    zone: dict[str, Any], *, tf: str | None, source: str | None, as_of: str | None,
) -> dict[str, Any]:
    """Retest (SECONDARY): ruptura previa -> vuelta al nivel dentro de tolerancia -> reaccion."""
    if boundary is None or bsign == 0 or not bars:
        return _obs(None, OBS_PENDING, timeframe=tf, source=source, as_of=as_of,
                    retest_status="pending", coverage="sin frontera o sin velas")
    idx = next((i for i, b in enumerate(bars) if (b["close"] - boundary) * bsign > 0), None)
    if idx is None:
        return _obs(None, OBS_PENDING, timeframe=tf, source=source, as_of=as_of,
                    retest_status="none", coverage="sin ruptura previa")
    tol, tol_src = _tolerance(atr, zone, boundary, RETEST_ATR_MULT)
    if tol is None:
        return _obs(None, OBS_UNAVAILABLE, timeframe=tf, source=source, as_of=as_of,
                    retest_status="pending", coverage="sin tolerancia normalizable")
    # Contacto: una vela posterior cuyo extremo del lado del nivel se acerca a la frontera.
    for j in range(idx + 1, len(bars)):
        b = bars[j]
        edge = b["low"] if bsign > 0 else b["high"]
        dist = abs(edge - boundary)
        if dist <= tol:
            reaccion = any((k["close"] - boundary) * bsign > 0 for k in bars[j + 1:])
            if reaccion:
                return _obs(True, OBS_MEASURED, timeframe=tf, source=source, as_of=as_of,
                            retest_status="done", retest_time=b["ts"],
                            retest_distance_atr=(dist / atr) if atr else None,
                            coverage=f"contacto a {dist:.6g} ({tol_src})")
    # Hubo ruptura y velas posteriores, pero ningun contacto+reaccion: aun sin retest.
    if len(bars) - 1 > idx:
        return _obs(False, OBS_MEASURED, timeframe=tf, source=source, as_of=as_of,
                    retest_status="not_yet", coverage="ruptura sin retest observado")
    return _obs(None, OBS_PENDING, timeframe=tf, source=source, as_of=as_of,
                retest_status="pending", coverage="sin periodo posterior")


def _last_pivots(pivots: dict[str, Any] | None) -> tuple[list, list]:
    piv = pivots or {}
    highs = [tuple(p) for p in (piv.get("highs") or []) if p and len(p) >= 2]
    lows = [tuple(p) for p in (piv.get("lows") or []) if p and len(p) >= 2]
    return highs, lows


def _pullback(
    bars: list[dict[str, Any]], signo: int, pivots: dict[str, Any] | None, atr: float | None,
    *, tf: str | None, source: str | None, as_of: str | None,
) -> dict[str, Any]:
    """Retroceso del ULTIMO impulso estructural en el sentido de la tendencia (spec 1.5).

    No es `ultimo - anterior`: identifica impulso (pivote a pivote) y mide el retroceso desde
    su extremo. Sin impulso completo -> None.
    """
    if signo == 0 or not bars:
        return _obs(None, OBS_UNAVAILABLE, timeframe=tf, source=source, as_of=as_of,
                    coverage="sin direccion o sin velas")
    highs, lows = _last_pivots(pivots)
    if signo > 0:
        if not highs or not lows:
            return _obs(None, OBS_UNAVAILABLE, timeframe=tf, source=source, as_of=as_of,
                        coverage="faltan pivotes para un impulso alcista")
        impulse_end = highs[-1]
        starts = [lo for lo in lows if lo[0] < impulse_end[0]]
        if not starts:
            return _obs(None, OBS_UNAVAILABLE, timeframe=tf, source=source, as_of=as_of,
                        coverage="sin pivote de inicio antes del maximo")
        impulse_start = starts[-1]
        if impulse_end[1] <= impulse_start[1]:
            return _obs(None, OBS_UNAVAILABLE, timeframe=tf, source=source, as_of=as_of,
                        coverage="el ultimo tramo no es un impulso alcista")
        posteriores = [b for b in bars if b["ts"] > impulse_end[0]]
        if not posteriores:
            return _obs(None, OBS_PENDING, timeframe=tf, source=source, as_of=as_of,
                        coverage="sin velas posteriores al maximo")
        pb_extreme = min(b["low"] for b in posteriores)
        pb_extreme_bar = min(posteriores, key=lambda b: b["low"])
        rango = impulse_end[1] - impulse_start[1]
    else:
        if not highs or not lows:
            return _obs(None, OBS_UNAVAILABLE, timeframe=tf, source=source, as_of=as_of,
                        coverage="faltan pivotes para un impulso bajista")
        impulse_end = lows[-1]
        starts = [hi for hi in highs if hi[0] < impulse_end[0]]
        if not starts:
            return _obs(None, OBS_UNAVAILABLE, timeframe=tf, source=source, as_of=as_of,
                        coverage="sin pivote de inicio antes del minimo")
        impulse_start = starts[-1]
        if impulse_end[1] >= impulse_start[1]:
            return _obs(None, OBS_UNAVAILABLE, timeframe=tf, source=source, as_of=as_of,
                        coverage="el ultimo tramo no es un impulso bajista")
        posteriores = [b for b in bars if b["ts"] > impulse_end[0]]
        if not posteriores:
            return _obs(None, OBS_PENDING, timeframe=tf, source=source, as_of=as_of,
                        coverage="sin velas posteriores al minimo")
        pb_extreme = max(b["high"] for b in posteriores)
        pb_extreme_bar = max(posteriores, key=lambda b: b["high"])
        rango = impulse_start[1] - impulse_end[1]
    if rango <= 0:
        return _obs(None, OBS_UNAVAILABLE, timeframe=tf, source=source, as_of=as_of,
                    coverage="impulso de rango nulo")
    pullback_pct = (pb_extreme - impulse_end[1]) / impulse_end[1] * 100
    pullback_atr = abs(impulse_end[1] - pb_extreme) / atr if atr else None
    return _obs(
        round(pullback_pct, 4), OBS_MEASURED, timeframe=tf, source=source, as_of=as_of,
        sample_count=len(posteriores), coverage="impulso y retroceso medidos",
        pullback_atr=round(pullback_atr, 4) if pullback_atr is not None else None,
        impulse_start=impulse_start[0], impulse_end=impulse_end[0],
        pullback_start=impulse_end[0], pullback_low=pb_extreme if signo > 0 else None,
        pullback_high=pb_extreme if signo < 0 else None,
        pullback_extreme_ts=pb_extreme_bar["ts"],
    )


def _level_defended(
    bars: list[dict[str, Any]], signo: int, pivots: dict[str, Any] | None, atr: float | None,
    zone: dict[str, Any], *, tf: str | None, source: str | None, as_of: str | None,
) -> dict[str, Any]:
    """Nivel estructural defendido: pullback lo toca, no hay aceptacion al otro lado, reacciona.

    Usa UN nivel explicito (el ultimo swing en el sentido de la tendencia) y lo declara; no
    mezcla soporte/VWAP/POC en silencio (spec 1.6).
    """
    if signo == 0 or not bars:
        return _obs(None, OBS_UNAVAILABLE, timeframe=tf, source=source, as_of=as_of,
                    coverage="sin direccion o sin velas")
    highs, lows = _last_pivots(pivots)
    piv = lows if signo > 0 else highs
    if not piv:
        return _obs(None, OBS_UNAVAILABLE, timeframe=tf, source=source, as_of=as_of,
                    defended_level_type=None, defended_level_price=None,
                    coverage="sin nivel estructural identificable")
    level_ts, level = piv[-1]
    tol, tol_src = _tolerance(atr, zone, level, LEVEL_TOL_ATR_MULT)
    if tol is None:
        return _obs(None, OBS_UNAVAILABLE, timeframe=tf, source=source, as_of=as_of,
                    defended_level_type="swing_low" if signo > 0 else "swing_high",
                    defended_level_price=level, coverage="sin tolerancia normalizable")
    posteriores = [b for b in bars if b["ts"] >= level_ts]
    if len(posteriores) < 2:
        return _obs(None, OBS_PENDING, timeframe=tf, source=source, as_of=as_of,
                    defended_level_type="swing_low" if signo > 0 else "swing_high",
                    defended_level_price=level, coverage="sin velas posteriores suficientes")
    # Aceptacion INVALIDANTE al otro lado: dos cierres claramente pasados el nivel.
    if signo > 0:
        aceptados = sum(1 for b in posteriores if b["close"] < level - tol)
        extremo = min(b["low"] for b in posteriores)
        toco = extremo <= level + tol
        reacciono = posteriores[-1]["close"] > extremo
    else:
        aceptados = sum(1 for b in posteriores if b["close"] > level + tol)
        extremo = max(b["high"] for b in posteriores)
        toco = extremo >= level - tol
        reacciono = posteriores[-1]["close"] < extremo
    tipo = "swing_low" if signo > 0 else "swing_high"
    if aceptados >= 2:
        return _obs(False, OBS_MEASURED, timeframe=tf, source=source, as_of=as_of,
                    defended_level_type=tipo, defended_level_price=level,
                    coverage=f"nivel perdido: {aceptados} cierres aceptados al otro lado")
    if toco and reacciono:
        return _obs(True, OBS_MEASURED, timeframe=tf, source=source, as_of=as_of,
                    defended_level_type=tipo, defended_level_price=level,
                    coverage=f"nivel tocado ({tol_src}) y con reaccion a favor")
    return _obs(None, OBS_PENDING, timeframe=tf, source=source, as_of=as_of,
                defended_level_type=tipo, defended_level_price=level,
                coverage="nivel aun sin probar o sin reaccion")


def setup_observables(
    *,
    direction: str,
    setup: str,
    zone: dict[str, Any] | None,
    bundle: dict[str, Any] | None,
) -> dict[str, Any]:
    """Mide los cinco observables reales desde velas CERRADAS y estructura.

    Devuelve, por observable, `{value, status, source, timeframe, sample_count, as_of,
    coverage, ...}`. `value` es lo que consume `evaluate_setup`; el resto explica la medida.
    Nunca infiere False por ausencia: usa None / NO_EVALUABLE / PENDING segun corresponda.
    """
    zone = zone or {}
    bundle = bundle or {}
    signo = DIRECTIONS.get(direction, {}).get("sign", 0)
    tf = bundle.get("timeframe")
    source = bundle.get("source")
    as_of = bundle.get("as_of")
    bar_seconds = bundle.get("bar_seconds")
    atr = bundle.get("atr")
    pivots = bundle.get("pivots")
    bars = _norm_bars(bundle)

    boundary, bsign = _breakout_frontier(setup, signo, zone)
    return {
        "zone_low": zone.get("low"),
        "zone_high": zone.get("high"),
        "zone_center": zone.get("center"),
        "breakout_boundary": boundary,
        "bars_closed_beyond": _bars_closed_beyond(
            bars, boundary, bsign, bar_seconds=bar_seconds, tf=tf, source=source, as_of=as_of),
        "returned_inside": _returned_inside(
            bars, setup, signo, boundary, bsign, zone, tf=tf, source=source, as_of=as_of),
        "retest_done": _retest_done(
            bars, signo, boundary, bsign, atr, zone, tf=tf, source=source, as_of=as_of),
        "pullback_pct": _pullback(
            bars, signo, pivots, atr, tf=tf, source=source, as_of=as_of),
        "level_defended": _level_defended(
            bars, signo, pivots, atr, zone, tf=tf, source=source, as_of=as_of),
    }


def build_setup_context(
    scalp: dict[str, Any],
    profile: dict[str, Any],
    trend: dict[str, Any] | None = None,
    barriers: dict[str, Any] | None = None,
    structure: dict[str, Any] | None = None,
    *,
    direction: str = "neutral",
    setup: str = "ninguno",
    observ_bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Traduce los bloques ya publicados a los observables que pide cada setup.

    Solo mapea; no calcula nada nuevo. Un observable que el sistema no mide (retest, cierres
    aceptados fuera del nivel, retroceso) se deja en None a proposito: el requisito
    correspondiente quedara `no_evaluable` y se dira, en vez de darse por bueno.
    """
    barriers = barriers or {}
    structure = structure or {}
    layers = profile.get("layers") or {}
    orden = list(layers)

    def bias_de(indice: int) -> str | None:
        if indice >= len(orden):
            return None
        bias = layers[orden[indice]].get("bias")
        return bias if bias in ("alcista", "bajista") else None

    contexto_bias = bias_de(0)
    confirm_bias = bias_de(1)

    resistencia = barriers.get("nearest_resistance") or {}
    soporte = barriers.get("nearest_support") or {}
    activa = barriers.get("active_zone")
    # La barrera relevante depende de hacia donde mira la tesis y de que se espera de ella:
    # una ruptura larga ataca la resistencia; un rechazo largo se apoya en el soporte.
    if setup == "rechazo":
        zona = soporte if direction == "long" else (resistencia if direction == "short" else {})
    else:
        zona = resistencia if direction == "long" else (soporte if direction == "short" else {})
    nivel = zona.get("center")

    # Observables MEDIDOS sobre velas cerradas cuando el llamador aporta el paquete de
    # confirmacion; si no, los cinco siguen en None (fail-closed, no se inventan). El
    # `barrier_level` de arriba sigue siendo el CENTRO para el chequeo blando de "cierre mas
    # alla"; la frontera de ruptura real es `breakout_boundary`, publicada aparte (spec 1.1).
    signo = DIRECTIONS.get(direction, {}).get("sign", 0)
    boundary, _ = _breakout_frontier(setup, signo, zona) if zona else (None, 0)
    medidos: dict[str, Any] = {
        "bars_closed_beyond": None,
        "returned_inside": None,
        "retest_done": None,
        "pullback_pct": None,
        "level_defended": None,
    }
    observables: dict[str, Any] | None = None
    if observ_bundle is not None:
        observables = setup_observables(
            direction=direction, setup=setup, zone=zona, bundle=observ_bundle
        )
        boundary = observables.get("breakout_boundary", boundary)
        for clave in medidos:
            medidos[clave] = observables[clave]["value"]

    horizontes = structure.get("horizons") or {}
    horizonte = horizontes.get("4h") or horizontes.get("1h") or {}
    evento, dir_evento = _structure_event(horizonte)
    estado_estructura = horizonte.get("state")
    tendencia_previa = (
        "alcista" if estado_estructura == "HH_HL"
        else "bajista" if estado_estructura == "LH_LL"
        else contexto_bias
    )

    liq_medida = scalp.get("liquidations_measured") is True
    long_liq, short_liq = scalp.get("long_liq_5m"), scalp.get("short_liq_5m")
    presion = barriers.get("live_pressure") or {}

    return {
        "price": barriers.get("current_price"),
        "barrier_level": nivel,
        "barrier_side": "resistencia" if zona is resistencia else ("soporte" if zona is soporte else None),
        # Tocar el nivel = el precio esta DENTRO de una zona de barreras. Es lo unico que el
        # sistema mide hoy sobre el contacto; el conteo de toques por episodio no llega aqui.
        "touched_level": (activa is not None) if barriers.get("available") else None,
        "volume_multiple": presion.get("volume_multiple_15m"),
        "spot_delta": scalp.get("spot_delta_3m"),
        "fut_delta": scalp.get("fut_delta_3m"),
        "oi_chg_pct": scalp.get("oi_chg_15m_pct"),
        "book_bid_share": scalp.get("imbalance_l5"),
        "absorption": scalp.get("absorption"),
        "reaction_pct": scalp.get("price_move_3m_pct"),
        "vwap_dist_pct": scalp.get("vwap_dist_pct"),
        "prior_trend": tendencia_previa,
        "structure_event": evento,
        "structure_direction": dir_evento,
        "liq_skew": (short_liq - long_liq) if liq_medida and None not in (short_liq, long_liq) else None,
        "multi_tf_aligned": (
            (contexto_bias == confirm_bias)
            if contexto_bias is not None and confirm_bias is not None
            else None
        ),
        # Fronteras de la zona: el centro NO es la frontera de ruptura (spec 1.1).
        "zone_low": zona.get("low"),
        "zone_high": zona.get("high"),
        "zone_center": zona.get("center"),
        "breakout_boundary": boundary,
        # Medidos desde velas cerradas si hay paquete; si no, None (fail-closed, no False).
        "bars_closed_beyond": medidos["bars_closed_beyond"],
        "retest_done": medidos["retest_done"],
        "returned_inside": medidos["returned_inside"],
        "pullback_pct": medidos["pullback_pct"],
        "level_defended": medidos["level_defended"],
        # Procedencia completa de cada observable (value/status/source/timeframe/as_of/...).
        "observables": observables,
    }


def evaluate_setup(
    setup: str, direction: str, ctx: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Evalua UN setup contra los observables disponibles. Pura y fail-closed."""
    ctx = ctx or {}
    if setup == "ninguno":
        return {
            "setup": "ninguno",
            "label": SETUP_LABELS["ninguno"],
            "direction": direction,
            "state": "NO EVALUABLE",
            "requisitos": [],
            "pendientes": [],
            "invalidaciones": [],
            "no_evaluables": [],
            "cumplidos": [],
            "faltantes": [],
            "requisitos_totales": 0,
            "requisitos_evaluables": 0,
            "coverage_pct": 0.0,
            "critical_total": 0,
            "critical_evaluable": 0,
            "critical_met": 0,
            "confirmation_total": 0,
            "confirmation_evaluable": 0,
            "confirmation_met": 0,
            "missing_critical": [],
            "missing_confirmation": [],
            "note": "Sin setup seleccionado no hay nada que confirmar ni invalidar.",
        }
    if setup not in SETUP_SPECS:
        raise ValueError(f"setup desconocido: {setup}")
    if direction not in DIRECTIONS:
        raise ValueError(f"direccion desconocida: {direction}")

    spec = SETUP_SPECS[setup]
    signo = DIRECTIONS[direction]["sign"]
    faltantes = [k for k in spec["obligatorios"] if ctx.get(k) is None]
    if spec["necesita_direccion"] and signo == 0:
        faltantes = [*faltantes, "direccion"]

    requisitos = spec["evaluar"](ctx, signo)
    pendientes = [r["requisito"] for r in requisitos if r["estado"] == PENDIENTE]
    invalidaciones = [
        f"{r['requisito']}: {r['detalle']}"
        for r in requisitos
        if r["invalida"] and r["estado"] == NO_CUMPLE
    ]
    no_evaluables = [r["requisito"] for r in requisitos if r["estado"] == NO_EVALUABLE]
    cumplidos = [r["requisito"] for r in requisitos if r["estado"] == CUMPLE]
    evaluables = [r for r in requisitos if r["estado"] != NO_EVALUABLE]

    criticos = [r for r in requisitos if r["nivel"] == CRITICAL]
    confirmaciones = [r for r in requisitos if r["nivel"] == CONFIRMATION]
    missing_critical = [r["requisito"] for r in criticos if r["estado"] == NO_EVALUABLE]
    missing_confirmation = [
        r["requisito"] for r in confirmaciones if r["estado"] == NO_EVALUABLE
    ]
    criticos_cumplidos = [r for r in criticos if r["estado"] == CUMPLE]
    criticos_pendientes = [r for r in criticos if r["estado"] in (PENDIENTE, NO_CUMPLE)]
    confirmaciones_cumplidas = [r for r in confirmaciones if r["estado"] == CUMPLE]
    coverage_pct = round(len(evaluables) / len(requisitos) * 100, 1) if requisitos else 0.0
    # Si el setup tiene menos requisitos de confirmacion que el minimo, se exigen todos.
    minimo_confirmaciones = min(MIN_CONFIRMATIONS, len(confirmaciones))

    # CONFIRMADO exige, en este orden: nada roto, TODOS los criticos evaluados y cumplidos,
    # el minimo de confirmaciones y cobertura suficiente. Antes bastaba con que hubiera algun
    # requisito cumplido y ninguno pendiente, asi que un setup con la mitad de los criticos
    # en NO EVALUABLE se publicaba como CONFIRMADO.
    if faltantes or not evaluables:
        state = "NO EVALUABLE"
    elif invalidaciones:
        state = "FALLIDO"
    elif missing_critical:
        # Falta informacion CRITICA: no se puede confirmar nada. Si ya hay evidencia a favor
        # es un candidato; si no hay nada medido, ni eso.
        state = "CANDIDATO" if cumplidos else "NO EVALUABLE"
    elif criticos_pendientes:
        state = "CANDIDATO" if cumplidos else "PENDIENTE"
    elif (
        len(confirmaciones_cumplidas) >= minimo_confirmaciones
        and coverage_pct >= MIN_COVERAGE_PCT
    ):
        state = "CONFIRMADO"
    elif cumplidos:
        state = "CANDIDATO"
    else:
        state = "PENDIENTE"

    return {
        "setup": setup,
        "label": spec["label"],
        "direction": direction,
        "direction_label": DIRECTIONS[direction]["label"],
        "thesis": spec["tesis"],
        "state": state,
        "requisitos": requisitos,
        "pendientes": pendientes,
        "invalidaciones": invalidaciones,
        "no_evaluables": no_evaluables,
        "cumplidos": cumplidos,
        "faltantes": faltantes,
        "requisitos_totales": len(requisitos),
        "requisitos_evaluables": len(evaluables),
        # Por que se puede o no confirmar, con los numeros a la vista.
        "coverage_pct": coverage_pct,
        "critical_total": len(criticos),
        "critical_evaluable": len(criticos) - len(missing_critical),
        "critical_met": len(criticos_cumplidos),
        "confirmation_total": len(confirmaciones),
        "confirmation_evaluable": len(confirmaciones) - len(missing_confirmation),
        "confirmation_met": len(confirmaciones_cumplidas),
        "missing_critical": missing_critical,
        "missing_confirmation": missing_confirmation,
        "min_confirmations": minimo_confirmaciones,
        "min_coverage_pct": MIN_COVERAGE_PCT,
        "note": (
            "Cada setup declara sus propios requisitos e invalidaciones, y cada requisito su "
            "nivel (CRITICAL/CONFIRMATION/SECONDARY). Un requisito sin observable queda "
            "no_evaluable; si es CRITICO, el setup NO puede llegar a CONFIRMADO."
        ),
    }
