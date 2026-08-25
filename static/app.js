'use strict';

const state = {
  symbol: 'BTCUSDT_PERP.A', symbols: [], charts: {}, series: {}, source: null,
  // Una serie de linea se dibuja como VARIAS series, una por tramo contiguo, para que los
  // huecos no se unan con una recta. `seriesMeta` guarda con que opciones clonarlas.
  seriesMeta: {}, seriesPool: {},
  refreshTimer: null, refreshSeq: 0, activeSection: 'mesa', viewLoadedAt: {},
  dashboard: {}, confidence: { rows: [] }, health: { status: 'degraded', services: [] },
  trend: {}, swing: {}, structureDetail: {}, wyckoff: {}, externalMacro: {}, daily: { rows: [] }, lastContextAt: 0,
  priceMode: 'intraday', priceBars: [],
  profileWindow: { interval: '4hour', days: 90 },
  // Perfil de trading: cambia QUE temporalidad manda, nunca los datos brutos.
  // Direccion y setup son INDEPENDIENTES: la primera dice hacia donde mira el operador, el
  // segundo que tiene que pasar para confirmarlo. Antes eran un unico selector.
  tradingProfile: 'intradia', tfProfile: {}, direction: 'long', setup: 'ninguno', hypothesisData: {}, desk: {},
  // Errores por endpoint: distinguir "sin datos" de "el endpoint fallo".
  errors: {},
};
const COLORS = { bg: '#111316', text: '#949ba4', grid: '#24292f', green: '#39d98a', red: '#ff5f69', blue: '#58a6ff', violet: '#bc8cff', amber: '#f6bd60', cyan: '#4cc9f0' };

function $(id) { return document.getElementById(id); }
// ESTRICTA a proposito. `Number()` convierte en 0 varias formas de "no hay dato":
// Number(null)===0, Number('')===0, Number('  ')===0, Number(false)===0, Number([])===0.
// Con la version laxa, un CVD ausente se pintaba como un cero medido y una liquidacion que
// nunca llego valia "0 USD liquidados". Aqui solo pasan numeros y cadenas numericas; el
// cero REAL sigue siendo 0.
function asNumber(value) {
  if (value === null || value === undefined || typeof value === 'boolean') return null;
  if (typeof value === 'string' && value.trim() === '') return null;
  if (typeof value !== 'number' && typeof value !== 'string') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}
// Punto de una serie temporal, o null si el valor no existe. Devolver null (en vez de
// {time, value: 0}) permite filtrar el hueco: una serie de linea que recibe 0 dibuja una
// caida al eje que se lee como "el dato bajo a cero".
function seriesPoint(time, value) {
  const n = asNumber(value);
  return n === null ? null : { time, value: n };
}
// Convierte filas a puntos DESCARTANDO los ausentes. Se conserva porque hay sitios donde
// solo hace falta la lista de puntos; para GRAFICAR usa `seriesSegments`, que ademas parte
// la serie en los huecos (si no, el motor une los dos extremos con una recta).
function seriesPoints(rows, timeOf, valueOf) {
  const points = [];
  let dropped = 0;
  safeArray(rows).forEach((row) => {
    const time = timeOf(row);
    const point = time === null || time === undefined ? null : seriesPoint(time, valueOf(row));
    if (point === null) dropped += 1; else points.push(point);
  });
  points.dropped = dropped;
  return points;
}

// Parte las filas en TRAMOS contiguos de dato presente y describe los huecos que los separan.
//
// Quitar el punto ausente no basta: lightweight-charts une los dos puntos que quedan a los
// lados con una recta, y esa recta se lee como "aqui hubo precio". Medido contra la version
// 5.2.0 vendorizada (`scratchpad/gapexp.html`), NI whitespace NI `value: null` rompen la
// linea de un LineSeries: lo unico que produce discontinuidad real es usar UNA SERIE POR
// TRAMO. El whitespace si sirve, y hace falta, para reservar el ancho del hueco en el eje,
// porque el eje coloca los puntos por indice y sin el los huecos se comprimen a nada.
//
// Un hueco al principio o al final tiene `from`/`to` en null: no se inventa un extremo.
function seriesSegments(rows, timeOf, valueOf) {
  const timeline = [];
  const segments = [];
  const gaps = [];
  let actual = null;
  let ultimoPresente = null;
  let ausentesSeguidos = 0;
  let primerAusente = null;

  const cerrarHueco = (hasta) => {
    if (!ausentesSeguidos) return;
    gaps.push({
      from: ultimoPresente,
      to: hasta,
      samples: ausentesSeguidos,
      first_missing: primerAusente,
      seconds: ultimoPresente !== null && hasta !== null ? hasta - ultimoPresente : null,
    });
    ausentesSeguidos = 0;
    primerAusente = null;
  };

  safeArray(rows).forEach((row) => {
    const time = timeOf(row);
    if (time === null || time === undefined || !Number.isFinite(time)) return;
    timeline.push(time);
    const value = asNumber(valueOf(row));
    if (value === null) {
      // Hueco: cierra el tramo en curso y empieza a contar muestras ausentes.
      if (!ausentesSeguidos) primerAusente = time;
      ausentesSeguidos += 1;
      actual = null;
      return;
    }
    cerrarHueco(time);
    if (actual === null) { actual = []; segments.push(actual); }
    actual.push({ time, value });
    ultimoPresente = time;
  });
  cerrarHueco(null);  // hueco final: no tiene extremo derecho

  timeline.sort((a, b) => a - b);
  const presentes = segments.reduce((n, s) => n + s.length, 0);
  return {
    segments,
    gaps,
    timeline: timeline.filter((t, i) => i === 0 || t !== timeline[i - 1]),
    present: presentes,
    missing: timeline.length - presentes,
    total: timeline.length,
    gap_seconds: gaps.reduce((n, g) => n + (g.seconds || 0), 0),
  };
}

// Texto para el pie del panel: cuantos huecos, cuanto duran y donde. Sin esto el operador
// ve la discontinuidad pero no sabe cuanto tiempo falta.
function gapCaption(info) {
  if (!info || !info.gaps.length) {
    return info && info.total ? `${info.total} muestras · sin huecos` : 'Sin datos';
  }
  const minutos = Math.round(info.gap_seconds / 60);
  const detalle = info.gaps.slice(0, 3).map(g => (
    g.from === null ? `inicio→${dateTime(g.to * 1000)}`
      : g.to === null ? `${dateTime(g.from * 1000)}→fin`
        : `${dateTime(g.from * 1000)}→${dateTime(g.to * 1000)}`
  )).join(', ');
  const resto = info.gaps.length > 3 ? ` (+${info.gaps.length - 3} más)` : '';
  return `${info.gaps.length} hueco(s) · ${info.missing} muestras ausentes`
    + `${minutos ? ` · ${minutos} min sin datos` : ''} · ${detalle}${resto}`;
}
function signClass(value) { const n = asNumber(value); return n === null || n === 0 ? 'neutral' : n > 0 ? 'positive' : 'negative'; }
function priceDirection1h(value) { const n = asNumber(value); if (n === null) return '1 h N/D'; return `1 h ${n > 0 ? 'al alza' : n < 0 ? 'a la baja' : 'lateral'}`; }
function ts(value) { return Math.floor(new Date(value).getTime() / 1000); }
function money(value, digits = 1) { const n = asNumber(value); if (n === null) return '—'; const abs = Math.abs(n); let d = 1, suffix = ''; if (abs >= 1e9) { d = 1e9; suffix = 'B'; } else if (abs >= 1e6) { d = 1e6; suffix = 'M'; } else if (abs >= 1e3) { d = 1e3; suffix = 'K'; } return `${n < 0 ? '-' : ''}$${(abs / d).toFixed(digits)}${suffix}`; }
function number(value, digits = 2) { const n = asNumber(value); return n === null ? '—' : n.toLocaleString('en-US', { maximumFractionDigits: digits }); }
function pct(value, digits = 2) { const n = asNumber(value); return n === null ? '—' : `${n >= 0 ? '+' : ''}${n.toFixed(digits)}%`; }
// Coinalyze ya entrega el funding en puntos porcentuales (0.01 = 0.01%).
function rate(value) { const n = asNumber(value); return n === null ? '—' : `${n.toFixed(4)}%`; }
function dateTime(value) { return value ? new Date(value).toLocaleString('es-MX', { hour12: false }) : '—'; }
function safeArray(value) { return Array.isArray(value) ? value : []; }
// Las series ya no llegan como un array pelado: vienen en un sobre {rows, coverage,
// data_gaps} porque el hueco viaja CON el dato (K03). Sin esta funcion, safeArray veria
// un objeto y devolveria [] -un panel vacio sin decir por que-, que es la peor de las
// respuestas posibles. Se sigue aceptando el array por si queda algun consumidor viejo.
function filasDe(sobre) { return Array.isArray(sobre) ? sobre : safeArray(sobre && sobre.rows); }
// "N/D" explicito para las metricas que ANTES fabricaban un cero. El guion largo sigue
// usandose en las tablas densas, pero donde el cero mentia hace falta decir por que no hay
// numero, no dejar un simbolo mudo.
function nd(value, formatter) { return asNumber(value) === null ? 'N/D' : formatter(value); }

async function api(path) {
  const response = await fetch(path, { headers: { Accept: 'application/json' }, cache: 'no-store' });
  if (!response.ok) { const text = await response.text(); console.error('API_ERROR', path, response.status, text.slice(0, 500)); throw new Error(`${response.status} ${path}`); }
  return response.json();
}
// Un endpoint caido y un endpoint sin datos NO son lo mismo. Antes ambos devolvian el
// fallback vacio y el operador leia "sin datos" ante un 500 de la API o un Postgres caido.
// Ahora el error se conserva en state.errors y la barra global lo muestra.
async function maybe(path, fallback) {
  try {
    const result = await api(path);
    if (state.errors) delete state.errors[path];
    return result;
  } catch (error) {
    if (state.errors) {
      state.errors[path] = { message: String(error && error.message || error), at: Date.now() };
    }
    console.error('endpoint fallo', path, error);
    return fallback;
  }
}
function lastEndpointError() {
  const entries = Object.entries(state.errors || {});
  if (!entries.length) return null;
  entries.sort((a, b) => b[1].at - a[1].at);
  return { path: entries[0][0], ...entries[0][1], count: entries.length };
}

