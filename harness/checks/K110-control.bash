#!/bin/bash
# K110-control · cada brazo de K110 y cada decision de OF-4a que se puede romper, con un plantado que TIENE que fallar.
#
# EL SUJETO ES REAL. K110-flujo.jsonl.xz son 11 min 40 s (2026-10-17 23:41:19-23:52:59Z, desde 143) de los flujos
# PUBLICOS de libro de SOL en binance_usdm (diferencias y fotos REST cada 60 s) y bybit_linear (orderbook.1000): los
# nueve venues y los tres activos no caben en el repo (48 MB en crudo), y K110_VENUES / K110_ACTIVOS lo dicen. Y
# K110-viejo.tsv las filas de orderbook_snapshot que el colector
# VIEJO de 140 -independiente- escribio esos mismos minutos. K110-reproduce.py pasa la grabacion por el codigo REAL del
# colector del arbol con el reloj de la grabacion, y `K110-libro.py sirve` guarda lo que las rutas del arbol sirven.
# Sobre eso, K110 tiene que salir VERDE.
#
# PLANTADOS DE CODIGO (la reproduccion corre con UN defecto inyectado en el proceso; el arbol no se toca):
#   salto_no_detectado · foto_fuera_de_banda · cobertura_rellena
# PLANTADOS DE DATOS (sobre una COPIA de la base buena): un libro cruzado, una cantidad negativa, el nivel de la mejor
#   compra desplazado, niveles fuera del alcance, un hueco sin declarar, un minuto ausente, una cobertura rellenada a
#   mano, una foto sin su fila de cobertura, el otro colector torcido, lo servido torcido (fotos y cobertura), una foto
#   mas vieja que su retencion, la particion de manana ausente, las funciones de particion de antes de OF-4a, el
#   servicio parado.
# NO MEDIDO: sin las tablas (el esquema de main antes de OF-4a, 26b7324), cero filas, el canal caido, poca vida.
# Cada plantado exige su rc, su frase y que la HUELLA del sujeto cambie; al final la base buena tiene su huella de
# antes y el arbol esta como estaba. Despues, las TRES invocaciones (A56) y los DOS modos de SIGPIPE (A89).
set -u
AQUI=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || exit 2
REPO=$(cd -- "$AQUI/../.." && pwd -P) || exit 2
CHK="$AQUI/K110-el-libro.sh"
PY="$REPO/.venv/bin/python"
H=/var/run/postgresql
PID=$$
DB="k110_ctl_${PID}"
ANTES=26b7324  # main justo antes de OF-4a: su esquema no tiene libro_* y sus funciones de particion no gestionan libro_foto
VENUES=binance_usdm,bybit_linear
ACTIVOS=SOL
PARES=40  # 11 min de SOL dan ~60-70 pares por venue; en produccion, 100
[ -r "$CHK" ] && [ -r "$AQUI/K110-flujo.jsonl.xz" ] && [ -r "$AQUI/K110-viejo.tsv" ] || { echo "K110-control: faltan piezas en $AQUI"; exit 2; }
exec 9>/tmp/k110-control.lock
flock -n 9 || { echo "K110-control: otro K110-control esta corriendo; no se pisan"; exit 2; }
T=$(mktemp -d) || exit 2
ARBOL_ANTES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)
limpia() {
  for db in $(psql -h "$H" -d postgres -Atc "SELECT datname FROM pg_database WHERE datname LIKE '${DB}%'"); do
    psql -h "$H" -d postgres -qc "DROP DATABASE IF EXISTS \"$db\" WITH (FORCE)" >/dev/null 2>&1
  done
  quedan=$(psql -h "$H" -d postgres -Atc "SELECT count(*) FROM pg_database WHERE datname LIKE '${DB}%'")
  echo "K110-control: bases ${DB}* que quedan: $quedan"
  rm -rf "$T"
}
trap limpia EXIT
trap 'limpia; trap - EXIT; exit 143' INT TERM

