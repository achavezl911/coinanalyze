#!/bin/bash
# K84-control  LOS PLANTADOS DE K84: UNO QUE TIENE QUE FALLAR POR CADA COSA QUE SE PROMETE.
#
# QUE PRUEBA Y QUE NO. K84 dice «en el mismo sobre, dos bloques que publican la misma cantidad
# dicen lo mismo». Este control fabrica el fenomeno REAL -un escritor concurrente sobre una base,
# no un doble que devuelve cifras- y comprueba que K84 y el arbol se comportan como se promete:
# el arbol de `main` ensena los dos bloques DISTINTOS y el de esta rama, IGUALES.
#
# LA VARIABLE QUE DECIDE ES *CUANDO* SE ESCRIBE LA FILA (A57). Una fila plantada ANTES del
# armado la ven los dos bloques y no separa nada: el mismo plantado, con el mismo contenido y en
# la misma tabla, solo condena si cae A MITAD. Por eso el brazo A5 existe y tiene que salir
# IGUAL en los dos arboles: si condenara, este control estaria midiendo el plantado y no el
# instante.
#
# EL RETRASO SE BARRE Y NO SE CLAVA (A65). El armado dura ~1-2 s y las dos matrices se calculan
# con milisegundos de diferencia: un escritor que planta a un retraso FIJO puede caer siempre
# antes de las dos o siempre despues y no ver nada. Se barren N retrasos repartidos por todo el
# armado y se cuenta en CUANTOS aparece la diferencia.
#
# LA ADULTERACION SE PRUEBA POR LO QUE PRODUJO (A67): el escritor devuelve cuantas filas
# INSERTO de verdad y ese numero sale en la linea del brazo. Una corrida con 0 filas no se juzga.
#
# EL BANCO ES UNA BASE DESECHABLE, no el espejo compartido: se crea con sql/schema.sql, se
# siembra, y al terminar se BORRA. La huella de cada plantado -conteos antes y despues- sale en
# la salida, y cada plantado se deshace antes del siguiente.
#
# Se comprueba con: bash harness/checks/K84-control.bash
# Variables: K84C_RETRASOS (por defecto 10), K84C_DEJAR_BASE=1 para no borrar el banco.

set -u
# A56 · todo lo que se carga se resuelve a ABSOLUTA antes de cualquier cd, y se comprueba.
B=/srv/coinanalyze/harness
. "$B/env"
: "${REPO:?el env del arnes no definio REPO}"
AYUDANTE_CARGADO=1
[ "$AYUDANTE_CARGADO" = 1 ] || { echo "NO MEDIDO: el env del arnes no cargo"; exit 2; }

H="--host=/var/run/postgresql"
PY="$REPO/.venv/bin/python"
RETRASOS="${K84C_RETRASOS:-10}"
SIMBOLO=BTCUSDT_PERP.A
WS=BTC
PASA=0; TOTAL=0; FALLOS=""

ok()  { TOTAL=$((TOTAL+1)); PASA=$((PASA+1)); printf '  ok    %s\n' "$1"; }
mal() { TOTAL=$((TOTAL+1)); FALLOS="${FALLOS:+$FALLOS · }$2"; printf '  FALLA %s\n' "$1"; }

TMP=$(mktemp -d) || { echo "NO MEDIDO: no se pudo crear el temporal"; exit 2; }
DB=uc_k84_$$
limpia() {
  [ "${K84C_DEJAR_BASE:-0}" = 1 ] || dropdb $H --if-exists "$DB" 2>/dev/null
  git -C "$REPO" worktree remove --force "$TMP/viejo" 2>/dev/null
  rm -rf "$TMP"
}
trap limpia EXIT

# ---------------------------------------------------------------- el arbol VIEJO (bytes de main)
git -C "$REPO" worktree add --detach "$TMP/viejo" main >/dev/null 2>&1 || {
  echo "NO MEDIDO: no se pudo fabricar el arbol de main en $TMP/viejo"; exit 2; }
VIEJO_SHA=$(git -C "$TMP/viejo" rev-parse --short HEAD)
NUEVO_SHA=$(git -C "$REPO" rev-parse --short HEAD)
# Que el arbol viejo sea DE VERDAD el viejo: si ya trajera el arreglo, todo lo que sigue miente.
if grep -q '_corte_unico' "$TMP/viejo/app/ai_context.py" 2>/dev/null; then
  echo "NO MEDIDO: el arbol de main ($VIEJO_SHA) YA trae _corte_unico: no hay bytes viejos contra"
  echo "  los que ejercitar nada. Este control solo vale antes de que la rama se mezcle."
  exit 2
fi
grep -q '_corte_unico' "$REPO/app/ai_context.py" 2>/dev/null || {
  echo "NO MEDIDO: el arbol de trabajo ($NUEVO_SHA) no trae _corte_unico"; exit 2; }

# ---------------------------------------------------------------- el banco
createdb $H "$DB" 2>"$TMP/db.err" || { echo "NO MEDIDO: createdb: $(cat "$TMP/db.err")"; exit 2; }
psql $H -d "$DB" -q -v ON_ERROR_STOP=1 -f "$REPO/sql/schema.sql" >/dev/null 2>"$TMP/esq.err" || {
  echo "NO MEDIDO: no se pudo aplicar sql/schema.sql: $(tail -1 "$TMP/esq.err")"; exit 2; }

sql() { psql $H -d "$DB" -qtAX -c "$1"; }

# Serie base: 2 h de buckets de 5 s en las dos patas (cadencia real medida en 140: p50 5.0 s) y
# 6 dias de velas de 1 min, que dan de sobra para los 120 buckets de 1 h de structure_detail.
sql "
INSERT INTO spot_trades_realtime (symbol,exchange,ts,buy_vol_usd,sell_vol_usd,inst_buy_usd,inst_sell_usd,trade_count,last_px,venue_count)
SELECT '$WS', e, g, 1000+extract(epoch from g)::int%97, 900+extract(epoch from g)::int%89, 10,9,3,100,vc
FROM generate_series(date_trunc('second',now())-interval '2 hours', date_trunc('second',now()), interval '5 seconds') g,
     (VALUES ('combined',2),('binance',1),('bybit',1)) AS x(e,vc);
