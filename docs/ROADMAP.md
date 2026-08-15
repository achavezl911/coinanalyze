# Roadmap — hasta el resultado autoritativo

Orden real de trabajo. Las etapas son **secuenciales**: cada una bloquea a la siguiente, y
saltarse una invalida el resultado final aunque el código funcione.

Estados: `CONFIRMED` · `DECIDED` · `PLANNED` · `BLOCKED` · `EXTERNAL_UNVERIFIED` ·
`MISSING_EXTERNAL_EVIDENCE` (ver [`README.md`](README.md)).

Fecha de esta revisión: **2026-08-14**.

---

## 1. Cierre real de R05

`ESTADO: CONFIRMED en esta rama · pendiente de revisión independiente`

Cerrar A-01 **y** A-02 de verdad: el ruteo efectivo debe ser un objeto científico desde la
construcción del índice hasta la escritura cruda.

- A-01 (mapas efectivos divergentes) — cerrado en `c879bdec`.
- A-02 (aplicación del ruteo fuera de la identidad) — **no** cerrado en `c879bdec`;
  intentado en `700f7695`/`450cf2fb` y **refutado**; cerrado en
  `e84ebe8140c8393ea2ef3447d8c165d32b594917`.
- Región de `config.py` reducida a las cuatro proyecciones.
- Identity-v1 recomputada: `c939add3…` (candidato).

Tres intentos, dos refutaciones. `c879bdec` dejó A-02 abierto. `700f7695`/`450cf2fb` mutaban
la **primera aparición textual** de cada expresión, que tras esa corrección siempre caía
dentro de una región, así que la suite se ponía verde mientras los puntos de llamada reales
—la selección de sesión en los bucles y el wiring invocado por `main()`/`run()`— seguían
fuera. Detalle en [`HANDOFF_IA.md`](HANDOFF_IA.md) §6.1.

Bloquea: todo lo demás.

## 2. Revisión independiente con P0=0 / P1=0

`ESTADO: PLANNED · BLOCKED por la etapa 1`

La etapa 1 ya falló **dos** revisiones. No se declara cerrada por autoafirmación ni por CI en
verde: hace falta una revisión adversarial externa que intente reproducir el bypass con
mutaciones propias y no lo consiga.

Criterio de salida: cero hallazgos P0 y P1 sobre
`e84ebe8140c8393ea2ef3447d8c165d32b594917`. Vectores obligatorios en
[`HANDOFF_IA.md`](HANDOFF_IA.md) §11.

Sólo tras esta aprobación el digest `c939add3…` deja de ser candidato, y sólo entonces se
congela identity-v1 (antes del primer manifest spec-v4). Cualquier cambio posterior exige
identity-v2.

## 3. PostgreSQL 17 en el CI de `main`

`ESTADO: CONFIRMED en el workflow · EXTERNAL_UNVERIFIED para las ejecuciones de main`

`.github/workflows/ci.yml` levanta un clúster PostgreSQL 17 aislado, aplica `sql/schema.sql`
y exporta `TEST_DATABASE_URL`; aborta si la versión no es 17. Verificado en este repositorio.

Lo que **no** está verificado desde aquí: el historial de ejecuciones sobre `main` y la
salud del runner self-hosted. Se declara `EXTERNAL_UNVERIFIED`, no se asume verde.

## 4. Cierre de deuda: spec-v1, auditorías históricas, cohorte legacy y pivotes

`ESTADO: PLANNED · BLOCKED por la etapa 2`

- **spec-v1**: mantener sus hashes byte-estables (`e2f967bb…`, `2f21afe9…`, `7fd50764…`)
  mientras se decide si sigue siendo un camino soportado o queda como legado.
- **Auditorías históricas**: `MISSING_EXTERNAL_EVIDENCE`. No existe en el repositorio una
  auditoría independiente de las cohortes anteriores a la procedencia de contrato. No se
  inventa ninguna.
- **Cohorte legacy**: las observaciones con `runtime_contract_*` en NULL **no** son
  admisibles como evidencia confirmatoria spec-v4. Se conservan identificadas como
  histórico/diagnóstico. No habrá backfill de procedencia.
- **Pivotes**: decidir explícitamente qué series históricas entran y cuáles no, con criterio
  escrito, antes de que exista el manifest.

## 5. Review y merge humanos

