# DECLARADA · `GET /api/scalp/absorption`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-scalp-absorption.md`](../rutas/api-scalp-absorption.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **1** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P4.7** — ¿Hay flujo pasivo absorbiendo en mi contra?  
  <sub>`entregas/20260904-2100-bateria-trader.md:174`</sub>

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

**MEDIDO en la foto de produccion** (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z, arco 37 387 ms).

El AST no le derivo ninguna clave temporal, pero **si publica marca de tiempo en el**
**cuerpo**. Son cosas distintas y aqui se separan: lo primero es un limite del
analisis estatico, lo segundo una afirmacion sobre el producto.

Claves **anidadas** (3), dentro de filas o bloques:

- `[].as_of` (nombre)
- `[].coverage.window_seconds` (nombre)
- `[].window` (nombre)

**Y NO tiene ninguna de primer nivel.** O sea: la respuesta fecha sus FILAS pero
no se fecha a SI MISMA. Para K43 eso importa — un consumidor que quiera saber de
cuando es la foto entera tiene que deducirlo de la fila mas reciente, y eso es
adivinar. **Candidata a familia 1 con defecto declarado.**

<sub>Medido leyendo el cuerpo de la respuesta en la foto, no supuesto. 3 claves temporales en total.</sub>

## PROMESA

### La promesa que comparte casi toda la familia `/api/scalp/*`

**Publica SU EDAD y EL UMBRAL con el que hay que juzgarla, en vez de dejar que el
consumidor lo suponga.** Medido en la foto (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z): las rutas de esta familia traen
`status` junto a alguna forma de `age`/`lag` y su `stale_after_seconds` o
`max_age_seconds`. Es lo que convierte "este numero es viejo" en una comprobacion y no en
una opinion.

*Que significa no cumplirlo:* publicar un valor rancio indistinguible de uno vivo. Es
**P0.9** de la bateria — *"si el proveedor esta caido, ¿me entero o veo el ultimo valor
congelado?"* — y su respuesta solo puede darla la propia ruta, porque nadie de fuera sabe
cuanto es demasiado para ESTE dato.

### Lo propio de esta ruta

**PROMESA · cada ventana trae SU propio `as_of` y SU propio umbral.**
En la foto devuelve **una lista de 4 ventanas**, cada una con `window`, `as_of`,
`fut_delta`, `fut_volume`, `delta_ratio` y **`min_ratio`**. El umbral viaja con el dato.

Eso importa porque `min_ratio` **no es una constante**: sale de `metric_baseline` (p75 de
esa ventana y ese simbolo), y el codigo lo explica con su medida —
*"medido, 0.10 dejaba pasar el 78 % de las ventanas de 3 m y el 13 % de las de 4 h"*
(`app/scalp_logic.py:209-210`). Un umbral unico o pasa casi todo o no pasa nada.

*Que significa no cumplirlo:* publicar `delta_ratio` sin su `min_ratio`, y entonces
"absorcion fuerte" no significaria nada comparable entre ventanas.

**Es familia 2 de K43 aunque solo pida `symbol`**: cada elemento declara su propia ventana.
La candidata derivada de la firma decia 1, y aqui se corrige con cita.


## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1552`
- **tests**: `tests/test_metrics_endpoint.py:140`
