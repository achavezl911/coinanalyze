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
  # EL PATRON VA CON CORCHETE Y CON EL NOMBRE DEL MODULO PROPIO: un `pkill -f banco` se casaria
  # con cualquier proceso que lleve esa palabra, incluida esta misma linea de ordenes.
  pkill -f '[b]anco132:app' 2>/dev/null
}
trap limpia EXIT INT TERM

pasa=0; falla=0; nomed=0; total=0

huella() { sha256sum "$1" | cut -c1-16; }

# LOS PLANTADOS SE JUZGAN EN **UN** ACTIVO, Y LA LINEA BASE EN LOS TRES.
# Ninguno de los parches de este control es del activo -van en el CSS, en el JS o en la ruta- y
# el sobre plantado sirve lo MISMO para los tres. Barrer los tres en cada plantado multiplicaria
# por tres las 18 vistas sin anadir una sola medida. La linea base si los barre: ahi el sujeto es
# la mesa de verdad y el margen del pliegue SI depende del activo (A81).
CTRL_ACTIVOS="${CTRL_ACTIVOS:-SOL}"

juzga() {  # juzga [base] -> rc
  local b="${1:-$BASE}"
  MESA_BASE="$b" K102_OBSERVA="${K102_OBSERVA:-18}" K102_ACTIVOS="$CTRL_ACTIVOS" \
    bash "$CHECK" > "$TMP/sal" 2>&1
  echo $?
}

