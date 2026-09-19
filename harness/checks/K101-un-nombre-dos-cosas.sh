#!/bin/bash
# K101  DOS CAMPOS CON EL MISMO NOMBRE PARA EL MISMO HORIZONTE, Y OTRA DEFINICION.
#
# EL DEFECTO QUE LO TRAJO, medido en produccion el 2026-09-18 a las 23:42Z con
# `profile=max` sobre los tres simbolos. En EL MISMO sobre, para EL MISMO dia:
#     structure_horizons.1d.bias       bajista      structure_horizons.1d.structure  LH_LL
#     trend_matrix.timeframes.1d.bias  alcista      trend_matrix.timeframes.1d.structure  mixed
# De las 15 parejas de `bias` (5 horizontes x 3 simbolos): 4 OPUESTAS -una alcista y la
# otra bajista-, 9 con una nula y la otra con direccion, 1 iguales, 1 distintas sin ser
# opuestas. Ninguna de las dos cifras esta mal: son dos calculos distintos con el mismo
# nombre, y el sobre no lo decia en ninguna parte. Lo leen el bridge de 140, la skill de
# la mesa y quien pega el sobre en una IA por web.
#
# LO QUE ESTE CHECK *NO* JUZGA, dicho antes que lo que si: NO compara valores entre
# bloques y NO dice cual tiene razon. Que discrepen es correcto. Lo que se condena es que
# el sobre no lo declare. Tampoco mira la pantalla: eso es de quien lea el panel.
#
# EL SUJETO SE ELIGE Y SE DICE EN CADA LINEA (K101_SUJETO):
#   arbol       (por defecto) el sobre se CONSTRUYE en proceso con el codigo de ESTA rama
#               y una conexion que no contesta nada. Sale la FORMA del sobre -que claves
#               existen- con entradas fijas y sin red. NO abre el pool: `app.db.create_pool`
#               ESCRIBE en market_assets y symbols y crea particiones por DDL, asi que no
#               se importa; se llama a build_ai_symbol_context con un doble de conexion.
#   produccion  el sobre de 140 por /api/ai/context. Es el producto de verdad, pero es el
#               RELEASE desplegado: si sale ROJO y el arbol sale VERDE, lo que falta es
#               desplegar, y la linea lo dice con esas palabras.
#   espejo      no existe como sujeto y se dice: el espejo de 143 es una BASE, no una API,
#               y ademas esta vacia -medido el 2026-09-18: `symbols` 6 filas y el resto a
#               cero-, asi que un sobre construido contra ella no tendria valores.
#
# EL INVENTARIO DEL BRAZO DEL PROMPT SE AMPLIA A PROPOSITO. Un sobre construido contra una
# base vacia NO trae las claves de los bloques que dependen de datos -medido: con la base
# seca faltan oi_context.zscore_1y, snapshot.regime_score y seis mas que en produccion SI
# estan-. Juzgar el prompt solo contra el sobre seco condenaria citas correctas. Por eso,
# cuando el canal de produccion contesta, el brazo D juzga el prompt DEL ARBOL contra las
# claves del arbol MAS las de produccion: una cita vale si existe en el producto de hoy o
# en lo que esta rama anade. Sin canal, el brazo D lo dice y no condena por lo que no pudo
# mirar (A54).
#
# LOS CINCO BRAZOS y sus controles positivos estan en la cabecera de K101-homonimos.py.
#
# Se comprueba con:  bash harness/checks/K101-un-nombre-dos-cosas.sh
#          y control: bash harness/checks/K101-control.bash

set -u
# LA RUTA DEL CHECK SE RESUELVE A ABSOLUTA ANTES DE NADA (A56): este guion se invoca por
# ruta absoluta desde verify, por ruta relativa a mano y desde cualquier directorio, y un
# `python3 checks/...` relativo mediria otra cosa -o nada- segun desde donde se lance.
AQUI=$(cd "$(dirname "$0")" && pwd)
B=${VERIFY_HARNESS:-/srv/coinanalyze/harness}
[ -f "$B/env" ] && . "$B/env"
REPO=${REPO:-/srv/coinanalyze/repo}
SUJETO=${K101_SUJETO:-arbol}
SIMBOLO=${K101_SIMBOLO:-BTCUSDT_PERP.A}
MOTOR="$AQUI/K101-homonimos.py"
PY="$REPO/.venv/bin/python"

[ -f "$MOTOR" ] || { echo "NO MEDIDO: no esta el motor $MOTOR"; exit 2; }
[ -x "$PY" ] || PY=$(command -v python3) || {
  echo "NO MEDIDO: no hay interprete de python para correr el motor"; exit 2; }

