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
# EL SUJETO ES EL ARBOL: harness/bin/espejosql, harness/bin/prodsql y -desde el 2026-09-07-
# harness/bin/api. Este check existia para que un canal no fallara en silencio y **no miraba
# al tercero**: medido por el operador, `api /api/no-existe-esta-ruta` daba rc=0 con 22 B de
# `{"detail":"Not Found"}`, o sea el error disfrazado de dato. 16 checks leen por ahi.
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
# EL TERCER CANAL TIENE OTRO MOTOR. `bin/api` no habla SQL: habla HTTP, y su motor es `curl`.
# Por eso el brazo de arriba NO LE SIRVE -no se le puede pasar un SELECT- y necesita su propio
# elegible. Se monta un `curl` de mentira que respeta `-o fichero` y `-w %{http_code}` como el de
# verdad, y que se controla con dos variables:
#     K94C_CODIGO  el codigo HTTP que devuelve      (404 para el negativo, 200 para el positivo)
#     K94C_CUERPO  lo que escribe en el fichero de -o
# ES IMPORTANTE QUE EL FALSO SALGA CON rc=0 TAMBIEN EN EL 404: es justo lo que hace curl de
# verdad -para el, entregar la respuesta de error ES un exito- y es la mitad del defecto que este
# brazo existe para vigilar. Un `curl` de mentira que saliera !=0 probaria el otro defecto, el
# del pipe, y dejaria este sin probar.
# Y ES FIEL A LAS DOS INTERFACES: **sin** `-o` escribe el cuerpo en stdout, que es lo que hacia
# la version anterior de `bin/api`. La primera version de este doble solo servia a la nueva, y
# entonces el `api` viejo recibia el CODIGO donde esperaba el CUERPO: el contraste seguia
# saliendo, pero por el motivo equivocado. Un doble infiel es un falso positivo esperando.
{
  printf '#!/bin/sh\n'
  printf 'destino=""\n'
  printf 'while [ $# -gt 0 ]; do\n'
  printf '  case "$1" in -o) destino=$2; shift 2 ;; *) shift ;; esac\n'
  printf 'done\n'
  printf 'if [ -n "$destino" ]; then\n'
  printf '  printf "%%s" "${K94C_CUERPO:-}" > "$destino"\n'
  printf '  printf "%%s" "${K94C_CODIGO:-200}"\n'
  printf 'else\n'
  printf '  printf "%%s" "${K94C_CUERPO:-}"\n'
  printf 'fi\n'
  printf 'exit 0\n'
} > "$DIR/bin/curl"
chmod +x "$DIR/bin/curl"

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

prueba_api() {  # <ruta de bin/api>
  local bin="$1"
  [ -r "$bin" ] || { echo "NO MEDIDO: no encuentro $bin"; exit 2; }
  local out err rc so se

  # R4 · EL POSITIVO, Y VA PRIMERO. Un canal que dijera que TODO falla estaria tan roto como el
  # que no decia nada, y ademas haria pasar a R1-R3 sin haber probado nada: si `api` saliera !=0
  # por cualquier motivo -un netrc que falta, un env mal cargado- los tres brazos de abajo darian
  # ok en falso. Asi que si el positivo no pasa, esto es NO MEDIDO y no un aprobado.
  out=$(mktemp); err=$(mktemp)
  K94C_CODIGO=200 K94C_CUERPO='{"status":"ok"}' sh "$bin" /api/healthz >"$out" 2>"$err"
  rc=$?
  so=$(cat "$out"); se=$(cat "$err"); rm -f "$out" "$err"
  if [ "$rc" != 0 ] || [ -z "$so" ]; then
    echo "NO MEDIDO: con una respuesta 200 el canal api sale rc=$rc y stdout de $(printf '%s' "$so" | wc -c) B."
    echo "  sin ese positivo, los tres requisitos de abajo pasarian sin haber probado nada."
    exit 2
  fi
  n_probados=$((n_probados+1))
  printf '  %-10s R4(el 200 pasa entero)=ok  stdout=%s B\n' api "$(printf '%s' "$so" | wc -c)"

  # R1-R3 · y ahora el negativo: la capa de arriba dice que no.
  out=$(mktemp); err=$(mktemp)
  K94C_CODIGO=404 K94C_CUERPO='{"detail":"Not Found"}' sh "$bin" /api/no-existe-esta-ruta >"$out" 2>"$err"
  rc=$?
  so=$(cat "$out"); se=$(cat "$err"); rm -f "$out" "$err"
  local r1 r2 r3
  [ "$rc" != "0" ] && r1=ok || r1=FALLA
  [ -n "$se" ]     && r2=ok || r2=FALLA
  # R3 para este canal: el CUERPO DEL ERROR no puede salir por stdout, porque ahi es
  # indistinguible de un dato. Es la misma exigencia que a los otros dos, con el error de HTTP
  # en vez del de psql.
  if printf '%s' "$so" | grep -q 'Not Found'; then r3=FALLA; else r3=ok; fi
  printf '  %-10s rc=%-3s R1(rc!=0)=%-5s R2(mensaje llega)=%-5s R3(canales separados)=%s\n' \
    api "$rc" "$r1" "$r2" "$r3"
  [ "$r1" = ok ] || fallos="$fallos api:R1"
  [ "$r2" = ok ] || fallos="$fallos api:R2"
  [ "$r3" = ok ] || fallos="$fallos api:R3"
}

prueba espejosql "$REPO/harness/bin/espejosql"
prueba prodsql   "$REPO/harness/bin/prodsql"
prueba_api       "$REPO/harness/bin/api"

# CERO CANALES PROBADOS NO ES CERO DEFECTOS.
[ "$n_probados" -eq 3 ] || { echo "NO MEDIDO: solo se probaron $n_probados canal(es) de 3"; exit 2; }

if [ -n "${fallos# }" ]; then
  n=$(printf '%s' "$fallos" | wc -w)
  echo "$n requisito(s) incumplidos, con una pregunta que falla:$fallos"
  echo "  R1 rc!=0 · R2 el mensaje llega al llamante · R3 no viene mezclado con los datos"
  echo "  un canal que no puede decir que fallo apaga TODOS los guardias escritos contra el"
  exit 1
fi
echo "los 3 canales propagan el fallo -SQL en dos, HTTP en api-: rc!=0, con mensaje, y sin mezclarlo con los datos"
exit 0
