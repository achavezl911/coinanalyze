#!/bin/bash
# K102-control · UN PLANTADO QUE TIENE QUE FALLAR POR CADA COSA QUE K102 PROMETE,
#                Y UN GEMELO FIEL QUE TIENE QUE PASAR POR CADA COSA QUE K102 NO DEBE CONDENAR
#
# POR QUE LAS DOS MITADES. Un check que condena todo es tan inutil como uno que no condena
# nada, y el segundo error es el que costo esta ronda: K102 condenaba paginas IMPECABLES por
# dos caminos -la precision del redondeo y un segundo sobre que nadie pinto-. Desde aqui, cada
# promesa se ataca con un PLANTADO que tiene que condenar, y cada cosa que NO es un defecto se
# defiende con un GEMELO que tiene que pasar.
#
# UN PLANTADO QUE NO LLEGA A APLICARSE NO ES UN APROBADO. Si el parche no encuentra su linea
# -porque el codigo cambio debajo-, el sujeto nunca se planto y el check midio un arbol sano:
# eso es NO MEDIDO, no «la red no caza». La version anterior lo contaba como fallo de la red y
# acusaba al instrumento de un descuido del control. Por eso cada plantado COMPARA LA HUELLA
# antes y despues y se planta solo si de verdad cambio.
#
# SE INVOCA DE LAS TRES FORMAS (A56).
set -u

D="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # ABSOLUTA ANTES de cualquier cd
B=/srv/coinanalyze/harness
[ -r "$B/env" ] || { echo "NO MEDIDO: no se pudo resolver $B/env"; exit 2; }
. "$B/env"
AYUDANTE_CARGADO=1
[ "${AYUDANTE_CARGADO:-0}" = "1" ] || { echo "NO MEDIDO: el env no cargo"; exit 2; }
REPO="${REPO:-/srv/coinanalyze/repo}"
PY="$REPO/.venv/bin/python"
CHECK="$D/K102-decide-lo-primero.sh"
PLANTADO="$D/K102-sobre-plantado.py"
[ -r "$CHECK" ]    || { echo "NO MEDIDO: falta $CHECK"; exit 2; }
[ -r "$PLANTADO" ] || { echo "NO MEDIDO: falta $PLANTADO"; exit 2; }

BASE="${MESA_BASE:-}"
[ -n "$BASE" ] || { echo "NO MEDIDO: hace falta MESA_BASE=<url que sirva el ARBOL>"; exit 2; }

CSS="$REPO/static/mesa/mesa.css"
JS="$REPO/static/mesa/mesa-decide.js"
APP="$REPO/static/mesa/mesa-app.js"
CTX="$REPO/app/ai_context.py"

TMP="$(mktemp -d)" || exit 2
limpia() {
  rm -rf "$TMP"
  pkill -f '[K]102-sobre-plantado.py' 2>/dev/null
  pkill -f '[u]vicorn app.api:app --host 127.0.0.1 --port 8095' 2>/dev/null
}
trap limpia EXIT INT TERM

pasa=0; falla=0; nomed=0; total=0

huella() { sha256sum "$1" | cut -c1-16; }

juzga() {  # juzga [base] -> rc
  local b="${1:-$BASE}"
  MESA_BASE="$b" K102_OBSERVA="${K102_OBSERVA:-18}" bash "$CHECK" > "$TMP/sal" 2>&1
  echo $?
}

