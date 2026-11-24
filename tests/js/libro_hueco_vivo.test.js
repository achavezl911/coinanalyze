'use strict';
// (libro r1, F12c M1 + M2, P18) en /libro en vivo, el instante que no se leyo es una columna HUECO, no un salto entre
// dos columnas contiguas; y el fallo del footprint se escribe aunque quede la huella de antes. Las funciones se sacan del
// texto de la pagina (libro-app.js no es un modulo) y corren contra dobles de reloj y temporizadores.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

Object.assign(global, require('../../static/flujo/flujo-calculo.js'));
const C = require('../../static/libro/libro-calculo.js');
const E = require('../../static/libro/libro-escalera.js');
const APP = fs.readFileSync(path.join(__dirname, '../../static/libro/libro-app.js'), 'utf8');
const MAPA = fs.readFileSync(path.join(__dirname, '../../static/libro/libro-mapa.js'), 'utf8');

function funcion(src, nombre) { // `function nombre(...) {...}` hasta su llave de cierre (salta comentarios y cadenas)
  const m = new RegExp('^(async )?function ' + nombre + '\\(', 'm').exec(src);
  let hondo = 0;
  for (let i = src.indexOf('{', src.indexOf(')', m.index)); i < src.length; i++) {
    const ch = src[i];
    if (ch === '/' && src[i + 1] === '/') { i = src.indexOf('\n', i); continue; }
    if (ch === "'" || ch === '"' || ch === '`') { for (i++; src[i] !== ch; i++) if (src[i] === '\\') i++; continue; }
    if (ch === '{') hondo++;
    if (ch === '}' && --hondo === 0) return src.slice(m.index, i + 1);
  }
  throw new Error('sin cierre: ' + nombre);
}
const entorno = (o) => new Proxy(o, { has: () => true, get: (t, k) => (k in t ? t[k] : globalThis[k]) });
const evalua = (src, env) => new Function('__e', 'with (__e) { return (' + src + '); }')(entorno(env));

const cada = C.cadaPara(2, C.LIBRO_VENTANAS['30m'] * 60);
const c = cada * 1000;
const t0 = Date.parse('2026-11-20T06:00:00Z');

/* programaColumna con la historia de 30m hasta t0 y un doble de temporizadores; `tardes` = retraso de cada despertar */
function corre(tardes, ws) {
  let T = t0 + 1000;
  const cola = [];
  const columnas = [];
  const n0 = (C.LIBRO_VENTANAS['30m'] * 60) / cada;
  for (let k = n0 - 1; k >= 0; k--) columnas.push({ ts: t0 - k * c, estado: 'foto', origen: 'historia' });
  const libro = () => ({ m: { tipo: 'libro' }, get llegadaMs() { return ws ? T - 500 : t0 + 3 * c; } });
  const e = { MODELO: { cada, fijo: false, venues: ['binance_usdm', 'bybit_linear'], N: 2, paso: '1', columnas, honda: null },
    VIVO: { libros: { binance_usdm: libro(), bybit_linear: libro() }, columna: null }, VISTA: { ventana: '30m' },
    LIBRO_VENTANAS: C.LIBRO_VENTANAS, HONDA_EN_VIVO: false, ahora: () => T, estadoVenue: E.estadoVenue,
    setTimeout: (fn, ms) => { cola.push({ fn, a: T + ms }); return cola.length; },
    libroDe: (v) => ({ venue: v }), sumaFamilia: (v) => (v.length ? { leido: T } : null), EL_MAPA: { actualiza() {} } };
  evalua(funcion(APP, 'programaColumna'), e)();
  tardes.forEach((tarde) => { const x = cola.shift(); T = x.a + tarde; x.fn(); });
  const cs = e.MODELO.columnas;
  const saltos = cs.filter((x, j) => j > 0 && x.ts - cs[j - 1].ts !== c).length;
  const vivas = cs.filter((x) => x.origen === 'vivo');
  // la geometria de libro-mapa.js (xDe por indice, xT por tiempo), con la ventana entera a la vista
  const bs = 1100 / cs.length;
  const xDe = (j) => 1100 - (cs.length - j) * bs;
  const desfase = xDe(0) + ((cs[cs.length - 1].ts - cs[0].ts) / c) * bs - xDe(cs.length - 1);
  return { saltos, desfase, vivas, huecos: vivas.filter((x) => x.estado === 'hueco').length, T };
}

