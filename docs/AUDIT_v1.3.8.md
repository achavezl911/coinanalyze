# Auditoría v1.3.8 — semántica de flujo, componentes muertos y cobertura declarada

Todo lo que sigue se verificó contra la base viva del LXC 140 (`150.1.7.13`) el 2026-08-04
antes y después de tocar el código. Donde hay incertidumbre, se dice.

---

## Resumen

Cuatro defectos con impacto directo en decisiones de trading, más un grupo de correcciones
de "cero silencioso". El hilo común: **el sistema presentaba como medición lo que era
ausencia de dato, y como dirección lo que era un artefacto de escala.**

| # | Severidad | Defecto | Estado |
|---|---|---|---|
| 1 | **P0** | El diferencial spot−futuros se usaba como voto direccional en `trend_matrix` y como confirmación en `passive_flow` | Corregido |
| 2 | **P1** | El componente "absorción CVD" del score de barreras valía siempre 0 | Corregido |
| 3 | **P1** | `long_share_pct` publicaba "100% long" con 4 de 7 componentes mudos | Corregido |
| 4 | **P1** | Pivotes 4h calculados sobre 6.7% de la historia que el código pide, sin declararlo | Declarado; falta backfill |
| 5 | **P2** | Momentum/movimiento de precio ausente se publicaba como `0.0` | Corregido |
| 6 | **P2** | Doble conteo en `_classify_passive` (`diff<0` es colineal con `fut_delta>0`) | Corregido |

---

## 1. P0 — El diferencial spot−futuros votaba dirección

### Descripción

`trend_matrix` calculaba `cvd_flow = spot_delta − fut_delta` por marco intradía y lo usaba
como uno de los tres votos (junto a estructura y momentum) que deciden el sesgo de cada
timeframe. `passive_flow` exigía `diff > 0` / `diff < 0` para confirmar reacumulación o
redistribución. Ese sesgo escalaba hasta `swing_score` → `daily_verdict` → portada y alertas.

### Causa raíz

Las dos patas no son comparables en magnitud. `cvd_fut` sale del perp de Binance, que mueve
~10× el spot de Binance+Bybit. Por construcción, `sign(spot − fut) ≈ −sign(fut)`.

El proyecto **ya había diagnosticado esto** en v1.3.3/v1.3.4 y lo corrigió en la capa diaria
(`flowQuadrant`, panel "Flujo por sesión"), pero `trend_matrix` y `passive_flow` quedaron con
la semántica vieja.

### Evidencia medida (no estimada)

Sobre las últimas 90 sesiones × 3 símbolos en `daily_session_agg`:

| símbolo | `sign(diff) == −sign(fut)` | coincide con spot | ambas patas igual signo y diff al revés |
|---|---|---|---|
| BTC | 94.4% | 31.1% | 62 / 90 (69%) |
| ETH | 93.3% | 27.8% | 65 / 90 (72%) |
| SOL | 94.4% | 37.8% | 56 / 90 (62%) |

Y en vivo, BTC 2026-08-04 21:43 UTC:

```
15m  spot=+10 047      fut=+8 152 135     diff=−8 142 089   -> voto BAJISTA
4h   spot=+10 448 052  fut=+43 472 236    diff=−33 024 184  -> voto BAJISTA
8h   spot=+37 299 491  fut=+79 446 121    diff=−42 146 630  -> voto BAJISTA
```

**En los tres marcos ambas patas estaban comprando y el sistema votaba bajista.**

### Corrección

Nueva función pura `flow_confirmation(spot_delta, fut_delta)` que clasifica por el **signo de
ambas patas**:

- ambas > 0 → voto +1 (`spot_y_futuros_compran`)
- ambas < 0 → voto −1 (`spot_y_futuros_venden`)
- signos opuestos → voto **0** y `agreement: false` (el desacuerdo es información, no dirección)
- cualquiera ausente → voto `None`, `sin_datos` (nunca 0)

