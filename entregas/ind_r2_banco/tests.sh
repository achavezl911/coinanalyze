#!/bin/bash
# ruff y los dos tests de IND R2 en una base desechable con el esquema
cd /srv/coinanalyze/repo
H=/var/run/postgresql
.venv/bin/python -m ruff check . 2>&1 | tail -3
dropdb --host=$H --if-exists ind_r2_t
createdb --host=$H ind_r2_t
TEST_DATABASE_URL="postgresql:///ind_r2_t?host=$H" .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_orderflow.py \
  -k "sondeo_de_la_ejecucion or se_pinta_donde_se_ejecuto" 2>&1 | tail -5
dropdb --host=$H --if-exists ind_r2_t