// El formateador por defecto del motor solo escribe la fecha en los cambios de dia: con
// 48 h de velas de 5 min el eje quedaba lleno de HH:MM y practicamente sin fechas. Estas
// marcas siempre llevan dia/mes. Las series usan UTCTimestamp, asi que el eje es UTC.
const MESES_ES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
function pad2(value) { return String(value).padStart(2, '0'); }
function tickMarkFormatter(withTime) {
  return (time, tickMarkType) => {
    const d = new Date(time * 1000);
    const dia = `${pad2(d.getUTCDate())}/${pad2(d.getUTCMonth() + 1)}`;
    if (tickMarkType === 0) return String(d.getUTCFullYear());                       // Año
    if (tickMarkType === 1) return `${MESES_ES[d.getUTCMonth()]} ${String(d.getUTCFullYear()).slice(2)}`;
    if (tickMarkType === 2 || !withTime) return dia;                                  // Día del mes
    return `${dia} ${pad2(d.getUTCHours())}:${pad2(d.getUTCMinutes())}`;               // Hora
  };
}
function crosshairFormatter(withTime) {
  return time => {
    const d = new Date(time * 1000);
    const fecha = `${pad2(d.getUTCDate())}/${pad2(d.getUTCMonth() + 1)}/${d.getUTCFullYear()}`;
    return withTime ? `${fecha} ${pad2(d.getUTCHours())}:${pad2(d.getUTCMinutes())} UTC` : `${fecha} UTC`;
  };
}
// El eje por defecto imprime el float crudo: la serie de CVD marcaba "418951166.51" y la de
// OI "7100000000.00". Estos formateadores aplican al eje, a la etiqueta del crosshair y a la
// del price line, que es donde se leen los numeros mientras se opera.
function axisMoney(value) { return money(value, 2); }
function axisPrice(value) { const n = asNumber(value); if (n === null) return '—'; const digits = Math.abs(n) >= 1000 ? 2 : Math.abs(n) >= 1 ? 3 : 6; return n.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits }); }
function chartOptions(container, withTime = true, priceFormatter = axisPrice) { return { width: container.clientWidth, height: container.clientHeight, layout: { background: { type: LightweightCharts.ColorType.Solid, color: COLORS.bg }, textColor: COLORS.text, fontSize: 10 }, grid: { vertLines: { color: COLORS.grid }, horzLines: { color: COLORS.grid } }, rightPriceScale: { borderColor: COLORS.grid }, timeScale: { borderColor: COLORS.grid, timeVisible: withTime, secondsVisible: false, tickMarkFormatter: tickMarkFormatter(withTime) }, crosshair: { mode: LightweightCharts.CrosshairMode.Normal }, localization: { locale: 'es-MX', timeFormatter: crosshairFormatter(withTime), priceFormatter } }; }
function newChart(id, withTime = true, priceFormatter = axisPrice) { const container = $(id); const chart = LightweightCharts.createChart(container, chartOptions(container, withTime, priceFormatter)); new ResizeObserver(() => chart.resize(container.clientWidth, container.clientHeight)).observe(container); state.charts[id] = chart; return chart; }
// Registra una serie de LINEA y guarda con que opciones y en que grafico se creo, para poder
// clonarla luego: cada TRAMO de datos contiguos necesita su propia serie (ver seriesSegments).
function lineSeries(chart, chartId, key, options) {
  const serie = chart.addSeries(LightweightCharts.LineSeries, options);
  state.series[key] = serie;
  state.seriesMeta[key] = { chartId, options };
  state.seriesPool[key] = [serie];
  return serie;
}
function initCharts() {
  if (!window.LightweightCharts) throw new Error('Lightweight Charts no cargó');
  let chart = newChart('price-chart');
  // Las velas no se unen entre si: cada barra es independiente, asi que un hueco ya se ve.
  state.series.price = chart.addSeries(LightweightCharts.CandlestickSeries, { upColor: COLORS.green, downColor: COLORS.red, borderUpColor: COLORS.green, borderDownColor: COLORS.red, wickUpColor: COLORS.green, wickDownColor: COLORS.red });
  chart = newChart('cvd-chart', true, axisMoney);
  lineSeries(chart, 'cvd-chart', 'cvdSpot', { color: COLORS.green, lineWidth: 2, priceLineVisible: false });
  lineSeries(chart, 'cvd-chart', 'cvdFut', { color: COLORS.blue, lineWidth: 2, priceLineVisible: false });
  lineSeries(chart, 'cvd-chart', 'cvdDiff', { color: COLORS.violet, lineWidth: 2, priceLineVisible: false });
  chart = newChart('oi-chart', true, axisMoney);
  lineSeries(chart, 'oi-chart', 'oi', { color: COLORS.cyan, lineWidth: 2, priceLineVisible: false });
  chart = newChart('whale-chart', true, axisMoney);
  // Histograma: barras sueltas, tampoco hay nada que unir.
  state.series.whale = chart.addSeries(LightweightCharts.HistogramSeries, { priceFormat: { type: 'custom', formatter: axisMoney }, priceLineVisible: false });
  chart = newChart('daily-chart', false, axisMoney);
  lineSeries(chart, 'daily-chart', 'daily', { color: COLORS.violet, lineWidth: 2, priceLineVisible: false });
}

const MAX_SEGMENTS = 40;
// Pinta una serie de linea partida en sus tramos, de forma que los huecos se VEAN.
//
// La primera serie del grupo carga ademas la linea de tiempo completa como whitespace: eso
// reserva en el eje el ancho real del hueco (el eje coloca por indice, y sin los huecos
// reservados un corte de dos horas se dibujaria del mismo ancho que uno de un minuto).
function setGappedLine(key, rows, timeOf, valueOf) {
  const meta = state.seriesMeta[key];
  if (!meta) return null;
  const info = seriesSegments(rows, timeOf, valueOf);
  const pool = state.seriesPool[key];
  const chart = state.charts[meta.chartId];
  // Serie demasiado fragmentada: se dibuja SOLO el eje. Trocearla en cientos de series
  // seria inutilizable, y dibujarla de una pieza volveria a sugerir continuidad.
  const fragmentada = info.segments.length > MAX_SEGMENTS;
  info.too_fragmented = fragmentada;
  const necesarias = fragmentada ? 1 : Math.max(1, info.segments.length);
  while (pool.length < necesarias) {
    pool.push(chart.addSeries(LightweightCharts.LineSeries, meta.options));
  }
  for (let i = 0; i < pool.length; i++) {
    if (i >= necesarias) { pool[i].setData([]); continue; }
    if (fragmentada) { pool[0].setData(info.timeline.map(t => ({ time: t }))); continue; }
    const tramo = info.segments[i] || [];
    if (i === 0) {
      const propios = new Set(tramo.map(p => p.time));
      const huecos = info.timeline.filter(t => !propios.has(t)).map(t => ({ time: t }));
      pool[0].setData(huecos.concat(tramo).sort((a, b) => a.time - b.time));
    } else {
      pool[i].setData(tramo);
    }
  }
  return info;
}
// Escribe el recuento de huecos bajo la grafica, y el detalle en el tooltip del elemento.
function renderGapNote(id, info) {
  const nodo = $(id);
  if (!nodo) return;
  const texto = gapCaption(info);
  nodo.textContent = info && info.too_fragmented
    ? `${texto} · demasiados tramos para dibujarla sin sugerir continuidad`
    : texto;
  nodo.className = `source-note${info && info.gaps.length ? ' has-gaps' : ''}`;
  nodo.title = info && info.gaps.length
    ? 'Los tramos separados indican intervalos SIN datos. No se interpola ni se rellena con cero.'
    : 'Serie continua: no faltan muestras en la ventana.';
}

function renderTabs() { const tabs = $('symbol-tabs'); tabs.replaceChildren(); for (const item of state.symbols) { const button = document.createElement('button'); button.type = 'button'; button.textContent = item.asset; button.className = item.symbol === state.symbol ? 'active' : ''; button.addEventListener('click', () => selectSymbol(item.symbol)); tabs.append(button); } }
// Sparkline de la serie diaria ya descargada. Sin ejes ni escala: solo dice la forma del
// ultimo tramo. El numero grande sigue siendo el dato; esto es contexto.
function sparkline(values) {
  const points = safeArray(values).map(asNumber).filter(v => v !== null);
  if (points.length < 3) return null;
  const NS = 'http://www.w3.org/2000/svg';
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = (max - min) || Math.abs(max) || 1;
  const step = 100 / (points.length - 1);
  const coords = points.map((v, i) => `${(i * step).toFixed(2)},${(23 - ((v - min) / span) * 20).toFixed(2)}`);
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', '0 0 100 26');
  svg.setAttribute('preserveAspectRatio', 'none');
  svg.setAttribute('class', `spark ${points[points.length - 1] >= points[0] ? 'up' : 'down'}`);
  svg.setAttribute('aria-hidden', 'true');
  const area = document.createElementNS(NS, 'polygon');
  area.setAttribute('class', 'spark-area');
  area.setAttribute('points', `0,26 ${coords.join(' ')} 100,26`);
  const line = document.createElementNS(NS, 'polyline');
  line.setAttribute('class', 'spark-line');
  line.setAttribute('points', coords.join(' '));
  svg.append(area, line);
  return svg;
}
function card(label, value, sub, className = '', series = null, seriesTitle = '') {
  const node = document.createElement('article');
  node.className = 'summary-card';
  const l = document.createElement('div');
  l.className = 'label';
  l.textContent = label;
  const v = document.createElement('div');
  v.className = `value ${className}`;
  v.textContent = value;
  const s = document.createElement('div');
  s.className = 'sub';
  s.textContent = sub;
  node.append(l, v, s);
  const spark = sparkline(series);
  if (spark) { node.append(spark); node.title = seriesTitle; }
  return node;
}
function dailySeries(field) { return safeArray((state.daily || {}).rows).map(row => row[field]); }
// Funding ausente NO es funding tranquilo: sin dato la tarjeta queda neutra y lo dice el
// propio valor ('—'), pero nunca se afirma que este por debajo del umbral de tension.
function fundingClass(value) {
  const n = asNumber(value);
  return n !== null && Math.abs(n) >= .03 ? 'negative' : 'neutral';
}
function renderSummary(s, scalp, cvdSwing = {}) {
  const sessions = safeArray((state.daily || {}).rows).length;
  const note = sessions ? `Últimas ${sessions} sesiones` : '';
  $('summary').replaceChildren(
    card('Precio', money(s.price, 2), priceDirection1h(s.price_dir_1h), signClass(s.price_dir_1h), dailySeries('price_close'), `Cierre diario · ${note}`),
    card('CVD spot 24 h', money(s.cvd_spot_24h), 'Binance + Bybit', signClass(s.cvd_spot_24h), dailySeries('cumulative_spot'), `CVD spot acumulado · ${note}`),
    card('Open Interest', money(s.oi), `${pct(s.oi_chg_24h_pct)} / 24 h`, signClass(s.oi_chg_24h_pct), dailySeries('oi_close'), `Open interest al cierre · ${note}`),
    card('Funding / liquidez', rate(s.fr_avg), `${number(scalp.spread_bps, 2)} bps · book ${scalp.book_status || 'sin datos'}`, fundingClass(s.fr_avg), dailySeries('fr_avg'), `Funding medio por sesión · ${note}`),
  );
  $('price-context').textContent = `${money(s.price, 2)} · Δ3m ${money(s.delta_3min)}`;
}
function rowDL(container, name, value, cls = '') { const row = document.createElement('div'); const dt = document.createElement('dt'); const dd = document.createElement('dd'); dt.textContent = name; dd.textContent = value; dd.className = cls; row.append(dt, dd); container.append(row); }

