#!/bin/bash
# K03  el hueco no se puede inferir de los nulos: hay que declararlo, con ventana y
# con estado, y distinguiendo 'unresolved' de 'unrecoverable' y de "el mercado no
# cotizo". Hoy data_gap tiene 484 filas y NO las devuelve ningun endpoint.
#
# Lo que devuelven hoy, medido el 2026-08-25, es material para ADIVINAR:
#   /api/ohlcv  da sample_count, expected_count, is_complete y coverage_pct por barra
#   /api/daily  da un coverage_note que es PROSA ESTATICA sobre que significa NULL,
#               mas contadores por fila (futures_ohlcv_minutes vs
#               session_expected_minutes). Ninguno dice "de X a Y falto, y por que".
#
# OJO · EL CRITERIO DE LA COLA NO ERA EJECUTABLE. Decia "pidiendo un rango que
# contiene un data_gap conocido", y NINGUNO de los 9 endpoints de serie acepta un
# rango: siete toman symbol/interval/limit -o sea las N barras mas recientes- y solo
# /api/daily acepta through_session_date. No se puede pedir el hueco del 2026-08-14.
# Asi que se mide lo que si se puede: (1) que la respuesta traiga un bloque de hueco
# con ventana y estado, y (2) en el unico endpoint que acepta ventana historica, que
# ese bloque venga RELLENO cuando el rango contiene un hueco conocido. Sin (2) el
# check aceptaria un campo que existe y siempre viene vacio.
set -uo pipefail
B=/srv/coinanalyze/harness; . "$B/env"
# DOS FAMILIAS, y la distincion es del 2026-08-25. Los ocho de antes no se pedian lo
# mismo porque no devuelven lo mismo:
#
#   SERIE     devuelve filas. Se le exige el bloque de hueco con ventana y estado.
#   AGREGADO  devuelve escalares CALCULADOS SOBRE UNA SERIE. A este se le exige otra
#             cosa, y mas dura: que declare la COMPLETITUD DE LA VENTANA que agrego.
#
# Por que mas dura. history_avg_pct{8h,24h,7d} de /api/funding-context es un promedio
# sobre filas de funding_rate; windows{5m,15m,1h,4h,24h} de /api/oi-context es un
# cambio calculado sobre open_interest. Si esa ventana tiene huecos, el escalar sale de
# datos incompletos y no lo dice. Eso es PEOR que una serie con huecos: la serie ensena
# sus agujeros y el promedio los esconde detras de un numero con decimales. Un hueco
# que se puede ver es un hueco; un hueco promediado es una cifra falsa.
#
# EL CONTRATO que se exige aqui, y se escribe entero porque K34 va a reabrirlo:
#   "coverage": {
#      "<etiqueta de ventana>": {
#          "window_start": "...", "window_end": "...",
#          "expected_buckets": N, "observed_buckets": M, "complete": bool
#      }, ...
#   }
# K34 (BLOQUE 10 de COLA.md) pedira anadir a cada entrada su nivel de evidencia de la
# taxonomia del par.17 (LIVE_OBSERVATION, HISTORICAL, BACKTEST, ...). Es EL MISMO
# CONTRATO DE RESPUESTA, asi que se deja el hueco previsto y no se abre dos veces.
SERIE="/api/ohlcv /api/oi /api/liquidations /api/whale/delta /api/cvd /api/cvd/spot"
AGREGADO="/api/funding-context /api/oi-context"
SIM=BTCUSDT_PERP.A

# curl directo y NO bin/api: bin/api pasa por _corta, que trunca a 8 KB y parte el
# JSON por la mitad. Con el, seis de los ocho endpoints daban "sin_json" y el check
# habria estado ROJO por un motivo que no es el defecto.
pide() { curl -sS -k --netrc-file "$NETRC" --max-time 25 "$API_PROD$1" 2>/dev/null; }

vivo=$(pide /api/healthz | head -c 40)
[ -n "$vivo" ] || { echo "NO MEDIDO: la API no responde"; exit 2; }

