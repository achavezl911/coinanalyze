'use strict';
// SVG: perfil de delta, niveles de liquidacion y barreras
// Trozo 6 de 11 del panel. Sale de static/app.js SIN TOCAR UNA LINEA DE LOGICA
// (FASE 2, 2026-09-13): lineas 1103-1432 del fichero original.
// El orden de los <script defer> de index.html ES el orden de este fichero: no se
// reordena nada, porque en scripts clasicos un `const` de primer nivel solo existe a
// partir del script que lo declara.
// Perfil de volumen y delta por nivel. Cada barra es un cubo de precio: el largo es el volumen
// y el color, el signo del delta de futuros. El area de valor y el POC van de fondo.
const PROFILE_SVG_WIDTH = 1000;
const PROFILE_ROW_HEIGHT = 8;
// Etiquetas de precio a la izquierda y barras creciendo a la derecha: sin hueco muerto.
const PROFILE_LABEL_X = 68;
const PROFILE_BAR_X = 78;
const PROFILE_BAR_WIDTH = 848;
const PROFILE_NS = 'http://www.w3.org/2000/svg';
function svgEl(name, attrs) { const node = document.createElementNS(PROFILE_NS, name); for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value); return node; }
function profileRowY(rows, price, step) {
  // Las filas van de mayor a menor precio; y es el centro del cubo que contiene ese precio.
  const first = rows[0].price;
  const offset = (first + step - price) / step;
  return Math.min(Math.max(offset, 0), rows.length) * PROFILE_ROW_HEIGHT;
}
function renderDeltaProfile(result) {
  const container = $('profile-chart');
  const stats = $('profile-stats');
  const note = $('profile-note');
  const sub = $('profile-sub');
  if (!container || !stats) return;
  container.replaceChildren();
  stats.replaceChildren();
  const rows = safeArray(result.rows);
  if (!result.available || !rows.length) {
    const empty = document.createElement('p');
    empty.className = 'liq-empty';
    empty.textContent = result.reason || 'Sin perfil disponible para esta ventana.';
    container.append(empty);
    if (sub) sub.textContent = 'Sin cobertura suficiente';
    if (note) note.textContent = '';
    return;
  }
  const step = asNumber(result.bucket_usd) || 1;
  const height = rows.length * PROFILE_ROW_HEIGHT;
  // Los niveles sin volumen medido no normalizan a nadie: se excluyen del maximo.
  const volumes = rows.map(r => asNumber(r.volume_usd)).filter(v => v !== null);
  const peak = volumes.length ? Math.max(...volumes) || 1 : 1;
  const svg = svgEl('svg', { viewBox: `0 0 ${PROFILE_SVG_WIDTH} ${height}`, class: 'profile-svg', role: 'img' });
  svg.setAttribute('aria-label', `Perfil de volumen por precio, ${rows.length} niveles`);

  const vaHigh = asNumber(result.value_area_high);
  const vaLow = asNumber(result.value_area_low);
  if (vaHigh !== null && vaLow !== null) {
    const top = profileRowY(rows, vaHigh, step);
    const bottom = profileRowY(rows, vaLow, step);
    svg.append(svgEl('rect', { x: PROFILE_BAR_X, y: top, width: PROFILE_BAR_WIDTH, height: Math.max(bottom - top, PROFILE_ROW_HEIGHT), class: 'profile-va' }));
  }

  const labelEvery = Math.max(1, Math.round(rows.length / 12));
  rows.forEach((row, index) => {
    const volume = asNumber(row.volume_usd);
    const delta = asNumber(row.delta_usd);
    const y = index * PROFILE_ROW_HEIGHT;
    // Nivel sin volumen medido: no se dibuja barra (ni siquiera de ancho 0 coloreada, que
    // se leeria como "aqui se opero cero"). El delta ausente no elige color de signo.
    if (volume === null) return;
    const width = Math.max((volume / peak) * PROFILE_BAR_WIDTH, volume > 0 ? 1 : 0);
    const clase = delta === null ? 'sin-dato' : (delta >= 0 ? 'up' : 'down');
    const bar = svgEl('rect', { x: PROFILE_BAR_X, y: y + 1, width, height: PROFILE_ROW_HEIGHT - 2, class: `profile-bar ${clase}${row.thin ? ' thin' : ''}` });
    const tip = document.createElementNS(PROFILE_NS, 'title');
    tip.textContent = `${money(row.price, 2)} · ${money(volume)} (${number(row.share_pct, 2)}% del total) · delta ${delta === null ? 'N/D' : money(delta)} (${number(row.delta_share_pct, 2)}% del nivel)`;
    bar.append(tip);
    svg.append(bar);
    if (index % labelEvery === 0) {
      const label = svgEl('text', { x: PROFILE_LABEL_X, y: y + PROFILE_ROW_HEIGHT - 1, class: 'profile-price' });
      label.textContent = money(row.price, 2);
      svg.append(label);
    }
  });

  const tagX = PROFILE_BAR_X + PROFILE_BAR_WIDTH + 6;
  const poc = asNumber(result.poc);
  if (poc !== null) {
    const y = profileRowY(rows, poc, step) + PROFILE_ROW_HEIGHT / 2;
    svg.append(svgEl('line', { x1: PROFILE_BAR_X, y1: y, x2: tagX - 4, y2: y, class: 'profile-poc' }));
    const tag = svgEl('text', { x: tagX, y: y + 3, class: 'profile-poc-tag' });
    tag.textContent = 'POC';
    svg.append(tag);
  }
  const price = asNumber(result.price);
  if (price !== null) {
    const y = profileRowY(rows, price, step);
    svg.append(svgEl('line', { x1: PROFILE_BAR_X, y1: y, x2: tagX - 4, y2: y, class: 'profile-now' }));
    const tag = svgEl('text', { x: tagX, y: y + 3, class: 'profile-now-tag' });
    tag.textContent = 'ahora';
    svg.append(tag);
  }
  container.append(svg);

  const netShare = asNumber(result.net_delta_share_pct);
  rowDL(stats, 'POC', money(result.poc, 2), 'neutral');
  rowDL(stats, 'Área de valor 70%', `${money(vaLow, 2)} – ${money(vaHigh, 2)}`, 'neutral');
  rowDL(stats, 'Volumen de la ventana', money(result.total_volume_usd), 'neutral');
  rowDL(stats, 'Delta neto', `${money(result.net_delta_usd)} (${pct(netShare)})`, signClass(result.net_delta_usd));
  rowDL(stats, 'Niveles delgados', number(rows.filter(r => r.thin).length, 0), 'neutral');
  rowDL(stats, 'Velas', `${number(result.bars, 0)} · ${result.from || '—'} → ${result.to || '—'}`, 'neutral');
  if (sub) sub.textContent = `${rows.length} niveles de ${money(step, 2)} · ${number(result.bars, 0)} velas`;
  if (note) note.textContent = (result.warning || '') + ' ' + ((result.method || {}).reparto || '');
}
async function loadDeltaProfile() {
  const symbol = state.symbol;
  const price = (state.dashboard.snapshot || {}).price;
  const query = `symbol=${encodeURIComponent(symbol)}&interval=${state.profileWindow.interval}&days=${state.profileWindow.days}`
    + (price ? `&price=${encodeURIComponent(price)}` : '');
  const result = await maybe(`/api/delta-profile?${query}`, { available: false, reason: 'No se pudo consultar el perfil.' });
  if (symbol !== state.symbol) return;
  renderDeltaProfile(result);
}
function initDeltaProfile() {
  const group = $('profile-windows');
  if (!group) return;
  for (const button of group.querySelectorAll('button')) {
    button.addEventListener('click', () => {
      state.profileWindow = { interval: button.dataset.interval, days: Number(button.dataset.days) };
      for (const other of group.querySelectorAll('button')) other.classList.toggle('active', other === button);
      loadDeltaProfile().catch(error => console.error(error));
    });
  }
}

