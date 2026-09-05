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

**PENDIENTE.** No se ha escrito que promete esta ruta ni que significa no cumplirlo.

Una promesa vale si es comprobable: "publica el instante de construccion", "no
publica un 0 sin testigo", "la senal dura al menos N minutos". Si la ruta no
promete nada comprobable, eso tambien se escribe.

## SUPERFICIE

**Instrumento interno**, medido.

- **checks**: `harness/checks/K79-el-coste-calla-lo-que-le-falta.sh:109`, `harness/checks/K79-el-coste-calla-lo-que-le-falta.sh:140`
- **tests**: `tests/test_v150_desk_snapshot.py:126`
