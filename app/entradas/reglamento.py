"""El REGLAMENTO de las entradas: configuracion de PRODUCTO, legible por maquina (campana 135, E1).

Vive en config/entradas/reglamento.json y cambia SOLO por PR. Este modulo lo carga, lo valida y
calcula sus huellas. Es biblioteca estandar a proposito: lo importan el generador, la ruta, los
tests y el check K105 (que corre en 143 sin el entorno de la app).

LA HUELLA. sha256 del JSON canonico de lo que DECIDE de un bloque: {parametro: {valor, unidad}}.
El ORIGEN de cada umbral documenta y no entra: corregir una cita no cambia la regla. Hay una huella
por FAMILIA (F1, F2) y una por bloque (comun, calendario, lectura, papel), asi que un cambio en F1
no reinicia la cuenta de F2. Los EVENTOS del calendario van en una cadena de revisiones aparte,
compartida por todas las versiones en curso: renovarlos no crea version (el ANCLA no muere cuando el
calendario vence) y cada revision tiene su propia huella (bloque 'calendario_datos').

LO QUE ESTE MODULO NO PUEDE VER. El CI clona a profundidad 1 (.github/workflows/ci.yml): un test
solo ve el fichero de su arbol. Si alguien cambia un umbral de v1 Y recalcula su huella declarada,
validar() no lo ve; lo ve el test de historia contra origin/main (tests/test_entradas_reglamento.py)
y, en produccion, la tabla entrada_reglamento, que guarda la huella de cada (etiqueta, bloque) la
primera vez que corre y rechaza una segunda regla bajo la misma etiqueta (UNIQUE), y K105 a.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

FORMATO = "coinalyze.entradas.reglamento"
FORMATO_VERSION = 1
FAMILIAS = ("F1", "F2")
BLOQUES = ("F1", "F2", "comun", "calendario", "lectura", "papel")
BLOQUE_CALENDARIO_DATOS = "calendario_datos"
RUTA = Path(__file__).resolve().parents[2] / "config" / "entradas" / "reglamento.json"

_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_INSTANTE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_ETIQUETA = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class ReglamentoInvalido(ValueError):
    """El fichero no cumple sus propias reglas: ningun candidato se emite con el."""


def canonico(valor: Any) -> str:
    """El MISMO JSON canonico que app/signal_replay.py:canonical_json_object (lo prueba un test)."""
    return json.dumps(
        valor, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    )


def huella(valor: Any) -> str:
    return hashlib.sha256(canonico(valor).encode("utf-8")).hexdigest()


def instante(texto: str) -> datetime:
    """'AAAA-MM-DDTHH:MM:SSZ' -> datetime UTC. Ningun otro formato: la hora del reglamento es UTC."""
    if not isinstance(texto, str) or not _INSTANTE.match(texto):
        raise ReglamentoInvalido(f"instante no UTC 'AAAA-MM-DDTHH:MM:SSZ': {texto!r}")
    return datetime.strptime(texto, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def contenido_bloque(bloque: dict[str, Any]) -> dict[str, Any]:
    """Lo que DECIDE de un bloque. El origen, el nombre y la definicion documentan y no entran."""
    parametros = bloque.get("parametros") if isinstance(bloque, dict) else None
    if not isinstance(parametros, dict) or not parametros:
        raise ReglamentoInvalido("un bloque sin 'parametros'")
    salida: dict[str, Any] = {}
    for nombre, parametro in parametros.items():
        if not isinstance(parametro, dict) or "valor" not in parametro:
            raise ReglamentoInvalido(f"el parametro {nombre!r} no trae 'valor'")
        salida[nombre] = {"valor": parametro["valor"], "unidad": parametro.get("unidad", "")}
    return {"parametros": salida}


def huella_bloque(bloque: dict[str, Any]) -> str:
    return huella(contenido_bloque(bloque))


def contenido_revision(revision: dict[str, Any]) -> dict[str, Any]:
    """Lo que DECIDE de una revision del calendario: su vigencia, su cobertura y sus eventos."""
    eventos = revision.get("eventos")
    if not isinstance(eventos, list):
        raise ReglamentoInvalido("una revision de calendario sin lista 'eventos'")
    limpios = [
        {
            "clave": e.get("clave"),
            "titulo": e.get("titulo"),
            "hora_utc": e.get("hora_utc"),
            "importancia": e.get("importancia"),
        }
        for e in eventos
        if isinstance(e, dict)
    ]
    limpios.sort(key=lambda e: (str(e["hora_utc"]), str(e["clave"])))
    return {
        "vigente_desde": revision.get("vigente_desde"),
        "cubre_hasta": revision.get("cubre_hasta"),
        "eventos": limpios,
    }


def huella_revision(revision: dict[str, Any]) -> str:
    return huella(contenido_revision(revision))


def valores(bloque: dict[str, Any]) -> dict[str, Any]:
    """{parametro: valor} de un bloque: lo que lee el generador."""
    return {n: p["valor"] for n, p in contenido_bloque(bloque)["parametros"].items()}


# --------------------------------------------------------------------------- validacion


def _texto(valor: Any) -> bool:
    return isinstance(valor, str) and bool(valor.strip())


def _valida_bloque(donde: str, nombre: str, bloque: Any) -> list[str]:
    errores: list[str] = []
    parametros = bloque.get("parametros") if isinstance(bloque, dict) else None
    if not isinstance(parametros, dict) or not parametros:
        return [f"{donde}: el bloque {nombre} no trae parametros"]
    for p, cuerpo in parametros.items():
        if not isinstance(cuerpo, dict) or "valor" not in cuerpo:
            errores.append(f"{donde}: {nombre}.{p} sin 'valor'")
            continue
        if not isinstance(cuerpo.get("unidad", ""), str):
            errores.append(f"{donde}: {nombre}.{p} con 'unidad' que no es texto")
        if not _texto(cuerpo.get("origen")):
            errores.append(
                f"{donde}: {nombre}.{p} sin ORIGEN (una constante fichero:linea, una medida con su "
                "comando, o 'ARBITRARIO v1')"
            )
    return errores


def _valida_version(i: int, v: Any, vistas: dict[str, dict[str, Any]]) -> list[str]:
    etiqueta = v.get("version") if isinstance(v, dict) else None
    donde = f"version #{i} ({etiqueta})"
    if not isinstance(v, dict) or not isinstance(etiqueta, str) or not _ETIQUETA.match(etiqueta):
        return [f"{donde}: etiqueta de version invalida"]
    if etiqueta in vistas:
        return [
            f"{donde}: la etiqueta {etiqueta} aparece dos veces: una etiqueta de version no abarca "
            "dos reglas (la regla de K62)"
        ]
    errores: list[str] = []
    padre = v.get("padre")
    if i == 0:
        if padre is not None:
            errores.append(f"{donde}: el ANCLA no tiene padre")
        if v.get("ancla") is not True:
            errores.append(f"{donde}: la primera version es el ANCLA y lo declara (ancla: true)")
    else:
        if v.get("ancla") not in (False, None):
            errores.append(f"{donde}: solo la primera version es el ANCLA")
        if padre not in vistas:
            errores.append(f"{donde}: su padre {padre!r} no es una version anterior del fichero")
    if not (isinstance(v.get("fecha"), str) and _FECHA.match(v["fecha"])):
        errores.append(f"{donde}: fecha AAAA-MM-DD obligatoria")
    for campo in ("autor", "motivo"):
        if not _texto(v.get(campo)):
            errores.append(f"{donde}: sin {campo}")
    hipotesis = v.get("hipotesis")
    if not isinstance(hipotesis, dict) or not all(
        _texto(hipotesis.get(k)) for k in ("celdas", "sentido", "lectura")
    ):
        errores.append(
            f"{donde}: sin HIPOTESIS completa: que celda espera mover (celdas), en que sentido "
            "(sentido) y en que lectura se juzga (lectura)"
        )
    retirada = v.get("retirada")
    if retirada is not None:
        if i == 0 or v.get("ancla") is True:
            errores.append(f"{donde}: el ANCLA no se retira (corre siempre)")
        if (
            not isinstance(retirada, dict)
            or not (isinstance(retirada.get("fecha"), str) and _FECHA.match(retirada["fecha"]))
            or not _texto(retirada.get("motivo"))
            or not isinstance(retirada.get("antes_de_su_lectura"), bool)
        ):
            errores.append(
                f"{donde}: una retirada lleva fecha, motivo y antes_de_su_lectura (true/false)"
            )
    bloques = v.get("bloques")
    if not isinstance(bloques, dict) or set(bloques) != set(BLOQUES):
        errores.append(f"{donde}: los bloques son exactamente {', '.join(BLOQUES)}")
        return errores
    for nombre in BLOQUES:
        errores.extend(_valida_bloque(donde, nombre, bloques[nombre]))
    declaradas = v.get("huellas")
    if not isinstance(declaradas, dict):
        errores.append(f"{donde}: sin mapa de huellas declaradas")
        return errores
    sobran = sorted(set(declaradas) - set(BLOQUES))
    if sobran:
        errores.append(f"{donde}: huellas de bloques que no existen: {', '.join(sobran)}")
    calculadas: dict[str, str] = {}
    for nombre in BLOQUES:
        try:
            calculadas[nombre] = huella_bloque(bloques[nombre])
        except ReglamentoInvalido:
            continue
        if declaradas.get(nombre) != calculadas[nombre]:
            errores.append(
                f"{donde}: la huella declarada de {nombre} ({declaradas.get(nombre)!r}) no es la "
                f"calculada ({calculadas[nombre]}): un umbral cambio sin version nueva, o la "
                "version nueva no registro su huella"
            )
    if i > 0 and padre in vistas and calculadas == vistas[padre].get("_calculadas"):
        errores.append(f"{donde}: no cambia ningun bloque respecto a su padre {padre}")
    v["_calculadas"] = calculadas
    return errores


def _valida_calendario(calendario: Any) -> list[str]:
    revisiones = calendario.get("revisiones") if isinstance(calendario, dict) else None
    if not isinstance(revisiones, list) or not revisiones:
        return ["calendario: sin revisiones"]
    errores: list[str] = []
    vistas: set[str] = set()
    previa: datetime | None = None
    for i, r in enumerate(revisiones):
        etiqueta = r.get("revision") if isinstance(r, dict) else None
        donde = f"calendario #{i} ({etiqueta})"
        if not isinstance(r, dict) or not isinstance(etiqueta, str) or not _ETIQUETA.match(etiqueta):
            errores.append(f"{donde}: etiqueta de revision invalida")
            continue
        if etiqueta in vistas:
            errores.append(f"{donde}: la revision {etiqueta} aparece dos veces")
            continue
        padre = r.get("padre")
        if (i == 0 and padre is not None) or (i > 0 and padre not in vistas):
            errores.append(f"{donde}: padre {padre!r} invalido")
        vistas.add(etiqueta)
        if not (isinstance(r.get("fecha"), str) and _FECHA.match(r["fecha"])):
            errores.append(f"{donde}: fecha AAAA-MM-DD obligatoria")
        for campo in ("autor", "motivo"):
            if not _texto(r.get(campo)):
                errores.append(f"{donde}: sin {campo}")
        try:
            desde = instante(r.get("vigente_desde"))
            hasta = instante(r.get("cubre_hasta"))
        except ReglamentoInvalido as exc:
            errores.append(f"{donde}: {exc}")
            continue
        if hasta < desde:
            errores.append(f"{donde}: cubre_hasta anterior a vigente_desde")
        if previa is not None and desde < previa:
            errores.append(f"{donde}: vigente_desde anterior al de la revision previa")
        previa = desde
        eventos = r.get("eventos")
        if not isinstance(eventos, list):
            errores.append(f"{donde}: sin lista de eventos")
            continue
        claves: set[str] = set()
        for e in eventos:
            if not isinstance(e, dict) or not _texto(e.get("clave")) or not _texto(e.get("titulo")):
                errores.append(f"{donde}: evento sin clave o sin titulo")
                continue
            if e["clave"] in claves:
                errores.append(f"{donde}: evento {e['clave']} repetido")
            claves.add(e["clave"])
            try:
                hora = instante(e.get("hora_utc"))
            except ReglamentoInvalido as exc:
                errores.append(f"{donde}: evento {e['clave']}: {exc}")
                continue
            if hora < desde:
                errores.append(
                    f"{donde}: el evento {e['clave']} ({e['hora_utc']}) es anterior a la revision "
                    f"que lo trae ({r['vigente_desde']}): un calendario no se rellena hacia atras"
                )
            if e.get("importancia") not in (1, 2, 3):
                errores.append(f"{donde}: evento {e['clave']} con importancia fuera de 1..3")
            if not _texto(e.get("fuente")):
                errores.append(f"{donde}: evento {e['clave']} sin fuente")
        try:
            if r.get("huella") != huella_revision(r):
                errores.append(
                    f"{donde}: la huella declarada ({r.get('huella')!r}) no es la calculada "
                    f"({huella_revision(r)})"
                )
        except ReglamentoInvalido as exc:
            errores.append(f"{donde}: {exc}")
    return errores


def validar(doc: Any) -> list[str]:
    """Todos los errores del fichero contra sus propias reglas. Lista vacia = valido."""
    if not isinstance(doc, dict):
        return ["el reglamento no es un objeto JSON"]
    errores: list[str] = []
    if doc.get("formato") != FORMATO or doc.get("formato_version") != FORMATO_VERSION:
        errores.append(f"formato distinto de {FORMATO} v{FORMATO_VERSION}")
    versiones = doc.get("versiones")
    if not isinstance(versiones, list) or not versiones:
        return errores + ["sin versiones"]
    vistas: dict[str, dict[str, Any]] = {}
    for i, v in enumerate(versiones):
        errores.extend(_valida_version(i, v, vistas))
        if isinstance(v, dict) and isinstance(v.get("version"), str):
            vistas.setdefault(v["version"], v)
    for v in versiones:
        if isinstance(v, dict):
            v.pop("_calculadas", None)
    errores.extend(_valida_calendario(doc.get("calendario")))
    return errores


# --------------------------------------------------------------------------- lectura


def cargar(ruta: str | Path | None = None) -> dict[str, Any]:
    return json.loads(Path(ruta or RUTA).read_text(encoding="utf-8"))


def cargar_valido(ruta: str | Path | None = None) -> dict[str, Any]:
    doc = cargar(ruta)
    errores = validar(doc)
    if errores:
        raise ReglamentoInvalido("; ".join(errores))
    return doc


def versiones_en_curso(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Las que corren: todas las no retiradas, en el orden del fichero (el ANCLA primero)."""
    return [v for v in doc["versiones"] if v.get("retirada") is None]


