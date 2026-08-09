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
if [[ -n "${API_INTERNAL_TOKEN:-}" && "$BASE_URL" == http://127.0.0.1:* ]]; then
  CURL_HEADERS=(-H "X-Internal-Token: ${API_INTERNAL_TOKEN}")
fi
for service in $REQUIRED_SYSTEMD_SERVICES; do
  if systemctl is-failed --quiet "$service" || ! systemctl is-active --quiet "$service"; then
    echo "Required service is not active and healthy: $service" >&2
    exit 1
  fi
done
curl --fail --silent --show-error "${CURL_HEADERS[@]}" "$BASE_URL/api/symbols" >/dev/null
HEALTH_JSON=$(mktemp)
trap 'rm -f "$HEALTH_JSON"' EXIT
curl --fail --silent --show-error "${CURL_HEADERS[@]}" "$BASE_URL/api/healthz" >"$HEALTH_JSON"
python3 - "$HEALTH_JSON" "$DEPLOY_RESTART_EPOCH" "$REQUIRED_HEARTBEATS" <<'PY_HEALTH'
import datetime
import json
import sys

path, restart_epoch, required_raw = sys.argv[1:]
try:
    with open(path, encoding="utf-8") as handle:
        health = json.load(handle)
except (OSError, json.JSONDecodeError) as exc:
    raise SystemExit(f"healthz did not return valid JSON: {exc}")
if health.get("status") != "ok":
    raise SystemExit(f"healthz is not ok: {health.get('status')!r}")
if restart_epoch:
    try:
        deployed_at = datetime.datetime.fromtimestamp(float(restart_epoch), datetime.UTC)
    except (ValueError, OverflowError) as exc:
        raise SystemExit(f"invalid deploy restart epoch: {exc}")
    services = {str(row.get("service")): row for row in health.get("services", [])}
    for service in required_raw.split():
        row = services.get(service)
        if row is None:
            raise SystemExit(f"post-restart heartbeat missing: {service}")
        try:
            updated_at = datetime.datetime.fromisoformat(
                str(row["updated_at"]).replace("Z", "+00:00")
            )
        except (KeyError, ValueError) as exc:
            raise SystemExit(f"invalid heartbeat timestamp for {service}: {exc}")
        if updated_at < deployed_at:
            raise SystemExit(
                f"heartbeat predates restart: {service} updated_at={updated_at.isoformat()} "
                f"restart={deployed_at.isoformat()}"
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
printf 'Smoke test OK: %s\n' "$BASE_URL"
