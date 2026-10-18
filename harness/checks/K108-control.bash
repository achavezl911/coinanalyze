#!/bin/bash
# K108-control · cada brazo de K108 y cada decision de OF-1 que se puede romper, con un plantado que TIENE que fallar.
#
# EL SUJETO ES REAL. K108-flujo.jsonl.gz son 15 min de los nueve flujos publicos (2026-10-17 04:02-04:17Z, 64 959
# mensajes) y K108-agregados.tsv las filas de spot/futures_trades_agg que los colectores de 140 -independientes-
# escribieron esos mismos minutos. K108-reproduce.py pasa la grabacion por el codigo REAL del colector del arbol
# (interpreta, Almacen, Cobertura, vuelca) con el reloj de la grabacion, y `K108-orderflow.py sirve` guarda lo que
# las rutas del arbol sirven. Sobre eso, K108 tiene que salir VERDE.
#
# PLANTADOS DE CODIGO (la reproduccion corre con UN defecto inyectado en el proceso; el arbol no se toca):
#   agresor_okx_swap · nivel_float · doble_escritura · minuto_partido
# PLANTADOS DE DATOS (sobre una COPIA de la base buena): una celda alterada, un negativo, un hueco sin declarar, un
#   minuto ausente, el otro colector torcido, lo servido torcido (footprint y value area), una fila mas vieja que su
#   retencion, la particion de manana ausente, las funciones de particion de antes de OF-1, el servicio parado.
# OF-3 (campana 143), lo servido de los perfiles: una VAH de sesion movida, una letra de TPO en otro periodo, el VWAP
#   con otra cuenta (el precio del nivel) y la sesion que cruza la medianoche partida en dos (estos dos, con el
#   defecto inyectado en la ruta del arbol al servir); y un sujeto anterior a OF-3, que tiene que salir VERDE con
#   «(d) OF-3: SIN JUZGAR».
# NO MEDIDO: sin las tablas (el esquema de antes de OF-1, d641818), cero filas, el canal caido, poca vida.
# Cada plantado exige su rc, su frase y que la HUELLA del sujeto cambie (un plantado que no mueve nada no prueba
# nada); al final la base buena tiene su huella de antes y el arbol esta como estaba. Despues, las TRES
# invocaciones (A56) y los DOS modos de SIGPIPE (A89).
set -u
AQUI=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || exit 2
REPO=$(cd -- "$AQUI/../.." && pwd -P) || exit 2
CHK="$AQUI/K108-el-dato-del-order-flow.sh"
PY="$REPO/.venv/bin/python"
H=/var/run/postgresql
PID=$$
DB="k108_ctl_${PID}"
RELOJ=2026-10-17T04:20:00+00:00
ANTES=d641818  # main justo antes de OF-1: su esquema no tiene las tablas y sus funciones de particion gestionan cinco
[ -r "$CHK" ] && [ -r "$AQUI/K108-flujo.jsonl.gz" ] && [ -r "$AQUI/K108-agregados.tsv" ] || { echo "K108-control: faltan piezas en $AQUI"; exit 2; }
exec 9>/tmp/k108-control.lock
flock -n 9 || { echo "K108-control: otro K108-control esta corriendo; no se pisan"; exit 2; }
T=$(mktemp -d) || exit 2
ARBOL_ANTES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)
limpia() {
  for db in $(psql -h "$H" -d postgres -Atc "SELECT datname FROM pg_database WHERE datname LIKE '${DB}%'"); do
    psql -h "$H" -d postgres -qc "DROP DATABASE IF EXISTS \"$db\" WITH (FORCE)" >/dev/null 2>&1
  done
  quedan=$(psql -h "$H" -d postgres -Atc "SELECT count(*) FROM pg_database WHERE datname LIKE '${DB}%'")
  echo "K108-control: bases ${DB}* que quedan: $quedan"
  rm -rf "$T"
}
trap limpia EXIT
trap 'limpia; trap - EXIT; exit 143' INT TERM

pasan=0; total=0; fallan=""
comprueba() { total=$((total+1)); if [ "$2" = 0 ]; then pasan=$((pasan+1)); printf '  PASA  %-24s %s\n' "$1" "$3"; else fallan="$fallan $1"; printf '  FALLA %-24s %s\n' "$1" "$3"; fi; }
dsn() { echo "postgresql:///$1?host=$H"; }
en() { psql -h "$H" -d "$1" -v ON_ERROR_STOP=1 -qAt -c "SET TIME ZONE 'UTC'" -c "$2" >/dev/null; }
copia() { psql -h "$H" -d postgres -qc "CREATE DATABASE \"${DB}_$1\" TEMPLATE \"${DB}_$2\"" >/dev/null && echo "${DB}_$1"; }

