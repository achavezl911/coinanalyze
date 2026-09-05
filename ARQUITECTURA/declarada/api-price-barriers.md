# DECLARADA · `GET /api/price-barriers`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-price-barriers.md`](../rutas/api-price-barriers.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **3** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P2.8** — ¿Hay un nivel más fuerte justo detrás del mío?  
  <sub>`entregas/20260904-2100-bateria-trader.md:144`</sub>
- **P3.1** — ¿Cuál es el objetivo y de dónde sale?  
  <sub>`entregas/20260904-2100-bateria-trader.md:152`</sub>
- **P3.5** — ¿El objetivo está antes o después de una barrera?  
  <sub>`entregas/20260904-2100-bateria-trader.md:156`</sub>

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

**MEDIDO en la foto de produccion** (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z, arco 37 387 ms).

El AST no le derivo ninguna clave temporal, pero **si publica marca de tiempo en el**
**cuerpo**. Son cosas distintas y aqui se separan: lo primero es un limite del
analisis estatico, lo segundo una afirmacion sobre el producto.

Claves **anidadas** (9), dentro de filas o bloques:

- `active_zone.age_days` (nombre)
- `active_zone.last_touch` (valor ISO)
- `live_pressure.absorption_15m` (sufijo de periodo)
- `live_pressure.delta_ratio_15m` (sufijo de periodo)
- `live_pressure.volume_multiple_15m` (sufijo de periodo)
- `nearest_resistance.age_days` (nombre)
- `nearest_resistance.last_touch` (valor ISO)
- `nearest_support.age_days` (nombre)
- _… y 1 mas_

**Y NO tiene ninguna de primer nivel.** O sea: la respuesta fecha sus FILAS pero
no se fecha a SI MISMA. Para K43 eso importa — un consumidor que quiera saber de
cuando es la foto entera tiene que deducirlo de la fila mas reciente, y eso es
adivinar. **Candidata a familia 1 con defecto declarado.**

<sub>Medido leyendo el cuerpo de la respuesta en la foto, no supuesto. 9 claves temporales en total.</sub>

## PROMESA


### NADIE LA LLAMA, y esta medido

Censo sobre `static/app.js`, `static/index.html`, `harness/checks`, `tests`, `tools` y
`README.md`, con limite de token y separando llamada de mencion: **cero llamadas y cero
menciones**. Es una de las **seis** rutas del sistema sin ningun rastro.

No prueba que este muerta -puede llamarla una IA por su nombre, o algo fuera del repo-,
pero es la forma exacta del patron que en esta casa se ha repetido nueve veces.

### Lo que promete

**PROMESA · cada zona declara SU fuerza y CUANTAS VECES la han tocado.**
En la foto: `active_zone`, `nearest_support` y `nearest_resistance`, las tres con
`center`, `low`, `high`, `score`, `difficulty` y **`touches`**. Mas `current_price`,
`decision = "ESPERAR: zona en disputa"`, `live_pressure` y `long_case`.

`touches` es lo que contesta **P2.2** -"¿cuantas veces ese nivel ha aguantado?"-. Sin el,
como dice la bateria, *"el nivel es una raya"*.

Recuento sobre las 65 rutas de la foto, buscando cualquier clave con `touch` hasta 4
niveles: **4 rutas lo publican** — esta, `/api/ai/context`, `/api/ai/context/bundle` y
`/api/dashboard/state`. Las otras tres **embeben el bloque de barreras**: el dato sale de
aqui y llega al producto por esas puertas. **La ruta que lo calcula no la llama nadie.**

**PROMESA · dice que NO hacer, no solo que hay.** `decision` incluye `ESPERAR`. Es una de
las pocas respuestas del sistema al **P5.9** -la prueba de fuego del ¶19-: un producto que
nunca dice "no operes" es un generador de razones.

**Y NADIE LA LLAMA, que es lo grave aqui.** Esta ruta contesta P2.2, P2.8, P3.1 y P3.5 -y
la unica de las 68 que publica `touches`- y no la consume ni el panel ni un check.


## SUPERFICIE

**Sin consumidor conocido**, medido: no aparece en `static/app.js`,
`static/index.html`, `harness/checks`, `tests`, `tools` ni `README.md`.

No prueba que este muerta -puede llamarla algo fuera del repo-, pero es la
forma del patron que en esta casa se ha repetido nueve veces.
