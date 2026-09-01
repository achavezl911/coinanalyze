#!/bin/bash
# K83  LA VENTANA DE 24 H PIDE UNA FUENTE QUE NO ES LA QUE TIENE EL DATO.
#
# LA VIA, REPRODUCIDA ANTES QUE LA CIFRA -- y por septima vez el encargo traia la cifra
# cierta por una via que no era. El encargo decia "cvd_matrix publica null y no llega a la
# pantalla". Las dos mitades hay que matizarlas:
#
#   1 · NO SE CALCULA Y SE DESCARTA: NO SE CALCULA NUNCA. pick_fut (scalp_logic.py:2696-2699)
#       corta por `rtf_obs >= sec` ANTES de consultar nada. La unica fuente de futuros de
#       cvd_matrix es _cvd_src(conn,"futures_trades_realtime",...) en :2660, y
#       futures_trades_agg NO APARECE en la funcion. El spot SI tiene empalme montado y
#       probado: spot_flow_windows (:2431) une spot_trades_agg 1min + cola realtime sin
#       solapamiento, y su regla de completo es agg_lo<=inicio AND rt_hi>=fin-30s AND
#       rt_lo<=agg_hi+1min. Al futuro le falta ESE empalme, no le falta el dato.
#
#   2 · EL null DE cvd_matrix NO LLEGA A LA PANTALLA: el panel no pide esa ruta -cero
#       ocurrencias de "cvd-matrix" en static/app.js-, solo la lee la IA (ai_context.py:868).
#       PERO EL MISMO DEFECTO SI SE PINTA POR OTRO SITIO: delta_matrix (scalp_logic.py:4092)
#       sirve su ventana 1d con _realtime_flow sobre futures_trades_realtime -- el mismo
#       corte, la misma fuente-, y ESA ruta el panel SI la pide (app.js:1551) y la pinta
#       (renderDeltaMatrix, app.js:484). Por eso este check gatea LAS DOS rutas: si gateara
#       solo cvd_matrix estaria vigilando el sintoma que NO se ve.
#       EN PANTALLA EL PANEL ES HONESTO, y se dice para no acusarle de mas: con una pata
#       nula deltaFlowQuadrant (app.js:457) devuelve 'sin_datos' y la fila 1d sale
#       "Parcial / N/D / Sin datos". No inventa direccion. Lo que hay es un agujero
#       innecesario, no una mentira.
#
# EL DANO, MEDIDO EN 140 EL 2026-09-01T03:0x-03:1xZ:
#   cvd_matrix 24h de ETH en vivo   spot = -5 753 605   futures = null
#     futures_status.reason = "insufficient_retention", derivada de las 12 h del realtime
#   futures_trades_agg 24h combined de ETH                 = +188 775 113
#   O SEA QUE LA UNICA PATA VISIBLE DICE VENDE Y LA PATA SUPRIMIDA, 33 VECES MAYOR, COMPRA.
#   Cruza tambien contra la ventana vecina que si se publica:
#     fut 8h ETH = -134 787 097   frente a   fut 24h = +188 775 113
#   BTC no cruza (8h -223 200 204 · 24h -85 099 914). SOL cruza pero su 24h es +17 968,
#   ruido, y no lo cuento como cruce. UNO DE TRES cruza -- suficiente para que la ausencia
#   no se pueda suplir extrapolando la ventana de al lado, que es lo unico que puede hacer
#   hoy quien lee.
#
# EL SIGNO NO SE GATEA, Y ES DELIBERADO. Que ETH cruce hoy es una propiedad del mercado de
# hoy, no del sistema: un brazo que exigiera el cruce sacaria ROJO o VERDE segun el dia.
# Es la leccion de K80 con el componente que saturaba. El cruce es el MOTIVO, esta fechado
# aqui arriba con su comando, y lo que se gatea es la ausencia de la pata.
#
# LA COBERTURA, MEDIDA HOY, Y CORRIGE AL ENCARGO: el 99.86 % (1438/1440) del 2026-08-31 hoy
# es 1436 de 1440 = 99.72 %, igual en los tres simbolos y los tres exchange. Y los cuatro
# minutos que faltan NO son una sola cosa:
#     09-01 01:11                     UN hueco interno, y NO esta declarado
#     09-01 03:07 03:08 03:09 03:10   BORDE DE COLA: el agg va 3.69 min detras del reloj
# El borde explica tres de los cuatro, y el borde LO CUBRE EL REALTIME (end_gap 20.5 s):
# es exactamente para eso que el spot empalma las dos fuentes en vez de elegir una. Por eso
# este check NO exige 1440 de 1440 a la fuente historica: exige que la ventana quede cubierta
# por el EMPALME, que es la unica pregunta con sentido.
# Y EL HUECO INTERNO NO PUEDE ESTAR DECLARADO: data_gap no tiene NI UNA fila con
# feed='futures_trades' -control positivo del instrumento: si tiene 664 de long_short_ratio
# y 435 de ohlcv_1min-, luego el blocked_futures de cvd_matrix:2681 sale SIEMPRE vacio.
# Es un guardarrail que no puede disparar. Se declara aqui y no se gatea: gatear un feed de
# huecos nuevo es otro trabajo, y meterlo aqui seria ampliar el arnes.
#
# LO QUE ESTE CHECK ENCONTRO Y NO GATEA, PORQUE ES OTRO DEFECTO CON OTRO ARREGLO. La primera
# version gateaba toda ventana cubierta por el agg, y saco ROJO tambien por SOL 4h y 8h. No
# es lo mismo y conviene no mezclarlo: en esas dos ventanas el realtime SI llega, y las DOS
# RUTAS DISCREPAN DEL MISMO NUMERO EN EL MISMO INSTANTE (140, 2026-09-01T03:2xZ):
#     cvd_matrix SOL 4h = -1 888 879     delta_matrix SOL 4h = null, "partial"
#     cvd_matrix SOL 8h = -47 951 783    delta_matrix SOL 8h = null, "partial"
# La causa esta medida: delta_matrix exige max_internal_gap <= REALTIME_STALE_SECONDS = 30 s
# (scalp_logic.py:184, :3933, :4123) y SOL trae un hueco interno de 35 s; cvd_matrix no aplica
# esa regla a la pata de futuros. O sea que el simbolo mas fino sale en blanco en la pantalla
# y con numero en el contexto de la IA. Se anota en COLA y en hechos.tsv, y NO se arregla
# aqui: mezclarlo dejaria este check rojo por una causa que su arreglo no toca, que es como
# K81 nacio inarreglable.
# POR ESO EL ELEGIBLE LLEVA SUELO ADEMAS DE TECHO: solo entran las ventanas que el realtime
# NO alcanza y el agg SI -- la clase que unicamente el empalme puede servir.
#
# LOS CUATRO BRAZOS:
#   A · CONSECUENCIA EN LA IA. Toda ventana de cvd_matrix que publique spot y cuya fuente de
#       futuros la CUBRA tiene que publicar tambien futuros. Hoy la 24h cumple lo primero y
#       falla lo segundo.
#   B · CONSECUENCIA EN PANTALLA. Lo mismo sobre la ventana 1d de /api/scalp/delta-matrix,
#       que es la que el operador ve.
#   C · ELEGIBLE DERIVADO DE INSTRUMENTO EXTERNO, CON SUELO Y TECHO. La ventana no es
#       elegible porque yo diga "24 h": lo es cuando los DOS arcos MEDIDOS en 140 la
#       encierran -- por encima del arco del realtime (que no la alcanza) y por debajo del
#       arco de futures_trades_agg (que si), y con el realtime empalmando la cola del agg,
#       aplicando LA MISMA regla que el spot ya usa. Si manana el agg encogiera, la 24h
#       dejaria de ser elegible y este check tiene que decir eso en vez de seguir en rojo
#       por un peligro que ya no existe (leccion de K71).
#       Medido hoy: realtime 12.97 h · agg 35.99 h -> entra la 24h, y solo ella. La 3d y la
#       7d se quedan fuera por techo; la 4h y la 8h, por suelo.
#   D · CONTROL POSITIVO Y CASO VACIO. Alguna ventana tiene que venir CON numero en cada
#       ruta: si todas salieran nulas el check no distinguiria "defecto" de "instrumento
#       ciego" y eso es NOMED. Y si futures_trades_agg no tuviera filas en el arco, no hay
#       nada que reclamar: NOMED tambien, no VERDE.
#   E · CONTROL NEGATIVO DEL INSTRUMENTO. Las ventanas que el arco NO cubre -3d y 7d hoy-
#       tienen que seguir nulas. Si una saliera con numero, mi medida del arco y lo que la
#       aplicacion cree que puede servir no son la misma cosa, y entonces el brazo A estaria
#       atribuyendo el hueco a la causa equivocada: NOMED.
#
# DE QUE ARBOL: los cinco brazos miden 140 -- A, B y E por la API, C y D por prodsql.
# El VERDE exige A y B con C y D vivos.
#
# Se comprueba con: bash harness/checks/K83-la-ventana-pide-la-fuente-que-no-tiene-el-dato.sh

