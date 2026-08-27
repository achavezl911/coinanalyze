#!/bin/bash
# K58  UN VEREDICTO NO PUEDE SER UNA RAZON CONTRA UN CERO.
#
# El resultado del walk-forward no es "la ventana de prueba gano dinero": es una
# COMPARACION contra la ventana de descubrimiento. app/signal_walk_forward.py:1994
# retention_ratio = test/discovery y :1995 sign_preserved = (discovery>0)==(test>0).
# Medida la base del fold 1, NO SE DISTINGUE DE CERO. Asi que hoy el evaluador divide
# por un denominador nulo y compara el signo de una moneda al aire, y lo sirve como un
# numero sin decir que lo es.
#
# --- POR QUE HACE FALTA ADEMAS LA n EFECTIVA, Y NO SOLO EL PORTON -------------------
# El manifiesto declara DOS modos de muestreo y el evaluador ya calcula los dos
# (:2509 for mode in options.sampling_modes). En dense_periodic las ventanas SE SOLAPAN:
# hay una observacion por minuto y una ventana de h minutos, o sea ~h ventanas por cada
# hueco independiente. Medido en 140 sobre el fold 1, ventana de PRUEBA, h=15: la |t|
# ingenua da 4.68 BTC / 4.80 ETH / 2.71 SOL y la corregida por solapamiento 1.91 / 1.96
# / 1.24. La ingenua cruza el liston y la real no. Y crece con el horizonte por puro
# solapamiento -h=60 llega a 11.07 ingenua contra 1.43 corregida-, o sea que cuanto mas
# largo el horizonte mas seguro PARECE el resultado. Un error estandar sin n efectiva
# no es un error estandar: es el mismo enganno con una cifra al lado.
#
# LA n EFECTIVA SE MIDE, NO SE ESTIMA: es el numero de huecos no solapados distintos que
# ocupan las filas del grupo, (symbol, floor(minuto/h)). Para utc_nonoverlap sale igual a
# n por construccion, que es la comprobacion de que la definicion es la correcta. Contra
# la medicion independiente del operador -14.98 observaciones por simbolo y bloque de 15
# min- este check da 4017/671 = 5.99 ... no: da la misma razon sobre el mismo dato.
#
# LO QUE EXIGE
#   1 · CONTRATO. Cada bloque de estadisticas con n>0 declara expectancy_std_error_pct
#       finito y n_effective entero con 1 <= n_effective <= n. Sin las dos cifras, "no
#       se distingue de cero" no es expresable y el lector no tiene con que juzgar.
#   2 · PORTON. Cuando la BASE no se distingue de cero al umbral que el propio modulo
#       declara, expectancy_retention_ratio y sign_preserved salen None -no un numero- y
#       el bloque dice POR QUE con un motivo legible.
#   3 · CON LOS DATOS DE HOY. Las tres celdas de h=15 del fold 1 tienen base |t| 0.23
#       BTC / 0.24 ETH / 0.52 SOL: las tres tienen que salir no concluyentes.
#   CONTROL POSITIVO, obligatorio y con dato REAL: en h=1 no hay solapamiento y la base
#       SI se distingue -6.79 BTC y 4.26 ETH-, asi que esas dos celdas tienen que dar un
#       retention_ratio NUMERICO y un sign_preserved booleano. Un check que declare todo
#       no concluyente no mide nada. Y en el MISMO horizonte SOL da 0.52 y tiene que
#       salir no concluyente: el porton discrimina dentro de la misma pasada, no por
#       horizonte.
#
# ALCANCE, dicho para que nadie lo lea de mas: esto prueba la CAPA DE VEREDICTO con las
# funciones reales del modulo. El SQL de abajo reproduce las condiciones de elegibilidad
# del evaluador (signal_family, is_periodic, logic_version, sampling_version,
# frame.context_version, outcome_version, status, actionable, direction, window_end
# dentro del periodo) pero NO es la funcion de fetch del evaluador. Lo que se juzga es
# que hace el modulo con filas validas, no como las trae.
#
# DE QUE ARBOL: las filas salen de 140 (prodsql, solo lectura). El espejo de 143 no
# sirve para esto y esta medido: solo llega al 2026-08-13 con 32144 observaciones, y las
# dos ventanas del fold 1 terminan el 08-24. El codigo bajo prueba sale del repo de 143.
set -uo pipefail
B=/srv/coinanalyze/harness
REPO=/srv/coinanalyze/repo

