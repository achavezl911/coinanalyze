#!/usr/bin/env bash
# Tarball de GitHub por el commit (lo que baja el envoltorio nuevo) contra el artefacto del workflow de hoy
# (.github/workflows/deploy-production.yml:78-82, mismo tar sobre un checkout limpio del commit).
set -euo pipefail
B=${B:-/srv/coinanalyze/x1-tmp/banco-envoltorio-r1}
R=/srv/coinanalyze/repo
SHA=$(git -C "$R" rev-parse main)
mkdir -p "$B/gh" "$B/cmp"
curl -fsSL --proto '=https' --proto-redir '=https' -m 300 -o "$B/gh/github.tgz" \
  -w 'GitHub: http %{http_code} · %{size_download} bytes\n' "https://api.github.com/repos/achavezl911/coinanalyze/tarball/$SHA"
rm -rf "$B/cmp/wt"
git -C "$R" worktree add -q --detach "$B/cmp/wt" "$SHA"
tar czf "$B/cmp/artefacto.tgz" \
  --exclude='./.git' --exclude='./.github' --exclude='./.venv' \
  --exclude='*/__pycache__' --exclude='./.pytest_cache' --exclude='./.ruff_cache' \
  --exclude='./graphify-out' \
  -C "$B/cmp/wt" .
git -C "$R" worktree remove --force "$B/cmp/wt"
echo "artefacto: $(stat -c %s "$B/cmp/artefacto.tgz") bytes"
# lo que DEJA cada uno al extraerlo como el envoltorio (GNU tar), sin la carpeta de cabeza
rm -rf "$B/cmp/x-gh" "$B/cmp/x-art"; mkdir -p "$B/cmp/x-gh" "$B/cmp/x-art"
tar --no-same-owner --no-same-permissions -xzf "$B/gh/github.tgz" -C "$B/cmp/x-gh"
tar --no-same-owner --no-same-permissions -xzf "$B/cmp/artefacto.tgz" -C "$B/cmp/x-art"
echo "cabeza del tarball (entradas en la raiz): $(ls -A "$B/cmp/x-gh" | tr '\n' ' ')"
GH=$(find "$B/cmp/x-gh" -mindepth 1 -maxdepth 1)
( cd "$GH" && find . -mindepth 1 \( -type f -o -type l \) | sort ) > "$B/cmp/l-gh"
( cd "$B/cmp/x-art" && find . -mindepth 1 \( -type f -o -type l \) | sort ) > "$B/cmp/l-art"
echo "ficheros: tarball $(wc -l < "$B/cmp/l-gh") · artefacto $(wc -l < "$B/cmp/l-art") · git ls-tree $(git -C "$R" ls-tree -r --name-only "$SHA" | wc -l)"
echo "solo en el tarball:"; comm -23 "$B/cmp/l-gh" "$B/cmp/l-art" | head -n 20
echo "solo en el artefacto:"; comm -13 "$B/cmp/l-gh" "$B/cmp/l-art" | head -n 20
n=0; d=0
while read -r f; do n=$((n+1)); cmp -s "$GH/$f" "$B/cmp/x-art/$f" || { d=$((d+1)); echo "DISTINTO: $f"; }; done \
  < <(comm -12 "$B/cmp/l-gh" "$B/cmp/l-art")
echo "comunes $n · distintos en bytes $d"
echo "enlaces simbolicos: tarball $(find "$GH" -type l | wc -l) · artefacto $(find "$B/cmp/x-art" -type l | wc -l)"
echo "SHA=$SHA"
