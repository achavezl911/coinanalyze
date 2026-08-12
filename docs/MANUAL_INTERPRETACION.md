# Manual de interpretación — Coinalyze Derivatives Dashboard

**Versión:** v1.2.1 — versión final validada con modo scalping persistente, UI cableada, confidence layer, basis, niveles de liquidación, calibración corregida y métricas Prometheus.

Guía económica de cada dato del dashboard y cómo leerlos en conjunto para anticipar
movimientos. Nivel: operador de perpetuos con marco de microestructura. Asume
conocimiento de CVD, funding, OI y order flow.

**Advertencia de uso:** todo lo aquí descrito es lectura de microestructura, no
señal mecánica de entrada. El dashboard mide presión y posicionamiento, no predice
precio. Las combinaciones sugeridas son sesgos probabilísticos, no garantías. La
gestión de riesgo (tamaño, stop, invalidación) es responsabilidad del operador y no
la cubre esta herramienta.

> **Corrección v1.3.5:** este manual conserva secciones históricas de v1.2.1. El
> diferencial spot−futuros **no demuestra acumulación ni distribución**: las patas tienen
> distinta escala y el histórico de futuros es Binance frente a spot Binance+Bybit. Usa
> `cvd_spot_usd` para leer flujo de fondo y el panel **CVD 90 sesiones** para operaciones
> de dos sesiones. `whale` casi siempre está vacío y no entra ya en los setups diarios.
> Esta corrección prevalece sobre cualquier descripción antigua del Diff que aparezca abajo.

---

## Parte I — El marco mental

El dashboard responde una pregunta central: **¿quién está empujando el precio y con
qué convicción?** Separa el flujo en dos mundos y los contrasta:

- **Spot**: dinero "real" que compra/vende el activo. Tiende a reflejar convicción
  de mediano plazo (acumulación/distribución de manos fuertes).
- **Futuros/perpetuos**: dinero apalancado, especulativo, que puede mover precio sin
  respaldo de spot. Tiende a reflejar posicionamiento de corto plazo y sentimiento.

La tesis operativa: **cuando spot y futuros divergen, el spot suele tener razón en el
mediano plazo.** Si los futuros empujan el precio arriba pero el spot vende (CVD
diferencial negativo), ese rally es frágil — lo sostiene apalancamiento, no demanda
real. Eso precede reversiones. El dashboard existe para ver esa divergencia antes de
que se resuelva en precio.

---

## Parte II — Cada indicador, individualmente

### 1. CVD de futuros (cvd_session / cvd_nyse_session)

**Qué mide:** el volumen neto direccional de los perpetuos, en USD. Suma de
(compras a mercado − ventas a mercado). Subiendo = los agresores compran; bajando =
los agresores venden.

**Cómo leerlo:** la pendiente importa más que el nivel absoluto. CVD de futuros
subiendo con precio subiendo = tendencia alcista con respaldo de flujo apalancado.
CVD subiendo pero precio plano = compras absorbidas (alguien vende pasivo contra esas
compras; señal de techo potencial).

**Nota de nomenclatura:** en el sistema, `cvd_session` es el CVD de futuros de 24h y
`cvd_nyse_session` el de la sesión NYSE en curso. (Los nombres no coinciden con su
contenido por herencia; el de "sesión" es el de 24h.)

### 2. CVD de spot (cvd_spot_24h / cvd_spot_session)

**Qué mide:** lo mismo pero para el mercado spot (Binance + Bybit combinados, en
USD). Es el flujo de dinero "real".

**Cómo leerlo:** es tu lectura de convicción de fondo. Spot CVD subiendo
sostenidamente = acumulación real. Bajando = distribución real. Más lento y más
significativo que el de futuros.

### 3. CVD diferencial (cvd_diff_24h / cvd_diff_ses) — comparación de magnitud

**Qué mide:** `CVD_spot − CVD_futuros`, en USD. Spot cubre Binance+Bybit y el
histórico de futuros cubre Binance; además el perpetuo mueve aproximadamente diez veces
más volumen.

**Cómo leerlo:** muestra qué pata domina la magnitud, pero su signo suele ser el inverso
del CVD de futuros y **no identifica por sí solo acumulación o distribución spot**. Lee
primero el signo y percentil de `cvd_spot_usd`. Usa el Diff solo para describir
discrepancia relativa y declara siempre sus venues.

### 4. Whale delta / intensidad institucional (whale_intensity, whale_label)

