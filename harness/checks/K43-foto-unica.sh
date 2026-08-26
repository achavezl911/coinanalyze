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
#
# LA PROMESA DE FOTO SE EJECUTA, y hasta el 2026-08-26 no se ejecutaba (auditoria del
# operador, K45 de COLA): para SERIE y DEMANDA el check pedia la ruta a 140 y miraba la
# respuesta, pero para las de FOTO solo comprobaba que EXISTIERA UNA CLAVE CON UN
# NOMBRE PARECIDO en el sobre, deducido por un heuristico. Cuatro pasaban sin que su
# contenido estuviera dentro: /api/profile 0 de 29 campos, /api/quality/feeds 14 de 35,
# /api/scalp/orderbook 10 de 22 y /api/oi 0 de 2. Ahora la pareja ruta->clave se DECLARA
# una a una aqui abajo, el check PIDE la ruta a 140 y exige que los nombres de campo de
# la respuesta -menos el envoltorio declarado- sean un SUBCONJUNTO de los nombres de esa
# clave. Subconjunto y no un porcentaje: un umbral se afloja despues sin que ningun
# numero lo distinga de haberlo mejorado.
#
# LO QUE ESTE CRITERIO NO PRUEBA, dicho aqui para que nadie lo lea de mas: compara
# NOMBRES, no valores ni cardinalidades. La foto arma liquidation_levels con
# limit=liq_levels (8 en el perfil por defecto) y el panel pide limit=50 (app.js:1598):
# los nombres de campo son los mismos y esto pasa, pero son 8 filas contra 50. Eso lo
# tiene que ver K44 cuando el panel deje de pedir las partes, no este subconjunto.
set -uo pipefail
_REPO_LLAMANTE=${REPO:-}
B=/srv/coinanalyze/harness; . "$B/env"
REPO=${_REPO_LLAMANTE:-${REPO:-/srv/coinanalyze/repo}}
PANEL="$REPO/static/app.js"
SIM=${K43_SIMBOLO:-BTCUSDT_PERP.A}
# Por defecto mide 140, que es lo que cuenta. K43_API y K43_CABECERA lo apuntan al espejo
# para poder ver el efecto de un cambio ANTES de desplegarlo -el espejo no tiene nginx
# delante, asi que el token interno va en cabecera en vez de en el netrc-. bin/verify
# nunca los pone: lo que decide ROJO o VERDE es produccion.
API_PROD=${K43_API:-$API_PROD}
CAB=()
[ -n "${K43_CABECERA:-}" ] && CAB=(-H "$K43_CABECERA")

# --- LA ASIGNACION. Una linea por ruta, con la familia y el motivo medido. ---
# desk/state, scalp/execution-cost y profile estan en DEMANDA y no en FOTO, y NO por su
# firma: los tres declaran symbol como unico parametro obligatorio. Es por medicion
# contra 140: desk/state con direction=long y direction=short devuelve cuerpos distintos
# (22159 B vs 22186 B, sha 14a69d09 vs d118d355) y con profile=swing vs scalper devuelve
# 22747 B vs 53 B; scalp/execution-cost con profile=intradia vs swing da 6572 B vs
# 6567 B, sha 9111bab6 vs 0a0afc9c; /api/profile con profile=intradia/swing/scalper da
# 1751/2185/52 B, sha 479380f3/9e4a429d/fd484f84 (2026-08-26). app.js los llama con
# state.tradingProfile y state.direction, o sea con eleccion del operador. Meterlos en la
# foto obligaria a armar una foto por combinacion, o a pintar cifras de un perfil bajo la
# ventana de otro, que es justo lo que esta unidad existe para impedir.
#
# /api/oi es SERIE y no FOTO, corregido el 2026-08-26: devuelve 384 barras de 15 min con
# su coverage, su interval y sus data_gaps, o sea la definicion literal de SERIE que esta
# escrita arriba. Estaba en FOTO y pasaba porque existe la clave oi_context, que es otra
# cosa -oi_total_usd, windows, zscore_1y- sin bucket ni oi: la serie que el panel pinta
# quedaba bajo NINGUNA ventana, que es justo lo que este check existe para impedir.
ASIGNACION="
/api/data-confidence=FOTO /api/divergences=FOTO /api/external-macro=FOTO
/api/funding-context=FOTO /api/macro-context=FOTO
/api/passive-flow=FOTO /api/quality/feeds=FOTO
/api/scalp/delta-matrix=FOTO /api/scalp/liquidation-levels=FOTO
/api/scalp/orderbook=FOTO /api/structure=FOTO /api/structure-detail=FOTO
/api/swing-score=FOTO /api/trend-matrix=FOTO
/api/dashboard/state=FOTO /api/market-impact=FOTO /api/positioning=FOTO
/api/scalp/absorption=FOTO /api/scalp/basis=FOTO /api/scalp/liquidations=FOTO
/api/wyckoff=FOTO
/api/ohlcv=SERIE /api/cvd/divergence=SERIE /api/daily=SERIE
/api/delta-profile=SERIE /api/whale/delta=SERIE /api/verdicts=SERIE /api/oi=SERIE
/api/level/breakout=DEMANDA /api/range/validate=DEMANDA /api/zone/analysis=DEMANDA
/api/scalp/execution-cost=DEMANDA /api/desk/state=DEMANDA /api/profile=DEMANDA
/api/stream=EXENTA /api/healthz=EXENTA /api/symbols=EXENTA
"
# EXENTAS, con su motivo: stream es SSE -empuje continuo, no una foto y no puede
# serlo-; healthz es salud del sistema; symbols es catalogo de configuracion.

