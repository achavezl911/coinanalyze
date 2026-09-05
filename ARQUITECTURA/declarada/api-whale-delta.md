# DECLARADA · `GET /api/whale/delta`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-whale-delta.md`](../rutas/api-whale-delta.md).
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

**MEDIDO en la foto de produccion** (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z, arco 37 387 ms).

El AST no le derivo ninguna clave temporal, pero **si publica marca de tiempo en el**
**cuerpo**. Son cosas distintas y aqui se separan: lo primero es un limite del
analisis estatico, lo segundo una afirmacion sobre el producto.

Claves **anidadas** (6), dentro de filas o bloques:

- `coverage.served_window` (nombre)
- `coverage.served_window.window_end` (nombre)
- `coverage.served_window.window_start` (nombre)
- `data_gaps.window_end` (nombre)
- `data_gaps.window_start` (nombre)
- `rows[].bucket` (valor ISO)

**Y NO tiene ninguna de primer nivel.** O sea: la respuesta fecha sus FILAS pero
no se fecha a SI MISMA. Para K43 eso importa — un consumidor que quiera saber de
cuando es la foto entera tiene que deducirlo de la fila mas reciente, y eso es
adivinar. **Candidata a familia 1 con defecto declarado.**

<sub>Medido leyendo el cuerpo de la respuesta en la foto, no supuesto. 6 claves temporales en total.</sub>

## PROMESA


### Lo que promete · es la unica serie que declara su cobertura POR BUCKET

En la foto (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z): `rows = [384]` con `bucket`, `whale_delta`, y **cuatro campos de
cobertura por fila**: `covered_seconds_min`, `short_minutes`, `unknown_minutes`,
`minutes_present`.

Las otras tres series de familia 2 (`ohlcv`, `cvd`, `oi`) declaran su cobertura **de la
ventana entera** con `coverage.served_window`. Esta la declara **de cada bucket**, y esa es
la diferencia que importa.

**PROMESA 1 · un bucket de 15 min hecho con 11 minutos lo dice.**
`minutes_present` contra el esperado, y `short_minutes` contando los minutos incompletos.
Es **P0.7** —*"¿el minuto que estoy viendo esta completo?"*— contestado por fila y no por
ventana.

**PROMESA 2 · distingue el minuto CORTO del minuto AUSENTE.**
`short_minutes` y `unknown_minutes` son campos separados: un minuto que se recogio a medias
y un minuto del que no se sabe nada **no son el mismo hueco**. Es **P0.5** aplicado al eje
del tiempo, y es justo la distincion que K52 persigue.

**PROMESA 3 · publica el MINIMO de segundos cubiertos, no la media.**
`covered_seconds_min`. Una media de 58 s sobre 15 minutos puede esconder un minuto de 5 s;
el minimo no. Publicar el peor caso en vez del promedio es lo que hace la cifra utilizable.

*Que significa no cumplirlo:* que `whale_delta` viniera solo con `bucket`. Entonces un
bucket construido con un tercio de los datos y otro completo pesarian igual en cualquier
agregado de aguas abajo, y **la bateria ya midio el caso**: `spot_trades_agg` con
`venue_count=2` para `combined` hace que **el minuto desaparezca** si un venue calla.

**Es la ruta que mejor material da para F4**, donde aterriza `covered_seconds`.


## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1549`
- **readme**: `README.md:408`
