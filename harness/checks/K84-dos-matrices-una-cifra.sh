#!/bin/bash
# K84  EN UN MISMO SOBRE, DOS BLOQUES QUE PUBLICAN LA MISMA CIFRA NO DICEN LO MISMO.
#
# EL SUJETO CAMBIO EL 2026-09-28, Y ESO ES LO QUE PERMITE COMPARAR IMPORTES. Hasta hoy este
# check pedia DOS RUTAS -/api/cvd-matrix y /api/scalp/delta-matrix- y solo podia comparar
# PRESENCIA, porque entre dos peticiones hay DERIVA: el mercado se mueve, y una diferencia de
# importes no se puede atribuir a las rutas. Su cabecera lo decia y tenia razon.
# Ahora el sujeto es UN SOLO /api/ai/context. Los dos bloques viajan DENTRO del mismo sobre y
# cuelgan del MISMO as_of, asi que no hay deriva que excusar: si publican cifras distintas para
# la misma ventana y la misma pata, es un defecto y no el mercado.
#
# LO QUE DEJA DE VIGILARSE, DICHO: el cableado de las dos rutas SUELTAS (la tabla de #flujo del
# panel sale de /api/scalp/delta-matrix, static/js/07-decision-y-ciclos.js:325, con su propio
# corte). El CALCULO es el mismo -las dos rutas llaman a las mismas funciones que el sobre-, asi
# que lo que se pierde es la ruta, no la cifra.
#
# EL DEFECTO QUE LO TRAJO, medido por el operador en 140 el 2026-09-28: 48 sobres en reposo,
# 21 con delta_matrix y cvd_matrix publicando cifras DISTINTAS con el MISMO as_of, 126 de 432
# parejas, y la diferencia CONSTANTE en todas las ventanas de cada pata afectada (la mayor,
# 4 686 954.29 USD en los futuros de ETH). Reproducido por el implementador el mismo dia sobre
# el release ec62c97: 12 sobres entre las 17:48:48Z y las 17:50:06Z, 62 de 144 parejas.
# LA CAUSA no es ninguno de los dos bloques: es que UN as_of COMPARTIDO NO ES UN CORTE. Cada
# bloque lanza sus SELECT en un instante distinto contra una base que se escribe, y una fila con
# ts <= as_of que entra a mitad del armado la ve el tardio y no el temprano. Por eso este check
# empieza mirando si el sobre DECLARA haberse armado sobre una instantanea unica.
#
# LOS SIETE BRAZOS, y el VERDE exige A, B, C, D y E con F y G vivos:
#   A · EL CORTE DECLARADO. envelope_cut.snapshot == 'repeatable_read'. Sin eso, la igualdad de
#       B y D no es exigible: el sobre no promete un corte. Un sobre SIN el bloque es un sobre
#       anterior al 2026-09-28, y el mensaje distingue «no esta arreglado» de «falta desplegar».
#   B · VALOR. Emparejado por SEGUNDOS y no por etiqueta -las dos rutas llaman 24h y 1d a la
#       misma ventana- y POR PATA: spot y futuros. Si las dos traen cifra, es LA MISMA.
#   C · PRESENCIA, en LAS DOS PATAS. Hasta hoy este brazo solo miraba la de futuros (:118,:124
#       de la version anterior), que es justo por donde se colo el defecto del spot.
#   D · ESTRUCTURA. structure_horizons.<h> es copia de structure_detail.horizons.<h>: misma
#       structure, mismo close y misma barra de cierre.
#   E · BARRA CERRADA. Una barra que el sobre publica como cerrada tiene su ULTIMA vela de
#       origen; si no, su close es el de la vela anterior con la etiqueta de la barra entera.
#   F · CONTROL POSITIVO. Tiene que haber al menos una pareja con cifra en LAS DOS y al menos un
#       horizonte con estructura. Si no, no se distingue «coinciden» de «los dos estan mudos».
#   G · CASO VACIO. Sin ventanas comunes o sin horizontes no hay nada que comparar: NOMED.
#
# DE QUE ARBOL: K84_SUJETO=produccion (por defecto) mide 140 por la API; =espejo arma el sobre
# con el codigo de ESTA rama contra la base de 143; =fichero juzga un sobre ya escrito
# (K84_SOBRE), que es como lo ejercita su control con plantados.
#
# Se comprueba con: bash harness/checks/K84-dos-matrices-una-cifra.sh

