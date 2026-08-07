#!/usr/bin/env bash
set -Eeuo pipefail
BASE_URL=${1:-http://127.0.0.1:8000}
CURL_HEADERS=()
if [[ -f /etc/coinalyze/coinalyze.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source /etc/coinalyze/coinalyze.env
  set +a
fi
if [[ -n "${API_INTERNAL_TOKEN:-}" && "$BASE_URL" == http://127.0.0.1:* ]]; then
  CURL_HEADERS=(-H "X-Internal-Token: ${API_INTERNAL_TOKEN}")
fi
curl --fail --silent --show-error "${CURL_HEADERS[@]}" "$BASE_URL/api/symbols" >/dev/null
curl --fail --silent --show-error "${CURL_HEADERS[@]}" "$BASE_URL/api/healthz" >/dev/null
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
