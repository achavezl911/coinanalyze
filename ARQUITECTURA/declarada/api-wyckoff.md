# DECLARADA · `GET /api/wyckoff`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-wyckoff.md`](../rutas/api-wyckoff.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **2** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P1.4** — ¿En qué fase de Wyckoff estamos?  
  <sub>`entregas/20260904-2100-bateria-trader.md:116`</sub>
- **S11** — ¿Wyckoff distingue acumulación de distribución, o sólo detecta una?  
  <sub>`entregas/20260904-2100-bateria-trader.md:328`</sub>

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

**PENDIENTE · no se le ha derivado ninguna clave temporal.** O no publica
marca de tiempo, o sus campos no son derivables estaticamente. La foto de
produccion lo decide: `entregas/20260904-foto-prod-1.json`.

## PROMESA

**PENDIENTE.** No se ha escrito que promete esta ruta ni que significa no cumplirlo.

Una promesa vale si es comprobable: "publica el instante de construccion", "no
publica un 0 sin testigo", "la senal dura al menos N minutos". Si la ruta no
promete nada comprobable, eso tambien se escribe.

## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1481`, `static/app.js:1583`
- **readme**: `README.md:149`
- **tests**: `tests/test_wyckoff.py:106`