set -u
B=/srv/coinanalyze/harness
. "$B/env"
: "${AYUDANTE_CARGADO:=}"
SIMBOLOS="${K84_SIMBOLOS:-BTCUSDT_PERP.A ETHUSDT_PERP.A SOLUSDT_PERP.A}"
SUJETO="${K84_SUJETO:-produccion}"
PERFIL="${K84_PERFIL:-max}"
PY="${PY:-$REPO/.venv/bin/python}"

# bin/api corta a 8000 bytes y eso ROMPE el JSON del sobre por la mitad.
export TODO=1
TMP=$(mktemp -d) || { echo "NO MEDIDO: no se pudo crear el temporal"; exit 2; }
trap 'rm -rf "$TMP"' EXIT

# El ROJO distingue "el arreglo no funciona" de "falta desplegar" (nota de K77, K80 y K83).
ARBOL_OK=0
grep -q '_corte_unico' "$REPO/app/ai_context.py" 2>/dev/null && ARBOL_OK=1

cat > "$TMP/motor.py" <<'PY'
import json, sys
from datetime import datetime, timedelta

SEG = {'15s':15,'30s':30,'1m':60,'3m':180,'5m':300,'15m':900,'18m':1080,'30m':1800,
       '1h':3600,'4h':14400,'8h':28800,'1d':86400,'24h':86400,'3d':259200,'7d':604800}
# Las dos rutas suman las MISMAS filas por caminos distintos (_cvd_src agrupa por exchange,
# _realtime_flow suma la ventana), asi que se admite el ultimo bit del float y nada mas.
def igual(a, b):
    return abs(a - b) <= max(1e-6, 1e-9 * max(abs(a), abs(b)))

rojos, lineas = [], []
parejas = coinciden = horizontes = con_estructura = barras = 0
sin_corte = []

for ruta in sys.argv[1:]:
    try:
        p = json.load(open(ruta))
    except Exception as e:
        print('NOMED|no se pudo parsear %s: %s' % (ruta, e)); raise SystemExit
    sym = p.get('symbol') or ruta

    # --- A · el corte declarado
    corte = p.get('envelope_cut')
    if not isinstance(corte, dict):
        sin_corte.append('%s: el sobre no trae envelope_cut' % sym)
    elif corte.get('snapshot') != 'repeatable_read':
        sin_corte.append('%s: envelope_cut.snapshot=%r (%s)'
                         % (sym, corte.get('snapshot'), corte.get('snapshot_reason')))

    cvd = p.get('cvd_matrix') or {}
    delta = p.get('delta_matrix')
    if not isinstance(delta, list):
        print('NOMED|delta_matrix no es una lista en %s' % sym); raise SystemExit
    c = {}
    for lab, w in (cvd.get('windows') or {}).items():
        sec = w.get('window_seconds') or SEG.get(lab)
        if sec:
            c[sec] = (lab, w)
    d = {}
    for r in delta:
        sec = SEG.get(r.get('window'))
        if sec:
            d[sec] = (r.get('window'), r)
    for sec in sorted(set(c) & set(d)):
        cl, cw = c[sec]
        dl, dr = d[sec]
        patas = (
            ('spot', cw.get('spot'), dr.get('spot_delta'),
             (cw.get('spot_status') or {}).get('reason'), dr.get('spot_coverage_status')),
            ('futuros', cw.get('futures'), dr.get('fut_delta'),
             (cw.get('futures_status') or {}).get('reason'), dr.get('futures_coverage_status')),
        )
        for pata, cv, dv, cr, dc in patas:
            parejas += 1
            if (cv is None) != (dv is None):
                # --- C · presencia
                rojos.append('C · %s %s/%s(%ds).%s: cvd=%s delta=%s · el que calla dice %r/%r'
                             % (sym, cl, dl, sec, pata,
                                'CIFRA' if cv is not None else 'null',
                                'CIFRA' if dv is not None else 'null', cr, dc))
            elif cv is not None:
                coinciden += 1
                if not igual(cv, dv):
                    # --- B · valor
                    rojos.append('B · %s %s/%s(%ds).%s: cvd=%r delta=%r dif=%+.4f'
                                 % (sym, cl, dl, sec, pata, cv, dv, cv - dv))

    # --- D · estructura
    sd = ((p.get('structure_detail') or {}).get('horizons')) or {}
    sh = p.get('structure_horizons') or {}
    for h, v in sorted(sh.items()):
        o = sd.get(h)
        if not isinstance(o, dict):
            rojos.append('D · %s %s: structure_horizons publica un horizonte que '
                         'structure_detail no tiene' % (sym, h))
            continue
        horizontes += 1
        if v.get('structure') is not None:
            con_estructura += 1
        for campo, a, b in (('structure', v.get('structure'), o.get('state')),
                            ('close', v.get('close'), o.get('close')),
                            ('close_bar_start', v.get('close_bar_start'),
                             o.get('close_bar_start'))):
            if a != b:
                rojos.append('D · %s %s.%s: structure_horizons=%r contra '
                             'structure_detail=%r' % (sym, h, campo, a, b))

    # --- E · barra cerrada con su dato
    for h, o in sorted(sd.items()):
        if (o.get('group') or '') != 'med':
            continue
        ini, secs = o.get('close_bar_start'), o.get('close_bar_seconds')
        ult = o.get('close_source_last_ts')
        if not ini or not secs:
            if o.get('state') is not None or o.get('close') is not None:
                rojos.append('E · %s %s: publica una estructura sin decir de que barra sale '
                             '(no hay close_bar_start/close_bar_seconds)' % (sym, h))
            continue
        barras += 1
        if not ult:
            rojos.append('E · %s %s: barra %s (+%ss) sin close_source_last_ts' % (sym, h, ini, secs))
            continue
        b0 = datetime.fromisoformat(ini)
        u = datetime.fromisoformat(ult)
        # 60 s = la vela de origen mas fina que se remuestrea (ohlcv 1min).
        if u < b0 + timedelta(seconds=int(secs)) - timedelta(seconds=60):
            rojos.append('E · %s %s: publica como CERRADA la barra %s (+%ss) cuya ultima vela '
                         'es %s: el close es el de la vela anterior' % (sym, h, ini, secs, ult))

