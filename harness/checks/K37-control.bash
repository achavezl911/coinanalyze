#!/usr/bin/env bash
# K37-control · ¿el veredicto de K37 depende de la HORA a la que se le pregunte?
#
#     bash harness/checks/K37-control.bash
#
# EL PUNTO (COLA 128, A53). La MISMA perdida de buckets daba VERDE o ROJO segun la hora del dia
# UTC a la que se corriera K37. MEDIDO en produccion el 2026-09-19T04:59:07Z: los 88 minutos que
# `futures_trades_agg` perdio el 09-16 salian a 0.895 % con el suelo de la serie en 09-12 04:07
# y a 1.019 % con el suelo en 09-13 00:00, con los MISMOS 88 perdidos en las dos cuentas. El
# suelo era `min(ts)`, que en esa tabla no es el nacimiento sino la RETENCION -168 h-, o sea
# now() menos 7 dias: avanzaba con el reloj y encogia el denominador durante el dia. La cabecera
# de K37 dice desde agosto que su ventana es de dias cerrados precisamente para que la tasa no
# dependa de la hora.
#
# COMO SE MUEVE EL RELOJ, Y POR QUE ASI. No se toca el reloj de la maquina ni el del servidor:
# se pone una funcion `now()` propia en un esquema DELANTE de `pg_catalog` en el `search_path`,
# y K37 -que pregunta por `now()` y no por CURRENT_TIMESTAMP- se la come sin enterarse. El reloj
# vive en una fila, asi que cambiar la hora es un UPDATE.
#
# LO QUE ESTE CONTROL REPRODUCE Y LO QUE NO, dicho aqui y no en una nota al pie. La hora, sola,
# sobre bytes IDENTICOS, no movia nunca el veredicto viejo: dentro de un mismo dia UTC la
# ventana no cambia. Lo que lo movia era la RETENCION, que borra filas segun avanza el reloj y
# arrastra `min(ts)` con ella. Reproducir el actor incluye reproducir lo que lo mueve (A57, A59),
# asi que cada brazo parte de LA MISMA tabla generada -misma perdida, en los mismos minutos
# absolutos- y le aplica la retencion que produccion tendria a esa hora. Lo que varia entre los
# dos brazos de un par es la hora y solo la hora; lo que la hora arrastra es el mecanismo bajo
# prueba, no una licencia del banco.
#
# LA BASE ES DESECHABLE Y SE BORRA. Nada de esto toca 140 ni el espejo: `createdb` local, las
# nueve tablas declaradas con su forma minima, y `dropdb` al salir.
#
# NO LLEVA .sh A PROPOSITO: bin/verify globea checks/*.sh.
set -uo pipefail
ORIG=${REPO:-/srv/coinanalyze/repo}
CHK="$ORIG/harness/checks/K37-tasa-de-perdida.sh"
[ -r "$CHK" ] || { echo "NO MEDIDO: no encuentro el check en $CHK"; exit 2; }
command -v createdb >/dev/null 2>&1 || { echo "NO MEDIDO: no hay createdb en esta maquina"; exit 2; }

DB="k37ctl_$$"
DIR=$(mktemp -d) || exit 2
limpia() { dropdb --if-exists "$DB" >/dev/null 2>&1; rm -rf "$DIR"; }
trap limpia EXIT
fallos=0; pasan=0
declare -A SALIDA RC
comprueba() {  # $1 = etiqueta   $2 = si|no
  if [ "$2" = si ]; then pasan=$((pasan+1)); printf '  [ok   ] %-64s\n' "$1"
  else fallos=$((fallos+1)); printf '  [FALLA] %-64s\n' "$1"; fi
}
sql() { psql -X -A -t -q -v ON_ERROR_STOP=1 -d "$DB" -c "$1"; }

createdb "$DB" >/dev/null 2>&1 || { echo "NO MEDIDO: no se pudo crear la base desechable $DB"; exit 2; }

# ── EL MUNDO DE MENTIRA ─────────────────────────────────────────────────────────────────────
# Las nueve tablas que K37 declara, con la forma minima que su consulta necesita. Ocho se quedan
# vacias a proposito: no aportan series y asi el sujeto es una sola tabla. Si se quedaran FUERA,
# la consulta ni siquiera compilaria, y ademas la rama SINTECHO las denunciaria.
psql -X -q -v ON_ERROR_STOP=1 -d "$DB" >/dev/null <<'SQL' || { echo "NO MEDIDO: no se pudo montar el mundo"; exit 2; }
CREATE SCHEMA reloj;
CREATE TABLE reloj.ajuste(t timestamptz);
INSERT INTO reloj.ajuste VALUES ('2026-09-19 04:00:00+00');
CREATE FUNCTION reloj.now() RETURNS timestamptz
  LANGUAGE sql STABLE AS $$ SELECT t FROM reloj.ajuste LIMIT 1 $$;
