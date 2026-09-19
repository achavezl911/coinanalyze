#!/usr/bin/env bash
# K37-control · ¿el veredicto de K37 depende de algo que no es la perdida?
#
#     bash harness/checks/K37-control.bash
#
# EL PUNTO, EN DOS EJES. La MISMA perdida de buckets daba veredictos distintos segun
#   1) LA HORA del dia UTC a la que se corriera K37, y
#   2) CUANTO FUERA POR DETRAS LA PODA de la tabla.
# El suelo de cada serie salia de `min(ts)`, y `min(ts)` no es el nacimiento de un feed podado:
# es donde llego la ultima poda. La poda real es `cleanup()` de app/scalp_collector.py:1570-1583,
# un `sleep(3600)` en bucle y despues el DELETE de `cleanup_expired_rows` (:1549,
# `ts < now()-168h`): corre una vez por hora CONTADA DESDE QUE ARRANCA EL COLECTOR, la primera
# una hora despues de arrancar, y ninguna mientras esta caido. Asi que `min(ts)` va por detras
# del corte teorico en una cantidad que va de cero a una hora en marcha normal, y de HORAS tras
# un reinicio. MEDIDO contra 140 el 2026-09-19T15:01:19Z: min(ts) 09-12 14:07, corte teorico
# 09-12 15:01, retraso 54.3 min; el colector arranco a las 03:06:08Z, poda a los minutos :06 y
# por eso el dato empieza en :07. El retraso NO es una propiedad: es el arranque.
#
# Durante los primeros minutos de cada dia UTC -tantos como el retraso- `min(ts)` cae en el dia
# ANTERIOR, el suelo baja un dia entero y la misma perdida se mide sobre 7 dias en vez de 6.
#
# POR ESO LOS BRAZOS SON UNA MATRIZ y no una pareja: dos horas del MISMO dia UTC por tres
# retrasos (cero, el medido, y uno de horas), con la MISMA perdida plantada en los MISMOS
# minutos absolutos. Lo que el sujeto tiene que garantizar no es un veredicto concreto: es que
# los seis sean EL MISMO. Y se corre con dos perdidas -una que pasa el techo y otra que no- para
# que «los seis coinciden» no lo cumpla un check que diga siempre lo mismo.
#
# COMO SE MUEVE EL RELOJ. No se toca el reloj de la maquina ni el del servidor: una funcion
# `now()` propia en un esquema DELANTE de `pg_catalog` en el `search_path`, y K37 -que pregunta
# por `now()` y no por CURRENT_TIMESTAMP- se la come sin enterarse. El reloj vive en una fila.
#
# COMO SE MUEVE LA PODA. Cada plantado rellena la tabla desde una tabla PRISTINA aplicando
# `ts >= reloj - 168h - retraso`, que es exactamente lo que produccion tendria a esa hora con esa
# poda. La perdida se planta en minutos ABSOLUTOS, iguales en los seis.
#
# LA BASE ES DESECHABLE Y SE BORRA. Nada de esto toca 140 ni el espejo.
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
declare -A SALIDA RC TASA
comprueba() {  # $1 = etiqueta   $2 = si|no
  if [ "$2" = si ]; then pasan=$((pasan+1)); printf '  [ok   ] %-66s\n' "$1"
  else fallos=$((fallos+1)); printf '  [FALLA] %-66s\n' "$1"; fi
}
sql() { psql -X -A -t -q -v ON_ERROR_STOP=1 -d "$DB" -c "$1"; }

createdb "$DB" >/dev/null 2>&1 || { echo "NO MEDIDO: no se pudo crear la base desechable $DB"; exit 2; }

