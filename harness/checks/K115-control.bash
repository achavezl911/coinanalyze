#!/bin/bash
# K115-control · UN PLANTADO QUE TIENE QUE FALLAR POR CADA BRAZO DE K115 (campana 147).
#
# EL ESCENARIO BUENO, sembrado con el RELOJ PLANTADO a las 2026-10-19T21:40:00Z: una base desechable k115_ctl_<pid>
# con las ocho tablas (solo symbol y ts: es lo unico que K115 mira) y un MANIFIESTO como el que escribe archiva.sh,
# desde la primera hora archivada que K115 declara (NACE) hasta la de las 20:00Z, escrita a las 21:13Z. La base
# tiene lo que la poda de 140 le deja: DECIDE 72 h y futuros 12 h, como su coinalyze.env de hoy, y lo demas lo del
# config.py del arbol; la ultima hora de cada tabla, recortada a mitad. El arbol declara DECIDE en 720 h y la base
# solo tiene 72: es la TRANSICION de esta campana, y tiene que salir VERDE. Cada plantado, en su copia:
#
#   hora_quitada      sin la linea de la cinta de las 18:00Z, que la base aun tiene              (a)
#   filas_cambiadas   la linea de DECIDE de las 12:00Z con una fila de mas                       (b)
#   fila_tardia       una fila de celdas escrita en la base despues de archivar su hora          (b)
#   manifiesto_viejo  la copia sin el ultimo pase (las lineas escritas a las 21:13Z)             (c), y sin (a)
#   hora_borrada      la poda del libro L1 avanza hasta las 17:00Z y la hora de las 16:00Z
#                     no esta en el manifiesto                                                   (d)
#   duplicada         una linea dos veces                                                        ROJO
#   sin_manifiesto    no hay fichero                                                             NO MEDIDO
#   base_vacia        las ocho tablas vacias: no absuelve                                        NO MEDIDO
#   canal_caido       una base que no existe                                                     NO MEDIDO (CANAL)
#
# Y el check: sus tres invocaciones (A56) y los dos modos de SIGPIPE (A89) sobre el escenario bueno, y uno plantado.
# No usa produccion ni el espejo. Al salir: 0 bases k115_ctl_<pid>*, el arbol intacto.
set -u
AQUI=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || { echo "control: no resuelvo mi directorio"; exit 2; }
REPO=$(cd -- "$AQUI/../.." && pwd -P)
CHK="$AQUI/K115-el-archivo.sh"
AYU="$AQUI/K115-archivo.py"
PY="$REPO/.venv/bin/python"
H=/var/run/postgresql
for f in "$CHK" "$AYU" "$PY"; do [ -r "$f" ] || { echo "control: falta $f"; exit 2; }; done
PID=$$
DB="k115_ctl_${PID}"
T=$(mktemp -d) || exit 2
ARBOL_ANTES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)
AHORA=2026-10-19T21:40:00Z

limpia() {
  for db in $(psql -h "$H" -d postgres -Atc "SELECT datname FROM pg_database WHERE datname LIKE 'k115_ctl_${PID}%'"); do
    psql -h "$H" -d postgres -qc "DROP DATABASE IF EXISTS \"$db\" WITH (FORCE)" > /dev/null 2>&1
  done
  echo "bases k115_ctl_${PID}* que quedan: $(psql -h "$H" -d postgres -Atc "SELECT count(*) FROM pg_database WHERE datname LIKE 'k115_ctl_${PID}%'")"
  rm -rf "$T"
}
trap limpia EXIT
trap 'limpia; trap - EXIT; exit 143' INT TERM