# EL RELOJ: dos minutos despues del ultimo minuto ENTERO de la grabacion, para que la ventana de K110 acabe justo ahi.
FIN=$("$PY" -c "import json, lzma, sys; print(max(json.loads(x)['rx'] for x in lzma.open(sys.argv[1], 'rt')) // 60000 * 60)" "$AQUI/K110-flujo.jsonl.xz")
RELOJ=$("$PY" -c "import sys, datetime as d; print(d.datetime.fromtimestamp(int(sys.argv[1]) + 120, d.UTC).isoformat())" "$FIN")

pasan=0; total=0; fallan=""
comprueba() { total=$((total+1)); if [ "$2" = 0 ]; then pasan=$((pasan+1)); printf '  PASA  %-26s %s\n' "$1" "$3"; else fallan="$fallan $1"; printf '  FALLA %-26s %s\n' "$1" "$3"; fi; }
dsn() { echo "postgresql:///$1?host=$H"; }
en() { psql -h "$H" -d "$1" -v ON_ERROR_STOP=1 -qAt -c "SET TIME ZONE 'UTC'" -c "$2" >/dev/null; }
copia() { psql -h "$H" -d postgres -qc "CREATE DATABASE \"${DB}_$1\" TEMPLATE \"${DB}_$2\"" >/dev/null && echo "${DB}_$1"; }

