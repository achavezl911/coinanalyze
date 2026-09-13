'use strict';
// memoria, setups, lectura de mercado, diario, salud y precio
// Trozo 5 de 11 del panel. Sale de static/app.js SIN TOCAR UNA LINEA DE LOGICA
// (FASE 2, 2026-09-13): lineas 673-1102 del fichero original.
// El orden de los <script defer> de index.html ES el orden de este fichero: no se
// reordena nada, porque en scripts clasicos un `const` de primer nivel solo existe a
// partir del script que lo declara.
function renderMarketMemory(result) {
  const body = $('market-memory');
  if (!body) return;
  body.replaceChildren();
  if (!result || result.available !== true) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = result && result.reason ? result.reason : 'Memoria histórica aún no disponible.';
    body.append(empty);
    $('memory-sub').textContent = `${number(result && result.sessions, 0)} días disponibles`;
    return;
  }
  const current = result.current || {};
  const summary = result.analog_summary || {};
  const coverage = result.coverage || {};
  const tilt = ['LONG', 'SHORT'].includes(result.historical_tilt) ? result.historical_tilt : 'NEUTRAL';
  const overview = document.createElement('div');
  overview.className = 'memory-overview';
  const regime = document.createElement('div');
  regime.className = 'memory-regime';
  const label = document.createElement('span');
  label.textContent = 'Régimen actual';
  const phase = document.createElement('strong');
  phase.className = tilt === 'LONG' ? 'positive' : tilt === 'SHORT' ? 'negative' : 'neutral';
  phase.textContent = result.phase || 'sin clasificar';
  const tiltNode = document.createElement('small');
  tiltNode.textContent = `Inclinación de análogos: ${tilt}`;
  regime.append(label, phase, tiltNode);
  const stats = document.createElement('div');
  stats.className = 'memory-stats';
  for (const [name, value, detail, cls] of [
    ['Posición rango 60d', `${number(current.range_position_60d_pct, 1)}%`, '0% mínimo · 100% máximo', 'neutral'],
    ['Desde máximo 2 años', pct(current.distance_from_high_pct, 1), money(current.two_year_high, 2), signClass(current.distance_from_high_pct)],
    ['Retorno 20 días', pct(current.return_20d_pct, 1), `volatilidad ${number(current.volatility_20d_pct, 2)}%`, signClass(current.return_20d_pct)],
    ['Análogos +20 días', pct(summary.median_return_20d_pct, 1), `${number(summary.positive_20d_count, 0)}/${number(summary.sample, 0)} terminaron arriba`, signClass(summary.median_return_20d_pct)],
  ]) {
    const item = document.createElement('div');
    item.className = 'memory-stat';
    const nameNode = document.createElement('span');
    nameNode.textContent = name;
    const valueNode = document.createElement('strong');
    valueNode.className = cls;
    valueNode.textContent = value;
    const detailNode = document.createElement('small');
    detailNode.textContent = detail;
    item.append(nameNode, valueNode, detailNode);
    stats.append(item);
  }
  overview.append(regime, stats);

  const analogs = document.createElement('div');
  analogs.className = 'memory-analogs';
  const intro = document.createElement('p');
  intro.textContent = 'Episodios no solapados más parecidos al estado actual y lo que ocurrió después:';
  const scroll = document.createElement('div');
  scroll.className = 'table-scroll';
  const table = document.createElement('table');
  const thead = document.createElement('thead');
  const header = document.createElement('tr');
  for (const text of ['Fecha', 'Similitud', 'Estado entonces', '+5d', '+10d', '+20d', 'Mejor / peor 20d']) {
    const th = document.createElement('th');
    th.textContent = text;
    header.append(th);
  }
  thead.append(header);
  const tbody = document.createElement('tbody');
  for (const analog of safeArray(result.analogs)) {
    const tr = document.createElement('tr');
    const prior = analog.state || {};
    const forward = analog.forward || {};
    td(tr, analog.date, '');
    td(tr, `${number(analog.similarity_score, 1)}/100`, 'neutral');
    td(tr, `20d ${pct(prior.return_20d_pct, 1)} · rango ${number(prior.range_position_60d_pct, 0)}%`, signClass(prior.return_20d_pct));
    td(tr, pct(forward.return_5d_pct, 1), signClass(forward.return_5d_pct));
    td(tr, pct(forward.return_10d_pct, 1), signClass(forward.return_10d_pct));
    td(tr, pct(forward.return_20d_pct, 1), signClass(forward.return_20d_pct));
    td(tr, `${pct(forward.best_20d_pct, 1)} / ${pct(forward.worst_20d_pct, 1)}`, 'neutral');
    tbody.append(tr);
  }
  table.append(thead, tbody);
  scroll.append(table);
  analogs.append(intro, scroll);
  const warning = document.createElement('p');
  warning.className = 'memory-warning';
  warning.textContent = `${result.source} ${result.warning}`;
  body.append(overview, analogs, warning);
  $('memory-sub').textContent = `${number(coverage.days, 0)} días · ${coverage.from || '—'} a ${coverage.to || '—'}`;
}

