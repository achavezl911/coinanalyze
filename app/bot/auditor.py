"""AUDITOR R1: reglas fijas entre la respuesta de Opus y el mensaje de Telegram (encargo del dueno del 2026-11-22,
pasos 2 y 3; entregas/AUDITOR-R1-encargo-dueno-20261122.md).

PURO: sin red, sin base, sin reloj propio (recibe `ahora`), sin azar. Mismas entradas, mismo dictamen.

Nueve compuertas, cada una con una severidad: OK y NO_APLICABLE aprueban, AVISO deja CON RESERVAS, FALLA
RECHAZA y NO_EVALUABLE deja el dictamen NO EVALUABLE. El estado es la PEOR severidad; sin compuertas no hay
dictamen. Falla CERRADO en tres capas: una excepcion en una compuerta, un dato que falta o un umbral que falta dan
NO_EVALUABLE con su motivo. Un umbral NUNCA se inventa aqui: se lee de donde vive (calc.py, scalp_logic.py,
ai_context.py, config/entradas/reglamento.json) y si no se puede leer, la compuerta que lo usa no evalua.
"""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from app.bot import calc

VERSION = "auditor-r1"
OK, NO_APLICABLE, AVISO, FALLA, NO_EVALUABLE = "OK", "NO_APLICABLE", "AVISO", "FALLA", "NO_EVALUABLE"
RANGO = {OK: 0, NO_APLICABLE: 0, AVISO: 1, FALLA: 2, NO_EVALUABLE: 3}
ESTADOS = {0: "APROBADO", 1: "CON RESERVAS", 2: "RECHAZADO", 3: "NO EVALUABLE"}
COMPUERTAS = ("A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9")
RIESGO = ("A5", "A6", "A7")  # una FALLA en estas manda ademas una alerta aparte (respuesta 3 del dueno)
VEREDICTOS = ("A FAVOR", "EN CONTRA", "NO EVALUABLE")
CON_LADO = ("A FAVOR", "EN CONTRA")
BPS = 10_000.0


class UmbralFaltante(LookupError):
    pass


class DatoFaltante(LookupError):
    pass


def _carga_umbrales() -> dict[str, Any]:
    """Cada umbral, de donde vive. Lo que no se puede leer NO entra: la compuerta que lo pida dira cual falta."""
    u: dict[str, Any] = {"PERDIDA_MAX": calc.PERDIDA_MAX, "LIQ_VECES": calc.LIQ_VECES}
    try:  # importa ~100 modulos y tarda medio segundo, sin efectos: solo al cargar este, una vez
        from app.scalp_logic import REALTIME_STALE_SECONDS
        u["REALTIME_STALE_SECONDS"] = float(REALTIME_STALE_SECONDS)
    except Exception:  # noqa: BLE001 - falla cerrado: A2 dira que falta
        pass
    try:
        from app.ai_context import MESA_DECIDE_MAX_AGE_S
        u["MESA_DECIDE_MAX_AGE_S"] = float(MESA_DECIDE_MAX_AGE_S)
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.entradas import reglamento as R
        v = R.version_activa(R.cargar_valido())
        comun, cal = R.valores(v["bloques"]["comun"]), R.valores(v["bloques"]["calendario"])
        u["reglamento"] = v["version"]
        for k in ("libro_edad_max_s", "comision_bps_lado", "coste_pata", "banda_coste_objetivo_max",
                  "banda_coste_riesgo_max"):
            if k in comun:
                u[k] = comun[k]
        if "importancia_minima" in cal:
            u["importancia_minima"] = cal["importancia_minima"]
        if "intradia" in (cal.get("ventana_min") or {}):
            u["ventana_min_intradia"] = cal["ventana_min"]["intradia"]
    except Exception:  # noqa: BLE001
        pass
    return u


UMBRALES = _carga_umbrales()


@dataclass
class Compuerta:
    nombre: str
    severidad: str
    razon: str
    valor: Any = None
    umbral: Any = None

    def como_dict(self) -> dict[str, Any]:
        return {"nombre": self.nombre, "severidad": self.severidad, "razon": self.razon,
                "valor": _limpio(self.valor), "umbral": _limpio(self.umbral)}