# Un bloque de hueco de verdad: una clave que lo nombre, y dentro ventana y estado.
#
# QUE CUENTA COMO "RELLENO", corregido el 2026-08-25 antes de implementar nada. La
# version anterior daba por relleno cualquier valor que no fuera None/[]/{} , y con eso
# la comprobacion (2) -la unica que impide un campo que existe y siempre viene vacio- se
# volvia hueca en cuanto el bloque fuera un objeto: un dict con la ventana dentro nunca
# esta vacio, asi que (2) habria pasado sola. Relleno = hay AL MENOS UNA ENTRADA DE
# HUECO, o sea un elemento de lista que trae su propia ventana y su propio estado. Es
# mas estricto que antes, no mas laxo: sigue siendo ROJO donde lo era.
tiene_bloque() {
  printf '%s' "$1" | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    print("nojson"); raise SystemExit(0)
def entradas(v):
    if isinstance(v, list):
        return [x for x in v if isinstance(x, dict)
                and any(k in x for k in ("start", "start_ts", "from", "window_start"))
                and "status" in x]
    if isinstance(v, dict):
        total = []
        for w in v.values():
            total += entradas(w)
        return total
    return []
def busca(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if any(t in k.lower() for t in ("data_gap", "gaps", "gap_windows", "coverage_windows")):
                texto = json.dumps(v).lower()
                if ("start" in texto or "from" in texto) and "status" in texto:
                    return "relleno" if entradas(v) else "vacio"
                return "incompleto"
            r = busca(v)
            if r: return r
    elif isinstance(o, list):
        for x in o[:5]:
            r = busca(x)
            if r: return r
    return ""
print(busca(d) or "ausente")
' 2>/dev/null
}

# Un agregado honrado: coverage con al menos una ventana, y cada ventana con sus dos
# cuentas y sus dos limites. Se comprueban ademas expected>0 y 0<=observed<=expected,
# que no prueba que la cifra sea derivada pero descarta el relleno perezoso.
declara_completitud() {
  printf '%s' "$1" | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    print("nojson"); raise SystemExit(0)
cov = d.get("coverage") if isinstance(d, dict) else None
if not isinstance(cov, dict) or not cov:
    print("ausente"); raise SystemExit(0)
for etiqueta, v in cov.items():
    if not isinstance(v, dict):
        print("incompleto"); raise SystemExit(0)
    esp, obs = v.get("expected_buckets"), v.get("observed_buckets")
    if not isinstance(esp, int) or not isinstance(obs, int):
        print("incompleto"); raise SystemExit(0)
    if not v.get("window_start") or not v.get("window_end"):
        print("incompleto"); raise SystemExit(0)
    if esp <= 0 or obs < 0 or obs > esp:
        print("absurdo"); raise SystemExit(0)
print("ok")
' 2>/dev/null
}

fallos=""
for ruta in $SERIE; do
  cuerpo=$(pide "$ruta?symbol=$SIM")
  case "$(tiene_bloque "$cuerpo")" in
    relleno|vacio) ;;
    incompleto) fallos="$fallos $ruta(bloque_sin_ventana_o_estado)" ;;
    nojson)     fallos="$fallos $ruta(sin_json)" ;;
    *)          fallos="$fallos $ruta(sin_bloque_de_hueco)" ;;
  esac
done

for ruta in $AGREGADO; do
  cuerpo=$(pide "$ruta?symbol=$SIM")
  case "$(declara_completitud "$cuerpo")" in
    ok) ;;
    incompleto) fallos="$fallos $ruta(coverage_sin_cuentas_o_sin_ventana)" ;;
    absurdo)    fallos="$fallos $ruta(coverage_con_cuentas_imposibles)" ;;
    nojson)     fallos="$fallos $ruta(sin_json)" ;;
    *)          fallos="$fallos $ruta(agregado_sin_declarar_completitud)" ;;
  esac
done

# (2) /api/daily es el UNICO que acepta ventana historica. El 2026-08-14 hay un
# data_gap de ohlcv_1min de 16:47 a 18:13 UTC (86 minutos) en los tres simbolos: ahi el
# bloque tiene que venir RELLENO, no solo existir. La sesion de psql de 140 responde en
# CST, asi que ese mismo hueco se lee "10:47 a 12:13" si no se pide UTC explicito; es la
# misma trampa que dio 7.99 en vez de 7.74 en K37. Se comprueba con:
#   prodsql "SELECT min(start_ts) AT TIME ZONE 'UTC', max(end_ts) AT TIME ZONE 'UTC',
#            count(*) FROM data_gap WHERE symbol='BTCUSDT_PERP.A' AND feed='ohlcv_1min'
#            AND start_ts >= '2026-08-14T00:00:00Z' AND start_ts < '2026-08-15T00:00:00Z'"
cuerpo=$(pide "/api/daily?symbol=$SIM&through_session_date=2026-08-15&days=3")
case "$(tiene_bloque "$cuerpo")" in
  relleno) ;;
  vacio)   fallos="$fallos; /api/daily declara el bloque pero viene VACIO sobre un hueco conocido del 2026-08-14" ;;
  *)       fallos="$fallos; /api/daily no declara el hueco conocido del 2026-08-14" ;;
esac

if [ -n "${fallos# }" ]; then
  n=$(printf '%s' "$fallos" | grep -o 'sin_bloque_de_hueco' | wc -l)
  m=$(printf '%s' "$fallos" | grep -o 'agregado_sin_declarar_completitud' | wc -l)
  otros=$(printf '%s' "$fallos" | tr ';' '\n' \
          | grep -v 'sin_bloque_de_hueco\|agregado_sin_declarar_completitud' \
          | tr -d '\n' | sed 's/^ *//')
  echo "$n de 6 de serie sin bloque de hueco y $m de 2 agregados sin declarar completitud; ${otros:-sin mas}" \
    | cut -c1-200
  exit 1
fi
echo "los 6 de serie declaran el hueco y los 2 agregados declaran su completitud"
