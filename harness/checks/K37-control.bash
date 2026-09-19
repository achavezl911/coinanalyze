#!/usr/bin/env bash
# K37-control · ¿el veredicto de K37 depende de algo que no es la perdida?
#
#     bash harness/checks/K37-control.bash
#
# EL PUNTO, EN TRES EJES. La MISMA perdida daba veredictos distintos segun
#   1) LA HORA del dia UTC a la que se corriera K37,
#   2) CUANTO FUERA POR DETRAS LA PODA de la tabla, y
#   3) DONDE CAYERA la perdida: si tocaba el suelo de la ventana, el hueco se volvia el
#      `min(ts)` y una perdida se leia como «el dato no llega».
# Y ademas un simbolo callado MAS que la retencion se quedaba sin filas y DESAPARECIA del
# universo, con lo que callarse mas tiempo salia VERDE.
#
# LA CAUSA ES UNA SOLA: en una tabla PODADA, `min(ts)` no es el nacimiento de nada. Es donde
# llego la ultima poda, o donde empieza el primer hueco que se ha tragado. La poda real es
# `cleanup()` de app/scalp_collector.py:1570-1583, un `sleep(3600)` en bucle desde que arranca
# el colector, asi que va por detras del corte teorico entre 0 y 60 min, y HORAS tras un
# reinicio. MEDIDO contra 140 el 2026-09-19T15:01:19Z: min(ts) 09-12 14:07, corte 09-12 15:01,
# retraso 54.3 min, con el colector arrancado a las 03:06:08Z -poda al minuto :06-.
#
# POR ESO UN FEED PODADO DECLARA DE QUE TABLA SIN PODA salen su universo y su nacimiento, y esos
# son los unicos `min(ts)` que K37 lee. Aqui se ataca por los tres ejes y por el universo.
#
# COMO SE MUEVE EL RELOJ: una funcion `now()` propia DELANTE de `pg_catalog` en el `search_path`.
# COMO SE MUEVE LA PODA: cada plantado rellena desde una tabla PRISTINA aplicando
# `ts >= reloj - 168h - retraso`, que es lo que produccion tendria a esa hora con esa poda. LA
# PODA SE LE APLICA A TODOS LOS SIMBOLOS, sano y mudo: produccion borra por `ts`, no por simbolo,
# y un mundo donde el mudo conserva filas que la poda ya se llevo no puede darse (A57).
# COMO SE LEE LA RETENCION: K37 la pide por `bin/prod`; aqui se le da un `bin/prod` de mentira
# que devuelve el valor que cada brazo quiera.
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
  if [ "$2" = si ]; then pasan=$((pasan+1)); printf '  [ok   ] %-70s\n' "$1"
  else fallos=$((fallos+1)); printf '  [FALLA] %-70s\n' "$1"; fi
}
sql() { psql -X -A -t -q -v ON_ERROR_STOP=1 -d "$DB" -c "$1"; }

createdb "$DB" >/dev/null 2>&1 || { echo "NO MEDIDO: no se pudo crear la base desechable $DB"; exit 2; }

# ── EL MUNDO DE MENTIRA ─────────────────────────────────────────────────────────────────────
# Las nueve tablas declaradas, con la forma minima que la consulta necesita. Las que NO son el
# sujeto se siembran COMPLETAS: un mundo de mentira tiene que ser INOCENTE en todo lo que no se
# esta midiendo, o el check condena por ellas y los brazos fallan con el sujeto correcto delante.
# `liquidations` se queda vacia: su techo es NA, no produce serie y no entra en SINSERIE.
# `base` llega hasta el 08-19 porque `ohlcv` -la fuente del universo de futures- tiene que
# guardar los 30 dias que el universo dice mirar, y K37 lo comprueba.
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
CREATE TABLE base(ts timestamptz);
INSERT INTO base
  SELECT g FROM generate_series('2026-08-19 00:00:00+00'::timestamptz,
                                '2026-09-18 23:59:00+00'::timestamptz, interval '1 minute') g;
