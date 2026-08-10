# Coinalyze Operator Dashboard v1.5.0

## v1.5.0 — reorganización en 8 pestañas, fail-closed y separación dirección/setup

Detalle completo en [`docs/CHANGES_v1.5.0.md`](docs/CHANGES_v1.5.0.md).

- **Navegación en 8 pestañas**: `mesa → estructura → flujo → derivados → liquidez → contexto
  → calidad → replay`. Los enlaces internos apuntan a los identificadores reales y cualquier
  hash desconocido abre **Mesa**; antes caía en una sección inexistente y dejaba la página
  en blanco.
- **La ausencia de dato deja de valer cero.** `asNumber()` rechaza `null`, `''`, booleanos,
  `NaN` e infinitos; las gráficas omiten los puntos ausentes en vez de dibujarlos sobre el
  eje. En el backend, `compute_scalp_summary()` conserva `None` en liquidaciones, cambio de
  OI y distancia a VWAP, y esos componentes dejan de contar peso en la cobertura. Un cero
  **medido** sigue mostrándose como cero.
- **Dirección y setup son dos controles**: *Long/Short/Neutral* y
  *Ninguno/Ruptura/Rechazo/Reversión/Continuación*. Cada setup tiene requisitos,
  pendientes e invalidaciones propios (`app/setups.py`) y publica
  `PENDIENTE / CANDIDATO / CONFIRMADO / FALLIDO / NO EVALUABLE`. Los valores guardados de la
  versión anterior se traducen al par correspondiente.
- **Fin del umbral universal de 5 bps.** La ejecución se juzga con
  `coste_total / objetivo` y `coste_total / riesgo` (`execution_assessment()`). Sin objetivo,
  stop, comisión o tamaño el veredicto es **SIN EVALUAR**. Queda un umbral de spread
  *configurable por perfil* como aviso secundario, que no veta nada.
- **El perfil cambia la jerarquía visual, no el dato bruto.** Intradía prioriza 4h/1h y
  18m/15m/5m; swing prioriza 3d/1d/8h y 4h/1h, con 18m/15m/5m como entrada y 1m/30s como
  capa de ejecución de peso 0. `5m` deja de estar a la vez en entrada y en referencia.
- **El diferencial spot−futuros deja de encabezar el flujo.** Manda cada pata, su
  delta/volumen y el cuadrante; la resta queda como columna de auditoría, oculta por
  defecto, sin color direccional y con la advertencia de que compara escalas distintas.
- **La pestaña Calidad separa tres niveles**: salud de servicios, calidad de feeds de
  mercado (`/api/quality/feeds`) y calidad por métrica. El título “Fuentes de datos” ya no
  se usa para procesos internos.
- **Mesa con snapshot coherente**: `/api/desk/state` calcula una sola vez los componentes
  compartidos y los publica con un mismo `as_of`, declarando la frescura por fuente y los
  estados parciales.
- **Etiquetas ajustadas a la evidencia**: “Frecuencia histórica de ruptura” (no
  probabilidad), “Operaciones spot de gran tamaño” (el tamaño no identifica al
  participante) y “Lectura contextual”.
- **Barra superior con `grid-template-areas`**, verificada a 1920/1440/1366/1100/900/700/430 px.

**Limitaciones conocidas.** La integridad de huecos explícitos y el CLI
`scripts/recover_gaps.py` ya forman parte de PR #3. La recuperación solo se permite cuando
existe una fuente histórica con exchange, mercado, significado, símbolo y granularidad
idénticos; como todavía no hay adapters exactos registrados para los streams realtime ni
para order books, esos huecos se marcan `unrecoverable` en vez de sintetizarse. Los endpoints
administrativos `/api/data-quality/gaps*` siguen fuera de alcance. Las bandas de
coste/objetivo y los pesos por capa son convenciones declaradas, no resultados
backtesteados, y viajan en la respuesta para poder auditarlos. La afirmación anterior de que
`bars_closed_beyond`, `retest_done`, `returned_inside`, `pullback_pct` y `level_defended` no
se medían quedó **superseded** por la implementación posterior de `setup_observables()`:
ahora se calculan desde velas cerradas cuando existe un `observ_bundle`; sin ese paquete
siguen en `None` de forma fail-closed.

