'use strict';
// rango, wyckoff, tendencia, swing, sesion y divergencias
// Trozo 11 de 11 del panel. Sale de static/app.js SIN TOCAR UNA LINEA DE LOGICA
// (FASE 2, 2026-09-13): lineas 3624-4430 del fichero original.
// El orden de los <script defer> de index.html ES el orden de este fichero: no se
// reordena nada, porque en scripts clasicos un `const` de primer nivel solo existe a
// partir del script que lo declara.
// ---------------- Validador de rango (fase 2) ----------------
const RANGE_VERDICT = {
  rango: ['positive', 'Es un rango'],
  rango_en_formacion: ['neutral', 'Rango en formación'],
  no_es_rango: ['negative', 'No es un rango'],
};

function clearRange() {
  const body = $('range-body');
  if (body) body.replaceChildren();
  const sub = $('range-sub');
  if (sub) sub.textContent = 'Cinco pruebas con umbral medido';
}

function rangeEmpty(text) {
  const body = $('range-body');
  if (!body) return;
  const div = document.createElement('div');
  div.className = 'zone-empty';
  div.textContent = text;
  body.replaceChildren(div);
}

function renderRange(result) {
  const body = $('range-body');
  if (!body) return;
  body.replaceChildren();
  if (!result.available) {
    rangeEmpty(result.reason || 'Sin datos suficientes para juzgar el tramo.');
    return;
  }
  const [cls, label] = RANGE_VERDICT[result.verdict] || ['neutral', '—'];

  const head = document.createElement('div');
  head.className = `range-verdict ${cls}`;
  head.textContent = label;
  const score = document.createElement('div');
  score.className = 'range-score';
  score.textContent = `${result.passed} de ${result.evaluated} pruebas superadas `
    + `(se piden ${result.required}) · ${result.from} → ${result.to} · ${result.bars} sesiones · `
    + `altura ${number(result.range.height_pct, 1)}%`;
  body.append(head, score);

  for (const test of safeArray(result.tests)) {
    const row = document.createElement('div');
    row.className = 'range-test';
    // Un test no medible NO es un test fallado: se marca aparte para no contarlo en contra.
    const unavailable = test.status === 'unavailable';
    const cls2 = unavailable ? 'neutral' : test.passed ? 'positive' : 'negative';
    const mark = document.createElement('span');
    mark.className = `range-test-mark ${cls2}`;
    mark.textContent = unavailable ? '○' : test.passed ? '✓' : '✗';

    const middle = document.createElement('div');
    const name = document.createElement('div');
    name.className = 'range-test-label';
    name.textContent = test.label + (unavailable ? ' · sin dato' : '');
    const reading = document.createElement('div');
    reading.className = 'range-test-reading';
    reading.textContent = test.reading || '';
    const why = document.createElement('div');
    why.className = 'range-test-why';
    why.textContent = test.why || '';
    middle.append(name, reading, why);

    const value = document.createElement('span');
    value.className = `range-test-value ${cls2}`;
    value.textContent = unavailable
      ? '—'
      : `${number(test.value, 2)} ${test.operator} ${number(test.threshold, 2)}`;

    row.append(mark, middle, value);
    body.append(row);
  }

  for (const line of safeArray(result.narrative)) {
    const note = document.createElement('div');
    note.className = 'range-note';
    note.textContent = line;
    body.append(note);
  }
  if (result.invalidation) {
    const inval = document.createElement('div');
    inval.className = 'range-note negative';
    inval.textContent = result.invalidation;
    body.append(inval);
  }

  const sub = $('range-sub');
  if (sub) {
    sub.textContent = `${result.passed}/${result.evaluated} pruebas · `
      + (result.mode === 'fechas' ? `${result.start_date} → ${result.end_date}` : `${result.window_days} sesiones`);
  }
}

async function submitRange(event) {
  if (event) event.preventDefault();
  const low = asNumber(($('range-low') || {}).value);
  const high = asNumber(($('range-high') || {}).value);
  const start = (($('range-start') || {}).value || '').trim();
  const end = (($('range-end') || {}).value || '').trim();
  if (low === null || high === null || low <= 0 || high <= low) {
    rangeEmpty('Introduce un suelo y un techo válidos, con el suelo por debajo.');
    return;
  }
  // Las fechas van juntas o no van: una sola dejaría el tramo a medio definir.
  if (Boolean(start) !== Boolean(end)) {
    rangeEmpty('Indica las dos fechas, o ninguna para usar las últimas 180 sesiones.');
    return;
  }
  if (start && end && start >= end) {
    rangeEmpty('La fecha inicial debe ser anterior a la final.');
    return;
  }
  rangeEmpty('Validando…');
  let query = `symbol=${encodeURIComponent(state.symbol)}&low=${low}&high=${high}`;
  query += start && end ? `&start_date=${start}&end_date=${end}` : '&days=180';
  const result = await maybe(`/api/range/validate?${query}`, null);
  if (!result) {
    rangeEmpty('No se pudo validar el tramo. Revisa el panel de salud de datos.');
    return;
  }
  renderRange(result);
}