# ── EL MUNDO DE MENTIRA ─────────────────────────────────────────────────────────────────────
# Las nueve tablas que K37 declara, con la forma minima que su consulta necesita. Si alguna se
# quedara FUERA, la consulta ni compilaria, y ademas la rama SINTECHO la denunciaria.
#
# Y LAS OCHO QUE NO SON EL SUJETO SE SIEMBRAN COMPLETAS, con un simbolo y sin un solo hueco. La
# primera version las dejo VACIAS -«asi el sujeto es una sola tabla»- y eso las ponia en la rama
# SINSERIE: el check condenaba por ellas, y los brazos que esperaban VERDE fallaban con el sujeto
# correcto delante. Un mundo de mentira tiene que ser INOCENTE en todo lo que no se esta
# midiendo. `liquidations` se queda vacia a proposito: su techo es NA, no produce serie y no
# entra en SINSERIE.
#   · 5 min -> 2016 buckets en la ventana de 7 dias · 1 min -> 10080. Los dos, exactos.
#   · a `long_short_ratio` se le siembra SOLO BTC: si se le sembrara SOL -que tiene excepcion de
#     techo- la excepcion saldria SOBRANTE y volveria a condenar por algo que no es el sujeto.
psql -X -q -v ON_ERROR_STOP=1 -d "$DB" >/dev/null <<'SQL' || { echo "NO MEDIDO: no se pudo montar el mundo"; exit 2; }
CREATE SCHEMA reloj;
CREATE TABLE reloj.ajuste(t timestamptz);
INSERT INTO reloj.ajuste VALUES ('2026-09-19 12:00:00+00');
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
  SELECT g FROM generate_series('2026-09-10 00:00:00+00'::timestamptz,
                                '2026-09-18 23:59:00+00'::timestamptz, interval '1 minute') g;
-- los siete inocentes, completos y sin un hueco
INSERT INTO long_short_ratio        SELECT g,'BTCUSDT_PERP.A','5min' FROM generate_series('2026-09-11 00:00:00+00'::timestamptz,'2026-09-18 23:55:00+00'::timestamptz, interval '5 minutes') g;
INSERT INTO funding_rate            SELECT g,'BTCUSDT_PERP.A','5min' FROM generate_series('2026-09-11 00:00:00+00'::timestamptz,'2026-09-18 23:55:00+00'::timestamptz, interval '5 minutes') g;
INSERT INTO open_interest           SELECT g,'BTCUSDT_PERP.A','5min' FROM generate_series('2026-09-11 00:00:00+00'::timestamptz,'2026-09-18 23:55:00+00'::timestamptz, interval '5 minutes') g;
INSERT INTO oi_bybit                SELECT g,'BTCUSDT_PERP.A','5min' FROM generate_series('2026-09-11 00:00:00+00'::timestamptz,'2026-09-18 23:55:00+00'::timestamptz, interval '5 minutes') g;
INSERT INTO predicted_funding_rate  SELECT g,'BTCUSDT_PERP.A','5min' FROM generate_series('2026-09-11 00:00:00+00'::timestamptz,'2026-09-18 23:55:00+00'::timestamptz, interval '5 minutes') g;
INSERT INTO ohlcv                   SELECT base.ts,'BTCUSDT_PERP.A','1min' FROM base;
INSERT INTO spot_trades_agg         SELECT base.ts,'BTCUSDT_PERP.A','1min' FROM base;
SQL

# EL CANAL DE MENTIRA. K37 llama a "$B/bin/prodsql" y `B` es una constante en su cabecera: se
# copia el check cambiando esa linea, y se comprueba que el sed MORDIO -si no, se estaria
# midiendo contra produccion y el control aprobaria midiendo otra cosa-.
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
# $1 reloj ISO · $2 retraso de la poda en minutos · $3 inicio de la perdida · $4 minutos perdidos
planta() {
  sql "UPDATE reloj.ajuste SET t = '$1'::timestamptz" >/dev/null
  sql "TRUNCATE futures_trades_agg" >/dev/null
  sql "INSERT INTO futures_trades_agg(ts,symbol,\"interval\")
       SELECT ts,'BTCUSDT_PERP.A','1min' FROM base
        WHERE ts >= '$1'::timestamptz - interval '168 hours' - interval '$2 minutes'
          AND NOT (ts >= '$3'::timestamptz
                   AND ts < '$3'::timestamptz + interval '$4 minutes')" >/dev/null
}
huella() { sql "SELECT count(*)||'/'||coalesce(md5(string_agg(ts::text,',' ORDER BY ts)),'-') FROM futures_trades_agg"; }
# LA HUELLA SE COMPRUEBA EN CADA BRAZO, no en un acumulador global al final. La version de la
# entrega anterior guardaba un unico HUELLA_OK y un fallo tardio podia taparse.
corre() {  # $1 = etiqueta
  local a d
  a=$(huella); SALIDA["$1"]=$(timeout -k 5 120 bash "$COPIA" 2>&1); RC["$1"]=$?; d=$(huella)
  TASA["$1"]=$(printf '%s' "${SALIDA[$1]}" | grep -o '[0-9.]* %/dia' | head -1)
  printf '      %-14s reloj=%s retraso=%-6s rc=%s tasa=%-10s min(ts)=%s\n' \
    "$1" "$(sql "SELECT to_char(reloj.now() AT TIME ZONE 'UTC','MM-DD HH24:MI')")" \
    "$2" "${RC[$1]}" "${TASA[$1]:-—}" \
    "$(sql "SELECT to_char(min(ts) AT TIME ZONE 'UTC','MM-DD HH24:MI') FROM futures_trades_agg")"
  [ "$a" = "$d" ] || comprueba "$1 · K37 MOVIO la tabla ($a -> $d)" no
}

