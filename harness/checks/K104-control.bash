#!/bin/bash
# K104-control · ¿ve la red que un dia cerrado encogio, y SOLO cuando encogio de verdad?
#
#     bash harness/checks/K104-control.bash
#
# LA VARIABLE QUE DECIDE (A57) son DOS, y cada brazo mueve una sola:
#   1 · que el dia tenga HOY menos filas que la marca de agua
#   2 · DONDE cae el dia respecto del borde de la retencion declarada
# El tamano, el nombre de la tabla y la cantidad de filas no deciden nada, y por eso el
# plantado y su gemelo son la MISMA base con la MISMA siembra.
#
# EL BRAZO QUE IMPORTA ES EL DEL BORDE (A68). La misma perdida, de las mismas filas, tiene
# que CONDENAR si el dia cabe entero en la ventana y NO condenar si la ventana ya lo dejo
# fuera -ahi encoger es el oficio de la poda-. Los dos sujetos se diferencian SOLO en el
# numero declarado de retencion, que es justo la variable 2. Un control que plantara la
# perdida siempre en mitad de la ventana no veria nada de esto: es el error exacto de A68.
#
# Y UN CONTROL DE RESPUESTA CONOCIDA CON LAS FILAS DE VERDAD: las 38 que produccion perdio
# el 09-16 (17 observaciones + 21 instantaneas, todas del 08-29) estan en
# /root/banco-129/repara-PRODUCCION.sql. Puestas en una copia y quitadas despues, la red tiene
# que decir -17 y -21 del 08-29 y NADA mas. Si ese material no esta en la maquina, el brazo
# sale SIN MATERIAL con su nombre: no cuenta como que paso.
#
# NO LLEVA .sh A PROPOSITO: bin/verify globea checks/*.sh.
set -uo pipefail
ORIG=${REPO:-/srv/coinanalyze/repo}
CHK="$ORIG/harness/checks/K104-el-dia-cerrado-que-encoge.sh"
DECL="$ORIG/harness/checks/K104-tablas.tsv"
[ -r "$CHK" ] || { echo "NO MEDIDO: no encuentro el check en $CHK"; exit 2; }
[ -r "$DECL" ] || { echo "NO MEDIDO: no encuentro las declaraciones en $DECL"; exit 2; }
command -v psql >/dev/null || { echo "NO MEDIDO: no hay psql en esta maquina"; exit 2; }

BD="k104_ctl_$$"
BK="k104_ctl_banco_$$"
BG="k104_ctl_grande_$$"
DIR=$(mktemp -d) || exit 2
# WITH (FORCE) y COMPROBAR DESPUES: una limpieza que falla callada deja bases por el disco de
# 143 y nadie se entera. Al control de K103 le paso -catorce bases abandonadas, 108 MB, una por
# corrida-, asi que aqui va la misma guarda aunque este no tenga sesiones colgando.
limpia() {
  for d in "$BD" "$BK" "$BG"; do
    psql -X -q -d postgres -c "DROP DATABASE IF EXISTS $d WITH (FORCE)" >/dev/null 2>&1
  done
  rm -rf "$DIR"
  q=$(psql -X -A -t -d postgres -c "SELECT coalesce(string_agg(datname,' '),'') FROM pg_database WHERE datname IN ('$BD','$BK','$BG')" 2>/dev/null)
  [ -z "${q// /}" ] || echo "AVISO: no pude borrar mis bases temporales: $q"
}
[ "${K104_CONTROL_GUARDA:-0}" = "1" ] || trap limpia EXIT
fallos=0; pasan=0; sinmat=""
comprueba() { if [ "$2" = si ]; then pasan=$((pasan+1)); printf '  [ok   ] %-70s\n' "$1"
              else fallos=$((fallos+1)); printf '  [FALLA] %-70s\n' "$1"; fi; }

