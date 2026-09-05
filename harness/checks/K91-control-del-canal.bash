#!/bin/bash
# K91-control-del-canal · prodsql TIENE QUE PROPAGAR EL FALLO DEL SQL.
#
# EL DEFECTO QUE ESTE CONTROL EXISTE PARA QUE NO VUELVA.
# `prodsql` terminaba en `ssh ... 2>&1 | "$B/bin/_corta"`. En un pipe el rc que ve el
# llamante es el del ULTIMO mandato -_corta, que siempre sale 0-, asi que
# `prodsql "SELECT no_existe FROM t"` devolvia **0**, igual que `SELECT 1`. Medido por el
# operador el 2026-09-05.
#
# LO QUE ESO APAGABA, y no era solo un check: de los 51 checks del arnes, **31 llaman a
# prodsql**. Solo **4** comprueban su rc, y de esos 4 **tres** tenian el guardia
# `[ "$rc" = 0 ] || NO MEDIDO`, que NO PODIA DISPARARSE NUNCA. Un SQL roto llegaba
# disfrazado de "sin filas", y un check que tratara cero filas como VERDE se habria puesto
# verde con la consulta rota. Es la version de canal del "NOMED no es ROJO".
#
# COMO SE PRUEBA SIN RED: se copia `prodsql` y se le sustituye la linea del `ssh` por un
# guion de mentira que imprime lo que se le pida y sale con el rc que se le pida. Todo lo
# demas del programa -la captura, el guardia del rc, el grep de ERROR y el corte- es el
# original, letra por letra.
#
# NO LLEVA .sh A PROPOSITO: bin/verify globea checks/*.sh y el sujeto es el canal, no
# produccion. Corre sin red y sin base de datos.
set -uo pipefail

ORIG=${K91_REPO:-/srv/coinanalyze/repo}
FUENTE="$ORIG/harness/bin/prodsql"
[ -r "$FUENTE" ] || { echo "NO MEDIDO: no encuentro $FUENTE"; exit 2; }

DIR=$(mktemp -d) || exit 2
[ "${K91_GUARDA:-0}" = "1" ] || trap 'rm -rf "$DIR"' EXIT
cd "$DIR" || exit 2
fallos=0; pasan=0

# --- el doble: mismo programa, transporte sustituido -----------------------------------
# La sustitucion se hace por el patron del `ssh`, y si no casa el control se declara NO
# MEDIDO en vez de probar un fichero que no es el que cree: es la leccion del I6 de K88.
python3 - "$FUENTE" "$DIR/prodsql-doble" <<'PY'
import re, sys
src = open(sys.argv[1], encoding="utf-8").read()
# el bloque: salida=$(ssh ... )   ->   salida=$(sh "$K91_FALSO")
# LA SUSTITUCION CONSERVA LA REDIRECCION DE stderr, y no es un detalle.
# La primera version reemplazaba por `salida=$(sh "$K91_FALSO")` a secas: el doble escribia
# su stderr a la terminal en vez de al fichero que el sujeto luego inspecciona, asi que los
# casos P1 y P2 daban rc=0 y parecia que la segunda defensa no funcionaba. El defecto era
# del CONTROL: probaba un prodsql sin la redireccion, o sea, un sujeto que no es.
# Es la misma familia de la que llevo cuatro rondas: el instrumento midiendo otra cosa.
nuevo, n = re.subn(
    r'salida=\$\(ssh[^)]*?"\$PROD_SSH_USER@\$PROD_HOST"[^)]*?(2>"\$err")\)',
    r'salida=$(sh "$K91_FALSO" \1)', src, flags=re.S)
if n != 1:
    sys.stderr.write(f"SUSTITUCIONES={n}\n"); sys.exit(3)
# el env del arnes trae rutas reales que aqui no hacen falta
nuevo = nuevo.replace('B=/srv/coinanalyze/harness; . "$B/env"',
                      'B=${K91_B:-/srv/coinanalyze/harness}; . "$B/env" 2>/dev/null || true')
open(sys.argv[2], "w", encoding="utf-8").write(nuevo)
PY
rc=$?
if [ "$rc" != "0" ]; then
  echo "NO MEDIDO: no pude sustituir el transporte en prodsql (rc=$rc)."
  echo "  Si el programa cambio de forma, este control NO esta probando lo que dice."
  exit 2
fi
chmod +x "$DIR/prodsql-doble"

# _corta de mentira, para no depender del arnes entero
mkdir -p "$DIR/harness/bin"
printf '#!/bin/sh\ncat\n' > "$DIR/harness/bin/_corta"; chmod +x "$DIR/harness/bin/_corta"
printf 'PROD_SSH_USER=x\nPROD_HOST=x\nPROD_SSH_KEY=/dev/null\nPROD_KNOWN_HOSTS=/dev/null\nPROD_PG_USER=x\nPROD_PG_DB=x\n' \
  > "$DIR/harness/env"

