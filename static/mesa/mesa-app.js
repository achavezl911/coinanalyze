'use strict';
/* LA MESA · el estado, el enrutador y las DOS OLAS
 * ---------------------------------------------------------------------------
 * POR QUE EL ESTADO VIVE EN EL HASH. Cada vista tiene su URL -`#scalp/BTC`,
 * `#swing/ETH`, `#scalp/BTC/status`- y eso no es comodidad: las capturas van por Chromium
 * headless, y **headless no puede pulsar nada**. Con el estado en el hash cada vista es
 * verificable con una URL y una captura, que es lo que necesitan C4 y la red de K102.
 *
 * POR QUE DOS OLAS, Y POR QUE ESE ES EL ARREGLO DE LA LENTITUD.
 * Medido contra 140 el 2026-09-28, el camino viejo pedia el sobre entero para pintar DECIDE:
 *     /api/ai/context?profile=default   7.026 · 6.318 · 7.497 s   141639 B
 * DECIDE no necesita el sobre. Necesita `operator_read`, que son dos consultas. Asi que:
 *     OLA 1 · UNA peticion a /api/mesa/decide  ->  se pinta DECIDE y se para el reloj
 *     OLA 2 · el resto de los paneles, DESPUES de que DECIDE ya este en pantalla
 * La ola 2 no puede retrasar a la ola 1: se lanza en un `setTimeout(0)` posterior al pintado
 * para que el navegador tenga ocasion de presentar el primer fotograma antes de empezar a
 * pedir nueve rutas mas.
 *
 * LOS HITOS SE MARCAN CON `performance.mark` PARA QUE SE PUEDAN MEDIR DESDE FUERA:
 *     mesa:decide-pintado     ·  cuando DECIDE ENSENA DATOS
 *     mesa:completo           ·  cuando la ola 2 termina
 * `window.MESA_HITOS` los expone para que la sonda de Chromium los lea sin adivinar.
 */

const ESTADO = { marco: 'scalp', activo: 'BTC', vista: 'mesa' };

window.MESA_HITOS = { t0: null, decidePintado: null, completo: null, peticiones: [] };

function marca(nombre) {
  try {
    if (window.performance && window.performance.mark) window.performance.mark(nombre);
  } catch (e) {
    /* una marca que falla no puede tumbar la mesa */
  }
}

/* ------------------------------------------------------------ el hash */
/* `#<marco>/<activo>[/status]`. Lo que no se entiende NO se adivina: se cae al defecto y se
 * reescribe el hash, para que la URL y la pantalla nunca digan cosas distintas. */
