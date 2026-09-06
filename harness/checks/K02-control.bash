#!/usr/bin/env bash
# K02-control · ¿el criterio nuevo caza lo que dice?
#
# El criterio viejo -«pasa por el enmascarado»- contaba LLAMADAS, no EFECTO, y por eso daba
# por cubiertas dos rutas cuya llamada no puede honrarse y enrojecia con la unica que declara
# cobertura por cubo. El nuevo gatea el SUELO -publicar data_gaps- y CUENTA el instrumento
# fino. Hay que probar las dos mitades por separado: que la ausencia del suelo enrojece, y
# que el reparto fino no enrojece nunca aunque sea deuda.
#
# El fixture es un api.py GENERADO aqui: asi los casos no caducan cuando alguien toque el de
# verdad, que es lo que le paso a la lista escrita a mano del criterio viejo.
set -uo pipefail
ORIG=${REPO:-/srv/coinanalyze/repo}
CHK="$ORIG/harness/checks/K02-cobertura-hueco.sh"
[ -r "$CHK" ] || { echo "NO MEDIDO: no encuentro el check en $CHK"; exit 2; }

DIR=$(mktemp -d) || exit 2
[ "${K02_CONTROL_GUARDA:-0}" = "1" ] || trap 'rm -rf "$DIR"' EXIT
mkdir -p "$DIR/t/app" "$DIR/t/harness/bin" "$DIR/t/sql"
cp "$ORIG/harness/bin/arquitectura" "$DIR/t/harness/bin/" || exit 2
cp "$ORIG/sql/schema.sql" "$DIR/t/sql/" || exit 2

SERIE="/api/ohlcv /api/oi /api/liquidations /api/whale/delta /api/daily /api/cvd /api/cvd/spot"

# --- el api.py de mentira --------------------------------------------------------------
# Cada ruta se genera con tres interruptores: si publica data_gaps (el suelo), con que feed
# enmascara, y si nombra covered_seconds. spot_trades_agg aparece cuando toca porque el check
# la saca del catalogo REAL: es la tabla con covered_seconds y decide a quien se le exige.
ruta() {  # <camino> <suelo 0|1> <feed o -> <por_cubo 0|1>
  local nom; nom=$(printf '%s' "$1" | tr -c 'a-z' '_')
  echo "@app.get(\"$1\")"
  echo "async def h$nom(symbol: str) -> dict:"
  echo "    rows = await conn.fetch(\"SELECT 1 FROM spot_trades_agg\")"
  [ "$4" = 1 ] && echo "    x = row['covered_seconds']"
  [ "$3" = "-" ] || echo "    await mask_gapped_series_rows(conn, rows, feed=\"$3\")"
  if [ "$2" = 1 ]; then
    echo "    result[\"data_gaps\"] = {\"status\": \"ok\"}"
  fi
  echo "    return result"
  echo
}
cabecera() {
  echo "async def declared_series_response(conn, rows, **kw): ..."
  echo "async def mask_gapped_series_rows(conn, rows, **kw): ..."
  echo
}
monta() { { cabecera; cat; } > "$DIR/t/app/api.py"; }

# el arbol de mentira necesita un registrador para que `liquidations` cuente como detectado
mkdir -p "$DIR/t/app"
printf 'async def x():\n    await record_event_stream_loss(feed="liquidations")\n' > "$DIR/t/app/scalp_collector.py"
printf 'async def record_event_stream_loss(**kw): ...\nasync def record_data_gap(**kw): ...\n' > "$DIR/t/app/data_gaps.py"

fallos=0; pasan=0
caso() {  # <nombre> <rc> <patron>
  local nombre="$1" esperado="$2" patron="$3" out rc ok=1
  out=$(REPO="$DIR/t" bash "$CHK" 2>&1); rc=$?
  [ "$rc" = "$esperado" ] || ok=0
  if [ -n "$patron" ] && ! printf '%s' "$out" | grep -qE "$patron"; then ok=0; fi
  if [ "$ok" = 1 ]; then
    pasan=$((pasan+1)); printf '  [ok   ] %-54s rc=%s\n' "$nombre" "$rc"
  else
    fallos=$((fallos+1))
    printf '  [FALLA] %-54s rc=%s (esperaba %s, patron /%s/)\n      %s\n' \
      "$nombre" "$rc" "$esperado" "$patron" "$(printf '%s' "$out" | head -2 | tr '\n' ' ' | cut -c1-170)"
  fi
}

todas() {  # <suelo> <feed> <por_cubo>  para las 7
  { for r in $SERIE; do ruta "$r" "$1" "$2" "$3"; done; } | monta
}

echo "K02-control · sujeto: $CHK"
echo

echo "EL SUELO · lo unico que gatea"
todas 1 ohlcv_1min 0
caso "N1 las 7 publican data_gaps" 0 "los 7 endpoints de serie publican"

# P1 · EL DEFECTO QUE ESTE CHECK EXISTE PARA CAZAR: una serie que sirve cubos y no dice si le
# falta alguno. Es lo que pasaba cuando K02 se escribio.
{ ruta /api/ohlcv 0 ohlcv_1min 0
  for r in /api/oi /api/liquidations /api/whale/delta /api/daily /api/cvd /api/cvd/spot; do
    ruta "$r" 1 ohlcv_1min 0; done; } | monta
caso "P1 una ruta sin data_gaps enrojece" 1 "NO declaran su ventana"
caso "P2 y la nombra" 1 "/api/ohlcv"

todas 0 ohlcv_1min 0
caso "P3 las 7 sin data_gaps: 7 de 7" 1 "7 de 7 endpoints"

echo
echo "EL REPARTO FINO · informa, nunca enrojece"
# N2 · EL CASO QUE JUSTIFICA EL CAMBIO. Enmascarar con un feed sin detector es una llamada
# que no se honra: es DEUDA, no defecto. Con el criterio viejo esto contaba como cubierto.
todas 1 spot_trades 0
caso "N2 enmascarado que su feed no honra: deuda, no rojo" 0 "no puede honrar"

# N3 · y la otra mitad del mismo error: la ruta que NO enmascara pero declara por cubo es la
# MEJOR instrumentada, y el criterio viejo la enrojecia. Aqui sale como cobertura por cubo.
todas 1 - 1
caso "N3 sin enmascarar pero con cobertura por cubo: verde" 0 "cobertura por cubo"

# N4 · leer una tabla con covered_seconds y no publicarlo se cuenta como deuda.
todas 1 - 0
caso "N4 lee spot_trades_agg y no publica por cubo: deuda" 0 "no publica cobertura por cubo"

# N5 · ANTI-FANTASMA DEL REPARTO: el feed CON detector no puede salir como hueca. Sin este
# caso, "no puede honrar" podria estar disparando siempre y N2 no probaria nada.
todas 1 liquidations 0
caso "N5 feed con detector: NO se marca como hueca" 0 "enmascarado efectivo: liquidations"

echo
echo "ANTI-FANTASMA · lo que no se puede medir es NOMED, jamas VERDE"
{ ruta /api/ohlcv 1 - 0; } | monta
caso "F1 solo 1 de las 7 rutas resuelta: NOMED" 2 "solo se resolvieron"

rm -f "$DIR/t/app/api.py"
caso "F2 sin api.py: NOMED" 2 "no se puede leer"

todas 1 ohlcv_1min 0
python3 - "$DIR/t/app/api.py" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1])
p.write_text(p.read_text().replace("async def declared_series_response", "async def otra_cosa"))
PY
caso "F3 declared_series_response desaparecio: NOMED" 2 "hay que reescribirlo"

echo
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
