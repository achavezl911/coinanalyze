#!/bin/bash
# K49  las cuatro libretas -hechos.tsv, COLA.md, CAMBIOS.md, ESTADO.md- son 368.8 KB de
# CRITERIO acumulado en seis semanas y vivian en un solo sitio: el rootfs de 143.
#
# LO QUE ESTE CHECK NO ACEPTA COMO RESPALDO
# Los 24 .bak de harness/ estan en el MISMO rootfs: protegen de una edicion mala, no de
# perder el contenedor. Y el respaldo que corre en 140 escribe en /var/backups/coinalyze,
# o sea el rootfs de 140, que esta en el MISMO nodo Proxmox que 143: no sirve para el
# fallo que importa. Copia y respaldo no son lo mismo, que es la leccion entera de K01b.
#
# POR QUE NO BASTA CON QUE EL FICHERO EXISTA
# Un fichero de 0 bytes en el destino tambien "existe", y un push truncado tambien deja
# un commit. Se exige PRUEBA DE RESTAURACION: se clona el destino de verdad, se recupera
# hechos.tsv y su sha256 tiene que cuadrar con el vivo. Sin eso es un fichero, no un
# respaldo.
#
# LO QUE NO SE GUARDA, y es deliberado: harness/secretos/. Son 1605 bytes REGENERABLES
# -el nodo Proxmox entra a 140 sin la clave- y lo irrecuperable no son las llaves, es el
# criterio. harness/env si va: su primera linea dice que ahi no vive ningun secreto.
set -uo pipefail
B=/srv/coinanalyze/harness; . "$B/env"
DESTINO=${LIBRETAS_REMOTO:-https://github.com/achavezl911/coinanalyze-libretas.git}
MAX_HORAS=24

declare -A VIVAS=(
  [hechos.tsv]=/srv/coinanalyze/harness/hechos.tsv
  [COLA.md]=/srv/coinanalyze/harness/COLA.md
  [ESTADO.md]=/srv/coinanalyze/harness/ESTADO.md
  [CAMBIOS.md]=/srv/coinanalyze/CAMBIOS.md
)

for f in "${!VIVAS[@]}"; do
  [ -r "${VIVAS[$f]}" ] || { echo "NO MEDIDO: no se puede leer la libreta viva ${VIVAS[$f]}"; exit 2; }
done

# TRES ESTADOS, NO UNO. La version anterior metia "no existe", "existe pero vacio" y "no
# se pudo alcanzar" en el mismo saco y afirmaba ROJO para los tres: dio VERDE, ROJO y
# VERDE otra vez en minutos, y ese ROJO decia "siguen SOLO en el rootfs de 143" cuando el
# remoto ya tenia las cuatro libretas dentro. Era falso. Es la misma forma que K19 y K07
# -leer sin filtrar por estado- y aqui pesa mas, porque K49 vigila lo unico que si se
# pierde no se recupera, y un check que enrojece segun el momento acaba tratandose como
# ruido. GIT_TERMINAL_PROMPT=0 y timeout para que un remoto colgado falle rapido en vez
# de quedarse esperando una credencial que nadie va a teclear.
ls_salida=$(GIT_TERMINAL_PROMPT=0 timeout 30 git ls-remote --exit-code "$DESTINO" HEAD 2>&1)
ls_rc=$?
case $ls_rc in
  0) : ;;                                   # alcanzable y con refs: se sigue midiendo
  2) echo "el destino existe pero esta VACIO: $DESTINO no tiene ni una ref, las libretas siguen solo en 143"; exit 1 ;;
  *)
    # Alcanzar el remoto y que conteste "no" es una respuesta y se afirma. No alcanzarlo
    # no es una respuesta: eso es NO MEDIDO, y el mensaje lleva lo que dijo git para que
    # se distinga de un vistazo si se perdio el repo o solo el acceso.
    if printf '%s' "$ls_salida" | grep -qiE 'not found|does not exist|access denied|permission denied|403'; then
      echo "el remoto contesta y NIEGA el destino ($DESTINO): $(printf '%s' "$ls_salida" | tr '\n' ' ' | cut -c1-120)"; exit 1
    fi
    echo "NO MEDIDO: no se pudo alcanzar $DESTINO (rc=$ls_rc): $(printf '%s' "$ls_salida" | tr '\n' ' ' | cut -c1-120)"; exit 2 ;;
