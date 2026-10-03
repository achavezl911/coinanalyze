"""El MOTOR de las entradas: una funcion PURA de la vela T y de sus insumos (campana 135, E1).

Nada aqui lee el reloj ni la base. Los insumos llegan ya cortados en T (insumos.py) y el estado
previo llega del registro (registro.py): mismo T y mismos insumos -> misma foto, byte a byte.

EL LARGO Y EL CORTO. El corto NO es el complemento del largo: tiene sus propias condiciones, que
son las del largo aplicadas al mercado REFLEJADO (precio -> -precio, compras <-> ventas). El motor
razona en el «espacio del lado» (zona_al_lado, vela_al_lado, _s): un corto es el reflejo exacto de
su largo por construccion, y el control del reflejo lo comprueba en vez de suponerlo.

LO QUE CONGELA. Al pasar a VIGILANDO, la zona y la escalera entera (MC5: todas las zonas hasta k
ATR diarios, no solo la mas cercana) se construyen SOLO con velas diarias y de 4 h cerradas antes
del inicio del episodio (corte = apertura de la vela que arma): ningun pivote del episodio define
su propia zona, y cada medida se ancla en el inicio de SU episodio, no en el primer evento de la
ventana de velas. El candidato se juzga contra su zona congelada aunque el precio este dentro.

LA FOTO BASTA. decidir(foto) recalcula plan, filtros y estado leyendo SOLO la foto; el generador
la llama exactamente asi, de modo que reproducir una decision desde el registro no es una promesa
sino el mismo camino.

Los defectos del sobre que NO se heredan: no se usan /api/hypothesis (MC1), level/breakout (MC2),
zone/analysis (MC6/MC8), cumulative_spot (MC9) ni precios de liquidacion (MC7); el flujo se mide
aqui por minutos con su hueco (MC10/MC11) y el largo exige su spot (MC12).
"""

from __future__ import annotations

import hashlib
import inspect
import re
from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Any

from app.entradas import reglamento as R
from app.interpretation import BARRIER_PIVOT_WIDTH, _barrier_candidates, _barrier_zones

CODIGO_VERSION = "entradas-motor-1"
ESQUEMA_FOTO = "entradas.foto.v1"
ESTADOS = ("VIGILANDO", "DISPARADO", "SOMBRA", "CERRADO_SIN_DISPARO")
LADOS = ("largo", "corto")
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
GEOMETRIA = ("objetivo", "coste_objetivo", "coste_riesgo", "r_neto_t1")
CUMPLE, FALLA, NO_EVALUABLE, NO_MEDIDO = "cumple", "falla", "no_evaluable", "no_medido"
REGLA_ENTRADA = {
    "mercado": "apertura_siguiente_minuto_tras_registro",
    "limite": "limite_cruzada_tras_registro",
}
PROSPECTIVO, BACKTEST = "prospectivo", "backtest"
BPS = 10_000
PCT = 100
MIN_DIA = 1440


class CodigoIncompatible(RuntimeError):
    """El reglamento declara algo que este codigo no aplica: no se emite ningun candidato."""


# EL VOCABULARIO QUE ESTE CODIGO APLICA. Cada valor de texto del reglamento que DECIDE algo se
# contrasta aqui: una version que diga otra cosa (otro evento, otro reloj, otra venue) no corre
# con la logica de v1 en silencio; se salta con su motivo (A62).
VOCABULARIO: dict[str, dict[tuple[str, ...], Any]] = {
    "F1": {
        ("zona_por_lado",): {"largo": "soporte", "corto": "resistencia"},
        ("evento",): "toque",
        ("aceptacion",): "cierre_al_otro_lado",
        ("gatillo",): "cierre_de_vuelta_fuera",
        ("stop_ancla",): "extremo_del_episodio",
        ("entrada",): "mercado",
    },
    "F2": {
        ("zona_por_lado",): {"largo": "resistencia", "corto": "soporte"},
        ("borde",): {"largo": "alto", "corto": "bajo"},
        ("sin_volver_dentro",): "ningun_cierre_dentro",
        ("gatillo",): "cierre_de_reaccion",
        ("stop_ancla",): "extremo_del_episodio",
        ("entrada",): "mercado",
    },
    "comun": {
        ("venues",): {"ejecucion": "bybit", "trayectoria": "binance", "funding": "binance"},
        ("invalidacion_reloj",): "UTC",
        ("atr", "estadistico"): "mediana_rango_verdadero",
        ("spot", "vela_gatillo"): "signo_del_lado",
        ("spot", "ultima_hora"): "no_en_contra",
        ("hueco", "spot"): "todos_los_minutos",
        ("hueco", "futuros"): "todos_los_minutos",
        ("colchon_stop", "racimo"): "tolerancia_racimo",
        ("colchon_stop", "fuera_de_racimo"): True,
    },
    "calendario": {("fuentes",): ["macro_event", "manual"]},
}


def _fijados_por_el_codigo_reutilizado() -> dict[str, float | None]:
    """Los valores que _barrier_candidates y _barrier_zones fijan por dentro y deciden los bordes
    de las zonas: se leen de su fuente para contrastarlos con lo que declara el reglamento."""
    zonas = inspect.getsource(_barrier_zones)
    candidatos = inspect.getsource(_barrier_candidates)
    margen = re.search(r"pad = tolerance \* ([0-9.]+)", zonas)
    peso = re.search(r'"touch_weight": ([0-9.]+) if source == "1d"', candidatos)
    return {
        "borde_pad_tolerancia": float(margen.group(1)) if margen else None,
        "peso_toque_1d": float(peso.group(1)) if peso else None,
        "pivote_anchura": BARRIER_PIVOT_WIDTH,
    }


FIJADOS_POR_EL_CODIGO = _fijados_por_el_codigo_reutilizado()


