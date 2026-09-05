# DECLARADA · `GET /api/desk/state`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-desk-state.md`](../rutas/api-desk-state.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

**NINGUNA de las 66 preguntas de la bateria la nombra.**

Medido sobre `entregas/20260904-2100-bateria-trader.md`: ninguna fila de las 54 (P0.1..P5.9) ni de las 12
(S1..S12) cita esta ruta en su columna de destino ni en la de medicion.

Eso NO significa que no sirva: significa que **el trader no le ha formulado**
**una pregunta**. Si es un instrumento interno, lo normal es que no la haya.
Si es superficie de producto y no contesta ninguna pregunta, merece mirarse.

## VENTANA

**PENDIENTE de familia.** parametros ['direction', 'profile', 'setup', 'symbol']: no encaja en 1/2/3 sin leerla

Declara su ventana con estas claves, derivadas de los campos que publica:

- `as_of` — literal en app/api.py:1288

## PROMESA


### Lo que promete

Medido en la foto (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z):

```
/api/desk/state   21 926 B
  instante de RAIZ ....................... as_of = 2026-09-04T22:33:03.644050+00:00
  bloques de primer nivel ................ 3   (components, partial, source_timestamps)
  instantes DISTINTOS en el cuerpo ....... 1
```

**PROMESA 1 · publica un bloque dedicado a la procedencia temporal.**
`source_timestamps` con `book_lag_seconds`, `book_status`, `basis_status`,
`liquidations_measured`, `collectors` y `liquidations_last_event_age_s`.

Es una solucion **distinta** a la de `/api/ai/context` para el mismo problema: en vez de que
cada bloque lleve su `as_of`, **hay un bloque que declara el retraso de cada fuente**. Para
P0.1 es defendible: un `book_lag_seconds` dice mas que un `as_of` del libro, porque ya trae
la resta hecha.

**PROMESA 2 · declara lo que le FALTA.** `partial` es un bloque de primer nivel. Una mesa
armada con cinco de seis componentes y otra con seis **no se pintan igual**, y aqui la
diferencia es un campo y no una impresion.

**PROMESA 3 · `components` enumera los seis de los que se compone**: `trend_matrix`,
`delta_matrix`, `profile`, `hypothesis`, `scalp`, `data_quality`. La mesa no es una caja
negra: se puede ir a cada uno.

*Que significa no cumplirlo:* que `partial` desapareciera. Entonces una mesa incompleta
seria indistinguible de una completa, que es **P0.5** aplicado al agregado.

**PENDIENTE · lo que no puedo sostener con la foto.** `liquidations_measured` y
`basis_status` son campos de estado cuyo dominio no conozco: no se si `basis_status` puede
valer algo distinto de `VALID`, ni si `liquidations_measured` es un booleano o un recuento.
La peticion, **con el simbolo real comprobado**:

```sh
harness/bin/api '/api/desk/state?symbol=BTCUSDT_PERP.A' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['source_timestamps'])"
```


## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1488`
- **readme**: `README.md:34`
- **tests**: `tests/test_v150_desk_snapshot.py:128`