DESCUB_INI='2026-08-10T17:22:00.805335Z'
CORTE='2026-08-17T23:05:00Z'
PRUEBA_FIN='2026-08-24T23:05:00Z'

filas=$(TODO=1 "$B/bin/prodsql" "
SELECT obs.symbol,
       floor(extract(epoch FROM obs.observed_at)/60.0)::bigint AS minuto,
       out.horizon_minutes, obs.state, obs.direction, obs.regime_label,
       out.directional_return_pct, out.mfe_pct, out.mae_pct,
       CASE WHEN obs.observed_at < '$CORTE' THEN 'D' ELSE 'P' END AS ventana
FROM signal_observation obs
JOIN signal_replay_frame frame ON frame.observation_id = obs.observation_id
JOIN signal_outcome out ON out.observation_id = obs.observation_id
WHERE obs.signal_family='scalp' AND obs.is_periodic
  AND obs.logic_version='scalp-summary-v1' AND obs.sampling_version=1
  AND frame.context_version=1
  AND out.outcome_version=1 AND out.status='evaluated'
  AND obs.actionable AND obs.direction IN ('long','short')
  AND out.horizon_minutes IN (1,15)
  AND obs.observed_at >= '$DESCUB_INI' AND obs.observed_at < '$PRUEBA_FIN'
  AND out.window_end <= CASE WHEN obs.observed_at < '$CORTE'
                             THEN TIMESTAMPTZ '$CORTE' ELSE TIMESTAMPTZ '$PRUEBA_FIN' END
" 2>&1)
rc=$?
if [ $rc -ne 0 ] || [ -z "$filas" ]; then
  echo "NO MEDIDO: 140 no devolvio filas del fold 1 (rc=$rc). $(printf '%s' "$filas" | head -1)"
  exit 2
fi

PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || { echo "NO MEDIDO: falta el venv del repo en $PY"; exit 2; }

printf '%s\n' "$filas" | PYTHONPATH="$REPO" "$PY" -c '
import sys, math
from datetime import UTC, datetime

sys.path.insert(0, "'"$REPO"'")
import app.signal_walk_forward as wf
from app.signal_execution import DENSE_PERIODIC, UTC_NONOVERLAP

def num(s):
    return None if s == "" else float(s)

grids = {"D": [], "P": []}
for linea in sys.stdin.read().splitlines():
    if not linea.strip():
        continue
    p = linea.split("|")
    if len(p) != 10:
        continue
    sym, minuto, h, estado, direccion, regimen, ret, mfe, mae, ventana = p
    grids[ventana].append({
        "symbol": sym,
        "observed_minute": datetime.fromtimestamp(int(minuto) * 60, tz=UTC),
        "horizon_minutes": int(h),
        "state": estado or None,
        "direction": direccion,
        "regime_label": regimen or None,
        "directional_return_pct": num(ret),
        "mfe_pct": num(mfe),
        "mae_pct": num(mae),
        "usable": True,
        "status": "evaluated",
        "actionable": True,
    })

if not grids["D"] or not grids["P"]:
    print("NO MEDIDO: falta una de las dos ventanas (D=%d P=%d)" % (len(grids["D"]), len(grids["P"])))
    sys.exit(2)

fallos = []

# --- 1 · CONTRATO: el umbral tiene que estar DECLARADO en el modulo -------------------
umbral = getattr(wf, "BASE_SIGNIFICANCE_T", None)
if umbral is None:
    fallos.append("el modulo no declara BASE_SIGNIFICANCE_T: no hay umbral contra el que "
                  "decidir si la base se distingue de cero, asi que el porton no existe")

vistas = {}
for modo in (DENSE_PERIODIC, UTC_NONOVERLAP):
    vistas[modo] = wf._build_gross_views(
        discovery_grid=wf._sample_grid(grids["D"], modo),
        test_grid=wf._sample_grid(grids["P"], modo),
        min_group_n=wf.DEFAULT_MIN_GROUP_N,
        fold_state="ready_by_clock",
    )

# --- 2 · CONTRATO: error estandar y n efectiva en cada bloque -------------------------
sin_error, sin_neff, neff_mala = 0, 0, 0
for modo, v in vistas.items():
    for celda in v["overall"]:
        for lado in ("discovery", "test"):
            st = celda[lado]
            if st["n"] == 0:
                continue
            se = st.get("expectancy_std_error_pct")
            neff = st.get("n_effective")
            if se is None or not isinstance(se, float) or not math.isfinite(se):
                sin_error += 1
            if not isinstance(neff, int) or isinstance(neff, bool):
                sin_neff += 1
            elif not (1 <= neff <= st["n"]):
                neff_mala += 1
            elif modo == UTC_NONOVERLAP and neff != st["n"]:
                neff_mala += 1
if sin_error:
    fallos.append("%d bloques con n>0 no declaran expectancy_std_error_pct finito" % sin_error)
if sin_neff:
    fallos.append("%d bloques con n>0 no declaran n_effective entera" % sin_neff)
if neff_mala:
    fallos.append("%d bloques con n_effective fuera de rango o distinta de n en "
                  "utc_nonoverlap, donde no hay solapamiento que corregir" % neff_mala)

# --- 3 · EL PORTON, sobre dense_periodic, que es el modo que hoy se lee ---------------
CONCLUYENTES = {("BTCUSDT_PERP.A", 1), ("ETHUSDT_PERP.A", 1)}
NO_CONCLUYENTES = {("BTCUSDT_PERP.A", 15), ("ETHUSDT_PERP.A", 15),
                   ("SOLUSDT_PERP.A", 15), ("SOLUSDT_PERP.A", 1)}
vistos = {}
for celda in vistas[DENSE_PERIODIC]["overall"]:
    clave = (celda["symbol"], celda["horizon_minutes"])
    if clave in CONCLUYENTES or clave in NO_CONCLUYENTES:
        vistos[clave] = celda

faltan = (CONCLUYENTES | NO_CONCLUYENTES) - set(vistos)
if faltan:
    print("NO MEDIDO: el fold 1 ya no sirve estas celdas: %s" %
          ", ".join("%s/h%d" % c for c in sorted(faltan)))
    sys.exit(2)

def t_de(st):
    se = st.get("expectancy_std_error_pct")
    m = st.get("expectancy_gross_pct")
    if se in (None, 0) or m is None or not isinstance(se, float):
        return None
    return abs(m) / se

for clave in sorted(NO_CONCLUYENTES):
    c = vistos[clave]
    t = t_de(c["discovery"])
    if c["expectancy_retention_ratio"] is not None or c["sign_preserved"] is not None:
        fallos.append("%s/h%d: base con |t|=%s y AUN ASI sirve retention_ratio=%s "
                      "sign_preserved=%s" % (clave[0], clave[1],
                      "no declarada" if t is None else round(t, 2),
                      c["expectancy_retention_ratio"], c["sign_preserved"]))
    elif not c.get("base_inconclusive_reason"):
        fallos.append("%s/h%d: no sirve el numero pero tampoco dice por que "
                      "(falta base_inconclusive_reason)" % clave)

# --- 4 · CONTROL POSITIVO: h=1 no solapa y la base SI se distingue --------------------
for clave in sorted(CONCLUYENTES):
    c = vistos[clave]
    t = t_de(c["discovery"])
    if c["expectancy_retention_ratio"] is None or c["sign_preserved"] is None:
        fallos.append("CONTROL POSITIVO ROTO: %s/h%d tiene base |t|=%s, se distingue de "
                      "cero, y aun asi el porton se la traga" % (clave[0], clave[1],
                      "no declarada" if t is None else round(t, 2)))

if fallos:
    print("ROJO: " + fallos[0])
    for f in fallos[1:]:
        print("      " + f)
    sys.exit(1)

resumen = []
for clave in sorted(CONCLUYENTES | NO_CONCLUYENTES):
    c = vistos[clave]
    t = t_de(c["discovery"])
    r = c["expectancy_retention_ratio"]
    resumen.append("%s/h%d |t|=%.2f %s" % (clave[0][:3], clave[1], t,
                   "NO CONCLUYENTE" if r is None else "ratio=%.3f" % r))
n_d = sum(1 for c in vistas[DENSE_PERIODIC]["overall"])
print("VERDE: %d celdas juzgadas con umbral |t|>=%s; %s" % (n_d, umbral, " · ".join(resumen)))
'
exit $?