function renderExecutionLevels(scalp) {
  const levels = $('levels');
  levels.replaceChildren();
  rowDL(levels, 'VWAP sesión', money(scalp.session_vwap, 2), 'neutral');
  // Sin basis utilizable se dice POR QUE, no se pinta un guion mudo.
  rowDL(levels, 'Basis perp-spot',
    scalp.basis_bps === null || scalp.basis_bps === undefined
      ? (scalp.basis_status === 'STALE' ? 'Desfasado' : scalp.basis_status === 'UNAVAILABLE' ? 'Sin datos' : '—')
      : `${number(scalp.basis_bps, 2)} bps`,
    scalp.basis_bps === null || scalp.basis_bps === undefined ? 'negative' : signClass(scalp.basis_bps));
  // Estos tres SOLIAN publicar 0 cuando faltaba el insumo: "sobre el VWAP", "OI plano" y
  // "0 USD liquidados" son afirmaciones, no huecos. Ahora el hueco se dice N/D.
  rowDL(levels, 'Dist VWAP', nd(scalp.vwap_dist_pct, pct), signClass(scalp.vwap_dist_pct));
  // El spread BRUTO se muestra en NEUTRO. Colorearlo de rojo al pasar de 5 bps era el mismo
  // umbral universal que se retiró del backend: 5 bps se comen un cuarto de un scalp de 20 y
  // son ruido en un swing de 400. El color lo decide `execution.verdict`, que compara el
  // coste total contra el objetivo de ESTA operación.
  rowDL(levels, 'Spread', nd(scalp.spread_bps, v => `${number(v, 2)} bps`), 'neutral');
  // No es un "imbalance" en -1..+1: es la fraccion bid/(bid+ask), 0-1 centrada en 0.5.
  const bidShare = asNumber(scalp.imbalance_l5);
  rowDL(levels, 'Bid share L1/L5/L10 (0-1)', `${number(scalp.imbalance_l1, 2)} / ${number(scalp.imbalance_l5, 2)} / ${number(scalp.imbalance_l10, 2)}`, bidShare === null ? 'neutral' : signClass(bidShare - .5));
  rowDL(levels, 'OI 15m', nd(scalp.oi_chg_15m_pct, pct), signClass(scalp.oi_chg_15m_pct));
  const liqMedida = scalp.liquidations_measured === true;
  rowDL(levels, 'Liquidaciones 5m (L/S)',
    liqMedida ? `${money(scalp.long_liq_5m)} / ${money(scalp.short_liq_5m)}` : 'N/D · feed no medido',
    liqMedida ? 'neutral' : 'negative');
  rowDL(levels, 'Absorción', scalp.absorption || 'N/D', scalp.absorption && scalp.absorption.includes('ventas') ? 'positive' : scalp.absorption && scalp.absorption.includes('compras') ? 'negative' : 'neutral');
}
// Los cuatro cuadrantes de flujo. La clasificacion sale del signo de AMBAS patas, que es la
// lectura que informa: dos mercados con escalas distintas no se restan para sacar direccion.
const FLOW_QUADRANTS = {
  ambos_compran: ['Spot compra / futuros compran', 'positive'],
  ambos_venden: ['Spot vende / futuros venden', 'negative'],
  spot_compra: ['Spot compra / futuros venden', 'neutral'],
  spot_vende: ['Spot vende / futuros compran', 'neutral'],
  plano: ['Una pata plana', 'neutral'],
  sin_datos: ['Sin datos', 'neutral'],
};
// ---------------- jerarquia visual del perfil ----------------
// El perfil NO cambia ningun dato bruto: cambia que temporalidad manda la lectura. Aqui se
// traduce la jerarquia publicada por /api/profile a una clase CSS por fila, de forma que en
// intradia destaquen 4h/1h y 18m/15m/5m, y en swing 3d/1d/8h y 4h/1h.
const LAYER_RANK = { contexto: 1, confirmacion: 2, entrada: 3, gatillo: 3, ejecucion: 4 };
function profileLayerOf(timeframe) {
  const layers = (state.tfProfile || {}).layers || {};
  for (const [name, layer] of Object.entries(layers)) {
    for (const entry of safeArray(layer.timeframes)) {
      if (entry.timeframe === timeframe) return name;
    }
  }
  return null;
}
// Ancla temporal del snapshot de Mesa. Se publica para que se vea que todos los paneles de
// la pestana describen el MISMO instante, y para que un snapshot viejo se note.
function renderDeskAsOf(desk) {
  const pill = $('desk-asof');
  if (!pill) return;
  const asOf = desk && desk.as_of;
  if (!asOf) {
    pill.textContent = 'Snapshot N/D';
    pill.className = 'live-pill negative';
    pill.title = 'La Mesa no recibió snapshot coherente en este ciclo';
    return;
  }
  const edad = Math.max(0, Math.round((Date.now() - new Date(asOf).getTime()) / 1000));
  const parcial = desk.partial || {};
  const faltan = safeArray(parcial.scalp_missing_components).length + safeArray(parcial.profile_missing_data).length;
  pill.textContent = `Snapshot ${dateTime(asOf)} · ${edad}s${faltan ? ` · ${faltan} parcial(es)` : ''}`;
  pill.className = `live-pill ${edad > 180 || faltan ? 'negative' : 'neutral'}`;
  pill.title = `Todos los paneles de la Mesa comparten este ancla. `
    + `Evidencia scalp ${number(parcial.scalp_coverage_pct, 0)}% · marcos ${number(parcial.profile_coverage_pct, 0)}%`;
}

// Cabecera de la Mesa: dice EXPLICITAMENTE que temporalidades manda el perfil activo, para
// que el enfasis de las tablas no sea un efecto visual sin explicacion.
function renderProfileEmphasis(result) {
  const layers = (result || {}).layers || {};
  const listar = nombre => safeArray((layers[nombre] || {}).timeframes).map(t => t.timeframe).join(' · ');
  const set = (id, texto) => { const el = $(id); if (el) el.textContent = texto || 'N/D'; };
  set('emphasis-contexto', listar('contexto'));
  set('emphasis-confirmacion', listar('confirmacion'));
  set('emphasis-entrada', listar('entrada') || listar('gatillo'));
  const nota = $('emphasis-note');
  if (nota) {
    const ejecucion = listar('ejecucion');
    nota.textContent = ejecucion
      ? `${ejecucion} solo ejecutan: no invalidan la tesis en ${result.profile_label || result.profile || 'este perfil'}.`
      : (result.invalidation || '');
  }
}
// Marca la fila con su capa. `data-layer` permite al CSS destacar contexto/confirmacion y
// atenuar la capa de ejecucion, que en swing no debe robar atencion.
function markProfileLayer(tr, timeframe) {
  // Sin jerarquia cargada todavia no se marca NADA: atenuar toda la tabla porque el perfil
  // aun no ha llegado seria un artefacto de carga, no una lectura.
  if (!Object.keys((state.tfProfile || {}).layers || {}).length) return null;
  const layer = profileLayerOf(timeframe);
  if (!layer) { tr.dataset.layer = 'fuera'; return null; }
  tr.dataset.layer = layer;
  tr.dataset.rank = String(LAYER_RANK[layer] || 9);
  tr.title = `Capa ${layer} del perfil ${state.tradingProfile}`;
  return layer;
}
// Ojo con el nombre: `flowQuadrant` (sin prefijo) ya existe mas abajo y clasifica SESIONES
// diarias. Esta trabaja sobre las ventanas de la matriz de delta.
function deltaFlowQuadrant(spotDelta, futDelta) {
  const s = asNumber(spotDelta);
  const f = asNumber(futDelta);
  if (s === null || f === null) return 'sin_datos';
  if (s === 0 || f === 0) return 'plano';
  if (s > 0 && f > 0) return 'ambos_compran';
  if (s < 0 && f < 0) return 'ambos_venden';
  return s > 0 ? 'spot_compra' : 'spot_vende';
}
// Delta normalizado por su PROPIO volumen: es lo unico que permite comparar las dos patas
// entre si sin que la escala del perp aplaste al spot.
function deltaShare(delta, volume) {
  const d = asNumber(delta);
  const v = asNumber(volume);
  return d === null || v === null || v === 0 ? null : d / v;
}
function initDiffToggle() {
  const box = $('show-diff');
  if (!box) return;
  const apply = () => {
    for (const cell of document.querySelectorAll('.diff-col')) cell.hidden = !box.checked;
    const note = $('delta-diff-note');
    if (note) note.hidden = !box.checked;
  };
  box.addEventListener('change', apply);
  apply();
}
function renderDeltaMatrix(rows) {
  const body = $('delta-matrix');
  body.replaceChildren();
  const verDiff = !!($('show-diff') && $('show-diff').checked);
  for (const r of safeArray(rows)) {
    const tr = document.createElement('tr');
    markProfileLayer(tr, r.window);
    const complete = r.coverage_status === 'complete';
    const coverage = complete ? 'Completa' : (r.coverage_status === 'unavailable' ? 'Sin datos' : 'Parcial');
    td(tr, r.window, '');
    const statusCell = td(tr, coverage, complete ? 'positive' : 'negative');
    statusCell.title = `Spot: ${r.spot_source || 'sin fuente'} · lag ${number(r.spot_end_gap_seconds, 0)} s`;
    // Lo direccional son las DOS patas y su cuadrante. El diferencial spot-futuros no lo es
    // (medido: su signo es el del CVD de futuros invertido en 93-94% de las sesiones), asi
    // que baja a columna de auditoria, sin color y oculta por defecto.
    td(tr, nd(r.spot_delta, money), signClass(r.spot_delta));
    td(tr, nd(r.fut_delta, money), signClass(r.fut_delta));
    const spotShare = deltaShare(r.spot_delta, r.spot_volume);
    const futShare = deltaShare(r.fut_delta, r.fut_volume);
    td(tr, spotShare === null ? 'N/D' : number(spotShare, 3), signClass(spotShare));
    td(tr, futShare === null ? 'N/D' : number(futShare, 3), signClass(futShare));
    const quadrant = FLOW_QUADRANTS[deltaFlowQuadrant(r.spot_delta, r.fut_delta)];
    td(tr, quadrant[0], quadrant[1]);
    td(tr, nd(r.fut_volume, money), 'neutral');
    td(tr, r.oi_change_pct == null ? 'N/D' : `${number(r.oi_change_pct, 2)}%`, signClass(r.oi_change_pct));
    const diffCell = td(tr, nd(r.diff, money), 'neutral');
    diffCell.className = 'neutral diff-col';
    diffCell.hidden = !verDiff;
    diffCell.title = 'Resta de dos mercados con escalas distintas: no indica direcci\u00f3n';
    body.append(tr);
  }
}
// Absorcion con la evidencia a la vista: el ratio medido, el umbral que tuvo que superar,
// DE DONDE sale ese umbral, la banda contra su propia distribucion y el tamano de muestra.
function renderAbsorption(rows) {
  const body = $('absorption-matrix');
  body.replaceChildren();
  for (const r of safeArray(rows)) {
    const tr = document.createElement('tr');
    const ctx = r.context || {};
    const cls = r.score > 0 ? 'positive' : r.score < 0 ? 'negative' : 'neutral';
    td(tr, r.window, '');
    td(tr, nd(r.fut_delta, money), signClass(r.fut_delta));
    td(tr, nd(r.delta_ratio, v => number(v, 3)), 'neutral');
    td(tr, nd(r.min_ratio, v => number(v, 3)), 'neutral');
    td(tr, r.threshold_source || 'N/D', r.threshold_source === 'baseline_p75_medido' ? 'positive' : 'neutral');
    td(tr, ctx.band || 'sin baseline', ctx.band === 'extremo' || ctx.band === 'alto' ? 'negative' : 'neutral');
    td(tr, ctx.sample_count == null ? 'N/D' : `n=${number(ctx.sample_count, 0)}`, 'neutral');
    td(tr, nd(r.price_move_pct, pct), signClass(r.price_move_pct));
    const estado = td(tr, r.absorption || 'N/D', cls);
    // La cobertura de la ventana viaja en el tooltip: "Absorción fuerte" medida sobre dos
    // buckets sueltos no vale lo mismo que sobre la ventana entera.
    const cov = r.coverage || {};
    estado.title = cov.buckets == null
      ? 'Sin cobertura declarada'
      : `Cobertura: ${cov.buckets} buckets · ${number(cov.span_seconds, 0)} s de ${cov.window_seconds} s`;
    body.append(tr);
  }
}
// La imbalance es una fraccion 0-1 centrada en 0.5: la barra la hace legible de un vistazo
// sin quitar el numero, que es lo que se compara entre venues.
function imbalanceCell(tr, value) {
  const share = asNumber(value);
  const cell = td(tr, share === null ? '—' : number(share, 2), signClass((share === null ? .5 : share) - .5));
  if (share === null) return cell;
  const gauge = document.createElement('span');
  gauge.className = 'imb-gauge';
  const fill = document.createElement('i');
  const offset = Math.min(Math.max(share, 0), 1) - .5;
  fill.className = offset >= 0 ? 'positive' : 'negative';
  fill.style.left = offset >= 0 ? '50%' : `${(0.5 + offset) * 100}%`;
  fill.style.width = `${Math.abs(offset) * 100}%`;
  gauge.append(fill);
  cell.append(gauge);
  return cell;
}
// El spread por venue tambien va en NEUTRO: comparar bps sueltos contra un literal no dice
// si la operacion sale cara. Eso lo responde `execution_assessment` con objetivo y riesgo.
function renderOrderbook(result) { const body = $('orderbook-body'); body.replaceChildren(); for (const r of safeArray(result.rows)) { const tr = document.createElement('tr'); td(tr, r.exchange, ''); td(tr, nd(r.spread_bps, v => `${number(v, 2)} bps`), 'neutral'); imbalanceCell(tr, r.imbalance_l1); imbalanceCell(tr, r.imbalance_l5); imbalanceCell(tr, r.imbalance_l10); td(tr, pct(r.wall_up_pct), 'neutral'); td(tr, pct(r.wall_down_pct), 'neutral'); body.append(tr); } }
// null !== 0: "no se midio" y "no hubo liquidaciones" son lecturas distintas y el operador
// necesita distinguirlas. Solo se calcula el ratio cuando AMBAS patas existen.
function renderLiquidations(result) {
  const body = $('liq-matrix');
  body.replaceChildren();
  for (const r of safeArray(result.matrix)) {
    const longV = asNumber(r.long_liq);
    const shortV = asNumber(r.short_liq);
    const known = longV !== null && shortV !== null;
    const ratio = known && shortV > 0 ? longV / shortV : null;
    const tr = document.createElement('tr');
    [[r.window, ''],
     [longV === null ? 'Sin dato' : money(longV), longV === null ? 'neutral' : 'negative'],
     [shortV === null ? 'Sin dato' : money(shortV), shortV === null ? 'neutral' : 'positive'],
     [ratio === null ? '\u2014' : number(ratio, 2), known ? signClass(shortV - longV) : 'neutral'],
     [r.events == null ? '\u2014' : number(r.events, 0), 'neutral']].forEach(([v, c]) => td(tr, v, c));
    body.append(tr);
  }
}
function td(tr, value, cls = '') { const cell = document.createElement('td'); cell.textContent = value ?? '—'; cell.className = cls || ''; tr.append(cell); return cell; }

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