# LA HUELLA del sujeto: las cuatro tablas, sus huecos, los agregados, las funciones de particion, las particiones y lo
# servido. Cambia si y solo si cambia algo que K108 puede mirar.
huella() {  # $1 = base   $2 = directorio de lo servido   [$3 = reloj]   [$4 = minimo]
  local h
  h=$(psql -h "$H" -d "$1" -Atq -c "SET TIME ZONE 'UTC'" -c "SELECT md5(concat_ws('|',
      (SELECT md5(string_agg(concat_ws(',',ts,venue,symbol,nivel,compra_base,venta_base,compra_usd,venta_usd,compras,ventas), ';' ORDER BY symbol,ts,venue,nivel)) FROM orderflow_celda),
      (SELECT md5(string_agg(concat_ws(',',ts,venue,symbol,segundos,operaciones,tardias,fuera,definitivo), ';' ORDER BY symbol,ts,venue)) FROM orderflow_cobertura),
      (SELECT concat_ws(',', count(*), sum(usd), sum(base), min(ts), max(ts), sum(CASE WHEN compra THEN 1 ELSE 0 END)) FROM orderflow_cinta),
      (SELECT md5(string_agg(concat_ws(',',exchange,symbol,start_ts,end_ts,status), ';' ORDER BY exchange,symbol,start_ts)) FROM data_gap),
      (SELECT concat_ws(',', sum(buy_vol_usd), sum(sell_vol_usd)) FROM spot_trades_agg),
      (SELECT concat_ws(',', sum(buy_vol_usd), sum(sell_vol_usd)) FROM futures_trades_agg),
      (SELECT md5(string_agg(pg_get_functiondef(oid), ';' ORDER BY proname)) FROM pg_proc WHERE proname LIKE '%temporal_partitions'),
      (SELECT string_agg(relname, ',' ORDER BY relname) FROM pg_class WHERE relname LIKE 'orderflow_%_p2%')))" 2>/dev/null)
  { echo "${h:-sinbase}"; cat "$2"/*.json 2>/dev/null; echo "reloj ${3:-$RELOJ} minimo ${4:-10}"; } | sha256sum | cut -c1-16
}
k108() {  # $1 = base   $2 = servido   [$3 = reloj]   [$4 = minimo]  -> rc; salida en $T/sal
  K108_SUJETO=local K108_BASE="$(dsn "$1")" K108_SERVIDO="$2" K108_RELOJ="${3:-$RELOJ}" K108_MINIMO="${4:-10}" \
    bash "$CHK" > "$T/sal" 2>&1
  echo $?
}
sirve() {  # $1 = base   $2 = directorio   [$3 = planta de lo servido (OF-3), el arbol sin tocar]
  mkdir -p "$2"
  K108_BASE="$(dsn "$1")" K108_RELOJ="$RELOJ" "$PY" "$AQUI/K108-orderflow.py" sirve "$2" ${3:+--planta "$3"} > "$T/sirve.log" 2>&1
}
planta() {  # $1 nombre  $2 rc esperado  $3 patron  $4 base  $5 servido  $6 huella de antes  [$7 reloj] [$8 minimo]
  local despues rc visto
  despues=$(huella "$4" "$5" "${7:-$RELOJ}" "${8:-10}")
  rc=$(k108 "$4" "$5" "${7:-$RELOJ}" "${8:-10}")
  visto=$(grep -E -m1 -- "$3" "$T/sal" | cut -c1-110)
  comprueba "$1" "$([ "$rc" = "$2" ] && [ -n "$visto" ] && [ "$6" != "$despues" ] && echo 0 || echo 1)" \
    "rc=$rc · $6 -> $despues · ${visto:-$(head -1 "$T/sal" | cut -c1-110)}"
}

# --- LA BASE VACIA: el esquema del arbol y los agregados de 140 -----------------------------------------------
createdb -h "$H" "${DB}_vacia" || exit 2
psql -h "$H" -d "${DB}_vacia" -v ON_ERROR_STOP=1 -q -f "$REPO/sql/schema.sql" > /dev/null 2>&1 || { echo "K108-control: el esquema del arbol no se aplica"; exit 2; }
grep -v '^#' "$AQUI/K108-agregados.tsv" > "$T/agregados.tsv"
psql -h "$H" -d "${DB}_vacia" -v ON_ERROR_STOP=1 -q \
  -c "INSERT INTO market_assets(base_asset) VALUES ('BTC'),('ETH'),('SOL') ON CONFLICT DO NOTHING" \
  -c "INSERT INTO symbols(symbol, base_asset, is_perpetual) VALUES ('BTCUSDT_PERP.A','BTC',true),('ETHUSDT_PERP.A','ETH',true),('SOLUSDT_PERP.A','SOL',true) ON CONFLICT DO NOTHING" \
  -c "CREATE TABLE k108_a(tabla text, ts timestamptz, symbol text, exchange text, b float8, s float8, n int, c smallint)" \
  -c "\\copy k108_a FROM '$T/agregados.tsv'" \
  -c "INSERT INTO spot_trades_agg(ts,symbol,exchange,venue_count,interval,buy_vol_usd,sell_vol_usd,inst_buy_usd,inst_sell_usd,mid_buy_usd,mid_sell_usd,retail_buy_usd,retail_sell_usd,trade_count,covered_seconds) SELECT ts,symbol,exchange,1,'1min',b,s,0,0,0,0,0,0,n,c FROM k108_a WHERE tabla='spot_trades_agg'" \
  -c "INSERT INTO futures_trades_agg(ts,symbol,exchange,venue_count,interval,buy_vol_usd,sell_vol_usd,large_buy_usd,large_sell_usd,trade_count,covered_seconds) SELECT ts,symbol,exchange,1,'1min',b,s,0,0,n,c FROM k108_a WHERE tabla='futures_trades_agg'" \
  -c "DROP TABLE k108_a" > /dev/null || { echo "K108-control: no se cargaron los agregados"; exit 2; }
psql -h "$H" -d "${DB}_vacia" -qc "SELECT ensure_temporal_partitions('$RELOJ', 1, 2)" > /dev/null
# OF-5a (campana 146): las seis series de 5 min de Coinalyze de esa franja, de 140 (K108-coinalyze.tsv), SIN el latido del
# barrido de liquidaciones: una liquidacion de 5 min sin fila no la certifica nadie, y se sirve como hueco
grep -v '^#' "$AQUI/K108-coinalyze.tsv" > "$T/coinalyze.tsv"
psql -h "$H" -d "${DB}_vacia" -v ON_ERROR_STOP=1 -q \
  -c "CREATE TABLE k108_c(tabla text, ts timestamptz, symbol text, a float8, b float8, c float8, d float8)" \
  -c "\\copy k108_c FROM '$T/coinalyze.tsv'" \
  -c "INSERT INTO open_interest(ts,symbol,interval,oi_open,oi_high,oi_low,oi_close) SELECT ts,symbol,'5min',a,b,c,d FROM k108_c WHERE tabla='open_interest'" \
  -c "INSERT INTO oi_bybit(ts,symbol,interval,oi_open,oi_high,oi_low,oi_close) SELECT ts,symbol,'5min',a,b,c,d FROM k108_c WHERE tabla='oi_bybit'" \
  -c "INSERT INTO funding_rate(ts,symbol,interval,fr_open,fr_high,fr_low,fr_close) SELECT ts,symbol,'5min',a,b,c,d FROM k108_c WHERE tabla='funding_rate'" \
  -c "INSERT INTO predicted_funding_rate(ts,symbol,interval,pfr_open,pfr_high,pfr_low,pfr_close) SELECT ts,symbol,'5min',a,b,c,d FROM k108_c WHERE tabla='predicted_funding_rate'" \
  -c "INSERT INTO long_short_ratio(ts,symbol,interval,long_pct,short_pct,ratio) SELECT ts,symbol,'5min',a,b,c FROM k108_c WHERE tabla='long_short_ratio'" \
  -c "INSERT INTO liquidations(ts,symbol,interval,long_liq,short_liq) SELECT ts,symbol,'5min',a,b FROM k108_c WHERE tabla='liquidations'" \
  -c "DROP TABLE k108_c" > /dev/null || { echo "K108-control: no se cargaron las series de Coinalyze"; exit 2; }

# --- LA BASE BUENA: la grabacion por el colector del arbol -------------------------------------------------------
reproduce() {  # $1 = base   [$2 = planta]
  "$PY" "$AQUI/K108-reproduce.py" "$(dsn "$1")" "$AQUI/K108-flujo.jsonl.gz" ${2:+--planta "$2"} > "$T/rep.log" 2>&1
}
B0=$(copia limpia vacia) || exit 2
reproduce "$B0" || { echo "K108-control: la reproduccion fallo: $(tail -2 "$T/rep.log")"; exit 2; }
grep -q "app de $REPO/app/orderflow.py" "$T/rep.log" || { echo "K108-control: la reproduccion no uso el colector de $REPO: $(cat "$T/rep.log")"; exit 2; }
sirve "$B0" "$T/s0" || { echo "K108-control: sirve fallo: $(tail -2 "$T/sirve.log")"; exit 2; }
H_BUENA=$(huella "$B0" "$T/s0")
rc=$(k108 "$B0" "$T/s0")
comprueba base_verde "$([ "$rc" = 0 ] && grep -q '^VERDE  K108' "$T/sal" && echo 0 || echo 1)" "rc=$rc · $H_BUENA · $(head -1 "$T/sal" | cut -c1-90)"
cp "$T/sal" "$T/sal-base"

# --- PLANTADOS DE CODIGO -----------------------------------------------------------------------------------------
for p in agresor_okx_swap:'^ROJO  K108 \(f\) okx_swap' nivel_float:'^ROJO  K108 \(b\) [0-9]+ de [0-9]+ celdas no son la agregacion exacta' \
         doble_escritura:'\(b\) [0-9]+ de [0-9]+ celdas no son la agregacion exacta de su cinta' \
         minuto_partido:'\(b\) [0-9]+ de [0-9]+ celdas no son la agregacion exacta de su cinta'; do
  nombre=${p%%:*}; patron=${p#*:}
  b=$(copia "$nombre" vacia) || exit 2
  if reproduce "$b" "$nombre" && sirve "$b" "$T/s-$nombre"; then
    planta "codigo_$nombre" 1 "$patron" "$b" "$T/s-$nombre" "$H_BUENA"
  else
    comprueba "codigo_$nombre" 1 "la reproduccion plantada no corrio: $(tail -1 "$T/rep.log")"
  fi
done

# --- PLANTADOS DE DATOS (copias de la buena; lo servido es el bueno salvo donde se tuerce) ------------------------
b=$(copia celda limpia); en "$b" "UPDATE orderflow_celda SET compra_base = compra_base + 1, compra_usd = compra_usd + 1 WHERE (symbol, ts, venue, nivel) = (SELECT symbol, ts, venue, nivel FROM orderflow_celda WHERE venue='okx_spot' AND compras > 0 AND ts = '2026-10-17 04:10:00+00' ORDER BY symbol, nivel LIMIT 1)"
planta celda_alterada 1 '\(b\) 1 de [0-9]+ celdas no son la agregacion exacta de su cinta' "$b" "$T/s0" "$H_BUENA"
b=$(copia arranque limpia); en "$b" "UPDATE orderflow_celda SET compra_base = compra_base + 1, compra_usd = compra_usd + 1 WHERE (symbol, ts, venue, nivel) = (SELECT symbol, ts, venue, nivel FROM orderflow_celda WHERE venue='okx_spot' AND compras > 0 AND ts = '2026-10-17 04:02:00+00' ORDER BY symbol, nivel LIMIT 1)"
planta celda_del_arranque 1 '\(b\) 1 celdas de minutos de ARRANQUE con mas de lo que hay en su cinta' "$b" "$T/s0" "$H_BUENA"
b=$(copia negativo limpia); en "$b" "ALTER TABLE orderflow_celda DROP CONSTRAINT orderflow_celda_venta_base_check"
en "$b" "UPDATE orderflow_celda SET venta_base = -1 WHERE (symbol, ts, venue, nivel) = (SELECT symbol, ts, venue, nivel FROM orderflow_celda WHERE venue='deribit_perp' ORDER BY ts, symbol, nivel LIMIT 1)"
planta valor_negativo 1 '\(b\) 1 valores negativos' "$b" "$T/s0" "$H_BUENA"
b=$(copia hueco limpia); en "$b" "DELETE FROM data_gap WHERE feed='orderflow' AND exchange='coinbase_spot' AND symbol='ETH'"
planta hueco_sin_declarar 1 '\(c\) coinbase_spot: [0-9]+ minutos-activo incompletos o ausentes SIN declarar' "$b" "$T/s0" "$H_BUENA"
b=$(copia ausente limpia); en "$b" "DELETE FROM orderflow_celda WHERE venue='bitget_usdt' AND symbol='SOL' AND ts='2026-10-17 04:10:00+00'"
en "$b" "DELETE FROM orderflow_cobertura WHERE venue='bitget_usdt' AND symbol='SOL' AND ts='2026-10-17 04:10:00+00'"
planta minuto_ausente 1 '\(c\) bitget_usdt: 1 minutos-activo incompletos o ausentes SIN declarar en data_gap \(1 sin fila\)' "$b" "$T/s0" "$H_BUENA"
b=$(copia otro limpia); en "$b" "UPDATE spot_trades_agg SET buy_vol_usd = buy_vol_usd * 1.1 WHERE exchange='bybit'"
planta otro_colector_torcido 1 '\(a\) bybit_spot contra spot_trades_agg/bybit' "$b" "$T/s0" "$H_BUENA"
cp -r "$T/s0" "$T/s-fp"
f=$(grep -l '"que": "footprint' "$T"/s-fp/*.json | head -1)
"$PY" -c "import json,sys; p=sys.argv[1]; d=json.load(open(p)); n=next(n for v in d['velas'] for n in v['niveles'] if n['compra']!='0'); n['compra']=str(__import__('decimal').Decimal(n['compra'])+1); json.dump(d,open(p,'w'))" "$f"
planta servido_footprint 1 '\(d\) [A-Z]+ .*niveles servidos != recalculados' "$B0" "$T/s-fp" "$H_BUENA"
cp -r "$T/s0" "$T/s-va"
f=$(grep -l '"que": "perfil' "$T"/s-va/*.json | head -1)
"$PY" -c "import json,sys; p=sys.argv[1]; d=json.load(open(p)); d['value_area']['val']=d['niveles'][0]['nivel']; d['value_area']['vah']=d['niveles'][-1]['nivel']; json.dump(d,open(p,'w'))" "$f"
planta servido_value_area 1 '\(d\) [A-Z]+ .*value area servida' "$B0" "$T/s-va" "$H_BUENA"
# OF-2 (campana 142): la value area de CADA vela del footprint, aplastada a su VAL en una vela que no la tiene de un nivel
cp -r "$T/s0" "$T/s-vav"
f=$(grep -l '"que": "footprint' "$T"/s-vav/*.json | head -1)
"$PY" -c "import json,sys; p=sys.argv[1]; d=json.load(open(p)); v=next(v for v in d['velas'] if v.get('value_area') and v['value_area']['val']!=v['value_area']['vah']); v['value_area']['vah']=v['value_area']['val']; json.dump(d,open(p,'w'))" "$f"
planta servido_va_de_una_vela 1 '\(d\) [A-Z]+ .*value area servida .* != recalculada' "$B0" "$T/s-vav" "$H_BUENA"
# OF-3 (campana 143): lo servido de las sesiones, el VWAP y el TPO, cada decision con su plantado
cp -r "$T/s0" "$T/s-vah"
f=$(grep -l '"sesion": {"nombre": "dia"' "$T"/s-vah/*sesiones*.json | head -1)
"$PY" -c "import json,sys,decimal; p=sys.argv[1]; d=json.load(open(p)); s=next(s for s in d['sesiones'] if s['value_area']); s['value_area']['vah']=str(decimal.Decimal(s['value_area']['vah'])+decimal.Decimal(d['paso'])); json.dump(d,open(p,'w'))" "$f"
planta servido_vah_movida 1 '\(d\) [A-Z]+ .*sesiones dia .*value area servida' "$B0" "$T/s-vah" "$H_BUENA"
cp -r "$T/s0" "$T/s-tpo"
f=$(grep -l '"que": "TPO' "$T"/s-tpo/*.json | head -1)
"$PY" -c "import json,sys; p=sys.argv[1]; d=json.load(open(p)); L=d['letras']; n=next(n for s in d['sesiones'] for n in s['niveles']); n['letras']=n['letras'][:-1]+L[L.index(n['letras'][-1])+1]; json.dump(d,open(p,'w'))" "$f"
planta servido_letra_de_otro_periodo 1 '\(d\) [A-Z]+ .*tpo dia .*letras servidas != recalculadas' "$B0" "$T/s-tpo" "$H_BUENA"
if sirve "$B0" "$T/s-vwn" vwap_al_nivel; then
  planta servido_vwap_otra_cuenta 1 '\(d\) [A-Z]+ .*vwap [0-9:]+-[0-9:]+ vela .*vwap servido' "$B0" "$T/s-vwn" "$H_BUENA"
else
  comprueba servido_vwap_otra_cuenta 1 "sirve plantado no corrio: $(tail -1 "$T/sirve.log")"
fi
if sirve "$B0" "$T/s-med" partir_medianoche; then
  planta servido_sesion_partida 1 '\(d\) [A-Z]+ .*sesiones [0-9:]+-[0-9:]+: sesiones servidas .* != recalculadas' "$B0" "$T/s-med" "$H_BUENA"
else
  comprueba servido_sesion_partida 1 "sirve plantado no corrio: $(tail -1 "$T/sirve.log")"
fi
# un sujeto ANTERIOR a OF-3 (en produccion, un 404): VERDE, con (d) OF-3 SIN JUZGAR, y nunca NO MEDIDO
mkdir -p "$T/s-sin"
cp "$T"/s0/*footprint* "$T"/s0/*perfil* "$T/s-sin/"
touch "$T/s-sin/sin-of3"
rc=$(k108 "$B0" "$T/s-sin")
comprueba sujeto_anterior_a_of3 "$([ "$rc" = 0 ] && grep -q '^VERDE  K108' "$T/sal" && grep -q '(d) OF-3: SIN JUZGAR' "$T/sal" && echo 0 || echo 1)" "rc=$rc · $(grep -m1 'OF-3' "$T/sal" | cut -c1-100)"
# OF-5a (campana 146): lo servido de los indicadores y de la orden agregada, cada decision con su plantado
cp -r "$T/s0" "$T/s-ind"
f=$(grep -l '"que": "los indicadores' "$T"/s-ind/*.json | head -1)
"$PY" -c "import json,sys,decimal; p=sys.argv[1]; d=json.load(open(p)); c=next(c for c in d['series']['oi_binance']['cubos'] if c['valores']); c['valores']['oi']=str(decimal.Decimal(c['valores']['oi'])+1); json.dump(d,open(p,'w'))" "$f"
planta servido_indicador_alterado 1 '\(d\) [A-Z]+ .*indicadores: oi_binance: cubos servidos != recalculados' "$B0" "$T/s-ind" "$H_BUENA"
if sirve "$B0" "$T/s-cer" cero_sin_certificar; then
  planta servido_hueco_como_cero 1 '\(d\) [A-Z]+ .*indicadores: el barrido servido' "$B0" "$T/s-cer" "$H_BUENA"
else
  comprueba servido_hueco_como_cero 1 "sirve plantado no corrio: $(tail -1 "$T/sirve.log")"
fi
if sirve "$B0" "$T/s-seg" orden_por_segundo; then
  planta servido_orden_mal_sumada 1 '\(d\) [A-Z]+ .*ordenes: la orden .* sus operaciones suman' "$B0" "$T/s-seg" "$H_BUENA"
else
  comprueba servido_orden_mal_sumada 1 "sirve plantado no corrio: $(tail -1 "$T/sirve.log")"
fi
mkdir -p "$T/s-sin5"
cp "$T"/s0/*.json "$T/s-sin5/"
rm -f "$T"/s-sin5/*indicadores* "$T"/s-sin5/*ordenes*
touch "$T/s-sin5/sin-of5a"
rc=$(k108 "$B0" "$T/s-sin5")
comprueba sujeto_anterior_a_of5a "$([ "$rc" = 0 ] && grep -q '^VERDE  K108' "$T/sal" && grep -q '(d) OF-5a: SIN JUZGAR' "$T/sal" && echo 0 || echo 1)" "rc=$rc · $(grep -m1 'OF-5a' "$T/sal" | cut -c1-100)"
b=$(copia vieja limpia); en "$b" "SELECT ensure_temporal_partitions('2026-10-14 12:00+00', 0, 0)"
en "$b" "INSERT INTO orderflow_cinta(ts,venue,symbol,precio,base,usd,compra,id) VALUES ('2026-10-14 12:00+00','binance_spot','BTC',80000,1,80000,true,'vieja')"
planta retencion_cinta 1 '\(e\) 1 filas de cinta mas viejas que su retencion' "$b" "$T/s0" "$H_BUENA"
b=$(copia particion limpia); en "$b" "DROP TABLE orderflow_cinta_p20261018"
planta particion_de_manana 1 '\(e\) faltan particiones de hoy o de manana' "$b" "$T/s0" "$H_BUENA"
b=$(copia funcion limpia)
git -C "$REPO" show "$ANTES:sql/schema.sql" > "$T/antes.sql" 2>/dev/null || { echo "K108-control: sin $ANTES en el repo"; exit 2; }
"$PY" - "$T/antes.sql" "$T/funcion.sql" <<'PY'
import sys
s = open(sys.argv[1]).read()
i = s.index("CREATE OR REPLACE FUNCTION ensure_temporal_partitions(")
j = s.index("$$;", s.index("AS $$", i)) + 3
open(sys.argv[2], "w").write(s[i:j] + "\n")
PY
psql -h "$H" -d "$b" -q -f "$T/funcion.sql" > /dev/null 2>&1
planta funcion_de_antes 1 '\(e\) las funciones vivas de particion no gestionan' "$b" "$T/s0" "$H_BUENA"
planta servicio_parado 1 '\(c\) el servicio no escribe' "$B0" "$T/s0" "$H_BUENA" 2026-10-17T04:40:00+00:00

# --- NO MEDIDO -------------------------------------------------------------------------------------------------------
createdb -h "$H" "${DB}_antes" && psql -h "$H" -d "${DB}_antes" -q -f "$T/antes.sql" > /dev/null 2>&1
planta sin_tablas 2 '^NO MEDIDO: FALTA DESPLEGAR' "${DB}_antes" "$T/s0" "$H_BUENA"
planta cero_filas 2 '^NO MEDIDO: las tablas orderflow_\* estan pero orderflow_cobertura no tiene ni una fila' "${DB}_vacia" "$T/s0" "$H_BUENA"
planta canal_caido 2 '^NO MEDIDO \(CANAL\)' "${DB}_no_existe" "$T/s0" "$H_BUENA"
planta poca_vida 2 '^NO MEDIDO: el servicio lleva menos de' "$B0" "$T/s0" "$H_BUENA" "$RELOJ" 30

# --- LAS TRES INVOCACIONES Y LOS DOS MODOS DE SIGPIPE (sobre la base buena) -----------------------------------------
ENV=(K108_SUJETO=local "K108_BASE=$(dsn "$B0")" "K108_SERVIDO=$T/s0" "K108_RELOJ=$RELOJ" K108_MINIMO=10)
inv() { "$@" > "$T/inv" 2>&1; echo "$? $(head -1 "$T/inv" | cut -c1-40)"; }
r1=$(inv env "${ENV[@]}" bash "$CHK")
r2=$(cd "$REPO" && inv env "${ENV[@]}" bash harness/checks/K108-el-dato-del-order-flow.sh)
r3=$(cd /tmp && inv env "${ENV[@]}" bash "$CHK")
for r in "$r1" "$r2" "$r3"; do case "$r" in "0 VERDE  K108"*) ;; *) bad=1 ;; esac; done
comprueba tres_invocaciones "${bad:-0}" "absoluta: $r1 · relativa: $r2 · ajena: $r3"
for m in --ignore-signal=PIPE --default-signal=PIPE; do
  env $m "${ENV[@]}" bash "$CHK" > "$T/sp" 2>&1; rc=$?
  comprueba "sigpipe$m" "$([ "$rc" = 0 ] && head -1 "$T/sp" | grep -q '^VERDE  K108' && ! grep -qi 'broken pipe' "$T/sp" && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sp" | cut -c1-60)"
done

# --- LO QUE TIENE QUE QUEDAR COMO ESTABA ------------------------------------------------------------------------------
H_FIN=$(huella "$B0" "$T/s0")
comprueba escenario_restaurado "$([ "$H_FIN" = "$H_BUENA" ] && echo 0 || echo 1)" "$H_BUENA -> $H_FIN"
ARBOL_DESPUES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)
comprueba arbol_intacto "$([ "$ARBOL_ANTES" = "$ARBOL_DESPUES" ] && echo 0 || echo 1)" "git status $ARBOL_ANTES -> $ARBOL_DESPUES"
echo "--- la salida de K108 sobre la base buena:"
cut -c1-200 "$T/sal-base"
echo "K108-control: $pasan de $total${fallan:+ · FALLAN:$fallan}"
[ "$pasan" = "$total" ]