## v1.4.9 — régimen macro externo interpretable

- Separa los percentiles internos de CVD/OI/funding del contexto macro real.
- Conserva 800 días de tasas, dólar, renta variable, VIX y stablecoins; añade calendario
  CPI/NFP/PPI/JOLTS/FOMC y flujo ETF BTC opcional mediante `COINGLASS_API_KEY`.
- Clasifica el entorno como favorable/mixto/restrictivo y explica conflictos con el sesgo
  interno sin fabricar probabilidades ni convertir el macro en gatillo de entrada.
- Inyecta `external_macro_context` en `/api/ai/context` y, por extensión, en `/preview`.

Dashboard interno de microestructura y scalping para BTC, ETH y SOL. Incluye API privada para contexto IA, PostgreSQL local, colectores systemd, UI web y nginx como único punto remoto.

## v1.4.8 — lectura rápida del flujo sin look-ahead

- Nueva tarjeta visible al entrar: resume la última sesión como **hecho**, **interpretación**,
  **acción de vigilancia**, **confirmación** e **invalidación**. Puede decir “se está comprando
  fuerte en spot”, “por más que venden, el precio no cae” o “posible reversión”, pero nunca lo
  presenta como una orden ni como probabilidad de ganancia.
- El algoritmo combina el cuartil histórico del CVD spot, la dirección de futuros, la respuesta
  del precio y una secuencia de hasta cuatro sesiones. Sólo marca posible reversión cuando una
  defensa previa recibe después compra spot fuerte con avance.
- `/api/daily` incorpora `quick_read` y acepta `as_of=AAAA-MM-DD`. Tanto la muestra visible como
  los percentiles se cortan en esa fecha, de modo que un replay histórico no conoce el futuro.
- La interfaz mantiene los importes que sustentan la lectura y declara qué dato la confirmaría
  o invalidaría. “Confluencia” mide acuerdo entre evidencias, no probabilidad de éxito.

## v1.4.7 — flujo ejecutado y respuesta del precio

- El contexto diario deja de llamar **Acumulación/Distribución** a una sola sesión de CVD.
  Ahora informa el hecho observable: ambos compraron, ambos vendieron o spot y futuros se
  opusieron.
- Nueva columna **Respuesta del precio**: distingue compra/venta con seguimiento de compra o
  venta sin avance. Esta última se presenta como posible absorción, nunca como prueba de
  inventario institucional.
- Se retiran de la tabla los dos diferenciales spot−futuros: mezclaban escalas y uno carece de
  histórico. Los datos siguen en la API para auditoría, pero no ocupan la lectura operativa.
- Las barras comparan spot y futuros contra su propia escala de 24 sesiones para que el mayor
  volumen del perp no oculte la pata spot. La sesión se identifica explícitamente como
  09:30 ET del día anterior → 09:30 ET del día mostrado.

## v1.4.6 — perfil de volumen y delta por nivel de precio

- Nuevo `/api/delta-profile` y panel **Perfil de volumen y delta**: reparte el volumen y el
  delta de cada vela entre los cubos de precio que cruza su rango low-high, y publica POC,
  área de valor del 70%, nodos delgados y delta neto. Contesta "en esta zona, ¿hubo más compra
  o más venta?" para todos los niveles a la vez, sin teclear los bordes.
- Ventanas según la cobertura real: 30/90/300 días con velas de 4 h (1.801 velas desde
  2025-10-08) e intradía con 5 min (2.512 velas desde 2026-07-27). No se ofrece 300 d en 5 min
  porque esa profundidad no existe en la fuente.
- Declara sus dos límites: el reparto dentro de la vela es uniforme y por tanto aproximado, y
  el delta es de **futuros Binance (`.A`)**, no del contado — el CVD spot histórico solo existe
  agregado por sesión, sin resolución de precio.
- No sustituye a `/api/volume-profile`, que sigue alimentando el contexto de IA con la sesión
  UTC en curso.