// ---------------- Wyckoff automatico ----------------
const WYCKOFF_LABEL = {
  compatible_con_acumulacion: 'Compatible con acumulación',
  compatible_con_distribucion: 'Compatible con distribución',
  equilibrio_sin_ventaja: 'Equilibrio sin ventaja',
};

function renderWyckoff(result) {
  const body = $('wyckoff-body');
  if (!body) return;
  body.replaceChildren();
  const sub = $('wyckoff-sub');
  if (!result || !result.available) {
    const empty = document.createElement('div');
    empty.className = 'zone-empty';
    empty.textContent = (result && result.reason) || 'No hay un rango reciente que supere las pruebas mínimas.';
    body.append(empty);
    if (sub) sub.textContent = 'Sin rango automático válido';
    return;
  }

  const range = result.range || {};
  const bias = result.bias || {};
  const phase = result.phase || {};
  const validation = range.validation || {};
  const biasClass = bias.bias === 'bullish' ? 'positive' : bias.bias === 'bearish' ? 'negative' : 'neutral';
  const head = document.createElement('div');
  head.className = 'wyckoff-head';
  const verdict = document.createElement('div');
  const title = document.createElement('div');
  title.className = `wyckoff-verdict ${biasClass}`;
  title.textContent = `${WYCKOFF_LABEL[bias.reading] || 'Lectura neutral'} · ${number(bias.score, 0)}/100`;
  const phaseText = document.createElement('div');
  phaseText.className = 'wyckoff-phase';
  phaseText.textContent = `Fase ${phase.code || '—'} · ${(phase.state || 'sin fase').replaceAll('_', ' ')}. ${phase.explanation || ''}`;
  verdict.append(title, phaseText);

  const rangeGrid = document.createElement('div');
  rangeGrid.className = 'wyckoff-range';
  const rangeItems = [
    ['Soporte', money(range.low, 2)],
    ['Mitad', money(range.mid, 2)],
    ['Resistencia', money(range.high, 2)],
    ['Validación', `${validation.passed || 0}/${validation.evaluated || 0} pruebas`],
  ];
  for (const [label, value] of rangeItems) {
    const item = document.createElement('div');
    const small = document.createElement('span');
    small.textContent = label;
    const strong = document.createElement('strong');
    strong.textContent = value;
    item.append(small, strong);
    rangeGrid.append(item);
  }
  head.append(verdict, rangeGrid);
  body.append(head);

  const components = document.createElement('div');
  components.className = 'wyckoff-components';
  for (const component of safeArray(bias.components)) {
    const card = document.createElement('div');
    const contribution = asNumber(component.contribution);
    card.className = `wyckoff-component ${component.status === 'unavailable' ? 'neutral' : signClass(contribution)}`;
    const value = document.createElement('strong');
    value.textContent = component.status === 'unavailable'
      ? '—'
      : `${contribution > 0 ? '+' : ''}${number(contribution, 1)}`;
    const label = document.createElement('span');
    label.textContent = `${component.label}${component.status === 'unavailable' ? ' · sin dato' : ''}. ${component.detail || ''}`;
    card.append(value, label);
    components.append(card);
  }
  body.append(components);

  const events = safeArray(result.events);
  if (events.length) {
    const eventList = document.createElement('div');
    eventList.className = 'wyckoff-events';
    for (const event of events.slice(-5)) {
      const chip = document.createElement('span');
      chip.className = `wyckoff-event ${event.direction === 'bullish' ? 'positive' : 'negative'}`;
      chip.textContent = `${event.date} · ${event.type}${event.volume_multiple ? ` · vol ${number(event.volume_multiple, 1)}x` : ''}`;
      chip.title = event.detail || '';
      eventList.append(chip);
    }
    body.append(eventList);
  }

  const plan = document.createElement('div');
  plan.className = 'wyckoff-plan';
  for (const [label, text] of [
    ['Dentro del rango', (result.trade_map || {}).inside_range],
    ['Confirmación long', (result.trade_map || {}).long_confirmation],
    ['Confirmación short', (result.trade_map || {}).short_confirmation],
  ]) {
    const item = document.createElement('div');
    const strong = document.createElement('strong');
    strong.textContent = `${label}: `;
    item.append(strong, text || '—');
    plan.append(item);
  }
  body.append(plan);

  const chartButton = document.createElement('button');
  chartButton.type = 'button';
  chartButton.className = 'wyckoff-chart-button';
  chartButton.textContent = 'Ver rango completo en la gráfica diaria';
  chartButton.addEventListener('click', () => {
    setPriceMode('wyckoff');
    const chart = $('price-chart');
    if (chart) chart.scrollIntoView({ behavior: 'smooth', block: 'center' });
  });
  body.append(chartButton);
  if (sub) {
    sub.textContent = `${range.from} → ${range.to} · ${range.bars} sesiones · `
      + `${number((result.current || {}).position_pct, 0)}% de la altura`;
  }
}

