#!/bin/bash
# K43  toda cifra que el panel pinta esta cubierta por UNA ventana declarada.
#
# Hoy la pantalla es un collage: app.js menciona 37 rutas en 49 sitios y hace 8
# Promise.all; cada endpoint resuelve su propio now() y solo uno de esos instantes se
# pinta. Medido el 2026-08-26: las 37 rutas son 403749 B y 14.10 s sumadas;
# /api/ai/context trae 16 de ellas -y 12 de las 20 huerfanas de K31- en 71586 B y
# 3.15 s, en UNA peticion.
#
# NO SE DEJA DE PINTAR NADA. Las 37 siguen en pantalla; lo que cambia es que cada una
# queda bajo una ventana en vez de bajo ninguna. Y no todas van al mismo sitio: meter
# una serie de 576 velas en cada refresco es un error de categoria -una serie no tiene
# un instante, tiene una ventana- y revienta los 69.9 KB de la foto.
#
# CUATRO FAMILIAS, cada ruta en UNA y declarada aqui con lo que promete:
#   FOTO     estado ambiente del instante: solo depende de symbol. Va dentro de
#            /api/ai/context y la gobierna su [build_started_at, build_finished_at].
#   SERIE    devuelve una sucesion de barras. Su ventana es su coverage, que K03 ya
#            le obliga a declarar. NO entra en el sobre.
#   DEMANDA  la respuesta depende de algo que ELIGE el operador -un nivel, un rango,
#            un perfil-. La foto no puede saber que le vas a preguntar, asi que cada
#            respuesta trae su propio as_of.
#   EXENTA   no es una cifra de mercado. Con cita, no por conveniencia.
#
# LA MITAD (a) -que la foto declare su ventana- ya esta VERDE contra 140 desde
# f36d009. Lo que sigue ROJO es esta mitad.
#
# POR QUE NO SE EXIGE "EXACTAMENTE UNA" EN EL SENTIDO LITERAL, y esto se midio antes
# de decidirlo: 11 de las 37 estan a la vez en la foto y traen as_of o coverage propio
# -external-macro, funding-context, macro-context, oi, passive-flow, profile,
# quality/feeds, structure, structure-detail, swing-score, trend-matrix-. Eso NO es un
# defecto: es el mismo dato alcanzable por dos caminos, y quien pinta elige uno. Exigir
# "una y solo una" habria puesto 11 rutas en ROJO por algo que no rompe nada, que es
# el error que ya casi se comete en K42 al implementar el oraculo tal como se encargo.
# Lo que si se exige, y es lo que impide la escapatoria: cada ruta esta ASIGNADA a una
# familia aqui, y esa familia CUMPLE su promesa contra 140. Una ruta sin familia es un
# fallo; una familia que no cumple lo que promete, tambien.
set -uo pipefail
_REPO_LLAMANTE=${REPO:-}
B=/srv/coinanalyze/harness; . "$B/env"
REPO=${_REPO_LLAMANTE:-${REPO:-/srv/coinanalyze/repo}}
PANEL="$REPO/static/app.js"
SIM=${K43_SIMBOLO:-BTCUSDT_PERP.A}

# --- LA ASIGNACION. Una linea por ruta, con la familia y el motivo medido. ---
# desk/state y scalp/execution-cost estan en DEMANDA y no en FOTO, y NO por su firma:
# los dos declaran symbol como unico parametro obligatorio. Es por medicion del
# 2026-08-26 contra 140: desk/state con direction=long y direction=short devuelve
# cuerpos distintos (22159 B vs 22186 B, sha 14a69d09 vs d118d355) y con
# profile=swing vs scalper devuelve 22747 B vs 53 B; scalp/execution-cost con
# profile=intradia vs swing da 6572 B vs 6567 B, sha 9111bab6 vs 0a0afc9c. app.js los
# llama con state.tradingProfile y state.direction, o sea con eleccion del operador.
# Meterlos en la foto obligaria a armar una foto por combinacion, o a pintar cifras de
# un perfil bajo la ventana de otro, que es justo lo que esta unidad existe para
# impedir.
ASIGNACION="
/api/data-confidence=FOTO /api/divergences=FOTO /api/external-macro=FOTO
/api/funding-context=FOTO /api/macro-context=FOTO /api/oi=FOTO
/api/passive-flow=FOTO /api/profile=FOTO /api/quality/feeds=FOTO
/api/scalp/delta-matrix=FOTO /api/scalp/liquidation-levels=FOTO
/api/scalp/orderbook=FOTO /api/structure=FOTO /api/structure-detail=FOTO
/api/swing-score=FOTO /api/trend-matrix=FOTO
/api/dashboard/state=FOTO /api/market-impact=FOTO /api/positioning=FOTO
/api/scalp/absorption=FOTO /api/scalp/basis=FOTO /api/scalp/liquidations=FOTO
/api/wyckoff=FOTO
/api/ohlcv=SERIE /api/cvd/divergence=SERIE /api/daily=SERIE
/api/delta-profile=SERIE /api/whale/delta=SERIE /api/verdicts=SERIE
/api/level/breakout=DEMANDA /api/range/validate=DEMANDA /api/zone/analysis=DEMANDA
/api/scalp/execution-cost=DEMANDA /api/desk/state=DEMANDA
/api/stream=EXENTA /api/healthz=EXENTA /api/symbols=EXENTA
"
# EXENTAS, con su motivo: stream es SSE -empuje continuo, no una foto y no puede
# serlo-; healthz es salud del sistema; symbols es catalogo de configuracion.