def version_activa(doc: dict[str, Any]) -> dict[str, Any]:
    """La ultima no retirada por orden del fichero, o sea por PR. Nunca la elegida por resultado."""
    return versiones_en_curso(doc)[-1]


def version(doc: dict[str, Any], etiqueta: str) -> dict[str, Any] | None:
    return next((v for v in doc["versiones"] if v.get("version") == etiqueta), None)


def revision_vigente(doc: dict[str, Any], momento: datetime) -> dict[str, Any] | None:
    """La ultima revision de eventos con vigente_desde <= momento (None si ninguna)."""
    vigente = None
    for r in doc["calendario"]["revisiones"]:
        if instante(r["vigente_desde"]) <= momento:
            vigente = r
    return vigente


def diferencia_con_padre(doc: dict[str, Any], etiqueta: str) -> dict[str, Any]:
    """Que bloques y que parametros cambian respecto al padre (el ANCLA no tiene padre)."""
    v = version(doc, etiqueta)
    if v is None:
        return {"version": etiqueta, "disponible": False, "motivo": "no existe en el reglamento"}
    padre = version(doc, v["padre"]) if v.get("padre") else None
    if padre is None:
        return {"version": etiqueta, "padre": None, "motivo": "es el ANCLA: no tiene padre"}
    bloques: dict[str, Any] = {}
    for nombre in BLOQUES:
        antes = contenido_bloque(padre["bloques"][nombre])["parametros"]
        despues = contenido_bloque(v["bloques"][nombre])["parametros"]
        cambios = {
            p: {"antes": antes.get(p), "despues": despues.get(p)}
            for p in sorted(set(antes) | set(despues))
            if antes.get(p) != despues.get(p)
        }
        bloques[nombre] = {
            "huella_padre": padre["huellas"][nombre],
            "huella": v["huellas"][nombre],
            "cambia": bool(cambios),
            "parametros": cambios,
        }
    return {"version": etiqueta, "padre": padre["version"], "bloques": bloques}


