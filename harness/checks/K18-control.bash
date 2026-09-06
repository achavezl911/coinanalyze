#!/usr/bin/env bash
# K18-control · ¿el brazo de «encoge sin declarar» distingue un REEMPLAZO de un BORRADO?
#
# EL DEFECTO QUE ESTE CONTROL EXISTE PARA QUE NO VUELVA. El 2026-09-06 K18 publico
# `macro_event(encoge_sin_declarar:33->29)` y la causa que nombraba no era la real: ese brazo
# compara EL ESPEJO -congelado el 2026-08-13- contra PRODUCCION, y `macro_event` es un
# calendario que se REEMPLAZA ENTERO en cada refresco. Las 33 del espejo comparten un
# `fetched_at` y las 29 de produccion comparten otro: son dos fotos con 24 dias entre ellas,
# no un borrado. Salto ese dia y no antes porque el prefiltro es `b < a*0.9`: a 30 filas no
# disparaba y a 29 si.
#
# LO QUE HAY QUE PROBAR NO ES QUE HOY DE VERDE, sino que la exencion es ESTRECHA:
#   1  un reemplazo completo NO enrojece                       -> el arreglo
#   2  un borrado de verdad SIGUE enrojeciendo                 -> no lo afloje
#   3  una tabla con sellos MEZCLADOS no se lleva la exencion  -> el borde
#   4  dos fotos con el MISMO sello y menos filas SI enrojecen -> es la misma foto
#   5  una tabla de 1 fila no se lleva la exencion por trivialidad
# El 2 es el que decide: una exencion que exime todo no exime nada.
#
# COMO SE MIDE SIN TOCAR 140 NI EL ESPEJO: se ponen por delante en el PATH un `espejosql` y un
# `prodsql` de mentira que contestan lo que este fichero les dice, y se apunta K18 a un arnes
# de mentira con `K18_HARNESS`. Todo lo demas del check -el prefiltro, el bucle, la
# clasificacion- es el original letra por letra. Es la tecnica de K91/K94.
#
# NO LLEVA .sh A PROPOSITO: bin/verify globea checks/*.sh y el sujeto es el criterio.
set -uo pipefail
ORIG=${REPO:-/srv/coinanalyze/repo}
CHK="$ORIG/harness/checks/K18-borrado.sh"
[ -r "$CHK" ] || { echo "NO MEDIDO: no encuentro el check en $CHK"; exit 2; }
grep -q 'K18_HARNESS' "$CHK" || { echo "NO MEDIDO: el check no acepta K18_HARNESS: no se le puede apuntar a un arnes de mentira"; exit 2; }

DIR=$(mktemp -d) || exit 2
[ "${K18_CONTROL_GUARDA:-0}" = "1" ] || trap 'rm -rf "$DIR"' EXIT
fallos=0; pasan=0

# --- el arnes de mentira: env vacio y dos canales que contestan de una tabla de guion ------
monta() {  # <dir> <fichero de guion>
  rm -rf "$1"; mkdir -p "$1/bin" "$1/estado"
  : > "$1/env"
  for canal in espejosql prodsql; do
    {
      printf '#!/bin/bash\n'
      printf 'LADO=%s\n' "$canal"
      printf 'GUION=%s\n' "$2"
      cat <<'SH'
q="$*"
# el guion es: LADO<TAB>PATRON<TAB>RESPUESTA. Primera linea cuyo patron case, gana.
while IFS=$'\t' read -r lado pat resp; do
  case "$lado" in ''|'#'*) continue ;; esac
  [ "$lado" = "$LADO" ] || [ "$lado" = "*" ] || continue
  case "$q" in $pat) printf '%s\n' "$resp"; exit 0 ;; esac
done < "$GUION"
exit 0
SH
    } > "$1/bin/$canal"
    chmod +x "$1/bin/$canal"
  done
}

caso() {  # <nombre> <rc esperado> <patron> <guion>
  local nombre="$1" esperado="$2" patron="$3" guion="$4" out rc ok=1
  monta "$DIR/h" "$guion"
  out=$(K18_HARNESS="$DIR/h" bash "$CHK" 2>&1); rc=$?
  [ "$rc" = "$esperado" ] || ok=0
  if [ -n "$patron" ] && ! printf '%s' "$out" | grep -qE "$patron"; then ok=0; fi
  if [ "$ok" = 1 ]; then
    pasan=$((pasan+1)); printf '  [ok   ] %-52s rc=%s\n' "$nombre" "$rc"
  else
    fallos=$((fallos+1))
    printf '  [FALLA] %-52s rc=%s (esperaba %s, patron /%s/)\n      %s\n' \
      "$nombre" "$rc" "$esperado" "$patron" "$(printf '%s' "$out" | head -1 | cut -c1-170)"
  fi
}

# --- el guion base: todo sano salvo lo que cada caso cambie -------------------------------
# Las tablas de VENTANAS y SUELOS tienen que salir bien o el check enrojece por otra cosa.
# LAS LINEAS DEL GUION SE ESCRIBEN CON printf Y NO CON UN HEREDOC, y esto no es estilo:
# el separador es un TABULADOR y un heredoc no garantiza que lo que se teclea como tal llegue
# como tal. Me paso: la primera version usaba heredocs, el guion no parseaba, y **los cuatro
# casos que esperan ROJO pasaban igual** -porque cuando el guion no contesta, el discriminante
# no puede dispararse y el check enrojece, que es justo lo que ellos esperaban-. Cuatro casos
# verdes sin probar nada. Lo destapo el UNICO caso que espera VERDE. Es la regla de siempre:
# sin el positivo, los negativos no prueban nada.
#
# EL SPAN VA POR TABLA Y NO UNO PARA TODAS: las seis ventanas declaradas son 6, 6, 6, 72, 2 y
# 36 h y el criterio es w/2 <= span <= w+gracia. NINGUN valor unico las satisface a la vez
# -72 h exige >= 36 y 2 h exige <= 29-, asi que un guion con un solo span hace enrojecer el
# check por una tabla que este control no esta mirando.
linea() { printf '%s\t%s\t%s\n' "$1" "$2" "$3" >> "$G"; }

