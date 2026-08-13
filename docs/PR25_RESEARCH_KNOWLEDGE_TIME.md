# PR25 research knowledge-time visibility

PR25 corrige Audit 3 (A3-01/A3-02/A3-03) de forma aditiva y prospectiva. No
reescribe evidencia histórica, no reinterpreta `pr11-fixed-kernel-v1`, no crea
`pr11-fixed-kernel-v2`.

## A3-01 — certificación de visibilidad post-commit

`signal_observation.created_at`, `signal_replay_frame.created_at`,
`signal_outcome.created_at` y `signal_outcome.finalized_at` se siguen
poblando con `clock_timestamp()` **antes** del `COMMIT` de la transacción del
colector (`persist_scalp_signals` en `app/scalp_collector.py`). Eso los deja
correctos como *provenance* (cuándo el proceso decidió/finalizó algo), pero
los invalida como prueba de *visibilidad histórica*: un `knowledge_cutoff`
fijo puede caer después de ese timestamp almacenado pero antes del `COMMIT`
real, filtrando filas que un lector histórico no podía conocer todavía.

Esos campos **no se tocan** y **no se reinterpretan**. PR25 añade un contrato
nuevo, aditivo y append-only en `app/signal_visibility.py`:

- `RESEARCH_VISIBILITY_VERSION = 1`.
- `signal_research_bundle_visibility`: certifica que un bundle de
  investigación periódico completo (`signal_observation` + `signal_replay_frame`
  + los 8 horizontes programados de `signal_outcome` + los 2 snapshots de
  `signal_execution_snapshot`) ya estaba comprometido y visible.
- `signal_outcome_final_visibility`: certifica que un estado final
  (`evaluated`/`not_evaluable`) de `signal_outcome` ya estaba comprometido y
  visible.

`verified_visible_at` **no es** el commit timestamp de Postgres. Significa:
"una transacción posterior leyó exitosamente el estado fuente ya comprometido,
y sólo DESPUÉS de esa lectura exitosa obtuvo este `clock_timestamp()`". Es una
cota superior conservadora: prueba que la fuente era visible a más tardar en
`verified_visible_at`. La fila de certificado puede comprometerse después de
`verified_visible_at` sin problema — ese timestamp atestigua el estado FUENTE
que la transacción certificadora ya leyó exitosamente, no el commit de la
propia fila de certificado.

Secuencia obligatoria (nunca al revés):

1. nueva transacción, iniciada después de que la transacción fuente comprometió;
2. `SELECT` y validación del estado fuente comprometido (bundle completo /
   estado final);
3. `SELECT clock_timestamp()`;
4. `INSERT` del certificado append-only (`ON CONFLICT DO NOTHING`).

`app/signal_visibility.py` es idempotente, batch acotado, sin
`datetime.now()` como reloj, y nunca certifica evidencia v1-v5. La
certificación se integra en el colector (`app/scalp_collector.py`) recién
después de que la transacción fuente (`fenced_transaction`) salió con éxito —
es siempre una transacción distinta y posterior, nunca un savepoint anidado
dentro de la escritura fuente. Un fallo de certificación no revierte
evidencia ya comprometida; sólo se loguea y se reintenta en el próximo ciclo.

### Evidence v6 es prospectivo

`SIGNAL_EVIDENCE_VERSION` avanza de 5 a 6 (`app/signal_ledger.py`). Evidence
v1-v5 sigue siendo histórica bajo su semántica original de publicación. Sólo
evidence v6 es elegible para `RESEARCH_VISIBILITY_VERSION = 1`. No hay
backfill de certificados para v1-v5, ni siquiera si esas filas son visibles
hoy — la tabla `signal_research_bundle_visibility` tiene un CHECK que fija
`evidence_version = 6` para `visibility_version = 1`.

## A3-02 — CLI de freeze expone la tupla científica completa

`scripts/freeze_walk_forward_manifest.py` era el único escritor productivo de
PR11 y no exponía ninguna versión científica, heredando siempre
`evidence_version=1` por defecto de dataclass. Ahora expone
`--spec-version`, `--logic-version`, `--evidence-version`,
`--sampling-version`, `--context-version`, `--outcome-version`,
`--execution-snapshot-version` y `--research-visibility-version`.

La invocación legacy (sin flags) sigue resolviendo exactamente lo mismo que
antes: spec v1, `evidence_version=1`, comportamiento idempotente para
`pr11-fixed-kernel-v1`. Crear un manifest `--spec-version 2` exige intención
explícita del operador: **todas** las versiones científicas deben
suministrarse a mano — no hay fallback a "latest/current" ni mapeo silencioso
de spec v1 a la tupla v2. Omitir cualquiera de ellas falla cerrado antes de
tocar la base de datos. Esta PR no crea ningún manifest de producción spec-v2.

## PR11 spec v2 — contrato consciente de la certificación

`app/signal_walk_forward.py` soporta explícitamente `WALK_FORWARD_SPEC_VERSION
= 1` (histórico, congelado) y `WALK_FORWARD_SPEC_VERSION_V2 = 2` (nuevo). Spec
v1 no cambia ni un bit: mismo hash, misma validación, mismo comportamiento de
evaluación, mismo `pr11-fixed-kernel-v1`. La tupla prospectiva soportada por
spec v2 es:

