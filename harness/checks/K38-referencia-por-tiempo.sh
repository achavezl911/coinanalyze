#!/bin/bash
# K38  la barra de referencia se resuelve POR TIEMPO, no por posicion.
#
# oi_context.back() hace series[max(0, len-1-round(sec/cadencia))]
# (app/scalp_logic.py:2947), que solo acierta si la serie es contigua. Con un hueco la
# barra devuelta NO esta a `sec` segundos de la ultima, y las cinco ventanas de
# /api/oi-context (5m, 15m, 1h, 4h, 24h) heredan el error en sus DOS patas, la de OI y
# la de precio, que se indexan igual. Ese contexto se le manda al modelo
# (app/ai_context.py:779, app/analysis_prompt.py:21-23): un "cambio de 5m" que en
# realidad son 20m acaba dentro de un analisis firmado.
#
# EL CRITERIO NO ES "QUE NO HAYA HUECOS". Es que la cifra diga sobre que dos barras se
# calculo y que la distancia entre ellas sea EXACTAMENTE la que anuncia su etiqueta.
# Dos dientes:
#   1  toda cifra no nula viaja con su barra de referencia, y ultima - referencia = sec
#      al segundo. Una cifra null es respuesta VALIDA y no falla: es lo que toca cuando
#      la barra no esta. Si TODAS son null no se midio nada -> NOMED, no VERDE.
#   2  esas barras EXISTEN como filas en las tablas de 140. Sin este diente bastaria con
#      publicar ultima-sec como texto sin haber leido nunca esa barra.
#
# EL ANCLA ES LA ULTIMA BARRA Y NO now(). Medido el 2026-08-25T23:39Z contra 140:
#   prodsql "SELECT EXTRACT(EPOCH FROM (now()-max(ts))) FROM open_interest
#            WHERE symbol='BTCUSDT_PERP.A' AND interval='5min'"   ->  556.35
# open_interest 5min llega con ~9 min de retraso, asi que anclar en now()-300 daria la
# ULTIMA barra como referencia de 5m y el cambio saldria 0.000 % siempre. Anclando en la
# ultima barra, el intervalo es exactamente el de la etiqueta y la frescura ya la cuenta
# coverage (K03): el 2026-08-25T23:38Z la ventana de 5m traia open_interest_5min con
# expected_buckets=1 y observed_buckets=0.
set -uo pipefail
B=/srv/coinanalyze/harness; . "$B/env"
SIM=${K38_SIMBOLO:-BTCUSDT_PERP.A}

cuerpo=$(curl -sS -k --netrc-file "$NETRC" --max-time 20 "$API_PROD/api/oi-context?symbol=$SIM" 2>/dev/null)
[ -n "$cuerpo" ] || { echo "NO MEDIDO: /api/oi-context no respondio"; exit 2; }

salida=$(printf '%s' "$cuerpo" | python3 -c '
import sys, json
from datetime import datetime

VENTANAS = (("5m", 300), ("15m", 900), ("1h", 3600), ("4h", 14400), ("24h", 86400))
PATAS = (("oi", "oi_change_pct", "oi_reference_ts", "oi_latest_ts"),
         ("px", "price_change_pct", "price_reference_ts", "price_latest_ts"))

def di(linea):
    print(linea)

try:
    d = json.load(sys.stdin)
except Exception:
    di("VEREDICTO NOMED json ilegible"); raise SystemExit(0)
if not isinstance(d, dict):
    di("VEREDICTO NOMED la respuesta no es un objeto"); raise SystemExit(0)
if d.get("available") is not True:
    di("VEREDICTO NOMED available=%s" % d.get("available")); raise SystemExit(0)
w = d.get("windows")
if not isinstance(w, dict):
    di("VEREDICTO NOMED no hay windows"); raise SystemExit(0)

def hora(v):
    if not isinstance(v, str):
        return None
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        return None

fallos, cifras, nulas, refs = [], 0, 0, {"oi": [], "px": []}
for pata, k_chg, k_ref, k_ult in PATAS:
    ultima = hora(d.get(k_ult))
    for lab, sec in VENTANAS:
        e = w.get(lab)
        if not isinstance(e, dict):
            fallos.append("%s: la ventana no existe" % lab); continue
        chg = e.get(k_chg)
        if chg is None:
            nulas += 1
            if e.get(k_ref) is not None:
                fallos.append("%s/%s: cifra null con referencia %s" % (lab, pata, e.get(k_ref)))
            continue
        cifras += 1
        if ultima is None:
            fallos.append("%s/%s: no hay %s en el nivel de arriba" % (lab, pata, k_ult)); continue
        ref = hora(e.get(k_ref))
        if ref is None:
            fallos.append("%s/%s: cifra %s sin %s" % (lab, pata, chg, k_ref)); continue
        real = (ultima - ref).total_seconds()
        if real != sec:
            fallos.append("%s/%s: dice %ds y mide %.0fs" % (lab, pata, sec, real)); continue
        refs[pata].append(ref.isoformat())

if cifras == 0:
    di("VEREDICTO NOMED las 10 cifras son null: no hay nada que comprobar"); raise SystemExit(0)
if fallos:
    di("VEREDICTO FALLA %d de %d cifras mal ancladas: %s" % (len(fallos), cifras, "; ".join(fallos[:3])))
    raise SystemExit(0)
di("VEREDICTO OK %d cifras ancladas al segundo, %d null declaradas" % (cifras, nulas))
for pata in ("oi", "px"):
    unicos = sorted(set(refs[pata]))
    di("IN %s %d %s" % (pata, len(unicos), ",".join("'"'"'%s'"'"'" % t for t in unicos)))
' 2>/dev/null)

veredicto=$(printf '%s' "$salida" | sed -n 's/^VEREDICTO //p')
case "$veredicto" in
  NOMED*) echo "NO MEDIDO: ${veredicto#NOMED }"; exit 2 ;;
  FALLA*) echo "la referencia no se resuelve por tiempo: ${veredicto#FALLA }"; exit 1 ;;
  OK*) ;;
  *) echo "NO MEDIDO: sin veredicto"; exit 2 ;;
esac

# Diente 2: las barras citadas existen en 140.
comprobar() {  # $1 pata  $2 tabla  $3 interval
  local linea n lista vistas
  linea=$(printf '%s' "$salida" | sed -n "s/^IN $1 //p")
  n=${linea%% *}; lista=${linea#* }
  [ -n "${n:-}" ] && [ "$n" -gt 0 ] 2>/dev/null || { echo 0; return; }
  vistas=$("$B/bin/prodsql" "SELECT count(DISTINCT ts) FROM $2 WHERE symbol='$SIM' AND interval='$3' AND ts IN ($lista)" 2>/dev/null | tr -d ' \n')
  case "$vistas" in ''|*[!0-9]*) echo "NOSE"; return ;; esac
  [ "$vistas" = "$n" ] && echo 0 || echo "$1:$vistas/$n"
}
falta_oi=$(comprobar oi open_interest 5min)
falta_px=$(comprobar px ohlcv 1min)
case "$falta_oi$falta_px" in
  *NOSE*) echo "NO MEDIDO: no se pudo contar las barras citadas en 140"; exit 2 ;;
esac
if [ "$falta_oi" != 0 ] || [ "$falta_px" != 0 ]; then
  echo "hay referencias que no existen como fila en 140: $falta_oi $falta_px"; exit 1
fi

echo "${veredicto#OK }, y todas existen como fila en 140"
exit 0
