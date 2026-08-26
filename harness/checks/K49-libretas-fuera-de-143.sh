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

git ls-remote --exit-code "$DESTINO" HEAD >/dev/null 2>&1 || {
  echo "las cuatro libretas siguen SOLO en el rootfs de 143: $DESTINO no responde o no existe"; exit 1; }

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

# LA PRUEBA. hechos.tsv recuperado contra hechos.tsv vivo, byte a byte.
sha_vivo=$(sha256sum "${VIVAS[hechos.tsv]}" | cut -d' ' -f1)
sha_copia=$(sha256sum "$TMP/copia/hechos.tsv" | cut -d' ' -f1)
if [ "$sha_vivo" != "$sha_copia" ]; then
  bytes_v=$(wc -c < "${VIVAS[hechos.tsv]}"); bytes_c=$(wc -c < "$TMP/copia/hechos.tsv")
  echo "hechos.tsv restaurado NO cuadra con el vivo: copia ${sha_copia:0:12} ($bytes_c B) vs vivo ${sha_vivo:0:12} ($bytes_v B), copia de hace $horas h"
  exit 1
fi

total=$(( $(wc -c < "${VIVAS[hechos.tsv]}") + $(wc -c < "${VIVAS[COLA.md]}") \
        + $(wc -c < "${VIVAS[ESTADO.md]}") + $(wc -c < "${VIVAS[CAMBIOS.md]}") ))
echo "las 4 libretas ($total B) estan fuera de 143, copia de hace ${horas} h, y hechos.tsv RESTAURADO cuadra con el vivo: sha256 ${sha_vivo:0:12}"