pasan=0; total=0; fallan=""
comprueba() {  # nombre condicion(0/1) detalle
  total=$((total + 1))
  if [ "$2" = "0" ]; then pasan=$((pasan + 1)); printf '  PASA  %-22s %s\n' "$1" "$3"
  else fallan="$fallan $1"; printf '  FALLA %-22s %s\n' "$1" "$3"; fi
}
dsn() { echo "postgresql:///$1?host=$H"; }
en() { psql -h "$H" -d "$1" -X -q -A -t -v ON_ERROR_STOP=1 -c "$2"; }
copia() {  # nombre -> una base nueva copia de la buena
  psql -h "$H" -d postgres -qc "CREATE DATABASE \"${DB}_$1\" TEMPLATE \"${DB}_base\"" > /dev/null || return 1
  echo "${DB}_$1"
}
huella() {  # base manifiesto -> huella del sujeto: las filas de la base y los bytes del manifiesto
  local b m
  b=$(en "$1" "SELECT md5(string_agg(t || symbol || ts::text, ',' ORDER BY t, symbol, ts)) FROM (SELECT 'cinta' t, symbol, ts FROM orderflow_cinta UNION ALL SELECT 'foto', symbol, ts FROM libro_foto UNION ALL SELECT 'celda', symbol, ts FROM orderflow_celda UNION ALL SELECT 'decide', symbol, ts FROM scalp_signal_snapshot UNION ALL SELECT 'fut', symbol, ts FROM futures_trades_realtime UNION ALL SELECT 'l1', symbol, ts FROM orderbook_snapshot UNION ALL SELECT 'lcob', symbol, ts FROM libro_cobertura UNION ALL SELECT 'ocob', symbol, ts FROM orderflow_cobertura) x" 2>/dev/null || echo sin-base)
  echo "${b:0:8}$( [ -r "$2" ] && sha256sum < "$2" | cut -c1-6 || echo sin-manif)"
}
k115() {  # base manifiesto -> rc; salida en $T/sal
  K115_SUJETO=local K115_BASE="$(dsn "$1")" K115_MANIFIESTO="$2" K115_AHORA="$AHORA" K115_REPO="$REPO" \
    bash "$CHK" > "$T/sal" 2>&1
  echo $?
}

