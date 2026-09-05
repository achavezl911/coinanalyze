# DECLARADA · `GET /api/scalp/delta-matrix`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-scalp-delta-matrix.md`](../rutas/api-scalp-delta-matrix.md).
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

Claves **anidadas** (5), dentro de filas o bloques:

- `[].as_of` (nombre)
- `[].futures_end_gap_seconds` (nombre)
- `[].spot_end_gap_seconds` (nombre)
- `[].window` (nombre)
- `[].window_type` (nombre)

**Y NO tiene ninguna de primer nivel.** O sea: la respuesta fecha sus FILAS pero
no se fecha a SI MISMA. Para K43 eso importa — un consumidor que quiera saber de
cuando es la foto entera tiene que deducirlo de la fila mas reciente, y eso es
adivinar. **Candidata a familia 1 con defecto declarado.**

<sub>Medido leyendo el cuerpo de la respuesta en la foto, no supuesto. 5 claves temporales en total.</sub>

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

**PROMESA · declara que sus ventanas SE SOLAPAN, en el propio cuerpo.**
En la foto devuelve **12 elementos**, cada uno con `window`, `as_of`, `window_type`,
**`windows_are_nested`**, **`independent_confirmations`** y `acceleration_measured`.

`windows_are_nested` es una promesa poco comun y muy valiosa: dice que las ventanas de la
matriz **no son observaciones independientes**. Doce ventanas anidadas que "confirman" lo
mismo son UNA observacion repetida doce veces, y `independent_confirmations` da el numero
que de verdad se puede contar.

*Que significa no cumplirlo:* contar doce confirmaciones cuando hay una. Es exactamente el
error que la bateria persigue en **P5.3** -"¿la muestra solapa ventanas?"- llevado a la
respuesta: aqui no hay que deducirlo, la ruta lo dice.


## SUPERFICIE

**Superficie de producto**, medido.

- **checks**: `harness/checks/K83-la-ventana-pide-la-fuente-que-no-tiene-el-dato.sh:216`, `harness/checks/K84-dos-matrices-una-cifra.sh:86`
- **panel**: `static/app.js:1551`
