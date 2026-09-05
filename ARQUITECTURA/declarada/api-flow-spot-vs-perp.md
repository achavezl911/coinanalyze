# DECLARADA · `GET /api/flow/spot-vs-perp`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-flow-spot-vs-perp.md`](../rutas/api-flow-spot-vs-perp.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

**NINGUNA de las 66 preguntas de la bateria la nombra.**

Medido sobre `entregas/20260904-2100-bateria-trader.md`: ninguna fila de las 54 (P0.1..P5.9) ni de las 12
(S1..S12) cita esta ruta en su columna de destino ni en la de medicion.

Eso NO significa que no sirva: significa que **el trader no le ha formulado**
**una pregunta**. Si es un instrumento interno, lo normal es que no la haya.
Si es superficie de producto y no contesta ninguna pregunta, merece mirarse.

## VENTANA

Familia **2** de K43 — coverage de su propia serie.

Derivado de su firma: pide ['days', 'interval']: coverage de su propia serie.

**MEDIDO en la foto de produccion** (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z, arco 37 387 ms).

El AST no le derivo ninguna clave temporal, pero **si publica marca de tiempo en el**
**cuerpo**. Son cosas distintas y aqui se separan: lo primero es un limite del
analisis estatico, lo segundo una afirmacion sobre el producto.

Claves **anidadas** (1), dentro de filas o bloques:

- `rows[].ts` (nombre)

**Y NO tiene ninguna de primer nivel.** O sea: la respuesta fecha sus FILAS pero
no se fecha a SI MISMA. Para K43 eso importa — un consumidor que quiera saber de
cuando es la foto entera tiene que deducirlo de la fila mas reciente, y eso es
adivinar. **Candidata a familia 1 con defecto declarado.**

<sub>Medido leyendo el cuerpo de la respuesta en la foto, no supuesto. 1 claves temporales en total.</sub>

## PROMESA


### Lo que promete

Medido en la foto (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z), **204 422 B** — la respuesta mas grande de las 68:

**PROMESA 1 · nombra LOS DOS SIMBOLOS que compara, no solo uno.**
`symbol = "BTCUSDT_PERP.A"` y **`spot_symbol = "BTCUSD.A"`**, mas
`venue = "binance (perp .A vs spot .A)"`. Un diferencial spot-perp entre dos instrumentos que
no se nombran es un numero sin sujeto; aqui los dos lados estan escritos, y el venue tambien.

**PROMESA 2 · declara su unidad y su bucket.** `unit = "USD"`, `interval = "4hour"`.

Es **P1.1** —*"¿hay una senal activa ahora y de que lado?"*— por el eje del flujo, y la
bateria le pone una advertencia medida: *"el diferencial spot-futuros NO vota direccion"*.
Que esta ruta publique los dos simbolos es lo que permite **comprobar** esa afirmacion en vez
de creerla: se puede re-derivar el diferencial desde las dos series.

*Que significa no cumplirlo:* que `spot_symbol` desapareciera. El mismo numero calculado
contra `BTCUSDT` spot o contra `BTCUSD.A` es distinto, y sin el campo no habria forma de
saber cual.

**Nadie la llama**: es una de las rutas cuyos unicos rastros son menciones (ver ficha
derivada).


## SUPERFICIE

**El recuento vive en la ficha derivada**, que se regenera: [`rutas/api-flow-spot-vs-perp.md`](../rutas/api-flow-spot-vs-perp.md), seccion *Superficie*. Aqui NO se copia el numero.

La primera version de estas fichas lo copiaba y envejecio el mismo dia: el andamio escribio "sin consumidor conocido" cuando el detector no veia `RUTA=/api/x` ni `$VAR/api/x`, y al arreglarlo la prosa quedo mintiendo mientras el JSON del mismo commit decia otra cosa. K88 lo caza ahora (brazo 5), y esto quita la causa.

Lo que si aporta esta capa: de lo que hay, **nada es una llamada**. Una ruta de la que solo se habla en comentarios no tiene consumidor: tiene quien la nombra.