**Qué mide:** el desbalance de los trades grandes (institucionales) en spot. Umbral
por activo: BTC ≥5M USD/trade, ETH ≥1M, SOL ≥200k. Intensidad ∈ [-1, +1].

**Cómo leerlo:**
- "Acumulación agresiva" (intensidad > +0.6): las ballenas compran con fuerte
  desbalance. Señal alcista de convicción.
- "Distribución agresiva" (< -0.6): las ballenas venden agresivo. Señal bajista de
  convicción.
- "Acumulando/Distribuyendo" (±0.3-0.6): sesgo moderado.
- "Neutro" o "Sin actividad relevante": las ballenas no están activas o están
  balanceadas. Ausencia de señal (no es alcista ni bajista; es ruido).

**Clave:** con los umbrales actuales casi ningún trade cruza el filtro; la serie diaria
está vacía en la práctica. Trátalo como no disponible y no como cero ni como confirmación.

### 5. Funding rate (fr_avg) y divergencia PFR-FR (pfr_fr_div)

**Qué mide el funding:** el costo de mantener posiciones perpetuas. Positivo = longs
pagan a shorts (mayoría apalancada está larga). Negativo = shorts pagan a longs.

**Cómo leerlo:**
- Funding **muy positivo y sostenido**: exceso de longs apalancados. Combustible para
  liquidaciones en cascada si el precio cae (presión bajista latente). Por eso en el
  regime score el funding entra con signo invertido.
- Funding **negativo**: exceso de shorts. Potencial para short squeeze al alza.
- Funding **cerca de cero**: posicionamiento equilibrado, mercado sano.

**La divergencia PFR-FR:** `funding_predicho − funding_vigente`. Si el predicho se
opone al vigente, anticipa un cambio de presión de posiciones. Es una señal de
adelanto: el mercado de funding "ve" un cambio antes de que se materialice.

### 6. Open Interest (oi, oi_chg_24h_pct, oi_vol_24h_ratio)

**Qué mide:** el valor total de contratos abiertos (USD). Cuánto dinero apalancado
está en juego.

**Cómo leerlo — siempre en combinación con precio:**
- **OI subiendo + precio subiendo**: nuevo dinero entrando largo. Tendencia alcista
  con convicción (pero cuidado si el funding se dispara → sobrecalentamiento).
- **OI subiendo + precio bajando**: nuevo dinero entrando corto. Tendencia bajista con
  convicción.
- **OI bajando + precio subiendo**: shorts cerrando (short squeeze / cobertura). Rally
  de baja calidad, no es demanda nueva.
- **OI bajando + precio bajando**: longs cerrando (long capitulation). Caída por
  desapalancamiento.

`oi_vol_24h_ratio` (OI/volumen): OI alto relativo al volumen = mercado cargado de
posiciones poco rotadas, más frágil a movimientos bruscos.

### 7. Liquidaciones (long_liq_24h, short_liq_24h, liq_ratio_24h)

**Qué mide:** USD liquidados forzosamente en 24h, por lado. `liq_ratio = long/short`.

**Cómo leerlo:**
- ratio < 1 (más shorts liquidados): presión alcista (squeezes de shorts). Favorece
  continuación al alza.
- ratio > 1 (más longs liquidados): presión bajista (cascadas de longs).
- Picos de liquidaciones marcan a menudo extremos locales (clímax de capitulación o
  euforia).

### 8. Buy-trade ratio (btr_15m, btr_1h, btr_24h)

**Qué mide:** fracción de trades de futuros que fueron compra a mercado
(`btx/tx`). Mide **participación**, no volumen. Responde "¿cuánta gente compra?" en
lugar de "¿cuánto se compra?".

**Cómo leerlo:** ortogonal al CVD. btr alto (>0.5) con CVD plano = muchos
compradores pequeños sin mover volumen neto (posible acumulación minorista o
distribución hacia retail). Útil para detectar divergencias entre participación y
volumen. Las tres ventanas (15m/1h/24h) son rolling y anidadas: su orden aporta contexto
de persistencia relativa, pero no mide una aceleración formal ni constituye confirmaciones
independientes.

### 9. Regime score y label (regime_score, regime_label)

**Qué mide:** un sintetizador [-100, +100] que combina la media de los imbalances CVD
spot/futuros de 24h (peso 25), whale (30), OI (15), funding (15, invertido) y
liquidaciones (15). Cada imbalance es `net/gross` dentro del mismo mercado y ventana;
si falta una pata gross/neteada, el componente CVD no vota. Los pesos no fueron
recalibrados.

