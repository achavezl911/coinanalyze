#!/bin/bash
# K105 · EL REGISTRO ANTES DEL RESULTADO · campana 135 (E1 de las entradas)
#
# QUE JUZGA. El registro de hipotesis de entrada (entrada_reglamento, entrada_registro,
# entrada_latido): que lo que se apunta ANTES de saber como acaba sea lo que el reglamento del
# release dice, append-only de verdad, con una foto que baste y sin mirar el futuro. Los seis
# brazos (a-f) los juzga harness/checks/K105-registro.py; este guion solo REUNE los datos.
#
# POR QUE ASI.
#   b  se juzga por CATALOGO (pg_trigger + pg_proc): el canal de produccion es de solo lectura, y
#      un UPDATE de prueba lo rechazaria la SESION (25006), no el disparador. El intento real va en
#      la base desechable de K105-control.bash, que comprueba que el error es el del disparador.
#   c,d con cero DISPARADOS y SOMBRAS en la ventana salen NO MEDIDO, nunca VERDE (A54).
#   a  el arbol trae el registro y produccion no: ROJO «FALTA DESPLEGAR», que es su estado correcto
#      hasta el despliegue (el precedente de K101 con el sobre).
#
# SUJETOS. K105_SUJETO=produccion (por defecto: prodsql + prod sobre 140), espejo (espejosql; el
# release es el arbol), o local (K105_BASE = DSN de psql, K105_RELEASE = directorio con
# config/entradas/, K105_RETENCION_DIAS). Solo lee: ninguna rama escribe en ninguna base.
#
# rc: 0 VERDE · 1 ROJO · 2 NO MEDIDO.
set -u

REPO=${K105_REPO:-/srv/coinanalyze/repo}
B=${K105_HARNESS:-/srv/coinanalyze/harness}
PY=${K105_PY:-$REPO/.venv/bin/python}
SUJETO=${K105_SUJETO:-produccion}
VENTANA=${K105_VENTANA_DIAS:-7}
AYUDANTE="$REPO/harness/checks/K105-registro.py"
[ -r "$AYUDANTE" ] || { echo "NO MEDIDO: no encuentro $AYUDANTE"; exit 2; }
[ -x "$PY" ] || { echo "NO MEDIDO: sin python del arbol en $PY"; exit 2; }
case "$VENTANA" in ''|*[!0-9]*) echo "NO MEDIDO: K105_VENTANA_DIAS no es un entero"; exit 2 ;; esac

D=$(mktemp -d) || { echo "NO MEDIDO: sin directorio temporal"; exit 2; }
trap 'rm -rf "$D"' EXIT
printf '%s\n' "$VENTANA" > "$D/ventana_dias"

consulta() {
  case "$SUJETO" in
    produccion) TODO=1 "$B/bin/prodsql" "$1" ;;
    espejo)     TODO=1 "$B/bin/espejosql" "$1" ;;
    local)      PGOPTIONS='-c timezone=UTC -c default_transaction_read_only=on' \
                  psql "$K105_BASE" -X -A -t -F'|' -q -v ON_ERROR_STOP=1 -c "$1" ;;
  esac
}

case "$SUJETO" in
  produccion) NOMBRE="produccion" ;;
  espejo)     NOMBRE="espejo" ;;
  local)
    [ -n "${K105_BASE:-}" ] && [ -n "${K105_RELEASE:-}" ] \
      || { echo "NO MEDIDO: K105_SUJETO=local pide K105_BASE y K105_RELEASE"; exit 2; }
    base=${K105_BASE%%\?*}
    NOMBRE="local:${base##*/}" ;;
  *) echo "NO MEDIDO: K105_SUJETO=$SUJETO desconocido (produccion | espejo | local)"; exit 2 ;;
esac
printf '%s\n' "$NOMBRE" > "$D/sujeto"

vivo=$(consulta "SELECT 'ok_k105'" 2>/dev/null)
case "$vivo" in *ok_k105*) ;; *) echo "NO MEDIDO: la base de $NOMBRE no contesta"; exit 2 ;; esac

