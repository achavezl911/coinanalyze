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
defecto** — el llamador debe suministrar los 19 campos explícitamente:

| Campo | Significado |
|---|---|
| `primary_endpoint_version` | Versión del endpoint económico primario (`CONFIRMATORY_PRIMARY_ENDPOINT_VERSION = 1`). |
| `primary_symbol` | El único símbolo primario. |
| `primary_horizon_minutes` | El único horizonte primario (debe estar en `OUTCOME_HORIZONS_MINUTES` y en `options.horizons`). |
| `primary_sampling_mode` | Debe ser exactamente `utc_nonoverlap` — `dense_periodic` es sólo descriptivo, nunca primario. |
| `primary_exchange` | El único exchange primario. |
| `primary_size_usd` | El único tamaño primario. |
| `primary_taker_fee_bps` | Fee explícito; debe igualar el `fee_bps_per_side` congelado del manifest para `primary_exchange` — sin divergencia posible entre el fee aplicado y el fee declarado. |
| `baseline_version` | Versión del baseline clock/direction-matched (`CLOCK_DIRECTION_MATCHED_BASELINE_VERSION = 1`). |
| `unmodeled_execution_stress_bps` | Estrés no-negativo congelado para riesgo de salida/funding/latencia no modelado. PR26 **no elige** este valor — debe suministrarlo el operador que congele un manifest futuro. |
| `inference_version` | Versión del motor de bootstrap por bloques (`BLOCK_BOOTSTRAP_INFERENCE_VERSION = 1`). |
| `block_unit` / `block_length` | Unidad de bloque calendario (`hour`\|`day`) y su multiplicador. |
| `bootstrap_repetitions` | Repeticiones del resampling. |
| `bootstrap_seed` | Seed determinista congelada. |
| `confidence_level` | Nivel de confianza (0,1) para el CI. |
| `minimum_effect_bps` | Efecto mínimo económicamente relevante, comparado contra el límite inferior del CI. |
| `minimum_primary_blocks` | Mínimo de bloques primarios madurados para poder decidir. |
| `minimum_execution_data_coverage_pct` | Cobertura mínima de datos de ejecución para poder decidir. |
| `confirmatory_decision_policy` | Identificador fijo (`two_sided_block_bootstrap_ci_vs_minimum_effect_v1`). |

`validate_confirmatory_contract()` sólo valida estructura/tipo/rango — nunca
expresa una opinión sobre qué valor "recomendado" debería tener
`minimum_effect_bps`, `unmodeled_execution_stress_bps`,
`bootstrap_repetitions`, etc. Elegir esos valores es responsabilidad del
operador que congele un manifest spec-v3 futuro, no de esta PR.

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
lo tanto cada uno de los 19 campos: mutar cualquiera de ellos cambia el hash.

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

## Baseline: `clock_direction_matched_baseline_v1`

```python
def clock_direction_matched_baseline_bps(directional_return_pct: float) -> float:
    return directional_return_pct * 100.0
```

`directional_return_pct` de PR5 (`app.signal_outcomes.compute_path_metrics`)
ya es el retorno de precio crudo sobre la ventana exacta de la observación,
con el signo invertido para calzar con la dirección declarada de la señal
(positivo si el mercado se movió en la dirección de la señal). Es, por
construcción, ya "clock-matched" (misma ventana) y "direction-matched" (mismo
convenio de signo que la señal). Esta función sólo nombra, versiona y
documenta esa cantidad como el baseline confirmatorio — **nunca la recalcula**
desde barras OHLCV: PR11/PR26 leen únicamente la salida ya inmutable de
PR4-PR10.

El valor primario por fila reutiliza la matemática de costo ya existente
(`_execution_measure`, entrada medida / salida modelada simétrica,
`symmetric_entry_book_v1`) menos el nuevo término de estrés:

```
primary_row_value_bps = modeled_net_after_fees_bps - unmodeled_execution_stress_bps
```

`baseline_bps` se reporta por separado como una cifra diagnóstica nombrada y
hasheada — no se resta una segunda vez, porque ya está embebida dentro de
`modeled_net_after_fees_bps` vía la matemática simétrica de costo existente.

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

`confirmatory_state` es `not_ready` mientras el **último** fold congelado no
alcance `clock_state == "ready_by_clock"` — una puerta puramente de reloj,
nunca acoplada a integridad. Un fold intermedio con un efecto positivo
enorme, evaluado solo, nunca puede producir un PASS confirmatorio: el gate es
sobre el ÚLTIMO fold de todo el calendario congelado, no sobre cualquier fold
individual. Un fold anterior bloqueado por integridad, o que aún no sea
`evaluation_ready`, simplemente contribuye cero bloques primarios una vez
pasada esa puerta de reloj — lo que puede empujar hacia `inconclusive` vía
`minimum_primary_blocks`/`minimum_execution_data_coverage_pct`, pero nunca
vuelve a extender `not_ready`.

En la madurez final:

1. Si los bloques primarios madurados son menos que `minimum_primary_blocks`,
   o la cobertura de datos de ejecución medida es menor que
   `minimum_execution_data_coverage_pct`: **inconclusive**, sin correr el
   bootstrap.
2. Si no: se corre `block_bootstrap_v1` sobre el valor primario agrupado por
   bloque, pooled a través de TODOS los folds madurados (los folds siguen
   siendo diagnósticos de estabilidad temporal, nunca réplicas estadísticas
   independientes), y se calcula el CI de dos colas al `confidence_level`
   congelado.
   - `lower_ci_bps > minimum_effect_bps` → **pass**.
   - `upper_ci_bps <= 0.0` → **fail**.
   - En cualquier otro caso → **inconclusive**.

No hay parada adaptativa/opcional: `evaluate_walk_forward(conn,
manifest_name)` mantiene exactamente esa firma (sin parámetros externos), y
`_compute_confirmatory_result` es una función pura del estado ya comprometido
— reevaluar un manifest ya madurado más tarde siempre devuelve el mismo
`confirmatory_result`. No se extiende un experimento porque su CI sea ancho;
un experimento nuevo más largo requeriría un manifest prospectivo NUEVO.

El endpoint primario confirmatorio usa **sólo** filas OOS (nunca discovery):
`_fetch_confirmatory_primary_rows` reconsulta explícitamente sólo la ventana
`[test_start, test_end)` de cada fold madurado, vía la misma
`_fetch_period_grid_v2` reutilizada sin cambios.

## Exploratorio vs confirmatorio

Las vistas `overall`/`state`/`regime`, los otros horizontes/exchanges/
tamaños, y `positive_oos_gate_count` permanecen exactamente como estaban —
exploratorios, sin corrección de multiplicidad (no se requiere FDR para
salidas puramente exploratorias) y estructuralmente desconectados de la
decisión v3: `_compute_confirmatory_result` ni siquiera referencia esos
nombres en su código fuente (verificado por test).

## CLI

`scripts/freeze_walk_forward_manifest.py` exige, bajo `--spec-version 3`,
**todos** los flags de la tupla v2 más un flag por cada uno de los 19 campos
del contrato confirmatorio, además de
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
  (`measured_entry_modeled_exit_net_of_fees_and_stress_v1`)
- `CLOCK_DIRECTION_MATCHED_BASELINE_VERSION = 1`
  (`clock_direction_matched_baseline_v1`)
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