function renderSetups(result) { const container = $('setups'); container.replaceChildren(); const setups = result.setups || []; if (!setups.length) { const e = document.createElement('div'); e.className = 'empty'; e.textContent = 'Sin evaluación disponible.'; container.append(e); return; } for (const item of setups) { const stateClass = item.state === 'activo' ? 'active' : item.state === 'vigilancia' ? 'watch' : 'inactive'; const node = document.createElement('article'); node.className = `setup ${stateClass}`; const title = document.createElement('div'); title.className = 'setup-title'; const name = document.createElement('span'); name.textContent = `${item.id} · ${item.name}`; const score = document.createElement('span'); score.className = 'setup-score'; score.textContent = `${item.confidence}/100`; title.append(name, score); const bias = document.createElement('div'); bias.className = 'setup-bias'; bias.textContent = `${String(item.state).toUpperCase()} · ${item.bias}`; node.append(title, bias); const matches = (item.matched || []).slice(0, 3); if (matches.length) { const ul = document.createElement('ul'); ul.className = 'setup-details'; for (const text of matches) { const li = document.createElement('li'); li.textContent = text; ul.append(li); } node.append(ul); } if (item.state !== 'inactivo' && item.reading) { const reading = document.createElement('div'); reading.className = 'setup-reading'; reading.textContent = item.reading; node.append(reading); }
    // FOLLOW · lo que le FALTA, lo que lo INVALIDA y su HORIZONTE. El backend los sirve desde
    // antes de esta campana -`missing`, `invalidation`, `horizon` en cada setup- y la tarjeta
    // no los pintaba: era exactamente «lo servido que no se ve».
    //
    // AUSENTE SE VE COMO AUSENTE, y es la parte que hay que mirar dos veces: un setup sin
    // `missing` NO es un setup al que no le falte nada -eso seria leer un hueco como un cero-.
    // Por eso se distingue «no le falta nada» (lista vacia, que el backend SI sirve cuando el
    // setup esta completo) de «no lo dice» (la clave no viene).
    const falta = document.createElement('div');
    falta.className = 'setup-falta';
    if (!Object.hasOwn(item, 'missing')) falta.textContent = 'Le falta: no declarado.';
    else if (!safeArray(item.missing).length) falta.textContent = 'Le falta: nada, cumple todo lo suyo.';
    else falta.textContent = `Le falta: ${safeArray(item.missing).join(' · ')}`;
    node.append(falta);

    const invalida = document.createElement('div');
    invalida.className = 'setup-invalida';
    invalida.textContent = item.invalidation
      ? `Se invalida si: ${item.invalidation}`
      : 'Se invalida si: no declarado.';
    node.append(invalida);

    const horizonte = document.createElement('div');
    horizonte.className = 'setup-horizonte';
    horizonte.textContent = item.horizon ? `Horizonte: ${item.horizon}` : 'Horizonte: no declarado.';
    node.append(horizonte);
    container.append(node); } }

