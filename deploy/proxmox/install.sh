#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
export LANG=C.UTF-8 LC_ALL=C.UTF-8

[[ $EUID -eq 0 ]] || { echo 'Ejecutar como root dentro del LXC Proxmox o VM Debian.' >&2; exit 1; }
[[ -n "${COINALYZE_API_KEY:-}" ]] || {
  echo "Falta COINALYZE_API_KEY. Uso: COINALYZE_API_KEY='...' DASHBOARD_PASSWORD='...' NGINX_ALLOWED_CIDRS='[\"10.10.100.0/28\"]' ./deploy/proxmox/install.sh" >&2
  exit 1
}
[[ "$COINALYZE_API_KEY" =~ ^[A-Za-z0-9._-]+$ ]] || { echo 'API key con caracteres no permitidos.' >&2; exit 1; }

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
SOURCE_DIR=$(cd -- "$SCRIPT_DIR/../.." && pwd)

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

DASHBOARD_USER=${DASHBOARD_USER:-operator}
[[ "$DASHBOARD_USER" =~ ^[A-Za-z0-9._-]+$ ]] || { echo 'DASHBOARD_USER inválido.' >&2; exit 1; }

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  python3 python3-venv python3-pip postgresql postgresql-client nginx \
  apache2-utils ca-certificates curl rsync openssl iproute2 tzdata locales \
  unattended-upgrades

sed -i 's/^# *\(en_US.UTF-8 UTF-8\)/\1/' /etc/locale.gen
locale-gen en_US.UTF-8
update-locale LANG=en_US.UTF-8

install -m 0644 "$SOURCE_DIR/deploy/apt/20auto-upgrades" /etc/apt/apt.conf.d/20auto-upgrades
systemctl enable --now apt-daily.timer apt-daily-upgrade.timer

DASHBOARD_PASSWORD=${DASHBOARD_PASSWORD:-$(openssl rand -base64 18 | tr -d '/+=')}
NGINX_ALLOWED_CIDRS=${NGINX_ALLOWED_CIDRS:-$DEFAULT_NGINX_ALLOWED_CIDRS}
DB_PASSWORD=$(openssl rand -hex 24)
API_INTERNAL_TOKEN=$(openssl rand -hex 32)
BACKUP_KEY_FILE=/etc/coinalyze/backup.key

systemctl enable --now postgresql
getent group coinalyze >/dev/null || groupadd --system coinalyze
id coinalyze >/dev/null 2>&1 || useradd --system --gid coinalyze --home-dir /nonexistent --shell /usr/sbin/nologin coinalyze

install -d -o root -g coinalyze -m 0750 /opt/coinalyze /etc/coinalyze /var/backups/coinalyze
if [[ ! -s "$BACKUP_KEY_FILE" ]]; then
  openssl rand -hex 32 > "$BACKUP_KEY_FILE"
fi
chmod 0600 "$BACKUP_KEY_FILE"
rsync -a --delete --exclude '.venv' --exclude '.env' "$SOURCE_DIR/" /opt/coinalyze/
python3 -m venv /opt/coinalyze/.venv
/opt/coinalyze/.venv/bin/pip install --upgrade pip setuptools wheel
/opt/coinalyze/.venv/bin/pip install --no-cache-dir -r /opt/coinalyze/requirements.lock
/opt/coinalyze/.venv/bin/pip install --no-cache-dir --no-deps "$SOURCE_DIR"

