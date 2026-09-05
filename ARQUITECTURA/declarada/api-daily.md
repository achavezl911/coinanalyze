# DECLARADA · `GET /api/daily`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-daily.md`](../rutas/api-daily.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

**NINGUNA de las 66 preguntas de la bateria la nombra.**

Medido sobre `entregas/20260904-2100-bateria-trader.md`: ninguna fila de las 54 (P0.1..P5.9) ni de las 12
(S1..S12) cita esta ruta en su columna de destino ni en la de medicion.

Eso NO significa que no sirva: significa que **el trader no le ha formulado**
**una pregunta**. Si es un instrumento interno, lo normal es que no la haya.
Si es superficie de producto y no contesta ninguna pregunta, merece mirarse.

## VENTANA

Familia **3** de K43 — su propio as_of bajo demanda.

Derivado de su firma: pide ['as_of']: el operador elige el momento.

Declara su ventana con estas claves, derivadas de los campos que publica:

- `knowledge_time_replay` — literal en app/api.py:596
- `projection_latest_session_date` — literal en app/api.py:592
- `through_session_date` — literal en app/api.py:589

## PROMESA

**PENDIENTE.** No se ha escrito que promete esta ruta ni que significa no cumplirlo.

Una promesa vale si es comprobable: "publica el instante de construccion", "no
publica un 0 sin testigo", "la senal dura al menos N minutos". Si la ruta no
promete nada comprobable, eso tambien se escribe.

## SUPERFICIE

**Superficie de producto**, medido.

- **checks**: `harness/checks/K03-hueco-declarado.sh:161`, `harness/checks/K43-foto-unica.sh:296`
- **panel**: `static/app.js:1482`, `static/app.js:1550`, `static/app.js:1635`
- **readme**: `README.md:70`, `README.md:90`, `README.md:409`
- **tests**: `tests/test_dashboard_presentation.py:83`