CREATE TABLE futures_trades_agg(ts timestamptz, symbol text, "interval" text);
CREATE TABLE spot_trades_agg   (ts timestamptz, symbol text, "interval" text);
CREATE TABLE long_short_ratio  (ts timestamptz, symbol text, "interval" text);
CREATE TABLE funding_rate      (ts timestamptz, symbol text, "interval" text);
CREATE TABLE open_interest     (ts timestamptz, symbol text, "interval" text);
CREATE TABLE oi_bybit          (ts timestamptz, symbol text, "interval" text);
CREATE TABLE predicted_funding_rate(ts timestamptz, symbol text, "interval" text);
CREATE TABLE ohlcv             (ts timestamptz, symbol text, "interval" text);
CREATE TABLE liquidations      (ts timestamptz, symbol text, "interval" text);
-- La tabla PRISTINA de la que sale cada plantado. Nunca se toca despues de nacer.
CREATE TABLE base(ts timestamptz);
INSERT INTO base
  SELECT g FROM generate_series('2026-09-11 00:00:00+00'::timestamptz,
                                '2026-09-18 23:59:00+00'::timestamptz, interval '1 minute') g;
SQL

# EL CANAL DE MENTIRA. K37 llama a "$B/bin/prodsql" y `B` es una constante en su linea 76: se
# copia el check cambiando esa linea, y se comprueba que el sed MORDIO -si no, se estaria
# midiendo el check de verdad contra produccion y el control aprobaria midiendo otra cosa-.
mkdir -p "$DIR/bin"
cat > "$DIR/bin/prodsql" <<EOF
#!/bin/sh
PGOPTIONS='-c search_path=reloj,public,pg_catalog -c timezone=UTC' \\
  exec psql -X -A -F'|' -t -v ON_ERROR_STOP=1 -q -d "$DB" -c "\$*"
EOF
chmod +x "$DIR/bin/prodsql"
COPIA="$DIR/K37.sh"
sed "s#^B=/srv/coinanalyze/harness\$#B=$DIR#" "$CHK" > "$COPIA"
if cmp -s "$CHK" "$COPIA"; then echo "NO MEDIDO: el sed del canal NO mordio"; exit 2; fi
grep -q "^B=$DIR\$" "$COPIA" || { echo "NO MEDIDO: la copia no apunta al canal de mentira"; exit 2; }

# ── EL PLANTADO ─────────────────────────────────────────────────────────────────────────────
# Rellena futures_trades_agg desde `base` a la hora $1, con la retencion de 168 h aplicada como
# la aplicaria produccion, y con $3 minutos ausentes a partir de $2. La perdida se planta en
# MINUTOS ABSOLUTOS, iguales en los dos brazos de cada par.
planta() {  # $1 = reloj ISO   $2 = inicio de la perdida   $3 = minutos perdidos
  sql "UPDATE reloj.ajuste SET t = '$1'::timestamptz" >/dev/null
  sql "TRUNCATE futures_trades_agg" >/dev/null
  sql "INSERT INTO futures_trades_agg(ts,symbol,\"interval\")
       SELECT ts,'BTCUSDT_PERP.A','1min' FROM base
        WHERE ts >= '$1'::timestamptz - interval '168 hours'
          AND NOT (ts >= '$2'::timestamptz
                   AND ts < '$2'::timestamptz + interval '$3 minutes')" >/dev/null
}
# LA HUELLA: cuantas filas y que suma. Se toma ANTES y DESPUES de correr K37 para demostrar que
# el check LEE y no escribe -y K37 corre por un canal que solo sabe hacer SELECT, pero eso es
# una promesa del canal y esto es la comprobacion-.
huella() { sql "SELECT count(*)||'/'||coalesce(md5(string_agg(ts::text,',' ORDER BY ts)),'-') FROM futures_trades_agg"; }
corre() {  # $1 = etiqueta
  local a d
  a=$(huella); SALIDA["$1"]=$(timeout -k 5 120 bash "$COPIA" 2>&1); RC["$1"]=$?; d=$(huella)
  printf '      %s  reloj=%s  huella %s -> %s\n' "$1" "$(sql "SELECT to_char(reloj.now() AT TIME ZONE 'UTC','MM-DD HH24:MI')")" "$a" "$d"
  printf '      %s  rc=%s · %s\n' "$1" "${RC[$1]}" "$(printf '%s' "${SALIDA[$1]}" | head -1 | cut -c1-140)"
  [ "$a" = "$d" ] || { comprueba "$1 · K37 MOVIO la tabla ($a -> $d)" no; return; }
  HUELLA_OK=1
}

