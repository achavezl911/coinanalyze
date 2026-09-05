# DECLARADA · `GET /api/trend-matrix`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-trend-matrix.md`](../rutas/api-trend-matrix.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **3** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P1.2** — ¿Cuál es la tendencia en 15m, 1h, 4h y diario?  
  <sub>`entregas/20260904-2100-bateria-trader.md:114`</sub>
- **P1.3** — ¿Los marcos se contradicen entre sí?  
  <sub>`entregas/20260904-2100-bateria-trader.md:115`</sub>
- **S12** — ¿La matriz de tendencia produce «bajista» tantas veces como «alcista»?  
  <sub>`entregas/20260904-2100-bateria-trader.md:329`</sub>

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

Declara su ventana con estas claves, derivadas de los campos que publica:

- `as_of` — literal en app/scalp_logic.py:5990

## PROMESA

**PENDIENTE.** No se ha escrito que promete esta ruta ni que significa no cumplirlo.

Una promesa vale si es comprobable: "publica el instante de construccion", "no
publica un 0 sin testigo", "la senal dura al menos N minutos". Si la ruta no
promete nada comprobable, eso tambien se escribe.

## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1478`, `static/app.js:1580`
- **tests**: `tests/test_v150_desk_snapshot.py:126`
