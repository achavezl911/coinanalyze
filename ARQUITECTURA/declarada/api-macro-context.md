# DECLARADA · `GET /api/macro-context`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-macro-context.md`](../rutas/api-macro-context.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **1** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P1.13** — ¿El régimen actual favorece este setup?  
  <sub>`entregas/20260904-2100-bateria-trader.md:125`</sub>

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

Declara su ventana con estas claves, derivadas de los campos que publica:

- `as_of` — literal en app/scalp_logic.py:1871
- `session_date` — literal en app/scalp_logic.py:1873

## PROMESA


### Lo que promete

Medido en la foto (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z), **2 389 B**:

**PROMESA 1 · cada metrica trae su PERCENTIL y su REGIMEN, no solo su valor.**
`metrics = [7]` con `key`, `label`, `value`, `percentile`, `regime` y `conditional`. Es
**P5.8** —*"sin linea base, 'fuerte' no significa nada"*— resuelto por fila.

**PROMESA 2 · declara sobre cuantas SESIONES se calcula.** `sessions = 365` y
`session_date = "2026-09-04"`. La ventana y el dia de corte, los dos en primer nivel.

**PROMESA 3 · marca lo condicional como condicional.**
`conditional_note = "'conditional' = retorno posterior e…"`. El campo `conditional` de cada
metrica es un retorno **posterior** —o sea, mirado con el diario del lunes— y la ruta lo
dice. Es **P5.4** —*"¿esto se midio antes o despues de conocer el resultado?"*— contestado
por la propia ruta, que es donde menos suele estar.

*Que significa no cumplirlo:* que `conditional` viajara sin su nota. Un retorno condicional
leido como predictivo es la forma mas comun de convertir una correlacion en una promesa.


## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1578`, `static/app.js:1636`
- **readme**: `README.md:278`