function renderMarketReading(result, trend, swing, divergences, confidence, setup) {
  const body = $('market-reading');
  if (!body) return;
  body.replaceChildren();
  if (!result || result.available !== true) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = result && result.reason ? result.reason : 'Lectura CVD no disponible.';
    body.append(empty);
    return;
  }

  const signal = result.signal || 'ESPERAR';
  const trendBias = trend.medium_term_alignment === 'alcista' ? 'LONG' : trend.medium_term_alignment === 'bajista' ? 'SHORT' : 'MIXTO';
  const quality = safeArray(confidence.rows)[0] || {};
  const structureOpposes = (signal === 'LONG' && trendBias === 'SHORT') || (signal === 'SHORT' && trendBias === 'LONG');
  const levels = result.reference_levels || {};
  const confirmed = signal === 'LONG'
    ? asNumber(levels.last_close) > asNumber(levels.confirm_above)
    : signal === 'SHORT' ? asNumber(levels.last_close) < asNumber(levels.confirm_below) : false;
  let decision = signal;
  if (quality.status !== 'ok') decision = 'NO TRADE';
  else if (signal === 'ESPERAR' || structureOpposes) decision = 'ESPERAR';
  else if (!confirmed) decision = `VIGILAR ${signal}`;
  const cls = decision.includes('LONG') ? 'positive' : decision.includes('SHORT') ? 'negative' : 'neutral';

  const hero = document.createElement('div');
  hero.className = 'reading-hero';
  const badge = document.createElement('strong');
  badge.className = `reading-badge ${cls}`;
  badge.textContent = decision;
  const thesis = document.createElement('p');
  thesis.textContent = result.thesis;
  hero.append(badge, thesis);

  const evidence = document.createElement('div');
  evidence.className = 'reading-evidence';
  const ev = result.evidence || {};
  for (const [label, value, detail, valueClass] of [
    ['Score CVD/precio', `${asNumber(result.score) > 0 ? '+' : ''}${number(result.score, 1)}`, 'Señal desde ±30 puntos', signClass(result.score)],
    ['CVD spot 3 sesiones', money(ev.cvd_spot_3s_usd), `percentil ${number(ev.cvd_spot_percentile_90s, 0)}`, signClass(ev.cvd_spot_3s_usd)],
    ['Precio 3 sesiones', pct(ev.price_change_3s_pct), `percentil ${number(ev.price_percentile_90s, 0)}`, signClass(ev.price_change_3s_pct)],
    ['CVD futuros 3 sesiones', money(ev.cvd_futures_3s_usd), `percentil ${number(ev.cvd_futures_percentile_90s, 0)} · contexto`, signClass(ev.cvd_futures_3s_usd)],
  ]) {
    const item = document.createElement('div');
    const labelNode = document.createElement('span');
    labelNode.textContent = label;
    const valueNode = document.createElement('strong');
    valueNode.className = valueClass;
    valueNode.textContent = value;
    const detailNode = document.createElement('small');
    detailNode.textContent = detail;
    item.append(labelNode, valueNode, detailNode);
    evidence.append(item);
  }

  const notes = document.createElement('ul');
  notes.className = 'reading-notes';
  const noteTexts = [];
  if (quality.status !== 'ok') noteTexts.push('Datos degradados: la lectura queda bloqueada hasta recuperar calidad.');
  else if (structureOpposes) noteTexts.push(`La estructura 4h/8h/1d es ${trend.medium_term_alignment}; contradice el CVD y obliga a esperar.`);
  else noteTexts.push(`Estructura 4h/8h/1d ${trend.medium_term_alignment || 'sin definir'}; ${confirmed ? 'el cierre confirma' : 'falta confirmación del cierre'} para ${signal}.`);
  noteTexts.push(`Swing de fondo: ${swing.bias || 'NEUTRAL'} (${swing.conviction || 'sin convicción'}). Divergencias: ${String(divergences.summary || 'sin lectura').replaceAll('_', ' ')}.`);
  const primary = setup && setup.primary;
  if (primary) noteTexts.push(`Setup principal: ${primary.name} · ${primary.state} · ${primary.confidence}/100.`);
  if (signal === 'LONG') noteTexts.push(`Confirmación: cierre sobre ${money(levels.confirm_above, 2)}. ${result.invalidation}`);
  else if (signal === 'SHORT') noteTexts.push(`Confirmación: cierre bajo ${money(levels.confirm_below, 2)}. ${result.invalidation}`);
  else noteTexts.push(result.invalidation);
  const bt = result.backtest || {};
  noteTexts.push(`Walk-forward del activo: ${number(bt.trades, 0)} señales, ${number(bt.win_rate_pct, 1)}% favorables, retorno medio firmado ${pct(bt.mean_return_pct)} a 2 sesiones.`);
  for (const text of noteTexts) { const li = document.createElement('li'); li.textContent = text; notes.append(li); }

  const warning = document.createElement('p');
  warning.className = 'reading-warning';
  warning.textContent = result.warning;
  body.append(hero, evidence, notes, warning);
  const sub = $('reading-sub');
  if (sub) sub.textContent = `${result.as_of} · horizonte ${result.horizon} · fuerza ${result.strength}`;
}
// "-$257.1M" no dice si es normal o extremo. El percentil vs toda la historia guardada sí.
function withScale(value, percentile) {
  const p = asNumber(percentile);
  return p === null ? money(value) : `${money(value)} · p${p.toFixed(0)}`;
}
function renderQuickRead(result) {
  const body = $('quick-read-body');
  if (!body) return;
  const read = (result || {}).quick_read || {};
  const date = $('quick-read-date');
  if (date) date.textContent = read.as_of ? `Sesión ${read.as_of}` : 'Última sesión cerrada';
  body.replaceChildren();
  if (!read.available) {
    const empty = document.createElement('p');
    empty.className = 'empty';
    empty.textContent = read.reason || 'Sin datos suficientes para una lectura rápida.';
    body.append(empty);
    return;
  }

  const hero = document.createElement('section');
  hero.className = `quick-read-hero ${read.tone || 'neutral'}`;
  const copy = document.createElement('div');
  const kicker = document.createElement('span');
  kicker.className = 'quick-read-kicker';
  kicker.textContent = `${String(read.state || 'sin ventaja').replaceAll('_', ' ')} · confluencia ${read.confluence || '—'}`;
  const headline = document.createElement('strong');
  headline.className = 'quick-read-headline';
  headline.textContent = read.headline || 'Sin lectura';
  const interpretation = document.createElement('p');
  interpretation.textContent = read.interpretation || '';
  copy.append(kicker, headline, interpretation);
  const action = document.createElement('strong');
  action.className = `quick-read-action ${read.tone || 'neutral'}`;
  action.textContent = read.action || 'ESPERAR';
  hero.append(copy, action);

  const metrics = document.createElement('div');
  metrics.className = 'quick-read-metrics';
  const values = read.metrics || {};
  for (const [label, value, cls] of [
    ['CVD spot', withScale(values.cvd_spot_usd, values.cvd_spot_percentile), signClass(values.cvd_spot_usd)],
    ['CVD futuros', money(values.cvd_fut_usd), signClass(values.cvd_fut_usd)],
    ['Respuesta precio', pct(values.price_chg_pct), signClass(values.price_chg_pct)],
    ['Cambio OI', money(values.oi_chg_usd), signClass(values.oi_chg_usd)],
  ]) {
    const item = document.createElement('div');
    const name = document.createElement('span');
    name.textContent = label;
    const amount = document.createElement('strong');
    amount.className = cls;
    amount.textContent = value;
    item.append(name, amount);
    metrics.append(item);
  }

  const playbook = document.createElement('dl');
  playbook.className = 'quick-read-playbook';
  for (const [label, value] of [['Para confirmar', read.confirmation], ['Queda invalidado si', read.invalidation]]) {
    const row = document.createElement('div');
    const dt = document.createElement('dt');
    const dd = document.createElement('dd');
    dt.textContent = label;
    dd.textContent = value || '—';
    row.append(dt, dd);
    playbook.append(row);
  }
  const warning = document.createElement('p');
  warning.className = 'quick-read-warning';
  warning.textContent = `${read.method || ''} ${read.warning || ''}`.trim();
  body.append(hero, metrics, playbook, warning);
}
function renderDaily(result) {
  const rows = result.rows || [];
  $('daily-context').textContent = `Racha spot ${result.streak > 0 ? '+' : ''}${result.streak} sesiones · ${rows.length} registros`;
  // Sin filtro, una sesion sin acumulado entraba como value 0 y la curva caia al eje.
  // Ahora ademas se parte en los huecos: una sesion sin dato deja de unirse con la siguiente.
  renderGapNote('daily-gaps', setGappedLine('daily', rows, r => ts(`${r.session_date}T12:00:00Z`), r => r.cumulative_spot));
  if (rows.length) state.charts['daily-chart'].timeScale().fitContent();
  const body = $('daily-body');
  body.replaceChildren();
  for (const row of [...rows].reverse()) {
    const tr = document.createElement('tr');
    const q = flowQuadrant(row);
    const response = sessionResponse(row);
    td(tr, row.session_date, '');
    td(tr, pct(row.price_chg_pct), signClass(row.price_chg_pct));
    const flowCell = td(tr, q.label, q.cls);
    flowCell.title = 'Describe qué lado ejecutó órdenes agresivas en spot y futuros; no demuestra acumulación institucional';
    const responseCell = td(tr, response.label, response.cls);
    responseCell.title = response.detail;
    td(tr, withScale(row.cvd_spot_usd, row.cvd_spot_percentile), signClass(row.cvd_spot_usd));
    td(tr, money(row.cvd_fut_usd), signClass(row.cvd_fut_usd));
    td(tr, money(row.cumulative_spot), signClass(row.cumulative_spot));
    td(tr, money(row.oi_chg_usd), signClass(row.oi_chg_usd));
    td(tr, rate(row.fr_avg), signClass(-asNumber(row.fr_avg)));
    body.append(tr);
  }
  const note = $('daily-sources');
  if (note) {
    const src = result.sources || {};
      note.textContent = `Agresión no es inventario: CVD negativo significa que vendedores cruzaron el spread; no muestra las compras límite que pudieron absorberlos. "Venta sin caída" es una huella de posible defensa, no prueba de acumulación, y exige confirmación en varias sesiones. Cada fecha cubre la sesión cripto de 09:30 ET del día anterior a 09:30 ET de ese día. CVD spot: ${(src.cvd_spot_usd || {}).venues || '—'} · futuros: ${(src.cvd_fut_usd || {}).venues || '—'} · p = percentil histórico.`;
  }
  renderQuickRead(result);
}
function renderHealth(result) { const ok = result.status === 'ok'; $('health-status').textContent = String(result.status || 'unknown').toUpperCase(); $('health-status').className = ok ? 'estado-ok' : 'estado-malo'; const container = $('health-services'); container.replaceChildren(); for (const service of result.services || []) { const item = document.createElement('div'); item.className = 'health-item'; const strong = document.createElement('strong'); strong.textContent = service.service; const span = document.createElement('span'); span.textContent = `${service.status} · lag ${number(service.lag_seconds, 0)} s`; item.append(strong, span); container.append(item); } }
// Arrastrar o hacer zoom sobre el eje de precios DESACTIVA el autoescalado de esa escala en
// lightweight-charts, y no se reactiva solo. Al cambiar de activo el eje seguia clavado en el
// rango del anterior: con BTC (~64 000) y luego ETH (~1 870), las velas de ETH quedaban
// aplastadas contra el borde y el eje seguia rotulando precios de BTC. fitContent() no lo
// arregla, porque solo actua sobre el eje de tiempo.
function resetPriceScales() {
  for (const chart of Object.values(state.charts || {})) {
    try { chart.priceScale('right').applyOptions({ autoScale: true }); } catch (_) {}
    try { chart.timeScale().fitContent(); } catch (_) {}
  }
}