# --- SIN TUBERIA EN LOS BRAZOS, Y NO ES ESTILO -------------------------------------------
# `printf '%s' "$OUT" | grep -q PATRON` es la forma que costo la mitad del remate de la
# campana 131 en K104: `grep -q` sale en el PRIMER acierto y cierra su extremo de la tuberia,
# y si la variable pasa de los 64 KB del buffer el `printf` se queda a medias. Con `pipefail`
# el estado de la tuberia es el del printf -141 por SIGPIPE, o 1 y un «write error: Broken
# pipe» por stderr si SIGPIPE esta IGNORADO-, asi que el brazo saldria [FALLA] SIN HABER
# MIRADO la salida. Aqui `OUT` es la salida de un check y su techo NO es pequeno: K104 sobre
# un sujeto con miles de parejas condenadas pasa de 64 KB sin esfuerzo.
# Se escribe a FICHERO y se grepea el FICHERO: ahi no hay tuberia que romper.
#   dice  PATRON [TEXTO]   subcadena/BRE   ·   diceE PATRON [TEXTO]   ERE
#   prim  TEXTO PATRON     solo la PRIMERA linea, con expansion de bash y cero procesos
dice()  { printf '%s\n' "${2-$OUT}" > "$DIR/_o"; grep -q  -- "$1" "$DIR/_o"; }
diceE() { printf '%s\n' "${2-$OUT}" > "$DIR/_o"; grep -qE -- "$1" "$DIR/_o"; }
prim()  { case "${1%%$'\n'*}" in "$2"*) return 0 ;; *) return 1 ;; esac; }

D() { date -u -d "$1 days ago" +%F; }   # D 3 -> el dia de hace 3 dias, en UTC
# TODA MUTACION VA CON timezone='UTC', Y ESO LO ENSENO EL PROPIO CONTROL. El servidor de 143
# esta en America/Mexico_City: sin esto, `current_date` dentro de psql era 10-01 mientras el
# dia UTC del check era el 10-02, asi que el brazo T creia borrar filas de HOY y borraba las
# de un dia YA CERRADO -y el check condenaba con razon-. Un instrumento que no fija la zona no
# planta lo que cree plantar. Es la misma mordida que la cabecera de K01b tiene escrita.
m() { psql -X -q -d "${BDM:-$BD}" -c "SET timezone='UTC'; $1" >/dev/null 2>&1; }
q() { psql -X -A -t -d "${BDM:-$BD}" -c "SET timezone='UTC'" -c "$1" 2>/dev/null | tail -1; }

psql -X -q -d postgres -c "DROP DATABASE IF EXISTS $BD" -c "CREATE DATABASE $BD" >/dev/null 2>&1
# LA SIEMBRA. Tres tablas declaradas en el TSV de verdad -dos sin poda y una podada por
# SNAPSHOT_RETENTION_DAYS- y una CUARTA que NO esta declarada, para ver si la red la nombra.
psql -X -q -v ON_ERROR_STOP=1 -d "$BD" >/dev/null 2>&1 <<SQL
SET timezone='UTC';
CREATE TABLE signal_observation (observation_id bigint PRIMARY KEY, created_at timestamptz NOT NULL);
CREATE TABLE signal_execution_snapshot (execution_snapshot_id bigint PRIMARY KEY,
       observation_id bigint REFERENCES signal_observation(observation_id), created_at timestamptz NOT NULL);
CREATE TABLE metrics_snapshot (id bigint PRIMARY KEY, ts timestamptz NOT NULL);
CREATE TABLE tabla_que_nadie_declaro (id int PRIMARY KEY, ts timestamptz NOT NULL);
INSERT INTO signal_observation
  SELECT g, (current_date - k)::timestamptz + interval '10 hours'
    FROM generate_series(0,9) k, generate_series(1,20) i, LATERAL (SELECT k*100+i AS g) z;
INSERT INTO signal_execution_snapshot
  SELECT 10000+o.observation_id, o.observation_id, o.created_at FROM signal_observation o;
INSERT INTO metrics_snapshot
  SELECT g, (current_date - k)::timestamptz + interval '10 hours'
    FROM generate_series(0,9) k, generate_series(1,20) i, LATERAL (SELECT k*100+i AS g) z;
INSERT INTO tabla_que_nadie_declaro SELECT i, current_date::timestamptz FROM generate_series(1,5) i;
SQL
sem=$(q "SELECT count(*) FROM signal_observation")

