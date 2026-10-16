#!/bin/bash
# K107-control · UN PLANTADO QUE TIENE QUE FALLAR POR CADA COSA QUE K107 PROMETE (campana 139, C2-C5).
#
# EL ESCENARIO BUENO es una COPIA DEL REGISTRO de produccion (K107-copia.json: los dos DISPARADOS de la
# historia, sus episodios, la SOMBRA de v1 de su mismo episodio, el reglamento registrado y las velas de 1 min
# de sus vidas, congelados el 2026-10-16 por bin/prodsql) cargada con sql/schema.sql DEL ARBOL en una base
# desechable k107_ctl_<pid>, en el esquema `copia` con el RELOJ PLANTADO a las 2026-10-15T06:00:00Z: 3945 toco
# su stop a las 05:16Z y su reloj caduca a las 08:45Z; 2632 se invalido el 10-12. Sobre ella lo que el ARBOL
# guarda y sirve en /api/entradas tiene que salir VERDE, y cada plantado -en su propia copia (createdb -T)-
# tiene que caer por SU brazo:
#
#   guardado_que_no_sale   una fila de entrada_resultado con huellas validas y otra salida (A, y B al servirla)
#   main_sirve_vivo        lo que sirve main en la misma copia y a la misma hora: 3945 VIVO y sin resultado (B)
#   final_sin_guardar      la fila FINAL de 3945 no esta y su asentamiento paso hace mas de 15 min (C)
#   cuentas_que_no_salen   la respuesta sirve un resuelto de mas (D)
#   papel_que_no_sale      la respuesta sirve otro saldo en la cuenta de v2 (E)
#   papel_una_operacion    otro P&L en UNA operacion de v2, con el saldo y n intactos: la linea nombra la
#                          operacion y el campo, con sus dos valores (E; remate de la 139, R3)
#   pendiente_servido      sin la vela de entrada de 3945: el arbol lo sirve pendiente y la cuenta provisional:
#                          VERDE (remate de la 139, R2)
#   pendiente_como_saltado lo mismo servido como en d9f4520 -saltado, y la cuenta final-: lo condena E (R2)
#   catalogo_sin_guardia   sin el disparador que rechaza TRUNCATE (F)
#   velas_podadas          sin las velas de 2632: NO MEDIDO para ese, y VERDE lo demas (ni absuelve ni condena)
#   todo_podado            sin ninguna vela: NO MEDIDO (rc=2), nunca VERDE
#   sin_la_tabla           schema.sql de main: ROJO «FALTA DESPLEGAR»
#   canal_caido            una base que no existe: NO MEDIDO (CANAL)
#   provisional / recien   a las 05:30Z (STOP provisional) y a las 05:18Z: el arbol sirve lo provisional fiel
#
# Y el check: sus tres invocaciones (A56) y los dos modos de SIGPIPE (A89) sobre el escenario bueno, y uno
# plantado. No usa produccion ni el espejo. Al salir: 0 bases k107_ctl_<pid>*, el arbol intacto.
set -u
AQUI=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || { echo "control: no resuelvo mi directorio"; exit 2; }
REPO=$(cd -- "$AQUI/../.." && pwd -P)
CHK="$AQUI/K107-el-resultado-que-sale-de-su-plan.sh"
AYU="$AQUI/K107-resultado.py"
COPIA="$AQUI/K107-copia.json"
PY="$REPO/.venv/bin/python"
H=/var/run/postgresql
for f in "$CHK" "$AYU" "$COPIA" "$PY"; do [ -r "$f" ] || { echo "control: falta $f"; exit 2; }; done
PID=$$
DB="k107_ctl_${PID}"
T=$(mktemp -d) || exit 2
ARBOL_ANTES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)
RELOJ=2026-10-15T06:00:00Z

limpia() {
  for db in $(psql -h "$H" -d postgres -Atc "SELECT datname FROM pg_database WHERE datname LIKE 'k107_ctl_${PID}%'"); do
    psql -h "$H" -d postgres -qc "DROP DATABASE IF EXISTS \"$db\" WITH (FORCE)" > /dev/null 2>&1
  done
  echo "bases k107_ctl_${PID}* que quedan: $(psql -h "$H" -d postgres -Atc "SELECT count(*) FROM pg_database WHERE datname LIKE 'k107_ctl_${PID}%'")"
  rm -rf "$T"
}
trap limpia EXIT
trap 'limpia; trap - EXIT; exit 143' INT TERM