set -u
B=/srv/coinanalyze/harness
. "$B/env"
SIMBOLOS="BTCUSDT_PERP.A ETHUSDT_PERP.A SOLUSDT_PERP.A"

# bin/api corta a 8000 bytes y eso ROMPE el JSON de estas dos rutas por la mitad: no es que
# se pierda una clave, es que no se puede ni parsear. Aqui el corte se desactiva a proposito.
export TODO=1

FALLOS=""; ELEGIBLES=0; SERVIDAS=0; ARCO_TXT=""

for S in $SIMBOLOS; do
  CORTO=${S%%USDT*}

  # --- C+D · el arco REAL de la fuente de futuros, medido en 140. Es el instrumento
  # externo del que sale "elegible", y se re-mide en cada pasada.
  ARCO=$("$B/bin/prodsql" "
    WITH c AS (SELECT clock_timestamp() AS t),
      a AS (SELECT MIN(ts) lo, MAX(ts) hi,
                   COUNT(*) FILTER (WHERE ts >= (SELECT t FROM c)-interval '24 hours') n24
            FROM futures_trades_agg
            WHERE symbol='$S' AND exchange='combined' AND venue_count=2 AND interval='1min'
              AND ts <= (SELECT t FROM c)),
      r AS (SELECT MIN(ts) lo, MAX(ts) hi FROM futures_trades_realtime
            WHERE symbol='$S' AND exchange='combined' AND ts <= (SELECT t FROM c))
    SELECT round(EXTRACT(EPOCH FROM (c.t-a.lo))::numeric,0),
           round(EXTRACT(EPOCH FROM (c.t-r.hi))::numeric,1),
           CASE WHEN r.lo <= a.hi + interval '1 minute' THEN 1 ELSE 0 END,
           a.n24,
           round(EXTRACT(EPOCH FROM (c.t-r.lo))::numeric,0)
    FROM c,a,r" 2>/dev/null | tr -d ' ' | head -1)
  case "$ARCO" in
    [0-9]*\|*\|[01]\|[0-9]*\|[0-9]*) : ;;
    *) echo "NO MEDIDO: 140 no contesto por el arco de futures_trades_agg de $CORTO: $(printf '%s' "$ARCO" | head -c 90)"; exit 2 ;;
  esac
  IFS='|' read -r ARCO_S COLA_S EMPALMA N24 RT_S <<EOF
