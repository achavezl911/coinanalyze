#!/bin/bash
# K01b-control · ¿sabe el comparador distinguir lo que la retencion borro de lo que falta?
#
#     bash harness/checks/K01b-control.bash
#
# POR QUE ESTE CONTROL. El 2026-09-14 la prueba de restauracion dio FALLO sobre un respaldo que
# restaura bien (COLA 123, decision 2): condeno DOS particiones que en 140 tenian CERO filas
# porque la retencion de 12 h las habia vaciado esa manana. Con 0 filas vivas `min(ts)` sale
# vacio, el filtro del tramo vivo se apagaba solo y se comparaba la particion ENTERA. Un
# comparador que confunde «la retencion lo borro» con «al respaldo le faltan filas» acusa al
# unico mecanismo que no tiene vuelta atras.
#
# NO SE BAJA NINGUN RESPALDO Y NO SE TOCA 140. El comparador se ejercita entre DOS BASES
# LOCALES: una hace de respaldo restaurado y otra hace de 140, servida por un `bin/prodsql` de
# mentira que no es un `case` de cadenas sino un psql de verdad contra la segunda base. Asi el
# stub no puede «acertar» por haber adivinado la consulta.
#
# LOS TRES BRAZOS SON LOS TRES QUE EL ENCARGO PIDE, y el segundo es el que sostiene a los otros:
#   C1  una particion VACIADA en 140            -> NO JUZGADA, con su nombre. No condena.
#   C2  una particion con filas vivas que NO cuadran -> FALLO. Si este no dispara, C1 no vale
#       nada: un comparador que nunca condena tambien «perdona» la retencion.
#   C3  ninguna particion con dato              -> NO puede escribir OK.
#
# NO LLEVA .sh A PROPOSITO: bin/verify globea checks/*.sh.
set -uo pipefail
ORIG=${REPO:-/srv/coinanalyze/repo}
CHK="$ORIG/harness/checks/K01b-respaldo-cifrado.sh"
[ -r "$CHK" ] || { echo "NO MEDIDO: no encuentro el check en $CHK"; exit 2; }
command -v psql >/dev/null || { echo "NO MEDIDO: no hay psql en esta maquina"; exit 2; }

DIR=$(mktemp -d) || exit 2
RES="k01b_ctl_res_$$"; PROD="k01b_ctl_140_$$"
limpia() { psql -X -q -d postgres -c "DROP DATABASE IF EXISTS $RES" -c "DROP DATABASE IF EXISTS $PROD" >/dev/null 2>&1; rm -rf "$DIR"; }
[ "${K01B_CONTROL_GUARDA:-0}" = "1" ] || trap limpia EXIT
fallos=0; pasan=0
comprueba() { if [ "$2" = si ]; then pasan=$((pasan+1)); printf '  [ok   ] %-62s\n' "$1"
              else fallos=$((fallos+1)); printf '  [FALLA] %-62s\n' "$1"; fi; }

psql -X -q -d postgres -c "DROP DATABASE IF EXISTS $RES" -c "CREATE DATABASE $RES" >/dev/null 2>&1
psql -X -q -d postgres -c "DROP DATABASE IF EXISTS $PROD" -c "CREATE DATABASE $PROD" >/dev/null 2>&1

# El arnes de mentira: solo `env` y un `bin/prodsql` que habla con la base que hace de 140.
mkdir -p "$DIR/bin"
printf '%s\n' ". /srv/coinanalyze/harness/env" > "$DIR/env"
{ printf '%s\n' '#!/bin/bash'
  printf '%s\n' "printf 'LLAMADO\\n' >> $DIR/senal"
  printf '%s\n' "exec psql -X -A -t -d $PROD -c \"\$1\""
} > "$DIR/bin/prodsql"
chmod +x "$DIR/bin/prodsql"
: > "$DIR/senal"
sed "s#^B=/srv/coinanalyze/harness; . \"\$B/env\"#B=$DIR; . \"\$B/env\"#" "$CHK" > "$DIR/K01b.sh"
cmp -s "$CHK" "$DIR/K01b.sh" && { echo "NO MEDIDO: el sed no mordio; se compararia el check consigo mismo"; exit 2; }

# ESCENARIO: tres particiones cerradas, iguales en las dos bases salvo lo que cada brazo mueva.
siembra() {  # $1 = base
  psql -X -q -d "$1" >/dev/null 2>&1 <<'SQL'
CREATE TABLE cuadra_p20260101 (ts timestamptz, v int);
CREATE TABLE falla_p20260101  (ts timestamptz, v int);
CREATE TABLE vacia_p20260101  (ts timestamptz, v int);
INSERT INTO cuadra_p20260101 SELECT '2026-01-01T00:00:00Z'::timestamptz + (i||' min')::interval, i FROM generate_series(1,50) i;
INSERT INTO falla_p20260101  SELECT '2026-01-01T00:00:00Z'::timestamptz + (i||' min')::interval, i FROM generate_series(1,50) i;
INSERT INTO vacia_p20260101  SELECT '2026-01-01T00:00:00Z'::timestamptz + (i||' min')::interval, i FROM generate_series(1,50) i;
SQL
}
siembra "$RES"; siembra "$PROD"
# 140 hoy: `vacia` la borro la retencion; a `falla` le sobra una fila que el respaldo NO tiene.
psql -X -q -d "$PROD" -c "DELETE FROM vacia_p20260101" >/dev/null 2>&1
psql -X -q -d "$PROD" -c "INSERT INTO falla_p20260101 VALUES ('2026-01-01T00:30:30Z', 999)" >/dev/null 2>&1
# Y el respaldo tiene ADEMAS el prefijo viejo que la retencion ya se llevo de 140: eso es lo
# NORMAL y no puede condenar. Sin esta fila el brazo C1 pasaria por la razon equivocada.
psql -X -q -d "$RES" -c "INSERT INTO cuadra_p20260101 VALUES ('2025-12-31T23:00:00Z', -1)" >/dev/null 2>&1

