# PR27 — integridad del endpoint confirmatorio

PR27 instala una ruta científica nueva, aditiva y prospectiva. No cambia el
significado de los specs v1, v2 o v3; no modifica `evidence-v6`, no recertifica
historia, no crea `pr11-fixed-kernel-v2`, y no congela un manifest de
producción. Los valores de calibración del experimento futuro siguen siendo
responsabilidad de una fase posterior.

## Decisión de versionado

La corrección vive en `WALK_FORWARD_SPEC_VERSION_V4 = 4`. Aunque actualmente
no haya manifests spec-v3 en producción, spec v3 y sus identificadores ya
fueron publicados. Cambiar su endpoint, baseline, bootstrap o política de
decisión reinterpretaría un contrato histórico. Por ello PR27 conserva spec
v3 exactamente y añade:

| Contrato | Identidad nueva |
|---|---|
| Walk-forward | spec v4 / report v4 |
| Endpoint primario | `..._v2` |
| Baseline | `block_binance_mid_unconditional_direction_matched_baseline_v2` |
| Inferencia | `paired_block_bootstrap_v2` |
| Generador de draws | `sha256_counter_rejection_v1` |
| Decisión | `conjunctive_absolute_positive_and_excess_ci_v2` |
| Resultado autoritativo | result contract v1 |

Los hashes estáticos dorados de specs v1, v2 y v3 quedan fijados por tests de
regresión. Una evaluación spec-v4 no puede pasar por el API legacy que
devuelve resultados no persistidos.

## Contrato spec v4

`ConfirmatoryContractV2` no tiene defaults. El operador futuro debe congelar
explícitamente un único símbolo, horizonte, muestreo `utc_nonoverlap`, venue,
tamaño, fee, estrés no-funding, MES, bloque, seed, repeticiones, confianza,
mínimos de bloques/cobertura y settlement grace. PR27 valida estructura y
compatibilidad, pero no elige ninguno de esos valores.

La primera versión corregida exige:

- `primary_exchange = binance`;
- `outcome_price_venue = binance`;
- `funding_semantics = excluded_v1`;
- evidencia 6, visibility 1, outcome 1 y execution snapshot 1;
- un settlement grace positivo y congelado.

Bybit sigue disponible en análisis exploratorios y en el endpoint v1. Sólo
el endpoint v2 falla cerrado para Bybit porque la serie OHLCV de outcomes
actual no tiene dimensión exchange y representa el perpetual de Binance.

## Álgebra económica exacta

Para cada fila accionable, todos los precios del endpoint v2 pertenecen al
camino Binance soportado. Sean:

- `M`: mid del snapshot de ejecución en tiempo de decisión;
- `B`: VWAP de compra para el tamaño congelado en ese snapshot;
- `S`: VWAP de venta para ese tamaño;
- `c_b`: costo de compra contra `M`, en bps;
- `c_s`: costo de venta contra `M`, en bps;
- `X`: close Binance al final de la ventana outcome v1;
- `f`: taker fee congelado por lado, en bps;
- `s`: estrés de ejecución no-funding congelado, en bps.

El snapshot sólo es evaluable si su forma es válida, ambos lados tienen
profundidad suficiente y se cumplen, dentro de tolerancia numérica:

```text
B = M * (1 + c_b / 10000)
S = M * (1 - c_s / 10000)
```

### Long

```text
entry_fill_long       = B
modeled_exit_long     = X * (1 - c_s / 10000)
r_long                = modeled_exit_long / B
absolute_long_bps     = [r_long*(1 - f/10000) - (1 + f/10000)]*10000 - s
```

### Short

```text
entry_fill_short      = S
modeled_cover_short   = X * (1 + c_b / 10000)
r_short               = modeled_cover_short / S
absolute_short_bps    = [(1 - f/10000) - r_short*(1 + f/10000)]*10000 - s
```

No hay convención implícita: long compra al entrar y vende al salir; short
vende al entrar y compra para cerrar. El costo de salida usa el lado opuesto
del mismo snapshot de decisión y se aplica al precio outcome del mismo venue.
El fee se cobra una vez por lado sobre el notional real de cada pata y el
retorno se expresa contra el notional de entrada. Por eso el costo total de
fees es `f*(1+r_long)` para long y `f*(1+r_short)` para short, no la
aproximación constante `2*f`. El estrés se resta exactamente una vez.