function renderTrend(result) {
  const body = $('trend-body');
  if (!body) return;
  body.replaceChildren();
  const bcl = b => b === 'alcista' ? 'positive' : (b === 'bajista' ? 'negative' : 'neutral');
  const slbl = s => s === 'HH_HL' ? 'HH/HL' : (s === 'LH_LL' ? 'LH/LL' : (s ? 'Mixta' : '\u2014'));
  const scl = s => s === 'HH_HL' ? 'positive' : (s === 'LH_LL' ? 'negative' : 'neutral');
  const pn = (v, pos, neg) => (v == null) ? ['\u2014', 'neutral'] : (v > 0 ? [pos, 'positive'] : (v < 0 ? [neg, 'negative'] : ['~', 'neutral']));
  // El flujo intradia se etiqueta por el estado de AMBAS patas, no por el signo del
  // diferencial: spot y futuros pueden estar comprando los dos y el diff salir negativo.
  const FLOW_LABEL = {
    spot_y_futuros_compran: ['Ambas compran', 'positive'],
    spot_y_futuros_venden: ['Ambas venden', 'negative'],
    spot_compra_futuros_vende: ['Spot compra / Fut vende', 'neutral'],
    spot_vende_futuros_compra: ['Spot vende / Fut compra', 'neutral'],
    una_pata_plana: ['Una pata plana', 'neutral'],
    cvd_spot_comprador: ['Spot +', 'positive'],
    cvd_spot_vendedor: ['Spot \u2212', 'negative'],
    cvd_spot_plano: ['Spot ~', 'neutral'],
    sin_datos: ['\u2014', 'neutral'],
  };
  for (const [tf, r] of Object.entries(result.timeframes || {})) {
    const tr = document.createElement('tr');
    // Misma tabla, distinto ENFASIS segun el perfil: en swing manda 3d/1d/8h y en intradia
    // 4h/1h. Los numeros no cambian; cambia cual se lee primero.
    markProfileLayer(tr, tf);
    const flow = FLOW_LABEL[r.flow_state] || (r.cvd_spot == null
      ? pn(r.cvd_diff, 'Diff +', 'Diff \u2212')
      : pn(r.cvd_spot, 'Spot +', 'Spot \u2212'));
    const oi = pn(r.oi_change_pct, 'OI \u2191', 'OI \u2193');
    const mo = pn(r.momentum_pct, '\u2191', '\u2193');
    td(tr, tf, '');
    td(tr, slbl(r.structure), scl(r.structure));
    td(tr, flow[0], flow[1]);
    td(tr, oi[0], oi[1]);
    td(tr, mo[0], mo[1]);
    td(tr, (r.bias || '').toUpperCase(), bcl(r.bias));
    body.append(tr);
  }
  const sub = document.getElementById('trend-sub');
  if (sub && result.medium_term_alignment) sub.textContent = 'Mediano (4h\u00b78h\u00b71D): ' + result.medium_term_alignment.toUpperCase();
}

function renderStructureLevels(sd, barriers, wyckoff) {
  try {
    const priceSeries = state.series.price;
    if (!priceSeries) return;
    for (const line of state.priceLines || []) {
      try { priceSeries.removePriceLine(line); } catch (_) {}
    }
    state.priceLines = [];
    const add = (price, color, title, style = 2) => {
      if (asNumber(price) === null) return;
      try {
        state.priceLines.push(priceSeries.createPriceLine({
          price: asNumber(price), color, lineWidth: 1, lineStyle: style,
          axisLabelVisible: true, title,
        }));
      } catch (_) {}
    };

    const range = wyckoff && wyckoff.available ? wyckoff.range || {} : null;
    if (range) {
      add(range.low, COLORS.green, 'WYK soporte', 0);
      add(range.high, COLORS.red, 'WYK resistencia', 0);
      if (state.priceMode === 'wyckoff') add(range.mid, COLORS.amber, 'WYK mitad', 2);
    }

    const horizon = ((sd && sd.horizons) || {})['4h'];
    if (state.priceMode === 'intraday') {
      if (horizon) {
        add(horizon.bos_level, COLORS.green, 'BOS 4h');
        add(horizon.choch_level, COLORS.amber, 'CHoCH 4h');
        add(horizon.invalidation_level, COLORS.red, 'Invalid 4h');
      }
      const support = barriers && barriers.nearest_support;
      const resistance = barriers && barriers.nearest_resistance;
      if (support && asNumber(support.distance_pct) <= 5) add(support.center, COLORS.green, `S ${number(support.score, 0)}`);
      if (resistance && asNumber(resistance.distance_pct) <= 5) add(resistance.center, COLORS.red, `R ${number(resistance.score, 0)}`);
    }

    const markers = [];
    if (state.priceMode === 'wyckoff') {
      for (const event of safeArray(wyckoff && wyckoff.events)) {
        markers.push({
          time: ts(event.date),
          position: event.type === 'spring' ? 'belowBar' : 'aboveBar',
          color: event.type === 'spring' ? COLORS.green : COLORS.red,
          shape: 'circle',
          text: event.type === 'spring' ? 'Spring' : 'UT',
        });
      }
    } else if (horizon) {
      const push = (swing, text, color, position) => {
        if (swing && swing.timestamp && swing.price != null) markers.push({ time: ts(swing.timestamp), position, color, shape: 'circle', text });
      };
      push(horizon.previous_swing_high, '', COLORS.green, 'aboveBar');
      push(horizon.last_swing_high, 'HH', COLORS.green, 'aboveBar');
      push(horizon.previous_swing_low, '', COLORS.amber, 'belowBar');
      push(horizon.last_swing_low, 'HL', COLORS.amber, 'belowBar');
    }
    markers.sort((a, b) => a.time - b.time);
    if (state.priceMarkers && state.priceMarkers.setMarkers) state.priceMarkers.setMarkers(markers);
    else if (window.LightweightCharts && LightweightCharts.createSeriesMarkers) state.priceMarkers = LightweightCharts.createSeriesMarkers(priceSeries, markers);
  } catch (_) {}
}

