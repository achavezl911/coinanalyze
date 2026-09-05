#!/bin/bash
# K90  LO QUE EL PANEL PUBLICA SOBRE LA PERSISTENCIA NO ES LO QUE LA SERIE MIDE.
#
# EL SUJETO CAMBIO EL 2026-09-05, Y ESTE COMENTARIO EXPLICA POR QUE.
#
# La primera version comparaba EL CALCULO contra EL ROTULO: la tarjeta de corto decia
# `time: '1-15 minutos'` -una cadena escrita a mano en static/app.js:1435- y la señal duraba
# una mediana de 1 minuto con p90 de 3. El check leia el rotulo, sacaba su punto medio (8) y
# enrojecia si el p90 no llegaba.
#
# La decision de producto -D1, tomada bajo delegacion el 2026-09-05- fue **convertir el
# rotulo en una medida**: la tarjeta ya no promete un rango, publica la persistencia medida
# de la propia señal (`scalp_persistence` en /api/dashboard/state, app/api.py). Se descarto
# meter histeresis con motivo: eso cambia lo que el sistema CALCULA, y todo lo que cuelga de
# la señal -signal_outcome, el walk-forward, K21-K25- quedaria medido contra otra señal.
#
# ASI QUE EL SUJETO NUEVO ES OTRO, Y SIGUE SIENDO UN PAR:
#
#   antes   calculo (sin memoria)   contra   rotulo (una promesa escrita a mano)
#   ahora   LO PUBLICADO            contra   LO MEDIDO
#
# Si el panel publica "p90 3 min" y la consulta sobre los mismos 30 dias dice 7, eso es
# ROJO: el sistema esta afirmando una cifra que su propia serie no sostiene. Es el mismo
# defecto de antes -afirmar algo falso- en su forma nueva, y por eso el check conserva su
# numero en vez de cerrarse y abrir otro.
#
# EL BRAZO DE CONTROL SE MANTIENE Y CAMBIA DE SITIO. Antes el control era el p90 de los
# episodios NO accionables: si los dos lados salian igual de cortos, el sujeto era el
# muestreo y no la señal. Ese control sigue, y ahora viaja **dentro de la respuesta
# publicada** (`p90_no_accionable_min`), asi que el check puede comprobarlo sin una segunda
# consulta — y ademas comprueba que el publicado y el medido coinciden TAMBIEN en el control.
# Un panel que copiara mal solo la cifra principal se cazaria; uno que copiara mal las dos,
# tambien.
set -uo pipefail
B=/srv/coinanalyze/harness
_repo_pedido=${REPO:-}
[ -r "$B/env" ] && . "$B/env"
REPO=${_repo_pedido:-${REPO:-/srv/coinanalyze/repo}}
APPJS=${K90_APPJS:-$REPO/static/app.js}
PRODSQL=${K90_PRODSQL:-$B/bin/prodsql}
API=${K90_API:-$B/bin/api}
DIAS=${K90_DIAS:-30}
# tolerancia en minutos: dos medidas del mismo p90 tomadas con segundos de diferencia
# pueden diferir en 1 por el borde de la ventana movil. Mas de eso no es el borde.
TOL=${K90_TOL:-1}

command -v python3 >/dev/null 2>&1 || { echo "NO MEDIDO: no hay python3"; exit 2; }

# --- 1 · EL PANEL YA NO PUEDE LLEVAR EL ROTULO ESCRITO A MANO --------------------------
# Es la mitad barata del check y no necesita red. Si alguien vuelve a poner un rango
# literal en la tarjeta, esto lo caza sin preguntar a nadie.
[ -r "$APPJS" ] || { echo "NO MEDIDO: no encuentro $APPJS"; exit 2; }
literal=$(grep -oE "name: *'Corto plazo', *time: *'[^']*[0-9][^']*'" "$APPJS" | head -1)
if [ -n "$literal" ]; then
  echo "la tarjeta de corto vuelve a llevar un horizonte ESCRITO A MANO: $literal"
  echo "  el rotulo tiene que salir de scalp_persistence, no de una cadena (decision D1)"
  exit 1
fi

# --- 2 · LO PUBLICADO ------------------------------------------------------------------
[ -x "$API" ] || { echo "NO MEDIDO: no hay canal a la API ($API)"; exit 2; }
SIMB=${K90_SIMBOLO:-BTCUSDT_PERP.A}
cuerpo=$(TODO=1 "$API" "/api/dashboard/state?symbol=$SIMB" 2>&1); rc=$?
if [ "$rc" != "0" ]; then
  echo "NO MEDIDO: la peticion fallo (rc=$rc): $(printf '%s' "$cuerpo" | tail -1 | cut -c1-120)"
  exit 2
fi
# UN 200 CON CUERPO DE ERROR PARECE UNA MEDIDA. Se imprimen los bytes y se exige la clave.
bytes=$(printf '%s' "$cuerpo" | wc -c)
pub=$(printf '%s' "$cuerpo" | python3 -c '
import json,sys
try: d=json.load(sys.stdin)
except Exception as e: print("NOJSON",e); raise SystemExit
p=d.get("scalp_persistence")
if p is None: print("SINBLOQUE"); raise SystemExit
if not p.get("available"): print("NODISPONIBLE",p.get("motivo","")); raise SystemExit
print(p.get("mediana_min"),p.get("p90_min"),p.get("p90_no_accionable_min"),p.get("dias"))
' 2>&1)

case "$pub" in
  NOJSON*)   echo "NO MEDIDO: la respuesta no es JSON ($bytes B): $(printf '%s' "$pub" | cut -c1-90)"; exit 2 ;;
  SINBLOQUE) echo "/api/dashboard/state NO publica scalp_persistence ($bytes B): el rotulo no tiene de donde salir"; exit 1 ;;
  NODISPONIBLE*) echo "NO MEDIDO: scalp_persistence dice que no es medible: $(printf '%s' "$pub" | cut -c14-100)"; exit 2 ;;
  "") echo "NO MEDIDO: no se pudo leer scalp_persistence del cuerpo ($bytes B)"; exit 2 ;;
