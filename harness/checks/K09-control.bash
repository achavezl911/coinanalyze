#!/usr/bin/env bash
# K09-control · el criterio nuevo mira lo INSTALADO en 140, no la plantilla del repo.
#
# El criterio viejo leia $REPO/deploy/systemd/*.service y llevaba 26 de 27 pasadas en ROJO
# acusando a unos ficheros que apuntan a APP_ROOT A PROPOSITO -el desplegador los reapunta,
# deploy-coinalyze:124-138-. Hay que probar que el nuevo caza las dos grietas REALES de ese
# reapuntado -una unit fuera de la lista SERVICES, y una ruta que no es ${APP_ROOT}/.venv- y
# que NO se inventa culpables: /opt/coinalyze-ai-bridge empieza igual que /opt/coinalyze.
set -uo pipefail
ORIG=${REPO:-/srv/coinanalyze/repo}
CHK="$ORIG/harness/checks/K09-systemd.sh"
[ -r "$CHK" ] || { echo "NO MEDIDO: no encuentro el check en $CHK"; exit 2; }

DIR=$(mktemp -d) || exit 2
[ "${K09_CONTROL_GUARDA:-0}" = "1" ] || trap 'rm -rf "$DIR"' EXIT
mkdir -p "$DIR/bin"

# --- el 140 de mentira. Contesta segun la variable, que es lo que cada caso mueve. ------
cat > "$DIR/bin/prod" <<'PY'
#!/bin/sh
case "$1" in
  *Result*) printf '%s\n' "${K09C_RESULT:-success}" ;;
  *)        printf '%s\n' "${K09C_UNITS:-}" ;;
esac
exit "${K09C_RC:-0}"
PY
chmod +x "$DIR/bin/prod" 2>/dev/null || { echo "NO MEDIDO: no puedo dar el bit de ejecucion"; exit 2; }
cat > "$DIR/bin/prod-roto" <<'PY'
#!/bin/sh
echo "ssh: connect to host: No route to host" >&2
exit 255
PY
chmod +x "$DIR/bin/prod-roto"

T=$(printf '\t')
SANAS="coinalyze-api${T}{ path=/opt/coinalyze/current/.venv/bin/uvicorn ; argv[]=/opt/coinalyze/current/.venv/bin/uvicorn app.api:app }
coinalyze-daily${T}{ path=/opt/coinalyze/current/.venv/bin/python ; argv[]=/opt/coinalyze/current/.venv/bin/python -m app.daily_agg }
coinalyze-ingest${T}{ path=/opt/coinalyze/current/.venv/bin/python ; argv[]=/opt/coinalyze/current/.venv/bin/python -m app.ingest }
coinalyze-scalp${T}{ path=/opt/coinalyze/current/.venv/bin/python ; argv[]=/opt/coinalyze/current/.venv/bin/python -m app.scalp_collector }
coinalyze-ws${T}{ path=/opt/coinalyze/current/.venv/bin/python ; argv[]=/opt/coinalyze/current/.venv/bin/python -m app.ws_collector }
coinalyze-backup${T}{ path=/bin/bash ; argv[]=/bin/bash /opt/coinalyze/current/scripts/backup.sh }
coinalyze-ai-bridge${T}{ path=/opt/coinalyze-ai-bridge/.venv/bin/coinalyze-ai-bridge ; argv[]=/opt/coinalyze-ai-bridge/.venv/bin/coinalyze-ai-bridge }"

fallos=0; pasan=0
caso() {  # <nombre> <rc> <patron> [prod]
  local nombre="$1" esperado="$2" patron="$3" prod="${4:-$DIR/bin/prod}" out rc ok=1
  out=$(REPO="$ORIG" K09_PROD="$prod" bash "$CHK" 2>&1); rc=$?
  [ "$rc" = "$esperado" ] || ok=0
  if [ -n "$patron" ] && ! printf '%s' "$out" | grep -qE "$patron"; then ok=0; fi
  if [ "$ok" = 1 ]; then
    pasan=$((pasan+1)); printf '  [ok   ] %-54s rc=%s\n' "$nombre" "$rc"
  else
    fallos=$((fallos+1))
    printf '  [FALLA] %-54s rc=%s (esperaba %s, patron /%s/)\n      %s\n' \
      "$nombre" "$rc" "$esperado" "$patron" "$(printf '%s' "$out" | head -2 | tr '\n' ' ' | cut -c1-170)"
  fi
}