echo "== el escenario bueno a las $AHORA: la base con lo que la poda le deja y el manifiesto hasta el pase de las 21:13Z"
psql -h "$H" -d postgres -qc "CREATE DATABASE \"${DB}_base\"" > /dev/null || exit 2
"$PY" - "$AYU" "$REPO" "$AHORA" "$T/siembra.sql" "$T/manif.tsv" <<'PY' || { echo "control: la siembra fallo"; exit 2; }
import datetime as dt, hashlib, importlib.util, os, sys
ayu, repo, ahora_s, sql_f, man_f = sys.argv[1:]
spec = importlib.util.spec_from_file_location("k115", ayu)
k = importlib.util.module_from_spec(spec); spec.loader.exec_module(k)
os.environ.update(K115_SUJETO="local", K115_REPO=repo)
ret = k.Sujeto().retencion()                       # lo que K115 lee del arbol
poda = {**ret, "scalp_signal_snapshot": 72, "futures_trades_realtime": 12}  # lo que la base de 140 aplica hoy
ahora = k.lee(ahora_s)
pase = ahora.replace(minute=13, second=0)           # el pase de archiva.sh de esta hora (a los :12, 1 min de faena)
H1 = dt.timedelta(hours=1)
def filas(t, h):                                    # cuantas filas tuvo la hora entera: de 1 a 4, segun la hora
    return 1 + (int(h.timestamp()) // 3600 + len(t)) % 4
sim = ["BTC", "ETH", "SOL"]
sql = [f"CREATE TABLE {t} (symbol text NOT NULL, ts timestamptz NOT NULL);" for t in k.TABLAS]
man = ["tabla\thora\tfilas\tbytes\tsha256\tescrito"]
for t in k.TABLAS:
    h, vals = k.lee(k.NACE[t]), []
    while h < ahora:
        n = filas(t, h)
        for i in range(n):
            ts = h + dt.timedelta(seconds=(i + 0.5) * 3600 / n)
            if ahora - dt.timedelta(hours=poda[t]) <= ts < ahora:
                vals.append(f"('{sim[i % 3]}', '{k.iso(ts)}')")
        if h + H1 + dt.timedelta(minutes=10) <= pase:
            sha = hashlib.sha256(f"{t}{h}".encode()).hexdigest()
            man.append(f"{t}\t{k.iso(h)}\t{n}\t{100 * n}\t{sha}\t{k.iso(h + H1 + dt.timedelta(minutes=13))}")
        h += H1
    if vals:
        sql.append(f"INSERT INTO {t} VALUES {', '.join(vals)};")
open(sql_f, "w").write("\n".join(sql) + "\n")
open(man_f, "w").write("\n".join(man) + "\n")
print(f"siembra: {len(man) - 1} lineas de manifiesto; retencion leida del arbol: DECIDE {ret['scalp_signal_snapshot']} h")
PY
psql -h "$H" -d "${DB}_base" -X -q -v ON_ERROR_STOP=1 -f "$T/siembra.sql" > /dev/null || { echo "control: la carga fallo"; exit 2; }
H_BUENA=$(huella "${DB}_base" "$T/manif.tsv")
rc=$(k115 "${DB}_base" "$T/manif.tsv")
comprueba base_verde "$([ "$rc" = 0 ] && head -1 "$T/sal" | grep -q '^VERDE  K115' && echo 0 || echo 1)" "rc=$rc · huella $H_BUENA · $(head -1 "$T/sal" | cut -c1-110)"
decide=$(grep -oE 'scalp_signal_snapshot: [0-9]+ lineas desde [^,]+, [0-9]+ horas contadas contra la base \(retencion 720 h, borde [^)]+\)' "$T/sal")
comprueba transicion_720_72 "$([ -n "$decide" ] && echo 0 || echo 1)" "${decide:-NO SALE: $(grep 'scalp_signal_snapshot:' "$T/sal" | cut -c1-120)}"

planta() {  # nombre esperado_rc patron detalle base manifiesto
  local nombre=$1 rc_e=$2 patron=$3 que=$4 base=$5 man=$6 rc despues visto
  despues=$(huella "$base" "$man")
  rc=$(k115 "$base" "$man")
  visto=$(grep -E "$patron" "$T/sal" | head -1 | cut -c1-150)
  comprueba "$nombre" "$([ "$rc" = "$rc_e" ] && [ -n "$visto" ] && [ "$H_BUENA" != "$despues" ] && echo 0 || echo 1)" \
    "rc=$rc · $H_BUENA -> $despues · ${visto:-NO SALE: $(head -1 "$T/sal" | cut -c1-100)} · $que"
}

echo "== los brazos: cada plantado en su copia, por el brazo que lo tiene que condenar"
grep -vP '^orderflow_cinta\t2026-10-19T18:00:00Z\t' "$T/manif.tsv" > "$T/m-quitada.tsv"
planta hora_quitada 1 "^ROJO  K115 \(a\) orderflow_cinta 2026-10-19T18:00:00Z: cerro hace 160 min y no esta en el manifiesto; la base aun la tiene \([1-4] filas\)" "sin la linea de la cinta de las 18:00Z" "${DB}_base" "$T/m-quitada.tsv"

n=$(grep -P '^scalp_signal_snapshot\t2026-10-19T12:00:00Z\t' "$T/manif.tsv" | cut -f3)
awk -F'\t' -v OFS='\t' '$1 == "scalp_signal_snapshot" && $2 == "2026-10-19T12:00:00Z" { $3 = $3 + 1 } 1' "$T/manif.tsv" > "$T/m-filas.tsv"
planta filas_cambiadas 1 "^ROJO  K115 \(b\) scalp_signal_snapshot 2026-10-19T12:00:00Z: el manifiesto dice $((n + 1)) filas y la base tiene $n$" "las filas de DECIDE de las 12:00Z, $n -> $((n + 1))" "${DB}_base" "$T/m-filas.tsv"

b=$(copia tardia); en "$b" "INSERT INTO orderflow_celda VALUES ('BTC', '2026-10-19T19:30:00Z')" > /dev/null
n=$(grep -P '^orderflow_celda\t2026-10-19T19:00:00Z\t' "$T/manif.tsv" | cut -f3)
planta fila_tardia 1 "^ROJO  K115 \(b\) orderflow_celda 2026-10-19T19:00:00Z: el manifiesto dice $n filas y la base tiene $((n + 1))$" "una fila de celdas a las 19:30Z, despues del pase de las 20:13Z" "$b" "$T/manif.tsv"

grep -vP '\t2026-10-19T21:13:00Z$' "$T/manif.tsv" > "$T/m-viejo.tsv"
planta manifiesto_viejo 1 "^ROJO  K115 \(c\) la ultima linea del manifiesto se escribio a las 2026-10-19T20:13:00Z, hace 87 min" "sin las $(grep -cP '\t2026-10-19T21:13:00Z$' "$T/manif.tsv") lineas del ultimo pase" "${DB}_base" "$T/m-viejo.tsv"
comprueba viejo_sin_a "$([ "$(grep -c '(a)' "$T/sal")" = 0 ] && echo 0 || echo 1)" "lineas (a) en su salida: $(grep -c '(a)' "$T/sal") (la hora de las 20:00Z aun no es exigible)"

b=$(copia borrada); en "$b" "DELETE FROM orderbook_snapshot WHERE ts < '2026-10-19T17:00:00Z'" > /dev/null
grep -vP '^orderbook_snapshot\t2026-10-19T16:00:00Z\t' "$T/manif.tsv" > "$T/m-borrada.tsv"
planta hora_borrada 1 "^ROJO  K115 \(d\) orderbook_snapshot 2026-10-19T16:00:00Z: la base ya no la tiene y no esta en el manifiesto: perdida$" "la poda del L1 hasta las 17:00Z y sin la linea de las 16:00Z" "$b" "$T/m-borrada.tsv"

{ cat "$T/manif.tsv"; grep -P '^libro_foto\t2026-10-19T10:00:00Z\t' "$T/manif.tsv"; } > "$T/m-dup.tsv"
planta duplicada 1 "^ROJO  K115 manifiesto ilegible: libro_foto 2026-10-19T10:00:00Z esta 2 veces$" "una linea de libro_foto dos veces" "${DB}_base" "$T/m-dup.tsv"

planta sin_manifiesto 2 "^NO MEDIDO: K115 no hay manifiesto del archivo en local $T/no-existe.tsv$" "K115_MANIFIESTO a un fichero que no existe" "${DB}_base" "$T/no-existe.tsv"

b=$(copia vacia)
for t in orderflow_cinta libro_foto orderflow_celda scalp_signal_snapshot futures_trades_realtime orderbook_snapshot libro_cobertura orderflow_cobertura; do
  en "$b" "DELETE FROM $t" > /dev/null
done
planta base_vacia 2 "^NO MEDIDO: K115 \(b\) sin juzgar: la base no tiene ninguna hora entera archivada de orderflow_cinta, " "las ocho tablas vacias" "$b" "$T/manif.tsv"

rc=$(k115 "${DB}_no_existe" "$T/manif.tsv")
comprueba canal_caido "$([ "$rc" = 2 ] && head -1 "$T/sal" | grep -q '^NO MEDIDO (CANAL): K115' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sal" | cut -c1-110)"

