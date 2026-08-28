#!/bin/bash
# K09  nada debe apuntar al arbol LEGACY. Dos mitades: las 8 units versionadas, y la
# unit INSTALADA del respaldo nocturno, que hoy ejecuta el backup.sh del legacy.
set -uo pipefail
# EL ARBOL LO PUEDE FIJAR EL LLAMANTE. Sin esto, `. "$B/env"` PISA la REPO del entorno y
# el check mide siempre el arbol de trabajo, pasara lo que pasara: no se puede correr
# contra origin/main -que es lo que hace el gate de K15- ni montarle un control con un
# arbol de mentira. Lo descubri intentando inducir los casos de abajo: el override no
# tomaba. Es el mismo patron que ya usa K31.
_REPO_LLAMANTE=${REPO:-}
B=/srv/coinanalyze/harness; . "$B/env"
REPO=${_REPO_LLAMANTE:-${REPO:-/srv/coinanalyze/repo}}
# EL ANCLA SUBCONTABA, Y EL DIA QUE ALGUIEN ARREGLARA LAS SEIS ESTE CHECK HABRIA DICHO
# "0 units a legacy" CON DOS TODAVIA A LEGACY. El patron viejo era
#     ExecStart=/opt/coinalyze/(\.venv|scripts)
# o sea LEXICO: exigia que la ruta legacy fuera lo PRIMERO tras ExecStart=. Pero
# coinalyze-scalp@.service y coinalyze-ws@.service empiezan por /usr/bin/env:
#     ExecStart=/usr/bin/env COLLECTOR_SHARD_INDEX=%i /opt/coinalyze/.venv/bin/python ...
# apuntan a legacy igual y el grep no las veia. MEDIDO sobre origin/main: con el ancla
# salen 6, sin ella 8.
# LA PREGUNTA ES SEMANTICA, NO LEXICA: ¿este ExecStart toca /opt/coinalyze SIN pasar por
# current? Asi da igual por donde empiece la linea.
# Se mira LINEA A LINEA y no el fichero entero a la vez: una unit con dos ExecStart, uno
# a current y otro a legacy, pasaria si bastara con que ALGUNA linea mencionara current.
malas_lista=""
for f in "$REPO"/deploy/systemd/*.service; do
  [ -r "$f" ] || continue
  mala=no
  while IFS= read -r es; do
    case "$es" in
      *"/opt/coinalyze/current/"*) ;;
      *"/opt/coinalyze/"*) mala=si ;;
    esac
  done <<EOFUNIT
$(grep -h '^ExecStart=' "$f" 2>/dev/null)
EOFUNIT
  [ "$mala" = si ] && malas_lista="$malas_lista $(basename "$f")"
done
malas=$(printf '%s' "$malas_lista" | wc -w)
# La unit INSTALADA se mira con systemctl show, no con grep al fichero: asi se lee lo
# que systemd va a ejecutar de verdad, drop-ins incluidos.
inst=$("$B/bin/prod" "systemctl show coinalyze-backup.service -p ExecStart --value" 2>/dev/null || true)
# Y NO basta con que la ruta diga 'current'. El desplegador hace chmod 0640 a todo el
# release (deploy-coinalyze:369), asi que un ExecStart apuntando directo al script del
# release apunta a un fichero NO EJECUTABLE y la copia no se haria. Se comprueba
# ademas que la ultima ejecucion termino bien: es el unico oraculo de que corre.
ultimo=$("$B/bin/prod" "systemctl show coinalyze-backup.service -p Result --value" 2>/dev/null || true)
fallos=""
[ "$malas" -eq 0 ] || fallos="$malas units versionadas a legacy:$malas_lista"
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
