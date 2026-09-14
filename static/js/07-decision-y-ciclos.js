'use strict';
// la mesa de decision y los ciclos refreshOverview/loadSection
// Trozo 7 de 11 del panel. Sale de static/app.js SIN TOCAR UNA LINEA DE LOGICA
// (FASE 2, 2026-09-13): lineas 1433-1859 del fichero original.
// El orden de los <script defer> de index.html ES el orden de este fichero: no se
// reordena nada, porque en scripts clasicos un `const` de primer nivel solo existe a
// partir del script que lo declara.
function renderDecisionBoard(dashboard, trend, swing, structureDetail, confidence, externalMacro = {}) {
  const body = $('decision-horizons');
  if (!body) return;
  const quality = safeArray(confidence && confidence.rows)[0] || {};
  const qualityOk = quality.status === 'ok';
  const scalp = dashboard.scalp || {};
  const barriers = dashboard.barriers || {};
  const cvd = dashboard.cvd_swing || {};
  const memory = dashboard.market_memory || {};
  const externalRegime = externalMacro.regime || 'sin_datos';
  const externalAlignment = externalMacro.alignment || {};
  const eventRisk = externalMacro.event_risk || {};

  // D1 · EL HORIZONTE DE LA TARJETA DE CORTO SALE DE UN DATO, NO DE UNA CADENA.
  // Aqui decia `time: '1–15 minutos'`, escrito a mano, y medido contra 30 dias la senal
  // dura una mediana de 1 minuto con p90 de 3. El rotulo prometia un horizonte que el
  // calculo no sostiene, y ese error se paga con dinero: invita a aguantar una posicion
  // por un plazo que la senal no cubre.
  // Ahora la cifra viene de /api/dashboard/state -> scalp_persistence, que la mide del
  // mismo sitio del que sale el veredicto de K90. Si el bloque no llega o no es medible,
  // se dice "sin medida", NUNCA un rango inventado: un rotulo sin dato es lo que habia.
  const persistencia = dashboard.scalp_persistence || {};
  const shortHorizon = persistencia.available && persistencia.etiqueta
    ? persistencia.etiqueta
    : 'persistencia sin medida';
  // LA TASA BASE, CON SU ALCANCE PEGADO. Viene de /api/dashboard/state -> signal_base_rate,
  // que la mide sobre `signal_outcome`. K95 comprueba que lo que se pinta aqui es lo que sale
  // de la tabla.
  //
  // LO QUE ESTA FRASE NO DICE, Y ES DELIBERADO: no dice «el sistema pierde». Lo medido es que
  // la señal NO anticipa nada -ni a favor ni en contra: la ventaja neta es 0.0003 % con t
  // 0.13 sobre 1191 bloques- y que ENTRA AL PEOR PRECIO de su propia ventana. Eso es una
  // afirmacion sobre la EJECUCION, no sobre el acierto, y la diferencia decide si lo que hay
  // que arreglar es como se entra o que se decide.
  //
  // Y EL ALCANCE VA EN LA MISMA FRASE, no en un tooltip: la unica ventana con señal son ~27
  // dias que caen en el percentil 95.9 de la historia comparable, y la mitad de esa historia
  // son ventanas negativas que no hemos visto. Una tasa base medida en el mejor 5 % de dos
  // años tiene que decir que lo es, o es un numero limpio y falso.
  const tasaBase = dashboard.signal_base_rate || {};
  const alcance = tasaBase.alcance || {};
  const shortBaseRate = tasaBase.available
    ? [
        // CUATRO DECIMALES Y NO TRES: con tres, una ventaja neta de 0.0003 se pinta como
        // "+0.000%" y se lee como un cero redondeado en vez de como la cifra que es.
        //
        // DOS COSTES DE ENTRADA Y LOS DOS SE DICEN. El primero va ponderado POR BLOQUE,
        // igual que la ventaja, y es el que se puede comparar con ella: comparar dos medias
        // ponderadas de forma distinta no decompone nada. El segundo va por OPERACION, que
        // es lo que le cuesta a quien opera, porque cada entrada es una observacion y no un
        // bloque. La diferencia entre 0.0531 y 0.0479 es ponderacion, no señal.
        `Coste de entrada ${pct(tasaBase.coste_entrada_pct, 4)} por bloque`
          + (tasaBase.coste_entrada_por_obs_pct === null || tasaBase.coste_entrada_por_obs_pct === undefined
              ? '' : ` (${pct(tasaBase.coste_entrada_por_obs_pct, 4)} por operación)`)
          + ` · ventaja neta ${pct(tasaBase.ventaja_neta_pct, 4)}`
          + (tasaBase.t_neta === null || tasaBase.t_neta === undefined ? '' : ` (t ${number(tasaBase.t_neta, 3)})`),
        // «BLOQUES» SON BLOQUES DE TIEMPO DISTINTOS, no pares (bloque, lado). Los dos lados
        // del mismo bloque leen el MISMO tramo de mercado: no son dos muestras de tiempo, y
        // publicarlos como si lo fueran doblaba la muestra en la unica cifra cuyo proposito
        // es ser honesta sobre el tamaño de muestra. Encontrado por el operador el 09-06.
        `sobre ${number(tasaBase.observaciones, 0)} observaciones en ${number(tasaBase.n_efectiva, 0)} bloques distintos de ${number(tasaBase.horizonte_min, 0)} min, ${number(tasaBase.dias_de_arco, 1)} días de arco.`,
        // LA FRASE CAMBIO EL 2026-09-06 Y LO QUE CAMBIO ES LA LECTURA, NO LA MEDIDA.
        // Decia: «El coste de entrada es del orden de la ventaja: es un problema de ejecución,
        // no de acierto.» La primera mitad sigue medida y sigue aquí. La segunda no se
        // sostiene: la campaña de la regla de entrada midió que NINGUNA regla alcanzable la
        // recupera —el retraso fijo solo la recupera entera a k=60 min, que es el horizonte
        // completo, y la orden limitada es PEOR que no esperar en las 18 celdas medidas—.
        // Llamar «de ejecución» a algo que ninguna ejecución arregla es un eufemismo.
        //
        // Y NO SE DICE «la señal se publica después del movimiento que nombra», aunque sea la
        // lectura natural: eso es una inferencia. Lo MEDIDO es que entra a un precio
        // desplazado y que esperar no lo recupera. La tarjeta dice lo medido.
        tasaBase.lectura === 'el coste de entrada se come la ventaja'
          ? (tasaBase.supervivencia_1min_pct === null || tasaBase.supervivencia_1min_pct === undefined
              ? 'El coste de entrada se lleva la ventaja. No se pudo medir cuánto dura la señal, así que esta tarjeta no dice si esperar lo arreglaría.'
              : `El coste de entrada se lleva la ventaja, y NO se arregla cambiando cómo se entra: al minuto siguiente la señal ya no existe en el ${number(100 - tasaBase.supervivencia_1min_pct, 1)} % de los casos (${number(tasaBase.supervivencia_n, 0)} señales; sigue viva = ${tasaBase.supervivencia_definicion}), así que esperar a un precio mejor es operar otra cosa.`)
          : 'Hay ventaja direccional medible además del coste de entrada.',
        alcance.available
          ? `Alcance: esos ${number(alcance.dias_de_la_ventana, 0)} días están en el percentil ${number(alcance.percentil_de_la_ventana, 1)} de ${number(alcance.ventanas_comparadas, 0)} ventanas comparables (mediana ${pct(alcance.mediana_historica_pct, 2)}); ${number(alcance.ventanas_negativas, 0)} de ellas fueron negativas y no están en la muestra.`
          : 'Alcance: no se pudo situar la ventana en la historia, así que esta cifra no dice cuán representativa es.',
      ].join(' ')
    : `Sin medida${tasaBase.motivo ? ` (${tasaBase.motivo})` : ''}`;

  const scalpState = String(scalp.state || '').toLowerCase();
  const shortSide = scalpState.includes('long') ? 'LONG' : scalpState.includes('short') ? 'SHORT' : 'WAIT';
  let shortAction = shortSide === 'WAIT' ? 'ESPERAR' : `VIGILAR ${shortSide}`;
  let shortThesis = scalp.reason || 'El score intradía todavía no supera el umbral operativo.';
  if (!qualityOk) shortAction = 'NO OPERAR';
  else if (barriers.active_zone) {
    shortAction = 'ESPERAR';
    shortThesis = `El precio está dentro de una barrera ${barriers.active_zone.difficulty || ''}; la lectura ${shortSide === 'WAIT' ? 'intradía' : shortSide} aún no tiene espacio limpio.`;
  }
  const shortTrigger = shortSide === 'SHORT'
    ? ((barriers.short_case || {}).breakdown || (barriers.short_case || {}).rejection)
    : shortSide === 'LONG'
      ? ((barriers.long_case || {}).breakout || (barriers.long_case || {}).rejection)
      : 'Score long o short ≥60, book fresco y cierre 15m fuera de la zona disputada';
  const shortInvalidation = shortSide === 'SHORT' && barriers.nearest_resistance
    ? `Cancelar short sobre ${money(barriers.nearest_resistance.high, 2)}`
    : shortSide === 'LONG' && barriers.nearest_support
      ? `Cancelar long bajo ${money(barriers.nearest_support.low, 2)}`
      : 'No entrar sin nivel técnico de salida';

  const mediumSignal = ['LONG', 'SHORT'].includes(cvd.signal) ? cvd.signal : 'WAIT';
  const mediumAlignment = trend.medium_term_alignment === 'alcista' ? 'LONG' : trend.medium_term_alignment === 'bajista' ? 'SHORT' : 'WAIT';
  const refs = cvd.reference_levels || {};
  const lastClose = asNumber(refs.last_close);
  const confirmed = mediumSignal === 'LONG'
    ? lastClose !== null && lastClose > asNumber(refs.confirm_above)
    : mediumSignal === 'SHORT' && lastClose !== null && lastClose < asNumber(refs.confirm_below);
  const mediumAligned = mediumSignal !== 'WAIT' && mediumSignal === mediumAlignment;
  let mediumAction = mediumSignal === 'WAIT' ? 'ESPERAR' : `VIGILAR ${mediumSignal}`;
  if (!qualityOk) mediumAction = 'NO OPERAR';
  else if (!mediumAligned || !confirmed) mediumAction = mediumSignal === 'WAIT' ? 'ESPERAR' : `VIGILAR ${mediumSignal}`;
  if (qualityOk && ['alto', 'elevado'].includes(eventRisk.level)) mediumAction = 'ESPERAR EVENTO';
  else if (qualityOk && externalAlignment.state === 'conflicto' && mediumSignal !== 'WAIT') mediumAction = `VIGILAR ${mediumSignal} · TÁCTICO`;
  const mediumTrigger = mediumSignal === 'LONG'
    ? `Cierre sobre ${money(refs.confirm_above, 2)} con 4h/8h/1d alcistas`
    : mediumSignal === 'SHORT'
      ? `Cierre bajo ${money(refs.confirm_below, 2)} con 4h/8h/1d bajistas`
      : 'Separación CVD/precio ≥30 puntos y estructura 4h/8h/1d alineada';

  const longSide = ['LONG', 'SHORT'].includes(swing.bias) ? swing.bias : 'WAIT';
  const longFrame = ((structureDetail || {}).horizons || {})['3d'] || ((structureDetail || {}).horizons || {})['1d'] || {};
  let longAction = !qualityOk ? 'NO OPERAR' : longSide === 'WAIT' ? 'NEUTRAL' : `SESGO ${longSide}`;
  if (qualityOk && ['alto', 'elevado'].includes(eventRisk.level)) longAction = 'ESPERAR EVENTO';
  else if (qualityOk && externalAlignment.state === 'conflicto' && longSide !== 'WAIT') longAction = `SESGO ${longSide} · TÁCTICO`;
  const directionalComponents = safeArray(swing.components)
    .filter(item => longSide === 'LONG' ? asNumber(item.contribution) > 0 : longSide === 'SHORT' ? asNumber(item.contribution) < 0 : asNumber(item.contribution) !== 0)
    .slice(0, 2)
    .map(item => item.name)
    .join(' + ');
  const longTrigger = longSide === 'LONG'
    ? `Cierre 3D sobre ${money(longFrame.bos_level, 2)}`
    : longSide === 'SHORT'
      ? `Cierre 3D bajo ${money(longFrame.bos_level, 2)}`
      : 'Score swing fuera de ±30 y estructura diaria confirmada';
  const longInvalidation = longFrame.invalidation_level != null
    ? `Tesis inválida al perder ${money(longFrame.invalidation_level, 2)} en 3D`
    : 'Sin nivel estructural: no construir posición';
  const analogSummary = memory.analog_summary || {};
  let longThesis = longSide === 'WAIT'
    ? 'La evidencia de fondo está equilibrada.'
    : `El balance de evidencia favorece ${longSide}; la memoria de 2 años clasifica el entorno como ${memory.phase || 'aún sin datos'}.`;
  if (externalAlignment.reading) longThesis += ` ${externalAlignment.reading}`;

  body.replaceChildren(
    horizonCard({
      name: 'Corto plazo', time: shortHorizon, action: shortAction, side: shortAction.includes(shortSide) ? shortSide : 'WAIT',
      thesis: shortThesis, trigger: shortTrigger, invalidation: shortInvalidation,
      // UNA CIFRA Y SU COMPLEMENTO, NO DOS LECTURAS. Medido sobre las 22 187 filas de
      // scalp_signal_snapshot: long+short = 100 en TODAS, corr = -1.0000 exacta, y cero filas
      // con las dos por encima -o por debajo- de su mediana. «62 L / 38 S» se leia como si dos
      // mediciones hubieran votado; lo que hay es un solo numero dicho dos veces. Se publica
      // como lo que es: un sesgo de 0 a 100, con su complemento entre parentesis.
      metric: `Sesgo scalp ${number(scalp.long_score, 0)}/100 hacia largo (el 'short' es su complemento, no una segunda lectura) · barrera ${barriers.decision || 'sin lectura'}`,
      baseRate: shortBaseRate,
      link: '#liquidez', linkText: 'Ver liquidez y barreras',
    }),
    horizonCard({
      name: 'Mediano plazo', time: '2 sesiones', action: mediumAction, side: mediumAction.includes(mediumSignal) ? mediumSignal : 'WAIT',
      thesis: [cvd.thesis, externalAlignment.reading].filter(Boolean).join(' '), trigger: mediumTrigger, invalidation: cvd.invalidation,
      metric: `CVD90 ${number(cvd.score, 1)}/100 · tendencia ${trend.medium_term_alignment || 'sin definir'} · macro ext ${externalRegime}`,
      link: '#contexto', linkText: 'Ver CVD 90 sesiones',
    }),
    horizonCard({
      name: 'Largo plazo', time: 'Días–semanas', action: longAction, side: longAction.includes(longSide) ? longSide : 'WAIT',
      thesis: longThesis,
      trigger: longTrigger, invalidation: longInvalidation,
      metric: `${number(swing.score, 0)}/100 · ${swing.conviction || 'sin convicción'} · macro ext ${externalRegime} · análogos +20d ${pct(analogSummary.median_return_20d_pct, 1)}${directionalComponents ? ` · ${directionalComponents}` : ''}`,
      link: '#estructura', linkText: 'Ver estructura y swing',
    }),
  );

  const alignment = $('decision-alignment');
  const sides = [shortSide, mediumSignal, longSide].filter(side => side !== 'WAIT');
  const hasLong = sides.includes('LONG');
  const hasShort = sides.includes('SHORT');
  let text = 'Sin ventaja operativa';
  let cls = 'neutral';
  if (!qualityOk) text = 'Datos degradados · no operar';
  else if (['alto', 'elevado'].includes(eventRisk.level)) text = 'Evento macro próximo · esperar';
  else if (externalAlignment.state === 'conflicto') text = 'Macro e impulso en conflicto · posición táctica';
  else if (hasLong && hasShort) text = 'Horizontes mixtos · reducir riesgo';
  else if (sides.length >= 2) { text = `Sesgo ${sides[0]} ${sides.length}/3 · confirmar entrada`; cls = sides[0] === 'LONG' ? 'positive' : 'negative'; }
  else if (sides.length === 1) { text = `Sesgo parcial ${sides[0]} · esperar`; cls = sides[0] === 'LONG' ? 'positive' : 'negative'; }
  alignment.textContent = text;
  alignment.className = `decision-alignment ${cls}`;
}

