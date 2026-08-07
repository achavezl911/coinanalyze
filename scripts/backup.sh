#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

[[ $EUID -eq 0 ]] || { echo 'Ejecutar como root.' >&2; exit 1; }

BACKUP_DIR=${BACKUP_DIR:-/var/backups/coinalyze}
BACKUP_KEY_FILE=${BACKUP_ENCRYPTION_KEY_FILE:-/etc/coinalyze/backup.key}
BACKUP_RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-14}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
FINAL_NAME="coinalyze-full-${STAMP}.tar.gz.enc"
FINAL_PATH="$BACKUP_DIR/$FINAL_NAME"

for name in PG_HOST PG_PORT PG_USER PG_DB PG_PASSWORD; do
  [[ -n "${!name:-}" ]] || { echo "Falta $name para el respaldo." >&2; exit 1; }
done
[[ -s "$BACKUP_KEY_FILE" ]] || {
  echo "Falta la llave de respaldo: $BACKUP_KEY_FILE" >&2
  exit 1
}

mkdir -p "$BACKUP_DIR"
STAGE=$(mktemp -d "$BACKUP_DIR/.stage-${STAMP}.XXXXXX")
PLAIN_ARCHIVE="$STAGE/payload.tar.gz"
trap 'rm -rf -- "$STAGE" "$FINAL_PATH.tmp"' EXIT
mkdir -p "$STAGE/database" "$STAGE/rootfs" "$STAGE/metadata"

copy_tree() {
  local source=$1
  local target="$STAGE/rootfs$source"
  [[ -d "$source" ]] || return 0
  mkdir -p "$target"
  rsync -a \
    --exclude '.venv' \
    --exclude '.pytest_cache' \
    --exclude '.ruff_cache' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude 'build' \
    --exclude 'backup.key' \
    "$source/" "$target/"
}

copy_path() {
  local source=$1
  [[ -e "$source" || -L "$source" ]] || return 0
  cp -a --parents "$source" "$STAGE/rootfs"
}

export PGPASSWORD="$PG_PASSWORD"
pg_dump -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" \
  --format=custom --compress=9 --file="$STAGE/database/coinalyze.dump"
pg_restore --list "$STAGE/database/coinalyze.dump" >/dev/null

copy_tree /opt/coinalyze
copy_tree /opt/coinalyze-ai-bridge
copy_tree /etc/coinalyze
copy_tree /etc/coinalyze-ai-bridge

for path in \
  /etc/nginx/sites-available/coinalyze \
  /etc/nginx/sites-enabled/coinalyze \
  /etc/nginx/snippets/coinalyze-allowlist.conf \
  /etc/nginx/coinalyze.htpasswd \
  /etc/nginx/coinalyze.crt \
  /etc/nginx/coinalyze.key; do
  copy_path "$path"
done
for path in /etc/systemd/system/coinalyze-*; do
  copy_path "$path"
done

STATE_DB=/var/lib/coinalyze-ai-bridge/state.db
if [[ -f "$STATE_DB" ]]; then
  STATE_COPY="$STAGE/rootfs/var/lib/coinalyze-ai-bridge/state.db"
  mkdir -p "$(dirname "$STATE_COPY")"
  python3 - "$STATE_DB" "$STATE_COPY" <<'PY_SQLITE'
import sqlite3
import sys

source = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
target = sqlite3.connect(sys.argv[2])
try:
    source.backup(target)
    result = target.execute("PRAGMA integrity_check").fetchone()
    if not result or result[0] != "ok":
        raise RuntimeError(f"SQLite integrity check failed: {result}")
finally:
    target.close()
    source.close()
PY_SQLITE
  chmod 0600 "$STATE_COPY"
fi

{
  echo "generated_at=$STAMP"
  echo "hostname=$(hostname -f 2>/dev/null || hostname)"
  echo "dashboard_version=$(/opt/coinalyze/.venv/bin/python -c 'import importlib.metadata as m; print(m.version("coinalyze-operator-dashboard"))' 2>/dev/null || echo unknown)"
  echo "bridge_version=$(/opt/coinalyze-ai-bridge/.venv/bin/python -c 'import importlib.metadata as m; print(m.version("coinalyze-ai-telegram-bridge"))' 2>/dev/null || echo unknown)"
  echo "postgres_version=$(pg_dump --version)"
} > "$STAGE/metadata/versions.txt"

cat > "$STAGE/RESTORE.txt" <<'RESTORE'
Decrypt with the separately stored backup key:
  openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
    -pass file:/secure/path/backup.key -in BACKUP.tar.gz.enc -out BACKUP.tar.gz

Verify MANIFEST.sha256 after extraction. Restore PostgreSQL with pg_restore and set
ownership of /var/lib/coinalyze-ai-bridge/state.db back to the bridge service account.
The encryption key is intentionally excluded from this archive.
RESTORE

(
  cd "$STAGE"
  find database rootfs metadata -type f -print0 | sort -z | xargs -0 sha256sum > MANIFEST.sha256
  tar -czf "$PLAIN_ARCHIVE" database rootfs metadata MANIFEST.sha256 RESTORE.txt
)

openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 \
  -pass "file:$BACKUP_KEY_FILE" -in "$PLAIN_ARCHIVE" -out "$FINAL_PATH.tmp"
chmod 0600 "$FINAL_PATH.tmp"
mv "$FINAL_PATH.tmp" "$FINAL_PATH"
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
  -pass "file:$BACKUP_KEY_FILE" -in "$FINAL_PATH" | gzip -t
(
  cd "$BACKUP_DIR"
  sha256sum "$FINAL_NAME" > "$FINAL_NAME.sha256"
  chmod 0600 "$FINAL_NAME.sha256"
)

find "$BACKUP_DIR" -maxdepth 1 -type f \
  \( -name 'coinalyze-full-*.tar.gz.enc' -o -name 'coinalyze-full-*.tar.gz.enc.sha256' -o -name 'coinalyze-*.dump' \) \
  -mtime "+$BACKUP_RETENTION_DAYS" -delete

echo "$FINAL_PATH"
