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
