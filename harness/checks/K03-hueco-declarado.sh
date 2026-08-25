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
SERIE="/api/ohlcv /api/oi /api/liquidations /api/whale/delta /api/cvd /api/cvd/spot /api/funding-context /api/oi-context"
SIM=BTCUSDT_PERP.A

# curl directo y NO bin/api: bin/api pasa por _corta, que trunca a 8 KB y parte el
# JSON por la mitad. Con el, seis de los ocho endpoints daban "sin_json" y el check
# habria estado ROJO por un motivo que no es el defecto.
pide() { curl -sS -k --netrc-file "$NETRC" --max-time 25 "$API_PROD$1" 2>/dev/null; }

vivo=$(pide /api/healthz | head -c 40)
[ -n "$vivo" ] || { echo "NO MEDIDO: la API no responde"; exit 2; }

# Un bloque de hueco de verdad: una clave que lo nombre, y dentro ventana y estado.
tiene_bloque() {
  printf '%s' "$1" | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    print("nojson"); raise SystemExit(0)
def busca(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if any(t in k.lower() for t in ("data_gap", "gaps", "gap_windows", "coverage_windows")):
                texto = json.dumps(v).lower()
                if ("start" in texto or "from" in texto) and "status" in texto:
                    return "relleno" if v not in (None, [], {}) else "vacio"
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

# (2) /api/daily es el UNICO que acepta ventana historica. El 2026-08-14 hay un
# data_gap de ohlcv_1min de 10:47 a 12:13 en los tres simbolos: ahi el bloque tiene
# que venir RELLENO, no solo existir.
cuerpo=$(pide "/api/daily?symbol=$SIM&through_session_date=2026-08-15&days=3")
case "$(tiene_bloque "$cuerpo")" in
  relleno) ;;
  vacio)   fallos="$fallos; /api/daily declara el bloque pero viene VACIO sobre un hueco conocido del 2026-08-14" ;;
  *)       fallos="$fallos; /api/daily no declara el hueco conocido del 2026-08-14" ;;
esac

if [ -n "${fallos# }" ]; then
  n=$(printf '%s' "$fallos" | grep -o 'sin_bloque_de_hueco' | wc -l)
  otros=$(printf '%s' "$fallos" | tr ';' '\n' | grep -v 'sin_bloque_de_hueco' | tr -d '\n' | sed 's/^ *//')
  echo "$n de 8 endpoints de serie sin bloque de hueco; ${otros:-sin mas}" | cut -c1-200
  exit 1
fi
echo "los 9 endpoints de serie declaran el hueco con ventana y estado"
