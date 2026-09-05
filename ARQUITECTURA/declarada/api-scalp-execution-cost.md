# DECLARADA · `GET /api/scalp/execution-cost`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-scalp-execution-cost.md`](../rutas/api-scalp-execution-cost.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **1** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P4.1** — ¿Cuánto me cuesta entrar con MI tamaño?  
  <sub>`entregas/20260904-2100-bateria-trader.md:168`</sub>

## VENTANA

**PENDIENTE de familia.** parametros ['entry', 'exchange', 'fee_bps_per_side', 'funding_bps', 'order_type', 'profile', 'size_usd', 'sizes', 'stop', 'symbol', 'target']: no encaja en 1/2/3 sin leerla

Declara su ventana con estas claves, derivadas de los campos que publica:

- `as_of` — literal en app/scalp_logic.py:5154
- `stale_after_seconds` — literal en app/scalp_logic.py:5155

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

**PROMESA · el coste es POR VENUE y la ruta dice explicitamente que no hay uno combinado.**
En la foto: `note = "coste por venue; no existe 'combined'…"`, `venues = [2]` con su
`exchange`, `ts`, `age_seconds` y `status` cada uno, `as_of`,
`stale_after_seconds = 30.0`, `status = "VALID"`.

Es la respuesta directa a la trampa de **P4.1**: dos rutas con dos definiciones de "coste".
Esta lo resuelve **negandose a promediar** y diciendolo en el cuerpo.

*Que significa no cumplirlo:* que apareciera un coste "combinado" sin decir de que libro
sale. Un coste medio de dos libros distintos no es el coste de ninguna operacion real.

**PROMESA · valida el tamaño en vez de recortarlo en silencio.**
`422 · "hasta 8 tamanios, cada uno entre 0 y 5.000.000 USD"` (`app/api.py:1401`).

Consumidores: `static/app.js:1567` (**la llama el panel**), `K43-foto-unica.sh:105`.


## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1567`
