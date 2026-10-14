"""Mide reglas para la PALABRA GRANDE de DECIDE sobre lo que el colector registro (campana 138, C1).

La palabra de UNA evaluacion cambia decenas de veces por hora. Esto simula refrescos de la mesa cada 15 s
sobre la serie entera de scalp_signal_snapshot y, para cada regla candidata, cuenta: cuantas veces por hora
cambiaria la palabra grande, en que fraccion de los refrescos (el criterio de la campana: no mas del 5 % en
cada activo), que fraccion del tiempo diria un lado, que fraccion del tiempo que el INSTANTE pasa en un lado
acaba dicha como ESE lado, y cuanto tarda en decir un lado.

LA SERIE, de 140 y de solo lectura (TODO=1: son ~56k filas y van a un fichero, no a la pantalla):

    TODO=1 sh harness/bin/prodsql "SELECT symbol, to_char(ts AT TIME ZONE 'UTC',
        'YYYY-MM-DD\\"T\\"HH24:MI:SS.US\\"Z\\"'), state, coalesce(book_status, 'NULL')
        FROM scalp_signal_snapshot ORDER BY symbol, ts" > serie.txt

USO:  python scripts/mide_palabra_grande.py serie.txt        el informe
      python scripts/mide_palabra_grande.py --control        la serie de respuesta conocida (rc=0 si da lo que
                                                             tiene que dar; tests/test_mide_palabra_grande.py
                                                             comprueba ademas que tres mutantes la tumban)

Cada evaluacion se clasifica con la MISMA classify_signal_observation del registro, por su estado y su libro.
La cobertura no se registra, pero va dentro del estado (compute_scalp_summary escribe «Sin datos suficientes»
por debajo de 50) y se pasa como 100; la calidad tampoco se registra: es puerta del instante y aqui no se
simula. En cada refresco t lo visible son las evaluaciones con ts <= t; la palabra del instante es la de la
mas reciente, y si esa no es evaluable la grande tampoco.
"""

from __future__ import annotations

import bisect
import random
import statistics
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.signal_ledger import classify_signal_observation  # noqa: E402

L, S, N, E = "LONG", "SHORT", "NO OPERAR", "NO EVALUABLE"
PALABRA = {"long": L, "short": S, "neutral": N}
REFRESCO = 15.0
FRESCURA = 60.0  # la ultima evaluacion con mas de esto: el colector no escribe y la grande no ve
CADENCIA = 13.9  # la del colector, para el minimo de cada ventana (la mitad de lo que cabe)


def palabra(state: str, book: str) -> str:
    _d, direccion, _a = classify_signal_observation(
        {"state": state, "book_status": None if book == "NULL" else book, "evidence_coverage_pct": 100.0}
    )
    return PALABRA.get(direccion, E)


class Serie:
    def __init__(self, ts: list[float], ws: list[str]):
        self.ts, self.ws = ts, ws
        self.cl, self.cs = [0], [0]
        for w in ws:
            self.cl.append(self.cl[-1] + (w == L))
            self.cs.append(self.cs[-1] + (w == S))


# ------------------------------------------------------- las reglas: (serie, ultima visible) -> (palabra, inicio ventana)


def deslizante(ventana: float, umbral: float, estricta: bool = False, minimo: int | None = None):
    minimo = minimo if minimo is not None else int(ventana / CADENCIA / 2)

    def regla(s: Serie, i: int) -> tuple[str, int]:
        lo = bisect.bisect_right(s.ts, s.ts[i] - ventana)
        n, cl, cs = i + 1 - lo, s.cl[i + 1] - s.cl[lo], s.cs[i + 1] - s.cs[lo]
        if n < minimo:
            return E, lo
        for lado, c in ((L, cl), (S, cs)):
            if (c * 2 > n) if estricta else (c >= umbral * n):
                return lado, lo
        return N, lo

    return regla


