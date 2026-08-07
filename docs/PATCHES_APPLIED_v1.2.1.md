# Patches aplicados — v1.2.1

## Objetivo

Cerrar los residuales detectados en la revisión de v1.2.0 sin ampliar el alcance funcional hacia v1.3.0.

## Cambios aplicados

1. **Separación de capas para scalp**
   - Se creó `app/scalp_logic.py`.
   - Se movieron funciones puras y SQL compartido desde `app/api.py`:
     - `scalp_context()`
     - `compute_scalp_summary()`
     - `scalp_bias_label()`
     - `score_component()`
     - `as_float()`
   - `app/api.py` y `app/scalp_collector.py` importan desde `app.scalp_logic`.
   - `app/scalp_collector.py` ya no importa la capa web `app.api`, evitando que el worker dependa de `FastAPI`, `StaticFiles` o del árbol `/static`.

2. **UI cableada a endpoints v1.2.0**
   - El frontend ahora consume `/api/dashboard/state` para snapshot, scalp y setup.
   - Se agregaron paneles visibles para:
     - `/api/scalp/basis`
     - `/api/scalp/signals`
     - `/api/scalp/liquidation-levels`
   - Se mantienen las llamadas específicas para matrices realtime, charts y salud.

3. **Calibración corregida contra autocorrelación**
   - `scripts/calibrate_signals.py` ahora soporta:
     - `--mode raw`
     - `--mode episode` default
     - `--mode non_overlap`
   - El modo `episode` toma una muestra por transición de estado/confianza/lado por símbolo.
   - El modo `non_overlap` impone separación temporal por bucket.
   - El reporte ahora incluye `requested_days`, `effective_days`, `raw_rows`, `effective_rows` y `coverage_pct`.
   - `effective_days` queda limitado por `HARD_DATA_RETENTION_DAYS` para no simular cobertura mayor que la retención real de OHLCV.

4. **Documentación operacional Prometheus**
   - Se documentó el scraping de `/metrics` con `X-Internal-Token` o vía Nginx con Basic Auth.

5. **Pruebas nuevas**
   - Se añadieron pruebas para:
     - confirmar que `scalp_collector.py` no importa `app.api`;
     - confirmar que `scalp_logic.py` no depende de FastAPI ni StaticFiles;
     - confirmar que el frontend referencia los endpoints v1.2.0;
     - confirmar deduplicación por episodio;
     - confirmar deduplicación por ventana no solapada.

## Fuera de alcance

No se implementó todavía:

- funding cross-venue/anualizado con countdown;
- umbrales whale/large adaptativos por percentil;
- push in-process sub-segundo.

Estos quedan como alcance natural de v1.3.0.
