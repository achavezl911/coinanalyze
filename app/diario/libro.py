"""EL LIBRO: un fichero JSONL solo-anadir (por defecto /srv/coinanalyze/diario/entradas.jsonl) encadenado por sha256.

Cada linea es un objeto JSON canonico (claves ordenadas, sin espacios, ASCII) que lleva:
  n      su numero (0, 1, 2...)          prev   el sha256 de los BYTES de la linea anterior (sin el \\n); la 0, 64 ceros
  tipo   propuesta | resultado | rechazo  t      la hora de escritura (s Unix)
y los campos de su tipo (ver PROPUESTA, RESULTADO, RECHAZO). Tocar un byte de una linea cambia su hash y rompe el `prev`
de la siguiente; quitar o meter una linea rompe `n` y `prev`. La ULTIMA linea solo la protege una cabeza conocida: el
marcador publica `cabeza` (sha256 de la ultima linea y su n) por el camino del informe, y `verifica(cabeza=...)` la
compara. Se escribe con flock y open('ab'): nunca se reescribe nada.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import time

GENESIS = "0" * 64
TIPOS = ("propuesta", "resultado", "rechazo")
PROPUESTA = ("fuente", "id", "activo", "lado", "orden", "entrada", "stop", "objetivo", "caduca", "plazo_s", "riesgo_usd",
             "sello", "porque")
RESULTADO = ("id", "llenada", "px_llenado", "t_llenado", "salida", "px_salida", "t_salida", "r_neto", "usd_neto", "coste")
RECHAZO = ("fuente", "id", "motivo", "cruda", "sello")
CAMPOS = {"propuesta": PROPUESTA, "resultado": RESULTADO, "rechazo": RECHAZO}


def canon(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def huella(linea: bytes) -> str:
    return hashlib.sha256(linea).hexdigest()


def _ultima(ruta: str) -> tuple[int, str]:
    """(n de la proxima linea, prev para ella) leyendo solo la cola del fichero."""
    if not os.path.exists(ruta) or os.path.getsize(ruta) == 0:
        return 0, GENESIS
    with open(ruta, "rb") as f:
        f.seek(0, 2)
        fin = f.tell()
        paso = 4096
        while True:
            ini = max(0, fin - paso)
            f.seek(ini)
            cola = f.read(fin - ini)
            lineas = cola.rstrip(b"\n").split(b"\n")
            if len(lineas) > 1 or ini == 0:
                ult = lineas[-1]
                return json.loads(ult)["n"] + 1, huella(ult)
            paso *= 4


class Libro:
    def __init__(self, ruta: str):
        self.ruta = ruta

    def anade(self, tipo: str, campos: dict, ahora: int | None = None) -> dict:
        """Anade UNA linea y la devuelve. Falla (sin escribir) si al tipo le falta un campo."""
        if tipo not in TIPOS:
            raise ValueError(f"tipo desconocido: {tipo}")
        falta = [c for c in CAMPOS[tipo] if c not in campos]
        if falta:
            raise ValueError(f"a la linea {tipo} le faltan {falta}")
        os.makedirs(os.path.dirname(os.path.abspath(self.ruta)), exist_ok=True)
        with open(self.ruta + ".lock", "a") as cerrojo:
            fcntl.flock(cerrojo, fcntl.LOCK_EX)
            n, prev = _ultima(self.ruta)
            obj = {**campos, "n": n, "prev": prev, "tipo": tipo, "t": int(time.time() if ahora is None else ahora)}
            with open(self.ruta, "ab") as f:
                f.write(canon(obj) + b"\n")
                f.flush()
                os.fsync(f.fileno())
        return obj

    def lee(self) -> list[dict]:
        """Todas las lineas, SOLO si la cadena esta intacta (si no, ValueError con los problemas)."""
        problemas = verifica(self.ruta)
        if problemas:
            raise ValueError("libro tocado: " + "; ".join(problemas[:5]))
        if not os.path.exists(self.ruta):
            return []
        with open(self.ruta, "rb") as f:
            return [json.loads(x) for x in f.read().splitlines()]

    def cabeza(self) -> dict:
        n, prev = _ultima(self.ruta)
        return {"n": n - 1, "sha256": prev}


def verifica(ruta: str, cabeza: dict | None = None) -> list[str]:
    """Los problemas de la cadena (lista vacia = intacta). cabeza={'n','sha256'} comprueba tambien la ultima linea."""
    if not os.path.exists(ruta):
        return [] if not cabeza or cabeza.get("n", -1) < 0 else ["el libro no existe y la cabeza dice que si"]
    with open(ruta, "rb") as f:
        datos = f.read()
    if datos and not datos.endswith(b"\n"):
        return ["la ultima linea no acaba en salto de linea (escritura cortada o tocada)"]
    out, prev, ids, resueltas = [], GENESIS, set(), set()
    lineas = datos.splitlines()
    for k, ln in enumerate(lineas):
        try:
            o = json.loads(ln)
        except ValueError:
            out.append(f"linea {k}: no es JSON")
            prev = huella(ln)
            continue
        if canon(o) != ln:
            out.append(f"linea {k}: no es canonica (reescrita)")
        if o.get("n") != k:
            out.append(f"linea {k}: n={o.get('n')} (falta o sobra una linea)")
        if o.get("prev") != prev:
            out.append(f"linea {k}: prev no es el sha256 de la linea {k - 1} (la {k - 1} se toco, o se quito/metio una)")
        tipo = o.get("tipo")
        if tipo not in TIPOS:
            out.append(f"linea {k}: tipo {tipo!r}")
        elif tipo == "propuesta":
            if o.get("id") in ids:
                out.append(f"linea {k}: propuesta {o.get('id')} repetida")
            ids.add(o.get("id"))
        elif tipo == "resultado":
            if o.get("id") not in ids:
                out.append(f"linea {k}: resultado de {o.get('id')} sin propuesta antes")
            if o.get("id") in resueltas:
                out.append(f"linea {k}: segundo resultado de {o.get('id')}")
            resueltas.add(o.get("id"))
        prev = huella(ln)
    if cabeza is not None and (cabeza.get("n") != len(lineas) - 1
                               or cabeza.get("sha256") != (prev if lineas else GENESIS)):
        out.append(f"la cabeza publicada (n={cabeza.get('n')}) no es la del libro (n={len(lineas) - 1}): "
                   "se toco, quito o anadio la cola")
    return out
