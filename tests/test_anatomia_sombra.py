"""BOT-5: la definicion compartida (app/anatomia.py) contra los gemelos numpy del estudio, punto a punto.
La parte de estudio necesita numpy (la CI no lo trae: se corre en 143 con un venv que si)."""
import math
import random
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(RAIZ))
from app import anatomia as A  # noqa: E402


def test_comun_reexporta_la_definicion():
    import anatomia_comun as C
    for n in ("ESQUEMAS", "COMISION", "HORIZONTE", "REJILLA", "GRANDE_100K", "CAPA_B_DESDE", "etiqueta",
              "sin_solape", "empate", "azar", "VENUES_SPOT", "VENUE_REF"):
        assert getattr(C, n) is getattr(A, n), n


def test_cinta_fila_reparte_por_venue_y_tamano():
    f, b = A.minuto_vacio(), {}
    filas = [("2026-10-21 04:00:00.2+00", "binance_spot", 100.0, 100_000.0, False),
             ("2026-10-21 04:00:00.3+00", "okx_spot", 100.0, 99_999.99, False),
             ("2026-10-21 04:00:00.4+00", "binance_usdm", 101.0, 500_000.0, False),
             ("2026-10-21 04:00:00.1+00", "binance_usdm", 99.0, 10.0, True),
             ("2026-10-21 04:00:00.4+00", "binance_usdm", 102.0, 10.0, True),
             ("2026-10-21 04:00:00.5+00", "venue_rara", 1.0, 1e9, True)]
    for x in filas:
        A.cinta_fila(f, b, *x)
    c = A.COL
    assert f[c["ds100k"]] == -100_000.0 and f[c["ds"]] == -199_999.99 and f[c["dp100k"]] == -500_000.0
    assert (f[c["o"]], f[c["h"]], f[c["l"]], f[c["c"]]) == (99.0, 102.0, 99.0, 102.0)


def _serie(n, rng):
    o, h, lo, c, fl = [], [], [], [], []
    p = 100.0
    for i in range(n):
        if rng.random() < 0.01:
            o.append(None), h.append(None), lo.append(None), c.append(None)
        else:
            a = p
            p *= math.exp(rng.gauss(0, 0.002))
            o.append(a), c.append(p)
            h.append(max(a, p) * (1 + abs(rng.gauss(0, 0.001)))), lo.append(min(a, p) * (1 - abs(rng.gauss(0, 0.001))))
        fl.append(None if (i // 60) % 9 == 4 else (rng.gauss(0, 2e5) if rng.random() < 0.2 else 0.0))
    return o, h, lo, c, fl


def test_la_definicion_es_la_del_estudio():
    np = pytest.importorskip("numpy")
    import anatomia_estudio as E
    rng = random.Random(5)
    o, h, lo, c, fl = _serie(3000, rng)
    t0 = A.CAPA_B_DESDE + 3 * 86400
    ts = np.arange(len(o)) * 60 + t0
    nf = lambda v: np.array([math.nan if x is None else x for x in v])  # noqa: E731
    S = E.rsum(nf(fl), 60)
    G = E.rejilla(ts)
    assert [int(g) for g in G] == [i for i in range(len(o)) if A.es_decision(int(ts[i]))]
    for t in range(len(o)):
        s = A.suma_ventana([fl[m] if m >= 0 else None for m in range(t - 59, t + 1)])
        assert (s is None) == math.isnan(S[t]) and (s is None or abs(s - S[t]) < 1e-6), t
    fuente = nf([A.FUENTE_CINTA if x is not None else 0 for x in o])
    cinta = E._acum((fuente == A.FUENTE_CINTA).astype(float))
    Gc = np.minimum(G, len(ts) - A.HORIZONTE - 1)
    camino = (cinta[Gc + A.HORIZONTE + 1] - cinta[Gc + 1] == A.HORIZONTE) & (len(ts) > G + A.HORIZONTE)
    for lado in (1, -1):
        ex, ne, sa, va = E.etiquetas(nf(o), nf(h), nf(lo), nf(c), G, lado, "E1")
        for i, t in enumerate(G):
            r = A.etiqueta_entera(o, h, lo, c, int(t), lado, "E1")
            assert (r is not None) == bool(va[i] and camino[i]), t
            if r is not None:
                assert (r[0], r[2]) == (int(ex[i]), int(sa[i])) and abs(r[1] - ne[i]) < 1e-12, t
        assert sum(1 for i in range(len(G)) if va[i] and ex[i]) > 0