function renderActivePriceChart() {
  const daily = state.priceMode === 'wyckoff';
  const source = daily ? safeArray(state.wyckoff.chart_bars) : safeArray(state.priceBars);
  // Una vela exige las CUATRO patas. El filtro anterior solo miraba `close`, asi que una
  // barra con `open` ausente se dibujaba abriendo en 0: un cuerpo del alto del grafico.
  state.series.price.setData(source.map((r) => {
    const time = ts(r.bucket || r.time);
    const bar = { time, open: asNumber(r.open), high: asNumber(r.high), low: asNumber(r.low), close: asNumber(r.close) };
    const completa = Number.isFinite(time) && ['open', 'high', 'low', 'close'].every(k => bar[k] !== null);
    return completa ? bar : null;
  }).filter(bar => bar !== null));
  try {
    const chart = state.charts['price-chart'];
    chart.timeScale().applyOptions({ timeVisible: !daily, tickMarkFormatter: tickMarkFormatter(!daily) });
    chart.applyOptions({ localization: { locale: 'es-MX', timeFormatter: crosshairFormatter(!daily), priceFormatter: axisPrice } });
    chart.priceScale('right').applyOptions({ autoScale: true });
    chart.timeScale().fitContent();
  } catch (_) {}
}

function renderPriceChart(ohlcv) {
  state.priceBars = safeArray(ohlcv);
  renderActivePriceChart();
}