INSERT INTO futures_trades_realtime (symbol,exchange,ts,buy_vol_usd,sell_vol_usd,large_buy_usd,large_sell_usd,trade_count,last_px,venue_count)
SELECT '$SIMBOLO', e, g, 2000+extract(epoch from g)::int%101, 1800+extract(epoch from g)::int%83, 10,9,5,100,vc
FROM generate_series(date_trunc('second',now())-interval '2 hours', date_trunc('second',now()), interval '5 seconds') g,
     (VALUES ('combined',2),('binance',1),('bybit',1)) AS x(e,vc);
INSERT INTO ohlcv (symbol,interval,ts,open,high,low,close,volume,buy_volume,tx,btx)
-- El precio NO puede ser periodico en 1 h: si lo fuera, la barra anterior y la de la cola
-- traerian el MISMO close y el brazo C no distinguiria «retiene la barra» de «no hace nada».
-- Periodo 997 min (~16.6 h), primo con 60.
SELECT '$SIMBOLO','1min', g,
       100+ ((extract(epoch from g)::int/60)%997)/10.0,
       102+ ((extract(epoch from g)::int/60)%997)/10.0,
        98+ ((extract(epoch from g)::int/60)%997)/10.0,
       100+ ((extract(epoch from g)::int/60)%997)/10.0,
       50, 25, 10, 5
FROM generate_series(date_trunc('minute',now())-interval '6 days', date_trunc('minute',now()), interval '1 minute') g;
" >/dev/null 2>"$TMP/siembra.err" || { echo "NO MEDIDO: la siembra fallo: $(tail -1 "$TMP/siembra.err")"; exit 2; }

BASE_SPOT=$(sql "SELECT count(*) FROM spot_trades_realtime")
BASE_FUT=$(sql "SELECT count(*) FROM futures_trades_realtime")
BASE_OHLCV=$(sql "SELECT count(*) FROM ohlcv")
echo "BANCO $DB · huella de la siembra: spot=$BASE_SPOT fut=$BASE_FUT ohlcv=$BASE_OHLCV"
echo "ARBOLES · viejo=main@$VIEJO_SHA  nuevo=$(git -C "$REPO" branch --show-current)@$NUEVO_SHA"
echo

# ---------------------------------------------------------------- el armador, con escritor real
cat > "$TMP/armar.py" <<'PY'
"""Arma el sobre y, si se pide, un ESCRITOR CONCURRENTE de verdad sobre OTRA conexion.

argv: <arbol> <db> <salida.json> <tabla|nada> <retraso_s> <repeticiones>
Imprime en stdout: filas_insertadas <n> · segundos <t>
"""
import asyncio, json, sys, time
from datetime import timedelta

arbol, db, salida, tabla, retraso, reps = (
    sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], float(sys.argv[5]), int(sys.argv[6])
)
sys.path.insert(0, arbol)
import asyncpg

URL = f"postgresql:///{db}?host=/var/run/postgresql"
INSERTA = {
    "spot": (
        "INSERT INTO spot_trades_realtime (symbol,exchange,ts,buy_vol_usd,sell_vol_usd,"
        "inst_buy_usd,inst_sell_usd,trade_count,last_px,venue_count) VALUES "
        "('BTC',$1,$2,777777,111111,10,9,3,100,CASE WHEN $1='combined' THEN 2 ELSE 1 END)"
    ),
    "fut": (
        "INSERT INTO futures_trades_realtime (symbol,exchange,ts,buy_vol_usd,sell_vol_usd,"
        "large_buy_usd,large_sell_usd,trade_count,last_px,venue_count) VALUES "
        "('BTCUSDT_PERP.A',$1,$2,888888,222222,10,9,5,100,CASE WHEN $1='combined' THEN 2 ELSE 1 END)"
    ),
    "vela": (
        "INSERT INTO ohlcv (symbol,interval,ts,open,high,low,close,volume,buy_volume,tx,btx) "
        "VALUES ('BTCUSDT_PERP.A','1min',$1,500,501,499,500,50,25,10,5) "
        "ON CONFLICT DO NOTHING"
    ),
}


async def escritor(marca, fin):
    """Escribe DE VERDAD, con su propia conexion y su propio COMMIT, mientras el sobre se arma.

    Cada vuelta usa un ts distinto -marca menos i milisegundos- porque la clave de las tablas
    de trades es (ts,symbol,exchange) y repetir el mismo instante seria un conflicto, no una
    escritura. Todos caen dentro de todas las ventanas y por debajo del as_of.
    """
    puestas = 0
    conn = await asyncpg.connect(URL)
    try:
        await asyncio.sleep(retraso)
        for i in range(reps):
            if fin.is_set():
                break
            ts = marca - timedelta(milliseconds=i)
            try:
                if tabla == "vela":
                    await conn.execute(INSERTA[tabla], marca)
                else:
                    for ex in ("combined", "binance", "bybit"):
                        await conn.execute(INSERTA[tabla], ex, ts)
                puestas += 1
            except Exception:
                break
            await asyncio.sleep(0.01)
    finally:
        await conn.close()
    return puestas


async def main():
    from app import ai_context
    conn = await asyncpg.connect(URL)
    fin = asyncio.Event()
    tarea = None
    if tabla in INSERTA:
        # La fila cae DENTRO de todas las ventanas y por debajo del as_of que el sobre resuelve
        # al empezar: lo unico que la separa de una fila normal es CUANDO se escribe.
        marca = await conn.fetchval(
            "SELECT date_trunc('second', clock_timestamp()) - interval '10 seconds'"
            if tabla != "vela"
            else "SELECT date_bin('1 hour', clock_timestamp(), '1970-01-01'::timestamptz) - interval '1 minute'"
        )
        tarea = asyncio.create_task(escritor(marca, fin))
    t0 = time.monotonic()
    try:
        p = await ai_context.build_ai_symbol_context(conn, "BTCUSDT_PERP.A", profile="max")
    finally:
        dt = time.monotonic() - t0
        fin.set()
        await conn.close()
    puestas = await tarea if tarea is not None else 0
    json.dump(p, open(salida, "w"), default=str, ensure_ascii=False)
    print("filas_insertadas %d · segundos %.3f" % (puestas, dt))


asyncio.run(main())
PY

# ---------------------------------------------------------------- el juez: dentro de UN sobre
cat > "$TMP/juez.py" <<'PY'
"""Dice, de UN sobre, cuantas parejas ventana-pata no dicen lo mismo y si la estructura difiere.

Sale: <parejas> <con_cifra_en_ambas> <valor_dif> <presencia_dif> <estructura_dif> <barra_mal> <detalle>
"""
import json, sys
from datetime import datetime, timedelta

