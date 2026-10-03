"""GET /api/entradas · lo que el registro de entradas sirve (campana 135, C4).

Sirve, con todos sus parametros por defecto: los VIGILANDO y DISPARADOS vivos y los de una ventana
pedida, por lado; las SOMBRAS con su vector de filtros; el reglamento vigente y su diferencia con
el padre; por familia, cuantas versiones e hipotesis van probadas y las retiradas antes de su
lectura; por (familia, perfil, lado, version), cuantos hay en cada estado y cuantos resueltos (0
hasta la E3); el estado del generador; y lo que falta, con su motivo.

LO QUE NO SIRVE: ninguna fraccion ni tasa de aciertos de los candidatos. «Probabilistico» sera una
FRECUENCIA MEDIDA (E4) sobre DISPARADOS resueltos, y hasta n efectiva 30 ningun porcentaje.
fracciones_servidas() es la red que lo vigila (tests/test_entradas_ruta.py).

LO QUE SI SIRVE como REFERENCIA FIJA, rotulada «ya medido» y citada de donde se midio: que la
ventaja direccional de la senal scalp no paga la comision (COLA 100/101/103/110 y su re-medida
fuera de muestra). No habla de estos candidatos: es el suelo contra el que se juzgaran.

No entra en el sobre (/api/ai/context): es una pantalla aparte (E2).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any

from app.entradas import motor as M
from app.entradas import reglamento as R

REFERENCIA_YA_MEDIDO = {
    "rotulo": "YA MEDIDO · sobre la senal scalp del sistema, NO sobre estos candidatos",
    "items": [
        {
            "que": "ventaja direccional de la senal scalp a 1 min sobre una moneda lanzada",
            "valor": "+3.48 pp (n = 112 282, error tipico 0.15)",
            "cita": "harness/COLA.md:10695 (COLA 101)",
        },
        {
            "que": "la misma ventaja fuera de muestra (12 dias que la conclusion no vio)",
            "valor": "+3.61 ± 0.26 pp (n = 37 221); retorno medio 0.67 bps contra una ida y vuelta "
            "de 4.013 (maker) a 11.013 bps (taker) en Bybit sin VIP",
            "cita": "harness/hechos.tsv:1707 (OPERADOR.VENTAJA.FUERA_DE_MUESTRA_0923)",
        },
        {
            "que": "con la comision dentro, ninguna de las diez celdas medidas queda en positivo",
            "valor": "la mejor da +2.11 bps brutos; harian falta < 1.05 bps por lado",
            "cita": "harness/COLA.md:11143-11145 (COLA 103)",
        },
        {
            "que": "el giro real long <-> short, la mejor medida del sistema",
            "valor": "+9.28 pp",
            "cita": "harness/COLA.md:12137 (COLA 110)",
        },
        {
            "que": "y aun asi no paga la comision maker",
            "valor": "le falta un factor 2.3: equilibrio 0.855 bps por lado contra 2.0 del maker",
            "cita": "harness/COLA.md:12171 y :12271-12272 (COLA 110)",
        },
    ],
    "consecuencia": "toda frecuencia que se publique despues (E4) lleva el coste dentro y se juzga "
    "contra su propio equilibrio p*, nunca contra el 50 %",
}

FALTAN = [
    {"que": "pantalla ENTRADAS en la mesa", "etapa": "E2",
     "motivo": "esta campana (E1) solo registra; la vista la construye la E2"},
    {"que": "resultado de cada DISPARADO (objetivo, stop, invalidado, caducado, no llenado)",
     "etapa": "E3", "motivo": "el resolutor por primer toque en ohlcv 1 min no existe todavia: "
     "resueltos = 0 en todas las celdas"},
    {"que": "cuenta de papel de 200 USD", "etapa": "E3",
     "motivo": "sus reglas estan escritas en el bloque papel de v1; no se ejecuta hasta la E3"},
    {"que": "frecuencia por version contra el equilibrio", "etapa": "E4",
     "motivo": "sin resueltos no hay frecuencia; hasta n efectiva 30: SIN CALIBRAR · MUESTRA "
     "INSUFICIENTE (n/30), sin porcentaje"},
]

_FRACCION = re.compile(
    r"(\d+\s*/\s*\d+)|(\d+([.,]\d+)?\s*%)|\b(tasa|acierto|aciertos|win|hit|probabilidad|"
    r"probability|fraccion|ratio_exito)\b",
    re.IGNORECASE,
)
_CLAVES_PROHIBIDAS = re.compile(
    r"(tasa|acierto|win_?rate|hit_?rate|probabilidad|probability|fraccion|exito_pct|pct_exito)",
    re.IGNORECASE,
)


def fracciones_servidas(respuesta: Any, ruta: str = "") -> list[str]:
    """Todo lo que la respuesta sirve con forma de fraccion o tasa de aciertos de los candidatos.

    Se salta referencia_ya_medido (rotulada y citada) y los textos de prosa fija (que_es, faltan):
    lo que se mira es el DATO. Una clave con nombre de tasa ya condena, valga lo que valga."""
    hallazgos: list[str] = []
    if isinstance(respuesta, dict):
        for clave, valor in respuesta.items():
            camino = f"{ruta}.{clave}" if ruta else str(clave)
            # parametros: las reglas del reglamento copiadas en la foto (con su huella), no datos
            if clave in ("referencia_ya_medido", "que_es", "faltan", "nota", "rotulo", "parametros"):
                continue
            if _CLAVES_PROHIBIDAS.search(str(clave)):
                hallazgos.append(f"{camino}: clave con forma de tasa de aciertos")
            hallazgos.extend(fracciones_servidas(valor, camino))
    elif isinstance(respuesta, list):
        for i, valor in enumerate(respuesta):
            hallazgos.extend(fracciones_servidas(valor, f"{ruta}[{i}]"))
    elif isinstance(respuesta, str) and _FRACCION.search(respuesta) and not _prosa(ruta):
        hallazgos.append(f"{ruta}: {respuesta[:60]!r}")
    return hallazgos


def _prosa(ruta: str) -> bool:
    """Textos fijos que explican una regla o un motivo: no son un dato servido."""
    return (ruta.endswith("motivo") or ".filtros." in ruta or ruta.endswith(".regla")
            or ".zonas_origen" in ruta or ruta.endswith("fuente"))


def _resumen(fila: dict[str, Any], foto_entera: bool) -> dict[str, Any]:
    foto = json.loads(fila["foto"]) if isinstance(fila["foto"], str) else fila["foto"]
    salida = {
        "registro_id": fila["registro_id"],
        "registered_at": fila["registered_at"].isoformat(),
        "vela_cierre": fila["vela_cierre"].isoformat(),
        "retraso_s": float(fila["retraso_s"]),
        "version": fila["version"],
        "familia": fila["familia"],
        "perfil": fila["perfil"],
        "lado": fila["lado"],
        "symbol": fila["symbol"],
        "clave": fila["clave"],
        "episodio": fila["episodio"],
        "estado": fila["estado"],
        "motivo": fila["motivo"],
        "caduca_en": fila["caduca_en"].isoformat() if fila["caduca_en"] else None,
        "huella_foto": fila["huella_foto"],
    }
    if foto_entera:
        salida["foto"] = foto
        return salida
    plan = foto.get("plan") or {}
    salida["resumen"] = {
        "zona": foto.get("zona"),
        "corte_zonas": foto.get("corte_zonas"),
        "entrada": plan.get("entrada"),
        "stop": (plan.get("stop") or {}).get("precio"),
        "objetivos": plan.get("objetivos"),
        "invalidacion": plan.get("invalidacion"),
        "caducidad": plan.get("caducidad"),
        "cocientes_coste": plan.get("cocientes"),
        "r": plan.get("r"),
        "p_equilibrio": plan.get("p_equilibrio"),
        "filtros": {n: {k: f.get(k) for k in ("estado", "valor", "umbral", "motivo")}
                    for n, f in (foto.get("filtros") or {}).items()},
        "decision": foto.get("decision"),
    }
    return salida


async def construir(conn, *, lado: str, desde: datetime | None, hasta: datetime | None,
                    version: str | None, symbol: str | None, limite: int,
                    foto: bool) -> dict[str, Any]:
    as_of = await conn.fetchval("SELECT clock_timestamp()")
    hasta = hasta or as_of
    desde = desde or hasta - timedelta(hours=24)
    pedido = {"lado": lado, "desde": desde.isoformat(), "hasta": hasta.isoformat(),
              "version": version, "symbol": symbol, "limite": limite, "foto": foto}
    base = {
        "as_of": as_of.isoformat(),
        "que_es": "Registro de hipotesis de entrada en largo y en corto, apuntadas ANTES de "
        "saber como acaban, con su foto. NO es una orden ni una probabilidad: ninguna fraccion "
        "de aciertos se sirve aqui.",
        "parametros": pedido,
        "referencia_ya_medido": REFERENCIA_YA_MEDIDO,
        "faltan": FALTAN,
    }
    existe = await conn.fetchval(
        "SELECT to_regclass('entrada_registro') IS NOT NULL AND "
        "to_regclass('entrada_reglamento') IS NOT NULL AND to_regclass('entrada_latido') IS NOT NULL"
    )
    if not existe:
        return {**base, "disponible": False,
                "motivo": "esta base no tiene las tablas del registro de entradas: falta "
                "desplegar (o alinear el esquema del espejo)"}

    try:
        doc = R.cargar_valido()
        reglamento = _reglamento(doc, as_of)
    except Exception as exc:  # noqa: BLE001 - el motivo se sirve
        doc = None
        reglamento = {"disponible": False, "motivo": f"el reglamento del release no valida: {exc}"[:600]}
    registradas = {
        (r["etiqueta"], r["bloque"]): r["huella"]
        for r in await conn.fetch("SELECT etiqueta, bloque, huella FROM entrada_reglamento")
    }
    if doc is not None:
        reglamento["registro_en_base"] = [
            {"etiqueta": f["etiqueta"], "bloque": f["bloque"],
             "estado": "registrado" if registradas.get((f["etiqueta"], f["bloque"])) == f["huella"]
             else ("OTRA HUELLA" if (f["etiqueta"], f["bloque"]) in registradas else "sin registrar")}
            for f in R.registros_esperados(doc)
        ]

    filtros_sql = ["($1::text IS NULL OR version = $1)", "($2::text IS NULL OR symbol = $2)",
                   "($3::text = 'ambos' OR lado = $3)"]
    donde = " AND ".join(filtros_sql)
    args = (version, symbol, lado)
    vivos = await conn.fetch(
        f"""
        SELECT *, foto::text AS foto FROM (
          SELECT DISTINCT ON (episodio) * FROM entrada_registro
          WHERE {donde} ORDER BY episodio, vela_cierre DESC, registro_id DESC
        ) u
        WHERE (estado = 'VIGILANDO') OR (estado = 'DISPARADO' AND caduca_en > $4)
        ORDER BY vela_cierre DESC, registro_id DESC LIMIT $5
        """,
        *args, as_of, limite,
    )
    ventana = await conn.fetch(
        f"""
        SELECT *, foto::text AS foto FROM entrada_registro
        WHERE {donde} AND estado IN ('DISPARADO', 'SOMBRA')
          AND vela_cierre >= $4 AND vela_cierre < $5
        ORDER BY vela_cierre DESC, registro_id DESC LIMIT $6
        """,
        *args, desde, hasta, limite,
    )
    cuentas = await conn.fetch(
        """
        SELECT familia, perfil, lado, version, estado, count(*)::int AS n
        FROM entrada_registro GROUP BY 1, 2, 3, 4, 5 ORDER BY 1, 2, 3, 4, 5
        """
    )
    latidos = await conn.fetch(
        "SELECT registered_at, vela_cierre, estado, duracion_s, error, detalle::text AS detalle "
        "FROM entrada_latido ORDER BY latido_id DESC LIMIT 5"
    )

    por_lado: dict[str, Any] = {}
    for un_lado in M.LADOS:
        if lado not in ("ambos", un_lado):
            continue
        por_lado[un_lado] = {
            "vivos": {
                "vigilando": [_resumen(dict(f), foto) for f in vivos
                              if f["lado"] == un_lado and f["estado"] == "VIGILANDO"],
                "disparados": [_resumen(dict(f), foto) for f in vivos
                               if f["lado"] == un_lado and f["estado"] == "DISPARADO"],
            },
            "ventana": {
                "disparados": [_resumen(dict(f), foto) for f in ventana
                               if f["lado"] == un_lado and f["estado"] == "DISPARADO"],
                "sombras": [_resumen(dict(f), foto) for f in ventana
                            if f["lado"] == un_lado and f["estado"] == "SOMBRA"],
            },
        }
    celdas: dict[tuple, dict[str, Any]] = {}
    for c in cuentas:
        clave = (c["familia"], c["perfil"], c["lado"], c["version"])
        celda = celdas.setdefault(clave, {"familia": clave[0], "perfil": clave[1], "lado": clave[2],
                                          "version": clave[3], "VIGILANDO": 0, "DISPARADO": 0,
                                          "SOMBRA": 0, "CERRADO_SIN_DISPARO": 0})
        celda[c["estado"]] = c["n"]
    for celda in celdas.values():
        celda["resueltos"] = 0
        celda["resueltos_motivo"] = "la E3 (resolutor) no existe todavia"
    generador = [
        {"registered_at": f["registered_at"].isoformat(),
         "vela_cierre": f["vela_cierre"].isoformat() if f["vela_cierre"] else None,
         "estado": f["estado"], "duracion_s": float(f["duracion_s"]) if f["duracion_s"] is not None else None,
         "error": f["error"],
         "motivo": (json.loads(f["detalle"]) or {}).get("motivo")}
        for f in latidos
    ]
    return {
        **base,
        "disponible": True,
        "generador": {
            "ultimos_latidos": generador,
            "motivo": None if generador else "el generador aun no ha corrido en esta base",
        },
        "por_lado": por_lado,
        "reglamento": reglamento,
        "cuentas": list(celdas.values()),
    }


def _reglamento(doc: dict[str, Any], momento: datetime) -> dict[str, Any]:
    activa = R.version_activa(doc)
    revision = R.revision_vigente(doc, momento)
    familias: dict[str, Any] = {}
    for familia in R.FAMILIAS:
        huellas = []
        retiradas = []
        for v in doc["versiones"]:
            if v["huellas"][familia] not in huellas:
                huellas.append(v["huellas"][familia])
            if v.get("retirada") and v["retirada"].get("antes_de_su_lectura"):
                retiradas.append({"version": v["version"], "fecha": v["retirada"]["fecha"],
                                  "motivo": v["retirada"]["motivo"],
                                  "etiqueta": "RETIRADA ANTES DE SU LECTURA"})
        familias[familia] = {
            "versiones_distintas": len(huellas),
            "hipotesis_probadas": len(huellas),
            "huellas": huellas,
            "retiradas_antes_de_su_lectura": retiradas,
        }
    return {
        "disponible": True,
        "version_activa": activa["version"],
        "versiones_en_curso": [v["version"] for v in R.versiones_en_curso(doc)],
        "ancla": doc["versiones"][0]["version"],
        "huellas_activa": activa["huellas"],
        "hipotesis_activa": activa["hipotesis"],
        "diferencia_con_el_padre": R.diferencia_con_padre(doc, activa["version"]),
        "por_familia": familias,
        "calendario_vigente": {
            "revision": revision["revision"] if revision else None,
            "cubre_hasta": revision["cubre_hasta"] if revision else None,
            "dias_que_le_quedan": round((R.instante(revision["cubre_hasta"]) - momento).total_seconds()
                                        / 86_400, 2) if revision else None,
            "renovacion_minima_dias": R.valores(activa["bloques"]["calendario"])["renovacion_minima_dias"],
            "motivo": None if revision else "no hay revision de calendario vigente",
        },
    }
