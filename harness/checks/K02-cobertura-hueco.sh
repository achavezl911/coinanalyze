#!/bin/bash
# K02  la API tiene que declarar el hueco en LOS ENDPOINTS DE SERIE.
#
# EL CRITERIO CAMBIO EL 2026-09-06 Y EL VIEJO ESTABA DEL REVES. Enrojecia con «6 de 7
# endpoints de serie pasan por el enmascarado; sin cubrir: `whale/delta`» y llevaba ROJO
# 26 de 27 pasadas guardadas. Al medirlo salio que la ruta acusada es la MEJOR instrumentada
# de las siete y que dos de las seis «cubiertas» hacen una llamada que no puede enmascarar
# nada. Las cuatro medidas, cada una con su instrumento:
#
#   1. EL ENMASCARADO SOLO FUNCIONA SI ALGUIEN APUNTA EL HUECO. mask_gapped_series_rows
#      consulta identidades de hueco en `data_gap`. Medido en 140:
#        SELECT feed, count(*) FROM data_gap GROUP BY 1
#          -> long_short_ratio 809 · ohlcv_1min 435 · ohlcv_5min 6 · open_interest_5min 6
#             funding_rate 3 · predicted_funding_rate 3
#        SELECT count(*) FROM data_gap WHERE feed='spot_trades'   -> 0
#      Y en el arbol: `spot_trades` aparece 0 veces en app/data_gaps.py, y el unico detector
#      que llama desde fuera es app/scalp_collector.py:590 record_event_stream_loss(), para
#      `liquidations`. NO HAY DETECTOR DE HUECOS PARA spot_trades.
#
#   2. POR ESO `whale/delta` NO ENMASCARA, y esta escrito en app/api.py:1067: seria una
#      llamada hueca. En su lugar declara la cobertura POR CUBO -covered_seconds_min,
#      short_minutes, unknown_minutes, minutes_present- y es la UNICA de las siete que lo
#      hace. Declara MAS, no menos.
#
#   3. PERO ESE MOTIVO, SOLO, NO DISTINGUE, y por eso no vale como exencion a secas:
#      `cvd/spot` (api.py:747-794) usa el MISMO feed `spot_trades` y llama al enmascarado
#      igualmente. Su llamada tampoco puede honrarse. Es inofensiva -sin huecos apuntados no
#      enmascara nada- pero contarla como cobertura era el error del criterio viejo.
#
#   4. Y EL SUELO SE MOVIO DEBAJO DEL CHECK. Cuando K02 se escribio, pasar por el
#      enmascarado era la unica forma de declarar. Hoy las SIETE devuelven por
#      declared_series_response un bloque `coverage` y un `data_gaps` con estado. Medido en
#      140 el 2026-09-06 con TODO=1 y symbol=BTCUSDT_PERP.A: las siete traen `data_gaps`, y
#      seis traen coverage.served_window{complete,expected_buckets,observed_buckets};
#      `daily` trae `coverage_note` porque su fila es una sesion y no un cubo.
#
# QUE SE GATEA AHORA. El SUELO -toda ruta de serie declara su ventana y su estado de hueco-
# y no el MECANISMO. Se deriva del arbol: la ruta tiene que devolver declared_series_response.
# Es un proxy, y esta validado contra 140 con la medida del punto 4: el proxy no se cree, se
# comprueba. Ademas se CUENTA, sin enrojecer, el instrumento fino de cada una, que es donde
# esta la informacion que el criterio viejo destruia al reducirlo todo a un si/no.
#
# LO QUE ESTE CHECK DEJA DICHO Y NO ARREGLA: `cvd/spot` lee `spot_trades_agg` -la misma
# tabla y el mismo WHERE que `whale/delta`, api.py:761 contra :1029- que tiene
# covered_seconds, y NO publica cobertura por cubo. Un cubo suyo construido sobre minutos
# cortos es indistinguible de uno completo. Anadir los cuatro agregados es una copia de lo
# que ya hace whale/delta, pero cambia la forma de la respuesta -y eso es producto-, asi que
# va a la mesa de Alejandro y no lo decido yo.
#
# K03 mide otra cosa y las dos hacen falta: K03 pregunta si la RESPUESTA declara el hueco con
# ventana y estado; esta pregunta si la ruta tiene por donde declararlo.
set -uo pipefail
_REPO_LLAMANTE=${REPO:-}
B=/srv/coinanalyze/harness; . "$B/env"
REPO=${_REPO_LLAMANTE:-${REPO:-/srv/coinanalyze/repo}}
API="$REPO/app/api.py"
# El sujeto sigue escrito a mano y sigue siendo correcto decirlo: son las rutas que sirven
# una SERIE de cubos. `funding-context` y `oi-context` no la sirven (ver K03).
#
# SE PUEDE SOBREESCRIBIR, y no es un capricho: un control que ejercite este check tiene que
# fabricar un api.py con estas rutas dentro, y entonces el detector de consumidores del mapa
# acredita al FIXTURE como consumidor de rutas reales. Medido: con el control nombrandolas,
# /api/ohlcv pasaba de 7 llamadas a 11 y /api/cvd de 2 a 4. Con K02_SERIE el control usa
# nombres inventados y el mapa no se entera de que existe. Es la quinta autocontaminacion de
# esta campana y la primera que se arregla en el sujeto en vez de en la prosa.
SERIE=${K02_SERIE:-"/api/ohlcv /api/oi /api/liquidations /api/whale/delta /api/daily /api/cvd /api/cvd/spot"}