def incompatibilidades(version: dict[str, Any]) -> list[str]:
    """Lo que una version declara y este codigo NO aplica. Vacia = la version puede correr."""
    errores: list[str] = []
    for bloque, esperado in VOCABULARIO.items():
        valores = R.valores(version["bloques"][bloque])
        for camino, valor in esperado.items():
            actual: Any = valores
            for paso_ in camino:
                actual = actual.get(paso_) if isinstance(actual, dict) else None
            if actual != valor:
                errores.append(f"{bloque}.{'.'.join(camino)} = {actual!r} y el codigo aplica {valor!r}")
    zonas = R.valores(version["bloques"]["comun"])["zonas"]
    for nombre, fijado in FIJADOS_POR_EL_CODIGO.items():
        if fijado is None or zonas.get(nombre) != fijado:
            errores.append(f"comun.zonas.{nombre} = {zonas.get(nombre)!r} y el codigo reutilizado "
                           f"fija {fijado!r} (app/interpretation.py)")
    return errores


class FotoIncoherente(ValueError):
    """Una foto que no contiene la decision que dice contener."""


# --------------------------------------------------------------------------- utilidades


def iso(momento: datetime) -> str:
    """Instante UTC truncado al segundo: nunca redondea hacia el futuro."""
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def de_iso(texto: str) -> datetime:
    return datetime.strptime(texto, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def huella_foto(foto: dict[str, Any]) -> str:
    return R.huella(foto)


def foto_canonica(foto: dict[str, Any]) -> str:
    """El texto EXACTO que se guarda (columna json): sha256 de este texto = huella_foto."""
    return R.canonico(foto)


def _s(lado: str) -> float:
    if lado not in LADOS:
        raise CodigoIncompatible(f"lado desconocido {lado!r}")
    return 1.0 if lado == "largo" else -1.0


def zona_al_lado(zona: dict[str, Any], lado: str) -> tuple[float, float]:
    """(bajo, alto) de una zona en el espacio del lado: el corto la ve reflejada."""
    a, b = _s(lado) * zona["low"], _s(lado) * zona["high"]
    return (min(a, b), max(a, b))


def vela_al_lado(vela: dict[str, Any], lado: str) -> dict[str, float]:
    s = _s(lado)
    extremos = (s * vela["high"], s * vela["low"])
    return {"o": s * vela["open"], "h": max(extremos), "l": min(extremos), "c": s * vela["close"]}


def dist_pct(borde: float, precio: float) -> float:
    """La distancia de interpretation.py:942-947: |borde/precio - 1| en %."""
    return abs(borde / precio - 1) * PCT


def completa(vela: dict[str, Any]) -> bool:
    """VELA CERRADA DE VERDAD: todos sus minutos de 1 min presentes."""
    return vela["minutos"] == vela["esperados"]


def atr_mediana(velas: list[dict[str, Any]], n: int) -> float | None:
    """Mediana de los n ultimos rangos verdaderos (la convencion de interpretation.py:728-729)."""
    rangos: list[float] = []
    previo: float | None = None
    for v in velas:
        cierre = v["close"] if previo is None else previo
        rangos.append(max(v["high"] - v["low"], abs(v["high"] - cierre), abs(v["low"] - cierre)))
        previo = v["close"]
    muestra = [r for r in rangos[-n:] if r > 0]
    return median(muestra) if muestra else None


def episodio_id(version: str, symbol: str, familia: str, perfil: str, lado: str, clave: str,
                inicio: datetime) -> str:
    texto = "|".join((version, symbol, familia, perfil, lado, clave, iso(inicio)))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def clave_zona(zona: dict[str, Any]) -> str:
    return f"zona:{zona['low']!r}:{zona['high']!r}"


def solapan(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return a["low"] <= b["high"] and b["low"] <= a["high"]


def parametros(version: dict[str, Any], familia: str) -> dict[str, Any]:
    """Los valores que decide una version para una familia: lo que viaja en cada foto."""
    bloques = version["bloques"]
    return {
        "comun": R.valores(bloques["comun"]),
        "familia": R.valores(bloques[familia]),
        "calendario": R.valores(bloques["calendario"]),
    }


def huellas(version: dict[str, Any], familia: str, revision: dict[str, Any] | None,
            codigo: str) -> dict[str, str | None]:
    return {
        "familia": version["huellas"][familia],
        "comun": version["huellas"]["comun"],
        "calendario": version["huellas"]["calendario"],
        "calendario_datos": revision["huella"] if revision else None,
        "lectura": version["huellas"]["lectura"],
        "papel": version["huellas"]["papel"],
        "codigo": codigo,
    }


# --------------------------------------------------------------------------- zonas


def construir_zonas(
    *,
    diarias: list[dict[str, Any]],
    h4: list[dict[str, Any]],
    precio_corte: float | None,
    corte: datetime,
    comun: dict[str, Any],
) -> dict[str, Any]:
    """La escalera de zonas a la hora `corte`, con velas cerradas ANTES de ella (MC5: todas).

    Reutiliza _barrier_candidates y _barrier_zones (los mismos pivotes 1d+4h y el mismo
    agrupamiento que price_barriers), pero sin CVD -no tiene corte en el tiempo, scalp_logic.py
    :1347- y sin el ATR «de ahora»: el corte es un argumento, no el reloj.
    """
    z = comun["zonas"]
    if z["pivote_anchura"] != BARRIER_PIVOT_WIDTH:
        raise CodigoIncompatible(
            f"el reglamento pide pivotes de anchura {z['pivote_anchura']} y el codigo reutilizado "
            f"usa {BARRIER_PIVOT_WIDTH} (app/interpretation.py)"
        )
    diarias = diarias[-z["sesiones_1d"]:]
    h4 = h4[-z["velas_4h"]:]
    if len(diarias) < z["minimo_velas"] or len(h4) < z["minimo_velas"]:
        return {
            "disponible": False,
            "motivo": f"velas cerradas antes de {iso(corte)} insuficientes para zonas: 1d "
            f"{len(diarias)}, 4h {len(h4)} (minimo {z['minimo_velas']})",
        }
    atr_diario = atr_mediana(diarias, comun["atr"]["n"])
    if not atr_diario or not precio_corte:
        return {"disponible": False, "motivo": "sin ATR diario o sin precio en el corte"}
    tol = comun["tolerancia_racimo"]
    tolerancia = max(abs(precio_corte) * tol["pct_precio"] / PCT, atr_diario * tol["atr_diario"])
    candidatos: list[dict[str, Any]] = []
    for fuente, filas in (("1d", diarias), ("4h", h4)):
        encontrados, _ = _barrier_candidates(
            filas,
            source=fuente,
            time_key="t",
            high_key="high",
            low_key="low",
            close_key="close",
            volume_key="volume",
            bar_days=z["barra_min"][fuente] / MIN_DIA,
        )
        candidatos.extend(encontrados)
    todas = _barrier_zones(candidatos, precio_corte, tolerancia)
    rango = comun["escalera_atr_diarios"] * atr_diario
    escalera = sorted(
        (
            {
                "low": zona["low"],
                "high": zona["high"],
                "center": zona["center"],
                "score": zona["score"],
                "touches": zona["touches"],
                "sources": zona["sources"],
                "last_touch": zona["last_touch"],
            }
            for zona in todas
            if zona["high"] >= precio_corte - rango and zona["low"] <= precio_corte + rango
        ),
        key=lambda zona: (zona["low"], zona["high"]),
    )
    return {
        "disponible": True,
        "origen": "pivotes fractales 1d+4h agrupados (app/interpretation.py _barrier_candidates/"
        "_barrier_zones), velas ohlcv daily y 4hour cerradas antes del corte, sin CVD",
        "corte": iso(corte),
        "precio_corte": precio_corte,
        "atr_diario": atr_diario,
        "tolerancia_racimo": tolerancia,
        "ultima_vela": {
            "1d": {"inicio": diarias[-1]["t"], "cierre": diarias[-1]["cierre"]},
            "4h": {"inicio": h4[-1]["t"], "cierre": h4[-1]["cierre"]},
        },
        "n_zonas": len(todas),
        "escalera": escalera,
    }


# --------------------------------------------------------------------------- estructura


def _f1(zl: float, zh: float, velas: list[dict[str, float] | None], p: dict[str, Any]) -> dict:
    """RECHAZO DE ZONA en el espacio del lado: toca, no la acepta y cierra de vuelta fuera."""
    tocada = False
    for i, v in enumerate(velas):
        if v is None:  # vela incompleta: ni toca ni cierra (se anota en la foto)
            continue
        tocada = tocada or v["l"] <= zh
        if v["c"] < zl:
            return {"estado": "CERRADO", "i": i, "motivo": "zona aceptada: cierre al otro lado"}
        if tocada and v["c"] > zh:
            extremo = min(x["l"] for x in velas[: i + 1] if x is not None)
            return {"estado": "GATILLO", "i": i, "extremo": extremo}
        if not tocada and dist_pct(zh, v["c"]) > p["armar_distancia_pct"]:
            return {"estado": "CERRADO", "i": i, "motivo": "se alejo sin tocar la zona"}
    return {"estado": "VIGILANDO", "progreso": {"tocada": tocada}}


def _f2(
    zl: float, zh: float, velas: list[dict[str, float] | None], atr_perfil: float, p: dict[str, Any]
) -> dict:
    """RUPTURA + RETEST en el espacio del lado: rompe el BORDE alto con N cierres seguidos,
    retesta a <= k ATR del borde sin cerrar dentro, y dispara en el cierre de reaccion."""
    borde = zh
    seguidos = 0
    ruptura: int | None = None
    contacto = False
    for i, v in enumerate(velas):
        if ruptura is None:
            if v is None:
                seguidos = 0
                continue
            seguidos = seguidos + 1 if v["c"] > borde else 0
            if seguidos >= p["ruptura_cierres"]:
                ruptura = i
                continue
            if seguidos == 0 and v["c"] < zl and dist_pct(zl, v["c"]) > p["armar_distancia_pct"]:
                return {"estado": "CERRADO", "i": i, "motivo": "se alejo sin romper la zona"}
            continue
        if v is not None:
            if v["c"] <= borde:
                return {"estado": "CERRADO", "i": i, "motivo": "volvio dentro tras la ruptura"}
            if v["l"] <= borde + p["retest_atr_perfil"] * atr_perfil:
                contacto = True
            if contacto and v["c"] > v["o"] and v["c"] > borde:
                # El extremo del RETEST: velas despues de la ruptura confirmada hasta el gatillo.
                extremo = min(x["l"] for x in velas[ruptura + 1 : i + 1] if x is not None)
                return {"estado": "GATILLO", "i": i, "extremo": extremo, "ruptura": ruptura}
        if i - ruptura >= p["retest_max_velas"]:
            return {
                "estado": "CERRADO",
                "i": i,
                "motivo": f"sin retest con reaccion en {p['retest_max_velas']} velas",
            }
    return {
        "estado": "VIGILANDO",
        "progreso": {"ruptura": ruptura is not None, "contacto": contacto, "seguidos": seguidos},
    }


def estructura(familia: str, zona: dict[str, Any], lado: str, velas: list[dict[str, Any]],
               atr_perfil: float, p: dict[str, Any]) -> dict:
    zl, zh = zona_al_lado(zona, lado)
    al_lado = [vela_al_lado(v, lado) if completa(v) else None for v in velas]
    if familia == "F1":
        return _f1(zl, zh, al_lado, p)
    if familia == "F2":
        return _f2(zl, zh, al_lado, atr_perfil, p)
    raise CodigoIncompatible(f"familia desconocida {familia!r}")


def elegible(familia: str, zona: dict[str, Any], lado: str, precio_corte: float) -> bool:
    """F1 mira soportes en el corte (zona no entera por encima del precio); F2, resistencias."""
    zl, zh = zona_al_lado(zona, lado)
    pc = _s(lado) * precio_corte
    return zl <= pc if familia == "F1" else zh >= pc


def arma(familia: str, zona: dict[str, Any], lado: str, vela: dict[str, Any],
         p: dict[str, Any]) -> bool:
    """VIGILANDO: la vela toca la zona o cierra a <= armar_distancia_pct de su borde cercano."""
    if not completa(vela):
        return False
    zl, zh = zona_al_lado(zona, lado)
    v = vela_al_lado(vela, lado)
    if familia == "F1":
        return v["l"] <= zh or (v["c"] >= zl and dist_pct(zh, v["c"]) <= p["armar_distancia_pct"])
    return v["h"] >= zl or (v["c"] <= zh and dist_pct(zl, v["c"]) <= p["armar_distancia_pct"])


# --------------------------------------------------------------------------- decision


def _filtro(estado: str, valor: Any = None, umbral: Any = None, motivo: str | None = None) -> dict:
    return {"estado": estado, "valor": valor, "umbral": umbral, "motivo": motivo}


def _stop(extremo: float, colchon: float, escalera: list[tuple[float, float]]) -> tuple[float, list]:
    """Mas alla del extremo con colchon, y fuera de todo racimo: si cae dentro de una zona, se
    repite desde su borde lejano."""
    stop = extremo - colchon
    saltados: list[list[float]] = []
    for _ in range(len(escalera) + 1):
        dentro = [z for z in escalera if z[0] <= stop <= z[1]]
        if not dentro:
            break
        z = min(dentro)
        saltados.append([z[0], z[1]])
        stop = z[0] - colchon
    return stop, saltados


def _pata(tipo: str, componentes_por_tipo: dict[str, list[str]], comision: dict[str, float],
          spread: float | None, desl: float | None, venue: str, modo: str) -> dict[str, Any]:
    valores: dict[str, float | None] = {}
    for c in componentes_por_tipo[tipo]:
        if c in comision:
            valores[c] = comision[c]
        elif c == "spread":
            valores[c] = spread
        elif c == "deslizamiento":
            valores[c] = desl
        else:
            raise CodigoIncompatible(f"componente de coste desconocido {c!r}")
    faltan = [c for c, v in valores.items() if v is None]
    if faltan and modo != BACKTEST:
        total = None
    else:
        total = sum(v for v in valores.values() if v is not None)
    return {"tipo": tipo, "venue": venue, "componentes_bps": valores, "no_medido": faltan,
            "total_bps": total}


def decidir(foto: dict[str, Any]) -> dict[str, Any]:
    """Plan, filtros y decision leidos SOLO de la foto (sin plan/filtros/decision previos)."""
    pc = foto["parametros"]["comun"]
    pf = foto["parametros"]["familia"]
    pcal = foto["parametros"]["calendario"]
    p = {**pc, **pf}
    lado, perfil, modo = foto["lado"], foto["perfil"], foto["modo"]
    s = _s(lado)
    zona = foto["zona"]
    velas = foto["episodio"]["velas"]
    atr_perfil = foto["atr"]["perfil"]
    hecho = estructura(foto["familia"], zona, lado, velas, atr_perfil, p)
    if hecho["estado"] != "GATILLO" or hecho["i"] != len(velas) - 1:
        raise FotoIncoherente("la foto no trae un gatillo en su ultima vela")

    escalera = [zona_al_lado(z, lado) for z in foto["escalera"]]
    mid = (foto.get("mids") or {}).get("binance")
    entrada = s * mid["mid"] if mid else None
    colchon = max(pc["colchon_stop"]["atr_perfil"] * atr_perfil, foto["atr"]["tolerancia_racimo"])
    stop_lado, saltados = _stop(hecho["extremo"], colchon, escalera)
    objetivos_lado = (
        sorted(z[0] for z in escalera if z[0] > entrada)[: pc["objetivos_n"]]
        if entrada is not None
        else []
    )
    libro = foto.get("libro_bybit")
    libro_ok = bool(libro) and libro["edad_s"] <= pc["libro_edad_max_s"]
    spread = libro["spread_bps"] if libro_ok else None
    desl_entrada = desl_salida = None
    if libro_ok:
        compra, venta = libro["ask_notional_l1"], libro["bid_notional_l1"]
        entra, sale = (compra, venta) if lado == "largo" else (venta, compra)
        desl_entrada = 0.0 if entra is not None and pc["tamano_plan_usd"] <= entra else None
        desl_salida = 0.0 if sale is not None and pc["tamano_plan_usd"] <= sale else None
    venue = pc["venues"]["ejecucion"]
    comision = pc["comision_bps_lado"]
    patas = {
        "entrada": _pata(pf["entrada"], pc["coste_pata"], comision, spread, desl_entrada, venue, modo),
        "objetivo": _pata("limite", pc["coste_pata"], comision, spread, None, venue, modo),
        "stop": _pata("stop", pc["coste_pata"], comision, spread, desl_salida, venue, modo),
    }
    c_ent, c_obj, c_stop = (patas[k]["total_bps"] for k in ("entrada", "objetivo", "stop"))

    filtros: dict[str, dict] = {}
    ausencias: dict[str, str] = {}
    d_t1 = d_stop = cociente_obj = cociente_riesgo = r_bruto = r_neto = p_eq = None
    if entrada is None:
        motivo = "sin mid de Binance en T: no hay referencia para medir el plan"
        ausencias.update({"entrada.referencia": motivo, "p_equilibrio": motivo})
        for nombre in GEOMETRIA:
            filtros[nombre] = _filtro(NO_EVALUABLE, motivo=motivo)
    else:
        if objetivos_lado:
            filtros["objetivo"] = _filtro(CUMPLE, valor=len(objetivos_lado))
            d_t1 = (objetivos_lado[0] - entrada) / abs(entrada) * BPS
        else:
            motivo = f"ninguna zona opuesta en la escalera ({pc['escalera_atr_diarios']} ATR diarios)"
            filtros["objetivo"] = _filtro(FALLA, valor=0, motivo=motivo)
            ausencias["objetivos"] = motivo
        d_stop = (entrada - stop_lado) / abs(entrada) * BPS
        costes_ok = None not in (c_ent, c_obj, c_stop)
        motivo_coste = None if costes_ok else (
            "libro de Bybit ausente, rancio (> "
            f"{pc['libro_edad_max_s']} s) o sin profundidad L1 para {pc['tamano_plan_usd']} USD"
        )
        sin_t1 = "sin T1: el plan no tiene objetivo por estructura"
        stop_malo = "el stop estructural no queda mas alla de la entrada"
        # coste/objetivo: depende de T1 y del coste
        if d_t1 is None:
            filtros["coste_objetivo"] = _filtro(FALLA, motivo=sin_t1)
        elif not costes_ok:
            filtros["coste_objetivo"] = _filtro(NO_EVALUABLE, motivo=motivo_coste)
        else:
            cociente_obj = (c_ent + c_obj) / d_t1
            filtros["coste_objetivo"] = _filtro(
                CUMPLE if cociente_obj <= pc["banda_coste_objetivo_max"] else FALLA,
                round(cociente_obj, 4),
                pc["banda_coste_objetivo_max"],
            )
        # coste/riesgo: depende del stop y del coste
        if d_stop <= 0:
            filtros["coste_riesgo"] = _filtro(FALLA, valor=round(d_stop, 4), motivo=stop_malo)
        elif not costes_ok:
            filtros["coste_riesgo"] = _filtro(NO_EVALUABLE, motivo=motivo_coste)
        else:
            cociente_riesgo = (c_ent + c_stop) / d_stop
            filtros["coste_riesgo"] = _filtro(
                CUMPLE if cociente_riesgo <= pc["banda_coste_riesgo_max"] else FALLA,
                round(cociente_riesgo, 4),
                pc["banda_coste_riesgo_max"],
            )
        # R neto en T1 y el equilibrio: dependen de los tres
        if d_t1 is None or d_stop <= 0:
            filtros["r_neto_t1"] = _filtro(FALLA, motivo=sin_t1 if d_t1 is None else stop_malo)
            ausencias["p_equilibrio"] = sin_t1 if d_t1 is None else stop_malo
        elif not costes_ok:
            filtros["r_neto_t1"] = _filtro(NO_EVALUABLE, motivo=motivo_coste)
            ausencias["p_equilibrio"] = motivo_coste
        else:
            r_bruto = d_t1 / d_stop
            ganancia = d_t1 - c_ent - c_obj
            perdida = d_stop + c_ent + c_stop
            r_neto = ganancia / perdida
            filtros["r_neto_t1"] = _filtro(
                CUMPLE if r_neto >= pc["r_neto_min_t1"] else FALLA,
                round(r_neto, 4),
                pc["r_neto_min_t1"],
            )
            if ganancia > 0:
                p_eq = perdida / (ganancia + perdida)
            else:
                ausencias["p_equilibrio"] = "el objetivo no paga el coste: no hay equilibrio"

    vol = foto["volumen"]
    base_minima = vol["base_total"] * pc["volumen"]["fraccion_minima_completas"]
    if vol["base_mediana"] is None or vol["base_completas"] < base_minima:
        filtros["volumen"] = _filtro(
            NO_EVALUABLE,
            motivo=f"base de volumen con {vol['base_completas']} de {vol['base_total']} velas completas",
        )
    else:
        multiple = vol["vela"] / vol["base_mediana"] if vol["base_mediana"] > 0 else 0.0
        filtros["volumen"] = _filtro(
            CUMPLE if multiple >= pc["volumen"]["min_x"] else FALLA,
            round(multiple, 4),
            pc["volumen"]["min_x"],
        )

    spot = foto["flujos"]["spot"]
    for nombre, ventana, estricto in (("spot_vela", "vela", True), ("spot_hora", "ultima_hora", False)):
        tramo = spot[ventana]
        if not tramo["completo"]:
            filtros[nombre] = _filtro(
                NO_EVALUABLE,
                motivo=f"hueco de spot: {tramo['minutos']} de {tramo['esperados']} minutos con las "
                f"{pc['hueco']['spot_venues']} venues",
            )
            continue
        a_favor = s * tramo["delta_usd"]
        ok = a_favor > 0 if estricto else a_favor >= 0
        filtros[nombre] = _filtro(CUMPLE if ok else FALLA, round(a_favor, 2), 0)

    cal = foto["calendario"]
    if not cal["cubierto"]:
        filtros["calendario"] = _filtro(
            NO_MEDIDO if modo == BACKTEST else NO_EVALUABLE,
            motivo=f"calendario sin cubrir: la ventana acaba {cal['ventana']['hasta']} y la "
            f"revision {cal['revision']} cubre hasta {cal['cubre_hasta']}",
        )
    elif cal["eventos"]:
        filtros["calendario"] = _filtro(
            FALLA,
            valor=[e["clave"] for e in cal["eventos"]],
            umbral=pcal["importancia_minima"],
            motivo="evento de importancia alta dentro de la ventana",
        )
    else:
        filtros["calendario"] = _filtro(CUMPLE, valor=0, umbral=pcal["importancia_minima"])

    # Insumos que un DISPARADO tiene que traer aunque no sean filtros (C3): sin ellos la foto no
    # basta y el candidato va a SOMBRA «datos», con el motivo servido. En BACKTEST el espejo no
    # tiene libro: lo que falta por eso se declara NO MEDIDO y no manda a SOMBRA.
    no_medidos: list[str] = []
    faltan: list[str] = []
    for nombre, valor, clave in (
        ("libro de Bybit", foto.get("libro_bybit"), "libro_bybit"),
        ("mid de Bybit", (foto.get("mids") or {}).get("bybit"), "mids.bybit"),
        ("funding", foto.get("funding"), "funding"),
    ):
        if valor:
            continue
        if modo == BACKTEST and clave != "funding":
            no_medidos.append(nombre)
        else:
            faltan.append(nombre)
            ausencias.setdefault(clave, f"{nombre}: sin dato en T (ausente o rancio)")
    malos = [n for n in FILTROS if filtros[n]["estado"] in (FALLA, NO_EVALUABLE)]
    estado = "SOMBRA" if malos or faltan else "DISPARADO"
    etiquetas: list[str] = []
    if any(filtros[n]["estado"] == FALLA for n in GEOMETRIA):
        etiquetas.append("geometria")
    if filtros["calendario"]["estado"] == FALLA:
        etiquetas.append("evento")
    if filtros["calendario"]["estado"] == NO_EVALUABLE:
        etiquetas.append("calendario sin cubrir")
    fut = foto["flujos"]["futuros"]["vela"]
    if filtros["spot_vela"]["estado"] == FALLA and fut["completo"] and s * fut["delta_usd"] > 0:
        etiquetas.append("solo perpetuo")
    for nombre in ("volumen", "spot_vela", "spot_hora"):
        if filtros[nombre]["estado"] == FALLA:
            etiquetas.append(nombre)

    fin = de_iso(velas[-1]["fin"])
    caduca = fin + timedelta(minutes=pc["caducidad_min"][perfil])
    nivel = zona["low"] if (foto["familia"] == "F1") == (lado == "largo") else zona["high"]
    banda = None
    if spread is not None or modo == BACKTEST:
        banda = (spread or 0.0) + (desl_entrada or 0.0)
    plan = {
        "entrada": {
            "tipo": pf["entrada"],
            "precio": None,
            "regla_codigo": REGLA_ENTRADA[pf["entrada"]],
            "regla": "apertura de la vela de 1 min floor(registered_at)+1min, mas spread y "
            "deslizamiento congelados en banda pesimista (largo: maximo; corto: minimo)"
            if pf["entrada"] == "mercado"
            else "limite: solo se llena si el precio la CRUZA despues de registered_at",
            "referencia": {"precio": mid["mid"], "ts": mid["ts"], "fuente": "orderbook_snapshot binance mid en T"}
            if mid
            else None,
            "banda_pesimista_bps": banda,
        },
        "stop": {
            "precio": s * stop_lado,
            "extremo_episodio": s * hecho["extremo"],
            "colchon": colchon,
            "racimos_saltados": [[s * a, s * b] for a, b in saltados],
            "tipo_disparo": "stop a mercado (taker) sobre el precio de Binance (.A)",
        },
        "objetivos": [s * t for t in objetivos_lado],
        "invalidacion": {
            "nivel": nivel,
            "regla": "cierre de vela del perfil al otro lado de la zona congelada",
            "reloj": f"{pc['invalidacion_reloj']}: velas de {pc['perfiles'][perfil]['vela_min']} min "
            "con date_bin desde 1970-01-01",
            "hasta": iso(caduca),
        },
        "caducidad": {"minutos": pc["caducidad_min"][perfil], "caduca_en": iso(caduca)},
        "costes": patas,
        "distancias_bps": {"t1": d_t1, "stop": d_stop},
        "cocientes": {"coste_objetivo": cociente_obj, "coste_riesgo": cociente_riesgo},
        "r": {"bruto": r_bruto, "neto": r_neto},
        "p_equilibrio": p_eq,
    }
    return {
        "plan": plan,
        "filtros": filtros,
        "decision": {
            "estado": estado,
            "motivo": malos + [f"falta {nombre}" for nombre in faltan],
            "tipo_sombra": None
            if estado == "DISPARADO"
            else (
                "datos"
                if faltan or any(filtros[n]["estado"] == NO_EVALUABLE for n in malos)
                else "filtro"
            ),
            "etiquetas": etiquetas,
            "ausencias": ausencias,
            "no_medido_backtest": no_medidos,
        },
    }


# --------------------------------------------------------------------------- el paso


def _ventana(insumos: dict[str, Any], pata: str, ventana: str) -> dict[str, Any]:
    tramo = insumos["flujos"][pata][ventana]
    return dict(tramo)


def _base_volumen(velas: list[dict[str, Any]], indice: int, n: int) -> dict[str, Any]:
    previas = velas[max(0, indice - n) : indice]
    completas = [v["volume"] for v in previas if completa(v)]
    return {
        "vela": velas[indice]["volume"],
        "base_mediana": median(completas) if completas else None,
        "base_completas": len(completas),
        "base_total": n,
    }


def _foto_base(*, version: dict, familia: str, perfil: str, lado: str, symbol: str, T: datetime,
               modo: str, revision: dict | None, codigo: str) -> dict[str, Any]:
    return {
        "esquema": ESQUEMA_FOTO,
        "codigo_version": CODIGO_VERSION,
        "modo": modo,
        "version": version["version"],
        "familia": familia,
        "perfil": perfil,
        "lado": lado,
        "symbol": symbol,
        "vela_cierre": iso(T),
        "parametros": parametros(version, familia),
        "huellas": huellas(version, familia, revision, codigo),
    }


def _calendario(T: datetime, perfil: str, pcal: dict[str, Any], revision: dict | None,
                eventos_macro: list[dict[str, Any]]) -> dict[str, Any]:
    hasta = T + timedelta(minutes=pcal["ventana_min"][perfil])
    cubre = R.instante(revision["cubre_hasta"]) if revision else None
    dentro = []
    for e in eventos_macro:
        hora = de_iso(e["hora_utc"])
        if T <= hora < hasta and e["importancia"] >= pcal["importancia_minima"]:
            dentro.append({**e, "fuente_tabla": "macro_event"})
    for e in (revision or {}).get("eventos", []):
        hora = R.instante(e["hora_utc"])
        if T <= hora < hasta and e["importancia"] >= pcal["importancia_minima"]:
            dentro.append({**e, "fuente_tabla": "manual"})
    dentro.sort(key=lambda e: (e["hora_utc"], e["clave"]))
    return {
        "revision": revision["revision"] if revision else None,
        "cubre_hasta": revision["cubre_hasta"] if revision else None,
        "ventana": {"desde": iso(T), "hasta": iso(hasta)},
        "cubierto": cubre is not None and hasta <= cubre,
        "eventos": dentro,
    }


def _ocupaciones(previos: list[dict[str, Any]], T: datetime, velas: list[dict[str, Any]],
                 sep_atr: float, ventana_inicio: datetime) -> tuple[dict, list[dict]]:
    """Episodios abiertos y zonas ocupadas de UNA clave de grupo (version, simbolo, familia,
    perfil, lado). Ocupa: un VIGILANDO abierto, un DISPARADO hasta su caducidad, y un episodio
    cerrado mientras el precio no se haya separado de su zona."""
    por_episodio: dict[str, list[dict[str, Any]]] = {}
    for fila in previos:
        por_episodio.setdefault(fila["episodio"], []).append(fila)
    abiertos: dict[str, dict[str, Any]] = {}
    ocupadas: list[dict[str, Any]] = []
    for ep, filas in por_episodio.items():
        filas.sort(key=lambda f: (f["vela_cierre"], f["orden"]))
        ultima = filas[-1]
        vigilando = next((f for f in filas if f["estado"] == "VIGILANDO"), None)
        # Si la ventana del registro dejo fuera el VIGILANDO, la fila terminal trae la misma
        # zona congelada y el mismo ATR (cada foto terminal copia la congelada).
        congelado = (vigilando or ultima)["foto"]
        if ultima["estado"] == "VIGILANDO":
            abiertos[ep] = {"vigilando": vigilando, "congelado": congelado}
            ocupadas.append(congelado["zona"])
            continue
        fin = ultima["caduca_en"] if ultima["estado"] == "DISPARADO" else ultima["vela_cierre"]
        if ultima["estado"] == "DISPARADO" and fin > T:
            ocupadas.append(congelado["zona"])
            continue
        if fin < ventana_inicio:
            continue  # cerrado antes de la ventana de separacion: cuenta como separado
        zona = congelado["zona"]
        umbral = sep_atr * congelado["atr"]["perfil"]
        separado = False
        for v in velas:
            if de_iso(v["fin"]) <= fin or de_iso(v["fin"]) > T or not completa(v):
                continue
            c = v["close"]
            distancia = 0.0 if zona["low"] <= c <= zona["high"] else min(
                abs(c - zona["low"]), abs(c - zona["high"])
            )
            if distancia >= umbral:
                separado = True
                break
        if not separado:
            ocupadas.append(zona)
    return abiertos, ocupadas


def paso(
    *,
    T: datetime,
    symbol: str,
    perfil: str,
    modo: str,
    versiones: list[dict[str, Any]],
    insumos: dict[str, Any],
    previos: list[dict[str, Any]],
    revision: dict[str, Any] | None,
    codigo: str,
) -> dict[str, Any]:
    """Una vela T de un simbolo y un perfil, para todas las versiones en curso.

    `previos`: filas del registro de este simbolo y perfil con vela_cierre < T (cada una con
    version, familia, lado, clave, episodio, estado, vela_cierre, caduca_en, orden y su foto).
    Devuelve las transiciones a registrar y como fue la evaluacion (para el latido).
    """
    velas = insumos["velas"]
    if not velas or de_iso(velas[-1]["fin"]) != T:
        return {"transiciones": [], "evaluacion": {"estado": "no_evaluable",
                "motivo": f"no hay vela del perfil que cierre en {iso(T)}"}}
    actual = velas[-1]
    if not completa(actual):
        return {"transiciones": [], "evaluacion": {"estado": "no_evaluable",
                "motivo": f"vela {actual['inicio']} incompleta: {actual['minutos']} de "
                f"{actual['esperados']} minutos de ohlcv 1min"}}
    transiciones: list[dict[str, Any]] = []
    zonas_por_comun: dict[str, dict[str, Any]] = {}
    motivos: list[str] = []
    for version in versiones:
        incompatible = incompatibilidades(version)
        if incompatible:
            motivos.append(f"{version['version']} NO CORRE: {'; '.join(incompatible)}")
            continue
        pc = R.valores(version["bloques"]["comun"])
        if symbol not in pc["simbolos"]:
            continue
        vela_min = pc["perfiles"][perfil]["vela_min"]
        inicio_actual = T - timedelta(minutes=vela_min)
        clave_comun = version["huellas"]["comun"]
        if clave_comun not in zonas_por_comun:
            zonas_por_comun[clave_comun] = construir_zonas(
                diarias=insumos["diarias"],
                h4=insumos["h4"],
                precio_corte=insumos["precio_corte"],
                corte=inicio_actual,
                comun=pc,
            )
        zonas = zonas_por_comun[clave_comun]
        if not zonas["disponible"]:
            motivos.append(f"{version['version']}: {zonas['motivo']}")
        completas = [v for v in velas if completa(v)]
        indices = {v["inicio"]: i for i, v in enumerate(velas)}
        for familia in R.FAMILIAS:
            p = {**pc, **R.valores(version["bloques"][familia])}
            for lado in LADOS:
                grupo = [
                    f for f in previos
                    if f["version"] == version["version"] and f["familia"] == familia
                    and f["lado"] == lado
                ]
                ventana_sep = T - timedelta(
                    minutes=vela_min * pc["separacion_ventana_velas"][perfil]
                )
                abiertos, ocupadas = _ocupaciones(
                    grupo, T, velas, pc["separacion_atr_perfil"], ventana_sep
                )
                base = {"version": version, "familia": familia, "perfil": perfil, "lado": lado,
                        "symbol": symbol, "modo": modo, "revision": revision, "codigo": codigo}
                for ep in abiertos.values():
                    transiciones.extend(
                        _avanza(ep, T, velas, indices, insumos, p, base)
                    )
                if not zonas["disponible"]:
                    continue
                atr_perfil = atr_mediana(
                    [v for v in completas if de_iso(v["fin"]) <= inicio_actual], pc["atr"]["n"]
                )
                if not atr_perfil:
                    motivos.append(f"{version['version']} {familia} {lado}: sin ATR del perfil")
                    continue
                for zona in zonas["escalera"]:
                    if not elegible(familia, zona, lado, zonas["precio_corte"]):
                        continue
                    if any(solapan(zona, o) for o in ocupadas):
                        continue
                    if not arma(familia, zona, lado, actual, p):
                        continue
                    hecho = estructura(familia, zona, lado, [actual], atr_perfil, p)
                    if hecho["estado"] == "CERRADO":
                        continue  # la vela que armaria ya lo cierra: no hay episodio
                    nuevas = _nuevo_episodio(zona, zonas, atr_perfil, inicio_actual, T, velas,
                                             indices, insumos, p, base, hecho)
                    transiciones.extend(nuevas)
                    ocupadas.append(zona)
    return {
        "transiciones": transiciones,
        "evaluacion": {"estado": "ok", "motivo": "; ".join(motivos) or None,
                       "transiciones": len(transiciones)},
    }


def _fila(base: dict, *, estado: str, clave: str, episodio: str, inicio: datetime,
          vela_cierre: datetime, foto: dict, motivo: str | None, caduca_en: datetime | None) -> dict:
    pc = foto["parametros"]["comun"]
    return {
        "version": base["version"]["version"],
        "familia": base["familia"],
        "perfil": base["perfil"],
        "lado": base["lado"],
        "symbol": base["symbol"],
        "clave": clave,
        "episodio": episodio,
        "estado": estado,
        "motivo": motivo,
        "vela_cierre": vela_cierre,
        "inicio_episodio": inicio,
        "caduca_en": caduca_en,
        "tope_retraso_s": pc["tope_retraso_s"],
        "huellas": foto["huellas"],
        "codigo_version": CODIGO_VERSION,
        "foto": foto,
        "huella_foto": huella_foto(foto),
    }


def _nuevo_episodio(zona: dict, zonas: dict, atr_perfil: float, inicio: datetime, T: datetime,
                    velas: list[dict], indices: dict, insumos: dict, p: dict, base: dict,
                    hecho: dict) -> list[dict]:
    clave = clave_zona(zona)
    ep = episodio_id(base["version"]["version"], base["symbol"], base["familia"], base["perfil"],
                     base["lado"], clave, inicio)
    congelado = _foto_base(T=T, **{k: base[k] for k in ("version", "familia", "perfil", "lado",
                                                        "symbol", "modo", "revision", "codigo")})
    congelado.update(
        {
            "estado": "VIGILANDO",
            "zona": zona,
            "escalera": zonas["escalera"],
            "corte_zonas": zonas["corte"],
            "precio_corte": zonas["precio_corte"],
            "ultima_vela_zonas": zonas["ultima_vela"],
            "zonas_origen": zonas["origen"],
            "atr": {
                "diario": zonas["atr_diario"],
                "perfil": atr_perfil,
                "tolerancia_racimo": zonas["tolerancia_racimo"],
                "definicion": "mediana de los ultimos rangos verdaderos (n del bloque comun)",
            },
            "episodio": {"id": ep, "inicio": iso(inicio), "velas": [velas[-1]]},
        }
    )
    filas = [_fila(base, estado="VIGILANDO", clave=clave, episodio=ep, inicio=inicio,
                   vela_cierre=T, foto=congelado, motivo=None, caduca_en=None)]
    if hecho["estado"] == "GATILLO":
        filas.append(_terminal_gatillo(congelado, [velas[-1]], T, velas, indices, insumos, p, base,
                                       clave, ep, inicio))
    return filas


def _avanza(ep: dict, T: datetime, velas: list[dict], indices: dict, insumos: dict, p: dict,
            base: dict) -> list[dict]:
    vig = ep["vigilando"]
    congelado = ep["congelado"]
    inicio = vig["inicio_episodio"]
    del_episodio = [v for v in velas if de_iso(v["inicio"]) >= inicio and de_iso(v["fin"]) <= T]
    hecho = estructura(base["familia"], congelado["zona"], base["lado"], del_episodio,
                       congelado["atr"]["perfil"], p)
    clave, episodio = vig["clave"], vig["episodio"]
    if hecho["estado"] == "GATILLO":
        hasta = del_episodio[: hecho["i"] + 1]
        cierre = de_iso(hasta[-1]["fin"])
        return [_terminal_gatillo(congelado, hasta, cierre, velas, indices, insumos, p, base, clave,
                                  episodio, inicio)]
    if hecho["estado"] == "CERRADO":
        hasta = del_episodio[: hecho["i"] + 1]
        return [_terminal_cerrado(congelado, hasta, de_iso(hasta[-1]["fin"]), hecho["motivo"], base,
                                  clave, episodio, inicio)]
    if T - inicio >= timedelta(minutes=p["vigilando_max_min"][base["perfil"]]):
        return [_terminal_cerrado(congelado, del_episodio, T,
                                  f"vida maxima de VIGILANDO ({p['vigilando_max_min'][base['perfil']]} min)",
                                  base, clave, episodio, inicio)]
    return []


def _terminal_cerrado(congelado: dict, velas_ep: list[dict], cierre: datetime, motivo: str,
                      base: dict, clave: str, episodio: str, inicio: datetime) -> dict:
    foto = {k: v for k, v in congelado.items() if k != "episodio"}
    foto.update(
        {
            "estado": "CERRADO_SIN_DISPARO",
            "vela_cierre": iso(cierre),
            "episodio": {"id": episodio, "inicio": iso(inicio), "velas": velas_ep},
            "motivo": motivo,
        }
    )
    return _fila(base, estado="CERRADO_SIN_DISPARO", clave=clave, episodio=episodio, inicio=inicio,
                 vela_cierre=cierre, foto=foto, motivo=motivo, caduca_en=None)


def _terminal_gatillo(congelado: dict, velas_ep: list[dict], cierre: datetime, velas: list[dict],
                      indices: dict, insumos: dict, p: dict, base: dict, clave: str, episodio: str,
                      inicio: datetime) -> dict:
    perfil = base["perfil"]
    actual = cierre == insumos["T"]
    foto = {k: v for k, v in congelado.items() if k not in ("episodio", "estado")}
    foto["vela_cierre"] = iso(cierre)
    foto["episodio"] = {"id": episodio, "inicio": iso(inicio), "velas": velas_ep}
    foto["volumen"] = _base_volumen(velas, indices[velas_ep[-1]["inicio"]],
                                    p["volumen"]["base_velas"][perfil])
    if actual:
        foto["flujos"] = {
            "spot": {"vela": _ventana(insumos, "spot", "vela"),
                     "ultima_hora": _ventana(insumos, "spot", "ultima_hora")},
            "futuros": {"vela": _ventana(insumos, "futuros", "vela"),
                        "ultima_hora": _ventana(insumos, "futuros", "ultima_hora")},
        }
        foto["libro_bybit"] = insumos["libro_bybit"]
        foto["mids"] = insumos["mids"]
        foto["funding"] = insumos["funding"]
    else:
        vacio = {"delta_usd": None, "minutos": 0, "esperados": None, "completo": False,
                 "desde": None, "hasta": None, "ultimo_minuto": None,
                 "motivo": "gatillo en una vela pasada: sus flujos no se cargaron en esta pasada"}
        foto["flujos"] = {"spot": {"vela": vacio, "ultima_hora": vacio},
                          "futuros": {"vela": vacio, "ultima_hora": vacio}}
        foto["libro_bybit"] = None
        foto["mids"] = None
        foto["funding"] = None
    foto["calendario"] = _calendario(cierre, perfil, foto["parametros"]["calendario"],
                                     base["revision"], insumos["eventos_macro"])
    resultado = decidir(foto)
    foto.update(resultado)
    decision = resultado["decision"]
    estado = decision["estado"]
    caduca = de_iso(resultado["plan"]["caducidad"]["caduca_en"])
    motivo = None if estado == "DISPARADO" else ",".join(decision["motivo"])
    return _fila(base, estado=estado, clave=clave, episodio=episodio, inicio=inicio,
                 vela_cierre=cierre, foto=foto, motivo=motivo,
                 caduca_en=caduca if estado == "DISPARADO" else None)