**Cómo leerlo:** es un **filtro de contexto**, no una señal de entrada. Te dice en qué
"régimen" está el mercado para que ajustes tu sesgo:
- "Continuación alcista orgánica": score alto + ballenas acumulando + componente CVD
  normalizado positivo.
  El alza tiene respaldo real. Favorece longs en pullbacks.
- "Euforia / Sobreextensión bullish": score alto PERO con distribución. El alza está
  sobreextendida y las manos fuertes venden. Precaución con longs; vigilar reversión.
- "Squeeze inminente bullish": score positivo, componente CVD normalizado no positivo,
  sin acumulación.
  Posible squeeze técnico (no por demanda real).
- "Distribución (Bearish)" / "Capitulación (Bearish)": manos fuertes saliendo.
  Favorece shorts o cash.
- "Absorción de compras (Bearish)": el diff es positivo pero el score es negativo —
  las compras se están absorbiendo (alguien vende contra ellas). Techo potencial.
- "Compresión / Acumulación silenciosa": score bajo en magnitud pero ballenas
  acumulando. Acumulación discreta antes de un posible movimiento.
- "Lateral / Indecisión": sin señal dominante.

**Advertencia explícita:** los pesos del score son heurísticos y NO están calibrados
con backtest. Úsalo para enmarcar, no para gatillar. El parámetro de escala del CVD
diferencial (10% del volumen 24h = señal máxima) está fijado a ojo.

### 10. Histórico diario y CVD spot acumulado

**Qué mide:** una fila por día (corte 09:30 ET), con CVD spot/fut/diff, CVD spot
acumulado, racha spot, % de precio, ΔOI y funding de cada sesión. La mini-gráfica muestra
el CVD spot acumulado.

**Cómo leerlo — esta es tu lectura de mediano plazo, la que el resto del dashboard no
da:**
- **La pendiente del CVD spot acumulado** es la señal más limpia de
  distribución/acumulación sostenida. Inclinándose hacia abajo varias semanas =
  distribución persistente, aunque el precio aguante. Hacia arriba = acumulación
  persistente.
- **La racha** (días consecutivos del mismo signo de CVD spot): una racha de -5, -7, -10
  días de distribución es una señal de convicción que un día aislado no da. Cuanto
  más larga la racha y más clara la pendiente spot, más fuerte la lectura.
- **La columna Precio % cruzada con CVD spot**: si ves varios días de precio subiendo
  (Precio % positivo) pero spot vendedor, es distribución encubierta de mediano plazo
  — el setup más valioso para anticipar una caída fuerte.
- **ΔOI por sesión**: distingue distribución con OI subiendo (se abren shorts,
  bajista activo) de distribución con OI bajando (longs cerrando, desapalancamiento).

---

## Parte III — Cómo se relacionan (mapa de dependencias)

Ningún indicador se lee solo. Las relaciones clave:

- **CVD spot ↔ Whale**: ambas métricas describen agresión spot desde ángulos distintos.
  No atribuyas identidad al flujo ni uses el Diff de escalas desiguales como dirección.
- **OI ↔ Precio ↔ Funding**: el trío del apalancamiento. OI sube + precio sube +
  funding se dispara = alza sobrecalentada (frágil). OI sube + precio baja + funding
  negativo = bajada con convicción de shorts.
- **Funding ↔ Liquidaciones**: funding extremo predice qué lado se liquidará. Funding
  muy positivo → longs vulnerables → vigilar cascada de long_liq.
- **btr ↔ CVD**: participación vs volumen. Divergencia entre ambos revela quién
  participa (retail vs ballenas).
- **CVD spot acumulado ↔ CVD spot actual**: el histórico da contexto de mediano plazo;
  el snapshot, el estado ahora. El Diff raw queda como descripción de magnitud, no como
  voto direccional.

---

## Parte IV — Lecturas combinadas (setups)

Combinaciones concretas que sugieren un sesgo direccional. **Sesgos probabilísticos,
no señales mecánicas.** Cada uno requiere confirmación de precio y gestión de riesgo
propia.

### Setup A — Distribución encubierta (sesgo SHORT de mediano plazo)

**Señales alineadas:**
- CVD spot vendedor.
- Precio lateral o subiendo (el % de precio en el histórico es positivo).
- Racha de CVD spot vendedor en el histórico diario (≥3 sesiones).
- CVD spot acumulado con pendiente bajista sostenida.
- Bonus: OI subiendo (shorts institucionales abriendo) + funding aún positivo (longs
  atrapados).

