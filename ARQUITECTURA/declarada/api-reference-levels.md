# DECLARADA · `GET /api/reference-levels`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-reference-levels.md`](../rutas/api-reference-levels.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **3** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P2.1** — ¿Dónde está el soporte más cercano por debajo?  
  <sub>`entregas/20260904-2100-bateria-trader.md:137`</sub>
- **P2.2** — ¿Cuántas veces ese nivel ha aguantado?  
  <sub>`entregas/20260904-2100-bateria-trader.md:138`</sub>
- **P2.7** — ¿El nivel viene de mi marco o de otro?  
  <sub>`entregas/20260904-2100-bateria-trader.md:143`</sub>

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

Declara su ventana con estas claves, derivadas de los campos que publica:

- `current_day` — literal en app/scalp_logic.py:3237
- `previous_day` — literal en app/scalp_logic.py:3236

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
