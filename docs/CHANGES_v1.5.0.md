# v1.5.0 — corrección de la reorganización

---

## PR1 — integridad P0 de market data (2026-08-09)

- Bybit conserva la semántica documentada de la posición liquidada: `Buy` es long y `Sell`
  es short. Binance mantiene su semántica previa basada en el lado de la orden forzada.
- `market_feed_health` registra por exchange la continuidad real del stream de
  liquidaciones. Una ventana de 5 minutos sólo se publica como medida si Binance y Bybit
  estuvieron sanos durante toda ella, sin pérdidas de cola y con estado reciente.
- El libro Bybit valida continuidad con `u` (update ID); `seq` queda sólo como diagnóstico.
  Duplicados, retrocesos o saltos eliminan el libro local hasta recibir un snapshot nuevo;
  `u=1` reemplaza el libro conforme a la documentación oficial.
- OI 15m usa cuatro observaciones 5m consecutivas y cerradas. Como `ts` etiqueta el inicio
  del bucket, sus cierres efectivos delimitan la misma ventana `[start,end)` que las quince
  velas 1m cerradas usadas para el movimiento de precio.

**Migración:** `sql/schema.sql` crea tabla e índice con `IF NOT EXISTS`; puede aplicarse sobre
una instalación existente sin borrar datos. **Rollback:** detener primero el código que lee
la salud específica y después ejecutar `DROP INDEX IF EXISTS market_feed_health_updated_idx;`
y `DROP TABLE IF EXISTS market_feed_health;`. La tabla sólo contiene estado operativo, no
eventos de mercado.

---

## Segunda ronda (2026-08-07): cuatro correcciones previas al gap recovery

### 1. El umbral de 5 bps desaparece también de la capa visual

El backend ya juzgaba la ejecución por coste/objetivo, pero `static/app.js` seguía pintando
de rojo el spread bruto en tres sitios (`(asNumber(scalp.spread_bps) || 0) > 5`, lo mismo en
el libro por venue y en el slippage por tamaño). Un número en rojo es una clasificación,
aunque el backend no la haga.

El spread, el slippage y el spread por venue se muestran ahora en **neutro**. El color del
veredicto sale de `executionClass()`, que lee `cost_to_target_band` y `cost_to_risk_band` y
se queda con la peor de las dos. `SIN EVALUAR` es neutro a propósito: no saber si sale cara
no es lo mismo que saber que sale cara. `spread_warning` se muestra como fila aparte,
etiquetada «secundario», y no interviene en el color.

### 2. Un setup no se CONFIRMA con requisitos críticos sin evaluar

`evaluate_setup()` confirmaba cuando había algún requisito cumplido y ninguno pendiente, sin
mirar los `NO EVALUABLE`. Una ruptura se confirmaba con la aceptación, el retest y el regreso
al rango sin medir: es decir, por «precio por encima de la resistencia + delta positivo».

Cada requisito declara ahora su nivel:

| | Ruptura | Rechazo | Reversión | Continuación |
|---|---|---|---|---|
| **CRITICAL** | barrera, cierre más allá, aceptación, no vuelve dentro | contacto, sin aceptación fuera, retorno al rango, sin cierres fuera | contexto previo contrario, estructura, cambio de flujo | contexto alineado, retroceso, defensa del nivel |
| **CONFIRMATION** | volumen, delta spot, delta futuros, OI | reacción, flujo contrario | spot, OI | flujo reanudado, multitemporal |
| **SECONDARY** | retest, libro | absorción | liquidaciones | VWAP |

`CONFIRMADO` exige: sin invalidaciones, **todos** los críticos evaluables y cumplidos,
`MIN_CONFIRMATIONS` confirmaciones y `MIN_COVERAGE_PCT` de cobertura. Si falta un crítico, el
techo es `CANDIDATO`. Se publica `coverage_pct`, `critical_total`, `critical_evaluable`,
`confirmation_total`, `confirmation_evaluable`, `missing_critical` y `missing_confirmation`.

**Nota histórica superseded:** en ese momento ningún setup confirmaba porque
`bars_closed_beyond`, `retest_done`, `returned_inside`, `pullback_pct` y `level_defended` aún
no se medían. El commit posterior `957b4b1` añadió `setup_observables()` sobre velas cerradas;
cuando el llamador aporta `observ_bundle`, los cinco observables ya se miden. Sin ese paquete
siguen en `None`, conservando el comportamiento fail-closed.

### 3. El signo del Open Interest deja de votar dirección

`_flow_check(oi_chg_pct, direction_sign)` trataba ΔOI como si fuera un delta. No lo es: el OI
sube cuando se abren contratos, los abra quien los abra.

