#!/bin/bash
# base desechable del banco IND R2: esquema de main + particiones
set -e
DB=ind_r2
H=/var/run/postgresql
dropdb --host=$H --if-exists "$DB"
createdb --host=$H "$DB"
psql --host=$H -d "$DB" -q -v ON_ERROR_STOP=1 -f /srv/coinanalyze/repo/sql/schema.sql >/dev/null
psql --host=$H -d "$DB" -At -c "SELECT c.relname FROM pg_inherits i JOIN pg_class c ON c.oid=i.inhrelid JOIN pg_class p ON p.oid=i.inhparent WHERE p.relname IN ('orderflow_cinta','liquidations_realtime') ORDER BY 1" | tr '\n' ' '
echo
psql --host=$H -d "$DB" -At -c "SHOW lc_collate" -c "SHOW server_version"