`trend_matrix` publica ahora `spot_delta_usd`, `fut_delta_usd`, `flow_state`, `legs_agree`,
`votes_up`/`votes_down`. `cvd_diff` se conserva como dato descriptivo pero **no vota**.

### Resultado tras el cambio (mismo símbolo, datos vivos)

```
4h   flow=spot_y_futuros_compran   spot=+8 781 292   fut=+39 381 909  -> alcista
8h   flow=spot_y_futuros_compran   spot=+33 499 749  fut=+111 348 532 -> alcista
SOL 4h flow=spot_vende_futuros_compra -> conflicto, voto 0 (antes: voto bajista espurio)
```

### Riesgo de regresión

El sesgo por marco cambia para escenarios donde las patas discrepan: antes salía dirección,
ahora sale conflicto (voto 0). Eso **reduce** el número de sesgos direccionales emitidos, que
es el comportamiento correcto. `medium_term_alignment` (4h/8h/1d) puede pasar a "mixto" más a
menudo, lo que degrada `swing_score` vía el componente de alineación — intencional.

---

## 2. P1 — El componente "absorción CVD" del score de barreras estaba muerto

### Descripción

`price_barrier_read` anuncia en su propio `method.score_components`:
`"toques 35 + reaccion ATR 25 + volumen relativo 20 + absorcion CVD 10 + recencia 10"`.
El término de absorción valía **exactamente 0 para toda zona, siempre**.

### Causa raíz

Dos caminos, ambos ciegos:

1. `price_barriers` construye las barras diarias desde `ohlcv` interval=`daily` y les asigna
   `"cvd_spot_usd": None` (no hay CVD en esa tabla). `number(None)` → `nan`, y
   `nan > 0` es `False`, igual que `nan < 0`. La absorción quedaba `False`, no "desconocida".
2. El camino 4h pasaba `cvd_key=None` → `math.nan` → mismo resultado.

El fallback a `daily_session_agg` (que sí tiene `cvd_spot_usd`) solo se activa con
`len(daily_rows) < 120`, y hay 730 velas diarias, así que **nunca se activaba**.

### Verificación aritmética

Resistencia de BTC en vivo: score `77.7`. Descomponiendo:

```
toques:            min(9/4, 1) * 35     = 35.00
reacción ATR:      min(2.47/2, 1) * 25  = 25.00
volumen relativo:  min((1.08-0.5)/1.5,1)*20 =  7.73
absorción CVD:     0.0 * 10             =  0.00   <-- muerto
recencia:          ~1.0 * 10            = 10.00
                                          ------
                                           77.73  == 77.7 observado
```

El componente no solo no aportaba: al sumar 0 en vez de excluirse, **hundía el score ~10
puntos** y desplazaba la etiqueta `fuerte`/`media`/`débil` hacia abajo sin señal alguna.

### Corrección

Dos partes:

1. **CVD real donde el reloj coincide.** Se adjunta CVD spot por bucket de 4h desde
   `spot_trades_agg`, que se agrupa con el mismo `date_bin` desde epoch que las velas.
   Las velas **diarias** siguen sin CVD a propósito: `daily_session_agg` va en sesión NYSE
   (D−1 09:30 ET → D 09:30 ET), desalineada ~14.5 h del día UTC de `ohlcv`; adjuntarlo sería
   fabricar una alineación que no existe.
2. **Renormalización.** El score se reparte sobre los componentes **medibles** de cada zona:
   `score = Σ(valor·peso)/Σ(peso disponible) · 100`. Cada zona publica `scored_components`,
   `unavailable_components`, `absorption_rate` y `score_weight_pct`.

Esto además arregla un caso silencioso preexistente: `volume_multiple = None` también
descontaba 20 puntos sin avisar.

### Resultado tras el cambio (datos vivos)

