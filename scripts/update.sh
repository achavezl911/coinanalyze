#!/usr/bin/env bash
set -Eeuo pipefail
export LANG=C.UTF-8 LC_ALL=C.UTF-8
[[ $EUID -eq 0 ]] || { echo 'Ejecutar como root.' >&2; exit 1; }
SOURCE_DIR=${1:-$(pwd)}
[[ -f "$SOURCE_DIR/pyproject.toml" ]] || { echo 'Directorio fuente inválido.' >&2; exit 1; }
[[ $(realpath "$SOURCE_DIR") != /opt/coinalyze ]] || {
  echo 'El directorio fuente debe ser una copia distinta de /opt/coinalyze.' >&2
  exit 1
}

# El rsync de mas abajo usa --delete: cualquier ruta ausente en $SOURCE_DIR se borra
# de /opt/coinalyze. Un paquete parcial (solo app/ + static/) dejaria el contenedor
# sin schema.sql, sin units systemd y sin scripts/ (incl. backup.sh y este archivo).
# Verificar ANTES de parar servicios y antes de tocar el arbol.
REQUIRED_PATHS=(
  pyproject.toml
  requirements.lock
  sql/schema.sql
  scripts/backup.sh
  scripts/backfill_ohlcv_daily.py
  scripts/smoke_test.sh
  scripts/update.sh
  deploy/nginx/coinalyze.conf
  deploy/systemd/coinalyze-api.service
  deploy/systemd/coinalyze-backup.service
  deploy/systemd/coinalyze-backup.timer
  deploy/proxmox/install.sh
  app
  static
)
MISSING=()
for path in "${REQUIRED_PATHS[@]}"; do
  [[ -e "$SOURCE_DIR/$path" ]] || MISSING+=("$path")