ROLE_EXISTS=$(runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='coinalyze'")
if [[ "$ROLE_EXISTS" != "1" ]]; then
  runuser -u postgres -- psql -v ON_ERROR_STOP=1 -c "CREATE ROLE coinalyze LOGIN PASSWORD '$DB_PASSWORD'"
else
  runuser -u postgres -- psql -v ON_ERROR_STOP=1 -c "ALTER ROLE coinalyze LOGIN PASSWORD '$DB_PASSWORD'"
fi
DB_EXISTS=$(runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_database WHERE datname='coinalyze'")
if [[ "$DB_EXISTS" != "1" ]]; then
  runuser -u postgres -- createdb --owner=coinalyze coinalyze
else
  runuser -u postgres -- psql -v ON_ERROR_STOP=1 -c "ALTER DATABASE coinalyze OWNER TO coinalyze"
fi

cat > /etc/coinalyze/coinalyze.env <<ENV
API_KEY=$COINALYZE_API_KEY
COINALYZE_BASE_URL=https://api.coinalyze.net/v1
INGEST_INTERVAL_SECONDS=60
COINALYZE_RATE_LIMIT_UNITS=35
EXTERNAL_MACRO_ENABLED=true
EXTERNAL_MACRO_REFRESH_SECONDS=3600
COINGLASS_API_KEY=
PG_HOST=127.0.0.1
PG_PORT=5432
PG_DB=coinalyze
PG_USER=coinalyze
PG_PASSWORD=$DB_PASSWORD
PG_POOL_MIN=1
PG_POOL_MAX=4
PG_SSLMODE=disable
API_HOST=127.0.0.1
API_PORT=8000
API_INTERNAL_TOKEN=$API_INTERNAL_TOKEN
API_INTERNAL_ALLOWED_CIDRS='["127.0.0.1/32","::1/128","10.10.100.0/28"]'
NGINX_ALLOWED_CIDRS='$NGINX_ALLOWED_CIDRS'
METRICS_ENABLED=true
LOG_LEVEL=INFO
TRUSTED_HOSTS='["127.0.0.1","localhost"]'
SCALP_ENABLED=true
SCALP_FLUSH_SECONDS=2
SCALP_ORDERBOOK_FLUSH_SECONDS=2
SCALP_TRADE_RETENTION_HOURS=6
SCALP_ORDERBOOK_RETENTION_HOURS=6
SCALP_SIGNAL_INTERVAL_SECONDS=10
SCALP_SIGNAL_RETENTION_HOURS=72
TRADESTORE_MAX_BUCKET_MINUTES=20
TRADESTORE_MAX_BUCKETS_PER_KEY=30
BINANCE_BOOK_MAX_EVENT_LAG_SECONDS=10
BINANCE_BOOK_STALE_SECONDS=15
BINANCE_BOOK_FORCE_RECONNECT_SECONDS=300
HARD_DATA_RETENTION_DAYS=14
HTF_DATA_RETENTION_DAYS=400
SNAPSHOT_RETENTION_DAYS=30
REALTIME_RETENTION_HOURS=2
DAILY_LOOKBACK_DAYS=13
DAILY_SESSION_RETENTION_DAYS=0
SYMBOLS='["BTCUSDT_PERP.A","ETHUSDT_PERP.A","SOLUSDT_PERP.A"]'
ENV
chmod 0640 /etc/coinalyze/coinalyze.env
chown root:coinalyze /etc/coinalyze/coinalyze.env

export PGPASSWORD="$DB_PASSWORD"
psql -h 127.0.0.1 -U coinalyze -d coinalyze -v ON_ERROR_STOP=1 -f /opt/coinalyze/sql/schema.sql
set -a
source /etc/coinalyze/coinalyze.env
set +a
/opt/coinalyze/.venv/bin/python /opt/coinalyze/scripts/backfill_ohlcv_daily.py --days 730

install -m 0644 /opt/coinalyze/deploy/systemd/coinalyze-*.service /etc/systemd/system/
install -m 0644 /opt/coinalyze/deploy/systemd/coinalyze-backup.timer /etc/systemd/system/
install -m 0644 /opt/coinalyze/deploy/nginx/coinalyze.conf /etc/nginx/sites-available/coinalyze
sed -i "s|__API_INTERNAL_TOKEN__|$API_INTERNAL_TOKEN|g" /etc/nginx/sites-available/coinalyze
write_nginx_allowlist
ln -sfn /etc/nginx/sites-available/coinalyze /etc/nginx/sites-enabled/coinalyze
rm -f /etc/nginx/sites-enabled/default
htpasswd -bc /etc/nginx/coinalyze.htpasswd "$DASHBOARD_USER" "$DASHBOARD_PASSWORD"
chmod 0640 /etc/nginx/coinalyze.htpasswd
chown root:www-data /etc/nginx/coinalyze.htpasswd

LXC_IP=$(ip -4 -o addr show scope global | awk '{split($4,a,"/"); print a[1]; exit}')
[[ -n "$LXC_IP" ]] || { echo 'No se detectó una IPv4 global.' >&2; exit 1; }
LXC_HOSTNAME=$(hostname -f 2>/dev/null || hostname)
openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 825 \
  -keyout /etc/nginx/coinalyze.key -out /etc/nginx/coinalyze.crt \
  -subj "/CN=${LXC_HOSTNAME}" \
  -addext "subjectAltName=DNS:${LXC_HOSTNAME},IP:${LXC_IP}"
chmod 0640 /etc/nginx/coinalyze.key
chown root:www-data /etc/nginx/coinalyze.key /etc/nginx/coinalyze.crt

chown -R root:coinalyze /opt/coinalyze
find /opt/coinalyze -path /opt/coinalyze/.venv -prune -o -type d -exec chmod 0750 {} +
find /opt/coinalyze -path /opt/coinalyze/.venv -prune -o -type f -exec chmod 0640 {} +
find /opt/coinalyze/.venv -type d -exec chmod 0750 {} +
find /opt/coinalyze/.venv -type f -exec chmod 0640 {} +
find /opt/coinalyze/.venv/bin -type f -exec chmod 0750 {} +
chmod 0750 /opt/coinalyze/deploy/proxmox/install.sh /opt/coinalyze/scripts/*.sh
nginx -t
systemctl daemon-reload
systemctl enable --now coinalyze-ingest coinalyze-ws coinalyze-scalp coinalyze-daily coinalyze-api coinalyze-backup.timer nginx

for i in $(seq 1 30); do
  if /opt/coinalyze/scripts/smoke_test.sh http://127.0.0.1:8000; then
    break
  fi
  if ! systemctl is-active --quiet coinalyze-api; then
    systemctl status coinalyze-api --no-pager -l || true
    journalctl -u coinalyze-api -n 120 --no-pager || true
    exit 1
  fi
  sleep 2
done
cat <<RESULT

Instalación terminada.
URL: https://${LXC_IP}:8443
Usuario: ${DASHBOARD_USER}
Contraseña: ${DASHBOARD_PASSWORD}

Restringe TCP/8443 (y 8090 si conserva la redirección HTTP) a tu VLAN de administración mediante firewall de Proxmox o firewall L3.
RESULT
