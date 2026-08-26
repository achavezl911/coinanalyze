#!/bin/bash
# K24  signal_replay_frame son 125717 filas y 162 MB: los INSUMOS CONGELADOS con los que
# se tomo cada decision, uno por observacion, con su hash. Productor funcionando, cero API.
#
# QUE CAPA CIERRA ESTE CHECK Y CUAL DEJA ABIERTA. Se declara aqui, como en K21-K23.
#
#   CERRADA · el marco esta INTACTO. Por cada frame se recalcula sha256 del JSON canonico
#     del context que sirve LA RUTA y se compara contra el context_hash que escribio el
#     productor, leido de 140 POR OTRO CANAL (ssh+psql, no la API). Un context mutado en
#     el camino no puede pasar: tendria que traer tambien el hash de la base.
#   CERRADA · la DECISION es reproducible. Se vuelve a ejecutar el nucleo real
#     -compute_scalp_summary, via replay_summary_for_logic- sobre el context congelado y
#     el resumen resultante tiene que salir IDENTICO byte a byte (hash canonico) a la
#     evidence que se guardo. Esto no es "la ruta cuadra consigo misma": el nucleo se
#     importa del repo y se ejecuta aqui.
#   CERRADA · y contra OTRO endpoint y OTRA tabla: 12 campos de la decision -state,
#     confidence, reason, long_score, short_score, evidence_coverage_pct,
#     decision_status, direction, actionable, reference_price y su fuente y su hora- se
#     recalculan desde el replay y se comparan contra lo que sirve /api/signals/ledger,
#     que sale de columnas de signal_observation. Si la ruta de replay se inventara la
#     evidence, el ledger la contradiria.
#   CERRADA · la capa de ABAJO, la que a K22 se le habia escapado: cuatro INSUMOS del
#     context contra su origen persistido en ohlcv 1min -ohlcv_price en su ohlcv_price_at,
#     first_px_15m, last_px_15m y bars_15m sobre la ventana [oi_window_start,
#     oi_window_end) que declara CADA frame-. No se comparan contra la propia fila.
#   ABIERTA · el resto del context: libro (spread_bps, imbalance_l1/l5/l10, wall_*),
#     liquidaciones (long_liq, short_liq), OI (oi_now, oi_start), deltas de futuros y
#     spot, session_vwap y baseline_3m. NO es "no se puede": spread/imbalance tienen
#     origen en orderbook_snapshot (K23) y las liquidaciones en liquidations_realtime
#     (K42). Es que este check no los ancla y no afirma nada sobre ellos. Lo que SI es
#     imposible por diseno es reconstruir el context entero a posteriori, y esta escrito
#     en el esquema: sql/schema.sql:713 "forward-only: historical context is never
#     reconstructed after the fact from corrected/recovered market data".
#
# LA FRONTERA QUE SE MIDIO ANTES DE ESCRIBIR EL CHECK (140, 1800 frames, 2026-08-26):
#   ohlcv_price contra ohlcv en ohlcv_price_at-1min   0 descuadres de 1800
#   first_px_15m contra el open de la primera vela    0 descuadres de 1800
#   last_px_15m y bars_15m                            0 descuadres en los 1435 que
#     declaran price_move_15m_coverage=complete; y 11 de 65 en los que declaran partial.
#   ESO NO ES UN FALLO y por poco lo cuento como tal: son los frames capturados 2-5 s
#   DESPUES de cerrar la ventana, que vieron 14 velas porque la ultima aun no estaba
#   escrita. Lo DECLARAN ellos mismos (bars_15m=14, coverage=partial). Los capturados a
#   partir de 6 s vieron las 15 y cuadran 288/288. Es la misma familia que bars_found en
#   K22. Por eso last_px_15m/bars_15m se exigen SOLO a los completos, y a los parciales
#   se les exige lo que si es invariante: bars(hoy) >= bars_15m(congelado), porque ohlcv
#   solo se rellena hacia adelante. Un frame que hubiera visto MAS velas de las que hoy
#   existen seria perdida de datos: 0 casos de 1800.
#
# EL NUCLEO SALE DEL REPO DE 143 (HEAD). Hoy HEAD es exactamente lo que corre 140. Si
# alguien cambia compute_scalp_summary sin subir logic_version, esta comparacion sale
# ROJO, que es justo lo que tiene que pasar. Si la fila trae una logic_version que este
# arbol no sabe replicar, sale NO MEDIDO: no se puede replicar lo que no se tiene.
set -uo pipefail
B=/srv/coinanalyze/harness; . "$B/env"
RUTA=/api/signals/replay
RUTA_LEDGER=/api/signals/ledger
TOPE_FILAS=400
PY=/srv/coinanalyze/repo/.venv/bin/python
[ -x "$PY" ] || { echo "NO MEDIDO: falta $PY, que es de donde sale el nucleo que replica"; exit 2; }