caso() {  # <nombre> <rc esperado> <lo que va a STDOUT> <rc del transporte> <lo que va a STDERR>
  local nombre="$1" esperado="$2" texto="$3" rct="${4:-0}" errtxt="${5:-}"
  # EL DOBLE ESCRIBE POR LOS DOS CANALES POR SEPARADO, que es lo que el sujeto distingue
  # ahora. La version anterior solo sabia escribir por stdout, y por eso sus 6 casos no
  # podian ver que la segunda defensa miraba el canal equivocado: un control que no puede
  # representar el fallo no lo caza.
  printf '%s\n' "$texto" > "$DIR/falso-salida"
  printf '%s' "$errtxt" > "$DIR/falso-err"
  printf '#!/bin/sh\ncat "%s/falso-salida"\n[ -s "%s/falso-err" ] && cat "%s/falso-err" >&2\nexit %s\n' \
    "$DIR" "$DIR" "$DIR" "$rct" > "$DIR/falso.sh"
  local out rc
  out=$(K91_B="$DIR/harness" K91_FALSO="$DIR/falso.sh" \
        sh "$DIR/prodsql-doble" "SELECT 1" 2>&1); rc=$?
  if [ "$rc" = "$esperado" ]; then
    pasan=$((pasan+1)); printf '  [ok   ] %-50s rc=%s\n' "$nombre" "$rc"
  else
    fallos=$((fallos+1))
    printf '  [FALLA] %-50s rc=%s (esperaba %s)  salida: %s\n' \
      "$nombre" "$rc" "$esperado" "$(printf '%s' "$out" | head -1 | cut -c1-60)"
  fi
}

echo "K91-control-del-canal · sujeto: $FUENTE"
echo

echo "POSITIVO · un SQL roto NO puede salir con 0"
# P1 · EL FORMATO REAL DEL ERROR DE psql, que es el caso que la version anterior NO cubria.
# psql se invoca con `-f -`, asi que escribe `psql:<stdin>:N: ERROR:  ...` y lo manda por
# STDERR. El control viejo ponia el texto en stdout y sin el prefijo `psql:`: probaba un
# error que este canal no produce, y por eso sus 6 casos pasaron sobre una defensa que
# tenia cero verdaderos positivos.
# El rc del transporte se fuerza a 0 A PROPOSITO: asi el caso ejercita la SEGUNDA defensa y
# no la primera. Si pasara por el rc, no probaria lo que dice probar.
caso "P1 error real de psql por stderr, con rc del transporte 0" 5 \
     ' BTCUSDT|1|2' 0 'psql:<stdin>:1: ERROR:  column "ts" does not exist
LINE 3:          date_trunc(...)'
caso "P2 error de psql SIN prefijo psql: (otra invocacion)" 5 \
     '' 0 'ERROR:  relation "x" does not exist'
caso "P3 el transporte falla (ssh caido)" 255 '' 255 'ssh: connect to host port 22: No route'
caso "P4 psql sale con !=0 y lo dice por stderr" 3 '' 3 'psql:<stdin>:1: ERROR:  syntax error'

echo
echo "NEGATIVO · una consulta buena sigue saliendo con 0"
caso "N1 filas normales" 0 ' BTCUSDT_PERP.A|7524|3|6|34439'
caso "N2 cero filas (vacio NO es error del canal)" 0 ''
# N3 · el texto EN MEDIO de una fila. Lo resolvia ya el ancla, y sigue resuelto.
caso "N3 una FILA que contiene el texto ERROR:" 0 ' BTCUSDT|nivel=ERROR: algo paso|3'
# N4 · EL FALSO POSITIVO DEMOSTRADO, y es el que la version anterior no probaba.
# Una fila cuyo PRIMER campo empieza por ERROR: — `SELECT 'ERROR: esto es un dato'` — daba
# rc=5 con el ancla '^ERROR:'. Hoy no hay ninguna fila asi en produccion (0 en
# pipeline_heartbeat.detail, market_feed_health.detail, data_gap.*_reason y
# scalp_signal_snapshot.reason, medido por el operador), asi que era un fallo LATENTE con
# disparador demostrado en un canal que usan 31 checks. Con los canales separados no puede
# volver: el dato de negocio nunca pasa por stderr.
caso "N4 una FILA cuyo PRIMER campo empieza por ERROR:" 0 'ERROR: esto es un dato'
caso "N5 fila que empieza por ERROR: y ademas filas normales" 0 'ERROR: al inicio
 BTCUSDT|1|2'

echo
total=$((pasan + fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
