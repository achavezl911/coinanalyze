#!/usr/bin/env bash
# K100 · EL ROOT QUE DESPLIEGA, Y QUE NADIE VIGILA
#
# SUJETO   `/usr/local/sbin/deploy-coinalyze` en 140, comparado con `deploy/140/deploy-coinalyze`
#          de este repo.
# VERDE    los dos lados coinciden BYTE A BYTE.
# ROJO     difieren, se haya movido el de 140 o el del repo.
# NOMED    140 no contesto, o falta la copia del repo. NUNCA VERDE por no poder mirar.
#
# POR QUE EXISTE. El despliegue a 140 no lo hace el repo: lo hace
# `/usr/local/sbin/deploy-coinalyze`, root:root 0750, FUERA del arbol (docs/DEPLOYMENT.md:51).
# Es el UNICO root que ejecuta el deploy -valida el sha256 del artefacto, extrae el release,
# construye el venv, respalda la base y mueve `current`-, y hasta el 2026-09-16 NINGUN check
# miraba si cambiaba. K93 mide el CAMINO DE ACTUALIZACION DEL ESQUEMA, que es otra cosa: un
# cambio en el wrapper -a mano, por error o por un tercero con root- no lo veia nadie.
#
# EL ELEGIBLE SE DERIVA, NO SE TECLEA UNA HUELLA. En el repo vive el FICHERO, no su md5: con
# una huella escrita a mano nadie puede auditar QUE cambio, solo QUE cambio algo, y ademas la
# huella se copia mal una vez y miente para siempre -es la enfermedad de K18 con sus ventanas-.
# Con el fichero, un ROJO trae un `diff` que se lee.
#
# NO LLEVA SECRETOS, Y ESO SE MIDIO ANTES DE COPIARLO. Medido el 2026-09-16 sobre las 504 lineas
# del wrapper: CERO asignaciones con valor literal que huelan a credencial y CERO blobs de alta
# entropia. Lo que parece secreto son REFERENCIAS: `PGPASSWORD="${PG_PASSWORD:-}"` en cuatro
# sitios y un token que LEE de `/etc/coinalyze/coinalyze.env` (linea 22 del wrapper). Ese fichero
# es de 140 y NO viaja aqui. Si algun dia el wrapper llevara un secreto dentro, la copia NO se
# actualiza: se declara cual y este check pasa a NO MEDIDO, porque un repo publico no es sitio.
#
# SE LEE POR EL CANAL SANCIONADO (`bin/prod`, solo verbos de lectura). No hay un segundo camino
# a 140 ni hace falta.
#
# LA PUERTA DE INYECCION VA MARCADA. `K100_REMOTO` sustituye lo que 140 devuelve, para que el
# control pueda plantar una huella distinta sin tocar 140. Cuando se usa, la linea lo DICE: es
# exactamente la puerta por la que se forzaria un VERDE.
#
# CONTROL: harness/checks/K100-control.bash.
set -uo pipefail
_REPO_LLAMANTE=${REPO:-}
B=/srv/coinanalyze/harness
[ -r "$B/env" ] && . "$B/env"
REPO=${_REPO_LLAMANTE:-${REPO:-/srv/coinanalyze/repo}}

LOCAL="${K100_LOCAL:-$REPO/deploy/140/deploy-coinalyze}"
RUTA_140=${K100_RUTA:-/usr/local/sbin/deploy-coinalyze}
MARCA=""

if [ ! -r "$LOCAL" ]; then
  echo "NO MEDIDO: no encuentro la copia del repo en $LOCAL. Sin el elegible no hay con que" \
       "comparar, y dar VERDE seria decir que coincide con nada."
  exit 2
fi

if [ -n "${K100_REMOTO:-}" ]; then
  [ -r "$K100_REMOTO" ] || { echo "NO MEDIDO: K100_REMOTO apunta a un fichero que no existe"; exit 2; }
  remoto=$(cat "$K100_REMOTO"); rc=0
  MARCA=" [REMOTO INYECTADO por K100_REMOTO, no leido de 140]"
else
  # `TODO=1` NO ES INERCIA, Y AQUI HAY QUE DECIR POR QUE: `bin/_corta` trunca en MAX_BYTES
  # -8000 por omision- y el wrapper son 13 940 B. Sin esto el check comparaba las 293 primeras
  # lineas contra las 504 del repo y salia ROJO SIEMPRE, por el canal y no por el sujeto. Lo
  # canto el propio check en su primera corrida.
  remoto=$(TODO=1 "$B/bin/prod" "cat $RUTA_140" 2>/dev/null); rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "NO MEDIDO: 140 no contesto (bin/prod rc=$rc) pidiendo $RUTA_140. Esta linea NO dice" \
         "nada sobre el wrapper: ni que coincida ni que no."
    exit 2
  fi
fi

if [ -z "${remoto//[$' \t\n']/}" ]; then
  echo "NO MEDIDO: 140 contesto VACIO para $RUTA_140. Un fichero vacio y un canal mudo se" \
       "parecen demasiado como para llamar a esto una medida.$MARCA"
  exit 2
fi

h_local=$(md5sum "$LOCAL" | cut -d' ' -f1)
h_remoto=$(printf '%s\n' "$remoto" | md5sum | cut -d' ' -f1)
n_local=$(wc -l < "$LOCAL")
n_remoto=$(printf '%s\n' "$remoto" | wc -l)

if [ "$h_local" != "$h_remoto" ]; then
  tmp=$(mktemp); printf '%s\n' "$remoto" > "$tmp"
  # QUE cambio, no solo QUE cambio algo: las primeras lineas del diff van en la linea del rojo.
  d=$(diff -u "$LOCAL" "$tmp" 2>/dev/null | sed -n '3,8p' | tr '\n' ' ' | cut -c1-320)
  rm -f "$tmp"
  echo "ROJO: el wrapper de 140 y la copia del repo NO coinciden. 140 $RUTA_140: $n_remoto" \
       "lineas, md5 $h_remoto · repo ${LOCAL#$REPO/}: $n_local lineas, md5 $h_local." \
       "Se movio UNO DE LOS DOS y este check no sabe cual: el diff lo dice -> $d$MARCA"
  exit 1
fi

echo "el root que despliega es el que el repo dice: $RUTA_140 en 140 y ${LOCAL#$REPO/}" \
     "coinciden byte a byte ($n_local lineas, md5 $h_local), leido por bin/prod. El elegible es" \
     "el FICHERO y no una huella escrita a mano, asi que un rojo trae su diff$MARCA"
exit 0