pasan=0; total=0; fallan=""
comprueba() {  # nombre condicion(0/1) detalle
  total=$((total + 1))
  if [ "$2" = "0" ]; then pasan=$((pasan + 1)); printf '  PASA  %-24s %s\n' "$1" "$3"
  else fallan="$fallan $1"; printf '  FALLA %-24s %s\n' "$1" "$3"; fi
}
dsn() { echo "postgresql:///$1?host=$H"; }
copia() {  # nombre [plantilla] -> una base nueva: por omision la copia LIMPIA (cargada, sin nada guardado)
  psql -h "$H" -d postgres -qc "CREATE DATABASE \"${DB}_$1\" TEMPLATE \"${DB}_${2:-limpia}\"" > /dev/null || return 1
  echo "${DB}_$1"
}
en() {  # base sql -> lo que devuelve, con el esquema y el reloj de la copia
  psql -h "$H" -d "$1" -X -q -A -t -v ON_ERROR_STOP=1 -c "SET search_path TO copia, pg_catalog, public; $2"
}
sirve() {  # arbol base reloj salida -> lo que ese arbol sirve en /api/entradas
  "$PY" -S "$AYU" sirve "$1" "$(dsn "$2")" copia "$3" "$4"
}
huella() {  # base servido -> huella del sujeto: lo guardado, las velas, el catalogo y lo servido
  local h
  h=$(en "$1" "SELECT md5(coalesce((SELECT string_agg(registro_id || salida || huella_resultado, ',' ORDER BY registro_id) FROM entrada_resultado), '') || (SELECT count(*) FROM ohlcv) || coalesce((SELECT string_agg(tgname, ',' ORDER BY tgname) FROM pg_trigger WHERE tgrelid = 'entrada_resultado'::regclass), ''))" 2>/dev/null || echo sin-tabla)
  echo "${h:0:10}$( [ -r "$2" ] && sha256sum < "$2" | cut -c1-6)"
}
k107() {  # base servido reloj -> rc; salida en $T/sal
  K107_SUJETO=local K107_BASE="$(dsn "$1")" K107_ESQUEMA=copia K107_RELOJ="$3" K107_SERVIDO="$2" \
    bash "$CHK" > "$T/sal" 2>&1
  echo $?
}

echo "== la base: la copia del registro con schema.sql del arbol, y lo que el arbol guarda y sirve a las $RELOJ"
psql -h "$H" -d postgres -qc "CREATE DATABASE \"${DB}_limpia\"" > /dev/null || exit 2
"$PY" "$AYU" carga "$COPIA" "$(dsn "${DB}_limpia")" "$REPO/sql/schema.sql" > "$T/carga" 2>&1 || { echo "control: la carga fallo: $(tail -1 "$T/carga")"; exit 2; }
head -1 "$T/carga"
copia base > /dev/null || exit 2
sirve "$REPO" "${DB}_base" "$RELOJ" "$T/servido-base.json" || { echo "control: el arbol no sirve"; exit 2; }
H_BUENA=$(huella "${DB}_base" "$T/servido-base.json")
rc=$(k107 "${DB}_base" "$T/servido-base.json" "$RELOJ")
comprueba base_verde "$([ "$rc" = 0 ] && head -1 "$T/sal" | grep -q '^VERDE  K107' && echo 0 || echo 1)" "rc=$rc · huella $H_BUENA · $(head -1 "$T/sal" | cut -c1-120)"

planta() {  # nombre esperado_rc patron detalle base servido reloj antes
  local nombre=$1 rc_e=$2 patron=$3 que=$4 base=$5 serv=$6 reloj=$7 antes=$8 rc despues visto
  despues=$(huella "$base" "$serv")
  rc=$(k107 "$base" "$serv" "$reloj")
  visto=$(grep -E "$patron" "$T/sal" | head -1 | cut -c1-140)
  comprueba "$nombre" "$([ "$rc" = "$rc_e" ] && [ -n "$visto" ] && [ "$antes" != "$despues" ] && echo 0 || echo 1)" \
    "rc=$rc · $antes -> $despues · ${visto:-NO SALE: $(head -1 "$T/sal" | cut -c1-100)} · $que"
}

