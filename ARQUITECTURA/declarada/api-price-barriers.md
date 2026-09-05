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

**PENDIENTE.** No se ha escrito que promete esta ruta ni que significa no cumplirlo.

Una promesa vale si es comprobable: "publica el instante de construccion", "no
publica un 0 sin testigo", "la senal dura al menos N minutos". Si la ruta no
promete nada comprobable, eso tambien se escribe.

## SUPERFICIE

**Sin consumidor conocido**, medido: no aparece en `static/app.js`,
`static/index.html`, `harness/checks`, `tests`, `tools` ni `README.md`.

No prueba que este muerta -puede llamarla algo fuera del repo-, pero es la
forma del patron que en esta casa se ha repetido nueve veces.