[ -r "$PANEL" ] || { echo "NO MEDIDO: no se puede leer static/app.js"; exit 2; }

foto=$(curl -sS -k --netrc-file "$NETRC" --max-time 40 \
       "$API_PROD/api/ai/context?symbol=$SIM" 2>/dev/null)
[ -n "$foto" ] || { echo "NO MEDIDO: /api/ai/context no respondio"; exit 2; }

printf '%s' "$foto" | REPO="$REPO" SIM="$SIM" ASIGNACION="$ASIGNACION" \
  NETRC="$NETRC" API_PROD="$API_PROD" python3 -c '
import json, os, re, subprocess, sys

foto = json.load(sys.stdin)
claves = set(foto)
repo, sim = os.environ["REPO"], os.environ["SIM"]
netrc, base = os.environ["NETRC"], os.environ["API_PROD"]

asign = {}
for par in os.environ["ASIGNACION"].split():
    r, _, f = par.partition("=")
    asign[r] = f

pintadas = sorted(set(subprocess.run(
    ["grep", "-o", "/api/[a-z0-9/-]*", repo + "/static/app.js"],
    capture_output=True, text=True).stdout.split()))
pintadas = [r for r in pintadas if r != "/api/ai/context"]

def clave_en_foto(r):
    n = r.replace("/api/", "").replace("/", "_").replace("-", "_")
    cand = [n, n.replace("scalp_", ""), n + "_context"]
    cand += {"oi": ["oi_context"], "market_memory": ["market_memory_2y"],
             "quality_feeds": ["data_quality"], "external_macro": ["external_macro_context"],
             "scalp_orderbook": ["orderbook"], "structure": ["market_structure"],
             "scalp_liquidations": ["scalp_liquidations"]}.get(n, [])
    # /api/dashboard/state no necesita seccion propia: es un COMPUESTO de claves que la
    # foto ya trae. Medido el 2026-08-26 contra 140, sus 7 claves estan todas dentro,
    # cuatro con el mismo nombre (scalp setup snapshot symbol) y tres renombradas, con
    # los MISMOS campos una a una: barriers=price_barriers (14 de 14),
    # cvd_swing=cvd_swing_90d (2 de 2), market_memory=market_memory_2y (11 de 11).
    # Anadirlo como clave duplicaria 12571 B por foto. Lo que toca no es meterlo: es
    # dejar de pedirlo.
    if r == "/api/dashboard/state":
        COMPUESTO = ("scalp", "setup", "snapshot", "price_barriers", "cvd_swing_90d",
                     "market_memory_2y")
        faltan = [c for c in COMPUESTO if c not in claves]
        return None if faltan else "compuesto:" + ",".join(COMPUESTO)
    return next((c for c in cand if c in claves), None)

def cuerpo(r):
    out = subprocess.run(["curl", "-sS", "-k", "--netrc-file", netrc, "--max-time", "30",
        base + r + "?symbol=%s&level=78800&low=77000&high=80000" % sim],
        capture_output=True, text=True).stdout
    try:
        return json.loads(out)
    except Exception:
        return None

sin_familia, incumplen = [], []
for r in pintadas:
    fam = asign.get(r)
    if fam is None:
        sin_familia.append(r)
        continue
    if fam == "EXENTA":
        continue
    if fam == "FOTO":
        if not clave_en_foto(r):
            incumplen.append("%s(FOTO: no esta en el sobre)" % r)
        continue
    d = cuerpo(r)
    if not isinstance(d, dict):
        incumplen.append("%s(%s: sin json)" % (r, fam))
    elif fam == "SERIE" and not ("coverage" in d or "data_gaps" in d):
        incumplen.append("%s(SERIE: sin coverage)" % r)
    elif fam == "DEMANDA" and not any(k in d for k in ("as_of", "generated_at", "snapshot_ts")):
        incumplen.append("%s(DEMANDA: sin as_of)" % r)

if sin_familia:
    print("%d rutas que el panel pinta no tienen familia asignada: %s"
          % (len(sin_familia), " ".join(sin_familia)))
    raise SystemExit(1)
if incumplen:
    print("%d de %d rutas no cumplen lo que su familia promete: %s"
          % (len(incumplen), len(pintadas), " ".join(incumplen)))
    raise SystemExit(1)
print("las %d rutas que el panel pinta estan cubiertas: %d en la foto, %d series con "
      "coverage, %d bajo demanda con as_of propio, %d exentas con cita"
      % (len(pintadas),
         sum(1 for r in pintadas if asign[r] == "FOTO"),
         sum(1 for r in pintadas if asign[r] == "SERIE"),
         sum(1 for r in pintadas if asign[r] == "DEMANDA"),
         sum(1 for r in pintadas if asign[r] == "EXENTA")))
'
