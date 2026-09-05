# DECLARADA · `GET /api/verdicts`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-verdicts.md`](../rutas/api-verdicts.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **2** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P1.8** — ¿El veredicto tiene fecha o es perpetuo?  
  <sub>`entregas/20260904-2100-bateria-trader.md:120`</sub>
- **S2** — ¿Cuántas veces dijo NO ENTRAR?  
  <sub>`entregas/20260904-2100-bateria-trader.md:319`</sub>

## VENTANA

Familia **2** de K43 — coverage de su propia serie.

Derivado de su firma: pide ['limit']: coverage de su propia serie.

**MEDIDO en la foto de produccion** (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z, arco 37 387 ms).

El AST no le derivo ninguna clave temporal, pero **si publica marca de tiempo en el**
**cuerpo**. Son cosas distintas y aqui se separan: lo primero es un limite del
analisis estatico, lo segundo una afirmacion sobre el producto.

Claves **anidadas** (8), dentro de filas o bloques:

- `coverage.served_window` (nombre)
- `coverage.served_window.window_end` (nombre)
- `coverage.served_window.window_start` (nombre)
- `rows[].metrics_snapshot_ts` (nombre)
- `rows[].observed_at` (nombre)
- `rows[].reference_price_at` (nombre)
- `rows[].session_date` (nombre)
- `rows[].session_end_at` (nombre)

**Y NO tiene ninguna de primer nivel.** O sea: la respuesta fecha sus FILAS pero
no se fecha a SI MISMA. Para K43 eso importa — un consumidor que quiera saber de
cuando es la foto entera tiene que deducirlo de la fila mas reciente, y eso es
adivinar. **Candidata a familia 1 con defecto declarado.**

<sub>Medido leyendo el cuerpo de la respuesta en la foto, no supuesto. 8 claves temporales en total.</sub>

## PROMESA


### Lo que promete

**PROMESA 1 · el veredicto es INMUTABLE desde su primera emision.**
En la foto: `note = "snapshot = primera emision inmutabl…"` y `logic_version =
"daily-verdict-v4"`. Contesta **P1.8** —*"¿el veredicto tiene fecha o es perpetuo?"*— y
**P5.4** —*"¿esto se midio antes o despues de conocer el resultado?"*—: un veredicto que se
congela al emitirse no se puede reescribir cuando se sabe como acabo.

**PROMESA 2 · la version de la logica es un PARAMETRO, no un adorno.**
`logic_version` se puede pedir (`app/api.py:1826`, con su defecto
`DAILY_VERDICT_LOGIC_VERSION`). O sea que se puede preguntar por lo que decia la version
anterior **sin** que la nueva reescriba la historia. Es exactamente lo que faltaba en el
defecto de **P5.5** que la bateria ya midio: *"dos etiquetas de version ocupaban DIAS
DISTINTOS"*.

**PROMESA 3 · declara su cobertura.** `coverage = {served_window}` al lado de
`rows = [20]`: la ventana servida no se deduce del numero de filas.

*Que significa no cumplirlo:* que una fila cambiara de valor entre dos consultas del mismo
`session_date` y `logic_version`. Eso es comprobable con dos capturas, y **no lo he hecho**:

```sh
harness/bin/api '/api/verdicts?symbol=BTCUSDT&limit=5' > /tmp/v1.json
# esperar, repetir, y comparar por (session_date, logic_version)
```

**La llama el panel** (`static/app.js:1630`).


## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1630`
- **readme**: `README.md:72`, `README.md:276`, `README.md:410`
