#!/bin/bash
# K01a  el espejo de 143 tiene que existir y servir. Era la unica unidad cerrada SIN
# check: "hecha pero no medida", que en este proyecto es lo mismo que una opinion.
#
# Se comprueba por NOMBRE, no por cuenta. El espejo tiene 66 tablas y schema.sql
# declara 39: contar y comparar 66 >= 39 daria VERDE aunque faltara justo la tabla
# que importa, porque sobran particiones y las _unpartitioned_backup. Se exige que
# esten LAS 39 declaradas, una por una.
#
# Y no basta con que existan: el espejo sirve para correr los tests de persistencia
# (probado el 2026-08-25, 16 passed de test_pr25_..._postgres.py contra el), asi que
# el check confirma tambien que se puede LEER de verdad de una tabla con datos. Una
# base restaurada a medias tiene las tablas creadas y vacias.
set -uo pipefail
_REPO_LLAMANTE=${REPO:-}
B=/srv/coinanalyze/harness; . "$B/env"
REPO=${_REPO_LLAMANTE:-${REPO:-/srv/coinanalyze/repo}}
ESQUEMA="$REPO/sql/schema.sql"

[ -r "$ESQUEMA" ] || { echo "NO MEDIDO: no se puede leer sql/schema.sql"; exit 2; }

vivo=$("$B/bin/espejosql" "SELECT 'ok_espejo'" 2>/dev/null | grep -c 'ok_espejo')
[ "$vivo" -ge 1 ] || { echo "NO MEDIDO: el espejo $ESPEJO_DB no responde"; exit 2; }

declaradas=$(grep -oE '^CREATE TABLE( IF NOT EXISTS)? [a-z_]+' "$ESQUEMA" \
             | awk '{print $NF}' | sort -u)
n_decl=$(printf '%s\n' "$declaradas" | grep -c .)
[ "$n_decl" -ge 30 ] || { echo "NO MEDIDO: solo se extrajeron $n_decl tablas de schema.sql"; exit 2; }

# K63 · UNA CONSULTA QUE NO DEVUELVE LO QUE PEDI ES NO MEDIDO, NUNCA ROJO.
# El error de este check no era el veredicto, era la FRASE: como devops, espejosql
# devuelve "ERROR: permission denied for table signal_outcome", el filtro numerico se lo
# comia y la linea publicaba "signal_outcome esta vacia" -algo FALSO sobre la evidencia de
# produccion, dicho con la misma cara que una medicion buena, y el espejo tiene 180696
# filas-. La salida cruda se guarda ANTES de filtrar, para poder nombrar el error.
# SE PREGUNTA PRIMERO EL CONTEO Y DESPUES LOS NOMBRES, y no es rodeo: en una LISTA, cero
# filas es ambiguo -puede ser un error tragado o una base de verdad sin tablas- y resolver
# esa ambiguedad hacia NO MEDIDO esconderia un ROJO real, que es este mismo defecto del
# reves. Un count(*) NO es ambiguo: si tuvo exito devuelve exactamente una linea numerica,
# nunca cero. Asi "no pude leer" y "lei y hay 0" quedan separados por la forma.
crudo_n=$("$B/bin/espejosql" "SELECT count(*) FROM pg_tables WHERE schemaname='public'" 2>&1)
n_pub=$(printf '%s\n' "$crudo_n" | grep -E '^[0-9]+$' | head -1)
[ -n "$n_pub" ] || {
  echo "NO MEDIDO: contar las tablas del espejo no devolvio un numero: $(printf '%s' "$crudo_n" | head -1 | cut -c1-120)"
  exit 2; }

crudo_tablas=$("$B/bin/espejosql" "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1" 2>&1)
presentes=$(printf '%s\n' "$crudo_tablas" | grep -E '^[a-z_][a-z0-9_]*$' | sort -u)
n_pres=$(printf '%s\n' "$presentes" | grep -c .)
# Y la lista tiene que traer TANTOS nombres como dijo el conteo. Si no, llego recortada
# -harness/bin/_corta corta a 8 KB- y juzgar "faltan tablas" sobre una lista truncada es
# inventar. Hoy me paso con 180 filas en otro check: la salida partida no colo por poco.
[ "$n_pres" -eq "$n_pub" ] || {
  echo "NO MEDIDO: el espejo dice tener $n_pub tablas y el listado trajo $n_pres nombres; la lista llego incompleta y no se puede juzgar que falta"
  exit 2; }

faltan=$(comm -23 <(printf '%s\n' "$declaradas") <(printf '%s\n' "$presentes") | tr '\n' ' ')
[ -z "${faltan// /}" ] || { echo "al espejo le faltan $(printf '%s' "$faltan" | wc -w) de $n_decl tablas: ${faltan}" | cut -c1-200; exit 1; }

# Restaurada a medias = tablas creadas y vacias. Se lee de una con datos de verdad.
# LOS DOS CASOS SE SEPARAN, y esa separacion es el check: "no pude contar" es NO MEDIDO y
# nombra el error; "conte y salio 0" sigue siendo ROJO, que es el control positivo de K63
# -un arreglo que convirtiera todo vacio en NO MEDIDO apagaria el check-.
crudo_filas=$("$B/bin/espejosql" "SELECT count(*) FROM signal_outcome" 2>&1)
filas=$(printf '%s\n' "$crudo_filas" | grep -E '^[0-9]+$' | head -1)
[ -n "$filas" ] || {
  echo "NO MEDIDO: contar signal_outcome en el espejo no devolvio un numero: $(printf '%s' "$crudo_filas" | head -1 | cut -c1-120)"
  exit 2; }
[ "$filas" -gt 0 ] || { echo "el espejo tiene las $n_decl tablas pero signal_outcome esta VACIA: 0 filas contadas"; exit 1; }

echo "espejo con las $n_decl tablas de schema.sql y $filas filas en signal_outcome"
