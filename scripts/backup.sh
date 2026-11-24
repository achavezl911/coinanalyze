#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

BACKUP_DIR_POR_DEFECTO=/var/backups/coinalyze
BACKUP_DIR=${BACKUP_DIR:-$BACKUP_DIR_POR_DEFECTO}

# ROOT SIEMPRE, salvo para podar un directorio que NO es el de produccion. Respaldar toca
# Postgres y la llave de cifrado, y podar BORRA ficheros: la guarda tiene motivo. Pero si no se
# pudiera podar un directorio de mentira sin ser root, la poda no se podria PROBAR en CI, y un
# test que siempre se salta no guarda nada. La guarda se afina, no se quita.
if [[ $EUID -ne 0 ]]; then
  if [[ ${1:-} != --solo-podar || $BACKUP_DIR == "$BACKUP_DIR_POR_DEFECTO" ]]; then
    echo 'Ejecutar como root.' >&2
    exit 1
  fi
fi
BACKUP_KEY_FILE=${BACKUP_ENCRYPTION_KEY_FILE:-/etc/coinalyze/backup.key}
# 4 y no 14: la historia larga vive en el nodo, que copia cada dia los cifrados con sha256 y manifiesto.
BACKUP_RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-4}
# LOS VOLCADOS PRE-DESPLIEGUE SE PODAN POR CUENTA, NO POR EDAD. El cifrado es la copia de
# seguridad de verdad y se guarda cuatro dias aqui. El pre-despliegue solo sirve para revertir
# el despliegue reciente, asi que basta con el del release activo y el del ultimo intento: los 2
# MAS RECIENTES por mtime. La vida de 3 dias (Alejandro, 2026-09-08) no acotaba nada: con varios
# intentos al dia de ~3.6 GB cada uno, 11 volcados dentro de su vida llenaron el disco de 140 al
# 100 % el 2026-11-23 y un despliegue revirtio por «No space left on device». Y por edad, una
# semana sin desplegar borraba tambien el del release activo.
PREDEPLOY_KEEP=${PREDEPLOY_KEEP:-2}
# Al menos 1: con 0 la poda se llevaria el volcado del release que corre.
[[ $PREDEPLOY_KEEP =~ ^[1-9][0-9]*$ ]] || { echo "PREDEPLOY_KEEP invalido: $PREDEPLOY_KEEP" >&2; exit 1; }
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
FINAL_NAME="coinalyze-full-${STAMP}.tar.gz.enc"
FINAL_PATH="$BACKUP_DIR/$FINAL_NAME"

# Poda una CLASE de respaldo: sus patrones de nombre y su vida, ambos recibidos.
# `-maxdepth 1 -type f` y patrones anclados por prefijo: la poda no sale del directorio de
# respaldos ni toca nada que no lleve uno de estos nombres.
podar_clase() {
  local dias="$1"; shift
  local expr=()
  for patron in "$@"; do
    ((${#expr[@]})) && expr+=( -o )
    expr+=( -name "$patron" )
  done
  find "$BACKUP_DIR" -maxdepth 1 -type f \( "${expr[@]}" \) -mtime "+$dias" -delete
}

# Los volcados PRE-DESPLIEGUE, solos. Separada porque es la unica poda que puede correr antes de
# saber si el respaldo de hoy sale: estos no los escribe este script y no son el respaldo diario.
# Quedan los $PREDEPLOY_KEEP mas nuevos por mtime; cada borrado deja su linea en stderr (journal).
podar_predeploy() {
  local n=0 linea f
  while IFS= read -r -d '' linea; do
    f=${linea#* }
    n=$((n + 1))
    if ((n <= PREDEPLOY_KEEP)); then
      continue
    fi
    echo "poda predeploy: borro $(basename -- "$f") (puesto $n, se quedan $PREDEPLOY_KEEP)" >&2
    # El `.sha256` va aunque hoy el wrapper no lo escriba: si algun dia lo escribe, se poda con su
    # volcado en vez de quedarse huerfano acumulandose, que es como empezo este defecto.
    rm -f -- "$f" "$f.sha256"
  done < <(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'predeploy-*.sql.gz' -printf '%T@ %p\0' | LC_ALL=C sort -z -rn)
  # Un `.sha256` cuyo volcado ya no esta no protege nada.
  while IFS= read -r -d '' f; do
    if [[ ! -e ${f%.sha256} ]]; then
      echo "poda predeploy: borro $(basename -- "$f") (huerfano)" >&2
      rm -f -- "$f"
    fi
  done < <(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'predeploy-*.sql.gz.sha256' -print0)
}

# LAS DOS CLASES: los cifrados por edad, los pre-despliegue por cuenta.
podar_respaldos() {
  podar_clase "$BACKUP_RETENTION_DAYS" \
    'coinalyze-full-*.tar.gz.enc' \
    'coinalyze-full-*.tar.gz.enc.sha256' \
    'coinalyze-*.dump'
  podar_predeploy
}

# SOLO PODAR, sin respaldar. Existe para poder EJERCITAR la poda plantando ficheros: correr el
# script entero pide credenciales de Postgres y la llave de cifrado, asi que sin esta puerta la
# poda no se podria probar nunca. Es el mismo codigo que corre el servicio diario.
if [[ ${1:-} == --solo-podar ]]; then
  [[ -d "$BACKUP_DIR" ]] || { echo "No existe $BACKUP_DIR" >&2; exit 1; }
  podar_respaldos
  exit 0
fi

for name in PG_HOST PG_PORT PG_USER PG_DB PG_PASSWORD; do
  [[ -n "${!name:-}" ]] || { echo "Falta $name para el respaldo." >&2; exit 1; }
done
[[ -s "$BACKUP_KEY_FILE" ]] || {
  echo "Falta la llave de respaldo: $BACKUP_KEY_FILE" >&2
  exit 1
}

mkdir -p "$BACKUP_DIR"
# Antes del STAGE se podan SOLO los pre-despliegue: si solo se podara al final, un respaldo que
# muere por falta de disco no podaria nunca (140, 2026-11-02: 41 GB de caducos). Los CIFRADOS no:
# se podan unicamente tras un respaldo correcto (al final). Si el respaldo falla N dias seguidos
# (llave, Postgres, disco), podarlos aqui los haria caducar uno a uno hasta no dejar ninguno.
podar_predeploy
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
# SE VERIFICA EL .tmp Y SOLO DESPUES SE PUBLICA (D-05). Con el `mv` delante, un cifrado que no
# descifraba quedaba con nombre de respaldo y sin .sha256: la poda lo contaba y la restauracion
# cogia el mas nuevo. Si esto falla, la trampa EXIT borra el .tmp y el guion acaba en fallo.
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
  -pass "file:$BACKUP_KEY_FILE" -in "$FINAL_PATH.tmp" | gzip -t
mv "$FINAL_PATH.tmp" "$FINAL_PATH"
(
  cd "$BACKUP_DIR"
  sha256sum "$FINAL_NAME" > "$FINAL_NAME.sha256"
  chmod 0600 "$FINAL_NAME.sha256"
)

podar_respaldos

echo "$FINAL_PATH"