echo "== los brazos: cada plantado en su propia copia, por el brazo que lo tiene que condenar"
# A · una fila guardada con huellas validas que dice OTRA salida, antes de que el arbol guarde la suya: la
# verdadera de 3945 (la que guardo la base buena) con la salida y el precio de T1
b=$(copia guardado)
verdadera=$(en "${DB}_base" "SELECT resultado::text FROM entrada_resultado WHERE registro_id = 3945")
"$PY" - "$(dsn "$b")" "$RELOJ" "$verdadera" <<'PY'
import hashlib, json, subprocess, sys
dsn, reloj, texto = sys.argv[1:]
r = json.loads(texto)
r.update(salida="objetivo", precio=106.843)
sys.path.insert(0, "/srv/coinanalyze/repo")
from app.entradas import reglamento as R
falso = R.canonico(r)
conv = R.canonico({"version": r["resolutor"], "convenciones": __import__("app.entradas.resolutor", fromlist=["x"]).CONVENCIONES})
sql = ("SET search_path TO copia, pg_catalog, public; "
       "DO $r$ BEGIN PERFORM set_config('reloj.desfase', ('" + reloj + "'::timestamptz - pg_catalog.clock_timestamp())::text, false); END $r$; "
       "INSERT INTO entrada_resultado (registro_id, resolutor, huella_convenciones, hipotetico, salida, instante, asentado_en, "
       "huella_resultado, resultado, convenciones) VALUES (3945, %s, %s, false, 'objetivo', %s, %s, %s, %s::json, %s::json)")
q = lambda v: "'" + str(v).replace("'", "''") + "'"
sql = sql % (q(r["resolutor"]), q(r["huella_convenciones"]), q(r["instante"]), q(r["asentado_en"]),
             q(hashlib.sha256(falso.encode()).hexdigest()), q(falso), q(conv))
subprocess.run(["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-d", dsn, "-c", sql], check=True)
PY
sirve "$REPO" "$b" "$RELOJ" "$T/s-guardado.json"
planta guardado_que_no_sale 1 "^   - A 3945: lo guardado dice objetivo" "una fila con huellas validas y salida objetivo" "$b" "$T/s-guardado.json" "$RELOJ" "$H_BUENA"

# B · lo que sirve main en la misma copia y a la misma hora
mkdir -p "$T/main"; git -C "$REPO" archive main app config | tar -x -C "$T/main"
git -C "$REPO" show main:sql/schema.sql > "$T/main-schema.sql"
b=$(copia main base)   # con lo que el arbol ya guardo: main no lo lee, pero el sujeto lo tiene
sirve "$T/main" "$b" "$RELOJ" "$T/s-main.json"
planta main_sirve_vivo 1 "^   - B 3945: servido VIVO y su plan ya acabo: stop a las 05:16Z" "main sirve 3945 entre los vivos" "$b" "$T/s-main.json" "$RELOJ" "$H_BUENA"

# C · lo final sin guardar: la copia buena sin la fila de 3945, juzgada a las 07:00Z (una hora despues de su
# asentamiento de las 05:59Z; la holgura del bucle de la API es de 15 min) con la respuesta de las 06:00Z
b=$(copia final base)
en "$b" "ALTER TABLE entrada_resultado DISABLE TRIGGER USER; DELETE FROM entrada_resultado WHERE registro_id = 3945; ALTER TABLE entrada_resultado ENABLE TRIGGER USER" > /dev/null
cp "$T/servido-base.json" "$T/s-final.json"
planta final_sin_guardar 1 "^   - C 3945: FINAL desde las 2026-10-15T05:59:00Z" "sin la fila guardada de 3945, a las 07:00Z" "$b" "$T/s-final.json" 2026-10-15T07:00:00Z "$H_BUENA"

# D · un resuelto de mas en la celda de 3945
"$PY" -c "import json,sys; r=json.load(open(sys.argv[1])); [c.update(resueltos=c['resueltos']+1) for c in r['cuentas'] if (c['familia'],c['perfil'],c['version'])==('F1','intradia','v2') and c['lado']=='largo']; json.dump(r,open(sys.argv[2],'w'))" "$T/servido-base.json" "$T/s-cuentas.json"
planta cuentas_que_no_salen 1 "^   - D F1/intradia/largo/v2: sirve 2 resueltos y hay 1 guardados" "resueltos 1 -> 2" "${DB}_base" "$T/s-cuentas.json" "$RELOJ" "$H_BUENA"

