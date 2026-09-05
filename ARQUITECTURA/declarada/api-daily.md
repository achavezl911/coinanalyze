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


### Lo que promete · es la ruta que mas explicitamente contesta P5.4 de las 68

Medido en la foto (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z), **73 936 B**:

```
temporal_semantics       = 'mutable_current_projection'
knowledge_time_replay    = False
through_session_date     = null
projection_latest_session_date = '2026-09-04'
streak = 2   streak_source = 'cvd_spot_usd'
coverage_note = 'session_coverage_version=NULL signi...'
```

**PROMESA 1 · declara que lo que devuelve es MUTABLE, y con qué nombre.**
`temporal_semantics = "mutable_current_projection"`. La sesion en curso **va a cambiar**, y
la ruta lo dice en su cuerpo en vez de dejar que el consumidor lo descubra al volver a
pedirla. Es **P1.8** —*"¿el veredicto tiene fecha o es perpetuo?"*— contestado por el otro
lado: no es perpetuo, es explicitamente provisional.

**PROMESA 2 · declara si esta reproduciendo el pasado o proyectando el presente.**
`knowledge_time_replay = False` junto a `through_session_date = null`. Con `replay=True` y
un `through_session_date` puesto, la respuesta seria *lo que se sabia entonces*; con
`False`, es *lo que se sabe ahora*. **Es P5.4 —"¿esto se midio antes o despues de conocer el
resultado?"— resuelto con un campo booleano**, y es la unica de las 68 que lo hace asi.

**PROMESA 3 · la racha dice de QUE serie sale.** `streak = 2` con
`streak_source = "cvd_spot_usd"`, y `sources` enumera las cuatro disponibles. Una racha de 2
en spot y una de 2 en futuros no son la misma racha.

**PROMESA 4 · explica que significa su NULL.**
`coverage_note = "session_coverage_version=NULL signi…"`. Un nulo con su significado escrito
deja de ser ambiguo — es **P0.5** en la forma que mas cuesta ver.

*Que significa no cumplirlo:* que `temporal_semantics` desapareciera. Entonces una
proyeccion mutable se cachearia como si fuera un cierre, y **la bateria ya midio ese error**:
dos etiquetas de version ocupando dias distintos (P5.5).


## SUPERFICIE

**Superficie de producto**, medido.

- **checks**: `harness/checks/K03-hueco-declarado.sh:161`, `harness/checks/K43-foto-unica.sh:296`
- **panel**: `static/app.js:1482`, `static/app.js:1550`, `static/app.js:1635`
- **readme**: `README.md:70`, `README.md:90`, `README.md:409`
- **tests**: `tests/test_dashboard_presentation.py:83`