ret() { printf 'SNAPSHOT_RETENTION_DAYS=%s\n' "$1" > "$DIR/ret.tsv"; }
corre() {  # $1 = fichero de censo
  OUT=$(env K104_SUJETO=local K104_BASE="$BD" K104_TABLAS="$DECL" \
            K104_RETENCIONES="$DIR/ret.tsv" K104_CENSO="$1" \
            timeout -k 5 300 bash "$CHK" 2>&1); RC=$?
}

echo "K104-control · sujeto: $CHK"
echo
echo "0 · la siembra existe: 10 dias x 20 filas en tres tablas"
comprueba "0a signal_observation tiene 200 filas (dio $sem)" "$([ "$sem" = 200 ] && echo si || echo no)"

echo
echo "F · SIN CENSO ANTERIOR no es un VERDE: solo se puede sembrar"
ret 7
corre "$DIR/c1.tsv"
comprueba "F1 NO MEDIDO, rc=2 (rc=$RC)" "$([ "$RC" = 2 ] && echo si || echo no)"
comprueba "F2 y dice que solo ha podido SEMBRAR" \
  "$(dice 'solo ha podido SEMBRAR' && echo si || echo no)"
comprueba "F3 el censo quedo escrito" "$([ -s "$DIR/c1.tsv" ] && echo si || echo no)"

echo
echo "H · la tabla que nadie declaro sale NOMBRADA, no juzgada por omision"
comprueba "H1 nombra tabla_que_nadie_declaro" \
  "$(dice 'SIN DECLARAR.*tabla_que_nadie_declaro' && echo si || echo no)"

echo
echo "G · GEMELO · sin tocar nada, la segunda corrida PASA"
cp "$DIR/c1.tsv" "$DIR/c2.tsv"
corre "$DIR/c2.tsv"
comprueba "G1 rc=0 (rc=$RC)" "$([ "$RC" = 0 ] && echo si || echo no)"
comprueba "G2 y lo dice contando parejas" \
  "$(dice 'ningun dia cerrado encogio' && echo si || echo no)"

echo
echo "P · PLANTADO · 7 filas menos en un dia CERRADO de una tabla sin poda"
DIA3=$(D 3)
m "SET session_replication_role='replica'; DELETE FROM signal_observation WHERE created_at::date='$DIA3' AND observation_id % 3 = 0;"
quitadas=$(q "SELECT 20-count(*) FROM signal_observation WHERE created_at::date='$DIA3'")
cp "$DIR/c1.tsv" "$DIR/c3.tsv"
corre "$DIR/c3.tsv"
comprueba "P0 el plantado existe: $quitadas filas menos el $DIA3" "$([ "${quitadas:-0}" -gt 0 ] && echo si || echo no)"
comprueba "P1 condena, rc=1 (rc=$RC)" "$([ "$RC" = 1 ] && echo si || echo no)"
comprueba "P2 con su TABLA y su DIA" \
  "$(diceE "signal_observation +$DIA3 " && echo si || echo no)"
comprueba "P3 y con el antes y el ahora" \
  "$(diceE "signal_observation +$DIA3 +antes 20 +ahora $((20-quitadas))" && echo si || echo no)"
comprueba "P4 y NO condena ningun otro dia ni tabla (1 dia, no 2)" \
  "$(diceE 'PERDIDA SILENCIOSA en .*: 1 dia' && echo si || echo no)"
comprueba "P5 y el veredicto va en la PRIMERA linea, que es lo que verify cita" \
  "$(prim "${OUT}" 'PERDIDA SILENCIOSA' && echo si || echo no)"

echo
echo "E · LA MARCA DE AGUA NO SE REBAJA: con la perdida ahi, la corrida siguiente sigue ROJA"
corre "$DIR/c3.tsv"
comprueba "E1 sigue rc=1 (rc=$RC)" "$([ "$RC" = 1 ] && echo si || echo no)"
comprueba "E2 y sigue diciendo antes 20" \
  "$(diceE "signal_observation +$DIA3 +antes 20" && echo si || echo no)"