// Perfil de liquidaciones por nivel. Es densidad YA EJECUTADA en la ventana, no una
// proyeccion de donde reventaran posiciones: no tenemos el apalancamiento del libro.
function liqProfileRow(price, longV, shortV, events, scale) {
  const row = document.createElement('div');
  row.className = 'liq-row';
  const label = document.createElement('span');
  label.className = 'liq-price';
  label.textContent = money(price, 2);
  const track = document.createElement('div');
  track.className = 'liq-track';
  for (const [side, value] of [['long', longV], ['short', shortV]]) {
    const half = document.createElement('div');
    half.className = `liq-side ${side}`;
    const fill = document.createElement('i');
    fill.style.width = `${scale > 0 ? Math.min((value / scale) * 100, 100) : 0}%`;
    half.append(fill);
    track.append(half);
  }
  const amount = document.createElement('span');
  amount.className = `liq-amount ${signClass(shortV - longV)}`;
  amount.textContent = money(longV + shortV);
  const evt = document.createElement('span');
  evt.className = 'liq-events';
  evt.textContent = number(events, 0);
  row.append(label, track, amount, evt);
  row.title = `Longs liquidados ${money(longV)} · shorts liquidados ${money(shortV)} · ${number(events, 0)} eventos`;
  return row;
}
function renderLiquidationLevels(result, price) {
  const body = $('liq-levels-body');
  if (!body) return;
  body.replaceChildren();
  const rows = safeArray(result.rows)
    // Aqui el cero SI es medido: la fila existe porque hubo eventos en ese bucket, asi que
    // un lado sin importe significa "ninguna liquidacion de ese lado", no "sin dato".
    .map(r => ({
      price: asNumber(r.price_bucket),
      long: asNumber(r.long_liq) === null ? 0 : asNumber(r.long_liq),
      short: asNumber(r.short_liq) === null ? 0 : asNumber(r.short_liq),
      events: asNumber(r.events) === null ? 0 : asNumber(r.events),
    }))
    .filter(r => r.price !== null)
    .sort((a, b) => b.price - a.price);
  const sub = $('liq-levels-sub');
  if (!rows.length) {
    const empty = document.createElement('p');
    empty.className = 'liq-empty';
    empty.textContent = 'Sin liquidaciones registradas en la ventana.';
    body.append(empty);
    if (sub) sub.textContent = 'Densidad ya ejecutada · sin eventos';
    return;
  }
  const scale = Math.max(...rows.map(r => Math.max(r.long, r.short)));
  const current = asNumber(price);
  let marked = current === null;
  for (const r of rows) {
    if (!marked && r.price < current) { body.append(liqProfileMark(current)); marked = true; }
    body.append(liqProfileRow(r.price, r.long, r.short, r.events, scale));
  }
  if (!marked) body.append(liqProfileMark(current));
  const totalLong = rows.reduce((acc, r) => acc + r.long, 0);
  const totalShort = rows.reduce((acc, r) => acc + r.short, 0);
  const legend = document.createElement('div');
  legend.className = 'liq-legend';
  const left = document.createElement('span');
  left.className = 'negative';
  left.textContent = `Longs liquidados ${money(totalLong)}`;
  const right = document.createElement('span');
  right.className = 'positive';
  right.textContent = `Shorts liquidados ${money(totalShort)}`;
  legend.append(left, right);
  body.append(legend);
  if (sub) sub.textContent = `Densidad ya ejecutada · ${result.minutes || 60} min · ${rows.length} niveles`;
}
function liqProfileMark(price) {
  const mark = document.createElement('div');
  mark.className = 'liq-row liq-mark';
  const label = document.createElement('span');
  label.className = 'liq-price';
  label.textContent = money(price, 2);
  const line = document.createElement('div');
  line.className = 'liq-mark-line';
  const tag = document.createElement('span');
  tag.className = 'liq-mark-tag';
  tag.textContent = 'precio actual';
  mark.append(label, line, tag);
  return mark;
}