# LA HUELLA del sujeto: fotos, cobertura, huecos, el colector viejo, las funciones de particion, las particiones y lo
# servido. Cambia si y solo si cambia algo que K110 puede mirar.
huella() {  # $1 = base   $2 = directorio de lo servido   [$3 = reloj]   [$4 = minimo]
  local h
  h=$(psql -h "$H" -d "$1" -Atq -c "SET TIME ZONE 'UTC'" -c "SELECT md5(concat_ws('|',
      (SELECT md5(string_agg(concat_ws(',',ts,venue,symbol,ts_libro,compra,venta,paso,compra_nivel,compras,venta_nivel,ventas,alcance_compra,alcance_venta), ';' ORDER BY symbol,ts,venue)) FROM libro_foto),
      (SELECT md5(string_agg(concat_ws(',',ts,venue,symbol,segundos,fotos,saltos,resincronizaciones,reconexiones), ';' ORDER BY symbol,ts,venue)) FROM libro_cobertura),
      (SELECT md5(string_agg(concat_ws(',',exchange,symbol,start_ts,end_ts,evidence_type,status), ';' ORDER BY exchange,symbol,start_ts)) FROM data_gap),
      (SELECT concat_ws(',', count(*), sum(bid_px), sum(ask_px)) FROM orderbook_snapshot),
      (SELECT md5(string_agg(pg_get_functiondef(oid), ';' ORDER BY proname)) FROM pg_proc WHERE proname LIKE '%temporal_partitions'),
      (SELECT string_agg(relname, ',' ORDER BY relname) FROM pg_class WHERE relname LIKE 'libro_foto_p2%')))" 2>/dev/null)
  { echo "${h:-sinbase}"; cat "$2"/*.json 2>/dev/null; echo "reloj ${3:-$RELOJ} minimo ${4:-10}"; } | sha256sum | cut -c1-16
}
k110() {  # $1 = base   $2 = servido   [$3 = reloj]   [$4 = minimo]  -> rc; salida en $T/sal
  K110_SUJETO=local K110_BASE="$(dsn "$1")" K110_SERVIDO="$2" K110_RELOJ="${3:-$RELOJ}" K110_MINIMO="${4:-10}" \
    K110_VENUES="$VENUES" K110_ACTIVOS="$ACTIVOS" K110_PARES="$PARES" bash "$CHK" > "$T/sal" 2>&1
  echo $?
}
sirve() {  # $1 = base   $2 = directorio
  mkdir -p "$2"
  K110_BASE="$(dsn "$1")" K110_RELOJ="$RELOJ" K110_VENUES="$VENUES" K110_ACTIVOS="$ACTIVOS" "$PY" "$AQUI/K110-libro.py" sirve "$2" > "$T/sirve.log" 2>&1
}
planta() {  # $1 nombre  $2 rc esperado  $3 patron  $4 base  $5 servido  $6 huella de antes  [$7 reloj] [$8 minimo]
  local despues rc visto
  despues=$(huella "$4" "$5" "${7:-$RELOJ}" "${8:-10}")
  rc=$(k110 "$4" "$5" "${7:-$RELOJ}" "${8:-10}")
  visto=$(grep -E -m1 -- "$3" "$T/sal" | cut -c1-110)
  comprueba "$1" "$([ "$rc" = "$2" ] && [ -n "$visto" ] && [ "$6" != "$despues" ] && echo 0 || echo 1)" \
    "rc=$rc · $6 -> $despues · ${visto:-$(head -1 "$T/sal" | cut -c1-110)}"
}

# --- LA BASE VACIA: el esquema del arbol y el colector viejo de 140 ----------------------------------------------
createdb -h "$H" "${DB}_vacia" || exit 2
psql -h "$H" -d "${DB}_vacia" -v ON_ERROR_STOP=1 -q -f "$REPO/sql/schema.sql" > /dev/null 2>&1 || { echo "K110-control: el esquema del arbol no se aplica"; exit 2; }
grep -v '^#' "$AQUI/K110-viejo.tsv" > "$T/viejo.tsv"
psql -h "$H" -d "${DB}_vacia" -v ON_ERROR_STOP=1 -q \
  -c "SELECT ensure_temporal_partitions('$RELOJ', 1, 2)" \
  -c "INSERT INTO market_assets(base_asset) VALUES ('BTC'),('ETH'),('SOL') ON CONFLICT DO NOTHING" \
  -c "INSERT INTO symbols(symbol, base_asset, is_perpetual) VALUES ('BTCUSDT_PERP.A','BTC',true),('ETHUSDT_PERP.A','ETH',true),('SOLUSDT_PERP.A','SOL',true) ON CONFLICT DO NOTHING" \
  -c "CREATE TABLE k110_v(ts timestamptz, symbol text, exchange text, bid_px float8, ask_px float8)" \
  -c "\\copy k110_v FROM '$T/viejo.tsv'" \
  -c "INSERT INTO orderbook_snapshot(ts,symbol,exchange,venue_count,bid_px,ask_px) SELECT ts,symbol,exchange,1,bid_px,ask_px FROM k110_v" \
  -c "DROP TABLE k110_v" > /dev/null || { echo "K110-control: no se cargo el colector viejo"; exit 2; }

# --- LA BASE BUENA: la grabacion por el colector del arbol -------------------------------------------------------
reproduce() {  # $1 = base   [$2 = planta]
  "$PY" "$AQUI/K110-reproduce.py" "$(dsn "$1")" "$AQUI/K110-flujo.jsonl.xz" ${2:+--planta "$2"} > "$T/rep.log" 2>&1
}
B0=$(copia limpia vacia) || exit 2
reproduce "$B0" || { echo "K110-control: la reproduccion fallo: $(tail -2 "$T/rep.log")"; exit 2; }
grep -q "app de $REPO/app/libro.py" "$T/rep.log" || { echo "K110-control: la reproduccion no uso el colector de $REPO: $(tail -3 "$T/rep.log")"; exit 2; }
sirve "$B0" "$T/s0" || { echo "K110-control: sirve fallo: $(tail -2 "$T/sirve.log")"; exit 2; }
H_BUENA=$(huella "$B0" "$T/s0")
rc=$(k110 "$B0" "$T/s0")
comprueba base_verde "$([ "$rc" = 0 ] && grep -q '^VERDE  K110' "$T/sal" && echo 0 || echo 1)" "rc=$rc · $H_BUENA · $(head -1 "$T/sal" | cut -c1-90)"
cp "$T/sal" "$T/sal-base"

# --- PLANTADOS DE CODIGO -----------------------------------------------------------------------------------------
for p in 'salto_no_detectado:^ROJO  K110 \((a|b|c)\)' \
         'foto_fuera_de_banda:\(a\) [0-9]+ de [0-9]+ fotos con mas niveles que la banda' \
         'cobertura_rellena:\(c\) cobertura RELLENADA: [0-9]+ minutos completos sin sus'; do
  nombre=${p%%:*}; patron=${p#*:}
  b=$(copia "$nombre" vacia) || exit 2
  if reproduce "$b" "$nombre" && sirve "$b" "$T/s-$nombre"; then
    planta "codigo_$nombre" 1 "$patron" "$b" "$T/s-$nombre" "$H_BUENA"
  else
    comprueba "codigo_$nombre" 1 "la reproduccion plantada no corrio: $(tail -1 "$T/rep.log")"
  fi
done

# --- PLANTADOS DE DATOS (copias de la buena; lo servido es el bueno salvo donde se tuerce) ------------------------
UNA="(SELECT symbol, ts, venue FROM libro_foto WHERE venue='bybit_linear' AND symbol='SOL' AND cardinality(compras) >= 2 ORDER BY ts LIMIT 1 OFFSET 20)"
b=$(copia cruzado limpia); en "$b" "ALTER TABLE libro_foto DROP CONSTRAINT libro_foto_check"
en "$b" "UPDATE libro_foto SET venta = compra WHERE (symbol, ts, venue) = $UNA"
planta libro_cruzado 1 '\(a\) 1 de [0-9]+ fotos con la mejor compra >= la mejor venta' "$b" "$T/s0" "$H_BUENA"
b=$(copia negativo limpia); en "$b" "ALTER TABLE libro_foto DROP CONSTRAINT libro_foto_compras_check"
en "$b" "UPDATE libro_foto SET compras[2] = -1 WHERE (symbol, ts, venue) = $UNA"
planta cantidad_negativa 1 '\(a\) 1 de [0-9]+ fotos con alguna cantidad negativa' "$b" "$T/s0" "$H_BUENA"
b=$(copia nivel limpia); en "$b" "UPDATE libro_foto SET compra_nivel = compra_nivel - paso WHERE (symbol, ts, venue) = $UNA"
planta nivel_desplazado 1 '\(a\) 1 de [0-9]+ fotos con el nivel de la mejor compra' "$b" "$T/s0" "$H_BUENA"
b=$(copia alcance limpia); en "$b" "UPDATE libro_foto SET alcance_compra = compra_nivel WHERE (symbol, ts, venue) = $UNA"
planta fuera_de_alcance 1 '\(a\) 1 de [0-9]+ fotos con niveles fuera del alcance' "$b" "$T/s0" "$H_BUENA"
b=$(copia hueco limpia); en "$b" "DELETE FROM data_gap WHERE feed='libro' AND exchange='bybit_linear' AND symbol='SOL'"
planta hueco_sin_declarar 1 '\(c\) bybit_linear: [0-9]+ minutos-activo incompletos o ausentes SIN declarar' "$b" "$T/s0" "$H_BUENA"
MIN="(SELECT ts FROM libro_cobertura WHERE venue='binance_usdm' AND symbol='SOL' AND segundos=60 ORDER BY ts LIMIT 1 OFFSET 3)"
b=$(copia ausente limpia); en "$b" "DELETE FROM libro_foto WHERE venue='binance_usdm' AND symbol='SOL' AND date_trunc('minute', ts) = $MIN"
en "$b" "DELETE FROM libro_cobertura WHERE venue='binance_usdm' AND symbol='SOL' AND ts = (SELECT ts FROM libro_cobertura WHERE venue='binance_usdm' AND symbol='SOL' AND segundos=60 ORDER BY ts LIMIT 1 OFFSET 3)"
planta minuto_ausente 1 '\(c\) binance_usdm: 1 minutos-activo incompletos o ausentes SIN declarar en data_gap \(1 sin fila\)' "$b" "$T/s0" "$H_BUENA"
b=$(copia rellenada limpia); en "$b" "UPDATE libro_cobertura SET segundos = 60 WHERE venue='bybit_linear' AND symbol='SOL' AND ts = (SELECT min(ts) FROM libro_cobertura)"
planta cobertura_rellenada 1 '\(c\) cobertura RELLENADA' "$b" "$T/s0" "$H_BUENA"
b=$(copia sinfila limpia); en "$b" "DELETE FROM libro_cobertura WHERE venue='bybit_linear' AND symbol='SOL' AND ts = (SELECT ts FROM libro_cobertura WHERE symbol='SOL' AND segundos=60 ORDER BY ts LIMIT 1)"
planta foto_sin_cobertura 1 '\(c\) cobertura RELLENADA: 1 minutos con fotos y sin fila de cobertura' "$b" "$T/s0" "$H_BUENA"
b=$(copia otro limpia); en "$b" "UPDATE orderbook_snapshot SET bid_px = bid_px * 1.001, ask_px = ask_px * 1.001 WHERE exchange='bybit'"
planta otro_colector_torcido 1 '\(b\) bybit_linear contra orderbook_snapshot/bybit' "$b" "$T/s0" "$H_BUENA"
cp -r "$T/s0" "$T/s-fo"
f=$(grep -l '"que": "las fotos' "$T"/s-fo/*.json | head -1)
"$PY" -c "import json,sys; p=sys.argv[1]; d=json.load(open(p)); x=next(x for x in d['fotos'] if x['compras']); x['compras']['cantidades'][0]=str(__import__('decimal').Decimal(x['compras']['cantidades'][0])+1); json.dump(d,open(p,'w'))" "$f"
planta servido_fotos 1 '\(d\) [A-Z]+ fotos paso .*servido .* != guardado' "$B0" "$T/s-fo" "$H_BUENA"
cp -r "$T/s0" "$T/s-co"
f=$(grep -l '"que": "la cobertura' "$T"/s-co/*.json | head -1)
"$PY" -c "import json,sys; p=sys.argv[1]; d=json.load(open(p)); d['venues'][0]['fotos']+=1; json.dump(d,open(p,'w'))" "$f"
planta servido_cobertura 1 '\(d\) [A-Z]+ cobertura .*servida .* != guardada' "$B0" "$T/s-co" "$H_BUENA"
VIEJA=$("$PY" -c "import sys, datetime as d; print((d.datetime.fromisoformat(sys.argv[1]) - d.timedelta(days=9)).isoformat())" "$RELOJ")
b=$(copia vieja limpia); en "$b" "SELECT ensure_temporal_partitions('$VIEJA', 0, 0)"
en "$b" "INSERT INTO libro_foto SELECT '$VIEJA'::timestamptz, venue, symbol, ts_libro, compra, venta, paso, compra_nivel, compras, venta_nivel, ventas, alcance_compra, alcance_venta FROM libro_foto WHERE (symbol, ts, venue) = $UNA"
planta retencion_vieja 1 '\(e\) 1 fotos mas viejos que su retencion' "$b" "$T/s0" "$H_BUENA"
MANANA=$("$PY" -c "import sys, datetime as d; print((d.datetime.fromisoformat(sys.argv[1]) + d.timedelta(days=1)).strftime('%Y%m%d'))" "$RELOJ")
b=$(copia particion limpia); en "$b" "DROP TABLE libro_foto_p$MANANA"
planta particion_de_manana 1 '\(e\) faltan particiones de hoy o de manana' "$b" "$T/s0" "$H_BUENA"
b=$(copia funcion limpia)
git -C "$REPO" show "$ANTES:sql/schema.sql" > "$T/antes.sql" 2>/dev/null || { echo "K110-control: sin $ANTES en el repo"; exit 2; }
"$PY" - "$T/antes.sql" "$T/funcion.sql" <<'PY'
import sys
s = open(sys.argv[1]).read()
i = s.rindex("CREATE OR REPLACE FUNCTION ensure_temporal_partitions(")
j = s.index("$$;", s.index("AS $$", i)) + 3
open(sys.argv[2], "w").write(s[i:j] + "\n")
PY
psql -h "$H" -d "$b" -q -f "$T/funcion.sql" > /dev/null 2>&1
planta funcion_de_antes 1 '\(e\) las funciones vivas de particion no gestionan libro_foto' "$b" "$T/s0" "$H_BUENA"
PARADO=$("$PY" -c "import sys, datetime as d; print((d.datetime.fromisoformat(sys.argv[1]) + d.timedelta(minutes=15)).isoformat())" "$RELOJ")
planta servicio_parado 1 '\(c\) el servicio no escribe' "$B0" "$T/s0" "$H_BUENA" "$PARADO"

# --- NO MEDIDO -------------------------------------------------------------------------------------------------------
createdb -h "$H" "${DB}_antes" && psql -h "$H" -d "${DB}_antes" -q -f "$T/antes.sql" > /dev/null 2>&1
planta sin_tablas 2 '^NO MEDIDO: FALTA DESPLEGAR' "${DB}_antes" "$T/s0" "$H_BUENA"
planta cero_filas 2 '^NO MEDIDO: las tablas libro_\* estan pero libro_cobertura no tiene ni una fila' "${DB}_vacia" "$T/s0" "$H_BUENA"
planta canal_caido 2 '^NO MEDIDO \(CANAL\)' "${DB}_no_existe" "$T/s0" "$H_BUENA"
planta poca_vida 2 '^NO MEDIDO: el servicio lleva menos de' "$B0" "$T/s0" "$H_BUENA" "$RELOJ" 60

# --- LAS TRES INVOCACIONES Y LOS DOS MODOS DE SIGPIPE (sobre la base buena) -----------------------------------------
ENV=(K110_SUJETO=local "K110_BASE=$(dsn "$B0")" "K110_SERVIDO=$T/s0" "K110_RELOJ=$RELOJ" K110_MINIMO=10 "K110_VENUES=$VENUES" "K110_ACTIVOS=$ACTIVOS" "K110_PARES=$PARES")
inv() { "$@" > "$T/inv" 2>&1; echo "$? $(head -1 "$T/inv" | cut -c1-40)"; }
r1=$(inv env "${ENV[@]}" bash "$CHK")
r2=$(cd "$REPO" && inv env "${ENV[@]}" bash harness/checks/K110-el-libro.sh)
r3=$(cd /tmp && inv env "${ENV[@]}" bash "$CHK")
for r in "$r1" "$r2" "$r3"; do case "$r" in "0 VERDE  K110"*) ;; *) bad=1 ;; esac; done
comprueba tres_invocaciones "${bad:-0}" "absoluta: $r1 · relativa: $r2 · ajena: $r3"
for m in --ignore-signal=PIPE --default-signal=PIPE; do
  env $m "${ENV[@]}" bash "$CHK" > "$T/sp" 2>&1; rc=$?
  comprueba "sigpipe$m" "$([ "$rc" = 0 ] && head -1 "$T/sp" | grep -q '^VERDE  K110' && ! grep -qi 'broken pipe' "$T/sp" && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sp" | cut -c1-60)"
done

# --- LO QUE TIENE QUE QUEDAR COMO ESTABA ------------------------------------------------------------------------------
H_FIN=$(huella "$B0" "$T/s0")
comprueba escenario_restaurado "$([ "$H_FIN" = "$H_BUENA" ] && echo 0 || echo 1)" "$H_BUENA -> $H_FIN"
ARBOL_DESPUES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)
comprueba arbol_intacto "$([ "$ARBOL_ANTES" = "$ARBOL_DESPUES" ] && echo 0 || echo 1)" "git status $ARBOL_ANTES -> $ARBOL_DESPUES"
echo "--- la salida de K110 sobre la base buena (reloj $RELOJ):"
cut -c1-220 "$T/sal-base"
echo "K110-control: $pasan de $total${fallan:+ · FALLAN:$fallan}"
[ "$pasan" = "$total" ]
