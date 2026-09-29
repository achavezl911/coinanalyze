#!/bin/bash
# K102-control · UN PLANTADO QUE TIENE QUE FALLAR POR CADA COSA QUE K102 PROMETE
#
# POR QUE ESTE FICHERO EXISTE. K102 dio VERDE la primera vez que se corrio. Un check que nace
# verde no ha demostrado nada: puede estar midiendo la forma equivocada, o la nada. Asi que por
# cada promesa se PLANTA el defecto y se exige que K102 CONDENE; y ademas se corre contra los
# BYTES DE ANTES DE LA MESA, donde se publica cuantos brazos condenan y cuales.
#
# CADA PLANTADO LLEVA SU HUELLA DE ANTES Y DE DESPUES, Y SE RESTAURA. La huella no es adorno:
# es la unica prueba de que el arbol quedo como estaba.
#
# LOS PLANTADOS VIVEN EN `static/`, QUE ES LO QUE `FileResponse` LEE EN CADA PETICION: por eso
# no hace falta reiniciar el servidor entre plantados. El unico que necesitaria reinicio -mover
# el umbral de 70 en `app/ai_context.py`- se sustituye por su gemelo del lado del cliente, que
# condena el MISMO brazo.
#
# SE INVOCA DE LAS TRES FORMAS (A56) desde `K102-control-tres.bash`, que llama a este.
set -u

# RUTA ABSOLUTA ANTES DE CUALQUIER `cd`, y se comprueba que cargo. Un ayudante que no carga no
# es un brazo menos: es un control que aprueba midiendo la nada (A56).
D="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
B=/srv/coinanalyze/harness
[ -r "$B/env" ] || { echo "NO MEDIDO: no se pudo resolver $B/env"; exit 2; }
. "$B/env"
AYUDANTE_CARGADO=1
[ "${AYUDANTE_CARGADO:-0}" = "1" ] || { echo "NO MEDIDO: el env no cargo"; exit 2; }
REPO="${REPO:-/srv/coinanalyze/repo}"
PY="$REPO/.venv/bin/python"
CHECK="$D/K102-decide-lo-primero.sh"
[ -r "$CHECK" ] || { echo "NO MEDIDO: falta $CHECK"; exit 2; }

BASE="${MESA_BASE:-}"
[ -n "$BASE" ] || { echo "NO MEDIDO: hace falta MESA_BASE=<url que sirva el ARBOL>"; exit 2; }

CSS="$REPO/static/mesa/mesa.css"
JS="$REPO/static/mesa/mesa-decide.js"

pasa=0; falla=0; total=0
# El veredicto de K102 con el plantado puesto. Devuelve rc.
juzga() {
  MESA_BASE="$BASE" bash "$CHECK" > "$TMP/sal" 2>&1
  echo $?
}

espero_condena() {  # espero_condena <rotulo> <fichero tocado> <grep que tiene que salir>
  local rot="$1" fich="$2" patron="$3"
  total=$((total + 1))
  local rc; rc=$(juzga)
  if [ "$rc" = "1" ] && grep -q "$patron" "$TMP/sal"; then
    pasa=$((pasa + 1))
    printf '  CONDENA   %-46s rc=%s · %s\n' "$rot" "$rc" "$(grep -m1 "$patron" "$TMP/sal" | sed 's/^ *//' | cut -c1-96)"
  else
    falla=$((falla + 1))
    printf '  NO CAZA   %-46s rc=%s  <-- el plantado paso sin condena\n' "$rot" "$rc"
    sed -n '1,6p' "$TMP/sal" | sed 's/^/      /'
  fi
}

TMP="$(mktemp -d)" || exit 2
trap 'rm -rf "$TMP"' EXIT INT TERM

echo "K102-control · sujeto: $BASE"
echo

# ---------------------------------------------------------------- linea base
total=$((total + 1))
rc0=$(juzga)
if [ "$rc0" = "0" ]; then
  pasa=$((pasa + 1))
  echo "  LIMPIO    la mesa REAL pasa                            rc=0"
else
  falla=$((falla + 1))
  echo "  ROTO      la mesa REAL no pasa (rc=$rc0): sin linea base no hay control"
  sed -n '1,8p' "$TMP/sal" | sed 's/^/      /'
  echo
  echo "RESUMEN: $pasa de $total"
  exit 1
fi
echo

# --------------------------------------------- P1 · DECIDE por DEBAJO del pliegue
h_css_antes=$(sha256sum "$CSS" | cut -c1-16)
cp "$CSS" "$TMP/css.bak"
printf '\n/* PLANTADO K102-control P1 */\n.scan { min-height: 1200px; }\n' >> "$CSS"
echo "P1 · DECIDE empujado por debajo del pliegue  (mesa.css $h_css_antes -> $(sha256sum "$CSS" | cut -c1-16))"
espero_condena "B1 tiene que condenar el pliegue" "$CSS" "B1 "
cp "$TMP/css.bak" "$CSS"
h_css_desp=$(sha256sum "$CSS" | cut -c1-16)
[ "$h_css_antes" = "$h_css_desp" ] && echo "  restaurado: $h_css_desp OK" || echo "  RESTAURO MAL: $h_css_antes -> $h_css_desp"
echo