```
BTC resistencia:  77.7 -> 86.6   absorption_rate=1.00   weight=100%
BTC soporte:      70.2 -> 73.6   absorption_rate=0.67   weight=100%
SOL resistencia:          89.1   absorption_rate=0.75   weight=100%
```

### Riesgo de regresión

Los scores suben de forma generalizada (ya no se pierden puntos por componentes ausentes), así
que **los umbrales 70/50 de `fuerte`/`media` quedan menos exigentes en términos absolutos**.
Los valores viejos y nuevos no son comparables entre sí. No están calibrados contra resultado
realizado, ni antes ni ahora.

---

## 3. P1 — "100% long" con la mitad de la evidencia muda

### Descripción

`compute_swing_score` calculaba `long_share_pct = lp / (lp + sp)`, es decir, la cuota sobre la
evidencia **que resultó no nula**. El panel la pinta como un medidor circular y como texto
`"X% long · Y% short"`.

En vivo, BTC: `score 45`, `conviction media`, y **`long_share_pct: 100.0`** — con 4 de 7
componentes en cero (55 de 100 puntos de peso sin señal). El medidor salía lleno.
SOL simétricamente: `long_share_pct: 0.0` con 35 puntos de peso mudos.

### Causa raíz

La fórmula normaliza sobre `lp+sp`, que colapsa a un solo componente activo cuando el resto
vale 0. Y un componente valía 0 tanto por "medido y neutral" como por "las dos sub-señales se
contradicen" como por "no hay dato" — tres estados indistinguibles.

### Corrección

- Las cuotas se reparten sobre el **peso total (100)**: `long_share_pct`, `short_share_pct` y
  el nuevo `neutral_share_pct` suman 100, así que la parte sin señal es visible.
- Cada componente lleva `status`: `signal` | `neutral` | `conflict` | `partial` | `unavailable`.
- Nuevo `evidence_coverage_pct` = % del peso que sí pudo medirse. Por debajo de 50 la
  convicción se degrada a `baja` automáticamente.
- Nuevo `conflicts`: lista de componentes cuyas sub-señales se contradicen.
- Si **ningún** componente pudo medirse, el sesgo es `SIN_DATOS`, no `NEUTRAL`.

Casos concretos que ahora se distinguen:

- **Estructura 1d/3d con HH_HL y LH_LL**: antes `(+1 + −1)/2 = 0` → idéntico a "sin dato".
  Ahora `status: conflict` y aparece en `conflicts`.
- **Fuerza relativa vs BTC en el propio BTC**: `cross_asset` devuelve `null` en todas las
  ventanas porque el activo base *es* BTC. Antes contaba como neutral medido; ahora
  `unavailable`, y la cobertura de BTC es 95%, no 100%.

### Resultado tras el cambio (datos vivos)

```
BTC  LONG  score=45.0  long=45.0  short=0.0  neutral=55.0  coverage=95%  conflicts=['Estructura 1d/3d']
SOL  SHORT score=-52.5 long=0.0   short=52.5 neutral=47.5  coverage=100% conflicts=['Alineacion 4h/8h/1d']
```

### Riesgo de regresión

`daily_verdict.long_share_pct` cambia de significado. Solo hay 9 filas históricas, todas de
2026-08-02 en adelante. `swing_bias` puede ahora valer `SIN_DATOS` y `conviction` `sin datos`,
valores que la tabla no admite: `persist_verdicts` los escribe como `NULL`, que es lo que la
columna ya usaba para "no hubo veredicto".

---

## 4. P1 — Pivotes 4h sobre el 6.7% de la historia pedida

### Descripción

`price_barriers` pide 720 barras de 4h (120 días) desde `ohlcv` interval=`5min`. La tabla tiene
**7.8 días** (2 255 filas/símbolo desde 2026-07-27), así que devuelve **48 barras**.

### Causa raíz

