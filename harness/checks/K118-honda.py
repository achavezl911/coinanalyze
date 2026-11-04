"""K118 · el juicio: la capa honda del libro recontada a mano desde la respuesta CRUDA del venue.

Lo llama K118-libro-honda.sh con K118_REPO y K118_MUESTRA. Sale con 0 VERDE, 1 ROJO, 2 NO MEDIDO.

La muestra (json.xz, fuera del repo) trae por foto: venue, activo, ts, la respuesta cruda, el vivo y el precio del
instante, y la fila que el colector GUARDO (o null si no guardo ninguna). El recuento de aqui no usa app/libro_honda:
  un nivel L es [L, L+paso); compra hondo si L < vivo_compra (el vivo no lo ve entero) y L >= el precio mas bajo de la
  foto (la foto si); venta hondo si L+paso > vivo_venta y L+paso <= el mas alto; los dos hasta el nivel que toca el 2 %.
  Un lado solo tiene niveles si su cubo (mcd de las diferencias, y todo precio multiplo) parte el paso Y el venue
  agrupa por suelo o exacto: la venta de merge-depth agrupa (P - c, P] y no parte nunca.
Contra ese recuento: (a) la fila guardada y la que el codigo del arbol recalcula del mismo crudo; (b) un lado que no
parte el paso con niveles es ROJO; (c) servida pasados 75 s de la hora del venue (decision C), con niveles es ROJO; y a
75 s justos, sin ellos tambien (un rancio de mas no puede esconder el arreglo).
"""

import glob
import json
import lzma
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal as D
from pathlib import Path

REPO = Path(os.environ["K118_REPO"]).resolve()
MUESTRA = Path(os.environ["K118_MUESTRA"])
RANCIA_S = 75  # decision C del encargo 151, no la constante del arbol
TOPE = D("0.02")
TECHO = {("bitget_usdt", "a")}  # merge-depth agrupa las ventas por techo (medido el 2026-11-03, 151-A)


def no_medido(m: str) -> None:
    print(f"NO MEDIDO: K118 {m}")
    sys.exit(2)


if not MUESTRA.is_file():
    no_medido(f"sin la muestra {MUESTRA}")
sys.path[:0] = [str(REPO)]
sys.path += glob.glob(str(REPO / ".venv/lib/python3*/site-packages")) or glob.glob(
    "/srv/coinanalyze/repo/.venv/lib/python3*/site-packages")
try:
    import app
    from app import libro_honda as lh
    from app import libro_lectura as lec
    from app.libro import PASOS, VENUES
except Exception as e:  # noqa: BLE001
    no_medido(f"no importo el arbol {REPO}: {type(e).__name__} {e}"[:300])
if Path(app.__file__).resolve().parent != REPO / "app":
    no_medido(f"importo otro arbol: {app.__file__}")


def cubo_de(ps: list[D]) -> D | None:
    exp = min(p.as_tuple().exponent for p in ps)
    ns = sorted({int(p.scaleb(-exp)) for p in ps})
    g = 0
    for a, b in zip(ns, ns[1:], strict=False):
        g = g if b - a == 0 else (b - a if g == 0 else __import__("math").gcd(g, b - a))
    return D(g).scaleb(exp) if g else None


