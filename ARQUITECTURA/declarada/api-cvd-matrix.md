# DECLARADA · `GET /api/cvd-matrix`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-cvd-matrix.md`](../rutas/api-cvd-matrix.md).
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

- `as_of` — literal en app/scalp_logic.py:2883
- `window_meta` — literal en app/scalp_logic.py:2885

## PROMESA


### Lo que promete

**PROMESA 1 · publica su instante DOS veces, y la segunda con contexto.**
`as_of` en primer nivel y **`window_meta`** con su propio `as_of`, `window_type`,
`windows_are_nested`, `independent_confirmations`, `acceleration_measured` y
`reset_timezone`.

**PROMESA 2 · declara que sus ventanas SE SOLAPAN.**
`windows_are_nested` e `independent_confirmations` — el mismo contrato que
`/api/scalp/delta-matrix`, y por la misma razon: **seis ventanas anidadas que "confirman" lo
mismo son UNA observacion repetida seis veces**. Es **P5.3** contestado por la propia ruta
en vez de deducido por el consumidor.

**PROMESA 3 · declara su huso de reinicio.** `reset_timezone`. Un CVD de sesion depende de
donde se corta el dia, y dos rutas que corten distinto dan cifras distintas del mismo
mercado. Publicarlo es lo que permite compararlas.

*Que significa no cumplirlo:* que `independent_confirmations` desapareciera y quedaran seis
ventanas sueltas. El consumidor contaria seis confirmaciones donde hay una.


## SUPERFICIE

**Instrumento interno**, medido.

- **checks**: `harness/checks/K83-la-ventana-pide-la-fuente-que-no-tiene-el-dato.sh:170`, `harness/checks/K84-dos-matrices-una-cifra.sh:84`