TEMPRANO='2026-09-19 04:00:00+00'
TARDE='2026-09-19 23:30:00+00'
PERDIDA='2026-09-16 10:00:00+00'   # bien dentro de los dias enteros, en los dos relojes
echo "K37-control · sujeto: $CHK"
echo "   base desechable: $DB · reloj falso por search_path · dias UTC cerrados: 09-12 a 09-19"
echo "   los dos relojes: $TEMPRANO y $TARDE (el MISMO dia UTC)"
echo

# ── C1/C2 · LA MISMA PERDIDA, DOS HORAS DEL MISMO DIA ───────────────────────────────────────
# 88 minutos, que es la perdida real del apagon del 09-16. Con el suelo viejo esto daba 0.89 %
# (VERDE) a las 04:00Z y 1.01 % (ROJO) a las 23:30Z. El brazo no pide un veredicto concreto:
# pide que los DOS SEAN EL MISMO, que es lo unico que el sujeto tiene que garantizar.
echo "C1 · 88 minutos perdidos · reloj TEMPRANO (04:00Z)"
planta "$TEMPRANO" "$PERDIDA" 88; corre C1
echo "C2 · los MISMOS 88 minutos · reloj TARDIO (23:30Z), mismo dia UTC"
planta "$TARDE" "$PERDIDA" 88; corre C2
comprueba "C1/C2a EL PUNTO: el MISMO veredicto a las dos horas (rc ${RC[C1]} y ${RC[C2]})" \
  "$([ "${RC[C1]}" = "${RC[C2]}" ] && echo si || echo no)"
comprueba "C1/C2b y la MISMA tasa, no solo el mismo rc" \
  "$([ "$(printf '%s' "${SALIDA[C1]}" | grep -o '[0-9.]* %/dia' | head -1)" \
    = "$(printf '%s' "${SALIDA[C2]}" | grep -o '[0-9.]* %/dia' | head -1)" ] && echo si || echo no)"
comprueba "C1/C2c y la linea dice SOBRE QUE DIAS calculo, en las dos" \
  "$(printf '%s' "${SALIDA[C1]}" | grep -q '2026-09-12 a 2026-09-19' \
   && printf '%s' "${SALIDA[C2]}" | grep -q '2026-09-12 a 2026-09-19' && echo si || echo no)"
comprueba "C1/C2d y dice que a futures_trades_agg le subio el suelo a un dia entero" \
  "$(printf '%s' "${SALIDA[C1]}" | grep -q 'futures_trades_agg desde 2026-09-13' && echo si || echo no)"

# ── C3/C4 · UNA PERDIDA QUE SI PASA EL TECHO: CONDENA A LAS DOS HORAS ───────────────────────
# Sin este par, «los dos veredictos coinciden» lo cumpliria un check que dijera siempre lo mismo.
echo
echo "C3 · 300 minutos perdidos (3.5 %, muy por encima del techo) · reloj TEMPRANO"
planta "$TEMPRANO" "$PERDIDA" 300; corre C3
echo "C4 · los MISMOS 300 · reloj TARDIO"
planta "$TARDE" "$PERDIDA" 300; corre C4
comprueba "C3/C4a CONDENA a las dos horas (rc ${RC[C3]} y ${RC[C4]})" \
  "$([ "${RC[C3]}" = 1 ] && [ "${RC[C4]}" = 1 ] && echo si || echo no)"
comprueba "C3/C4b con la MISMA tasa en las dos" \
  "$([ "$(printf '%s' "${SALIDA[C3]}" | grep -o '[0-9.]* %/dia' | head -1)" \
    = "$(printf '%s' "${SALIDA[C4]}" | grep -o '[0-9.]* %/dia' | head -1)" ] && echo si || echo no)"