# espera <CONDENA|PASA> <rotulo> <patron> [base]
espera() {
  local quiero="$1" rot="$2" patron="$3" b="${4:-$BASE}"
  total=$((total + 1))
  local rc; rc=$(juzga "$b")
  if [ "$quiero" = "CONDENA" ]; then
    if [ "$rc" = "1" ] && grep -q "$patron" "$TMP/sal"; then
      pasa=$((pasa + 1))
      printf '  CONDENA   %-44s rc=%s · %s\n' "$rot" "$rc" \
        "$(grep -m1 "$patron" "$TMP/sal" | sed 's/^ *//' | cut -c1-92)"
    else
      falla=$((falla + 1))
      printf '  NO CAZA   %-44s rc=%s  <-- el plantado paso sin condena\n' "$rot" "$rc"
      sed -n '1,6p' "$TMP/sal" | sed 's/^/      /'
    fi
  else
    if [ "$rc" = "0" ]; then
      pasa=$((pasa + 1))
      printf '  PASA      %-44s rc=0 · la pagina FIEL no se condena\n' "$rot"
    else
      falla=$((falla + 1))
      printf '  CONDENA MAL %-42s rc=%s  <-- condena una pagina FIEL\n' "$rot" "$rc"
      grep -E '^   - ' "$TMP/sal" | sed 's/^/      /' | head -5
    fi
  fi
}

# planta <fichero> <rotulo> ; usa $TMP/parche.py. Devuelve 0 si de verdad cambio el fichero.
planta() {
  local f="$1" rot="$2"
  local antes; antes=$(huella "$f")
  cp "$f" "$TMP/bak"
  "$PY" "$TMP/parche.py" "$f" > "$TMP/parche.log" 2>&1
  local despues; despues=$(huella "$f")
  if [ "$antes" = "$despues" ]; then
    total=$((total + 1)); nomed=$((nomed + 1))
    printf '  NO MEDIDO %-44s el parche NO aplico: %s\n' "$rot" \
      "$(tail -1 "$TMP/parche.log" | cut -c1-70)"
    printf '            (el sujeto nunca se planto; esto NO es que la red no cace)\n'
    cp "$TMP/bak" "$f"
    return 1
  fi
  printf '%s · huella %s -> %s\n' "$rot" "$antes" "$despues"
  return 0
}

restaura() {  # restaura <fichero> <huella esperada>
  local f="$1" esperada="$2"
  cp "$TMP/bak" "$f"
  local h; h=$(huella "$f")
  if [ "$h" = "$esperada" ]; then
    echo "  restaurado: $h OK"
  else
    echo "  RESTAURO MAL: esperaba $esperada y quedo $h"
    falla=$((falla + 1))
  fi
}

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
  sed -n '1,10p' "$TMP/sal" | sed 's/^/      /'
  echo; echo "RESUMEN: $pasa de $total"
  exit 1
fi
echo

h_css=$(huella "$CSS"); h_js=$(huella "$JS"); h_app=$(huella "$APP"); h_ctx=$(huella "$CTX")

# --------------------------------------------- P1 · DECIDE por DEBAJO del pliegue
cat > "$TMP/parche.py" <<'PY'
import pathlib, sys
f = pathlib.Path(sys.argv[1])
f.write_text(f.read_text(encoding="utf-8")
             + "\n/* PLANTADO K102-control P1 */\n.scan { min-height: 1200px; }\n",
             encoding="utf-8")
PY
if planta "$CSS" "P1 · DECIDE empujado por debajo del pliegue"; then
  espera CONDENA "B1 tiene que condenar el pliegue" "B1 "
  restaura "$CSS" "$h_css"
fi
echo

# ------------------------------- P2 · un valor de DECIDE que NO sale del sobre
# MUTAR NO ES PREFIJAR: se REEMPLAZA. Prefijar dejaria el valor bueno dentro de la cadena.
cat > "$TMP/parche.py" <<'PY'
import pathlib, sys
f = pathlib.Path(sys.argv[1]); t = f.read_text(encoding="utf-8")
viejo = "  if (hay('state')) campos.appendChild(celda('state', 'estado', origen.state));"
nuevo = ("  if (hay('state')) campos.appendChild(celda('state', 'estado',\n"
         "    Object.assign({}, origen.state, {value: 'Valor Inventado'})));")
assert viejo in t, "no encontre la linea de `state`"
f.write_text(t.replace(viejo, nuevo, 1), encoding="utf-8")
PY
if planta "$JS" "P2 · el campo 'state' pintado con una constante"; then
  espera CONDENA "B3 tiene que condenar el valor" "el valor de la celda no es el servido"
  restaura "$JS" "$h_js"
