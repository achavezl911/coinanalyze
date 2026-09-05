# DECLARADA · `GET /api/market-impact`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-market-impact.md`](../rutas/api-market-impact.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **1** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P4.3** — ¿Cuánto mueve el precio mi entrada?  
  <sub>`entregas/20260904-2100-bateria-trader.md:170`</sub>

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

Declara su ventana con estas claves, derivadas de los campos que publica:

- `as_of` — literal en app/scalp_logic.py:5513

## PROMESA


### Lo que promete

**PROMESA 1 · publica su DEFINICION y sus LIMITACIONES en el cuerpo.**
En la foto: `metric = "impact_bps_per_musd"`,
`definition = "|cambio de precio en bps| / (|delta…"`, y **`limitations = [3]`**, la primera
de las cuales dice *"Es impacto agregado del mercado, no…"*.

**Solo 2 de las 68 publican un campo `limitations`**: esta y `/api/positioning`.
(Escribi "la unica" sin contarlo; el recuento sobre `derivada.json` da dos.) Contesta **P4.3** —*"¿cuanto
mueve el precio mi entrada?"*— y, mas importante, **avisa de que no lo contesta del todo**:
el impacto agregado del mercado no es el impacto de TU orden. Eso es el ¶19 aplicado a una
metrica concreta, y publicado por la propia ruta en vez de escrito en un documento aparte.

**PROMESA 2 · cada ventana declara si esta COMPLETA.**
`windows = [4]` con `window`, `impact_bps_per_musd`, `net_delta_musd`, `price_move_bps`,
`coverage` y **`coverage_complete`**. Un booleano al lado del porcentaje: la diferencia
entre "cubierto al 92 %" y "completo" no se deja al criterio del que lee.

*Que significa no cumplirlo:* que `limitations` se quitara "porque ensucia la respuesta".
Entonces un impacto agregado se leeria como impacto propio, que es exactamente el error que
el campo existe para impedir.

**La llama el panel** (`static/app.js:1568`).


## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1568`
