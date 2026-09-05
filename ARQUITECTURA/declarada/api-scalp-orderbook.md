# DECLARADA · `GET /api/scalp/orderbook`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-scalp-orderbook.md`](../rutas/api-scalp-orderbook.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **3** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P4.2** — ¿Hay profundidad suficiente para salir?  
  <sub>`entregas/20260904-2100-bateria-trader.md:169`</sub>
- **P4.6** — ¿El spread ahora es normal o está ancho?  
  <sub>`entregas/20260904-2100-bateria-trader.md:173`</sub>
- **S8** — ¿La profundidad que se publica es la que voy a consumir?  
  <sub>`entregas/20260904-2100-bateria-trader.md:325`</sub>

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

**MEDIDO en la foto de produccion** (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z, arco 37 387 ms).

El AST no le derivo ninguna clave temporal, pero **si publica marca de tiempo en el**
**cuerpo**. Son cosas distintas y aqui se separan: lo primero es un limite del
analisis estatico, lo segundo una afirmacion sobre el producto.

Claves **anidadas** (4), dentro de filas o bloques:

- `freshness.age_seconds` (nombre)
- `freshness.as_of` (nombre)
- `freshness.max_age_seconds` (nombre)
- `rows[].ts` (nombre)

**Y NO tiene ninguna de primer nivel.** O sea: la respuesta fecha sus FILAS pero
no se fecha a SI MISMA. Para K43 eso importa — un consumidor que quiera saber de
cuando es la foto entera tiene que deducirlo de la fila mas reciente, y eso es
adivinar. **Candidata a familia 1 con defecto declarado.**

<sub>Medido leyendo el cuerpo de la respuesta en la foto, no supuesto. 4 claves temporales en total.</sub>

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

**PROMESA · la frescura va en un bloque PROPIO, no mezclada con los datos.**
En la foto: `freshness = {status, as_of, age_seconds, max_age_seconds}` al lado de
`rows[3]`. Separarlo importa: un consumidor puede comprobar la frescura **sin entender el
libro**, y un `rows` vacio con `freshness.status` malo no se confunde con un mercado quieto.

*Que significa no cumplirlo:* el defecto que vigila `harness/checks/K13-vacio-o-rancio.sh`
-en sus lineas 33, 92 y 94-, que es literalmente "vacio o rancio" tratados como lo mismo.

**PENDIENTE · la trampa de P4.2 no la he comprobado.** La bateria avisa de **dos formas**
de esta respuesta (`{rows:[…]}` e indexada por venue). En la foto salio `rows`, pero una
sola foto no descarta la otra forma. Comando para cerrarlo:

```sh
harness/bin/api '/api/scalp/orderbook?symbol=ETHUSDT' | head -c 400
```


## SUPERFICIE

**Superficie de producto**, medido.

- **checks**: `harness/checks/K13-vacio-o-rancio.sh:32`, `harness/checks/K79-el-coste-calla-lo-que-le-falta.sh:89`
- **panel**: `static/app.js:1564`