`signal_observation.reference_price`, `directional_return_pct` y
`market_return_pct` no alimentan el endpoint corregido. Se mantienen en los
reportes legacy y como diagnóstico, pero un feed de referencia stale u
offset no puede cambiar `absolute_stressed_net_bps` v2.

## Control incondicional coherente

Para cada observación periódica evaluada —accionable o no— en el mismo
símbolo, horizonte, muestreo y ventana OOS:

```text
venue_mid_market_return_bps = (X / M - 1) * 10000
```

Dentro de cada bloque calendario congelado:

```text
block_market_mean_bps = mean(venue_mid_market_return_bps de todas las filas)
baseline_long_bps     =  block_market_mean_bps
baseline_short_bps    = -block_market_mean_bps
excess_bps            = absolute_stressed_net_bps - baseline_direction_bps
```

Así el control y la señal parten del mismo estado de mercado y terminan en el
mismo outcome. La diferencia entre `M` y el fill real es costo de ejecución
medido, no un término cross-feed oculto. El baseline es deliberadamente
frictionless; aplicar fricción sólo a la señal hace la comparación
conservadora.

La ruta v4 no descarta silenciosamente inputs del baseline. Reporta, contra
el denominador de filas periódicas evaluadas, `snapshot_missing_n`,
`snapshot_nonvalid_n`, `snapshot_time_mismatch_n`, `snapshot_invalid_mid_n`
y `baseline_evaluable_n`. Un snapshot sólo pertenece al estado de decisión
si `captured_at` coincide exactamente con `signal_observation.observed_at`.
Falta de cualquier input requerido deja `baseline_complete=false` y fuerza
`INCONCLUSIVE`. La ausencia de observaciones completas se mide aparte contra
el denominador determinista de slots esperados mediante research coverage.
Un outcome marcado `evaluated` sólo cuenta si es knowledge-usable al cutoff y
si sus `window_end` y `due_at` reproducen exactamente `outcome_window_v1`.

## Inferencia pareada y decisión conjunta

Cada fila cost-evaluable aporta el par dependiente:

```text
(absolute_stressed_net_bps, excess_bps)
```

Los pares se agrupan antes de resamplear. Cada repetición extrae bloques
completos con reemplazo y usa el mismo draw para ambos componentes. El
generador `sha256_counter_rejection_v1` evita depender del PRNG de una versión
de Python y usa rejection sampling para no introducir sesgo de módulo. Los
cuatro límites percentiles se calculan con la interpolación lineal versionada
en endpoint-v2. Toda media usa `sorted_math_fsum_mean_v1`: primero ordena los
valores finitos y después aplica `math.fsum`, por lo que el planner de
PostgreSQL no puede cambiar el resultado al devolver las mismas filas en otro
orden.

La hipótesis confirmatoria es una sola conjunción (intersection-union):

```text
componente absoluto PASS  <=> mean(absolute) > 0
                              AND lower_CI(absolute) > 0
componente exceso   PASS  <=> mean(excess) > frozen_MES
                              AND lower_CI(excess) > frozen_MES

componente X FAIL          <=> upper_CI(X) <= umbral de X
componente X INCONCLUSIVE  <=> ninguno de los dos casos anteriores
```

El umbral absoluto es cero y el umbral de exceso es el MES congelado. Por
ejemplo, un CI de exceso enteramente positivo pero enteramente por debajo del
MES es `FAIL`; uno que cruza el MES es `INCONCLUSIVE`.

Exigir también el estimador observado cierra un caso extremo de bootstrap con
bloques de tamaños desiguales: un intervalo percentil sesgado no puede por sí
solo producir PASS si la economía absoluta observada es negativa.
Si el estimador no supera el umbral pero el intervalo aún lo cruza —o incluso
queda por encima por sesgo de resampling— el estado fail-closed es
`INCONCLUSIVE`, no un PASS ni un FAIL decisivo fabricado.

La decisión conjunta es:

| Absoluto | Exceso | Resultado conjunto |
|---|---|---|
| PASS | PASS | PASS |
| FAIL | cualquiera | FAIL |
| cualquiera | FAIL | FAIL |
| PASS | INCONCLUSIVE | INCONCLUSIVE |
| INCONCLUSIVE | PASS | INCONCLUSIVE |
| INCONCLUSIVE | INCONCLUSIVE | INCONCLUSIVE |

