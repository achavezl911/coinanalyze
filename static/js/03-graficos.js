'use strict';
// lightweight-charts: series, escalas, huecos
// Trozo 3 de 11 del panel. Sale de static/app.js SIN TOCAR UNA LINEA DE LOGICA
// (FASE 2, 2026-09-13): lineas 236-339 del fichero original.
// El orden de los <script defer> de index.html ES el orden de este fichero: no se
// reordena nada, porque en scripts clasicos un `const` de primer nivel solo existe a
// partir del script que lo declara.
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