esac

# Restauracion de verdad: se clona a un directorio nuevo. Si el destino esta vacio,
# truncado o sin alguna libreta, se ve aqui y no cuando haga falta.
TMP=$(mktemp -d /tmp/k49-restaura.XXXXXX) || { echo "NO MEDIDO: no se pudo crear el directorio de restauracion"; exit 2; }
trap 'rm -rf "$TMP"' EXIT
git clone --quiet --depth 1 "$DESTINO" "$TMP/copia" 2>/dev/null || {
  echo "NO MEDIDO: $DESTINO responde pero no se pudo clonar"; exit 2; }

faltan=""
for f in "${!VIVAS[@]}"; do
  [ -s "$TMP/copia/$f" ] || faltan="$faltan $f"
done
[ -z "$faltan" ] || { echo "la copia existe pero no trae (o trae vacias):$faltan"; exit 1; }

# Fecha del respaldo: la del ULTIMO COMMIT del destino, no la mtime del clon, que es de
# hace un segundo y diria que siempre esta fresco.
commit_epoch=$(git -C "$TMP/copia" log -1 --format=%ct 2>/dev/null)
[ -n "$commit_epoch" ] || { echo "NO MEDIDO: la copia no trae fecha de commit"; exit 2; }
horas=$(( ( $(date +%s) - commit_epoch ) / 3600 ))
[ "$horas" -le "$MAX_HORAS" ] || {
  echo "la copia de las libretas tiene $horas h, por encima del techo de $MAX_HORAS h: el respaldo dejo de correr"; exit 1; }

# LA PRUEBA DE RESTAURACION. Lo recuperado del remoto contra el manifiesto que viajo en
# el MISMO commit: eso demuestra el viaje de ida y vuelta -que nada se trunco ni se
# corrompio- y no depende del instante en que se mire.
#
# NO se compara contra el fichero vivo, y es deliberado: se probo, y sale ROJO cada vez
# que alguien anade un hecho a hechos.tsv entre dos ticks del timer, con el mensaje "no
# cuadra con el vivo", que se lee como corrupcion cuando lo unico que pasa es que la
# copia va minutos por detras. Lo que acota ese retraso es el techo de $MAX_HORAS de
# arriba, no una comparacion que enrojece por el reloj. El desfase se MIDE y se dice en
# la linea de VERDE, para que se vea en vez de esconderse.
[ -s "$TMP/copia/SHA256SUMS" ] || { echo "la copia no trae manifiesto: sin el, restaurar no se puede demostrar"; exit 1; }
if ! ( cd "$TMP/copia" && sha256sum --quiet -c SHA256SUMS >/dev/null 2>&1 ); then
  malas=$( cd "$TMP/copia" && sha256sum -c SHA256SUMS 2>/dev/null | grep -v ': OK$' | cut -d: -f1 | tr '\n' ' ')
  echo "lo restaurado del remoto NO cuadra con su propio manifiesto: $malas (copia de hace $horas h)"; exit 1
fi

sha_vivo=$(sha256sum "${VIVAS[hechos.tsv]}" | cut -d' ' -f1)
sha_copia=$(sha256sum "$TMP/copia/hechos.tsv" | cut -d' ' -f1)
if [ "$sha_vivo" = "$sha_copia" ]; then
  desfase="hechos.tsv identico al vivo"
else
  desfase="hechos.tsv $(( $(wc -c < "${VIVAS[hechos.tsv]}") - $(wc -c < "$TMP/copia/hechos.tsv") )) B por detras del vivo, dentro del techo de ${MAX_HORAS} h"
fi

total=$(( $(wc -c < "${VIVAS[hechos.tsv]}") + $(wc -c < "${VIVAS[COLA.md]}") \
        + $(wc -c < "${VIVAS[ESTADO.md]}") + $(wc -c < "${VIVAS[CAMBIOS.md]}") ))
echo "las 4 libretas ($total B) estan fuera de 143, copia de hace ${horas} h, RESTAURADA y cuadrada contra su manifiesto (6 ficheros); $desfase"
