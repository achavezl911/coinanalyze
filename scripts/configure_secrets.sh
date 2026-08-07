#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

ENV_DIR="/etc/coinalyze"
ENV_FILE="$ENV_DIR/coinalyze.env"
NGINX_SITE="/etc/nginx/sites-available/coinalyze"

DEFAULT_NGINX_ALLOWED_CIDRS='["127.0.0.1/32","::1/128","10.10.100.0/28"]'

render_nginx_allowlist() {
  local cidrs="${NGINX_ALLOWED_CIDRS:-$DEFAULT_NGINX_ALLOWED_CIDRS}"
  python3 - "$cidrs" <<'PY_ALLOWLIST'
import ipaddress
import json
import sys

raw = sys.argv[1].strip()
try:
    values = json.loads(raw) if raw.startswith("[") else [item.strip() for item in raw.split(",")]
except Exception as exc:
    raise SystemExit(f"NGINX_ALLOWED_CIDRS inválido: {exc}")
if not isinstance(values, list):
    raise SystemExit("NGINX_ALLOWED_CIDRS debe ser una lista JSON o CSV de CIDR")
seen = set()
lines = []
for value in values:
    text = str(value).strip().strip("'\"")
    if not text:
        continue
    try:
        network = ipaddress.ip_network(text, strict=False)
    except ValueError as exc:
        raise SystemExit(f"CIDR inválido para nginx: {text}: {exc}")
    cidr = str(network)
    if cidr not in seen:
        seen.add(cidr)
        lines.append(f"allow {cidr};")
if not lines:
    raise SystemExit("NGINX_ALLOWED_CIDRS no puede quedar vacío")
print("\n".join(lines))
print("deny all;")
PY_ALLOWLIST
}

write_nginx_allowlist() {
  install -d -m 0755 /etc/nginx/snippets
  render_nginx_allowlist > /etc/nginx/snippets/coinalyze-allowlist.conf
  chmod 0644 /etc/nginx/snippets/coinalyze-allowlist.conf
}


[[ $EUID -eq 0 ]] || { echo "Ejecuta como root o con sudo." >&2; exit 1; }
install -d -o root -g coinalyze -m 0750 "$ENV_DIR" 2>/dev/null || install -d -o root -g root -m 0750 "$ENV_DIR"
if [[ ! -f "$ENV_FILE" ]]; then
  install -m 0640 -o root -g coinalyze .env.example "$ENV_FILE" 2>/dev/null || install -m 0640 .env.example "$ENV_FILE"
fi

set_kv() {
  local key="$1"
  local value="$2"
  local escaped
  escaped=$(printf '%s' "$value" | sed -e 's/[\\&|]/\\&/g')
  if grep -qE "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=\"${escaped}\"|" "$ENV_FILE"
  else
    printf '%s="%s"\n' "$key" "$value" >> "$ENV_FILE"
  fi
}

set_raw_kv() {
  local key="$1"
  local value="$2"
  local escaped
  escaped=$(printf '%s' "$value" | sed -e 's/[\\&|]/\\&/g')
  if grep -qE "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=${escaped}|" "$ENV_FILE"
  else
    printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
  fi
}

current_value() {
  local key="$1"
  grep -E "^${key}=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"
}

ask_secret() {
  local key="$1"
  local prompt="$2"
  local current="$(current_value "$key")"
  local value
  read -rsp "$prompt${current:+ [ENTER=conservar]}: " value; echo
  [[ -z "$value" ]] && value="$current"
  [[ -n "$value" ]] && set_kv "$key" "$value"
}

ask_value() {
  local key="$1"
  local prompt="$2"
  local default="${3:-}"
  local current="${default:-$(current_value "$key")}" 
  local value
  read -rp "$prompt${current:+ [$current]}: " value
  [[ -z "$value" ]] && value="$current"
  [[ -n "$value" ]] && set_kv "$key" "$value"
}

generate_if_empty() {
  local key="$1"
  local len="${2:-32}"
  if [[ -z "$(current_value "$key")" || "$(current_value "$key")" == replace_* ]]; then
    set_kv "$key" "$(openssl rand -hex "$len")"
  fi
}

echo "Configuración segura de Coinalyze Operator Dashboard"
echo "Archivo: $ENV_FILE"
echo

ask_secret "API_KEY" "Coinalyze.net API key rotada"
generate_if_empty "API_INTERNAL_TOKEN" 32
generate_if_empty "PG_PASSWORD" 24

ask_value "COINALYZE_BASE_URL" "Coinalyze base URL" "https://api.coinalyze.net/v1"
ask_value "INGEST_INTERVAL_SECONDS" "Intervalo ingest segundos" "60"
ask_value "COINALYZE_RATE_LIMIT_UNITS" "Rate limit units" "35"

ask_value "API_HOST" "API host" "127.0.0.1"
ask_value "API_PORT" "API port" "8000"
set_kv "METRICS_ENABLED" "true"
set_kv "LOG_LEVEL" "INFO"

