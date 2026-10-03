"""LA FOTO BASTA (C3): que trae cada fila del registro y que no puede traer (campana 135, E1).

validar_fila() lo juzga leyendo SOLO la fila y su foto, con las horas de la PROPIA foto. La usan
el resolutor de juguete de los tests y K105 (por eso es biblioteca estandar y no toca la base).

Lo que exige a todo DISPARADO y a toda SOMBRA: zona con su origen y la hora de su ultima vela;
entrada (tipo y regla), stop, objetivos, invalidacion con nivel y reloj, caducidad; flujos spot y
futuros con su hueco y los bordes de su ventana; ATR; libro de Bybit; mids de Binance y de Bybit;
funding; coste por pata con su venue; los dos cocientes; R bruto y neto; el equilibrio p*; el
vector de filtros; y las huellas (familia, comun, calendario, lectura, papel y codigo). Una SOMBRA
puede traer un hueco solo si su foto dice POR QUE falta (A86); un DISPARADO, ninguno.

Lo que no puede traer nadie: un insumo con hora posterior a su registro; una entrada a mercado con
precio fijado o anclada en el cierre de la vela que dispara; un DISPARADO por encima del tope de
retraso o sin la pata spot completa a favor (MC12).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

ESQUEMA_FOTO = "entradas.foto.v1"
FILTROS = (
    "objetivo",
    "coste_objetivo",
    "coste_riesgo",
    "r_neto_t1",
    "volumen",
    "spot_vela",
    "spot_hora",
    "calendario",
)
ESTADOS_FILTRO = ("cumple", "falla", "no_evaluable")
REGLA_ENTRADA_MERCADO = "apertura_siguiente_minuto_tras_registro"
HUELLAS = ("familia", "comun", "calendario", "lectura", "papel", "codigo")


def _instante(valor: Any) -> datetime | None:
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.astimezone(UTC)
    texto = str(valor).replace("Z", "+00:00")
    try:
        momento = datetime.fromisoformat(texto)
    except ValueError:
        return None
    return momento if momento.tzinfo else momento.replace(tzinfo=UTC)


def huella_texto(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def horas_de_insumos(foto: dict[str, Any]) -> list[tuple[str, str]]:
    """(que, hora) de cada insumo que la foto declara: lo que K105 d compara con el registro."""
    horas: list[tuple[str, str | None]] = [("corte_zonas", foto.get("corte_zonas"))]
    ultima = foto.get("ultima_vela_zonas") or {}
    for fuente, datos in ultima.items():
        horas.append((f"ultima_vela_zonas.{fuente}.cierre", (datos or {}).get("cierre")))
    for i, vela in enumerate((foto.get("episodio") or {}).get("velas") or []):
        horas.append((f"episodio.velas[{i}].fin", (vela or {}).get("fin")))
    for pata, tramos in (foto.get("flujos") or {}).items():
        for nombre, tramo in (tramos or {}).items():
            horas.append((f"flujos.{pata}.{nombre}.hasta", (tramo or {}).get("hasta")))
            horas.append((f"flujos.{pata}.{nombre}.ultimo_minuto", (tramo or {}).get("ultimo_minuto")))
    if foto.get("libro_bybit"):
        horas.append(("libro_bybit.ts", foto["libro_bybit"].get("ts")))
    for venue, mid in ((foto.get("mids") or {}).items()):
        if isinstance(mid, dict):
            horas.append((f"mids.{venue}.ts", mid.get("ts")))
    for venue, dato in ((foto.get("funding") or {}).items()):
        if isinstance(dato, dict):
            horas.append((f"funding.{venue}.ts", dato.get("ts")))
    return [(que, hora) for que, hora in horas if hora is not None]


def _hay(valor: Any) -> bool:
    return valor is not None and valor != [] and valor != {}


def validar_fila(fila: dict[str, Any]) -> list[str]:
    """Errores de una fila del registro contra C3/C5 c y d. Lista vacia = la fila cumple."""
    estado = fila.get("estado")
    foto = fila.get("foto")
    if isinstance(foto, str):
        texto = foto
        foto = json.loads(foto)
        if fila.get("huella_foto") and huella_texto(texto) != fila["huella_foto"]:
            return ["huella_foto no es el sha256 del texto de la foto"]
    if not isinstance(foto, dict):
        return ["sin foto"]
    errores: list[str] = []
    if foto.get("esquema") != ESQUEMA_FOTO:
        errores.append(f"esquema de foto {foto.get('esquema')!r} distinto de {ESQUEMA_FOTO}")
    zona = foto.get("zona") or {}
    if not (_hay(zona.get("low")) and _hay(zona.get("high"))):
        errores.append("sin zona congelada")
    if not foto.get("zonas_origen") or not foto.get("ultima_vela_zonas"):
        errores.append("zona sin su origen o sin la hora de su ultima vela")
    registrada = _instante(fila.get("registered_at"))
    if registrada is not None:
        for que, hora in horas_de_insumos(foto):
            momento = _instante(hora)
            if momento is None:
                errores.append(f"{que}: hora ilegible {hora!r}")
            elif momento > registrada:
                errores.append(f"{que} = {hora} es POSTERIOR al registro ({fila.get('registered_at')})")
    if estado not in ("DISPARADO", "SOMBRA"):
        return errores

    plan = foto.get("plan") or {}
    decision = foto.get("decision") or {}
    ausencias = decision.get("ausencias") or {}
    filtros = foto.get("filtros") or {}
    disparado = estado == "DISPARADO"

    entrada = plan.get("entrada") or {}
    if entrada.get("tipo") not in ("mercado", "limite"):
        errores.append("entrada sin tipo")
    if entrada.get("tipo") == "mercado":
        if entrada.get("precio") is not None:
            errores.append("entrada a mercado con precio fijado: la fija la E3 con la apertura del "
                           "minuto siguiente al registro, nunca el cierre de la vela que dispara")
        if entrada.get("regla_codigo") != REGLA_ENTRADA_MERCADO:
            errores.append(f"entrada a mercado con regla {entrada.get('regla_codigo')!r}: tiene que "
                           f"ser {REGLA_ENTRADA_MERCADO}")
    referencia = entrada.get("referencia") or {}
    velas = (foto.get("episodio") or {}).get("velas") or []
    if referencia.get("fuente") and "cierre" in str(referencia.get("fuente")).lower():
        errores.append("la referencia del plan sale del cierre de una vela")
    if velas and referencia.get("ts") == velas[-1].get("fin") and referencia.get("precio") == velas[-1].get("close"):
        errores.append("la referencia del plan es el cierre de la vela que dispara")

    def exige(nombre: str, valor: Any, ausencia: str | None = None) -> None:
        if _hay(valor):
            return
        if disparado:
            errores.append(f"DISPARADO sin {nombre}")
        elif not (ausencia and ausencia in ausencias) and not _sombra_sin(nombre, foto):
            errores.append(f"SOMBRA sin {nombre} y sin el motivo de su ausencia")

    exige("stop", (plan.get("stop") or {}).get("precio"))
    exige("objetivos", plan.get("objetivos"), "objetivos")
    inval = plan.get("invalidacion") or {}
    if not (_hay(inval.get("nivel")) and _hay(inval.get("reloj")) and _hay(inval.get("hasta"))):
        errores.append("invalidacion sin nivel, reloj u hora")
    if not _hay((plan.get("caducidad") or {}).get("caduca_en")):
        errores.append("sin caducidad")
    flujos = foto.get("flujos") or {}
    for pata in ("spot", "futuros"):
        for tramo in ("vela", "ultima_hora"):
            datos = (flujos.get(pata) or {}).get(tramo)
            completo = isinstance(datos, dict) and all(
                k in datos for k in ("desde", "hasta", "minutos", "esperados", "completo")
            )
            excusado = not disparado and isinstance(datos, dict) and bool(datos.get("motivo"))
            if not completo and not excusado:
                errores.append(f"flujo {pata}.{tramo} sin su estado de hueco y los bordes de su ventana")
    atr = foto.get("atr") or {}
    if not (_hay(atr.get("diario")) and _hay(atr.get("perfil"))):
        errores.append("sin ATR")
    exige("libro de Bybit", foto.get("libro_bybit"), "libro_bybit")
    mids = foto.get("mids") or {}
    exige("mid de Binance", mids.get("binance"), "entrada.referencia")
    exige("mid de Bybit", mids.get("bybit"), "mids.bybit")
    exige("funding", foto.get("funding"), "funding")
    costes = plan.get("costes") or {}
    for pata in ("entrada", "objetivo", "stop"):
        datos = costes.get(pata) or {}
        if not datos.get("venue"):
            errores.append(f"coste de la pata {pata} sin venue")
        exige(f"coste de la pata {pata}", datos.get("total_bps"), "p_equilibrio")
    cocientes = plan.get("cocientes") or {}
    exige("coste/objetivo", cocientes.get("coste_objetivo"), "p_equilibrio")
    exige("coste/riesgo", cocientes.get("coste_riesgo"), "p_equilibrio")
    r = plan.get("r") or {}
    exige("R bruto", r.get("bruto"), "p_equilibrio")
    exige("R neto", r.get("neto"), "p_equilibrio")
    exige("p* (equilibrio con coste)", plan.get("p_equilibrio"), "p_equilibrio")
    for nombre in FILTROS:
        f = filtros.get(nombre)
        if not isinstance(f, dict) or f.get("estado") not in ESTADOS_FILTRO:
            errores.append(f"filtro {nombre} ausente o con estado fuera de {ESTADOS_FILTRO}")
    huellas = foto.get("huellas") or {}
    for nombre in HUELLAS:
        if not huellas.get(nombre):
            errores.append(f"sin huella de {nombre}")
    if not foto.get("codigo_version"):
        errores.append("sin version del codigo")
    malos = [n for n in FILTROS if (filtros.get(n) or {}).get("estado") != "cumple"]
    if disparado:
        if malos:
            errores.append(f"DISPARADO con filtros que no cumplen: {', '.join(malos)}")
        spot = (flujos.get("spot") or {}).get("vela") or {}
        if not spot.get("completo") or (filtros.get("spot_vela") or {}).get("estado") != "cumple":
            errores.append("DISPARADO sin la pata spot completa y a favor (MC12)")
        retraso, tope = fila.get("retraso_s"), fila.get("tope_retraso_s")
        if retraso is None or tope is None or float(retraso) > float(tope):
            errores.append(f"DISPARADO con retraso {retraso} sobre el tope {tope}")
        if decision.get("estado") != "DISPARADO":
            errores.append("la decision de la foto no es DISPARADO")
    elif not malos and fila.get("motivo") != "tardio":
        errores.append("SOMBRA con todos los filtros cumplidos y sin ser tardia")
    return errores


def _sombra_sin(nombre: str, foto: dict[str, Any]) -> bool:
    """Una SOMBRA cuyo gatillo es de una vela pasada no carga flujos, libro ni mids: lo dice."""
    tramo = ((foto.get("flujos") or {}).get("spot") or {}).get("vela") or {}
    return bool(tramo.get("motivo")) and nombre in (
        "libro de Bybit", "mid de Binance", "mid de Bybit", "funding",
    )
