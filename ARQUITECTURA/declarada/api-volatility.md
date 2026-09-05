# DECLARADA · `GET /api/volatility`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-volatility.md`](../rutas/api-volatility.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **1** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P2.5** — ¿Qué distancia hay hasta mi stop en % y en ATR?  
  <sub>`entregas/20260904-2100-bateria-trader.md:141`</sub>

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

**MEDIDO en la foto de produccion** (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z, arco 37 387 ms).

El AST no le derivo ninguna clave temporal, pero **si publica marca de tiempo en el**
**cuerpo**. Son cosas distintas y aqui se separan: lo primero es un limite del
analisis estatico, lo segundo una afirmacion sobre el producto.

Claves de **primer nivel** — la respuesta declara su propio instante o periodo:

- `daily_range_percentile_1y` (sufijo de periodo)

<sub>Medido leyendo el cuerpo de la respuesta en la foto, no supuesto. 1 claves temporales en total.</sub>

## PROMESA


### NADIE LA LLAMA, y esta medido

Censo sobre `static/app.js`, `static/index.html`, `harness/checks`, `tests`, `tools` y
`README.md`, con limite de token y separando llamada de mencion: **cero llamadas y cero
menciones**. Es una de las **seis** rutas del sistema sin ningun rastro.

No prueba que este muerta -puede llamarla una IA por su nombre, o algo fuera del repo-,
pero es la forma exacta del patron que en esta casa se ha repetido nueve veces.

### Lo que promete

**PROMESA · publica la volatilidad en las TRES formas que hacen falta para un stop.**
En la foto: `atr` por `5m`/`15m`/`1h`/`4h`/`1d`, `realized_vol_annualized_pct` por
`1h`/`24h`/`7d`, `daily_range_percentile_1y = 43.6`, `compression_score = 0.488`,
`range_expansion = false` y `note = "realized vol anualizada desde velas…"`.

Contesta **P2.5** -"¿que distancia hay hasta mi stop en % y en ATR?"- con el ATR de cinco
marcos, que es lo que permite decir si *"un stop a 0.3 % en un activo con ATR de 2 % es
ruido, no stop"*.

**PROMESA · el percentil trae SU ventana en el nombre.** `daily_range_percentile_1y`: el
`_1y` va en la clave, no en la documentacion. Un percentil sin ventana no es comparable
entre dias.

**NO publica ninguna marca temporal**, y aqui pesa: un ATR de hace seis horas se parece
mucho a uno de ahora, y no hay forma de distinguirlos desde la respuesta. **Candidata a la
misma familia que `/api/scalp/liquidation-levels`.**


## SUPERFICIE

**Sin consumidor conocido**, medido: no aparece en `static/app.js`,
`static/index.html`, `harness/checks`, `tests`, `tools` ni `README.md`.

No prueba que este muerta -puede llamarla algo fuera del repo-, pero es la
forma del patron que en esta casa se ha repetido nueve veces.