async function refreshOverview(forceContext = false) {
  const requestId = ++state.refreshSeq;
  const symbol = state.symbol;
  const q = encodeURIComponent(symbol);
  const contextExpired = forceContext || Date.now() - state.lastContextAt > 60000;
  // El rollup diario cambia una vez por sesion: va en el tramo lento, no en el de 15 s.
  const contextRequest = contextExpired ? Promise.all([
    // FASE 1 · LAS CINCO FOTO DE ESTE TRAMO SALEN DEL SOBRE, no de cinco rutas sueltas.
    // El sobre se pide UNA vez arriba y estas cinco lecturas son sincronas sobre el.
    pedirSobre(q).then(() => delSobre('trend_matrix', { timeframes: {} })),
    pedirSobre(q).then(() => delSobre('swing_score', {})),
    pedirSobre(q).then(() => delSobre('structure_detail', { horizons: {} })),
    pedirSobre(q).then(() => delSobre('wyckoff', { available: false })),
    maybe(`/api/daily?symbol=${q}&days=60`, { rows: [] }),
    pedirSobre(q).then(() => delSobre('external_macro_context', { available: false })),
    // EL COSTE Y EL VEREDICTO VAN EN EL TRAMO LENTO a proposito: son gasto y lectura de lo que
    // ya paso, no un tick. Y el veredicto se pide con una ventana de 7 dias porque el horizonte
    // declarado es dias-a-semanas; la respuesta echa el instante que uso, asi que la lectura de
    // la portada se puede volver a pedir cerrada y auditar.
    maybe(`/api/carry/matriz?dias=15`, null),
    maybe(`/api/rango/estructura?symbol=${q}&desde=${encodeURIComponent(desdePortada())}`, null),
    // UN solo snapshot para la Mesa: perfil, hipotesis, matrices y calidad salen del MISMO
    // calculo y comparten `as_of`. Antes eran dos peticiones que recalculaban trend_matrix,
    // delta_matrix y scalp_context por separado, cada una con su propio `now()`.
    // Va en el tramo lento (60 s): es jerarquia y contexto, no un tick.
    maybe(`/api/desk/state?symbol=${q}&profile=${encodeURIComponent(state.tradingProfile)}&direction=${encodeURIComponent(state.direction)}&setup=${encodeURIComponent(state.setup)}`, { components: {} }),
  ]) : null;
  // EL SOBRE VA PRIMERO Y SOLO UNA VEZ POR REFRESCO. De el sale data-confidence.
  //
  // `/api/dashboard/state` SIGUE PIDIENDOSE SUELTA, y es una decision medida, no un olvido:
  // la ruta devuelve NUEVE claves y el sobre solo cubre SIETE. `scalp_persistence` y
  // `signal_base_rate` no estan en el sobre por ningun camino -buscados en las 49 claves y
  // en sus hijos- y el panel las pinta las dos. Moverla costaria esas dos cifras, y el
  // criterio de esta fase es que ninguna tarjeta pierda un campo. Ampliar el sobre es
  // backend y es otra fase.
  await pedirSobre(q, contextExpired);
  const [dashboard, ohlcv, health] = await Promise.all([
    maybe(`/api/dashboard/state?symbol=${q}`, { snapshot: null, scalp: {}, setup: { setups: [] } }),
    maybe(`/api/ohlcv?symbol=${q}&interval=5min&limit=576`, { rows: [] }),
    maybe('/api/healthz', { status: 'degraded', services: [] }),
  ]);
  const confidence = sobreConfianza({ rows: [] });
  const context = contextRequest ? await contextRequest : null;
  if (symbol !== state.symbol) return;
  if (requestId !== state.refreshSeq) return;
  if (context) {
    let desk;
    let carry, tramo;
    [state.trend, state.swing, state.structureDetail, state.wyckoff, state.daily,
     state.externalMacro, carry, tramo, desk] = context;
    state.carry = carry;
    state.tramo = tramo;
    state.desk = desk || {};
    const componentes = state.desk.components || {};
    // El perfil y la hipotesis salen del snapshot, no de dos peticiones independientes.
    state.tfProfile = componentes.profile || { layers: {} };
    state.hypothesisData = componentes.hypothesis || { evidence: {} };
    // trend_matrix del snapshot manda sobre la peticion suelta: es la que comparte `as_of`
    // con el resto de los paneles de la Mesa.
    if (componentes.trend_matrix) state.trend = componentes.trend_matrix;
    state.lastContextAt = Date.now();
    renderTfProfile(state.tfProfile);
    renderProfileEmphasis(state.tfProfile);
    renderHypothesis(state.hypothesisData);
    renderDeskAsOf(state.desk);
  }
  state.dashboard = dashboard;
  state.confidence = confidence;
  state.health = health;
  // DESPUES de asignar `state.dashboard`: la portada lee de ahi la tasa base. Pintarla
  // antes hacia que declarase un hueco que no existia.
  renderCarry(state.carry);
  renderPortada(state.tramo, state.carry);
  renderGlobalBar(health);
  const snapshot = dashboard.snapshot;
  const scalp = dashboard.scalp || {};
  if (snapshot) renderSummary(snapshot, scalp, dashboard.cvd_swing || {});
  else clearSnapshotView();
  renderExecutionLevels(scalp);
  renderDecisionBoard(dashboard, state.trend, state.swing, state.structureDetail, confidence, state.externalMacro);
  renderQuickRead(state.daily);
  renderWyckoff(state.wyckoff);
  renderMarketMemory(dashboard.market_memory || {});
  renderPriceChart(filasDe(ohlcv));
  renderStructureLevels(state.structureDetail, dashboard.barriers || {}, state.wyckoff);
  const wyckoffButton = $('price-mode-wyckoff');
  if (wyckoffButton) wyckoffButton.disabled = !state.wyckoff.available;
  renderHealth(health);
  renderDataConfidence(confidence);
  setConnection(health.status === 'ok' ? 'ok' : 'bad', health.status === 'ok' ? 'En línea' : 'Pipeline degradado');
}

