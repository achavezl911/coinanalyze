#!/bin/bash
# Reproduce el fallo por carga del borde de test_entradas_espera (a/c/d): corre ESE test N veces
# con CARGA procesos python en bucle ocupado (nice 0) y, si IO > 0, IO escritores que llenan la
# base de WAL (INSERT de 200k filas y TRUNCATE, en bucle, en la misma base desechable): la CI
# compite tambien por Postgres, no solo por CPU. Cuenta los fallos y su linea.
# uso: entregas/espera_borde_carga.sh N CARGA SALIDA [IO]   (base desechable propia, borrada al final)
set -u
N=${1:-12}; CARGA=${2:-4}; OUT=${3:-/tmp/espera-borde.txt}; IO=${4:-0}
TEST="tests/test_entradas_espera.py::test_a_c_d_la_vela_de_v2_se_decide_con_el_spot_completo_y_v1_no_cambia_de_reloj"
cd "$(dirname "$0")/.."
DB="eb_borde_$$"
: > "$OUT"
createdb --host=/var/run/postgresql "$DB" || exit 1
psql --host=/var/run/postgresql -d "$DB" -q -v ON_ERROR_STOP=1 -f sql/schema.sql > /dev/null || exit 1
export TEST_DATABASE_URL="postgresql:///${DB}?host=/var/run/postgresql"
PIDS=()
for _ in $(seq "$CARGA"); do
  python3 -c "while True: pass" & PIDS+=($!)
done
for k in $(seq "$IO"); do
  psql --host=/var/run/postgresql -d "$DB" -q -c "CREATE TABLE public.eb_lastre_$k(x text)" > /dev/null
  ( while true; do
      psql --host=/var/run/postgresql -d "$DB" -q -c \
        "INSERT INTO public.eb_lastre_$k SELECT md5(g::text) FROM generate_series(1,200000) g" \
        -c "TRUNCATE public.eb_lastre_$k" > /dev/null 2>&1
    done ) & PIDS+=($!)
done
echo "N=$N CARGA=$CARGA IO=$IO inicio $(date -u +%H:%M:%SZ) load $(cut -d' ' -f1-3 /proc/loadavg)" >> "$OUT"
FALLOS=0
for i in $(seq "$N"); do
  LOG="$OUT.$i"
  .venv/bin/pytest -q -s -p no:cacheprovider "$TEST" > "$LOG" 2>&1
  RC=$?
  [ "$RC" -ne 0 ] && FALLOS=$((FALLOS + 1))
  CUENTA=$(grep -o "a/c (escala.*" "$LOG" | head -1 | cut -c1-200)
  DONDE=$(grep -E "^tests/test_entradas_espera.py:[0-9]+:|^E +(assert|AssertionError|.*Failed)" "$LOG" | head -3 | tr '\n' ' ' | cut -c1-400)
  REP=$(grep -o "PREMISA[^\"']*" "$LOG" | head -2 | tr '\n' ' ' | cut -c1-300)
  echo "$i rc=$RC | $CUENTA | $DONDE | $REP" >> "$OUT"
  [ "$RC" -eq 0 ] && rm -f "$LOG"
done
kill "${PIDS[@]}" 2>/dev/null
echo "FALLAN $FALLOS de $N · fin $(date -u +%H:%M:%SZ)" >> "$OUT"
sleep 2
dropdb --host=/var/run/postgresql --if-exists --force "$DB"
echo "TERMINADO" >> "$OUT"
