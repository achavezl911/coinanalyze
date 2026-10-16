"""GET /api/mesa/entradas · lo que la vista ENTRADAS de la mesa pinta, y nada mas (campana 137, E2).

POR QUE UNA RUTA APARTE Y NO /api/entradas. Medido contra 140 el 2026-10-13: /api/entradas pesa
253 278 B con todo por defecto y de 49 a 130 KB para un solo activo, y la vista no pinta ni la
mitad. Aqui va SOLO lo que la pantalla ensena, para UN activo y con UN as_of, de modo que toda la
pantalla sale de UNA respuesta: lo pintado se puede comparar con ella (A76).

DE DONDE SALE CADA COSA, y por que aqui no se decide nada del registro:
  los planes     de ruta.construir(foto=True): la MISMA definicion de «vivo» y de «ventana» que
                 /api/entradas. Esta capa elige campos de la foto; no re-evalua ningun plan.
  la palabra     de build_mesa_decide(frame="swing"): su decide.bias es la palabra de SWING y su
                 lectura_scalp.bias la de SCALP, la misma que sirve /api/mesa/decide en cada marco.
  el precio      el cierre de la ultima vela de 1 min de ohlcv, con su instante.

EL CLIENTE SOLO CALCULA UNA EDAD Y UNA CUENTA ATRAS, desde instantes servidos. Por eso aqui se
sirve cada cifra ya redondeada, cada estado y cada FRASE: lo que significa cada palabra de DECIDE
para un plan, por que una celda esta vacia, que no puede hacer el ancla, que falta (A86).

LO QUE NO SIRVE: ninguna fraccion ni tasa de aciertos. Pasa por fracciones_servidas() como
/api/entradas (tests/test_entradas_vista.py). El rotulo de muestra sale del bloque lectura del
reglamento, con la n servida.

EL RESULTADO (campana 139, E3). Cada DISPARADO lleva como acabo -o hasta que vela se sabe que no ha
tocado nada-, compuesto AQUI del resultado del resolutor (el FINAL guardado o el PROVISIONAL de las
velas de ahora: ruta.construir): rotulo, hora, firmeza y cifras, ya escritos. Un DISPARADO que ya acabo
no esta en «lo vivo» en ninguna respuesta posterior a la llegada de la vela que lo acaba. «Lo reciente»
ensena ademas los ultimos DISPARADOS del activo anteriores a su ventana, en filas cortas con su
resultado (con el plan entero no caben en el presupuesto de K106). La cuenta de papel de cada version
va entera salvo sus operaciones, de las que van las ultimas OPERACIONES_EN_PANTALLA (todas: /api/entradas).
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

from app.entradas import foto as F
from app.entradas import reglamento as R
from app.entradas import resolutor as RES
from app.entradas import resultados as RS
from app.entradas import ruta as RUTA

ESQUEMA = "mesa.entradas.v1"

# CADA CUANTO VUELVE A PEDIR LA VISTA, y contra que se justifica. El registro cambia una vez por
# vela de 15 min, asi que para el REGISTRO cualquier cadencia por debajo de la vela sobra. Lo que
# se mueve entre vela y vela es la palabra de DECIDE y la distancia al precio. DECIDE declara 120 s
# de edad maxima y su instantanea se escribe cada minuto (medido en 140 el 2026-10-13: una fila de
# metrics_snapshot por minuto), o sea que llega servida con 0 a ~60 s de edad: con 45 s de cadencia
# la palabra no pasa de ~110 s entre dos refrescos buenos; con 60 tocaria su tope en cada refresco
# que sirviera una instantanea vieja.
REFRESCO_S = 45
# Un refresco que FALLA se dice en el acto. Esto es para el que ni falla ni llega: sin una
# respuesta buena en dos cadencias y media, la vista deja de ensenar nada como vivo.
SIN_DATO_S = 120
VELA_GENERADOR_S = 900
VELAS_SIN_LATIR = 2
LIMITE = 200

PERFILES = ("intradia", "swing")
LADOS = ("largo", "corto")

# QUE PALABRA DE DECIDE ACOMPANA A CADA PERFIL, Y POR QUE. DECIDE tiene tres marcos (scalp, swing,
# largo) y el registro dos perfiles. LARGO (horizonte de 9 dias) no acompana a ninguno.
MARCO_DEL_PERFIL = {
    "intradia": {
        "marco": "scalp",
        "por_que": "el perfil intradia (velas de 15 min) va con la palabra del marco SCALP: es el "
        "unico marco de DECIDE por debajo de las 4 h y el unico que hoy se evalua",
    },
    "swing": {
        "marco": "swing",
        "por_que": "el perfil swing (velas de 4 h) va con la palabra del marco SWING, cuyo horizonte "
        "estructural son las mismas 4 h",
    },
}

SIN_LADO = "plan condicional: el sistema no toma lado"
SIN_LADO_SOSTENIDO = "plan condicional: el sistema no sostiene un lado"
_LADO_DE = {"LONG": "largo", "SHORT": "corto"}

QUE_ES = (
    "Planes de entrada apuntados ANTES de saber como acaban. No es una senal, no ejecuta ordenes, "
    "no guarda claves y no mueve fondos."
)
VIVO_QUE_ES = (
    "VIVO quiere decir que su reloj no ha caducado y que, en las velas de 1 min que ya estan en la base, no ha "
    "tocado su stop, su T1 ni su invalidacion: cada plan dice hasta que hora se sabe. Un DISPARADO que ya acabo "
    "no esta aqui: esta abajo, en lo reciente, con su salida y su hora."
)
# El estado que la pantalla pone en cada plan vivo. Los dos ultimos los decide el RELOJ del
# navegador (una cuenta atras que llega a cero, una edad que pasa su tope): las palabras son de aqui.
ROTULOS_VIVO = {
    "vigilando": "VIGILANDO",
    "disparado_vivo": "DISPARADO · VIVO",
    "disparado_caducado": "DISPARADO · CADUCADO",
    "no_se_sabe": "YA NO SE SABE",
}
RESULTADO_QUE_ES = (
    "Cada DISPARADO dice como acabo: su salida y su hora, por primer toque en las velas de 1 min de su simbolo "
    "(las convenciones del resolutor, abajo). PROVISIONAL quiere decir que sus velas aun pueden reescribirse, y "
    "dice hasta cuando. Es lo que le paso a UN plan: aqui ninguna cifra suma planes."
)
ROTULO_SALIDA = {
    RES.OBJETIVO: "OBJETIVO (T1)",
    RES.STOP: "STOP",
    RES.MISMA_VELA: "STOP (T1 en la misma vela)",
    RES.INVALIDADO: "INVALIDADO",
    RES.CADUCADO: "CADUCADO",
    RES.SIN_ENTRADA: "SIN ENTRADA",
    RES.NO_EVALUABLE: "NO EVALUABLE",
    RES.LIMITE_NO_LLENADA: "LIMITE NO LLENADA",
}
A_FAVOR_QUE_ES = ("lo que dentro de un minuto no se puede saber se cuenta en contra; este es el caso a favor, "
                  "fuera de toda cuenta")
ANTERIORES_N = 10
ANTERIORES_QUE_ES = (f"los DISPARADOS de este activo y de esta version anteriores a la ventana (hasta los "
                     f"{ANTERIORES_N} ultimos), con su resultado; el plan entero de cada uno, en /api/entradas?foto=true")
OPERACIONES_EN_PANTALLA = 20
PAPEL_QUE_ES = (
    "CUENTA DE PAPEL de cada version en curso: su bloque papel tal como esta registrado, sobre los resultados "
    "de sus DISPARADOS de los tres activos (nunca una SOMBRA). Sin apalancamiento: toma cada DISPARADO por orden "
    "de registro si cabe, con la cantidad hacia abajo al paso de Bybit, y apunta los saltados (los que no caben o "
    "no dimensionan) con su motivo. Un DISPARADO sin entrada real todavia queda pendiente, y detras de el los "
    "posteriores que necesitan capital. Los que no abren posicion (sin entrada, limite no llenada) y los que no "
    "tienen resultado (no evaluables, o sin P&L) se apuntan aparte: la cuenta no les reserva capital. Una "
    "operacion a la espera (su plan acabo y falta una vela para saber como salio) sigue ocupando su nocional. Si la "
    "cuenta es PROVISIONAL, dice por que. Funding solo adverso. No mueve fondos ni ejecuta nada.")
_ANTERIORES_SQL = """
SELECT * FROM (
    SELECT registro_id, version, familia, perfil, lado, symbol, clave, inicio_episodio, estado, vela_cierre,
           registered_at, caduca_en,
           row_number() OVER (PARTITION BY version ORDER BY vela_cierre DESC, registro_id DESC) AS n
    FROM entrada_registro WHERE estado = 'DISPARADO' AND symbol = $1 AND vela_cierre < $2) x
