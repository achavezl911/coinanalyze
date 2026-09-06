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

# LAS FILAS QUE QUEDAN DENTRO DE LA VENTANA DE RETENCION, que es lo que el discriminante mira.
# El patron del conteo TOTAL no lleva comodin final, asi que casa la cadena entera y NO puede
# tragarse esta consulta aunque comparta prefijo. Se dice porque en este mismo fichero un
# `count(*)` sin escapar ya se comio una consulta que no era la suya.
dentro() {  # <tabla> <columna> <espejo> <prod>
  linea 'espejosql' "SELECT count(\\*) FROM $1 WHERE $2 >= now()*" "$3"
  linea 'prodsql'   "SELECT count(\\*) FROM $1 WHERE $2 >= now()*" "$4"
}

echo "K18-control · sujeto: $CHK"
echo

echo "EL ARREGLO · lo que borra el borrador declarado no es un borrado sin declarar"
# El caso real del 2026-09-06: la tabla pierde 4 filas en total y NINGUNA de dentro de la
# ventana de 30 dias. Las cuatro estaban por debajo del corte, o sea que las borro el DELETE
# que la cabecera de K18 ya lista como uno de sus nueve borradores.
G="$DIR/g1"; base; sospechosa macro_event 33 29; dentro macro_event event_at 29 29
caso "N1 encoge solo por su retencion: VERDE"  0 "encogen SOLO por su retencion" "$G"
caso "N1b y publica los dos recuentos"         0 "macro_event\(event_at>=now\(\)-30d:29==29,total_33->29\)" "$G"
caso "N1c y cuenta UNA"                        0 "· 1 tabla\(s\) encogen SOLO" "$G"

echo
echo "EL BRAZO QUE FALTABA · la MAGNITUD entra en la decision"
# EL CASO QUE EL K18 DE 485cdc4 DEJABA PASAR. Medido sobre aquel check con estos mismos
# canales de mentira: espejo 33 -> prod 5 daba VERDE diciendo «se REEMPLAZAN enteras».
# Escenario concreto: un dedazo que ponga `interval '3 days'` en external_macro.py:576.
G="$DIR/g2"; base; sospechosa macro_event 33 5; dentro macro_event event_at 29 5
# EL GUION LLEVA TAMBIEN LO QUE EL CHECK VIEJO PREGUNTABA -los sellos de carga-, o el
# contraste de P5b no seria justo: sin esas lineas el viejo enrojeceria por no poder mirar,
# no por saber. Al nuevo no le estorban: ya no consulta sellos.
linea '*'         'SELECT string_agg(column_name*'    'event_at fetched_at'
linea 'espejosql' 'SELECT count(DISTINCT event_at)*'   '33|2026-08-07 12:30:00'
linea 'prodsql'   'SELECT count(DISTINCT event_at)*'   '5|2026-09-06 12:30:00'
linea 'espejosql' 'SELECT count(DISTINCT fetched_at)*' '1|2026-08-13 17:10:19'
linea 'prodsql'   'SELECT count(DISTINCT fetched_at)*' '1|2026-09-06 16:30:19'
caso "P5 pierde 24 filas DENTRO de la ventana: ROJO" 1 "pierde_filas_DENTRO_de_la_ventana_de_30d:29->5" "$G"
# P5b · Y LA COMPARACION QUE HACE VALER AL BRAZO: el check ANTERIOR, sacado de git, sobre EL
# MISMO guion. Si diera lo mismo que el nuevo, este remate no habria cambiado nada.
if VIEJO=$(cd "$ORIG" && git show 485cdc4:harness/checks/K18-borrado.sh 2>/dev/null) \
   && [ -n "$VIEJO" ]; then
  printf '%s' "$VIEJO" > "$DIR/K18-485cdc4.sh"
  monta "$DIR/h" "$G"
  outv=$(K18_HARNESS="$DIR/h" bash "$DIR/K18-485cdc4.sh" 2>&1); rcv=$?
  if [ "$rcv" = 0 ]; then
    pasan=$((pasan+1)); printf '  [ok   ] %-52s rc=%s (VERDE: el defecto que este remate cierra)\n' \
      "P5b el K18 de 485cdc4 daba VERDE con esto" "$rcv"
  else
    fallos=$((fallos+1)); printf '  [FALLA] %-52s rc=%s: si el viejo ya enrojecia, el brazo no prueba el arreglo\n' \
      "P5b el K18 de 485cdc4 daba VERDE con esto" "$rcv"
  fi
else
  printf '  [....] %-52s\n' "P5b no se pudo sacar 485cdc4 de git: sin contraste"
fi

echo
echo "NO LO AFLOJO · lo que no se puede atribuir al borrador sigue enrojeciendo"
# P1 · una tabla que encoge y NO tiene retencion declarada: no hay nada que la explique.
G="$DIR/g3"; base; sospechosa zzz_sin_retencion 33 29
caso "P1 sin retencion declarada: ROJO"        1 "zzz_sin_retencion\(encoge_sin_declarar:33->29\)" "$G"

# P2 · pierde una sola fila de dentro de la ventana. La magnitud no es la unica regla: si falta
# UNA de las que deberian seguir vivas, el borrador declarado no lo explica.
G="$DIR/g4"; base; sospechosa macro_event 33 28; dentro macro_event event_at 29 28
caso "P2 pierde UNA de dentro de la ventana: ROJO" 1 "pierde_filas_DENTRO_de_la_ventana_de_30d:29->28" "$G"

# P3 · cero filas dentro de la ventana en el espejo: "iguales" no probaria nada.
G="$DIR/g5"; base; sospechosa macro_event 33 5; dentro macro_event event_at 0 0
caso "P3 cero dentro de la ventana: no se exime" 1 "cero_filas_dentro_de_30d" "$G"

# P4 · si el canal no contesta el recuento de dentro, NO se exime por defecto.
G="$DIR/g6"; base; sospechosa macro_event 33 29
caso "P4 sin recuento de dentro: ROJO"          1 "no_se_pudo_contar_dentro_de_la_ventana" "$G"

echo
echo "ANTI-FANTASMA · sin canal no hay veredicto"
G="$DIR/g7"; : > "$G"
caso "F1 prodsql no contesta: NOMED"           2 "prodsql no responde" "$G"

echo
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
