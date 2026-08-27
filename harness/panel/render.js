// Ejecuta el app.js REAL en un DOM real y devuelve el DOM resultante.
// Dos modos:
//   capture  -> el fetch sale a PRODUCCION por curl y guarda cada respuesta en fixtures/
//   replay   -> el fetch se sirve desde fixtures/, sin red y determinista
// El sujeto es SIEMPRE app.js: el motor de graficos se sustituye por un doble porque
// pinta en canvas, y lo que se mide aqui es el DOM de texto.
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const { JSDOM } = require('jsdom');

const REPO = process.env.REPO || '/srv/coinanalyze/repo';
const NETRC = process.env.NETRC || '/srv/coinanalyze/harness/secretos/api.netrc';
const API_PROD = process.env.API_PROD || 'https://10.151.1.6:8443';

function fixtureName(urlPath) {
  return urlPath.replace(/^\//, '').replace(/[^A-Za-z0-9._-]/g, '_') + '.json';
}

// EL RELOJ SE CONGELA, Y NO ES UN DETALLE. Medido: dos renders identicos del mismo
// payload dan textos distintos -"497s" vs "501s"-, porque el panel pinta antiguedades
// contra Date.now(). Con el reloj vivo, CUALQUIER diferencia de DOM se explica por el
// tiempo, asi que una prueba por mutacion diria "sí, llega a la pantalla" de todos los
// campos, incluidos los que nadie pinta. Congelado, el render es funcion PURA del
// payload y una diferencia de DOM solo puede venir de la mutacion.
function freezeClock(w, ms) {
  const Real = w.Date;
  class Frozen extends Real {
    constructor(...a) { if (a.length === 0) super(ms); else super(...a); }
    static now() { return ms; }
  }
  Frozen.parse = Real.parse; Frozen.UTC = Real.UTC;
  w.Date = Frozen;
  w.performance = w.performance || {};
  try { w.performance.now = () => 0; } catch (e) { /* solo lectura en algunas versiones */ }
}

async function render({ mode, fixtures, settleMs = 4000, onFetch = null, frozenAt = null, transform = null }) {
  const html = fs.readFileSync(path.join(REPO, 'static/index.html'), 'utf8');
  const appjs = fs.readFileSync(path.join(REPO, 'static/app.js'), 'utf8');
  const dom = new JSDOM(html, { runScripts: 'outside-only', url: 'http://localhost/', pretendToBeVisual: true });
  const w = dom.window;

  w.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
  // jsdom no trae EventSource y app.js:1648 abre /api/stream para las pastillas vivas.
  // El doble guarda la instancia para poder inyectarle UNA trama capturada de produccion:
  // asi las tres pastillas (precio, delta, libro) tambien son medibles.
  const streams = [];
  w.EventSource = class {
    constructor(url) { this.url = url; this.readyState = 1; streams.push(this); }
    close() { this.readyState = 2; }
    addEventListener() {}
  };
  w.__streams = streams;
  if (!w.matchMedia) w.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} });
  freezeClock(w, frozenAt || Date.now());
  w.scrollTo = () => {};                                  // jsdom no lo implementa; app.js:1698 lo llama al cambiar de seccion
  Object.defineProperty(w.HTMLElement.prototype, 'scrollIntoView', { value() {}, writable: true });

  const serie = { setData() {}, applyOptions() {}, update() {}, priceScale: () => ({ applyOptions() {} }) };
  const chart = {
    addSeries: () => serie, applyOptions() {}, resize() {}, remove() {},
    timeScale: () => ({ fitContent() {}, applyOptions() {}, setVisibleRange() {} }),
    priceScale: () => ({ applyOptions() {} }),
    subscribeCrosshairMove() {}, subscribeClick() {},
  };
  w.LightweightCharts = {
    createChart: () => chart, createSeriesMarkers: () => ({ setMarkers() {} }),
    ColorType: { Solid: 'solid' }, CrosshairMode: { Normal: 0 },
    LineSeries: 'Line', CandlestickSeries: 'Candlestick', HistogramSeries: 'Histogram',
  };

  const requested = [];   // toda url pedida, en orden
  const status = {};      // url -> codigo
  const errors = [];

  w.fetch = async (url) => {
    const u = String(url);
    requested.push(u);
    if (onFetch) onFetch(u);
    const file = path.join(fixtures, fixtureName(u));
    if (mode === 'capture') {
      if (!fs.existsSync(file)) {
        let body = '', code = 0;
        try {
          const out = execFileSync('curl', ['-sS', '-k', '--netrc-file', NETRC, '--max-time', '25',
            '-w', '\n%{http_code}', API_PROD + u], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
          const cut = out.lastIndexOf('\n');
          body = out.slice(0, cut); code = parseInt(out.slice(cut + 1), 10);
        } catch (e) { code = -1; body = ''; }
        status[u] = code;
        if (code === 200) fs.writeFileSync(file, body);
        else fs.writeFileSync(file + '.status', String(code));
      }
    }
    if (fs.existsSync(file)) {
      let body = fs.readFileSync(file, 'utf8');
      if (transform) body = transform(u, body);
      status[u] = status[u] || 200;
      return { ok: true, status: 200, text: async () => body, json: async () => JSON.parse(body) };
    }
    const code = status[u] || 404;
    return { ok: false, status: code, text: async () => 'sin fixture', json: async () => ({}) };
  };

  w.addEventListener('error', (e) => errors.push(String(e.message || e)));
  w.console.error = (...a) => errors.push(a.map(String).join(' ').slice(0, 300));
  w.console.warn = () => {};

  let fatal = null;
  try {
    w.eval(appjs);
    w.document.dispatchEvent(new w.Event('DOMContentLoaded', { bubbles: true }));
  } catch (e) { fatal = e && e.stack ? e.stack.split('\n').slice(0, 3).join(' | ') : String(e); }

  await new Promise(r => setTimeout(r, settleMs));
  return { dom, window: w, document: w.document, requested, status, errors, fatal };
}

module.exports = { render, fixtureName };
