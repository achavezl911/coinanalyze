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

presentes=$("$B/bin/espejosql" "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1" 2>/dev/null \
            | grep -E '^[a-z_][a-z0-9_]*$' | sort -u)

faltan=$(comm -23 <(printf '%s\n' "$declaradas") <(printf '%s\n' "$presentes") | tr '\n' ' ')
[ -z "${faltan// /}" ] || { echo "al espejo le faltan $(printf '%s' "$faltan" | wc -w) de $n_decl tablas: ${faltan}" | cut -c1-200; exit 1; }

# Restaurada a medias = tablas creadas y vacias. Se lee de una con datos de verdad.
filas=$("$B/bin/espejosql" "SELECT count(*) FROM signal_outcome" 2>/dev/null | grep -E '^[0-9]+$' | head -1)
[ -n "$filas" ] && [ "$filas" -gt 0 ] || { echo "el espejo tiene las $n_decl tablas pero signal_outcome esta vacia (${filas:-sin respuesta})"; exit 1; }

echo "espejo con las $n_decl tablas de schema.sql y $filas filas en signal_outcome"
