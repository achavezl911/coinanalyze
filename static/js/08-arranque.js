'use strict';
// stream, navegacion, analizador y boot
// Trozo 8 de 11 del panel. Sale de static/app.js SIN TOCAR UNA LINEA DE LOGICA
// (FASE 2, 2026-09-13): lineas 1860-2028 del fichero original.
// El orden de los <script defer> de index.html ES el orden de este fichero: no se
// reordena nada, porque en scripts clasicos un `const` de primer nivel solo existe a
// partir del script que lo declara.
function connectStream() { if (state.source) state.source.close(); const source = new EventSource('/api/stream'); state.source = source; source.onopen = () => setConnection('ok', 'Streaming activo'); source.onerror = () => setConnection('bad', 'Reconectando stream'); source.onmessage = event => { try { const payload = JSON.parse(event.data); const asset = state.symbol.split('USDT')[0]; const full = state.symbol; const row = (payload.rows || []).find(item => item.symbol === asset); const scalp = (payload.scalp || []).find(item => item.symbol === full); const book = (payload.books || []).find(item => item.symbol === full); if (row && row.last_px) { $('live-price').textContent = `Px ${money(row.last_px, 2)}`; } if (scalp) { $('live-delta').textContent = `Fut Δ5s ${money(scalp.fut_delta_5s)}`; $('live-delta').className = `live-pill ${signClass(scalp.fut_delta_5s)}`; } else if (row) { $('live-delta').textContent = `Spot Δ5s ${money(row.delta_5s)}`; $('live-delta').className = `live-pill ${signClass(row.delta_5s)}`; } if (book) { $('live-book').textContent = `Book ${number(book.imbalance_l5, 2)} · ${number(book.spread_bps, 2)}bps`; $('live-book').className = `live-pill ${signClass((asNumber(book.imbalance_l5) || .5) - .5)}`; } } catch (error) { console.error(error); } }; }
async function selectSymbol(symbol) {
  if (symbol === state.symbol) return;
  state.symbol = symbol;
  state.viewLoadedAt = {};
  state.lastContextAt = 0;
  // Los veredictos de zona y rango son de unos precios concretos: al cambiar de activo dejan
  // de significar nada y mantenerlos en pantalla los atribuiria al simbolo equivocado.
  clearZone();
  clearRange();
  clearBreakout();
  releaseAnalyzerInputs();
  state.trend = {};
  state.tfProfile = {};
  state.swing = {};
  state.structureDetail = {};
  state.wyckoff = {};
  state.externalMacro = {};
  state.daily = { rows: [] };
  state.priceBars = [];
  setPriceMode('intraday');
  renderTabs();
  clearSymbolView();
  await refreshOverview(true);
  await loadSection(state.activeSection, true);
}
// Seccion a la que cae cualquier destino desconocido. Es la PRIMERA de la navegacion real
// del HTML, no un id heredado: 'overview' no existe desde la reorganizacion en 8 pestanas,
// asi que un hash invalido dejaba las 8 secciones ocultas y la pagina en blanco.
const FALLBACK_SECTION = 'mesa';
function initSectionNav() {
  const links = [...document.querySelectorAll('.section-links a')];
  const sections = links.map(link => $(link.hash.slice(1))).filter(Boolean);
  const valid = new Set(sections.map(section => section.id));
  // Si por lo que sea 'mesa' no existiera, se usa la primera seccion realmente presente:
  // el fallback nunca puede ser un id que no este en el documento.
  const fallback = valid.has(FALLBACK_SECTION) ? FALLBACK_SECTION : (sections[0] || {}).id;
  const initial = location.hash.slice(1);
  state.activeSection = valid.has(initial) ? initial : fallback;
  const show = async (id, updateHash = true) => {
    if (!valid.has(id)) id = fallback;
    state.activeSection = id;
    for (const section of sections) section.hidden = section.id !== id;
    for (const link of links) {
      const active = link.hash === `#${id}`;
      link.classList.toggle('active', active);
      if (active) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    }
    if (updateHash && location.hash !== `#${id}`) history.pushState(null, '', `#${id}`);
    window.scrollTo({ top: 0, behavior: 'auto' });
    await loadSection(id);
  };
  for (const link of links) link.addEventListener('click', event => {
    event.preventDefault();
    show(link.hash.slice(1));
  });
  document.addEventListener('click', event => {
    const link = event.target.closest && event.target.closest('.horizon-link');
    if (!link) return;
    event.preventDefault();
    show(link.hash.slice(1));
  });
  window.addEventListener('popstate', () => {
    show(location.hash.slice(1), false);
  });
  for (const section of sections) section.hidden = section.id !== state.activeSection;
  for (const link of links) {
    const active = link.hash === `#${state.activeSection}`;
    link.classList.toggle('active', active);
    if (active) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  }
  state.showSection = show;
}
// Los tres analizadores comparten panel: eran tres tarjetas casi vacias apiladas.
const ANALYZER_TABS = [['zone', 'analyzer-tab-zone', 'analyzer-zone'], ['range', 'analyzer-tab-range', 'analyzer-range'], ['breakout', 'analyzer-tab-breakout', 'analyzer-breakout'], ['tramo', 'analyzer-tab-tramo', 'analyzer-tramo']];
const ANALYZER_INPUTS = ['zone-low', 'zone-high', 'range-low', 'range-high', 'range-start', 'range-end', 'breakout-level', 'tramo-desde', 'tramo-hasta'];
function showAnalyzer(key) {
  for (const [name, tabId, paneId] of ANALYZER_TABS) {
    const tab = $(tabId);
    const pane = $(paneId);
    const active = name === key;
    if (tab) { tab.classList.toggle('active', active); tab.setAttribute('aria-selected', active ? 'true' : 'false'); }
    if (pane) pane.hidden = !active;
  }
}
function initAnalyzer() {
  for (const [name, tabId] of ANALYZER_TABS) {
    const tab = $(tabId);
    if (tab) tab.addEventListener('click', () => showAnalyzer(name));
  }
  // Un valor escrito a mano deja de ser recargable: solo se repone lo que puso el panel.
  for (const id of ANALYZER_INPUTS) {
    const input = $(id);
    if (input) input.addEventListener('input', () => { delete input.dataset.auto; });
  }
}
// Un precio de BTC escrito a mano no significa nada en SOL: al cambiar de activo todo
// vuelve a ser recargable y la siguiente precarga lo sustituye.
function releaseAnalyzerInputs() {
  for (const id of ANALYZER_INPUTS) {
    const input = $(id);
    if (input) input.dataset.auto = '1';
  }
}
function presetInput(id, value) {
  const input = $(id);
  if (!input || value === null || value === undefined || value === '') return;
  if (input.value !== '' && input.dataset.auto !== '1') return;
  input.value = typeof value === 'number' ? String(Number(value.toFixed(value >= 1000 ? 2 : 4))) : value;
  input.dataset.auto = '1';
}
// Precarga con lo que el propio dashboard ya detecto: zona activa o soporte mas cercano,
// rango de Wyckoff con sus fechas y la resistencia como nivel de ruptura.
function presetAnalyzer(barriers, wyckoff) {
  const zone = (barriers || {}).active_zone || (barriers || {}).nearest_support;
  if (zone) { presetInput('zone-low', asNumber(zone.low)); presetInput('zone-high', asNumber(zone.high)); }
  const range = (wyckoff || {}).range;
  if (range && range.available !== false) {
    presetInput('range-low', asNumber(range.low));
    presetInput('range-high', asNumber(range.high));
    presetInput('range-start', range.from);
    presetInput('range-end', range.to);
  }
  const resistance = (barriers || {}).nearest_resistance;
  if (resistance) presetInput('breakout-level', asNumber(resistance.low));
}
async function boot() {
  try {
    initCharts();
    initSectionNav();
    const zoneForm = $('zone-form');
    if (zoneForm) zoneForm.addEventListener('submit', event => { submitZone(event).catch(error => console.error(error)); });
    const rangeForm = $('range-form');
    if (rangeForm) rangeForm.addEventListener('submit', event => { submitRange(event).catch(error => console.error(error)); });
    const tramoForm = $('tramo-form');
    if (tramoForm) tramoForm.addEventListener('submit', event => { submitTramo(event).catch(error => console.error(error)); });
    const breakoutForm = $('breakout-form');
    if (breakoutForm) breakoutForm.addEventListener('submit', event => { submitBreakout(event).catch(error => console.error(error)); });
    initAnalyzer();
    initDeltaProfile();
    const intradayMode = $('price-mode-intraday');
    if (intradayMode) intradayMode.addEventListener('click', () => setPriceMode('intraday'));
    const wyckoffMode = $('price-mode-wyckoff');
    if (wyckoffMode) {
      wyckoffMode.disabled = true;
      wyckoffMode.addEventListener('click', () => setPriceMode('wyckoff'));
    }
    initTradingProfile();
    initHypothesis();
    initDiffToggle();
    state.symbols = await api('/api/symbols');
    if (state.symbols.length && !state.symbols.some(s => s.symbol === state.symbol)) state.symbol = state.symbols[0].symbol;
    renderTabs();
    connectStream();
    await refreshOverview(true);
    await loadSection(state.activeSection, true);
    state.refreshTimer = window.setInterval(() => {
      refreshOverview().catch(error => console.error(error));
      loadSection(state.activeSection).catch(error => console.error(error));
    }, 15000);
  } catch (error) {
    console.error(error);
    setConnection('bad', 'Error de inicialización');
  };
}
document.addEventListener('DOMContentLoaded', boot);

