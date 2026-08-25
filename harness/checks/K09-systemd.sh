#!/bin/bash
# K09  nada debe apuntar al arbol LEGACY. Dos mitades: las 8 units versionadas, y la
# unit INSTALADA del respaldo nocturno, que hoy ejecuta el backup.sh del legacy.
set -uo pipefail
B=/srv/coinanalyze/harness; . "$B/env"
malas=$(grep -l -E 'ExecStart=/opt/coinalyze/(\.venv|scripts)' \
        "$REPO"/deploy/systemd/*.service 2>/dev/null | wc -l)
# La unit INSTALADA se mira con systemctl show, no con grep al fichero: asi se lee lo
# que systemd va a ejecutar de verdad, drop-ins incluidos.
inst=$("$B/bin/prod" "systemctl show coinalyze-backup.service -p ExecStart --value" 2>/dev/null || true)
# Y NO basta con que la ruta diga 'current'. El desplegador hace chmod 0640 a todo el
# release (deploy-coinalyze:369), asi que un ExecStart apuntando directo al script del
# release apunta a un fichero NO EJECUTABLE y la copia no se haria. Se comprueba
# ademas que la ultima ejecucion termino bien: es el unico oraculo de que corre.
ultimo=$("$B/bin/prod" "systemctl show coinalyze-backup.service -p Result --value" 2>/dev/null || true)
fallos=""
[ "$malas" -eq 0 ] || fallos="$malas units versionadas a legacy"
case "$inst" in
  *"/opt/coinalyze/current/"*) ;;
  "") echo "NO MEDIDO: no se pudo leer la unit instalada en 140 (${fallos:-canal caido})"; exit 2 ;;
  *) fallos="$fallos; la unit instalada de backup ejecuta el arbol legacy" ;;
esac
case "${ultimo:-}" in
  success|"") ;;
  *) fallos="$fallos; la ultima ejecucion del respaldo acabo en '$ultimo'" ;;
esac
[ -z "${fallos# }" ] || { echo "${fallos#; }"; exit 1; }
echo "0 units a legacy, incluida la instalada del respaldo"
