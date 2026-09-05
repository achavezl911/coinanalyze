# DECLARADA · `GET /api/positioning`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-positioning.md`](../rutas/api-positioning.md).
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

- `age_seconds` — literal en app/scalp_logic.py:5599
- `ts` — literal en app/scalp_logic.py:5598

## PROMESA


### Lo que promete · es la ruta que mejor declara SU MUESTRA de las 68

Medido en la foto (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z), **542 B**:

```
unit = 'porcentaje de cuentas'      sample_count = 8600     sample_days = 29.99
long_pct / short_pct / ratio        sample_is_full_month = True
median_sample / percentile_sample   ts = '2026-09-04T22:25:00Z'   age_seconds = 489.1
limitations = [2]  'Es reparto de CUENTAS, no de nocional...'
```

**PROMESA 1 · dice EN QUE UNIDAD esta, y la unidad es la trampa.**
`unit = "porcentaje de cuentas"` y `limitations[0] = "Es reparto de CUENTAS, no de
nocional…"`. Un 50/50 de cuentas con el 90 % del nocional de un lado **no es un 50/50**, y
la ruta lo dice en su propio cuerpo en vez de dejar que se lea al reves.

**Es una de las solo 2 rutas de las 68 que publican `limitations`** (la otra es
`/api/market-impact`).

**PROMESA 2 · publica su MUESTRA entera, no solo el percentil.**
`sample_count = 8600`, `sample_days = 29.99` y **`sample_is_full_month`**. Es **P5.2**
—*"¿sobre cuantas operaciones se calcula? n=3 y n=300 no se pintan igual"*— contestado sin
que haya que preguntarlo, y `sample_is_full_month` es la respuesta a la pregunta de detras:
*¿el percentil se calculo sobre una ventana completa o sobre lo que habia?*

**PROMESA 3 · publica su EDAD, no solo su instante.** `ts` mas `age_seconds = 489.1`. La
resta ya viene hecha, asi que un consumidor no puede equivocarse de huso al calcularla.

**PROMESA 4 · el percentil viene con su mediana.** `percentile_sample = 21.8` junto a
`median_sample = 1.1422`. Un percentil sin la distribucion detras no se puede juzgar.

*Que significa no cumplirlo:* que `unit` o `limitations` desaparecieran. El numero seguiria
siendo correcto y **se leeria mal**, que es peor.


## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1608`