# --- LAS PAREJAS DE FOTO. ruta | clave del sobre | envoltorio ---
# El ENVOLTORIO son los nombres de PRIMER NIVEL que la ruta pone alrededor de su dato y
# la foto no repite porque el sobre los declara UNA sola vez para todas las secciones
# (symbol, as_of) o porque son la caja y no el contenido (rows). Se descuenta el nombre
# de la caja pero NO lo que hay dentro: los campos de cada fila siguen contando.
# Con "ruta#campo" se declara una pareja por campo de primer nivel, para las rutas que
# son un COMPUESTO de secciones que la foto ya trae por separado.
# Una ruta de FOTO sin pareja declarada aqui es un fallo: no se deduce por parecido de
# nombre, que es como pasaban cuatro que no estaban dentro.
PAREJAS="
/api/data-confidence           | data_confidence        | rows
/api/divergences               | divergences            |
/api/external-macro            | external_macro_context |
/api/funding-context           | funding_context        |
/api/macro-context             | macro_context          |
/api/passive-flow              | passive_flow           |
/api/quality/feeds             | data_quality           |
/api/scalp/delta-matrix        | delta_matrix           |
/api/scalp/liquidation-levels  | liquidation_levels     | symbol,bucket_bps,minutes,rows
/api/scalp/orderbook           | orderbook              | symbol,rows
/api/structure                 | market_structure       |
/api/structure-detail          | structure_detail       |
/api/swing-score               | swing_score            | symbol,as_of,as_of_semantics
/api/trend-matrix              | trend_matrix           |
/api/market-impact             | market_impact          |
/api/positioning               | positioning            |
/api/wyckoff                   | wyckoff                |
/api/dashboard/state#scalp          | scalp            |
/api/dashboard/state#setup          | setup            |
/api/dashboard/state#snapshot       | snapshot         | symbol
/api/dashboard/state#symbol         | symbol           |
/api/dashboard/state#barriers       | price_barriers   |
/api/dashboard/state#cvd_swing      | cvd_swing_90d    |
/api/dashboard/state#market_memory  | market_memory_2y |
"
# /api/dashboard/state no necesita seccion propia y por eso va por campos: es un
# COMPUESTO de claves que la foto ya trae, cuatro con el mismo nombre y tres renombradas.
# Anadirlo como clave duplicaria 12571 B por foto (medido 2026-08-26). Lo que toca no es
# meterlo: es dejar de pedirlo.
#
# NO HAY EXCEPCIONES y hoy no hace falta ninguna. Cuando haga falta -una ruta que a
# proposito lleve mas detalle del que cabe en la foto- va con la medicion y la FECHA
# dentro, y el check tiene que delatarla cuando deje de hacer falta, como hacen los
# techos de K37 (linea 148) y las excepciones de K41. Una excepcion vieja no puede
# seguir cubriendo un fallo nuevo.

[ -r "$PANEL" ] || { echo "NO MEDIDO: no se puede leer static/app.js"; exit 2; }

foto=$(curl -sS -k --netrc-file "$NETRC" "${CAB[@]}" --max-time 60 \
       "$API_PROD/api/ai/context?symbol=$SIM" 2>/dev/null)
[ -n "$foto" ] || { echo "NO MEDIDO: /api/ai/context no respondio"; exit 2; }