**Lectura:** las manos fuertes salen mientras el precio aguanta por apalancamiento. Es
el setup de mayor valor del dashboard porque anticipa caídas antes de que ocurran.
**Régimen esperado:** "Euforia / Sobreextensión bullish" o "Distribución (Bearish)".

**Invalidación:** el CVD spot gira comprador o la racha se rompe. Si el precio rompe al
alza con CVD spot comprador y OI+volumen reales, la
tesis de distribución falla.

### Setup B — Acumulación silenciosa (sesgo LONG de mediano plazo)

**Señales alineadas:**
- CVD spot comprador.
- Precio lateral o cayendo levemente (acumulación en debilidad).
- Racha de CVD spot comprador + acumulado spot con pendiente alcista.
- Funding neutro o negativo (sin exceso de longs; espacio para subir).
- OI estable o bajando con precio sostenido (manos débiles salieron, fuertes entraron).

**Lectura:** dinero real acumula discretamente mientras el precio no refleja aún la
demanda. **Régimen esperado:** "Compresión / Acumulación silenciosa".

**Invalidación:** CVD spot gira vendedor o ruptura bajista con
CVD spot vendiendo.

### Setup C — Squeeze de shorts inminente (sesgo LONG de corto plazo)

**Señales alineadas:**
- Funding negativo y profundizando (exceso de shorts).
- liq_ratio < 1 (ya se están liquidando shorts).
- OI alto (mucho corto cargado) + precio rebotando.
- btr comprador en ventanas anidadas (persistencia relativa, no aceleración formal).
- Regime "Squeeze inminente bullish".

**Lectura:** demasiados shorts apalancados; un movimiento al alza los liquida en
cascada, acelerando la subida. Corto plazo, técnico (no por demanda real de fondo).

**Invalidación:** funding gira positivo (shorts ya cerraron), o el precio pierde
soporte y los shorts ganan convicción.

### Setup D — Euforia / techo de corto plazo (sesgo SHORT / reducir longs)

**Señales alineadas:**
- Funding muy positivo y sostenido (longs sobreextendidos).
- OI subiendo + precio subiendo parabólico.
- CVD futuros disparado pero CVD spot plano o cayendo (diff negativo).
- liq_ratio empezando a subir (primeros longs liquidándose).
- Regime "Euforia / Sobreextensión bullish".

**Lectura:** alza sostenida por apalancamiento sin respaldo spot. Vulnerable a una
corrección violenta por cascada de liquidaciones de longs. Momento de tomar
ganancias en longs o buscar shorts tácticos con stop ajustado.

**Invalidación:** el spot se suma (diff gira positivo) y el funding se normaliza sin
caída — el alza se vuelve sostenible.

### Setup E — Capitulación / suelo de corto plazo (sesgo LONG contrarian)

**Señales alineadas:**
- Pico de long_liq (cascada de liquidaciones de longs).
- liq_ratio >> 1 (longs masacrados).
- OI desplomándose (desapalancamiento masivo).
- CVD spot empezando a girar positivo (ballenas comprando el miedo).
- Regime "Capitulación (Bearish)" tornando.

**Lectura:** el desapalancamiento forzado suele marcar suelos locales. Cuando el
whale delta spot empieza a acumular en plena capitulación de futuros, es señal de
manos fuertes comprando el pánico. Contrarian, alto riesgo, requiere confirmación.

**Invalidación:** las liquidaciones continúan sin que el spot acumule (la caída tiene
más recorrido).

---

## Parte V — Rutina de lectura sugerida

Un orden para no perderse entre tantos datos:

1. **Contexto de mediano plazo primero (histórico diario):** ¿cuál es la pendiente del
   CVD spot acumulado? ¿Hay racha spot? Esto enmarca el flujo de fondo (compras vs
   distribución).
2. **Estado actual (snapshot + regime):** ¿qué dice el régimen ahora? ¿Confirma o
   contradice el sesgo de fondo?
3. **Contexto de spot y futuros:** ¿sus signos coinciden? ¿Cómo se comparan sus
   imbalances normalizados? No atribuyas identidad a los participantes.
4. **Estado del apalancamiento (OI + funding + liquidaciones):** ¿el movimiento tiene
   respaldo o es frágil? ¿Qué lado está vulnerable?
5. **Timing de corto plazo (CVD live + btr + delta_3min):** ¿hay presión relativa,
   net rate y persistencia ahora mismo?

**Regla de oro:** mayor convicción cuando el corto plazo (pasos 4-5) se alinea con el
mediano plazo (paso 1). Operar el snapshot a favor de la pendiente del CVD spot acumulado
es más seguro que contra ella. Cuando los pasos se contradicen, espera o reduce tamaño.

