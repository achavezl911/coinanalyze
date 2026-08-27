#!/bin/bash
# K23  signal_execution_snapshot son 200068 filas y 166 MB: el coste real de ejecutar
# cada senal, con una CURVA DE COSTE por tamano de orden. Productor funcionando, cero API.
#
# QUE CAPA CIERRA ESTE CHECK Y CUAL DEJA ABIERTA. Se declara aqui a proposito, porque un
# eslabon 6 que no dice donde se para invita a leerlo de mas.
#
#   CERRADA · la aritmetica de la curva. Por cada punto (tamano x lado) se recalculan
#     filled+shortfall = notional · insufficient_depth <-> market_cost null ·
#     slippage_bps_vs_best · market_cost_bps_vs_mid, y ademas mid_px y spread_bps desde
#     best_bid/best_ask. Todo desde los campos que sirve la propia ruta.
#   CERRADA · el TOPE del libro contra su origen: best_bid_px y best_ask_px contra
#     orderbook_snapshot en el book_ts que declara cada fila. Medido en 140: cuadra
#     3209/3209. OJO, la cobertura no es total: solo 3209 de 3816 filas de 4 h tienen
#     libro persistido en su ts exacto (84%), porque el libro se muestrea y la captura
#     no. Se exige el cuadre de las que SI tienen origen y se DECLARA la cobertura.
#   ABIERTA · avg_price y levels_used. Recalcularlos exige recorrer la escalera de 50
#     niveles, y orderbook_snapshot NO la retiene: guarda agregados -bid_px, ask_px,
#     notional_l1/l5/l10, imbalance-. Sin escalera no hay forma de repetir el paseo por
#     el libro. Este check NO afirma nada sobre avg_price mas alla de que las cifras
#     derivadas de el son consistentes.
#
# LAS CONVENCIONES SE MIDIERON, NO SE SUPUSIERON (140, 46768 puntos, 2026-08-26):
#   mid_px      = (best_bid+best_ask)/2                                    100%
#   spread_bps  = (best_ask-best_bid)/mid*10000                            100%
#   slippage_bps_vs_best = (avg-best_ask)/best_ask*1e4 compra ·
#                          (best_bid-avg)/best_bid*1e4 venta               100%
#   market_cost_bps_vs_mid = (avg-mid)/mid*1e4 compra · (mid-avg)/mid*1e4 venta
#   filled_usd + shortfall_usd = notional                                  100%
#   Y LA QUE NO ES OBVIA: market_cost_bps_vs_mid es NULL EXACTAMENTE cuando
#   insufficient_depth, bicondicional exacto -45354 con bandera falsa y cero nulos, 1430
#   con bandera cierta y los 1430 nulos-, mientras slippage_bps_vs_best SI se calcula.
#   Al medirla, un count(*) FILTER la conto como descuadre en vez de como nulo: la misma
#   trampa que en K22 con mfe_pct. Por eso se mide antes de escribir el check.
#
# EL RELOJ: estas filas NO se actualizan -UNIQUE(observation_id,exchange), sin estados
# que transicionen-, asi que no hace falta margen para que se asienten. Pero el libro de
# origen SI caduca: orderbook_snapshot retiene ~8 h medidas. La ventana va reciente a
# proposito, justo al reves que K22.
set -uo pipefail
B=/srv/coinanalyze/harness; . "$B/env"
RUTA=/api/signals/execution
TOPE_FILAS=400

