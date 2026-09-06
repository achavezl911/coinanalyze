#!/bin/bash
# K09  nada de lo que systemd EJECUTA debe apuntar al arbol LEGACY.
#
# EL CRITERIO CAMBIO EL 2026-09-06 PORQUE MEDIA EL ARBOL EQUIVOCADO. La version anterior
# enrojecia con «8 units versionadas a legacy» leyendo $REPO/deploy/systemd/*.service, y
# llevaba ROJA 26 de 27 pasadas guardadas. Medido en las dos puntas el 2026-09-06:
#
#   EL REPO dice legacy en las 9:      grep -c "opt/coinalyze/current" deploy/systemd/*.service
#                                      -> 0 en todas
#   140 EJECUTA current en las 7:      systemctl show <u> -p ExecStart --value
#                                      -> /opt/coinalyze/current/.venv/bin/{uvicorn,python}
#                                         y /bin/bash /opt/coinalyze/current/scripts/backup.sh
#
# NO ES QUE OCHO FICHEROS ESTEN MAL: es que esos ficheros son la PLANTILLA y no lo instalado.
# Quien escribe la version es el desplegador, y esta es la cita
# (/usr/local/sbin/deploy-coinalyze:124-138, leido en 140):
#
#     for u in "${SERVICES[@]}"; do
#       local f="/etc/systemd/system/$u.service"
#       [ -f "$f" ] || continue
#       if ! grep -q "$CURRENT" "$f"; then
#         cp -a "$f" "$f.pre-releases.bak" 2>/dev/null || true
#         sed -i -e "s#^WorkingDirectory=${APP_ROOT}\$#WorkingDirectory=${CURRENT}#" \
#                -e "s#${APP_ROOT}/\.venv#${CURRENT}/.venv#g" "$f"
#
# O sea que la unit del repo apunta a APP_ROOT A PROPOSITO y el desplegador la reapunta a
# CURRENT al instalar. Exigirle `current` al fichero del repo es exigirle que ya este
# sustituido antes de sustituirlo.
#
# LO QUE SI PUEDE ROMPERSE, y es lo que se gatea ahora, son las DOS grietas de ese sed:
#   1. Solo recorre ${SERVICES[@]}, una lista FIJA dentro del wrapper. Una unit nueva que no
#      entre en esa lista no se reapunta nunca y se queda ejecutando el arbol legacy.
#   2. Solo sustituye ${APP_ROOT}/.venv. coinalyze-backup.service apunta a
#      /opt/coinalyze/scripts/backup.sh -sin .venv-, asi que ese sed NO lo habria arreglado;
#      hoy esta bien por otro camino (K49, commit 69f0245).
# Las dos grietas se ven igual desde fuera: una unit INSTALADA cuyo ExecStart toca
# /opt/coinalyze/ sin pasar por current/. Eso es lo que se mide, y sobre TODAS las units
# instaladas, no sobre una lista.
#
# LA PREGUNTA ES SEMANTICA, NO LEXICA: ¿este ExecStart toca /opt/coinalyze SIN pasar por
# current? Asi da igual por donde empiece la linea -coinalyze-scalp@ y coinalyze-ws@
# empiezan por /usr/bin/env- y da igual si la ruta va en `path=` o en `argv[]=`, que es
# donde vive la de backup.
# EL PREFIJO LLEVA BARRA A PROPOSITO: /opt/coinalyze-ai-bridge es el TERCER arbol y empieza
# igual que /opt/coinalyze. Sin la barra saldria acusado un servicio que no tiene que ver.
set -uo pipefail
_REPO_LLAMANTE=${REPO:-}
B=/srv/coinanalyze/harness; . "$B/env"
REPO=${_REPO_LLAMANTE:-${REPO:-/srv/coinanalyze/repo}}
PROD=${K09_PROD:-$B/bin/prod}

[ -x "$PROD" ] || { echo "NO MEDIDO: no hay canal a 140 ($PROD)"; exit 2; }

# --- 1 · TODAS las units instaladas y su ExecStart completo ----------------------------
# Se piden las dos partes -path= y argv[]=- porque la de backup ejecuta /bin/bash y el
# script del release viaja en argv. Mirar solo path= la daria por buena siempre.
crudo=$("$PROD" 'for f in /etc/systemd/system/coinalyze-*.service; do u=$(basename "$f" .service); printf "%s\t%s\n" "$u" "$(systemctl show "$u.service" -p ExecStart --value 2>/dev/null | tr "\n" " ")"; done' 2>&1); rc=$?
if [ "$rc" != "0" ]; then
  echo "NO MEDIDO: no se pudieron leer las units instaladas en 140 (rc=$rc): $(printf '%s' "$crudo" | tail -1 | cut -c1-110)"
  exit 2
fi
n_units=$(printf '%s\n' "$crudo" | grep -c '^coinalyze-' || true)
# CERO UNITS NO ES CERO DEFECTOS: si el glob no encuentra nada, "0 a legacy" seria
# indistinguible de "no he mirado ninguna". Son 7 hoy; menos de 4 es que algo se rompio.
[ "${n_units:-0}" -ge 4 ] || { echo "NO MEDIDO: solo $n_units unit(s) instaladas encontradas en 140"; exit 2; }

malas_lista=""
sin_exec=0
while IFS=$'\t' read -r u es; do
  [ -n "$u" ] || continue
  case "$u" in coinalyze-*) ;; *) continue ;; esac
  if [ -z "${es// /}" ]; then sin_exec=$((sin_exec+1)); continue; fi
  # toca el arbol de la app SIN pasar por current -> mala. El resto (ai-bridge, /bin/bash,
  # /usr/bin/env) no se toca.
  resto=$(printf '%s' "$es" | sed 's#/opt/coinalyze/current/#|OK|#g')
  case "$resto" in
    *"/opt/coinalyze/"*) malas_lista="$malas_lista $u" ;;
  esac
done <<EOFU
$(printf '%s\n' "$crudo")
EOFU
malas=$(printf '%s' "$malas_lista" | wc -w)

# --- 2 · el respaldo nocturno corre, y acaba bien --------------------------------------
# No basta con que la ruta diga 'current': el desplegador hace chmod 0640 a todo el release
# (deploy-coinalyze:369), asi que un ExecStart al script del release apunta a un fichero NO
# ejecutable. El Result es el unico oraculo de que corre de verdad.
ultimo=$("$PROD" "systemctl show coinalyze-backup.service -p Result --value" 2>/dev/null || true)

fallos=""
[ "$malas" -eq 0 ] || fallos="$malas unit(s) INSTALADAS en 140 ejecutan el arbol legacy:$malas_lista"
case "${ultimo:-}" in
  success|"") ;;
  *) fallos="$fallos; la ultima ejecucion del respaldo acabo en '$ultimo'" ;;
esac

[ -z "${fallos# }" ] || { echo "${fallos#; }"; exit 1; }
echo "las $n_units units instaladas en 140 ejecutan /opt/coinalyze/current, y el ultimo respaldo acabo en success"
printf '  las plantillas de %s/deploy/systemd apuntan a APP_ROOT a proposito: el desplegador las reapunta\n' "$(basename "$REPO")"
printf '  (deploy-coinalyze:124-138). Lo que se vigila aqui es el RESULTADO en 140, no la plantilla.\n'
[ "$sin_exec" -eq 0 ] || printf '  %s unit(s) sin ExecStart legible: plantilladas (@) sin instancia activa\n' "$sin_exec"
exit 0
