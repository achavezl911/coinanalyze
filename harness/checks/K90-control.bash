#!/bin/bash
# K90-control · LOS BRAZOS DEL GUARDIA, INDUCIDOS SIN RED Y SIN BASE.
#
# EL SUJETO CAMBIO CON LA DECISION D1, Y ESTE CONTROL CON EL.
# Antes K90 comparaba el CALCULO contra el ROTULO -la cadena '1-15 minutos' de app.js- y
# cuatro casos de este fichero probaban el parseo de ese rango. Con el rotulo convertido en
# MEDIDA, el sujeto es **lo publicado contra lo medido**, y esos cuatro dejaron de tener
# sujeto. El reparto, contado:
#
#   SOBREVIVEN sin tocar (9) ... F1..F4 (anti-fantasma), C2 (canal), S1..S3 (formato de
#                                simbolo), C1 (el control del muestreo). Ninguno dependia
#                                del rotulo.
#   CAMBIAN (4) ............... P1, P2, N3, N4 -los del parseo del rango-. Su sujeto era la
#                               cadena; ahora es la comparacion de cifras.
#   NACEN (6) ................. el rotulo literal que vuelve, el bloque que falta, el que
#                               dice no-disponible, la mediana que no cuadra, el p90 que no
#                               cuadra, y el CONTROL publicado que no cuadra.
#
# TODO SE INYECTA: un `api` de mentira que devuelve el cuerpo que se le pida y un `prodsql`
# de mentira que devuelve la fila que se le pida. Asi se ejercitan las dos mitades del par
# por separado y en combinacion, que es lo que un solo dato real no permitiria.
#
# Y LA LECCION DE F3d SIGUE EN PIE: un control que fabrica su sustituto no caza el
# desacuerdo con el original. Por eso E1 lee el ESQUEMA REAL y comprueba que las columnas
# que el SQL de K90 nombra existen -con su control negativo-.
#
# NO LLEVA .sh A PROPOSITO: bin/verify globea checks/*.sh.
set -uo pipefail

ORIG=${K90_CONTROL_REPO:-/srv/coinanalyze/repo}
CHK="$(cd "$(dirname "$0")" && pwd)/K90-la-senal-no-dura-su-rotulo.sh"
[ -r "$CHK" ] || { echo "NO MEDIDO: no encuentro el check en $CHK"; exit 2; }

DIR=$(mktemp -d) || exit 2
[ "${K90_CONTROL_GUARDA:-0}" = "1" ] || trap 'rm -rf "$DIR"' EXIT
cd "$DIR" || exit 2          # se demuestra que no depende del cwd
fallos=0; pasan=0

mkdir -p "$DIR/repo/static" "$DIR/repo/app" "$DIR/bin"

# --- el panel de mentira -----------------------------------------------------------------
rotulo_en() {   # $1 = lo que va en `time:`  (vacio = la forma nueva, sin literal)
  if [ -z "$1" ]; then
    printf "      name: 'Corto plazo', time: shortHorizon, action: shortAction,\n" \
      > "$DIR/repo/static/app.js"
  else
    printf "      name: 'Corto plazo', time: '%s', action: shortAction,\n" "$1" \
      > "$DIR/repo/static/app.js"
  fi
}

# --- el api de mentira: devuelve el JSON que se le ponga en K90C_CUERPO -------------------
cat > "$DIR/bin/api" <<'PY'
#!/bin/sh
printf '%s' "${K90C_CUERPO:-}"
exit "${K90C_APIRC:-0}"
PY
chmod +x "$DIR/bin/api"

# --- el prodsql de mentira ----------------------------------------------------------------
cat > "$DIR/bin/prodsql" <<'PY'
#!/bin/sh
[ -n "${K90C_FILA:-}" ] || exit 0
printf '%s\n' "$K90C_FILA"
PY
chmod +x "$DIR/bin/prodsql"
cat > "$DIR/bin/prodsql-roto" <<'PY'
#!/bin/sh
echo "psql:<stdin>:1: ERROR:  column \"x\" does not exist" >&2
exit 3
PY
chmod +x "$DIR/bin/prodsql-roto"

# cuerpos que se reutilizan
CUERPO_OK='{"symbol":"BTCUSDT_PERP.A","scalp_persistence":{"available":true,"mediana_min":1,"p90_min":3,"p90_no_accionable_min":6,"dias":30,"etiqueta":"mediana 1 min · p90 3 min"}}'
FILA_OK=' 1|3|6|7524|34439'

