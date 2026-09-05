#!/bin/bash
# K92-control · LOS BRAZOS, INDUCIDOS SIN RED Y SIN BASE.
#
# K92 necesita DOS canales -el journal para las paradas y prodsql para la cobertura- y esta
# sesion no llega a ninguno, asi que el control los inyecta los dos. Eso permite ejercitar
# combinaciones que un solo dato real no daria: parada sin fila, minuto siguiente completo,
# journal vacio, esquema sin la columna.
#
# EL BRAZO QUE MAS IMPORTA ES EL CONTROL DEL SUJETO: si el minuto SIGUIENTE a la parada
# tambien sale completo, el defecto no esta en la cobertura sino en el registro de paradas o
# en el reloj, y el check tiene que decir NO MEDIDO en vez de acusar. Un check que acusa sin
# haber descartado la explicacion alternativa es el que produce los K falsos que este arnes
# lleva seis paquetes evitando.
#
# NO LLEVA .sh A PROPOSITO: bin/verify globea checks/*.sh.
set -uo pipefail

ORIG=${K92_CONTROL_REPO:-/srv/coinanalyze/repo}
CHK="$(cd "$(dirname "$0")" && pwd)/K92-el-minuto-que-miente.sh"
[ -r "$CHK" ] || { echo "NO MEDIDO: no encuentro el check en $CHK"; exit 2; }

DIR=$(mktemp -d) || exit 2
[ "${K92_CONTROL_GUARDA:-0}" = "1" ] || trap 'rm -rf "$DIR"' EXIT
cd "$DIR" || exit 2
fallos=0; pasan=0
mkdir -p "$DIR/bin"

# --- el journal de mentira ----------------------------------------------------------------
cat > "$DIR/bin/prod" <<'PY'
#!/bin/sh
printf '%s\n' "${K92C_JOURNAL:-}"
exit "${K92C_PRODRC:-0}"
PY
chmod +x "$DIR/bin/prod"
cat > "$DIR/bin/prod-roto" <<'PY'
#!/bin/sh
echo "ssh: connect to host: No route to host" >&2
exit 255
PY
chmod +x "$DIR/bin/prod-roto"

# --- la base de mentira -------------------------------------------------------------------
cat > "$DIR/bin/prodsql" <<'PY'
#!/bin/sh
[ -n "${K92C_FILAS:-}" ] || exit 0
printf '%s\n' "$K92C_FILAS"
PY
chmod +x "$DIR/bin/prodsql"
cat > "$DIR/bin/prodsql-roto" <<'PY'
#!/bin/sh
echo 'psql:<stdin>:1: ERROR:  column "covered_seconds" does not exist' >&2
exit 3
PY
chmod +x "$DIR/bin/prodsql-roto"

JOURNAL_OK='2026-09-05T17:16:55+00:00 coinalyze-ws[123]: Stopped Coinalyze WS collector.'
# formato de la consulta: parada|segundo|cov_parada|cov_siguiente|filas_parada|filas_siguiente
FILA_MIENTE=' 2026-09-05T17:16| 55| 60| 45| 2| 2'
FILA_SANA='   2026-09-05T17:16| 55| 55| 45| 2| 2'
FILA_AUSENTE='2026-09-05T17:16| 55|   |   | 0| 0'

caso() {  # <nombre> <rc> <patron> <journal> <filas> [prodsql] [prod]
  local nombre="$1" esperado="$2" patron="$3" jr="$4" fl="$5"
  local psql="${6:-$DIR/bin/prodsql}" prod="${7:-$DIR/bin/prod}"
  local out rc
  out=$(REPO="$ORIG" K92_PRODSQL="$psql" K92_PROD="$prod" \
        K92C_JOURNAL="$jr" K92C_FILAS="$fl" bash "$CHK" 2>&1); rc=$?
  local ok=1
  [ "$rc" = "$esperado" ] || ok=0
  if [ -n "$patron" ] && ! printf '%s' "$out" | grep -qE "$patron"; then ok=0; fi
  if [ "$ok" = 1 ]; then
    pasan=$((pasan+1)); printf '  [ok   ] %-52s rc=%s\n' "$nombre" "$rc"
  else
    fallos=$((fallos+1))
    printf '  [FALLA] %-52s rc=%s (esperaba %s, patron /%s/)\n      %s\n' \
      "$nombre" "$rc" "$esperado" "$patron" "$(printf '%s' "$out" | head -2 | tr '\n' ' ' | cut -c1-150)"
  fi
}

echo "K92-control · sujeto: $CHK"
echo

echo "POSITIVO · el minuto que miente"
# P1 · EL CASO REAL, con las cifras medidas en 140: parada en el segundo 55, el minuto de la
# parada dice 60 -deberia decir 55- y el siguiente dice 45.
caso "P1 cov=60 con la parada dentro del minuto" 1 "dicen covered_seconds=60" \
     "$JOURNAL_OK" "$FILA_MIENTE"
# P2 · dos paradas, una miente y otra no: tiene que nombrar solo la que miente.
caso "P2 dos paradas, solo una miente" 1 "17:16" \
     "$JOURNAL_OK