# ------------------------------- P2 · un valor de DECIDE que NO sale del sobre
h_js_antes=$(sha256sum "$JS" | cut -c1-16)
cp "$JS" "$TMP/js.bak"
# MUTAR NO ES PREFIJAR: se REEMPLAZA el valor servido por una constante. Si se prefijara, el
# texto seguiria conteniendo el valor bueno y un comparador por subcadena lo absolveria.
"$PY" - "$JS" <<'PY'
import pathlib, sys
f = pathlib.Path(sys.argv[1]); t = f.read_text(encoding="utf-8")
viejo = "  const texto = hayValor ? (o.formato ? o.formato(campo.value) : String(campo.value)) : null;"
nuevo = ("  const texto = hayValor ? (nombre === 'state' ? 'Valor Inventado'\n"
         "    : (o.formato ? o.formato(campo.value) : String(campo.value))) : null;")
assert viejo in t, "no encontre la linea a plantar"
f.write_text(t.replace(viejo, nuevo, 1), encoding="utf-8")
PY
echo "P2 · el campo 'state' se pinta con una constante  (mesa-decide.js $h_js_antes -> $(sha256sum "$JS" | cut -c1-16))"
espero_condena "B3 tiene que condenar el valor" "$JS" "el valor de la celda no es el servido"
cp "$TMP/js.bak" "$JS"
h=$(sha256sum "$JS" | cut -c1-16)
[ "$h_js_antes" = "$h" ] && echo "  restaurado: $h OK" || echo "  RESTAURO MAL: $h_js_antes -> $h"
echo

# ------------------- P3 · UN INTERCAMBIO entre dos claves que YA estan en pantalla (A43)
cp "$JS" "$TMP/js.bak"
"$PY" - "$JS" <<'PY'
import pathlib, sys
f = pathlib.Path(sys.argv[1]); t = f.read_text(encoding="utf-8")
# Se INTERCAMBIAN las claves de `state` y `reason`: las dos siguen en pantalla, asi que un
# comparador por CONJUNTOS de claves no veria nada. La pareja (clave, valor) si.
a = "  campos.appendChild(celda('state', 'estado', dec.state));"
b = "  campos.appendChild(celda('reason', 'razón', dec.reason));"
assert a in t and b in t, "no encontre las dos lineas del intercambio"
t = t.replace(a, "  campos.appendChild(celda('state', 'estado', dec.reason));", 1)
t = t.replace(b, "  campos.appendChild(celda('reason', 'razón', dec.state));", 1)
f.write_text(t, encoding="utf-8")
PY
echo "P3 · INTERCAMBIO de state y reason  (mesa-decide.js -> $(sha256sum "$JS" | cut -c1-16))"
espero_condena "B3 tiene que ver un intercambio" "$JS" "B3: "
cp "$TMP/js.bak" "$JS"
h=$(sha256sum "$JS" | cut -c1-16)
[ "$h_js_antes" = "$h" ] && echo "  restaurado: $h OK" || echo "  RESTAURO MAL: $h_js_antes -> $h"
echo

# ------------------------------- P4 · una celda que se pinta SIN declarar su clave
cp "$JS" "$TMP/js.bak"
"$PY" - "$JS" <<'PY'
import pathlib, sys
f = pathlib.Path(sys.argv[1]); t = f.read_text(encoding="utf-8")
viejo = "  if (campo.source_key) caja.appendChild(nodoClave(campo.source_key));"
nuevo = "  if (campo.source_key && nombre !== 'evidence') caja.appendChild(nodoClave(campo.source_key));"
assert viejo in t, "no encontre la linea de la clave"
f.write_text(t.replace(viejo, nuevo, 1), encoding="utf-8")
PY
echo "P4 · la celda 'evidence' deja de declarar su clave  (-> $(sha256sum "$JS" | cut -c1-16))"
espero_condena "B3 tiene que exigir la procedencia" "$JS" "SIN declarar su source_key"
cp "$TMP/js.bak" "$JS"
h=$(sha256sum "$JS" | cut -c1-16)
[ "$h_js_antes" = "$h" ] && echo "  restaurado: $h OK" || echo "  RESTAURO MAL: $h_js_antes -> $h"
echo

