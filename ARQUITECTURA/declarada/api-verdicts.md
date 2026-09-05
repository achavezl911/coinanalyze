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

**PENDIENTE.** No se ha escrito que promete esta ruta ni que significa no cumplirlo.

Una promesa vale si es comprobable: "publica el instante de construccion", "no
publica un 0 sin testigo", "la senal dura al menos N minutos". Si la ruta no
promete nada comprobable, eso tambien se escribe.

## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1630`
- **readme**: `README.md:72`, `README.md:276`, `README.md:410`
