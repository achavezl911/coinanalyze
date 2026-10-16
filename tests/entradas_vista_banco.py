"""Banco de la vista ENTRADAS (campana 137): un registro SINTETICO con la forma de ruta.construir(foto=True)
y la respuesta que vista.componer saca de el. Sin base. Lo usan tests/test_entradas_vista.py y, por
la linea de ordenes, tests/js/mesa_entradas.test.js (asi el test de la pantalla pinta lo que el
backend compone de verdad, no una copia escrita a mano de su forma).

    python tests/entradas_vista_banco.py [PALABRA] [SEGUNDOS_HASTA_CADUCAR] [EDAD_DEL_LATIDO_S]
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.entradas import papel as PAPEL  # noqa: E402
from app.entradas import reglamento as R  # noqa: E402
from app.entradas import resolutor as RES  # noqa: E402
from app.entradas import ruta as RUTA  # noqa: E402
from app.entradas import vista as V  # noqa: E402

AS_OF = datetime(2026, 10, 13, 12, 0, 1, tzinfo=UTC)
PLAN = {
    "entrada": {"tipo": "mercado", "regla": "apertura del minuto siguiente al registro",
                "referencia": {"precio": 100.5, "ts": "2026-10-13T11:44:59Z", "fuente": "libro de binance en T"}},
    "stop": {"precio": 99.0, "tipo_disparo": "stop a mercado"},
    "objetivos": [103.0, 104.5],
    "distancias_bps": {"stop": 150.0, "t1": 250.0},
    "invalidacion": {"nivel": 100.0, "hasta": "2026-10-13T15:45:00Z", "regla": "cierre al otro lado", "reloj": "UTC"},
    "caducidad": {"minutos": 240},
    "r": {"neto": 1.6, "bruto": 1.7},
    "p_equilibrio": 0.4,
    "costes": {"entrada": {"total_bps": 6.0, "venue": "bybit", "tipo": "mercado"},
               "objetivo": {"total_bps": 2.0, "venue": "bybit", "tipo": "limite"},
               "stop": {"total_bps": 6.0, "venue": "bybit", "tipo": "stop"}},
    "cocientes": {"coste_objetivo": 0.032},
}


def fila(i: int, vela: datetime, estado: str = "SOMBRA", *, version: str = "v2", lado: str = "largo",
         perfil: str = "intradia", zona: tuple[float, float] = (100.0, 101.0), caduca: datetime | None = None,
         filtros: dict | None = None) -> dict[str, Any]:
    foto: dict[str, Any] = {"zona": {"low": zona[0], "high": zona[1]}, "filtros": filtros or {}, "decision": {}}
    if estado == "DISPARADO":
        foto["plan"] = PLAN
        foto["filtros"] = {n: {"estado": "cumple", "motivo": None} for n in ("objetivo", "spot_vela")}
    return {"registro_id": i, "registered_at": vela.isoformat(), "vela_cierre": vela.isoformat(),
            "version": version, "familia": "F1", "perfil": perfil, "lado": lado, "estado": estado,
            "symbol": "BTCUSDT_PERP.A", "caduca_en": caduca.isoformat() if caduca else None, "foto": foto}


def resultado(vela: datetime, caduca: datetime) -> dict[str, Any]:
    """El resultado que la ruta sirve (E3) para el DISPARADO del banco: ABIERTO mientras su reloj corre y nada
    lo ha tocado; CADUCADO, provisional, cuando caduca. Con la forma de app/entradas/resolutor.py."""
    entrada = {"instante": RES.iso(vela + timedelta(minutes=3)), "precio": 100.51, "tipo": "mercado",
               "apertura": 100.5, "banda_bps": 1.0, "comision_bps": 5.5}
    base = {"registro_id": 7, "version": "v2", "resolutor": RES.RESOLUTOR_VERSION,
            "huella_convenciones": RES.HUELLA_CONVENCIONES, "hipotetico": False, "entrada": entrada,
            "a_favor": None, "funding": [], "t2": None, "t3": None}
    if caduca > AS_OF:
        return {**base, "estado": RES.ABIERTO, "salida": None, "firmeza": RES.PROVISIONAL, "asentado_en": None,
                "instante": None, "precio": None, "pnl": None, "excursion": None,
                "sabido_hasta": RES.iso(AS_OF.replace(second=0)),
                "motivo": "sin tocar stop, T1 ni invalidacion hasta la vela de 1 min de las 12:00Z"}
    return {**base, "estado": RES.ACABADO, "salida": RES.CADUCADO, "firmeza": RES.PROVISIONAL,
            "asentado_en": RES.iso(caduca + timedelta(minutes=43)), "instante": RES.iso(caduca), "precio": 100.89,
            "pnl": {"bps_brutos": 37.8, "bps_netos": 26.8, "r_neto": 0.165, "comision_bps": {"entrada": 5.5, "salida": 5.5}},
            "excursion": {"favor_bps": 80.0, "contra_bps": 40.0}, "sabido_hasta": None, "motivo": None,
            "t2": {"precio": 104.5, "cruzado": False, "instante": None}}


def registro(*, caduca_en_s: float = 3600.0, latido_hace_s: float | None = 100.0,
             latido_vela_h: int = 11) -> dict[str, Any]:
    """Un DISPARADO de v2 (vivo si caduca_en_s > 0), un VIGILANDO de v2 y otro de v1 sobre la MISMA
    zona, y tres SOMBRAS de v2 (dos a la misma hora) mas una de v1."""
    hora = lambda h: AS_OF.replace(hour=h, minute=0, second=0)  # noqa: E731
    caduca = AS_OF + timedelta(seconds=caduca_en_s)
    disparado = {**fila(7, hora(8), "DISPARADO", caduca=caduca), "resultado": resultado(hora(8), caduca)}
    doc = R.cargar_valido()
    falla = {"r_neto_t1": {"estado": "falla", "motivo": None},
             "spot_hora": {"estado": "no_evaluable", "motivo": "hueco de spot: 58 de 60 minutos con las 2 venues"}}
    return {
        "as_of": AS_OF.isoformat(), "disponible": True, "faltan": RUTA.FALTAN,
        "parametros": {"desde": (AS_OF - timedelta(hours=24)).isoformat(), "hasta": AS_OF.isoformat()},
        "generador": {"ultimos_latidos": [] if latido_hace_s is None else [
            {"registered_at": (AS_OF - timedelta(seconds=latido_hace_s)).isoformat(),
             "vela_cierre": hora(latido_vela_h).isoformat(), "estado": "ok", "duracion_s": 2.0, "error": None,
             "motivo": None}],
            "motivo": "el generador aun no ha corrido en esta base" if latido_hace_s is None else None},
        "reglamento": {"disponible": True, "version_activa": "v2", "ancla": "v1", "versiones_en_curso": ["v1", "v2"],
                       "hipotesis_activa": {"celdas": "c", "sentido": "s", "lectura": "l"},
                       "calendario_vigente": {"revision": "cal-banco", "vigente_desde": "2026-10-10T00:00:00Z",
                                              "cubre_hasta": "2026-11-30T23:59:59Z", "eventos": 20,
                                              "dias_que_le_quedan": 48.5, "motivo": None}},
        "cuentas": [{"familia": "F1", "perfil": "intradia", "lado": "largo", "version": "v2", "VIGILANDO": 3,
                     "DISPARADO": 1, "SOMBRA": 3, "CERRADO_SIN_DISPARO": 0, "resueltos": 0, "sin_entrada": 0,
                     "no_evaluables": 0, "resueltos_motivo": RUTA.RESUELTOS_QUE_ES}],
        "resultados": {"que_es": RUTA.RESULTADOS_QUE_ES, "resolutor": RES.RESOLUTOR_VERSION,
                       "huella_convenciones": RES.HUELLA_CONVENCIONES, "convenciones": RES.CONVENCIONES,
                       "cambios_e3": RES.CAMBIOS_E3, "barrido_emparejado": {"que_es": RUTA.BARRIDO_QUE_ES, "planes": []}},
        "papel": {v["version"]: PAPEL.cuenta(v, [disparado] if v["version"] == "v2" else [], {7: disparado["resultado"]})
                  for v in R.versiones_en_curso(doc)},
        "por_lado": {
            "largo": {"vivos": {"vigilando": [fila(11, hora(11), "VIGILANDO"),
                                              fila(10, hora(11), "VIGILANDO", version="v1")],
                                "disparados": [disparado] if caduca_en_s > 0 else []},
                      "ventana": {"disparados": [disparado],
                                  "sombras": [fila(1, hora(10), filtros=falla), fila(3, hora(11), filtros=falla),
                                              fila(2, hora(11), filtros=falla),
                                              fila(4, hora(11), version="v1", filtros=falla)]}},
            "corto": {"vivos": {"vigilando": [], "disparados": []}, "ventana": {"disparados": [], "sombras": []}},
        },
    }


def decide(scalp: str | None, edad: float = 10.0) -> dict[str, Any] | None:
    """Lo que build_mesa_decide(frame="swing") sirve, reducido a lo que la vista lee."""
    if scalp is None:
        return None
    return {"max_age_s": 120.0, "age": {"snapshot_lag_seconds": {"value": edad, "status": "ok"}},
            "decide": {"bias": {"value": "NO EVALUABLE", "source_key": "mesa.decide.frame",
                                "motivo": "la lectura del operador es del SCALP, no de SWING"}},
            # mesa.decide.v3 (campana 138): la palabra del scalp es la que el sistema SOSTIENE, con su edad
            "lectura_scalp": {"bias": {"value": scalp, "source_key": "mesa.decide.memoria",
                                       "motivo": "data_confidence 12 < 70" if scalp == "NO EVALUABLE" else None},
                              "memoria": {"edad": {"desde": (AS_OF - timedelta(seconds=1043)).isoformat(),
                                                   "frase": f"desde las "
                                                   f"{(AS_OF - timedelta(seconds=1043)):%H:%M:%S}Z (17 min)"}}}}


def respuesta(scalp: str | None = "LONG", **kw: Any) -> dict[str, Any]:
    precio = {"valor": 102.0, "instante": (AS_OF - timedelta(seconds=1)).isoformat(),
              "fuente": V.PRECIO_FUENTE, "motivo": None}
    return V.componer(registro(**kw), symbol="BTCUSDT_PERP.A", activo="BTC", precio=precio, decide=decide(scalp),
                      decide_error=None if scalp else "DECIDE no contesta", doc=R.cargar_valido())


if __name__ == "__main__":
    a = sys.argv[1:]
    palabra = None if (a and a[0] == "SIN") else (a[0] if a else "LONG")
    print(json.dumps(respuesta(palabra, caduca_en_s=float(a[1]) if len(a) > 1 else 3600.0,
                               latido_hace_s=float(a[2]) if len(a) > 2 else 100.0), ensure_ascii=False))