lineas.append('A corte: %d sobre(s) sin instantanea unica' % len(sin_corte))
lineas.append('B/C %d parejas ventana-pata, %d con cifra en LAS DOS' % (parejas, coinciden))
lineas.append('D %d horizontes emparejados, %d con estructura no nula' % (horizontes, con_estructura))
lineas.append('E %d barra(s) intradia con su barra de cierre declarada' % barras)

# --- G · caso vacio
if parejas == 0:
    print('NOMED|0 parejas ventana-pata comunes entre delta_matrix y cvd_matrix'); raise SystemExit
if horizontes == 0:
    print('NOMED|0 horizontes comunes entre structure_horizons y structure_detail'); raise SystemExit
# --- F · control positivo
if coinciden == 0:
    print('NOMED|NINGUNA de las %d parejas trae cifra en LAS DOS rutas: sin un solo acuerdo no '
          'se distingue "discrepan" de "las dos estan mudas"' % parejas); raise SystemExit
if con_estructura == 0:
    print('NOMED|ninguno de los %d horizontes trae estructura: D no puede distinguir "copia '
          'fiel" de "los dos nulos"' % horizontes); raise SystemExit

print('OK|%s|%s|%s' % (json.dumps(sin_corte), json.dumps(rojos), json.dumps(lineas)))
PY

# ---- el sobre de PRODUCCION
produccion() {
  ok=1
  for S in $SIMBOLOS; do
    C=${S%%USDT*}
    "$B/bin/api" "/api/ai/context?symbol=$S&profile=$PERFIL" > "$TMP/$C.json" 2>"$TMP/$C.err" || ok=0
    [ -s "$TMP/$C.json" ] || ok=0
  done
  [ "$ok" = 1 ]
}