test('M1: un despertar 180 s tarde deja 18 instantes como HUECO, sin salto; lo anclado al tiempo cae en su columna', () => {
  for (const ws of [true, false]) {
    const r = corre([0, 0, 0, 180000, 0, 0, 0], ws);
    assert.strictEqual(r.saltos, 0, 'saltos entre columnas contiguas (ws=' + ws + ')');
    assert.ok(Math.abs(r.desfase) < 1e-6, 'xT - xDe de la ultima columna: ' + r.desfase);
    assert.strictEqual(r.vivas.length, 7 + 180000 / c, 'una columna por instante de rejilla');
    assert.strictEqual(r.huecos, ws ? 180000 / c : 7 + 180000 / c - 3, 'los saltados son hueco; con sondeo, rancios');
  }
});

test('M1: con un despertar por minuto (pestana oculta), entra una columna por instante, no una por despertar', () => {
  const r = corre([0, ...Array(10).fill(60000 - c)], true);
  assert.strictEqual(r.saltos, 0);
  assert.strictEqual(r.vivas.length, (r.T - t0) / c);
});

test('SIN retraso: 400 despertares a su hora (y con hasta 999 ms de deriva) no dan NINGUN hueco de mas', () => {
  for (const deriva of [0, 999]) {
    const r = corre(Array.from({ length: 400 }, (_, k) => (k * 37) % (deriva + 1)), true);
    assert.deepStrictEqual([r.saltos, r.huecos, r.vivas.length], [0, 0, 400]);
  }
});

const huella = { desde: isoZ(t0 - 120 * 60000), hasta: isoZ(t0), velas: [{ ts: isoZ(t0 - 60000), cierre: '62000.5' }] };

test('M2: 5 refrescos del footprint con 502 dejan la huella de antes, pero repintan el mapa 5 veces', async () => {
  const t = t0;
  let pintadas = 0;
  const e = { MODELO: { fijo: false, activo: 'BTC', venues: ['binance_usdm'], paso: '1', huella, huellaUltimo: t - 60000,
    huellaFallo: null, liq: null }, CARGA: 1, isoZ, RUTA_HUELLA: '/api/orderflow/footprint', apuntar() {},
    window: { LIBRO_HITOS: { congelado: false, recibidos: { huella: 0 } } },
    pedir: async () => ({ ok: false, http: 502 }), EL_MAPA: { actualiza() { pintadas += 1; } } };
  const lateHuella = evalua(funcion(APP, 'lateHuella'), e);
  for (let k = 1; k <= 5; k++) await lateHuella(1, t + k * 60000);
  assert.strictEqual(e.MODELO.huella, huella); // la de antes se queda...
  assert.strictEqual(e.MODELO.huellaFallo, 'el footprint respondió 502');
  assert.strictEqual(pintadas, 5); // ...pero el mapa se repinta y lo dice
});

test('M2: el aviso del mapa escribe el fallo del footprint aunque se vea la huella de antes', () => {
  const a = MAPA.indexOf('const hh = ');
  const bloque = MAPA.slice(a, MAPA.indexOf('L.aviso.title', a));
  const L = { ver: 10, pedido: 10, aviso: {} };
  const m = { huella, huellaFallo: 'el footprint respondió 502', honda: null };
  new Function('__e', 'with (__e) { ' + bloque + ' }')(entorno({ L, n: 10, filas: 5, conocidos: 5, cx: 99, cy: 99, m,
                                                               volumen: { desde: huella.desde, hasta: huella.hasta } }));
  assert.match(L.aviso.textContent, /footprint 1m de 04:00 a 06:00Z/);
  assert.match(L.aviso.textContent, /volumen: el footprint respondió 502 \(se ve el de antes\)/);
});
