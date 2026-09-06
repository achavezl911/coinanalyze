#!/usr/bin/env bash
# K93-control · ¿el check caza el defecto que motivo su existencia?
#
# El control positivo estaba escrito antes que el check: el recorte de la migracion
# incrustada -que la CI aprobo y que el operador tuvo que revocar el 2026-09-06- tiene que
# hacerlo enrojecer. Si no lo hiciera, K93 no serviria para lo unico que se le pide.
#
# Y el negativo, sin el cual el positivo no vale: sobre el arbol sano tiene que ser VERDE, y
# tiene que seguir siendolo cuando se le cambia algo que NO afecta al camino de actualizacion.
set -uo pipefail
ORIG=${REPO:-/srv/coinanalyze/repo}
CHK="$ORIG/harness/checks/K93-el-camino-de-actualizacion.sh"
[ -r "$CHK" ] || { echo "NO MEDIDO: no encuentro el check en $CHK"; exit 2; }
command -v psql >/dev/null 2>&1 || { echo "NO MEDIDO: no hay psql"; exit 2; }

DIR=$(mktemp -d) || exit 2
[ "${K93_CONTROL_GUARDA:-0}" = "1" ] || trap 'rm -rf "$DIR"' EXIT
fallos=0; pasan=0

# EL ARBOL DE MENTIRA ES UNA COPIA CON SU .git: el check deriva el esquema previo del
# historial, asi que sin historial no puede medir -y ese es tambien un caso-.
SANO="$DIR/sano"
mkdir -p "$SANO/sql/migrations" "$SANO/harness/checks"
cp "$ORIG/sql/schema.sql" "$SANO/sql/"
cp "$ORIG/sql/migrations/20260809_temporal_partitioning.sql" "$SANO/sql/migrations/"
cp "$CHK" "$SANO/harness/checks/"
# el historial de verdad: se clona solo lo que hace falta para que `git log` resuelva.
cp -r "$ORIG/.git" "$SANO/.git" 2>/dev/null || { echo "NO MEDIDO: no puedo copiar .git"; exit 2; }

caso() {  # <nombre> <rc esperado> <patron> <arbol>
  local nombre="$1" esperado="$2" patron="$3" arbol="$4" out rc ok=1
  out=$(REPO="$arbol" K93_PREFIJO="k93c_$$_$RANDOM" bash "$CHK" 2>&1); rc=$?
  [ "$rc" = "$esperado" ] || ok=0
  if [ -n "$patron" ] && ! printf '%s' "$out" | grep -qE "$patron"; then ok=0; fi
  if [ "$ok" = 1 ]; then
    pasan=$((pasan+1)); printf '  [ok   ] %-54s rc=%s\n' "$nombre" "$rc"
  else
    fallos=$((fallos+1))
    printf '  [FALLA] %-54s rc=%s (esperaba %s, patron /%s/)\n      %s\n' \
      "$nombre" "$rc" "$esperado" "$patron" "$(printf '%s' "$out" | head -2 | tr '\n' ' ' | cut -c1-160)"
  fi
}

echo "K93-control · sujeto: $CHK"
echo "  (cada caso crea y tira dos bases desechables)"
echo

echo "NEGATIVO · el arbol sano no puede enrojecer"
caso "N1 el esquema tal cual" 0 "sobreviven al de ACTUALIZACION" "$SANO"

# N2 · un cambio ADITIVO fuera de la region no afecta al camino de actualizacion.
ADI="$DIR/aditivo"; cp -r "$SANO" "$ADI"
printf '\nCREATE TABLE IF NOT EXISTS zzz_k93_control (id int);\n' >> "$ADI/sql/schema.sql"
caso "N2 una tabla nueva al final: sigue VERDE" 0 "sobreviven al de ACTUALIZACION" "$ADI"

echo
echo "POSITIVO · EL DEFECTO QUE MOTIVO EL CHECK"
# P1 · EL RECORTE QUE LA CI APROBO Y HUBO QUE REVOCAR. Se quita la migracion incrustada
# entera. En vacio no se nota -y por eso la CI lo dejo pasar-; por el camino de
# ACTUALIZACION la tabla viva se queda sin su trigger de unicidad.
ROTO="$DIR/roto"; cp -r "$SANO" "$ROTO"
python3 - "$ROTO" <<'PY'
import sys
from pathlib import Path
t = Path(sys.argv[1])
schema = (t / "sql/schema.sql").read_text(encoding="utf-8")
mig = (t / "sql/migrations/20260809_temporal_partitioning.sql").read_text(encoding="utf-8").strip()
i = schema.index(mig)
(t / "sql/schema.sql").write_text(schema[:i] + schema[i + len(mig):], encoding="utf-8")
PY
caso "P1 sin la migracion incrustada: ROJO" 1 "NO tras el camino de ACTUALIZACION" "$ROTO"
caso "P2 y nombra el trigger que se pierde" 1 "liquidations_realtime_event_unique_trigger" "$ROTO"

echo
echo "ANTI-FANTASMA · lo que no se puede medir es NOMED, jamas VERDE"
SINGIT="$DIR/singit"; cp -r "$SANO" "$SINGIT"; rm -rf "$SINGIT/.git"
caso "F1 sin historial: no hay esquema previo, NOMED" 2 "que commit anadio" "$SINGIT"

SINMIG="$DIR/sinmig"; cp -r "$SANO" "$SINMIG"; rm -f "$SINMIG/sql/migrations/20260809_temporal_partitioning.sql"
caso "F2 sin el fichero de migracion: NOMED" 2 "falta sql/migrations" "$SINMIG"

echo
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
