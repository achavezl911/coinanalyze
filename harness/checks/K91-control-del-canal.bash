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
nuevo, n = re.subn(
    r'salida=\$\(ssh[^)]*?"\$PROD_SSH_USER@\$PROD_HOST"[^)]*?\)',
    'salida=$(sh "$K91_FALSO")', src, flags=re.S)
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

caso() {  # <nombre> <rc esperado> <salida que finge psql> <rc del transporte>
  local nombre="$1" esperado="$2" texto="$3" rct="${4:-0}"
  printf '%s\n' "$texto" > "$DIR/falso-salida"
  printf '#!/bin/sh\ncat "%s/falso-salida"\nexit %s\n' "$DIR" "$rct" > "$DIR/falso.sh"
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
caso "P1 ERROR de psql al principio de linea" 5 'ERROR:  column "ts" does not exist'
caso "P2 ERROR precedido de filas validas" 5 ' BTCUSDT|1|2
ERROR:  relation "x" does not exist'
caso "P3 el transporte falla (ssh caido)" 255 'ssh: connect to host port 22: No route' 255

echo
echo "NEGATIVO · una consulta buena sigue saliendo con 0"
caso "N1 filas normales" 0 ' BTCUSDT_PERP.A|7524|3|6|34439'
caso "N2 cero filas (vacio NO es error del canal)" 0 ''
# N3 · EL FALSO POSITIVO QUE HAY QUE EVITAR. Si el grep no anclara al principio de linea,
# una fila cuyo TEXTO contenga "ERROR:" -un mensaje de log guardado en una tabla, por
# ejemplo- haria fallar el canal entero. En un canal que usan 31 checks eso seria caro.
caso "N3 una FILA que contiene el texto ERROR:" 0 ' BTCUSDT|nivel=ERROR: algo paso|3'

echo
total=$((pasan + fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
