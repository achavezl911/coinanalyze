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


### NADIE LA LLAMA, y esta medido

Censo sobre `static/app.js`, `static/index.html`, `harness/checks`, `tests`, `tools` y
`README.md`, con limite de token y separando llamada de mencion: **cero llamadas y cero
menciones**. Es una de las **seis** rutas del sistema sin ningun rastro.

No prueba que este muerta -puede llamarla una IA por su nombre, o algo fuera del repo-,
pero es la forma exacta del patron que en esta casa se ha repetido nueve veces.

### Lo que promete

**PROMESA · cada nivel declara SU MARCO temporal.**
En la foto: `previous_day` y `current_day` (con `high`/`low`/`close`/`open`), `opens` por
`daily`/`weekly`/`monthly`, `sessions_today_utc` por `asia`/`london`/`new_york`, y
`note = "niveles desde ohlcv 1min (retencion…)"`.

Es **P2.7** -"¿el nivel viene de mi marco o de otro?"-: un soporte diario no invalida un
scalp. Aqui el marco no hay que deducirlo, esta en el nombre de la clave.

**INCUMPLE parcialmente P2.1**, y esta medido. La bateria pide que *"cada nivel declare SU
procedencia"* porque el frontend maneja **seis fuentes distintas de niveles**. Esta ruta
declara el MARCO (`daily`, `weekly`, `asia`…) pero **no la FUENTE**: los seis grupos salen
todos de `ohlcv` -la unica tabla que lee- y no hay campo que distinga un nivel de sesion de
un open semanal mas alla de donde esta colgado.

*Que significa:* dos niveles del mismo precio en grupos distintos no se pueden deduplicar.
No lo abro como K porque el criterio -¿cuantos niveles duplicados hacen falta para que
importe?- no lo puedo fijar sin una medida sobre varios simbolos.


## SUPERFICIE

**Sin consumidor conocido**, medido: no aparece en `static/app.js`,
`static/index.html`, `harness/checks`, `tests`, `tools` ni `README.md`.

No prueba que este muerta -puede llamarla algo fuera del repo-, pero es la
forma del patron que en esta casa se ha repetido nueve veces.
