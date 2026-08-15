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
el digest agregado SHA-256. La identidad v1 cubre **28 componentes**: tres
módulos Python completos (`app/scalp_collector.py`, `app/ws_collector.py`,
`app/signal_runtime_contract.py`) más 17 regiones AST y 8 regiones SQL. La
superficie comienza en la construcción del catálogo de mercados y del ruteo
efectivo (R05), sigue con la construcción del contexto y el kernel que genera
la decisión, continúa por clasificación, persistencia y replay, e incluye la
producción de certificados de visibilidad, el límite transaccional que
garantiza su orden, materialización de outcomes y `data_gap`, snapshots de
ejecución, proyección knowledge-time, denominador UTC, endpoint, baseline,
bloques, medias, bootstrap, decisión, persistencia autoritativa, la creación
de suscripciones y la conversión par-externo -> clave-interna en ambos
colectores, las rutas de entrega a las tablas crudas y todos sus límites SQL
append-only.

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
digest           = 451f49552b732bd829a72c10fb2a615cd9d74e0a2a471f677cbd7642975ac378
```

Historial de digests v1 dentro de esta PR sin mergear: R03 registró
`f696a268…`; R04 no añadió componentes (seguía en 25) pero amplió
`scientific_runtime_contract_mechanics` con la guarda del productor crudo y
registró `9749e643db19ccc2a6e41a72c8f3ed36621871d3ab29d090b4151d17702ce976`;
R05 añadió cinco componentes de ruteo y registró `25f6c2e5…` en `c879bdec`;
el primer intento de cierre amplió las regiones hasta los puntos de aplicación,
redujo la de `config.py` a las cuatro proyecciones, subió a 32 componentes y
registró `5a5cb09f…` en `700f7695`/`450cf2fb`; una segunda revisión lo refutó y
el cierre de wiring registró `c939add3…` en `e84ebe81`/`9b2e082c`, con los
mismos 32 componentes; una **tercera** revisión refutó también ese valor —cinco
mutaciones lo conservaban— y el cierre por módulo completo registró
`c7bf8e5b…`, bajando a **28** componentes al sustituir siete regiones parciales
por tres módulos enteros (ADR-012).  Los commits 3.1 y 3.2 lo desplazaron dos
veces más -- superficie descubierta, y después verificación post-import -- hasta
el valor vigente `451f4955…` sobre **42** componentes.  El valor autoritativo
es siempre `identity/registry.json`; cualquier cita en prosa es una instantánea.

Ese valor es **candidato**, no definitivo: se registra para que las pruebas y
el runtime sean coherentes, y sólo queda firme si la superficie corregida
supera una revisión independiente con P0=0 y P1=0. Ni un informe del
implementador ni un CI en verde constituyen esa aprobación. Después de ella y
antes del primer manifest spec-v4, identity-v1 queda congelada.

Expandir o recomputar identity-v1 en estos reworks no reinterpreta un artefacto
publicado: PR27 sigue sin merge, el repositorio no contiene manifests spec-v4
ni resultados spec-v4 autoritativos, y los digests anteriores sólo existieron
en heads revisados de esta misma PR. **La ventana de sustitución se cierra
antes del primer manifest spec-v4**: desde ese momento cualquier cambio del
source cubierto requiere registrar una nueva versión de identidad y el digest
v1 no volverá a reemplazarse.

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
| Derivación, registro y verificación del contrato de runtime | A | Componente `scientific_runtime_contract_mechanics`; registro append-only (ahora dentro de la región hasheada) y comparación fail-closed. |
| Ruteo de mercado resuelto (`symbol`, `base_asset`, `futures_pair`, `spot_pair`) | A | Valores congelados en `scientific_runtime_contract` dentro del manifest v4; attestation en productores y verificación por fila en evaluación. |
| Lógica de las cuatro proyecciones de ruteo (`symbol -> base_asset`, `symbol -> futures_pair`, `base_asset -> spot_pair`, `futures_pair -> symbol`) | A | Componente `market_routing_construction`, reducido a esas cuatro líneas; además la atestación exige que los mapas coincidan con la proyección del contrato validado. |
| Objeto de ruteo efectivo aplicado por los productores | A | `EffectiveMarketRouting` congelado, derivado del contrato validado, devuelto por `attest_raw_market_producer()` y pasado explícitamente; `expected=` re-atestigua el mismo objeto en cada flush. |
| Índice de ruteo que convierte par externo -> clave interna | A | `FuturesRoutingIndex`/`SpotRoutingIndex` sólo se construyen desde un `EffectiveMarketRouting` atestiguado y validan cada conversión en `__post_init__` con `require_routed_pair_origins`; un índice forjado falla cerrado antes de suscribirse. |
| Endpoints de venue, construcción de URL/topics, conexión y despacho al handler | A | Componentes `scalp_routing_application` y `ws_routing_application`: las sesiones conectadas construyen el índice, derivan URL/topics, abren la conexión y despachan cada mensaje sin exponer el índice al bucle. |
| Inyección del ruteo desde `main()` / `run()` a cada tarea productora | A | Componentes `scalp_routing_entrypoint` y `ws_routing_entrypoint`: una sola función recibe un ruteo y devuelve todas las tareas ligadas a él. |
| Traspaso desde los stores en memoria a la entrega cruda | A | `flush_*_cycle()` dentro de `scalp_raw_delivery` / `ws_raw_delivery`: atestación, snapshot, entrega y acknowledgement. |
| Entrega a persistencia cruda (`deliver_*`, SQL de las siete tablas crudas) | A | Componentes `scalp_raw_delivery` y `ws_raw_delivery`; la guarda y `require_routed_internal_keys` viven dentro de la función que ejecuta el INSERT. |
| Reconexión, backoff, logging, health de feeds y parámetros de transporte WS | D | Fuera de las regiones a propósito y fijado por test: no seleccionan mercado ni transforman insumos. |
| Procedencia de contrato ya persistida en `signal_observation` | C | Columnas append-only cubiertas por la identidad SQL; se comparan contra el manifest congelado antes de consumir la fila. |
| Umbrales whale/large-trade, `bybit_oi_symbol`, `spot_history_symbol` | B | Operativos probados: no alteran ninguna columna que lea el contexto ni el endpoint v2. Ver "Excluido a propósito". |
| Ruta del fichero de catálogo y ortografía de variables de entorno | D | El contrato proyecta valores resueltos; la ruta no puede cambiar el hash. |

Las regiones SQL cubren además los boundaries de observación, replay, outcome,
gaps, snapshots, certificados y resultado. Hashar todo el repositorio no es
necesario: UI, rutas de presentación y documentación quedan fuera porque no
pueden formar el payload autoritativo ni escribir evidencia científica.

## Contrato científico de configuración en runtime

### Identidad de fuente frente a identidad de runtime

Hashear la fuente científica prueba **qué calcula el código**. No prueba **qué
insumos crudos seleccionó**, porque la selección la deciden valores resueltos en
runtime desde el entorno y desde el catálogo versionado de mercados.

`scalp_context()` pasa `WS_SYMBOL_MAP[symbol]` como parámetro `$2` de su consulta,
dentro de la región AST `PR27_SCIENTIFIC_SIGNAL_SUMMARY_KERNEL_V1`. El
canonicalizador hashea la *expresión*, nunca su *valor resuelto*, y ese valor
tampoco llega al `ctx` devuelto: no está en `signal_replay_frame.context` ni en
`context_hash`.

Por eso repuntar `BTCUSDT_PERP.A -> BTC` hacia otro activo spot produce el mismo
digest de fuente, el mismo replay y un contexto inmutable distinto. El replay
reproduce fielmente el contexto equivocado. R01 no cierra R03.

### Valores congelados

`app/signal_runtime_contract.py` deriva un contrato determinista, canonicalizable
en JSON, versionado, no secreto, independiente de la ruta del fichero de catálogo
y basado en valores resueltos. Por cada símbolo científicamente soportado congela
exactamente cuatro campos:

| Campo | Por qué es result-material |
|---|---|
| `symbol` | `$1` de la consulta de contexto y identificador de mercado upstream para `ohlcv`, `open_interest`, funding y liquidaciones. |
| `base_asset` | `$2` de la consulta de contexto: selecciona `spot_trades_realtime` y por tanto `spot_price`, `spot_delta_3m` y `spot_volume_3m`. |
| `futures_pair` | Decide qué mercado de futuros de Binance registra el colector bajo `symbol` (`futures_trades_realtime`, `orderbook_snapshot`). |
| `spot_pair` | Decide qué mercado spot de Binance registra el colector bajo `base_asset`. |

```text
runtime_contract_version = 1
canonicalizer            = scientific_runtime_contract_canonicalization_v1
digest                   = c9cbe967b1f256644c0caf1ec851ea5a73d67029286afe0bb04461f582a21b00
```

Cambiar sólo la ruta del catálogo dejando el ruteo resuelto idéntico **no** crea
diferencia científica. Cambiar un valor result-material **sí** cambia el hash.

### Excluido a propósito

No se hashea el entorno completo, ni secretos, ni configuración operativa, ni el
repositorio entero. Cada exclusión está probada contra el código, no asumida:

| Valor | Prueba de exclusión |
|---|---|
| `whale_threshold_usd` | `buy_vol_usd`/`sell_vol_usd` se acumulan **incondicionalmente antes** del test de umbral; el umbral sólo reparte las columnas `inst_`/`mid_`/`retail_`, que `scalp_context` nunca selecciona. Su único alcance es `regime_label`, diagnóstico: no aparece en la región del kernel ni en `signal_replay.py`, y no entra al endpoint ni al payload autoritativo v4. |
| `large_trade_threshold_usd` | Misma estructura en `scalp_collector.TradeBucket.add`. |
| `bybit_oi_symbol` | El OI de Bybit se escribe en la tabla separada `oi_bybit`. `scalp_context` sólo lee `open_interest`. Endpoint-v2 exige Binance explícitamente. |
| `spot_history_symbol` | Sólo alcanza `spot_perp_flow()` y el agregado diario, ambos fuera de la superficie científica; su símbolo (`BTCUSD.A`) no colisiona con el `$1` de la consulta de contexto. |
| Ruta del catálogo y ortografía de variables de entorno | El contrato proyecta valores resueltos, nunca rutas ni nombres de variables. |
| `COLLECTOR_SHARD_INDEX` / `COLLECTOR_SHARD_COUNT` | Estrechan `ACTIVE_SYMBOLS`, no `Settings.SYMBOLS`. Si afectaran al contrato, cada shard resolvería un digest distinto y sólo uno podría coincidir con el registro. Hay test que lo fija. |
| Resto de `Settings` (retención, flush, intervalo, `PG_*`, `API_*`, `LOG_LEVEL`) | Sólo afectan disponibilidad/cobertura. `compute_scalp_summary` no lee **ningún** símbolo de `app.config`. |

Nota deliberada: `metrics.py` liga `WHALE_ACTIVITY_MIN = WHALE_THRESHOLD_MAP`
dentro de la región `SIGNAL_SESSION_BOUNDARY`, aunque lo científico de esa región
es `current_nyse_start`. Es una ligadura de nombre, no de valor, y su consumidor
`whale_classification` queda fuera de la región.

### Alcance por `Settings.SYMBOLS`

El contrato cubre los símbolos de `Settings.SYMBOLS`, no el catálogo completo.
Es una decisión explícita del operador y una desviación consciente de la
propiedad "independiente de la ortografía de la variable de entorno": el hash
depende del conjunto activo resuelto.

Se mitiga hasta donde es posible: el alcance es `sorted(set(...))`, así que la
ortografía (CSV o JSON), el orden, los duplicados y los espacios **no** cambian
el hash; sólo lo cambia el conjunto resuelto. Y se usa `Settings.SYMBOLS`, nunca
`assigned_symbols(...)`, para que el sharding sea neutral.

Consecuencia que debe conocer quien opere el sistema: cambiar `SYMBOLS` cambia el
hash del contrato y detiene la producción de evidencia científica hasta registrar
un digest nuevo, aunque el ruteo del símbolo primario v4 no haya cambiado.

### Cuatro puntos de aplicación

**Congelación.** `_static_options_spec()` añade `scientific_runtime_contract` sólo
en la rama spec-v4, junto a `scientific_implementation`. Entra en el hash del
manifest y en la comparación de idempotencia. Los specs v1, v2 y v3 no lo llevan
y sus hashes estáticos dorados quedan intactos por construcción. Al cargar, un
manifest se revalida contra la resolución viva; nunca se reinterpreta con la
configuración actual.

**Producción cruda (R04, cerrada por R05).** Antes de suscribirse o de escribir
dato crudo result-material, `scalp_collector` y `ws_collector` atestiguan con
`attest_raw_market_producer()`, que desde R05 valida además los cuatro mapas
efectivos contra la proyección del contrato y devuelve el objeto congelado
`EffectiveMarketRouting` que el productor aplica y re-atestigua en cada flush y
en cada entrega. Es el punto que faltaba: sin él la aplicación empezaba
*después* de que el dato crudo ya existiera, y con solo R04 el gate miraba el
catálogo mientras los productores aplicaban los mapas. Detalle en "Clausura del
productor crudo" y "Cierre R05".

**Producción.** Antes de escribir evidencia, `persist_signal_observations`,
`materialize_due_signal_outcomes`, `certify_research_bundles` y
`certify_final_outcomes` verifican que el contrato resuelto coincide con el
registrado. Mientras un ruteo no registrado esté activo, la generación de
evidencia de investigación falla cerrada. El snapshot operativo del dashboard
sigue su política de aislamiento existente: vive en su propio savepoint.

**Evaluación.** La v4 exige, por cada fila OOS muestreada, procedencia presente e
igual a la del manifest congelado. Ausencia o divergencia levantan
`ConfirmatoryScientificIntegrityError` dentro de la transacción autoritativa y
antes del INSERT, así que no se persiste `PASS`, `FAIL` ni `INCONCLUSIVE`. No es
filtrado de filas ni `INCONCLUSIVE`: filtrarlas encogería en silencio la
población contra la que se calculó el denominador congelado. La fila autoritativa
guarda además `scientific_runtime_contract_digest`, con `CHECK` de coherencia
contra el JSON canónico y un trigger que lo contrasta con el manifest, de modo
que ni un INSERT SQL directo puede declarar un contrato que el manifest no
congeló.

### Procedencia por fila y A -> B -> A

No basta con el estado final del proceso. `signal_observation` gana dos columnas
nullable, `runtime_contract_version` y `runtime_contract_digest`, escritas en el
mismo INSERT que la observación y protegidas por los triggers append-only que ya
existían.

Así la secuencia peligrosa queda cerrada por dos mecanismos independientes: bajo
el ruteo B el productor ni siquiera escribe, y si una fila B existiera igualmente
llevaría el digest de B para siempre, por lo que restaurar A no puede blanquearla.

La procedencia es **prospectiva y aditiva**. Las filas históricas quedan en NULL,
no hay backfill y **ningún** `CHECK` ata las columnas nuevas a `evidence_version`,
porque eso reinterpretaría `evidence-v6`. `context_version=1` y
`visibility_version=1` tampoco cambian, y los lectores legacy v1-v3 siguen
igual. La evidencia de calibración existente se conserva bajo sus caveats. Como
el OOS spec-v4 empieza después de la congelación, exigir procedencia prospectiva
no obliga a reescribir historia.

## Clausura del productor crudo

### Por qué R03 no cerraba A -> B -> A

R03 impide escribir `signal_observation`, outcomes y evidencia de visibilidad
mientras un contrato B está activo. La aplicación empieza, sin embargo, *después*
de que el dato crudo result-material ya se produjo.

`futures_pair` y `spot_pair` **no aparecen en la clave de la fila**: el colector
graba el mercado que ellos seleccionan bajo `symbol` (`futures_trades_realtime`,
`orderbook_snapshot`, `orderbook_depth`, `liquidations_realtime`) y bajo
`base_asset` (`spot_trades_realtime`). Un colector bajo B escribe por tanto datos
de otro mercado bajo la clave de A, sin dejar rastro en la fila.

Al restaurar A, `scientific_runtime_contract()` vuelve a pasar y `scalp_context`
todavía tiene esas filas dentro de sus ventanas de 1 m, 3 m y 5 m. La observación
se sella con el digest de A, el replay pasa porque reproduce fielmente el
contexto contaminado, y la procedencia por fila pasa porque la observación sí se
creó bajo A. Los tres mecanismos de R03 son correctos y ninguno ve la
contaminación.

Nota de simetría: `symbol` y `base_asset` son a la vez selector y clave, así que
cambiarlos **reubica** filas en vez de contaminarlas. Se cubren igualmente porque
el contrato hashea los cuatro campos juntos.

### Auditoría de escritores

Se auditaron todos los escritores de insumos crudos que el kernel congelado
consume. La pregunta es una sola: ¿puede un ruteo no registrado dejar datos que
`scalp_context(A)` consuma bajo la clave de A?

| Tabla | Escritor | Ruteo result-material | ¿Contamina? |
|---|---|---|---|
| `futures_trades_realtime`, `futures_trades_agg` | `scalp_collector.flush_trades` | `FUTURES_PAIR_MAP`, `PAIR_SYMBOL_MAP` | **Sí** |
| `orderbook_snapshot`, `orderbook_depth` | `scalp_collector.flush_books` | igual | **Sí** (`orderbook_depth` alimenta el execution snapshot) |
| `liquidations_realtime` | `scalp_collector.flush_liquidations` | igual | **Sí** |
| `spot_trades_realtime`, `spot_trades_agg` | `ws_collector.flush_realtime` / `flush_minute` | `SPOT_PAIR_MAP` ∘ `WS_SYMBOL_MAP` | **Sí** |
| `ohlcv`, `open_interest`, `funding_rate`, `predicted_funding_rate`, `liquidations`, `long_short_ratio` | `app/ingest.py` | ninguno: mapa identidad `{symbol: symbol}` | No: el id upstream **es** la clave, así que cambiar `symbol` reubica la fila, no rellena la clave de A con datos de B |
| `oi_bybit` | `app/ingest.py` | `BYBIT_SYMBOL_MAP` | No: tabla separada sin lector científico (prueba de R03) |
| `ohlcv` (filas spot), `daily_*` | `app/daily_agg.py`, `scripts/backfill_ohlcv_*.py` | `SPOT_HISTORY_MAP` | No: espacio de claves disjunto (`BTCUSD.A`), fuera de la superficie científica |
| `metric_baseline` | `app/daily_agg._store_baseline` | ninguno | No: es **derivado**, se calcula sobre filas de `ohlcv` ya almacenadas y no selecciona ningún mercado externo |
| `symbols`, `market_assets` | `app/db.sync_market_catalog` | catálogo directo | No: registra claves (`symbol`, `base_asset`, `spot_history_symbol`), nunca selectores |
| — | `app/api.py` | — | No escribe nada |

Sólo dos procesos quedan dentro: `coinalyze-scalp` y `coinalyze-ws`. No se añaden
guardas a productores no afectados.

### Dónde se atestigua, y por qué en dos sitios

**Arranque.** Primera sentencia de `scalp_collector.main()` y de
`ws_collector.run()`, antes del lock de servicio, del pool y de cualquier
suscripción.

**Límite de escritura.** Una llamada en cada bucle de flush, justo después del
`await asyncio.sleep(...)` y **fuera** del `try` existente, para que escape del
proceso en vez de registrarse y reintentarse como un fallo transitorio de flush.
Ningún snapshot se consume si la atestación falla.

¿Basta con el arranque? El argumento original de R04 ("el contrato resuelto es
constante durante la vida del proceso") era cierto para el catálogo pero **no
para el ruteo efectivo**: los cuatro mapas derivados son dicts mutables a nivel
de módulo, y la atestación de R04 ni siquiera los miraba (hallazgo A-01, ver
"Cierre R05"). R05 cambia ambas mitades:

- La atestación valida también los mapas efectivos contra la proyección del
  contrato validado, y devuelve el objeto congelado `EffectiveMarketRouting`
  que el productor aplica. Una mutación posterior de los mapas no puede cambiar
  ese objeto; sólo puede hacer que la siguiente atestación falle.
- La del límite de escritura se conserva y se refuerza: cada bucle de flush
  re-atestigua con `expected=routing` fuera del `try` (para escapar del
  proceso), y además la propia función de entrega que ejecuta el INSERT vuelve
  a atestiguar y valida con `require_routed_internal_keys` que cada clave
  interna escrita pertenece al ruteo atestiguado. La guarda vive dentro del
  camino de escritura, no solo alrededor.

### Consecuencia operativa

Un servicio cuyo ruteo result-material no es el registrado **no produce nada**.
Sale con código distinto de cero y `Restart=on-failure` + `RestartSec=5s`
reintenta hasta que un operador restaure el ruteo o registre un contrato nuevo.
Es deliberado: correctitud por encima de disponibilidad. Preferimos una ventana
de datos ausente a filas científicamente mal ruteadas, porque la ausencia es
visible para `data_gap` y la contaminación no lo es para nadie.

### Superficie científica y clausura

`attest_raw_market_producer()`, `require_routed_internal_keys()`,
`EffectiveMarketRouting` y el registro `_RESULT_MATERIAL_RAW_PRODUCERS_V1` viven
**dentro** de la región `PR27_SCIENTIFIC_RUNTIME_CONTRACT_V1`, así que la
política —qué productores y qué tablas son result-material, y qué objeto de
ruteo se valida— queda congelada por identity-v1: encoger el conjunto guardado
o debilitar la guarda cambia el digest. Desde R05 el registro
`REGISTERED_SCIENTIFIC_RUNTIME_CONTRACT_DIGESTS` también está dentro de la
región: repuntar el digest de contrato aceptado ya no es invisible para la
identidad.

R04 decidió **no** añadir `scalp_collector.py` ni `ws_collector.py` para no
hacer a la identidad rehén de ediciones operativas (reconexión, sharding,
health de feeds). El hallazgo A-02 mostró el precio: un cambio semántico en la
construcción o aplicación del ruteo no movía el digest. R05 intentó resolver la
tensión sin hashear los ficheros enteros, con regiones compactas sobre los
builders de suscripción, los handlers de conversión y las funciones de entrega.

**Esa primera versión no cerró A-02, y la afirmación de que un bypass no podía
alcanzar la ruta de escritura era falsa.** Una revisión independiente la
refutó con dos mutaciones ejecutadas fuera de toda región protegida (ver
"Corrección de cierre R05"). La clausura vigente amplía las regiones hasta los
puntos donde el ruteo se aplica de verdad y hace el índice de ruteo
inconstruible fuera del ruteo atestiguado; la plomería de reconexión, backoff,
logging y health sigue fuera y hay tests que fijan ambas direcciones.

### Regresión

`tests/test_pr27_r04_raw_producer_closure.py` fija la guarda, su cableado en los
cinco bucles de flush (con un pool que registraría cualquier acceso a la base) y
el arranque de ambos servicios en un intérprete nuevo con un catálogo B real —
lo único que reproduce la ligadura de producción, porque los colectores importan
los mapas con `from app.config import ...` y `monkeypatch` no los alcanza.

`tests/test_pr27_r04_raw_producer_closure_postgres.py` ejecuta los caminos reales
de flush contra PostgreSQL 17: A escribe, B falla cerrada sin escribir una sola
fila, y al restaurar A `scalp_context` sólo ve insumos ruteados por A. Cubre las
dos familias (`futures_pair` y `spot_pair`/`base_asset`) y termina con una
observación cuya procedencia es A y cuyo replay pasa.

`test_residual_b_row_inside_the_three_minute_window_reaches_scalp_context`
**reproduce el defecto** en vez de afirmar la guarda: escribe exactamente lo que
un colector sin guarda habría escrito bajo B y demuestra que `scalp_context(A)`
lo consume. Sigue pasando aunque se elimine la guarda, que es justamente su
función: prueba que el resto de la suite es portante.

## Cierre R05: integridad del ruteo efectivo

### Hallazgos

**A-01 — la atestación validaba el objeto equivocado.** La guarda de R04
recomputa el contrato desde `MARKET_SYMBOL_CATALOG`, pero los productores
aplican `WS_SYMBOL_MAP`, `FUTURES_PAIR_MAP`, `SPOT_PAIR_MAP` y
`PAIR_SYMBOL_MAP`, cuatro dicts mutables derivados del catálogo al importar.
Con cualquiera de los cuatro divergido, el contrato del catálogo seguía
coincidiendo con su digest registrado, `attest_raw_market_producer()` pasaba
para ambos productores y `scientific_runtime_contract()` pasaba en la frontera
de evidencia — mientras los colectores se suscribían, convertían y escribían
bajo el ruteo divergente. `A -> B -> A` seguía alcanzable en el límite crudo.
La prueba roja sobre `ee3792ca` (12 casos `DID NOT RAISE`) está en
`tests/test_pr27_r05_routing_closure.py`.

**A-02 — construcción y aplicación del ruteo fuera de la identidad.**
`config.py` (catálogo + mapas), y en ambos colectores la creación de
suscripciones, la conversión par-externo -> clave-interna y la entrega cruda,
no pertenecían a ninguna región de identidad: un cambio semántico allí no movía
el digest.

Los dos hallazgos son el mismo problema — el ruteo *efectivo* no era un objeto
científico — y se cierran juntos.

### Arquitectura del cierre

`EffectiveMarketRouting` (frozen dataclass, en la región
`PR27_SCIENTIFIC_RUNTIME_CONTRACT_V1`) es la única representación tipada e
inmutable del ruteo efectivo:

- se deriva **exclusivamente** del contrato de runtime ya validado
  (`effective_market_routing_from_contract`);
- contiene los pares externos y claves internas realmente usados, con
  proyecciones `futures_index()` / `spot_index()` por alcance asignado;
- se construye **una sola vez** al arrancar cada productor: es el valor de
  retorno de `attest_raw_market_producer()`, exactamente el objeto validado;
- se pasa **explícitamente** a suscripciones, handlers, flushes y entregas
  (`routing=` keyword-only obligatorio, sin default): no existe fallback que
  lo reconstruya desde variables globales;
- una mutación posterior de los mapas no puede alterarlo (frozen +
  `MappingProxyType`); la siguiente atestación con `expected=routing` la
  detecta y mata el proceso.

Los cuatro mapas de `config.py` se conservan por compatibilidad operacional
(los leen `scalp_logic`, `metrics`, `ingest`, `daily_agg`), pero **ya no son
autoritativos** y ningún camino científico de los colectores los lee
(`co_names` fijado por test). La atestación — compartida por productores y
frontera de evidencia — exige que coincidan con la proyección inmutable:
entrada registrada ausente o distinta en cualquiera de los cuatro, o un alias
de `PAIR_SYMBOL_MAP` que apunte un par extranjero a un símbolo configurado,
bloquean ambos productores antes de suscribirse o escribir. Entradas extra para
símbolos fuera del alcance configurado (catálogo extendido con `SYMBOLS`
estrechado) son inertes por construcción y no bloquean; hay tests que fijan
ambas direcciones.

### Regresión R05

`tests/test_pr27_r05_routing_closure.py` fija: divergencia de cada mapa (in
situ, reasignación y borrado) bloqueando ambos productores y la frontera de
evidencia; el alias extranjero; los extras inertes; la congelación e
insensibilidad a mutación posterior del objeto atestiguado; la re-atestación
con `expected`; suscripciones y conversión derivadas del routing y no de los
mapas (con el mapa envenenado tras atestiguar); firmas keyword-only sin
fallback; el gate dentro de las funciones de entrega; y que una modificación
semántica en construcción, suscripción, conversión o entrega mueve el digest de
identidad mientras el backoff operativo no lo mueve.
`tests/test_pr27_r05_routing_closure_postgres.py` ejecuta los flush reales
contra PostgreSQL 17 bajo divergencia de mapa (cero filas nuevas) y el rechazo
de claves internas fuera del ruteo atestiguado.

## Corrección de cierre R05: los puntos de aplicación del ruteo

`c879bdec` cerró A-01 de forma razonable, pero **no cerró A-02**. Una revisión
independiente lo demostró con evidencia reproducible, no con un argumento.

### Lo que la revisión probó

Las regiones de identidad de `c879bdec` cubrían los *builders* de suscripción y
los *handlers* de conversión, pero no los puntos donde el ruteo se aplica
realmente: `scalp_collector.binance_loop`, `binance_market_loop`, `bybit_loop`,
`ws_collector.binance_consumer`, `bybit_consumer`, `scalp_collector.main` y
`ws_collector.run`.

Sustituyendo, **fuera** de toda región protegida:

```python
index = routing.futures_index(ACTIVE_SYMBOLS)
```

por un índice equivalente a
`FuturesRoutingIndex(pairs=("ETHUSDT",), symbol_by_pair={"ETHUSDT": "BTCUSDT_PERP.A"})`
—y la mutación análoga con `SpotRoutingIndex` en el lado spot— el digest
científico permanecía en `25f6c2e5…`. El handler convertía datos ETH en la
clave interna BTC, y como la entrega sólo validaba la *clave interna* —que es
legítima— el bypass alcanzaba el store y la escritura sin dejar rastro en la
identidad.

La revisión encontró además que la región `PR27_SCIENTIFIC_MARKET_ROUTING_SOURCE_V1`
era demasiado amplia: cambiar `whale_threshold_usd` de `5_000_000` a
`5_000_001` movía el digest de `25f6c2e5…` a `06da5f1f…`, contradiciendo la
exclusión documentada de esos umbrales como valores no materiales.

Ambas observaciones se reprodujeron antes de tocar código, con pruebas rojas
sobre `c879bdec` (`tests/test_pr27_r05_routing_application_closure.py`:
31 fallos, 11 pasos).

### Lo que cierra el hallazgo

**1. Regiones sobre los puntos de aplicación, no sólo sobre los helpers.** Cada
colector expone ahora *sesiones* conectadas dentro de la región de identidad:
construyen el índice desde el ruteo atestiguado, derivan URL y topics, abren la
conexión y despachan cada mensaje al handler. El índice nunca sale de la
región, así que un bucle no puede sustituirlo: no llega a tenerlo. Los bucles
conservan sólo reconexión, backoff, logging y health de feeds.

**2. Inyección única del ruteo.** `scalp_routing_producers()` y
`ws_routing_producers()` —ambas dentro de la identidad— reciben **un** ruteo
atestiguado y devuelven todas las tareas productoras ya ligadas a él. El
entrypoint no puede elegir por tarea, que es exactamente como un store mal
ruteado sobrevivía a una entrega correcta.

**3. Entrega desde el store dentro de la identidad.** El traspaso completo
—atestación, snapshot que sale del store, entrega guardada y acknowledgement—
vive en `flush_*_cycle()` dentro de las regiones de entrega cruda.

**4. Índice de ruteo inconstruible.** `FuturesRoutingIndex` y `SpotRoutingIndex`
exigen el `EffectiveMarketRouting` atestiguado y validan en `__post_init__`
cada conversión par-externo -> clave-interna contra él
(`require_routed_pair_origins`). La mutación exacta de la revisión ya no
compila un objeto válido: falla cerrada antes de suscribirse. Es la respuesta a
que **la validación de claves internas no detecta por sí sola una procedencia
externa incorrecta**: la clave `BTCUSDT_PERP.A` es legítima; lo que no lo es
es que la haya producido `ETHUSDT`.

**5. Endpoints dentro de la identidad.** Qué venue se lee decide qué mercado
acaba bajo la clave interna, igual que el par. `BINANCE_STREAM_BASE`,
`BINANCE_MARKET_STREAM_BASE`, `BYBIT_LINEAR_WS` y `BYBIT_URL` pasan a las
regiones; los parámetros de transporte (`ping_interval`, `max_size`, timeouts)
quedan fuera en `WS_CONNECT_KWARGS`.

**6. Región de `config.py` reducida.** `PR27_SCIENTIFIC_MARKET_ROUTING_SOURCE_V1`
cubre ahora **sólo** las cuatro proyecciones —`symbol -> base_asset`,
`symbol -> futures_pair`, `base_asset -> spot_pair`, `futures_pair -> symbol`—.
El catálogo, su loader, los dos umbrales, `bybit_oi_symbol` y
`spot_history_symbol` quedan fuera: sus *valores resueltos* siguen congelados
por el runtime contract, que es donde corresponde.

La clausura pasó de 30 a **32 componentes** en aquel intento, añadiendo
`scalp_routing_entrypoint` y `ws_routing_entrypoint`. La corrección posterior
por módulo completo las sustituye: ver «Cierre por módulo completo» más abajo.

### Regresión de la corrección

`tests/test_pr27_r05_routing_application_closure.py` fija: 18 mutaciones sobre
las líneas exactas de aplicación (índice, streams/topics, despacho, inyección
del ruteo y el traspaso store -> entrega en los cinco flush) que deben mover el
digest; que ninguna llamada result-material queda fuera de una región en
ninguno de los dos colectores (barrido AST del fichero completo); que los
endpoints están dentro; que un índice forjado —o sin ruteo— no se construye;
que la validación de clave interna acepta lo que la de procedencia externa
rechaza; que cambiar cualquiera de las cuatro proyecciones mueve la identidad;
y que umbrales, `bybit_oi_symbol`, `spot_history_symbol`, backoff, logging y
health **no** la mueven.

**Esa suite resultó insuficiente**, y su docstring lo declara. Ver el apartado
siguiente.

## Segunda refutación: la mutación miraba el sitio equivocado

`CONFIRMED — hallazgos P1 reproducidos sobre 450cf2fb antes de tocar código`

El helper `_mutate` de esa suite reescribe la **primera aparición textual** de
cada expresión (`source.replace(old, new, 1)`). Tras la corrección anterior, la
primera aparición siempre quedaba *dentro* de una región —
`routing.futures_index(ACTIVE_SYMBOLS)` en `scalp_futures_index()`,
`binance_loop(routing=routing)` en `scalp_routing_producers()`— de modo que el
digest se movía, la suite pasaba y **los puntos de llamada reales seguían
desprotegidos**. Una segunda revisión independiente lo demostró:

**P1-1 — la inyección real del ruteo estaba fuera de la identidad.** Las
invocaciones reales son `scalp_routing_producers(pool, service_lock, routing)`
en `main()` y `ws_routing_producers(pool, service_lock, symbols, routing)` en
`run()`. Sustituirlas por wiring directo —ruteo falso para el productor,
correcto para el flusher— dejaba el digest en `5a5cb09f…`.

**P1-2 — la selección real de sesión estaba fuera de la identidad.**
`binance_futures_session → binance_market_session` dentro de `binance_loop()`,
y `binance_spot_session → bybit_spot_session` dentro de `binance_consumer()`:
ambas dejaban el digest en `5a5cb09f…`.

**P1-3 — `EffectiveMarketRouting` es construible a mano.** Un ruteo forjado con
`symbol="BTCUSDT_PERP.A", futures_pair="ETHUSDT"` es autoconsistente y puede
llevar el digest registrado como simple cadena, así que
`require_routed_pair_origins` lo aceptaba: comparaba el índice con el ruteo que
venía con él. Producía `FuturesRoutingIndex`/`SpotRoutingIndex` ETHUSDT→BTC, y
la entrega —sosteniendo el ruteo correcto— aceptaba la clave resultante porque
esa clave sí está ruteada.

**P2-4 — trailing whitespace** en `.github/pull_request_template.md` (líneas 64,
65, 67, 68, 69 y 87) pese a que el informe anterior afirmó `git diff --check`
limpio. Corregido.

Evidencia roja: `tests/test_pr27_r05_routing_wiring_closure.py` sobre
`450cf2fb` → **25 failed, 6 passed**.

### Lo que cierra el hallazgo, en tres capas

**A. Procedencia.** `require_attested_routing()` **re-deriva** el contrato desde
el catálogo, los settings y los mapas efectivos vivos y exige que reproduzca
exactamente las filas del ruteo en uso. Ambos índices lo llaman en
`__post_init__`, antes de las validaciones de forma. La autoconsistencia del
objeto y una cadena de digest dejan de contar como evidencia de procedencia.
Como el chequeo recomputa en cada construcción, también convierte la barrera en
un guardia continuo: un ruteo atestiguado al arrancar que después diverge falla
al construir el siguiente índice, **antes** de suscribirse, del store y de
escribir.

**B. Estructura.** Los bucles de reconexión (`binance_loop`,
`binance_market_loop`, `bybit_loop`, `binance_consumer`, `bybit_consumer`) y los
de flush (`flush_trades`, `flush_books`, `flush_liquidations`, `flush_minute`,
`flush_realtime`) reciben un `connect`/`cycle` **ya ligado**, construido dentro
de la identidad con `functools.partial`. No nombran venue, ni sesión, ni store,
ni entrega, ni ruteo: la sustitución que la revisión ejecutó no tiene forma
expresable ahí. `main()`/`run()` llaman `require_attested_*_routing()` y
`start_*_routing_producers()`; esta última atestigua, cablea y **crea las tareas
materiales** dentro de la identidad, así que el entrypoint nunca sostiene un
`EffectiveMarketRouting`. Un barrido AST endurecido exige que **ningún símbolo
material se lea fuera de una región** en ninguno de los dos colectores, cubriendo
bucles, consumers, factories y flushers raw.

**C. Anclaje.** Las mutaciones nuevas localizan cada referencia por AST —sobre
los sitios reales de lectura del símbolo, byte a byte— en vez de por
desplazamiento textual. Una expresión duplicada dentro de una región ya no puede
hacerse pasar por la real.

`tests/test_pr27_r05_routing_wiring_closure.py` fijaba además la neutralidad en
la otra dirección: la invocación opaca `connect(...)`/`cycle()`, los sleeps, el
backoff, el logging y el health **no** movían la identidad.

Identidad recomputada en aquel intento: `5a5cb09f…` → `c939add3…`, con los
mismos 32 componentes.

## Cierre por módulo completo (corrección vigente, ADR-012)

Una tercera revisión independiente refutó `e84ebe81`/`9b2e082c`. El defecto no
era un símbolo olvidado sino la **forma** de la propiedad: mientras la identidad
se construya con regiones parciales más `MATERIAL_SYMBOLS`, lo único que puede
afirmar es «lo enumerado no cambió». Cinco mutaciones conservaban `c939add3…`:

1. Escritura directa en `TRADE_STORE` desde código fuera de toda región.
2. Un helper nuevo que escribe en el store, lanzado como tarea desde `main()`.
3. Invertir la clasificación buy/sell en `TradeBucket.add`.
4. Ampliar el bucket realtime de 5 a 10 segundos.
5. Sustituir `from functools import partial` por una implementación que descarta
   el último argumento ligado —el `routing` atestiguado.

La corrección añade el tipo de componente `python_module`, que canonicaliza el
**AST completo** de un fichero sin marcadores y sin lista de símbolos, y lo
aplica a `app/scalp_collector.py`, `app/ws_collector.py` y
`app/signal_runtime_contract.py`. Los siete componentes parciales que se
solapaban con esos ficheros quedan sustituidos: 32 → **28** componentes.

La cobertura incluye por construcción imports, parsing, clasificación de
agresión, cálculo de buckets, stores, colas, sesiones, loops, flush, delivery,
creación de tareas y entrypoints.

**Coste aceptado y documentado**: backoff, logging, health y sleeps en los dos
colectores **dejan de ser neutrales**. Los tests que fijaban esa neutralidad se
invierten en vez de borrarse. Comentarios, docstrings y formato **siguen**
siendo neutrales, por canonicalización AST.

`MATERIAL_SYMBOLS`, los marcadores `BEGIN/END` y los barridos estructurales se
conservan **sólo como defensa adicional**; los helpers de spans se re-anclaron a
los marcadores del fichero en vez de al registro de componentes, de modo que ya
no se pueden desactivar editando la lista.

Regresión: `tests/test_pr27_r05_module_identity_closure.py` — 20 tests. Las
cinco mutaciones anclan por AST en el nodo real y reescriben en sus propios
desplazamientos de byte.

Identidad recomputada: `c939add3…` → `c7bf8e5b…`, 28 componentes (después `451f4955…`, 42). Contrato de
runtime y hashes legacy spec v1/v2/v3 **sin cambios**.

### Nomenclatura de la serie de reworks

| Rework | Commit | Estado |
|---|---|---|
| Implementación inicial | `5a99ab5371eca057afc7374ed8cbf544e558113e` | landed |
| R01 | `e58f1fab2b8ebfd158608805fafc87fc559211c7` | landed |
| R02 | **no existe commit identificable**; se declara explícitamente y no se inventa | — |
| R03 | `0496819a15699bae3b80fc92e803a50adf40df54` | landed |
| R04 | `ee3792ca9f26b1cc20f354e9eaf35332b8ce266e` | landed, incompleto |
| R05 (candidato parcial) | `c879bdecf5eb453b5a91853e917be79d3df9042d` | **REFUTADO: A-02 abierto** |
| R05 (primer cierre) | `700f7695f97c1d094a2180b7a6916686429abda3` | **REFUTADO: mutaciones por primera aparición textual** |
| R05 (continuidad documental) | `450cf2fb5633779755f3d7db4069fc86a800eb8b` | **REFUTADO junto con `700f7695`** |
| R05 (cierre de wiring) | `e84ebe8140c8393ea2ef3447d8c165d32b594917` | **CANDIDATO**, pendiente de revisión independiente P0=0/P1=0 |

Esta corrección **no es R06**: sigue siendo el cierre del mismo R05, en su
tercer intento.

### Admisibilidad de observaciones anteriores

Las observaciones producidas antes de la procedencia de contrato (columnas
`runtime_contract_*` en NULL) **no son admisibles como evidencia confirmatoria
spec-v4**: no puede demostrarse bajo qué ruteo efectivo se produjeron sus
insumos crudos. No se realizará ningún backfill inventado de procedencia.
Pueden conservarse únicamente como información histórica o diagnóstica,
claramente identificada como tal por sus columnas de procedencia en NULL y por
quedar fuera de cualquier población OOS spec-v4, cuyo muestreo exige
procedencia presente e igual a la del manifest congelado.

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