CREATE INDEX ON base(ts);
CREATE INDEX ON futures_trades_agg(symbol, ts);
CREATE INDEX ON ohlcv(symbol, ts);
INSERT INTO long_short_ratio        SELECT g,'BTCUSDT_PERP.A','5min' FROM generate_series('2026-08-19 00:00:00+00'::timestamptz,'2026-09-18 23:55:00+00'::timestamptz, interval '5 minutes') g;
INSERT INTO funding_rate            SELECT g,'BTCUSDT_PERP.A','5min' FROM generate_series('2026-08-19 00:00:00+00'::timestamptz,'2026-09-18 23:55:00+00'::timestamptz, interval '5 minutes') g;
INSERT INTO open_interest           SELECT g,'BTCUSDT_PERP.A','5min' FROM generate_series('2026-08-19 00:00:00+00'::timestamptz,'2026-09-18 23:55:00+00'::timestamptz, interval '5 minutes') g;
INSERT INTO oi_bybit                SELECT g,'BTCUSDT_PERP.A','5min' FROM generate_series('2026-08-19 00:00:00+00'::timestamptz,'2026-09-18 23:55:00+00'::timestamptz, interval '5 minutes') g;
INSERT INTO predicted_funding_rate  SELECT g,'BTCUSDT_PERP.A','5min' FROM generate_series('2026-08-19 00:00:00+00'::timestamptz,'2026-09-18 23:55:00+00'::timestamptz, interval '5 minutes') g;
INSERT INTO spot_trades_agg         SELECT base.ts,'BTCUSDT_PERP.A','1min' FROM base;
SQL

# EL CANAL DE MENTIRA. K37 llama a "$B/bin/prodsql" y a "$B/bin/prod", y `B` es una constante en
# su cabecera: se copia el check cambiando esa linea, y se comprueba que el sed MORDIO.
mkdir -p "$DIR/bin"
cat > "$DIR/bin/prodsql" <<EOF
#!/bin/sh
PGOPTIONS='-c search_path=reloj,public,pg_catalog -c timezone=UTC' \\
  exec psql -X -A -F'|' -t -v ON_ERROR_STOP=1 -q -d "$DB" -c "\$*"
EOF
# El `prod` de mentira contesta lo que diga $DIR/retencion, y solo a la pregunta del entorno:
# asi el brazo elige el valor y se puede ver caer la comprobacion de la retencion.
cat > "$DIR/bin/prod" <<EOF
#!/bin/sh
case "\$*" in
  *coinalyze.env*) cat "$DIR/retencion" 2>/dev/null ;;
  *) exit 1 ;;
esac
EOF
chmod +x "$DIR/bin/prodsql" "$DIR/bin/prod"
printf 'SCALP_MINUTE_RETENTION_HOURS=168\n' > "$DIR/retencion"
COPIA="$DIR/K37.sh"
sed "s#^B=/srv/coinanalyze/harness\$#B=$DIR#" "$CHK" > "$COPIA"
if cmp -s "$CHK" "$COPIA"; then echo "NO MEDIDO: el sed del canal NO mordio"; exit 2; fi
grep -q "^B=$DIR\$" "$COPIA" || { echo "NO MEDIDO: la copia no apunta al canal de mentira"; exit 2; }