---

## Parte VI — Errores de interpretación a evitar

- **Leer el Diff raw como dirección.** Mezcla mercados con escalas distintas; úsalo solo
  como descripción de magnitud y lee las patas/imbalances por separado.
- **Tratar el regime label como señal de entrada.** Es contexto. Los pesos no están
  calibrados.
- **Confundir participación (btr) con volumen (CVD).** Son cosas distintas; su
  divergencia es información, no contradicción.
- **Ignorar la unidad temporal.** El histórico diario (mediano plazo) y el snapshot
  (ahora) responden preguntas distintas. No los mezcles sin distinguir horizonte.
- **Operar contra la pendiente del CVD spot acumulado** sin razón fuerte. El flujo spot
  sostenido suele ganar.
- **Sobreleer el ruido.** Whale "Neutro" o Diff cerca de cero = ausencia de señal, no
  señal débil. A veces no hay setup y lo correcto es no operar.
- **Olvidar que esto mide presión, no precio.** La distribución puede durar semanas
  antes de resolverse. El dashboard te dice que la presión existe, no cuándo se
  materializa. El timing y el riesgo son tuyos.

---

## Parte VII — Modo Scalping / Ejecución rápida

El modo scalping no reemplaza el marco de fondo del dashboard; lo comprime a ventanas
operativas de segundos y minutos. Su objetivo es responder rápido:

- ¿hay agresión inmediata?
- ¿el flujo agresivo tiene continuidad o está siendo absorbido?
- ¿qué lado del libro tiene presión inmediata?
- ¿qué lado apalancado está vulnerable?
- ¿hay condiciones para ejecutar o conviene esperar?

El `regime_score` sigue siendo contexto. Para entrada rápida usa `scalp_score`, delta
matrix, order book, absorción y liquidaciones inmediatas.

### 11. Delta matrix 15s–15m

**Qué mide:** delta spot y delta de futuros en ventanas rolling: 15s, 30s, 1m, 3m, 5m
y 15m. El raw delta es notional agresivo neto acumulado en el lookback y
`diff = spot_delta − fut_delta` conserva esa resta descriptiva. `imbalance = net/gross`
mide presión agresiva relativa dentro de cada ventana; `net_rate_usd_per_min` mide neto
agresivo USD por minuto.

**Cómo leerlo:**

- **Fut delta positivo + spot delta positivo:** impulso alcista confirmado.
- **Fut delta negativo + spot delta negativo:** impulso bajista confirmado.
- **Fut delta fuerte y spot débil/contrario:** movimiento frágil, probable squeeze o
  apalancamiento sin confirmación.
- **Diff positivo fuerte con fut delta negativo:** los futuros venden agresivo, pero el
  spot resiste mejor; posible absorción de ventas.
- **Diff negativo fuerte con fut delta positivo:** los futuros compran agresivo, pero
  el spot no confirma; posible distribución hacia compradores apalancados.

Las ventanas están anidadas y son evidencia correlacionada/dependiente, no confirmaciones
independientes. El mismo signo en 15s → 30s → 1m aporta contexto de persistencia inmediata;
3m → 5m aporta contexto de continuidad y 15m contexto intradía. PR22 no publica una
estadística formal de aceleración calculada sobre ventanas disjuntas.

### 12. Futures tape real-time

**Qué mide:** flujo de trades de futuros en tiempo real desde Binance USD-M y Bybit
Linear: volumen comprador, volumen vendedor, delta, número de trades y volumen medio.

**Cómo leerlo:**

- **Delta fuerte con muchos trades:** participación amplia; mejor continuidad.
- **Delta fuerte con pocos trades grandes:** posible actividad institucional o sweep;
  necesita confirmación de precio.
- **Delta fuerte sin desplazamiento de precio:** absorción.
- **Delta fuerte con spread ampliándose:** ejecución más riesgosa; evita perseguir.

### 13. Order book imbalance

**Qué mide:** presión visible del libro en L1/L5/L10, spread en bps y paredes cercanas.
`imbalance_l5 = bid_notional_l5 / (bid_notional_l5 + ask_notional_l5)`.

**Cómo leerlo:**

- **Imbalance > 0.60:** más bid visible que ask; presión inmediata alcista.
- **Imbalance < 0.40:** más ask visible que bid; presión inmediata bajista.
- **Spread bajo:** ejecución limpia.
- **Spread alto o cambiante:** peor calidad de entrada.
- **Pared cercana arriba:** resistencia inmediata; cuidado con longs tardíos.
- **Pared cercana abajo:** soporte/liquidez inmediata; cuidado con shorts tardíos.