`classify_oi()` devuelve un **estado** —`EXPANSION`, `CONTRACTION`, `FLAT`,
`EXTREME_EXPANSION`, `EXTREME_CONTRACTION`, `NO_EVALUABLE`— con `directional: False`
explícito. El extremo lo decide la banda medida o el z robusto si existen, y sólo si no, un
múltiplo declarado del piso; la respuesta dice cuál de los dos mandó.

`oi_price_reading()` compone precio + OI + flujo:

| Precio | OI | Lectura |
|---|---|---|
| ↑ | ↑ | expansión compatible con continuación alcista |
| ↓ | ↑ | expansión compatible con presión short |
| ↑ | ↓ | cierre de cortos / toma de beneficios — **no demuestra compras nuevas** |
| ↓ | ↓ | desapalancamiento / cierre de largos — **no demuestra ventas nuevas** |

Los dos cuadrantes de cierre devuelven `supports: None`: no sostienen ninguna dirección, así
que el requisito queda `PENDIENTE`, no `NO_CUMPLE`. Cada lectura lleva su `caveat`; ninguna
se presenta como relación causal.

### 4. Los huecos se dibujan como huecos

`seriesPoints()` ya no convertía la ausencia en cero, pero quitar el punto dejaba que el
motor uniera los dos extremos con una recta que se lee como dato.

**Medido contra la librería vendorizada** (5.2.0, `scratchpad/gapexp.html`, contando píxeles
de línea sobre la franja del hueco): ni `whitespace` ni `value: null` rompen un `LineSeries`
—las tres formas dibujaban ~400 px de línea sobre el hueco, igual que el control continuo—.
Lo único que produce discontinuidad real es **una serie por tramo**: 0 px.

`seriesSegments()` parte las filas en tramos contiguos y describe los huecos (muestras,
duración, extremos; `from`/`to` en `null` si el hueco está en un borde). `setGappedLine()`
mantiene un pool de series por gráfica: la primera carga además la línea de tiempo completa
como whitespace, que es lo que reserva el ancho real del hueco en el eje (el eje coloca por
índice, y sin eso un corte de dos horas se dibujaría igual que uno de un minuto). Por encima
de `MAX_SEGMENTS` tramos no se dibuja línea y se dice por qué, en lugar de sugerir
continuidad. Bajo cada gráfica va el recuento: huecos, muestras ausentes, minutos y rango.

Las velas y el histograma no necesitan tratamiento: sus barras no se unen entre sí.

---

La reorganización del dashboard en 8 pestañas ya estaba desplegada. Esta versión **no la
rediseña**: corrige los defectos que quedaron y que hacían que el tablero afirmara cosas que
no había medido.

---

## P0 — la ausencia de dato ya no vale cero

### Frontend (`static/app.js`)

`asNumber()` usaba `Number(value)`, y en JavaScript eso convierte en `0` varias formas
distintas de «no hay dato»:

```js
Number(null) === 0     Number('') === 0      Number('  ') === 0
Number(false) === 0    Number([]) === 0
```

El resultado era que un CVD ausente se pintaba como un cero medido y una liquidación que
nunca llegó valía «0 USD liquidados». Peor: varios filtros del tipo
`.filter(x => Number.isFinite(x.value))` **no descartaban nada**, porque `0` sí es finito.

Ahora sólo pasan números y cadenas numéricas; `null`, `undefined`, cadenas vacías o de sólo
espacios, booleanos, `NaN` e infinitos devuelven `null`. **Un cero real se sigue viendo como
cero.**

Series afectadas y corregidas: CVD spot/futuros/diferencia, acumulado diario, Open Interest,
operaciones spot grandes, velas OHLC (una vela exige las cuatro patas: antes una barra sin
`open` se dibujaba abriendo en 0), perfil de volumen, barras de flujo por sesión y
contribuciones del swing score.

Helpers nuevos: `seriesPoint()`, `seriesPoints()` (descarta los ausentes y **cuenta el
hueco**) y `nd()` para mostrar `N/D` donde antes había un cero fabricado.

### Backend (`app/scalp_logic.py`)

`compute_scalp_summary()` contenía el patrón `as_float(x) or 0.0`. Corregido:

| Componente | Antes | Ahora |
|---|---|---|
| Liquidaciones long/short 5m | `0.0` al faltar | `None`, salvo ventana medida |
| Cambio de OI 15m | `0.0` = «OI plano» | `None` si falta cualquiera de las dos lecturas |
| Distancia a VWAP | `0.0` = «precio sobre el VWAP» | `None` sin VWAP o sin precio |
| Componente OI del score | valía `0.0` y **sumaba peso 10** | queda fuera del peso medido |