ventana=$("$B/bin/prodsql" "
  SELECT o.symbol,
         to_char(date_trunc('hour', fr.context_as_of) AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:00:00\"Z\"'),
         count(*)
  FROM signal_replay_frame fr JOIN signal_observation o USING (observation_id)
  WHERE fr.context_as_of >= now() - interval '5 hours'
    AND fr.context_as_of <  date_trunc('hour', now())
  GROUP BY 1,2 HAVING count(*) BETWEEN 20 AND $TOPE_FILAS
  ORDER BY 2 DESC, 3 DESC LIMIT 1" 2>/dev/null | grep -E '^[A-Z0-9_.]+\|' | head -1)
[ -n "$ventana" ] || { echo "NO MEDIDO: ninguna hora cerrada de las ultimas 5 h tiene entre 20 y $TOPE_FILAS frames"; exit 2; }

simbolo=${ventana%%|*}; resto=${ventana#*|}
desde=${resto%%|*}; esperadas=${resto##*|}
hasta=$(date -u -d "$desde +1 hour" +%Y-%m-%dT%H:00:00Z 2>/dev/null)
led_desde=$(date -u -d "$desde -5 minutes" +%Y-%m-%dT%H:%M:00Z 2>/dev/null)
led_hasta=$(date -u -d "$desde +65 minutes" +%Y-%m-%dT%H:%M:00Z 2>/dev/null)
[ -n "$hasta" ] && [ -n "$led_desde" ] && [ -n "$led_hasta" ] || { echo "NO MEDIDO: no se pudo calcular la ventana"; exit 2; }

ref=$("$B/bin/prodsql" "
  SELECT count(*), count(DISTINCT fr.observation_id), count(DISTINCT fr.context_hash),
         count(DISTINCT fr.context_version),
         sum((fr.context->>'bars_15m')::int),
         count(*) FILTER (WHERE fr.context->>'price_move_15m_coverage'='complete')
  FROM signal_replay_frame fr JOIN signal_observation o USING (observation_id)
  WHERE o.symbol='$simbolo' AND fr.context_as_of >= timestamptz '$desde'
    AND fr.context_as_of < timestamptz '$hasta'" 2>/dev/null | grep -E '^[0-9]+\|' | head -1)
[ -n "$ref" ] || { echo "NO MEDIDO: la consulta de referencia no devolvio nada"; exit 2; }

# El hash que escribio el productor y el origen en ohlcv, los dos por ssh+psql y no por
# la API: es lo que impide que la ruta se valide a si misma.
ORIGEN=$(mktemp) || { echo "NO MEDIDO: no se pudo crear el fichero de origen"; exit 2; }
CUERPO=$(mktemp) || { echo "NO MEDIDO: no se pudo crear el fichero de respuesta"; exit 2; }
LIBRO=$(mktemp) || { echo "NO MEDIDO: no se pudo crear el fichero del ledger"; exit 2; }
trap 'rm -f "$ORIGEN" "$CUERPO" "$LIBRO"' EXIT

TODO=1 "$B/bin/prodsql" "
  SELECT fr.observation_id, fr.context_hash, px.ref_px, w.first_open, w.last_close, w.bars
  FROM signal_replay_frame fr
  JOIN signal_observation o USING (observation_id)
  LEFT JOIN LATERAL (
    SELECT close AS ref_px FROM ohlcv
    WHERE symbol=o.symbol AND interval='1min'
      AND ts = (fr.context->>'ohlcv_price_at')::timestamptz - interval '1 minute'
  ) px ON true
  LEFT JOIN LATERAL (
    SELECT (array_agg(open  ORDER BY ts ASC))[1]  AS first_open,
           (array_agg(close ORDER BY ts DESC))[1] AS last_close,
           count(*)::int AS bars
    FROM ohlcv
    WHERE symbol=o.symbol AND interval='1min'
      AND ts >= (fr.context->>'oi_window_start')::timestamptz
      AND ts <  (fr.context->>'oi_window_end')::timestamptz
  ) w ON true
  WHERE o.symbol='$simbolo' AND fr.context_as_of >= timestamptz '$desde'
    AND fr.context_as_of < timestamptz '$hasta'" 2>/dev/null \
  | grep -E '^[0-9]+\|' > "$ORIGEN"

TODO=1 "$B/bin/api" "$RUTA?symbol=$simbolo&since=$desde&until=$hasta&limit=$TOPE_FILAS" > "$CUERPO" 2>/dev/null
[ -s "$CUERPO" ] || { echo "NO MEDIDO: $RUTA no devolvio nada (canal)"; exit 2; }
TODO=1 "$B/bin/api" "$RUTA_LEDGER?symbol=$simbolo&since=$led_desde&until=$led_hasta&limit=5000" > "$LIBRO" 2>/dev/null
[ -s "$LIBRO" ] || { echo "NO MEDIDO: $RUTA_LEDGER no devolvio nada (canal)"; exit 2; }

"$PY" -c '
import json, sys
sys.path.insert(0, "/srv/coinanalyze/repo")
from datetime import datetime, UTC
from app.signal_replay import canonical_json_hash, replay_summary_for_logic
from app.signal_replay import ReplayUnsupportedLogicVersion
from app.signal_ledger import classify_signal_observation, select_reference_price

ref = sys.argv[1].split("|")
simbolo, desde, esperadas, ruta = sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
camino_cuerpo, camino_origen, camino_libro = sys.argv[6], sys.argv[7], sys.argv[8]

crudo = open(camino_cuerpo).read()
try:
    d = json.loads(crudo)
except Exception as e:
    print(f"NO MEDIDO: {ruta} no devolvio JSON ({e}): {crudo[:80]!r}"); sys.exit(2)
if isinstance(d, dict) and "frames" not in d and set(d) <= {"detail"}:
    print(f"la capacidad no tiene API: {ruta} devuelve {d} en 140 ({esperadas} frames solo en {desde} de {simbolo})"); sys.exit(1)
if not isinstance(d, dict) or "frames" not in d:
    print(f"{ruta} responde pero no sirve los frames: sin clave frames"); sys.exit(1)
filas = d["frames"]
if d.get("truncated"):
    print(f"NO MEDIDO: {ruta} declara truncated=true"); sys.exit(2)
if d.get("count") is not None and d["count"] != len(filas):
    print(f"{ruta} declara count={d["count"]} y sirve {len(filas)} frames"); sys.exit(1)

CLAVES = ("frame_id","observation_id","context_version","context_as_of","context_hash",
          "logic_version","context","evidence")
faltan = sorted({k for k in CLAVES for f in filas if k not in f})
if faltan:
    print(f"{ruta} sirve frames sin las claves {faltan[:6]}"); sys.exit(1)
malformados = [f["observation_id"] for f in filas if not isinstance(f["context"], dict) or not isinstance(f["evidence"], dict)]
if malformados:
    print(f"{ruta} sirve context o evidence que no son objetos JSON: {malformados[:3]}"); sys.exit(1)

def casi(a, b, tol=1e-9):
    if a is None and b is None: return True
    if a is None or b is None: return False
    return abs(float(a) - float(b)) < tol

def hora(v):
    return None if v in (None, "") else datetime.fromisoformat(str(v)).astimezone(UTC)

origen = {}
for linea in open(camino_origen):
    partes = linea.rstrip("\n").split("|")
    if len(partes) < 6: continue
    origen[int(partes[0])] = partes[1:6]

libro = json.loads(open(camino_libro).read())
if not isinstance(libro, dict) or "observations" not in libro:
    print(f"NO MEDIDO: el ledger no sirve observations, no se puede cruzar"); sys.exit(2)
ledger = {o["observation_id"]: o for o in libro["observations"]}

fallos, replicados, anclados, cruzados, completos = [], 0, 0, 0, 0
CAMPOS = ("state","confidence","reason","long_score","short_score","evidence_coverage_pct")

for f in filas:
    oid = f["observation_id"]
    ctx, ev = f["context"], f["evidence"]

    # --- CAPA 1: el marco esta intacto -------------------------------------------------
    h = canonical_json_hash(ctx)
    if h != f["context_hash"]:
        fallos.append(f"frame {oid}: el context servido hashea {h[:12]} y la ruta declara {f["context_hash"][:12]}")
    o = origen.get(oid)
    if o is not None and h != o[0]:
        fallos.append(f"frame {oid}: el context servido hashea {h[:12]} y la BASE guarda {o[0][:12]}")

    # --- CAPA 2: la decision se reproduce ejecutando el nucleo real ---------------------
    try:
        rep = replay_summary_for_logic(f["logic_version"], ctx)
    except ReplayUnsupportedLogicVersion:
        print(f"NO MEDIDO: la fila {oid} declara logic_version={f["logic_version"]}, que este arbol no sabe replicar"); sys.exit(2)
    replicados += 1
    if canonical_json_hash(rep) != canonical_json_hash(ev):
        distintos = sorted({k for k in set(rep) | set(ev) if rep.get(k) != ev.get(k)})
        fallos.append(f"frame {oid}: replicar el context NO devuelve la evidence guardada, difieren {distintos[:4]}")
        continue

    # --- CAPA 2b: y contra el ledger, que es otra tabla y otro endpoint -----------------
    fila = ledger.get(oid)
    if fila is not None:
        cruzados += 1
        for c in CAMPOS:
            a, b = rep.get(c), fila.get(c)
            ok = casi(a, b) if isinstance(a, (int, float)) and not isinstance(a, bool) else a == b
            if not ok:
                fallos.append(f"frame {oid}: {c} replicado {a!r} y el ledger sirve {b!r}")
        ds, di, ac = classify_signal_observation(rep)
        if ds != fila.get("decision_status"): fallos.append(f"frame {oid}: decision_status {ds} != {fila.get("decision_status")}")
        if di != fila.get("direction"): fallos.append(f"frame {oid}: direction {di} != {fila.get("direction")}")
        if bool(ac) != bool(fila.get("actionable")): fallos.append(f"frame {oid}: actionable {ac} != {fila.get("actionable")}")
        ctx_dt = dict(ctx)
        if isinstance(ctx_dt.get("ohlcv_price_at"), str):
            ctx_dt["ohlcv_price_at"] = hora(ctx_dt["ohlcv_price_at"])
        px, fuente, cuando = select_reference_price(ctx_dt, rep)
        if not casi(px, fila.get("reference_price")): fallos.append(f"frame {oid}: reference_price {px} != {fila.get("reference_price")}")
        if fuente != fila.get("reference_price_source"): fallos.append(f"frame {oid}: reference_price_source {fuente!r} != {fila.get("reference_price_source")!r}")
        if cuando != hora(fila.get("reference_price_at")): fallos.append(f"frame {oid}: reference_price_at {cuando} != {fila.get("reference_price_at")}")

    # --- CAPA 3: los insumos contra ohlcv, no contra si mismos --------------------------
    if o is None:
        continue
    ref_px, first_open, last_close, bars = o[1], o[2], o[3], o[4]
    cobertura = ctx.get("price_move_15m_coverage")
    if ref_px != "":
        anclados += 1
        if not casi(ctx.get("ohlcv_price"), float(ref_px)):
            fallos.append(f"frame {oid}: ohlcv_price congelado {ctx.get("ohlcv_price")} y ohlcv dice {ref_px}")
    if bars != "":
        if int(bars) < int(ctx.get("bars_15m") or 0):
            fallos.append(f"frame {oid}: el frame vio {ctx.get("bars_15m")} velas y hoy ohlcv solo tiene {bars}: se perdieron velas")
        if cobertura == "complete":
            completos += 1
            if int(bars) != int(ctx.get("bars_15m") or -1):
                fallos.append(f"frame {oid}: declara completo con {ctx.get("bars_15m")} velas y ohlcv tiene {bars}")
            if not casi(ctx.get("first_px_15m"), float(first_open) if first_open else None):
                fallos.append(f"frame {oid}: first_px_15m {ctx.get("first_px_15m")} y el open de la primera vela es {first_open}")
            if not casi(ctx.get("last_px_15m"), float(last_close) if last_close else None):
                fallos.append(f"frame {oid}: last_px_15m {ctx.get("last_px_15m")} y el close de la ultima vela es {last_close}")

if fallos:
    print(f"{len(fallos)} comprobaciones fallan sobre {len(filas)} frames: " + " · ".join(fallos[:3])); sys.exit(1)
if replicados == 0:
    print(f"NO MEDIDO: la ventana {desde} de {simbolo} no trae ni un frame que replicar"); sys.exit(2)
if cruzados * 10 < len(filas) * 9:
    print(f"NO MEDIDO: solo {cruzados} de {len(filas)} frames tienen fila en el ledger; el cruce no cubre la ventana"); sys.exit(2)
if completos == 0:
    print(f"NO MEDIDO: ningun frame de la ventana declara price_move_15m_coverage=complete"); sys.exit(2)

agregados = [len(filas), len({f["observation_id"] for f in filas}),
             len({f["context_hash"] for f in filas}),
             len({f["context_version"] for f in filas}),
             sum(int(f["context"].get("bars_15m") or 0) for f in filas),
             sum(1 for f in filas if f["context"].get("price_move_15m_coverage") == "complete")]
NOMBRES = ("frames","observaciones distintas","hashes distintos","versiones de context",
           "suma bars_15m","frames con ventana completa")
descuadres = []
for nombre, esperado, obtenido in zip(NOMBRES, ref, agregados):
    e, o2 = esperado.strip(), str(obtenido)
    try: iguales = abs(float(e) - float(o2)) < 1e-6
    except ValueError: iguales = e == o2
    if not iguales: descuadres.append(f"{nombre} {o2} != {e}")
if descuadres:
    print(f"{len(descuadres)} de {len(NOMBRES)} conteos no cuadran: " + " · ".join(descuadres[:4])); sys.exit(1)
if len(filas) != esperadas:
    print(f"la ruta sirve {len(filas)} frames y la hora tiene {esperadas}"); sys.exit(1)

print(f"{replicados} decisiones REPLICADAS desde su context congelado y identicas a la evidence guardada + {cruzados} cruzadas contra el ledger en 12 campos + {anclados} insumos contra ohlcv y {completos} ventanas de 15 min recalculadas + {len(NOMBRES)} conteos: {simbolo} {desde}, {len(filas)} frames enteros. ABIERTO a proposito: libro, liquidaciones, OI y deltas del context, que este check no ancla")
' "$ref" "$simbolo" "$desde" "$esperadas" "$RUTA" "$CUERPO" "$ORIGEN" "$LIBRO"
exit $?
