# DECLARADA · `GET /api/funding-context`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-funding-context.md`](../rutas/api-funding-context.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **3** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P4.4** — ¿El funding me cobra o me paga por estar largo?  
  <sub>`entregas/20260904-2100-bateria-trader.md:171`</sub>
- **P4.5** — ¿Cuánto funding acumulo si aguanto una semana?  
  <sub>`entregas/20260904-2100-bateria-trader.md:172`</sub>
- **S5** — ¿El signo del funding cambia con el lado?  
  <sub>`entregas/20260904-2100-bateria-trader.md:322`</sub>

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

Declara su ventana con estas claves, derivadas de los campos que publica:

- `next_funding_time_utc` — literal en app/scalp_logic.py:3408

## PROMESA

**PENDIENTE.** No se ha escrito que promete esta ruta ni que significa no cumplirlo.

Una promesa vale si es comprobable: "publica el instante de construccion", "no
publica un 0 sin testigo", "la senal dura al menos N minutos". Si la ruta no
promete nada comprobable, eso tambien se escribe.

## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1607`
