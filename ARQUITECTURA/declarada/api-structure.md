# DECLARADA · `GET /api/structure`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-structure.md`](../rutas/api-structure.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **1** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P1.2** — ¿Cuál es la tendencia en 15m, 1h, 4h y diario?  
  <sub>`entregas/20260904-2100-bateria-trader.md:114`</sub>

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

Declara su ventana con estas claves, derivadas de los campos que publica:

- `as_of` — literal en app/scalp_logic.py:1179

## PROMESA


### Lo que promete

**PROMESA · cada capa publica SUS VOTOS, no solo su conclusion.**
En la foto (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z): `layers = [3]` con `layer`, `horizon`, `bias`, **`votes_up`**,
**`votes_total`** y `method`. Mas `as_of` y `alignment = "mixto"` en primer nivel.

`votes_up` sobre `votes_total` es lo que hace **auditable** el sesgo: un `bias = "alcista"`
con 2 de 3 votos y otro con 3 de 3 no son lo mismo, y sin los votos serian indistinguibles.
Es **P1.5** aplicado a la estructura —*"si el score no se puede recalcular desde sus
componentes publicados, no es auditable y eso es un K"*—.

**PROMESA · publica la contradiccion en vez de resolverla.** `alignment = "mixto"` con tres
capas de horizonte distinto: la ruta **no elige** por el trader. Es P1.3 y la mitad de P5.9.

*Que significa no cumplirlo:* que `votes_total` desapareciera, o que `alignment` nunca
saliera `mixto`. Lo primero rompe la auditabilidad; lo segundo delata un aplanamiento.

**La llama el panel** (`static/app.js:1577`).


## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1577`