El book es cancelable; úsalo como presión instantánea, no como convicción estructural.

### 14. Absorption matrix

**Qué mide:** relación entre delta de futuros y desplazamiento de precio en 1m, 3m,
5m y 15m.

**Cómo leerlo:**

- **Delta positivo fuerte + precio plano/bajando:** absorción de compras. Lectura
  bajista; los compradores agresivos no logran desplazar precio.
- **Delta negativo fuerte + precio plano/subiendo:** absorción de ventas. Lectura
  alcista; los vendedores agresivos no logran desplazar precio.
- **Delta fuerte + precio acompaña:** momentum, no absorción.
- **Delta bajo + precio moviéndose:** movimiento con poca participación; puede ser
  barrida de liquidez o vacío de libro.

La absorción tiene más valor cerca de VWAP, high/low intradía, apertura NYSE o niveles
de liquidez recientes.

### 15. Liquidation tape real-time

**Qué mide:** liquidaciones recientes por lado, con lectura de presión forzada.

**Cómo leerlo:**

- **Short liquidations aumentando:** combustible alcista ya detonando.
- **Long liquidations aumentando:** combustible bajista ya detonando.
- **Liquidaciones fuertes + OI bajando:** cierre forzado/desapalancamiento.
- **Liquidaciones fuertes + spot absorbiendo:** posible clímax local y reversión
  contraria.

No toda liquidación es señal de entrada. Una cascada puede continuar mucho más de lo
esperado.

### 16. OI microdelta

**Qué mide:** cambio de Open Interest en ventana corta frente a cambio de precio.

**Cómo leerlo:**

- **OI sube + precio sube:** longs nuevos entrando.
- **OI sube + precio baja:** shorts nuevos entrando.
- **OI baja + precio sube:** short covering; rally de menor calidad si spot no
  confirma.
- **OI baja + precio baja:** longs cerrando; venta por desapalancamiento.

Para scalping, OI micro es confirmación secundaria. La entrada debe apoyarse primero
en delta, book, absorción y ubicación respecto a VWAP/niveles.

### 17. VWAP y niveles intradía

**Qué mide:** precio medio ponderado por volumen de la sesión y distancia porcentual
actual contra VWAP.

**Cómo leerlo:**

- **Precio sobre VWAP + delta comprador confirmado:** longs en pullback tienen mayor
  calidad.
- **Precio bajo VWAP + delta vendedor confirmado:** shorts en rebote tienen mayor
  calidad.
- **Precio lejos de VWAP:** evita perseguir; espera pullback o confirmación fuerte.
- **Absorción sobre VWAP:** posible continuación alcista si el book acompaña.
- **Absorción bajo VWAP:** posible continuación bajista si el book acompaña.

### 18. Scalp score

**Qué mide:** sintetizador operativo de corto plazo. Combina delta de futuros,
divergencia spot/futuros, order book, absorción, liquidaciones, OI micro y VWAP de
sesión. Produce `long_score`, `short_score`, estado, confianza y razón.

**Pesos actuales v1.2.1:**

- **Delta de futuros:** 20%. Mide agresión apalancada inmediata.
- **Divergencia spot/futuros:** 15%. Penaliza movimientos de futuros sin confirmación
  spot y favorece lecturas donde el spot absorbe o lidera.
- **Order book:** 20%. Usa presión L5/L10 y calidad del spread; si el libro está
  `stale` o `missing`, la confianza debe degradarse.
- **Absorción:** 20%. Detecta agresión que no desplaza precio.
- **Liquidaciones:** 10%. Lee presión forzada reciente.
- **OI micro:** 10%. Confirma si entra o sale apalancamiento.
- **VWAP:** 5%. Penaliza persecución lejos del precio medio de sesión.

**Estados típicos:**

- **Long Momentum:** delta y book favorecen continuación alcista.
- **Long Pullback:** contexto alcista con retroceso hacia nivel útil.
- **Short Momentum:** delta y book favorecen continuación bajista.
- **Short Rejection:** presión vendedora activa o rechazo tras intento alcista.
- **No Trade:** información contradictoria, insuficiente o degradada.

**Uso correcto:** el score prioriza atención. No debe usarse como gatillo único. Si el
score contradice el contexto de fondo, reduce tamaño o espera confirmación. Si
`book_status` no es `ok`, trata cualquier score como preliminar.

