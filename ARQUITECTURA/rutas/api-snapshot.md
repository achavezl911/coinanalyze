# `GET /api/snapshot`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `snapshot` · `app/api.py:614` (cuerpo hasta la 630) · decorador en la linea 613.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str | None` | `None` | no |

## Campos que publica

35 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `btr_15m` | columna de metrics_snapshot (sql/schema.sql) |
| `btr_1h` | columna de metrics_snapshot (sql/schema.sql) |
| `btr_24h` | columna de metrics_snapshot (sql/schema.sql) |
| `cvd_diff_24h` | columna de metrics_snapshot (sql/schema.sql) |
| `cvd_diff_ses` | columna de metrics_snapshot (sql/schema.sql) |
| `cvd_fut_imbalance_24h` | columna de metrics_snapshot (sql/schema.sql) |
| `cvd_nyse_session` | columna de metrics_snapshot (sql/schema.sql) |
| `cvd_session` | columna de metrics_snapshot (sql/schema.sql) |
| `cvd_spot_24h` | columna de metrics_snapshot (sql/schema.sql) |
| `cvd_spot_imbalance_24h` | columna de metrics_snapshot (sql/schema.sql) |
| `cvd_spot_session` | columna de metrics_snapshot (sql/schema.sql) |
| `delta_3min` | columna de metrics_snapshot (sql/schema.sql) |
| `fr_avg` | columna de metrics_snapshot (sql/schema.sql) |
| `liq_ratio_24h` | columna de metrics_snapshot (sql/schema.sql) |
| `long_liq_24h` | columna de metrics_snapshot (sql/schema.sql) |
| `metrics_cutoff_at` | columna de metrics_snapshot (sql/schema.sql) |
| `oi` | columna de metrics_snapshot (sql/schema.sql) |
| `oi_bybit` | columna de metrics_snapshot (sql/schema.sql) |
| `oi_chg_24h_pct` | columna de metrics_snapshot (sql/schema.sql) |
| `oi_vol_24h_ratio` | columna de metrics_snapshot (sql/schema.sql) |
| `pfr_avg` | columna de metrics_snapshot (sql/schema.sql) |
| `pfr_fr_div` | columna de metrics_snapshot (sql/schema.sql) |
| `price` | columna de metrics_snapshot (sql/schema.sql) |
| `price_cutoff_at` | columna de metrics_snapshot (sql/schema.sql) |
| `price_dir_1h` | columna de metrics_snapshot (sql/schema.sql) |
| `regime_label` | columna de metrics_snapshot (sql/schema.sql) |
| `regime_logic_version` | columna de metrics_snapshot (sql/schema.sql) |
| `regime_score` | columna de metrics_snapshot (sql/schema.sql) |
| `short_liq_24h` | columna de metrics_snapshot (sql/schema.sql) |
| `spot_vol_24h` | columna de metrics_snapshot (sql/schema.sql) |
| `symbol` | columna de metrics_snapshot (sql/schema.sql) |
| `ts` | columna de metrics_snapshot (sql/schema.sql) |
| `vol_24h` | columna de metrics_snapshot (sql/schema.sql) |
| `whale_intensity` | columna de metrics_snapshot (sql/schema.sql) |
| `whale_label` | columna de metrics_snapshot (sql/schema.sql) |

**Lo que de esta respuesta NO se sabe** (y por eso no se rellena):

- la respuesta pasa por dict(), que no se puede seguir
- devuelve la variable 'row', cuyo contenido no se resuelve estaticamente
- la cadena de retornos pasa de 4 saltos: no se sigue mas para no adivinar
- campos derivados del SELECT * sobre metrics_snapshot: son las columnas declaradas en sql/schema.sql, no una lista escrita a mano. Si la consulta filtra columnas en codigo, esta lista es un techo, no la respuesta exacta

Forma de la respuesta segun el AST: lista, lista de objetos, valor escalar.

Tipo declarado en la firma: `Any`.

## Tablas que toca

LEE:

- `metrics_snapshot` — `sql/schema.sql:945`, 35 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:666`
  - la llena `app.metrics.insert_snapshot` (INSERT) — `app/metrics.py:683`

## Funciones que la componen

3 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.latest_snapshot` — `app/api.py:466`
- `app.api.records` — `app/api.py:234`
- `app.api.validate_symbol` — `app/api.py:221`

<details><summary>Llamadas que salen del arbol o no se resuelven (4)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `HTTPException`
- `app.state.pool.acquire`
- `conn.fetch`
- `list`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:223` | una funcion de su cierre |
| 404 | No data | `app/api.py:620` | el propio handler |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | — | `harness/checks/K31-cubos.py:109` |
| **readme** | — | `README.md:401` |
| **tests** | — | `tests/test_pr24_daily_historical_integrity.py:89` |

**Nadie la llama.** Sus 3 rastros son todos MENCION -comentario,
docstring o documento-. Es la forma del patron que en esta casa se ha repetido
nueve veces: algo de lo que se habla y nadie ejecuta. **Merece una mirada.**

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **1** — solo pide symbol (o nada): estado ambiente.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `metrics_cutoff_at`
- `price_cutoff_at`
- `ts`

## Capa DECLARADA

**Declarada** en [`declarada/api-snapshot.md`](../declarada/api-snapshot.md) — pregunta del trader,
familia de ventana decidida, promesa y superficie, cada una con su cita.

## Radio de impacto

El radio por tabla va con **dos numeros**: `k=0` es lo que la funcion escribe ella
misma (**exacto**) y `k<=2` sube por los llamadores (**cota superior declarada**;
lo que este mas arriba no se afirma).

Las funciones de esta ruta, y a cuantas rutas MAS llega cada una. Un numero alto
significa que ese arreglo de dos lineas no es de dos lineas:

| funcion | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto | detalle |
|---|---|---|---|---|---|
| `app.api.validate_symbol` | 62 | **0** | 0 | **62** | [impacto](../impacto/app-api.md) |
| `app.api.records` | 22 | **0** | 7 ↑ | **22** | [impacto](../impacto/app-api.md) |
| `app.api.latest_snapshot` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-api.md) |
| `app.api.snapshot` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
