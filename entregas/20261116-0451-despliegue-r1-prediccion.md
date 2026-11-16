# Despliegue R1 · prediccion (antes de tocar nada) · repo main@11df0b4, rama claude/despliegue-r1

S1 · scripts/smoke_test.sh:97-99 hoy sale 86 ante CUALQUIER latido gobernado posterior al reinicio que no diga ok.
- Con la foto del operador hecha fixture, el smoke de main da 86 (lo fijo como test antes del arreglo); con el arreglo, 75.
- (b) otro motivo, (c) arranque+error, (d) marcador con cola: 86 antes y despues.
- Espero un riesgo que la frase del encargo no cubre: ohlcv_1m late cada INGEST_INTERVAL_SECONDS (offset 5) y
  metrics_5m cada 300 s (offset 15) (app/ingest.py:1103-1126). Entre ~T+65 s y ~T+315 s el compuesto sera
  «metrics_5m=degraded:<marcador>;ohlcv_1m=ok:<detalle>». Si «mezcla» = 86 al pie de la letra, el despliegue se
  revierte igual a los ~65 s. Prediccion: hay que admitir partes `ok` junto a >=1 parte de arranque; solo `ok`
  y el marcador exacto; `error`, `missing` u otro `degraded` siguen siendo 86.
- El separador del compuesto (`;`, app/db.py:488-492) aparece DENTRO del marcador («starting; awaiting»): partir por
  `;` rompe. Parto por `;<comp>=<estado>:`.
- deploy/140/deploy-coinalyze no hace falta tocarlo: ya reintenta 75 hasta SMOKE_MAX_WAIT=450 (:115-133), y la
  vuelta atras usa el smoke del release mas nuevo con la misma espera (:376).
- Margen: el primer ciclo de metrics_5m llega a <=~315 s + lo que dure el ciclo; 450 s deberia bastar. NO SE SABE
  cuanto dura un ciclo de metrics en 140.

S2 · nginx: hoy 0 locations con 'self'/SAMEORIGIN; tras el cambio, exactamente 1 (`= /flujo`) con las 7 cabeceras.
