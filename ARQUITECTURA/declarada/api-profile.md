# DECLARADA · `GET /api/profile`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-profile.md`](../rutas/api-profile.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

**NINGUNA de las 66 preguntas de la bateria la nombra.**

Medido sobre `entregas/20260904-2100-bateria-trader.md`: ninguna fila de las 54 (P0.1..P5.9) ni de las 12
(S1..S12) cita esta ruta en su columna de destino ni en la de medicion.

Eso NO significa que no sirva: significa que **el trader no le ha formulado**
**una pregunta**. Si es un instrumento interno, lo normal es que no la haya.
Si es superficie de producto y no contesta ninguna pregunta, merece mirarse.

## VENTANA

**PENDIENTE de familia.** parametros ['profile', 'symbol']: no encaja en 1/2/3 sin leerla

Declara su ventana con estas claves, derivadas de los campos que publica:

- `as_of` — literal en app/api.py:1366

## PROMESA


### Lo que promete · es la segunda ruta que publica su propia INVALIDACION

Medido en la foto (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z), **1 928 B**:

**PROMESA 1 · publica QUE LA INVALIDA.**
`invalidation = "La tesis se invalida si la capa de…"`. Junto a `/api/hypothesis`, son **las
unicas dos de las 68** que traen un campo de invalidacion. Es **P1.12** —*"¿que me haria
cambiar de opinion ahora mismo?"*—, que la bateria marca como la prueba del ¶19.

**PROMESA 2 · publica sus CONTRADICCIONES en vez de resolverlas.**
`contradictions = [1]` con `entre`, `detalle`, `efecto` y `motivo`. No dice solo que hay una
contradiccion: dice **entre que capas**, **que efecto tiene** y **por que**. Es **P1.10**
—*"¿el setup de largo contradice al de corto?"*— y la bateria es exacta al respecto: *"la
contradiccion es informacion; el silencio sobre la contradiccion es el defecto"*.

**PROMESA 3 · declara lo que le FALTA, con la fraccion.**
`missing_data = [1]: "confirmacion: 2/3"` y `coverage_pct = 85.0`. No es un booleano: dice
**cual** de las tres capas esta incompleta y **cuanto**.

**PROMESA 4 · separa lo que PESA de lo que solo se consulta.**
`reference_only = [3]: '8h'` junto a `layers = {contexto, confirmacion, gatillo}`. Un
horizonte de referencia que no vota no se confunde con uno que si.

**PROMESA 5 · dice que sus pesos son una CONVENCION.**
`weights_note = "Los pesos por capa son una convenci…"`. El `net_score = 0.059` sale de una
ponderacion elegida, no descubierta, y la ruta no lo presenta como una medida.

*Que significa no cumplirlo:* que `contradictions` viniera siempre vacio. Es el mismo
sintoma que P1.3 describe para la matriz de tendencia: *"si son 0, sospechar del metodo, no
del mercado"*.


## SUPERFICIE

**Instrumento interno**, medido.

- **tests**: `tests/test_v150_desk_snapshot.py:126`
