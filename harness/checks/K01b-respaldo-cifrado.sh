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
# EL REGISTRO ES ESTADO COMPARTIDO: un OK escrito aqui pone VERDE a K01b para todo el mundo.
# `K01B_REG` existe SOLO para poder demostrar el comparador sin tocar el registro de verdad, y
# cuando se usa la salida lo DICE. Una prueba que escribe en el registro de todos desde una
# rama sin auditar es exactamente la puerta que este check no puede tener.
REG=${K01B_REG:-$B/estado/k01b.tsv}
MARCA_REG=""
[ -n "${K01B_REG:-}" ] && MARCA_REG=" [registro DESVIADO a $REG por K01B_REG, no es el compartido]"
DIAS_MAX=${K01B_DIAS_MAX:-8}
# La base local donde aterriza el respaldo. Se parametriza para que el CONTROL pueda montar
# escenarios pequenos -una particion vaciada, una que no cuadra- sin bajar 242 MB cada vez.
BASE=${K01B_BASE:-coinalyze_k01b}

if [ "${K01B_RESTAURA:-0}" = "1" ]; then
  # SALTAR LA RESTAURACION NO PUEDE ESCRIBIR EN EL REGISTRO DE TODOS. Sin descifrar ni
  # restaurar, esta corrida NO sabe si el respaldo restaura: solo ejercita el comparador. Que
  # pudiera dejar un OK compartido convertiria el mando de pruebas en una puerta para poner
  # VERDE a K01b sin respaldo ninguno.
  if [ "${K01B_SALTA_RESTAURA:-0}" = "1" ] && [ -z "${K01B_REG:-}" ]; then
    echo "NO MEDIDO: K01B_SALTA_RESTAURA solo se puede usar con K01B_REG apuntando a un" \
         "registro propio. Sin restaurar, esta corrida no sabe si el respaldo restaura y no" \
         "puede dejar un OK en el registro compartido."
    exit 2
  fi
  SP=$(mktemp -d /tmp/k01b.XXXXXX)
  trap 'rm -rf "$SP"' EXIT
  if [ "${K01B_SALTA_RESTAURA:-0}" = "1" ]; then
    fecha=${K01B_FECHA:-$(date -u +%Y%m%d)}
    rc=0
    MARCA_REG="$MARCA_REG [RESTAURACION SALTADA: se reusa la base $BASE, esta corrida NO prueba que el respaldo restaure]"
    echo "comparador sobre la base $BASE, sin restaurar"
  else
  SSH="ssh -n -o BatchMode=yes -o ConnectTimeout=8 -i $PROD_SSH_KEY -o UserKnownHostsFile=$PROD_KNOWN_HOSTS $PROD_SSH_USER@$PROD_HOST"
  enc=$($SSH "ls -1 /var/backups/coinalyze/coinalyze-full-*.tar.gz.enc | tail -1")
  [ -n "$enc" ] || { echo "NO MEDIDO: no hay ningun .enc en 140"; exit 2; }
  fecha=$(basename "$enc" | sed 's/coinalyze-full-\([0-9]\{8\}\)T.*/\1/')
  echo "probando $(basename "$enc")"
  $SSH "openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass file:/etc/coinalyze/backup.key -in $enc" \
    | tar xzf - -C "$SP" database/coinalyze.dump || { echo "NO MEDIDO: fallo el descifrado"; exit 2; }
  psql -X -q -d postgres -c "DROP DATABASE IF EXISTS $BASE" -c "CREATE DATABASE $BASE" >/dev/null 2>&1
  pg_restore --no-owner --no-privileges --jobs=2 -d "$BASE" "$SP/database/coinalyze.dump" >/dev/null 2>&1
  rc=$?
  fi
  # Particiones diarias YA CERRADAS (fecha anterior a la del respaldo) presentes en
  # LAS DOS. Se comparan todas las que haya, no una elegida a dedo.
  comunes=$(comm -12 \
    <(psql -X -A -t -d "$BASE" -c "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename ~ '_p[0-9]{8}\$' AND substring(tablename from '[0-9]{8}\$') < '$fecha' ORDER BY 1" 2>/dev/null | grep -E '^[a-z]' | sort) \
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
  # LO QUE LA RETENCION YA BORRO NO CONDENA AL RESPALDO. Medido el 2026-09-14 (COLA 123,
  # decision 2): la prueba dio FALLO sobre un respaldo que restaura bien, por DOS particiones
  # -futures_trades_realtime_p20260913 y liquidations_realtime_p20260913- que en 140 tenian CERO
  # filas porque la retencion de 12 h las habia vaciado esa manana. El defecto era de este
  # comparador: con 0 filas vivas `min(ts)` sale VACIO, el filtro del tramo vivo se apagaba solo
  # y se comparaba la PARTICION ENTERA -21693 filas contra 0-.
  #
  # Y no se arregla comparando igual: sobre una particion vacia en 140 el criterio
  # «el respaldo es SUPERCONJUNTO de lo que queda» se cumple SIEMPRE, asi que compararla no
  # dice nada ni a favor ni en contra. Se declara NO JUZGADA, CON SU NOMBRE, y no se cuenta.
  # Eso incluye el caso que antes «pasaba» por casualidad -orderbook_snapshot_p20260913, 0
  # filas en los dos lados-: dos vacios que coinciden no son una prueba de nada.
  fallos=""; probadas=0; vacias=""; sinvivas=0
  for t in $comunes; do
    col=$(psql -X -A -t -d "$BASE" -c "SELECT column_name FROM information_schema.columns WHERE table_name='$t' AND column_name='ts'" 2>/dev/null | grep -E '^ts$' | head -1)
    # CUANTAS FILAS TIENE 140 HOY. Es lo que decide si hay algo que comparar, y se pregunta
    # SIEMPRE -con columna ts o sin ella-: una particion sin `ts` y vacia tenia el mismo
    # agujero por otro camino, porque su filtro tambien quedaba en nada.
    vivas=$("$B/bin/prodsql" "SELECT count(*) FROM $t" 2>/dev/null | grep -E '^[0-9]+$' | head -1)
    if [ -z "$vivas" ]; then
      vacias="$vacias $t(140 no contesto)"; sinvivas=$((sinvivas+1)); continue
    fi
    if [ "$vivas" -eq 0 ]; then
      vacias="$vacias $t(0 filas vivas en 140: la retencion la vacio)"; sinvivas=$((sinvivas+1)); continue
    fi
    if [ -n "$col" ]; then
      desde=$("$B/bin/prodsql" "SELECT min(ts)::text FROM $t" 2>/dev/null | grep -E '^[0-9]{4}-' | head -1)
      if [ -z "$desde" ]; then
        vacias="$vacias $t($vivas filas en 140 pero sin min(ts) legible)"; sinvivas=$((sinvivas+1)); continue
      fi
      filtro="WHERE ts >= '$desde'"
    else
      filtro=""
    fi
    # SET timezone='UTC' EN LOS DOS LADOS, junto al extra_float_digits. Sin el, este lado
    # hereda el timezone del SERVIDOR de 143 -America/Mexico_City- mientras prodsql fuerza
    # UTC desde K77, y md5(x::text) sobre filas con timestamptz da hashes distintos PARA LA
    # MISMA FILA. Eso es lo que hacia FALLAR a scalp_signal_snapshot_p20260831 y _p20260901
    # sin que hubiera nada roto. Medido: SELECT md5(now()::timestamptz::text) da
    # 52043ad7a8f53acff983b1b50bc8cd39 en America/Mexico_City y 83d0a377e7f763b94950e0f82e7be523
    # en UTC. Un comparador que depende de la zona de la sesion no compara datos, compara sesiones.
    a=$(psql -X -A -t -d "$BASE" -c "SET timezone='UTC'" -c "SET extra_float_digits=0" -c "SELECT count(*)||':'||coalesce(md5(string_agg(x::text,E'\n' ORDER BY x::text)),'vacia') FROM $t x $filtro" 2>/dev/null | grep -E '^[0-9]' | head -1)
    b=$("$B/bin/prodsql" "SET timezone='UTC'; SET extra_float_digits=0; SELECT count(*)||':'||coalesce(md5(string_agg(x::text,E'\n' ORDER BY x::text)),'vacia') FROM $t x $filtro" 2>/dev/null | grep -E '^[0-9]' | head -1)
    probadas=$((probadas+1))
    [ -n "$a" ] && [ "$a" = "$b" ] || fallos="$fallos $t($a vs $b)"
  done
  COLA_V=""
  [ -n "${vacias// /}" ] && COLA_V=" · $sinvivas NO JUZGADA(S), con su nombre y su motivo:$vacias"

  # UNA PRUEBA QUE NO COMPARO NADA NO ES UN OK. Si ninguna particion tenia dato vivo, este
  # brazo no ha ejercitado el respaldo: escribir OK ahi pondria VERDE a K01b durante ocho dias
  # citando una prueba que no probo nada, que es peor que no tenerla. NO se escribe en el
  # registro -ni OK ni FALLO-: no hay hecho sobre el respaldo que registrar.
  if [ "$probadas" -eq 0 ]; then
    echo "NO MEDIDO: pg_restore rc=$rc, pero CERO particiones tenian dato vivo con el que" \
         "comparar, asi que esta prueba no ha ejercitado el respaldo y no puede decir ni que" \
         "vale ni que no. No se escribe en el registro.$COLA_V$MARCA_REG"
    exit 2
  fi
  if [ "$rc" -eq 0 ] && [ -z "${fallos// /}" ]; then
    printf '%s\tOK\t%s\t%d particiones CON DATO cuadran fila a fila%s\n' "$(date -u +%FT%TZ)" "$fecha" "$probadas" "$COLA_V" >> "$REG"
    echo "OK: $probadas particiones cerradas CON DATO VIVO cuadran fila a fila con 140$COLA_V$MARCA_REG"
  else
    printf '%s\tFALLO\t%s\trc=%d%s%s\n' "$(date -u +%FT%TZ)" "$fecha" "$rc" "$fallos" "$COLA_V" >> "$REG"
    echo "FALLO: rc=$rc$fallos · sobre $probadas particiones CON DATO$COLA_V$MARCA_REG"
  fi
fi

[ -s "$REG" ] || { echo "nunca se ha restaurado un .enc: lanza K01B_RESTAURA=1 $0"; exit 1; }
# EL VEREDICTO SALE DE LA ULTIMA LINEA, NO DEL ULTIMO OK. Antes se grepeaban solo los OK,
# asi que un OK ANTIGUO tapaba un FALLO RECIENTE y el check publicaba "restaurado y cuadrado"
# citando una prueba vieja mientras la ultima habia fallado. Una prueba de respaldo que
# ignora su propio fallo mas reciente es peor que no tenerla: afirma justo lo que no sabe.
reciente=$(tail -1 "$REG")
case "$reciente" in
  *"$(printf '\t')FALLO$(printf '\t')"*)
    echo "la prueba de restauracion MAS RECIENTE fallo: $reciente"; exit 1 ;;
esac
ultima=$(grep -P '\tOK\t' "$REG" | tail -1)
[ -n "$ultima" ] || { echo "la ultima prueba de restauracion FALLO: $(tail -1 "$REG")"; exit 1; }
probado=$(printf '%s' "$ultima" | cut -f3)
edad=$(( ( $(date -u +%s) - $(date -u -d "$probado" +%s) ) / 86400 ))
[ "$edad" -le "$DIAS_MAX" ] || {
  echo "el ultimo .enc probado es del $probado, hace $edad dias (limite $DIAS_MAX)"; exit 1; }
echo "respaldo cifrado del $probado restaurado y cuadrado contra 140 hace $edad dias"
