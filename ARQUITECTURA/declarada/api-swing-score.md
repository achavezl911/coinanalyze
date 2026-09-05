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

**PENDIENTE, y el motivo es que no la he medido.** No esta entre las rutas cuyo cuerpo he
leido en la foto, y sus campos no se derivan del AST lo bastante como para sostener una
promesa.

Lo que **si** se sabe y esta en su ficha derivada: la bateria le asigna **P1.5** —*"¿que
dice el score de swing y de que se compone?"*, con el criterio *"recalcular el score desde
sus componentes publicados; si no se puede, el score no es auditable y eso es un K"*— y
**S10** —*"¿el score de swing puede ser negativo? un score que solo vive en positivo no
puede recomendar un corto"*—.

Las dos son comprobables y ninguna con una foto de un instante:

```sh
harness/bin/api '/api/swing-score?symbol=BTCUSDT' | python3 -m json.tool
harness/bin/prodsql "SELECT MIN(swing_score), MAX(swing_score), COUNT(*)
  FROM daily_verdict WHERE session_date >= now() - interval '30 days'"
```

**S10 es la barata y la que mas delata**: si el minimo de 30 dias es >= 0, el score no puede
recomendar un corto y el producto es asimetrico por construccion.


## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1479`, `static/app.js:1581`