Cobertura insuficiente, outcome incompleto, baseline incompleto o bloques
insuficientes también producen `INCONCLUSIVE`. `outcome_complete` conserva
su requisito de 100%. En particular, una estrategia con retorno absoluto
negativo pero exceso positivo nunca puede producir PASS.

## Identidad de implementación científica

El manifest v4 congela `scientific_implementation`, que contiene una versión,
el canonicalizador, la lista ordenada de componentes, el digest de cada uno y
el digest agregado SHA-256. La identidad v1 cubre 24 regiones explícitas. La
superficie comienza en la construcción del contexto y el kernel que genera la
decisión, continúa por clasificación, persistencia y replay, e incluye la
producción de certificados de visibilidad, el límite transaccional que
garantiza su orden, materialización de outcomes y `data_gap`, snapshots de
ejecución, proyección knowledge-time, denominador UTC, endpoint, baseline,
bloques, medias, bootstrap, decisión, persistencia autoritativa y todos sus
límites SQL append-only.

La cobertura no se limita al digest final del evaluador. Los productores de
observaciones evidence-v6, outcomes-v1 evidence-v6 y certificados
visibility-v1 verifican la identidad registrada antes de escribir. Así una
implementación transitoria no registrada no puede producir evidencia nueva.
Además, la evaluación v4 vuelve a ejecutar el kernel sobre cada frame
inmutable de su población OOS y compara tanto el objeto completo de evidencia
como los campos escalares que definen la población. Esta segunda prueba
histórica es la que detecta el caso A -> B -> A aunque al evaluar el source
actual haya regresado exactamente a A.

Los componentes Python usan AST canónico y no dependen de comentarios,
docstrings, posiciones o formato. El bloque SQL sólo normaliza finales de
línea: conserva whitespace y comentarios porque un salto de línea tras `--`
es semántico. El mapeo `identity_version -> digest` es append-only. Si el
source runtime no reproduce la identidad congelada, la evaluación falla antes
de confiar en un resultado. Un cambio científico legítimo requiere otra
identidad y otro experimento prospectivo; un commit Git completo no se usa
como identidad porque incluye cambios irrelevantes de UI o documentación.

La identidad científica registrada por PR27 es:

```text
identity_version = 1
canonicalizer    = scientific_source_canonicalization_v1
digest           = 30825e7f5b9c5dbd11eac92fa8ab1b3f636bf67fc45c0218699dbd4b9a79f743
```

Expandir identity-v1 en este rework no reinterpreta un artefacto publicado:
PR27 sigue sin merge, el repositorio no contiene manifests spec-v4 ni
resultados spec-v4 congelados, y el digest anterior sólo existía en el head
revisado de esta misma PR. Una futura modificación posterior a la publicación
de esta identidad deberá ser aditiva y usar otra versión; nunca podrá cambiar
el registro de la versión 1.

### Integridad de replay OOS

Antes de filtrar por outcome evaluado, `actionable`, `direction`, estado o
disponibilidad de ejecución, v4 forma por fold esta población:

```text
observación periódica certificada y visible al cutoff
-> seleccionada por utc_nonoverlap
-> cuya ventana outcome esperada termina dentro del fold OOS
```

Los ids se cargan y reproducen en un solo fetch batch, no con N+1 queries. Por
cada id se exige: frame presente; `context_version` y `logic_version`
soportados; hash canónico del contexto exacto; evidencia JSON completa igual
a `compute_scalp_summary(context)`; y reproducción exacta de
`decision_status`, `direction`, `actionable`, `state`, `confidence`, `reason`,
scores y cobertura. `regime_label` no selecciona ni entra al endpoint o al
payload autoritativo v4; conserva su uso diagnóstico legacy sin redefinirlo.

Cualquier ausencia, versión no soportada, hash inválido, evidencia distinta o
campo de población distinto levanta `ConfirmatoryScientificIntegrityError`.
No se convierte en cero, execution-missing ni `INCONCLUSIVE`, y no se elimina
del denominador. La excepción ocurre dentro de la transacción autoritativa,
antes del INSERT, por lo que no puede persistirse `PASS`, `FAIL` ni
`INCONCLUSIVE` después de una violación.

