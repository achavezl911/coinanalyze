#!/bin/bash
# K01b  el respaldo CIFRADO diario tiene que restaurar de verdad, y lo restaurado
# tiene que cuadrar contra 140. Es lo unico irreversible de la cola: si esto no vale,
# no hay vuelta atras de nada.
#
# La prueba de verdad tarda ~2 min (descifrar 242 MB + pg_restore de 224 MB), asi que
# NO se corre en cada verify. Se corre a mano con K01B_RESTAURA=1 y deja el resultado
# en estado/k01b.tsv; el check normal solo mira ese registro y ROJEA si el respaldo
# probado es viejo. Asi un respaldo que deje de producirse, o que deje de restaurar,
# enrojece solo aunque nadie vuelva a lanzar la prueba.
#
# La clave NO sale de 140: se descifra en streaming por ssh y solo viaja el texto
# claro hacia 143. Antes esto era PUERTA 2; dejo de serlo cuando el canal paso a root.
#
# La referencia NO puede ser el propio respaldo -un volcado truncado tambien restaura
# y tambien cuenta-, asi que se compara md5 fila a fila de las particiones diarias YA
# CERRADAS contra las mismas particiones en 140. Todas las que haya en comun, no una
# elegida a dedo: la primera vez que corrio, la elegida a mano cuadraba y la de al
# lado no.
set -uo pipefail
B=/srv/coinanalyze/harness; . "$B/env"
REG="$B/estado/k01b.tsv"
DIAS_MAX=${K01B_DIAS_MAX:-8}

if [ "${K01B_RESTAURA:-0}" = "1" ]; then
  SP=$(mktemp -d /tmp/k01b.XXXXXX)
  trap 'rm -rf "$SP"' EXIT
  SSH="ssh -n -o BatchMode=yes -o ConnectTimeout=8 -i $PROD_SSH_KEY -o UserKnownHostsFile=$PROD_KNOWN_HOSTS $PROD_SSH_USER@$PROD_HOST"
  enc=$($SSH "ls -1 /var/backups/coinalyze/coinalyze-full-*.tar.gz.enc | tail -1")
  [ -n "$enc" ] || { echo "NO MEDIDO: no hay ningun .enc en 140"; exit 2; }
  fecha=$(basename "$enc" | sed 's/coinalyze-full-\([0-9]\{8\}\)T.*/\1/')
  echo "probando $(basename "$enc")"
  $SSH "openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass file:/etc/coinalyze/backup.key -in $enc" \
    | tar xzf - -C "$SP" database/coinalyze.dump || { echo "NO MEDIDO: fallo el descifrado"; exit 2; }
  psql -X -q -d postgres -c "DROP DATABASE IF EXISTS coinalyze_k01b" -c "CREATE DATABASE coinalyze_k01b" >/dev/null 2>&1
  pg_restore --no-owner --no-privileges --jobs=2 -d coinalyze_k01b "$SP/database/coinalyze.dump" >/dev/null 2>&1
  rc=$?
  # Particiones diarias YA CERRADAS (fecha anterior a la del respaldo) presentes en
  # LAS DOS. Se comparan todas las que haya, no una elegida a dedo.
  comunes=$(comm -12 \
    <(psql -X -A -t -d coinalyze_k01b -c "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename ~ '_p[0-9]{8}\$' AND substring(tablename from '[0-9]{8}\$') < '$fecha' ORDER BY 1" 2>/dev/null | grep -E '^[a-z]' | sort) \
    <("$B/bin/prodsql" "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename ~ '_p[0-9]{8}\$' AND substring(tablename from '[0-9]{8}\$') < '$fecha' ORDER BY 1" 2>/dev/null | grep -E '^[a-z]' | sort))
  [ -n "$comunes" ] || { echo "NO MEDIDO: ninguna particion cerrada en comun con 140"; exit 2; }
  # Se compara SOLO el tramo que SIGUE VIVO en 140, no la particion entera. Motivo
  # medido el 2026-08-25: scalp_signal_snapshot_p20260822 tenia 6456 filas en el
  # respaldo y 5472 en 140, y no era un respaldo malo: la retencion habia borrado el
  # prefijo MAS VIEJO despues de hacerlo (min(ts) 18:00 en el respaldo, 21:41 en
  # 140; el max(ts) identico al microsegundo). Un respaldo tiene que ser un
  # SUPERCONJUNTO de lo que hoy queda; exigir igualdad exacta convierte la retencion
  # normal en un falso rojo. El tramo vivo si tiene que cuadrar byte a byte, y eso
  # sigue cazando un respaldo truncado: si a 140 le sobran filas ahi, no cuadra.
  fallos=""; probadas=0
  for t in $comunes; do
    col=$(psql -X -A -t -d coinalyze_k01b -c "SELECT column_name FROM information_schema.columns WHERE table_name='$t' AND column_name='ts'" 2>/dev/null | grep -E '^ts$' | head -1)
    if [ -n "$col" ]; then
      desde=$("$B/bin/prodsql" "SELECT min(ts)::text FROM $t" 2>/dev/null | grep -E '^[0-9]{4}-' | head -1)
      [ -n "$desde" ] && filtro="WHERE ts >= '$desde'" || filtro=""
    else
      filtro=""
    fi
    a=$(psql -X -A -t -d coinalyze_k01b -c "SET extra_float_digits=0" -c "SELECT count(*)||':'||coalesce(md5(string_agg(x::text,E'\n' ORDER BY x::text)),'vacia') FROM $t x $filtro" 2>/dev/null | grep -E '^[0-9]' | head -1)
    b=$("$B/bin/prodsql" "SET extra_float_digits=0; SELECT count(*)||':'||coalesce(md5(string_agg(x::text,E'\n' ORDER BY x::text)),'vacia') FROM $t x $filtro" 2>/dev/null | grep -E '^[0-9]' | head -1)
    probadas=$((probadas+1))
    [ -n "$a" ] && [ "$a" = "$b" ] || fallos="$fallos $t($a vs $b)"
  done
  if [ "$rc" -eq 0 ] && [ -z "${fallos// /}" ]; then
    printf '%s\tOK\t%s\t%d particiones cuadran fila a fila\n' "$(date -u +%FT%TZ)" "$fecha" "$probadas" >> "$REG"
    echo "OK: $probadas particiones cerradas cuadran fila a fila con 140"
  else
    printf '%s\tFALLO\t%s\trc=%d%s\n' "$(date -u +%FT%TZ)" "$fecha" "$rc" "$fallos" >> "$REG"
    echo "FALLO: rc=$rc$fallos"
  fi
fi

[ -s "$REG" ] || { echo "nunca se ha restaurado un .enc: lanza K01B_RESTAURA=1 $0"; exit 1; }
ultima=$(grep -P '\tOK\t' "$REG" | tail -1)
[ -n "$ultima" ] || { echo "la ultima prueba de restauracion FALLO: $(tail -1 "$REG")"; exit 1; }
probado=$(printf '%s' "$ultima" | cut -f3)
edad=$(( ( $(date -u +%s) - $(date -u -d "$probado" +%s) ) / 86400 ))
[ "$edad" -le "$DIAS_MAX" ] || {
  echo "el ultimo .enc probado es del $probado, hace $edad dias (limite $DIAS_MAX)"; exit 1; }
echo "respaldo cifrado del $probado restaurado y cuadrado contra 140 hace $edad dias"
