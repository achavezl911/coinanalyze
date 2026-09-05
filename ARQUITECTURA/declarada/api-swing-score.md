# DECLARADA · `GET /api/swing-score`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-swing-score.md`](../rutas/api-swing-score.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **2** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P1.5** — ¿Qué dice el score de swing y de qué se compone?  
  <sub>`entregas/20260904-2100-bateria-trader.md:117`</sub>
- **S10** — ¿El score de swing puede ser negativo?  
  <sub>`entregas/20260904-2100-bateria-trader.md:327`</sub>

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

Declara su ventana con estas claves, derivadas de los campos que publica:

- `as_of` — literal en app/scalp_logic.py:6167
- `as_of_semantics` — literal en app/scalp_logic.py:6168

## PROMESA


### Lo que promete

**PROMESA · el score de swing es SIMETRICO: puede recomendar cortos.**

Medido en 140 por el operador el 2026-09-05 sobre `daily_verdict`:

```
MIN(swing_score) = -55   MAX = 60   filas = 81
control de la ventana: 81 filas · 27 dias distintos · 2026-08-07 a 2026-09-05
```

Contesta **S10** de la bateria —*"¿el score de swing puede ser negativo? un score que solo
vive en positivo no puede recomendar un corto"*— y la respuesta es **si**: el minimo real es
**-55** sobre 81 filas de 27 dias distintos.

**S10 NO es K.** El criterio que yo mismo escribi era *"si el minimo de 30 dias es >= 0, es
K"*, y con -55 no se cumple: el producto no es asimetrico por este eje.

*Que significa no cumplirlo:* que el minimo subiera a 0 en una ventana de 30 dias. Entonces
el score no podria recomendar un corto y la mitad del ¶19 —"el Dashboard tiene que decir
LARGO, CORTO o NO ENTRAR"— seria imposible por construccion. **El control va en la misma
consulta**: el recuento de dias distintos, porque un minimo negativo sacado de 3 dias no
dice lo mismo que uno sacado de 27.

**PENDIENTE · P1.5 sigue abierta y su motivo no es el tiempo.**
*"Recalcular el score desde sus componentes publicados; si no se puede, el score no es
auditable y eso es un K."* No he leido el cuerpo de esta ruta en la foto, asi que **no se si
publica sus componentes**. Es una peticion, no una consulta:

```sh
harness/bin/api '/api/swing-score?symbol=BTCUSDT' | python3 -m json.tool
```

Si la respuesta trae el score y **no** trae de que se compone, es K por P1.5.

## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1479`, `static/app.js:1581`