function renderSwing(result) {
  const body = $('swing-body');
  if (!body) return;
  const bias = ['LONG', 'SHORT'].includes(result.bias) ? result.bias : 'NEUTRAL';
  const biasClass = bias === 'LONG' ? 'positive' : bias === 'SHORT' ? 'negative' : 'neutral';
  const longShare = Math.min(100, Math.max(0, asNumber(result.long_share_pct) ?? 50));
  body.replaceChildren();

  const overview = document.createElement('div');
  overview.className = 'swing-overview';
  const gauge = document.createElement('div');
  gauge.className = 'swing-gauge';
  gauge.style.setProperty('--long-share', `${longShare * 3.6}deg`);
  const gaugeContent = document.createElement('div');
  gaugeContent.className = 'swing-gauge-content';
  const gaugeBias = document.createElement('strong');
  gaugeBias.className = biasClass;
  gaugeBias.textContent = bias;
  const gaugeScore = document.createElement('span');
  gaugeScore.textContent = `score ${number(result.score, 0)}`;
  gaugeContent.append(gaugeBias, gaugeScore);
  gauge.append(gaugeContent);

  const reading = document.createElement('div');
  const balance = document.createElement('div');
  balance.className = 'swing-balance';
  // Las cuotas reparten el peso TOTAL: la parte sin senal se ve en vez de esconderse. Antes
  // long_share salia de lp/(lp+sp) y con un solo componente activo pintaba "100% long".
  const shortShare = asNumber(result.short_share_pct);
  const neutralShare = asNumber(result.neutral_share_pct);
  balance.textContent = (shortShare === null || neutralShare === null)
    ? `${Math.round(longShare)}% long · ${Math.round(100 - longShare)}% short`
    : `${Math.round(longShare)}% long · ${Math.round(shortShare)}% short · ${Math.round(neutralShare)}% sin señal`;
  const conviction = document.createElement('div');
  conviction.className = 'swing-conviction';
  const convictionValue = document.createElement('strong');
  convictionValue.className = biasClass;
  convictionValue.textContent = result.conviction || 'sin convicción';
  conviction.append('Convicción: ', convictionValue);
  if (result.horizon) conviction.append(` · ${result.horizon}`);
  reading.append(balance, conviction);
  const coverage = asNumber(result.evidence_coverage_pct);
  if (coverage !== null) {
    const cov = document.createElement('div');
    cov.className = `swing-coverage ${coverage < 50 ? 'negative' : 'neutral'}`;
    cov.textContent = `Evidencia medible: ${Math.round(coverage)}% del peso`
      + (coverage < 50 ? ' · convicción degradada por falta de datos' : '');
    reading.append(cov);
  }
  const conflicts = safeArray(result.conflicts);
  if (conflicts.length) {
    const warn = document.createElement('div');
    warn.className = 'swing-conflicts negative';
    warn.textContent = `Señales en conflicto: ${conflicts.join(', ')}`;
    reading.append(warn);
  }
  overview.append(gauge, reading);
  body.append(overview);

  const components = document.createElement('div');
  components.className = 'swing-components';
  for (const component of safeArray(result.components)) {
    // Contribucion ausente no es contribucion nula: se marca sin-dato y no dibuja barra.
    const contribution = asNumber(component.contribution);
    const direction = contribution === null ? 'sin-dato' : contribution > 0 ? 'long' : contribution < 0 ? 'short' : 'neutral';
    const width = contribution === null ? 0 : Math.min(50, Math.abs(contribution) / 25 * 50);
    const row = document.createElement('div');
    row.className = 'swing-component';
    if (component.why) row.title = String(component.why);
    const name = document.createElement('span');
    name.className = 'swing-component-name';
    // Un 0 puede ser "medido y neutral", "las sub-senales se contradicen" o "no hay dato".
    // Sin esta marca los tres se veian igual en el panel.
    const STATUS_TAG = { unavailable: ' · sin dato', conflict: ' · conflicto', partial: ' · parcial' };
    name.textContent = (component.name || '—') + (STATUS_TAG[component.status] || '');
    const track = document.createElement('span');
    track.className = 'evidence-track';
    const fill = document.createElement('span');
    fill.className = `evidence-fill ${direction}`;
    fill.style.left = contribution < 0 ? `${50 - width}%` : '50%';
    fill.style.width = `${width}%`;
    track.append(fill);
    const value = document.createElement('span');
    value.className = `swing-component-value ${direction === 'long' ? 'positive' : direction === 'short' ? 'negative' : 'neutral'}`;
    value.textContent = component.status === 'unavailable'
      ? '—'
      : `${contribution > 0 ? '+' : ''}${number(contribution, 1)}`;
    row.append(name, track, value);
    components.append(row);
  }
  body.append(components);
  const sub = $('swing-sub');
  if (sub) sub.textContent = `${bias} · ${result.conviction || 'sin convicción'}`;
}
// CVD mide órdenes agresivas ejecutadas; una sesión no demuestra acumulación institucional.
// Los nombres se limitan al hecho observable: quién compró/vendió en cada pata.
function flowQuadrant(row) {
  const spot = asNumber(row.cvd_spot_usd);
  const futures = asNumber(row.cvd_fut_usd);
  if (spot === null || futures === null || spot === 0 || futures === 0) return { key: 'sd', label: '—', color: '#5b6673', cls: 'neutral' };
  if (spot > 0 && futures > 0) return { key: 'ambos_compran', label: 'Ambos compraron', color: COLORS.green, cls: 'positive' };
  if (spot < 0 && futures < 0) return { key: 'ambos_venden', label: 'Ambos vendieron', color: COLORS.red, cls: 'negative' };
  if (spot > 0) return { key: 'spot_compra', label: 'Spot compró · futuros vendieron', color: COLORS.cyan, cls: 'neutral' };
  return { key: 'futuros_compran', label: 'Spot vendió · futuros compraron', color: COLORS.amber, cls: 'neutral' };
}
const QUADRANT_COLOR = { ambos_compran: COLORS.green, ambos_venden: COLORS.red, spot_compra: COLORS.cyan, futuros_compran: COLORS.amber };
const SESSION_RESPONSE = {
  venta_sin_caida: { label: 'Venta sin caída · posible defensa', cls: 'positive', detail: 'Spot y futuros vendieron, pero el precio no cayó. Es compatible con absorción compradora; una sesión aislada no la confirma.' },
  venta_con_caida: { label: 'Venta con seguimiento', cls: 'negative', detail: 'Spot y futuros vendieron y el precio cayó: la oferta sí produjo desplazamiento.' },
  compra_sin_subida: { label: 'Compra sin subida · posible oferta', cls: 'negative', detail: 'Spot y futuros compraron, pero el precio no subió. Es compatible con absorción vendedora; una sesión aislada no la confirma.' },
  compra_con_subida: { label: 'Compra con seguimiento', cls: 'positive', detail: 'Spot y futuros compraron y el precio subió: la demanda sí produjo desplazamiento.' },
  flujo_dividido: { label: 'Flujo dividido', cls: 'neutral', detail: 'Spot y futuros ejecutaron en direcciones opuestas; no hay consenso de agresión.' },
};
function sessionResponse(row) {
  return SESSION_RESPONSE[row.price_response] || { label: '—', cls: 'neutral', detail: 'Sin datos suficientes para comparar flujo y respuesta del precio.' };
}

