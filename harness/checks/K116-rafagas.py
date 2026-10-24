"""K116 · el juicio: la prueba de las rafagas recalculada sobre la muestra fija contra la de la entrega.

Lo llama K116-las-rafagas.sh con K116_REPO, K116_MUESTRA y K116_ESPERADO. Sale con 0 VERDE, 1 ROJO, 2 NO MEDIDO.
"""

import json
import os
import sys
from pathlib import Path

REPO = Path(os.environ["K116_REPO"]).resolve()
MUESTRA = Path(os.environ["K116_MUESTRA"])
ESPERADO = Path(os.environ["K116_ESPERADO"])


def hojas(a, b, ruta=""):
    """(ruta, a, b) de cada hoja distinta entre dos arboles de dict."""
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            yield from hojas(a.get(k), b.get(k), f"{ruta}.{k}" if ruta else k)
    elif a != b:
        yield ruta, a, b


def diferencias(esp: dict, r: dict) -> list[str]:
    d = [f"umbral movido: {k} {esp['umbrales'].get(k)} -> {r['umbrales'].get(k)}"
         for k in sorted(set(esp["umbrales"]) | set(r["umbrales"]))
         if esp["umbrales"].get(k) != r["umbrales"].get(k)]
    for v in ("sin_liq", "con_liq"):
        e = {(x[0], x[1]): x for x in esp[v]["eventos"]}
        o = {(x[0], x[1]): x for x in r[v]["eventos"]}
        d += [f"falta la rafaga {s} {t} ({e[s, t][3]}) [{v}]" for s, t in sorted(e.keys() - o.keys())]
        d += [f"rafaga de mas {s} {t} ({o[s, t][3]}) [{v}]" for s, t in sorted(o.keys() - e.keys())]
        for k in sorted(e.keys() & o.keys()):
            if e[k][3] != o[k][3]:
                d.append(f"clase cambiada {k[0]} {k[1]}: {e[k][3]} -> {o[k][3]} [{v}]")
            elif e[k] != o[k]:
                d.append(f"decision cambiada {k[0]} {k[1]}: {e[k][2:]} -> {o[k][2:]} [{v}]")
        for ce, co in zip(esp[v]["control"], r[v]["control"], strict=True):
            if ce != co:
                d.append(f"control {ce['control']} [{v}]: visto {ce['visto']} -> {co['visto']}, eventos "
                         f"{ce['eventos']} -> {co['eventos']}")
        d += [f"tabla {v}.{p}: {a} -> {b}" for p, a, b in hojas(esp[v]["tablas"], r[v]["tablas"])]
    d += [f"{k}: {esp.get(k)} -> {r.get(k)}" for k in ("prueba", "quitado", "dias", "equilibrio")
          if esp.get(k) != r.get(k)]
    return d


def main() -> int:
    if not MUESTRA.is_file():
        print(f"NO MEDIDO: K116 sin la muestra {MUESTRA}")
        return 2
    if not ESPERADO.is_file():
        print(f"NO MEDIDO: K116 sin la salida de la entrega {ESPERADO}")
        return 2
    sys.path.insert(0, str(REPO))
    import app.rafagas as rf
    from scripts import rafagas_estudio as es

    for m in (rf, es):
        if not Path(m.__file__).resolve().is_relative_to(REPO):
            print(f"NO MEDIDO: K116 importo {m.__file__}, que no es del arbol {REPO}")
            return 2
    esp = json.loads(ESPERADO.read_text(encoding="ascii"))
    h = es.huella(MUESTRA)
    if h != esp["huella"]:
        print(f"ROJO  K116 la muestra no es la de la entrega: huella {h[:16]}, la entrega dice {esp['huella'][:16]}")
        return 1
    r = json.loads(es._json(es.prueba(es.carga(MUESTRA))))
    d = diferencias(esp, r)
    if d:
        print(f"ROJO  K116 {d[0]}")
        for x in d[1:20]:
            print(f"   - {x}")
        if len(d) > 20:
            print(f"   - ... y {len(d) - 20} diferencias mas")
        return 1
    # los controles van delante: verify cita 70 caracteres, y un control que no se ve no puede quedar fuera
    n = {v: len(r[v]["eventos"]) for v in ("sin_liq", "con_liq")}
    vistos = [c["visto"] for v in ("sin_liq", "con_liq") for c in r[v]["control"]]
    ctl = "controles del 10-20 VISTOS" if all(vistos) else f"controles del 10-20 vistos {sum(vistos)} de {len(vistos)}"
    print(f"VERDE  K116 · {ctl} · la muestra {h[:12]} da los {n['sin_liq']} eventos sin liquidaciones y "
          f"{n['con_liq']} con ellas, sus clases y las tablas de la entrega ({r['prueba'][0]}..{r['prueba'][1]}, "
          f"{r['dias']} dias)")
    for v in ("sin_liq", "con_liq"):
        for c in r[v]["control"]:
            print(f"   - {v} {c['control']} {c['franja'][0]}..{c['franja'][1][11:]}: "
                  f"{'visto' if c['visto'] else 'NO visto'} {c['eventos']}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # un arbol que no importa o revienta no se juzga: rc 3, el guion dice NO MEDIDO
        print(f"{type(exc).__name__}: {exc}")
        sys.exit(3)