echo "== el check: A89 los dos modos de SIGPIPE y A56 las tres invocaciones, sobre la base buena; y uno plantado"
ENV=(K115_SUJETO=local "K115_BASE=$(dsn "${DB}_base")" "K115_MANIFIESTO=$T/manif.tsv" "K115_AHORA=$AHORA" "K115_REPO=$REPO")
for modo in --ignore-signal=PIPE --default-signal=PIPE; do
  env "$modo" "${ENV[@]}" bash "$CHK" > "$T/chk" 2>&1; rc=$?
  comprueba "sigpipe$modo" "$([ "$rc" = 0 ] && head -1 "$T/chk" | grep -q '^VERDE  K115' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-90)"
done
(env "${ENV[@]}" bash "$CHK" > "$T/chk" 2>&1); rc=$?
comprueba invocacion_absoluta "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-90)"
(cd "$REPO" && env "${ENV[@]}" bash harness/checks/K115-el-archivo.sh > "$T/chk" 2>&1); rc=$?
comprueba invocacion_relativa "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-90)"
(cd /tmp && env "${ENV[@]}" bash "$CHK" > "$T/chk" 2>&1); rc=$?
comprueba invocacion_ajena "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-90)"
(env K115_SUJETO=local "K115_BASE=$(dsn "${DB}_base")" "K115_MANIFIESTO=$T/m-quitada.tsv" "K115_AHORA=$AHORA" "K115_REPO=$REPO" bash "$CHK" > "$T/chk" 2>&1); rc=$?
comprueba el_check_condena "$([ "$rc" = 1 ] && head -1 "$T/chk" | grep -q '^ROJO  K115 (a) orderflow_cinta' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-90)"

echo "== restaurado"
H_FIN=$(huella "${DB}_base" "$T/manif.tsv")
comprueba escenario_restaurado "$([ "$H_FIN" = "$H_BUENA" ] && echo 0 || echo 1)" "huella del escenario bueno $H_BUENA y al final $H_FIN"
ARBOL_DESPUES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)
comprueba arbol_intacto "$([ "$ARBOL_ANTES" = "$ARBOL_DESPUES" ] && echo 0 || echo 1)" "git status del arbol $ARBOL_ANTES -> $ARBOL_DESPUES"

echo
echo "K115-control: $pasan de $total${fallan:+ · FALLAN:$fallan}"
[ "$pasan" = "$total" ]
