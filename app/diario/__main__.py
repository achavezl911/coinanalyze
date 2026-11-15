"""python -m app.diario [--dir D] [--ahora T] [--sin-red] [--sin-entrega] cuarto|diario

  cuarto  (cada 15 min, coinalyze-diario-cuarto.timer): velas de 140 a la cache; resuelve lo sellado; evalua las reglas
          congeladas en la barra recien cerrada; sella o rechaza el buzon de Fable.
  diario  (00:05Z, coinalyze-diario-dia.timer): velas; la rejilla del dia cerrado; el marcador a <D>/marcador.txt y, si
          no se dice --sin-entrega, a 140 (BOT_INFORMES/diario-entradas.txt) por el mismo camino que el informe semanal
          (tools/bot/semanal.py: harness/bin/prod + sha256 de vuelta).
El libro (<D>/entradas.jsonl) se VERIFICA antes de escribir: tocado, no se escribe nada y sale con rc 2. Lo que no se
pudo hacer (canal caido, hueco de velas) va a <D>/estado.json y al marcador; un canal caido no es un dato.
--ahora planta el reloj (s Unix): con --sin-red sirve para rehacer una corrida sobre la cache.
python -m app.diario ciego plan|foto|corre ...: el SIMULADOR CIEGO sobre el pasado (ciego.py), en su propia carpeta.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import time

from app.diario import fuentes as fu
from app.diario import libro as lb
from app.diario import marcador as mc
from app.diario import resuelve as rs
from app.diario import velas as vl

DIR = os.environ.get("DIARIO_DIR", "/srv/coinanalyze/diario")


def refresca(cache: vl.Cache, ahora: int, red: bool, errores: list) -> tuple[dict, dict]:
    v5, v4 = {}, {}
    for a in vl.ACTIVOS:
        for iv, lim, dest in (("5min", 2000, v5), ("4hour", 300, v4)):
            nuevas = {}
            if red:
                try:
                    nuevas = vl.pide(a, iv, lim)
                except Exception as e:  # el canal caido se anota y se sigue con la cache
                    errores.append(f"{a} {iv}: {type(e).__name__} {str(e)[:160]}")
            dest[a] = cache.mezcla(a, iv, nuevas, ahora) if nuevas else cache.lee(a, iv)
    return v5, v4


def resuelve_todo(L: lb.Libro, filas: list, v5: dict, ahora: int) -> tuple[int, list]:
    props, res = mc.operaciones(filas)
    n, huecos = 0, []
    for i, p in props.items():
        if i in res:
            continue
        r = rs.resuelve(p, v5.get(p["activo"], {}), ahora)
        if r["estado"] == "resuelta":
            L.anade("resultado", r["resultado"], ahora)
            n += 1
        elif r["hueco"] is not None:
            huecos.append(f"{i} desde {time.strftime('%m-%d %H:%MZ', time.gmtime(r['hueco']))}")
    return n, huecos


def sella(L: lb.Libro, ps: list, v5: dict, ahora: int, vistos: set) -> tuple[int, int]:
    s = r = 0
    for p in ps:
        if p["id"] in vistos:
            continue
        motivo = fu.valida(p, fu.precio(v5.get(p["activo"], {}), ahora), ahora, vistos)
        if motivo:
            L.anade("rechazo", {"fuente": p["fuente"], "id": p["id"], "motivo": motivo, "cruda": None, "sello": ahora}, ahora)
            r += 1
        else:
            L.anade("propuesta", p, ahora)
            s += 1
        vistos.add(p["id"])
    return s, r


def corre(orden: str, carpeta: str, ahora: int, red: bool, entregar: bool) -> dict:
    """Una corrida cada vez (cerrojo en <D>/.corrida): dos a la vez resolverian dos veces la misma propuesta."""
    with open(os.path.join(carpeta, ".corrida"), "w") as cerrojo:
        fcntl.flock(cerrojo, fcntl.LOCK_EX)
        return _corre(orden, carpeta, ahora, red, entregar)


def _corre(orden: str, carpeta: str, ahora: int, red: bool, entregar: bool) -> dict:
    ruta = os.path.join(carpeta, "entradas.jsonl")
    malos = lb.verifica(ruta) if os.path.exists(ruta) else []
    if malos:
        return {"rc": 2, "libro_tocado": malos[:5]}
    L, errores = lb.Libro(ruta), []
    v5, v4 = refresca(vl.Cache(carpeta), ahora, red, errores)
    filas = L.lee()
    vistos = {f["id"] for f in filas if f["tipo"] in ("propuesta", "rechazo")}
    resueltas, huecos = resuelve_todo(L, filas, v5, ahora)
    est = {"orden": orden, "ahora": ahora, "resueltas": resueltas, "huecos": huecos, "errores": errores}
    if orden == "cuarto":
        props, res = mc.operaciones(L.lee())
        abiertas = {(p["fuente"][6:], p["activo"]) for i, p in props.items() if p["fuente"].startswith("regla:") and i not in res}
        ps, est["notas"] = fu.reglas(v4, ahora, abiertas)
        est["reglas"] = sella(L, ps, v5, ahora, vistos)
        precios = {a: fu.precio(v5.get(a, {}), ahora) for a in vl.ACTIVOS}
        est["buzon"] = fu.sella_buzon(L, os.path.join(carpeta, "buzon"), precios, ahora, vistos)
    else:
        est["rejilla"] = sella(L, fu.rejilla(v4, ahora), v5, ahora, vistos)
        t = mc.texto(L.lee(), L.cabeza(), ahora, huecos)
        if errores:
            t += f"\nCANAL: {len(errores)} lecturas de 140 fallaron hoy ({errores[0][:80]})"
        with open(os.path.join(carpeta, "marcador.txt"), "w") as f:
            f.write(t + "\n")
        if entregar:
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                            "tools", "bot"))
            import semanal
            try:
                est["entrega_sha256"] = semanal.entrega("diario-entradas.txt", t + "\n")
            except Exception as e:
                errores.append(f"entrega: {type(e).__name__} {str(e)[:160]}")
    est["cabeza"] = L.cabeza()
    tmp = os.path.join(carpeta, "estado.json.tmp")
    with open(tmp, "w") as f:
        json.dump(est, f, indent=1)
    os.replace(tmp, os.path.join(carpeta, "estado.json"))
    est["rc"] = 1 if errores else 0
    return est


def main(argv: list[str]) -> int:
    if argv and argv[0] == "ciego":
        from app.diario import ciego
        return ciego.main(argv[1:])
    ap = argparse.ArgumentParser(prog="python -m app.diario")
    ap.add_argument("orden", choices=("cuarto", "diario"))
    ap.add_argument("--dir", default=DIR)
    ap.add_argument("--ahora", type=int, default=None)
    ap.add_argument("--sin-red", action="store_true")
    ap.add_argument("--sin-entrega", action="store_true")
    a = ap.parse_args(argv)
    os.makedirs(a.dir, exist_ok=True)
    est = corre(a.orden, a.dir, a.ahora or int(time.time()), not a.sin_red, not a.sin_entrega)
    print(json.dumps({k: v for k, v in est.items() if k != "notas"}, separators=(",", ":"))[:2000])
    return est["rc"]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
