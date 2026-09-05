# DECLARADA · `GET /api/signals/outcomes`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-signals-outcomes.md`](../rutas/api-signals-outcomes.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **6** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P1.14** — ¿Cuántas veces este setup ha funcionado en ESTE régimen?  
  <sub>`entregas/20260904-2100-bateria-trader.md:126`</sub>
- **P3.3** — ¿Cuánto tarda históricamente en llegar?  
  <sub>`entregas/20260904-2100-bateria-trader.md:154`</sub>
- **P3.4** — ¿Cuántas veces llegó al objetivo antes que al stop?  
  <sub>`entregas/20260904-2100-bateria-trader.md:155`</sub>
- **P5.1** — ¿Cuál es la expectativa histórica de este setup?  
  <sub>`entregas/20260904-2100-bateria-trader.md:185`</sub>
- **P5.2** — ¿Sobre cuántas operaciones se calcula?  
  <sub>`entregas/20260904-2100-bateria-trader.md:186`</sub>
- **S3** — ¿La expectativa histórica de los cortos se calcula igual que la de los largos?  
  <sub>`entregas/20260904-2100-bateria-trader.md:320`</sub>

## VENTANA

Familia **3** de K43 — su propio as_of bajo demanda.

Derivado de su firma: pide ['since']: el operador elige el momento.

Declara su ventana con estas claves, derivadas de los campos que publica:

- `since` — literal en app/api.py:2240
- `until` — literal en app/api.py:2241

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
