'use strict';
// el estado compartido, la paleta y las utilidades de formato
// Trozo 1 de 11 del panel. Sale de static/app.js SIN TOCAR UNA LINEA DE LOGICA
// (FASE 2, 2026-09-13): lineas 1-160 del fichero original.
// El orden de los <script defer> de index.html ES el orden de este fichero: no se
// reordena nada, porque en scripts clasicos un `const` de primer nivel solo existe a
// partir del script que lo declara.

const state = {
  symbol: 'BTCUSDT_PERP.A', symbols: [], charts: {}, series: {}, source: null,
  // Una serie de linea se dibuja como VARIAS series, una por tramo contiguo, para que los
  // huecos no se unan con una recta. `seriesMeta` guarda con que opciones clonarlas.
  seriesMeta: {}, seriesPool: {},
  refreshTimer: null, refreshSeq: 0, activeSection: 'mesa', viewLoadedAt: {},
  dashboard: {}, confidence: { rows: [] }, health: { status: 'degraded', services: [] },
  trend: {}, swing: {}, structureDetail: {}, wyckoff: {}, externalMacro: {}, daily: { rows: [] }, lastContextAt: 0,
  // EL SOBRE. Una respuesta atomica con UN generated_at, de la que sale TODO lo que K43
  // marca FOTO. Antes cada tarjeta pedia su ruta suelta y resolvia su propio instante, asi
  // que la pantalla daba a entender que todo estaba igual de fresco cuando no lo estaba.
  sobre: null, sobreAt: 0, sobrePendiente: null,
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