WHERE n <= $3 ORDER BY vela_cierre DESC, registro_id DESC
"""
# LA TABLA DE RECUENTOS (campana 137, remate R3). Su primera columna se llamaba VIGILANDO, como el estado
# de un plan vivo, y «VIGILANDO 264» se leia «264 planes vigilados ahora». Lo que cuenta es otra cosa y sale
# del registro: un episodio tiene UNA fila VIGILANDO y UNA terminal (app/entradas/registro.py, insertar).
# Medido en produccion el 2026-10-13 23:43Z: 1646 episodios y 3260 filas, ninguno con mas de dos, ninguno
# sin su fila VIGILANDO, ninguno con un estado repetido, y 32 abiertos. Lo ata tests/test_entradas_vista.py.
CUENTAS_QUE_CUENTAN = (
    "Esta tabla cuenta EPISODIOS del registro, NO planes vivos. Cada episodio deja una fila al abrirse "
    "(VIGILANDO) y otra al cerrarse, con como acabo (DISPARADO, SOMBRA o CERRADO SIN DISPARO). Cada columna "
    "cuenta los episodios que tienen esa fila, de todos los activos juntos y desde que el registro existe; "
    "uno que sigue abierto solo cuenta en la primera. Lo que se vigila AHORA en este activo esta arriba, en "
    "«lo vivo»."
)
# La cabecera de cada columna, en pasado: lo que le paso a un episodio, no el estado de un plan.
CUENTAS_ROTULOS = {
    "VIGILANDO": "SE ABRIERON",
    "DISPARADO": "ACABARON EN DISPARADO",
    "SOMBRA": "ACABARON EN SOMBRA",
    "CERRADO_SIN_DISPARO": "SE CERRARON SIN DISPARO",
}
_PRECIO_SQL = """
SELECT ts, close FROM ohlcv
WHERE symbol = $1 AND interval = '1min' AND ts >= $2
ORDER BY ts DESC LIMIT 1
"""
PRECIO_FUENTE = "cierre de la ultima vela de 1 min (ohlcv), el precio con que el generador mide las zonas"


async def precio_ahora(conn, symbol: str, as_of: datetime) -> dict[str, Any]:
    """El ultimo precio que la base tiene, con SU instante: contra el se mide la distancia."""
    fila = await conn.fetchrow(_PRECIO_SQL, symbol, as_of - timedelta(hours=1))
    if fila is None or fila["close"] is None:
        return {"valor": None, "instante": None, "fuente": PRECIO_FUENTE,
                "motivo": "no hay ninguna vela de 1 min de este activo en la ultima hora"}
    return {"valor": _precio(fila["close"]), "fuente": PRECIO_FUENTE, "motivo": None,
            "instante": (fila["ts"] + timedelta(minutes=1)).isoformat()}


def _precio(valor: Any) -> float | None:
    """La precision se decide AQUI y la pantalla pinta lo que llega (A77): 2 decimales desde 1000,
    3 desde 10, 4 por debajo. Es la regla de _round_number del sobre."""
    if valor is None:
        return None
    n = float(valor)
    return round(n, 2 if abs(n) >= 1000 else 3 if abs(n) >= 10 else 4)


def _r(valor: Any, decimales: int) -> float | None:
    return None if valor is None else round(float(valor), decimales)


def _fraccion(valor: Any) -> float | None:
    """Una fraccion del objetivo, a la precision con que se pinta (A77): dos decimales, y por debajo de
    0,01 los que hagan falta para que se vea su primera cifra. De aqui no sale como cero lo que no lo
    es: «x0,00 del objetivo» se lee «no cuesta nada» (campana 137, remate R2)."""
    if valor is None:
        return None
    n = float(valor)
    return round(n, max(2, -math.floor(math.log10(abs(n))))) if n else 0.0


# --------------------------------------------------------------------------- DECIDE


def _significado(palabra: str | None, marco: str, motivo: str | None,
                 sostenida: bool = False) -> dict[str, Any]:
    """Que significa para un plan cada una de las cinco respuestas de DECIDE. La frase la escribe
    quien sabe cual de las cinco es; la pantalla no la deduce de una palabra. `sostenida`: la palabra
    es la que el sistema SOSTIENE en su ventana (campana 138), no la de un instante."""
    M = marco.upper()
    if palabra in _LADO_DE:
        mismo = _LADO_DE[palabra]
        otro = "corto" if mismo == "largo" else "largo"
        cuando = "sostiene {} en los ultimos 5 min" if sostenida else "toma {} en este instante"
        return {
            "frase": f"DECIDE ({M}) {cuando.format(palabra)}. Un plan {mismo} va de su mismo "
            f"lado; un plan {otro} va EN CONTRA. DECIDE no es un requisito del plan: ni lo dispara "
            "ni lo anula.",
            "para": {
                mismo: {"relacion": "mismo_lado", "etiqueta": f"mismo lado que DECIDE ({palabra})"},
                otro: {"relacion": "en_contra",
                       "etiqueta": f"EN CONTRA de DECIDE ({palabra}): este plan es {otro}"},
            },
        }
    if palabra == "NO OPERAR" and sostenida:
        return {
            "frase": f"{SIN_LADO_SOSTENIDO}. DECIDE ({M}) no sostiene un lado en los ultimos 5 min; el "
            "plan sigue apuntado con sus propias reglas.",
            "para": {lado: {"relacion": "condicional", "etiqueta": SIN_LADO_SOSTENIDO} for lado in LADOS},
        }
    if palabra == "NO OPERAR":
        return {
            "frase": f"{SIN_LADO}. DECIDE ({M}) evaluo y no opera en este instante; el plan sigue "
            "apuntado con sus propias reglas.",
            "para": {lado: {"relacion": "condicional", "etiqueta": SIN_LADO} for lado in LADOS},
        }
    if palabra == "NO EVALUABLE":
        return {
            "frase": f"DECIDE ({M}) dice NO EVALUABLE: {motivo or 'sin motivo servido'}. No dice "
            "nada de estos planes: ni los respalda ni los desaconseja.",
            "para": {lado: {"relacion": "no_dice",
                            "etiqueta": "DECIDE no evaluable: ni respalda ni desaconseja el plan"}
                     for lado in LADOS},
        }
    return {
        "frase": f"Sin respuesta de DECIDE ({M}): {motivo or 'no llego ninguna palabra'}. No se sabe "
        "que decide el sistema en este instante; los planes se leen sin esa palabra.",
        "para": {lado: {"relacion": "sin_respuesta",
                        "etiqueta": "sin respuesta de DECIDE: no se sabe que decide el sistema"}
                 for lado in LADOS},
    }


def _decide(payload: dict[str, Any] | None, error: str | None) -> dict[str, Any]:
    """Las dos palabras, cada una con lo que significa. `payload` es build_mesa_decide(frame=swing)."""
    por_marco: dict[str, dict[str, Any]] = {}
    memoria: dict[str, Any] = {}
    recalculo = None
    if payload is not None:
        por_marco["swing"] = (payload.get("decide") or {}).get("bias") or {}
        por_marco["scalp"] = (payload.get("lectura_scalp") or {}).get("bias") or {}
        # LA PALABRA DEL SCALP ES LA QUE EL SISTEMA SOSTIENE (campana 138), con su edad: la de la
        # palabra, no la de la instantanea de debajo.
        memoria = (payload.get("lectura_scalp") or {}).get("memoria") or {}
        # Y LO QUE HACE FALTA PARA RECALCULARLA desde ESTA respuesta (A76): la regla, las evaluaciones de
        # SU VENTANA con sus instantes, el corte y la palabra del instante. No se pinta; lo lee K106. Solo
        # la ventana: la serie entera de la edad pesa hasta ~32 KB y la verifica K102 en /api/mesa/decide.
        if memoria:
            corte = (memoria.get("ventana") or {}).get("despues_de")
            recalculo = {
                # sin su texto: lleva «60 %» y esta ruta no sirve ninguno (fracciones_servidas); los numeros
                # de la regla bastan para recalcularla
                "regla": {k: v for k, v in (memoria.get("regla") or {}).items() if k != "texto"},
                "serie": [x for x in memoria.get("serie") or [] if corte is not None and x[0] > corte],
                "edad": memoria.get("edad"),
                "as_of": (payload.get("envelope_cut") or {}).get("as_of"),
                "instante": ((payload.get("lectura_scalp") or {}).get("instante") or {}).get("value"),
            }
    perfiles: dict[str, Any] = {}
    for perfil in PERFILES:
        marco = MARCO_DEL_PERFIL[perfil]["marco"]
        campo = por_marco.get(marco) or {}
        palabra = campo.get("value") if campo.get("value") in (*_LADO_DE, "NO OPERAR", "NO EVALUABLE") else None
        motivo = campo.get("motivo") if palabra else (
            error or (f"DECIDE sirvio {campo.get('value')!r}, que no es ninguna de sus cuatro palabras"
                      if campo.get("value") else "DECIDE no sirvio la palabra de este marco"))
        sostenida = marco == "scalp" and palabra is not None and bool(memoria)
        edad = (memoria.get("edad") or {}) if sostenida else {}
        perfiles[perfil] = {
            "marco": marco.upper(),
            "por_que_este_marco": MARCO_DEL_PERFIL[perfil]["por_que"],
            "palabra": palabra,
            "rotulo": palabra or "SIN RESPUESTA",
            "sin_respuesta": palabra is None,
            "motivo": motivo,
            "edad_de_la_palabra": edad.get("frase") if sostenida or palabra is None else
            f"la palabra de {marco.upper()} no sale de una ventana de evaluaciones: no tiene edad propia",
            "recalculo": recalculo if sostenida else None,
            **_significado(palabra, marco, motivo, sostenida),
        }
    edad = ((payload or {}).get("age") or {}).get("snapshot_lag_seconds") or {}
    tope = (payload or {}).get("max_age_s")
    return {
        "edad_s": _r(edad.get("value"), 1),
        "edad_motivo": None if edad.get("value") is not None else (
            edad.get("motivo") or error or "DECIDE no sirvio la edad de su instantanea"),
        "max_age_s": tope,
        "rancio": {
            "rotulo": "RANCIO",
            "frase": f"La palabra de DECIDE tiene mas de {tope:g} s y ya no se sostiene: no se sabe "
            "que decide el sistema ahora." if tope else None,
            "etiqueta": "DECIDE rancio: no se sabe que decide el sistema ahora",
        },
        "perfiles": perfiles,
    }


# --------------------------------------------------------------------------- los planes


def _zona(foto: dict[str, Any]) -> dict[str, Any]:
    zona = foto.get("zona") or {}
    return {"low": _precio(zona.get("low")), "high": _precio(zona.get("high"))}


def _distancia(zona: dict[str, Any], precio: dict[str, Any]) -> dict[str, Any]:
    """Lo que separa la zona del precio, en % DEL PRECIO. No es una tasa: es una distancia."""
    p, low, high = precio.get("valor"), zona.get("low"), zona.get("high")
    if p is None or low is None or high is None:
        return {"pct": None, "donde": None,
                "motivo": precio.get("motivo") or "la foto no trae los bordes de la zona"}
    if p > high:
        return {"pct": round((p - high) / p * 100, 2), "donde": "por encima de la zona", "motivo": None}
    if p < low:
        return {"pct": round((low - p) / p * 100, 2), "donde": "por debajo de la zona", "motivo": None}
    return {"pct": 0.0, "donde": "dentro de la zona", "motivo": None}


def _base(fila: dict[str, Any]) -> dict[str, Any]:
    return {
        "registro_id": fila["registro_id"],
        "version": fila["version"],
        "familia": fila["familia"],
        "perfil": fila["perfil"],
        "lado": fila["lado"],
        "vela_cierre": fila["vela_cierre"],
        "zona": _zona(fila["foto"]),
    }


def _requisitos(foto: dict[str, Any]) -> list[dict[str, Any]]:
    """La LISTA, con el estado de cada uno y el motivo cuando lo trae. Sin conteo y sin nota."""
    filtros = foto.get("filtros") or {}
    orden = [n for n in F.FILTROS if n in filtros] + sorted(n for n in filtros if n not in F.FILTROS)
    return [{"nombre": n, "estado": filtros[n].get("estado"), "motivo": filtros[n].get("motivo")}
            for n in orden]


def _vigilando(fila: dict[str, Any], precio: dict[str, Any]) -> dict[str, Any]:
    plan = _base(fila)
    plan["distancia"] = _distancia(plan["zona"], precio)
    return plan


def _hora(iso: str | None) -> str | None:
    """La hora de un instante servido como la pinta la vista: «MM-DD HH:MMZ»."""
    return None if not iso else f"{iso[5:10]} {iso[11:16]}Z"


def _rotulo_de(r: dict[str, Any]) -> str:
    rotulo = ROTULO_SALIDA[r["salida"]]
    return f"{rotulo} · {_hora(r['instante'])}" if r.get("instante") else rotulo


def _firmeza(r: dict[str, Any]) -> str:
    if r["firmeza"] == RES.FINAL:
        return "FINAL"
    if r.get("asentado_en"):
        return f"PROVISIONAL hasta las {_hora(r['asentado_en'])}"
    return f"PROVISIONAL: sus velas de los ultimos {int(RES.ASENTAMIENTO.total_seconds() // 60)} min aun pueden reescribirse"


def _resultado(r: dict[str, Any] | None) -> dict[str, Any]:
    """Lo que la pantalla pinta del resultado de UN DISPARADO, ya escrito. `vivo` es lo unico que no es
    texto: lo lee el reloj de la vista para no llamar VIVO a lo que ya acabo."""
    if not r:
        return {"vivo": False, "rotulo": "SIN RESULTADO", "frase": "el resolutor no devolvio nada para este plan"}
    vivo = r["estado"] == RES.ABIERTO
    if vivo:
        rotulo = "VIVO"
        frase = (f"sin tocar stop, T1 ni invalidacion en las velas de 1 min hasta las {_hora(r['sabido_hasta'])}"
                 if r.get("sabido_hasta") else r.get("motivo"))
    elif r["estado"] == RES.ESPERANDO:
        rotulo, frase = "ESPERANDO VELAS", r.get("motivo")
    else:
        rotulo, frase = _rotulo_de(r), r.get("motivo")
    pnl, ent = r.get("pnl") or {}, r.get("entrada") or {}
    salida: dict[str, Any] = {"vivo": vivo, "rotulo": rotulo, "frase": frase, "firmeza": _firmeza(r)}
    if ent:
        salida["entrada"] = {"instante": ent.get("instante"), "precio": _precio(ent.get("precio"))}
    if r.get("precio") is not None:
        salida["precio_salida"] = _precio(r["precio"])
    if pnl:
        salida.update(r_neto=_r(pnl.get("r_neto"), 2), bps_netos=_r(pnl.get("bps_netos"), 1))
    for t in ("t2", "t3"):
        x = r.get(t)
        if x and not vivo:
            salida[t] = {"precio": _precio(x["precio"]), "frase": (
                f"cruzado a las {_hora(x['instante'])}" if x["cruzado"] else
                "no cruzado" if x["cruzado"] is False else "no se sabe: falto una vela")}
    if r.get("excursion") and not vivo:
        salida["excursion"] = {k: _r(v, 1) for k, v in r["excursion"].items()}
    favor = r.get("a_favor")
    if favor:
        x = favor.get("hipotetico_a_mercado") or favor
        salida["a_favor"] = {
            "rotulo": ("HIPOTETICO A MERCADO: " if "hipotetico_a_mercado" in favor else "")
            + (ROTULO_SALIDA.get(x.get("salida")) or "SIN SALIDA"),
            "precio": _precio(x.get("precio")), "r_neto": _r((x.get("pnl") or {}).get("r_neto"), 2),
            "frase": favor.get("que_es") or A_FAVOR_QUE_ES}
    return salida


def _fila_corta(fila: dict[str, Any]) -> dict[str, Any]:
    """Un DISPARADO anterior a la ventana: quien es y como acabo."""
    return {"registro_id": fila["registro_id"], "version": fila["version"], "familia": fila["familia"],
            "perfil": fila["perfil"], "lado": fila["lado"], "vela_cierre": RES.iso(RES._t(fila["vela_cierre"])),
            "caduca_en": RES.iso(RES._t(fila["caduca_en"])), "resultado": _resultado(fila.get("resultado"))}


def _papel(cuentas: dict[str, Any], versiones: list[dict[str, str]]) -> dict[str, Any]:
    """La cuenta de papel de cada version en curso, ya escrita: saldo, n, cada operacion con su lote, su R y su
    P&L, los saltados, los pendientes, los que no abren posicion y los que no tienen resultado con su motivo, y el
    funding cobrado."""
    por_version = []
    for v in versiones:
        c = cuentas.get(v["version"])
        if c is None:
            continue
        ops = c["operaciones"][-OPERACIONES_EN_PANTALLA:]
        por_version.append({
            "version": v["version"], "papel": v["papel"], "capital_usd": c["capital_usd"],
            "saldo_usd": c["saldo_usd"], "n": c["n"], "abiertas": c["abiertas"], "funding_usd": c["funding_usd"],
            "meta_usd": c["meta_usd"], "meta": c["meta"], "no_dimensiona": c["no_dimensiona"],
            # cada razon la da la cuenta, cierta del estado que la pone; «hasta las» solo si es lo unico que falta
            "firmeza": "FINAL" if c["firmeza"] == RES.FINAL else (
                f"PROVISIONAL hasta las {_hora(c['provisional_hasta'])}" if c.get("provisional_hasta") else
                "PROVISIONAL: " + "; ".join(c["provisional_por"])),
            "recortada": (f"se ven las ultimas {OPERACIONES_EN_PANTALLA} de sus operaciones: todas, en "
                          "/api/entradas") if len(c["operaciones"]) > OPERACIONES_EN_PANTALLA else None,
            "operaciones": [{
                "registro_id": op["registro_id"], "activo": op["symbol"].split("USDT")[0],
                "vela_cierre": op["vela_cierre"], "perfil": op["perfil"], "lado": op["lado"],
                "rotulo": _rotulo_de({"salida": op["salida"], "instante": op["instante_salida"]}) if op["salida"]
                else op["estado"].upper(), "firmeza": "FINAL" if op["firmeza"] == RES.FINAL else "PROVISIONAL",
                "lote": op["lote"], "precio_entrada": _precio(op["precio_entrada"]),
                "precio_salida": _precio(op["precio_salida"]), "r_neto": _r(op["r_neto"], 2),
                "pnl_usd": op["pnl_usd"], "comision_usd": op["comision_usd"], "funding_usd": op["funding_usd"],
                "funding_sin_medir": op["funding_sin_medir"] or None} for op in ops],
            **{lista: [{"registro_id": s["registro_id"], "activo": s["symbol"].split("USDT")[0],
                        "vela_cierre": s["vela_cierre"], "motivo": s["motivo"]} for s in c[lista]]
               for lista in ("saltados", "pendientes", "sin_posicion", "sin_resultado")},
        })
    return {"que_es": PAPEL_QUE_ES, "por_version": por_version}


def _disparado(fila: dict[str, Any], as_of: datetime) -> dict[str, Any]:
    """El plan ENTERO tal como su foto lo guarda. Lo unico que se anade es el coste de cada pata
    como fraccion del objetivo (sus bps entre la distancia a T1, las dos de la foto)."""
    foto = fila["foto"]
    p = foto.get("plan") or {}
    entrada, stop, dist = p.get("entrada") or {}, p.get("stop") or {}, p.get("distancias_bps") or {}
    ref = entrada.get("referencia") or {}
    t1 = dist.get("t1")
    caduca = fila.get("caduca_en")
    plan = _base(fila)
    plan.update({
        "registered_at": fila["registered_at"],
        "caduca_en": caduca,
        "caducado": bool(caduca) and datetime.fromisoformat(caduca) <= as_of,
        "entrada": {"tipo": entrada.get("tipo"), "regla": entrada.get("regla"),
                    "referencia": {"precio": _precio(ref.get("precio")), "instante": ref.get("ts"),
                                   "fuente": ref.get("fuente")}},
        "stop": {"precio": _precio(stop.get("precio")), "tipo_disparo": stop.get("tipo_disparo"),
                 "distancia_bps": _r(dist.get("stop"), 1)},
        "objetivos": [{"nombre": f"T{i}", "precio": _precio(o)}
                      for i, o in enumerate(p.get("objetivos") or [], 1)],
        "t1_distancia_bps": _r(t1, 1),
        "invalidacion": {k: (p.get("invalidacion") or {}).get(k) for k in ("nivel", "hasta", "regla", "reloj")},
        "caducidad_min": (p.get("caducidad") or {}).get("minutos"),
        "r_neto": _r((p.get("r") or {}).get("neto"), 2),
        "r_bruto": _r((p.get("r") or {}).get("bruto"), 2),
        "p_equilibrio": _r(p.get("p_equilibrio"), 3),
        "costes": [
            {"pata": pata, "venue": c.get("venue"), "tipo": c.get("tipo"),
             "bps": _r(c.get("total_bps"), 2),
             "x_objetivo": _fraccion(c["total_bps"] / t1) if c.get("total_bps") is not None and t1 else None}
            for pata, c in ((n, (p.get("costes") or {}).get(n) or {}) for n in ("entrada", "objetivo", "stop"))
        ],
        "coste_ida_y_vuelta_x_objetivo": _fraccion((p.get("cocientes") or {}).get("coste_objetivo")),
        "requisitos": _requisitos(foto),
        "resultado": _resultado(fila.get("resultado")),
    })
    plan["invalidacion"]["nivel"] = _precio(plan["invalidacion"]["nivel"])
    return plan


def _sombra(fila: dict[str, Any]) -> dict[str, Any]:
    plan = _base(fila)
    requisitos = _requisitos(fila["foto"])
    plan["tipo_sombra"] = (fila["foto"].get("decision") or {}).get("tipo_sombra")
    plan["fallan"] = [r["nombre"] for r in requisitos if r["estado"] == "falla"]
    plan["no_evaluables"] = [{"nombre": r["nombre"], "motivo": r["motivo"]}
                             for r in requisitos if r["estado"] == "no_evaluable"]
    return plan


def _de(grupo: list[dict[str, Any]], version: str, perfil: str | None = None,
        lado: str | None = None) -> list[dict[str, Any]]:
    return [f for f in grupo if f["version"] == version
            and perfil in (None, f["perfil"]) and lado in (None, f["lado"])]


def _orden(planes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Por HORA, la mas reciente primero; a igual hora, el registro mas reciente. Nunca por nada
    que dependa de como acabo el plan."""
    return sorted(planes, key=lambda p: (p["vela_cierre"], p["registro_id"]), reverse=True)


