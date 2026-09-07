#!/bin/bash
# K22  signal_outcome son 632256 filas y 270 MB: por cada observacion, que paso a 1, 3,
# 5, 15, 30, 60, 120 y 240 minutos. Productor funcionando y cero API.
#
# ESLABON 6, Y AQUI SI HAY DONDE MORDER. K21 recalcula conteos; esta tabla lleva CIFRAS
# DERIVADAS -market_return_pct, up/down_excursion_pct, directional_return_pct, mfe_pct,
# mae_pct- que salen de cuatro precios crudos y de la direccion de la senal. El VERDE de
# este check no es "el dato existe": es que cada una de esas seis se RECALCULA desde su
# definicion, fila a fila, y cuadra a 1e-6 con lo que sirve la ruta.
#
# LAS DEFINICIONES NO SE COPIARON DEL PRODUCTOR, se derivaron y se confirmaron contra
# 108507 filas de 140 el 2026-08-26 (prodsql, agrupando por direction):
#   market_return_pct  = (end_price - entry)/entry*100                      100%
#   up_excursion_pct   = (max_high  - entry)/entry*100                      100%
#   down_excursion_pct = (min_low   - entry)/entry*100                      100%
#   directional_return = market si long, -market si short, NULL si neutral/unavailable
#   mfe_pct = greatest(0, up) si long · greatest(0,-down) si short          100%
#   mae_pct = greatest(0,-down) si long · greatest(0, up) si short          100%
# Las dos que no son obvias -el recorte en cero y el NULL en neutral- solo aparecen
# midiendo. Suponerlas habria dado un check que pasa por el motivo equivocado.
#
# EL RELOJ, Y AQUI MUERDE MAS QUE EN K21: estas filas se ACTUALIZAN. Nacen pending y se
# evaluan cuando vence su horizonte, que llega a 240 min. Una ventana reciente es un
# blanco movil y el check fallaria por motivos que no son correccion. Por eso la ventana
# va con MARGEN_HORAS por detras y ademas se EXIGE que no quede ni una pending dentro: si
# queda, es NO MEDIDO, no ROJO.
set -uo pipefail
B=/srv/coinanalyze/harness; . "$B/env"
RUTA=/api/signals/outcomes
TOPE_FILAS=600
MARGEN_HORAS=6

