#!/usr/bin/env bash
# DATOS B (fable-f8 F3) · Lo que root ejecuta en 143 deja de salir del arbol de trabajo /srv/coinanalyze/repo (alli se
# sacan ramas de campana) y sale de una COPIA CONGELADA de main, de root y sin escritura para nadie mas:
# /opt/coinalyze-143/<sha>, con /opt/coinalyze-143/current apuntando a la vigente. Desde esa copia instala el informe
# semanal (coinalyze-bot-semanal), el respaldo de las libretas (coinalyze-libretas), el diario de entradas
# (coinalyze-diario-cuarto y -dia, con el python del sistema: E-01) y el cron de capta-healthz (K05),
# y quita del crontab de root la linea vieja de capta-healthz (dos crons escribirian dos muestras por minuto).
#
# Lo corre el OPERADOR, como root:
#   git -C /srv/coinanalyze/repo fetch origin main
#   bash /srv/coinanalyze/repo/deploy/143/instala.sh [<sha de main>]      (por omision, origin/main)
# Repetirlo con un sha mas nuevo es actualizar; con uno anterior, volver. Las copias viejas se quedan en /opt/coinalyze-143.
set -Eeuo pipefail
REPO=/srv/coinanalyze/repo
BASE=/opt/coinalyze-143
UNIT_DIR=/etc/systemd/system
CRON_FILE=/etc/cron.d/coinalyze-capta-healthz
UNITS=(coinalyze-bot-semanal.service coinalyze-bot-semanal.timer coinalyze-libretas.service coinalyze-libretas.timer
       coinalyze-diario-cuarto.service coinalyze-diario-cuarto.timer coinalyze-diario-dia.service coinalyze-diario-dia.timer)

die(){ echo "instala.sh: $*" >&2; exit 1; }
log(){ echo "instala.sh: $*"; }
[ "$(id -u)" -eq 0 ] || die "hay que correrlo como root"

g(){ git -c safe.directory="$REPO" -C "$REPO" "$@"; }
ref=${1:-origin/main}
sha=$(g rev-parse --verify -q "$ref^{commit}") || die "no existe en $REPO: $ref"
main=$(g rev-parse --verify -q "origin/main^{commit}") || die "no hay origin/main en $REPO"
g merge-base --is-ancestor "$sha" "$main" || die "$sha no esta en origin/main"

# 1 · la copia: lo COMMITEADO (git archive), no lo que haya en el arbol de trabajo.
mkdir -p "$BASE"
chown root:root "$BASE"
chmod 755 "$BASE"
dest="$BASE/$sha"
if [ ! -d "$dest" ]; then
  tmp=$(mktemp -d "$BASE/.nueva.XXXXXX")
  g archive --format=tar "$sha" | tar -x --no-same-owner -C "$tmp"
  chown -R root:root "$tmp"
  chmod -R go-w "$tmp"
  chmod 755 "$tmp"
  mv -T "$tmp" "$dest"
fi
ln -sfn "$sha" "$BASE/.current.nuevo"
mv -T "$BASE/.current.nuevo" "$BASE/current"
log "copia congelada: $dest (current -> $sha)"

# 2 · las unidades, desde la copia.
for u in "${UNITS[@]}"; do
  src="$dest/deploy/143/$u"
  [ -f "$src" ] || src="$dest/deploy/systemd/$u"
  [ -f "$src" ] || die "la copia no trae $u"
  install -m 644 "$src" "$UNIT_DIR/$u"
done
systemctl daemon-reload
systemctl enable --now coinalyze-bot-semanal.timer coinalyze-libretas.timer coinalyze-diario-cuarto.timer coinalyze-diario-dia.timer
log "unidades instaladas: ${UNITS[*]}"

# 3 · el cron de capta-healthz, desde la copia; fuera la linea vieja del crontab de root.
printf '%s\n' "# DATOS B: capta-healthz (K05) desde la copia congelada de main; lo instala deploy/143/instala.sh" \
  "* * * * * root $BASE/current/harness/bin/capta-healthz" > "$CRON_FILE.nuevo"
chmod 644 "$CRON_FILE.nuevo"
mv -T "$CRON_FILE.nuevo" "$CRON_FILE"
viejo=$(mktemp)
trap 'rm -f "$viejo" "$viejo.sin"' EXIT
if crontab -l -u root > "$viejo" 2>/dev/null && grep -q 'harness/bin/capta-healthz' "$viejo"; then
  grep -v 'harness/bin/capta-healthz' "$viejo" > "$viejo.sin" || true
  crontab -u root "$viejo.sin"
  log "quitada del crontab de root: $(grep 'harness/bin/capta-healthz' "$viejo" | tr '\n' ' ')"
fi
log "cron: $CRON_FILE"
log "OK $sha"