```
logic_version = scalp-summary-v1
evidence_version = 6
sampling_version = 1
context_version = 1
outcome_version = 1
execution_snapshot_version = 1
research_visibility_version = 1
```

Bajo spec v2, la elegibilidad de observación/replay/outcome-scheduling exige
el certificado `signal_research_bundle_visibility` con
`verified_visible_at <= knowledge_cutoff`; sin certificado, la observación
está simplemente ausente de la grilla — no sólo anulada. El estado final de
`signal_outcome` sólo se trata como final en un cutoff histórico si existe el
certificado `signal_outcome_final_visibility` correspondiente con
`verified_visible_at <= knowledge_cutoff`; si no, se proyecta cerrado como
`pending`, igual que la semántica de proyección tardía de spec v1 pero
anclada al certificado, nunca a `created_at`/`finalized_at`. Los snapshots de
ejecución admitidos por spec v2 derivan únicamente del mismo bundle
certificado.

`WALK_FORWARD_REPORT_VERSION = 1` se mantiene sin cambios para spec v1;
`WALK_FORWARD_REPORT_VERSION_V2 = 2` añade un bloque
`knowledge_visibility_contract` aditivo al reporte de spec v2. Un
`spec_version` desconocido falla cerrado. Esta PR no crea ningún
`pr11-fixed-kernel-v2`.

## A3-03 — mapa congelado evidencia → regime logic

`app/signal_regime.py` interpretaba evidencia histórica contra el
`REGIME_LOGIC_VERSION` **vivo** importado de `app/metrics.py`. Un futuro bump
de esa constante reinterpretaría silenciosamente evidencia 3/4/5 ya
publicada. Ahora usa un mapa explícito y congelado,
`FROZEN_EVIDENCE_REGIME_LOGIC_VERSION`, embebido literalmente en el SQL de
`_regime_status_sql()` — este módulo ya no importa `REGIME_LOGIC_VERSION`:

```
evidence 3 -> regime logic 2
evidence 4 -> regime logic 2
evidence 5 -> regime logic 2
evidence 6 -> regime logic 2
```

Evidence 1/2 conserva su semántica legacy (sin regime provenance). Cualquier
evidence_version "moderna" (>= 3) ausente del mapa — incluida una versión
futura que este lector no haya sido actualizado explícitamente para soportar
— falla cerrado como `unavailable`, nunca hereda el `REGIME_LOGIC_VERSION`
vivo. La escritura (`app/signal_ledger.py`) sigue usando el
`REGIME_LOGIC_VERSION` actual sin cambios: sólo la interpretación de
evidencia histórica quedó congelada.

Las constraints SQL correspondientes en `sql/schema.sql` (
`signal_observation_pr25_regime_provenance_check`,
`signal_observation_pr25_reference_time_check`) amplían los conjuntos PR24 a
evidence 3/4/5/6 y 5/6 respectivamente. Evidence 1-5 conserva exactamente su
constraint anterior en efecto; ninguna fila histórica se reescribe.

## Migración

`sql/migrations/20260815_pr25_research_knowledge_time.sql` (+ `_down.sql`) es
idempotente en UP y falla cerrado en DOWN si existe cualquiera de: evidencia
v6, un certificado de bundle, un certificado de outcome final, un manifest
spec-v2, o un manifest que referencie `research_visibility_version=1`. DOWN
nunca borra datos para poder ejecutarse.

## Versiones

- `SIGNAL_EVIDENCE_VERSION = 6`
- `RESEARCH_VISIBILITY_VERSION = 1`
- `REGIME_LOGIC_VERSION = 2` (sin cambios; sólo el lector histórico deja de
  seguirlo en vivo)
- `SCALP_SIGNAL_LOGIC_VERSION = scalp-summary-v1`
- `SIGNAL_SAMPLING_VERSION = 1`
- `REPLAY_CONTEXT_VERSION = 1`
- `OUTCOME_VERSION = 1`
- `EXECUTION_SNAPSHOT_VERSION = 1`
- `WALK_FORWARD_MANIFEST_VERSION = 1` (formato de tabla sin cambios)
- `WALK_FORWARD_SPEC_VERSION = 1` (congelado) / `WALK_FORWARD_SPEC_VERSION_V2 = 2` (nuevo)
- `WALK_FORWARD_REPORT_VERSION = 1` (congelado) / `WALK_FORWARD_REPORT_VERSION_V2 = 2` (nuevo)

## Limitación de alcance conocida

`freeze_walk_forward_manifest()` sigue siendo genérico sobre `options` y su
cómputo de `discovery_start` (la primera observación periódica compatible)
no exige por sí mismo un certificado de visibilidad — sólo filtra por
`evidence_version`. Esto es aceptable porque ningún manifest spec-v2 de
producción se crea en esta PR, y la puerta crítica de corrección
decision-time (Stage B, `evaluate_walk_forward`) sí está completamente
condicionada por el certificado. Si en el futuro se congela un
`pr11-fixed-kernel-v2` real, revisar si `discovery_start` también debería
exigir certificación antes de esa freeze.

## Rollback

DOWN falla cerrado (ver arriba) mientras exista evidencia PR25. Sin evidencia
v6/certificados/manifests spec-v2, DOWN restaura exactamente las constraints
PR24 y elimina las dos tablas nuevas. Ningún dato histórico se pierde ni se
reescribe.