_crudo=$("$B/bin/prodsql" "
  SELECT o.symbol,
         to_char(date_trunc('hour', so.window_start) AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:00:00\"Z\"'),
         count(*), count(*) FILTER (WHERE so.status='pending')
  FROM signal_outcome so JOIN signal_observation o USING (observation_id)
  WHERE so.window_start >= now() - interval '48 hours'
    AND so.window_start <  date_trunc('hour', now()) - interval '$MARGEN_HORAS hours'
  GROUP BY 1,2
  HAVING count(*) BETWEEN 20 AND $TOPE_FILAS AND count(*) FILTER (WHERE so.status='pending') = 0
  ORDER BY 2 DESC, 3 DESC
  LIMIT 1" 2>/dev/null) || { rc=$?; echo "NO MEDIDO: prodsql no contesto (rc=$rc). Esto NO es una ventana vacia: es que no se pudo preguntar."; exit 2; }
ventana=$(printf '%s\n' "$_crudo" | grep -E '^[A-Z0-9_.]+\|' | head -1)

[ -n "$ventana" ] || { echo "NO MEDIDO: ninguna hora de las ultimas 48 h con margen de $MARGEN_HORAS h tiene entre 20 y $TOPE_FILAS resultados y cero pending"; exit 2; }

simbolo=${ventana%%|*}; resto=${ventana#*|}
desde=${resto%%|*}; resto=${resto#*|}
esperadas=${resto%%|*}
hasta=$(date -u -d "$desde +1 hour" +%Y-%m-%dT%H:00:00Z 2>/dev/null)
[ -n "$hasta" ] || { echo "NO MEDIDO: no se pudo calcular el final de la ventana desde '$desde'"; exit 2; }

ref=$("$B/bin/prodsql" "
  SELECT count(*),
         count(*) FILTER (WHERE so.status='evaluated'),
         count(*) FILTER (WHERE so.status='not_evaluable'),
         count(DISTINCT so.horizon_minutes),
         count(DISTINCT so.observation_id),
         count(*) FILTER (WHERE so.directional_return_pct IS NULL),
         round(sum(so.bars_found)::numeric,0),
         round(sum(so.market_return_pct)::numeric,6)
  FROM signal_outcome so JOIN signal_observation o USING (observation_id)
  WHERE o.symbol='$simbolo'
    AND so.window_start >= timestamptz '$desde'
    AND so.window_start <  timestamptz '$hasta'" 2>/dev/null | grep -E '^[0-9]+\|' | head -1)
[ -n "$ref" ] || { echo "NO MEDIDO: la consulta de referencia contra signal_outcome no devolvio nada"; exit 2; }

# --- LA CAPA DE ABAJO: los cuatro precios contra su ORIGEN, no contra si mismos --------
# Sin esto el check afirma "dados los cuatro precios que guardamos, las seis derivadas son
# correctas", que es consistencia interna y no fidelidad: un max_high mal escrito al
# capturar pasaria, porque las seis serian consistentes con el. Es la misma forma que el
# manifiesto de K49. Aqui se recalculan max_high, min_low, end_price y bars_found desde
# ohlcv 1min, con el window_start/window_end que declara CADA fila, y se comparan contra
# lo que sirve la RUTA -no contra la tabla, que seria SQL contra SQL y dejaria al endpoint
# fuera del bucle-.
# El borde es [window_start, window_end): confirmado porque con el bars_found cuadra
# 600/600. El LATERAL tarda 0.48 s sobre 600 filas, muy por debajo del statement_timeout.
ORIGEN=$(mktemp) || { echo "NO MEDIDO: no se pudo crear el fichero de origen"; exit 2; }
trap 'rm -f "$ORIGEN"' EXIT
TODO=1 "$B/bin/prodsql" "
  SELECT so.outcome_id, v.barras, v.hi, v.lo, v.cierre
  FROM signal_outcome so
  JOIN signal_observation o USING (observation_id)
  CROSS JOIN LATERAL (
    SELECT count(DISTINCT c.ts) AS barras, max(c.high) AS hi, min(c.low) AS lo,
           (SELECT c2.close FROM ohlcv c2 WHERE c2.symbol=o.symbol AND c2.interval='1min'
              AND c2.ts >= so.window_start AND c2.ts < so.window_end
            ORDER BY c2.ts DESC LIMIT 1) AS cierre
    FROM ohlcv c WHERE c.symbol=o.symbol AND c.interval='1min'
      AND c.ts >= so.window_start AND c.ts < so.window_end
  ) v
  WHERE o.symbol='$simbolo' AND so.status='evaluated'
    AND so.window_start >= timestamptz '$desde'
    AND so.window_start <  timestamptz '$hasta'" 2>/dev/null | grep -E '^[0-9]+\|' > "$ORIGEN"
[ -s "$ORIGEN" ] || { echo "NO MEDIDO: no se pudo recalcular ningun precio desde ohlcv para $simbolo $desde"; exit 2; }

# TODO=1: se verifica que estan TODAS las filas y que cada una recalcula, asi que un corte
# de salida recortaria justo la afirmacion. Los frenos son TOPE_FILAS y el conteo de abajo.
cuerpo=$(TODO=1 "$B/bin/api" "$RUTA?symbol=$simbolo&since=$desde&until=$hasta" 2>/dev/null) || { rc=$?; echo "NO MEDIDO: la API no contesto (rc=$rc). Esto NO es una ventana vacia: es que no se pudo preguntar."; exit 2; }
[ -n "$cuerpo" ] || { echo "NO MEDIDO: $RUTA no devolvio nada (canal)"; exit 2; }

printf '%s' "$cuerpo" | python3 -c '
import json, sys
ref = sys.argv[1].split("|")
simbolo, desde, esperadas, ruta = sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
crudo = sys.stdin.read()
try:
    d = json.loads(crudo)
except Exception as e:
    print(f"NO MEDIDO: {ruta} no devolvio JSON ({e}): {crudo[:80]!r}"); sys.exit(2)
if isinstance(d, dict) and "outcomes" not in d and set(d) <= {"detail"}:
    print(f"la capacidad no tiene API: {ruta} devuelve {d} en 140 ({esperadas} resultados solo en {desde} de {simbolo})"); sys.exit(1)
if not isinstance(d, dict) or "outcomes" not in d:
    print(f"{ruta} responde pero no sirve los resultados: sin clave outcomes"); sys.exit(1)
filas = d["outcomes"]
if d.get("truncated"):
    print(f"NO MEDIDO: {ruta} declara truncated=true, no se puede verificar la ventana entera"); sys.exit(2)
if d.get("count") is not None and d["count"] != len(filas):
    print(f"{ruta} declara count={d['count']} y sirve {len(filas)} resultados"); sys.exit(1)

CLAVES = ("outcome_id","observation_id","direction","horizon_minutes","status",
          "bars_expected","bars_found","entry_reference_price","end_price","max_high",
          "min_low","market_return_pct","up_excursion_pct","down_excursion_pct",
          "directional_return_pct","mfe_pct","mae_pct")
faltan = sorted({k for k in CLAVES for f in filas if k not in f})
if faltan:
    print(f"{ruta} sirve resultados sin las claves {faltan[:6]}"); sys.exit(1)

def casi(a, b, tol=1e-6):
    if a is None and b is None: return True
    if a is None or b is None: return False
    return abs(a - b) < tol

# --- CAPA 1: los precios que sirve la ruta contra ohlcv, su origen ---------------------
origen = {}
with open(sys.argv[6]) as fh:
    for linea in fh:
        oid, barras, hi, lo, cierre = linea.rstrip("\n").split("|")
        origen[int(oid)] = (int(barras), float(hi), float(lo), float(cierre))

infieles, comparadas = [], 0
for f in filas:
    if f["status"] != "evaluated":
        continue
    o = origen.get(f["outcome_id"])
    if o is None:
        infieles.append(f"outcome {f['outcome_id']} evaluado y ohlcv no da ni una vela en su ventana")
        continue
    barras, hi, lo, cierre = o
    for nombre, desde_ohlcv, servido in (("bars_found", barras, f["bars_found"]),
                                         ("max_high", hi, f["max_high"]),
                                         ("min_low", lo, f["min_low"]),
                                         ("end_price", cierre, f["end_price"])):
        comparadas += 1
        if not casi(float(desde_ohlcv), None if servido is None else float(servido), 1e-9):
            infieles.append(f"outcome {f['outcome_id']} {nombre}: sirve {servido} y de ohlcv sale {desde_ohlcv}")
    # Un max_high correcto sobre una ventana INCOMPLETA es un numero correcto sobre datos
    # que faltan. Medido en 140: las 147260 filas evaluated de tres dias tienen
    # bars_found = bars_expected, o sea que es invariante para ese estado -no para
    # pending, que aun no se evaluo-. Conecta con K02, K03 y K04.
    if f["bars_found"] != f["bars_expected"]:
        infieles.append(f"outcome {f['outcome_id']} evaluado con {f['bars_found']} de {f['bars_expected']} velas: hueco dentro del horizonte")
if infieles:
    print(f"{len(infieles)} de {comparadas} comparaciones contra ohlcv fallan: " + " · ".join(infieles[:3])); sys.exit(1)
if comparadas == 0:
    print(f"NO MEDIDO: la ventana {desde} de {simbolo} no trae ni un resultado evaluado que comparar contra ohlcv"); sys.exit(2)

# --- CAPA 2 (ESLABON 6): las seis derivadas, fila a fila, desde los precios crudos -----
malas = []
recalculadas = 0
for f in filas:
    if f["status"] != "evaluated" or f["entry_reference_price"] in (None, 0):
        continue
    e, fin = f["entry_reference_price"], f["end_price"]
    hi, lo, dirn = f["max_high"], f["min_low"], f["direction"]
    mkt = (fin - e) / e * 100
    up  = (hi - e) / e * 100
    dn  = (lo - e) / e * 100
    corto = dirn == "short"
    dire = None if dirn not in ("long", "short") else (-mkt if corto else mkt)
    mfe = None if dirn not in ("long", "short") else max(0.0, -dn if corto else up)
    mae = None if dirn not in ("long", "short") else max(0.0, up if corto else -dn)
    for nombre, calculado, servido in (
        ("market_return_pct", mkt, f["market_return_pct"]),
        ("up_excursion_pct", up, f["up_excursion_pct"]),
        ("down_excursion_pct", dn, f["down_excursion_pct"]),
        ("directional_return_pct", dire, f["directional_return_pct"]),
        ("mfe_pct", mfe, f["mfe_pct"]),
        ("mae_pct", mae, f["mae_pct"]),
    ):
        recalculadas += 1
        if not casi(calculado, servido):
            oid = f["outcome_id"]
            malas.append(f"outcome {oid} {nombre}: sirve {servido} y de sus precios sale {calculado}")
if malas:
    print(f"{len(malas)} de {recalculadas} derivadas NO salen de los precios que sirve la propia ruta: " + " · ".join(malas[:3])); sys.exit(1)
if recalculadas == 0:
    print(f"NO MEDIDO: la ventana {desde} de {simbolo} no trae ni un resultado evaluado con precios"); sys.exit(2)

# --- y los conteos, contra SQL escrito aparte -----------------------------------------
agregados = [
    len(filas),
    sum(1 for f in filas if f["status"] == "evaluated"),
    sum(1 for f in filas if f["status"] == "not_evaluable"),
    len({f["horizon_minutes"] for f in filas}),
    len({f["observation_id"] for f in filas}),
    sum(1 for f in filas if f["directional_return_pct"] is None),
    sum(f["bars_found"] for f in filas),
    round(sum(f["market_return_pct"] for f in filas if f["market_return_pct"] is not None), 6),
]
NOMBRES = ("filas","evaluados","no evaluables","horizontes distintos",
           "observaciones distintas","sin retorno direccional","suma bars_found",
           "suma market_return_pct")
descuadres = []
for nombre, esperado, obtenido in zip(NOMBRES, ref, agregados):
    e, o = esperado.strip(), str(obtenido)
    try: iguales = abs(float(e) - float(o)) < 1e-6
    except ValueError: iguales = e == o
    if not iguales: descuadres.append(f"{nombre} {o} != {e}")
if descuadres:
    print(f"{len(descuadres)} de {len(NOMBRES)} conteos no cuadran contra signal_outcome: " + " · ".join(descuadres[:4])); sys.exit(1)
if len(filas) != esperadas:
    print(f"la ruta sirve {len(filas)} resultados y la hora tiene {esperadas}"); sys.exit(1)

print(f"{comparadas} precios contra ohlcv + {recalculadas} derivadas desde esos precios + {len(NOMBRES)} conteos, todo cuadra: {simbolo} {desde}, {len(filas)} resultados enteros, sin una vela ausente dentro de ningun horizonte")
' "$ref" "$simbolo" "$desde" "$esperadas" "$RUTA" "$ORIGEN"
exit $?