ask_value "PG_HOST" "PostgreSQL host" "127.0.0.1"
ask_value "PG_PORT" "PostgreSQL port" "5432"
ask_value "PG_DB" "PostgreSQL DB" "coinalyze"
ask_value "PG_USER" "PostgreSQL user" "coinalyze"
ask_value "PG_SSLMODE" "PostgreSQL sslmode" "disable"
set_kv "PG_POOL_MIN" "1"
set_kv "PG_POOL_MAX" "4"
ask_raw_json_default='["127.0.0.1/32","::1/128","10.10.100.0/28"]'
read -rp "CIDR autorizados para API interna [${ask_raw_json_default}]: " api_allowed_cidrs
api_allowed_cidrs="${api_allowed_cidrs:-$ask_raw_json_default}"
set_raw_kv "API_INTERNAL_ALLOWED_CIDRS" "'$api_allowed_cidrs'"
read -rp "CIDR autorizados en nginx para acceder al dashboard [${ask_raw_json_default}]: " nginx_allowed_cidrs
nginx_allowed_cidrs="${nginx_allowed_cidrs:-$ask_raw_json_default}"
set_raw_kv "NGINX_ALLOWED_CIDRS" "'$nginx_allowed_cidrs'"
export NGINX_ALLOWED_CIDRS="$nginx_allowed_cidrs"

LXC_IP=$(hostname -I | awk '{print $1}')
if [[ -n "$LXC_IP" ]]; then
  set_raw_kv "TRUSTED_HOSTS" "'[\"127.0.0.1\",\"localhost\",\"$LXC_IP\"]'"
else
  set_raw_kv "TRUSTED_HOSTS" "'[\"127.0.0.1\",\"localhost\"]'"
fi
set_raw_kv "SYMBOLS" "'[\"BTCUSDT_PERP.A\",\"ETHUSDT_PERP.A\",\"SOLUSDT_PERP.A\"]'"

for kv in \
  HARD_DATA_RETENTION_DAYS=14 SNAPSHOT_RETENTION_DAYS=30 REALTIME_RETENTION_HOURS=2 \
  DAILY_LOOKBACK_DAYS=13 DAILY_SESSION_RETENTION_DAYS=0 SCALP_ENABLED=true \
  SCALP_FLUSH_SECONDS=2 SCALP_ORDERBOOK_FLUSH_SECONDS=2 SCALP_TRADE_RETENTION_HOURS=6 \
  SCALP_ORDERBOOK_RETENTION_HOURS=6 SCALP_SIGNAL_INTERVAL_SECONDS=10 \
  SCALP_SIGNAL_RETENTION_HOURS=72 TRADESTORE_MAX_BUCKET_MINUTES=20 \
  TRADESTORE_MAX_BUCKETS_PER_KEY=30 BINANCE_BOOK_MAX_EVENT_LAG_SECONDS=10 \
  BINANCE_BOOK_STALE_SECONDS=15 BINANCE_BOOK_FORCE_RECONNECT_SECONDS=300 \
  EXTERNAL_MACRO_ENABLED=true EXTERNAL_MACRO_REFRESH_SECONDS=3600; do
  set_kv "${kv%%=*}" "${kv#*=}"
done

# Si Nginx ya existe, actualiza el header usado por el proxy externo.
API_INTERNAL_TOKEN="$(current_value API_INTERNAL_TOKEN)"
if [[ -f "$NGINX_SITE" ]]; then
  write_nginx_allowlist
  if grep -q "__API_INTERNAL_TOKEN__" "$NGINX_SITE"; then
    sed -i "s|__API_INTERNAL_TOKEN__|$API_INTERNAL_TOKEN|g" "$NGINX_SITE"
  elif grep -q "proxy_set_header X-Internal-Token" "$NGINX_SITE"; then
    sed -i "s|proxy_set_header X-Internal-Token .*;|proxy_set_header X-Internal-Token \"$API_INTERNAL_TOKEN\";|" "$NGINX_SITE"
  fi
  nginx -t && systemctl reload nginx || true
fi

chown root:coinalyze "$ENV_DIR" "$ENV_FILE" 2>/dev/null || chown root:root "$ENV_DIR" "$ENV_FILE"
chmod 0750 "$ENV_DIR"
chmod 0640 "$ENV_FILE"

echo
echo "Configuración escrita en $ENV_FILE"
echo "API_INTERNAL_TOKEN actual:"
echo "  sudo bash -lc 'set -a; source $ENV_FILE; set +a; printf %s\\n \"\$API_INTERNAL_TOKEN\"'"
echo
echo "Reinicia y valida:"
echo "  sudo systemctl restart coinalyze-api coinalyze-ingest coinalyze-ws coinalyze-scalp coinalyze-daily nginx"
echo "  sudo bash -lc 'set -a; source $ENV_FILE; set +a; curl -fsS -H \"X-Internal-Token: \$API_INTERNAL_TOKEN\" http://127.0.0.1:8000/api/healthz | python3 -m json.tool'"