`ESTADO: PLANNED · BLOCKED por las etapas 2-4`

PR #28 está apilada sobre `codex/pr27-confirmatory-endpoint-integrity`, no sobre `main`.
Orden obligatorio: primero PR #27 → `main`; después PR #28.

**Ninguna IA mergea.** El merge lo hace una persona tras la review y con CI en verde.

**`mergeable=true` en GitHub no significa aprobado**: sólo dice que no hay conflicto de
texto. PR #28 sigue marcada **DO NOT MERGE** hasta que se cumplan las etapas 2-4.

## 6. Verificación autorizada de producción

`ESTADO: PLANNED · BLOCKED por la etapa 5 · EXTERNAL_UNVERIFIED`

Comprobar en el LXC 140 que los colectores arrancan bajo el ruteo registrado y que un ruteo
no registrado **impide** producir (salida distinta de cero, `Restart=on-failure`).

Sólo mediante el flujo autorizado: `workflow_dispatch` desde `main` → artefacto por SHA →
wrapper root. Nunca por SSH manual. Ninguna IA toca producción.

## 7. Calibración pre-OOS

`ESTADO: PLANNED · BLOCKED por la etapa 6`

Elegir, **antes** de que exista el periodo OOS y sin mirarlo: símbolo, horizonte, MES,
tamaño de bloque, repeticiones de bootstrap, duración OOS, fees y estrés finales, umbral de
cobertura de ejecución y `settlement grace`.

PR27 deliberadamente **no** elige ninguno de esos valores. Pendientes conocidos que esta
etapa debería resolver: normalizar cada pata de CVD por su volumen, y decidir el tratamiento
de funding (endpoint-v2 es ex-funding; no se inventa un multiplicador).

## 8. Congelación prospectiva spec-v4

`ESTADO: PLANNED · BLOCKED por la etapa 7`

Congelar el manifest con folds, cutoffs, identidad científica y contrato de runtime. A
partir de aquí identity-v1 es inmutable: cualquier cambio del código cubierto exige
identity-v2 **y** un experimento prospectivo nuevo.

## 9. Recolección prospectiva

`ESTADO: PLANNED · BLOCKED por la etapa 8`

Acumular observaciones bajo el ruteo registrado durante el periodo OOS congelado. Sin
inspeccionar resultados. Toda ventana de datos ausente queda visible como `data_gap`; una
ausencia es preferible a una fila mal ruteada.

## 10. Evaluación autoritativa

`ESTADO: PLANNED · BLOCKED por la etapa 9`

Ejecutar la evaluación una vez alcanzado `evaluation_not_before = C + G`. Persiste una sola
fila (`PASS`/`FAIL`/`INCONCLUSIVE`). Recomputaciones posteriores comparan bytes canónicos;
una divergencia produce `ConfirmatoryReproducibilityError`, nunca un reemplazo silencioso.

## 11. Trade Tape / Footprint

`ESTADO: PLANNED · iniciativa posterior, fuera de PR27`

Persistencia tick a tick con su propio esquema, retención e identidad científica. Hoy los
trades se agregan a 1 minuto y 5 segundos y el libro llega a L1/L5/L10, así que no hay
footprint real.

Empieza **después** de la etapa 10 y en un PR propio. No forma parte de la evidencia
confirmatoria spec-v4.

---

## Resumen

| # | Etapa | Estado |
|---|---|---|
| 1 | Cierre real de R05 | CONFIRMED en rama, pendiente revisión |
| 2 | Revisión independiente P0=0/P1=0 | BLOCKED por 1 |
| 3 | PostgreSQL 17 en CI de main | CONFIRMED (workflow) / EXTERNAL_UNVERIFIED (runs) |
| 4 | Deuda spec-v1, auditorías, legacy, pivotes | BLOCKED por 2 · auditorías `MISSING_EXTERNAL_EVIDENCE` |
| 5 | Review y merge humanos | BLOCKED por 2-4 |
| 6 | Verificación autorizada de producción | BLOCKED por 5 |
| 7 | Calibración pre-OOS | BLOCKED por 6 |
| 8 | Congelación prospectiva spec-v4 | BLOCKED por 7 |
| 9 | Recolección prospectiva | BLOCKED por 8 |
| 10 | Evaluación autoritativa | BLOCKED por 9 |
| 11 | Trade Tape / Footprint | PLANNED, posterior |