# E · otro saldo en la cuenta de v2
"$PY" -c "import json,sys; r=json.load(open(sys.argv[1])); r['papel']['v2']['saldo_usd']+=1; json.dump(r,open(sys.argv[2],'w'))" "$T/servido-base.json" "$T/s-papel.json"
planta papel_que_no_sale 1 "^   - E v2: la cuenta de papel servida no es la de sus resultados: saldo_usd servido 197.14, recalculado 196.14$" "saldo 196,14 -> 197,14" "${DB}_base" "$T/s-papel.json" "$RELOJ" "$H_BUENA"
# E · otro P&L en una sola operacion, y el resumen intacto: la linea dice cual y que, con dos valores distintos
"$PY" -c "import json,sys; r=json.load(open(sys.argv[1])); op=r['papel']['v2']['operaciones'][0]; assert op['registro_id']==2632; op['pnl_usd']=round(op['pnl_usd']+1,2); json.dump(r,open(sys.argv[2],'w'))" "$T/servido-base.json" "$T/s-papel-op.json"
planta papel_una_operacion 1 "^   - E v2: la cuenta de papel servida no es la de sus resultados: operaciones\[2632\]\.pnl_usd servido (-?[0-9.]+), recalculado (-?[0-9.]+)$" "pnl de la operacion 2632 +1 USD; saldo y n intactos" "${DB}_base" "$T/s-papel-op.json" "$RELOJ" "$H_BUENA"
dos=$(grep -oE 'operaciones\[2632\]\.pnl_usd servido -?[0-9.]+, recalculado -?[0-9.]+$' "$T/sal" | head -1)
x=${dos#*servido }; x=${x%%,*}; y=${dos##*recalculado }
comprueba papel_dos_lados_distintos "$([ -n "$dos" ] && [ "$x" != "$y" ] && echo 0 || echo 1)" "servido ${x:-?} · recalculado ${y:-?}"

# E · un DISPARADO sin su vela de entrada (remate de la 139, R2): en la copia LIMPIA, sin la vela de entrada de
# 3945, el arbol lo sirve PENDIENTE y la cuenta PROVISIONAL, y K107 da VERDE; servido como en d9f4520 -saltado,
# y la cuenta final- lo condena E por esos campos
b=$(copia pendiente)
en "$b" "DELETE FROM ohlcv WHERE symbol = 'SOLUSDT_PERP.A' AND interval = '1min' AND ts = (SELECT date_trunc('minute', registered_at) + interval '1 minute' FROM entrada_registro WHERE registro_id = 3945)" > /dev/null
sirve "$REPO" "$b" "$RELOJ" "$T/s-pendiente.json"
H_PEND=$(huella "$b" "$T/s-pendiente.json")
pend=$("$PY" -c "import json,sys; p=json.load(open(sys.argv[1]))['papel']['v2']; print([x['registro_id'] for x in p['pendientes']], [x['registro_id'] for x in p['saltados']], p['firmeza'])" "$T/s-pendiente.json")
rc=$(k107 "$b" "$T/s-pendiente.json" "$RELOJ")
comprueba pendiente_servido "$([ "$rc" = 0 ] && [ "$pend" = "[3945] [] provisional" ] && [ "$H_PEND" != "$H_BUENA" ] && echo 0 || echo 1)" "rc=$rc · $H_BUENA -> $H_PEND · papel v2 (pendientes, saltados, firmeza): $pend"
"$PY" -c "import json,sys; r=json.load(open(sys.argv[1])); p=r['papel']['v2']; p['saltados']+=[{**x, 'motivo': 'aun sin entrada real: falta la vela de su entrada'} for x in p.pop('pendientes')]; p.pop('sin_posicion'); p['firmeza']='final'; json.dump(r,open(sys.argv[2],'w'))" "$T/s-pendiente.json" "$T/s-pendiente-d9.json"
planta pendiente_como_saltado 1 "^   - E v2: la cuenta de papel servida no es la de sus resultados: firmeza servido \"final\", recalculado \"provisional\"; saltados\[3945\] se sirve" "3945 saltado y la cuenta final, como en d9f4520" "$b" "$T/s-pendiente-d9.json" "$RELOJ" "$H_PEND"

# F · sin el disparador que rechaza TRUNCATE
b=$(copia catalogo base); en "$b" "DROP TRIGGER entrada_resultado_no_truncate ON entrada_resultado" > /dev/null
planta catalogo_sin_guardia 1 "^   - F entrada_resultado sin su disparador entrada_resultado_no_truncate" "DROP TRIGGER" "$b" "$T/servido-base.json" "$RELOJ" "$H_BUENA"

# la poda: sin las velas de 2632 NO MEDIDO para ese, y VERDE lo demas; sin ninguna, NO MEDIDO
b=$(copia poda base); en "$b" "DELETE FROM ohlcv WHERE ts < '2026-10-14'" > /dev/null
planta velas_podadas 0 "^   NO MEDIDO 2632: sus velas ya se podaron" "sin las velas del 10-12" "$b" "$T/servido-base.json" "$RELOJ" "$H_BUENA"
b=$(copia todo base); en "$b" "DELETE FROM ohlcv" > /dev/null
planta todo_podado 2 "^NO MEDIDO: ningun resultado se pudo recalcular" "sin ninguna vela" "$b" "$T/servido-base.json" "$RELOJ" "$H_BUENA"

# sin la tabla: la copia con el schema.sql de main
psql -h "$H" -d postgres -qc "CREATE DATABASE \"${DB}_sintabla\"" > /dev/null
"$PY" "$AYU" carga "$COPIA" "$(dsn "${DB}_sintabla")" "$T/main-schema.sql" > /dev/null 2>&1
sirve "$T/main" "${DB}_sintabla" "$RELOJ" "$T/s-sintabla.json"
planta sin_la_tabla 1 "^ROJO  K107 FALTA DESPLEGAR: el sujeto no tiene entrada_resultado" "schema.sql de main" "${DB}_sintabla" "$T/s-sintabla.json" "$RELOJ" "$H_BUENA"

# el canal: una base que no existe
rc=$(k107 "${DB}_no_existe" "$T/servido-base.json" "$RELOJ")
comprueba canal_caido "$([ "$rc" = 2 ] && head -1 "$T/sal" | grep -q '^NO MEDIDO (CANAL)' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sal" | cut -c1-110)"