- Corregido el índice de cubo: `104 // 0.2` da 519 y no 520, así que el volumen de una vela que
  empezaba justo en un borde se etiquetaba un cubo por debajo.

## v1.4.5 — presentación del operador

Solo presentación: ninguna fuente de datos ni indicador nuevo. Todo sale de payloads que el
dashboard ya descargaba.

- Los ejes de CVD, open interest, whale y diario dejan de imprimir el float crudo
  (`418951166.51`) y muestran importes compactos (`$418.95M`, `$7.05B`); el eje de precio
  recupera el separador de miles. Cubre eje, crosshair y línea de precio.
- **Perfil de liquidaciones por nivel** en lugar de la tabla de concentración: escalera de
  precios, longs a la izquierda, shorts a la derecha y el precio actual marcado. Es densidad
  **ya ejecutada** en los últimos 60 min, no una proyección de dónde reventarán posiciones: no
  disponemos del apalancamiento del libro y el panel lo declara.
- Zona, rango y ruptura comparten un panel con pestañas y llegan **precargados** con la zona
  activa, el rango de Wyckoff con sus fechas y la resistencia más cercana. Lo escrito a mano no
  se sobrescribe; al cambiar de activo todo vuelve a recargarse.
- Sparkline de 60 sesiones en las cuatro tarjetas de cabecera, alimentada del rollup diario en
  el tramo lento de refresco (1/min), no en el ciclo de 15 s.
- La ausencia de actividad whale se cuenta en texto (`1 de 384 ventanas`) en vez de dibujarse
  como una línea plana en cero.
- Los paneles se ajustan a su contenido y la imbalance del order book se dibuja como barra.

## v1.4.4 — rango Wyckoff automático

- `/api/wyckoff` busca por sí solo el rango reciente entre ventanas de 40 a 365 sesiones y
  reutiliza las cinco pruebas del validador manual.
- La lectura combina estructura de precio/volumen con CVD spot y delta de futuros para mostrar
  acumulación compatible, distribución compatible o equilibrio, siempre con componentes y
  cobertura visibles; el score no se presenta como probabilidad.
- El gráfico de precio incorpora el modo `Wyckoff 1D`, con soporte, mitad, resistencia y eventos
  spring/upthrust. El modo intradía de 5 minutos permanece disponible.
- Se corrige el conteo de intentos previos del estimador de ruptura: el empuje aún abierto ya no
  se cuenta como un intento anterior.

## v1.3.7 — cockpit por horizonte y memoria de mercado de dos años

- La portada deja de apilar todo el sistema y presenta un **plan operativo por horizonte**:
  corto (1–15m), mediano (2 sesiones) y largo (días–semanas). Cada lectura declara qué
  vigilar, cómo confirmarlo, dónde queda invalidada y qué evidencia la sustenta.
- Las cinco áreas son vistas exclusivas y se cargan bajo demanda. La actualización normal
  baja de 23 endpoints cada 15 segundos a 4, más 3 consultas de contexto cada minuto.
- Se retiran de la UI las alertas scalp desfasadas, su historial repetitivo y el bloque de
  posicionamiento duplicado. Los endpoints históricos se conservan para auditoría externa.
- Nuevo bloque `market_memory_2y`: guarda 730 velas diarias compactas y busca cinco
  episodios no solapados similares por retorno, posición/drawdown de 60d, volatilidad y
  volumen. Muestra los retornos observados 5/10/20 días después como analogía descriptiva,
  nunca como probabilidad ni señal autónoma. `/api/market-memory` lo expone también a IA.
- Las barreras diarias pueden usar los 730 días; el CVD de 90 sesiones se mantiene para su
  horizonte táctico de dos sesiones. El histórico diario no inventa CVD spot: su fuente es
  OHLCV de futuros Binance vía Coinalyze y la UI lo declara.
- Corregida la unidad de funding: Coinalyze entrega puntos porcentuales (`0.005 = 0.005%`).
  La UI y los umbrales heurísticos lo multiplicaban implícitamente por 100.

## v1.3.6 — barreras de precio y esfuerzo de ruptura

