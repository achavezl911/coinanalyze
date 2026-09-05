# DECLARADA · `GET /api/divergences`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-divergences.md`](../rutas/api-divergences.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **1** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P5.6** — ¿Hay divergencias activas y qué han valido históricamente?  
  <sub>`entregas/20260904-2100-bateria-trader.md:190`</sub>

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

**MEDIDO en la foto de produccion** (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z, arco 37 387 ms).

El AST no le derivo ninguna clave temporal, pero **si publica marca de tiempo en el**
**cuerpo**. Son cosas distintas y aqui se separan: lo primero es un limite del
analisis estatico, lo segundo una afirmacion sobre el producto.

Claves **anidadas** (16), dentro de filas o bloques:

- `intraday.anchored_at` (nombre)
- `intraday.lag_seconds` (nombre)
- `intraday.windows.15m.lag_seconds` (nombre)
- `intraday.windows.15m.window_seconds` (nombre)
- `intraday.windows.16h.lag_seconds` (nombre)
- `intraday.windows.16h.window_seconds` (nombre)
- `intraday.windows.1h.lag_seconds` (nombre)
- `intraday.windows.1h.window_seconds` (nombre)
- _… y 8 mas_

**Y NO tiene ninguna de primer nivel.** O sea: la respuesta fecha sus FILAS pero
no se fecha a SI MISMA. Para K43 eso importa — un consumidor que quiera saber de
cuando es la foto entera tiene que deducirlo de la fila mas reciente, y eso es
adivinar. **Candidata a familia 1 con defecto declarado.**

<sub>Medido leyendo el cuerpo de la respuesta en la foto, no supuesto. 16 claves temporales en total.</sub>

## PROMESA


### Lo que promete

**MEDIDO en la foto (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z), 4 482 B**, con las claves de primer nivel al lado del
veredicto:

```
symbol · available · sessions = 90 · windows = {1d,2d,3d,6d,9d,2s,4s} · summary
windows_confirming = 0 · sustained_windows_evaluated = 0
intraday = {available, bars, anchored_at, lag_seconds, windows, summary, windows_confirming}
note = 'precio vs CVD spot ACUMULADO (solo Binance+Bybit) sobre ses...'
```

**PROMESA 1 · publica CUANTAS ventanas confirman Y CUANTAS se evaluaron.**
`windows_confirming = 0` junto a `sustained_windows_evaluated = 0`, sobre las **7** ventanas
de `windows`. Los dos numeros son distintos y hacen falta los dos: **0 de 7 evaluadas** y
**0 de 0 evaluadas** son cosas opuestas —la primera dice que no hay divergencia, la segunda
que no se pudo mirar— y con un solo campo serian el mismo cero. Es **P0.5** aplicado al eje
de las ventanas.

**PROMESA 2 · declara su fuente y su ambito en el cuerpo.**
`note = "precio vs CVD spot ACUMULADO (solo Binance+Bybit)…"`. Dice **contra que** se compara
el precio y **con cuantos venues**. Sin eso, "divergencia" es una palabra: dos rutas que
comparen contra fuentes distintas pueden discrepar y las dos tener razon.

**PROMESA 3 · el bloque intradiario declara SU ancla y SU retraso.**
`intraday.anchored_at` y `intraday.lag_seconds`, ademas de `intraday.bars`. Es un bloque con
su propia ventana dentro de una respuesta de 90 sesiones, y **no hereda la marca de la
raiz** — que es justo el defecto que mide P0.1 en `/api/dashboard/state`.

**PROMESA 4 · `sessions = 90` y `available` de primer nivel.** La ventana del calculo y la
separacion entre "no hay divergencia" y "no se pudo calcular".

### La mitad de P5.6 que NO contesta, y es lo que hay que decir

La bateria pregunta en **P5.6**: *"¿hay divergencias activas **y que han valido
historicamente**?"*. Son dos preguntas:

- **La primera si la contesta**, y bien: `summary`, `windows_confirming`, `intraday`.
- **La segunda no la contesta nadie.** No hay ningun campo de tasa base, de rendimiento
  posterior ni de muestra historica: `sessions = 90` es la ventana **de calculo**, no el
  numero de divergencias observadas ni lo que valieron.

*Que significa:* un trader puede saber que hay una divergencia y **no puede saber si las
divergencias de este sistema han valido algo**. No lo abro como K porque el criterio
—¿cuantas divergencias historicas hacen falta para publicar una tasa?— es una decision de
producto, pero **queda escrito que la mitad de P5.6 no tiene ruta que la conteste**.

## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1638`
- **readme**: `README.md:281`
