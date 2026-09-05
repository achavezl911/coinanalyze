# DECLARADA · `GET /api/ai/context`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-ai-context.md`](../rutas/api-ai-context.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

**NINGUNA de las 66 preguntas de la bateria la nombra.**

Medido sobre `entregas/20260904-2100-bateria-trader.md`: ninguna fila de las 54 (P0.1..P5.9) ni de las 12
(S1..S12) cita esta ruta en su columna de destino ni en la de medicion.

Eso NO significa que no sirva: significa que **el trader no le ha formulado**
**una pregunta**. Si es un instrumento interno, lo normal es que no la haya.
Si es superficie de producto y no contesta ninguna pregunta, merece mirarse.

## VENTANA

**PENDIENTE de familia.** parametros ['bucket_bps', 'profile', 'symbol']: no encaja en 1/2/3 sin leerla

Declara su ventana con estas claves, derivadas de los campos que publica:

- `generated_at` — literal en app/ai_context.py:851

## PROMESA


### Lo que promete · y aqui P0.1 se mide, no se supone

Medido sobre el cuerpo de la foto (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z), contando bloques de primer nivel y buscando en
cada uno una clave temporal con valor ISO:

```
/api/ai/context   101 021 B
  instante de RAIZ ....................... generated_at = 2026-09-04T22:33:02.403024+00:00
  bloques de primer nivel ................ 39
  de esos, CON su propio instante ........ 21
  SIN instante propio .................... 18
  instantes DISTINTOS en el cuerpo ....... 35
```

**PROMESA 1 · publica su version de esquema.** `schema_version = "ai_context.v2"`. Un
consumidor que reciba `v3` sabe que tiene que releer, en vez de fallar campo a campo.

**PROMESA 2 · 21 de sus 39 bloques declaran SU propio instante**, no el de la raiz:
`absorption.as_of`, `basis.fut_ts`, `cross_asset.as_of`, `cvd_matrix.as_of`,
`delta_matrix.as_of`, `external_macro_context.as_of`, `feed_quality.generated_at`,
`liquidation_map.as_of`, `context_metadata.generated_at`…

**PROMESA 3 · lleva su propio prompt.** `interpretation_prompt` viaja en el cuerpo, asi que
la IA que consume no interpreta con un prompt que este en otro sitio y pueda divergir.

### P0.1 · lo que la bateria avisa, medido aqui

> *"hay **27 instantes distintos** dentro de una foto y la etiqueta de la raiz se toma a
> mitad del armado. Una etiqueta unica sobre datos de vendimias distintas miente MAS que 43
> etiquetas."* (`entregas/20260904-2100-bateria-trader.md:96`)

**Confirmado, y la cifra ha crecido: son 35**, no 27. Pero el diagnostico correcto no es que
la ruta mienta — es el contrario del que se podria suponer:

- **21 bloques SI se fechan a si mismos.** Para esos, `generated_at` de la raiz no es una
  etiqueta unica sobre vendimias distintas: es un dato mas, y el bueno esta al lado.
- **18 no lo hacen**, y son los que heredan la etiqueta de la raiz sin haberla ganado:
  `cvd_swing_90d`, `data_confidence`, `data_quality`, `divergences`, `liq_burst`,
  `liquidation_levels`, `market_memory_2y`, `operator_read`…

**PROMESA declarada:** *publica su instante de raiz y el de 21 de sus 39 bloques; para los
otros 18 el consumidor NO puede saber de cuando es el dato.* Que no lo cumpla seria que los
21 dejaran de fecharse; el defecto vivo son los 18, y **esta escrito en vez de tapado**.

**Es K candidata y no la abro yo**, porque el criterio es una decision de producto: ¿tienen
que fecharse los 39, o basta con que se sepa cuales no? El criterio ejecutable existe y es
barato — *"ROJO si un bloque de primer nivel de `/api/ai/context` no declara instante
propio"* daria hoy 18 — pero elegir el umbral es de Alejandro.


## SUPERFICIE

**Instrumento interno**, medido.

- **checks**: `harness/checks/K43-foto-unica.sh:196`, `harness/checks/K43-foto-unica.sh:235`, `harness/checks/K43-foto-unica.sh:284`
- **readme**: `README.md:62`, `README.md:414`, `README.md:518`