echo
echo "R · y cuando las filas VUELVEN, se pone VERDE sin que nadie lo edite"
m "SET session_replication_role='replica'; INSERT INTO signal_observation SELECT g, ('$DIA3'::date)::timestamptz + interval '10 hours' FROM generate_series(1,20) i, LATERAL (SELECT 300+i AS g) z ON CONFLICT DO NOTHING;"
vuelven=$(q "SELECT count(*) FROM signal_observation WHERE created_at::date='$DIA3'")
corre "$DIR/c3.tsv"
comprueba "R0 el dia vuelve a tener 20 o mas (dio $vuelven)" "$([ "${vuelven:-0}" -ge 20 ] && echo si || echo no)"
comprueba "R1 rc=0 (rc=$RC)" "$([ "$RC" = 0 ] && echo si || echo no)"

echo
echo "C · un dia cerrado que CRECE no condena"
m "INSERT INTO signal_observation VALUES (999999, ('$(D 4)'::date)::timestamptz + interval '11 hours')"
corre "$DIR/c3.tsv"
comprueba "C1 rc=0 (rc=$RC)" "$([ "$RC" = 0 ] && echo si || echo no)"

echo
echo "T · HOY no se juzga: lo que se va de hoy no es un dia cerrado"
m "SET session_replication_role='replica'; DELETE FROM signal_observation WHERE created_at::date=current_date;"
corre "$DIR/c3.tsv"
comprueba "T1 rc=0 (rc=$RC)" "$([ "$RC" = 0 ] && echo si || echo no)"
comprueba "T2 y dice cual es el dia cerrado mas reciente que juzga" \
  "$(dice "mas reciente que se juzga es $(D 1)" && echo si || echo no)"

echo
echo "B · EL BORDE (A68) · la MISMA perdida, dentro y fuera de la ventana declarada"
# Con 7 dias de retencion el dia de hace 6 cabe entero; con 5 ya no. Las filas que se van son
# las MISMAS y son la misma cantidad: lo unico que cambia entre los dos sujetos es el numero
# declarado de retencion, que es la variable 2.
DIA6=$(D 6)
ret 7
rm -f "$DIR/cb.tsv"; corre "$DIR/cb.tsv"          # siembra con ventana de 7
tenia=$(q "SELECT count(*) FROM metrics_snapshot WHERE ts::date='$DIA6'")
dentro=$(grep -cP "^metrics_snapshot\t$DIA6\t" "$DIR/cb.tsv" 2>/dev/null)
comprueba "B0 con ventana de 7 dias, $DIA6 ESTA en el censo (dio $dentro)" "$([ "${dentro:-0}" = 1 ] && echo si || echo no)"
m "SET session_replication_role='replica'; DELETE FROM metrics_snapshot WHERE ts::date='$DIA6' AND id % 2 = 0;"
ahora=$(q "SELECT count(*) FROM metrics_snapshot WHERE ts::date='$DIA6'")
cp "$DIR/cb.tsv" "$DIR/cb7.tsv"; cp "$DIR/cb.tsv" "$DIR/cb5.tsv"
ret 7; corre "$DIR/cb7.tsv"; RC7=$RC; OUT7=$OUT
ret 5; corre "$DIR/cb5.tsv"; RC5=$RC; OUT5=$OUT
comprueba "B0b la perdida es la misma en los dos: de $tenia a $ahora el $DIA6" "$([ "${ahora:-0}" -lt "${tenia:-0}" ] && echo si || echo no)"
comprueba "B1 DENTRO (retencion 7): CONDENA, rc=1 (rc=$RC7)" "$([ "$RC7" = 1 ] && echo si || echo no)"
comprueba "B2 y nombra metrics_snapshot $DIA6" \
  "$(diceE "metrics_snapshot +$DIA6 " "${OUT7}" && echo si || echo no)"
comprueba "B3 FUERA (retencion 5): NO condena, rc=0 (rc=$RC5)" "$([ "$RC5" = 0 ] && echo si || echo no)"
comprueba "B4 y el dia que salio de la ventana se OLVIDO del censo" \
  "$([ "$(grep -cP "^metrics_snapshot\t$DIA6\t" "$DIR/cb5.tsv" 2>/dev/null)" = 0 ] && echo si || echo no)"

