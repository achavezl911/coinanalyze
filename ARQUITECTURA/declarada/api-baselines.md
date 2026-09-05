# DECLARADA · `GET /api/baselines`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-baselines.md`](../rutas/api-baselines.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **1** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P5.8** — ¿Cuál es la línea base contra la que comparo?  
  <sub>`entregas/20260904-2100-bateria-trader.md:192`</sub>

## VENTANA

**PENDIENTE de familia.** parametros ['metric', 'symbol']: no encaja en 1/2/3 sin leerla

**MEDIDO en la foto de produccion** (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z, arco 37 387 ms).

El AST no le derivo ninguna clave temporal, pero **si publica marca de tiempo en el**
**cuerpo**. Son cosas distintas y aqui se separan: lo primero es un limite del
analisis estatico, lo segundo una afirmacion sobre el producto.

Claves **anidadas** (40), dentro de filas o bloques:

- `windows.15m.sample_end` (nombre)
- `windows.15m.sample_start` (nombre)
- `windows.15m.window_label` (nombre)
- `windows.15m.window_seconds` (nombre)
- `windows.18m.sample_end` (nombre)
- `windows.18m.sample_start` (nombre)
- `windows.18m.window_label` (nombre)
- `windows.18m.window_seconds` (nombre)
- _… y 32 mas_

**Y NO tiene ninguna de primer nivel.** O sea: la respuesta fecha sus FILAS pero
no se fecha a SI MISMA. Para K43 eso importa — un consumidor que quiera saber de
cuando es la foto entera tiene que deducirlo de la fila mas reciente, y eso es
adivinar. **Candidata a familia 1 con defecto declarado.**

<sub>Medido leyendo el cuerpo de la respuesta en la foto, no supuesto. 40 claves temporales en total.</sub>

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