function setPriceMode(mode) {
  if (mode === 'wyckoff' && !state.wyckoff.available) return;
  state.priceMode = mode === 'wyckoff' ? 'wyckoff' : 'intraday';
  const intraday = $('price-mode-intraday');
  const wyckoff = $('price-mode-wyckoff');
  if (intraday) intraday.classList.toggle('active', state.priceMode === 'intraday');
  if (wyckoff) {
    wyckoff.classList.toggle('active', state.priceMode === 'wyckoff');
    wyckoff.disabled = !state.wyckoff.available;
  }
  renderActivePriceChart();
  renderStructureLevels(state.structureDetail, state.dashboard.barriers || {}, state.wyckoff);
}
function renderFlowCharts(cvd, oi, whale) {
  // `Number(null)` es 0 y 0 SI es finito, asi que el filtro `Number.isFinite` de antes no
  // descartaba nada: los buckets sin CVD entraban como ceros y la linea volvia al eje.
  // Y quitarlos tampoco basta: hay que PARTIR la serie o el motor une los extremos.
  const gapSpot = setGappedLine('cvdSpot', cvd, r => ts(r.bucket), r => r.cvd_spot);
  const gapFut = setGappedLine('cvdFut', cvd, r => ts(r.bucket), r => r.cvd_fut);
  setGappedLine('cvdDiff', cvd, r => ts(r.bucket), r => r.cvd_diff);
  // Se declara el peor de los dos: si a una pata le faltan muestras, la lectura conjunta
  // tampoco es completa.
  renderGapNote('cvd-gaps', (gapSpot && gapFut && gapFut.missing > gapSpot.missing) ? gapFut : gapSpot);
  if (oi !== null) renderOiChart(oi);
  const whaleBars = seriesPoints(whale, r => ts(r.bucket), r => r.whale_delta)
    .map(p => ({ ...p, color: p.value >= 0 ? COLORS.green : COLORS.red }));
  state.series.whale.setData(whaleBars);
  renderWhaleActivity(whaleBars);
  for (const id of ['cvd-chart', 'whale-chart']) { try { state.charts[id].timeScale().fitContent(); } catch (_) {} }
}
// ESTE COMENTARIO DECIA QUE EL CERO ERA «una lectura valida, no un dato ausente». **Es falso**,
// y esta medido: el umbral es 5 000 000 USD POR OPERACION SUELTA y en BTC da 0 de 20 118 minutos
// en 7 dias (ETH 3 de 20 117, SOL 65 de 20 118: baja el umbral y el tramo aparece).
// Y el control que decide: el FUTURO del mismo BTC, los mismos 7 dias, con un umbral CINCO VECES
// MENOR -1 000 000-, dispara 117 de 4 340 minutos. El futuro las ve; el spot, ninguna.
// No es que no haya manos grandes: es que con este umbral NO SE PUEDEN VER.
// Cual seria el umbral bueno NO SE PUEDE MEDIR con lo que se guarda -solo agregados, nunca la
// operacion suelta-, asi que la tarjeta lo DECLARA en vez de publicar el cero como respuesta.
function renderWhaleActivity(bars) {
  const chart = $('whale-chart');
  const note = $('whale-note');
  if (!chart || !note) return;
  const active = bars.filter(bar => bar.value !== 0);
  const quiet = active.length < 2;
  chart.hidden = quiet;
  note.hidden = !quiet;
  if (!quiet) { try { state.charts['whale-chart'].resize(chart.clientWidth, chart.clientHeight); } catch (_) {} return; }
  if (!bars.length) { note.textContent = 'Sin ventanas medidas en el periodo.'; return; }
  // CERO ACTIVAS NO ES «no hubo manos grandes»: es que el instrumento no llega. Se dice con las
  // mismas letras que el resto, y el cero NO vota en nada que se derive de el.
  if (!active.length) {
    note.textContent = 'NO SE PUEDE MEDIR con el umbral actual: exige una sola operación de '
      + '5 000 000 USD, y en BTC eso no ocurre nunca (0 de 20 118 minutos en 7 días). '
      + 'El mismo BTC en futuros, esos mismos días y con un umbral cinco veces menor, sí la ve: '
      + '117 de 4 340 minutos. '
      + 'Esto NO significa que no haya manos grandes: significa que aquí no se ven. '
      + 'Cuál sería el umbral correcto no se puede calcular con lo que se guarda —solo agregados '
      + 'por minuto, nunca la operación suelta—, así que este panel no vota.';
    return;
  }
  const last = active[active.length - 1];
  const detail = last ? ` La última fue ${money(last.value)} el ${new Date(last.time * 1000).toLocaleString('es-MX', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })} UTC.` : '';
  note.textContent = `${active.length} de ${bars.length} ventanas de 15 min con órdenes de tamaño whale.${detail}`;
}
function setConnection(status, text) { $('connection-dot').className = `dot ${status}`; $('connection-text').textContent = text; }
function renderDataConfidence(conf) {
  const row = safeArray(conf.rows)[0];
  const pill = $('data-confidence');
  if (!pill) return;
  if (!row) { pill.textContent = 'Datos no disponibles'; pill.className = 'live-pill estado-malo'; return; }
  const flow = row.flow_8h_complete === true ? '8h' : '8h parcial';
  // Interpolar el campo crudo escribia "Sundefined/Fundefined/Bundefined" cuando el conteo
  // de venues no venia: un hueco tiene que leerse como hueco, no como texto roto.
  const venues = v => { const n = asNumber(v); return n === null ? 'N/D' : number(n, 0); };
  pill.textContent = `Datos ${row.status === 'ok' ? 'OK' : 'degradados'} · S${venues(row.spot_venues_live)}/F${venues(row.futures_venues_live)}/B${venues(row.book_venues_live)} · ${flow}`;
  pill.title = `Cobertura 8h: ${row.flow_8h_complete === true ? 'completa' : 'parcial'} · Spot: ${row.flow_8h_spot_source || 'sin fuente'} · lag ${number(row.flow_8h_spot_end_gap_seconds, 0)} s`;
  pill.className = `live-pill ${row.status === 'ok' ? 'estado-ok' : 'estado-malo'}`;
}