# lo provisional: a las 05:30Z el stop de las 05:16Z no esta asentado; a las 05:18Z acaba de pasar
for reloj in 2026-10-15T05:30:00Z 2026-10-15T05:18:00Z; do
  b=$(copia "p${reloj:11:2}${reloj:14:2}")
  sirve "$REPO" "$b" "$reloj" "$T/s-prov.json"
  prov=$("$PY" -c "import json,sys; r=json.load(open(sys.argv[1])); print([ (p['resultado']['salida'], p['resultado']['firmeza']) for l in r['por_lado'].values() for p in l['ventana']['disparados'] if p['registro_id']==3945])" "$T/s-prov.json")
  rc=$(k107 "$b" "$T/s-prov.json" "$reloj")
  comprueba "provisional_${reloj:11:5}" "$([ "$rc" = 0 ] && [ "$prov" = "[('stop', 'provisional')]" ] && echo 0 || echo 1)" "rc=$rc · 3945 servido $prov · $(head -1 "$T/sal" | cut -c1-90)"
done

echo "== el check: A89 los dos modos de SIGPIPE y A56 las tres invocaciones, sobre la base buena; y uno plantado"
ENV=(K107_SUJETO=local "K107_BASE=$(dsn "${DB}_base")" K107_ESQUEMA=copia "K107_RELOJ=$RELOJ" "K107_SERVIDO=$T/servido-base.json")
for modo in --ignore-signal=PIPE --default-signal=PIPE; do
  env "$modo" "${ENV[@]}" bash "$CHK" > "$T/chk" 2>&1; rc=$?
  comprueba "sigpipe$modo" "$([ "$rc" = 0 ] && head -1 "$T/chk" | grep -q '^VERDE  K107' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-90)"
done
(env "${ENV[@]}" bash "$CHK" > "$T/chk" 2>&1); rc=$?
comprueba invocacion_absoluta "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-90)"
(cd "$REPO" && env "${ENV[@]}" bash harness/checks/K107-el-resultado-que-sale-de-su-plan.sh > "$T/chk" 2>&1); rc=$?
comprueba invocacion_relativa "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-90)"
(cd /tmp && env "${ENV[@]}" bash "$CHK" > "$T/chk" 2>&1); rc=$?
comprueba invocacion_ajena "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-90)"
(env K107_SUJETO=local "K107_BASE=$(dsn "${DB}_base")" K107_ESQUEMA=copia "K107_RELOJ=$RELOJ" "K107_SERVIDO=$T/s-papel.json" bash "$CHK" > "$T/chk" 2>&1); rc=$?
comprueba el_check_condena "$([ "$rc" = 1 ] && head -1 "$T/chk" | grep -q '^ROJO  K107 E v2' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-90)"

echo "== restaurado"
H_FIN=$(huella "${DB}_base" "$T/servido-base.json")
comprueba escenario_restaurado "$([ "$H_FIN" = "$H_BUENA" ] && echo 0 || echo 1)" "huella de la base buena $H_BUENA y al final $H_FIN"
ARBOL_DESPUES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)
comprueba arbol_intacto "$([ "$ARBOL_ANTES" = "$ARBOL_DESPUES" ] && echo 0 || echo 1)" "git status del arbol $ARBOL_ANTES -> $ARBOL_DESPUES"

echo
echo "K107-control: $pasan de $total${fallan:+ · FALLAN:$fallan}"
[ "$pasan" = "$total" ]