caso() {  # <nombre> <rc> <patron> <rotulo> <cuerpo> <fila> [prodsql]
  local nombre="$1" esperado="$2" patron="$3" rot="$4" cuerpo="$5" fila="$6"
  local psql="${7:-$DIR/bin/prodsql}"
  rotulo_en "$rot"
  local out rc
  out=$(REPO="$DIR/repo" K90_APPJS="$DIR/repo/static/app.js" K90_API="$DIR/bin/api" \
        K90_PRODSQL="$psql" K90C_CUERPO="$cuerpo" K90C_FILA="$fila" \
        bash "$CHK" 2>&1); rc=$?
  local ok=1
  [ "$rc" = "$esperado" ] || ok=0
  if [ -n "$patron" ] && ! printf '%s' "$out" | grep -qE "$patron"; then ok=0; fi
  if [ "$ok" = 1 ]; then
    pasan=$((pasan+1)); printf '  [ok   ] %-54s rc=%s\n' "$nombre" "$rc"
  else
    fallos=$((fallos+1))
    printf '  [FALLA] %-54s rc=%s (esperaba %s, patron /%s/)\n      %s\n' \
      "$nombre" "$rc" "$esperado" "$patron" "$(printf '%s' "$out" | head -2 | tr '\n' ' ' | cut -c1-150)"
  fi
}

echo "K90-control · sujeto: $CHK"
echo

echo "NACEN · el rotulo literal ya no puede volver"
# N-R1 · EL CASO QUE LA DECISION D1 HACE POSIBLE. Antes el rango literal era el sujeto;
# ahora su MERA PRESENCIA es el defecto, y se caza sin red ni base.
caso "R1 vuelve el rango '1-15 minutos' a la tarjeta" 1 "ESCRITO A MANO" \
     "1–15 minutos" "$CUERPO_OK" "$FILA_OK"
caso "R2 vuelve con guion normal" 1 "ESCRITO A MANO" \
     "1-15 minutos" "$CUERPO_OK" "$FILA_OK"
# R3 · un texto SIN numeros no es un rango: "sin medida" es la salida legitima cuando el
# bloque no llega, y no puede confundirse con un rotulo inventado.
caso "R3 texto sin numeros NO es un rotulo literal" 0 "coincide con lo medido" \
     "persistencia sin medida" "$CUERPO_OK" "$FILA_OK"

echo
echo "NACEN · lo publicado contra lo medido"
caso "R4 publicado y medido coinciden" 0 "coincide con lo medido" \
     "" "$CUERPO_OK" "$FILA_OK"
# R5 · el caso central del sujeto NUEVO: el panel dice 3 y la serie dice 7.
caso "R5 el p90 publicado no es el medido (3 contra 7)" 1 "p90\(±4\)" \
     "" "$CUERPO_OK" ' 1|7|11|7524|34439'
caso "R6 la mediana publicada no es la medida" 1 "mediana\(±4\)" \
     "" "$CUERPO_OK" ' 5|3|6|7524|34439'
# R7 · EL CONTROL PUBLICADO TAMBIEN SE COMPARA. Un panel que copiara bien la cifra
# principal y mal el control seguiria afirmando algo falso, solo que mas escondido.
caso "R7 el CONTROL publicado no es el medido" 1 "control\(±5\)" \
     "" "$CUERPO_OK" ' 1|3|11|7524|34439'
# R8 · la tolerancia existe porque la ventana es movil: ±1 min no es un defecto.
caso "R8 diferencia de 1 min esta dentro de tolerancia" 0 "coincide con lo medido" \
     "" "$CUERPO_OK" ' 2|4|7|7524|34439'

echo
echo "NACEN · el bloque que falta o no es medible"
caso "R9 /api/dashboard/state no publica scalp_persistence" 1 "NO publica scalp_persistence" \
     "" '{"symbol":"BTCUSDT_PERP.A","scalp":{}}' "$FILA_OK"
# R10 · "no disponible" es NOMED, no ROJO: la ruta dice que no pudo medir, no que mienta.
caso "R10 scalp_persistence dice que no es medible" 2 "no es medible" \
     "" '{"scalp_persistence":{"available":false,"motivo":"sin episodios accionables"}}' "$FILA_OK"