echo
echo "T64 · UN CENSO DE MAS DE 64 KB, con SIGPIPE IGNORADO y con SIGPIPE POR OMISION"
# POR QUE ESTE BRAZO. El buffer de una tuberia de Linux son 64 KB. Mientras la variable quepa,
# un `printf "$VAR" | grep -q` termina de escribir antes de que grep cierre y nadie se entera de
# nada; en cuanto NO cabe, el printf se queda a medias y con `pipefail` el estado de la tuberia
# es el SUYO -141 por SIGPIPE, o 1 y un «write error: Broken pipe» por stderr si SIGPIPE esta
# IGNORADO, que es como corre todo lo que el operador lanza por `pct exec`-. O sea que el
# defecto SOLO existe por encima de un tamano, y un control con un sujeto pequeno NO LO VE:
# el mio no lo vio, y lo encontro el operador. Asi que el sujeto de este brazo esta sembrado a
# proposito para pasar de 64 KB, y el brazo MIDE el tamano del censo y lo publica: un control
# de «pasa de 64 KB» que no comprueba el tamano no mide lo que dice.
#
# Y va en los DOS modos porque el DANO es el mismo en los dos y el RASTRO solo esta en uno.
# Esa asimetria es la razon de que esto sobreviviera a 40 brazos verdes.
psql -X -q -d postgres -c "DROP DATABASE IF EXISTS $BG WITH (FORCE)" -c "CREATE DATABASE $BG" >/dev/null 2>&1
psql -X -q -v ON_ERROR_STOP=1 -d "$BG" >/dev/null 2>&1 <<'SQL'
SET timezone='UTC';
CREATE TABLE signal_observation (observation_id bigint PRIMARY KEY, created_at timestamptz NOT NULL);
CREATE TABLE signal_outcome (observation_id bigint, created_at timestamptz NOT NULL);
-- 2500 dias x 1 fila en dos tablas = 5000 parejas (tabla,dia). Con `sin_poda` el piso es
-- 1970-01-01, asi que entran todas.
INSERT INTO signal_observation
  SELECT k, (current_date - k)::timestamptz + interval '10 hours' FROM generate_series(1,2500) k;
INSERT INTO signal_outcome
  SELECT k, (current_date - k)::timestamptz + interval '11 hours' FROM generate_series(1,2500) k;
SQL
corre64() {  # $1 = fichero de censo, $2 = ignorado|omision
  if [ "$2" = ignorado ]; then F="--ignore-signal=PIPE"; else F="--default-signal=PIPE"; fi
  OUT=$(env "$F" K104_SUJETO=local K104_BASE="$BG" K104_TABLAS="$DECL" \
            K104_RETENCIONES="$DIR/ret.tsv" K104_CENSO="$1" \
            timeout -k 5 300 bash "$CHK" 2>"$DIR/e64-$2"); RC=$?
  JUNTO=$(env "$F" K104_SUJETO=local K104_BASE="$BG" K104_TABLAS="$DECL" \
            K104_RETENCIONES="$DIR/ret.tsv" K104_CENSO="$1" \
            timeout -k 5 300 bash "$CHK" 2>&1)
}
ret 7
rm -f "$DIR/c64.tsv"; corre64 "$DIR/c64.tsv" omision     # siembra
tam=$(wc -c < "$DIR/c64.tsv")
comprueba "T64-0 el censo del sujeto PASA de 64 KB (dio $tam B)" "$([ "${tam:-0}" -gt 65536 ] && echo si || echo no)"
for modo in ignorado omision; do
  cp "$DIR/c64.tsv" "$DIR/c64-$modo.tsv"
  corre64 "$DIR/c64-$modo.tsv" "$modo"
  bp=$(grep -c 'Broken pipe' "$DIR/e64-$modo" 2>/dev/null)
  rec=$(printf '%s\n' "$OUT" | sed -n 's/.* \([0-9]*\) recontada(s) una a una.*/\1/p' | head -1)
  comprueba "T64-$modo-a rc=0 (rc=$RC)" "$([ "$RC" = 0 ] && echo si || echo no)"
  comprueba "T64-$modo-b CERO «Broken pipe» por stderr (dio ${bp:-?})" "$([ "${bp:-1}" = 0 ] && echo si || echo no)"
  comprueba "T64-$modo-c CERO tablas recontadas una a una (dio ${rec:-?})" "$([ "${rec:-9}" = 0 ] && echo si || echo no)"
  # Lo que `verify:66` capturaria de verdad: stdout y stderr JUNTOS. Es la unica forma de medir
  # lo que acabaria en el marcador.
  comprueba "T64-$modo-d la PRIMERA linea de stdout+stderr es el veredicto" \
    "$(prim "${JUNTO}" 'ningun dia cerrado encogio' && echo si || echo no)"
