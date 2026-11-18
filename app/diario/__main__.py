"""python -m app.diario [--dir D] [--ahora T] [--sin-red] [--sin-entrega] cuarto|diario

  cuarto  (cada 15 min, coinalyze-diario-cuarto.timer): velas de 140 a la cache; resuelve lo sellado; evalua las reglas
          congeladas en la barra recien cerrada; sella o rechaza el buzon de Fable.
  diario  (00:05Z, coinalyze-diario-dia.timer): velas; la rejilla del dia cerrado; el marcador a <D>/marcador.txt y, si
          no se dice --sin-entrega, a 140 (BOT_INFORMES/diario-entradas.txt) por el mismo camino que el informe semanal
          (tools/bot/semanal.py: harness/bin/prod + sha256 de vuelta).
El libro (<D>/entradas.jsonl) se VERIFICA antes de escribir: tocado, no se escribe nada y sale con rc 2. Lo que no se
pudo hacer (canal caido, hueco de velas) va a <D>/estado.json y al marcador; un canal caido no es un dato.
--ahora planta el reloj (s Unix), SOLO con DIARIO_PRUEBA=1 en el entorno (sin ella, rc 2): con --sin-red sirve para
rehacer una corrida sobre la cache en una carpeta de prueba. El libro rechaza ademas un sello anterior a su ultima linea.
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
from app.diario import publico as pb
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


def huecos_abiertos(filas: list, v5: dict, ahora: int) -> dict[str, list[int]]:
    """{activo: [inicio de la vela que falta]} de las propuestas sin resultado (sin escribir nada)."""
    props, res = mc.operaciones(filas)
    out: dict[str, list[int]] = {}
    for i, p in props.items():
        if i not in res:
            r = rs.resuelve(p, v5.get(p["activo"], {}), ahora)
            if r["estado"] == "pendiente" and r["hueco"] is not None:
                out.setdefault(p["activo"], []).append(r["hueco"])
    return out


def con_publico(carpeta: str, filas: list, v5: dict, ahora: int, red: bool, errores: list, est: dict) -> tuple[dict, dict]:
    """Las velas de 140 con los huecos tapados por el volcado publico (manda 140), y los inicios publicos por activo.
    Con red, pide los dias que hagan falta; un hueco que cruza dias destapa el siguiente: hasta 5 vueltas."""
    P = pb.Publico(carpeta)
    for _ in range(5 if red else 0):
        mezcla = {a: {**P.lee(a), **v5.get(a, {})} for a in vl.ACTIVOS}
        fallos = est.setdefault("publico_fallos", [])
        nuevos = {a: P.rellena(a, ts, ahora, errores, fallos) for a, ts in huecos_abiertos(filas, mezcla, ahora).items()}
        nuevos = {a: d for a, d in nuevos.items() if d}
        if not nuevos:
            break
        for a, d in nuevos.items():
            est.setdefault("publico", {}).setdefault(a, []).extend(d)
    v5p, publicas = {}, {}
    for a in vl.ACTIVOS:
        pub = P.lee(a)
        v5p[a] = {**pub, **v5.get(a, {})}
        publicas[a] = set(pub) - set(v5.get(a, {}))
    return v5p, publicas


def resuelve_todo(L: lb.Libro, filas: list, v5: dict, ahora: int, publicas: dict | None = None) -> tuple[int, list]:
    props, res = mc.operaciones(filas)
    n, huecos = 0, []
    for i, p in props.items():
        if i in res:
            continue
        r = rs.resuelve(p, v5.get(p["activo"], {}), ahora, (publicas or {}).get(p["activo"], frozenset()))
        if r["estado"] == "resuelta":
            L.anade("resultado", r["resultado"], ahora)
            n += 1
        elif r["hueco"] is not None:
            ind = rs.indecidible(p, r["hueco"], ahora)
            if ind:
                L.anade("resultado", ind, ahora)
                n += 1
            else:
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
    malos = lb.verifica(ruta, lb.cabezas(carpeta)) if os.path.exists(ruta) or lb.cabezas(carpeta) else []
    if malos:
        return {"rc": 2, "libro_tocado": malos[:5]}
    L, errores = lb.Libro(ruta), []
    v5, v4 = refresca(vl.Cache(carpeta), ahora, red, errores)
    filas = L.lee()
    vistos = {f["id"] for f in filas if f["tipo"] in ("propuesta", "rechazo")}
    est = {"orden": orden, "ahora": ahora, "errores": errores}
    v5r, publicas = con_publico(carpeta, filas, v5, ahora, red, errores, est)
    resueltas, huecos = resuelve_todo(L, filas, v5r, ahora, publicas)
    est.update(resueltas=resueltas, huecos=huecos)
    if orden == "cuarto":
        props, res = mc.operaciones(L.lee())
        abiertas = {(p["fuente"][6:], p["activo"]) for i, p in props.items() if p["fuente"].startswith("regla:") and i not in res}
        ps, est["notas"] = fu.reglas(v4, ahora, abiertas)
        est["reglas"] = sella(L, ps, v5, ahora, vistos)
        precios = {a: fu.precio(v5.get(a, {}), ahora) for a in vl.ACTIVOS}
        est["buzon"] = fu.sella_buzon(L, os.path.join(carpeta, "buzon"), precios, ahora, vistos)
    else:
        est["rejilla_errores"] = []
        est["rejilla"] = sella(L, fu.rejilla(v4, ahora, est["rejilla_errores"]), v5, ahora, vistos)
        t = mc.texto(L.lee(), L.cabeza(), ahora, huecos)
        for e in est["rejilla_errores"]:
            t += f"\nERROR {e}"
        if errores:
            t += f"\nCANAL: {len(errores)} lecturas de 140 fallaron hoy ({errores[0][:80]})"
        errores.extend(est["rejilla_errores"])  # despues de CANAL, que cuenta solo lecturas de 140; rc 1
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
    if orden == "diario":
        lb.guarda_cabeza(carpeta, est["cabeza"], ahora)
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
    if argv[:2] == ["publico", "compara"] and len(argv) == 4:  # publico compara ACT AAAA-MM-DD (lee 140 y el volcado)
        from datetime import UTC, datetime
        d = int(datetime.strptime(argv[3], "%Y-%m-%d").replace(tzinfo=UTC).timestamp())
        print(json.dumps(pb.compara(argv[2], d, vl.pide(argv[2], "5min", 2000))))
        return 0
    ap = argparse.ArgumentParser(prog="python -m app.diario")
    ap.add_argument("orden", choices=("cuarto", "diario"))
    ap.add_argument("--dir", default=DIR)
    ap.add_argument("--ahora", type=int, default=None)
    ap.add_argument("--sin-red", action="store_true")
    ap.add_argument("--sin-entrega", action="store_true")
    a = ap.parse_args(argv)
    if a.ahora is not None and os.environ.get("DIARIO_PRUEBA") != "1":
        print("--ahora solo con DIARIO_PRUEBA=1: el diario en vivo sella con el reloj", file=sys.stderr)
        return 2
    os.makedirs(a.dir, exist_ok=True)
    est = corre(a.orden, a.dir, a.ahora or int(time.time()), not a.sin_red, not a.sin_entrega)
    print(json.dumps({k: v for k, v in est.items() if k != "notas"}, separators=(",", ":"))[:2000])
    return est["rc"]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
