#!/usr/bin/env python3
"""Ayudante de K105 · juzga el REGISTRO DE ENTRADAS con lo que el guion reunio en un directorio.

No toca ninguna base: lee ficheros. Usa el cargador del reglamento (app/entradas/reglamento.py) y
la validacion de la foto (app/entradas/foto.py) del arbol que lo invoca.

Brazos (campana 135, C5):
  a  el reglamento registrado es el del release, huella a huella, y todo lo registrado sigue en el
     fichero (codigo incluido); cada contenido es su huella
  b  append-only por CATALOGO: BEFORE UPDATE OR DELETE (fila) y BEFORE TRUNCATE (sentencia),
     activos, con la funcion que lanza; y el BEFORE INSERT que pone la hora y el tope
  c  todo DISPARADO y toda SOMBRA traen lo de C3; ningun DISPARADO sin la pata spot (MC12)
  d  ningun insumo de la foto posterior a su registro; ningun retraso sobre el tope; y como DATO,
     cuantas velas de la foto se compararon con las asentadas y cuantas difieren
  e  uno vivo por clave (zonas que se solapan cuentan como la misma clave)
  f  el calendario vigente cubre ahora + la caducidad maxima; la etiqueta de evento sale del
     calendario de SU registro; ningun evento anterior a su revision; y la retencion del ohlcv
     1min de 140 >= caducidad maxima + 7 dias de gracia (signal_outcomes)

Salida: lineas de veredicto; rc 0 VERDE, 1 ROJO, 2 NO MEDIDO. Con cero DISPARADOS y SOMBRAS
en la ventana se juzgan a, b, e y f, y c y d salen NO MEDIDO: nunca VERDE.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

GRACIA_DIAS = 7  # MISSING_DATA_FINAL_GRACE, app/signal_outcomes.py:22
TABLAS = ("entrada_reglamento", "entrada_registro", "entrada_latido")
FILA, ANTES, INSERT, DELETE, UPDATE, TRUNCATE = 1, 2, 4, 8, 16, 32


def _carga(directorio: Path, nombre: str, defecto=None):
    ruta = directorio / nombre
    if not ruta.exists() or not ruta.read_text(encoding="utf-8").strip():
        return defecto
    return json.loads(ruta.read_text(encoding="utf-8"))


def _instante(texto) -> datetime:
    momento = datetime.fromisoformat(str(texto).replace("Z", "+00:00"))
    return momento if momento.tzinfo else momento.replace(tzinfo=UTC)


def _zona(clave: str) -> tuple[float, float] | None:
    partes = clave.split(":")
    if len(partes) != 3 or partes[0] != "zona":
        return None
    try:
        return float(partes[1]), float(partes[2])
    except ValueError:
        return None


def brazo_a(R, doc, codigo, registradas, usados) -> list[str]:
    errores = [f"el reglamento del release no valida: {e}" for e in R.validar(doc)][:5]
    if errores:
        return errores
    esperadas = {(f["etiqueta"], f["bloque"]): f["huella"] for f in R.registros_esperados(doc)}
    for etiqueta, h in (codigo or {}).get("versiones", {}).items():
        esperadas[(etiqueta, "codigo")] = h
    en_base = {(r["etiqueta"], r["bloque"]): r for r in registradas}
    for v in R.versiones_en_curso(doc):
        for bloque in R.BLOQUES:
            fila = en_base.get((v["version"], bloque))
            if fila is None:
                errores.append(f"{v['version']}.{bloque} en curso y SIN REGISTRAR en la base")
            elif fila["huella"] != v["huellas"][bloque]:
                errores.append(f"{v['version']}.{bloque} registrado con otra huella")
    for (etiqueta, bloque), fila in en_base.items():
        if (etiqueta, bloque) not in esperadas:
            errores.append(f"{etiqueta}.{bloque} registrado y AUSENTE del fichero del release")
        elif esperadas[(etiqueta, bloque)] != fila["huella"]:
            errores.append(f"{etiqueta}.{bloque} registrado con huella distinta a la del fichero")
        if bloque != "codigo":
            from hashlib import sha256

            if sha256(fila["contenido"].encode("utf-8")).hexdigest() != fila["huella"]:
                errores.append(f"{etiqueta}.{bloque}: su contenido no es su huella")
    for version in sorted(usados):
        if (version, "codigo") not in en_base:
            errores.append(f"codigo {version} usado en el registro y sin registrar")
    return errores


def brazo_b(disparadores) -> list[str]:
    errores = []
    for tabla in TABLAS:
        propios = [d for d in disparadores if d["tabla"] == tabla]
        activos = [d for d in propios if d["activo"] in ("O", "A")]
        lanza = [d for d in activos if "append-only" in d["fuente"] and "RAISE EXCEPTION" in d["fuente"]]
        fila_ud = [d for d in lanza if d["tipo"] & ANTES and d["tipo"] & FILA
                   and d["tipo"] & UPDATE and d["tipo"] & DELETE]
        truncate = [d for d in lanza if d["tipo"] & ANTES and not d["tipo"] & FILA
                    and d["tipo"] & TRUNCATE]
        if not fila_ud:
            apagados = [d["nombre"] for d in propios if d["activo"] not in ("O", "A")]
            errores.append(f"{tabla}: sin BEFORE UPDATE OR DELETE activo que lance"
                           + (f" (desactivados: {', '.join(apagados)})" if apagados else ""))
        if not truncate:
            errores.append(f"{tabla}: sin BEFORE TRUNCATE activo que lance")
    hora = [d for d in disparadores if d["tabla"] == "entrada_registro" and d["activo"] in ("O", "A")
            and d["tipo"] & ANTES and d["tipo"] & FILA and d["tipo"] & INSERT]
    if not any("clock_timestamp" in d["fuente"] and "EN001" in d["fuente"] and "EN002" in d["fuente"]
               for d in hora):
        errores.append("entrada_registro: sin BEFORE INSERT activo que ponga la hora de la base y "
                       "rechace el DISPARADO tardio y los dos vivos")
    return errores


def brazos_cd(F, filas) -> tuple[list[str], list[str]]:
    c, d = [], []
    for fila in filas:
        for e in F.validar_fila(fila):
            destino = d if ("POSTERIOR" in e or "retraso" in e) else c
            destino.append(f"registro {fila['registro_id']} ({fila['estado']} {fila['symbol']}): {e}")
    return c, d


def brazo_e(disparados, abiertos) -> list[str]:
    errores = []
    grupos: dict[tuple, list[dict]] = {}
    for fila in disparados + abiertos:
        grupos.setdefault(
            (fila["version"], fila["symbol"], fila["familia"], fila["perfil"], fila["lado"]), []
        ).append(fila)
    for grupo, filas in grupos.items():
        for i, a in enumerate(filas):
            for b in filas[i + 1:]:
                if a["episodio"] == b["episodio"]:
                    continue
                za, zb = _zona(a["clave"]), _zona(b["clave"])
                misma = a["clave"] == b["clave"] or (
                    za and zb and za[0] <= zb[1] and zb[0] <= za[1]
                )
                if not misma:
                    continue
                fin_a = _instante(a["caduca_en"]) if a.get("caduca_en") else datetime.max.replace(tzinfo=UTC)
                fin_b = _instante(b["caduca_en"]) if b.get("caduca_en") else datetime.max.replace(tzinfo=UTC)
                if _instante(a["vela_cierre"]) < fin_b and _instante(b["vela_cierre"]) < fin_a:
                    errores.append(f"dos vivos en la clave {'/'.join(grupo)}: {a['clave']} "
                                   f"({a['estado']}) y {b['clave']} ({b['estado']})")
    return errores


def brazo_f(R, doc, filas, ahora: datetime, retencion_dias, calendarios_base) -> list[str]:
    errores = []
    revisiones = {r["revision"]: r for r in doc["calendario"]["revisiones"]}
    vigente = R.revision_vigente(doc, ahora)
    caducidad = max(
        max(R.valores(v["bloques"]["comun"])["caducidad_min"].values())
        for v in R.versiones_en_curso(doc)
    )
    if vigente is None:
        errores.append("no hay revision de calendario vigente")
    else:
        hasta = R.instante(vigente["cubre_hasta"])
        if hasta < ahora + timedelta(minutes=caducidad):
            errores.append(f"el calendario vigente ({vigente['revision']}) cubre hasta "
                           f"{vigente['cubre_hasta']} y hace falta ahora + {caducidad} min "
                           f"({(ahora + timedelta(minutes=caducidad)).strftime('%Y-%m-%dT%H:%MZ')})")
    origenes = [("registrado", c) for c in calendarios_base] + [
        ("en el fichero", r) for r in doc["calendario"]["revisiones"]
    ]
    for donde, contenido in origenes:
        desde = R.instante(contenido["vigente_desde"])
        for e in contenido.get("eventos", []):
            if R.instante(e["hora_utc"]) < desde:
                errores.append(f"evento {e['clave']} {donde} con hora {e['hora_utc']} anterior a "
                               f"la revision que lo trae ({contenido['vigente_desde']})")
    for fila in filas:
        foto = json.loads(fila["foto"]) if isinstance(fila["foto"], str) else fila["foto"]
        cal = foto.get("calendario") or {}
        etiquetas = (foto.get("decision") or {}).get("etiquetas") or []
        if not ({"evento", "calendario sin cubrir"} & set(etiquetas)):
            continue
        rev = revisiones.get(cal.get("revision"))
        if rev is None or (foto.get("huellas") or {}).get("calendario_datos") != rev["huella"]:
            errores.append(f"registro {fila['registro_id']}: su etiqueta de calendario no sale del "
                           f"calendario de su registro ({cal.get('revision')})")
    if retencion_dias is None:
        errores.append("HARD_DATA_RETENTION_DAYS de 140 sin leer")
    elif retencion_dias * 1440 < caducidad + GRACIA_DIAS * 1440:
        errores.append(f"HARD_DATA_RETENTION_DAYS={retencion_dias} < caducidad maxima "
                       f"({caducidad} min) + {GRACIA_DIAS} dias de gracia")
    return errores


def main() -> int:
    directorio = Path(sys.argv[1])
    repo = Path(sys.argv[2])
    sys.path.insert(0, str(repo))
    from app.entradas import foto as F
    from app.entradas import reglamento as R

    sujeto = (directorio / "sujeto").read_text(encoding="utf-8").strip()
    doc = _carga(directorio, "reglamento.json")
    codigo = _carga(directorio, "codigo.json", {})
    registradas = _carga(directorio, "registradas.json", [])
    disparadores = _carga(directorio, "disparadores.json", [])
    filas = _carga(directorio, "filas.json", [])
    vivos = _carga(directorio, "vivos.json", [])
    abiertos = _carga(directorio, "abiertos.json", [])
    usados = set(_carga(directorio, "codigos_usados.json", []))
    velas = _carga(directorio, "velas.json", {"comparadas": 0, "difieren": 0})
    ahora = _instante((directorio / "ahora").read_text(encoding="utf-8").strip())
    retencion = (directorio / "retencion").read_text(encoding="utf-8").strip()
    retencion_dias = int(retencion) if retencion.isdigit() else None
    ventana = (directorio / "ventana_dias").read_text(encoding="utf-8").strip()
    calendarios_base = [json.loads(r["contenido"]) for r in registradas
                        if r["bloque"] == R.BLOQUE_CALENDARIO_DATOS]

    if doc is None:
        print(f"ROJO  el release no trae config/entradas/reglamento.json (juzgado: {sujeto})")
        return 1
    def juzga(funcion, *args):
        try:
            return funcion(*args)
        except Exception as exc:  # noqa: BLE001 - un brazo que no se puede juzgar condena
            return [f"no se pudo juzgar: {type(exc).__name__}: {exc}"]

    resultado = {
        "a": juzga(brazo_a, R, doc, codigo, registradas, usados),
        "b": juzga(brazo_b, disparadores),
        "e": juzga(brazo_e, vivos, abiertos),
        "f": juzga(brazo_f, R, doc, filas, ahora, retencion_dias, calendarios_base),
    }
    try:
        c, d = brazos_cd(F, filas)
    except Exception as exc:  # noqa: BLE001
        c, d = [f"no se pudo juzgar: {type(exc).__name__}: {exc}"], []
    hay = len(filas)
    resultado["c"], resultado["d"] = c, d
    rojos = [k for k in "abcdef" if resultado[k]]
    nombres = {"a": "reglamento", "b": "append-only", "c": "foto", "d": "futuro",
               "e": "uno_vivo", "f": "calendario"}
    if rojos:
        primero = rojos[0]
        print(f"ROJO  K105 {primero} ({nombres[primero]}): {resultado[primero][0]} "
              f"(juzgado: {sujeto})")
    elif hay == 0:
        print(f"NO MEDIDO: a b e f VERDE; c d sin DISPARADOS ni SOMBRAS en {ventana} dias "
              f"(juzgado: {sujeto})")
    else:
        print(f"VERDE {hay} DISPARADOS y SOMBRAS con su foto, reglamento registrado = release, "
              f"append-only por catalogo, calendario cubierto (juzgado: {sujeto})")
    for k in "abcdef":
        estado = "ROJO" if resultado[k] else ("NO MEDIDO" if k in "cd" and hay == 0 else "VERDE")
        print(f"  {k} {nombres[k]:12s} {estado} · {len(resultado[k])} fallo(s)"
              + (f" · {resultado[k][0]}" if resultado[k] else ""))
        for e in resultado[k][1:4]:
            print(f"      {e}")
    print(f"  dato  velas de la foto comparadas con las asentadas: {velas['comparadas']}, "
          f"difieren: {velas['difieren']}")
    print(f"  dato  {hay} DISPARADOS y SOMBRAS en {ventana} dias; {len(vivos)} DISPARADOS en el "
          f"registro; {len(abiertos)} VIGILANDO abiertos; {len(registradas)} filas de reglamento")
    if rojos:
        return 1
    return 2 if hay == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
