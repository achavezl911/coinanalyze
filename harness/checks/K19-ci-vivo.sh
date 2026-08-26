#!/bin/bash
# K19  el CI no puede morirse en silencio. Paso 9 dias muerto -del 2026-08-15 al
# 25- con la unit en ActiveState=active: verde por fuera. Un Runner.Listener
# huerfano reparentado a PID 1 retenia la sesion de GitHub y la unit reiniciaba en
# bucle con SessionConflictException (NRestarts=13). Nada lo vigilaba, y verify
# tampoco, porque verify no mira sus propias tuberias.
#
# Tres senales, y ninguna vale sola:
#   1. UN solo Runner.Listener. Cero = runner caido; dos o mas = el huerfano otra vez.
#   2. NRestarts que no crece entre ejecuciones. Un bucle de reinicios es la firma
#      exacta de aquello, y ActiveState=active no lo delata.
#   3. El ultimo run de ci.yml en main, reciente y en success. Sin esto, un runner
#      sano que no ejecuta nada tambien pasaria.
#
# OJO: se cuenta con ps -C (nombre exacto), NO con pgrep -f. pgrep -f 'Runner.Listener'
# se encuentra a SI MISMO -la orden lleva el patron en su linea de comandos- y
# devolvia 2 con un solo listener vivo. Un check que se creyera eso enrojeceria solo.
set -uo pipefail
_REPO_LLAMANTE=${REPO:-}
B=/srv/coinanalyze/harness; . "$B/env"
REG="$B/estado/k19.tsv"
REPO=${_REPO_LLAMANTE:-${REPO:-/srv/coinanalyze/repo}}
DIAS_MAX=${K19_DIAS_MAX:-7}

command -v gh >/dev/null 2>&1 || { echo "NO MEDIDO: no hay gh"; exit 2; }

fallos=""

vivos=$(ps -C Runner.Listener --no-headers 2>/dev/null | wc -l)
case "$vivos" in
  1) ;;
  0) fallos="$fallos ningun Runner.Listener vivo (runner caido)" ;;
  *) fallos="$fallos $vivos Runner.Listener vivos: el huerfano otra vez" ;;
esac

activo=$(systemctl is-active github-runner.service 2>/dev/null || true)
[ "$activo" = "active" ] || fallos="$fallos; github-runner.service esta '$activo'"

ahora=$(systemctl show github-runner.service -p NRestarts --value 2>/dev/null)
case "$ahora" in ''|*[!0-9]*) ahora="" ;; esac
if [ -n "$ahora" ]; then
  previo=$(tail -1 "$REG" 2>/dev/null | cut -f2)
  case "${previo:-}" in ''|*[!0-9]*) previo="" ;; esac
  if [ -n "$previo" ] && [ "$ahora" -gt "$previo" ]; then
    fallos="$fallos; NRestarts crecio de $previo a $ahora: la unit reinicia en bucle"
  fi
  printf '%s\t%s\n' "$(date -u +%FT%TZ)" "$ahora" >> "$REG"
else
  fallos="$fallos; no se pudo leer NRestarts"
fi

# --status completed: un run EN COLA no es un run fallido. Sin este filtro, durante los
# minutos que van del merge al final del CI el ultimo run no tiene conclusion y esto
# imprimia "el ultimo CI de main acabo en ''" y ponia el check en ROJO. Es un ROJO FALSO y
# del canal, y ademas es el peor tipo: K07 tiene el mismo selector y ahi el mismo hueco
# sale como NO MEDIDO -falla abierto y se nota-, mientras que aqui fallaba CERRADO y se
# leia como una regresion del CI. Medido el 2026-08-26 con el run 32983804997 en cola.
ultimo=$(cd "$REPO" && gh run list --workflow=ci.yml --branch main --status completed --limit 1 \
         --json conclusion,createdAt --jq '.[0] | "\(.conclusion) \(.createdAt)"' 2>/dev/null)
[ -n "$ultimo" ] || { echo "NO MEDIDO: gh no devolvio runs de ci.yml en main"; exit 2; }
estado=${ultimo%% *}; cuando=${ultimo##* }
[ "$estado" = "success" ] || fallos="$fallos; el ultimo CI de main acabo en '$estado'"
edad=$(( ( $(date -u +%s) - $(date -u -d "$cuando" +%s) ) / 86400 ))
[ "$edad" -le "$DIAS_MAX" ] || fallos="$fallos; el ultimo CI de main es de hace $edad dias (limite $DIAS_MAX)"

[ -z "${fallos# }" ] || { echo "${fallos#; }" | sed 's/^ //'; exit 1; }
echo "1 listener, unit active, NRestarts=$ahora sin crecer, ultimo CI de main success hace $edad dias"