done
# EL GEMELO QUE SI TIENE QUE RECONTAR. Con el mismo sujeto grande y una tabla bloqueada por
# otra sesion, la recuenta es LEGITIMA y el numero tiene que ser distinto de 0: si saliera 0
# tambien, el brazo de arriba estaria midiendo «nunca recuenta» en vez de «no recuenta de mas».
psql -X -q -d "$BG" -c "BEGIN; LOCK TABLE signal_outcome IN ACCESS EXCLUSIVE MODE; SELECT pg_sleep(45);" >/dev/null 2>&1 &
PIDLOCK=$!
sleep 2
cp "$DIR/c64.tsv" "$DIR/c64-lock.tsv"
OUT=$(env --default-signal=PIPE K104_SUJETO=local K104_BASE="$BG" K104_TABLAS="$DECL" \
          K104_RETENCIONES="$DIR/ret.tsv" K104_CENSO="$DIR/c64-lock.tsv" K104_TIMEOUT_MS=1500 \
          timeout -k 5 300 bash "$CHK" 2>"$DIR/e64-lock"); RC=$?
kill "$PIDLOCK" 2>/dev/null; wait "$PIDLOCK" 2>/dev/null
psql -X -q -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$BG'" >/dev/null 2>&1
reclock=$(printf '%s\n' "$OUT" | sed -n 's/.* \([0-9]*\) recontada(s) una a una.*/\1/p' | head -1)
comprueba "T64-gemelo con una tabla BLOQUEADA si recuenta (dio ${reclock:-?})" \
  "$([ "${reclock:-0}" -gt 0 ] && echo si || echo no)"
# SIN PERDIDA CONTADA Y CON ALGO SIN CONTAR, el veredicto es NO MEDIDO y el mensaje va en
# MINUSCULAS; la version en MAYUSCULAS («y NO SE PUDO CONTAR ...») es la que va DENTRO de un
# ROJO, que es el brazo M. Mi primera version de este brazo buscaba la mayuscula en el camino
# del NO MEDIDO y daba [FALLA] con el check correcto delante: el defecto era del brazo.
comprueba "T64-gemelo NO MEDIDO, rc=2 (rc=$RC)" "$([ "$RC" = 2 ] && echo si || echo no)"
comprueba "T64-gemelo y nombra la que no pudo contar" \
  "$(dice 'no se pudo contar.*signal_outcome' && echo si || echo no)"
psql -X -q -d postgres -c "DROP DATABASE IF EXISTS $BG WITH (FORCE)" >/dev/null 2>&1

echo
echo "M · una tabla que NO SE PUEDE CONTAR no se cuenta como perdida, y no borra la que si se conto"
# Es la mitad fea del brazo H de K103 traida aqui: sin cuenta de hoy, `actual` no trae las
# parejas de esa tabla y la resta las daria a CERO, o sea una perdida INVENTADA del tamano de la
# tabla entera. Y la salida se lo atribuia a «las que SI se contaron». El bloqueo lo pone otra
# sesion, que es la unica forma honesta de que falle UNA tabla y no todas.
ret 7
rm -f "$DIR/cm.tsv"; corre "$DIR/cm.tsv"          # siembra limpia
DIA2=$(D 2)
m "SET session_replication_role='replica'; DELETE FROM signal_observation WHERE created_at::date='$DIA2' AND observation_id % 4 = 0;"
psql -X -q -d "$BD" -c "BEGIN; LOCK TABLE metrics_snapshot IN ACCESS EXCLUSIVE MODE; SELECT pg_sleep(45);" >/dev/null 2>&1 &
PIDLOCK=$!
sleep 2
tiene=$(psql -X -A -t -d "$BD" -c "SELECT count(*) FROM pg_locks l JOIN pg_class c ON c.oid=l.relation WHERE c.relname='metrics_snapshot' AND l.mode='AccessExclusiveLock'" 2>/dev/null)
comprueba "M0 el bloqueo esta puesto de verdad (locks=$tiene)" "$([ "${tiene:-0}" -ge 1 ] && echo si || echo no)"
OUT=$(env K104_SUJETO=local K104_BASE="$BD" K104_TABLAS="$DECL" K104_RETENCIONES="$DIR/ret.tsv" \
          K104_CENSO="$DIR/cm.tsv" K104_TIMEOUT_MS=1500 timeout -k 5 300 bash "$CHK" 2>&1); RC=$?