base() {  # usa $G
  : > "$G"
  linea '*' "SELECT 'canal_ok'*"                  'canal_ok'
  linea '*' '*epoch*futures_trades_realtime*'     '6.0'
  linea '*' '*epoch*orderbook_snapshot*'          '6.0'
  linea '*' '*epoch*liquidations_realtime*'       '6.0'
  linea '*' '*epoch*scalp_signal_snapshot*'       '72.0'
  linea '*' '*epoch*spot_trades_realtime*'        '2.0'
  linea '*' '*epoch*futures_trades_agg*'          '36.0'
  linea '*' 'SELECT count(\*) FROM pipeline_heartbeat' '14'
}

# EL ASTERISCO DE `count(*)` VA ESCAPADO, Y ESO ERA EL FALLO. En un patron de `case` el `*`
# es un COMODIN, asi que `SELECT count(*) FROM zzz_cal` casaba tambien
# `SELECT count(DISTINCT fetched_at)||'|'||...  FROM zzz_cal` -el comodin se tragaba el
# `DISTINCT ...` entero-. El canal de mentira contestaba «33» donde el check esperaba
# «1|2026-08-13...», el discriminante no podia dispararse, y N1 salia rojo. Con `\*` el
# asterisco es literal. Es la misma familia que todo lo de esta semana: un patron que casa
# mas de lo que su autor creia.
sospechosa() {  # <tabla> <filas_espejo> <filas_prod>
  linea 'espejosql' 'SELECT relname*' "$1 $2"
  linea 'prodsql'   'SELECT relname*' "$1 $3"
  linea 'espejosql' "SELECT count(\\*) FROM $1" "$2"
  linea 'prodsql'   "SELECT count(\\*) FROM $1" "$3"
}

echo "K18-control · sujeto: $CHK"
echo

echo "EL ARREGLO · un reemplazo completo no es un borrado"
G="$DIR/g1"; base; sospechosa zzz_cal 33 29
linea '*'         'SELECT string_agg(column_name*'    'fetched_at'
linea 'espejosql' 'SELECT count(DISTINCT fetched_at)*' '1|2026-08-13 17:10:19'
linea 'prodsql'   'SELECT count(DISTINCT fetched_at)*' '1|2026-09-06 16:30:19'
caso "N1 reemplazo completo: VERDE"            0 "se REEMPLAZAN enteras" "$G"
caso "N1b y lo NOMBRA con sus dos sellos"      0 "zzz_cal\(fetched_at:2026-08-13" "$G"
caso "N1c y cuenta UNA, no tres"               0 "· 1 tabla\(s\) se REEMPLAZAN" "$G"

echo
echo "NO LO AFLOJO · un borrado de verdad sigue enrojeciendo"
# P1 · sellos MEZCLADOS en los dos lados: no es un reemplazo, es una tabla que perdio filas.
G="$DIR/g2"; base; sospechosa zzz_cal 33 29
linea '*'         'SELECT string_agg(column_name*'    'fetched_at'
linea 'espejosql' 'SELECT count(DISTINCT fetched_at)*' '11|2026-08-13 17:10:19'
linea 'prodsql'   'SELECT count(DISTINCT fetched_at)*' '9|2026-09-06 16:30:19'
caso "P1 sellos mezclados: ROJO"               1 "zzz_cal\(encoge_sin_declarar:33->29\)" "$G"

# P2 · el MISMO sello en los dos lados y menos filas: es la misma foto, faltan filas.
G="$DIR/g3"; base; sospechosa zzz_cal 33 29
linea '*' 'SELECT string_agg(column_name*'    'fetched_at'
linea '*' 'SELECT count(DISTINCT fetched_at)*' '1|2026-09-06 16:30:19'
caso "P2 mismo sello, menos filas: ROJO"       1 "encoge_sin_declarar" "$G"

# P3 · sin ninguna columna de tiempo no hay discriminante posible: enrojece.
G="$DIR/g4"; base; sospechosa zzz_cal 33 29
linea '*' 'SELECT string_agg(column_name*' ''
caso "P3 sin columna de tiempo: ROJO"          1 "encoge_sin_declarar" "$G"

# P4 · una tabla de 1 fila tiene "un solo valor distinto" por trivialidad. No exime.
G="$DIR/g5"; base; sospechosa zzz_cal 3 1
linea '*'         'SELECT string_agg(column_name*'    'fetched_at'
linea 'espejosql' 'SELECT count(DISTINCT fetched_at)*' '1|2026-08-13 17:10:19'
linea 'prodsql'   'SELECT count(DISTINCT fetched_at)*' '1|2026-09-06 16:30:19'
caso "P4 una sola fila: no se lleva la exencion" 1 "encoge_sin_declarar:3->1" "$G"

echo
echo "ANTI-FANTASMA · sin canal no hay veredicto"
G="$DIR/g6"; : > "$G"
caso "F1 prodsql no contesta: NOMED"           2 "prodsql no responde" "$G"

echo
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