function renderBarrierZone(label, zone, cls) {
  const card = document.createElement('article');
  card.className = `barrier-zone ${cls}`;
  const heading = document.createElement('div');
  heading.className = 'barrier-zone-heading';
  const name = document.createElement('span');
  name.textContent = label;
  const strength = document.createElement('strong');
  strength.textContent = zone ? `${String(zone.difficulty).toUpperCase()} ${number(zone.score, 0)}/100` : 'SIN NIVEL';
  heading.append(name, strength);
  card.append(heading);
  if (!zone) {
    const empty = document.createElement('p');
    empty.textContent = 'No hay pivotes suficientes a este lado del precio.';
    card.append(empty);
    return card;
  }
  const price = document.createElement('div');
  price.className = 'barrier-price';
  price.textContent = `${money(zone.low, 2)} – ${money(zone.high, 2)}`;
  const reading = document.createElement('p');
  // reaction_atr es la MEDIANA de las reacciones (interpretation.py), no lo que hizo cada
  // toque: la mitad de los rechazos se quedaron por debajo de esa cifra.
  reading.textContent = `${number(zone.touches, 0)} rechazos; reacción mediana de ${number(zone.reaction_atr, 2)} ATR con ${number(zone.volume_multiple, 2)}x el volumen normal. Distancia ${number(zone.distance_pct, 2)}%.`;
  const refs = zone.volume_reference_usd || {};
  const volume = document.createElement('small');
  const parts = [];
  if (refs['4h'] != null) parts.push(`4h ${money(refs['4h'])}`);
  if (refs['1d'] != null) parts.push(`diario ${money(refs['1d'])}`);
  volume.textContent = parts.length ? `Volumen típico en los rechazos: ${parts.join(' · ')}` : 'Volumen histórico exacto no disponible; se usa volumen relativo.';
  card.append(price, reading, volume);
  return card;
}