function clearSnapshotView() { $('summary').replaceChildren(); $('decision-horizons').replaceChildren(); $('decision-alignment').textContent = 'Actualizando…'; $('decision-alignment').className = 'decision-alignment neutral'; $('price-context').textContent = 'Sin datos'; }
function clearSymbolView() {
  clearSnapshotView();
  renderDataConfidence({ rows: [] });
  for (const id of ['live-price', 'live-delta', 'live-book']) {
    const node = $(id);
    node.textContent = '—';
    node.className = 'live-pill neutral';
  }
  for (const id of [
    'levels', 'delta-matrix', 'absorption-matrix', 'orderbook-body',
    'liq-matrix', 'basis-details', 'liq-levels-body',
    'structure-body', 'macro-body', 'passive-body', 'trend-body', 'swing-body', 'barrier-map',
    'market-memory', 'market-reading', 'external-macro-body', 'setups', 'dailybars-body', 'daily-body', 'divergence-body',
  ]) $(id).replaceChildren();
  for (const id of ['structure-align', 'macro-sub', 'external-macro-sub', 'external-macro-badge', 'passive-sub', 'trend-sub', 'swing-sub', 'barrier-sub', 'memory-sub', 'reading-sub', 'daily-context', 'dailybars-sub', 'divergence-sub', 'daily-sources']) $(id).textContent = '—';
  for (const series of Object.values(state.series)) series.setData([]);
  for (const line of state.priceLines || []) {
    try { state.series.price.removePriceLine(line); } catch (_) {}
  }
  state.priceLines = [];
  try { if (state.priceMarkers && state.priceMarkers.setMarkers) state.priceMarkers.setMarkers([]); } catch (_) {}
  resetPriceScales();
}