async function loadSection(id, force = false) {
  if (id === 'mesa') return;
  if (!force && Date.now() - (state.viewLoadedAt[id] || 0) < 30000) return;
  const symbol = state.symbol;
  const q = encodeURIComponent(symbol);
  if (id === 'coste') {
    // El coste y sus dos heatmaps de dias ya los pinta el refresco general -van en el tramo
    // lento junto al veredicto-. Aqui solo hace falta el mapa por precio, que es de esta
    // seccion y de ninguna otra.
    await pedirSobre(q);
    renderLiqPrecio(delSobre('liquidation_map', null));
    if (symbol !== state.symbol) return;
    state.viewLoadedAt[id] = Date.now();
    return;
  }
  if (id === 'flujo') {
    const [cvd, oi, whale, daily, delta, absorption] = await Promise.all([
      // Desde 2026-08-26 la ruta sirve sobre con coverage (K43: una serie declara su
      // ventana). filasDe() acepta las dos formas, asi que el orden de despliegue da igual.
      maybe(`/api/cvd/divergence?symbol=${q}&interval=5min&limit=576`, { rows: [] }),
      maybe(`/api/oi?symbol=${q}&interval=15min&limit=384`, { rows: [] }),
      maybe(`/api/whale/delta?symbol=${q}&interval=15min&limit=384`, { rows: [] }),
      maybe(`/api/daily?symbol=${q}&days=60`, { rows: [], streak: 0 }),
      // LA MATRIZ DE DELTA SIGUE SUELTA, medido: la ruta sirve DOCE ventanas y el sobre
      // solo CINCO -15s, 1m, 3m, 5m, 15m-. Moverla perderia 30s, 18m, 30m, 1h, 4h, 8h y 1d,
      // que renderDeltaMatrix pinta como filas. Los campos por fila son los mismos; lo que
      // falta son FILAS, que es justo lo que una comparacion de nombres no ve.
      maybe(`/api/scalp/delta-matrix?symbol=${q}`, []),
      pedirSobre(q).then(() => delSobre('absorption', [])),
    ]);
    if (symbol !== state.symbol) return;
    renderFlowCharts(filasDe(cvd), null, filasDe(whale));
    renderDailyBars(daily);
    renderDeltaMatrix(delta);
    renderAbsorption(absorption);
  } else if (id === 'liquidez') {
    const [orderbook, execution, impact] = await Promise.all([
      // Sin freshness en el respaldo A PROPOSITO: si la peticion falla, el panel no
      // puede afirmar "no hay libro" ni "el libro es viejo". Lo que dice es que no hubo
      // lectura, que es lo unico cierto.
      pedirSobre(q).then(() => sobreOrderbook({ rows: [] })),
      // El perfil viaja al coste: el horizonte decide el umbral de AVISO de spread y con que
      // objetivo se compara el coste. Sin el, un swing recibia lectura de intradia.
      maybe(`/api/scalp/execution-cost?symbol=${q}&profile=${encodeURIComponent(state.tradingProfile)}`, { venues: [] }),
      pedirSobre(q).then(() => delSobre('market_impact', { windows: [] })),
    ]);
    if (symbol !== state.symbol) return;
    renderOrderbook(orderbook);
    renderExecutionCost(execution);
    renderMarketImpact(impact);
    await loadDeltaProfile();
  } else if (id === 'estructura') {
    const [structure, macro, passive, trend, swing, structureDetail, wyckoff] = await Promise.all([
      pedirSobre(q).then(() => delSobre('market_structure', { layers: [] })),
      pedirSobre(q).then(() => delSobre('macro_context', { metrics: [] })),
      pedirSobre(q).then(() => delSobre('passive_flow', { horizons: {} })),
      pedirSobre(q).then(() => delSobre('trend_matrix', { timeframes: {} })),
      pedirSobre(q).then(() => delSobre('swing_score', {})),
      pedirSobre(q).then(() => delSobre('structure_detail', { horizons: {} })),
      pedirSobre(q).then(() => delSobre('wyckoff', { available: false })),
    ]);
    if (symbol !== state.symbol) return;
    state.trend = trend;
    state.swing = swing;
    state.structureDetail = structureDetail;
    state.wyckoff = wyckoff;
    state.lastContextAt = Date.now();
    renderStructure(structure);
    renderMacro(macro);
    renderPassive(passive);
    renderTrend(trend);
    renderSwing(swing);
    renderWyckoff(wyckoff);
    renderStructureLevels(structureDetail, state.dashboard.barriers || {}, wyckoff);
    renderBarriers(state.dashboard.barriers || {});
    presetAnalyzer(state.dashboard.barriers, state.wyckoff);
    renderDecisionBoard(state.dashboard, trend, swing, structureDetail, state.confidence, state.externalMacro);
  } else if (id === 'derivados') {
    const [oi, basis, liq, liqLevels, funding, positioning, oiContexto] = await Promise.all([
      maybe(`/api/oi?symbol=${q}&interval=15min&limit=384`, { rows: [] }),
      pedirSobre(q).then(() => delSobre('basis', {})),
      pedirSobre(q).then(() => delSobre('scalp_liquidations', { matrix: [] })),
      // LOS NIVELES SIGUEN SUELTOS, medido: la ruta sirve DIECISEIS filas con limit=50 y el
      // sobre solo OCHO. renderLiquidationLevels las mapea TODAS, asi que moverla borraria
      // ocho cubos de precio de la tabla.
      maybe(`/api/scalp/liquidation-levels?symbol=${q}&minutes=60&bucket_bps=10&limit=50`, { rows: [] }),
      pedirSobre(q).then(() => delSobre('funding_context', {})),
      pedirSobre(q).then(() => delSobre('positioning', {})),
      // EL REPARTO POR VENUE del OI. No esta en /api/oi: vive en `oi_context` del sobre, que
      // ya se pide una vez por refresco. El panel no lo usaba: cero menciones antes de hoy.
      pedirSobre(q).then(() => delSobre('oi_context', null)),
    ]);
    if (symbol !== state.symbol) return;
    // A renderOiChart se le sigue dando SOLO las filas -no se toca-, y el venue se pinta
    // aparte con la respuesta ENTERA, que es donde el backend lo declara.
    renderOiVenue(oi, oiContexto);
    renderOiChart(filasDe(oi));
    renderBasisDetails(basis);
    renderLiquidations(liq);
    renderLiquidationLevels(liqLevels, (state.dashboard.snapshot || {}).price);
    renderFunding(funding);
    renderPositioning(positioning);
  } else if (id === 'calidad') {
    // Tres niveles distintos y tres fuentes distintas: servicios (healthz), feeds de
    // mercado y metricas publicadas (/api/quality/feeds).
    const [confidence, health, quality] = await Promise.all([
      pedirSobre(q).then(() => sobreConfianza({ rows: [] })),
      maybe('/api/healthz', { status: 'degraded', services: [] }),
      pedirSobre(q).then(() => delSobre('feed_quality', { feeds: [], metrics: [] })),
    ]);
    if (symbol !== state.symbol) return;
    renderQuality(confidence, health);
    renderFeedQuality(quality);
    renderMetricQuality(quality);
  } else if (id === 'replay') {
    // LAS CINCO SE PIDEN AQUI Y NO EN EL RESUMEN: la pestaña se carga a demanda, asi que el
    // arranque del panel no paga por ellas. Se piden con `pedir` -no con `maybe`- porque la
    // banda tiene que poder decir "no se pudo preguntar" en vez de ensenar una tabla vacia.
    const [verdicts, ledger, replay, execution, visibility, scalp] = await Promise.all([
      maybe(`/api/verdicts?symbol=${q}&days=90`, { rows: [] }),
      pedir(`/api/signals/ledger?symbol=${q}`, { observations: [] }),
      pedir(`/api/signals/replay?symbol=${q}`, { frames: [] }),
      pedir(`/api/signals/execution?symbol=${q}`, { snapshots: [] }),
      pedir(`/api/signals/visibility?symbol=${q}`, { certificates: [] }),
      pedir(`/api/scalp/signals?symbol=${q}`, { rows: [] }),
    ]);
    if (symbol !== state.symbol) return;
    renderReplay(verdicts);
    renderAuditoria(ledger, replay, execution, visibility);
    renderScalpHistorial(scalp);
  } else if (id === 'contexto') {
    const [daily, macro, externalMacro, divergences] = await Promise.all([
      maybe(`/api/daily?symbol=${q}&days=60`, { rows: [], streak: 0 }),
      pedirSobre(q).then(() => delSobre('macro_context', { metrics: [] })),
      pedirSobre(q).then(() => delSobre('external_macro_context', { available: false })),
      pedirSobre(q).then(() => delSobre('divergences', { available: false, windows: {} })),
    ]);
    if (symbol !== state.symbol) return;
    const setup = state.dashboard.setup || { setups: [] };
    renderSetups(setup);
    renderMacro(macro);
    state.externalMacro = externalMacro;
    renderExternalMacro(externalMacro);
    renderMarketMemory(state.dashboard.market_memory || {});
    renderMarketReading(state.dashboard.cvd_swing, state.trend, state.swing, divergences, state.confidence, setup);
    renderDaily(daily);
    renderDivergences(divergences);
    // Del sobre que esta vista YA pidio arriba: no abren peticion nueva.
    renderCrossAsset();
    renderVolatilidad();
    renderInvalida();
    renderPerfilVolumen();
    renderLiqBurst();
    renderHealth(state.health);
  }
  state.viewLoadedAt[id] = Date.now();
}