done
if (( ${#MISSING[@]} > 0 )); then
  echo "Directorio fuente incompleto: $SOURCE_DIR" >&2
  printf '  falta: %s\n' "${MISSING[@]}" >&2
  echo 'Use un arbol completo del proyecto, no un paquete solo-app.' >&2
  exit 1
fi


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

SERVICES=(coinalyze-api coinalyze-ingest coinalyze-daily)
for service in coinalyze-ws coinalyze-scalp; do
  systemctl is-active --quiet "$service" && SERVICES+=("$service")
done
mapfile -t ACTIVE_SHARD_SERVICES < <(
  systemctl list-units --type=service --state=active --plain --no-legend \
    'coinalyze-ws@*.service' 'coinalyze-scalp@*.service' | awk '{print $1}'
)
SERVICES+=("${ACTIVE_SHARD_SERVICES[@]}")
BACKUP_KEY_FILE=${BACKUP_ENCRYPTION_KEY_FILE:-/etc/coinalyze/backup.key}
recover() {
  rc=$?
  if (( rc != 0 )); then
    systemctl start "${SERVICES[@]}" >/dev/null 2>&1 || true
  fi
  trap - EXIT
  exit "$rc"
}
trap recover EXIT

set -a
source /etc/coinalyze/coinalyze.env
set +a
# Normalize JSON-like values so pydantic-settings and shell sourcing both work.
LXC_IP=$(hostname -I | awk '{print $1}')
sed -i \
  -e "s/^TRUSTED_HOSTS=.*/TRUSTED_HOSTS=\'[\"127.0.0.1\",\"localhost\",\"$LXC_IP\"]\'/" \
  /etc/coinalyze/coinalyze.env
# Migra solo el pin legacy exacto: así el catálogo versionado puede crecer sin otra edición,
# pero una selección operativa personalizada se conserva.
if grep -qx "SYMBOLS='\[\"BTCUSDT_PERP.A\",\"ETHUSDT_PERP.A\",\"SOLUSDT_PERP.A\"\]'" /etc/coinalyze/coinalyze.env; then
  sed -i '/^SYMBOLS=/d' /etc/coinalyze/coinalyze.env
fi
if ! grep -q "^API_INTERNAL_TOKEN=" /etc/coinalyze/coinalyze.env; then
  API_INTERNAL_TOKEN=$(openssl rand -hex 32)
  echo "API_INTERNAL_TOKEN=$API_INTERNAL_TOKEN" >> /etc/coinalyze/coinalyze.env
fi
if ! grep -q "^PG_SSLMODE=" /etc/coinalyze/coinalyze.env; then
  echo "PG_SSLMODE=disable" >> /etc/coinalyze/coinalyze.env
fi
if ! grep -q "^API_INTERNAL_ALLOWED_CIDRS=" /etc/coinalyze/coinalyze.env; then
  cat >> /etc/coinalyze/coinalyze.env <<'ENV_APPEND'
API_INTERNAL_ALLOWED_CIDRS='["127.0.0.1/32","::1/128","10.10.100.0/28"]'
ENV_APPEND
fi
if ! grep -q "^NGINX_ALLOWED_CIDRS=" /etc/coinalyze/coinalyze.env; then
  cat >> /etc/coinalyze/coinalyze.env <<'ENV_APPEND'
NGINX_ALLOWED_CIDRS='["127.0.0.1/32","::1/128","10.10.100.0/28"]'
ENV_APPEND
fi
for kv in COLLECTOR_SHARD_INDEX=0 COLLECTOR_SHARD_COUNT=1 SCALP_ENABLED=true SCALP_FLUSH_SECONDS=2 SCALP_ORDERBOOK_FLUSH_SECONDS=2 SCALP_TRADE_RETENTION_HOURS=6 SCALP_MINUTE_RETENTION_HOURS=36 SCALP_ORDERBOOK_RETENTION_HOURS=6 SCALP_SIGNAL_INTERVAL_SECONDS=10 SCALP_SIGNAL_RETENTION_HOURS=72 HTF_DATA_RETENTION_DAYS=400 DAILY_SESSION_RETENTION_DAYS=0 METRICS_ENABLED=true EXTERNAL_MACRO_ENABLED=true EXTERNAL_MACRO_REFRESH_SECONDS=3600; do
  key=${kv%%=*}
  grep -q "^${key}=" /etc/coinalyze/coinalyze.env || echo "$kv" >> /etc/coinalyze/coinalyze.env
done
set -a
source /etc/coinalyze/coinalyze.env
set +a
if [[ ! -s "$BACKUP_KEY_FILE" ]]; then
  openssl rand -hex 32 > "$BACKUP_KEY_FILE"
fi
chmod 0600 "$BACKUP_KEY_FILE"
/opt/coinalyze/scripts/backup.sh
systemctl stop "${SERVICES[@]}" >/dev/null 2>&1 || true
rsync -a --delete --exclude '.venv' --exclude '.env' --exclude '.deploy-backups' \
  "$SOURCE_DIR/" /opt/coinalyze/
/opt/coinalyze/.venv/bin/pip install --disable-pip-version-check --no-cache-dir \
  -r /opt/coinalyze/requirements.lock
/opt/coinalyze/.venv/bin/pip install --disable-pip-version-check --no-cache-dir \
  --no-deps "$SOURCE_DIR"
export PGPASSWORD="$PG_PASSWORD"
psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" \
  -v ON_ERROR_STOP=1 -f /opt/coinalyze/sql/schema.sql
/opt/coinalyze/.venv/bin/python /opt/coinalyze/scripts/backfill_ohlcv_daily.py --days 730

install -m 0644 /opt/coinalyze/deploy/systemd/coinalyze-*.service /etc/systemd/system/
install -m 0644 /opt/coinalyze/deploy/systemd/coinalyze-backup.timer /etc/systemd/system/
install -m 0644 /opt/coinalyze/deploy/nginx/coinalyze.conf /etc/nginx/sites-available/coinalyze
sed -i "s|__API_INTERNAL_TOKEN__|$API_INTERNAL_TOKEN|g" /etc/nginx/sites-available/coinalyze
write_nginx_allowlist

chown -R root:coinalyze /opt/coinalyze
find /opt/coinalyze -path /opt/coinalyze/.venv -prune -o -type d -exec chmod 0750 {} +
find /opt/coinalyze -path /opt/coinalyze/.venv -prune -o -type f -exec chmod 0640 {} +
find /opt/coinalyze/.venv -type d -exec chmod 0750 {} +
find /opt/coinalyze/.venv -type f -exec chmod 0640 {} +
find /opt/coinalyze/.venv/bin -type f -exec chmod 0750 {} +
chmod 0750 /opt/coinalyze/scripts/*.sh /opt/coinalyze/deploy/proxmox/install.sh

nginx -t
systemctl daemon-reload
systemctl restart "${SERVICES[@]}" nginx
for i in $(seq 1 30); do
  if /opt/coinalyze/scripts/smoke_test.sh >/dev/null 2>&1; then
    /opt/coinalyze/scripts/backup.sh
    trap - EXIT
    echo "Update complete."
    exit 0
  fi
  if ! systemctl is-active --quiet coinalyze-api; then
    systemctl status coinalyze-api --no-pager -l || true
    journalctl -u coinalyze-api -n 120 --no-pager || true
    exit 1
  fi
  sleep 2
done
echo "API smoke test did not pass within timeout." >&2
journalctl -u coinalyze-api -n 120 --no-pager || true
exit 1