# ---- el sobre del ESPEJO: el codigo de ESTA rama contra la base de 143.
# SOLO SELECT, y no se importa app.db: `app.db.create_pool` ESCRIBE en market_assets y symbols
# y crea particiones por DDL. Se conecta con asyncpg a pelo.
espejo() {
  cat > "$TMP/mojado.py" <<'PY'
import asyncio, json, sys
sys.path.insert(0, sys.argv[1])
import asyncpg

async def main():
    from app import ai_context
    conn = await asyncpg.connect(sys.argv[4])
    try:
        p = await ai_context.build_ai_symbol_context(conn, sys.argv[2], profile=sys.argv[5])
    finally:
        await conn.close()
    json.dump(p, open(sys.argv[3], "w"), default=str, ensure_ascii=False)

asyncio.run(main())
PY
  ok=1
  for S in $SIMBOLOS; do
    C=${S%%USDT*}
    "$PY" "$TMP/mojado.py" "$REPO" "$S" "$TMP/$C.json" \
      "postgresql:///${ESPEJO_DB:-coinalyze_espejo}?host=/var/run/postgresql" "$PERFIL" \
      2>"$TMP/$C.err" || ok=0
    [ -s "$TMP/$C.json" ] || ok=0
  done
  [ "$ok" = 1 ]
}

case "$SUJETO" in
  fichero)
    [ -n "${K84_SOBRE:-}" ] || { echo "NO MEDIDO: K84_SUJETO=fichero exige K84_SOBRE"; exit 2; }
    SOBRES="$K84_SOBRE"
    QUIEN="fichero ($K84_SOBRE)"
    ;;
  espejo)
    espejo || {
      echo "NO MEDIDO: no se pudo armar el sobre contra la base espejo"
      echo "  (${ESPEJO_DB:-coinalyze_espejo}): $(tail -1 "$TMP"/*.err 2>/dev/null | head -1)"
      exit 2
    }
    SOBRES=$(ls "$TMP"/*.json)
    QUIEN="espejo (143 · ${ESPEJO_DB:-coinalyze_espejo}, codigo de $(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo '?'))"
    ;;
  produccion)
    produccion || {
      echo "NO MEDIDO: /api/ai/context no contesto en 140 ($(tail -1 "$TMP"/*.err 2>/dev/null | head -1))"
      exit 2
    }
    SOBRES=$(ls "$TMP"/*.json)
    QUIEN="produccion (140 · $("$B/bin/prod" 'readlink -f /opt/coinalyze/current' 2>/dev/null | xargs -r basename | cut -c1-7))"
    ;;
  *)
    echo "NO MEDIDO: K84_SUJETO='$SUJETO' no es 'produccion', 'espejo' ni 'fichero'."
    exit 2
    ;;
esac

VER=$("$PY" "$TMP/motor.py" $SOBRES 2>"$TMP/motor.err")
case "$VER" in
  NOMED\|*) echo "NO MEDIDO: ${VER#NOMED|} [$QUIEN]"; exit 2 ;;
  OK\|*) : ;;
  *) echo "NO MEDIDO: el motor no produjo veredicto [$QUIEN]: $(tail -1 "$TMP/motor.err")"; exit 2 ;;
esac

"$PY" - "$QUIEN" "$ARBOL_OK" <<PY
import json, sys
quien, arbol_ok = sys.argv[1], sys.argv[2] == "1"
_, sin_corte, rojos, lineas = """$VER""".split("|", 3)
sin_corte, rojos, lineas = json.loads(sin_corte), json.loads(rojos), json.loads(lineas)
faltan = (" · EL ARBOL YA LO TIENE ARREGLADO (existe _corte_unico en app/ai_context.py): "
          "falta DESPLEGAR") if arbol_ok else ""
if sin_corte:
    print("ROJO [%s]: el sobre no se armo sobre UNA instantanea, asi que no puede prometer "
          "que dos bloques digan lo mismo. %s%s" % (quien, sin_corte[0], faltan))
    for s in sin_corte[1:]:
        print("   A · %s" % s)
    for r in rojos:
        print("   %s" % r)
    print("   --- lo que si se miro ---")
    for l in lineas:
        print("   %s" % l)
    raise SystemExit(1)
if rojos:
    print("ROJO [%s]: %d pareja(s) del MISMO sobre publican la misma cantidad y no dicen lo "
          "mismo. %s%s" % (quien, len(rojos), rojos[0], faltan))
    for r in rojos[1:]:
        print("   %s" % r)
    print("   --- lo que si se miro ---")
    for l in lineas:
        print("   %s" % l)
    raise SystemExit(1)
print("en el MISMO sobre, los bloques que publican la misma cantidad dicen lo mismo [%s] · %s"
      % (quien, " · ".join(lineas)))
PY