def bloques(largo: float, umbral: float):
    minimo = int(largo / CADENCIA / 2)

    def regla(s: Serie, i: int) -> tuple[str, int]:
        b = (s.ts[i] // largo) * largo  # el bloque de la ultima esta abierto; el anterior, cerrado
        lo, hi = bisect.bisect_left(s.ts, b - largo), bisect.bisect_left(s.ts, b)
        n, cl, cs = hi - lo, s.cl[hi] - s.cl[lo], s.cs[hi] - s.cs[lo]
        if n < minimo:
            return E, lo
        for lado, c in ((L, cl), (S, cs)):
            if c >= umbral * n:
                return lado, lo
        return N, lo

    return regla


def racha(k: int):
    def regla(s: Serie, i: int) -> tuple[str, int]:
        lo = i - k + 1
        if lo < 0:
            return E, 0
        if len(set(s.ws[lo : i + 1])) == 1 and s.ws[i] in (L, S):
            return s.ws[i], lo
        return N, lo

    return regla


REGLAS = {
    "R1 deslizante 5 min >=60% (ELEGIDA)": deslizante(300, 0.6),
    "R2 deslizante 10 min >=60%": deslizante(600, 0.6),
    "R3 deslizante 5 min >50%": deslizante(300, 0.5, estricta=True),
    "R4 bloques cerrados 5 min >=60%": bloques(300, 0.6),
    "R5 racha de 4": racha(4),
}


def grande(s: Serie, regla, t: float, frescura: float = FRESCURA) -> tuple[str, int, int]:
    """La palabra grande en el refresco t, la ultima evaluacion visible y el inicio de su ventana."""
    i = bisect.bisect_right(s.ts, t) - 1
    if i < 0 or t - s.ts[i] > frescura or s.ws[i] == E:
        return E, i, i
    g, lo = regla(s, i)
    return g, i, lo


def refrescos(s: Serie, regla, desfase: float = 0.0, frescura: float = FRESCURA, cola: float = 0.0):
    out, t = [], s.ts[0] + desfase
    while t <= s.ts[-1] + cola:
        g, i, lo = grande(s, regla, t, frescura)
        out.append((t, g, s.ws[i] if i >= 0 and t - s.ts[i] <= frescura else E, i, lo))
        t += REFRESCO
    return out


def medir(s: Serie, regla, desfase: float = 0.0, frescura: float = FRESCURA) -> dict:
    rs = refrescos(s, regla, desfase, frescura)
    pares = list(zip(rs, rs[1:], strict=False))
    horas = (rs[-1][0] - rs[0][0]) / 3600
    cambios = sum(a[1] != b[1] for a, b in pares)
    inst_lado = [r for r in rs if r[2] in (L, S)]
    gran_lado = [r for r in rs if r[1] in (L, S)]
    # T1 · cuando la grande PASA a un lado X: desde la primera evaluacion de X de la ventana que lo fija
    t1 = [b[0] - s.ts[next(j for j in range(b[4], b[3] + 1) if s.ws[j] == b[1])]
          for a, b in pares if b[1] in (L, S) and a[1] != b[1]]
    # T2 · sin depender de la regla: cada racha CONTINUA de un lado de 2 min o mas, desde su primera evaluacion
    # hasta el primer refresco dentro de ella en que la grande dice ese lado
    instantes = [r[0] for r in rs]
    rachas2, t2 = 0, []
    k = 0
    while k < len(s.ws):
        j = k
        while j + 1 < len(s.ws) and s.ws[j + 1] == s.ws[k] and s.ts[j + 1] - s.ts[j] <= frescura:
            j += 1
        if s.ws[k] in (L, S) and s.ts[j] - s.ts[k] >= 120:
            rachas2 += 1
            q0, q1 = bisect.bisect_left(instantes, s.ts[k]), bisect.bisect_right(instantes, s.ts[j] + REFRESCO)
            hit = next((rs[q][0] for q in range(q0, q1) if rs[q][1] == s.ws[k]), None)
            if hit is not None:
                t2.append(hit - s.ts[k])
        k = j + 1

    def mediana(v):
        return statistics.median(v) if v else float("nan")

    return {
        "cambios_h": cambios / horas,
        "pct_refrescos": 100 * cambios / len(pares),
        "pct_lado": 100 * len(gran_lado) / len(rs),
        "inst_pct_lado": 100 * len(inst_lado) / len(rs),
        "pct_dicho": 100 * sum(r[1] == r[2] for r in inst_lado) / len(inst_lado) if inst_lado else float("nan"),
        "pct_acuerdo": 100 * sum(r[1] == r[2] for r in gran_lado) / len(gran_lado) if gran_lado else float("nan"),
        "pct_contra": 100 * sum(r[2] in (L, S) and r[2] != r[1] for r in gran_lado) / len(gran_lado)
        if gran_lado else float("nan"),
        "t1_med": mediana(t1),
        "t1_n": len(t1),
        "rachas2": rachas2,
        "dichas2": len(t2),
        "t2_med": mediana(t2),
        "inst_pct_refrescos": 100 * sum(a[2] != b[2] for a, b in pares) / len(pares),
    }


def por_dia_y_duracion(s: Serie, regla) -> tuple[str, str]:
    rs = refrescos(s, regla)
    dias = defaultdict(lambda: [0, 0])
    episodios, inicio = defaultdict(list), rs[0]
    for a, b in zip(rs, rs[1:], strict=False):
        d = dias[datetime.fromtimestamp(b[0], UTC).strftime("%m-%d")]
        d[0] += 1
        d[1] += a[1] != b[1]
        if a[1] != b[1]:
            episodios[a[1]].append(b[0] - inicio[0])
            inicio = b
    txt_dias = " · ".join(f"{k} {100 * c / n:.2f} % ({n})" for k, (n, c) in sorted(dias.items()))
    txt_dur = " · ".join(f"{w}: {len(v)} ep, mediana {statistics.median(v) / 60:.1f} min, max {max(v) / 60:.0f}"
                         for w, v in sorted(episodios.items()) if len(v) >= 2)
    return txt_dias, txt_dur


def leer(ruta: str) -> dict[str, Serie]:
    por: dict[str, tuple[list[float], list[str]]] = {}
    for linea in Path(ruta).read_text().splitlines():
        if linea:
            sym, ts, state, book = linea.split("|")
            a, b = por.setdefault(sym, ([], []))
            a.append(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp())
            b.append(palabra(state, book))
    return {k: Serie(*v) for k, v in por.items()}


def informe(ruta: str) -> None:
    for sym, s in leer(ruta).items():
        ws = s.ws
        cambia = sum(a != b for a, b in zip(ws, ws[1:], strict=False))
        print(f"\n== {sym} · {len(ws)} evaluaciones en {(s.ts[-1] - s.ts[0]) / 3600:.2f} h · instante: cambia en el "
              f"{100 * cambia / (len(ws) - 1):.1f} % de las evaluaciones seguidas · en un lado el "
              f"{100 * sum(w in (L, S) for w in ws) / len(ws):.1f} % de ellas")
        for nombre, regla in REGLAS.items():
            ms = [medir(s, regla, float(d)) for d in range(0, 15, 3)]
            m = ms[0]
            print(f"   {nombre:<36} {m['cambios_h']:5.2f}/h · {m['pct_refrescos']:5.2f} % de refrescos (peor desfase "
                  f"{max(x['pct_refrescos'] for x in ms):.2f} %) · dice lado {m['pct_lado']:5.1f} % · del instante en "
                  f"un lado ({m['inst_pct_lado']:.1f} %) dicho como ESE lado {m['pct_dicho']:5.1f} % · grande=instante "
                  f"{m['pct_acuerdo']:5.1f} %, contra {m['pct_contra']:4.1f} % · T1 {m['t1_med']:.0f} s ({m['t1_n']}) · "
                  f"T2 {m['dichas2']}/{m['rachas2']} rachas >=2 min, {m['t2_med']:.1f} s")
        for nombre in ("R1 deslizante 5 min >=60% (ELEGIDA)", "R3 deslizante 5 min >50%"):
            dias, dur = por_dia_y_duracion(s, REGLAS[nombre])
            print(f"   {nombre[:3]} por dia UTC: {dias}\n   {nombre[:3]} duracion: {dur}")


# ------------------------------------------------------------------------------ la serie de respuesta conocida


def control(r1=None, frescura: float = FRESCURA) -> int:
    """Seis tramos con su respuesta escrita antes de correr, a cadencia 13.9 s. Devuelve cuantos dan MAL."""
    r1 = r1 or REGLAS["R1 deslizante 5 min >=60% (ELEGIDA)"]
    mal = 0

    def serie(*tramos):
        ts, ws, t = [], [], 1_800_000_000.0
        for w, cuantas, hueco in tramos:
            t += hueco
            for _ in range(cuantas):
                ts.append(t)
                ws.append(w)
                t += CADENCIA
        return Serie(ts, ws)

    def tramos(s, regla):
        out = []
        for _, g, *_ in refrescos(s, regla, frescura=frescura, cola=120):
            if out and out[-1][0] == g:
                out[-1][1] += 1
            else:
                out.append([g, 1])
        return out

    def espera(nombre, ok, detalle):
        nonlocal mal
        mal += not ok
        print(f"  {'OK ' if ok else 'MAL'} {nombre}: {detalle}")

    # A · un lado sostenido 30 min entre dos NO OPERAR: LONG una vez, y tarda lo que tardan 14 de las 22 evaluaciones
    #     de la ventana (el 60 % de 22 es 13.2): 13 pasos de 13.9 s = 180.7 s, mas el refresco (menos de 15 s)
    s = serie((N, 130, 0), (L, 130, 0), (N, 130, 0))
    tr = [g for g, _ in tramos(s, r1) if g != E]
    espera("A sostenido -> LONG una vez", tr == [N, L, N], tr)
    m = medir(s, r1, frescura=frescura)
    espera("A tarda 180.7-195.7 s", 180.69 <= m["t1_med"] < 195.71 and 180.69 <= m["t2_med"] < 195.71,
           f"T1 {m['t1_med']:.1f} s, T2 {m['t2_med']:.1f} s")
    # B · un parpadeo de UNA evaluacion: la grande no se mueve
    tr = [g for g, _ in tramos(serie((N, 130, 0), (L, 1, 0), (N, 130, 0)), r1) if g != E]
    espera("B parpadeo -> nunca LONG", tr == [N], tr)
    # C · oscilar LONG/NO OPERAR al 50 % no sostiene; al 67 % si
    tr = [g for g, _ in tramos(serie((N, 30, 0), *[(L, 1, 0), (N, 1, 0)] * 130, (N, 30, 0)), r1) if g != E]
    espera("C oscila al 50 % -> nunca un lado", tr == [N], tr)
    tr = [g for g, _ in tramos(serie((N, 30, 0), *[(L, 2, 0), (N, 1, 0)] * 90, (N, 30, 0)), r1) if g != E]
    espera("C' oscila al 67 % -> LONG", L in tr, tr)
    # D · un hueco del colector de 300 s: NO EVALUABLE desde 60 s tras la ultima hasta la decima nueva (379 s)
    s = serie((L, 60, 0), (L, 60, 300.0))
    tr = tramos(s, r1)
    espera("D hueco -> LONG, NO EVALUABLE, LONG", [g for g, _ in tr] == [E, L, E, L, E], tr)
    espera("D lo que dura el NO EVALUABLE del hueco", len(tr) == 5 and 24 <= tr[2][1] <= 26, tr)
    # E · los bloques: como mucho un cambio por bloque, donde la deslizante pasa de 12 por hora
    azar = random.Random(7)
    s = Serie([1_800_000_000.0 + CADENCIA * k for k in range(3000)], [L if azar.random() < 0.6 else N for _ in range(3000)])
    mb, md = medir(s, REGLAS["R4 bloques cerrados 5 min >=60%"]), medir(s, r1, frescura=frescura)
    espera("E bloques <= 12 cambios/h", mb["cambios_h"] <= 12.0 < md["cambios_h"],
           f"bloques {mb['cambios_h']:.2f}/h, deslizante {md['cambios_h']:.2f}/h")
    # F · la racha de 4: tres seguidas no se dicen, cuatro si
    tr = [g for g, _ in tramos(serie((N, 30, 0), (L, 3, 0), (N, 30, 0), (L, 4, 0), (N, 30, 0)), REGLAS["R5 racha de 4"])
          if g != E]
    espera("F racha 3 no, 4 si", tr == [N, L, N], tr)
    print(f"control: {mal} MAL")
    return mal


if __name__ == "__main__":
    if sys.argv[1:] == ["--control"]:
        sys.exit(1 if control() else 0)
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    informe(sys.argv[1])