# espera <CONDENA|PASA> <rotulo> <patron> [base]
#
# EL PATRON SE BUSCA EN LAS LINEAS DE HALLAZGO, NO EN TODA LA SALIDA, Y ESO ES UN ARREGLO.
# La salida del check ahora dice «B3, B4, B5, B7 y B8 solo en SOL» en su linea de ALCANCE, asi
# que un patron «B7 » casaba con esa linea y daba por bueno un `rc=1` que podia venir de
# cualquier otro brazo. Los hallazgos se imprimen con el prefijo «   - », y es ahi donde se
# busca. Un patron que casa con la prosa del veredicto absuelve por homonimia (A43).
espera() {
  local quiero="$1" rot="$2" patron="$3" b="${4:-$BASE}"
  total=$((total + 1))
  local rc; rc=$(juzga "$b")
  grep -E '^   - ' "$TMP/sal" > "$TMP/hallazgos" 2>/dev/null || : > "$TMP/hallazgos"
  if [ "$quiero" = "CONDENA" ]; then
    if [ "$rc" = "1" ] && grep -q "$patron" "$TMP/hallazgos"; then
      pasa=$((pasa + 1))
      printf '  CONDENA   %-44s rc=%s · %s\n' "$rot" "$rc" \
        "$(grep -m1 "$patron" "$TMP/hallazgos" | sed 's/^ *//' | cut -c1-92)"
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
rc0=$(CTRL_ACTIVOS="BTC ETH SOL" juzga)
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
# LO QUE `evaluable` DECIDE HOY ES EL RAYADO, no la palabra (v2 del sobre). Asi que el plantado
# es el que le quita el rayado: con calidad 0 en el espejo la tarjeta TIENE que salir rayada.
cat > "$TMP/parche.py" <<'PY'
import pathlib, sys
f = pathlib.Path(sys.argv[1]); t = f.read_text(encoding="utf-8")
viejo = "  caja.classList.toggle('no-evaluable', !evaluable);"
nuevo = "  caja.classList.remove('no-evaluable');  // PLANTADO K102-control P5"
assert viejo in t, "no encontre la linea del rayado de no-evaluable"
f.write_text(t.replace(viejo, nuevo, 1), encoding="utf-8")
PY
if planta "$JS" "P5 · la tarjeta deja de rayarse con evaluable=false"; then
  espera CONDENA "B5 tiene que condenar la regla del umbral" "B5: "
  restaura "$JS" "$h_js"
fi
echo

# ---------- P10 · C1 · LA PALABRA CONTRA EL ESTADO, en las dos direcciones -------------
# EL BANCO TIENE QUE TENER LAS DOS COSAS A LA VEZ, y por eso va contra el sobre PLANTADO: el
# espejo da `state = 'Sin datos suficientes'` en los tres activos desde el 08-13, asi que ni
# puede ensenar «el sistema decide» ni puede hacer discrepar la palabra del estado (A83).
# Cinco combinaciones, tres que TIENEN que condenar y dos gemelas que TIENEN que pasar.
#
#   quiero    bias           state             por que
#   CONDENA   LONG           No Trade          dice un lado que el sistema NO toma (el defecto
#                                              medido en produccion el 05:24:30Z: SHORT con
#                                              «No Trade» y edge 5.0)
#   PASA      NO OPERAR      No Trade          la palabra correcta para esa decision
#   CONDENA   NO OPERAR      Short Rejection   CALLA un lado que el sistema SI toma
#   PASA      SHORT          Short Rejection   la palabra correcta para esa decision
#   CONDENA   LONG           Long Breakout     un estado que hoy no existe NO se vuelve un lado
#                                              por parecerse a uno
echo "P10 · C1 · la palabra contra el estado de la MISMA respuesta (sobre plantado)"
p10() {  # p10 <CONDENA|PASA> <bias> <state> <rotulo>
  pkill -f '[K]102-sobre-plantado.py' 2>/dev/null; sleep 1
  nohup "$PY" "$PLANTADO" --puerto 8096 --lag 3 --tope 600 \
    --bias "$2" --state "$3" --balance Long --dc 100 > "$TMP/plantado.log" 2>&1 &
  sleep 3
  K102_OBSERVA=4 espera "$1" "$4" "B9 " "http://127.0.0.1:8096"
  pkill -f '[K]102-sobre-plantado.py' 2>/dev/null
}
p10 CONDENA "LONG"      "No Trade"        "P10a · LONG con ESTADO 'No Trade'"
p10 PASA    "NO OPERAR" "No Trade"        "G5 · NO OPERAR con ESTADO 'No Trade'"
p10 CONDENA "NO OPERAR" "Short Rejection" "P10b · calla el lado de 'Short Rejection'"
p10 PASA    "SHORT"     "Short Rejection" "G6 · SHORT con ESTADO 'Short Rejection'"
p10 CONDENA "LONG"      "Long Breakout"   "P10c · un estado que NO existe no da lado"
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
  extra=""; rot="G1 · redondeo fiel (63385.45 -> '63.385,5')"; obs=4
  if [ "$modo" = "varia" ]; then
    # G2 CON OBSERVACION LARGA A PROPOSITO: con 18 s el refresco de 15 s CAE DENTRO de la
    # corrida, asi que la pagina recibe DOS respuestas DISTINTAS -`edge` +1 en la segunda- y
    # pinta la primera. Es exactamente el caso que condenaba una pagina fiel («B3: edge:
    # pantalla '80,20' / sobre 81.2» con «2 peticion(es) vistas»). Con observacion corta este
    # gemelo no probaria nada, porque el refresco no llegaria a entrar.
    extra="--varia"; obs=18
    rot="G2 · DOS respuestas distintas en la MISMA carga"
  fi
  pkill -f '[K]102-sobre-plantado.py' 2>/dev/null; sleep 1
  # shellcheck disable=SC2086
  nohup "$PY" "$PLANTADO" --puerto 8096 --lag 3 --tope 600 --bias LONG --dc 100 $extra \
    > "$TMP/plantado.log" 2>&1 &
  sleep 3
  K102_OBSERVA=$obs espera PASA "$rot" "" "http://127.0.0.1:8096"
  if [ "$modo" = "varia" ]; then
    printf '            %s\n' "$(grep -m1 'el patron de comparacion' "$TMP/sal" | sed 's/^ *//' | cut -c1-140)"
  fi
  pkill -f '[K]102-sobre-plantado.py' 2>/dev/null
done
echo

# ------- P9 · R6 · DECIDE sale del pliegue SOLO en swing y largo ----------------------
# El plantado va en el BACKEND y devuelve el motivo largo de 211 caracteres que tenia antes:
# solo afecta a los marcos que NO son scalp -que son los unicos que lo publican- y estira la
# tarjeta en la columna estrecha de DECIDE. Un plantado de CSS empujaria los TRES marcos y no
# distinguiria esta regresion de cualquier otra.
cat > "$TMP/parche.py" <<'PY'
import pathlib, sys
f = pathlib.Path(sys.argv[1]); t = f.read_text(encoding="utf-8")
viejo = '        bias_motivo = f"la lectura del operador es del SCALP, no de {frame.upper()}"'
nuevo = ('        bias_motivo = (  # PLANTADO K102-control P9\n'
         '            f"la lectura del operador (operator_read) se calcula sobre la ventana "\n'
         '            f"del SCALP -deltas de 1 y 3 min, libro L5, liquidaciones de 5 min-, asi "\n'
         '            f"que no es un veredicto de {frame.upper()}. Se ve como lo que es en "\n'
         '            f"/mesa#scalp/{WS_SYMBOL_MAP[symbol]}"\n'
         '        )')
assert viejo in t, "no encontre la linea del motivo"
f.write_text(t.replace(viejo, nuevo, 1), encoding="utf-8")
PY
if planta "$CTX" "P9 · el motivo largo vuelve, y estira DECIDE en swing y largo"; then
  ( cd "$REPO" && PG_HOST=/var/run/postgresql PG_PORT=5432 PG_DB=coinalyze_espejo \
      PG_USER="$(id -un)" PG_PASSWORD= API_INTERNAL_TOKEN=k102p9 \
      nohup "$PY" -m uvicorn app.api:app --host 127.0.0.1 --port 8095 \
      > "$TMP/p9.log" 2>&1 & )
  sleep 8
  K102_CABECERA="X-Internal-Token: k102p9" K102_OBSERVA=4 \
    espera CONDENA "B1 tiene que condenar el pliegue en swing/largo" "B1 " "http://127.0.0.1:8095"
  pkill -f '[u]vicorn app.api:app --host 127.0.0.1 --port 8095' 2>/dev/null
  sleep 1
  restaura "$CTX" "$h_ctx"
fi
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
TOPE = 8.0

# LA MUESTRA QUE CAE JUSTO EN EL TOPE NO SE JUZGA, Y ESTO ES UN FALLO QUE PAGUE.
#
# La pantalla escribe la edad REDONDEADA a un decimal (`num(v.s, 1)`), y este control lee ESE
# texto. Cuando la edad real es 8.04 la pantalla pone «8,0» -y dice RANCIO, correctamente,
# porque 8.04 > 8- pero aqui se leia 8.0, que NO es mayor que 8, y la muestra se contaba entre
# las que NO deberian decir RANCIO. Resultado: el control condenaba una pantalla que acertaba.
#
# Es EXACTAMENTE el mismo defecto que R2a -comparar un numero redondeado contra un umbral
# exacto- cometido esta vez en el propio control. Lo delataron las TRES invocaciones de A56:
# absoluta y ajena dieron 12 de 12 y la relativa 11 de 12, y la diferencia no era la ruta sino
# DONDE cayo el muestreo respecto al tope (serie `4.1 5.1 6.1 7.1 8.1R` contra `4 5 6 7 8R`).
#
# Asi que se deja una zona muerta de MEDIA UNIDAD del ultimo decimal pintado: lo que cae dentro
# no se cuenta ni a favor ni en contra, y se DECLARA. Un control que no puede decidir una
# muestra tiene que decirlo, no adjudicarsela al lado que le convenga.
ZONA = 0.05

def edad(x):
    return x.get("edad_s")

antes = [x for x in m if edad(x) is not None and edad(x) < TOPE - ZONA]
despues = [x for x in m if edad(x) is not None and edad(x) > TOPE + ZONA]
borde = [x for x in m if edad(x) is not None and abs(edad(x) - TOPE) <= ZONA]

ok = (antes and despues
      and not any(x["dice_rancio"] for x in antes)
      and all(x["dice_rancio"] for x in despues))
print("  " + ("PASA      " if ok else "MAL       ")
      + "G3 · un DECIDE fresco pasa a RANCIO SOLO             "
      + f"{len(antes)} muestra(s) por debajo del tope sin RANCIO, "
      + f"{len(despues)} por encima con RANCIO")
if borde:
    print(f"            {len(borde)} muestra(s) EN EL BORDE (+-{ZONA} s del tope) NO se juzgan: "
          "la pantalla redondea y el veredicto ahi es indecidible")
if m:
    print("            serie: "
          + " ".join(f"{x.get('edad_s')}{'R' if x.get('dice_rancio') else '.'}" for x in m[:14]))
raise SystemExit(0 if ok else 1)
PY
  if [ "$?" = "0" ]; then pasa=$((pasa + 1)); else falla=$((falla + 1)); fi
fi
pkill -f '[K]102-sobre-plantado.py' 2>/dev/null
echo

# --------- G4 · R5 · la tarjeta del scalp ensena el LADO del scalp cuando lo tiene ------
# LO QUE SE FUERZA CAMBIO, Y POR ESO: hasta la v1 del sobre bastaba forzar `data_confidence` a
# 85, porque la palabra salia del signo de los scores y la calidad era lo unico que la tapaba.
# Desde la v2 la palabra sale del `state`, y el espejo da `state = 'Sin datos suficientes'` en
# los tres activos: con la calidad a 85 seguiria sin haber lado, y este gemelo no mediria nada
# (A57 · un control que no varia la variable que decide da 8 de 8 sin medir). Asi que lo que se
# planta ahora es el ESTADO.
#   · con `state` 'Short Rejection' forzado, swing y largo publican en `lectura_scalp` EL MISMO
#     lado, confirms, invalidates e invalidation_level que publica scalp;
#   · con el estado REAL del espejo, los tres siguen diciendo «sin lado», que ahi SI es cierto.
# El segundo es el que impide que el arreglo sea «dar lado siempre».
echo "G4 · la tarjeta del scalp y su lado (con el ESTADO forzado, y el control con el real)"
total=$((total + 1))
"$PY" - <<'PY' > "$TMP/g4.txt" 2>&1
import asyncio, getpass, json
import asyncpg
import app.ai_context as ctx

SUMMARY = ctx.compute_scalp_summary

def con_estado(valor):
    def _f(c):
        s = dict(SUMMARY(c))
        s["state"] = valor
        return s
    return _f

def foto(d):
    dec = d.get("decide") or {}
    ls = d.get("lectura_scalp")
    o = ls if ls else dec
    return {
        "bias_scalp": ((ls or {}).get("bias") or dec.get("bias") or {}).get("value"),
        "state": (o.get("state") or {}).get("value"),
        "balance": (o.get("evidence_balance") or {}).get("value"),
        "confirms": [c.get("value") for c in (o.get("confirms") or [])],
        "n_inval": len([c for c in (o.get("invalidates") or []) if c.get("value")]),
        "nivel": (o.get("invalidation_level") or {}).get("value"),
    }

async def main():
    conn = await asyncpg.connect(
        f"postgresql://{getpass.getuser()}@/coinalyze_espejo?host=/var/run/postgresql")
    fallos = []
    try:
        # --- con el ESTADO forzado: los tres marcos tienen que coincidir, y tener lado
        ctx.compute_scalp_summary = con_estado("Short Rejection")
        for sym in ("BTCUSDT_PERP.A", "ETHUSDT_PERP.A", "SOLUSDT_PERP.A"):
            fotos = {m: foto(await ctx.build_mesa_decide(conn, sym, frame=m))
                     for m in ("scalp", "swing", "largo")}
            s = fotos["scalp"]
            if s["bias_scalp"] != "SHORT":
                fallos.append(f"{sym}: con state 'Short Rejection' el scalp sale "
                              f"{s['bias_scalp']}: el control no puede medir nada")
                continue
            for m in ("swing", "largo"):
                if fotos[m] != s:
                    fallos.append(f"{sym}/{m}: la tarjeta del scalp NO dice lo mismo que scalp: "
                                  f"{json.dumps(fotos[m], ensure_ascii=False)[:120]}")
            print(f"  {sym[:3]} state 'Short Rejection' -> scalp {s['bias_scalp']}, nivel "
                  f"{s['nivel']}, {len(s['confirms'])} confirms, {s['n_inval']} invalidates, "
                  f"balance {s['balance']!r} · swing y largo IDENTICOS: "
                  f"{fotos['swing'] == s and fotos['largo'] == s}")
        # --- CONTROL con el estado REAL: «sin lado» tiene que seguir siendo la respuesta
        ctx.compute_scalp_summary = SUMMARY
        for sym in ("BTCUSDT_PERP.A",):
            for m in ("scalp", "swing", "largo"):
                f = foto(await ctx.build_mesa_decide(conn, sym, frame=m))
                if f["bias_scalp"] != "NO EVALUABLE" or f["nivel"] is not None or f["n_inval"]:
                    fallos.append(f"CONTROL {sym}/{m}: con el estado real ({f['state']!r}) "
                                  f"deberia ser NO EVALUABLE y sin lado, y sale "
                                  f"{json.dumps(f)[:110]}")
            print(f"  {sym[:3]} estado real -> los tres marcos NO EVALUABLE y sin lado: "
                  f"{not fallos}")
    finally:
        ctx.compute_scalp_summary = SUMMARY
        await conn.close()
    for x in fallos:
        print("  FALLO:", x)
    raise SystemExit(1 if fallos else 0)

asyncio.run(main())
PY
if [ "$?" = "0" ]; then
  pasa=$((pasa + 1))
  echo "  PASA      G4 · la tarjeta del scalp dice su lado cuando lo tiene"
  sed -n '1,5p' "$TMP/g4.txt"
else
  falla=$((falla + 1))
  echo "  MAL       G4 · la tarjeta del scalp NO dice su lado"
  sed -n '1,8p' "$TMP/g4.txt"
fi
echo

# --------- P11 · C2 · LA PALABRA NO GIRA MAS QUE LA DECISION ---------------------------
# LA SERIE ES LA MEDIDA, y el plantado es EL CODIGO VIEJO, no un sobre construido: se corre la
# MISMA serie -los scores girando de lado en cada muestra y el `state` quieto en 'No Trade'-
# contra `origin/main` y contra la rama, en el MISMO proceso y sobre el MISMO espejo.
#   la rama       0 giros de la palabra    = los 0 giros del estado
#   origin/main   la palabra gira en cada muestra con el estado quieto  <- el plantado que falla
# Sin el brazo de origin/main esto seria un control que no varia la variable que decide (A57):
# con la palabra ya arreglada, «0 giros» sale gratis.
echo "P11 · C2 · la palabra no cambia de lado mas que la decision (serie de 20)"
total=$((total + 1))
VIEJO_C2="$TMP/viejo-c2"
if ! git -C "$REPO" rev-parse --verify --quiet origin/main >/dev/null; then
  nomed=$((nomed + 1))
  echo "  NO MEDIDO P11 · no hay origin/main para correr la serie del codigo viejo"
else
  mkdir -p "$VIEJO_C2"
  git -C "$REPO" archive origin/main | tar -x -C "$VIEJO_C2" 2>/dev/null
  "$PY" - "$REPO" "$VIEJO_C2" <<'PY' > "$TMP/p11.txt" 2>&1
import asyncio, getpass, importlib, sys
import asyncpg

RAMA, VIEJO = sys.argv[1], sys.argv[2]
N = 20

# LOS SCORES GIRAN, EL ESTADO NO. Es la franja que el defecto habitaba: `scalp_bias_label` pide
# edge >= 12 para salir de 'No Trade', asi que con |long - short| = 4 el estado esta quieto y el
# SIGNO de la resta cambia en cada muestra.
def serie(i):
    a, b = (52.0, 48.0) if i % 2 == 0 else (48.0, 52.0)
    return {"state": "No Trade", "long_score": a, "short_score": b}

def parchea(ctx):
    original = ctx.compute_scalp_summary
    caja = {"i": 0}
    def _f(c):
        s = dict(original(c))
        s.update(serie(caja["i"]))
        caja["i"] += 1
        return s
    ctx.compute_scalp_summary = _f

    # Y LA CALIDAD, A 85. Sin esto el control NO MIDE, y la primera corrida lo demostro: con la
    # calidad 0 del espejo la regla VIEJA tapaba la palabra con NO EVALUABLE en las 20 muestras
    # -0 giros- y el brazo del plantado se declaraba a si mismo no medido (A57). El giro de la
    # palabra vieja solo existe con la puerta de la calidad ABIERTA, que es como esta en
    # produccion: `data_confidence` 100.0 el 2026-09-30T05:24:30Z.
    orig_dc = ctx.data_confidence_row
    async def _dc(conn, symbol):
        fila = dict(await orig_dc(conn, symbol))
        fila["quality_score"] = 85.0
        fila["status"] = "ok"
        return fila
    ctx.data_confidence_row = _dc

def lado(palabra):
    return {"LONG": "long", "SHORT": "short"}.get(str(palabra))

async def mide(arbol, rotulo):
    for m in [k for k in list(sys.modules) if k == "app" or k.startswith("app.")]:
        del sys.modules[m]
    sys.path.insert(0, arbol)
    try:
        ctx = importlib.import_module("app.ai_context")
        assert ctx.__file__.startswith(arbol), f"{rotulo}: cargue {ctx.__file__}"
        parchea(ctx)
        conn = await asyncpg.connect(
            f"postgresql://{getpass.getuser()}@/coinalyze_espejo?host=/var/run/postgresql")
        try:
            palabras, estados = [], []
            for _ in range(N):
                d = await ctx.build_mesa_decide(conn, "BTCUSDT_PERP.A", frame="scalp")
                dec = d["decide"]
                palabras.append(dec["bias"]["value"])
                estados.append((dec.get("state") or {}).get("value"))
        finally:
            await conn.close()
    finally:
        sys.path.remove(arbol)
    gp = sum(1 for a, b in zip(palabras, palabras[1:])
             if lado(a) is not None and lado(b) is not None and lado(a) != lado(b))
    ge = sum(1 for a, b in zip(estados, estados[1:]) if a != b)
    print(f"  {rotulo}: {gp} giro(s) de lado de la PALABRA, {ge} cambio(s) de ESTADO "
          f"en {N} muestras · palabras vistas: {sorted(set(map(str, palabras)))} · "
          f"estados: {sorted(set(map(str, estados)))}")
    return gp, ge

async def main():
    gp_v, ge_v = await mide(VIEJO, "origin/main (el plantado)")
    gp_r, ge_r = await mide(RAMA, "la rama")
    fallos = []
    if gp_v <= ge_v:
        fallos.append("el codigo VIEJO no giro mas que el estado: el plantado no planto nada, "
                      "asi que este control no mide (A57)")
    if gp_r != ge_r:
        fallos.append(f"la rama gira {gp_r} vez/veces y el estado {ge_r}: la palabra sigue "
                      "girando por su cuenta")
    for x in fallos:
        print("  FALLO:", x)
    raise SystemExit(1 if fallos else 0)

asyncio.run(main())
PY
  if [ "$?" = "0" ]; then
    pasa=$((pasa + 1))
    echo "  PASA      P11 · la palabra gira lo que gira la decision, y el viejo giraba mas"
  else
    falla=$((falla + 1))
    echo "  MAL       P11 · la serie no se comporto como debia"
  fi
  sed -n '1,6p' "$TMP/p11.txt"
fi
echo

# --------- C3 · `operator_read` SE PUBLICA IGUAL QUE ANTES ------------------------------
# El encargo prohibe mover lo que el sistema calcula. `operator_read` es el bloque del que salen
# `/api/ai/context`, el prompt de la IA y el panel viejo: se construye con el arbol de la rama y
# con el de `origin/main` contra el MISMO espejo congelado, y se comparan los dos JSON.
echo "C3 · el bloque operator_read, la rama contra origin/main"
total=$((total + 1))
if [ ! -d "$VIEJO_C2/app" ]; then
  nomed=$((nomed + 1))
  echo "  NO MEDIDO C3 · no hay arbol de origin/main desplegado"
else
  cat > "$TMP/c3.py" <<'PY'
import asyncio, getpass, json, sys
sys.path.insert(0, sys.argv[1])
import asyncpg
import app.ai_context as ctx

async def main():
    assert ctx.__file__.startswith(sys.argv[1]), f"cargue el arbol equivocado: {ctx.__file__}"
    conn = await asyncpg.connect(
        f"postgresql://{getpass.getuser()}@/coinalyze_espejo?host=/var/run/postgresql")
    try:
        out = {}
        for sym in ("BTCUSDT_PERP.A", "ETHUSDT_PERP.A", "SOLUSDT_PERP.A"):
            as_of = await ctx.resolve_matrix_as_of(conn)
            c = await ctx.scalp_context(conn, sym, as_of)
            out[sym] = ctx.build_operator_read(ctx.compute_scalp_summary(c),
                                               await ctx.data_confidence_row(conn, sym))
        print(json.dumps(out, sort_keys=True, indent=1, default=str))
    finally:
        await conn.close()

asyncio.run(main())
PY
  ( cd "$VIEJO_C2" && "$PY" "$TMP/c3.py" "$VIEJO_C2" ) > "$TMP/c3-viejo.json" 2>&1
  ( cd "$REPO"     && "$PY" "$TMP/c3.py" "$REPO" )     > "$TMP/c3-nuevo.json" 2>&1
  hv=$(huella "$TMP/c3-viejo.json"); hn=$(huella "$TMP/c3-nuevo.json")
  if [ "$hv" = "$hn" ] && [ -s "$TMP/c3-nuevo.json" ] && grep -q '"bias"' "$TMP/c3-nuevo.json"; then
    pasa=$((pasa + 1))
    echo "  PASA      C3 · operator_read IDENTICO en los tres activos · huella $hn"
    echo "            $(grep -c '"' "$TMP/c3-nuevo.json") lineas con valor, 0 diferencias"
  else
    falla=$((falla + 1))
    echo "  MAL       C3 · operator_read cambio: viejo $hv / nuevo $hn"
    diff "$TMP/c3-viejo.json" "$TMP/c3-nuevo.json" | head -12 | sed 's/^/      /'
  fi
fi
echo

# ------------------------------------------------------------------ P6 · bytes viejos
# ESTE CONTROL CAMBIO DE PREGUNTA, Y LO DICE. Cuando se escribio, `origin/main` no traia la mesa
# y lo que se comprobaba era que la red saliese NO MEDIDO -no VERDE- sobre un arbol donde el
# sujeto no existe. Hoy `origin/main` ES la mesa desplegada, asi que la pregunta correcta es la
# del encargo: **sobre los BYTES de origin/main, la red tiene que CONDENAR la palabra de hoy.**
#
# Y EL BANCO ES LA MITAD DEL CONTROL (A83). El espejo da `state = 'Sin datos suficientes'` en los
# tres activos, y con eso la palabra vieja tambien sale NO EVALUABLE: ni condena ni absuelve
# nada. Asi que el banco FUERZA UN ESTADO DISTINTO POR ACTIVO -uno CON lado, uno sin lado y uno
# no evaluable- desde un envoltorio que vive en $TMP: los bytes de origin/main NO se tocan, y su
# huella se comprueba al final.
#
#   BTC -> Long Momentum          el sistema decide un lado
#   ETH -> No Trade               el sistema evaluo y no toma lado
#   SOL -> Sin datos suficientes  el sistema no pudo evaluar
#
# El MISMO envoltorio se corre luego sobre la RAMA: si la red condenase tambien ahi, lo que
# estaria condenando seria el banco y no la palabra.
echo "P6 · la red contra los BYTES de origin/main, en un banco con y sin decision"
OLD="$TMP/viejo"
if ! git -C "$REPO" rev-parse --verify --quiet origin/main >/dev/null; then
  total=$((total + 1)); nomed=$((nomed + 1))
  echo "  NO MEDIDO: no hay origin/main en este repo"
else
  sha_old=$(git -C "$REPO" rev-parse --short origin/main)
  mkdir -p "$OLD"
  git -C "$REPO" archive origin/main | tar -x -C "$OLD" 2>/dev/null
  h_old_ctx=$(huella "$OLD/app/ai_context.py")
  echo "  origin/main = $sha_old · app/ai_context.py huella $h_old_ctx · mesa.html presente: \
$([ -f "$OLD/static/mesa.html" ] && echo si || echo NO)"

  # EL ENVOLTORIO. Fuerza el estado por SIMBOLO, que es lo que `compute_scalp_summary` no sabe
  # -no recibe el simbolo-, asi que se envuelve `build_mesa_decide` y se cambia el summary solo
  # durante SU llamada, con un cerrojo para que dos peticiones no se pisen el parche.
  cat > "$TMP/banco132.py" <<'PY'
import asyncio

import app.ai_context as ctx
import app.api as api

FORZADO = {
    "BTCUSDT_PERP.A": "Long Momentum",
    "ETHUSDT_PERP.A": "No Trade",
    "SOLUSDT_PERP.A": "Sin datos suficientes",
}
ORIG_SUMMARY = ctx.compute_scalp_summary
ORIG_BUILD = ctx.build_mesa_decide
CERROJO = asyncio.Lock()


async def build(conn, symbol, *, frame="scalp"):
    estado = FORZADO.get(symbol)
    if estado is None:
        return await ORIG_BUILD(conn, symbol, frame=frame)

    def _con_estado(c):
        s = dict(ORIG_SUMMARY(c))
        s["state"] = estado
        return s

    async with CERROJO:
        ctx.compute_scalp_summary = _con_estado
        try:
            return await ORIG_BUILD(conn, symbol, frame=frame)
        finally:
            ctx.compute_scalp_summary = ORIG_SUMMARY


api.build_mesa_decide = build
app = api.app
PY

  # CON `setsid`: el servidor se va a SU propia sesion, asi que cuando se le mate al final el
  # bash de este control no escupe un «Terminated» en medio del informe.
  corre_banco() {  # corre_banco <arbol> <puerto> <token> <log>
    ( cd "$1" && PG_HOST=/var/run/postgresql PG_PORT=5432 PG_DB=coinalyze_espejo \
        PG_USER="$(id -un)" PG_PASSWORD= API_INTERNAL_TOKEN="$3" PYTHONPATH="$TMP:$1" \
        setsid nohup "$PY" -m uvicorn banco132:app --host 127.0.0.1 --port "$2" \
        > "$4" 2>&1 & )
    sleep 9
  }

  for cual in viejo rama; do
    total=$((total + 1))
    if [ "$cual" = "viejo" ]; then arbol="$OLD"; puerto=8097; quiero=1; rot="origin/main ($sha_old)"
    else arbol="$REPO"; puerto=8099; quiero=0; rot="la rama"; fi
    pkill -f "[u]vicorn banco132:app --host 127.0.0.1 --port $puerto" 2>/dev/null
    corre_banco "$arbol" "$puerto" k102control "$TMP/banco-$cual.log"
    rc_b=$(MESA_BASE="http://127.0.0.1:$puerto" K102_CABECERA="X-Internal-Token: k102control" \
           K102_OBSERVA=4 K102_ACTIVOS="BTC ETH SOL" bash "$CHECK" > "$TMP/sal_$cual" 2>&1; echo $?)
    n_h=$(grep -cE '^   - ' "$TMP/sal_$cual")
    brazos=$(grep -oE '^   - B[0-9]+' "$TMP/sal_$cual" | sort -u | tr -d ' -' | tr '\n' ' ')
    if [ "$rc_b" = "$quiero" ]; then
      pasa=$((pasa + 1))
      if [ "$quiero" = "1" ]; then
        printf '  CONDENA   %-44s rc=%s · %s hallazgo(s) en: %s\n' \
          "P6 · $rot tiene la palabra de hoy" "$rc_b" "$n_h" "${brazos:-ninguno}"
        grep -m2 -E '^   - B9 ' "$TMP/sal_$cual" | sed 's/^ */            /' | cut -c1-140
        printf '            el brazo que NO puede condenar esto: %s\n' \
          "$(grep -m1 'campos servidos casan pareja' "$TMP/sal_$cual" | sed 's/^ *//' | cut -c1-96)"
      else
        printf '  PASA      %-44s rc=0 · el MISMO banco, y aqui no hay nada que condenar\n' \
          "P6 · $rot sobre el mismo banco"
      fi
      printf '            %s\n' \
        "$(grep -m1 'pareja(s) distinta(s)' "$TMP/sal_$cual" | sed 's/^ *//' | cut -c1-130)"
      grep -E '^    palabra ' "$TMP/sal_$cual" | sed 's/^ */            /' | cut -c1-130
    else
      falla=$((falla + 1))
      printf '  MAL       %-44s esperaba rc=%s y salio rc=%s\n' "P6 · $rot" "$quiero" "$rc_b"
      sed -n '1,8p' "$TMP/sal_$cual" | sed 's/^/      /'
    fi
    pkill -f "[u]vicorn banco132:app --host 127.0.0.1 --port $puerto" 2>/dev/null
    sleep 1
  done

  total=$((total + 1))
  if [ "$(huella "$OLD/app/ai_context.py")" = "$h_old_ctx" ]; then
    pasa=$((pasa + 1))
    echo "  CORRECTO  los bytes de origin/main NO se tocaron: huella $h_old_ctx sin cambio"
  else
    falla=$((falla + 1))
    echo "  MAL       el arbol de origin/main cambio de huella: el banco lo modifico"
  fi
  vivos=$(ps -eo cmd | grep -cE "[u]vicorn banco132:app")
  [ "$vivos" = "0" ] || echo "  AVISO: quedo un uvicorn de banco132; matalo a mano"
fi
echo

echo "RESUMEN: $pasa de $total se comportan como debian ($falla mal, $nomed no medidos)"
[ "$falla" = "0" ] && [ "$nomed" = "0" ] || exit 1
exit 0