function leerHash(hash) {
  const partes = String(hash || '')
    .replace(/^#/, '')
    .split('/')
    .filter(Boolean);
  const marco = MARCOS.indexOf(partes[0]) >= 0 ? partes[0] : 'scalp';
  const activo = ACTIVOS.indexOf(String(partes[1] || '').toUpperCase()) >= 0
    ? String(partes[1]).toUpperCase()
    : 'BTC';
  const vista = partes[2] === 'status' ? 'estado' : 'mesa';
  return { marco, activo, vista };
}

function escribirHash(e) {
  const h = '#' + e.marco + '/' + e.activo + (e.vista === 'estado' ? '/status' : '');
  if (window.location.hash !== h) window.location.hash = h;
  return h;
}

/* --------------------------------------------------------- los nodos */
function nodosDecide() {
  return {
    caja: document.getElementById('decide'),
    sesgo: document.getElementById('decide-sesgo'),
    motivo: document.getElementById('decide-motivo'),
    campos: document.getElementById('decide-campos'),
    edad: document.getElementById('decide-edad'),
    escalones: document.getElementById('conf-escalones'),
    confPalabra: document.getElementById('conf-palabra'),
    confClave: document.getElementById('conf-clave'),
    dcRelleno: document.getElementById('dc-relleno'),
    dcValor: document.getElementById('dc-valor'),
    dcClave: document.getElementById('dc-clave'),
  };
}

function apuntar(sobre) {
  window.MESA_HITOS.peticiones.push({
    ruta: sobre.ruta,
    ms: Math.round(sobre.ms),
    http: sobre.http,
    ok: sobre.ok,
  });
}

/* ------------------------------------------------------------ OLA 1 */
async function olaDecide() {
  const s = simbolo(ESTADO.activo);
  const sobre = await pedir('/api/mesa/decide', { symbol: s, frame: ESTADO.marco });
  apuntar(sobre);
  pintarDecide(sobre, nodosDecide());

  // EL RELOJ DE LA CABECERA ES EL CORTE DEL SOBRE, no un reloj de pared que se incrementa
  // solo: un contador que sube sin pedir nada diria una frescura que no tiene.
  const reloj = document.getElementById('reloj');
  if (sobre.ok) {
    const cut = sobre.datos.envelope_cut || {};
    const lag =
      (sobre.datos.age &&
        sobre.datos.age.snapshot_lag_seconds &&
        sobre.datos.age.snapshot_lag_seconds.value) ||
      null;
    reloj.textContent = String(cut.as_of || '').slice(11, 19) + ' UTC';
    const c = claseFrescura(lag, sobre.datos.max_age_s);
    reloj.className = 'reloj-valor ' + (c || '');
  } else {
    reloj.textContent = 'sin corte';
    reloj.className = 'reloj-valor viejo';
  }

  marca('mesa:decide-pintado');
  window.MESA_HITOS.decidePintado = (window.performance || Date).now();
  return sobre;
}

/* ------------------------------------------------------------ OLA 2 */
async function olaResto(sobreDecide) {
  const s = simbolo(ESTADO.activo);
  const m = ESTADO.marco;

  // Se piden EN PARALELO: son independientes y el navegador ya tiene DECIDE en pantalla.
  const trabajos = {
    feeds: pedir('/api/quality/feeds', { symbol: s }),
    scan: pedir('/api/scalp/signals', { symbol: s }),
    matriz: pedir('/api/scalp/delta-matrix', { symbol: s }),
    follow: pedir('/api/setup', { symbol: s }),
    learn: pedir('/api/signals/replay', { symbol: s }),
  };
  if (m === 'scalp') {
    trabajos.libro = pedir('/api/scalp/orderbook', { symbol: s });
    trabajos.liq = pedir('/api/liquidation-map', { symbol: s });
    trabajos.perfil = pedir('/api/volume-profile', { symbol: s });
  } else if (m === 'swing') {
    trabajos.wyckoff = pedir('/api/wyckoff', { symbol: s });
    trabajos.oi = pedir('/api/oi-context', { symbol: s });
    trabajos.liq = pedir('/api/liquidation-map', { symbol: s });
    trabajos.perfil = pedir('/api/volume-profile', { symbol: s });
  } else {
    trabajos.estructura = pedir('/api/structure-detail', { symbol: s });
    trabajos.basis = pedir('/api/scalp/basis', { symbol: s });
    trabajos.macro = pedir('/api/external-macro', { symbol: s });
  }

  const claves = Object.keys(trabajos);
  const hechos = await Promise.all(claves.map((k) => trabajos[k]));
  const d = { decide: sobreDecide };
  claves.forEach((k, i) => {
    d[k] = hechos[i];
    apuntar(hechos[i]);
  });

  if (d.feeds) pintarTira(d.feeds, document.getElementById('tira'));
  if (d.scan) pintarScan(d.scan, document.getElementById('scan'));
  if (d.matriz)
    pintarMatriz(
      d.matriz,
      document.getElementById('matriz'),
      document.getElementById('matriz-pie'),
      document.getElementById('matriz-venue')
    );
  pintarInspect(m, d, document.getElementById('inspect'));
  pintarResearch(m, d, document.getElementById('research'));
  if (d.follow) pintarFollow(d.follow, document.getElementById('follow'));
  if (d.learn) pintarLearn(d.learn, document.getElementById('learn'));
  if (d.feeds) pintarServicios(d.feeds, document.getElementById('pie-servicios'));

  marca('mesa:completo');
  window.MESA_HITOS.completo = (window.performance || Date).now();
  return d;
}

/* --------------------------------------------------- vista de estado */
async function pintarEstado() {
  const s = simbolo(ESTADO.activo);
  const [salud, feeds] = await Promise.all([
    pedir('/api/healthz', {}),
    pedir('/api/quality/feeds', { symbol: s }),
  ]);
  apuntar(salud);
  apuntar(feeds);

  const res = vaciar(document.getElementById('estado-resumen'));
  const tarjeta = (rotulo, valor, nota) => {
    const t = el('section', 'tarjeta');
    t.appendChild(el('div', 'rotulo conf-rotulo', rotulo));
    const v = el('div', 'valor mono');
    if (valor === null || valor === undefined) v.appendChild(noSe('ausente', nota || null));
    else v.textContent = valor;
    t.appendChild(v);
    if (nota && valor !== null && valor !== undefined) t.appendChild(el('div', 'pie', nota));
    return t;
  };

  const col = (feeds.ok && feeds.datos.collectors) || {};
  const vivos = Object.keys(col).filter((k) => String((col[k] || {}).status).toUpperCase() === 'OK');
  res.appendChild(
    tarjeta('servicios activos', Object.keys(col).length ? vivos.length + ' / ' + Object.keys(col).length : null,
            'de /api/quality/feeds.collectors')
  );
  const fs = (feeds.ok && feeds.datos.feeds) || [];
  const lats = fs.map((f) => f.latency_seconds).filter((x) => !esNada(x)).map(Number);
  res.appendChild(
    tarjeta('latencia mediana de feeds',
            lats.length ? num(lats.sort((a, b) => a - b)[Math.floor(lats.length / 2)], 1) + ' s' : null,
            'mediana DERIVADA de los ' + lats.length + ' feeds con latencia servida')
  );
  res.appendChild(
    tarjeta('ventana de calidad',
            feeds.ok && !esNada(feeds.datos.window_seconds) ? num(feeds.datos.window_seconds, 0) + ' s' : null,
            'feed_quality.window_seconds')
  );
  // UPTIME 30D: el mockup pone «99.9 %». El backend no lo publica. Se dice.
  res.appendChild(
    tarjeta('uptime 30 d', null, 'el backend no publica uptime a 30 dias: no se inventa un 99,9 %')
  );

  const proc = vaciar(document.getElementById('estado-procesos'));
  if (!feeds.ok) fallo(proc, feeds);
  else pintarServicios(feeds, proc);

  const cajaFeeds = vaciar(document.getElementById('estado-feeds'));
  if (!feeds.ok) fallo(cajaFeeds, feeds);
  else {
    const t = el('table', 'rejilla');
    const tr = el('tr');
    ['feed', 'venue', 'mercado', 'estado', 'latencia', 'cobertura'].forEach((h) =>
      tr.appendChild(el('th', null, h))
    );
    t.appendChild(tr);
    fs.forEach((f) => {
      const r = el('tr');
      r.appendChild(el('td', null, f.feed || 'N/D'));
      r.appendChild(el('td', null, f.exchange || 'N/D'));
      r.appendChild(el('td', null, f.market || 'N/D'));
      r.appendChild(el('td', null, f.status || 'N/D'));
      const tl = el('td');
      if (esNada(f.latency_seconds)) tl.appendChild(el('span', 'nd', 'N/D'));
      else tl.textContent = num(f.latency_seconds, 1) + ' s';
      r.appendChild(tl);
      const tc = el('td');
      if (esNada(f.coverage_pct)) tc.appendChild(el('span', 'nd', 'N/D'));
      else tc.textContent = num(f.coverage_pct, 1) + ' %';
      r.appendChild(tc);
      t.appendChild(r);
    });
    cajaFeeds.appendChild(t);
  }

  /* LO QUE ESTA PANTALLA NO PUEDE SERVIR COMO PIDE EL HANDOFF, dicho aqui y no escondido. */
  const dec = vaciar(document.getElementById('estado-declaraciones'));
  [
    [
      'la tipografía del handoff',
      'pide Space Grotesk e IBM Plex Mono «via Google Fonts CDN». La CSP de produccion ' +
        '(app/api.py) incluye `font-src \'self\'`, que bloquea ese CDN, y ninguna de las dos ' +
        'familias esta instalada en el servidor. Se usa una pila de sistema con la misma ' +
        'intencion. El propio README lo preveia: «swap for self-hosted fonts if required».',
    ],
    [
      'la «respuesta atómica» única',
      'el handoff pide UNA peticion para todo. Se cumple su OBJETIVO -que cada modulo ensene la ' +
        'edad real de su fuente- pero no su mecanismo: DECIDE va en UNA peticion con UN corte ' +
        'declarado (`envelope_cut.snapshot = repeatable_read`), y las familias con ventana propia ' +
        'van aparte porque meterlas dentro les borraria su cobertura.',
    ],
    [
      'el heatmap precio × tiempo',
      '/api/liquidation-map sirve niveles de PRECIO. El eje de TIEMPO no es un dato servido: solo ' +
        'se puede derivar restando ventanas acumuladas (8 peticiones).',
    ],
    [
      'la escalera del libro por nivel',
      '/api/scalp/orderbook sirve profundidad AGREGADA por venue (L1/L5/L10), no cinco precios.',
    ],
    [
      'el histograma del perfil de volumen',
      'el backend publica POC/VAH/VAL/HVN/LVN, no el histograma bin a bin.',
    ],
    [
      'la confianza como porcentaje',
      '`operator_read.confidence` sirve una PALABRA (baja/media/alta). La barra tiene tres ' +
        'escalones rotulados; un % seria precision inventada.',
    ],
    [
      'el lienzo de precio con CVD',
      'no dibujado en esta parada. Se declara como hueco en vez de pintar una linea de ejemplo.',
    ],
  ].forEach(([t, m]) => hueco(dec, t, m));

  marca('mesa:completo');
  window.MESA_HITOS.completo = (window.performance || Date).now();
}

/* ------------------------------------------------------------ enrutador */
function pintarSelectores() {
  document.querySelectorAll('#sel-marco button').forEach((b) => {
    b.setAttribute('aria-pressed', String(b.dataset.marco === ESTADO.marco));
  });
  document.querySelectorAll('#sel-activo button').forEach((b) => {
    b.setAttribute('aria-pressed', String(b.dataset.activo === ESTADO.activo));
  });
  document.getElementById('ir-estado').setAttribute(
    'href',
    '#' + ESTADO.marco + '/' + ESTADO.activo + '/status'
  );
  document.getElementById('volver').setAttribute('href', '#' + ESTADO.marco + '/' + ESTADO.activo);
}

let _pintando = 0;
async function pintar() {
  const mio = ++_pintando;
  window.MESA_HITOS.t0 = (window.performance || Date).now();
  window.MESA_HITOS.decidePintado = null;
  window.MESA_HITOS.completo = null;
  window.MESA_HITOS.peticiones = [];
  marca('mesa:t0');

  pintarSelectores();
  const esEstado = ESTADO.vista === 'estado';
  document.getElementById('vista-mesa').hidden = esEstado;
  document.getElementById('vista-estado').hidden = !esEstado;

  if (esEstado) {
    await pintarEstado();
    return;
  }

  const sobre = await olaDecide();
  if (mio !== _pintando) return; // llego otro cambio de vista: esta pasada ya no manda

  // La ola 2 espera un turno para que el navegador presente DECIDE antes de pedir nueve rutas.
  await new Promise((r) => setTimeout(r, 0));
  if (mio !== _pintando) return;
  await olaResto(sobre);
}

function aplicarHash() {
  const e = leerHash(window.location.hash);
  ESTADO.marco = e.marco;
  ESTADO.activo = e.activo;
  ESTADO.vista = e.vista;
  pintar();
}

function arrancar() {
  document.getElementById('sel-marco').addEventListener('click', (ev) => {
    const b = ev.target.closest('button[data-marco]');
    if (!b) return;
    ESTADO.marco = b.dataset.marco;
    escribirHash(ESTADO);
  });
  document.getElementById('sel-activo').addEventListener('click', (ev) => {
    const b = ev.target.closest('button[data-activo]');
    if (!b) return;
    ESTADO.activo = b.dataset.activo;
    escribirHash(ESTADO);
  });
  window.addEventListener('hashchange', aplicarHash);

  if (!window.location.hash) {
    escribirHash(ESTADO);
  }
  aplicarHash();
}

if (typeof document !== 'undefined' && document.addEventListener) {
  document.addEventListener('DOMContentLoaded', arrancar);
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { leerHash, ESTADO };
}
