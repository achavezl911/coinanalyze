# DECLARADA · `GET /api/snapshot`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-snapshot.md`](../rutas/api-snapshot.md).
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

Declara su ventana con estas claves, derivadas de los campos que publica:

- `metrics_cutoff_at` — columna de metrics_snapshot (sql/schema.sql)
- `price_cutoff_at` — columna de metrics_snapshot (sql/schema.sql)
- `ts` — columna de metrics_snapshot (sql/schema.sql)

## PROMESA


### Lo que promete

**PROMESA 1 · separa el corte de las METRICAS del corte del PRECIO.**
Entre sus 35 campos derivados estan **`metrics_cutoff_at`** y **`price_cutoff_at`**, ademas
de `ts`. Tres marcas distintas en una misma fila, y no es redundancia: un precio de hace 5
segundos junto a una metrica de hace 3 minutos es lo normal, y fundirlas en un `ts` unico
seria el defecto que **P0.1** describe —*"una etiqueta unica sobre datos de vendimias
distintas miente MAS que 43 etiquetas"*—.

**PROMESA 2 · publica la fila entera del snapshot, sin recortar.**
Los campos salen de `SELECT DISTINCT ON (symbol) * FROM metrics_snapshot` (`app/api.py:622`)
y son las 35 columnas declaradas en `sql/schema.sql:945`. Que sea `*` importa: un consumidor
que necesite una columna nueva la tiene el dia que se anade, sin tocar la ruta.

*Que significa no cumplirlo:* que apareciera una lista blanca de columnas. Entonces
`metrics_snapshot` y lo que se publica dejarian de ser lo mismo, y las 8 rutas que leen esa
tabla podrian divergir entre si.

**Nadie la llama.** Sus tres rastros son menciones (`K31-cubos.py:109`, `README.md:401`,
`tests/…:89`). Es la puerta directa a la tabla que alimenta a otras 8 rutas, y ninguna la
usa: todas leen la tabla por su cuenta.


## SUPERFICIE

**Instrumento interno**, medido.

- **readme**: `README.md:401`
- **tests**: `tests/test_pr24_daily_historical_integrity.py:89`
