# DECLARADA · `GET /api/scalp/basis`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-scalp-basis.md`](../rutas/api-scalp-basis.md).
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

Claves de **primer nivel** — la respuesta declara su propio instante o periodo:

- `fut_age_seconds` (nombre)
- `fut_lag_seconds` (nombre)
- `fut_ts` (nombre)
- `now_ms` (nombre)
- `spot_age_seconds` (nombre)
- `spot_lag_seconds` (nombre)
- `spot_ts` (nombre)
- `stale_after_seconds` (nombre)

<sub>Medido leyendo el cuerpo de la respuesta en la foto, no supuesto. 8 claves temporales en total.</sub>

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

**Es la que mejor cumple esa promesa de las 68, y conviene decirlo con sus numeros.**
En la foto publica **16 campos**, de los que **nueve son temporales**: `fut_ts`, `spot_ts`,
`fut_event_ms`, `spot_event_ms`, `now_ms`, `fut_lag_seconds`, `spot_lag_seconds`,
`fut_age_seconds`, `spot_age_seconds` — mas `skew_ms`, `stale_after_seconds = 30.0` y
`status = "VALID"`.

**PROMESA · declara el DESFASE ENTRE SUS DOS PATAS, no solo su edad.**
`skew_ms = 62` es la distancia entre el evento de futuros y el de spot. Una base calculada
con dos patas de instantes distintos es una base falsa, y `skew_ms` es lo que permite
descartarla sin adivinar.

*Que significa no cumplirlo:* publicar `basis_bps` con dos patas separadas por segundos y
sin decirlo. El numero pareceria razonable siempre.

Consumidores: `static/app.js:1604` (**la llama el panel**),
`harness/checks/K43-foto-unica.sh:100` y `:139`.


## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1604`
- **readme**: `README.md:488`, `README.md:499`
- **tests**: `tests/test_v121_hardening.py:28`
