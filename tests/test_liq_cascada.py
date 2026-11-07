"""Campana 150 · LA CASCADA M8 de la pagina contra la del estudio: la regla en JS (static/flujo/flujo-liq.js,
cascadaMinutos) da, minuto a minuto y por lado, la misma columna liq_{l,s}_casc que anatomia_extrae (Dia.liq_rt) sobre
LAS MISMAS filas; y n y s salen de un solo sitio (app/anatomia.py), el que sirve la ruta en sueltas.cascada.
"""
import gzip
import json
import random
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import anatomia_comun as C  # noqa: E402
import anatomia_extrae as X  # noqa: E402

from app import anatomia as A  # noqa: E402
from app import orderflow_lectura as OL  # noqa: E402

DIA = "2026-10-25"
NODE = shutil.which("node")


def _filas():
    """Rafagas deterministas de BTC y ETH (binance y bybit, los dos lados): de 3 a 8 en menos de un minuto, empates de
    ms, el borde exacto de CASCADA_S, rachas que cruzan el minuto y la medianoche (la hora 23 del dia anterior)."""
    rnd = random.Random(150)
    t0 = datetime.fromisoformat(DIA).replace(tzinfo=UTC)
    out = []
    t = t0 - timedelta(minutes=3)
    while t < t0 + timedelta(hours=3):
        sim = rnd.choice(("BTCUSDT", "ETHUSDT"))
        lado = rnd.choice(("long", "short"))
        k = rnd.randint(1, 8)
        u = t
        for _ in range(k):
            out.append((u, sim, rnd.choice(("binance", "bybit")), lado, round(rnd.uniform(50, 300_000), 2)))
            paso = rnd.choice((0, 0.001, 3.5, 11.0, 14.999, 15.0, 29.0, A.CASCADA_S / 4))
            u = u + timedelta(seconds=paso)
        t = t + timedelta(seconds=rnd.choice((20, 45, 60, 61, 95, 240)))
    # el borde: N del mismo lado con la primera EXACTAMENTE CASCADA_S antes de la ultima (el estudio la conserva)
    b = t0 + timedelta(hours=4)
    for i in range(A.CASCADA_N):
        out.append((b + timedelta(seconds=A.CASCADA_S * i / (A.CASCADA_N - 1)), "BTCUSDT", "binance", "long", 1000.0))
    return out


def _archivo(tmp, filas):
    for f in filas:
        dia, hora = f[0].strftime("%Y-%m-%d"), f[0].hour
        p = X.fichero(tmp, "liquidaciones-realtime", dia, hora)
        p.parent.mkdir(parents=True, exist_ok=True)
        ts = f[0].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + "+00"
        with gzip.open(p, "at", encoding="utf-8", newline="\n") as g:
            g.write("\t".join((ts, f[1], f[2], f[3], str(f[4]), "100", "1", "x")) + "\n")


def test_una_sola_definicion():
    assert (C.CASCADA_N, C.CASCADA_S) == (A.CASCADA_N, A.CASCADA_S)
    assert (OL.CASCADA_N, OL.CASCADA_S) == (A.CASCADA_N, A.CASCADA_S)
    assert f">= {A.CASCADA_N} " in OL.REGLA_CASCADA


@pytest.mark.skipif(NODE is None, reason="sin node")
def test_la_regla_js_es_la_del_estudio(tmp_path):
    filas = _filas()
    _archivo(tmp_path, filas)
    d = X.Dia(tmp_path, DIA)
    d.liq_rt()
    py = {}
    for s in ("BTC", "ETH"):
        for m in range(1440):
            for lado in ("l", "s"):
                v = d.m[s][m][X.COL[f"liq_{lado}_casc"]]
                if v is not None:
                    py[f"{s}|{d.t0 + 60 * m}|{lado}"] = int(v)
    ev = {}
    for f in filas:
        ev.setdefault(f[1][:3], []).append({"ts": f[0].strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z", "exchange": f[2],
                                            "lado": f[3], "usd": str(f[4]), "precio": "100"})
    js = ("const Q = require(process.argv[1]); const ev = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
          "const r = { n: Number(process.argv[2]), s: Number(process.argv[3]) }; const out = {};"
          "for (const s of Object.keys(ev)) { const m = Q.cascadaMinutos(Q.eventosLiq({ eventos: ev[s] }), r);"
          "for (const k of Object.keys(m)) for (const l of Object.keys(m[k])) out[s + '|' + k + '|' + l] = m[k][l]; }"
          "process.stdout.write(JSON.stringify(out));")
    p = subprocess.run([NODE, "-e", js, str(RAIZ / "static/flujo/flujo-liq.js"), str(A.CASCADA_N), str(A.CASCADA_S)],
                       input=json.dumps(ev), capture_output=True, text=True, check=True)
    t1 = d.t0 + 86400
    js_dia = {k: v for k, v in json.loads(p.stdout).items() if d.t0 <= int(k.split("|")[1]) < t1}
    assert sum(py.values()) >= 10, "el sujeto no tiene cascadas: no mide"
    assert len(py) - sum(py.values()) >= 10, "el sujeto no tiene minutos sin cascada: no mide"
    assert js_dia == py
    borde = f"BTC|{d.t0 + 4 * 3600 + int(A.CASCADA_S) // 60 * 60}|l"
    assert py[borde] == 1, "la racha del borde exacto tiene que cerrar cascada"