kill "$PIDLOCK" 2>/dev/null; wait "$PIDLOCK" 2>/dev/null
psql -X -q -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$BD'" >/dev/null 2>&1
comprueba "M1 ROJO por la perdida REAL, rc=1 (rc=$RC)" "$([ "$RC" = 1 ] && echo si || echo no)"
comprueba "M2 nombra la perdida de signal_observation el $DIA2" \
  "$(diceE "signal_observation +$DIA2 " && echo si || echo no)"
comprueba "M3 y NOMBRA metrics_snapshot como no contada" \
  "$(dice 'NO SE PUDO CONTAR.*metrics_snapshot' && echo si || echo no)"
comprueba "M4 y NO inventa una perdida de metrics_snapshot" \
  "$(diceE '^  metrics_snapshot +[0-9]{4}-' && echo no || echo si)"
comprueba "M5 un solo dia condenado, el de verdad" \
  "$(diceE 'PERDIDA SILENCIOSA en .*: 1 dia' && echo si || echo no)"

echo
echo "I · sin la retencion del sujeto no se juzga a ciegas"
printf 'OTRA_COSA=3\n' > "$DIR/ret.tsv"
corre "$DIR/c3.tsv"
comprueba "I1 NO MEDIDO, rc=2 (rc=$RC)" "$([ "$RC" = 2 ] && echo si || echo no)"
comprueba "I2 y nombra la variable que falta" \
  "$(dice 'SNAPSHOT_RETENTION_DAYS' && echo si || echo no)"

echo
echo "K · RESPUESTA CONOCIDA · las 38 filas REALES del 08-29, puestas y quitadas de una copia"
REP=${K104_REPARACION:-/root/banco-129/repara-PRODUCCION.sql}
if [ ! -r "$REP" ]; then
  sinmat="$sinmat K(no esta $REP)"
  echo "  [sin material] K · no esta $REP, asi que este brazo NO se ha ejercitado"
else
  # Las dos tablas de verdad, con las columnas que el COPY del banco nombra. La copia se
  # siembra con un vecindario de dias para que «y NADA mas» pueda ser falso.
  psql -X -q -d postgres -c "DROP DATABASE IF EXISTS $BK WITH (FORCE)" -c "CREATE DATABASE $BK" >/dev/null 2>&1
  cols_obs=$(sed -n 's/^COPY public.signal_observation (\(.*\)) FROM stdin;/\1/p' "$REP")
  cols_exe=$(sed -n 's/^COPY public.signal_execution_snapshot (\(.*\)) FROM stdin;/\1/p' "$REP")
  # Tipos generosos a proposito: lo que se mide es el CONTEO POR DIA, no el tipo de cada
  # columna. created_at y el id van tipados porque de ellos sale el dia y la clave.
  gen() { printf 'CREATE TABLE %s (' "$1"; shift; n=0
          for c in $(printf '%s' "$*" | tr -d ' ' | tr ',' ' '); do
            n=$((n+1)); [ "$n" -gt 1 ] && printf ', '
            case "$c" in created_at|observed_at|observed_minute|captured_at|book_ts|*_at|*_ts) printf '%s timestamptz' "$c" ;;
                         observation_id|execution_snapshot_id) printf '%s bigint' "$c" ;;
                         *) printf '%s text' "$c" ;; esac
          done; printf ');\n'; }
  { printf "SET timezone='UTC';\n"; gen signal_observation "$cols_obs"; gen signal_execution_snapshot "$cols_exe"; } > "$DIR/banco.sql"
  psql -X -q -v ON_ERROR_STOP=1 -d "$BK" -f "$DIR/banco.sql" >/dev/null 2>"$DIR/banco.err"
  # El vecindario: 08-27, 08-28, 08-29, 08-30 y 08-31 con filas propias, para que una
  # diferencia de mas pueda aparecer.
  psql -X -q -d "$BK" >/dev/null 2>&1 <<'SQL'