esac
set -- $pub
pub_med=$1 pub_p90=$2 pub_ctrl=$3 pub_dias=$4

# --- 3 · LO MEDIDO ---------------------------------------------------------------------
[ -x "$PRODSQL" ] || { echo "NO MEDIDO: no hay canal a produccion ($PRODSQL)"; exit 2; }
SQL="
WITH u AS (
  SELECT DISTINCT symbol, observed_minute AS m, (actionable IS TRUE) AS acc
  FROM signal_observation
  WHERE is_periodic IS TRUE AND symbol = '$SIMB'
    AND observed_minute >= now() - interval '$pub_dias days'
),
g AS (
  SELECT symbol, m, acc,
         (EXTRACT(EPOCH FROM m)/60)::bigint
           - ROW_NUMBER() OVER (PARTITION BY symbol, acc ORDER BY m) AS grupo
  FROM u
),
ep AS (SELECT acc, COUNT(*) AS minutos FROM g GROUP BY acc, grupo)
SELECT percentile_disc(0.5) WITHIN GROUP (ORDER BY minutos) FILTER (WHERE acc),
       percentile_disc(0.9) WITHIN GROUP (ORDER BY minutos) FILTER (WHERE acc),
       percentile_disc(0.9) WITHIN GROUP (ORDER BY minutos) FILTER (WHERE NOT acc),
       COUNT(*) FILTER (WHERE acc),
       (SELECT COUNT(*) FROM u)
FROM ep;
"
salida=$(TODO=1 "$PRODSQL" "$SQL" 2>&1); rc=$?
if [ "$rc" != "0" ] || printf '%s\n' "$salida" | grep -q 'ERROR:'; then
  echo "NO MEDIDO: la consulta fallo (rc=$rc): $(printf '%s\n' "$salida" | grep -m1 'ERROR:' | cut -c1-130)"
  exit 2
fi
fila=$(printf '%s\n' "$salida" | grep -E '^[[:space:]]*[0-9]+\|' | head -1)
if [ -z "$fila" ]; then
  echo "NO MEDIDO: la consulta no devolvio ninguna fila utilizable"
  echo "  primera linea: $(printf '%s\n' "$salida" | head -1 | cut -c1-100)"
  exit 2
fi
IFS='|' read -r med_p50 med_p90 med_ctrl med_ep med_min <<EOF
$fila
EOF
med_p50=$(printf '%s' "$med_p50" | tr -d ' '); med_p90=$(printf '%s' "$med_p90" | tr -d ' ')
med_ctrl=$(printf '%s' "$med_ctrl" | tr -d ' '); med_ep=$(printf '%s' "$med_ep" | tr -d ' ')
med_min=$(printf '%s' "$med_min" | tr -d ' ')

if [ -z "$med_ep" ] || [ "$med_ep" -eq 0 ]; then
  # CERO EPISODIOS NO ES PERSISTENCIA CERO. Leccion de K60.
  echo "NO MEDIDO: la serie no tiene ningun episodio accionable en $pub_dias dias"
  exit 2
fi

detalle="publicado p50=$pub_med p90=$pub_p90 ctrl=$pub_ctrl · medido p50=$med_p50 p90=$med_p90 ctrl=$med_ctrl (n=$med_ep ep, $med_min min)"

# --- 4 · EL CONTROL, EN LA MISMA CONSULTA ----------------------------------------------
# Si el lado NO accionable fuera igual de corto que el accionable, el sujeto seria el
# muestreo y no la señal, y comparar publicado contra medido no diria nada del producto.
if [ "$med_ctrl" != "" ] && [ "$med_ctrl" -le "$med_p90" ]; then
  echo "NO MEDIDO: el p90 no accionable ($med_ctrl) no supera al accionable ($med_p90): el sujeto seria el muestreo"
  echo "  $detalle"
  exit 2
fi

# --- 5 · EL VEREDICTO ------------------------------------------------------------------
dif() { a=$1; b=$2; [ "$a" -ge "$b" ] && echo $((a-b)) || echo $((b-a)); }
d_med=$(dif "$pub_med" "$med_p50")
d_p90=$(dif "$pub_p90" "$med_p90")
d_ctrl=0
[ -n "$pub_ctrl" ] && [ "$pub_ctrl" != "None" ] && [ -n "$med_ctrl" ] && d_ctrl=$(dif "$pub_ctrl" "$med_ctrl")

malas=''
[ "$d_med"  -gt "$TOL" ] && malas="$malas mediana(±$d_med)"
[ "$d_p90"  -gt "$TOL" ] && malas="$malas p90(±$d_p90)"
[ "$d_ctrl" -gt "$TOL" ] && malas="$malas control(±$d_ctrl)"

if [ -n "$malas" ]; then
  echo "el panel publica una persistencia que la serie no sostiene:$malas (tolerancia $TOL min)"
  echo "  $detalle"
  exit 1
fi

echo "lo publicado coincide con lo medido (tolerancia $TOL min): $detalle"
exit 0