fi
echo

# ------------------- P3 · UN INTERCAMBIO entre dos claves que YA estan en pantalla (A43)
cat > "$TMP/parche.py" <<'PY'
import pathlib, sys
f = pathlib.Path(sys.argv[1]); t = f.read_text(encoding="utf-8")
a = "  if (hay('state')) campos.appendChild(celda('state', 'estado', origen.state));"
b = "  if (hay('reason')) campos.appendChild(celda('reason', 'razón', origen.reason));"
assert a in t and b in t, "no encontre las dos lineas del intercambio"
t = t.replace(a, "  if (hay('state')) campos.appendChild(celda('state', 'estado', origen.reason));", 1)
t = t.replace(b, "  if (hay('reason')) campos.appendChild(celda('reason', 'razón', origen.state));", 1)
f.write_text(t, encoding="utf-8")
PY
if planta "$JS" "P3 · INTERCAMBIO de state y reason"; then
  espera CONDENA "B3 tiene que ver un intercambio" "B3: "
  restaura "$JS" "$h_js"
fi
echo

# ------------------------------- P4 · una celda que se pinta SIN declarar su clave
cat > "$TMP/parche.py" <<'PY'
import pathlib, sys
f = pathlib.Path(sys.argv[1]); t = f.read_text(encoding="utf-8")
viejo = "  if (campo.source_key) caja.appendChild(nodoClave(campo.source_key));"
nuevo = "  if (campo.source_key && nombre !== 'evidence') caja.appendChild(nodoClave(campo.source_key));"
assert viejo in t, "no encontre la linea de la clave"
f.write_text(t.replace(viejo, nuevo, 1), encoding="utf-8")
PY
if planta "$JS" "P4 · 'evidence' deja de declarar su clave"; then
  espera CONDENA "B3 tiene que exigir la procedencia" "SIN declarar su source_key"
  restaura "$JS" "$h_js"
fi
echo

# --------------------- P5 · la regla del handoff, rota en la direccion que importa
cat > "$TMP/parche.py" <<'PY'
import pathlib, sys
f = pathlib.Path(sys.argv[1]); t = f.read_text(encoding="utf-8")
viejo = "  const palabra = esNada(sesgo.value) ? 'SIN DATO' : String(sesgo.value);"
nuevo = "  const palabra = 'LONG';"
assert viejo in t, "no encontre la linea del sesgo"
f.write_text(t.replace(viejo, nuevo, 1), encoding="utf-8")
PY
if planta "$JS" "P5 · la pantalla pone LONG con evaluable=false"; then
  espera CONDENA "B5 tiene que condenar la regla de <70" "B5: "
  restaura "$JS" "$h_js"
fi
echo

# --------------------- P7 · R1 · la palabra de un marco no scalp vuelve a ser la del scalp
# EL PLANTADO VA EN EL BACKEND, que es de quien es la promesa: la RUTA sirve NO EVALUABLE para
# un marco que no es scalp. Plantarlo solo en el cliente mediria la mitad.
cat > "$TMP/parche.py" <<'PY'
import pathlib, sys
f = pathlib.Path(sys.argv[1]); t = f.read_text(encoding="utf-8")
viejo = '    es_scalp = frame == "scalp"'
nuevo = '    es_scalp = True  # PLANTADO K102-control P7'
assert viejo in t, "no encontre la linea de `es_scalp`"
f.write_text(t.replace(viejo, nuevo, 1), encoding="utf-8")
PY
if planta "$CTX" "P7 · la ruta vuelve a dar la lectura del scalp en swing y largo"; then
  # hace falta un servidor NUEVO: el modulo ya esta importado en el que corre.
  ( cd "$REPO" && PG_HOST=/var/run/postgresql PG_PORT=5432 PG_DB=coinalyze_espejo \
      PG_USER="$(id -un)" PG_PASSWORD= API_INTERNAL_TOKEN=k102p7 \
      nohup "$PY" -m uvicorn app.api:app --host 127.0.0.1 --port 8095 \
      > "$TMP/p7.log" 2>&1 & )
  sleep 8
  K102_CABECERA="X-Internal-Token: k102p7" \
    espera CONDENA "B7 tiene que condenar la lectura prestada" "B7 " "http://127.0.0.1:8095"
  pkill -f '[u]vicorn app.api:app --host 127.0.0.1 --port 8095' 2>/dev/null
  sleep 1
  restaura "$CTX" "$h_ctx"