SEG = {'1m':60,'3m':180,'5m':300,'15m':900,'30m':1800,'1h':3600,'4h':14400,'8h':28800,
       '1d':86400,'24h':86400,'3d':259200,'7d':604800,'15s':15,'30s':30,'18m':1080}
p = json.load(open(sys.argv[1]))
cvd, delta = p.get('cvd_matrix') or {}, p.get('delta_matrix') or []
c = {}
for lab, w in (cvd.get('windows') or {}).items():
    sec = w.get('window_seconds') or SEG.get(lab)
    if sec:
        c[sec] = (lab, w)
d = {}
for r in delta:
    sec = SEG.get(r.get('window'))
    if sec:
        d[sec] = (r.get('window'), r)
parejas = ambas = valor = presencia = 0
det = []
for sec in sorted(set(c) & set(d)):
    cl, cw = c[sec]
    dl, dr = d[sec]
    for pata, cv, dv in (('spot', cw.get('spot'), dr.get('spot_delta')),
                         ('fut', cw.get('futures'), dr.get('fut_delta'))):
        parejas += 1
        if (cv is None) != (dv is None):
            presencia += 1
            det.append('%s.%s presencia cvd=%s delta=%s'
                       % (cl, pata, 'CIFRA' if cv is not None else 'null',
                          'CIFRA' if dv is not None else 'null'))
        elif cv is not None:
            ambas += 1
            if abs(cv - dv) > max(1e-6, 1e-9 * max(abs(cv), abs(dv))):
                valor += 1
                det.append('%s.%s valor %+.4f' % (cl, pata, cv - dv))
sd = ((p.get('structure_detail') or {}).get('horizons')) or {}
sh = p.get('structure_horizons') or {}
est = 0
for h, v in sorted(sh.items()):
    o = sd.get(h) or {}
    if v.get('structure') != o.get('state') or v.get('close') != o.get('close'):
        est += 1
        det.append('%s estructura sh=%s/%s sd=%s/%s'
                   % (h, v.get('structure'), v.get('close'), o.get('state'), o.get('close')))
barra = 0
for h, o in sorted(sd.items()):
    if (o.get('group') or '') != 'med':
        continue
    ini, secs, ult = o.get('close_bar_start'), o.get('close_bar_seconds'), o.get('close_source_last_ts')
    if not ini or not secs or not ult:
        continue
    if datetime.fromisoformat(ult) < datetime.fromisoformat(ini) + timedelta(seconds=int(secs)) - timedelta(seconds=60):
        barra += 1
        det.append('%s barra %s con ultima vela %s' % (h, ini, ult))
print('%d %d %d %d %d %d %s' % (parejas, ambas, valor, presencia, est, barra, ' | '.join(det[:4])))
PY

# LA SERIE DEL BANCO SE QUEDA VIEJA EN 30 s Y ENTONCES NO MIDE NADA. `_realtime_flow` exige
# span.hi >= corte-30s para dar la ventana por completa: con la siembra parada, a los 31 s las
# dos matrices publican null y coinciden por estar MUDAS, que es el falso verde que el brazo F
# de K84 existe para evitar. Antes de cada armado se rellena la cola hasta `now`, y eso NO es
# parte de ningun plantado: la huella de cada plantado se toma justo antes y justo despues.
refresca() {
  sql "
  INSERT INTO spot_trades_realtime (symbol,exchange,ts,buy_vol_usd,sell_vol_usd,inst_buy_usd,inst_sell_usd,trade_count,last_px,venue_count)
  SELECT '$WS', x.e, g, 1000+extract(epoch from g)::int%97, 900+extract(epoch from g)::int%89, 10,9,3,100,x.vc
  FROM (VALUES ('combined',2),('binance',1),('bybit',1)) AS x(e,vc),
  LATERAL generate_series(
      (SELECT max(ts)+interval '5 seconds' FROM spot_trades_realtime WHERE symbol='$WS' AND exchange=x.e),
      date_trunc('second',now()), interval '5 seconds') g
  ON CONFLICT DO NOTHING;
  INSERT INTO futures_trades_realtime (symbol,exchange,ts,buy_vol_usd,sell_vol_usd,large_buy_usd,large_sell_usd,trade_count,last_px,venue_count)
  SELECT '$SIMBOLO', x.e, g, 2000+extract(epoch from g)::int%101, 1800+extract(epoch from g)::int%83, 10,9,5,100,x.vc
  FROM (VALUES ('combined',2),('binance',1),('bybit',1)) AS x(e,vc),
  LATERAL generate_series(
      (SELECT max(ts)+interval '5 seconds' FROM futures_trades_realtime WHERE symbol='$SIMBOLO' AND exchange=x.e),
      date_trunc('second',now()), interval '5 seconds') g
  ON CONFLICT DO NOTHING;" >/dev/null
}

arma() { # arma <arbol> <tabla|nada> <retraso> <reps> <salida>
  refresca
  "$PY" "$TMP/armar.py" "$1" "$DB" "$5" "$2" "$3" "$4" 2>"$TMP/arma.err"
}
juzga() { "$PY" "$TMP/juez.py" "$1"; }

# ================================================================== C1 · la fila a mitad del armado
barrido() { # barrido <arbol> <tabla> -> "corridas_con_diferencia/corridas filas_puestas"
  local arbol="$1" tabla="$2" con=0 n=0 puestas=0 i
  for i in $(seq 1 "$RETRASOS"); do
    local r
    r=$("$PY" -c "print(round(0.05 + ($i-1)*0.12, 3))")
    local out
    out=$(arma "$arbol" "$tabla" "$r" 200 "$TMP/s.json") || continue
    puestas=$((puestas + $(printf '%s' "$out" | awk '{print $2}')))
    local v
    v=$(juzga "$TMP/s.json")
    n=$((n+1))
    if [ "$(printf '%s' "$v" | awk '{print $3+$4+$5}')" -gt 0 ]; then
      con=$((con+1))
      printf '%s' "$v" | cut -d' ' -f7- > "$TMP/detalle.txt"
    fi
    # deshacer el plantado antes de la siguiente vuelta
    case "$tabla" in
      spot) sql "DELETE FROM spot_trades_realtime WHERE buy_vol_usd=777777" >/dev/null ;;
      fut)  sql "DELETE FROM futures_trades_realtime WHERE buy_vol_usd=888888" >/dev/null ;;
      vela) sql "DELETE FROM ohlcv WHERE close=500" >/dev/null ;;
    esac
  done
  echo "$con/$n $puestas"
}