- Nuevo panel **Barreras de precio** y bloque `price_barriers`: agrupa rechazos de pivotes
  diarios y 4h en zonas de soporte/resistencia. La dificultad 0–100 combina repeticiones,
  reacción posterior en ATR, volumen relativo, absorción CVD y recencia.
- Muestra volumen típico de los rechazos, distancia al precio y presión viva de ruptura:
  volumen perp de 15m frente a su mediana de 36h, delta direccional, movimiento y book L5.
  No llama probabilidad al score ni afirma conocer liquidez oculta.
- Una ruptura sólo se considera vigilable con cierre 15m fuera de la zona, esfuerzo
  direccional >=70/100 y retest. El caso contrario favorece vigilar rechazo; dentro del
  rango, indica esperar.
- Se incorporan velas de 5m con retención de 400 días para reconstruir zonas 4h de largo
  plazo sin ampliar innecesariamente las tablas pesadas. `backfill_ohlcv_5m.py` carga el
  histórico de forma idempotente.

## v1.3.5 — lectura CVD de 90 sesiones para operaciones de dos sesiones

- Nuevo bloque `cvd_swing_90d` en `/api/dashboard/state` y en el contexto IA. Compara el
  percentil del CVD spot de 3 sesiones con el percentil del retorno de precio equivalente,
  ambos contra una base móvil de 90 sesiones. Activa LONG/SHORT solo con una separación de
  ±30 puntos y entrega tesis, evidencia, confirmación e invalidación.
- El mismo bloque calcula su observación walk-forward a 2 sesiones por activo. Expone
  muestra, aciertos y retornos antes de costes, siempre etiquetados como contexto
  histórico con señales solapadas, no como probabilidad.
- Nuevo panel **Lectura operativa CVD 90 sesiones**: combina la señal con estructura
  4h/8h/1d, swing de fondo, divergencias, setup primario y calidad de datos. Un conflicto
  de estructura o datos degradados bloquea la lectura operativa.
- Los setups diarios y la racha usan ahora `cvd_spot_usd` y `cumulative_spot`; antes
  reutilizaban el diferencial sesgado por futuros pese a la advertencia de v1.3.3. Los
  valores ausentes ya no se convierten implícitamente en cero al evaluar condiciones.
- Corregida la sesión activa de fin de semana: el mercado cripto es 24/7 y ya no se
  fusionan sábado/domingo en una falsa sesión de 48–72 horas desde el viernes.
- Validación: 122 tests, `ruff`, sintaxis JavaScript, smoke test y barrido de endpoints.

## v1.3.4 — corrección de procedencia y contexto completo para IA por web

**`.A` en Coinalyze es Binance, no un agregado multi-venue.** El código venía etiquetando
la pata de futuros como `coinalyze_aggregate` / "todos los venues". Es falso: el catálogo
de exchanges de Coinalyze dice `.A = Binance`, y los números lo confirman
(`open_interest`(.A) = 6.90 B = OI real de Binance; `oi_bybit`(.6) = 3.65 B = Bybit).

- Corregidas las etiquetas en `api.DAILY_SOURCES`, `scalp_logic.context_metadata`, las
  notas de divergencias, el esquema, el front y este README.
- **Bug real corregido**: `oi_context.by_venue` publicaba `other_venues_oi_usd = total −
  bybit` describiéndolo como "todos los venues menos Bybit". Era Binance − Bybit, un número
  sin significado que podía salir negativo. Ahora expone `binance_oi_usd`, `bybit_oi_usd`,
  `two_venue_total_usd` y `bybit_share_of_two_venues_pct`.
- El hallazgo empírico de v1.3.3 no cambia (el diferencial sigue dominado por futuros en
  92-95% de las sesiones), pero **la causa sí**: no es "1 venue vs muchos" sino que el perp
  mueve ~10× el spot ($9.7 B vs $1.0 B/24 h en BTC). Por eso `cvd_diff_2v_usd` alinea
  venues pero **no** corrige la asimetría de escala.