### Auditoría explícita de clausura de dependencias

Cada dependencia material se asigna a exactamente una clase:

| Componente | Clase | Mecanismo de protección |
|---|---:|---|
| Canonicalizador, extracción de regiones y verificación runtime | A | Componente `scientific_identity_mechanics`; registro append-only y comparación fail-closed. |
| Construcción de contexto, `compute_scalp_summary` y helpers puros locales | A | Componente AST `signal_summary_decision_kernel`, incluida la consulta SQL de contexto. |
| `classify_oi`, `oi_price_reading` y `_sign` usados por el kernel | A | Componente AST `signal_summary_oi_helpers`. |
| Cutoff PostgreSQL y límite de sesión usados al construir el contexto | A | Componentes AST `signal_context_cutoff` y `signal_context_session_boundary`. |
| Clasificación, fingerprint, serialización y persistencia de la observación | A | Componente AST `signal_observation_generation` y attestation antes de evidence-v6. |
| Replay, canonicalización de contexto/evidencia y comparación de campos | A | Componente AST `signal_replay_integrity` y replay batch obligatorio en v4. |
| Observación, evidence JSON y replay frame ya persistidos | C | Tablas append-only cubiertas por identidad SQL; hash canónico de frame y replay independiente antes de consumirlos. |
| Literales `scalp-summary-v1`, evidence-v6 y context-v1 | B | Contrato versionado congelado; una versión no soportada falla cerrada. |
| Productor de certificados y orden read-committed -> clock -> INSERT | A | `visibility_certificate_production`; exige transacción nueva, attestation y clock PostgreSQL sólo después del SELECT. |
| `fenced_transaction` y verificación de ownership usados al certificar | A | Componente `visibility_transaction_boundary`. |
| Tupla de visibility-v1 (evidence/context/outcome/snapshot, horizontes y exchanges) | B | Literales locales congelados, sin imports de constantes “current”. |
| Certificados y `verified_visible_at` ya emitidos | C | Filas append-only; cutoff usa exclusivamente el timestamp certificado, sin backdating ni fallback a `created_at`/`finalized_at`. |
| Momento real de invocación o retraso operativo del certificador | C | Su único efecto científico queda capturado conservadoramente en el `verified_visible_at` inmutable; nunca cambia la regla de selección. |
| Ventana outcome, barras exactas, missingness y finalización | A | `outcome_materialization_semantics`; attestation antes de materializar evidence-v6. |
| Predicado half-open de gaps bloqueantes | A | `outcome_data_gap_blocking`, incluida la consulta SQL ejecutable. |
| Horizontes, outcome-v1 y grace/retry de finalización | B | Literales versionados dentro de las regiones cubiertas; no hay extensión adaptativa. |
| Outcome final ya persistido | C | Input inmutable/append-only verificado por constraints, versión, ventana y certificado final; cambios posteriores del estado operativo de gaps no lo reescriben. |
| Productor de snapshot decision-time y curva de costos | A | `execution_snapshot_semantics`. |
| Snapshot-v1 y conjunto de venues certificado | B | Contratos literales congelados; endpoint-v2 exige Binance de forma explícita. |
| Snapshots de ejecución ya persistidos | C | Tabla append-only cubierta por identidad SQL; v4 valida versión, instante, forma, profundidad y álgebra. |
| Proyección knowledge-time, grid certificado y denominador UTC non-overlap | A | `knowledge_time_projection_and_grid` y `confirmatory_v4_fetch_coverage_and_persistence`. |
| Baseline, endpoint-v2, bloques, media determinista, draws, CI y conjunción | A | `corrected_endpoint_and_paired_inference`; una sola región AST incluye todos los helpers result-material. |
| Manifest, folds, cutoffs y parámetros confirmatorios congelados | C | Input persistido append-only con JSON canónico/hash y validación completa al cargar; PR27 no elige valores. |
| Nombres/versiones de endpoint, baseline, bootstrap y decisión | B | Identificadores literales preregistrados dentro del contrato spec-v4. |
| Transacción, lock, persistencia y recomputación autoritativa | A | `authoritative_transaction_and_serialization` más componentes SQL de resultado. |
| Resultado autoritativo ya persistido | C | Único, append-only, FK restrictiva, payload canónico y SHA-256 recalculado por aplicación y PostgreSQL. |
| Pooling, logging y transporte de errores fuera de las transacciones científicas | D | No transforman inputs ni ofrecen fallback semántico; un fallo sólo aborta/reintenta antes de crear evidencia. |

