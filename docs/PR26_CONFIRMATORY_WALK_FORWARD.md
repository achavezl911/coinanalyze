# PR26 — walk-forward confirmatorio spec v3

PR26 implementa la remediación mínima de metodología de Audit-4 de forma
aditiva y prospectiva. No modifica walk-forward spec v1, no modifica spec v2,
no crea `pr11-fixed-kernel-v2`, no congela ningún manifest de producción, y no
selecciona un símbolo/horizonte/exchange/tamaño ganador.

## El problema

PR11/PR25 dan un motor walk-forward **exploratorio**: múltiples vistas
(`overall`/`state`/`regime`), múltiples horizontes/exchanges/tamaños,
múltiples modos de muestreo, sin corrección de multiplicidad. Ninguna celda
individual constituye evidencia confirmatoria — el propio código y la
documentación ya son explícitos en que "no group is ever ranked by OOS
performance and no 'winner' is chosen after seeing OOS". Audit-4 exige una
prueba confirmatoria real: UNA sola hipótesis primaria, pre-registrada antes
de que empiece el OOS, con inferencia consciente de la dependencia temporal
(block bootstrap), evaluada sólo al vencimiento final congelado.

## Contrato confirmatorio

`app/signal_confirmatory.py` define `ConfirmatoryContract`, un dataclass
congelado (`frozen=True, slots=True`) donde **ningún campo tiene valor por
defecto** — el llamador debe suministrar los 20 campos explícitamente:

| Campo | Significado |
|---|---|
| `primary_endpoint_version` | Versión del endpoint económico primario (`CONFIRMATORY_PRIMARY_ENDPOINT_VERSION = 1`). |
| `primary_symbol` | El único símbolo primario. |
| `primary_horizon_minutes` | El único horizonte primario (debe estar en `OUTCOME_HORIZONS_MINUTES` y en `options.horizons`). |
| `primary_sampling_mode` | Debe ser exactamente `utc_nonoverlap` — `dense_periodic` es sólo descriptivo, nunca primario. |
| `primary_exchange` | El único exchange primario. |
| `primary_size_usd` | El único tamaño primario. |
| `primary_taker_fee_bps` | Fee explícito; debe igualar el `fee_bps_per_side` congelado del manifest para `primary_exchange` — sin divergencia posible entre el fee aplicado y el fee declarado. |
| `baseline_version` | Versión del baseline unconditional/direction-matched por bloque (`BLOCK_UNCONDITIONAL_DIRECTION_MATCHED_BASELINE_VERSION = 1`). |
| `unmodeled_execution_stress_bps` | Estrés no-negativo congelado para riesgo de salida/funding/latencia no modelado. PR26 **no elige** este valor — debe suministrarlo el operador que congele un manifest futuro. |
| `inference_version` | Versión del motor de bootstrap por bloques (`BLOCK_BOOTSTRAP_INFERENCE_VERSION = 1`). |
| `block_unit` / `block_length` | Unidad de bloque calendario (`hour`\|`day`) y su multiplicador. |
| `bootstrap_repetitions` | Repeticiones del resampling. Debe ser `>= 2` (una sola repetición no puede producir un CI con dispersión real — estructuralmente degenerado). |
| `bootstrap_seed` | Seed determinista congelada. |
| `confidence_level` | Nivel de confianza (0,1) para el CI. |
| `minimum_effect_bps` | Efecto mínimo económicamente relevante, comparado contra el límite inferior del CI. Debe ser `>= 0` — un umbral negativo permitiría que un CI parcial o totalmente negativo produjera PASS. |
| `minimum_primary_blocks` | Mínimo de bloques primarios madurados para poder decidir. Debe ser `>= 2` (un solo bloque nunca puede dar un resample no degenerado). |
| `minimum_execution_data_coverage_pct` | Cobertura mínima de datos de ejecución para poder decidir. Debe estar en `(0, 100]` — `0%` de cobertura exigida es estructuralmente degenerado (equivale a no exigir cobertura). |
| `minimum_research_data_coverage_pct` | (Audit-4 A4-08) Cobertura mínima de FUENTE de investigación para poder decidir — ver [Completitud de outcomes y cobertura de fuente](#completitud-de-outcomes-y-cobertura-de-fuente-audit-4-a4-08). Debe estar en `(0, 100]`. Independiente de `minimum_execution_data_coverage_pct`: una mide cuántos slots esperados llegaron a estar certificados-visibles; la otra mide cuánta de la muestra ya evaluada es cost-evaluable. |
| `confirmatory_decision_policy` | Identificador fijo (`two_sided_block_bootstrap_ci_vs_minimum_effect_v1`). |

`validate_confirmatory_contract()` sólo valida estructura/tipo/rango — nunca
expresa una opinión sobre qué valor "recomendado" debería tener
`minimum_effect_bps`, `unmodeled_execution_stress_bps`,
`bootstrap_repetitions`, etc. (más allá de rechazar los valores
estructuralmente degenerados de la tabla arriba). Elegir los valores reales
de calibración es responsabilidad del operador que congele un manifest
spec-v3 futuro, no de esta PR.

**Exactamente UNA hipótesis primaria** es una garantía estructural, no sólo
una regla de validación: cada campo `primary_*` es un escalar (`str`/`int`/
`float`), nunca una tupla — no existe forma de codificar más de un símbolo,
horizonte, exchange, tamaño o modo de muestreo como "primario". Si en el
futuro se permite más de un símbolo en un contrato primario, un bloque deberá
preservar sus observaciones calendario conjuntas; para el primario de PR26 se
prefiere exigir un único símbolo primario explícito para evitar semántica de
pooling oculta.

`app/signal_walk_forward.py` embebe el contrato dentro del `spec` jsonb ya
existente de `signal_walk_forward_manifest` (`_static_options_spec` añade la
clave `confirmatory_contract` sólo cuando `spec_version ==
WALK_FORWARD_SPEC_VERSION_V3`) — el mismo mecanismo que v2 usó para
`research_visibility_version`. El hash del manifest (`_spec_hash`) cubre por
lo tanto cada uno de los 20 campos: mutar cualquiera de ellos cambia el hash.

## Herencia exacta del contrato PR25

Spec v3 exige la tupla científica soportada de spec v2 **exactamente igual**,
sin cambios:

```
logic_version = scalp-summary-v1
evidence_version = 6
sampling_version = 1
context_version = 1
outcome_version = 1
execution_snapshot_version = 1
research_visibility_version = 1
```

`_evaluate_fold()` no necesitó ningún cambio de código: su rama existente
`is_spec_v1 = options.spec_version == WALK_FORWARD_SPEC_VERSION` ya despacha
todo lo que no es v1 (v2 **y** v3) hacia `_fetch_period_grid_v2` /
`_fetch_execution_integrity_v2` — la misma maquinaria de conocimiento-temporal
consciente del certificado que v2 ya usaba. Spec v3 no reimplementa esa
maquinaria; la reutiliza sin cambios.

## Baseline: `block_unconditional_direction_matched_baseline_v1`

La versión original de este baseline (`clock_direction_matched_baseline_v1`)
era inválida como control: simplemente reetiquetaba `directional_return_pct`
de la MISMA fila de señal — es decir, comparaba la señal contra sí misma, y
`baseline_bps` se reportaba pero **nunca se restaba** del valor primario. El
PASS resultante medía por lo tanto la expectativa cruda de la señal
estresada, no una excedencia real sobre un control de mercado. Corregido
antes de cualquier manifest de producción (PR26 sigue sin congelar
`pr11-fixed-kernel-v3` alguno):

```python
def block_unconditional_direction_matched_baseline_bps(
    block_unconditional_market_mean_bps: float, *, direction: str
) -> float:
    if direction == "long":
        return block_unconditional_market_mean_bps
    if direction == "short":
        return -block_unconditional_market_mean_bps
    raise ValueError(...)
```

El baseline real es, por cada bloque calendario (`confirmatory_block_key`):

```
block_unconditional_market_mean_bps = mean(market_return_pct * 100)
```

calculado sobre **TODAS** las observaciones periódicas evaluadas compatibles
en ese bloque (mismo símbolo/horizonte/muestreo `utc_nonoverlap`/ventana OOS
congelada/`confirmatory_knowledge_cutoff` congelado) — **sin** restringir por
`actionable`, `direction`, `state` ni `regime_label`. La fuente es
`signal_outcome.market_return_pct` (PR5, inmutable), nunca
`directional_return_pct` — esa es la cantidad direction-agnostic, no la ya
sign-flipped hacia la señal. `app/signal_walk_forward.py`
(`_compute_confirmatory_result`) construye ese cohort (vía
`_all_periodic_evaluated`, deliberadamente más amplio que
`_actionable_evaluated`) y calcula la media por bloque; `app/signal_
confirmatory.py` sólo aplica el signo (`+mean` para `long`, `-mean` para
`short`) a la fila primaria — nunca calcula la media ni restringe qué filas
la alimentan.

Por cada fila primaria accionable en ese bloque:

```
baseline_bps = block_unconditional_direction_matched_baseline_bps(
    block_unconditional_market_mean_bps, direction=row.direction
)
primary_excess_bps = (
    modeled_net_after_fees_bps - unmodeled_execution_stress_bps - baseline_bps
)
```

`primary_excess_bps` — no el valor crudo — es lo que
`block_bootstrap_v1`/`block_bootstrap_ci` resamplean y lo que
`confirmatory_decision` evalúa. El baseline es deliberadamente sin fricción
(no se le aplican costos de trading), lo que hace la comparación
conservadora respecto de aplicarle costos también al control.
`baseline_mean_bps` se sigue reportando por separado, ahora como la media de
`baseline_bps` realmente usada (diagnóstico, coherente con el valor
efectivamente restado — no una segunda cantidad desconectada).

## Block bootstrap: `block_bootstrap_v1`

`confirmatory_block_key(observed_minute, block_unit, block_length)` es una
función pura, ancla en el epoch UNIX, de `(timestamp, block_unit,
block_length)` solamente — nunca lee el reloj de pared y es independiente de
los límites de fold, así que la misma fila siempre mapea a la misma clave de
bloque sin importar cuándo se llame.

Las filas se agrupan en `dict[str, list[float]]` **antes** de cualquier
resampling. `block_bootstrap_v1` resamplea bloques completos con reemplazo
usando una única instancia `random.Random(seed)`, creada una vez y avanzada
secuencialmente — nunca se re-siembra a mitad de corrida, nunca cae al módulo
`random` global. El resampler sólo indexa listas ya agrupadas por bloque y las
extiende completas (`pooled.extend(block_values[key])`) — no existe ninguna
ruta de código que pueda seleccionar un subconjunto de filas dentro de un
bloque. "Los bloques se resamplean completos, nunca las filas individuales" es
por lo tanto una propiedad estructural de la forma de los datos, no sólo una
convención probada por tests.

Todo el motor es stdlib puro (`random`, `statistics`, `math`) — confirmado
que no hay `numpy`/`scipy`/`pandas`/`statsmodels` en `requirements.lock` ni en
`pyproject.toml`.

El CI usa el método de percentiles sobre las medias resampleadas
(`block_bootstrap_ci`), reutilizando el mismo algoritmo de interpolación
lineal que ya existía en `_percentile()`.

## Política de decisión: `two_sided_block_bootstrap_ci_vs_minimum_effect_v1`

### `confirmatory_knowledge_cutoff`: corte de conocimiento congelado

`confirmatory_knowledge_cutoff = fold_specs[-1]["test_maturity_at"]` — el
`test_maturity_at` del ÚLTIMO fold, leído directamente del calendario ya
hasheado del manifest (nunca derivado de estado dinámico por-fold).
`confirmatory_state` es `not_ready` mientras `generated_at <
confirmatory_knowledge_cutoff`. Una vez `generated_at >=
confirmatory_knowledge_cutoff`, la elegibilidad de TODOS los datos
confirmatorios se evalúa exactamente AS OF ese corte congelado — nunca as of
el `generated_at` (reloj vivo) de la corrida actual.

Esto corrige un gap donde el corte de conocimiento usado para el filtro de
certificado (`bv.verified_visible_at <= knowledge_cutoff`,
`fv.verified_visible_at` para el outcome final) era el `generated_at` VIVO de
cada llamada — permitiendo que una recertificación tardía, ocurrida después
del primer `evaluate_walk_forward()`, apareciera en una segunda llamada
posterior aunque el fold ya estuviera `evaluation_ready` en la primera. Ahora
`_fetch_confirmatory_primary_rows` siempre recibe el mismo
`confirmatory_knowledge_cutoff` congelado como su `knowledge_cutoff`,
sin importar cuántas veces o cuánto después se reevalúe el manifest — un
certificado (de bundle o de outcome final) cuyo `verified_visible_at` cae
DESPUÉS de ese corte queda permanentemente fuera del experimento, incluso si
el reporte se vuelve a correr días después. La recuperación tardía puede
seguir reportándose diagnósticamente en otro lugar, pero nunca cambia la
muestra/CI/decisión primaria.

Una vez pasada la puerta `not_ready`, se consultan TODOS los folds del
calendario congelado (ya no se filtra por el `evaluation_ready` dinámico de
cada fold) — la determinación viene enteramente de usar siempre el mismo
`confirmatory_knowledge_cutoff` congelado en cada fetch, no de excluir folds
por su estado de integridad en vivo.

### Umbral y orden de decisión

1. Si los bloques primarios madurados son menos que `minimum_primary_blocks`,
   o la cobertura de datos de ejecución medida es menor que
   `minimum_execution_data_coverage_pct`, o `confirmatory_outcome_integrity.
   outcome_complete` es falso, o `research_data_coverage.
   research_data_coverage_pct` es menor que `minimum_research_data_coverage_pct`
   (Audit-4 A4-08, ver abajo): **inconclusive**, sin correr el bootstrap.
2. Si no: se corre `block_bootstrap_v1` sobre `primary_excess_bps` agrupado
   por bloque, pooled a través de TODOS los folds madurados (los folds siguen
   siendo diagnósticos de estabilidad temporal, nunca réplicas estadísticas
   independientes), y se calcula el CI de dos colas al `confidence_level`
   congelado.
   - `upper_ci_bps <= 0.0` → **fail** (se evalúa PRIMERO).
   - `lower_ci_bps > minimum_effect_bps` → **pass**.
   - En cualquier otro caso → **inconclusive**.

El orden defensivo (FAIL antes que PASS), combinado con
`minimum_effect_bps >= 0` obligatorio en la validación del contrato, hace
estructuralmente imposible que un CI total o parcialmente negativo produzca
PASS.

No hay parada adaptativa/opcional: `evaluate_walk_forward(conn,
manifest_name)` mantiene exactamente esa firma (sin parámetros externos), y
`_compute_confirmatory_result` es una función pura del estado ya comprometido
como de `confirmatory_knowledge_cutoff` — reevaluar un manifest ya madurado
más tarde siempre devuelve el mismo `confirmatory_result`. No se extiende un
experimento porque su CI sea ancho; un experimento nuevo más largo requeriría
un manifest prospectivo NUEVO.

El endpoint primario confirmatorio usa **sólo** filas OOS (nunca discovery):
`_fetch_confirmatory_primary_rows` reconsulta explícitamente sólo la ventana
`[test_start, test_end)` de cada fold madurado, vía la misma
`_fetch_period_grid_v2` reutilizada sin cambios.

## Completitud de outcomes y cobertura de fuente (Audit-4 A4-08)

Antes de esta corrección, `_actionable_evaluated()`/`_all_periodic_evaluated()`
filtraban a `status == "evaluated"` ANTES de que cualquier conteo ocurriera —
filas `pending`/`not_evaluable`/faltantes/de versión incorrecta desaparecían
silenciosamente del denominador confirmatorio, permitiendo que un subconjunto
positivo remanente diera PASS aunque outcomes OOS siguieran pendientes al
`confirmatory_knowledge_cutoff` congelado. Esto no es aceptable para un
experimento confirmatorio de endpoint fijo.

Dos mecanismos, distintos y no conflacionados, cierran ese gap:

### `confirmatory_outcome_integrity` — completitud de outcomes

`_fetch_confirmatory_primary_rows` ahora clasifica **toda** la grilla
`sampled` (`_sample_grid`, ya certificada-visible por bundle) ANTES de
filtrarla a evaluada, vía `_confirmatory_outcome_integrity_for_fold`. Reporta,
sumado a través de todos los folds madurados:

```
eligible_sampled_periodic_n   # filas boundary-eligible ya visibles (bundle
                               # certificado <= cutoff), independientemente
                               # de su status
evaluated_periodic_n
pending_periodic_n
not_evaluable_periodic_n
missing_or_wrong_version_n
evaluated_actionable_n        # subconjunto informativo: evaluada + actionable
unresolved_actionable_n       # subconjunto informativo: actionable + NO evaluada
outcome_complete               # True sii pending=not_evaluable=missing_or_wrong_version=0
```

Filas `boundary-purged` deterministas (`window_end` del outcome más allá del
`test_end` congelado del fold) NUNCA se cuentan — nunca fueron un outcome
esperado, y contarlas crearía incompletitud falsa.

### `research_data_coverage` — cobertura de fuente de investigación

Distinto de lo anterior: mide slots `utc_nonoverlap` esperados que ni
siquiera llegaron a estar certificados-visibles (nunca aparecieron en la
grilla en absoluto), no sólo los que están visibles pero pendientes.
`_expected_utc_nonoverlap_slot_count` recorre, de forma puramente
determinista (sin leer la base de datos ni el reloj), cada slot alineado a
época para el símbolo/horizonte primario dentro de `[test_start, test_end)`
de cada fold congelado — con la MISMA regla de alineación que `_sample_grid`
(`minute_index % horizon_minutes == 0`) y la misma ventana de outcome que
`app.signal_outcomes.outcome_window` (el inicio de la ventana es un minuto
DESPUÉS del minuto observado, nunca el minuto observado mismo). Sólo cuenta
slots cuya ventana cabe enteramente dentro de `test_end` — los boundary-purged
deterministas nunca se esperan.

```
expected_sample_slots            # conteo determinista, sin DB
certified_visible_sample_slots   # == eligible_sampled_periodic_n de arriba
research_data_coverage_pct       # certified_visible / expected * 100 (100.0
                                  # si expected_sample_slots == 0)
```

La decisión fija sólo puede proceder si `research_data_coverage_pct >=
contract.minimum_research_data_coverage_pct`; si no, **inconclusive**. Esta PR
no elige un umbral de producción — queda para la calibración futura previa al
congelamiento.

### Semántica de missingness: categorías nunca conflacionadas

1. slot de investigación esperado ausente/no-certificado (`research_data_coverage`)
2. fila de investigación visible pero outcome pending (`confirmatory_outcome_integrity`)
3. fila de investigación visible pero outcome not_evaluable (`confirmatory_outcome_integrity`)
4. snapshot de ejecución no válido (`coverage`)
5. profundidad de ejecución insuficiente (`coverage`)
6. cost-evaluable (`coverage`)

Ninguna categoría se vuelve cero silenciosamente ni desaparece del
denominador confirmatorio. La recuperación tardía (certificar/finalizar un
outcome DESPUÉS del `confirmatory_knowledge_cutoff` congelado) nunca puede
convertir un resultado `inconclusive` ya calculado en PASS — el resultado
permanece byte-idéntico, exactamente como con un certificado de bundle
tardío.

## Coverage characteristics (diagnóstico, Audit-4 A4-07)

`confirmatory_result["coverage_characteristics"]` reporta, por cada uno de
los 4 cohorts ya existentes y mantenidos distintos (`cost_evaluable`,
`snapshot_nonvalid`, `insufficient_depth`, `snapshot_missing` — nunca
conflacionados entre sí, y `insufficient_depth` nunca relabeled como dato
faltante): `n`, `gross_directional_mean_bps`, `gross_directional_median_bps`,
`abs_market_return_mean_bps`. Son diagnósticos puros — nunca alteran
PASS/FAIL/INCONCLUSIVE directamente; sólo `coverage_ok`/`blocks_ok` (sobre
`coverage["cost_evaluable_pct"]`/`primary_block_count`) lo hacen.

## Exploratorio vs confirmatorio

Las vistas `overall`/`state`/`regime`, los otros horizontes/exchanges/
tamaños, y `positive_oos_gate_count` permanecen exactamente como estaban —
exploratorios, sin corrección de multiplicidad (no se requiere FDR para
salidas puramente exploratorias) y estructuralmente desconectados de la
decisión v3: `_compute_confirmatory_result` ni siquiera referencia esos
nombres en su código fuente (verificado por test).

## CLI

`scripts/freeze_walk_forward_manifest.py` exige, bajo `--spec-version 3`,
**todos** los flags de la tupla v2 más un flag por cada uno de los 20 campos
del contrato confirmatorio (incluyendo
`--minimum-research-data-coverage-pct`, Audit-4 A4-08), además de
`--acknowledge-confirmatory-primary-hypothesis` — un flag booleano explícito
que el operador debe pasar para reconocer la única hipótesis primaria (
símbolo/horizonte/modo de muestreo/exchange/tamaño) que está a punto de
congelar. Cualquier flag confirmatorio faltante, o el flag de reconocimiento
ausente, falla cerrado (`SystemExit`) **antes** de tocar la base de datos —
no hay fallback a v1/v2/"actual". Los flags confirmatorios están además
prohibidos bajo `--spec-version 1` o `2` (falla cerrado simétrico).

`scripts/evaluate_walk_forward.py` no necesitó cambios estructurales: ya
volcaba el reporte completo como JSON genérico, así que
`confirmatory_contract`/`confirmatory_state`/`confirmatory_result` aparecen
automáticamente; sólo se añadió una línea de resumen en stdout mostrando
`confirmatory_state` cuando está presente.

## Migración

**Ninguna.** `signal_walk_forward_manifest` no tiene columnas específicas de
versión más allá del `spec jsonb` ya hasheado — el contrato confirmatorio
viaja dentro de él, igual que v2 hizo con `research_visibility_version`. Spec
v3 reutiliza `signal_research_bundle_visibility` /
`signal_outcome_final_visibility` exactamente como v2 (mismo
`visibility_version = 1`, misma tupla congelada por CHECK) — ninguna tabla
nueva, ningún archivo de migración nuevo.

## Versiones

- `WALK_FORWARD_SPEC_VERSION_V3 = 3` / `WALK_FORWARD_REPORT_VERSION_V3 = 3`
- `CONFIRMATORY_PRIMARY_ENDPOINT_VERSION = 1`
  (`measured_entry_modeled_exit_net_of_fees_stress_and_baseline_excess_v1`)
- `BLOCK_UNCONDITIONAL_DIRECTION_MATCHED_BASELINE_VERSION = 1`
  (`block_unconditional_direction_matched_baseline_v1`)
- `BLOCK_BOOTSTRAP_INFERENCE_VERSION = 1` (`block_bootstrap_v1`)
- `CONFIRMATORY_DECISION_POLICY_V1 =
  "two_sided_block_bootstrap_ci_vs_minimum_effect_v1"`
- Hereda sin cambios: `SPEC_V2_SUPPORTED_*` (tupla evidence6/
  research_visibility1), `SELECTION_POLICY = "fixed_kernel_no_selection_v1"`.

## Limitación de alcance conocida

`_fetch_confirmatory_primary_rows` reconsulta deliberadamente la grilla OOS de
cada fold madurado (en vez de ampliar el valor de retorno de
`_evaluate_fold`), para mantener aislado y de bajo riesgo el aporte de esta PR
sobre la garantía byte-for-byte de v1/v2. El costo es una consulta angosta
adicional por fold madurado, aceptable para una PR de sólo-capacidad/draft;
si el volumen de datos en un despliegue real lo justifica, una futura PR
podría ampliar `_evaluate_fold` bajo un `elif spec_version ==
WALK_FORWARD_SPEC_VERSION_V3` explícito.

## Alcance excluido

PR26 no: congela ningún manifest de producción; elige
símbolo/horizonte/exchange/tamaño/fee/stress/umbral alguno; introduce
`numpy`/`scipy`/`pandas`; modifica spec v1 o v2; ni cambia el esquema SQL.

## Rollback

Sin cambio de esquema, el rollback es borrar el commit — no se requiere una
migración DOWN. Si en el futuro se congela un `pr11-fixed-kernel-v3` real
sobre este contrato, esa PR futura deberá definir su propia estrategia de
rollback de datos, paralela a la guarda DOWN de PR25.