def verdad(c: dict) -> dict:
    """Los dos lados recontados: {lado: (desde, [cantidades], alcance) | None}, y el cubo de cada lado."""
    j = json.loads(c["crudo"], parse_float=D)
    d = j["data"][0] if c["venue"].startswith("okx") else j["data"]
    mult = VENUES[c["venue"]].multiplicador.get(c["activo"], D(1))
    paso, precio = PASOS[c["activo"]], D(c["precio"])
    out, cubos = {}, {}
    for k, clave, vivo in (("b", "bids", D(c["vivo"][0])), ("a", "asks", D(c["vivo"][1]))):
        pq = [(D(str(x[0])), D(str(x[1])) * mult) for x in d[clave]]
        ps = [p for p, _ in pq]
        cb = cubos[k] = cubo_de(ps)
        if not ps or cb is None or (c["venue"], k) in TECHO or paso % cb or any(p % cb for p in ps):
            out[k] = None
            continue
        if k == "b":
            ls = [L for L in (paso * n for n in range(int(min(ps) // paso), int(vivo // paso) + 2))
                  if min(ps) <= L < vivo and L + paso > precio * (1 - TOPE)]
            ls.sort(reverse=True)
        else:
            ls = [L for L in (paso * n for n in range(int(vivo // paso) - 1, int(max(ps) // paso) + 1))
                  if vivo < L + paso <= max(ps) and precio * (1 + TOPE) >= L]
        ls = [L for i, L in enumerate(ls) if not i or abs(L - ls[i - 1]) == paso]  # contiguos desde el borde
        out[k] = (ls[0], [sum((q for p, q in pq if L <= p < L + paso), D(0)) for L in ls],
                  min(ps) if k == "b" else max(ps)) if ls else None
    return {"lados": out, "cubos": cubos}


def lado_de(f: dict | tuple | None, k: str):
    if f is None:
        return None
    if isinstance(f, tuple):
        n, qs, al = (f[10], f[11], f[14]) if k == "b" else (f[12], f[13], f[15])
    else:
        n, qs, al = (f["compra_nivel"], f["compras"], f["alcance_compra"]) if k == "b" else (
            f["venta_nivel"], f["ventas"], f["alcance_venta"])
    return None if n is None else (D(str(n)), [D(str(q)) for q in qs], D(str(al)))


def igual(x, y) -> bool:
    if x is None or y is None:
        return x is y
    return x[0] == y[0] and x[2] == y[2] and len(x[1]) == len(y[1]) and all(a == b for a, b in zip(x[1], y[1], strict=True))


def corto(x) -> str:
    return "nada" if x is None else f"desde {x[0]} x{len(x[1])} {[str(q) for q in x[1][:4]]} alcance {x[2]}"


casos = json.loads(lzma.decompress(MUESTRA.read_bytes()))
mal: list[str] = []
niveles = guardadas = sin_partir = rancias = 0
fuentes = {(f.venue, f.activo): f for f in lh.FUENTES}
for c in casos:
    nom = f"{c['venue']} {c['activo']} ts={c['ts']}"
    fu = fuentes.get((c["venue"], c["activo"]))
    if fu is None:
        mal.append(f"{nom}: la fuente ya no esta en FUENTES")
        continue
    v = verdad(c)
    try:
        foto = lh.parsea(fu, c["crudo"].encode())
        r = lh.fila(fu, foto, c["ts"], (D(c["vivo"][0]), D(c["vivo"][1])), D(c["precio"]), "k118")
    except Exception as e:  # noqa: BLE001
        mal.append(f"{nom}: el codigo del arbol cae al recalcular: {type(e).__name__} {e}"[:200])
        continue
    for k, ln in (("b", "compra"), ("a", "venta")):
        t = v["lados"][k]
        if t is None and v["cubos"][k] is not None:
            sin_partir += 1
        for quien, x in (("guardada", lado_de(c["fila"], k)), ("recalculada por el arbol", lado_de(r, k))):
            if not igual(x, t):
                que = "nivel a medias guardado: el cubo no parte el paso o agrupa por techo" if t is None and x else "escalera distinta"
                mal.append(f"{nom} {ln} {quien}: {que} (cubo {v['cubos'][k]}, paso {PASOS[c['activo']]}): "
                           f"{corto(x)} != recuento {corto(t)}")
        niveles += len(t[1]) if t else 0
    if c["fila"] is None:
        continue
    guardadas += 1
    f = dict(c["fila"])
    for col in ("ts", "ts_libro"):
        f[col] = datetime.fromisoformat(f[col])
    for col in ("paso", "cubo", "precio", "vivo_compra", "vivo_venta", "compra_nivel", "venta_nivel",
                "alcance_compra", "alcance_venta"):
        f[col] = None if f[col] is None else D(f[col])
    for col in ("compras", "ventas"):
        f[col] = None if f[col] is None else [D(q) for q in f[col]]
    try:
        fresca = lec.honda_fila(f, f["ts_libro"] + timedelta(seconds=RANCIA_S))
        vieja = lec.honda_fila(f, f["ts_libro"] + timedelta(seconds=RANCIA_S, milliseconds=1))
        junta = [lh.junta(lado_de(f, k)[:2], k, f["paso"], f["vivo_compra" if k == "b" else "vivo_venta"],
                          f["ts_libro"], f["ts_libro"] + timedelta(seconds=RANCIA_S + 1))
                 for k in ("b", "a") if lado_de(f, k)]
    except Exception as e:  # noqa: BLE001
        mal.append(f"{nom}: servir la fila cae: {type(e).__name__} {e}"[:200])
        continue
    if vieja.get("compras") is not None or vieja.get("ventas") is not None or not vieja.get("rancia"):
        mal.append(f"{nom}: servida a {RANCIA_S}.001 s de la hora del venue CUENTA como conocida (rancia "
                   f"{vieja.get('rancia')}, compras {vieja.get('compras') is not None})")
    elif any(x is not None for x in junta):
        mal.append(f"{nom}: junta() da por conocida una foto de {RANCIA_S + 1} s")
    else:
        rancias += 1
    if fresca.get("rancia") or (fresca.get("compras") is None and fresca.get("ventas") is None):
        mal.append(f"{nom}: a {RANCIA_S} s justos ya se sirve sin niveles: el rancio no es el de la decision C")

if not guardadas or not niveles or not sin_partir:
    no_medido(f"la muestra no ejercita los tres brazos: {guardadas} filas, {niveles} niveles, {sin_partir} lados "
              f"sin partir")
if mal:
    print(f"ROJO: K118 {len(mal)} fallos en {len(casos)} fotos; el primero: {mal[0]}"[:600])
    for m in mal[1:6]:
        print(f"  {m}"[:400])
    sys.exit(1)
print(f"VERDE: K118 {len(casos)} fotos crudas ({guardadas} guardadas): {niveles} niveles iguales al recuento en la "
      f"fila guardada y en la recalculada; {sin_partir} lados que no parten el paso, sin niveles; rancia a "
      f"{RANCIA_S} s sin niveles en las {rancias}")