TMP=$(mktemp -d) || { echo "NO MEDIDO: no se pudo crear el temporal"; exit 2; }
trap 'rm -rf "$TMP"' EXIT

# ---- el sobre del ARBOL, construido en proceso y sin base de datos.
seco() {
  cat > "$TMP/seco.py" <<'PY'
import asyncio, json, sys
from datetime import UTC, datetime
sys.path.insert(0, sys.argv[1])
CORTE = datetime(2026, 1, 1, tzinfo=UTC)

class Fila(dict):
    # Una fila que EXISTE y no trae nada: `if fila:` sigue siendo falso, `dict(fila)` da {}
    # y `fila["x"]` da None en vez de KeyError. Sin esto el armado muere en
    # scalp_liquidations, que hace dict(row) sin guarda.
    def __missing__(self, _k):
        return None

class Seca:
    async def fetch(self, *_a, **_k):
        return []
    async def fetchrow(self, *_a, **_k):
        return Fila()
    async def fetchval(self, q, *_a, **_k):
        # resolve_matrix_as_of EXIGE un datetime; el resto puede ser None.
        return CORTE if "clock_timestamp" in str(q) else None

async def main():
    from app import ai_context
    p = await ai_context.build_ai_symbol_context(Seca(), sys.argv[2], profile="max")
    json.dump(p, open(sys.argv[3], "w"), default=str, ensure_ascii=False)

asyncio.run(main())
PY
  "$PY" "$TMP/seco.py" "$REPO" "$SIMBOLO" "$TMP/arbol.json" 2>"$TMP/seco.err"
}

# ---- el sobre de PRODUCCION. TODO=1 porque bin/api corta a 8 KB y partiria el JSON.
produccion() {
  ( export TODO=1
    "$B/bin/api" "/api/ai/context?symbol=$SIMBOLO&profile=max" ) > "$TMP/prod.json" 2>"$TMP/prod.err"
  [ -s "$TMP/prod.json" ] && "$PY" -c "import json,sys; json.load(open(sys.argv[1]))" "$TMP/prod.json" 2>/dev/null
}

case "$SUJETO" in
  espejo)
    echo "NO MEDIDO: 'espejo' no es un sujeto de K101. El espejo de 143 es una BASE, no"
    echo "una API, y ademas no tiene datos: un sobre construido contra ella no traeria"
    echo "valores. Usa K101_SUJETO=arbol (por defecto) o K101_SUJETO=produccion."
    exit 2
    ;;
  arbol)
    seco || {
      echo "NO MEDIDO: no se pudo construir el sobre del arbol en proceso ($(tail -1 "$TMP/seco.err" 2>/dev/null))"
      exit 2
    }
    EXTRA=""
    if produccion; then
      EXTRA="$TMP/prod.json"
    else
      echo "AVISO: el canal de produccion no contesto; el brazo D juzga el prompt SOLO"
      echo "contra el sobre seco del arbol, que no trae las claves de los bloques que"
      echo "dependen de datos. Lo que no pueda resolver lo dira sin condenar."
    fi
    # shellcheck disable=SC2086
    "$PY" "$MOTOR" "arbol ($(git -C "$REPO" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')@$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo '?'))" "$TMP/arbol.json" $EXTRA
    RC=$?
    ;;
  produccion)
    produccion || {
      echo "NO MEDIDO: /api/ai/context no devolvio un JSON legible ($(head -1 "$TMP/prod.err" 2>/dev/null))"
      exit 2
    }
    "$PY" "$MOTOR" "produccion (140)" "$TMP/prod.json"
    RC=$?
    # SI PRODUCCION CONDENA Y EL ARBOL NO, LO QUE FALTA ES DESPLEGAR, y se dice con esas
    # palabras en vez de dejar que alguien busque un defecto que ya esta arreglado.
    if [ "$RC" = "1" ] && seco && "$PY" "$MOTOR" arbol "$TMP/arbol.json" "$TMP/prod.json" >/dev/null 2>&1; then
      echo "   FALTA DESPLEGAR: este ROJO es del RELEASE de 140. El arbol de esta rama"
      echo "   ($(git -C "$REPO" rev-parse --short HEAD 2>/dev/null)) pasa el mismo criterio; lo que falta es el despliegue."
    fi
    ;;
  *)
    echo "NO MEDIDO: K101_SUJETO='$SUJETO' no existe. Son 'arbol' o 'produccion'."
    exit 2
    ;;
esac
exit "$RC"