// OHLC de LA MISMA sesión que alimenta la barra de flujo. Una vela incompleta o
// geométricamente imposible se omite: nunca se rellena con 0, close, nearest ni interpolación.
function sessionOhlc(row) {
  const open = asNumber(row && row.price_open);
  const high = asNumber(row && row.price_high);
  const low = asNumber(row && row.price_low);
  const close = asNumber(row && row.price_close);
  const values = [open, high, low, close];
  if (values.some(value => value === null || value <= 0)) return null;
  if (high < low || high < open || high < close || low > open || low > close) return null;
  return { open, high, low, close };
}

// Escala común para las 24 sesiones visibles. Solo participan velas OHLC completas.
// El padding es exclusivamente visual; no crea muestras ni altera los precios.
function sessionPriceDomain(rows) {
  const candles = safeArray(rows).map(sessionOhlc);
  const valid = candles.filter(candle => candle !== null);
  if (!valid.length) return null;
  const observedLow = Math.min(...valid.map(candle => candle.low));
  const observedHigh = Math.max(...valid.map(candle => candle.high));
  const observedSpan = observedHigh - observedLow;
  const reference = Math.max(Math.abs(observedLow), Math.abs(observedHigh), 1);
  const pad = observedSpan > 0 ? observedSpan * 0.08 : reference * 0.005;
  return {
    min: observedLow - pad,
    max: observedHigh + pad,
    observed_low: observedLow,
    observed_high: observedHigh,
    present: valid.length,
    missing: candles.length - valid.length,
  };
}

function appendSessionColumnGuides(svg, count, NS) {
  if (!count) return;
  const width = 100 / count;
  for (let index = 1; index < count; index++) {
    const guide = document.createElementNS(NS, 'line');
    const x = index * width;
    guide.setAttribute('x1', String(x));
    guide.setAttribute('y1', '0');
    guide.setAttribute('x2', String(x));
    guide.setAttribute('y2', '100');
    guide.setAttribute('class', 'session-column-guide');
    svg.append(guide);
  }
}