# LA FECHA DEL RESPALDO ES LA DE HOY, y no una del pasado. Con una fecha vieja el brazo C4
# salia rc=1 aunque el OK se hubiera escrito: el veredicto final de K01b mira la EDAD de la
# ultima prueba y 20260201 estaba a 226 dias del limite de 8. Era el control mal montado, no el
# check; y de paso deja claro que el brazo de la edad sigue vivo.
HOY=$(date -u +%Y%m%d)
corre() { OUT=$(env K01B_RESTAURA=1 K01B_SALTA_RESTAURA=1 K01B_BASE="$RES" \
                    K01B_FECHA="$HOY" K01B_REG="$DIR/reg.tsv" "$@" \
                    timeout -k 5 300 bash "$DIR/K01b.sh" 2>&1); RC=$?; }

echo "K01b-control · sujeto: $CHK"
echo

echo "C0 · el mando que salta la restauracion NO puede escribir en el registro compartido"
OUT0=$(env K01B_RESTAURA=1 K01B_SALTA_RESTAURA=1 K01B_BASE="$RES" timeout -k 5 60 bash "$DIR/K01b.sh" 2>&1); RC0=$?
comprueba "C0a NO MEDIDO, rc=2 (rc=$RC0)" "$([ "$RC0" = 2 ] && echo si || echo no)"
comprueba "C0b y lo dice: sin restaurar no sabe si el respaldo restaura" \
  "$(printf '%s' "$OUT0" | grep -q 'no sabe si el respaldo restaura' && echo si || echo no)"

echo
echo "C1 · una particion VACIADA por la retencion NO condena, y sale nombrada"
corre
comprueba "C1a el prodsql de mentira fue LLAMADO" "$([ -s "$DIR/senal" ] && echo si || echo no)"
comprueba "C1b NOMBRA vacia_p20260101 como no juzgada, con su motivo" \
  "$(printf '%s' "$OUT" | grep -q 'vacia_p20260101(0 filas vivas en 140: la retencion la vacio)' && echo si || echo no)"
comprueba "C1c y NO aparece entre los fallos" \
  "$(printf '%s' "$OUT" | grep -q 'vacia_p20260101(0:' && echo no || echo si)"
comprueba "C1d cuadra_p20260101 SI se compara, con el prefijo viejo que 140 ya no tiene" \
  "$(printf '%s' "$OUT" | grep -q 'cuadra_p20260101' && echo no || echo si)"

echo
echo "C2 · una particion con filas vivas que NO cuadran SI condena"
comprueba "C2a FALLO, rc distinto de 0 en la parte de prueba" \
  "$(printf '%s' "$OUT" | grep -q '^FALLO:' && echo si || echo no)"
comprueba "C2b y nombra falla_p20260101 con las dos huellas" \
  "$(printf '%s' "$OUT" | grep -q 'falla_p20260101(' && echo si || echo no)"
comprueba "C2c dice sobre CUANTAS particiones CON DATO lo dice" \
  "$(printf '%s' "$OUT" | grep -q 'sobre 2 particiones CON DATO' && echo si || echo no)"

echo
echo "C3 · sin NINGUNA particion con dato NO se puede escribir OK"
psql -X -q -d "$PROD" -c "DELETE FROM cuadra_p20260101" -c "DELETE FROM falla_p20260101" >/dev/null 2>&1
: > "$DIR/reg.tsv"
corre
comprueba "C3a NO MEDIDO, rc=2 (rc=$RC)" "$([ "$RC" = 2 ] && echo si || echo no)"
comprueba "C3b y dice que no ha ejercitado el respaldo" \
  "$(printf '%s' "$OUT" | grep -q 'no ha ejercitado el respaldo' && echo si || echo no)"
comprueba "C3c y NO escribio nada en el registro" \
  "$([ ! -s "$DIR/reg.tsv" ] && echo si || echo no)"
comprueba "C3d nombra las TRES no juzgadas" \
  "$(printf '%s' "$OUT" | grep -q 'cuadra_p20260101' && printf '%s' "$OUT" | grep -q 'falla_p20260101' \
     && printf '%s' "$OUT" | grep -q 'vacia_p20260101' && echo si || echo no)"

echo
echo "C4 · EL CONTROL POSITIVO · con todo cuadrando, escribe OK y el check queda VERDE"
siembra "$PROD" >/dev/null 2>&1
psql -X -q -d "$PROD" -c "DROP TABLE IF EXISTS falla_p20260101" >/dev/null 2>&1
psql -X -q -d "$RES"  -c "DROP TABLE IF EXISTS falla_p20260101" >/dev/null 2>&1
psql -X -q -d "$PROD" -c "DELETE FROM vacia_p20260101" >/dev/null 2>&1
: > "$DIR/reg.tsv"
corre
comprueba "C4a VERDE, rc=0 (rc=$RC)" "$([ "$RC" = 0 ] && echo si || echo no)"
comprueba "C4b escribe OK diciendo CUANTAS con dato" \
  "$(grep -q 'particiones CON DATO cuadran fila a fila' "$DIR/reg.tsv" && echo si || echo no)"
comprueba "C4c y la vaciada sigue nombrada en la linea" \
  "$(printf '%s' "$OUT" | grep -q 'vacia_p20260101(0 filas vivas' && echo si || echo no)"

echo
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
