#!/bin/bash
cd /srv/coinanalyze/x1-tmp/banco-ind-r2
date -u +%T
psql --host=/var/run/postgresql -d ind_r2 -v ON_ERROR_STOP=1 -f gen.sql > gen.log 2>&1
echo "rc=$?" >> gen.log
date -u +%T >> gen.log
df -h / | tail -1 >> gen.log