function renderBarriers(result) {
  const body = $('barrier-map');
  if (!body) return;
  body.replaceChildren();
  if (!result || result.available !== true) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = result && result.reason ? result.reason : 'Mapa de barreras no disponible.';
    body.append(empty);
    return;
  }
  const live = result.live_pressure || {};
  const decision = document.createElement('article');
  decision.className = 'barrier-decision';
  const badge = document.createElement('strong');
  badge.className = result.decision.includes('LONG') ? 'positive' : result.decision.includes('SHORT') ? 'negative' : 'neutral';
  badge.textContent = result.decision;
  const effort = document.createElement('p');
  const multiple = asNumber(live.volume_multiple_15m);
  const volumeState = multiple === null ? 'sin referencia' : multiple >= 1.5 ? 'alto' : multiple >= 1 ? 'normal' : 'bajo';
  effort.textContent = `Esfuerzo 15m ${volumeState}: ${money(live.volume_15m_usd)} (${number(live.volume_multiple_15m, 2)}x normal). Presión de ruptura arriba ${number(live.breakout_up_score, 0)}/100; abajo ${number(live.breakdown_score, 0)}/100. Absorción: ${live.absorption_15m || 'ninguna'}.`;
  const cases = document.createElement('ul');
  for (const text of [
    `LONG: ${result.long_case.breakout || result.long_case.rejection || 'sin nivel'}; exigir cierre y retest.`,
    `SHORT: ${result.short_case.breakdown || result.short_case.rejection || 'sin nivel'}; exigir cierre y retest.`,
  ]) {
    const li = document.createElement('li');
    li.textContent = text;
    cases.append(li);
  }
  const warning = document.createElement('small');
  warning.textContent = result.warning;
  decision.append(badge, effort, cases, warning);
  body.append(
    renderBarrierZone('SOPORTE', result.nearest_support, 'support'),
    decision,
    renderBarrierZone('RESISTENCIA', result.nearest_resistance, 'resistance'),
  );
  const sub = $('barrier-sub');
  if (sub) { const delta = asNumber(live.delta_ratio_15m); sub.textContent = `Precio ${money(result.current_price, 2)} · delta 15m ${delta === null ? '—' : pct(delta * 100, 1)} · book ${number(live.book_imbalance_l5, 2)}`; }
}

function horizonCard({ name, time, action, side, thesis, trigger, invalidation, metric, baseRate, link, linkText }) {
  const node = document.createElement('article');
  node.className = `horizon-card ${side === 'LONG' ? 'positive' : side === 'SHORT' ? 'negative' : 'neutral'}`;
  const head = document.createElement('div');
  head.className = 'horizon-card-head';
  const title = document.createElement('div');
  const nameNode = document.createElement('span');
  nameNode.className = 'horizon-name';
  nameNode.textContent = name;
  const timeNode = document.createElement('span');
  timeNode.className = 'horizon-time';
  timeNode.textContent = time;
  title.append(nameNode, timeNode);
  const actionNode = document.createElement('strong');
  actionNode.className = `horizon-action ${side === 'LONG' ? 'positive' : side === 'SHORT' ? 'negative' : 'neutral'}`;
  actionNode.textContent = action;
  head.append(title, actionNode);
  const thesisNode = document.createElement('p');
  thesisNode.className = 'horizon-thesis';
  thesisNode.textContent = thesis || 'Sin una ventaja confirmada en este horizonte.';
  const plan = document.createElement('dl');
  plan.className = 'horizon-plan';
  // 'Tasa base' va DESPUES de 'Evidencia' y solo si hay cifra. Un renglon fijo que a veces
  // dice "—" invita a leer el hueco como un cero; si no hay medida, no hay renglon.
  const filas = [['Confirmar', trigger], ['Salir si', invalidation], ['Evidencia', metric]];
  if (baseRate) filas.push(['Tasa base', baseRate]);
  for (const [label, value] of filas) {
    const row = document.createElement('div');
    const dt = document.createElement('dt');
    const dd = document.createElement('dd');
    dt.textContent = label;
    dd.textContent = value || '—';
    row.append(dt, dd);
    plan.append(row);
  }
  const detail = document.createElement('a');
  detail.className = 'horizon-link';
  detail.href = link;
  detail.textContent = `${linkText} →`;
  node.append(head, thesisNode, plan, detail);
  return node;
}