INSERT INTO signal_observation (observation_id, created_at)
  SELECT 900000+k*100+i, ('2026-08-27'::date + k)::timestamptz + interval '9 hours'
    FROM generate_series(0,4) k, generate_series(1,30) i;
INSERT INTO signal_execution_snapshot (execution_snapshot_id, observation_id, created_at)
  SELECT 900000+o.observation_id, o.observation_id, o.created_at FROM signal_observation o;
SQL
  # Y ahora las 38 de verdad, con el COPY tal cual viene del banco.
  sed -n '/^COPY public.signal_observation /,/^\\\.$/p;/^COPY public.signal_execution_snapshot /,/^\\\.$/p' "$REP" \
    | psql -X -q -v ON_ERROR_STOP=1 -d "$BK" >/dev/null 2>"$DIR/copy.err"
  puestas_o=$(BDM="$BK" q "SELECT count(*) FROM signal_observation WHERE observation_id BETWEEN 143691 AND 143754")
  puestas_e=$(BDM="$BK" q "SELECT count(*) FROM signal_execution_snapshot WHERE observation_id BETWEEN 143691 AND 143754")
  comprueba "K0 las 38 filas reales estan en la copia: 17 y 21 (dio $puestas_o y $puestas_e)" \
    "$([ "$puestas_o" = 17 ] && [ "$puestas_e" = 21 ] && echo si || echo no)"
  ret 7
  rm -f "$DIR/ck.tsv"
  OUT=$(env K104_SUJETO=local K104_BASE="$BK" K104_TABLAS="$DECL" K104_RETENCIONES="$DIR/ret.tsv" \
            K104_CENSO="$DIR/ck.tsv" timeout -k 5 300 bash "$CHK" 2>&1); RC=$?
  comprueba "K1 la primera corrida siembra (rc=2, rc=$RC)" "$([ "$RC" = 2 ] && echo si || echo no)"
  # LA PERDIDA, tal como fue: se van las 38 filas y nadie toca a sus hijas.
  BDM="$BK" m "SET session_replication_role='replica'; DELETE FROM signal_observation WHERE observation_id BETWEEN 143691 AND 143754; DELETE FROM signal_execution_snapshot WHERE observation_id BETWEEN 143691 AND 143754;"
  OUT=$(env K104_SUJETO=local K104_BASE="$BK" K104_TABLAS="$DECL" K104_RETENCIONES="$DIR/ret.tsv" \
            K104_CENSO="$DIR/ck.tsv" timeout -k 5 300 bash "$CHK" 2>&1); RC=$?
  comprueba "K2 condena, rc=1 (rc=$RC)" "$([ "$RC" = 1 ] && echo si || echo no)"
  comprueba "K3 -17 en signal_observation, del 2026-08-29" \
    "$(diceE 'signal_observation +2026-08-29 +antes 47 +ahora 30 +\(-17\)' && echo si || echo no)"
  comprueba "K4 -21 en signal_execution_snapshot, del 2026-08-29" \
    "$(diceE 'signal_execution_snapshot +2026-08-29 +antes 51 +ahora 30 +\(-21\)' && echo si || echo no)"
  comprueba "K5 y NADA mas: exactamente 2 dias condenados" \
    "$(diceE 'PERDIDA SILENCIOSA en .*: 2 dia' && echo si || echo no)"
  psql -X -q -d postgres -c "DROP DATABASE IF EXISTS $BK WITH (FORCE)" >/dev/null 2>&1
fi

echo
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan${sinmat:+ · SIN MATERIAL:$sinmat}"
[ "$fallos" -eq 0 ] || exit 1
exit 0