**Perfil `max` y serie diaria para análisis por IA.** El contexto entregaba agregados y
percentiles ya digeridos, pero nunca la serie cruda: un modelo no podía distinguir una
tendencia de semanas de un pico aislado.

- Nuevo bloque **`daily_history`**: sesión a sesión con CVD spot/futuros/diferencial,
  acumulados, percentiles contra toda la historia guardada, `flow_direction`, OI, funding,
  volumen y liquidaciones, más `totals` y `field_notes` que advierten al modelo de cómo
  leer cada columna. `pro` trae 30 sesiones, `max` trae 90.
- Nuevo perfil **`max`**: sin recortes — 90 sesiones, divergencias intradía, 9 ventanas de
  delta, veredictos pasados con su retorno realizado. Pensado para pegar el JSON en una IA
  por web, donde el coste en tokens no es la restricción.
- El bridge de Telegram usa `max` en `/preview` (`TELEGRAM_PREVIEW_PROFILE`), que ya
  entregaba el payload como documento JSON único. Resultado: **~446 KB, ~106 k tokens**,
  muy por debajo del límite de 50 MB de Telegram.
- Corregido de paso: `compact_value` no manejaba `date` (que no es subclase de `datetime`),
  así que `session_date` llegaba intacto a `json.dumps()` y habría reventado el endpoint.

## v1.3.3 — el diferencial spot/futuros dejaba de ser comparable

`cvd_fut_usd` se calcula desde `ohlcv`, que es el perp de **Binance** (el sufijo `.A` de
Coinalyze es Binance, **no** un agregado multi-venue: verificado contra su catálogo de
exchanges y contra el OI real), mientras `cvd_spot_usd` tiene **Binance + Bybit** spot.
Como el perp mueve ~10× el spot ($9.7 B vs $1.0 B/24 h en BTC), la resta queda dominada por
la pata de futuros: medido sobre 90 sesiones de las tres monedas, esa pata pesa 4.8-5.9×,
el signo del diferencial es el **inverso del CVD de futuros en 92-95%** de las sesiones y
solo coincide con lo que hizo el spot en **30-36%**. El panel que lo pintaba verde/rojo
estaba etiquetado "Acumulación / distribución", así que una sesión con spot **vendiendo**
salía como acumulación siempre que los futuros vendieran más (36 sesiones así solo en BTC).

- El panel pasa a llamarse **"Flujo por sesión"** y clasifica por el signo de **ambas**
  patas: acumulación / distribución / "solo cambió la magnitud". Ya no llama acumulación a
  una sesión en la que el spot vendió.
- Nueva columna `cvd_diff_2v_usd`: la misma resta con **ambas patas en Binance+Bybit**,
  desde `futures_trades_agg`. Alinea los venues, pero **no corrige la asimetría de escala**:
  el perp seguirá pesando ~10× más que el spot. Solo se puebla **hacia adelante** — depende
  de una tabla que se retiene horas, no meses. `SCALP_MINUTE_RETENTION_HOURS`
  (36 h) existe para que el job diario alcance a leer la sesión completa.
- La tabla diaria muestra la procedencia de cada columna y el **percentil** de cada valor
  frente a toda la historia guardada. Se retiró la columna Whale: era $0 en el 98% de las
  sesiones porque los umbrales por trade casi nunca se cruzan con dos venues.
- **`daily_verdict`**: el `swing_score`, su desglose, el régimen y el setup primario se
  calculaban al vuelo y se descartaban (`metrics_snapshot` retiene 30 días,
  `scalp_signal_snapshot` 72 horas). Ahora se congelan por sesión y `/api/verdicts` los
  devuelve junto al retorno realizado a 7 y 14 sesiones. Los pesos siguen **sin calibrar**;
  esto solo hace posible auditarlos más adelante.
- **Percentiles condicionales** en `/api/macro-context`: además del percentil, la
  distribución empírica del retorno posterior en las sesiones históricas que estuvieron en
  ese mismo estado. Descriptivo, no predictivo: ~1 año de muestra y un solo régimen.
- **`/api/divergences`**: precio vs CVD spot **acumulado** (una sola serie, un solo
  universo de venues) en ventanas de 2, 4 y 6 semanas.
