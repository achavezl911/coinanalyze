#!/bin/bash
# K59  EL COMPONENTE DE MAS PESO DEL REGIMEN VOTA CERO DONDE NO HUBO MEDICION.
#
# compute_regime dice en su propio cuerpo "un componente ausente no vota cero, no vota" y
# renormaliza sobre lo medido. El componente whale pesa 30 de 100, el mayor de los cinco.
# Y para BTC vota SIEMPRE, y vota cero: whale_classification (metrics.py:66-70) devuelve
# 0.0 cuando la actividad no llega al umbral, no None, asi que optional_finite lo ve como
# un float finito, measured sale 100 en vez de 70 y el score queda en 0.7 EXACTO del que
# manda su propia regla. El esquema ya se abrio para poder decir no-lo-se
# -schema.sql:956-962 quita el NOT NULL citando "ausencia != cero"- y el productor nunca
# pasa por esa puerta.
#
# ES LA TERCERA VEZ DE LA MISMA FORMA. K58 era un 0 en la celda del walk-forward, K60 un 0
# en su titular, y este es un 0 en el numero de cabecera del producto. La diferencia es
# que este SE PINTA: /api/whale/delta lo pide el navegador 2946 veces contra 532 de
# nuestros curl.
#
# LO QUE NO DECIDE ESTE CHECK, y es de Alejandro: si 5 M USD EN UN SOLO TRADE es el umbral
# correcto para BTC (config.py, whale_threshold_usd; ws_collector.py:74 clasifica con >=).
# Bajarlo cambia lo que la palabra institucional afirma. Lo que NO es decision de producto
# es servir 0.0 donde no hubo medicion.
#
# EL ELEGIBLE SALE DE UNA FUENTE INDEPENDIENTE, que es la trampa 8 de la casa: NO se
# pregunta a metrics_snapshot si hubo actividad -eso seria juzgar al sujeto con su propia
# declaracion-, se mide en spot_trades_agg, que es donde el colector escribe los importes
# por bucket. Y con cotas SANAS, no aproximadas: inst_buy+inst_sell es no negativo, asi
# que la suma sobre el arco [inicio-24h, fin] ACOTA POR ARRIBA cualquier ventana de 24 h
# de las que ve un snapshot del arco, y la suma sobre la interseccion [fin-24h, inicio] la
# ACOTA POR ABAJO. Un simbolo cuyo umbral cae ENTRE las dos cotas no se juzga: se declara.
#
# LO QUE EXIGE
#   1 · EL PORTON. Si el productor no observo actividad por encima del umbral en NINGUNA
#       de las ventanas posibles -cota superior por debajo del umbral-, whale_intensity se
#       escribe NULL y no 0.0.
#   2 · CREDIBILIDAD, eslabon 6: el score guardado se REPLICA desde sus cinco entradas con
#       la funcion real del modulo. Sin esto el resto es una opinion sobre codigo leido.
#   CONTROL POSITIVO, obligatorio: un simbolo que SI tiene operaciones grandes -SOL las
#       tiene a diario- tiene que SEGUIR votando: whale_intensity no nula, alguna
#       distinta de cero, y su score replicandose igual. Un arreglo que anule el
#       componente siempre no se distingue de haberlo borrado.
#   NOMED si no queda ningun simbolo juzgable en alguno de los dos brazos.
#
# DE QUE ARBOL: datos de 140 (prodsql, solo lectura). Codigo del repo de 143. El espejo no
# sirve: no tiene productor corriendo y sus filas se paran en el 2026-08-13.
set -uo pipefail
B=/srv/coinanalyze/harness
REPO=/srv/coinanalyze/repo

PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || { echo "NO MEDIDO: falta el venv del repo en $PY"; exit 2; }

# 30 min y no mas: un despliegue deja filas viejas en la ventana y el check las juzga con
# la vara nueva, asi que sale ROJO hasta que envejecen. Con 30 min eso dura media hora como
# mucho y siguen entrando ~35 snapshots por simbolo, que sobran. Un rojo falso largo es lo
# que ensena a ignorar el que si lo es.
VENTANA='30 minutes'