function renderBasisDetails(result) {
  const dl = $('basis-details'); if (!dl) return; dl.replaceChildren();
  const valid = result.basis_bps !== null && result.basis_bps !== undefined;
  rowDL(dl, 'Basis', valid ? `${number(result.basis_bps, 2)} bps` : 'No utilizable', valid ? signClass(result.basis_bps) : 'negative');
  rowDL(dl, 'Estado', result.status || '—', valid ? 'estado-ok' : 'estado-malo');
  if (!valid && result.reason) rowDL(dl, 'Motivo', result.reason, 'neutral');
  rowDL(dl, 'Futuros', money(result.fut_price, 2), 'neutral');
  rowDL(dl, 'Spot', money(result.spot_price, 2), 'neutral');
  // Edad del ULTIMO TRADE de cada pata: es lo que decide si el basis se publica. El lag de
  // bucket va aparte porque incluye el redondeo de 5 s de la rejilla.
  rowDL(dl, 'Edad fut/spot', `${number(result.fut_age_seconds, 1)}s / ${number(result.spot_age_seconds, 1)}s`, 'neutral');
  rowDL(dl, 'Skew entre patas', result.skew_ms === null || result.skew_ms === undefined ? '—' : `${number(result.skew_ms, 0)} ms (no invalida)`, 'neutral');
}
