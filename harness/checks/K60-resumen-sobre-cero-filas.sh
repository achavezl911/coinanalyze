#!/bin/bash
# K60  EL TITULAR DEL INFORME PROSPECTIVO AFIRMA SOBRE CERO FILAS.
#
# El operador corrio el evaluador -lo que nadie habia hecho- y contra produccion la
# ventana de prueba sale VACIA. La capa de CELDA es honesta: 24 de 24 con test n=0,
# label insufficient_sample y positive_oos_gate_passed=None. La de RESUMEN no:
#
#   "ready_by_clock=1 evaluation_ready=1 gross_positive_oos_gates=0"
#
# positive_oos_gate_count suma "is True" (:3148), asi que un None cuenta igual que un
# False y el total sale 0. Y evaluation_ready sale de state=="ready_by_clock" (:1668),
# o sea del RELOJ y no del dato. Quien lee esa linea entiende "evaluado, sin ventaja".
# Lo que ocurrio es "no habia nada que evaluar". Es la forma de K59 -un 0 donde tocaba
# None- un piso mas arriba, y en el unico numero que alguien va a leer del walk-forward.
#
# POR QUE ESTA VACIA, medido y cerrado, para que nadie persiga el fantasma: el manifiesto
# pr11-fixed-kernel-v1 congela evidence_version=1 y la ventana de prueba del fold 1 es
# CIEN POR CIEN v6 -30240 de 30240, cero de v1-. La de descubrimiento si tiene v1 (5421)
# y por eso no sale cero. El camino gateado por certificado es real pero NO es la causa
# aqui: el filtro de version vacia la ventana antes de que la visibilidad importe.
# ESO NO ES LO QUE ARREGLA ESTE CHECK. Que la ventana este vacia es una decision de
# etiquetado pendiente; que el resumen lo llame "0 puertas" es un defecto, y es este.
#
# EL ESPEJO ES LA INDUCCION GRATIS Y PERMANENTE. Solo llega al 2026-08-13, asi que su
# ventana de prueba esta vacia POR CONSTRUCCION: no hay que adulterar nada para provocar
# el modo de fallo por ausencia. Si algun dia el espejo se rellena y su ventana deja de
# estar vacia, este check lo dice y sale NO MEDIDO en vez de dar un VERDE hueco.
#
# LO QUE EXIGE
#   1 · gates declara cuantas celdas eran EVALUABLES y cuantas no. Sin ese par, "0
#       puertas pasadas" y "0 puertas medibles" son el mismo numero.
#   2 · con CERO celdas evaluables, positive_oos_gate_count NO puede ser 0: es None.
#   3 · evaluation_ready_fold_count no cuenta un fold cuya ventana de prueba tiene
#       integrity.test.periodic_observations = 0. El reloj no es el dato.
#   4 · LA LINEA QUE SE IMPRIME lo dice. Es lo unico que un humano lee de verdad, asi
#       que el check la mira a ella y no solo al JSON.
#   CONTROL POSITIVO, obligatorio: el mismo contador, con celdas que SI traen un booleano
#       de verdad, tiene que devolver su entero normal y no apagarse por precaucion. Un
#       informe que nunca publica un numero no informa.
#
# COSTE: la corrida del evaluador contra el espejo tarda ~24 s. Es cara para un check y
# se paga a proposito: es la unica comprobacion de extremo a extremo del unico artefacto
# prospectivo del proyecto, y el defecto vive en la ultima linea, no en el JSON.
#
# DE QUE ARBOL: codigo del repo de 143, datos del ESPEJO de 143. No toca 140.
set -uo pipefail
B=/srv/coinanalyze/harness
REPO=/srv/coinanalyze/repo
. "$B/env"

PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || { echo "NO MEDIDO: falta el venv del repo en $PY"; exit 2; }

SALIDA=$(mktemp /tmp/k60-wf-XXXXXX.json)
trap 'rm -f "$SALIDA"' EXIT

linea=$(cd "$REPO" && PG_HOST=/var/run/postgresql PG_DB="$ESPEJO_DB" PG_USER=root \
  "$PY" scripts/evaluate_walk_forward.py \
  --manifest-name pr11-fixed-kernel-v1 --output "$SALIDA" 2>&1 | tail -1)
rc=$?
if [ $rc -ne 0 ] || [ ! -s "$SALIDA" ]; then
  echo "NO MEDIDO: el evaluador no completo contra el espejo (rc=$rc). $(printf '%s' "$linea" | head -c 150)"
  exit 2
fi

LINEA="$linea" "$PY" - "$SALIDA" <<'PY'
import json, os, sys

sys.path.insert(0, "/srv/coinanalyze/repo")
informe = json.load(open(sys.argv[1]))
linea = os.environ["LINEA"]
gates = informe["gates"]
fallos = []

# --- el ELEGIBLE sale del informe, no de lo que yo espere que traiga -----------------
folds = informe["folds"]
vacios = [
    f for f in folds
    if int(f["integrity"]["test"]["periodic_observations"]) == 0
    and f["clock_state"] == "ready_by_clock"
]
if not vacios:
    print("NO MEDIDO: el espejo ya no tiene ningun fold maduro con la ventana de prueba "
          "vacia, que es lo que hacia de induccion gratis. Folds: %d" % len(folds))
    sys.exit(2)