$ARCO
EOF
  # El arco del realtime tiene que quedarse CORTO del agg, o no hay clase de ventanas que
  # solo el empalme pueda servir y este check no tendria sujeto.
  python3 -c "import sys; sys.exit(0 if $RT_S < $ARCO_S else 1)" || {
    echo "NO MEDIDO: en $CORTO el realtime ($RT_S s) ya llega tan atras como el agg ($ARCO_S s). No existe hoy ninguna ventana que SOLO el empalme pueda cubrir, que es lo unico que este check mide"
    exit 2
  }
  [ "$N24" -gt 0 ] || {
    echo "NO MEDIDO: futures_trades_agg no tiene NI UNA fila de $CORTO en las ultimas 24 h. Sin dato historico no hay nada que reclamarle a la respuesta, y un VERDE aqui no probaria nada"
    exit 2
  }
  # La cola tiene que empalmar, o la ventana no seria cubrible ni con el arreglo puesto y
  # este check estaria exigiendo lo imposible (la forma en que K81 nacio inarreglable).
  [ "$EMPALMA" = 1 ] || {
    echo "NO MEDIDO: en $CORTO el realtime no solapa con la cola del agg (agg_hi + 1 min queda por delante de rt_lo). Hoy la ventana no seria cubrible ni empalmando, asi que el defecto que mide este check no se puede distinguir de una parada del colector"
    exit 2
  }
  [ -n "$ARCO_TXT" ] || ARCO_TXT="arco $(python3 -c "print(round($ARCO_S/3600.0,2))") h, cola del realtime $COLA_S s"

  # --- A · cvd_matrix: la que lee la IA.
  PAYLOAD=$("$B/bin/api" "/api/cvd-matrix?symbol=$S" 2>/dev/null)
  [ -n "$PAYLOAD" ] || { echo "NO MEDIDO: /api/cvd-matrix no contesto para $CORTO"; exit 2; }
  VEREDICTO=$(printf '%s' "$PAYLOAD" | ARCO_S="$ARCO_S" RT_S="$RT_S" python3 -c "
import json,os,sys
try: d = json.load(sys.stdin)
except Exception as e: print('NOMED|no se pudo parsear cvd-matrix: %s' % e); sys.exit(0)
arco, rt = float(os.environ['ARCO_S']), float(os.environ['RT_S'])
faltan, servidas, elegibles, mentira = [], 0, 0, []
for lab, w in (d.get('windows') or {}).items():
    sec = w.get('window_seconds')
    if sec is None: continue
    if w.get('futures') is not None: servidas += 1
    # ELEGIBLE = solo el empalme puede servirla. Por debajo del arco del realtime la
    # ventana ya tiene fuente y un null ahi es OTRO defecto, no el que arregla K83.
    if sec <= rt: continue
    cabe = sec <= arco
    if not cabe:
        # E · control negativo: lo que el arco no cubre no puede venir servido.
        if w.get('futures') is not None:
            mentira.append('%s sirve futuros con %.1f h de arco' % (lab, arco/3600.0))
        continue
    if w.get('spot') is None: continue          # la ventana no la sabe contestar ni en spot
    elegibles += 1
    if w.get('futures') is None:
        faltan.append('%s (spot=%s, razon publicada %r)' % (
            lab, ('%.0f' % w['spot']) if w.get('spot') is not None else 'null',
            (w.get('futures_status') or {}).get('reason')))
print('%s|%d|%d|%s|%s' % ('MENTIRA' if mentira else 'OK', elegibles, servidas,
                          ' y '.join(faltan), ' y '.join(mentira)))
" 2>/dev/null)
  case "$VEREDICTO" in
    NOMED\|*) echo "NO MEDIDO: ${VEREDICTO#NOMED|} ($CORTO)"; exit 2 ;;
    OK\|*|MENTIRA\|*) : ;;
    *) echo "NO MEDIDO: la lectura de cvd-matrix de $CORTO no produjo veredicto ('$VEREDICTO')"; exit 2 ;;
  esac
  IFS='|' read -r ESTADO NELE NSER FALTAN MENTIRA <<EOF
