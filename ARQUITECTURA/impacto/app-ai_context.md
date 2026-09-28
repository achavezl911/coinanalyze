# Impacto · `app/ai_context.py`

> Generado por `harness/bin/arquitectura`. No editar a mano.

23 funciones de este fichero alcanzan alguna ruta. **Tocar cualquiera de ellas puede cambiar las rutas que se listan.**

El radio POR TABLA va con **dos numeros**: `k=0` es lo que la funcion escribe ella misma (**exacto**), y `k<=2` sube por los llamadores (**cota superior declarada**). Nunca uno solo.

| funcion | linea | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto |
|---|---|---|---|---|---|
| [`data_confidence_row`](#data-confidence-row) | 524 | 3 | **0** | 0 | **3** |
| [`orderbook_freshness`](#orderbook-freshness) | 661 | 3 | **0** | 0 | **3** |
| [`quality_score`](#quality-score) | 612 | 3 | **0** | 0 | **3** |
| [`_armar_sobre`](#-armar-sobre) | 902 | 2 | **0** | 0 | **2** |
| [`_corte_unico`](#-corte-unico) | 848 | 2 | **0** | 0 | **2** |
| [`_round_number`](#-round-number) | 219 | 2 | **0** | 0 | **2** |
| [`build_ai_symbol_context`](#build-ai-symbol-context) | 884 | 2 | **0** | 0 | **2** |
| [`build_operator_read`](#build-operator-read) | 740 | 2 | **0** | 0 | **2** |
| [`compact_dict`](#compact-dict) | 246 | 2 | **0** | 0 | **2** |
| [`compact_value`](#compact-value) | 230 | 2 | **0** | 0 | **2** |
| [`daily_data`](#daily-data) | 298 | 2 | **0** | 0 | **2** |
| [`daily_history`](#daily-history) | 387 | 2 | **0** | 0 | **2** |
| [`field_disambiguation`](#field-disambiguation) | 67 | 2 | **0** | 0 | **2** |
| [`latest_orderbook`](#latest-orderbook) | 673 | 2 | **0** | 0 | **2** |
| [`latest_snapshot`](#latest-snapshot) | 291 | 2 | **0** | 0 | **2** |
| [`liquidation_levels`](#liquidation-levels) | 701 | 2 | **0** | 0 | **2** |
| [`local_alerts`](#local-alerts) | 790 | 2 | **0** | 0 | **2** |
| [`normalize_profile`](#normalize-profile) | 212 | 2 | **0** | 0 | **2** |
| [`recent_signals`](#recent-signals) | 685 | 2 | **0** | 0 | **2** |
| [`rough_token_estimate`](#rough-token-estimate) | 276 | 2 | **0** | 0 | **2** |
| [`sin_perder_los_nulos`](#sin-perder-los-nulos) | 257 | 2 | **0** | 0 | **2** |
| [`verdict_history`](#verdict-history) | 479 | 2 | **0** | 0 | **2** |
| [`build_ai_context`](#build-ai-context) | 1072 | 1 | **0** | 0 | **1** |

## data_confidence_row

`app/ai_context.py:524` · clave completa `app.ai_context.data_confidence_row`

**Radio exacto: 3 rutas** de 70 · **cota superior: 3** (igual al exacto)

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 3 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## orderbook_freshness

`app/ai_context.py:661` · clave completa `app.ai_context.orderbook_freshness`

**Radio exacto: 3 rutas** de 70 · **cota superior: 3** (igual al exacto)

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 3 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## quality_score

`app/ai_context.py:612` · clave completa `app.ai_context.quality_score`

**Radio exacto: 3 rutas** de 70 · **cota superior: 3** (igual al exacto)

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 3 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## _armar_sobre

`app/ai_context.py:902` · clave completa `app.ai_context._armar_sobre`

**Radio exacto: 2 rutas** de 70 · **cota superior: 2** (igual al exacto)

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 3 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## _corte_unico

`app/ai_context.py:848` · clave completa `app.ai_context._corte_unico`

**Radio exacto: 2 rutas** de 70 · **cota superior: 2** (igual al exacto)

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 3 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## _round_number

`app/ai_context.py:219` · clave completa `app.ai_context._round_number`

**Radio exacto: 2 rutas** de 70 · **cota superior: 2** (igual al exacto)

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 4 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## build_ai_symbol_context

`app/ai_context.py:884` · clave completa `app.ai_context.build_ai_symbol_context`

**Radio exacto: 2 rutas** de 70 · **cota superior: 2** (igual al exacto)

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 3 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## build_operator_read

`app/ai_context.py:740` · clave completa `app.ai_context.build_operator_read`

**Radio exacto: 2 rutas** de 70 · **cota superior: 2** (igual al exacto)

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## compact_dict

`app/ai_context.py:246` · clave completa `app.ai_context.compact_dict`

**Radio exacto: 2 rutas** de 70 · **cota superior: 2** (igual al exacto)

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 10 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## compact_value

`app/ai_context.py:230` · clave completa `app.ai_context.compact_value`

**Radio exacto: 2 rutas** de 70 · **cota superior: 2** (igual al exacto)

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 9 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## daily_data

`app/ai_context.py:298` · clave completa `app.ai_context.daily_data`

**Radio exacto: 2 rutas** de 70 · **cota superior: 2** (igual al exacto)

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## daily_history

`app/ai_context.py:387` · clave completa `app.ai_context.daily_history`

**Radio exacto: 2 rutas** de 70 · **cota superior: 2** (igual al exacto)

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## field_disambiguation

`app/ai_context.py:67` · clave completa `app.ai_context.field_disambiguation`

**Radio exacto: 2 rutas** de 70 · **cota superior: 2** (igual al exacto)

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 4 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## latest_orderbook

`app/ai_context.py:673` · clave completa `app.ai_context.latest_orderbook`

**Radio exacto: 2 rutas** de 70 · **cota superior: 2** (igual al exacto)

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## latest_snapshot

`app/ai_context.py:291` · clave completa `app.ai_context.latest_snapshot`

**Radio exacto: 2 rutas** de 70 · **cota superior: 2** (igual al exacto)

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## liquidation_levels

`app/ai_context.py:701` · clave completa `app.ai_context.liquidation_levels`

**Radio exacto: 2 rutas** de 70 · **cota superior: 2** (igual al exacto)

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## local_alerts

`app/ai_context.py:790` · clave completa `app.ai_context.local_alerts`

**Radio exacto: 2 rutas** de 70 · **cota superior: 2** (igual al exacto)

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## normalize_profile

`app/ai_context.py:212` · clave completa `app.ai_context.normalize_profile`

**Radio exacto: 2 rutas** de 70 · **cota superior: 2** (igual al exacto)

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## recent_signals

`app/ai_context.py:685` · clave completa `app.ai_context.recent_signals`

**Radio exacto: 2 rutas** de 70 · **cota superior: 2** (igual al exacto)

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## rough_token_estimate

`app/ai_context.py:276` · clave completa `app.ai_context.rough_token_estimate`

**Radio exacto: 2 rutas** de 70 · **cota superior: 2** (igual al exacto)

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 4 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## sin_perder_los_nulos

`app/ai_context.py:257` · clave completa `app.ai_context.sin_perder_los_nulos`

**Radio exacto: 2 rutas** de 70 · **cota superior: 2** (igual al exacto)

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## verdict_history

`app/ai_context.py:479` · clave completa `app.ai_context.verdict_history`

**Radio exacto: 2 rutas** de 70 · **cota superior: 2** (igual al exacto)

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## build_ai_context

`app/ai_context.py:1072` · clave completa `app.ai_context.build_ai_context`

**Radio exacto: 1 rutas** de 70 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 1 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