# --------------------- P5 · la regla del handoff, rota en la direccion que importa
cp "$JS" "$TMP/js.bak"
"$PY" - "$JS" <<'PY'
import pathlib, sys
f = pathlib.Path(sys.argv[1]); t = f.read_text(encoding="utf-8")
# El sobre del espejo dice evaluable=false. Si la pantalla escribiera un sesgo de todas formas
# -que es el defecto que la regla del handoff prohibe-, B5 tiene que condenar.
viejo = "  const palabra = esNada(sesgo.value) ? 'SIN DATO' : String(sesgo.value);"
nuevo = "  const palabra = 'LONG';"
assert viejo in t, "no encontre la linea del sesgo"
f.write_text(t.replace(viejo, nuevo, 1), encoding="utf-8")
PY
echo "P5 · la pantalla pone LONG con un sobre que dice evaluable=false  (-> $(sha256sum "$JS" | cut -c1-16))"
espero_condena "B5 tiene que condenar la regla de <70" "$JS" "B5: "
cp "$TMP/js.bak" "$JS"
h=$(sha256sum "$JS" | cut -c1-16)
[ "$h_js_antes" = "$h" ] && echo "  restaurado: $h OK" || echo "  RESTAURO MAL: $h_js_antes -> $h"
echo

# --------------- P6 · LA RED CONTRA LOS BYTES DE ANTES DE LA MESA (origin/main)
# A57 pide que un control nuevo se ejercite contra los BYTES VIEJOS y que se publique cuantos
# brazos fallan ahi. Aqui el resultado es el que importa entender: en `origin/main` la mesa NO
# EXISTE, asi que `/mesa` no se sirve y la sonda no puede cosechar.
#
# LO QUE ESO TIENE QUE DAR ES **NO MEDIDO**, NO VERDE. Es el tercer estado: una red que no
# encuentra a su sujeto no lo absuelve. Si K102 diera 0 hallazgos y rc=0 sobre un arbol SIN
# mesa, estaria contando «no he mirado» como «esta bien», que es el defecto que este arnes ya
# pago dos veces. Asi que el control EXIGE rc=2 aqui.
echo "P6 · la red contra los BYTES de origin/main (sin mesa)"
total=$((total + 1))
OLD="$TMP/viejo"
if ! git -C "$REPO" rev-parse --verify --quiet origin/main >/dev/null; then
  echo "  NO MEDIDO: no hay origin/main en este repo: el brazo de los bytes viejos no se puede correr"
  falla=$((falla + 1))
else
  sha_old=$(git -C "$REPO" rev-parse --short origin/main)
  mkdir -p "$OLD"
  git -C "$REPO" archive origin/main | tar -x -C "$OLD" 2>/dev/null
  tiene_mesa=0
  [ -f "$OLD/static/mesa.html" ] && tiene_mesa=1
  grep -q '"/api/mesa/decide"' "$OLD/app/api.py" 2>/dev/null && tiene_mesa=$((tiene_mesa + 1))
  echo "  origin/main = $sha_old · static/mesa.html presente: $([ -f "$OLD/static/mesa.html" ] && echo si || echo NO) ·"\
       "ruta /api/mesa/decide en su app/api.py: $(grep -qc '"/api/mesa/decide"' "$OLD/app/api.py" 2>/dev/null && echo si || echo NO)"
  # Se levanta la app de ESOS bytes, con el .venv de aqui, contra el espejo.
  PUERTO=8097
  ( cd "$OLD" && PG_HOST=/var/run/postgresql PG_PORT=5432 PG_DB=coinalyze_espejo \
      PG_USER="$(id -un)" PG_PASSWORD= API_INTERNAL_TOKEN=k102control \
      nohup "$PY" -m uvicorn app.api:app --host 127.0.0.1 --port "$PUERTO" \
      > "$TMP/viejo.log" 2>&1 & echo $! > "$TMP/viejo.pid" )
  sleep 7
  rc_viejo=$(MESA_BASE="http://127.0.0.1:$PUERTO" K102_CABECERA="X-Internal-Token: k102control" \
             bash "$CHECK" > "$TMP/sal_viejo" 2>&1; echo $?)
  # `grep -c` sale 1 cuando no casa nada, y un `|| echo 0` detras imprime DOS lineas: la del
  # grep y el 0. Se cuenta con wc, que siempre sale 0.
  n_hall=$(grep -E '^   - ' "$TMP/sal_viejo" 2>/dev/null | wc -l | tr -d ' ')
  echo "  rc=$rc_viejo · hallazgos enumerados: $n_hall"
  sed -n '1,4p' "$TMP/sal_viejo" | sed 's/^/      /'
  if [ "$rc_viejo" = "2" ]; then
    pasa=$((pasa + 1))
    echo "  CORRECTO  sobre los bytes sin mesa la red sale NO MEDIDO (rc=2), no VERDE:"
    echo "            0 brazos condenan porque el SUJETO NO EXISTE, y eso no es un aprobado."
  else
    falla=$((falla + 1))
    echo "  MAL       esperaba rc=2 (NO MEDIDO) sobre un arbol sin mesa y salio rc=$rc_viejo"
  fi
  [ -f "$TMP/viejo.pid" ] && kill "$(cat "$TMP/viejo.pid")" 2>/dev/null
  sleep 1
fi
echo

# ------------------------------------------------------------------ RESUMEN
echo "RESUMEN: $pasa de $total plantados se comportan como debian"
[ "$falla" = "0" ] || exit 1
exit 0
