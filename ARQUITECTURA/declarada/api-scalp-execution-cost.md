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

**PENDIENTE.** No se ha escrito que promete esta ruta ni que significa no cumplirlo.

Una promesa vale si es comprobable: "publica el instante de construccion", "no
publica un 0 sin testigo", "la senal dura al menos N minutos". Si la ruta no
promete nada comprobable, eso tambien se escribe.

## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1567`