# --------------------------------------------------------------------------- el marco


def _papeles(reglamento: dict[str, Any], vistas: set[str]) -> list[dict[str, str]]:
    """Las versiones en el orden en que se leen: la ACTIVA primero, el ANCLA al final y aparte."""
    if not reglamento.get("disponible"):
        return [{"version": v, "papel": "SIN REGLAMENTO"} for v in sorted(vistas, reverse=True)]
    activa, ancla = reglamento["version_activa"], reglamento["ancla"]
    en_curso = list(reglamento["versiones_en_curso"])
    papel = {v: "EN CURSO" for v in en_curso}
    papel[ancla] = "ANCLA"
    papel[activa] = "ACTIVA Y ANCLA" if activa == ancla else "ACTIVA"
    orden = [activa] + [v for v in reversed(en_curso) if v not in (activa, ancla)]
    if ancla != activa and ancla in en_curso:
        orden.append(ancla)
    orden += sorted(v for v in vistas if v not in orden)
    return [{"version": v, "papel": papel.get(v, "RETIRADA")} for v in orden]


def _muestra(doc: dict[str, Any] | None, resueltos: int) -> dict[str, Any]:
    """El rotulo de muestra, del bloque lectura del reglamento y con la n que la ruta sirve. Mientras
    n < minimo no hay porcentaje, ni aqui ni en ningun sitio."""
    if doc is None:
        return {"n": resueltos, "minimo": None, "rotulo": None,
                "motivo": "el reglamento del release no valida: no hay rotulo de muestra que leer"}
    lectura = R.valores(R.version_activa(doc)["bloques"]["lectura"])
    minimo = int(lectura["n_efectiva_minima"])
    if resueltos < minimo:
        return {"n": resueltos, "minimo": minimo, "motivo": None,
                "rotulo": lectura["etiqueta_sin_muestra"].replace("(n/", f"({resueltos}/")}
    return {"n": resueltos, "minimo": minimo, "rotulo": None,
            "motivo": "con la muestra minima alcanzada la lectura la emite la E4, que no existe todavia"}