celdas = [
    fila
    for f in vacios
    for vistas in f["gross_views"].values()
    for filas in vistas.values()
    for fila in filas
]
evaluables = [c for c in celdas if c["positive_oos_gate_passed"] is not None]
if evaluables:
    print("NO MEDIDO: los folds de ventana vacia traen %d celdas con puerta evaluable, "
          "asi que este no es el modo de fallo por ausencia" % len(evaluables))
    sys.exit(2)

# --- 1 · el par evaluable / no evaluable tiene que existir ---------------------------
n_eval = gates.get("oos_gate_evaluable_cell_count")
n_noeval = gates.get("oos_gate_not_evaluable_cell_count")
if not isinstance(n_eval, int) or isinstance(n_eval, bool):
    fallos.append("gates no declara oos_gate_evaluable_cell_count: '0 puertas pasadas' y "
                  "'0 puertas medibles' son el mismo numero y no se pueden distinguir")
if not isinstance(n_noeval, int) or isinstance(n_noeval, bool):
    fallos.append("gates no declara oos_gate_not_evaluable_cell_count")
elif n_noeval < len(celdas):
    fallos.append("gates dice %d celdas no evaluables y en los folds vacios hay %d"
                  % (n_noeval, len(celdas)))

# --- 2 · con cero evaluables, el conteo no es 0: es None -----------------------------
if n_eval == 0 and gates.get("positive_oos_gate_count") is not None:
    fallos.append("cero celdas evaluables y positive_oos_gate_count=%r en vez de None"
                  % gates.get("positive_oos_gate_count"))
elif not isinstance(n_eval, int) and gates.get("positive_oos_gate_count") == 0:
    fallos.append("positive_oos_gate_count=0 sobre %d celdas que son TODAS None: el 0 "
                  "esta contando lo no medido como no pasado" % len(celdas))

# --- 3 · el reloj no es el dato ------------------------------------------------------
for f in vacios:
    if f["evaluation_ready"]:
        fallos.append("fold %s: evaluation_ready=True con "
                      "integrity.test.periodic_observations=0; sale de state=%s, o sea "
                      "del reloj" % (f["fold_index"], f["state"]))
    elif not f.get("not_evaluable_reason"):
        fallos.append("fold %s: no esta listo pero no dice por que "
                      "(falta not_evaluable_reason)" % f["fold_index"])
listos = gates.get("evaluation_ready_fold_count")
if isinstance(listos, int) and listos > len(folds) - len(vacios):
    fallos.append("evaluation_ready_fold_count=%d cuenta folds cuya ventana de prueba "
                  "esta vacia (%d de %d folds lo estan)" % (listos, len(vacios), len(folds)))

# --- 4 · LA LINEA QUE SE IMPRIME, que es lo unico que alguien lee ---------------------
if "gross_positive_oos_gates=0" in linea:
    fallos.append("la linea impresa dice 'gross_positive_oos_gates=0' sobre cero celdas "
                  "evaluables: se lee como 'evaluado, sin ventaja'")
if "oos_gate_evaluable=" not in linea:
    fallos.append("la linea impresa no publica cuantas celdas eran evaluables, asi que "
                  "el lector no puede notar que no habia nada que evaluar")

# --- CONTROL POSITIVO: el contador tiene que seguir contando -------------------------
try:
    from app.signal_walk_forward import _count_oos_gates
except ImportError:
    fallos.append("el modulo no expone _count_oos_gates, asi que el contador no se puede "
                  "probar con celdas que SI traen booleano")
else:
    def _fold(valores):
        return {
            "gross_views": {"dense_periodic": {"overall": [
                {"positive_oos_gate_passed": v} for v in valores
            ]}},
            "execution_views": {"dense_periodic": []},
        }
    pasadas, ev, noev = _count_oos_gates([_fold([True, True, False, None])])
    if pasadas != 2 or ev != 3 or noev != 1:
        fallos.append("CONTROL POSITIVO ROTO: con dos True, un False y un None el "
                      "contador da pasadas=%r evaluables=%r no_evaluables=%r y tenia que "
                      "dar 2/3/1. Un informe que nunca publica un numero no informa"
                      % (pasadas, ev, noev))
    todas_nulas, ev0, _ = _count_oos_gates([_fold([None, None])])
    if ev0 != 0 or todas_nulas is not None:
        fallos.append("CONTROL POSITIVO ROTO al reves: con todo None el contador da "
                      "pasadas=%r evaluables=%r y tenia que dar None/0" % (todas_nulas, ev0))

if fallos:
    print("ROJO: " + fallos[0])
    for f in fallos[1:]:
        print("      " + f)
    sys.exit(1)

print("VERDE: %d folds maduros con la ventana de prueba vacia y %d celdas sin puerta "
      "evaluable; el resumen lo declara (evaluables=%s, no evaluables=%s, conteo=%r) y la "
      "linea impresa tambien" % (len(vacios), len(celdas), n_eval, n_noeval,
                                 gates.get("positive_oos_gate_count")))
PY
exit $?