def registros_esperados(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Las filas que entrada_reglamento tiene que guardar para este fichero, en su orden."""
    filas: list[dict[str, Any]] = []
    for v in doc["versiones"]:
        for nombre in BLOQUES:
            filas.append(
                {
                    "etiqueta": v["version"],
                    "bloque": nombre,
                    "huella": huella_bloque(v["bloques"][nombre]),
                    "contenido": contenido_bloque(v["bloques"][nombre]),
                }
            )
    for r in doc["calendario"]["revisiones"]:
        filas.append(
            {
                "etiqueta": r["revision"],
                "bloque": BLOQUE_CALENDARIO_DATOS,
                "huella": huella_revision(r),
                "contenido": contenido_revision(r),
            }
        )
    return filas


# --------------------------------------------------------------------------- linea de ordenes


def _rellena_huellas(doc: dict[str, Any]) -> list[str]:
    """Rellena SOLO las huellas vacias. Nunca reescribe una declarada: eso seria lavar un cambio."""
    hechas: list[str] = []
    for v in doc["versiones"]:
        declaradas = v.setdefault("huellas", {})
        for nombre in BLOQUES:
            if not declaradas.get(nombre):
                declaradas[nombre] = huella_bloque(v["bloques"][nombre])
                hechas.append(f"{v['version']}.{nombre}")
    for r in doc["calendario"]["revisiones"]:
        if not r.get("huella"):
            r["huella"] = huella_revision(r)
            hechas.append(f"{r['revision']}")
    return hechas


def formatea(valor: Any, sangria: int = 0, prefijo: int = 0, ancho: int = 118) -> str:
    """JSON legible: en una linea lo que cabe, desplegado lo que no. La huella no depende de esto."""
    compacto = json.dumps(valor, ensure_ascii=False)
    if not isinstance(valor, (dict, list)) or not valor or sangria + prefijo + len(compacto) <= ancho:
        return compacto
    pad = " " * (sangria + 2)
    if isinstance(valor, dict):
        partes = []
        for k, v in valor.items():
            clave = json.dumps(k, ensure_ascii=False) + ": "
            partes.append(pad + clave + formatea(v, sangria + 2, len(clave), ancho))
        return "{\n" + ",\n".join(partes) + "\n" + " " * sangria + "}"
    partes = [pad + formatea(v, sangria + 2, 0, ancho) for v in valor]
    return "[\n" + ",\n".join(partes) + "\n" + " " * sangria + "]"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Valida el reglamento y calcula sus huellas.")
    parser.add_argument("--ruta", default=str(RUTA))
    parser.add_argument(
        "--rellena",
        action="store_true",
        help="escribe las huellas VACIAS (version o revision nuevas); no toca una declarada",
    )
    parser.add_argument("--registros", action="store_true", help="imprime etiqueta|bloque|huella")
    args = parser.parse_args(argv)
    doc = cargar(args.ruta)
    if args.rellena:
        hechas = _rellena_huellas(doc)
        Path(args.ruta).write_text(formatea(doc) + "\n", encoding="utf-8")
        print("huellas rellenadas: " + (", ".join(hechas) if hechas else "ninguna"))
    errores = validar(doc)
    if args.registros and not errores:
        for fila in registros_esperados(doc):
            print(f"{fila['etiqueta']}|{fila['bloque']}|{fila['huella']}")
    for e in errores:
        print(f"ERROR {e}", file=sys.stderr)
    return 1 if errores else 0


if __name__ == "__main__":
    raise SystemExit(main())