def pasada_en_curso(doc: dict[str, Any] | None, ultima_vela: str | None, vela_del_latido: str | None) -> str | None:
    """LA PASADA A MEDIAS. Cada version registra a SU hora tras el cierre de la vela (el ancla antes
    que la activa) y el latido se escribe al acabar la ultima. Si hay planes de una vela posterior a
    la del ultimo latido, esa vela esta todavia registrandose: quien mire la pantalla en ese rato ve
    lo que apunto una version y no lo que apuntara la otra. Se dice; no se esconde ni se espera."""
    if not ultima_vela or not vela_del_latido:
        return None
    if datetime.fromisoformat(ultima_vela) <= datetime.fromisoformat(vela_del_latido):
        return None
    horas = ""
    if doc is not None:
        horas = " (" + " y ".join(
            f"{v['version']} a partir de los "
            f"{R.valores(v['bloques']['comun'])['espera_datos_s']['primer_intento']} s"
            for v in R.versiones_en_curso(doc)) + ")"
    return (f"La vela de las {ultima_vela[11:16]}Z esta todavia registrandose: hay planes suyos y el "
            f"generador aun no ha latido por ella. Cada version decide a su hora tras el cierre{horas}; "
            "hasta ese latido, lo de esa vela puede estar a medias.")


def _ancla_no_puede(doc: dict[str, Any] | None, ancla: str, sombras: list[dict[str, Any]]) -> dict[str, Any]:
    """Lo que el ancla no puede hacer, dicho UNA vez. Sale de las filas servidas -los requisitos
    que no se pudieron evaluar en NINGUNA de sus sombras de la ventana- y de su reglamento."""
    comunes = ([n for n in F.FILTROS
                if all(n in {x["nombre"] for x in s["no_evaluables"]} for s in sombras)]
               if sombras else [])
    frase = f"ANCLA · {ancla} corre siempre y no cambia: es la referencia contra la que se compara la activa."
    if comunes:
        espera = None
        if doc is not None and R.version(doc, ancla) is not None:
            comun = R.valores(R.version(doc, ancla)["bloques"]["comun"])
            if not comun.get("espera_flujos"):
                espera = (comun.get("espera_datos_s") or {}).get("primer_intento")
        frase += (f" En sus {len(sombras)} SOMBRAS de esta ventana, {' y '.join(comunes)} no se "
                  "pudieron evaluar en NINGUNA")
        frase += (f": {ancla} no espera al flujo y decide a los {espera} s del cierre de la vela."
                  if espera is not None else ".")
        frase += " Se dice aqui una vez y no en cada fila."
    elif not sombras:
        frase += " No tiene SOMBRAS en esta ventana."
    return {"requisitos": comunes, "frase": frase}