function renderSetups(result) { const container = $('setups'); container.replaceChildren(); const setups = result.setups || []; if (!setups.length) { const e = document.createElement('div'); e.className = 'empty'; e.textContent = 'Sin evaluación disponible.'; container.append(e); return; } for (const item of setups) { const stateClass = item.state === 'activo' ? 'active' : item.state === 'vigilancia' ? 'watch' : 'inactive'; const node = document.createElement('article'); node.className = `setup ${stateClass}`; const title = document.createElement('div'); title.className = 'setup-title'; const name = document.createElement('span'); name.textContent = `${item.id} · ${item.name}`; const score = document.createElement('span'); score.className = 'setup-score'; score.textContent = `${item.confidence}/100`; title.append(name, score); const bias = document.createElement('div'); bias.className = 'setup-bias'; bias.textContent = `${String(item.state).toUpperCase()} · ${item.bias}`; node.append(title, bias); const matches = (item.matched || []).slice(0, 3); if (matches.length) { const ul = document.createElement('ul'); ul.className = 'setup-details'; for (const text of matches) { const li = document.createElement('li'); li.textContent = text; ul.append(li); } node.append(ul); } if (item.state !== 'inactivo' && item.reading) { const reading = document.createElement('div'); reading.className = 'setup-reading'; reading.textContent = item.reading; node.append(reading); } container.append(node); } }

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
function renderHealth(result) { const ok = result.status === 'ok'; $('health-status').textContent = String(result.status || 'unknown').toUpperCase(); $('health-status').className = ok ? 'positive' : 'negative'; const container = $('health-services'); container.replaceChildren(); for (const service of result.services || []) { const item = document.createElement('div'); item.className = 'health-item'; const strong = document.createElement('strong'); strong.textContent = service.service; const span = document.createElement('span'); span.textContent = `${service.status} · lag ${number(service.lag_seconds, 0)} s`; item.append(strong, span); container.append(item); } }
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
// Casi todas las ventanas valen cero porque no cruzo ninguna orden del tamano whale: es una
// lectura valida, no un dato ausente. Pero una linea plana en cero gasta un panel entero
// para decirlo, asi que con menos de dos ventanas activas se resume en texto.
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
  const last = active[active.length - 1];
  const detail = last ? ` La última fue ${money(last.value)} el ${new Date(last.time * 1000).toLocaleString('es-MX', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })} UTC.` : '';
  note.textContent = `${active.length} de ${bars.length} ventanas de 15 min con órdenes de tamaño whale.${detail}`;
}
function setConnection(status, text) { $('connection-dot').className = `dot ${status}`; $('connection-text').textContent = text; }
function renderDataConfidence(conf) {
  const row = safeArray(conf.rows)[0];
  const pill = $('data-confidence');
  if (!pill) return;
  if (!row) { pill.textContent = 'Datos no disponibles'; pill.className = 'live-pill negative'; return; }
  const flow = row.flow_8h_complete === true ? '8h' : '8h parcial';
  // Interpolar el campo crudo escribia "Sundefined/Fundefined/Bundefined" cuando el conteo
  // de venues no venia: un hueco tiene que leerse como hueco, no como texto roto.
  const venues = v => { const n = asNumber(v); return n === null ? 'N/D' : number(n, 0); };
  pill.textContent = `Datos ${row.status === 'ok' ? 'OK' : 'degradados'} · S${venues(row.spot_venues_live)}/F${venues(row.futures_venues_live)}/B${venues(row.book_venues_live)} · ${flow}`;
  pill.title = `Cobertura 8h: ${row.flow_8h_complete === true ? 'completa' : 'parcial'} · Spot: ${row.flow_8h_spot_source || 'sin fuente'} · lag ${number(row.flow_8h_spot_end_gap_seconds, 0)} s`;
  pill.className = `live-pill ${row.status === 'ok' ? 'positive' : 'negative'}`;
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
  rowDL(dl, 'Estado', result.status || '—', valid ? 'positive' : 'negative');
  if (!valid && result.reason) rowDL(dl, 'Motivo', result.reason, 'neutral');
  rowDL(dl, 'Futuros', money(result.fut_price, 2), 'neutral');
  rowDL(dl, 'Spot', money(result.spot_price, 2), 'neutral');
  // Edad del ULTIMO TRADE de cada pata: es lo que decide si el basis se publica. El lag de
  // bucket va aparte porque incluye el redondeo de 5 s de la rejilla.
  rowDL(dl, 'Edad fut/spot', `${number(result.fut_age_seconds, 1)}s / ${number(result.spot_age_seconds, 1)}s`, 'neutral');
  rowDL(dl, 'Skew entre patas', result.skew_ms === null || result.skew_ms === undefined ? '—' : `${number(result.skew_ms, 0)} ms (no invalida)`, 'neutral');
}
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