fi
echo

# --------------------------- P8 · R3 · la edad deja de avanzar (se quita el latido)
cat > "$TMP/parche.py" <<'PY'
import pathlib, sys
f = pathlib.Path(sys.argv[1]); t = f.read_text(encoding="utf-8")
viejo = "  arrancarLatido();"
nuevo = "  /* PLANTADO K102-control P8: sin latido */"
assert viejo in t, "no encontre la llamada a arrancarLatido"
f.write_text(t.replace(viejo, nuevo, 1), encoding="utf-8")
PY
if planta "$APP" "P8 · la mesa se queda sin latido"; then
  espera CONDENA "B8 tiene que condenar una edad congelada" "B8: "
  restaura "$APP" "$h_app"
fi
echo

# --------------- G1 y G2 · LOS GEMELOS FIELES, que TIENEN que pasar -------------------
# G1 · la pagina pinta 63.385,5 sobre un servido 63385.45, 63.000,0 sobre 62999.99 y 71 %
#      sobre 71.429. Es un REDONDEO FIEL y la red NO puede condenarlo. Esta es la primera de
#      las dos formas en que K102 condenaba paginas impecables.
# G2 · el sobre CAMBIA en cada peticion. Es la segunda forma: la red comparaba contra un
#      sobre pedido aparte, asi que el mercado moviendose entre dos peticiones la volvia loca.
#      Ahora compara contra el cuerpo QUE LA PAGINA RECIBIO, asi que esto le da igual.
for modo in fiel varia; do
  extra=""; rot="G1 · redondeo fiel (63385.45 -> '63.385,5')"
  if [ "$modo" = "varia" ]; then
    extra="--varia"; rot="G2 · el sobre cambia en CADA peticion"
  fi
  pkill -f '[K]102-sobre-plantado.py' 2>/dev/null; sleep 1
  # shellcheck disable=SC2086
  nohup "$PY" "$PLANTADO" --puerto 8096 --lag 3 --tope 600 --bias LONG --dc 100 $extra \
    > "$TMP/plantado.log" 2>&1 &
  sleep 3
  K102_OBSERVA=4 espera PASA "$rot" "" "http://127.0.0.1:8096"
  pkill -f '[K]102-sobre-plantado.py' 2>/dev/null
done
echo

# --------------- G3 · R3 · un DECIDE FRESCO abierto mas alla de su tope dice RANCIO ----
# El espejo sirve un snapshot de hace 46 dias: nace rancio, asi que con el NO se puede ver la
# TRANSICION, que es lo que se promete. Con un sobre fresco (lag 3 s) y un tope de 8 s, la
# pantalla tiene que pasar a RANCIO SOLA mientras se la mira.
total=$((total + 1))
pkill -f '[K]102-sobre-plantado.py' 2>/dev/null; sleep 1
nohup "$PY" "$PLANTADO" --puerto 8096 --lag 3 --tope 8 --bias LONG --dc 100 --sin-refresco \
  > "$TMP/plantado.log" 2>&1 &
sleep 3
"$PY" "$D/K102-mesa.py" --base http://127.0.0.1:8096 --marco scalp --activo BTC \
  --ancho 1920 --alto 1080 --frio --repite 1 --espera 25 --observa 14 \
  --salida "$TMP/g3.json" > /dev/null 2>&1