- Rollup diario ampliado: `volume_usd`, `price_high/low`, `oi_high/low`, liquidaciones y
  `tx_count` por sesión, para que lo granular no se pierda al cumplir 14 días.

## v1.3.2 — correcciones de la auditoría

La versión 1.3.2 fue de corrección, sin cambios de alcance sobre v1.3.1:

- `/metrics` devolvía 500 (`KeyError: 'detail'`): el `SELECT` de heartbeats no pedía
  la columna que el render necesitaba. El smoke test ahora cubre `/metrics` y tres
  endpoints por símbolo, que es lo que dejó pasar la regresión.
- `update.sh` valida que el árbol fuente esté completo antes del `rsync --delete`;
  un paquete solo-app borraba `sql/`, `deploy/`, `scripts/` y `requirements.lock`.
  El paquete de despliegue ahora incluye el árbol completo.
- `trend_matrix` medía el cambio de OI de `1d`/`3d` sobre toda la ventana cargada
  (~60 sesiones) en vez de sobre n sesiones.
- Absorción unificada en `classify_absorption`: el endpoint y el resumen de scalp
  usaban umbrales distintos (0.02 vs 0.04) y podían contradecirse en el dashboard.
- Los lags (`EXTRACT(EPOCH ...)`) se emiten como número y no como string.

La versión 1.3.1 conservaba la organización de v1.3.0 y corrigió el flujo spot de
4h/8h combinando agregados de un minuto con una cola realtime sin solapamiento.
La matriz muestra cobertura por horizonte, la confianza valida datos por símbolo
y cobertura 8h, el OI sub-5m se presenta como no disponible y el CVD usa buckets
cerrados presentes en spot y futuros.

Documentación principal:

- `docs/IMPLEMENTACION_DESDE_CERO.md`: instalación 0 a 100 para Proxmox LXC o ESXi Debian.
- `docs/MANUAL_IMPLEMENTACION_FINAL.md`: mismo manual publicado dentro de la UI en la sección `Manual`.
- `docs/AI_DEVELOPMENT_BRIEF.md`: descripción técnica para que otra IA entienda el diseño sin código.

Cierre final de seguridad:

- nginx aplica allowlist real mediante `/etc/nginx/snippets/coinalyze-allowlist.conf`.
- `NGINX_ALLOWED_CIDRS` controla qué IP/CIDR puede acceder a `8090/8443`.
- FastAPI conserva `API_INTERNAL_ALLOWED_CIDRS` para endpoints internos y acceso directo local.
- `API_INTERNAL_TOKEN` es obligatorio para `/api/*` y `/metrics`.

---

# Coinalyze Derivatives Operator

Aplicación web interna, de solo lectura, para interpretar microestructura de futuros
perpetuos de BTC, ETH y SOL. Contrasta flujo spot contra futuros y presenta CVD,
CVD diferencial, whale delta, funding, open interest, liquidaciones, buy-trade ratio,
régimen de mercado e histórico diario con corte NYSE.

No ejecuta órdenes, no se conecta a una cuenta de exchange y no genera entradas
mecánicas. El motor de setups clasifica contexto probabilístico e invalidaciones.

## Arquitectura

```text
Coinalyze REST ──> ingest (60 s) ───────────┐
                                             │
Binance spot WS ─┐                           v
                 ├─> ws collector ──> PostgreSQL 15 <── daily aggregator
Bybit spot WS ───┘          │                ^
                            └─ 5 s live       │
                                             │
Browser <── Basic Auth / Nginx + internal token <── FastAPI REST + SSE
```

Procesos independientes:

- `app.ingest`: OHLCV de futuros, OI, funding, predicted funding, liquidaciones y snapshots.
- `app.ws_collector`: trades spot públicos Binance/Bybit, buckets de 1 minuto y 5 segundos.
- `app.daily_agg`: histórico por ventanas `[09:30 ET D-1, 09:30 ET D)` y retención.
- `app.scalp_collector`: futures tape, order book, liquidaciones realtime y estado scalp.
- `app.api`: frontend, API de consulta, evaluación de setups, scalp summary y SSE.