# --- el reglamento y el codigo DEL RELEASE (no del arbol) ------------------------------------
case "$SUJETO" in
  produccion)
    TODO=1 "$B/bin/prod" "cat /opt/coinalyze/current/config/entradas/reglamento.json" \
      > "$D/reglamento.json" 2>/dev/null
    TODO=1 "$B/bin/prod" "cat /opt/coinalyze/current/config/entradas/codigo.json" \
      > "$D/codigo.json" 2>/dev/null ;;
  espejo)
    cp "$REPO/config/entradas/reglamento.json" "$D/reglamento.json" 2>/dev/null
    cp "$REPO/config/entradas/codigo.json" "$D/codigo.json" 2>/dev/null ;;
  local)
    cp "$K105_RELEASE/config/entradas/reglamento.json" "$D/reglamento.json" 2>/dev/null
    cp "$K105_RELEASE/config/entradas/codigo.json" "$D/codigo.json" 2>/dev/null ;;
esac
for f in reglamento.json codigo.json; do
  head -c 1 "$D/$f" 2>/dev/null | grep -q '{' || : > "$D/$f"
done

tabla=$(consulta "SELECT to_regclass('entrada_registro') IS NOT NULL AND to_regclass('entrada_reglamento') IS NOT NULL AND to_regclass('entrada_latido') IS NOT NULL" 2>/dev/null)
if [ "$tabla" != "t" ]; then
  if [ -s "$REPO/config/entradas/reglamento.json" ]; then
    echo "ROJO  FALTA DESPLEGAR: el arbol trae el registro de entradas y $NOMBRE no tiene sus tablas"
  else
    echo "ROJO  $NOMBRE no tiene el registro de entradas y el arbol tampoco lo trae"
  fi
  echo "  a reglamento   ROJO · sin entrada_reglamento en $NOMBRE"
  echo "  b append-only  ROJO · sin tablas que juzgar por catalogo"
  echo "  e uno_vivo     ROJO · sin entrada_registro"
  echo "  f calendario   ROJO · sin registro al que aplicarlo"
  exit 1
fi

# --- lo que hay en la base, como JSON ---------------------------------------------------------
consulta "SELECT coalesce(json_agg(json_build_object('etiqueta', etiqueta, 'bloque', bloque, 'huella', huella, 'contenido', contenido::text) ORDER BY reglamento_id), '[]') FROM entrada_reglamento" > "$D/registradas.json" \
  || { echo "NO MEDIDO: no se pudo leer entrada_reglamento de $NOMBRE"; exit 2; }
consulta "SELECT coalesce(json_agg(json_build_object('tabla', c.relname, 'nombre', t.tgname, 'activo', t.tgenabled, 'tipo', t.tgtype, 'funcion', p.proname, 'fuente', p.prosrc)), '[]') FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid JOIN pg_proc p ON p.oid = t.tgfoid WHERE c.oid IN (to_regclass('entrada_reglamento'), to_regclass('entrada_registro'), to_regclass('entrada_latido')) AND NOT t.tgisinternal" > "$D/disparadores.json" \
  || { echo "NO MEDIDO: no se pudo leer el catalogo de disparadores de $NOMBRE"; exit 2; }
consulta "SELECT coalesce(json_agg(json_build_object('registro_id', registro_id, 'estado', estado, 'motivo', motivo, 'registered_at', registered_at, 'vela_cierre', vela_cierre, 'retraso_s', retraso_s, 'tope_retraso_s', tope_retraso_s, 'huella_foto', huella_foto, 'symbol', symbol, 'foto', foto::text) ORDER BY registro_id), '[]') FROM entrada_registro WHERE estado IN ('DISPARADO', 'SOMBRA') AND registered_at >= now() - make_interval(days => $VENTANA)" > "$D/filas.json" \
  || { echo "NO MEDIDO: no se pudo leer entrada_registro de $NOMBRE"; exit 2; }
consulta "SELECT coalesce(json_agg(json_build_object('version', version, 'symbol', symbol, 'familia', familia, 'perfil', perfil, 'lado', lado, 'clave', clave, 'episodio', episodio, 'estado', estado, 'vela_cierre', vela_cierre, 'caduca_en', caduca_en)), '[]') FROM entrada_registro WHERE estado = 'DISPARADO'" > "$D/vivos.json" \
  || { echo "NO MEDIDO: no se pudo leer los DISPARADOS de $NOMBRE"; exit 2; }
consulta "SELECT coalesce(json_agg(json_build_object('version', version, 'symbol', symbol, 'familia', familia, 'perfil', perfil, 'lado', lado, 'clave', clave, 'episodio', episodio, 'estado', estado, 'vela_cierre', vela_cierre, 'caduca_en', NULL)), '[]') FROM (SELECT DISTINCT ON (episodio) * FROM entrada_registro ORDER BY episodio, vela_cierre DESC, registro_id DESC) u WHERE estado = 'VIGILANDO'" > "$D/abiertos.json" \
  || { echo "NO MEDIDO: no se pudo leer los VIGILANDO de $NOMBRE"; exit 2; }