$VEREDICTO
EOF
  [ "$ESTADO" = MENTIRA ] && {
    echo "NO MEDIDO: CONTROL NEGATIVO ROTO en $CORTO -- $MENTIRA. Mi medida del arco y lo que la aplicacion cree que puede servir no son la misma cosa, asi que el hueco que mide el brazo A no se puede atribuir todavia a la fuente que falta"
    exit 2
  }
  ELEGIBLES=$((ELEGIBLES+NELE)); SERVIDAS=$((SERVIDAS+NSER))
  [ -n "$FALTAN" ] && FALLOS="${FALLOS:+$FALLOS · }cvd_matrix de $CORTO calla futuros en $FALTAN"

  # --- B · delta_matrix: la que ve el operador en pantalla.
  DPAY=$("$B/bin/api" "/api/scalp/delta-matrix?symbol=$S" 2>/dev/null)
  [ -n "$DPAY" ] || { echo "NO MEDIDO: /api/scalp/delta-matrix no contesto para $CORTO"; exit 2; }
  DVER=$(printf '%s' "$DPAY" | ARCO_S="$ARCO_S" RT_S="$RT_S" python3 -c "
import json,os,sys
try: rows = json.load(sys.stdin)
except Exception as e: print('NOMED|no se pudo parsear delta-matrix: %s' % e); sys.exit(0)
if not isinstance(rows, list): print('NOMED|delta-matrix no devolvio una lista'); sys.exit(0)
arco, rt = float(os.environ['ARCO_S']), float(os.environ['RT_S'])
SEG = {'15s':15,'30s':30,'1m':60,'3m':180,'5m':300,'15m':900,'18m':1080,'30m':1800,
       '1h':3600,'4h':14400,'8h':28800,'1d':86400,'3d':259200}
faltan, servidas = [], 0
for r in rows:
    sec = SEG.get(r.get('window'))
    if sec is None: continue
    if r.get('fut_delta') is not None: servidas += 1
    if sec <= rt or sec > arco or r.get('spot_delta') is None: continue
    if r.get('fut_delta') is None:
        faltan.append('%s (spot_delta=%.0f, cobertura %r)' % (
            r['window'], r['spot_delta'], r.get('futures_coverage_status')))
print('OK|%d|%s' % (servidas, ' y '.join(faltan)))
" 2>/dev/null)
  case "$DVER" in NOMED\|*) echo "NO MEDIDO: ${DVER#NOMED|} ($CORTO)"; exit 2 ;; esac
  IFS='|' read -r _ DSER DFALTAN <<EOF