# ── LOS PLANTADOS ───────────────────────────────────────────────────────────────────────────
# `universo` rellena ohlcv -la fuente declarada del universo y del nacimiento de futures- con los
# simbolos que el brazo necesite, completa y desde el 08-19. NO se le aplica la poda: ohlcv es la
# tabla SIN poda, y que lo sea es justo lo que la hace servir.
universo() {  # $@ = simbolos
  sql "TRUNCATE ohlcv" >/dev/null
  for s in "$@"; do
    sql "INSERT INTO ohlcv SELECT base.ts,'$s','1min' FROM base" >/dev/null
  done
}
# `planta` rellena futures desde la pristina aplicando la poda del reloj, y quita la perdida.
# $1 reloj · $2 retraso (min) · $3 inicio de la perdida · $4 minutos perdidos · $5.. simbolos
planta() {
  local reloj="$1" lag="$2" ini="$3" mins="$4"; shift 4
  sql "UPDATE reloj.ajuste SET t = '$reloj'::timestamptz" >/dev/null
  sql "TRUNCATE futures_trades_agg" >/dev/null
  for s in "$@"; do
    sql "INSERT INTO futures_trades_agg(ts,symbol,\"interval\")
         SELECT ts,'$s','1min' FROM base
          WHERE ts >= '$reloj'::timestamptz - interval '168 hours' - interval '$lag minutes'
            AND NOT ('$s' = '$PERDEDOR' AND ts >= '$ini'::timestamptz
                     AND ts < '$ini'::timestamptz + interval '$mins minutes')" >/dev/null
  done
}
huella() { sql "SELECT count(*)||'/'||coalesce(md5(string_agg(ts::text||symbol,',' ORDER BY ts,symbol)),'-') FROM futures_trades_agg"; }
# LA HUELLA SE COMPRUEBA EN CADA BRAZO, no en un acumulador global al final.
corre() {  # $1 = etiqueta  $2 = nota
  local a d
  a=$(huella); SALIDA["$1"]=$(timeout -k 5 180 bash "$COPIA" 2>&1); RC["$1"]=$?; d=$(huella)
  TASA["$1"]=$(printf '%s' "${SALIDA[$1]}" | grep -o '[0-9.]* %/dia' | head -1)
  printf '      %-4s %-26s rc=%s tasa=%-10s min(ts) futures=%s\n' \
    "$1" "$2" "${RC[$1]}" "${TASA[$1]:-—}" \
    "$(sql "SELECT coalesce(to_char(min(ts) AT TIME ZONE 'UTC','MM-DD HH24:MI'),'(vacia)') FROM futures_trades_agg")"
  [ "$a" = "$d" ] || comprueba "$1 · K37 MOVIO la tabla ($a -> $d)" no
}
iguales() {  # $1 = etiqueta del brazo  resto = etiquetas a comparar
  local etq="$1"; shift
  local rcs tas
  rcs=$(for e in "$@"; do printf '%s\n' "${RC[$e]}"; done | sort -u | tr '\n' ' ')
  tas=$(for e in "$@"; do printf '%s\n' "${TASA[$e]}"; done | sort -u | grep -c .)
  comprueba "$etq (rc vistos: $rcs · tasas distintas: $tas)" \
    "$([ "$(printf '%s' "$rcs" | wc -w)" = 1 ] && [ "$tas" = 1 ] && echo si || echo no)"
}

PERDEDOR='BTCUSDT_PERP.A'
TEMPRANO='2026-09-19 00:30:00+00'
TARDE='2026-09-19 12:00:00+00'
NOCHE='2026-09-19 23:30:00+00'
LEJOS='2026-09-16 10:00:00+00'        # perdida LEJOS del suelo
SUELO='2026-09-12 23:00:00+00'        # perdida QUE TOCA el suelo (09-13 00:00)
echo "K37-control · sujeto: $CHK"
echo "   base desechable: $DB · reloj falso por search_path · dia UTC 2026-09-19"
echo "   universo y nacimiento de futures: ohlcv (sin poda, desde el 08-19)"
echo