## Decisiones de consumo

- PostgreSQL 15 estándar; no requiere TimescaleDB.
- HTML, CSS y JavaScript sin framework.
- Lightweight Charts vendorizado localmente.
- Despliegue directo con systemd; no requiere Docker ni Kubernetes.
- Retención predeterminada: 14 días de datos duros, 30 días de snapshots, 2 horas realtime.

Perfil inicial recomendado: LXC Debian 12 no privilegiado, 2 vCPU, 2 GB RAM y 24 GB SSD.

## Instalación en Proxmox

Consulte [`deploy/proxmox/README.md`](deploy/proxmox/README.md). Dentro del contenedor:

```bash
COINALYZE_API_KEY='SU_API_KEY' \
DASHBOARD_PASSWORD='UNA_CLAVE_LARGA' \
./deploy/proxmox/install.sh
```

El servicio queda en `https://IP_DEL_LXC:8443` con autenticación Basic. Restrinja ese
puerto a la VLAN o hosts de operación.

## Instalación manual para desarrollo

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
# Editar API_KEY y PG_PASSWORD
psql -h 127.0.0.1 -U coinalyze -d coinalyze -f sql/schema.sql
```

Terminales separadas:

```bash
python -m app.ingest
python -m app.ws_collector
python -m app.daily_agg
uvicorn app.api:app --host 127.0.0.1 --port 8000
```

## API

| Endpoint | Función |
|---|---|
| `/api/snapshot` | Último snapshot completo por símbolo |
| `/api/ohlcv` | Velas agregadas |
| `/api/cvd` | CVD de futuros |
| `/api/cvd/spot` | CVD spot |
| `/api/cvd/divergence` | Spot, futuros y diferencial |
| `/api/oi` | Open Interest |
| `/api/liquidations` | Liquidaciones long/short |
| `/api/whale/delta` | Delta institucional spot |
| `/api/daily` | Histórico NYSE, racha, lectura rápida y replay opcional con `as_of` |
| `/api/setup` | Evaluación de setups A–E e invalidaciones |
| `/api/stream` | SSE de precio, delta y whale live |
| `/api/healthz` | Estado y lag del pipeline |
| `/api/ai/context` | Payload compacto por símbolo para análisis IA |
| `/api/ai/context/bundle` | Payload compacto multi-símbolo para análisis IA |
| `/api/ai/profiles` | Perfiles `lite`, `default` y `pro` para payload IA |

Swagger/OpenAPI está deshabilitado deliberadamente.

## Seguridad implementada

- API y PostgreSQL escuchan solo en loopback.
- Nginx aplica autenticación, CSP, anti-framing, `nosniff` y límite de SSE.
- Consultas parametrizadas y allowlists de símbolos/intervalos.
- Validación de NaN, infinito, precios, cantidades, nocional y timestamps de feeds.
- Constraints SQL para integridad económica de OHLC, OI, BTR y volúmenes.
- Buckets WS se eliminan de memoria únicamente después del commit y si no cambió su revisión.
- Servicios systemd sin privilegios y con hardening.
- Backup PostgreSQL diario con retención de 14 días.

## Operación

```bash
systemctl status coinalyze-{api,ingest,ws,scalp,daily}
journalctl -u coinalyze-ingest -u coinalyze-ws -u coinalyze-scalp -f
curl -k -u operator https://IP_LXC:8443/api/healthz
systemctl list-timers coinalyze-backup.timer
```

Actualización desde una copia nueva del proyecto:

```bash
sudo /opt/coinalyze/scripts/update.sh /ruta/a/la/nueva/copia
```

Restauración de backup:

```bash
systemctl stop coinalyze-{api,ingest,ws,daily}
export PGPASSWORD='PASSWORD_DB'
pg_restore -h 127.0.0.1 -U coinalyze -d coinalyze --clean --if-exists \
  /var/backups/coinalyze/coinalyze-FECHA.dump