[ -r "$API" ] || { echo "NO MEDIDO: no se puede leer app/api.py"; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "NO MEDIDO: no hay python3"; exit 2; }

grep -q 'async def declared_series_response' "$API" \
  || { echo "NO MEDIDO: declared_series_response ya no existe: el check hay que reescribirlo"; exit 2; }

salida=$(python3 - "$API" "$REPO" $SERIE <<'PY' 2>&1
import ast, json, sys
from pathlib import Path
api, repo, rutas = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]
src = api.read_text(encoding="utf-8")
arbol = ast.parse(src)

# TABLAS CON covered_seconds: se leen del catalogo, no se teclean. Son las unicas donde la
# cobertura por cubo es POSIBLE, asi que decide a quien se le puede exigir.
try:
    from importlib.machinery import SourceFileLoader
    m = SourceFileLoader("arq", str(repo / "harness/bin/arquitectura")).load_module()
    cat = m.lee_catalogo(repo)["tablas"]
    CON_CS = {t for t, v in cat.items() if "covered_seconds" in v.get("columnas", [])}
except Exception as e:
    print("ERRCAT", e); raise SystemExit

def ruta_de(fn):
    for d in fn.decorator_list:
        if isinstance(d, ast.Call) and d.args and isinstance(d.args[0], ast.Constant):
            f = d.func
            nom = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            if nom in ("get", "post"):
                return d.args[0].value
    return None

info = {}
for fn in ast.walk(arbol):
    if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
        continue
    r = ruta_de(fn)
    if r not in rutas:
        continue
    cuerpo = ast.get_source_segment(src, fn) or ""
    # EL SUELO SE RECONOCE POR LO QUE PUBLICA, NO POR A QUIEN LLAMA. La primera version
    # exigia declared_series_response y dejaba fuera a `daily`, que llama a
    # declared_gap_windows() y monta el bloque a mano (api.py:1988). Produccion decia que
    # `daily` SI declara, asi que el proxy estaba mal y gano el instrumento.
    dat = {"suelo": '"data_gaps"' in cuerpo or "'data_gaps'" in cuerpo,
           "enmascara": [], "por_cubo": "covered_seconds" in cuerpo,
           "tablas": sorted(t for t in CON_CS if t in cuerpo)}
    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            nom = n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
            if nom == "declared_series_response":
                dat["suelo"] = True
            if nom == "mask_gapped_series_rows":
                fd = next((k.value.value for k in n.keywords
                           if k.arg == "feed" and isinstance(k.value, ast.Constant)), "?")
                dat["enmascara"].append(fd)
    info[r] = dat
print(json.dumps({"rutas": info, "con_cs": sorted(CON_CS)}))
PY
); rc=$?
case "$salida" in
  ERRCAT*) echo "NO MEDIDO: no se pudo leer el catalogo de tablas: $(printf '%s' "$salida" | cut -c1-100)"; exit 2 ;;
esac
[ "$rc" = "0" ] || { echo "NO MEDIDO: no se pudo analizar app/api.py: $(printf '%s' "$salida" | tail -1 | cut -c1-110)"; exit 2; }

n_res=$(printf '%s' "$salida" | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["rutas"]))' 2>/dev/null)
n_pedidas=$(printf '%s\n' $SERIE | grep -c .)
# CERO RUTAS RESUELTAS NO ES CERO DEFECTOS: si el AST deja de reconocer los decoradores,
# "todas cumplen" seria indistinguible de "no he mirado ninguna".
[ "${n_res:-0}" = "$n_pedidas" ] || {
  echo "NO MEDIDO: solo se resolvieron ${n_res:-0} de $n_pedidas rutas de serie en app/api.py"; exit 2; }

