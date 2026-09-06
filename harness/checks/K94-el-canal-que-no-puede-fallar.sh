#!/bin/bash
# K94  UN CANAL DE MEDIDA TIENE QUE PODER DECIR QUE FALLO, Y DECIR POR QUE.
#
# EL HECHO QUE LO MOTIVA, medido el 2026-09-06 y encontrado midiendo otra cosa:
#   espejosql "SELECT columna_que_no_existe FROM signal_outcome LIMIT 1"
#       rc=0 · stdout: "ERROR:  column ... does not exist" · stderr: vacio
#   prodsql   la misma consulta
#       rc=3 · stdout: vacio · stderr: VACIO
# El primero dice que todo fue bien. El segundo dice que fue mal y no dice que.
#
# POR QUE ES PEOR EN EL ESPEJO QUE EN PRODUCCION. CLAUDE.md §6 paso 5: «arregla en rama.
# Verifica en el ESPEJO, nunca en 140». El espejo es el canal con el que se comprueba
# todo lo demas antes de tocar produccion. Cualquier guardia `rc != 0 -> NO MEDIDO`
# escrito contra el espejo NO PUEDE DISPARARSE JAMAS, y una consulta rota llega al check
# disfrazada de «sin filas». Es el mismo fallo que el operador ya pago en `prodsql` el
# 2026-09-05 -y que K91-control-del-canal.bash vigila desde entonces- sin arreglar en el
# otro canal, pese a que el comentario de `espejosql:6-9` dice que los dos no deben
# discrepar.
#
# LOS TRES REQUISITOS, y son tres porque los dos canales fallan cada uno los suyos:
#   R1  con un SQL que falla, el canal sale con rc != 0
#   R2  el mensaje del motor LLEGA al llamante  (stderr no vacio)
#   R3  y NO viene mezclado con los datos (stdout no trae el texto del error), porque una
#       fila cuyo primer campo empiece por ERROR: seria indistinguible de un fallo. Esa
#       confusion ya produjo un falso positivo medido: `SELECT 'ERROR: esto es un dato'`
#       daba rc=5 en la version anterior de prodsql.
#
# COMO SE MIDE SIN RED Y SIN BASE. No se toca ni 140 ni el espejo: se pone por delante en
# el PATH un `psql` y un `ssh` de mentira que escriben el mensaje del motor en STDERR y
# salen con rc=3, que es lo que hacen los de verdad cuando ON_ERROR_STOP=1 corta un
# script. Todo lo demas del canal -la captura, el guardia, el corte- es el original letra
# por letra. Es la tecnica de K91, aplicada a los dos canales en vez de a uno.
#
# EL SUJETO ES EL ARBOL: harness/bin/espejosql y harness/bin/prodsql del repo.
set -uo pipefail
REPO=${K94_REPO:-${REPO:-/srv/coinanalyze/repo}}

DIR=$(mktemp -d) || { echo "NO MEDIDO: no se pudo crear el directorio de trabajo"; exit 2; }
trap 'rm -rf "$DIR"' EXIT

# --- los motores de mentira ---------------------------------------------------------
# Escriben en stderr y salen 3: exactamente lo que hace psql con ON_ERROR_STOP=1 ante un
# script que falla, y lo que ssh devuelve cuando el mandato remoto sale con ese codigo.
mkdir -p "$DIR/bin"
MSG='ERROR:  column "columna_que_no_existe" does not exist'
for prog in psql ssh; do
  {
    printf '#!/bin/sh\n'
    printf 'printf "%%s\\n" %s >&2\n' "'$MSG'"
    printf 'exit 3\n'
  } > "$DIR/bin/$prog"
  chmod +x "$DIR/bin/$prog"
done
# base64 y las demas herramientas que usan los canales tienen que seguir estando
export PATH="$DIR/bin:$PATH"

# el entorno que los canales esperan; si falta, es NO MEDIDO y no ROJO
ENVF="$REPO/harness/env"
[ -r "$ENVF" ] || ENVF=/srv/coinanalyze/harness/env
[ -r "$ENVF" ] || { echo "NO MEDIDO: no encuentro harness/env, que los canales cargan al arrancar"; exit 2; }

fallos=""
n_probados=0

prueba() {  # <nombre del canal> <ruta>
  local nombre="$1" bin="$2"
  [ -r "$bin" ] || { echo "NO MEDIDO: no encuentro $bin"; exit 2; }
  n_probados=$((n_probados+1))
  local out err rc
  out=$(mktemp); err=$(mktemp)
  # HARNESS apunta al arnes real porque los canales hacen `. "$B/env"`; lo que se sustituye
  # es el MOTOR, no la configuracion.
  sh "$bin" "SELECT columna_que_no_existe FROM signal_outcome LIMIT 1" >"$out" 2>"$err"
  rc=$?
  local so se
  so=$(cat "$out"); se=$(cat "$err")
  rm -f "$out" "$err"

  local r1 r2 r3
  [ "$rc" != "0" ] && r1=ok || r1=FALLA
  [ -n "$se" ]     && r2=ok || r2=FALLA
  if printf '%s' "$so" | grep -q 'ERROR:'; then r3=FALLA; else r3=ok; fi

  printf '  %-10s rc=%-3s R1(rc!=0)=%-5s R2(mensaje llega)=%-5s R3(canales separados)=%s\n' \
    "$nombre" "$rc" "$r1" "$r2" "$r3"
  [ "$r1" = ok ] || fallos="$fallos $nombre:R1"
  [ "$r2" = ok ] || fallos="$fallos $nombre:R2"
  [ "$r3" = ok ] || fallos="$fallos $nombre:R3"
}

prueba espejosql "$REPO/harness/bin/espejosql"
prueba prodsql   "$REPO/harness/bin/prodsql"

# CERO CANALES PROBADOS NO ES CERO DEFECTOS.
[ "$n_probados" -eq 2 ] || { echo "NO MEDIDO: solo se probaron $n_probados canal(es) de 2"; exit 2; }

if [ -n "${fallos# }" ]; then
  n=$(printf '%s' "$fallos" | wc -w)
  echo "$n requisito(s) incumplidos, con un SQL que falla:$fallos"
  echo "  R1 rc!=0 · R2 el mensaje llega al llamante · R3 no viene mezclado con los datos"
  echo "  un canal que no puede decir que fallo apaga TODOS los guardias escritos contra el"
  exit 1
fi
echo "los 2 canales propagan el fallo del SQL: rc!=0, con mensaje, y sin mezclarlo con los datos"
exit 0