`HTF_DATA_RETENTION_DAYS=400` está configurado y la retención respeta el 5min, pero el 5min
solo se construye **hacia adelante**: `rollup_ohlcv_5m` agrega los últimos 40 minutos en cada
ciclo de ingest. Existe `scripts/backfill_ohlcv_5m.py` (default 180 días) y **nunca se corrió
en producción**. El guardarraíl `if len(bars_4h) < 20` no salta porque 48 > 20.

### Corrección aplicada

El endpoint **declara la cobertura** en vez de aparentar 120 días:
`intraday_bars`, `intraday_target_bars`, `intraday_coverage_pct`, `intraday_coverage_status`
(`complete` ≥90% / `partial` ≥25% / `insufficient`), `intraday_source_interval`, y un
`warnings[]` explícito. Hoy sale:

```
bars=48/720  cov=6.7%  status=insufficient
warnings=['Pivotes 4h calculados sobre 48 barras de 720 objetivo (6.7%): las zonas
           intradia solo reflejan ese tramo reciente, no 120 dias.']
```

### El backfill se corrió — y demostró que el objetivo es inalcanzable

Se ejecutó `backfill_ohlcv_5m --days 180` en producción. Resultado: **la cobertura siguió en
7.8 días**. Las 6 780 filas del resumen eran re-upserts de lo ya presente; todos los chunks
anteriores a ~8 días devolvieron 0.

Probando la API directamente (BTC, ventana de 3 días, esperado ~864 velas):

| petición | velas devueltas |
|---|---|
| 5min hace 5 días | 864 (completo) |
| 5min hace 10 días | 245 (parcial) |
| 5min hace 20 días | **0** |
| 5min hace 60 días | **0** |
| 1min hace 20 días | **0** |

**Coinalyze solo sirve ~8-9 días de `ohlcv-history` a 5min.**

### CORRECCIÓN (v1.3.9): la conclusión anterior era errónea — se probó el intervalo equivocado

La primera versión de este informe concluyó que los 120 días de pivotes 4h "solo pueden ganarse
con uptime". **Falso.** El límite es del intervalo `5min`, no de la API. Midiendo otros
intervalos (BTC, ventana de 5 días, esperado 30 velas):

| intervalo | 30d | 120d | 200d | 300d | 365d |
|---|---|---|---|---|---|
| `15min` | 0 | 0 | — | — | — |
| `5min` | 0 | 0 | 0 | 0 | 0 |
| `1hour` | ✅ 120/120 | 0 | — | — | — |
| **`4hour`** | ✅ | ✅ | ✅ | ✅ | 0 |

Una petición única de 120 días a `4hour` devuelve **exactamente 720 velas**, el objetivo literal
de `BARRIER_INTRADAY_TARGET_BARS`. Y las velas incluyen `bv`/`btx`, así que conservan el reparto
comprador/vendedor: el delta sigue siendo real, no estimado.

**Solución aplicada en v1.3.9:**

- `sql/schema.sql`: `interval` acepta `'4hour'`.
- `app/ingest.py`: `upsert_ohlcv` admite `4hour`, y la tolerancia de timestamp **escala con el
  intervalo**. Antes era fija en 300 s, así que el primer bucket de 4 h de cada petición caía
  fuera de rango y se descartaba en silencio.
- `app/scalp_logic.py`: `price_barriers` prefiere velas 4h nativas; 5min y 1min quedan como
  fallback por profundidad decreciente.
- `app/daily_agg.py`: refresco horario de los últimos 7 días de 4h (el borde se reescribe
  mientras el bucket en curso cierra) y regla de retención propia.
- `scripts/backfill_ohlcv_4h.py`: backfill idempotente, tope en 300 días (el horizonte medido).

**Resultado medido tras el backfill de 300 días** (1 796 barras 4h por símbolo desde 2025-10-08):

```
BTC  fuente=4hour  barras=720/720  cov=100%  status=complete  warnings=[]
     soporte    score=75.1  toques=19  absorcion=0.50  peso=100%
     resistencia score=86.7 toques=14  absorcion=1.00  peso=100%
SOL  fuente=4hour  barras=720/720  cov=100%  status=complete  warnings=[]
```