### 19. Signal snapshots y memoria operativa

**Qué mide:** `scalp_signal_snapshot` persiste periódicamente lo que el tablero está
diciendo: estado, scores, confianza, razón y componentes principales. En versiones
anteriores esa señal era efímera; ahora queda trazabilidad.

**Cómo leerlo:** sirve para responder después: "¿qué estaba diciendo el dashboard
antes del movimiento?". También permite revisar transiciones de estado, contar falsas
señales y alimentar calibración. No es una señal adicional; es memoria de la señal.

**Uso correcto:** revisa snapshots para auditar disciplina operativa. Si una entrada
se tomó contra el score o contra baja confianza, debe quedar claro en la bitácora.

**Calibración:** la herramienta incluye un harness offline para medir retornos
forward por estado y confianza. Para evitar sobrecontar señales repetidas cada pocos
segundos, usa preferentemente los modos `episode` o `non_overlap`, no el modo `raw`,
cuando evalúes hit-rate o expectancy. La calibración debe interpretarse con la
retención real de `ohlcv`; si la base conserva 14 días, no atribuyas significancia a
una ventana estadística de 30 días.

**Interfaz v1.2.1:** las señales recientes ya se muestran en el dashboard junto con
basis, data confidence y niveles de liquidación. El endpoint batch `/api/dashboard/state`
se usa para reducir llamadas y mantener una lectura más coherente entre paneles.

### 20. Basis perp-spot

**Qué mide:** diferencia entre el precio de perpetuo y el precio spot, expresada en
bps. `basis_bps > 0` indica perpetuo con prima frente al spot; `basis_bps < 0` indica
descuento.

**Cómo leerlo:**

- **Prima positiva creciente:** mayor demanda o presión en perpetuos; puede reflejar
  apalancamiento largo o arbitraje activo.
- **Prima positiva + spot débil:** rally frágil, sostenido por futuros.
- **Descuento creciente:** presión vendedora en perpetuos o estrés de apalancamiento.
- **Basis comprimiéndose:** convergencia; el impulso apalancado pierde ventaja.

**Clave:** las patas CVD y sus imbalances comparan flujo; el basis compara precio. El Diff
raw conserva una resta descriptiva de escalas distintas y no añade un voto direccional.

### 21. Niveles de liquidación por precio

**Qué mide:** agrega `liquidations_realtime` por buckets de precio y lado. En lugar de
ver solo cuántas liquidaciones ocurrieron en 5m, muestra dónde se concentraron.

**Cómo leerlo:**

- **Clúster de short liquidations arriba:** zona donde los shorts fueron forzados a
  cerrar; puede actuar como imán si el precio se acerca con momentum.
- **Clúster de long liquidations abajo:** zona de estrés de longs; puede acelerar una
  cascada si se rompe soporte.
- **Clúster grande + absorción contraria:** posible clímax local.

No confundas nivel de liquidación reciente con soporte/resistencia permanente. Es
liquidez forzada ya ejecutada, útil para contexto inmediato.

### 21 bis. Barreras de precio y esfuerzo de ruptura

**Qué mide:** agrupa rechazos de pivotes diarios y 4h en zonas, no en líneas de falsa
precisión. La dificultad 0–100 combina número de toques, distancia de la reacción en ATR,
volumen relativo, absorción CVD y recencia. También compara el volumen perp de los últimos
15m con su mediana de 36h y cruza delta, desplazamiento y book L5.

**Cómo leerlo:**

- **Barrera fuerte + presión de ruptura menor de 70:** no anticipes el cruce; espera un
  rechazo confirmado para operar hacia el interior del rango.
- **Presión >=70 + cierre 15m fuera de la zona + retest sostenido:** la ruptura merece
  vigilancia en su dirección. Una mecha sola no confirma nada.
- **Volumen 1.5x normal pero delta contrario:** esfuerzo sin resultado; probable absorción.
- **Volumen bajo:** el precio puede atravesar una zona débil, pero una ruptura de una zona
  fuerte tiene poca confirmación.

No existe un volumen exacto conocido que garantice cruzar un nivel: hay liquidez oculta,
cancelaciones y ejecución pasiva. El panel muestra referencias observables, no probabilidad.

### 22. Data confidence

**Qué mide:** calidad operativa de los datos por símbolo: edad de snapshots, lag de
feeds, estado del order book, cobertura de venues y disponibilidad de señales scalp.

**Cómo leerlo:**

- **OK:** feeds recientes, snapshot fresco y libro confiable.
- **Degraded:** hay datos, pero algún carril está retrasado, faltante o con cobertura
  parcial. Reduce confianza y tamaño.