async def construir(conn, *, symbol: str, activo: str, palabra_de_decide) -> dict[str, Any]:
    """Lo que toca la base. `palabra_de_decide` es ai_context.build_mesa_decide: llega de fuera para
    que app/entradas no dependa del sobre. Si DECIDE falla, la vista NO falla: «sin respuesta» es
    una de las cinco cosas que tiene que saber decir, con su motivo."""
    registro = await RUTA.construir(conn, lado="ambos", desde=None, hasta=None, version=None,
                                    symbol=symbol, limite=LIMITE, foto=True)
    # Sin registro no hay distancia que medir: el precio solo se pide si hay planes que ensenar.
    precio = (await precio_ahora(conn, symbol, datetime.fromisoformat(registro["as_of"]))
              if registro.get("disponible") else {})
    decide = error = None
    try:
        decide = await palabra_de_decide(conn, symbol, frame="swing")
    except Exception as exc:  # noqa: BLE001 - el motivo se sirve
        error = f"DECIDE fallo al calcularse ({type(exc).__name__})"
    try:
        doc = R.cargar_valido()
    except Exception:  # noqa: BLE001 - ruta.construir ya sirve el motivo en reglamento.motivo
        doc = None
    anteriores = []
    if registro.get("disponible"):
        desde = datetime.fromisoformat(registro["parametros"]["desde"])
        anteriores = [dict(f) for f in await conn.fetch(_ANTERIORES_SQL, symbol, desde, ANTERIORES_N)]
        resultados = await RS.de_filas(conn, anteriores, datetime.fromisoformat(registro["as_of"]))
        anteriores = [{**f, "resultado": resultados.get(f["registro_id"])} for f in anteriores]
    return componer(registro, symbol=symbol, activo=activo, precio=precio, decide=decide,
                    decide_error=error, doc=doc, anteriores=anteriores)