ventana=$("$B/bin/prodsql" "
  SELECT o.symbol,
         to_char(date_trunc('hour', s.captured_at) AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:00:00\"Z\"'),
         count(*)
  FROM signal_execution_snapshot s JOIN signal_observation o USING (observation_id)
  WHERE s.captured_at >= now() - interval '5 hours'
    AND s.captured_at <  date_trunc('hour', now())
    AND s.status='valid'
  GROUP BY 1,2 HAVING count(*) BETWEEN 20 AND $TOPE_FILAS
  ORDER BY 2 DESC, 3 DESC LIMIT 1" 2>/dev/null | grep -E '^[A-Z0-9_.]+\|' | head -1)
[ -n "$ventana" ] || { echo "NO MEDIDO: ninguna hora cerrada de las ultimas 5 h tiene entre 20 y $TOPE_FILAS capturas validas"; exit 2; }

simbolo=${ventana%%|*}; resto=${ventana#*|}
desde=${resto%%|*}; esperadas=${resto##*|}
hasta=$(date -u -d "$desde +1 hour" +%Y-%m-%dT%H:00:00Z 2>/dev/null)
[ -n "$hasta" ] || { echo "NO MEDIDO: no se pudo calcular el final de la ventana"; exit 2; }

ref=$("$B/bin/prodsql" "
  SELECT count(*), count(DISTINCT s.exchange), count(DISTINCT s.observation_id),
         count(*) FILTER (WHERE s.status='valid'),
         round(sum(s.levels_reported)::numeric,0),
         round(sum(s.spread_bps)::numeric,6)
  FROM signal_execution_snapshot s JOIN signal_observation o USING (observation_id)
  WHERE o.symbol='$simbolo' AND s.captured_at >= timestamptz '$desde'
    AND s.captured_at < timestamptz '$hasta' AND s.status='valid'" 2>/dev/null | grep -E '^[0-9]+\|' | head -1)
[ -n "$ref" ] || { echo "NO MEDIDO: la consulta de referencia no devolvio nada"; exit 2; }

# El TOPE del libro contra su origen. Solo las filas cuyo libro se persistio en su ts.
ORIGEN=$(mktemp) || { echo "NO MEDIDO: no se pudo crear el fichero de origen"; exit 2; }
trap 'rm -f "$ORIGEN"' EXIT
TODO=1 "$B/bin/prodsql" "
  SELECT s.execution_snapshot_id, b.bid_px, b.ask_px
  FROM signal_execution_snapshot s
  JOIN signal_observation o USING (observation_id)
  JOIN orderbook_snapshot b ON b.symbol=o.symbol AND b.exchange=s.exchange AND b.ts=s.book_ts
  WHERE o.symbol='$simbolo' AND s.captured_at >= timestamptz '$desde'
    AND s.captured_at < timestamptz '$hasta' AND s.status='valid'" 2>/dev/null \
  | grep -E '^[0-9]+\|' > "$ORIGEN"

cuerpo=$(TODO=1 "$B/bin/api" "$RUTA?symbol=$simbolo&since=$desde&until=$hasta" 2>/dev/null)
[ -n "$cuerpo" ] || { echo "NO MEDIDO: $RUTA no devolvio nada (canal)"; exit 2; }

printf '%s' "$cuerpo" | python3 -c '
import json, sys
ref = sys.argv[1].split("|")
simbolo, desde, esperadas, ruta, camino = sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5], sys.argv[6]
crudo = sys.stdin.read()
try:
    d = json.loads(crudo)
except Exception as e:
    print(f"NO MEDIDO: {ruta} no devolvio JSON ({e}): {crudo[:80]!r}"); sys.exit(2)
if isinstance(d, dict) and "snapshots" not in d and set(d) <= {"detail"}:
    print(f"la capacidad no tiene API: {ruta} devuelve {d} en 140 ({esperadas} capturas solo en {desde} de {simbolo})"); sys.exit(1)
if not isinstance(d, dict) or "snapshots" not in d:
    print(f"{ruta} responde pero no sirve las capturas: sin clave snapshots"); sys.exit(1)
filas = d["snapshots"]
if d.get("truncated"):
    print(f"NO MEDIDO: {ruta} declara truncated=true"); sys.exit(2)
if d.get("count") is not None and d["count"] != len(filas):
    print(f"{ruta} declara count={d["count"]} y sirve {len(filas)} capturas"); sys.exit(1)

CLAVES = ("execution_snapshot_id","observation_id","exchange","status","book_ts",
          "best_bid_px","best_ask_px","mid_px","spread_bps","levels_reported","cost_curve")
faltan = sorted({k for k in CLAVES for f in filas if k not in f})
if faltan:
    print(f"{ruta} sirve capturas sin las claves {faltan[:6]}"); sys.exit(1)

# LA REFERENCIA CUENTA SOLO status='valid' Y LA RUTA SIRVE TODOS LOS ESTADOS, cada uno
# CON SU status. Comparar el total servido contra una referencia filtrada era comparar
# dos poblaciones distintas: mientras no hubo capturas 'stale' en la hora muestreada los
# dos numeros coincidian por casualidad, y el 2026-08-27T17:00Z aparecieron 3 -359 valid
# + 3 stale = 362- y el check enrojecio sin que nada estuviera roto. La ruta NO mezcla a
# ciegas: declara el estado de cada fila, que es justo lo que este proyecto le exige a
# todo lo demas. El defecto era del instrumento. Se compara valid contra valid, y las
# demas se DECLARAN, que es mas informacion que antes y no menos.
no_validas = [f for f in filas if f["status"] != "valid"]
otros = [f["status"] for f in no_validas]
filas = [f for f in filas if f["status"] == "valid"]

def casi(a, b, tol=1e-6):
    if a is None and b is None: return True
    if a is None or b is None: return False
    return abs(a - b) < tol

fallos = []

# --- CAPA CERRADA 1: el tope del libro contra orderbook_snapshot ----------------------
origen = {}
for linea in open(camino):
    sid, bid, ask = linea.rstrip("\n").split("|")
    origen[int(sid)] = (float(bid), float(ask))
con_origen = 0
for f in filas:
    o = origen.get(f["execution_snapshot_id"])
    if o is None:
        continue
    con_origen += 1
    if not casi(f["best_bid_px"], o[0], 1e-9):
        fallos.append(f"captura {f["execution_snapshot_id"]} best_bid_px sirve {f["best_bid_px"]} y el libro dice {o[0]}")
    if not casi(f["best_ask_px"], o[1], 1e-9):
        fallos.append(f"captura {f["execution_snapshot_id"]} best_ask_px sirve {f["best_ask_px"]} y el libro dice {o[1]}")

# --- CAPA CERRADA 2: la aritmetica de la curva, punto a punto -------------------------
puntos = 0
for f in filas:
    bid, ask, mid = f["best_bid_px"], f["best_ask_px"], f["mid_px"]
    if None in (bid, ask, mid):
        continue
    if not casi(mid, (bid + ask) / 2, 1e-9):
        fallos.append(f"captura {f["execution_snapshot_id"]} mid_px sirve {mid} y de bid/ask sale {(bid+ask)/2}")
    if not casi(f["spread_bps"], (ask - bid) / mid * 10000):
        fallos.append(f"captura {f["execution_snapshot_id"]} spread_bps sirve {f["spread_bps"]} y de bid/ask sale {(ask-bid)/mid*10000}")
    for tamano, curva in (f["cost_curve"] or {}).items():
        for lado in ("buy", "sell"):
            v = curva.get(lado)
            if not v:
                continue
            puntos += 1
            notional = float(tamano)
            avg, filled = v.get("avg_price"), v.get("filled_usd")
            falta, insuf = v.get("shortfall_usd"), v.get("insufficient_depth")
            # UN CENTIMO, no 1e-6: filled_usd y shortfall_usd se guardan a dos
            # decimales -medido, scale<=2 en los cuatro tamanos- y dos numeros
            # redondeados a centimos pueden sumar un centimo de mas. Exigir 1e-6 sobre
            # cantidades de 1e5 era pedirle a la representacion una precision que no
            # tiene, y hacia el check INTERMITENTE: paso un dia entero y salto solo
            # cuando el caso raro cayo dentro de la ventana. Medido en 140 sobre 184800
            # puntos de 24 h: UN solo punto no cuadra exacto y se desvia 0.0100, o sea
            # 0.0005%. Un fallo de verdad -un nivel del libro que falte- mueve dolares,
            # no centimos, y sigue saltando.
            if not casi(filled + falta, notional, 0.011):
                fallos.append(f"punto {tamano}/{lado}: filled+shortfall {filled+falta} != {notional}")
            if insuf != (falta > 0):
                fallos.append(f"punto {tamano}/{lado}: insufficient_depth={insuf} con shortfall={falta}")
            if avg is None:
                continue
            slip = (avg - ask) / ask * 10000 if lado == "buy" else (bid - avg) / bid * 10000
            if not casi(v.get("slippage_bps_vs_best"), slip):
                fallos.append(f"punto {tamano}/{lado}: slippage sirve {v.get("slippage_bps_vs_best")} y sale {slip}")
            # La que no es obvia: NULL exactamente cuando no se pudo llenar.
            coste = v.get("market_cost_bps_vs_mid")
            if insuf:
                if coste is not None:
                    fallos.append(f"punto {tamano}/{lado}: sin profundidad y aun asi market_cost={coste}")
            else:
                esperado = (avg - mid) / mid * 10000 if lado == "buy" else (mid - avg) / mid * 10000
                if not casi(coste, esperado):
                    fallos.append(f"punto {tamano}/{lado}: market_cost sirve {coste} y sale {esperado}")

if fallos:
    print(f"{len(fallos)} comprobaciones fallan sobre {len(filas)} capturas y {puntos} puntos de curva: " + " · ".join(fallos[:3])); sys.exit(1)
if puntos == 0:
    print(f"NO MEDIDO: la ventana {desde} de {simbolo} no trae ni un punto de curva de coste"); sys.exit(2)

agregados = [len(filas), len({f["exchange"] for f in filas}), len({f["observation_id"] for f in filas}),
             sum(1 for f in filas if f["status"] == "valid"),
             sum(f["levels_reported"] for f in filas),
             round(sum(f["spread_bps"] for f in filas if f["spread_bps"] is not None), 6)]
NOMBRES = ("filas","mercados distintos","observaciones distintas","validas",
           "suma levels_reported","suma spread_bps")
descuadres = []
for nombre, esperado, obtenido in zip(NOMBRES, ref, agregados):
    e, o = esperado.strip(), str(obtenido)
    try: iguales = abs(float(e) - float(o)) < 1e-6
    except ValueError: iguales = e == o
    if not iguales: descuadres.append(f"{nombre} {o} != {e}")
if descuadres:
    print(f"{len(descuadres)} de {len(NOMBRES)} conteos no cuadran: " + " · ".join(descuadres[:4])); sys.exit(1)
if len(filas) != esperadas:
    print(f"la ruta sirve {len(filas)} capturas y la hora tiene {esperadas}"); sys.exit(1)

cobertura = f"{con_origen}/{len(filas)}"
declarado = ""
if no_validas:
    conteo = {e: otros.count(e) for e in sorted(set(otros))}
    reparto = ", ".join(f"{e}={n}" for e, n in conteo.items())
    declarado = (f" DECLARADO y no juzgado: la ruta sirvio ademas {len(no_validas)} capturas"
                 f" no validas ({reparto}), cada una CON su status, y no se recalculan"
                 f" porque su libro no era utilizable en su instante")
print(f"{puntos} puntos de curva recalculados + tope del libro contra orderbook_snapshot en {cobertura} capturas con origen persistido + {len(NOMBRES)} conteos: {simbolo} {desde}, {len(filas)} capturas enteras. ABIERTO a proposito: avg_price y levels_used, que exigen la escalera que el libro no retiene.{declarado}")
' "$ref" "$simbolo" "$desde" "$esperadas" "$RUTA" "$ORIGEN"
exit $?