function horizonCard({ name, time, action, side, thesis, trigger, invalidation, metric, link, linkText }) {
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
  for (const [label, value] of [['Confirmar', trigger], ['Salir si', invalidation], ['Evidencia', metric]]) {
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
      name: 'Corto plazo', time: '1–15 minutos', action: shortAction, side: shortAction.includes(shortSide) ? shortSide : 'WAIT',
      thesis: shortThesis, trigger: shortTrigger, invalidation: shortInvalidation,
      metric: `Scalp ${number(scalp.long_score, 0)}L / ${number(scalp.short_score, 0)}S · barrera ${barriers.decision || 'sin lectura'}`,
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
    maybe(`/api/trend-matrix?symbol=${q}`, { timeframes: {} }),
    maybe(`/api/swing-score?symbol=${q}`, {}),
    maybe(`/api/structure-detail?symbol=${q}`, { horizons: {} }),
    maybe(`/api/wyckoff?symbol=${q}`, { available: false }),
    maybe(`/api/daily?symbol=${q}&days=60`, { rows: [] }),
    maybe(`/api/external-macro?symbol=${q}`, { available: false }),
    // UN solo snapshot para la Mesa: perfil, hipotesis, matrices y calidad salen del MISMO
    // calculo y comparten `as_of`. Antes eran dos peticiones que recalculaban trend_matrix,
    // delta_matrix y scalp_context por separado, cada una con su propio `now()`.
    // Va en el tramo lento (60 s): es jerarquia y contexto, no un tick.
    maybe(`/api/desk/state?symbol=${q}&profile=${encodeURIComponent(state.tradingProfile)}&direction=${encodeURIComponent(state.direction)}&setup=${encodeURIComponent(state.setup)}`, { components: {} }),
  ]) : null;
  const [dashboard, ohlcv, confidence, health] = await Promise.all([
    maybe(`/api/dashboard/state?symbol=${q}`, { snapshot: null, scalp: {}, setup: { setups: [] } }),
    maybe(`/api/ohlcv?symbol=${q}&interval=5min&limit=576`, { rows: [] }),
    maybe(`/api/data-confidence?symbol=${q}`, { rows: [] }),
    maybe('/api/healthz', { status: 'degraded', services: [] }),
  ]);
  const context = contextRequest ? await contextRequest : null;
  if (symbol !== state.symbol) return;
  if (requestId !== state.refreshSeq) return;
  if (context) {
    let desk;
    [state.trend, state.swing, state.structureDetail, state.wyckoff, state.daily, state.externalMacro, desk] = context;
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
  if (id === 'flujo') {
    const [cvd, oi, whale, daily, delta, absorption] = await Promise.all([
      maybe(`/api/cvd/divergence?symbol=${q}&interval=5min&limit=576`, []),
      maybe(`/api/oi?symbol=${q}&interval=15min&limit=384`, { rows: [] }),
      maybe(`/api/whale/delta?symbol=${q}&interval=15min&limit=384`, { rows: [] }),
      maybe(`/api/daily?symbol=${q}&days=60`, { rows: [], streak: 0 }),
      maybe(`/api/scalp/delta-matrix?symbol=${q}`, []),
      maybe(`/api/scalp/absorption?symbol=${q}`, []),
    ]);
    if (symbol !== state.symbol) return;
    renderFlowCharts(cvd, null, filasDe(whale));
    renderDailyBars(daily);
    renderDeltaMatrix(delta);
    renderAbsorption(absorption);
  } else if (id === 'liquidez') {
    const [orderbook, execution, impact] = await Promise.all([
      maybe(`/api/scalp/orderbook?symbol=${q}`, { rows: [] }),
      // El perfil viaja al coste: el horizonte decide el umbral de AVISO de spread y con que
      // objetivo se compara el coste. Sin el, un swing recibia lectura de intradia.
      maybe(`/api/scalp/execution-cost?symbol=${q}&profile=${encodeURIComponent(state.tradingProfile)}`, { venues: [] }),
      maybe(`/api/market-impact?symbol=${q}`, { windows: [] }),
    ]);
    if (symbol !== state.symbol) return;
    renderOrderbook(orderbook);
    renderExecutionCost(execution);
    renderMarketImpact(impact);
    await loadDeltaProfile();
  } else if (id === 'estructura') {
    const [structure, macro, passive, trend, swing, structureDetail, wyckoff] = await Promise.all([
      maybe(`/api/structure?symbol=${q}`, { layers: [] }),
      maybe(`/api/macro-context?symbol=${q}`, { metrics: [] }),
      maybe(`/api/passive-flow?symbol=${q}`, { horizons: {} }),
      maybe(`/api/trend-matrix?symbol=${q}`, { timeframes: {} }),
      maybe(`/api/swing-score?symbol=${q}`, {}),
      maybe(`/api/structure-detail?symbol=${q}`, { horizons: {} }),
      maybe(`/api/wyckoff?symbol=${q}`, { available: false }),
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
    const [oi, basis, liq, liqLevels, funding, positioning] = await Promise.all([
      maybe(`/api/oi?symbol=${q}&interval=15min&limit=384`, { rows: [] }),
      maybe(`/api/scalp/basis?symbol=${q}`, {}),
      maybe(`/api/scalp/liquidations?symbol=${q}`, { matrix: [] }),
      maybe(`/api/scalp/liquidation-levels?symbol=${q}&minutes=60&bucket_bps=10&limit=50`, { rows: [] }),
      maybe(`/api/funding-context?symbol=${q}`, {}),
      maybe(`/api/positioning?symbol=${q}`, {}),
    ]);
    if (symbol !== state.symbol) return;
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
      maybe(`/api/data-confidence?symbol=${q}`, { rows: [] }),
      maybe('/api/healthz', { status: 'degraded', services: [] }),
      maybe(`/api/quality/feeds?symbol=${q}`, { feeds: [], metrics: [] }),
    ]);
    if (symbol !== state.symbol) return;
    renderQuality(confidence, health);
    renderFeedQuality(quality);
    renderMetricQuality(quality);
  } else if (id === 'replay') {
    const verdicts = await maybe(`/api/verdicts?symbol=${q}&days=90`, { rows: [] });
    if (symbol !== state.symbol) return;
    renderReplay(verdicts);
  } else if (id === 'contexto') {
    const [daily, macro, externalMacro, divergences] = await Promise.all([
      maybe(`/api/daily?symbol=${q}&days=60`, { rows: [], streak: 0 }),
      maybe(`/api/macro-context?symbol=${q}`, { metrics: [] }),
      maybe(`/api/external-macro?symbol=${q}`, { available: false }),
      maybe(`/api/divergences?symbol=${q}`, { available: false, windows: {} }),
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
    renderHealth(state.health);
  }
  state.viewLoadedAt[id] = Date.now();
}
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
const ANALYZER_TABS = [['zone', 'analyzer-tab-zone', 'analyzer-zone'], ['range', 'analyzer-tab-range', 'analyzer-range'], ['breakout', 'analyzer-tab-breakout', 'analyzer-breakout']];
const ANALYZER_INPUTS = ['zone-low', 'zone-high', 'range-low', 'range-high', 'range-start', 'range-end', 'breakout-level'];
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

function initTradingProfile() {
  const tabs = $('profile-tabs');
  if (!tabs) return;
  tabs.addEventListener('click', event => {
    const button = event.target.closest('button[data-profile]');
    if (!button || button.dataset.profile === state.tradingProfile) return;
    state.tradingProfile = button.dataset.profile;
    for (const b of tabs.querySelectorAll('button[data-profile]')) {
      b.classList.toggle('active', b === button);
    }
    // Solo cambia la lectura: se fuerza el tramo de contexto, no se recargan datos brutos.
    state.lastContextAt = 0;
    // El enfasis por capa vive en las tablas de estructura y flujo, que se pintan desde
    // loadSection y tienen cache de 30 s: sin invalidarla, cambiar de perfil dejaba el
    // resaltado del perfil anterior hasta el siguiente ciclo.
    state.viewLoadedAt = {};
    refreshOverview(true)
      .then(() => loadSection(state.activeSection, true))
      .catch(error => console.error(error));
  });
}

// Jerarquia de temporalidades del perfil activo. Muestra peso y aportacion de cada capa
// porque un sesgo que no se puede auditar no sirve para decidir.
function renderTfProfile(result) {
  const box = $('tfprofile-layers');
  if (!box) return;
  box.replaceChildren();
  const cls = b => b === 'alcista' ? 'positive' : (b === 'bajista' ? 'negative' : 'neutral');
  const sub = $('tfprofile-subtitle');
  if (sub) sub.textContent = result.profile_label
    ? `${result.profile_label} · cobertura ${number(result.coverage_pct, 0)}% · confianza ${result.confidence || '—'}`
    : 'Sin datos';
  const pill = $('tfprofile-bias');
  if (pill) {
    pill.textContent = (result.bias || '—').replace('_', ' ');
    pill.className = `live-pill ${cls(result.bias)}`;
  }
  for (const [name, layer] of Object.entries(result.layers || {})) {
    const card = document.createElement('div');
    card.className = 'tfprofile-layer';
    const h = document.createElement('h4');
    h.textContent = name;
    const meta = document.createElement('div');
    meta.className = 'layer-meta';
    // El dato ausente se cuenta, no se disfraza de neutral.
    meta.textContent = `peso ${layer.weight} · ${layer.bias} · aporta ${layer.contribution === null || layer.contribution === undefined ? 'N/D' : number(layer.contribution, 1)} · ${layer.measurable_timeframes}/${layer.expected_timeframes} marcos`;
    const ul = document.createElement('ul');
    for (const tf of safeArray(layer.timeframes)) {
      const li = document.createElement('li');
      const a = document.createElement('span');
      a.textContent = tf.timeframe;
      const b = document.createElement('span');
      b.textContent = tf.bias === 'sin_datos' ? 'sin datos' : tf.bias;
      b.className = cls(tf.bias);
      b.title = `${tf.detail || ''} (fuente: ${tf.source || '—'})`;
      li.append(a, b);
      ul.append(li);
    }
    card.append(h, meta, ul);
    box.append(card);
  }
  const notes = $('tfprofile-contradictions');
  if (notes) {
    notes.replaceChildren();
    for (const c of safeArray(result.contradictions)) {
      const p = document.createElement('p');
      p.className = `tfprofile-note ${c.efecto}`;
      p.textContent = `${c.efecto === 'invalida' ? 'INVALIDA' : 'ESPERAR'} · ${c.detalle} — ${c.motivo}`;
      notes.append(p);
    }
    if (!safeArray(result.contradictions).length && result.bias) {
      const p = document.createElement('p');
      p.className = 'tfprofile-note';
      p.textContent = 'Sin contradicciones entre capas.';
      notes.append(p);
    }
  }
  const foot = $('tfprofile-footnote');
  if (foot) {
    const missing = safeArray(result.missing_data).join(' · ');
    foot.textContent = [result.invalidation, result.weights_note, missing ? `Datos faltantes: ${missing}` : '']
      .filter(Boolean).join(' ');
  }
}


// ---------------- paneles de la reorganizacion ----------------
function renderOiChart(oi) {
  renderGapNote('oi-gaps', setGappedLine('oi', oi, r => ts(r.bucket), r => r.oi));
  try { state.charts['oi-chart'].timeScale().fitContent(); } catch (_) {}
}

// Reparte la evidencia respecto de la hipotesis que puso el operador. No emite ordenes:
// solo dice que la apoya, que la contradice y que falta por ocurrir.
const HYP_BUCKETS = [
  ['a_favor', 'A favor', 'positive'],
  ['en_contra', 'En contra', 'negative'],
  ['pendiente', 'Pendiente', 'neutral'],
  ['neutral', 'Neutral', 'neutral'],
  ['no_evaluable', 'No evaluable', 'neutral'],
];
// La ejecucion ya no es una etiqueta binaria sacada de un umbral de spread: es el coste
// total de ida y vuelta comparado con el objetivo y con el riesgo de ESTA operacion. Sin
// objetivo, stop, comision ni tamano se dice SIN EVALUAR y se enumera lo que falta.
const EXEC_CLASS = { aceptable: 'positive', ajustado: 'neutral', prohibitivo: 'negative' };
// El estado visual de la ejecucion sale de la EVALUACION —las bandas de coste sobre objetivo
// y sobre riesgo—, nunca de comparar el spread bruto contra un literal. `SIN EVALUAR` es
// neutro a proposito: no saber si sale cara no es lo mismo que saber que sale cara.
function executionClass(execution) {
  if (!execution || typeof execution !== 'object' || execution.status !== 'EVALUADO') return 'neutral';
  const bandas = [execution.cost_to_target_band, execution.cost_to_risk_band].filter(Boolean);
  if (bandas.includes('prohibitivo')) return 'negative';
  if (bandas.includes('ajustado')) return 'neutral';
  if (bandas.includes('aceptable')) return 'positive';
  return 'neutral';
}
// El aviso de spread es SECUNDARIO: informa, no veta ni clasifica direccion. Se devuelve
// aparte para que nadie lo confunda con el veredicto.
function spreadWarning(execution) {
  return execution && execution.spread_warning ? String(execution.spread_warning) : null;
}
function renderExecutionRows(dl, execution) {
  if (!execution || typeof execution !== 'object') {
    rowDL(dl, 'Ejecución', 'N/D', 'neutral');
    return;
  }
  const veredicto = String(execution.verdict || 'SIN EVALUAR');
  rowDL(dl, `Ejecución (${execution.profile_label || execution.profile || '—'})`, veredicto, executionClass(execution));
  if (execution.status === 'SIN EVALUAR') {
    const faltan = safeArray(execution.missing_inputs).join(', ');
    rowDL(dl, 'Falta para evaluar', faltan || 'plan de operación', 'neutral');
    return;
  }
  rowDL(dl, 'Coste ida y vuelta', nd(execution.total_cost_bps, v => `${number(v, 2)} bps`), 'neutral');
  const sobreObjetivo = asNumber(execution.cost_to_target);
  rowDL(dl, 'Coste / objetivo',
    sobreObjetivo === null ? 'N/D' : `${number(sobreObjetivo * 100, 1)}% del objetivo · ${execution.cost_to_target_band}`,
    EXEC_CLASS[execution.cost_to_target_band] || 'neutral');
  const sobreRiesgo = asNumber(execution.cost_to_risk);
  rowDL(dl, 'Coste / riesgo',
    sobreRiesgo === null ? 'N/D' : `${number(sobreRiesgo * 100, 1)}% del riesgo · ${execution.cost_to_risk_band}`,
    EXEC_CLASS[execution.cost_to_risk_band] || 'neutral');
  // Advertencia SECUNDARIA, siempre en neutro: no cambia el veredicto ni añade dirección.
  const aviso = spreadWarning(execution);
  if (aviso) rowDL(dl, 'Aviso de spread (secundario)', aviso, 'neutral');
}

// Estado del SETUP con su propia lectura: cada tipo tiene requisitos e invalidaciones
// distintos, asi que se muestra cuantos se cumplen y cuantos no se pueden ni evaluar.
const SETUP_CLASS = {
  CONFIRMADO: 'positive', CANDIDATO: 'neutral', PENDIENTE: 'neutral',
  FALLIDO: 'negative', 'NO EVALUABLE': 'neutral',
};
function renderSetupRows(dl, setup) {
  if (!setup || setup.setup === 'ninguno') {
    rowDL(dl, 'Setup', 'Ninguno seleccionado', 'neutral');
    return;
  }
  rowDL(dl, `Setup · ${setup.label}`, String(setup.state), SETUP_CLASS[setup.state] || 'neutral');
  const cumplidos = safeArray(setup.cumplidos).length;
  const evaluables = asNumber(setup.requisitos_evaluables);
  rowDL(dl, 'Requisitos',
    evaluables === null ? 'N/D' : `${cumplidos}/${evaluables} cumplidos · ${safeArray(setup.no_evaluables).length} sin observable`,
    'neutral');
  if (safeArray(setup.faltantes).length) {
    rowDL(dl, 'No evaluable por', safeArray(setup.faltantes).join(', '), 'negative');
  }
}

function renderHypothesis(result) {
  const box = $('hyp-evidence');
  if (!box) return;
  box.replaceChildren();
  const sub = $('hyp-subtitle');
  if (sub) {
    sub.textContent = result.label
      ? `${result.label} · perfil ${result.profile || '—'} · datos ${number(result.data_coverage_pct, 0)}% · marcos ${number(result.profile_coverage_pct, 0)}%`
      : 'Sin datos';
  }
  const pill = $('hyp-verdict');
  if (pill) {
    const c = result.counts || {};
    pill.textContent = `${c.a_favor || 0} a favor · ${c.en_contra || 0} en contra`;
    pill.className = `live-pill ${(c.a_favor || 0) > (c.en_contra || 0) ? 'positive' : (c.en_contra || 0) > (c.a_favor || 0) ? 'negative' : 'neutral'}`;
  }
  const dl = $('hyp-summary');
  if (dl) {
    dl.replaceChildren();
    rowDL(dl, 'Contexto', result.context || '—', result.context === 'alcista' ? 'positive' : result.context === 'bajista' ? 'negative' : 'neutral');
    rowDL(dl, 'Timing', result.timing || '—', result.timing === 'alcista' ? 'positive' : result.timing === 'bajista' ? 'negative' : 'neutral');
    const cobertura = asNumber(result.data_coverage_pct);
    rowDL(dl, 'Datos', cobertura === null ? 'N/D' : `${number(cobertura, 0)}% de la evidencia`, cobertura !== null && cobertura >= 80 ? 'positive' : 'negative');
    renderExecutionRows(dl, result.execution);
    renderSetupRows(dl, result.setup_evaluation);
  }
  for (const entry of HYP_BUCKETS) {
    const items = safeArray((result.evidence || {})[entry[0]]);
    if (!items.length) continue;
    const card = document.createElement('div');
    card.className = 'tfprofile-layer';
    const h = document.createElement('h4');
    h.textContent = `${entry[1]} (${items.length})`;
    h.className = entry[2];
    const ul = document.createElement('ul');
    for (const it of items) {
      const li = document.createElement('li');
      const a = document.createElement('span');
      a.textContent = it.signal;
      const b = document.createElement('span');
      b.textContent = it.detail;
      li.append(a, b);
      ul.append(li);
    }
    card.append(h, ul);
    box.append(card);
  }
  const notes = [];
  for (const c of safeArray(result.pending_conditions)) notes.push(`PENDIENTE · ${c}`);
  for (const c of safeArray(result.invalidations)) notes.push(`INVALIDA · ${c}`);
  const foot = $('hyp-note');
  if (foot) foot.textContent = [notes.join('   |   '), result.note].filter(Boolean).join('   ');
}

function renderFunding(result) {
  const dl = $('funding-list');
  if (!dl) return;
  dl.replaceChildren();
  rowDL(dl, 'Funding actual', result.current_pct == null ? 'Sin dato' : rate(result.current_pct), result.current_pct == null ? 'neutral' : signClass(-result.current_pct));
  rowDL(dl, 'Predicho', result.predicted_pct == null ? 'Sin dato' : rate(result.predicted_pct), 'neutral');
  rowDL(dl, 'Divergencia pred-actual', result.divergence_pred_minus_current == null ? '—' : rate(result.divergence_pred_minus_current), 'neutral');
  rowDL(dl, 'Media histórica', result.history_avg_pct == null ? '—' : rate(result.history_avg_pct), 'neutral');
  rowDL(dl, 'Anualizado', result.annualized_pct == null ? '—' : `${number(result.annualized_pct, 2)}%`, 'neutral');
  rowDL(dl, 'Próximo pago (UTC)', result.next_funding_time_utc || '—', 'neutral');
  rowDL(dl, 'Régimen', result.regime || '—', 'neutral');
}

function renderPositioning(result) {
  const dl = $('positioning-list');
  if (!dl) return;
  dl.replaceChildren();
  if (result.status === 'UNAVAILABLE' || result.ratio == null) {
    rowDL(dl, 'Estado', result.reason || 'Sin datos', 'negative');
    return;
  }
  rowDL(dl, 'Ratio long/short', number(result.ratio, 3), signClass(result.ratio - 1));
  rowDL(dl, 'Long / Short', `${number(result.long_pct, 2)}% / ${number(result.short_pct, 2)}%`, 'neutral');
  rowDL(dl, 'Cambio 24 h', result.ratio_change_24h == null ? '—' : number(result.ratio_change_24h, 4), signClass(result.ratio_change_24h));
  rowDL(dl, 'Mediana de la muestra', result.median_sample == null ? '—' : number(result.median_sample, 3), 'neutral');
  rowDL(dl, 'Percentil en la muestra', result.percentile_sample == null ? 'Muestra corta' : `${number(result.percentile_sample, 1)}%`, 'neutral');
  rowDL(dl, 'Muestra', `${number(result.sample_count, 0)} obs · ${number(result.sample_days, 1)} d${result.sample_is_full_month ? '' : ' (aún no es un mes)'}`, 'neutral');
  rowDL(dl, 'Advertencia', 'Cuenta cuentas, no notional', 'neutral');
}

function renderExecutionCost(result) {
  const body = $('execution-body');
  if (!body) return;
  body.replaceChildren();
  for (const v of safeArray(result.venues)) {
    for (const lado of ['buy', 'sell']) {
      const filas = v[lado];
      const etiqueta = lado === 'buy' ? 'Compra' : 'Venta';
      if (!filas) {
        const tr = document.createElement('tr');
        [[v.exchange, ''], [etiqueta, ''], ['—', ''], ['—', ''], ['—', ''], ['—', ''], [v.status || 'UNAVAILABLE', 'negative']].forEach(x => td(tr, x[0], x[1]));
        body.append(tr);
        continue;
      }
      for (const f of filas) {
        const tr = document.createElement('tr');
        [[v.exchange, ''], [etiqueta, ''],
         [money(f.size_usd, 0), ''],
         [f.avg_price == null ? '—' : money(f.avg_price, 2), ''],
         // Neutro: el slippage por si solo no dice si la operacion sale cara; entra al
         // coste total y ahi se compara contra el objetivo.
         [nd(f.slippage_bps, v2 => `${number(v2, 2)} bps`), 'neutral'],
         [`${f.levels_used}/${f.levels_available}`, ''],
         [f.insufficient_depth ? `Falta ${money(f.shortfall_usd, 0)}` : v.status, f.insufficient_depth ? 'negative' : 'positive']].forEach(x => td(tr, x[0], x[1]));
        body.append(tr);
      }
    }
  }
}

function renderMarketImpact(result) {
  const body = $('impact-body');
  if (!body) return;
  body.replaceChildren();
  for (const w of safeArray(result.windows)) {
    const ctx = w.context || {};
    const tr = document.createElement('tr');
    [[w.window, ''],
     [w.impact_bps_per_musd == null ? 'No evaluable' : `${number(w.impact_bps_per_musd, 3)} bps/M`, 'neutral'],
     [w.net_delta_musd == null ? '—' : `${number(w.net_delta_musd, 2)} M`, 'neutral'],
     [w.price_move_bps == null ? '—' : `${number(w.price_move_bps, 1)} bps`, 'neutral'],
     [ctx.band || 'sin baseline', (ctx.band === 'extremo' || ctx.band === 'alto') ? 'negative' : 'neutral'],
     [`${w.coverage}${w.coverage_complete ? '' : ' (parcial)'}`, w.coverage_complete ? 'positive' : 'negative']].forEach(x => td(tr, x[0], x[1]));
    tr.title = w.reading || '';
    body.append(tr);
  }
}

function renderQuality(confidence, health) {
  const body = $('quality-body');
  if (!body) return;
  body.replaceChildren();
  for (const svc of safeArray(health.services)) {
    const tr = document.createElement('tr');
    const estado = svc.status || 'N/D';
    const lag = asNumber(svc.lag_seconds);
    // Una latencia DESCONOCIDA no puede pintarse como sana: `|| 0` la hacia pasar por 0 s.
    [[svc.service, ''],
     [estado, estado === 'ok' ? 'positive' : 'negative'],
     [dateTime(svc.updated_at), 'neutral'],
     [lag === null ? 'N/D' : `${number(lag, 1)} s`, lag === null || lag > 120 ? 'negative' : 'neutral'],
     [svc.detail || '—', 'neutral']].forEach(x => td(tr, x[0], x[1]));
    body.append(tr);
  }
  const rows = safeArray(confidence.rows);
  const row = rows.find(r => r.symbol === state.symbol) || rows[0] || {};
  const pill = $('quality-global');
  if (pill) {
    const score = asNumber(row.quality_score);
    pill.textContent = score === null ? 'Sin dato' : `Calidad ${number(score, 0)} · ${row.status || ''}`;
    pill.className = `live-pill ${score !== null && score >= 80 ? 'positive' : 'negative'}`;
    pill.title = 'Conectividad de los colectores, no cobertura de los feeds';
  }
  const errores = $('quality-errors');
  if (errores) {
    errores.replaceChildren();
    const entradas = Object.entries(state.errors || {});
    if (!entradas.length) {
      const p = document.createElement('p');
      p.className = 'tfprofile-note';
      p.textContent = 'Ningún endpoint ha fallado en este ciclo.';
      errores.append(p);
    }
    for (const par of entradas) {
      const p = document.createElement('p');
      p.className = 'tfprofile-note invalida';
      p.textContent = `ERROR · ${par[0]} — ${par[1].message}`;
      errores.append(p);
    }
  }
}

// Calidad de FEEDS: un feed es venue + mercado + tipo de dato, no un proceso interno.
// Los campos que el sistema no puede medir para ese feed se dicen N/D; nunca cero.
const FEED_STATE_CLASS = { OK: 'positive', PARTIAL: 'neutral', STALE: 'negative', DOWN: 'negative', UNAVAILABLE: 'negative' };
function renderFeedQuality(result) {
  const body = $('feeds-body');
  if (!body) return;
  body.replaceChildren();
  const filas = safeArray(result.feeds);
  const sub = $('feeds-sub');
  if (sub) {
    const sanos = filas.filter(f => f.status === 'OK').length;
    sub.textContent = filas.length
      ? `${sanos}/${filas.length} feeds OK · ventana ${number(result.window_seconds, 0)} s`
      : 'Sin información de feeds';
  }
  for (const f of filas) {
    const tr = document.createElement('tr');
    const lat = asNumber(f.latency_seconds);
    const cob = asNumber(f.coverage_pct);
    const hueco = asNumber(f.max_internal_gap_seconds);
    const ausentes = safeArray(f.missing_sources);
    td(tr, f.exchange || 'N/D', '');
    td(tr, f.market || 'N/D', '');
    td(tr, f.symbol || 'N/D', '');
    td(tr, f.data_type || 'N/D', '');
    td(tr, f.status || 'N/D', FEED_STATE_CLASS[f.status] || 'neutral');
    td(tr, f.last_ts ? dateTime(f.last_ts) : 'N/D', 'neutral');
    td(tr, lat === null ? 'N/D' : `${number(lat, 1)} s`, 'neutral');
    // Sin cadencia esperada NO hay cobertura que calcular: se dice, no se inventa un 0%.
    td(tr, cob === null ? 'N/D' : `${number(cob, 0)}%`, cob !== null && cob < 90 ? 'negative' : 'neutral');
    td(tr, f.samples_observed == null ? 'N/D' : number(f.samples_observed, 0), 'neutral');
    td(tr, f.samples_expected == null ? 'N/D' : number(f.samples_expected, 0), 'neutral');
    td(tr, hueco === null ? 'N/D' : `${number(hueco, 0)} s`, 'neutral');
    td(tr, f.missing_sources == null ? 'N/D' : (ausentes.length ? ausentes.join(', ') : 'ninguna'),
      ausentes.length ? 'negative' : 'neutral');
    td(tr, f.last_error || '—', f.last_error ? 'negative' : 'neutral');
    body.append(tr);
  }
}
// Calidad por METRICA: un feed sano no garantiza que la ventana que se apoya en el este
// completa, ni que el basis sea utilizable con las dos patas vivas pero desfasadas.
function renderMetricQuality(result) {
  const body = $('metrics-quality-body');
  if (!body) return;
  body.replaceChildren();
  for (const m of safeArray(result.metrics)) {
    const tr = document.createElement('tr');
    const lat = asNumber(m.latency_seconds);
    const estado = String(m.status || 'UNAVAILABLE');
    td(tr, m.metric, '');
    td(tr, m.timeframe || 'N/D', 'neutral');
    td(tr, estado, FEED_STATE_CLASS[estado] || (estado === 'VALID' ? 'positive' : 'neutral'));
    td(tr, m.coverage == null ? 'N/D' : String(m.coverage), 'neutral');
    td(tr, m.source || 'N/D', 'neutral');
    td(tr, lat === null ? 'N/D' : `${number(lat, 1)} s`, 'neutral');
    body.append(tr);
  }
}

function renderReplay(result) {
  const body = $('replay-body');
  if (!body) return;
  body.replaceChildren();
  for (const r of safeArray(result.rows)) {
    const tr = document.createElement('tr');
    [[r.session_date, ''],
     [r.swing_bias || '—', r.swing_bias === 'LONG' ? 'positive' : r.swing_bias === 'SHORT' ? 'negative' : 'neutral'],
     [r.swing_score == null ? '—' : number(r.swing_score, 1), 'neutral'],
     [r.swing_conviction || '—', 'neutral'],
     [r.regime_label || '—', 'neutral'],
     [r.fwd_return_7s_pct == null ? 'Pendiente' : pct(r.fwd_return_7s_pct), signClass(r.fwd_return_7s_pct)],
     [r.fwd_return_14s_pct == null ? 'Pendiente' : pct(r.fwd_return_14s_pct), signClass(r.fwd_return_14s_pct)]].forEach(x => td(tr, x[0], x[1]));
    body.append(tr);
  }
}

// Valores guardados de la version anterior, cuando hipotesis y setup eran un solo selector.
const LEGACY_HYPOTHESIS = {
  long: ['long', 'ninguno'],
  short: ['short', 'ninguno'],
  neutral: ['neutral', 'ninguno'],
  esperando_ruptura: ['neutral', 'ruptura'],
  esperando_rechazo: ['neutral', 'rechazo'],
  esperando_reversion: ['neutral', 'reversion'],
  esperando_continuacion: ['neutral', 'continuacion'],
};
function initHypothesis() {
  const dirSel = $('direction-select');
  const setupSel = $('setup-select');
  if (!dirSel || !setupSel) return;
  // Si viene un valor viejo en el hash o en el almacenamiento, se traduce al par nuevo en
  // vez de quedarse en un estado que ya no existe.
  const legacy = LEGACY_HYPOTHESIS[state.hypothesis];
  if (legacy) [state.direction, state.setup] = legacy;
  dirSel.value = state.direction;
  setupSel.value = state.setup;
  const onChange = () => {
    state.direction = dirSel.value;
    state.setup = setupSel.value;
    state.lastContextAt = 0;
    refreshOverview(true).catch(error => console.error(error));
  };
  dirSel.addEventListener('change', onChange);
  setupSel.addEventListener('change', onChange);
}

// Barra global: fuentes vivas, mayor latencia y ultimo error de endpoint.
function renderGlobalBar(health) {
  const services = safeArray(health.services);
  const sanos = services.filter(s => s.status === 'ok').length;
  const fuentes = $('live-sources');
  if (fuentes) {
    fuentes.textContent = `Fuentes ${sanos}/${services.length || 0}`;
    fuentes.className = `live-pill ${services.length && sanos === services.length ? 'positive' : 'negative'}`;
  }
  const lat = $('live-latency');
  if (lat) {
    // Una latencia DESCONOCIDA no es una latencia de 0 s. Antes `|| 0` la hacia pasar por la
    // mejor de todas y la barra mostraba "Lat 0 s" con el servicio mudo.
    const lags = services.map(s => asNumber(s.lag_seconds));
    const medidas = lags.filter(v => v !== null);
    const desconocidas = lags.length - medidas.length;
    const peor = medidas.length ? Math.max(...medidas) : null;
    lat.textContent = peor === null ? 'Lat N/D' : `Lat ${number(peor, 0)} s${desconocidas ? ` (+${desconocidas} N/D)` : ''}`;
    lat.className = `live-pill ${peor === null || desconocidas || peor > 120 ? 'negative' : 'neutral'}`;
    lat.title = desconocidas ? `${desconocidas} servicio(s) sin latencia publicada` : 'Mayor latencia entre servicios';
  }
  const err = $('live-error');
  if (err) {
    const ultimo = lastEndpointError();
    err.textContent = ultimo ? `Error: ${ultimo.path.split('?')[0]}${ultimo.count > 1 ? ` (+${ultimo.count - 1})` : ''}` : 'Sin errores';
    err.className = `live-pill ${ultimo ? 'negative' : 'neutral'}`;
    err.title = ultimo ? `${ultimo.path} — ${ultimo.message}` : 'Ningún endpoint ha fallado';
  }
}

function renderStructure(result) { const body = $('structure-body'); if (!body) return; body.replaceChildren(); const names = { micro: 'Micro (1m-15m)', mid: 'Mid (30m-4h)', macro: 'Macro (1d-7d)' }; const cls = b => b === 'alcista' ? 'positive' : (b === 'bajista' ? 'negative' : 'neutral'); for (const l of safeArray(result.layers)) { const tr = document.createElement('tr'); const chips = Object.entries(l.components || {}).map(([k, v]) => `${v === true ? '\u25B2' : (v === false ? '\u25BC' : '\u00B7')} ${k}`).join('  '); const ps = l.price_structure || '\u2014'; [[names[l.layer] || l.layer, ''], [`${l.bias} ${l.votes_up}/${l.votes_total}`, cls(l.bias)], [ps, ps === 'HH/HL' ? 'positive' : (ps === 'LH/LL' ? 'negative' : 'neutral')], [chips, 'neutral']].forEach(([v, c]) => td(tr, v, c)); body.append(tr); } const note = document.getElementById('structure-align'); if (note && result.alignment) note.textContent = result.alignment.replace('_', ' '); }

function externalClass(stateName) { return stateName === 'favorable' || stateName === 'alineado' ? 'positive' : stateName === 'restrictivo' || stateName === 'conflicto' || stateName === 'esperar_evento' ? 'negative' : 'neutral'; }
function externalMetricValue(metric) {
  if (metric.value == null) return 'Sin dato';
  const value = metric.key === 'stablecoin_supply_usd' ? money(metric.value, 1)
    : ['treasury_2y', 'real_yield_10y'].includes(metric.key) ? `${number(metric.value, 2)}%`
      : number(metric.value, 2);
  const change = metric.change == null ? 'sin cambio comparable'
    : metric.change_kind === 'bps' ? `${asNumber(metric.change) >= 0 ? '+' : ''}${number(metric.change, 0)} bps` : pct(metric.change, 2);
  return `${value} · ${change}`;
}
function renderExternalMacro(result = {}) {
  const body = $('external-macro-body');
  const sub = $('external-macro-sub');
  const badge = $('external-macro-badge');
  if (!body || !sub || !badge) return;
  body.replaceChildren();
  badge.textContent = result.regime_label || 'Datos insuficientes';
  badge.className = `warning ${externalClass(result.regime)}`;
  sub.textContent = result.as_of
    ? `Corte ${result.as_of} · cobertura ${number(result.coverage_pct, 0)}% · confianza de datos ${result.data_confidence || '—'}`
    : 'Esperando primera actualización de fuentes externas';
  if (!result.available) {
    const empty = document.createElement('p');
    empty.className = 'zone-empty';
    empty.textContent = safeArray(result.limitations)[0] || 'Aún no hay cobertura suficiente para clasificar el régimen.';
    body.append(empty);
    return;
  }

  const hero = document.createElement('div');
  hero.className = 'external-macro-hero';
  const regime = document.createElement('div');
  regime.className = 'external-regime';
  const regimeKicker = document.createElement('span');
  regimeKicker.textContent = 'Filtro de varias sesiones';
  const regimeValue = document.createElement('strong');
  regimeValue.className = externalClass(result.regime);
  regimeValue.textContent = result.regime_label;
  const regimeNote = document.createElement('small');
  regimeNote.textContent = 'Contexto, no gatillo de entrada ni probabilidad.';
  regime.append(regimeKicker, regimeValue, regimeNote);

  const alignment = result.alignment || {};
  const alignmentNode = document.createElement('div');
  alignmentNode.className = 'external-alignment';
  const alignmentTitle = document.createElement('strong');
  alignmentTitle.className = externalClass(alignment.state);
  alignmentTitle.textContent = alignment.state === 'alineado' ? 'Macro e impulso alineados'
    : alignment.state === 'conflicto' ? 'Conflicto de horizonte'
      : alignment.state === 'esperar_evento' ? 'Esperar evento macro' : 'Confirmación parcial';
  const alignmentText = document.createElement('p');
  alignmentText.textContent = alignment.reading || 'Sin evaluación de alineación.';
  const alignmentMeta = document.createElement('small');
  alignmentMeta.textContent = `Sesgo interno ${alignment.internal_bias || '—'} · fuente actualizada ${dateTime(result.fetched_at)}`;
  alignmentNode.append(alignmentTitle, alignmentText, alignmentMeta);
  hero.append(regime, alignmentNode);
  body.append(hero);

  const pillars = document.createElement('div');
  pillars.className = 'external-pillars';
  for (const pillar of Object.values(result.pillars || {})) {
    const node = document.createElement('article');
    node.className = `external-pillar ${externalClass(pillar.state)}`;
    const stateLabel = document.createElement('span');
    stateLabel.textContent = pillar.state;
    const title = document.createElement('h4');
    title.textContent = pillar.label;
    const narrative = document.createElement('p');
    narrative.textContent = pillar.narrative;
    node.append(stateLabel, title, narrative);
    for (const metric of safeArray(pillar.metrics)) {
      const row = document.createElement('div');
      row.className = 'external-metric';
      const label = document.createElement('span');
      label.textContent = metric.label;
      const value = document.createElement('strong');
      value.className = externalClass(metric.state);
      value.textContent = externalMetricValue(metric);
      row.append(label, value);
      node.append(row);
    }
    pillars.append(node);
  }
  body.append(pillars);

  const details = document.createElement('div');
  details.className = 'external-details';
  const institutional = result.institutional_flows || {};
  const etf = document.createElement('article');
  etf.className = 'external-detail';
  const etfKicker = document.createElement('span');
  etfKicker.textContent = 'Flujo institucional BTC';
  const etfValue = document.createElement('strong');
  etfValue.className = institutional.available ? signClass(institutional.flow_5d_usd) : 'neutral';
  etfValue.textContent = institutional.available
    ? `ETF 1d ${money(institutional.flow_1d_usd)} · 5d ${money(institutional.flow_5d_usd)} · 20d ${money(institutional.flow_20d_usd)}`
    : 'Feed ETF opcional no conectado';
  const etfText = document.createElement('p');
  etfText.textContent = institutional.interpretation || 'Sin lectura institucional.';
  etf.append(etfKicker, etfValue, etfText);

  const eventRisk = result.event_risk || {};
  const event = document.createElement('article');
  event.className = 'external-detail';
  const eventKicker = document.createElement('span');
  eventKicker.textContent = `Riesgo de evento · ${eventRisk.level || '—'}`;
  const eventValue = document.createElement('strong');
  eventValue.className = ['alto', 'elevado'].includes(eventRisk.level) ? 'negative' : 'neutral';
  const next = eventRisk.next_event;
  eventValue.textContent = next ? `${next.title} · ${dateTime(next.event_at)}` : 'Sin evento próximo registrado';
  const eventText = document.createElement('p');
  eventText.textContent = eventRisk.narrative || 'Sin calendario disponible.';
  event.append(eventKicker, eventValue, eventText);
  details.append(etf, event);
  body.append(details);

  const limitations = safeArray(result.limitations);
  if (limitations.length) {
    const note = document.createElement('p');
    note.className = 'external-limit';
    note.textContent = `${limitations.join(' ')} Fuentes: ${safeArray(result.sources).join(' · ')}.`;
    body.append(note);
  }
}

function renderMacro(result) { const body = $('macro-body'); if (!body) return; body.replaceChildren(); const cls = r => (r.indexOf('extremo') === 0) ? (r.indexOf('alto') >= 0 ? 'positive' : 'negative') : 'neutral'; for (const m of safeArray(result.metrics)) { const tr = document.createElement('tr'); const pval = m.percentile == null ? '\u2014' : (number(m.percentile, 0) + '%'); [[m.label, ''], [m.value == null ? '\u2014' : number(m.value, 2), 'neutral'], [pval, cls(m.regime)], [m.regime, cls(m.regime)]].forEach(([v, c]) => td(tr, v, c)); body.append(tr); } const sub = document.getElementById('macro-sub'); if (sub) sub.textContent = result.sessions ? ('percentil vs ' + result.sessions + ' sesiones \u00b7 tensi\u00f3n ' + (result.tension || 0)) : 'sin historia'; }

// La columna mostraba el diferencial spot-futuros con color por signo, que es el CVD de
// futuros invertido en ~93% de los casos. Ahora muestra el estado de las dos patas.
const PASSIVE_FLOW = {
  spot_y_futuros_compran: ['Ambas compran', 'positive'],
  spot_y_futuros_venden: ['Ambas venden', 'negative'],
  spot_compra_futuros_vende: ['Spot compra / Fut vende', 'neutral'],
  spot_vende_futuros_compra: ['Spot vende / Fut compra', 'neutral'],
  una_pata_plana: ['Una pata plana', 'neutral'],
  sin_datos: ['—', 'neutral'],
};
function renderPassive(result) { const body = $('passive-body'); if (!body) return; body.replaceChildren(); const cls = r => r === 'reacumulacion_silenciosa' ? 'positive' : (r === 'redistribucion_silenciosa' ? 'negative' : 'neutral'); const lbl = { reacumulacion_silenciosa: 'Reacum. silenciosa', redistribucion_silenciosa: 'Redistrib. silenciosa', neutral: '\u2014' }; for (const [hz, h] of Object.entries(result.horizons || {})) { const tr = document.createElement('tr'); [[hz, ''], [lbl[h.reading] + (h.confidence && h.reading !== 'neutral' ? ' (' + h.confidence + ')' : ''), cls(h.reading)], [h.absorption, h.absorption === 'ventas' ? 'positive' : (h.absorption === 'compras' ? 'negative' : 'neutral')], PASSIVE_FLOW[h.flow_state] || ['—', 'neutral'], [h.price_move_pct == null ? 's/d' : number(h.price_move_pct, 2) + '%', h.price_move_pct == null ? 'neutral' : signClass(h.price_move_pct)]].forEach(([v, c]) => td(tr, v, c)); body.append(tr); } const sub = document.getElementById('passive-sub'); if (sub) sub.textContent = (result.summary && result.summary !== 'neutral') ? (lbl[result.summary] + ' \u00b7 en ' + (result.location || 's/d')) : ('neutral \u00b7 ' + (result.location || 's/d')); }

// ---------------- Lectura de zona (fase 1) ----------------
// A diferencia del resto de paneles esto NO entra en el refresh de 15 s: el veredicto es de
// un tramo historico fijo, recalcularlo cada ciclo solo gastaria consultas.
const ZONE_LABEL = {
  acumulacion: ['Acumulación', 'positive'],
  distribucion: ['Distribución', 'negative'],
  sin_caracter: ['Sin carácter definido', 'neutral'],
  sin_datos: ['Sin datos suficientes', 'neutral'],
};
const ZONE_COMP_LABEL = {
  esfuerzo_resultado: 'Esfuerzo agresivo vs desplazamiento',
  cvd_spot: 'CVD spot de la zona',
  open_interest: 'Open interest',
  funding: 'Funding',
  rechazos: 'Cierres dentro de la barra',
};

function clearZone() {
  const body = $('zone-body');
  if (body) body.replaceChildren();
  const sub = $('zone-sub');
  if (sub) sub.textContent = 'Acumulación · distribución · rotación';
}

function zoneEmpty(text) {
  const body = $('zone-body');
  if (!body) return;
  const div = document.createElement('div');
  div.className = 'zone-empty';
  div.textContent = text;
  body.replaceChildren(div);
}

function renderZone(result) {
  const body = $('zone-body');
  if (!body) return;
  body.replaceChildren();
  const visits = safeArray(result.visits);
  if (!visits.length) {
    zoneEmpty('El precio no visitó esa zona en el periodo consultado.');
    return;
  }
  for (const visit of visits) {
    const card = document.createElement('article');
    card.className = 'zone-visit';

    if (!visit.available) {
      const head = document.createElement('div');
      head.className = 'zone-verdict neutral';
      head.textContent = 'Visita sin veredicto';
      const why = document.createElement('div');
      why.className = 'zone-meta';
      why.textContent = visit.reason || 'Cobertura insuficiente.';
      card.append(head, why);
      body.append(card);
      continue;
    }

    const [label, cls] = ZONE_LABEL[visit.character] || ['—', 'neutral'];
    const head = document.createElement('div');
    head.className = `zone-verdict ${cls}`;
    head.textContent = `${label} · ${visit.strength} · confianza ${visit.confidence}`;

    const meta = document.createElement('div');
    meta.className = 'zone-meta';
    meta.textContent = `${visit.from} → ${visit.to} · score ${number(visit.score, 0)}/100 · `
      + `evidencia medible ${number(visit.evidence_coverage_pct, 0)}% · `
      + `${visit.bars_4h} barras 4h · ${visit.sessions} sesiones`;
    card.append(head, meta);

    const evi = document.createElement('div');
    evi.className = 'zone-evi';
    for (const line of safeArray(visit.narrative)) {
      const row = document.createElement('div');
      row.className = 'zone-evi-line';
      const ico = document.createElement('span');
      ico.className = 'zone-evi-ico neutral';
      ico.textContent = '·';
      const text = document.createElement('span');
      text.textContent = line;
      row.append(ico, text);
      evi.append(row);
    }
    card.append(evi);

    const comps = document.createElement('div');
    comps.className = 'zone-comp';
    for (const c of safeArray(visit.components)) {
      const row = document.createElement('div');
      row.className = 'zone-comp-row';
      const name = document.createElement('span');
      name.className = 'zone-comp-name';
      name.textContent = (ZONE_COMP_LABEL[c.key] || c.label || c.key)
        + (c.status === 'unavailable' ? ' · sin dato' : '');
      const value = document.createElement('span');
      // Un componente sin dato muestra guion, nunca 0: un 0 se leeria como "medido y neutral".
      value.className = c.status === 'unavailable' ? 'neutral' : signClass(c.contribution);
      value.textContent = c.status === 'unavailable'
        ? '—'
        : `${c.contribution > 0 ? '+' : ''}${number(c.contribution, 1)} / ${number(c.weight, 0)}`;
      row.append(name, value);
      comps.append(row);
    }
    card.append(comps);

    const missing = safeArray((visit.method || {}).unavailable);
    if (missing.length) {
      const note = document.createElement('div');
      note.className = 'zone-missing';
      note.textContent = `No se pudo medir: ${missing.map(k => ZONE_COMP_LABEL[k] || k).join(', ')}. `
        + 'El score se reparte solo entre los componentes medibles.';
      card.append(note);
    }
    if (visit.warning) {
      const warn = document.createElement('div');
      warn.className = 'zone-missing';
      warn.textContent = visit.warning;
      card.append(warn);
    }
    body.append(card);
  }
  const sub = $('zone-sub');
  if (sub) {
    const scored = asNumber(result.scored_visits) || 0;
    sub.textContent = scored > 1 && String(result.summary).startsWith('La zona no')
      ? `${visits.length} visitas · carácter distinto entre ellas`
      : `${visits.length} visita(s) en ${result.lookback_days} días`;
  }
}

async function submitZone(event) {
  if (event) event.preventDefault();
  const low = asNumber(($('zone-low') || {}).value);
  const high = asNumber(($('zone-high') || {}).value);
  if (low === null || high === null || low <= 0 || high <= low) {
    zoneEmpty('Introduce dos precios válidos, con el inferior por debajo del superior.');
    return;
  }
  zoneEmpty('Analizando…');
  const query = `symbol=${encodeURIComponent(state.symbol)}&low=${low}&high=${high}`;
  const result = await maybe(`/api/zone/analysis?${query}`, null);
  if (!result) {
    zoneEmpty('No se pudo calcular la zona. Revisa el panel de salud de datos.');
    return;
  }
  renderZone(result);
}

// ---------------- Frecuencia historica de ruptura (fase 3) ----------------
// Es un CONTEO de intentos historicos, no la salida de un modelo calibrado, asi que no se
// llama probabilidad. La cifra NUNCA se muestra sola: sin n e intervalo se leeria como una.
function clearBreakout() {
  const body = $('breakout-body');
  if (body) body.replaceChildren();
  const sub = $('breakout-sub');
  if (sub) sub.textContent = 'Tasa base histórica, no un modelo';
}

function breakoutEmpty(text) {
  const body = $('breakout-body');
  if (!body) return;
  const div = document.createElement('div');
  div.className = 'zone-empty';
  div.textContent = text;
  body.replaceChildren(div);
}

function rateBlock(entry, headline) {
  const wrap = document.createElement('div');
  if (!entry.available) {
    const none = document.createElement('div');
    none.className = 'zone-empty';
    none.textContent = `${entry.label}: ${entry.reason}`;
    wrap.append(none);
    return wrap;
  }
  const title = document.createElement('div');
  title.className = 'brk-headline';
  title.textContent = headline || entry.label;
  const rate = document.createElement('div');
  rate.className = 'brk-rate';
  rate.textContent = `${number(entry.rate_pct, 1)}%`;
  const lo = entry.ci95_pct ? entry.ci95_pct[0] : null;
  const hi = entry.ci95_pct ? entry.ci95_pct[1] : null;
  const ci = document.createElement('div');
  ci.className = 'brk-ci';
  ci.textContent = `${entry.sustained} de ${entry.n} intentos análogos`
    + (lo !== null ? ` · IC95 ${number(lo, 0)}–${number(hi, 0)}%` : '')
    + (entry.n < 30 ? ' · muestra pequeña' : '');
  wrap.append(title, rate, ci);

  if (lo !== null) {
    const band = document.createElement('div');
    band.className = 'brk-band';
    const span = document.createElement('span');
    span.className = 'brk-band-ci';
    span.style.left = `${lo}%`;
    span.style.width = `${Math.max(hi - lo, 0.5)}%`;
    const point = document.createElement('span');
    point.className = 'brk-band-pt';
    point.style.left = `${entry.rate_pct}%`;
    band.append(span, point);
    const scale = document.createElement('div');
    scale.className = 'brk-scale';
    for (const tick of ['0%', '50%', '100%']) {
      const s = document.createElement('span');
      s.textContent = tick;
      scale.append(s);
    }
    wrap.append(band, scale);
  }
  const split = document.createElement('div');
  split.className = 'zone-meta';
  split.textContent = `Sostenida ${number(entry.rate_pct, 0)}% · falsa ${number(entry.false_break_pct, 0)}% · rechazo ${number(entry.rejection_pct, 0)}%`;
  wrap.append(split);
  return wrap;
}

function renderBreakout(result) {
  const body = $('breakout-body');
  if (!body) return;
  body.replaceChildren();
  if (!result.available) {
    breakoutEmpty(result.reason || 'Sin muestra suficiente para estimar una tasa.');
    return;
  }
  body.append(rateBlock(result.base_rate,
    `Ruptura ${result.direction} de ${money(result.level, 2)} — todos los intentos análogos`));

  const condTitle = document.createElement('div');
  condTitle.className = 'brk-headline';
  condTitle.style.marginTop = '14px';
  condTitle.textContent = 'Con las condiciones actuales';
  body.append(condTitle);

  for (const entry of safeArray(result.conditional_rates)) {
    const row = document.createElement('div');
    row.className = 'brk-cond';
    const name = document.createElement('span');
    name.className = 'brk-cond-name';
    name.textContent = entry.label;
    const value = document.createElement('span');
    if (entry.available) {
      const lo = entry.ci95_pct ? entry.ci95_pct[0] : null;
      const hi = entry.ci95_pct ? entry.ci95_pct[1] : null;
      value.textContent = `${number(entry.rate_pct, 1)}% (n=${entry.n}`
        + (lo !== null ? `, IC95 ${number(lo, 0)}–${number(hi, 0)}%` : '') + ')';
    } else {
      value.className = 'neutral';
      value.textContent = `sin muestra (n=${entry.n})`;
    }
    row.append(name, value);
    body.append(row);
  }

  const nocombine = document.createElement('div');
  nocombine.className = 'range-note';
  nocombine.textContent = 'Estas tasas son marginales y NO se multiplican entre sí: las '
    + 'variables están correlacionadas y combinarlas fabricaría precisión que la muestra no sostiene.';
  body.append(nocombine);

  const conf = result.confirmation || {};
  const confTitle = document.createElement('div');
  confTitle.className = 'brk-headline';
  confTitle.style.marginTop = '14px';
  confTitle.textContent = `Confirmación en vivo: ${conf.met}/${conf.required} · ${conf.state}`;
  body.append(confTitle);
  for (const check of safeArray(conf.checks)) {
    const row = document.createElement('div');
    row.className = 'brk-check';
    const mark = document.createElement('span');
    mark.className = check.met ? 'positive' : 'negative';
    mark.textContent = check.met ? '✓' : '✗';
    const text = document.createElement('span');
    text.textContent = `${check.label} — ${check.detail}`;
    row.append(mark, text);
    body.append(row);
  }

  const warn = document.createElement('div');
  warn.className = 'range-note negative';
  warn.textContent = result.warning || '';
  body.append(warn);

  const sub = $('breakout-sub');
  if (sub) {
    sub.textContent = result.base_rate.available
      ? `${number(result.base_rate.rate_pct, 0)}% sobre ${result.base_rate.n} intentos`
      : 'muestra insuficiente';
  }
}

async function submitBreakout(event) {
  if (event) event.preventDefault();
  const level = asNumber(($('breakout-level') || {}).value);
  const direction = ($('breakout-direction') || {}).value || 'up';
  if (level === null || level <= 0) {
    breakoutEmpty('Introduce un nivel de precio válido.');
    return;
  }
  breakoutEmpty('Calculando…');
  const query = `symbol=${encodeURIComponent(state.symbol)}&level=${level}&direction=${direction}`;
  const result = await maybe(`/api/level/breakout?${query}`, null);
  if (!result) {
    breakoutEmpty('No se pudo calcular la tasa base. Revisa el panel de salud de datos.');
    return;
  }
  renderBreakout(result);
}

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
