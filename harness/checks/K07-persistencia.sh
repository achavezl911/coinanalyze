#!/bin/bash
# K07  el CI tiene que probar la persistencia. Hoy no la prueba: los 16
# tests/*_postgres.py hacen pytest.skip en tiempo de ejecucion si falta
# TEST_DATABASE_URL, y ci.yml no la define NI UNA VEZ. Son 167 tests -toda la
# persistencia- que no se ejecutan nunca. Medido el 2026-08-25:
#   pytest tests/*_postgres.py --collect-only -q  ->  167 tests collected
#   grep -c TEST_DATABASE_URL .github/workflows/ci.yml  ->  0
#
# El criterio NO es "cuantos tests se recolectan": un test con skip se recolecta
# igual sin ejecutarse, asi que un suelo de recolectados se cumple habiendo probado
# CERO persistencia. Se mide lo que el CI realmente ejecuto, leyendo el resumen de
# pytest del ultimo run de main. Eso es un oraculo de comportamiento, no de texto.
#
# Y que el espejo sirve para esto ya esta probado (2026-08-25):
#   TEST_DATABASE_URL=postgresql://root@/coinalyze_espejo?host=/var/run/postgresql
#   pytest tests/test_pr25_research_knowledge_time_postgres.py -q  ->  16 passed
# Cada fichero crea su propio schema con uuid y lo tira: no toca tablas existentes.
set -uo pipefail
_REPO_LLAMANTE=${REPO:-}
B=/srv/coinanalyze/harness; . "$B/env"
REPO=${_REPO_LLAMANTE:-${REPO:-/srv/coinanalyze/repo}}
# 1052 pasan hoy sin persistencia + 167 de los *_postgres.py = 1219. El suelo va por
# debajo para dar margen a que alguno se reorganice, pero muy por encima de 1052:
# solo se alcanza si los *_postgres.py se ejecutan de verdad.
SUELO=${K07_SUELO:-1200}
# Hoy hay 215 saltados, de los que 167 son la persistencia. Si esos corren, los
# saltos tienen que bajar de 100 con holgura.
SALTOS_MAX=${K07_SALTOS_MAX:-100}

command -v gh >/dev/null 2>&1 || { echo "NO MEDIDO: no hay gh"; exit 2; }
[ -r "$REPO/.github/workflows/ci.yml" ] || { echo "NO MEDIDO: no se lee ci.yml"; exit 2; }

fallos=""
[ "$(grep -c 'TEST_DATABASE_URL' "$REPO/.github/workflows/ci.yml")" -ge 1 ] \
  || fallos="$fallos ci.yml no define TEST_DATABASE_URL"

rid=$(cd "$REPO" && gh run list --workflow=ci.yml --branch main --limit 1 --json databaseId --jq '.[0].databaseId' 2>/dev/null)
[ -n "$rid" ] || { echo "NO MEDIDO: gh no devolvio ningun run de ci.yml en main"; exit 2; }
resumen=$(cd "$REPO" && gh run view "$rid" --log 2>/dev/null | grep -oE '[0-9]+ passed(, [0-9]+ skipped)?' | tail -1)
[ -n "$resumen" ] || { echo "NO MEDIDO: el log del run $rid no trae resumen de pytest"; exit 2; }

pasan=$(printf '%s' "$resumen" | grep -oE '^[0-9]+')
saltan=$(printf '%s' "$resumen" | grep -oE '[0-9]+ skipped' | grep -oE '^[0-9]+')
saltan=${saltan:-0}

[ "$pasan" -ge "$SUELO" ] || fallos="$fallos; el ultimo CI de main paso $pasan tests, por debajo del suelo $SUELO"
[ "$saltan" -le "$SALTOS_MAX" ] || fallos="$fallos; salto $saltan tests, mas de $SALTOS_MAX: la persistencia sigue sin ejecutarse"

[ -z "${fallos# }" ] || { printf '%s\n' "${fallos#; }" | sed 's/^ //'; exit 1; }
echo "ci.yml define TEST_DATABASE_URL y el ultimo CI de main paso $pasan tests saltando $saltan"