PERDIDA='2026-09-16 10:00:00+00'   # bien dentro de los dias medidos en los seis casos
TEMPRANO='2026-09-19 00:30:00+00'  # DENTRO del retraso: es donde se colaba el defecto
TARDE='2026-09-19 12:00:00+00'     # fuera del retraso
echo "K37-control · sujeto: $CHK"
echo "   base desechable: $DB · reloj falso por search_path · dia UTC 2026-09-19"
echo "   dos horas: 00:30Z (dentro del retraso) y 12:00Z · tres retrasos: 0, 55 min y 5 h"
echo

# ── M · LA MATRIZ · la MISMA perdida, seis mundos ───────────────────────────────────────────
# 88 minutos, que es la perdida real del apagon del 09-16. El brazo no pide un veredicto
# concreto: pide que los SEIS sean el mismo.
echo "M · 88 minutos perdidos · 2 horas x 3 retrasos, MISMA perdida y MISMOS minutos absolutos"
for caso in "M1:$TEMPRANO:0" "M2:$TARDE:0" "M3:$TEMPRANO:55" "M4:$TARDE:55" "M5:$TEMPRANO:300" "M6:$TARDE:300"; do
  e=${caso%%:*}; resto=${caso#*:}; reloj=${resto%:*}; lag=${resto##*:}
  planta "$reloj" "$lag" "$PERDIDA" 88; corre "$e" "${lag} min"
done
rc_unicos=$(printf '%s\n' "${RC[M1]}" "${RC[M2]}" "${RC[M3]}" "${RC[M4]}" "${RC[M5]}" "${RC[M6]}" | sort -u | tr '\n' ' ')
ta_unicos=$(printf '%s\n' "${TASA[M1]}" "${TASA[M2]}" "${TASA[M3]}" "${TASA[M4]}" "${TASA[M5]}" "${TASA[M6]}" | sort -u | tr '\n' ' ')
comprueba "Ma EL PUNTO: los SEIS dan el mismo veredicto (rc vistos: $rc_unicos)" \
  "$([ "$(printf '%s' "$rc_unicos" | wc -w)" = 1 ] && echo si || echo no)"
comprueba "Mb y la MISMA tasa, no solo el mismo rc (tasas vistas: $ta_unicos)" \
  "$([ "$(printf '%s\n' "${TASA[M1]}" "${TASA[M2]}" "${TASA[M3]}" "${TASA[M4]}" "${TASA[M5]}" "${TASA[M6]}" | sort -u | grep -c .)" = 1 ] && echo si || echo no)"
comprueba "Mc la pareja que delataba el defecto: 00:30Z y 12:00Z con el retraso MEDIDO (55 min)" \
  "$([ "${RC[M3]}" = "${RC[M4]}" ] && [ "${TASA[M3]}" = "${TASA[M4]}" ] && echo si || echo no)"
comprueba "Md y la de un retraso de HORAS, que es lo que deja un reinicio (5 h)" \
  "$([ "${RC[M5]}" = "${RC[M6]}" ] && [ "${TASA[M5]}" = "${TASA[M6]}" ] && echo si || echo no)"
comprueba "Me la linea dice sobre que dias calculo, en los seis" \
  "$(n=0; for e in M1 M2 M3 M4 M5 M6; do printf '%s' "${SALIDA[$e]}" | grep -q '2026-09-12 a 2026-09-19' && n=$((n+1)); done; [ "$n" = 6 ] && echo si || echo no)"
comprueba "Mf y que a futures_trades_agg le declara una ventana mas corta, en los seis" \
  "$(n=0; for e in M1 M2 M3 M4 M5 M6; do printf '%s' "${SALIDA[$e]}" | grep -q 'futures_trades_agg desde 2026-09-13 (6 dias declarados)' && n=$((n+1)); done; [ "$n" = 6 ] && echo si || echo no)"
comprueba "Mg ninguna tasa sale NEGATIVA (esp y obs sobre el mismo intervalo)" \
  "$(n=0; for e in M1 M2 M3 M4 M5 M6; do printf '%s' "${SALIDA[$e]}" | grep -q -- '-[0-9.]* %/dia' && n=$((n+1)); done; [ "$n" = 0 ] && echo si || echo no)"

# ── N · LA MISMA MATRIZ CON UNA PERDIDA QUE NO PASA EL TECHO ────────────────────────────────
# Sin esto, «los seis coinciden» lo cumpliria un check que condenara siempre.
echo
echo "N · 40 minutos perdidos (por debajo del techo) · la MISMA matriz"
for caso in "N1:$TEMPRANO:0" "N2:$TARDE:0" "N3:$TEMPRANO:55" "N4:$TARDE:55" "N5:$TEMPRANO:300" "N6:$TARDE:300"; do
  e=${caso%%:*}; resto=${caso#*:}; reloj=${resto%:*}; lag=${resto##*:}
  planta "$reloj" "$lag" "$PERDIDA" 40; corre "$e" "${lag} min"
done
comprueba "Na ABSUELVE en los seis (rc: $(printf '%s' "${RC[N1]}${RC[N2]}${RC[N3]}${RC[N4]}${RC[N5]}${RC[N6]}"))" \
  "$(n=0; for e in N1 N2 N3 N4 N5 N6; do [ "${RC[$e]}" = 0 ] && n=$((n+1)); done; [ "$n" = 6 ] && echo si || echo no)"
comprueba "Nb y CONDENA en los seis con la perdida grande: el check sabe decir las dos cosas" \
  "$(n=0; for e in M1 M2 M3 M4 M5 M6; do [ "${RC[$e]}" = 1 ] && n=$((n+1)); done; [ "$n" = 6 ] && echo si || echo no)"
comprueba "Nc y el VERDE tambien dice sobre que dias calculo" \
  "$(printf '%s' "${SALIDA[N4]}" | grep -q 'dias UTC cerrados, 2026-09-12 a 2026-09-19' && echo si || echo no)"

# ── G · LA GUARDA DE COBERTURA · el numero declarado no puede envejecer en silencio ─────────
# La ventana es un numero DECLARADO, o sea una copia de lo que la poda hace. Esto es lo que
# impide que esa copia envejezca: si el dato no llega al suelo declarado, la serie NO se puede
# medir -contaria como perdidos unos buckets que nunca estuvieron- y sale NO MEDIDO, no VERDE.
echo
echo "G · el dato NO cubre los 6 dias declarados (como si alguien bajara la retencion)"
sql "UPDATE reloj.ajuste SET t = '$TARDE'::timestamptz" >/dev/null
sql "TRUNCATE futures_trades_agg" >/dev/null
sql "INSERT INTO futures_trades_agg(ts,symbol,\"interval\")
     SELECT ts,'BTCUSDT_PERP.A','1min' FROM base WHERE ts >= '2026-09-14 06:00:00+00'::timestamptz" >/dev/null
corre G1 "n/a"
comprueba "G1a NO MEDIDO, rc=2 (rc=${RC[G1]}): no se puede medir, y no es ni VERDE ni ROJO" \
  "$([ "${RC[G1]}" = 2 ] && echo si || echo no)"
comprueba "G1b y dice las DOS fechas: donde empieza el dato y donde la ventana declarada" \
  "$(printf '%s' "${SALIDA[G1]}" | grep -q '09-14 06:00' && printf '%s' "${SALIDA[G1]}" | grep -q '09-13 00:00' && echo si || echo no)"

# G2 · Y LO DECIDIBLE VA ANTES (A54): una serie que no se puede medir no se come una condena.
echo
echo "G2 · una serie descubierta JUNTO a otra que SI pasa el techo: manda la condena"
sql "INSERT INTO futures_trades_agg(ts,symbol,\"interval\")
     SELECT ts,'ETHUSDT_PERP.A','1min' FROM base
      WHERE ts >= '$TARDE'::timestamptz - interval '168 hours'
        AND NOT (ts >= '$PERDIDA'::timestamptz AND ts < '$PERDIDA'::timestamptz + interval '300 minutes')" >/dev/null
corre G2 "n/a"
comprueba "G2a ROJO, rc=1 (rc=${RC[G2]}): la condena de ETH no se la come la de BTC" \
  "$([ "${RC[G2]}" = 1 ] && echo si || echo no)"
comprueba "G2b y la descubierta va NOMBRADA en la misma linea" \
  "$(printf '%s' "${SALIDA[G2]}" | grep -q 'sin poder medir' && printf '%s' "${SALIDA[G2]}" | grep -q 'BTCUSDT_PERP.A' && echo si || echo no)"

# ── G3 · EL QUE SE CALLA SIGUE SALIENDO AL 100 % ───────────────────────────────────────────
# La guarda de cobertura podria haberse llevado por delante lo que el universo de 30 dias vino a
# proteger: un simbolo que DEJA de escribir. No se lo lleva, y aqui se comprueba. Su nac es viejo
# -cubre la ventana-, asi que no es «descubierta»: es una serie medible que perdio TODO.
echo
echo "G3 · un simbolo que se CALLA (dato hasta el 09-11 y nada mas) -> 100 % de perdida"
sql "UPDATE reloj.ajuste SET t = '$TARDE'::timestamptz" >/dev/null
sql "TRUNCATE futures_trades_agg" >/dev/null
sql "INSERT INTO futures_trades_agg(ts,symbol,\"interval\")
     SELECT ts,'BTCUSDT_PERP.A','1min' FROM base
      WHERE ts >= '$TARDE'::timestamptz - interval '168 hours'" >/dev/null
sql "INSERT INTO futures_trades_agg(ts,symbol,\"interval\")
     SELECT ts,'MUDOUSDT_PERP.A','1min' FROM base WHERE ts < '2026-09-11 00:00:00+00'::timestamptz" >/dev/null
corre G3 "n/a"
comprueba "G3a ROJO, rc=1 (rc=${RC[G3]})" "$([ "${RC[G3]}" = 1 ] && echo si || echo no)"
comprueba "G3b y el mudo sale al 100 %, NO como «sin poder medir»" \
  "$(printf '%s' "${SALIDA[G3]}" | grep -q 'MUDOUSDT_PERP.A *100.00 %/dia' && echo si || echo no)"

# ── R · EL CONTROL DEL CONTROL ─────────────────────────────────────────────────────────────
echo
echo "R · el control del control: si el reloj o la poda no se movieran, la matriz no mediria nada"
sql "UPDATE reloj.ajuste SET t = '$TEMPRANO'::timestamptz" >/dev/null
t1=$(PGOPTIONS='-c search_path=reloj,public,pg_catalog' psql -X -A -t -q -d "$DB" -c "SELECT now() AT TIME ZONE 'UTC'")
sql "UPDATE reloj.ajuste SET t = '$TARDE'::timestamptz" >/dev/null
t2=$(PGOPTIONS='-c search_path=reloj,public,pg_catalog' psql -X -A -t -q -d "$DB" -c "SELECT now() AT TIME ZONE 'UTC'")
printf '      now() temprano: %s · now() tardio: %s\n' "$t1" "$t2"
comprueba "R1 el reloj falso SI movio now()" "$([ "$t1" != "$t2" ] && echo si || echo no)"
planta "$TEMPRANO" 0 "$PERDIDA" 88;  n0=$(sql "SELECT to_char(min(ts) AT TIME ZONE 'UTC','MM-DD HH24:MI') FROM futures_trades_agg")
planta "$TEMPRANO" 55 "$PERDIDA" 88; n55=$(sql "SELECT to_char(min(ts) AT TIME ZONE 'UTC','MM-DD HH24:MI') FROM futures_trades_agg")
printf '      min(ts) con retraso 0: %s · con 55 min: %s\n' "$n0" "$n55"
comprueba "R2 el retraso SI movio min(ts) de un dia UTC al otro ($n0 -> $n55)" \
  "$([ "$n0" != "$n55" ] && echo si || echo no)"

echo
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