if [ ! -s "$TMP/g3.json" ]; then
  nomed=$((nomed + 1))
  echo "  NO MEDIDO G3 · la sonda no pudo observar la transicion a RANCIO"
else
  "$PY" - "$TMP/g3.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
m = (d.get("observacion") or {}).get("muestras") or []
antes = [x for x in m if x.get("edad_s") is not None and x["edad_s"] <= 8]
despues = [x for x in m if x.get("edad_s") is not None and x["edad_s"] > 8]
ok = (antes and despues
      and not any(x["dice_rancio"] for x in antes)
      and all(x["dice_rancio"] for x in despues))
print("  " + ("PASA      " if ok else "MAL       ")
      + "G3 · un DECIDE fresco pasa a RANCIO SOLO             "
      + f"{len(antes)} muestra(s) por debajo del tope sin RANCIO, "
      + f"{len(despues)} por encima con RANCIO")
if m:
    print("            serie: "
          + " ".join(f"{x.get('edad_s')}{'R' if x.get('dice_rancio') else '.'}" for x in m[:14]))
raise SystemExit(0 if ok else 1)
PY
  if [ "$?" = "0" ]; then pasa=$((pasa + 1)); else falla=$((falla + 1)); fi
fi
pkill -f '[K]102-sobre-plantado.py' 2>/dev/null
echo

# ------------------------------------------------------------------ P6 · bytes viejos
echo "P6 · la red contra los BYTES de origin/main (sin mesa)"
total=$((total + 1))
OLD="$TMP/viejo"
if ! git -C "$REPO" rev-parse --verify --quiet origin/main >/dev/null; then
  echo "  NO MEDIDO: no hay origin/main en este repo"
  nomed=$((nomed + 1))
else
  sha_old=$(git -C "$REPO" rev-parse --short origin/main)
  mkdir -p "$OLD"
  git -C "$REPO" archive origin/main | tar -x -C "$OLD" 2>/dev/null
  echo "  origin/main = $sha_old · static/mesa.html presente: $([ -f "$OLD/static/mesa.html" ] && echo si || echo NO)"
  PUERTO=8097
  ( cd "$OLD" && PG_HOST=/var/run/postgresql PG_PORT=5432 PG_DB=coinalyze_espejo \
      PG_USER="$(id -un)" PG_PASSWORD= API_INTERNAL_TOKEN=k102control \
      nohup "$PY" -m uvicorn app.api:app --host 127.0.0.1 --port "$PUERTO" \
      > "$TMP/viejo.log" 2>&1 & )
  sleep 7
  rc_viejo=$(MESA_BASE="http://127.0.0.1:$PUERTO" K102_CABECERA="X-Internal-Token: k102control" \
             K102_OBSERVA=4 bash "$CHECK" > "$TMP/sal_viejo" 2>&1; echo $?)
  echo "  rc=$rc_viejo · $(head -1 "$TMP/sal_viejo" | cut -c1-90)"
  if [ "$rc_viejo" = "2" ]; then
    pasa=$((pasa + 1))
    echo "  CORRECTO  sobre los bytes sin mesa la red sale NO MEDIDO (rc=2), no VERDE:"
    echo "            0 brazos condenan porque el SUJETO NO EXISTE, y eso no es un aprobado."
  else
    falla=$((falla + 1))
    echo "  MAL       esperaba rc=2 (NO MEDIDO) sobre un arbol sin mesa y salio rc=$rc_viejo"
  fi
  pkill -f "[u]vicorn app.api:app --host 127.0.0.1 --port $PUERTO" 2>/dev/null
  sleep 1
  vivos=$(ps -eo cmd | grep -cE "[u]vicorn app.api:app --host 127.0.0.1 --port $PUERTO")
  [ "$vivos" = "0" ] || echo "  AVISO: quedo un uvicorn en $PUERTO; matalo a mano"
fi
echo

echo "RESUMEN: $pasa de $total se comportan como debian ($falla mal, $nomed no medidos)"
[ "$falla" = "0" ] && [ "$nomed" = "0" ] || exit 1
exit 0