# ── C5/C6 · EL CONTROL POSITIVO · SIN PERDIDA, VERDE A LAS DOS HORAS ───────────────────────
echo
echo "C5 · 40 minutos perdidos (0.46 %, por debajo del techo) · reloj TEMPRANO"
planta "$TEMPRANO" "$PERDIDA" 40; corre C5
echo "C6 · los MISMOS 40 · reloj TARDIO"
planta "$TARDE" "$PERDIDA" 40; corre C6
comprueba "C5/C6a ABSUELVE a las dos horas (rc ${RC[C5]} y ${RC[C6]})" \
  "$([ "${RC[C5]}" = 0 ] && [ "${RC[C6]}" = 0 ] && echo si || echo no)"
comprueba "C5/C6b y el VERDE tambien dice sobre que dias calculo" \
  "$(printf '%s' "${SALIDA[C5]}" | grep -q 'dias UTC cerrados, 2026-09-12 a 2026-09-19' && echo si || echo no)"

# ── C7/C8 · EL DIA PARCIAL NO SE MIDE NI POR ARRIBA NI POR ABAJO ───────────────────────────
# La otra mitad del arreglo, y la trampa que tenia delante: si el suelo sube para los ESPERADOS
# y no para los OBSERVADOS, las filas del dia parcial se cuentan sin esperarse, los perdidos se
# van a NEGATIVO y este check da VERDE por debajo de cero. Aqui la perdida se planta ENTERA
# dentro del dia parcial del reloj temprano (09-12 04:00 -> 09-13 00:00).
#   · con el suelo viejo: 200 perdidos sobre 9840 = 2.03 % -> ROJO
#   · con el suelo nuevo: ese tramo no esta ni en esp ni en obs -> 0 perdidos -> VERDE
# Lo que cuesta y se declara: una perdida del dia parcial no se ve en ESTA pasada. Se vio en las
# seis anteriores -ese bucket estuvo dentro de la ventana de dias enteros seis dias seguidos-, y
# es la misma propiedad que la cabecera ya declara para el dia en curso.
echo
echo "C7 · 200 minutos perdidos DENTRO del dia parcial · reloj TEMPRANO"
planta "$TEMPRANO" '2026-09-12 06:00:00+00' 200; corre C7
echo "C8 · los MISMOS 200 · reloj TARDIO (para ese reloj ya ni existen: la retencion se los llevo)"
planta "$TARDE" '2026-09-12 06:00:00+00' 200; corre C8
comprueba "C7/C8a VERDE a las dos horas: el dia parcial no se imputa (rc ${RC[C7]} y ${RC[C8]})" \
  "$([ "${RC[C7]}" = 0 ] && [ "${RC[C8]}" = 0 ] && echo si || echo no)"
comprueba "C7/C8b y NINGUNA tasa sale negativa (obs y esp sobre el mismo intervalo)" \
  "$(printf '%s%s' "${SALIDA[C7]}" "${SALIDA[C8]}" | grep -q -- '-[0-9.]* %/dia' && echo no || echo si)"

# ── C9 · LA HUELLA · K37 NO ESCRIBE ────────────────────────────────────────────────────────
echo
comprueba "C9 ningun brazo movio la tabla plantada (huella antes == despues)" \
  "$([ "${HUELLA_OK:-0}" = 1 ] && echo si || echo no)"

# ── EL CONTROL DEL CONTROL · el reloj falso de verdad enganaba a K37 ───────────────────────
echo
echo "   el control del control · si el reloj no se moviera, los pares no medirian nada:"
sql "UPDATE reloj.ajuste SET t = '$TEMPRANO'::timestamptz" >/dev/null
t1=$(PGOPTIONS='-c search_path=reloj,public,pg_catalog' psql -X -A -t -q -d "$DB" -c "SELECT now() AT TIME ZONE 'UTC'")
sql "UPDATE reloj.ajuste SET t = '$TARDE'::timestamptz" >/dev/null
t2=$(PGOPTIONS='-c search_path=reloj,public,pg_catalog' psql -X -A -t -q -d "$DB" -c "SELECT now() AT TIME ZONE 'UTC'")
printf '      now() con el reloj temprano: %s\n      now() con el reloj tardio:   %s\n' "$t1" "$t2"
comprueba "C10 el reloj falso SI movio now() (si no, los seis pares serian el mismo)" \
  "$([ "$t1" != "$t2" ] && echo si || echo no)"

echo
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