filas=$(TODO=1 "$B/bin/prodsql" "
SELECT symbol, ts,
       cvd_spot_imbalance_24h, cvd_fut_imbalance_24h, oi_chg_24h_pct, fr_avg,
       long_liq_24h, short_liq_24h, whale_intensity, whale_label,
       regime_score, regime_label, regime_logic_version
FROM metrics_snapshot
WHERE ts >= now() - interval '$VENTANA'
ORDER BY ts
" 2>&1)
rc=$?
[ $rc -eq 0 ] && [ -n "$filas" ] || {
  echo "NO MEDIDO: 140 no devolvio snapshots (rc=$rc). $(printf '%s' "$filas" | head -1)"; exit 2; }

# cota SUPERIOR: arco entero.  cota INFERIOR: interseccion de todas las ventanas de 24 h.
cotas=$(TODO=1 "$B/bin/prodsql" "
WITH v AS (SELECT now() - interval '$VENTANA' AS ini, now() AS fin)
SELECT a.symbol,
       coalesce(sum(a.inst_buy_usd + a.inst_sell_usd)
                FILTER (WHERE a.ts >= v.ini - interval '24 hours'), 0) AS cota_alta,
       coalesce(sum(a.inst_buy_usd + a.inst_sell_usd)
                FILTER (WHERE a.ts >= v.fin - interval '24 hours' AND a.ts <= v.ini), 0) AS cota_baja
FROM spot_trades_agg a, v
WHERE a.ts >= v.ini - interval '24 hours'
GROUP BY a.symbol
" 2>&1)
[ -n "$cotas" ] || { echo "NO MEDIDO: spot_trades_agg no devolvio importes"; exit 2; }

printf '%s\n===COTAS===\n%s\n' "$filas" "$cotas" \
  | PYTHONPATH="$REPO" "$PY" -c '
import sys

sys.path.insert(0, "/srv/coinanalyze/repo")
from app.config import WHALE_THRESHOLD_MAP
from app.metrics import compute_regime

def num(s):
    return None if s in ("", "\\N") else float(s)

crudo = sys.stdin.read().split("===COTAS===")
if len(crudo) != 2:
    print("NO MEDIDO: no llegaron las dos consultas"); sys.exit(2)

cotas = {}
for l in crudo[1].splitlines():
    if not l.strip():
        continue
    p = l.split("|")
    if len(p) == 3:
        cotas[p[0]] = (float(p[1]), float(p[2]))

CAMPOS = ("cvd_spot_imbalance_24h", "cvd_fut_imbalance_24h", "oi_chg_24h_pct", "fr_avg",
          "long_liq_24h", "short_liq_24h", "whale_intensity")
filas = []
for l in crudo[0].splitlines():
    if not l.strip():
        continue
    p = l.split("|")
    if len(p) != 13:
        continue
    fila = {"symbol": p[0], "ts": p[1]}
    for i, campo in enumerate(CAMPOS):
        fila[campo] = num(p[2 + i])
    fila["whale_label"] = p[9] or None
    fila["regime_score"] = num(p[10])
    fila["regime_label"] = p[11] or None
    filas.append(fila)

if not filas:
    print("NO MEDIDO: cero snapshots en la ventana"); sys.exit(2)

# base del simbolo: metrics_snapshot usa BTCUSDT_PERP.A y spot_trades_agg usa BTC
def base(simbolo):
    return simbolo.split("USDT")[0]

fallos = []
sin_actividad, con_actividad, a_caballo = [], [], []
for simbolo in sorted({f["symbol"] for f in filas}):
    b = base(simbolo)
    umbral = WHALE_THRESHOLD_MAP.get(b)
    if umbral is None or b not in cotas:
        a_caballo.append("%s (sin umbral o sin importes)" % simbolo); continue
    alta, baja = cotas[b]
    if alta < umbral:
        sin_actividad.append((simbolo, b, alta, umbral))
    elif baja >= umbral:
        con_actividad.append((simbolo, b, baja, umbral))
    else:
        a_caballo.append("%s (cotas %.0f..%.0f alrededor de %.0f)" % (simbolo, baja, alta, umbral))

if not sin_actividad:
    print("NO MEDIDO: ningun simbolo esta claramente SIN actividad por encima de su "
          "umbral, que es el caso que este check juzga. A caballo: %s"
          % ("; ".join(a_caballo) or "ninguno")); sys.exit(2)
if not con_actividad:
    print("NO MEDIDO: ningun simbolo esta claramente CON actividad, asi que no hay "
          "control positivo. A caballo: %s" % ("; ".join(a_caballo) or "ninguno")); sys.exit(2)

# --- 1 · EL PORTON ------------------------------------------------------------------
for simbolo, b, alta, umbral in sin_actividad:
    suyas = [f for f in filas if f["symbol"] == simbolo]
    ceros = [f for f in suyas if f["whale_intensity"] is not None]
    if ceros:
        exactos = sum(1 for f in ceros if f["whale_intensity"] == 0.0)
        fallos.append("%s: %d de %d snapshots traen whale_intensity NO nula (%d de ellos "
                      "0.0 exacto) y spot_trades_agg da %.0f USD inst sobre el arco "
                      "entero, por debajo del umbral de %.0f. Es un cero servido donde no "
                      "hubo medicion" % (simbolo, len(ceros), len(suyas), exactos, alta, umbral))

# --- CONTROL POSITIVO: el que SI tiene actividad tiene que seguir votando -------------
for simbolo, b, baja, umbral in con_actividad:
    suyas = [f for f in filas if f["symbol"] == simbolo]
    nulas = [f for f in suyas if f["whale_intensity"] is None]
    if nulas:
        fallos.append("CONTROL POSITIVO ROTO: %s tiene %.0f USD inst garantizados en toda "
                      "ventana de 24 h (umbral %.0f) y aun asi %d de %d snapshots traen "
                      "whale_intensity nula" % (simbolo, baja, umbral, len(nulas), len(suyas)))
    elif not any(f["whale_intensity"] for f in suyas):
        fallos.append("CONTROL POSITIVO ROTO: %s tiene actividad garantizada y sus %d "
                      "snapshots traen whale_intensity 0.0 en TODOS: el componente esta "
                      "presente pero no vota nada" % (simbolo, len(suyas)))

# --- 2 · CREDIBILIDAD · el score se REPLICA desde sus cinco entradas ------------------
# HAY UNA PUERTA EXTERNA ANTES DE compute_regime y mi primer modelo no la tenia:
# metrics.py:588 devuelve (None, "Sin datos suficientes") sin renormalizar cuando falta
# una fuente de regimen o cuando las liquidaciones no estan MEDIDAS. Es deliberado -una
# perdida explicita no es una ausencia sana- y se nota en las entradas guardadas, porque
# cada fuente bloqueada deja su columna en NULL. Reproducirla es parte de replicar.
ENTRADAS_OBLIGATORIAS = ("cvd_spot_imbalance_24h", "cvd_fut_imbalance_24h",
                         "oi_chg_24h_pct", "fr_avg", "long_liq_24h", "short_liq_24h")

def replicar(f):
    if any(f[c] is None for c in ENTRADAS_OBLIGATORIAS):
        return None, "Sin datos suficientes"
    return compute_regime(f)

descuadres = []
for f in filas:
    score, etiqueta = replicar(f)
    guardado = f["regime_score"]
    if score is None or guardado is None:
        if score is not None or guardado is not None:
            descuadres.append((f["symbol"], f["ts"], score, guardado))
    elif abs(score - guardado) > 0.011:
        descuadres.append((f["symbol"], f["ts"], score, guardado))
if descuadres:
    s, ts, r, g = descuadres[0]
    fallos.append("%d de %d scores NO se replican desde sus cinco entradas con la funcion "
                  "real; el primero es %s en %s: recalculo %s contra %s guardado. Mientras "
                  "esto no cuadre, el resto del check no se puede creer"
                  % (len(descuadres), len(filas), s, ts, r, g))

if fallos:
    print("ROJO: " + fallos[0])
    for x in fallos[1:]:
        print("      " + x)
    sys.exit(1)

print("VERDE: %d snapshots, %d replicados desde sus cinco entradas. Sin actividad y por "
      "tanto SIN VOTO: %s. Con actividad y VOTANDO: %s.%s"
      % (len(filas), len(filas) - len(descuadres),
         ", ".join(s for s, _, _, _ in sin_actividad),
         ", ".join(s for s, _, _, _ in con_actividad),
         (" No juzgados: " + "; ".join(a_caballo)) if a_caballo else ""))
'
exit $?