systemctl start coinalyze-{ingest,ws,daily,api}
```

## Limitaciones explícitas

- La sesión en vivo omite feriados bursátiles; distingue fines de semana y DST.
- El histórico no puede recuperar datos anteriores a la primera instalación sin otra fuente.
- Los pesos de régimen y setups son heurísticos, no están calibrados mediante backtest.
- El CVD spot persistente espera la ventana de trades tardíos; el carril SSE permanece inmediato.
- La disponibilidad y exactitud dependen de Coinalyze, Binance y Bybit.

El manual funcional original se conserva en
[`docs/MANUAL_INTERPRETACION.md`](docs/MANUAL_INTERPRETACION.md).


## v1.1.1 — respaldo funcional validado

Esta versión consolida los patches aplicados durante la puesta en marcha:

- `coinalyze-scalp` habilitado e incluido en `pipeline_heartbeat`.
- `TRUSTED_HOSTS` y `SYMBOLS` robustos para `pydantic-settings`, `systemd` y `bash source`.
- Intervalos API enviados a PostgreSQL como `datetime.timedelta`.
- `update.sh` idempotente para upgrades desde v1.0/v1.1.0.
- Manual de interpretación ampliado con sección específica de scalping.

Ver `docs/PATCHES_APPLIED.md`.


## v1.1.2 hardening

Corrige la auditoría posterior a v1.1.1: contexto scalp sin colapso por libro ausente, divergencia spot/futuros en el score, heartbeat de scalp controlado por monitor, libro combinado no cruzado, validación de secuencia Bybit, conteo de overflow de liquidaciones, `liq_norm` simétrico, VWAP anclado a sesión NYSE, token interno opcional FastAPI/Nginx y frontend sin `innerHTML`.

## v1.2.2 — cierre de residuales

- `scalp_collector` ya no importa la capa web `app.api`; la lógica compartida vive en `app/scalp_logic.py`.
- UI conectada a `/api/dashboard/state`, `/api/scalp/basis`, `/api/scalp/signals` y `/api/scalp/liquidation-levels`.
- `calibrate_signals.py` corrige autocorrelación con modos `episode` y `non_overlap`.
- Documentación Prometheus agregada en `docs/PROMETHEUS.md`.
- Validación local: 25/25 tests.

## v1.2.0 — feedback loop y observabilidad

Extiende v1.1.2 sin modificar todavía el manual/PDF:

- `scalp_signal_snapshot` queda activo: `coinalyze-scalp` persiste el resumen de señales cada `SCALP_SIGNAL_INTERVAL_SECONDS`.
- Nuevo `/api/scalp/signals` para revisar histórico de señales efímeras.
- Nuevo `/api/scalp/basis` para basis perp-spot en bps.
- Nuevo `/api/scalp/liquidation-levels` para clustering de liquidaciones por bucket de precio.
- Nuevo `/api/data-confidence` con lag de snapshot, cobertura de venues y estado de libro combinado.
- Nuevo `/api/dashboard/state` como endpoint batch para reducir polling multipanel.
- Nuevo `/metrics` Prometheus protegido por `X-Internal-Token`.
- `monitor()` de scalp degrada también por flush de trades/books/signals, no solo por vivacidad WS.
- `smoke_test.sh` soporta `API_INTERNAL_TOKEN` para validaciones locales endurecidas.
- `scripts/calibrate_signals.py` genera reporte offline de forward returns sobre señales persistidas.
- Retención configurable para `scalp_signal_snapshot`; `daily_session_agg` conserva histórico indefinidamente por default (`DAILY_SESSION_RETENTION_DAYS=0`).
- Limpieza de código muerto de intervalos realtime en endpoints históricos y comparación de token con `hmac.compare_digest`.

Validación local: pytest 20/20, ruff limpio, compileall OK, bash -n OK y wheel build OK.

## v1.2.4 respaldo completo

Este paquete incluye instrucciones para instalación desde cero en `docs/IMPLEMENTACION_DESDE_CERO.md` y un asistente de configuración/rotación de secretos en `scripts/configure_secrets.sh`.

Mantiene la API consolidada para IA introducida en v1.2.3:

- `/api/ai/context`
- `/api/ai/context/bundle`
- `/api/ai/profiles`