echo
echo "SOBREVIVE · el control del muestreo, en la misma consulta"
# C1 · si el lado NO accionable es igual de corto, el sujeto es el muestreo. Sobrevive
# entero: no dependia del rotulo, solo cambia de sitio dentro del check.
caso "C1 el p90 no accionable no supera al accionable" 2 "el sujeto seria el muestreo" \
     "" '{"scalp_persistence":{"available":true,"mediana_min":1,"p90_min":3,"p90_no_accionable_min":3,"dias":30}}' \
     ' 1|3|3|7524|34439'

echo
echo "SOBREVIVEN · formato de simbolo y canal"
caso "S1 filas con BTCUSDT_PERP.A (las de 140)" 0 "coincide con lo medido" \
     "" "$CUERPO_OK" "$FILA_OK"
caso "S3 la consulta no devuelve ninguna fila util" 2 "ninguna fila utilizable" \
     "" "$CUERPO_OK" 'total | nada'
caso "C2 SQL roto: NO MEDIDO, no 'sin filas'" 2 "la consulta fallo" \
     "" "$CUERPO_OK" "$FILA_OK" "$DIR/bin/prodsql-roto"

echo
echo "SOBREVIVEN · anti-fantasma"
# F1 · SIN app.js NO SE PUEDE JUZGAR EL ROTULO, asi que es NOMED y no VERDE.
# NO se induce con `caso`: esa funcion llama a `rotulo_en`, que RECREA el fichero, o sea
# que el caso no borraba nada y pasaba por no haber inducido la averia. Es el mismo
# fantasma que este arnes lleva seis paquetes cazando, y lo cometi aqui. Se induce a mano.
rm -f "$DIR/repo/static/app.js"
out=$(REPO="$DIR/repo" K90_APPJS="$DIR/repo/static/app.js" K90_API="$DIR/bin/api" \
      K90_PRODSQL="$DIR/bin/prodsql" K90C_CUERPO="$CUERPO_OK" K90C_FILA="$FILA_OK" \
      bash "$CHK" 2>&1); rc=$?
if [ "$rc" = "2" ] && printf '%s' "$out" | grep -q "no encuentro"; then
  pasan=$((pasan+1)); printf "  [ok   ] %-54s rc=%s\n" "F1 sin app.js: NOMED, no verde" "$rc"
else
  fallos=$((fallos+1)); printf "  [FALLA] %-54s rc=%s\n" "F1 sin app.js" "$rc"
fi
rotulo_en ""

caso "F2 la respuesta no es JSON" 2 "no es JSON" \
     "" 'esto no es json' "$FILA_OK"
caso "F3 el api falla" 2 "NO MEDIDO" \
     "" "" "$FILA_OK"

echo
# =====================================================================================
# EL ESQUEMA REAL · el unico caso que NO usa un sustituto fabricado por mi.
# Es la leccion de F3c: los 12 controles de la primera version pasaron los 12 y ninguno
# toco el esquema, por eso no vieron que `ts` no existia. Las columnas del SQL nuevo se
# comprueban contra sql/schema.sql, que es el fichero que el desplegador aplica.
# =====================================================================================
echo "ESQUEMA REAL · las columnas que K90 nombra existen"
SCHEMA="$ORIG/sql/schema.sql"
if [ ! -r "$SCHEMA" ]; then
  fallos=$((fallos+1)); printf '  [FALLA] %-54s no encuentro %s\n' "E1" "$SCHEMA"
else
  # el catalogo del generador ya conoce las columnas de ALTER desde F4, asi que se usa el
  # mismo instrumento que el mapa: si el esquema cambia, los dos se enteran a la vez.
  res=$(python3 - "$ORIG" <<'PY'
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path
repo = Path(sys.argv[1])
m = SourceFileLoader("arq", str(repo / "harness/bin/arquitectura")).load_module()
cat = m.lee_catalogo(repo)
cols = set(cat["tablas"].get("signal_observation", {}).get("columnas", []))
faltan = [c for c in ("observed_minute", "is_periodic", "actionable", "symbol") if c not in cols]
falsos = [c for c in ("ts", "columna_que_no_existe") if c in cols]
print("FALTAN" if faltan else ("FALSOS" if falsos else "OK"), faltan or falsos)
PY
2>&1)
  case "$res" in
    OK*) pasan=$((pasan+1)); printf '  [ok   ] %-54s las 4 estan; ts y la inventada NO\n' "E1 esquema de signal_observation" ;;
    *)   fallos=$((fallos+1)); printf '  [FALLA] %-54s %s\n' "E1 esquema de signal_observation" "$res" ;;
  esac
fi

echo
total=$((pasan + fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
