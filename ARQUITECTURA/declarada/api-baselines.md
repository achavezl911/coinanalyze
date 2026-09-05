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

**PENDIENTE · no se le ha derivado ninguna clave temporal.** O no publica
marca de tiempo, o sus campos no son derivables estaticamente. La foto de
produccion lo decide: `entregas/20260904-foto-prod-1.json`.

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