@dataclass
class Dictamen:
    estado: str
    razon: str
    compuertas: list[Compuerta] = field(default_factory=list)
    ahora: str | None = None
    version: str = VERSION
    reglamento: str | None = None

    def como_dict(self) -> dict[str, Any]:
        return {"version": self.version, "estado": self.estado, "razon": self.razon, "ahora": self.ahora,
                "reglamento": self.reglamento, "compuertas": [c.como_dict() for c in self.compuertas]}

    def riesgo(self) -> list[Compuerta]:
        """Las reglas de riesgo que FALLAN (A5 sin stop, A6 perdida, A7 liquidacion): piden alerta aparte."""
        return [c for c in self.compuertas if c.nombre in RIESGO and c.severidad == FALLA]


def _limpio(x: Any) -> Any:
    """Lo que va al jsonb: floats finitos y redondeados, nada que no sea JSON."""
    if isinstance(x, bool) or x is None or isinstance(x, (int, str)):
        return x
    if isinstance(x, float):
        return round(x, 6) if math.isfinite(x) else None
    if isinstance(x, dict):
        return {str(k): _limpio(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_limpio(v) for v in x]
    return str(x)


def resuelve(compuertas: list[Compuerta]) -> tuple[str, str]:
    """El estado es la peor severidad; la razon principal, la primera compuerta con esa severidad. Sin compuertas o
    con una severidad desconocida: NO EVALUABLE."""
    if not compuertas:
        return ESTADOS[3], "sin compuertas: no hay dictamen"
    peor, razon = 0, None
    for c in compuertas:
        r = RANGO.get(c.severidad)
        texto = f"{c.nombre}: {c.razon}" if r is not None else f"{c.nombre}: severidad desconocida {c.severidad!r}"
        r = 3 if r is None else r
        if r > peor:
            peor, razon = r, texto
    return ESTADOS[peor], razon or f"las {len(compuertas)} compuertas pasan"


def umbral(u: dict[str, Any], clave: str) -> Any:
    if u.get(clave) is None:
        raise UmbralFaltante(clave)
    return u[clave]


def _dato(d: Any, ruta: str) -> Any:
    """d['a']['b'] por 'raiz.a.b' (el primer tramo es el nombre); falta o None -> DatoFaltante con la ruta."""
    x = d
    for paso in ruta.split(".")[1:]:
        if not isinstance(x, dict) or x.get(paso) is None:
            raise DatoFaltante(ruta)
        x = x[paso]
    return x


def _num(x: Any, ruta: str) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise DatoFaltante(f"{ruta} (no es un numero: {x!r})")
    return float(x)


def _instante(x: Any, ruta: str) -> datetime:
    if isinstance(x, datetime):
        t = x
    elif isinstance(x, str):
        try:
            t = datetime.fromisoformat(x.replace("Z", "+00:00"))
        except ValueError:
            raise DatoFaltante(f"{ruta} (no es un instante: {x!r})") from None
    else:
        raise DatoFaltante(f"{ruta} (no es un instante: {x!r})")
    if t.tzinfo is None:
        raise DatoFaltante(f"{ruta} (sin zona horaria)")
    return t


@dataclass
class _Caso:
    posicion: dict[str, Any]
    dec: dict[str, Any]
    sobre: dict[str, Any]
    opus: Any
    decide: Any
    ahora: Any
    u: dict[str, Any]

    def reloj(self) -> datetime:
        if not isinstance(self.ahora, datetime) or self.ahora.tzinfo is None:
            raise DatoFaltante("ahora (instante con zona)")
        return self.ahora

    def lado(self) -> int:
        lado = _dato(self.posicion, "posicion.lado")
        if lado not in (1, -1):
            raise DatoFaltante(f"posicion.lado (vale {lado!r}, se espera 1 o -1)")
        return lado

    def stop(self) -> float | None:
        """None si la posicion no lleva stop; DatoFaltante si la lectura ni siquiera trae la clave."""
        if "stop" not in self.posicion:
            raise DatoFaltante("posicion.stop (la lectura no trae la clave)")
        s = self.posicion["stop"]
        return None if s is None or s == 0 else _num(s, "posicion.stop")


def a1_opus(c: _Caso) -> Compuerta:
    if c.opus is None:
        return Compuerta("A1", NO_EVALUABLE, "Opus sin veredicto legible")
    if c.opus not in VEREDICTOS:
        return Compuerta("A1", NO_EVALUABLE, f"veredicto de Opus no reconocido: {c.opus!r}")
    return Compuerta("A1", OK, f"Opus dice {c.opus}", valor=c.opus)


def a2_frescura(c: _Caso) -> Compuerta:
    ahora, u = c.reloj(), c.u
    rt = umbral(u, "REALTIME_STALE_SECONDS")
    edades = {
        "DECIDE servido": ((ahora - _instante(_dato(c.dec, "dec.generated_at"), "dec.generated_at")).total_seconds(), rt),
        "DECIDE instantanea": (_num(_dato(c.dec, "dec.age.snapshot_lag_seconds.value"),
                                    "dec.age.snapshot_lag_seconds.value"), umbral(u, "MESA_DECIDE_MAX_AGE_S")),
        "sobre": ((ahora - _instante(_dato(c.sobre, "sobre.generated_at"), "sobre.generated_at")).total_seconds(), rt),
        "posicion": (ahora.timestamp() - _num(_dato(c.posicion, "posicion.visto"), "posicion.visto") / 1000, rt),
        "libro bybit": ((ahora - _instante(_dato(c.sobre, "sobre.orderbook.bybit.ts"),
                                           "sobre.orderbook.bybit.ts")).total_seconds(), umbral(u, "libro_edad_max_s")),
    }
    valor = {k: e for k, (e, _) in edades.items()}
    topes = {k: t for k, (_, t) in edades.items()}
    for k, (e, tope) in edades.items():
        if e < 0:
            return Compuerta("A2", NO_EVALUABLE, f"{k} viene del futuro ({e:.1f} s): reloj incoherente", valor, topes)
        if e > tope:
            return Compuerta("A2", NO_EVALUABLE, f"{k} tiene {e:.1f} s (tope {tope:g} s)", valor, topes)
    return Compuerta("A2", OK, "todo dentro de su tope de edad", valor, topes)


def a3_decide(c: _Caso) -> Compuerta:
    if c.decide in CON_LADO:
        return Compuerta("A3", OK, f"DECIDE dice {c.decide}", valor=c.decide)
    if c.decide == "NO EVALUABLE":
        return Compuerta("A3", AVISO, "Opus opina sin una lectura evaluable de DECIDE", valor=c.decide)
    return Compuerta("A3", NO_EVALUABLE, f"veredicto de DECIDE no reconocido: {c.decide!r}")


def a4_acuerdo(c: _Caso) -> Compuerta:
    if c.opus not in CON_LADO or c.decide not in CON_LADO:
        return Compuerta("A4", NO_APLICABLE, f"no hay dos lados que comparar (Opus {c.opus}, DECIDE {c.decide})")
    if c.opus == c.decide:
        return Compuerta("A4", OK, f"Opus y DECIDE coinciden: {c.opus}", valor=c.opus)
    return Compuerta("A4", AVISO, f"Opus dice {c.opus} y DECIDE dice {c.decide}", valor=[c.opus, c.decide])


def a5_stop(c: _Caso) -> Compuerta:
    s = c.stop()
    if s is None:
        return Compuerta("A5", FALLA, "la posicion no tiene stop")
    return Compuerta("A5", OK, f"stop en {s:g}", valor=s)


def a6_perdida(c: _Caso) -> Compuerta:
    s = c.stop()
    if s is None:
        return Compuerta("A6", NO_APLICABLE, "sin stop no hay perdida al stop (lo juzga A5)")
    tope = umbral(c.u, "PERDIDA_MAX")
    cantidad = abs(_num(_dato(c.posicion, "posicion.cantidad"), "posicion.cantidad"))
    entrada = _num(_dato(c.posicion, "posicion.entrada"), "posicion.entrada")
    perdida = calc.perdida_al_stop(cantidad, entrada, s, c.lado())
    if round(perdida, 6) > tope:
        return Compuerta("A6", FALLA, f"pierde {perdida:.2f} USD al stop con comision (tope {tope:g})", perdida, tope)
    return Compuerta("A6", OK, f"pierde {perdida:.2f} USD al stop con comision", perdida, tope)


def a7_liquidacion(c: _Caso) -> Compuerta:
    s = c.stop()
    if s is None:
        return Compuerta("A7", NO_APLICABLE, "sin stop no hay distancia al stop (lo juzga A5)")
    veces = umbral(c.u, "LIQ_VECES")
    if "liquidacion" not in c.posicion:
        raise DatoFaltante("posicion.liquidacion (la lectura no trae la clave)")
    liq = c.posicion["liquidacion"]
    if liq is None or liq == 0:
        return Compuerta("A7", AVISO, "liquidacion desconocida: no se puede medir el colchon", umbral=veces)
    liq, lado = _num(liq, "posicion.liquidacion"), c.lado()
    entrada = _num(_dato(c.posicion, "posicion.entrada"), "posicion.entrada")
    dist_stop, dist_liq = abs(entrada - s), (entrada - liq) * lado  # las de calc.calcula, desde la entrada
    if (s - liq) * lado <= 0:
        return Compuerta("A7", FALLA, f"la liquidacion ({liq:g}) queda ANTES del stop ({s:g})", liq, veces)
    ratio = dist_liq / dist_stop if dist_stop else None
    if dist_liq < veces * dist_stop:
        return Compuerta("A7", FALLA, f"la liquidacion queda a {ratio:.2f} veces la distancia al stop (menos de"
                                      f" {veces:g})", ratio, veces)
    return Compuerta("A7", OK, "liquidacion mas alla del stop" + (f" ({ratio:.2f} veces)" if ratio else ""),
                     ratio, veces)


def a8_costes(c: _Caso) -> Compuerta:
    s, objetivo = c.stop(), c.posicion.get("objetivo") or None
    if s is None and objetivo is None:
        return Compuerta("A8", NO_APLICABLE, "sin stop ni objetivo no hay banda de coste que medir")
    u = c.u
    comision, patas = umbral(u, "comision_bps_lado"), umbral(u, "coste_pata")
    b_obj, b_riesgo = umbral(u, "banda_coste_objetivo_max"), umbral(u, "banda_coste_riesgo_max")
    lado = c.lado()
    entrada = _num(_dato(c.posicion, "posicion.entrada"), "posicion.entrada")
    valor_usd = abs(_num(_dato(c.posicion, "posicion.cantidad"), "posicion.cantidad")) * entrada
    spread = _num(_dato(c.sobre, "sobre.orderbook.bybit.spread_bps"), "sobre.orderbook.bybit.spread_bps")
    ask = _num(_dato(c.sobre, "sobre.orderbook.bybit.ask_notional_l1"), "sobre.orderbook.bybit.ask_notional_l1")
    bid = _num(_dato(c.sobre, "sobre.orderbook.bybit.bid_notional_l1"), "sobre.orderbook.bybit.bid_notional_l1")
    entra, sale = (ask, bid) if lado > 0 else (bid, ask)

    def pata(tipo: str, l1: float | None) -> float:
        """La de motor._pata: suma de componentes en bps; el deslizamiento es 0 si el L1 cubre el tamano."""
        total = 0.0
        for comp in patas[tipo]:
            if comp in comision:
                total += float(comision[comp])
            elif comp == "spread":
                total += spread
            elif comp == "deslizamiento":
                if l1 is None or valor_usd > l1:
                    raise DatoFaltante(f"deslizamiento: el L1 de bybit ({l1}) no cubre {valor_usd:.0f} USD")
            else:
                raise UmbralFaltante(f"coste_pata.{tipo}: componente desconocido {comp!r}")
        return total

    c_ent = pata("mercado", entra)  # la entrada ya hecha se cuenta a mercado (taker): la cota pesimista
    valor: dict[str, Any] = {}
    avisos, notas = [], []
    if objetivo is not None:
        d_obj = (_num(objetivo, "posicion.objetivo") - entrada) * lado / abs(entrada) * BPS
        if d_obj <= 0:
            notas.append("objetivo del lado del stop: banda de objetivo no aplica")
        else:
            valor["coste_objetivo"] = q = (c_ent + pata("limite", None)) / d_obj
            if q > b_obj:
                avisos.append(f"el coste se come {q:.0%} del recorrido al objetivo (tope {b_obj:.0%})")
    else:
        notas.append("sin objetivo: banda de objetivo no aplica")
    if s is not None:
        d_stop = (entrada - s) * lado / abs(entrada) * BPS
        if d_stop <= 0:
            notas.append("stop en ganancia: banda de riesgo no aplica")
        else:
            valor["coste_riesgo"] = q = (c_ent + pata("stop", sale)) / d_stop
            if q > b_riesgo:
                avisos.append(f"el coste es {q:.0%} del riesgo al stop (tope {b_riesgo:.0%})")
    topes = {"coste_objetivo": b_obj, "coste_riesgo": b_riesgo}
    if avisos:
        return Compuerta("A8", AVISO, "; ".join(avisos), valor, topes)
    return Compuerta("A8", OK, "; ".join(["costes dentro de banda"] + notas), valor, topes)


def a9_calendario(c: _Caso) -> Compuerta:
    ahora = c.reloj()
    imp_min, ventana = umbral(c.u, "importancia_minima"), umbral(c.u, "ventana_min_intradia")
    eventos = _dato(c.sobre, "sobre.external_macro_context.event_risk.upcoming")
    if not isinstance(eventos, list):
        raise DatoFaltante(f"sobre.external_macro_context.event_risk.upcoming (no es una lista: {eventos!r})")
    limite, cubierto = ahora + timedelta(minutes=ventana), False
    for i, ev in enumerate(eventos):
        t = _instante(_dato(ev, "ev.event_at"), f"upcoming[{i}].event_at")
        if t > limite:
            cubierto = True
        elif _num(_dato(ev, "ev.importance"), f"upcoming[{i}].importance") >= imp_min:
            minutos = (t - ahora).total_seconds() / 60
            return Compuerta("A9", AVISO, f"evento de importancia {ev['importance']} en {minutos:.0f} min:"
                                          f" {str(ev.get('title') or '?')[:60]}", minutos, [imp_min, ventana])
    if not cubierto:
        return Compuerta("A9", NO_EVALUABLE, f"calendario sin cubrir: ningun evento mas alla de {ventana:g} min",
                         umbral=[imp_min, ventana])
    return Compuerta("A9", OK, f"sin eventos de importancia >= {imp_min} en {ventana:g} min",
                     umbral=[imp_min, ventana])


PUERTAS: tuple[tuple[str, Callable[[_Caso], Compuerta]], ...] = (
    ("A1", a1_opus), ("A2", a2_frescura), ("A3", a3_decide), ("A4", a4_acuerdo), ("A5", a5_stop),
    ("A6", a6_perdida), ("A7", a7_liquidacion), ("A8", a8_costes), ("A9", a9_calendario),
)


def _corre(nombre: str, fn: Callable[[_Caso], Compuerta], caso: _Caso) -> Compuerta:
    try:
        return fn(caso)
    except UmbralFaltante as e:
        return Compuerta(nombre, NO_EVALUABLE, f"umbral faltante: {e.args[0] if e.args else '?'}")
    except DatoFaltante as e:
        return Compuerta(nombre, NO_EVALUABLE, f"falta el dato: {e.args[0] if e.args else '?'}")
    except Exception as e:  # noqa: BLE001 - una compuerta que revienta no aprueba
        return Compuerta(nombre, NO_EVALUABLE, f"error: {type(e).__name__}: {str(e)[:160]}")


def audita(posicion: Any, dec: Any, sobre: Any, veredicto_opus: Any, veredicto_decide: Any, ahora: Any,
           umbrales: dict[str, Any] | None = None) -> Dictamen:
    """posicion: la de bybit.posiciones con `visto` (ms). dec: /api/mesa/decide. sobre: /api/ai/context entero.
    veredicto_opus: el de lee_veredicto (None si no hay). veredicto_decide: el de veredicto_decide. ahora: el
    instante del dictamen, con zona (el servicio pasa el de justo despues de leer sobre y DECIDE)."""
    try:
        u = UMBRALES if umbrales is None else umbrales
        caso = _Caso(*(x if isinstance(x, dict) else {} for x in (posicion, dec, sobre)),
                     veredicto_opus, veredicto_decide, ahora, u)
        compuertas = [_corre(n, fn, caso) for n, fn in PUERTAS]
        estado, razon = resuelve(compuertas)
        cuando = ahora.astimezone(UTC).isoformat() if isinstance(ahora, datetime) and ahora.tzinfo else None
        return Dictamen(estado, razon, compuertas, cuando, reglamento=u.get("reglamento"))
    except Exception as e:  # noqa: BLE001
        return Dictamen(ESTADOS[3], f"error: {type(e).__name__}: {str(e)[:160]}")


def linea(dictamen: Any, error: str | None = None) -> str:
    """La primera linea del mensaje. No puede fallar: lo que no sea un Dictamen sale como NO EVALUABLE."""
    try:
        if error is not None or not isinstance(dictamen, Dictamen):
            return f"AUDITOR: NO EVALUABLE (error: {str(error or 'sin dictamen')[:200]})"
        return f"AUDITOR: {dictamen.estado} · {dictamen.razon}"
    except Exception:  # noqa: BLE001
        return "AUDITOR: NO EVALUABLE (error: la linea no se pudo escribir)"
