# DECLARADA · `GET /api/hypothesis`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-hypothesis.md`](../rutas/api-hypothesis.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **2** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P1.12** — ¿Qué me haría cambiar de opinión ahora mismo?  
  <sub>`entregas/20260904-2100-bateria-trader.md:124`</sub>
- **P1.9** — ¿Qué hipótesis está viva y cuál se ha invalidado?  
  <sub>`entregas/20260904-2100-bateria-trader.md:121`</sub>

## VENTANA

**PENDIENTE de familia.** parametros ['direction', 'entry', 'exchange', 'fee_bps_per_side', 'funding_bps', 'hypothesis', 'order_type', 'profile', 'setup', 'size_usd', 'slippage_bps', 'stop', 'symbol', 'target']: no encaja en 1/2/3 sin leerla

Declara su ventana con estas claves, derivadas de los campos que publica:

- `as_of` — literal en app/api.py:1187

## PROMESA


### Lo que promete

**PROMESA 1 · publica QUE LA INVALIDARIA, no solo por que es plausible.**
Entre sus 24 campos derivados: **`invalidations`**, **`pending_conditions`**,
`setup_observables`, `setup_state` y `evidence`. Contesta **P1.12** —*"¿que me haria cambiar
de opinion ahora mismo?"*— que la bateria marca como la prueba del ¶19: *"si no hay
respuesta, el producto no cumple su ¶19"*.

**Es la unica de las 68 que publica un campo de invalidacion.**

**PROMESA 2 · declara cuanto dato tenia para decidir.**
`data_coverage_pct` y `profile_coverage_pct`, ademas de `as_of` y `counts`. Una hipotesis
construida con el 40 % de sus insumos y otra con el 100 % **no se pintan igual**, y aqui la
diferencia es un numero y no una impresion. Es **P0.4** —*"¿que antigüedad tiene el dato mas
viejo que entra en este calculo?"*— contestado por el lado de la cobertura.

**PROMESA 3 · el coste entra en la hipotesis, no aparte.**
Acepta `entry`, `target`, `stop`, `size_usd`, `fee_bps_per_side`, `order_type`, `exchange`,
`slippage_bps` y `funding_bps`, y publica `execution`. Es la respuesta a **P3.2** —*"¿cual
es el R:R real, ya con coste?"*—: el R:R y el coste salen de la MISMA llamada, asi que no
puede haber dos definiciones de coste como avisa **P4.1**.

*Que significa no cumplirlo:* que `invalidations` viniera vacio con una hipotesis activa.
Una hipotesis que no se puede invalidar no es una hipotesis.

**P1.9 comprobado, y la bateria tiene razon.** Dice que esta ruta *"llega por bundle, no
suelta"*, y el panel lo confirma: `state.hypothesisData = componentes.hypothesis` en
`static/app.js:1506`, dentro del render que consume `/api/ai/context/bundle`. El panel
**nunca pide `/api/hypothesis` por su cuenta** — su unico rastro en `app.js` es el consumo
del bloque del bundle.

O sea que la ruta responde 200 suelta -en la foto lo hace-, pero **su camino al producto es
el bundle**. Para el radio de impacto eso importa: tocar el bundle rompe la hipotesis en
pantalla aunque esta ruta siga sana.


## SUPERFICIE

**Instrumento interno**, medido.

- **checks**: `harness/checks/K79-el-coste-calla-lo-que-le-falta.sh:109`, `harness/checks/K79-el-coste-calla-lo-que-le-falta.sh:140`
- **tests**: `tests/test_v150_desk_snapshot.py:126`