- **Stale/Missing:** no uses el componente afectado para decidir.

**Regla:** ninguna señal de scalp debe leerse sin revisar primero data confidence.
Un score alto con feed degradado es una alerta de infraestructura, no una ventaja
operativa.

### 23. Métricas Prometheus y observabilidad

**Qué mide:** `/metrics` expone contadores y gauges operativos: heartbeats, lags,
liquidaciones descartadas, estado de servicios y salud de feeds. Está protegido por
`X-Internal-Token`.

**Cómo usarlo:** intégralo con Prometheus/Grafana o Wazuh para alertar si el dashboard
empieza a operar con datos atrasados, cola de liquidaciones saturada o feeds caídos.
Esto no mejora la señal económica; mejora la confiabilidad de la herramienta.

### 24. Alertas P1/P2

**Qué miden:** condiciones accionables o de vigilancia detectadas por combinación de
flujo, book y liquidaciones.

- **P1:** evento inmediato que merece atención operacional. Incluye alertas de
  calidad como `Order book no confiable` cuando `book_status` es `stale` o `missing`.
- **P2:** vigilancia; preparar escenario, no ejecutar sin confirmación.

Una alerta económica es válida solo si el precio está en una zona operable y el riesgo
está definido. Una alerta de calidad de datos debe interpretarse como bloqueo parcial
de lectura, no como señal de mercado. No persigas una alerta después de que el
desplazamiento ya ocurrió.

---

## Parte VIII — Rutina específica para scalping

Orden recomendado para lectura rápida:

1. **Data confidence:** confirma que feeds, snapshots y order book sean confiables.
2. **Estado superior:** precio, spread, latencia y símbolo correcto.
3. **Scalp score:** define si hay sesgo inmediato o `No Trade`.
4. **Delta matrix:** compara imbalance, net rate y persistencia sin llamarlos aceleración.
5. **Basis perp-spot:** valida si el precio de futuros confirma o se desacopla del
   spot.
6. **Order book:** valida si la liquidez inmediata acompaña o bloquea la operación.
7. **Absorción:** identifica si el flujo agresivo está fallando contra pasivos.
8. **Liquidaciones y niveles:** revisa si hay squeeze/cascada activa y dónde se
   concentró.
9. **VWAP/niveles:** decide si el precio está en zona ejecutable o tarde.
10. **Contexto de fondo:** regime, funding, OI 24h e histórico diario para no operar
    contra una presión estructural fuerte sin razón.

**Regla práctica:** si delta, book y absorción no están alineados, no hay scalp claro.
Si el spread se amplía o el book cambia violentamente, baja tamaño o espera.

---

## Parte IX — Errores de scalping a evitar

- **Perseguir delta tarde.** Un delta fuerte después del desplazamiento suele ser mala
  entrada.
- **Ignorar absorción.** Si el mercado compra agresivo y el precio no sube, el long es
  de baja calidad.
- **Sobreconfiar en el order book.** Las órdenes visibles pueden cancelarse.
- **Operar con spread alto.** El costo de ejecución invalida muchos scalps.
- **Confundir squeeze con demanda real.** Un short covering puede subir rápido y fallar
  igual de rápido.
- **Usar el scalp score como sistema mecánico.** Es un filtro, no una orden.
- **Operar con data confidence degradado.** Si el feed o el libro están viejos, el
  score puede verse limpio pero estar basado en datos inválidos.
- **Ignorar basis.** Un movimiento de futuros sin respaldo spot puede revertir con
  violencia cuando se comprime la prima.
- **No distinguir horizonte.** Un long scalp puede ser válido dentro de un régimen de
  distribución, pero exige salida rápida y menor tolerancia.

---

## Anexo — Cambios operativos v1.2.1

Esta versión cierra residuales de la revisión v1.2.0:

- La lógica de scalping compartida vive en `app/scalp_logic.py`; el collector ya no
  importa la capa FastAPI ni depende de assets estáticos.
- El frontend consume los endpoints de basis, señales recientes, niveles de
  liquidación, data confidence y estado batch del dashboard.
- La calibración soporta `episode` y `non_overlap` para reducir autocorrelación de
  muestras.
- Las métricas Prometheus siguen protegidas por `X-Internal-Token`; la configuración
  de scrape debe documentar ese header o pasar por Nginx con autenticación.

Regla de operación: si `data confidence` está degradado, la lectura económica debe
considerarse parcial aunque el score parezca claro.