**El caso de las liquidaciones es distinto al resto.** Son un feed de *eventos*: la suma
`NULL` puede significar «no hubo liquidaciones» (mercado en calma, dato legítimo) o «nadie
estaba escuchando». Lo único que distingue los dos casos es el latido del colector de
WebSockets, así que `scalp_context()` lo trae ahora en el propio contexto
(`liq_feed_status` / `liq_feed_lag_s`) y `compute_scalp_summary()` publica
`liquidations_measured`. Con el colector vivo y cero eventos se publica **cero, que es la
lectura correcta**; sin latido reciente se publica `None`. Fail-closed: sin heartbeat en el
contexto, se prefiere `N/D`.

`COLLECTOR_THRESHOLDS` pasa a ser constante compartida con `data_quality()`: si cada uno
usara su propio umbral, el panel podría decir «feed sano» mientras el resumen publica un
cero fabricado.

---

## P1 — navegación interna

`#liquidity → #liquidez`, `#context → #contexto`, `#structure → #estructura`. El fallback de
`initSectionNav()` era `'overview'`, un identificador que **dejó de existir con la
reorganización**: un hash desconocido ocultaba las ocho secciones y dejaba la página en
blanco. Ahora la constante es `FALLBACK_SECTION = 'mesa'` y, por si acaso, se degrada a la
primera sección realmente presente en el documento.

---

## P1 — dirección y setup separados

Antes había un solo selector con siete opciones. Las cuatro «esperando …» recorrían
**exactamente el mismo código**: al no tener dirección, todo caía en `PENDIENTE` y elegir una
u otra no cambiaba nada.

Ahora son dos controles independientes y `app/setups.py` da a cada setup su propia lectura:

| Setup | Dependencias obligatorias | Qué lo invalida |
|---|---|---|
| Ruptura | precio + barrera | volver dentro del rango tras cerrar fuera |
| Rechazo | precio + barrera | aceptación más allá del nivel; cierres aceptados fuera |
| Reversión | tendencia previa | que el contexto previo **no** sea contrario |
| Continuación | tendencia previa | que el contexto **no** esté alineado |

Estados publicados: `PENDIENTE`, `CANDIDATO`, `CONFIRMADO`, `FALLIDO`, `NO EVALUABLE`.

**Afirmación histórica superseded por `957b4b1`:** originalmente `build_setup_context()`
dejaba `bars_closed_beyond`, `retest_done`, `returned_inside`, `pullback_pct` y
`level_defended` en `None`. La implementación posterior añadió `setup_observables()` y los
mide con velas cerradas cuando recibe `observ_bundle`; si el paquete falta o la cobertura no
alcanza, conserva `None / NO_EVALUABLE / PENDING` sin inventar un resultado.

Compatibilidad: `split_hypothesis()` traduce los siete valores antiguos al par
(dirección, setup), tanto en el backend como en el navegador.

---

## P1 — fin del umbral universal de 5 bps

`spread > 5 bps` decidía tres cosas distintas: vetaba la lectura de scalp, generaba una
alerta `NO_TRADE` y etiquetaba la ejecución como «cara para intradía» **incluso sobre una
tesis swing de varios días**. Cinco puntos básicos se comen un cuarto de un scalp de 20 bps
y son ruido en un swing de 400: el mismo número no puede significar lo mismo en los dos.

`execution_assessment()` calcula el **coste total de ida y vuelta** —spread, comisiones ×2,
slippage ×2 y funding declarado— y lo compara con el objetivo y el riesgo de esa operación:

```
coste_total / objetivo     coste_total / riesgo
```

Manda la peor de las dos lecturas. Sin entrada, objetivo, stop, comisión o tamaño el
veredicto es **SIN EVALUAR** y se enumera lo que falta; no se inventan comisiones «típicas».

Del umbral queda un **aviso por perfil** (`EXECUTION_PROFILES`: 5 bps intradía, 25 bps
swing), documentado, publicado en la respuesta y **sin capacidad de veto**. `scalp_bias_label()`
ya no recibe el spread: sesgo y coste son dos lecturas distintas y mezclarlas ocultaba las dos.

---

## P1 — la pestaña Calidad, en tres niveles

Un panel titulado «Fuentes de datos» listaba en realidad los **procesos internos**. Son cosas
distintas y ahora van separadas:

1. **Salud de servicios** — API, ingest, WebSockets, scalp, daily, PostgreSQL.
2. **Calidad de feeds** (`/api/quality/feeds`) — por cada feed de mercado: exchange,
   mercado, símbolo, tipo de dato, estado, último timestamp, latencia, cobertura, muestras
   observadas/esperadas, hueco interno mayor, fuentes ausentes y último error.
3. **Calidad por métrica** — delta spot/futuros 5m, CVD 1h, basis, OI, funding y libro.

Reglas que sostienen la tabla:

- La **cobertura sólo se calcula donde hay cadencia esperada**. Los feeds de eventos no la
  tienen y la declaran `null`, no `0 %`.
- Un feed de eventos sin eventos **no está caído**: su estado sale del latido del colector.
- `orderbook_depth` guarda sólo el estado actual (se sobrescribe), así que contar filas ahí
  no mide cobertura: se declara `null`.
- Las **fuentes ausentes** sólo se calculan donde la tabla distingue `exchange`.

---

## P1 — el perfil cambia la jerarquía visual

| | Intradía ≤ 4 h | Swing varios días |
|---|---|---|
| Contexto | 4h, 1h | 3d, 1d, 8h |
| Confirmación | 18m, 15m, 5m | 4h, 1h |
| Entrada | — | 18m, 15m, 5m |
| Gatillo / ejecución | 1m, 30s | 1m, 30s (**peso 0**) |

`5m` estaba a la vez en la capa de entrada de swing y en `reference_only`: se describía como
entrada y como referencia secundaria, dos cosas incompatibles. `reference_only` de swing
queda vacío y 30s/1m pasan a una capa de **ejecución con peso 0**: se ven donde corresponde,
pero no pueden mover el sesgo de una tesis de varios días.

La detección de contradicciones se generalizó: antes sólo comparaba la segunda capa y la
última contra el contexto, así que con cuatro capas la de **entrada** se quedaba sin
comprobar. El efecto depende de qué capa discrepe: confirmación invalida, ejecución invalida
sólo si el perfil lo permite, y las capas intermedias aconsejan esperar.

En la interfaz, cada fila de las tablas de estructura y flujo lleva `data-layer` con su capa;
el CSS destaca contexto y confirmación y atenúa ejecución. **El dato bruto no cambia.** El
perfil también viaja a `/api/scalp/execution-cost`, que antes recibía siempre el horizonte
por defecto.

---

## P1 — presentación del flujo

`spot_delta − futures_delta` no es una dirección: medido sobre 90 sesiones × 3 símbolos, su
signo es el del CVD de futuros **invertido en el 93-94 %** de los casos, porque el perp mueve
unas 10× el spot.

La matriz de delta pasa a encabezarse con cada pata, su **delta/volumen** (única forma de
comparar las dos sin que la escala del perp aplaste al spot) y el **cuadrante**:

```
Spot compra / futuros compran      Spot compra / futuros venden
Spot vende  / futuros venden       Spot vende  / futuros compran
```

La diferencia monetaria queda como columna de auditoría: oculta tras un interruptor, sin
color de signo y con la advertencia de que compara mercados de escala distinta.

El panel de absorción publica ahora la evidencia completa: `delta_ratio`, umbral mínimo,
**fuente del umbral** (p75 medido o constante de respaldo), banda del baseline, tamaño de
muestra, movimiento de precio, temporalidad y cobertura declarada de la ventana.

---

## P2 — etiquetas

| Antes | Ahora | Por qué |
|---|---|---|
| Probabilidad de ruptura | Frecuencia histórica de ruptura | Es un conteo, no un modelo calibrado |
| Actividad institucional | Operaciones spot de gran tamaño | El tamaño no identifica al participante |
| Lectura probabilística | Lectura contextual | No hay validación fuera de muestra |

---

## P2 — snapshot coherente para la Mesa

La Mesa pedía `/api/trend-matrix`, `/api/profile`, `/api/hypothesis` y
`/api/dashboard/state` por separado, y cada uno recalculaba `trend_matrix`, `delta_matrix` y
`scalp_context` con su propio `now()`: dos paneles contiguos podían estar describiendo
instantes distintos y contradecirse sin que se viera por qué.

`/api/desk/state` calcula los componentes compartidos **una sola vez** y los publica con el
mismo `as_of`, más `source_timestamps` (frescura por fuente) y `partial` (lo que no se pudo
medir). Los endpoints originales siguen existiendo: otras vistas los usan.

---

## P2 — barra superior

Declaraba cuatro columnas para seis hijos; los dos últimos caían en columnas implícitas y al
añadir el selector de setup se solapaban. Ahora usa `grid-template-areas` con una
distribución declarada en cada punto de ruptura: 1920, 1440, 1366, 1100, 900, 700 y 430 px.

---

## Lo que NO entra en esta versión

- **El recuperador general de huecos** (`data_gaps`, CLI, `/api/data-quality/gaps*`) sigue
  sin implementarse, por decisión explícita. No se ha simulado ni esbozado.
- Las bandas de coste/objetivo y los pesos por capa son **convenciones declaradas**, no
  resultados backtesteados. Viajan en la respuesta precisamente para que se puedan discutir.
- No se ha validado contra PostgreSQL de producción con feeds vivos: las pruebas corren
  contra el árbol de staging.