# ── M · LA MATRIZ · perdida LEJOS del suelo · 2 horas x 3 retrasos ──────────────────────────
universo BTCUSDT_PERP.A
echo "M · 88 min perdidos LEJOS del suelo (09-16) · 00:30Z y 12:00Z x retraso 0 / 55 / 300 min"
for caso in "M1:$TEMPRANO:0" "M2:$TARDE:0" "M3:$TEMPRANO:55" "M4:$TARDE:55" "M5:$TEMPRANO:300" "M6:$TARDE:300"; do
  e=${caso%%:*}; r=${caso#*:}; reloj=${r%:*}; lag=${r##*:}
  planta "$reloj" "$lag" "$LEJOS" 88 "$PERDEDOR"; corre "$e" "reloj ${reloj:11:5} retraso ${lag}m"
done
iguales "Ma EL PUNTO: los SEIS dan el mismo veredicto y la misma tasa" M1 M2 M3 M4 M5 M6
comprueba "Mb la linea dice sobre que dias calculo, en los seis" \
  "$(n=0; for e in M1 M2 M3 M4 M5 M6; do printf '%s' "${SALIDA[$e]}" | grep -q '2026-09-12 a 2026-09-19' && n=$((n+1)); done; [ "$n" = 6 ] && echo si || echo no)"
comprueba "Mc y que futures_trades_agg declara 6 dias, en los seis" \
  "$(n=0; for e in M1 M2 M3 M4 M5 M6; do printf '%s' "${SALIDA[$e]}" | grep -q 'futures_trades_agg desde 2026-09-13 (6 dias declarados)' && n=$((n+1)); done; [ "$n" = 6 ] && echo si || echo no)"
comprueba "Md ninguna tasa sale NEGATIVA" \
  "$(n=0; for e in M1 M2 M3 M4 M5 M6; do printf '%s' "${SALIDA[$e]}" | grep -q -- '-[0-9.]* %/dia' && n=$((n+1)); done; [ "$n" = 0 ] && echo si || echo no)"

# ── P · LA PERDIDA QUE TOCA EL SUELO (COLA 128, remate 2) ───────────────────────────────────
# 240 min desde el 09-12 23:00Z: 180 de ellos caen DENTRO de [09-13, 09-19). Cuando la poda entra
# en ese hueco, el hueco se volvia el `min(ts)` y la serie salia «sin cubrir la ventana» -NO
# MEDIDO- a unas horas y ROJO a otras, con la MISMA perdida. La hora y el retraso, por separado.
echo
echo "P · 240 min perdidos TOCANDO el suelo (09-12 23:00, 180 dentro de la ventana)"
for caso in "P1:$TARDE:0" "P2:$NOCHE:0" "P3:$NOCHE:55" "P4:$TARDE:55"; do
  e=${caso%%:*}; r=${caso#*:}; reloj=${r%:*}; lag=${r##*:}
  planta "$reloj" "$lag" "$SUELO" 240 "$PERDEDOR"; corre "$e" "reloj ${reloj:11:5} retraso ${lag}m"
done
iguales "Pa EL PUNTO: la perdida EN el suelo da lo mismo a las 4 combinaciones" P1 P2 P3 P4
comprueba "Pb y CONDENA (no «no se puede medir»): rc=1 en las cuatro" \
  "$(n=0; for e in P1 P2 P3 P4; do [ "${RC[$e]}" = 1 ] && n=$((n+1)); done; [ "$n" = 4 ] && echo si || echo no)"
comprueba "Pc y ninguna dice que el dato no cubra la ventana" \
  "$(n=0; for e in P1 P2 P3 P4; do printf '%s' "${SALIDA[$e]}" | grep -qi 'no cubre la ventana\|aun no han vivido' && n=$((n+1)); done; [ "$n" = 0 ] && echo si || echo no)"

echo
echo "P5/P6 · una perdida EN el suelo que NO pasa el techo: absuelve a las dos horas"
for caso in "P5:$TARDE:0" "P6:$NOCHE:0"; do
  e=${caso%%:*}; r=${caso#*:}; reloj=${r%:*}; lag=${r##*:}
  planta "$reloj" "$lag" '2026-09-12 23:30:00+00' 60 "$PERDEDOR"; corre "$e" "reloj ${reloj:11:5} retraso ${lag}m"
done
comprueba "Pd ABSUELVE en las dos (rc ${RC[P5]} y ${RC[P6]}): el check sabe decir que no" \
  "$([ "${RC[P5]}" = 0 ] && [ "${RC[P6]}" = 0 ] && echo si || echo no)"

# ── Q · EL SIMBOLO QUE SE CALLA · MENOS y MAS que la retencion ──────────────────────────────
# En futures_trades_agg no hay 30 dias, hay 168 h: un simbolo callado mas que eso se quedaba sin
# filas y desaparecia del universo, asi que callarse MAS tiempo salia VERDE. El universo sale
# ahora de ohlcv. AL MUDO SE LE APLICA LA MISMA PODA QUE AL SANO: produccion borra por `ts`.
echo
echo "Q · un simbolo MUDO junto a uno sano · reloj 12:00Z, retraso 0"
# EL BASAL VA CON EL UNIVERSO DE UN SOLO SIMBOLO, y no es un detalle. La primera version metia al
# mudo en el universo ANTES de medir el basal, asi que el basal ya salia ROJO al 100 % por el
# mudo que todavia no habia plantado: un «control positivo» que no podia dar VERDE no controla
# nada. El universo se ensancha cuando entra el mudo, no antes.
universo BTCUSDT_PERP.A
sql "UPDATE reloj.ajuste SET t = '$TARDE'::timestamptz" >/dev/null
sql "TRUNCATE futures_trades_agg" >/dev/null
sql "INSERT INTO futures_trades_agg SELECT base.ts,'BTCUSDT_PERP.A','1min' FROM base
      WHERE base.ts >= '$TARDE'::timestamptz - interval '168 hours'" >/dev/null
corre Q0 "solo el sano"
comprueba "Qa el montaje ABSUELVE lo sano (rc=${RC[Q0]})" "$([ "${RC[Q0]}" = 0 ] && echo si || echo no)"

universo BTCUSDT_PERP.A MUDOUSDT_PERP.A
sql "TRUNCATE futures_trades_agg" >/dev/null
sql "INSERT INTO futures_trades_agg SELECT base.ts,'BTCUSDT_PERP.A','1min' FROM base
      WHERE base.ts >= '$TARDE'::timestamptz - interval '168 hours'" >/dev/null
sql "INSERT INTO futures_trades_agg SELECT base.ts,'MUDOUSDT_PERP.A','1min' FROM base
      WHERE base.ts >= '$TARDE'::timestamptz - interval '168 hours'
        AND base.ts < '2026-09-15 00:00:00+00'::timestamptz" >/dev/null
corre Q1 "mudo desde el 09-15"
comprueba "Qb mudez CORTA (dentro de la retencion): CONDENA y lo nombra" \
  "$([ "${RC[Q1]}" = 1 ] && printf '%s' "${SALIDA[Q1]}" | grep -q 'MUDOUSDT_PERP.A' && echo si || echo no)"

sql "DELETE FROM futures_trades_agg WHERE symbol='MUDOUSDT_PERP.A'" >/dev/null
sql "INSERT INTO futures_trades_agg SELECT base.ts,'MUDOUSDT_PERP.A','1min' FROM base
      WHERE base.ts >= '$TARDE'::timestamptz - interval '168 hours'
        AND base.ts < '2026-09-11 00:00:00+00'::timestamptz" >/dev/null
corre Q2 "mudo desde el 09-11 (la poda no le deja NI UNA fila)"
comprueba "Qc EL PUNTO: mudez LARGA (mas que la retencion) NO sale VERDE (rc=${RC[Q2]})" \
  "$([ "${RC[Q2]}" != 0 ] && echo si || echo no)"
comprueba "Qd y sale al 100 %, con su nombre" \
  "$(printf '%s' "${SALIDA[Q2]}" | grep -q 'MUDOUSDT_PERP.A *100.00 %/dia' && echo si || echo no)"
comprueba "Qe el mudo largo no tiene NI UNA fila: el mundo es el que la poda permite (A57)" \
  "$([ "$(sql "SELECT count(*) FROM futures_trades_agg WHERE symbol='MUDOUSDT_PERP.A'")" = 0 ] && echo si || echo no)"

# ── N · EL RECIEN NACIDO · lo que la guarda SI tiene que tapar ──────────────────────────────
# Un simbolo que aun no ha vivido la ventana no se puede medir sobre ella. Su nacimiento sale de
# ohlcv, que no se poda, asi que esto no depende de la hora.
echo
echo "N · un simbolo NACIDO el 09-17, con el sano al lado"
sql "TRUNCATE ohlcv" >/dev/null
sql "INSERT INTO ohlcv SELECT base.ts,'BTCUSDT_PERP.A','1min' FROM base" >/dev/null
sql "INSERT INTO ohlcv SELECT base.ts,'NUEVOUSDT_PERP.A','1min' FROM base WHERE base.ts >= '2026-09-17 00:00:00+00'::timestamptz" >/dev/null
for caso in "N1:$TARDE" "N2:$NOCHE"; do
  e=${caso%%:*}; reloj=${caso#*:}
  sql "UPDATE reloj.ajuste SET t = '$reloj'::timestamptz" >/dev/null
  sql "TRUNCATE futures_trades_agg" >/dev/null
  sql "INSERT INTO futures_trades_agg SELECT base.ts,'BTCUSDT_PERP.A','1min' FROM base
        WHERE base.ts >= '$reloj'::timestamptz - interval '168 hours'" >/dev/null
  sql "INSERT INTO futures_trades_agg SELECT base.ts,'NUEVOUSDT_PERP.A','1min' FROM base
        WHERE base.ts >= '2026-09-17 00:00:00+00'::timestamptz" >/dev/null
  corre "$e" "reloj ${reloj:11:5}"
done
comprueba "Na el recien nacido sale NO MEDIDO, no ROJO (rc ${RC[N1]} y ${RC[N2]})" \
  "$([ "${RC[N1]}" = 2 ] && [ "${RC[N2]}" = 2 ] && echo si || echo no)"
comprueba "Nb con su nombre y sus dos fechas, a las dos horas" \
  "$(n=0; for e in N1 N2; do printf '%s' "${SALIDA[$e]}" | grep -q 'NUEVOUSDT_PERP.A' \
     && printf '%s' "${SALIDA[$e]}" | grep -q 'aun no han vivido la ventana' && n=$((n+1)); done; [ "$n" = 2 ] && echo si || echo no)"

# ── U · LA FUENTE DEL UNIVERSO, COMPROBADA ──────────────────────────────────────────────────
echo
echo "U · si la fuente del universo dejara de guardar 30 dias, el mudo volveria a desaparecer"
sql "TRUNCATE ohlcv" >/dev/null
sql "INSERT INTO ohlcv SELECT base.ts,'BTCUSDT_PERP.A','1min' FROM base WHERE base.ts >= '2026-09-05 00:00:00+00'::timestamptz" >/dev/null
sql "UPDATE reloj.ajuste SET t = '$TARDE'::timestamptz" >/dev/null
sql "TRUNCATE futures_trades_agg" >/dev/null
sql "INSERT INTO futures_trades_agg SELECT base.ts,'BTCUSDT_PERP.A','1min' FROM base
      WHERE base.ts >= '$TARDE'::timestamptz - interval '168 hours'" >/dev/null
corre U1 "ohlcv solo desde el 09-05"
comprueba "Ua NO MEDIDO, rc=2 (rc=${RC[U1]}): la fuente del universo se quedo corta" \
  "$([ "${RC[U1]}" = 2 ] && echo si || echo no)"
comprueba "Ub y lo dice con la tabla y la fecha" \
  "$(printf '%s' "${SALIDA[U1]}" | grep -q 'fuente del universo se quedo corta' \
   && printf '%s' "${SALIDA[U1]}" | grep -q 'ohlcv' && echo si || echo no)"

# ── R · LA RETENCION, LEIDA DE QUIEN LA APLICA ──────────────────────────────────────────────
echo
echo "R · el numero de dias declarado contra la retencion que de verdad se aplica"
universo BTCUSDT_PERP.A
sql "TRUNCATE futures_trades_agg" >/dev/null
sql "INSERT INTO futures_trades_agg SELECT base.ts,'BTCUSDT_PERP.A','1min' FROM base
      WHERE base.ts >= '$TARDE'::timestamptz - interval '168 hours'" >/dev/null
corre R1 "retencion 168 h"
comprueba "Ra con 168 h la declaracion se sostiene y la linea DICE de donde salio el valor" \
  "$([ "${RC[R1]}" = 0 ] && printf '%s' "${SALIDA[R1]}" | grep -q 'SCALP_MINUTE_RETENTION_HOURS=168 h leido de el entorno de 140' && echo si || echo no)"
printf 'SCALP_MINUTE_RETENTION_HOURS=72\n' > "$DIR/retencion"
corre R2 "retencion bajada a 72 h"
comprueba "Rb si alguien la baja a 72 h, los 6 dias declarados dejan de sostenerse: NO MEDIDO (rc=${RC[R2]})" \
  "$([ "${RC[R2]}" = 2 ] && echo si || echo no)"
comprueba "Rc y lo dice con el ajuste, el valor y los dias que sostiene" \
  "$(printf '%s' "${SALIDA[R2]}" | grep -q 'SCALP_MINUTE_RETENTION_HOURS=72 h sostiene 2 dias' && echo si || echo no)"
printf 'SCALP_MINUTE_RETENTION_HOURS=168\n' > "$DIR/retencion"

# ── EL CONTROL DEL CONTROL ─────────────────────────────────────────────────────────────────
echo
echo "C · el control del control: si el reloj o la poda no se movieran, la matriz no mediria nada"
sql "UPDATE reloj.ajuste SET t = '$TEMPRANO'::timestamptz" >/dev/null
t1=$(PGOPTIONS='-c search_path=reloj,public,pg_catalog' psql -X -A -t -q -d "$DB" -c "SELECT now() AT TIME ZONE 'UTC'")
sql "UPDATE reloj.ajuste SET t = '$NOCHE'::timestamptz" >/dev/null
t2=$(PGOPTIONS='-c search_path=reloj,public,pg_catalog' psql -X -A -t -q -d "$DB" -c "SELECT now() AT TIME ZONE 'UTC'")
printf '      now() temprano: %s · now() nocturno: %s\n' "$t1" "$t2"
comprueba "C1 el reloj falso SI movio now()" "$([ "$t1" != "$t2" ] && echo si || echo no)"
planta "$NOCHE" 0 "$SUELO" 240 "$PERDEDOR";  n0=$(sql "SELECT to_char(min(ts) AT TIME ZONE 'UTC','MM-DD HH24:MI') FROM futures_trades_agg")
planta "$NOCHE" 55 "$SUELO" 240 "$PERDEDOR"; n55=$(sql "SELECT to_char(min(ts) AT TIME ZONE 'UTC','MM-DD HH24:MI') FROM futures_trades_agg")
printf '      con la perdida EN el suelo, min(ts) a las 23:30Z: retraso 0 -> %s · retraso 55 -> %s\n' "$n0" "$n55"
comprueba "C2 el plantado SI reproduce el fenomeno: el hueco mueve min(ts) de un dia UTC al otro" \
  "$([ "$n0" != "$n55" ] && echo si || echo no)"

echo
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
