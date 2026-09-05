# DECLARADA · `GET /api/ohlcv`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-ohlcv.md`](../rutas/api-ohlcv.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

**NINGUNA de las 66 preguntas de la bateria la nombra.**

Medido sobre `entregas/20260904-2100-bateria-trader.md`: ninguna fila de las 54 (P0.1..P5.9) ni de las 12
(S1..S12) cita esta ruta en su columna de destino ni en la de medicion.

Eso NO significa que no sirva: significa que **el trader no le ha formulado**
**una pregunta**. Si es un instrumento interno, lo normal es que no la haya.
Si es superficie de producto y no contesta ninguna pregunta, merece mirarse.

## VENTANA

Familia **2** de K43 — coverage de su propia serie.

Derivado de su firma: pide ['interval', 'limit']: coverage de su propia serie.

**PENDIENTE · no se le ha derivado ninguna clave temporal.** O no publica
marca de tiempo, o sus campos no son derivables estaticamente. La foto de
produccion lo decide: `entregas/20260904-foto-prod-1.json`.

## PROMESA

**PENDIENTE.** No se ha escrito que promete esta ruta ni que significa no cumplirlo.

Una promesa vale si es comprobable: "publica el instante de construccion", "no
publica un 0 sin testigo", "la senal dura al menos N minutos". Si la ruta no
promete nada comprobable, eso tambien se escribe.

## SUPERFICIE

**Superficie de producto**, medido.

- **checks**: `harness/checks/K20-cincoxx.sh:68`, `harness/checks/K31-eslabon5.sh:64`
- **panel**: `static/app.js:1492`
- **readme**: `README.md:402`
- **tests**: `tests/test_p1_timeframes_and_spot.py:52`