# --- el veredicto ----------------------------------------------------------------------
# QUE FEED PUEDE HONRAR UNA LLAMADA AL ENMASCARADO. Se DERIVA de DOS instrumentos y se unen,
# porque ninguno solo basta:
#   · del ARBOL: los feeds que alguien registra llamando a data_gaps.py desde fuera. Coge los
#     detectores de evento -hoy `liquidations`, por scalp_collector.py:590- y no caduca si
#     manana aparece uno para spot_trades.
#   · de 140: los feeds que YA tienen huecos apuntados. Coge los de CADENCIA, que data_gaps.py
#     dispara con el feed en una variable y no en un literal, asi que el arbol no los ve.
# La union es conservadora: mas feeds "con detector" = menos llamadas marcadas como huecas =
# el check no puede inventarse deuda. Si la base no responde, se gatea igual con el arbol y
# se DICE que el detalle fino va incompleto: el suelo no depende de la red.
det_arbol=$(grep -rhoE "feed=\"[a-z_0-9]+\"" $(grep -rl "record_event_stream_loss(\|record_data_gap(" \
             "$REPO/app/" --include='*.py' 2>/dev/null | grep -v '/data_gaps.py$') 2>/dev/null \
             | sed 's/feed="//; s/"//' | sort -u | tr '\n' ' ')
det_base=$("$B/bin/prodsql" "SELECT DISTINCT feed FROM data_gap" 2>/dev/null \
           | grep -E '^[a-z_0-9]+$' | sort -u | tr '\n' ' ')
if [ -z "${det_base// /}" ]; then
  aviso="  (la base no respondio: el reparto fino sale solo del arbol y puede marcar como hueca una llamada que si se honra)"
else
  aviso=""
fi
detectados="$det_arbol $det_base"

# EL PROGRAMA VA POR ARGUMENTO Y NO POR TUBERIA. Con `python3 - <<PY` el heredoc ES stdin, asi
# que un `printf | python3 - <<PY` deja a json.load(sys.stdin) sin nada que leer. Lo enseño
# correr el check: traceback de JSONDecodeError con el veredicto impreso igualmente debajo.
detalle=$(python3 - "$salida" "$detectados" <<'PY'
import json, sys
d = json.loads(sys.argv[1])
rutas = d["rutas"]
# CON_DETECTOR llega derivado del arbol y de 140 (ver arriba). Un feed que no esta ahi no
# tiene quien le apunte un hueco, asi que enmascarar con el es una llamada que no se honra.
CON_DETECTOR = set(sys.argv[2].split()) if len(sys.argv) > 2 else set()
sin_suelo, huecas, mejorables, lineas = [], [], [], []
for r, x in sorted(rutas.items()):
    if not x["suelo"]:
        sin_suelo.append(r)
    efectivo = [f for f in x["enmascara"] if f in CON_DETECTOR]
    hueca = [f for f in x["enmascara"] if f not in CON_DETECTOR]
    if hueca:
        huecas.append(f"{r}({','.join(hueca)})")
    if x["tablas"] and not x["por_cubo"]:
        mejorables.append(f"{r} lee {','.join(x['tablas'])}")
    fino = ("enmascarado efectivo: " + ",".join(efectivo)) if efectivo else \
           ("cobertura por cubo" if x["por_cubo"] else "solo ventana")
    lineas.append(f"    {r:22s} {fino}")
print("SINSUELO|" + " ".join(sin_suelo))
print("HUECAS|" + " ".join(huecas))
print("MEJORABLES|" + " ".join(mejorables))
print("LINEAS|" + "\n".join(lineas))
PY
)
sin_suelo=$(printf '%s\n' "$detalle" | sed -n 's/^SINSUELO|//p')
huecas=$(printf '%s\n' "$detalle" | sed -n 's/^HUECAS|//p')
mejorables=$(printf '%s\n' "$detalle" | sed -n 's/^MEJORABLES|//p')

if [ -n "${sin_suelo// /}" ]; then
  n=$(printf '%s\n' $sin_suelo | grep -c .)
  echo "$n de $n_pedidas endpoints de serie NO declaran su ventana ni su estado de hueco:$sin_suelo"
  echo "  no devuelven declared_series_response, o sea que su consumidor no puede saber si le falta un cubo"
  exit 1
fi

echo "los $n_pedidas endpoints de serie publican su bloque data_gaps con estado y ventana"
printf '%s\n' "$detalle" | sed -n '/^LINEAS|/,$p' | sed 's/^LINEAS|//'
[ -z "$aviso" ] || echo "$aviso"
[ -z "${huecas// /}" ] || echo "  DEUDA, no defecto: llamada al enmascarado que su feed no puede honrar (no hay detector): $huecas"
[ -z "${mejorables// /}" ] || echo "  DEUDA, no defecto: lee una tabla con covered_seconds y no publica cobertura por cubo: $mejorables"
echo "  la raiz de las dos deudas es la misma y no esta en api.py: falta detector de huecos para spot_trades"
exit 0