printf '%s' "$foto" | REPO="$REPO" SIM="$SIM" ASIGNACION="$ASIGNACION" PAREJAS="$PAREJAS" \
  NETRC="$NETRC" API_PROD="$API_PROD" K43_CABECERA="${K43_CABECERA:-}" python3 -c '
import json, os, subprocess, sys

foto = json.load(sys.stdin)
claves = set(foto)
repo, sim = os.environ["REPO"], os.environ["SIM"]
netrc, base = os.environ["NETRC"], os.environ["API_PROD"]

asign = {}
for par in os.environ["ASIGNACION"].split():
    r, _, f = par.partition("=")
    asign[r] = f

parejas = {}
for linea in os.environ["PAREJAS"].strip().splitlines():
    ruta, clave, env = (c.strip() for c in (linea + "||").split("|")[:3])
    parejas.setdefault(ruta.split("#")[0], []).append(
        (ruta.partition("#")[2], clave, [e for e in env.split(",") if e]))

pintadas = sorted(set(subprocess.run(
    ["grep", "-o", "/api/[a-z0-9/-]*", repo + "/static/app.js"],
    capture_output=True, text=True).stdout.split()))
pintadas = [r for r in pintadas if r != "/api/ai/context"]

cab = ["-H", os.environ["K43_CABECERA"]] if os.environ.get("K43_CABECERA") else []

def cuerpo(r):
    out = subprocess.run(["curl", "-sS", "-k", "--netrc-file", netrc] + cab +
        ["--max-time", "30",
        base + r + "?symbol=%s&level=78800&low=77000&high=80000" % sim],
        capture_output=True, text=True).stdout
    try:
        return json.loads(out)
    except Exception:
        return None

def nombres(o, acc, saltar=(), con_valor=False):
    # Recoge TODO nombre de campo, a cualquier profundidad. Del primer nivel se descuenta
    # el envoltorio declarado, pero se sigue entrando en su valor: la caja no cuenta, lo
    # que lleva dentro si.
    # con_valor es para el lado de la RUTA: un campo que la ruta trae a null no prueba
    # nada, porque compact_dict (ai_context.py:192) tira los None al armar la foto, o sea
    # que el mismo campo aparece o no segun el dato del momento. Medido el 2026-08-26:
    # dashboard/state trae scalp.last_loss_at=null y por eso "faltaba" en la foto. Contarlo
    # haria que este check parpadease con los datos en vez de con el codigo. Del lado de la
    # FOTO no se aplica: si la clave lleva el nombre, el que pinta puede leerlo.
    if isinstance(o, dict):
        for k, v in o.items():
            if k not in saltar and not (con_valor and v is None):
                acc.add(k)
            nombres(v, acc, con_valor=con_valor)
    elif isinstance(o, list):
        for v in o:
            nombres(v, acc, con_valor=con_valor)
    return acc

def cubre(r):
    if r not in parejas:
        return "sin pareja declarada"
    d = cuerpo(r)
    if d is None:
        return "sin json"
    fallos = []
    for campo, clave, env in parejas[r]:
        trozo = d.get(campo) if campo else d
        if campo and campo not in d:
            fallos.append("%s: la ruta ya no trae ese campo" % campo)
            continue
        if clave not in claves:
            fallos.append("%s no esta en el sobre" % clave)
            continue
        faltan = sorted(nombres(trozo, set(), env, con_valor=True)
                        - nombres(foto[clave], set()))
        if faltan:
            fallos.append("%d nombres fuera de %s: %s"
                          % (len(faltan), clave, ",".join(faltan[:6])))
    return "; ".join(fallos) if fallos else None

sin_familia, incumplen = [], []
for r in pintadas:
    fam = asign.get(r)
    if fam is None:
        sin_familia.append(r)
        continue
    if fam == "EXENTA":
        continue
    if fam == "FOTO":
        mal = cubre(r)
        if mal:
            incumplen.append("%s(FOTO: %s)" % (r, mal))
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
print("las %d rutas que el panel pinta estan cubiertas: %d en la foto con sus nombres de "
      "campo dentro de la clave declarada, %d series con coverage, %d bajo demanda con "
      "as_of propio, %d exentas con cita"
      % (len(pintadas),
         sum(1 for r in pintadas if asign[r] == "FOTO"),
         sum(1 for r in pintadas if asign[r] == "SERIE"),
         sum(1 for r in pintadas if asign[r] == "DEMANDA"),
         sum(1 for r in pintadas if asign[r] == "EXENTA")))
'