echo "K09-control · sujeto: $CHK"
echo

echo "NEGATIVO · lo instalado apunta a current"
K09C_UNITS="$SANAS" caso "N1 las 7 units sanas" 0 "ejecutan /opt/coinalyze/current"

# N2 · ANTI-FALSO-CULPABLE. /opt/coinalyze-ai-bridge empieza igual que /opt/coinalyze y NO
# es el arbol de la app: es el TERCER arbol. Sin la barra en el prefijo saldria acusado.
# Este caso vale por si solo porque N1 pasaria igual si el ai-bridge no estuviera.
K09C_UNITS="coinalyze-api${T}{ path=/opt/coinalyze/current/.venv/bin/uvicorn }
coinalyze-daily${T}{ path=/opt/coinalyze/current/.venv/bin/python }
coinalyze-ws${T}{ path=/opt/coinalyze/current/.venv/bin/python }
coinalyze-ai-bridge${T}{ path=/opt/coinalyze-ai-bridge/.venv/bin/x ; argv[]=/opt/coinalyze-ai-bridge/.venv/bin/x }" \
  caso "N2 el ai-bridge NO cuenta como legacy" 0 "ejecutan /opt/coinalyze/current"

echo
echo "POSITIVO · las dos grietas REALES del reapuntado"
# P1 · GRIETA 1: una unit que no esta en ${SERVICES[@]} del wrapper nunca se reapunta.
K09C_UNITS="$SANAS
coinalyze-nueva${T}{ path=/opt/coinalyze/.venv/bin/python ; argv[]=/opt/coinalyze/.venv/bin/python -m app.nueva }" \
  caso "P1 unit fuera de SERVICES: sigue en legacy" 1 "coinalyze-nueva"

# P2 · GRIETA 2: el sed solo sustituye \${APP_ROOT}/.venv. Una ruta a scripts/ no la toca, y
# esa ruta viaja en argv[] porque el ejecutable es /bin/bash. Mirar solo path= la daria por
# buena: este caso es el que obliga a leer las DOS partes del ExecStart.
K09C_UNITS="coinalyze-api${T}{ path=/opt/coinalyze/current/.venv/bin/uvicorn }
coinalyze-daily${T}{ path=/opt/coinalyze/current/.venv/bin/python }
coinalyze-ws${T}{ path=/opt/coinalyze/current/.venv/bin/python }
coinalyze-backup${T}{ path=/bin/bash ; argv[]=/bin/bash /opt/coinalyze/scripts/backup.sh }" \
  caso "P2 ruta legacy escondida en argv[], no en path=" 1 "coinalyze-backup"

# P3 · /usr/bin/env delante: el ancla LEXICA del criterio viejo no veia estas.
K09C_UNITS="$SANAS
coinalyze-ws@0${T}{ path=/usr/bin/env ; argv[]=/usr/bin/env SHARD=0 /opt/coinalyze/.venv/bin/python -m app.ws_collector }" \
  caso "P3 ExecStart que empieza por /usr/bin/env" 1 "coinalyze-ws@0"

# P4 · el respaldo puede apuntar bien y no correr: el desplegador deja el release en 0640.
K09C_UNITS="$SANAS" K09C_RESULT="exit-code" \
  caso "P4 rutas buenas pero el respaldo fallo" 1 "acabo en 'exit-code'"

echo
echo "ANTI-FANTASMA · lo que no se puede medir es NOMED, jamas VERDE"
K09C_UNITS="$SANAS" caso "F1 el canal a 140 esta caido" 2 "no se pudieron leer" "$DIR/bin/prod-roto"

# F2 · CERO UNITS NO ES CERO DEFECTOS. Si el glob no encuentra nada, "0 a legacy" seria
# indistinguible de "no he mirado ninguna". Es la leccion de K60 aplicada al elegible.
K09C_UNITS="" caso "F2 ninguna unit instalada: sin sujeto" 2 "solo 0 unit"

K09C_UNITS="coinalyze-api${T}{ path=/opt/coinalyze/current/.venv/bin/uvicorn }
coinalyze-ws${T}{ path=/opt/coinalyze/current/.venv/bin/python }" \
  caso "F3 solo 2 units: por debajo del suelo, NOMED" 2 "solo 2 unit"

echo
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
