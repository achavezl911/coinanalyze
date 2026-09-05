# DECLARADA · `GET /api/scalp/liquidations`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-scalp-liquidations.md`](../rutas/api-scalp-liquidations.md).
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

**MEDIDO en la foto de produccion** (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z, arco 37 387 ms).

El AST no le derivo ninguna clave temporal, pero **si publica marca de tiempo en el**
**cuerpo**. Son cosas distintas y aqui se separan: lo primero es un limite del
analisis estatico, lo segundo una afirmacion sobre el producto.

Claves **anidadas** (2), dentro de filas o bloques:

- `matrix[].window` (nombre)
- `recent[].ts` (nombre)

**Y NO tiene ninguna de primer nivel.** O sea: la respuesta fecha sus FILAS pero
no se fecha a SI MISMA. Para K43 eso importa — un consumidor que quiera saber de
cuando es la foto entera tiene que deducirlo de la fila mas reciente, y eso es
adivinar. **Candidata a familia 1 con defecto declarado.**

<sub>Medido leyendo el cuerpo de la respuesta en la foto, no supuesto. 2 claves temporales en total.</sub>

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

**PROMESA · cada ventana declara CUANTOS VENUES la respaldan.**
En la foto: `matrix = [6]` con `window`, `long_liq`, `short_liq`, `events` y **`venues`**.

Es la respuesta a **P0.6** -"¿cuantos venues respaldan esta cifra?"-. Sin `venues`, un cero
de un venue caido y un cero de mercado en calma son el mismo cero.

*Que significa no cumplirlo:* el defecto de **P0.5**, un cero sin testigo. Con `events` y
`venues` al lado, `long_liq = 0` con `events = 0` y `venues = 2` es una afirmacion
-no hubo liquidaciones-, y con `venues = 0` es una ausencia de medida.

**PENDIENTE · no he comprobado que `venues` sea distinto de 0 en algun caso real.** La foto
es una sola y de un momento tranquilo. Comando:

```sh
harness/bin/api '/api/scalp/liquidations?symbol=BTCUSDT_PERP.A' | python3 -m json.tool | grep -c venues
```


## SUPERFICIE

**Superficie de producto**, medido.

- **checks**: `harness/checks/K80-la-matriz-cambia-de-universo.sh:113`, `harness/checks/K80-la-matriz-cambia-de-universo.sh:156`
- **panel**: `static/app.js:1605`
