# DECLARADA · `GET /api/range/validate`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-range-validate.md`](../rutas/api-range-validate.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **1** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P2.3** — ¿Es un rango válido o me lo estoy inventando?  
  <sub>`entregas/20260904-2100-bateria-trader.md:139`</sub>

## VENTANA

Familia **2** de K43 — coverage de su propia serie.

Derivado de su firma: pide ['days']: coverage de su propia serie.

Declara su ventana con estas claves, derivadas de los campos que publica:

- `from` — literal en app/scalp_logic.py:1599
- `to` — literal en app/scalp_logic.py:1600
- `window_days` — literal en app/scalp_logic.py:1598

## PROMESA

**PENDIENTE.** No se ha escrito que promete esta ruta ni que significa no cumplirlo.

Una promesa vale si es comprobable: "publica el instante de construccion", "no
publica un 0 sin testigo", "la senal dura al menos N minutos". Si la ruta no
promete nada comprobable, eso tambien se escribe.

## SUPERFICIE

**Superficie de producto**, medido.

- **checks**: `harness/checks/K76-la-ventana-que-pides.sh:97`
- **panel**: `static/app.js:2890`
