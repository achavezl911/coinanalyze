"""ESTRUCTURA R1: los avisos deterministas del bridge de Telegram (coinalyze-ai-bridge en 140, fuera del repo), en el bot.

El bridge, en SEND_MODE=alert_only, manda cada ANALYSIS_INTERVAL_SECONDS «ESTRUCTURA / LIQUIDACIONES (<ts>)» con tres
clases de linea (su analyzer.py del 11-26, copia en x1-tmp/ref-bridge):
  giro de estructura    structure_horizons.<h>.bias pasa de alcista a bajista o al reves (solo patrones decisivos)
  liquidaciones masivas liq_burst.total >= max(LIQ_BURST_FLOOR_USD, LIQ_BURST_MULT x baseline_5m), una por activo
                        cada MIN_SEND_INTERVAL_SECONDS
  flujo pasivo          passive_flow.horizons.<1h|4h|8h>.reading pasa a reacumulacion/redistribucion silenciosa con
                        confianza alta o media
de /api/ai/context/bundle (o /api/ai/context con un solo simbolo), perfil default. Aqui va lo MISMO, con los mismos
nombres de variable, los mismos valores por defecto y el mismo texto, byte a byte (tests/test_bot_estructura.py lo
compara con el bridge), salvo el pie (PIE, ESTRUCTURA R3) y las palabras de AVISOS R1 (H3, abajo). La anti-repeticion es la suya: la estructura se apunta solo cuando no hay aviso o cuando el aviso
se entrego; el flujo pasivo se apunta al calcular; la rafaga de liquidaciones, cuando se entrego.

Lo que NO se trae: la divergencia CVD (detect_cvd_divergence_alerts) y build_alert_text. En alert_only el bridge la
calcula y la mete en local_alerts, pero el mensaje que manda (build_structural_alert) no la lee: nunca llego al dueno.

AVISOS R1 (Fable v6, H3; Fable I18: ninguna senal da direccion): las palabras del bridge que anunciaban adonde va el
precio (giro ALCISTA/BAJISTA con flechas, cascada BAJISTA, squeeze ALCISTA, REACUMULACION/REDISTRIBUCION) y el icono de la
cabecera se cambian por el hecho medido. La decision de enviar y la anti-repeticion no cambian: la prueba de equivalencia
compara el texto con el dorado del bridge mas su tabla de sustituciones (tests/test_bot_estructura.py, SUSTITUCIONES).

Funciones puras: el estado es un dict serializable {"kv", "t", "avisos"} que el bot guarda en bot_estado.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

MODOS = ("apagado", "sombra", "enviar")
SIMBOLOS = ["BTCUSDT_PERP.A", "ETHUSDT_PERP.A", "SOLUSDT_PERP.A"]  # config.py:148 del bridge
# ESTRUCTURA R3: el pie del bridge remitia a dos ordenes suyas que el bot no tiene. El bot contesta preguntas libres
# (AYUDA, servicio.py): el detalle se le pide asi. Es lo unico en que el texto difiere del bridge.
PIE = "Detalle: preguntame por el activo (por ejemplo, como esta BTC)."

_DECISIVO = {"alcista", "bajista"}
# el hecho detras de cada valor del sobre: bias alcista/bajista = patron HH_HL/LH_LL (app/setups.py:1265); la lectura del
# flujo pasivo = ventas/compras agresivas absorbidas con el CVD de contado opuesto (app/scalp_logic.py, _classify_passive)
_GIRO = {"alcista": "pasa a maximos y minimos mas altos", "bajista": "pasa a maximos y minimos mas bajos"}
_PASIVO = {"reacumulacion_silenciosa": "ventas agresivas absorbidas y contado comprando",
           "redistribucion_silenciosa": "compras agresivas absorbidas y contado vendiendo"}


@dataclass
class Umbrales:
    modo: str = "sombra"
    simbolos: list = field(default_factory=lambda: list(SIMBOLOS))
    bps: int = 10
    piso: float = 2_000_000.0
    mult: float = 4.0
    enfriamiento: float = 240.0
    intervalo: float = 300.0

    @classmethod
    def desde(cls, e: dict) -> tuple[Umbrales, list[str]]:
        """Las variables del bridge (config.py:195-206), que llegan por el mismo EnvironmentFile; un valor que no se
        entiende se queda en el de serie y se dice."""
        u, avisos = cls(), []
        modo = (e.get("BOT_ESTRUCTURA") or "sombra").strip().lower()
        if modo not in MODOS:
            avisos.append(f"BOT_ESTRUCTURA={modo[:20]!r} no es apagado|sombra|enviar: va en sombra")
            modo = "sombra"
        u.modo = modo
        raw = (e.get("SYMBOLS") or "").strip()
        if raw:
            try:  # config.py:46 _list_env: JSON o separado por comas
                v = json.loads(raw) if raw.startswith("[") else raw.split(",")
                u.simbolos = [str(x).strip() for x in v if str(x).strip()] or u.simbolos
            except ValueError:
                avisos.append("SYMBOLS no se entiende: van los de serie")
        for nombre, atr, tipo in (("LIQUIDATION_BUCKET_BPS", "bps", int), ("LIQ_BURST_FLOOR_USD", "piso", float),
                                  ("LIQ_BURST_MULT", "mult", float), ("MIN_SEND_INTERVAL_SECONDS", "enfriamiento", float),
                                  ("ANALYSIS_INTERVAL_SECONDS", "intervalo", float)):
            if e.get(nombre) not in (None, ""):
                try:
                    setattr(u, atr, tipo(e[nombre]))
                except ValueError:
                    avisos.append(f"{nombre} no es un numero: va {getattr(u, atr)}")
        u.intervalo = max(u.intervalo, 60.0)
        return u, avisos


def ruta(u: Umbrales) -> str:
    """analyzer.py:577-599: con un simbolo, su contexto; con varios, el bundle. Perfil default (scheduler.py:151)."""
    if len(u.simbolos) == 1:
        return f"/api/ai/context?symbol={u.simbolos[0]}&profile=default&bucket_bps={u.bps}"
    return f"/api/ai/context/bundle?symbols={','.join(u.simbolos)}&profile=default&bucket_bps={u.bps}"


def paquete(carga: dict, u: Umbrales) -> tuple[str, list[dict]]:
    """(generated_at, filas) como las arma collect_payload: con un simbolo la hora es la de la lectura, no la del sobre."""
    if len(u.simbolos) == 1:
        return datetime.now(UTC).isoformat(), [carga]
    filas = carga.get("symbols") if isinstance(carga, dict) else None
    if not isinstance(filas, list):
        raise LookupError("el bundle no trae symbols")
    return str(carga.get("generated_at") or datetime.now(UTC).isoformat()), [x for x in filas if isinstance(x, dict)]


def nuevo() -> dict:
    return {"kv": {}, "t": {}, "avisos": []}


def _px(v: Any) -> str:
    try:
        return f"{float(v):,.2f}"
    except (TypeError, ValueError):
        return "—"


def _usd(v: float) -> str:
    a = abs(v)
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if a >= div:
            return f"${v / div:.1f}{suf}"
    return f"${v:.0f}"


def _sym(item: dict) -> str:
    return str(item.get("symbol") or item.get("asset") or "")


def estructuras(filas: list[dict]) -> list[dict]:
    out = []
    for item in filas:
        hz = item.get("structure_horizons")
        if not isinstance(hz, dict):
            continue
        for h, x in hz.items():
            if isinstance(x, dict) and x.get("bias") in _DECISIVO:
                out.append({"symbol": _sym(item), "horizon": h, "group": x.get("group"), "bias": x.get("bias"),
                            "structure": x.get("structure"), "close": x.get("close")})
    return out


def rafagas(filas: list[dict], u: Umbrales) -> list[dict]:
    out = []
    for item in filas:
        lb = item.get("liq_burst")
        if not isinstance(lb, dict):
            continue
        total, base = float(lb.get("total") or 0.0), float(lb.get("baseline_5m") or 0.0)
        if total <= 0 or total < max(u.piso, u.mult * base):
            continue
        lado = "sobre todo de largos" if float(lb.get("long_liq") or 0.0) >= float(lb.get("short_liq") or 0.0) \
            else "sobre todo de cortos"
        out.append({"symbol": _sym(item), "total": total, "side": lado,
                    "mult_txt": f" · {total / base:.1f}x baseline" if base > 0 else ""})
    return out


def pasivos(filas: list[dict]) -> list[dict]:
    out = []
    for item in filas:
        pf = item.get("passive_flow")
        if not isinstance(pf, dict):
            continue
        for h, x in (pf.get("horizons") or {}).items():
            if h not in ("1h", "4h", "8h") or not isinstance(x, dict):
                continue
            r = x.get("reading")
            decisivo = r in _PASIVO and x.get("confidence") in ("alta", "media")
            out.append({"symbol": _sym(item), "horizon": h, "location": pf.get("location"), "confidence": x.get("confidence"),
                        "state": r if decisivo else "neutral", "label": _PASIVO.get(r)})
    return out


def construye(generado: str, filas: list[dict], est: dict, u: Umbrales, ahora: float) -> str | None:
    """build_structural_alert (analyzer.py:401): el texto, o None. Apunta YA el flujo pasivo, como el bridge."""
    kv, t, lineas = est["kv"], est["t"], []
    for s in estructuras(filas):
        antes = kv.get(f"struct:{s['symbol']}:{s['horizon']}")
        if antes and antes != s["bias"]:
            grupo = "medio" if s["group"] == "med" else "largo"
            lineas.append(f"- {s['symbol']} · estructura {s['horizon']} ({grupo}): "
                          f"{_GIRO[s['bias']]} (patron {s['structure']}, cierre {_px(s['close'])})")
    for r in rafagas(filas, u):
        if ahora - (t.get(f"liqburst:{r['symbol']}", 0.0) or 0.0) >= u.enfriamiento:
            lineas.append(f"- {r['symbol']} · liquidaciones masivas 5m: {_usd(r['total'])}, {r['side']}{r['mult_txt']}")
    for p in pasivos(filas):
        k = f"passive:{p['symbol']}:{p['horizon']}"
        antes, ahora_es = kv.get(k), p["state"]
        if antes and antes != ahora_es and ahora_es != "neutral":
            lineas.append(f"- {p['symbol']} · flujo pasivo {p['horizon']}: {p['label']} (precio en {p['location']}, {p['confidence']})")
        if antes != ahora_es:
            kv[k] = str(ahora_es)
    if not lineas:
        return None
    return "\n".join([f"ESTRUCTURA / LIQUIDACIONES ({generado})", "", *lineas, "", PIE])


def registra(filas: list[dict], est: dict) -> None:
    """record_structural_state (analyzer.py:437): la estructura de ahora es la base del siguiente giro."""
    for s in estructuras(filas):
        est["kv"][f"struct:{s['symbol']}:{s['horizon']}"] = str(s["bias"])


def marca(filas: list[dict], est: dict, u: Umbrales, ahora: float) -> None:
    """mark_structural_alert_sent (analyzer.py:443): solo despues de entregar el aviso."""
    registra(filas, est)
    for r in rafagas(filas, u):
        k = f"liqburst:{r['symbol']}"
        if ahora - (est["t"].get(k, 0.0) or 0.0) >= u.enfriamiento:
            est["t"][k] = float(ahora)


def restaura(guardado: Any) -> dict | None:
    """El estado de bot_estado, si se entiende; si no, None (y se empieza de cero, como un bridge con state.db nuevo)."""
    if not isinstance(guardado, dict):
        return None
    kv, t, av = guardado.get("kv"), guardado.get("t"), guardado.get("avisos")
    if not (isinstance(kv, dict) and isinstance(t, dict)):
        return None
    return {"kv": {str(k): str(v) for k, v in kv.items()},
            "t": {str(k): float(v) for k, v in t.items() if isinstance(v, (int, float))},
            "avisos": [list(x) for x in av if isinstance(x, list) and len(x) == 2] if isinstance(av, list) else []}
