# DECLARADA · `GET /api/cross-asset`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-cross-asset.md`](../rutas/api-cross-asset.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

**NINGUNA de las 66 preguntas de la bateria la nombra.**

Medido sobre `entregas/20260904-2100-bateria-trader.md`: ninguna fila de las 54 (P0.1..P5.9) ni de las 12
(S1..S12) cita esta ruta en su columna de destino ni en la de medicion.

Eso NO significa que no sirva: significa que **el trader no le ha formulado**
**una pregunta**. Si es un instrumento interno, lo normal es que no la haya.
Si es superficie de producto y no contesta ninguna pregunta, merece mirarse.

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

Declara su ventana con estas claves, derivadas de los campos que publica:

- `as_of` — literal en app/scalp_logic.py:3336

## PROMESA


### NADIE LA LLAMA, y esta medido

Censo sobre `static/app.js`, `static/index.html`, `harness/checks`, `tests`, `tools` y
`README.md`, con limite de token y separando llamada de mencion: **cero llamadas y cero
menciones**. Es una de las **seis** rutas del sistema sin ningun rastro.

No prueba que este muerta -puede llamarla una IA por su nombre, o algo fuera del repo-,
pero es la forma exacta del patron que en esta casa se ha repetido nueve veces.

### Lo que promete

**PROMESA · publica su instante Y el metodo con el que calculo, no solo el numero.**
En la foto: `as_of = "2026-09-04T22:33:02.187567+00:00"`, `available = true`,
`correlation`, `beta_vs_base` y `relative_strength_vs_base_pct` -las tres por `1h`, `4h`,
`24h`- y `note = "correlacion Pearson de retornos 5min…"`.

Es de las pocas que trae **`as_of` de primer nivel**: la respuesta se fecha a si misma, no
solo a sus filas. Y `available` separa "no hay correlacion" de "no se pudo calcular", que
es **P0.5** — el cero medido contra el cero sin dato.

*Que significa no cumplirlo:* una correlacion sin metodo ni ventana no se puede reproducir,
y una sin `available` no se distingue de un fallo silencioso.


## SUPERFICIE

**Sin consumidor conocido**, medido: no aparece en `static/app.js`,
`static/index.html`, `harness/checks`, `tests`, `tools` ni `README.md`.

No prueba que este muerta -puede llamarla algo fuera del repo-, pero es la
forma del patron que en esta casa se ha repetido nueve veces.