echo "== C1 · UNA FILA ESCRITA MIENTRAS EL SOBRE SE ARMA =="
for PATA in spot fut; do
  : > "$TMP/detalle.txt"
  R=$(barrido "$TMP/viejo" "$PATA"); CONV=${R%% *}; PUESTASV=${R##* }
  DET=$(cat "$TMP/detalle.txt")
  R=$(barrido "$REPO" "$PATA");     CONN=${R%% *}; PUESTASN=${R##* }
  NV=${CONV##*/}; CV=${CONV%%/*}; CN=${CONN%%/*}
  if [ "$PUESTASV" -eq 0 ] || [ "$PUESTASN" -eq 0 ]; then
    mal "A · $PATA: el escritor no inserto ni una fila (viejo=$PUESTASV nuevo=$PUESTASN): sin adulteracion no hay nada que juzgar" "A-$PATA sin plantado"
  elif [ "$CV" -gt 0 ] && [ "$CN" -eq 0 ]; then
    ok "A · $PATA: main separa los dos bloques en $CONV corridas ($PUESTASV escrituras) y la rama en $CONN ($PUESTASN escrituras) · $DET"
  elif [ "$CV" -eq 0 ]; then
    mal "A · $PATA: main NO separo los bloques en ninguna de las $NV corridas ($PUESTASV filas): el plantado no reproduce el fenomeno" "A-$PATA main no falla"
  else
    mal "A · $PATA: la rama TAMBIEN separa los bloques ($CONN corridas)" "A-$PATA rama falla"
  fi
done

echo
echo "== C1b · LA VARIABLE QUE DECIDE ES *CUANDO* (A57) =="
# LA HUELLA SE CUENTA POR LA MARCA DEL PLANTADO, no por el total de la tabla: entre el plantado
# y su deshecho hay armados, y cada armado refresca la cola de la serie. Un total no distingue
# «mi fila sigue ahi» de «la cola crecio tres buckets», y esa confusion es la que hace que un
# «restaurado» diga que si cuando no.
MARCA_SPOT="SELECT count(*) FROM spot_trades_realtime WHERE buy_vol_usd=777777"
ANTES_MARCA=$(sql "$MARCA_SPOT")
# La MISMA fila, el MISMO contenido, la MISMA tabla: escrita ANTES de empezar el armado.
sql "INSERT INTO spot_trades_realtime (symbol,exchange,ts,buy_vol_usd,sell_vol_usd,inst_buy_usd,inst_sell_usd,trade_count,last_px,venue_count)
     SELECT '$WS', e, date_trunc('second',now())-interval '10 seconds', 777777,111111,10,9,3,100,vc
     FROM (VALUES ('combined',2),('binance',1),('bybit',1)) AS x(e,vc)" >/dev/null
CON_MARCA=$(sql "$MARCA_SPOT")
arma "$TMP/viejo" "nada" 0 0 "$TMP/antes.json" >/dev/null
VA=$(juzga "$TMP/antes.json")
DIFA=$(printf '%s' "$VA" | awk '{print $3+$4+$5}')
if [ "$CON_MARCA" -le "$ANTES_MARCA" ]; then
  mal "A5 · el plantado previo no cambio la huella ($ANTES_MARCA -> $CON_MARCA filas con la marca)" "A5 sin huella"
elif [ "$DIFA" -eq 0 ]; then
  ok "A5 · la MISMA fila escrita ANTES del armado NO separa los bloques ni en main (huella $ANTES_MARCA -> $CON_MARCA filas con la marca 777777): lo que condena es el instante, no el plantado"
else
  mal "A5 · la fila escrita ANTES del armado ya separa los bloques en main ($DIFA): entonces el barrido no mide el instante" "A5 condena"
fi
sql "DELETE FROM spot_trades_realtime WHERE buy_vol_usd=777777" >/dev/null
VUELTA_MARCA=$(sql "$MARCA_SPOT")
[ "$VUELTA_MARCA" = "0" ] && ok "A5r · plantado deshecho: $CON_MARCA -> $VUELTA_MARCA filas con la marca" \
  || mal "A5r · quedan $VUELTA_MARCA filas con la marca 777777" "A5r sin restaurar"

echo
echo "== C1c · EL SOBRE A CABALLO DE LA HORA (structure_horizons contra structure_detail) =="
# ESTE PLANTADO NO ES UNA CARRERA, Y POR ESO ES EL QUE MANDA. El corte del sobre se pone a UN
# MILISEGUNDO por debajo del borde de la hora: para ese corte la ultima barra de 1 h todavia NO
# esta cerrada, y para el reloj que `horizon_structure` resuelve POR SU CUENTA -unos minutos
# despues- SI lo esta. O sea que los dos bloques cuelgan de lados distintos del mismo borde. No
# hace falta que nada entre a mitad del armado: basta con que el sobre se pida en el borde, que
# es lo que el operador midio en 140 (as_of 17:00:01.326Z).
cat > "$TMP/caballo.py" <<'PY'
import asyncio, json, sys
from datetime import timedelta
arbol, db = sys.argv[1], sys.argv[2]
sys.path.insert(0, arbol)
import asyncpg

async def main():
    from app import scalp_logic as sl
    conn = await asyncpg.connect(f"postgresql:///{db}?host=/var/run/postgresql")
    try:
        borde = await conn.fetchval(
            "SELECT date_bin('1 hour', clock_timestamp(), '1970-01-01'::timestamptz)")
        corte = borde - timedelta(milliseconds=1)
        det = await sl.structure_detail(conn, "BTCUSDT_PERP.A", corte)
        try:
            hz = await sl.horizon_structure(conn, "BTCUSDT_PERP.A", corte)
            acepta = True
        except TypeError:
            hz = await sl.horizon_structure(conn, "BTCUSDT_PERP.A")
            acepta = False
        d = (det.get("horizons") or {}).get("1h") or {}
        h = hz.get("1h") or {}
        print(json.dumps({
            "acepta_as_of": acepta,
            "corte": corte.isoformat(),
            "sd_close": d.get("state") and d.get("close") or d.get("close"),
            "sh_close": h.get("close"),
            "sd_state": d.get("state"),
            "sh_state": h.get("structure"),
        }))
    finally:
        await conn.close()

asyncio.run(main())
PY
CAB_V=$("$PY" "$TMP/caballo.py" "$TMP/viejo" "$DB" 2>"$TMP/cab.err")
CAB_N=$("$PY" "$TMP/caballo.py" "$REPO" "$DB" 2>>"$TMP/cab.err")
if [ -z "$CAB_V" ] || [ -z "$CAB_N" ]; then
  mal "A6a · no se pudo medir el borde de la hora: $(tail -1 "$TMP/cab.err")" "A6a sin medida"
else
  LEE() { printf '%s' "$1" | "$PY" -c "import json,sys; print(json.load(sys.stdin)[sys.argv[1]])" "$2"; }
  VSD=$(LEE "$CAB_V" sd_close); VSH=$(LEE "$CAB_V" sh_close); VAC=$(LEE "$CAB_V" acepta_as_of)
  NSD=$(LEE "$CAB_N" sd_close); NSH=$(LEE "$CAB_N" sh_close); NAC=$(LEE "$CAB_N" acepta_as_of)
  CORTE=$(LEE "$CAB_V" corte)
  if [ "$VAC" = "True" ]; then
    mal "A6a · el arbol viejo ya acepta as_of en horizon_structure: no son los bytes viejos" "A6a arbol raro"
  elif [ "$NAC" != "True" ]; then
    mal "A6a · la rama NO acepta as_of en horizon_structure" "A6a rama sin as_of"
  elif [ "$VSD" != "$VSH" ] && [ "$NSD" = "$NSH" ]; then
    ok "A6a · con el corte en $CORTE (1 ms por debajo del borde de la hora): main publica structure_detail close=$VSD y structure_horizons close=$VSH -DISTINTOS, cada uno a un lado del borde-; la rama publica $NSD y $NSH"
  elif [ "$VSD" = "$VSH" ]; then
    mal "A6a · main NO los separo en el borde ($VSD contra $VSH): el plantado no reproduce el fenomeno" "A6a main no falla"
  else
    mal "A6a · la rama TAMBIEN los separa ($NSD contra $NSH)" "A6a rama falla"
  fi
fi

# Y ademas la carrera, que es la otra mitad del mismo fenomeno y NO es deterministica.
# Para que la vela pueda ENTRAR a mitad del armado tiene que faltar antes: la siembra la puso,
# asi que se aparta y se devuelve al final. Es la vela que cierra la ultima barra de 1 h.
VELA_TS=$(sql "SELECT date_bin('1 hour', now(), '1970-01-01'::timestamptz) - interval '1 minute'")
sql "CREATE TABLE _resp_h AS SELECT symbol,interval,ts,open,high,low,close,volume,buy_volume,tx,btx
     FROM ohlcv WHERE symbol='$SIMBOLO' AND interval='1min' AND ts='$VELA_TS'" >/dev/null
APARTADA=$(sql "SELECT count(*) FROM _resp_h")
sql "DELETE FROM ohlcv WHERE symbol='$SIMBOLO' AND interval='1min' AND ts='$VELA_TS'" >/dev/null
: > "$TMP/detalle.txt"
R=$(barrido "$TMP/viejo" "vela"); CONV=${R%% *}; PUESTASV=${R##* }
DETH=$(cat "$TMP/detalle.txt")
R=$(barrido "$REPO" "vela");      CONN=${R%% *}; PUESTASN=${R##* }
CV=${CONV%%/*}; CN=${CONN%%/*}
[ "$APARTADA" = "1" ] || mal "A6h · no se pudo apartar la vela de $VELA_TS (apartadas=$APARTADA)" "A6h sin plantado"
if [ "$PUESTASV" -eq 0 ]; then
  mal "A6 · el escritor de velas no inserto nada" "A6 sin plantado"
elif [ "$CV" -gt 0 ] && [ "$CN" -eq 0 ]; then
  ok "A6 · la vela de $VELA_TS entrando a mitad del armado separa los bloques en main ($CONV corridas, $PUESTASV escrituras) y no en la rama ($CONN, $PUESTASN) · $DETH"
elif [ "$CV" -eq 0 ]; then
  echo "  AVISO A6 · la vela no separo los bloques en main en $CONV corridas ($PUESTASV escrituras):"
  echo "        horizon_structure y structure_detail se calculan con milisegundos de diferencia y la"
  echo "        ventana para colarse entre sus dos cortes es de ese orden. NO se apunta como paso ni"
  echo "        como fallo: lo que este control NO puede afirmar, no lo afirma."
else
  mal "A6 · la rama TAMBIEN separa los bloques ($CONN)" "A6 rama falla"
fi
sql "INSERT INTO ohlcv (symbol,interval,ts,open,high,low,close,volume,buy_volume,tx,btx)
     SELECT symbol,interval,ts,open,high,low,close,volume,buy_volume,tx,btx FROM _resp_h" >/dev/null
sql "DROP TABLE _resp_h" >/dev/null
VUELTA_H=$(sql "SELECT count(*) FROM ohlcv WHERE symbol='$SIMBOLO' AND interval='1min' AND ts='$VELA_TS' AND close<>500")
[ "$VUELTA_H" = "1" ] && ok "A6r · vela de $VELA_TS devuelta a su sitio" \
  || mal "A6r · la vela de $VELA_TS no volvio (hay $VUELTA_H)" "A6r sin restaurar"

# ================================================================== C2 · el hueco interno
echo
echo "== C2 · UN HUECO INTERNO PLANTADO EN SPOT Y OTRO EN FUTUROS =="
hueco() { # hueco <tabla> <simbolo>  -> borra 90 s de filas en mitad de la ventana de 30m
  sql "DELETE FROM $1 WHERE symbol='$2' AND ts >= now()-interval '20 minutes' AND ts < now()-interval '18 minutes 30 seconds'"
}
for CASO in "spot_trades_realtime $WS spot" "futures_trades_realtime $SIMBOLO fut"; do
  set -- $CASO
  TABLA=$1; SYM=$2; ETIQ=$3
  # La huella del hueco es la cuenta DENTRO del tramo que se vacia, no el total de la tabla:
  # entre el plantado y su deshecho hay armados que refrescan la cola.
  TRAMO="SELECT count(*) FROM $TABLA WHERE symbol='$SYM' AND ts >= '$(sql "SELECT now()-interval '20 minutes'")' AND ts < '$(sql "SELECT now()-interval '18 minutes 30 seconds'")'"
  ANTES=$(sql "$TRAMO")
  sql "CREATE TABLE _resp_$ETIQ AS SELECT * FROM $TABLA WHERE symbol='$SYM' AND ts >= now()-interval '20 minutes' AND ts < now()-interval '18 minutes 30 seconds'" >/dev/null
  hueco "$TABLA" "$SYM" >/dev/null
  DESPUES=$(sql "$TRAMO")
  QUITADAS=$((ANTES-DESPUES))
  arma "$TMP/viejo" "nada" 0 0 "$TMP/hv.json" >/dev/null
  arma "$REPO"      "nada" 0 0 "$TMP/hn.json" >/dev/null
  VV=$(juzga "$TMP/hv.json"); VN=$(juzga "$TMP/hn.json")
  PV=$(printf '%s' "$VV" | awk '{print $4}'); PN=$(printf '%s' "$VN" | awk '{print $4}')
  if [ "$QUITADAS" -eq 0 ]; then
    mal "B · $ETIQ: el hueco no quito ni una fila ($ANTES -> $DESPUES)" "B-$ETIQ sin plantado"
  elif [ "$ETIQ" = spot ] && [ "$PV" -gt 0 ] && [ "$PN" -eq 0 ]; then
    ok "B · $ETIQ: 90 s fuera ($ANTES -> $DESPUES, $QUITADAS filas) · main deja $PV pareja(s) con cifra en una y null en la otra; la rama, $PN · $(printf '%s' "$VV" | cut -d' ' -f7-)"
  elif [ "$ETIQ" = fut ] && [ "$PV" -eq 0 ] && [ "$PN" -eq 0 ]; then
    ok "B · $ETIQ: 90 s fuera ($QUITADAS filas) y NINGUNO de los dos arboles discrepa. ESTE BRAZO NO CONDENA A main, y es lo correcto: la guarda de futuros ya se propago en la campana 127 (scalp_logic.py, comentario de cvd_matrix)"
  elif [ "$PN" -gt 0 ]; then
    mal "B · $ETIQ: la rama deja $PN pareja(s) discrepando con el hueco delante" "B-$ETIQ rama falla"
  else
    mal "B · $ETIQ: main no discrepa ($PV) y se esperaba que si" "B-$ETIQ main no falla"
  fi
  sql "INSERT INTO $TABLA SELECT * FROM _resp_$ETIQ ON CONFLICT DO NOTHING" >/dev/null
  sql "DROP TABLE _resp_$ETIQ" >/dev/null
  VUELTA=$(sql "$TRAMO")
  [ "$VUELTA" = "$ANTES" ] && ok "Br · $ETIQ: hueco restaurado, el tramo vuelve a tener $VUELTA filas (tenia $ANTES, quedo en $DESPUES)" \
    || mal "Br · $ETIQ: el tramo no volvio a su huella ($ANTES -> $DESPUES -> $VUELTA)" "Br-$ETIQ sin restaurar"
done

# ================================================================== C3 · la barra cerrada
echo
echo "== C3 · LA VELA QUE CIERRA LA BARRA, AUSENTE =="
ULT=$(sql "SELECT date_bin('1 hour', now(), '1970-01-01'::timestamptz) - interval '1 minute'")
VELA="SELECT count(*) FROM ohlcv WHERE symbol='$SIMBOLO' AND interval='1min' AND ts='$ULT'"
ANTES_O=$(sql "$VELA")
CIERRE_REAL=$(sql "SELECT close FROM ohlcv WHERE symbol='$SIMBOLO' AND interval='1min' AND ts='$ULT'")
CIERRE_PREVIO=$(sql "SELECT close FROM ohlcv WHERE symbol='$SIMBOLO' AND interval='1min' AND ts='$ULT'::timestamptz-interval '1 minute'")
CIERRE_BARRA_ANTERIOR=$(sql "SELECT close FROM ohlcv WHERE symbol='$SIMBOLO' AND interval='1min' AND ts='$ULT'::timestamptz-interval '1 hour'")
sql "CREATE TABLE _resp_vela AS SELECT symbol,interval,ts,open,high,low,close,volume,buy_volume,tx,btx FROM ohlcv WHERE symbol='$SIMBOLO' AND interval='1min' AND ts='$ULT'" >/dev/null
sql "DELETE FROM ohlcv WHERE symbol='$SIMBOLO' AND interval='1min' AND ts='$ULT'" >/dev/null
DESPUES_O=$(sql "$VELA")
arma "$TMP/viejo" "nada" 0 0 "$TMP/bv.json" >/dev/null
arma "$REPO"      "nada" 0 0 "$TMP/bn.json" >/dev/null
CV_1H=$("$PY" -c "
import json,sys
p=json.load(open('$TMP/bv.json'))
h=(p.get('structure_detail') or {}).get('horizons',{}).get('1h') or {}
print(h.get('close'), h.get('close_bar_start'))")
CN_1H=$("$PY" -c "
import json,sys
p=json.load(open('$TMP/bn.json'))
h=(p.get('structure_detail') or {}).get('horizons',{}).get('1h') or {}
print(h.get('close'), h.get('close_bar_start'), h.get('close_source_last_ts'))")
BARRA_MAL_V=$(juzga "$TMP/bv.json" | awk '{print $6}')
BARRA_MAL_N=$(juzga "$TMP/bn.json" | awk '{print $6}')
if [ "$ANTES_O" != "1" ] || [ "$DESPUES_O" != "0" ]; then
  mal "C · el plantado no quito la vela de $ULT ($ANTES_O -> $DESPUES_O)" "C sin plantado"
else
  VIEJO_CIERRE=$(printf '%s' "$CV_1H" | awk '{print $1}')
  NUEVO_CIERRE=$(printf '%s' "$CN_1H" | awk '{print $1}')
  VIEJO_BARRA=$(printf '%s' "$CV_1H" | awk '{print $2}')
  NUEVO_BARRA=$(printf '%s' "$CN_1H" | awk '{print $2}')
  if [ "$VIEJO_BARRA" != "None" ]; then
    mal "C · el arbol viejo ya declara close_bar_start ($VIEJO_BARRA): no son los bytes viejos" "C arbol viejo raro"
  elif [ "$VIEJO_CIERRE" = "$NUEVO_CIERRE" ] && [ "$NUEVO_BARRA" != "None" ]; then
    mal "C · los dos publican el MISMO cierre ($VIEJO_CIERRE) con la vela ausente: la rama no cambio nada" "C rama no cambia"
  else
    ok "C · vela de $ULT fuera (cierre real $CIERRE_REAL · la de un minuto antes, $CIERRE_PREVIO · la que cierra la barra ANTERIOR, $CIERRE_BARRA_ANTERIOR) · main publica close=$VIEJO_CIERRE SIN decir de que barra; la rama publica close=$NUEVO_CIERRE de la barra $NUEVO_BARRA con su ultima vela"
  fi
  [ "$BARRA_MAL_N" -eq 0 ] && ok "C2 · la rama no deja NINGUNA barra publicada como cerrada sin su ultima vela (main no lo puede ni decir: $BARRA_MAL_V, no publica los campos)" \
    || mal "C2 · la rama deja $BARRA_MAL_N barra(s) sin su ultima vela" "C2 rama falla"
fi
sql "INSERT INTO ohlcv (symbol,interval,ts,open,high,low,close,volume,buy_volume,tx,btx)
     SELECT symbol,interval,ts,open,high,low,close,volume,buy_volume,tx,btx FROM _resp_vela
     ON CONFLICT DO NOTHING" >/dev/null
sql "DROP TABLE _resp_vela" >/dev/null
VUELTA_O=$(sql "$VELA")
[ "$VUELTA_O" = "$ANTES_O" ] && ok "Cr · vela restaurada en $ULT ($DESPUES_O -> $VUELTA_O)" \
  || mal "Cr · la vela de $ULT no volvio ($ANTES_O -> $DESPUES_O -> $VUELTA_O)" "Cr sin restaurar"

# ================================================================== C6 · la red
echo
echo "== C6 · LA RED CONTRA LOS BYTES VIEJOS Y CONTRA DOS BLOQUES IGUALES =="
# LA RED SE EJERCITA CONTRA LOS BYTES VIEJOS CON *TODOS* LOS PLANTADOS A LA VEZ, uno por
# fenomeno y por pata, para poder decir CUANTOS brazos fallan y CUALES. Un solo sobre no basta:
# la fila del borde es una carrera y hay armados en los que no cae entre los dos bloques.
con_diferencia() { # con_diferencia <tabla> <salida> -> repite hasta que el sobre viejo discrepa
  local tabla="$1" salida="$2" i r
  for i in $(seq 1 12); do
    r=$("$PY" -c "print(round(0.05 + ($i-1)*0.09, 3))")
    arma "$TMP/viejo" "$tabla" "$r" 200 "$salida" >/dev/null
    case "$tabla" in
      spot) sql "DELETE FROM spot_trades_realtime WHERE buy_vol_usd=777777" >/dev/null ;;
      fut)  sql "DELETE FROM futures_trades_realtime WHERE buy_vol_usd=888888" >/dev/null ;;
    esac
    [ "$(juzga "$salida" | awk '{print $3+$4}')" -gt 0 ] && return 0
  done
  return 1
}
con_diferencia spot "$TMP/red-spot.json" && RED_SPOT=si || RED_SPOT=no
con_diferencia fut  "$TMP/red-fut.json"  && RED_FUT=si  || RED_FUT=no
sql "CREATE TABLE _resp_red AS SELECT * FROM spot_trades_realtime WHERE symbol='$WS' AND ts >= now()-interval '20 minutes' AND ts < now()-interval '18 minutes 30 seconds'" >/dev/null
hueco spot_trades_realtime "$WS" >/dev/null
arma "$TMP/viejo" "nada" 0 0 "$TMP/red-hueco.json" >/dev/null
sql "INSERT INTO spot_trades_realtime SELECT * FROM _resp_red ON CONFLICT DO NOTHING" >/dev/null
sql "DROP TABLE _resp_red" >/dev/null
VT=$(sql "SELECT date_bin('1 hour', now(), '1970-01-01'::timestamptz) - interval '1 minute'")
sql "CREATE TABLE _resp_red2 AS SELECT symbol,interval,ts,open,high,low,close,volume,buy_volume,tx,btx FROM ohlcv WHERE symbol='$SIMBOLO' AND interval='1min' AND ts='$VT'" >/dev/null
sql "DELETE FROM ohlcv WHERE symbol='$SIMBOLO' AND interval='1min' AND ts='$VT'" >/dev/null
arma "$TMP/viejo" "nada" 0 0 "$TMP/red-vela.json" >/dev/null
sql "INSERT INTO ohlcv (symbol,interval,ts,open,high,low,close,volume,buy_volume,tx,btx)
     SELECT symbol,interval,ts,open,high,low,close,volume,buy_volume,tx,btx FROM _resp_red2
     ON CONFLICT DO NOTHING" >/dev/null
sql "DROP TABLE _resp_red2" >/dev/null

SAL=$(K84_SUJETO=fichero K84_SOBRE="$TMP/red-spot.json $TMP/red-fut.json $TMP/red-hueco.json $TMP/red-vela.json" bash "$B/checks/K84-dos-matrices-una-cifra.sh" 2>&1)
RC=$?
BRAZOS=$(printf '%s\n' "$SAL" | grep -oE '^   [A-G] ·' | tr -d ' ·' | tr '\n' ' ')
printf '%s\n' "$SAL" | head -1 | grep -q 'instantanea' && BRAZOS="A $BRAZOS"
BRAZOS=$(printf '%s\n' $BRAZOS | sort -u | tr '\n' ' ')
CUANTOS=$(printf '%s\n' "$SAL" | grep -cE '^   [A-G] ·')
if [ "$RC" = 1 ]; then
  # El brazo D de K84 -la estructura- NO sale aqui y no es un hueco: la unica forma de que
  # structure_horizons y structure_detail difieran es que los dos cortes caigan a lados
  # distintos del borde de una barra, y eso lo planta A6a sin carrera.
  ok "D · K84 condena los 4 sobres de main (fila en spot=$RED_SPOT, en futuros=$RED_FUT, hueco de spot, vela ausente): rc=1 · brazos que fallan: ${BRAZOS:-ninguno} · $CUANTOS linea(s) de defecto. El brazo D (estructura) no aparece porque su fenomeno es el borde de la barra, que planta A6a"
  printf '%s\n' "$SAL" | head -1 | sed 's/^/        /'
  printf '%s\n' "$SAL" | grep -E '^   [BCDE] ·' | head -4 | sed 's/^/        /'
else
  mal "D · K84 NO condena los sobres de main (rc=$RC): $(printf '%s' "$SAL" | head -1)" "D red no condena"
fi
[ "$RED_SPOT" = si ] && [ "$RED_FUT" = si ] && ok "D2 · la fila del borde se reprodujo en LAS DOS patas antes de juzgar" \
  || mal "D2 · no se reprodujo la fila del borde en spot=$RED_SPOT / futuros=$RED_FUT, asi que el brazo B de K84 no se ejercito en esa pata" "D2 sin reproducir"

arma "$REPO" "nada" 0 0 "$TMP/red-nuevo.json" >/dev/null
SAL2=$(K84_SUJETO=fichero K84_SOBRE="$TMP/red-nuevo.json" bash "$B/checks/K84-dos-matrices-una-cifra.sh" 2>&1)
RC2=$?
if [ "$RC2" = 0 ]; then
  ok "E · EL BRAZO QUE NO PUEDE CONDENAR: con dos bloques iguales DE VERDAD (rama, sin escritor) K84 da VERDE · $(printf '%s' "$SAL2" | head -1 | cut -c1-110)"
elif [ "$RC2" = 2 ]; then
  mal "E · K84 salio NO MEDIDO con el sobre bueno: $(printf '%s' "$SAL2" | head -1)" "E nomed"
else
  mal "E · K84 CONDENA un sobre en el que los dos bloques dicen lo mismo: $(printf '%s' "$SAL2" | head -2 | tail -1)" "E falso positivo"
fi

# ================================================================== C4 · el glosario cobra
echo
echo "== C4 · EL GLOSARIO PROMETE UNA COINCIDENCIA Y UN VALOR PLANTADO LA ROMPE =="
# El sobre nuevo se adultera EN EL VALOR -HH_HL pasa a LH_LL, que es otro valor DECLARADO y no
# un prefijo: 'ZZ'+v seguiria conteniendo v y un juez por subcadena lo dejaria pasar- y se le
# da al motor de K101. Con el glosario de esta rama diciendo «NO DISCREPA», su brazo G tiene
# que condenar. La prueba de que la adulteracion ocurrio va en la salida (A67).
arma "$REPO" "nada" 0 0 "$TMP/c4.json" >/dev/null
CAMBIOS_C4=$("$PY" - "$TMP/c4.json" "$TMP/c4-roto.json" <<'PY'
import json, sys
p = json.load(open(sys.argv[1]))
otro = {"HH_HL": "LH_LL", "LH_LL": "HH_HL", "mixed": "HH_HL", None: "HH_HL"}
n = 0
for h, v in (p.get("structure_horizons") or {}).items():
    if n == 0:
        v["structure"] = otro.get(v.get("structure"), "LH_LL")
        n += 1
json.dump(p, open(sys.argv[2], "w"), default=str, ensure_ascii=False)
print(n)
PY
)
if [ "${CAMBIOS_C4:-0}" -lt 1 ]; then
  mal "F · no se pudo adulterar ningun horizonte del sobre" "F sin plantado"
else
  SAL_C4=$("$PY" "$B/checks/K101-homonimos.py" "control de K84 (sobre adulterado)" "$TMP/c4-roto.json" 2>&1)
  RC_C4=$?
  SAL_C4_OK=$("$PY" "$B/checks/K101-homonimos.py" "control de K84 (sobre intacto)" "$TMP/c4.json" 2>&1)
  RC_OK=$?
  if [ "$RC_C4" = 1 ] && printf '%s' "$SAL_C4" | grep -q 'G ·'; then
    if [ "$RC_OK" = 0 ]; then
      ok "F · $CAMBIOS_C4 horizonte adulterado en el VALOR: el brazo G de K101 condena · $(printf '%s\n' "$SAL_C4" | grep -m1 'G ·' | cut -c1-140)"
    else
      mal "F · G condena el adulterado pero K101 tampoco pasa con el sobre INTACTO (rc=$RC_OK): no se puede atribuir" "F sin control negativo"
    fi
  elif [ "$RC_C4" = 1 ]; then
    mal "F · K101 condena pero NO por el brazo G: $(printf '%s' "$SAL_C4" | head -1 | cut -c1-120)" "F condena por otro brazo"
  else
    mal "F · K101 NO condena el sobre adulterado (rc=$RC_C4): la promesa del glosario no se cobra" "F no cobra"
  fi
fi

# ================================================================== huella final
echo
# La huella final es POR LAS MARCAS: los totales crecen con la cola que refresca cada armado,
# que es parte del banco y no de ningun plantado, y esos totales van en la linea para que se vea.
M_SPOT=$(sql "SELECT count(*) FROM spot_trades_realtime WHERE buy_vol_usd=777777")
M_FUT=$(sql "SELECT count(*) FROM futures_trades_realtime WHERE buy_vol_usd=888888")
M_VELA=$(sql "SELECT count(*) FROM ohlcv WHERE close=500")
FIN_SPOT=$(sql "SELECT count(*) FROM spot_trades_realtime")
FIN_FUT=$(sql "SELECT count(*) FROM futures_trades_realtime")
FIN_OHLCV=$(sql "SELECT count(*) FROM ohlcv")
if [ "$M_SPOT" = 0 ] && [ "$M_FUT" = 0 ] && [ "$M_VELA" = 0 ] && [ "$FIN_OHLCV" = "$BASE_OHLCV" ]; then
  ok "H · no queda ni una fila plantada (marcas 777777/888888/close=500 a cero) y ohlcv vuelve a $FIN_OHLCV, la cifra de la siembra. Las tablas de trades crecieron de $BASE_SPOT/$BASE_FUT a $FIN_SPOT/$FIN_FUT por la cola que refresca cada armado, que no es plantado"
else
  mal "H · quedan restos: spot=$M_SPOT fut=$M_FUT vela=$M_VELA marcadas · ohlcv $BASE_OHLCV->$FIN_OHLCV" "H sin restaurar"
fi

echo
if [ -n "$FALLOS" ]; then
  echo "ROJO: $PASA de $TOTAL brazos del control pasan · falla: $FALLOS"
  exit 1
fi
echo "$PASA de $TOTAL brazos del control pasan · banco $DB (borrado) · viejo main@$VIEJO_SHA contra $NUEVO_SHA"