2026-09-04T09:30:20+00:00 coinalyze-ws[123]: Stopped Coinalyze WS collector." \
     " 2026-09-05T17:16| 55| 60| 45| 2| 2
 2026-09-04T09:30| 20| 20| 50| 2| 2"

echo
echo "NEGATIVO · cuando la cobertura SI se escribe corta"
caso "N1 cov=55 con la parada en el segundo 55" 0 "declaran su cobertura corta" \
     "$JOURNAL_OK" "$FILA_SANA"
# N2 · la parada en el segundo 0 no acorta el minuto anterior: cov=60 es correcto ahi.
caso "N2 parada en el segundo 0: cov=60 es correcto" 0 "declaran su cobertura corta" \
     "2026-09-05T17:16:00+00:00 coinalyze-ws[123]: Stopped Coinalyze WS collector." \
     " 2026-09-05T17:16|  0| 60| 45| 2| 2"
# N3 · sin fila en el minuto de la parada es el caso AUSENTE, que YA se arreglo y no es el
# sujeto de este check. No puede contar como defecto.
caso "N3 minuto de la parada AUSENTE: no es el sujeto" 0 "" \
     "$JOURNAL_OK" "$FILA_AUSENTE"

echo
echo "EL CONTROL DEL SUJETO · en la misma consulta"
# C1 · si el minuto SIGUIENTE tambien sale completo, la parada no acorto nada: o el journal
# miente o el reloj no cuadra. NO MEDIDO, nunca ROJO.
caso "C1 el minuto siguiente TAMBIEN sale completo" 2 "el sujeto seria el registro de paradas" \
     "$JOURNAL_OK" " 2026-09-05T17:16| 55| 60| 60| 2| 2"

echo
echo "ANTI-FANTASMA · lo que no se puede medir es NOMED, jamas VERDE"
# F1 · CERO PARADAS NO ES CERO DEFECTOS. Sin parada no hay minuto de parada y el check no
# tiene sujeto. Es la leccion de K60 aplicada al elegible.
caso "F1 ninguna parada en la ventana" 2 "sin sujeto que medir" \
     "" "$FILA_MIENTE"
caso "F2 el journal no se puede leer" 2 "no se pudo leer el journal" \
     "$JOURNAL_OK" "$FILA_MIENTE" "$DIR/bin/prodsql" "$DIR/bin/prod-roto"
caso "F3 el SQL falla" 2 "la consulta fallo" \
     "$JOURNAL_OK" "$FILA_MIENTE" "$DIR/bin/prodsql-roto"
caso "F4 la consulta no devuelve filas" 2 "ninguna fila para las" \
     "$JOURNAL_OK" "total | nada"

echo
echo "ESQUEMA REAL · las columnas se comprueban ANTES de consultar"
# E1 · el sujeto NO es un doble: se lee sql/schema.sql de verdad, con el catalogo que desde
# F4 conoce tambien las columnas de ALTER -sin las cuales covered_seconds es invisible-.
res=$(python3 - "$ORIG" <<'PY'
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path
repo = Path(sys.argv[1])
m = SourceFileLoader("arq", str(repo / "harness/bin/arquitectura")).load_module()
cat = m.lee_catalogo(repo)
out = []
for t in ("spot_trades_agg", "futures_trades_agg"):
    cols = set(cat["tablas"].get(t, {}).get("columnas", []))
    falta = [c for c in ("ts", "symbol", "exchange", "interval", "covered_seconds") if c not in cols]
    out.append((t, falta))
malas = [t for t, f in out if f]
print("OK" if not malas else "FALTAN " + str(out))
PY
2>&1)
if [ "$res" = "OK" ]; then
  pasan=$((pasan+1)); printf '  [ok   ] %-52s las 5 en las DOS tablas\n' "E1 columnas de las dos tablas del defecto"
else
  fallos=$((fallos+1)); printf '  [FALLA] %-52s %s\n' "E1 columnas" "$res"
fi

# E2 · CONTROL NEGATIVO DEL PROPIO E1: una tabla que NO existe tiene que salir SINTABLA, no
# pasar por buena. Sin esto, E1 pasaria tambien con un catalogo vacio.
out=$(REPO="$ORIG" K92_TABLA="tabla_que_no_existe" K92_PRODSQL="$DIR/bin/prodsql" \
      K92_PROD="$DIR/bin/prod" K92C_JOURNAL="$JOURNAL_OK" K92C_FILAS="$FILA_MIENTE" \
      bash "$CHK" 2>&1); rc=$?
if [ "$rc" = "2" ] && printf '%s' "$out" | grep -q "no esta en sql/schema.sql"; then
  pasan=$((pasan+1)); printf '  [ok   ] %-52s rc=%s\n' "E2 tabla inventada: NOMED, no pasa por buena" "$rc"
else
  fallos=$((fallos+1)); printf '  [FALLA] %-52s rc=%s\n' "E2 tabla inventada" "$rc"
fi

echo
total=$((pasan + fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