function renderDailyBars(daily) {
  const b = $('dailybars-body');
  if (!b) return;
  const rows = safeArray(daily && daily.rows).slice(-24);
  if (!rows.length) { b.replaceChildren(); return; }

  const n = rows.length;
  const W = 100 / n;
  const NS = 'http://www.w3.org/2000/svg';
  const priceDomain = sessionPriceDomain(rows);

  // ---------------- precio OHLC ----------------
  // Es un track independiente, pero usa EXACTAMENTE los mismos n slots que el flujo.
  // Por eso vela i y barra i representan la misma session_date sin hacer joins en frontend.
  const stack = document.createElement('div');
  stack.className = 'session-map-stack';

  const priceTrack = document.createElement('section');
  priceTrack.className = 'session-map-track session-price-track';
  const priceHead = document.createElement('div');
  priceHead.className = 'session-map-track-head';
  const priceLabel = document.createElement('strong');
  priceLabel.textContent = 'Precio por sesión';
  const priceMeta = document.createElement('span');
  priceMeta.textContent = priceDomain
    ? `OHLC 09:30 ET → 09:30 ET · rango ${money(priceDomain.observed_low, 2)} – ${money(priceDomain.observed_high, 2)} · ${priceDomain.present}/${n} completas`
    : 'OHLC 09:30 ET → 09:30 ET · sin velas completas';
  priceHead.append(priceLabel, priceMeta);
  priceTrack.append(priceHead);

  if (priceDomain) {
    const priceSvg = document.createElementNS(NS, 'svg');
    priceSvg.setAttribute('viewBox', '0 0 100 100');
    priceSvg.setAttribute('preserveAspectRatio', 'none');
    priceSvg.setAttribute('width', '100%');
    priceSvg.setAttribute('height', '102');
    priceSvg.setAttribute('class', 'session-price-svg');
    priceSvg.setAttribute('role', 'img');
    priceSvg.setAttribute('aria-label', 'Precio OHLC por sesión, alineado con el flujo inferior');
    appendSessionColumnGuides(priceSvg, n, NS);

    const scaleSpan = priceDomain.max - priceDomain.min;
    const yOf = price => 94 - ((price - priceDomain.min) / scaleSpan) * 88;

    rows.forEach((row, index) => {
      const candle = sessionOhlc(row);
      if (!candle) return;
      const iso = String(row.session_date || '');
      const q = flowQuadrant(row);
      const response = sessionResponse(row);
      const centerX = (index + 0.5) * W;
      const bodyWidth = Math.max(0.45, W * 0.48);
      const openY = yOf(candle.open);
      const closeY = yOf(candle.close);
      const highY = yOf(candle.high);
      const lowY = yOf(candle.low);
      const rawBodyHeight = Math.abs(closeY - openY);
      const bodyHeight = Math.max(rawBodyHeight, 1.25);
      const bodyCenterY = (openY + closeY) / 2;
      const bodyY = Math.min(94 - bodyHeight, Math.max(6, bodyCenterY - bodyHeight / 2));
      const direction = candle.close > candle.open ? 'up' : candle.close < candle.open ? 'down' : 'flat';

      const group = document.createElementNS(NS, 'g');
      group.setAttribute('class', `session-price-candle ${direction}`);
      group.setAttribute('data-session-date', iso);

      const wick = document.createElementNS(NS, 'line');
      wick.setAttribute('x1', String(centerX));
      wick.setAttribute('x2', String(centerX));
      wick.setAttribute('y1', String(highY));
      wick.setAttribute('y2', String(lowY));
      wick.setAttribute('class', 'session-price-wick');

      const body = document.createElementNS(NS, 'rect');
      body.setAttribute('x', String(centerX - bodyWidth / 2));
      body.setAttribute('y', String(bodyY));
      body.setAttribute('width', String(bodyWidth));
      body.setAttribute('height', String(bodyHeight));
      body.setAttribute('class', 'session-price-body');

      const tip = document.createElementNS(NS, 'title');
      const sessionReturn = (candle.close / candle.open - 1) * 100;
      tip.textContent = `${iso} · OHLC de la misma sesión`
        + `\nO ${money(candle.open, 2)} · H ${money(candle.high, 2)} · L ${money(candle.low, 2)} · C ${money(candle.close, 2)}`
        + `\nRetorno ${pct(sessionReturn)}`
        + `\nFlujo ${q.label}`
        + `\nRespuesta ${response.label}`;
      group.append(wick, body, tip);
      priceSvg.append(group);
    });
    priceTrack.append(priceSvg);
  } else {
    const empty = document.createElement('div');
    empty.className = 'session-map-empty';
    empty.textContent = 'Precio OHLC no disponible para estas sesiones. No se dibuja una línea ni velas sintéticas.';
    priceTrack.append(empty);
  }

  // ---------------- flujo spot/futuros ----------------
  const flowTrack = document.createElement('section');
  flowTrack.className = 'session-map-track session-flow-track';
  const flowHead = document.createElement('div');
  flowHead.className = 'session-map-track-head';
  const flowLabel = document.createElement('strong');
  flowLabel.textContent = 'Flujo spot / futuros';
  const flowMeta = document.createElement('span');
  flowMeta.textContent = 'Mismas columnas y fechas que el precio superior';
  flowHead.append(flowLabel, flowMeta);

  const magnitudes = rows.map(r => ({
    spot: asNumber(r.cvd_spot_usd),
    futures: asNumber(r.cvd_fut_usd),
  }));
  const spotMax = Math.max(1, ...magnitudes.filter(m => m.spot !== null).map(m => Math.abs(m.spot)));
  const futuresMax = Math.max(1, ...magnitudes.filter(m => m.futures !== null).map(m => Math.abs(m.futures)));
  const strengths = magnitudes.map(m => (m.spot === null && m.futures === null ? null : Math.max(
    m.spot === null ? 0 : Math.abs(m.spot) / spotMax,
    m.futures === null ? 0 : Math.abs(m.futures) / futuresMax,
  )));
  const counts = { ambos_compran: 0, ambos_venden: 0, spot_compra: 0, futuros_compran: 0, sd: 0 };

  const flowSvg = document.createElementNS(NS, 'svg');
  flowSvg.setAttribute('viewBox', '0 0 100 100');
  flowSvg.setAttribute('preserveAspectRatio', 'none');
  flowSvg.setAttribute('width', '100%');
  flowSvg.setAttribute('height', '110');
  flowSvg.setAttribute('class', 'session-flow-svg');
  flowSvg.setAttribute('role', 'img');
  flowSvg.setAttribute('aria-label', 'Flujo spot y futuros por sesión');
  appendSessionColumnGuides(flowSvg, n, NS);

  const zero = document.createElementNS(NS, 'line');
  for (const [k, val] of [['x1', 0], ['y1', 50], ['x2', 100], ['y2', 50]]) zero.setAttribute(k, String(val));
  zero.setAttribute('class', 'session-flow-zero');
  flowSvg.append(zero);

  // Las fechas van en HTML aparte: preserveAspectRatio="none" deformaría texto SVG.
  const dates = document.createElement('div');
  dates.className = 'bars-dates';
  dates.style.gridTemplateColumns = `repeat(${n}, minmax(0, 1fr))`;

  for (let i = 0; i < n; i++) {
    const row = rows[i];
    const q = flowQuadrant(row);
    const response = sessionResponse(row);
    counts[q.key] += 1;
    const iso = String(row.session_date || '');
    const spotUsd = magnitudes[i].spot;

    // Sin CVD spot no hay barra direccional. Nunca Number(null) -> 0.
    if (strengths[i] !== null && spotUsd !== null) {
      const hh = strengths[i] * 46;
      const y = spotUsd >= 0 ? (50 - hh) : 50;
      const rect = document.createElementNS(NS, 'rect');
      rect.setAttribute('x', String(i * W + 0.4));
      rect.setAttribute('y', String(y));
      rect.setAttribute('width', String(W - 0.8));
      rect.setAttribute('height', String(hh));
      rect.setAttribute('fill', q.color);
      rect.setAttribute('class', `session-flow-bar ${q.key}`);
      rect.setAttribute('data-session-date', iso);

      const candle = sessionOhlc(row);
      const priceDetail = candle
        ? `OHLC ${money(candle.open, 2)} / ${money(candle.high, 2)} / ${money(candle.low, 2)} / ${money(candle.close, 2)}`
        : 'OHLC N/D';
      const tip = document.createElementNS(NS, 'title');
      tip.textContent = `${iso} · ${q.label}`
        + `\nSpot ${money(row.cvd_spot_usd)} · Fut ${money(row.cvd_fut_usd)}`
        + `\n${priceDetail} · retorno ${pct(row.price_chg_pct)}`
        + `\n${response.label}: ${response.detail}`;
      rect.append(tip);
      flowSvg.append(rect);
    }

    const cell = document.createElement('span');
    cell.title = iso;
    const long = document.createElement('b');
    long.className = 'd-full';
    long.textContent = iso.slice(5);
    const short = document.createElement('b');
    short.className = 'd-short';
    short.textContent = iso.slice(8);
    cell.append(long, short);
    dates.append(cell);
  }

  flowTrack.append(flowHead, flowSvg);
  stack.append(priceTrack, flowTrack);

  const legend = document.createElement('div');
  legend.className = 'bars-legend';
  for (const [key, text] of [
    ['ambos_compran', 'Ambos compraron'],
    ['ambos_venden', 'Ambos vendieron'],
    ['spot_compra', 'Spot compró / futuros vendieron'],
    ['futuros_compran', 'Spot vendió / futuros compraron'],
  ]) {
    const item = document.createElement('span');
    const dot = document.createElement('i');
    dot.style.background = QUADRANT_COLOR[key];
    item.append(dot, `${text}: ${counts[key]}`);
    legend.append(item);
  }

  const caption = document.createElement('div');
  caption.className = 'bars-caption';
  const first = String(rows[0].session_date || '');
  const last = String(rows[n - 1].session_date || '');
  caption.textContent = `Mapeo 1:1: cada vela superior y cada barra inferior comparten exactamente la misma columna y session_date (09:30 ET → 09:30 ET). `
    + `La vela muestra la respuesta REAL del precio; el color del flujo no la predice. `
    + `Sobre el eje = spot comprador; bajo el eje = spot vendedor. La altura del flujo compara cada pata contra su propio máximo de 24 sesiones para que el mayor volumen del perp no oculte al spot. `
    + `El color indica si futuros acompañó o se opuso; no etiqueta acumulación institucional. ${n} sesiones, ${first} a ${last}.`;

  // Un solo eje de fechas debajo de ambos tracks deja inequívoco el mapeo columna a columna.
  b.replaceChildren(stack, dates, legend, caption);
  const sub = $('dailybars-sub');
  if (sub) sub.textContent = `${counts.ambos_compran} compra conjunta · ${counts.ambos_venden} venta conjunta · ${counts.spot_compra + counts.futuros_compran} desacuerdo · OHLC ${priceDomain ? `${priceDomain.present}/${n}` : '0/' + n}`;
}
function renderDivergences(result) {
  const body = $('divergence-body');
  if (!body) return;
  body.replaceChildren();
  const names = {
    '9m': '9 min', '15m': '15 min', '1h': '1 hora', '2h': '2 horas', '4h': '4 horas', '8h': '8 horas', '16h': '16 horas',
    '1d': '1 d\u00eda', '2d': '2 d\u00edas', '3d': '3 d\u00edas', '6d': '6 d\u00edas', '9d': '9 d\u00edas', '2s': '2 semanas', '4s': '4 semanas', '6s': '6 semanas',
  };
  const groupRow = (text, hint) => {
    const tr = document.createElement('tr');
    tr.className = 'group-row';
    const cell = document.createElement('td');
    cell.colSpan = 5;
    cell.textContent = text;
    if (hint) cell.title = hint;
    tr.append(cell);
    body.append(tr);
  };
  const divergenceRow = (key, w, opts) => {
    const tr = document.createElement('tr');
    const nameCell = td(tr, names[key] || key, '');
    if (!w.available) {
      nameCell.className = 'neutral';
      td(tr, opts.missing(w), 'neutral');
      td(tr, '\u2014', 'neutral'); td(tr, '\u2014', 'neutral'); td(tr, '\u2014', 'neutral');
      body.append(tr);
      return;
    }
    const weak = opts.weak(w);
    if (weak) { nameCell.className = 'neutral'; nameCell.title = opts.weakHint; }
    const cls = w.divergence === 'alcista' ? 'positive' : w.divergence === 'bajista' ? 'negative' : 'neutral';
    td(tr, pct(w.price_change_pct), signClass(w.price_change_pct));
    td(tr, money(w.cvd_spot_change_usd), signClass(w.cvd_spot_change_usd));
    const divCell = td(tr, w.divergence === 'sin_divergencia' ? 'ninguna' : w.divergence, weak ? 'neutral' : cls);
    divCell.title = opts.hint(w);
    td(tr, w.reading || '\u2014', 'neutral');
    body.append(tr);
  };

  const intraday = (result && result.intraday) || {};
  if (intraday.available) {
    groupRow(`Intrad\u00eda \u00b7 velas 1 min \u00b7 retraso ${number(intraday.lag_seconds, 0)} s`,
      'El CVD spot espera la ventana de trades tard\u00edos, por eso las ventanas se anclan al \u00faltimo minuto con ambas series');
    for (const [key, w] of Object.entries(intraday.windows || {})) {
      divergenceRow(key, w, {
        missing: v => `faltan velas (${v.bars}/${v.required})`,
        weak: v => v.freshness === 'stale' || v.above_noise === false,
        weakHint: 'El retraso pesa demasiado en esta ventana, o el movimiento no supera su propio ruido',
        hint: v => v.above_noise === false
          ? `Movimiento (${number(v.price_change_pct, 3)}%) por debajo del ruido de la ventana (${number(v.noise_threshold_pct, 3)}%)`
          : `Por pendiente de regresi\u00f3n \u00b7 frescura ${v.freshness}`,
      });
    }
  }
  groupRow('Por sesiones NYSE', 'Una sesi\u00f3n va de 09:30 ET a 09:30 ET');
  for (const [key, w] of Object.entries((result && result.windows) || {})) {
    divergenceRow(key, w, {
      missing: v => `faltan sesiones (${v.sessions}/${v.required})`,
      weak: v => !v.sustained,
      weakHint: 'Observaci\u00f3n puntual, no divergencia sostenida',
      hint: v => v.method === 'pendiente' ? 'Por pendiente de regresi\u00f3n sobre la ventana' : 'Por cambio entre extremos (ventana muy corta para regresi\u00f3n)',
    });
  }
  const sub = $('divergence-sub');
  if (sub) {
    const parts = [];
    if (intraday.available) parts.push(`intrad\u00eda ${String(intraday.summary || 'sin_divergencia').replace(/_/g, ' ')}`);
    if (result && result.available) parts.push(`sesiones ${String(result.summary || 'sin_divergencia').replace(/_/g, ' ')}`);
    sub.textContent = parts.length ? parts.join(' \u00b7 ') : 'sin historia suficiente';
  }
}