Los toques por zona pasaron de 7-9 a 12-19: con 120 días de 4h reales aparecen pivotes que con
8 días no existían. El heartbeat del job diario confirma el refresco continuo
(`h4_candles=126` = 42 barras × 3 símbolos por ciclo).

El aviso de cobertura que se añadió en v1.3.8 sigue en el código y es el que garantiza que, si
la fuente 4h volviera a degradarse, el panel lo diga en vez de aparentar 120 días.

---

## 5-6. P2 — Ceros silenciosos y doble conteo

**Momentum/movimiento ausente publicado como `0.0`.** `trend_matrix` y `passive_flow` hacían
`mom = ... if (px_now and px_ago) else 0.0`. Un 0.0 inventado no solo se publicaba como
medición real: en `_classify_passive` hacía que la rama "el precio aguantó" se cumpliera y
disparara absorción falsa. Ahora es `None` y no vota.

**Doble conteo en la confirmación de absorción.** `_classify_passive` exigía
`absorbed == "compras"` (que implica `fut_delta > 0`) **y** `diff < 0` — pero `diff < 0` es casi
automático cuando los futuros compran, por la misma asimetría de escala del punto 1. Eran la
misma observación contada dos veces. Ahora la confirmación es el signo del **CVD spot**, que es
la única pata independiente del flujo agresivo que se está absorbiendo.

---

## Pruebas

`tests/test_flow_semantics.py`, 15 casos nuevos. Cada uno fija una conclusión medida contra la
base viva antes de tocar el código:

- 5 sobre `flow_confirmation` (ambas patas compran/venden, conflicto, patas ausentes, y un test
  de código fuente que impide reintroducir el voto por diferencial)
- 2 sobre `_classify_passive` (confirmación por spot, sin spot → neutral)
- 5 sobre `compute_swing_score` (un componente activo no es unanimidad, sin evidencia →
  `SIN_DATOS`, cobertura baja degrada convicción, conflicto marcado, componente sin dato →
  `unavailable`)
- 3 sobre barreras (renormalización sin CVD, CVD presente sí puntúa, cobertura intradía
  declarada y advertida)

**Resultado: 147 pasan** (132 preexistentes + 15 nuevos), `ruff check app/ tests/ scripts/`
limpio. Ejecutado en el propio LXC 140 con un venv desechable (`/tmp/testvenv`) para no tocar
`/opt/coinalyze/.venv`.

Además, verificación contra la **base de producción en modo lectura** desde el árbol nuevo
antes de desplegar: los cuatro algoritmos corridos sobre BTC y SOL reales, con las salidas
citadas arriba.

---

## Límites que esta auditoría NO resuelve

- **Los pesos siguen sin calibrar.** 25/15/20/10/15/10/5 en `swing_score` y 35/25/20/10/10 en
  barreras son elegidos a mano. `daily_verdict` existe para hacerlos evaluables pero solo tiene
  9 filas. Sin backtest, `score` es un balance de evidencia, no una probabilidad — y así lo dice.
- **La capa scalp sigue sin ser backtesteable** (72 h de retención).
- **`inst_delta_usd` (whale) sigue vacío**: 2/392 sesiones en BTC, 5 en ETH, 32 en SOL. Ya
  estaba retirado del panel; sigue en la tabla.
- **`cvd_diff_2v_usd` solo tiene 2 sesiones** (se puebla hacia adelante desde 2026-08-03).
- **`volume_usd`/`price_high`/`price_low` en `daily_session_agg` solo tienen 4 sesiones**; por
  eso las barreras diarias usan `ohlcv` y no esa tabla.
- Siguen los límites duros de feeds: 2 venues, trades agregados a 1 min, libro L1/L5/L10, sin
  opciones/on-chain/ETF/macro.