$DVER
EOF
  SERVIDAS=$((SERVIDAS+DSER))
  [ -n "$DFALTAN" ] && FALLOS="${FALLOS:+$FALLOS · }la matriz de delta que PINTA el panel calla futuros en $DFALTAN de $CORTO"
done

# --- D · control positivo: si NADA vino servido, el instrumento esta ciego y un rojo aqui
# no distinguiria el defecto de un fallo del canal.
[ "$SERVIDAS" -gt 0 ] || {
  echo "NO MEDIDO: ninguna ventana de ninguna de las dos rutas trajo futuros con numero. Sin un solo positivo no se puede saber si el null es el defecto o es el canal"
  exit 2
}
[ "$ELEGIBLES" -gt 0 ] || {
  echo "NO MEDIDO: 0 ventanas elegibles -- el arco de futures_trades_agg no llega hoy a ninguna ventana que cvd_matrix publique en spot"
  exit 2
}

# El ROJO tiene que distinguir "el arreglo no funciona" de "falta desplegar", que es la
# lectura facil y equivocada mientras el arbol va por delante de 140 (nota de K77 y K80).
ARBOL_OK=0
grep -q 'futures_flow_windows' "$REPO/app/scalp_logic.py" 2>/dev/null && ARBOL_OK=1

if [ -n "$FALLOS" ]; then
  [ "$ARBOL_OK" = 1 ] && FALLOS="$FALLOS · EL ARBOL YA LO TIENE ARREGLADO (existe futures_flow_windows): falta DESPLEGAR"
  printf 'ROJO: la ventana pide la fuente que no tiene el dato. %s · el arco medido de futures_trades_agg (%s) SI cubre esas ventanas: el null no es falta de dato, es un empalme que el spot tiene y el futuro no\n' \
    "$FALLOS" "$ARCO_TXT"
  exit 1
fi

printf 'las %d ventanas elegibles de las DOS rutas publican su pata de futuros. Elegible sale del arco MEDIDO de futures_trades_agg en 140 (%s), no de una constante. Control positivo: %d ventanas servidas con numero. Control negativo vivo: lo que el arco no cubre (3d, 7d) sigue nulo\n' \
  "$ELEGIBLES" "$ARCO_TXT" "$SERVIDAS"
