#!/bin/bash
# equivalencia y tiempos: main (worktree en cd794ea) contra la rama (repo), misma base ind_r2
cd /srv/coinanalyze/x1-tmp/banco-ind-r2
PY=/srv/coinanalyze/repo/.venv/bin/python
$PY corre.py main main 3 2>&1 | tail -3
$PY corre.py /srv/coinanalyze/repo rama 3 2>&1 | tail -3
for h in 6 12 24; do
  if cmp -s out/main-$h.json out/rama-$h.json; then echo "$h h IDENTICOS byte a byte ($(wc -c < out/rama-$h.json) B)"
  else echo "$h h DISTINTOS"; fi
done