consulta "SELECT coalesce(json_agg(DISTINCT codigo_version), '[]') FROM entrada_registro" > "$D/codigos_usados.json" \
  || { echo "NO MEDIDO: no se pudo leer las versiones de codigo de $NOMBRE"; exit 2; }
consulta "SELECT to_char(clock_timestamp() AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"')" > "$D/ahora" \
  || { echo "NO MEDIDO: sin el reloj de $NOMBRE"; exit 2; }

# d, como DATO: las velas de cada foto, contra las asentadas (pasados los 42 min de signal_outcomes)
"$PY" - "$D" > "$D/velas.sql" <<'PY'
import json, sys
from datetime import datetime, timedelta, timezone
d = sys.argv[1]
filas = json.load(open(f"{d}/filas.json"))
tuplas = []
for f in filas:
    foto = json.loads(f["foto"])
    reg = datetime.fromisoformat(str(f["registered_at"]).replace("Z", "+00:00"))
    for v in (foto.get("episodio") or {}).get("velas") or []:
        if v.get("minutos") and v.get("minutos") == v.get("esperados") and len(tuplas) < 400:
            tuplas.append((f["symbol"], v["inicio"], v["fin"], v["open"], v["high"], v["low"], v["close"]))
if not tuplas:
    print("SELECT json_build_object('comparadas', 0, 'difieren', 0)")
else:
    valores = ",".join(f"('{s}', '{i}'::timestamptz, '{e}'::timestamptz, {o}, {h}, {l}, {c})" for s, i, e, o, h, l, c in tuplas)
    print("WITH f(symbol, ini, fin, o, h, l, c) AS (VALUES " + valores + "), "
          "a AS (SELECT f.*, (SELECT (array_agg(open ORDER BY ts))[1] FROM ohlcv x WHERE x.symbol = f.symbol AND x.interval = '1min' AND x.ts >= f.ini AND x.ts < f.fin) AS ao, "
          "(SELECT max(high) FROM ohlcv x WHERE x.symbol = f.symbol AND x.interval = '1min' AND x.ts >= f.ini AND x.ts < f.fin) AS ah, "
          "(SELECT min(low) FROM ohlcv x WHERE x.symbol = f.symbol AND x.interval = '1min' AND x.ts >= f.ini AND x.ts < f.fin) AS al, "
          "(SELECT (array_agg(close ORDER BY ts DESC))[1] FROM ohlcv x WHERE x.symbol = f.symbol AND x.interval = '1min' AND x.ts >= f.ini AND x.ts < f.fin) AS ac FROM f "
          "WHERE f.fin <= now() - interval '42 minutes') "
          "SELECT json_build_object('comparadas', count(*), 'difieren', count(*) FILTER (WHERE abs(ao - o) > 1e-9 OR abs(ah - h) > 1e-9 OR abs(al - l) > 1e-9 OR abs(ac - c) > 1e-9 OR ao IS NULL)) FROM a")
PY
consulta "$(cat "$D/velas.sql")" > "$D/velas.json" 2>/dev/null || echo '{"comparadas": 0, "difieren": 0}' > "$D/velas.json"

# f: la retencion del ohlcv 1min de 140, como la leen K104 y K67 (env de 140; si no esta, el defecto)
case "$SUJETO" in
  produccion)
    linea=$("$B/bin/prod" "grep -hE '^HARD_DATA_RETENTION_DAYS=' /etc/coinalyze/coinalyze.env" 2>/dev/null | tail -1)
    valor=${linea#*=}
    if [ -z "$linea" ]; then
      defecto=$("$B/bin/prod" "grep -hE '^ *HARD_DATA_RETENTION_DAYS *:' /opt/coinalyze/current/app/config.py" 2>/dev/null | grep -oE 'default=[0-9]+' | head -1)
      valor=${defecto#default=}
    fi ;;
  *) valor=${K105_RETENCION_DIAS:-} ;;
esac
printf '%s\n' "$(printf '%s' "$valor" | tr -dc '0-9')" > "$D/retencion"

"$PY" "$AYUDANTE" "$D" "$REPO"