def componer(registro: dict[str, Any], *, symbol: str, activo: str, precio: dict[str, Any],
             decide: dict[str, Any] | None, decide_error: str | None,
             doc: dict[str, Any] | None, anteriores: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """De lo que sirve ruta.construir(foto=True) a lo que la vista pinta. Sin base: se prueba sola."""
    base = {
        "esquema": ESQUEMA,
        "as_of": registro["as_of"],
        "symbol": symbol,
        "activo": activo,
        "que_es": QUE_ES,
        "frescura": {
            "refresco_s": REFRESCO_S,
            "sin_dato_s": SIN_DATO_S,
            "regla": f"se vuelve a pedir cada {REFRESCO_S} s; sin una respuesta buena en "
            f"{SIN_DATO_S} s la vista deja de ensenar nada como vivo",
            # dos frases, porque son dos cosas: el ultimo intento FALLO, o no hay ninguna reciente
            # (una peticion colgada, una pestana que estuvo oculta y no pidio). Decir «no contesta»
            # de una ruta a la que no se pregunto seria falso.
            "sin_dato_frase": "SIN DATO · la ruta de entradas no contesta. Lo de abajo es lo ultimo "
            "que se supo y ya no se sabe si sigue vivo.",
            "viejo_frase": f"SIN DATO RECIENTE · la ultima respuesta buena tiene mas de {SIN_DATO_S} s. "
            "Lo de abajo es lo ultimo que se supo y ya no se sabe si sigue vivo.",
        },
        "decide": _decide(decide, decide_error),
    }
    if not registro.get("disponible"):
        return {**base, "disponible": False, "motivo": registro.get("motivo")}

    as_of = datetime.fromisoformat(registro["as_of"])
    reglamento = registro["reglamento"]
    familias = ({f: {k: R.version_activa(doc)["bloques"][f].get(k) for k in ("nombre", "definicion")}
                 for f in R.FAMILIAS} if doc is not None else {})
    filas: dict[str, list[dict[str, Any]]] = {"vigilando": [], "vivos": [], "disparados": [], "sombras": []}
    for lado in registro["por_lado"].values():
        filas["vigilando"] += lado["vivos"]["vigilando"]
        filas["vivos"] += lado["vivos"]["disparados"]
        filas["disparados"] += lado["ventana"]["disparados"]
        filas["sombras"] += lado["ventana"]["sombras"]
    vistas = {f["version"] for grupo in filas.values() for f in grupo}
    versiones = _papeles(reglamento, vistas)
    ancla = reglamento.get("ancla") if reglamento.get("disponible") else None

    # LO VIVO, por celda (perfil, lado) y dentro por version: la relacion con DECIDE es de la celda.
    vivos_id = {f["registro_id"] for f in filas["vivos"]}
    celdas = []
    for perfil in PERFILES:
        for lado in LADOS:
            por_version = []
            for v in versiones:
                disparados = _orden([_disparado(f, as_of)
                                     for f in _de(filas["vivos"], v["version"], perfil, lado)])
                vigilando = _orden([_vigilando(f, precio)
                                    for f in _de(filas["vigilando"], v["version"], perfil, lado)])
                por_version.append({
                    **v,
                    "disparados": disparados,
                    "vigilando": vigilando,
                    "sin_planes": None if disparados or vigilando else
                    f"{v['version']} no tiene ningun plan vivo en {perfil} · {lado}: ningun episodio "
                    "abierto ni DISPARADO vivo (los que ya acabaron estan en lo reciente, con su salida)",
                })
            celdas.append({"perfil": perfil, "lado": lado, "por_version": por_version})

    # LO RECIENTE, por version: los DISPARADOS de la ventana (vivos o caducados) y las SOMBRAS.
    reciente = []
    for v in versiones:
        disparados = _orden([{**_disparado(f, as_of), "vivo": f["registro_id"] in vivos_id}
                             for f in _de(filas["disparados"], v["version"])])
        sombras = _orden([_sombra(f) for f in _de(filas["sombras"], v["version"])])
        previos = [_fila_corta(f) for f in (anteriores or []) if f["version"] == v["version"]]
        bloque = {**v, "disparados": disparados, "sombras": sombras, "no_puede": None,
                  "anteriores": previos, "anteriores_que_es": ANTERIORES_QUE_ES if previos else None,
                  "sin_planes": None if disparados or sombras else
                  f"{v['version']} no tiene ningun DISPARADO ni SOMBRA de este activo en la ventana"}
        if v["version"] == ancla and v["papel"] == "ANCLA":
            bloque["no_puede"] = _ancla_no_puede(doc, ancla, sombras)
            dichos = set(bloque["no_puede"]["requisitos"])
            for s in sombras:
                s["no_evaluables"] = [x for x in s["no_evaluables"] if x["nombre"] not in dichos]
        reciente.append(bloque)

    n_ventana = len(filas["disparados"]) + len(filas["sombras"])
    ultima_vela = max((f["vela_cierre"] for grupo in filas.values() for f in grupo), default=None)
    latidos = registro["generador"]["ultimos_latidos"]
    tope = VELA_GENERADOR_S * VELAS_SIN_LATIR
    calendario = reglamento.get("calendario_vigente") or {}
    # El motivo de «resueltos» llega por celda. Si es el mismo en todas se sirve UNA vez.
    motivos = {c.get("resueltos_motivo") for c in registro["cuentas"]}
    motivo_comun = motivos.pop() if len(motivos) == 1 else None
    return {
        **base,
        "disponible": True,
        "motivo": None,
        "precio": precio,
        "generador": {
            "ultimo_latido": {k: latidos[0].get(k) for k in
                              ("registered_at", "vela_cierre", "estado", "error", "motivo")}
            if latidos else None,
            "motivo": registro["generador"]["motivo"],
            "pasada_en_curso": pasada_en_curso(doc, ultima_vela, latidos[0]["vela_cierre"] if latidos else None),
            "tope_s": tope,
            "regla": f"se da por PARADO si su ultimo latido tiene mas de {VELAS_SIN_LATIR} velas de "
            f"15 min ({tope} s)",
            "parado_frase": "EL GENERADOR ESTA PARADO · no ha latido en mas de dos velas. Lo de abajo "
            "es lo ultimo que registro y ya no se sabe si sigue vivo.",
        },
        "vivo": {"que_es": VIVO_QUE_ES, "rotulos": ROTULOS_VIVO, "celdas": celdas},
        "reciente": {
            "ventana": {"desde": registro["parametros"]["desde"], "hasta": registro["parametros"]["hasta"]},
            "que_es_el_resultado": RESULTADO_QUE_ES,
            "recortada": f"la ventana trae el tope de {LIMITE} planes: puede haber mas antiguos que "
            "no se ven" if n_ventana >= LIMITE else None,
            "por_version": reciente,
        },
        "marco": {
            "disponible": bool(reglamento.get("disponible")),
            "motivo": reglamento.get("motivo"),
            "version_activa": reglamento.get("version_activa"),
            "ancla": reglamento.get("ancla"),
            "versiones_en_curso": reglamento.get("versiones_en_curso"),
            "familias": familias,
            "calendario": {k: calendario.get(k) for k in
                           ("revision", "vigente_desde", "cubre_hasta", "eventos",
                            "dias_que_le_quedan", "motivo")},
            "hipotesis_activa": reglamento.get("hipotesis_activa"),
            "cuentas_que_cuentan": CUENTAS_QUE_CUENTAN,
            "cuentas_rotulos": CUENTAS_ROTULOS,
            "resueltos_motivo": motivo_comun,
            "cuentas": [{**{k: v for k, v in c.items() if k != "resueltos_motivo" or motivo_comun is None},
                         "muestra": _muestra(doc, c["resueltos"] - c.get("no_evaluables", 0))}
                        for c in registro["cuentas"]],
            "faltan": registro["faltan"],
            "resolutor": _resolutor(registro.get("resultados") or {}),
        },
        "papel": _papel(registro.get("papel") or {}, versiones),
    }


def _resolutor(r: dict[str, Any]) -> dict[str, Any] | None:
    """Las convenciones con que el resolutor da cada resultado, con su version y su huella: las sirve la ruta."""
    if not r:
        return None
    return {"version": r["resolutor"], "huella": r["huella_convenciones"], "frase": r["que_es"],
            "convenciones": [{"nombre": k, "regla": v} for k, v in r["convenciones"].items()],
            "cambios_e3": [{"que": x} for x in r["cambios_e3"]]}