Las regiones SQL cubren además los boundaries de observación, replay, outcome,
gaps, snapshots, certificados y resultado. Hashar todo el repositorio no es
necesario: UI, rutas de presentación y documentación quedan fuera porque no
pueden formar el payload autoritativo ni escribir evidencia científica.

## Settlement del certificado

Sean `C` el `confirmatory_knowledge_cutoff` congelado y `G` el grace positivo
suministrado por el operador y hasheado en el contrato:

```text
evaluation_not_before = C + G
```

Antes de ese instante el estado es `not_ready` y no se persiste resultado.
Esperar `G` sólo da tiempo a que una transacción cuyo certificado ya recibió
`verified_visible_at <= C` haga commit. Nunca ensancha el corte: el query
continúa exigiendo `verified_visible_at <= C`; un certificado estampado
después de `C` queda fuera aunque la evaluación ocurra mucho después.

PR27 no elige `G`. La calibración operativa futura debe congelar un valor que
cubra la duración/timeout de las transacciones certificadoras. Si una
transacción excepcionalmente permanece abierta más allá de `G`, el primer
resultado maduro sigue quedando fijado; una recomputación posterior que vea
una muestra distinta genera error de reproducibilidad en vez de reemplazarlo
silenciosamente.

## Resultado autoritativo e inmutabilidad

`signal_walk_forward_confirmatory_result` admite una sola fila por manifest
v4. `evaluate_walk_forward_authoritative()`:

1. rechaza una transacción externa;
2. serializa evaluadores del mismo manifest con advisory lock;
3. abre `REPEATABLE READ` después de obtener el lock;
4. no persiste mientras el resultado sea `not_ready`;
5. persiste el primer resultado maduro (`PASS`, `FAIL` o `INCONCLUSIVE`) con
   el manifest hash, identidad, cortes congelados, JSON canónico exacto y
   SHA-256;
6. en llamadas posteriores recomputa y compara metadata, hash y bytes
   canónicos; cualquier divergencia produce
   `ConfirmatoryReproducibilityError`.

La constraint única y la serialización impiden dos resultados competidores.
Triggers PostgreSQL rechazan `UPDATE`, `DELETE` y `TRUNCATE`; el FK es
`ON DELETE RESTRICT`. `ON CONFLICT` nunca reemplaza: sólo permite leer y
comparar la fila ganadora. Un `CHECK` nativo vuelve a calcular SHA-256 sobre
los bytes UTF-8 de `canonical_result_json`, por lo que ni siquiera un INSERT
SQL directo puede declarar un hash que no corresponda al payload persistido.
Los floats finitos de esa evidencia se codifican como binary64 hexadecimal
taggeado (`binary64_hex_v1`); así su hash no depende de cómo una versión de
Python elija imprimir el decimal equivalente. NaN e infinitos se rechazan.

## Funding y missingness de ejecución

Endpoint-v2 es explícitamente **ex-funding**. `absolute_stressed_net_bps` es
neto de los fees y del estrés no-funding congelados, pero no es “neto de todos
los costos”. PR27 no inventa un multiplicador de funding. La calibración debe
medir exposición por event-time y decidir prospectivamente si introduce un
modelo versionado, un bound conservador o limita el claim.

La ejecución no evaluable puede ser MNAR. PR27 conserva cohorts separados
para snapshot ausente, no válido, capturado en otro instante, forma inválida
y profundidad insuficiente; no inventa fills punitivos ni selecciona un
umbral. La calibración futura debe estudiar cobertura por estado de mercado,
diferencias de outcome, dependencia del tamaño y sensibilidad antes de
congelar el umbral de cobertura.

## Alcance y responsabilidades futuras

PR27 instala maquinaria, schema, pruebas adversariales y CI PostgreSQL 17.
No selecciona símbolo, horizonte, MES, bloque, repeticiones, duración OOS,
fees/estrés finales, cobertura ni settlement grace; no inspecciona OOS futuro,
no crea kernel-v2, no crea manifest de producción y no despliega. Sólo una
calibración separada y pre-OOS puede suministrar esos valores a un manifest
v4 futuro.
