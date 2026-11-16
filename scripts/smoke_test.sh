#!/usr/bin/env bash
set -Eeuo pipefail
BASE_URL=${1:-http://127.0.0.1:8000}
DEPLOY_RESTART_EPOCH=${DEPLOY_RESTART_EPOCH:-}
REQUIRED_HEARTBEATS=${REQUIRED_HEARTBEATS:-}
REQUIRED_SYSTEMD_SERVICES=${REQUIRED_SYSTEMD_SERVICES:-}
CURL_HEADERS=()
COINALYZE_ENV_FILE=${COINALYZE_ENV_FILE:-/etc/coinalyze/coinalyze.env}
if [[ -f "$COINALYZE_ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$COINALYZE_ENV_FILE"
  set +a
fi
# smoke-contract: 2 (deploy-coinalyze lo exige antes de usar este fichero)
# Salida: 0 sano; 75 aun arrancando (motivo de arranque conocido: quien llama puede reintentar
# hasta su espera maxima); 86 fallo definitivo (no se reintenta); cualquier otro, un sondeo fallido.
# El token va en un fichero de cabeceras 0600 (curl -H @fichero), nunca en el argv de curl: el argv
# de un proceso lo lee cualquier usuario de la maquina.
HEADER_FILE=$(umask 077 && mktemp)
HEALTH_JSON=$(umask 077 && mktemp)
trap 'rm -f "$HEADER_FILE" "$HEALTH_JSON"' EXIT
if [[ -n "${API_INTERNAL_TOKEN:-}" && "$BASE_URL" == http://127.0.0.1:* ]]; then
  printf 'X-Internal-Token: %s\n' "$API_INTERNAL_TOKEN" >"$HEADER_FILE"
  CURL_HEADERS=(-H "@$HEADER_FILE")
fi
unset API_INTERNAL_TOKEN
# A collector can pass this check and still die while the HTTP probes below run: its
# heartbeat can stay inside the freshness window even after the process is gone. Reusing
# this function both before and after the probes closes that window instead of trusting
# a single point-in-time check taken before anything actually exercised the services.
require_active_services() {
  local service
  for service in $REQUIRED_SYSTEMD_SERVICES; do
    if systemctl is-failed --quiet "$service"; then
      echo "Required service is not active and healthy: $service (failed)" >&2
      return 86
    fi
    if ! systemctl is-active --quiet "$service"; then
      echo "Required service is not active and healthy: $service (not active yet)" >&2
      return 75
    fi
  done
  return 0
}

require_active_services || exit $?
curl --fail --silent --show-error "${CURL_HEADERS[@]}" "$BASE_URL/api/symbols" >/dev/null
curl --fail --silent --show-error "${CURL_HEADERS[@]}" "$BASE_URL/api/healthz" >"$HEALTH_JSON"
python3 - "$HEALTH_JSON" "$DEPLOY_RESTART_EPOCH" "$REQUIRED_HEARTBEATS" <<'PY_HEALTH'
import datetime
import json
import re
import sys

STARTING, DEFINITIVE = 75, 86
# Marcadores de ARRANQUE: el texto EXACTO que un colector escribe en su latido al arrancar, antes de su
# primer ciclo bueno. Si cambia en app/, cambia aqui: tests/test_smoke_arranque.py lo busca en el fuente.
STARTUP_MARKERS = frozenset({
    "collector starting; awaiting successful cycle",  # app/ingest.py:1078
    "scalp collector starting; awaiting stream confirmation",  # app/scalp_collector.py:630
})
# Un compuesto es «comp=estado:detalle» unido por «;» (app/db.py:490-494). El marcador tambien lleva «;»,
# asi que se parte por «;comp=estado:», no por «;».
COMPOSITE_PART = re.compile(r"(?:^|;)([A-Za-z0-9_]+)=(ok|degraded|error|missing):")


def fail(code: int, message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(code)


def parse_ts(value: object) -> datetime.datetime:
    return datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def startup_only(detail: str) -> bool:
    """El detalle es SOLO arranque: un marcador exacto, o un compuesto cuyas partes son todas «degraded» con un
    marcador exacto u «ok», con al menos una de arranque. Las partes «ok» se admiten porque ohlcv_1m late cada
    minuto y metrics_5m cada 300 s (app/ingest.py:1103-1126): durante minutos uno ya esta ok y el otro arranca."""
    if detail in STARTUP_MARKERS:
        return True
    parts = list(COMPOSITE_PART.finditer(detail))
    if not parts or parts[0].start() != 0:
        return False
    starting = False
    for index, part in enumerate(parts):
        end = parts[index + 1].start() if index + 1 < len(parts) else len(detail)
        if part.group(2) == "degraded" and detail[part.end():end] in STARTUP_MARKERS:
            starting = True
        elif part.group(2) != "ok":
            return False
    return starting


path, restart_epoch, required_raw = sys.argv[1:]
try:
    with open(path, encoding="utf-8") as handle:
        health = json.load(handle)
except (OSError, json.JSONDecodeError) as exc:
    fail(DEFINITIVE, f"healthz did not return valid JSON: {exc}")
deployed_at = None
if restart_epoch:
    try:
        deployed_at = datetime.datetime.fromtimestamp(float(restart_epoch), datetime.UTC)
    except (ValueError, OverflowError) as exc:
        fail(DEFINITIVE, f"invalid deploy restart epoch: {exc}")
services = {str(row.get("service")): row for row in health.get("services") or []}
status = health.get("status")
if status != "ok":
    # «degraded» solo se tolera por un motivo de ARRANQUE conocido: un latido gobernado que aun no ha
    # llegado (falta, o es de antes del reinicio), un colector que DESPUES del reinicio solo dice que arranca
    # («degraded» con un marcador de STARTUP_MARKERS, solo o en cada parte de arranque de un compuesto) o la
    # ingesta que aun no ha alcanzado a los simbolos. Cualquier otro no-ok posterior al reinicio es un fallo.
    informative = {str(r.get("service")) for r in health.get("informative_services") or []}
    starting: list[str] = [f"missing heartbeat: {s}" for s in health.get("missing_services") or []]
    for name, row in sorted(services.items()):
        if name in informative:
            continue
        try:
            updated_at = parse_ts(row.get("updated_at"))
        except ValueError:
            fail(DEFINITIVE, f"invalid heartbeat timestamp for {name}")
        if deployed_at is None or updated_at < deployed_at:
            if deployed_at is not None or row.get("status") != "ok":
                starting.append(f"awaiting first heartbeat since restart: {name}")
        elif row.get("status") == "degraded" and startup_only(str(row.get("detail") or "")):
            starting.append(f"collector starting since restart: {name}")
        elif row.get("status") != "ok":
            detail = str(row.get("detail") or "")[:200]
            fail(DEFINITIVE, f"healthz is {status!r}: {name} reported {row.get('status')!r} after the restart: {detail}")
    if health.get("missing_symbols") or any(float(r.get("lag_seconds") or 0) > 180.0 for r in health.get("symbols") or []):
        starting.append("ingest has not caught up with every symbol")
    if status != "degraded" or not starting:
        fail(DEFINITIVE, f"healthz is not ok: {status!r} and no known startup reason explains it")
    fail(STARTING, f"healthz is not ok: {status!r} (starting: {'; '.join(starting[:6])})")
if deployed_at is not None:
    for service in required_raw.split():
        row = services.get(service)
        if row is None:
            fail(STARTING, f"post-restart heartbeat missing: {service}")
        try:
            updated_at = parse_ts(row["updated_at"])
        except (KeyError, ValueError) as exc:
            fail(DEFINITIVE, f"invalid heartbeat timestamp for {service}: {exc}")
        if updated_at < deployed_at:
            fail(
                STARTING,
                f"heartbeat predates restart: {service} updated_at={updated_at.isoformat()} "
                f"restart={deployed_at.isoformat()}",
            )
PY_HEALTH
curl --fail --silent --show-error "${CURL_HEADERS[@]}" "$BASE_URL/api/ai/profiles" >/dev/null
# /metrics estuvo devolviendo 500 durante versiones sin que nadie lo notara,
# justamente porque el smoke test no lo cubria.
if [[ "${METRICS_ENABLED:-true}" == "true" ]]; then
  curl --fail --silent --show-error "${CURL_HEADERS[@]}" "$BASE_URL/metrics" >/dev/null
fi
SYMBOL=$(curl --fail --silent "${CURL_HEADERS[@]}" "$BASE_URL/api/symbols" \
  | sed -n 's/.*"symbol":"\([^"]*\)".*/\1/p' | head -n1)
if [[ -n "$SYMBOL" ]]; then
  for path in /api/dashboard/state /api/market-memory /api/scalp/summary /api/data-confidence /api/wyckoff /api/external-macro; do
    curl --fail --silent --show-error --get --data-urlencode "symbol=$SYMBOL" \
      "${CURL_HEADERS[@]}" "$BASE_URL$path" >/dev/null
  done
fi
# Required again, immediately before success: a collector that died mid-probe must not
# be masked by a still-fresh heartbeat or by probes that happened to succeed anyway.
require_active_services || exit $?
printf 'Smoke test OK: %s\n' "$BASE_URL"
