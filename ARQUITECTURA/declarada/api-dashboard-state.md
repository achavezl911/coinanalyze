# DECLARADA · `GET /api/dashboard/state`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-dashboard-state.md`](../rutas/api-dashboard-state.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

**NINGUNA de las 66 preguntas de la bateria la nombra.**

Medido sobre `entregas/20260904-2100-bateria-trader.md`: ninguna fila de las 54 (P0.1..P5.9) ni de las 12
(S1..S12) cita esta ruta en su columna de destino ni en la de medicion.

Eso NO significa que no sirva: significa que **el trader no le ha formulado**
**una pregunta**. Si es un instrumento interno, lo normal es que no la haya.
Si es superficie de producto y no contesta ninguna pregunta, merece mirarse.

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

**MEDIDO en la foto de produccion** (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z, arco 37 387 ms).

El AST no le derivo ninguna clave temporal, pero **si publica marca de tiempo en el**
**cuerpo**. Son cosas distintas y aqui se separan: lo primero es un limite del
analisis estatico, lo segundo una afirmacion sobre el producto.

Claves **anidadas** (56), dentro de filas o bloques:

- `barriers.active_zone.age_days` (nombre)
- `barriers.active_zone.last_touch` (valor ISO)
- `barriers.live_pressure.absorption_15m` (sufijo de periodo)
- `barriers.live_pressure.delta_ratio_15m` (sufijo de periodo)
- `barriers.live_pressure.volume_multiple_15m` (sufijo de periodo)
- `barriers.nearest_resistance.age_days` (nombre)
- `barriers.nearest_resistance.last_touch` (valor ISO)
- `barriers.nearest_support.age_days` (nombre)
- _… y 48 mas_

**Y NO tiene ninguna de primer nivel.** O sea: la respuesta fecha sus FILAS pero
no se fecha a SI MISMA. Para K43 eso importa — un consumidor que quiera saber de
cuando es la foto entera tiene que deducirlo de la fila mas reciente, y eso es
adivinar. **Candidata a familia 1 con defecto declarado.**

<sub>Medido leyendo el cuerpo de la respuesta en la foto, no supuesto. 56 claves temporales en total.</sub>

## PROMESA

**PENDIENTE.** No se ha escrito que promete esta ruta ni que significa no cumplirlo.

Una promesa vale si es comprobable: "publica el instante de construccion", "no
publica un 0 sin testigo", "la senal dura al menos N minutos". Si la ruta no
promete nada comprobable, eso tambien se escribe.

## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1491`
- **readme**: `README.md:195`, `README.md:488`, `README.md:502`
- **tests**: `tests/test_metrics_endpoint.py:162`, `tests/test_v121_hardening.py:27`, `tests/test_v150_desk_snapshot.py:126`
