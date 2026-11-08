'use strict';
/* Lo puro del dibujo de /flujo (campana 146-D, static/flujo/flujo-trazos.js): la regresion del canal, las siete
 * lineas de Fibonacci, la distancia de un clic a un segmento, la x de un instante (con un hueco en las velas y fuera
 * de ellas) y la lectura de lo guardado. Se llama a las funciones de verdad, como flujo_pro.test.js. */
const test = require('node:test');
const assert = require('node:assert');
const T = require('../../static/flujo/flujo-trazos.js');

const cerca = (a, b, tol = 1e-9) => assert.ok(Math.abs(a - b) <= tol * Math.max(1, Math.abs(b)), `${a} != ${b}`);

test('regresion: cierres = 3 + 2i, exacta (pendiente 2, ordenada 3, sigma 0)', () => {
  const r = T.regresion([3, 5, 7, 9, 11, 13]);
  cerca(r.pendiente, 2);
  cerca(r.ordenada, 3);
  cerca(r.sigma, 0);
  assert.strictEqual(r.n, 6);
});

test('regresion: residuos conocidos; sigma de la POBLACION (n, no n-1)', () => {
  // y = 10 + i + e, e = [+1, -1, -1, +1]: simetrico respecto al centro y ortogonal a x - media -> pendiente 1, ordenada 10
  const r = T.regresion([11, 10, 11, 14]);
  cerca(r.pendiente, 1);
  cerca(r.ordenada, 10);
  cerca(r.sigma, 1); // raiz(4 / 4); con n-1 seria raiz(4 / 3)
  assert.ok(Math.abs(r.sigma - Math.sqrt(4 / 3)) > 0.1);
});

test('regresion: un null ocupa su indice pero no cuenta; con menos de 3, null', () => {
  const r = T.regresion([3, null, 7, 9]);
  cerca(r.pendiente, 2);
  cerca(r.ordenada, 3);
  assert.strictEqual(r.n, 3);
  assert.strictEqual(T.regresion([1, null, 2]), null);
  assert.strictEqual(T.regresion([]), null);
});

test('canalDe: la vela hueco no cuenta y x es el indice dentro del tramo', () => {
  const velas = [100, 3, 5, 999, 9, 11].map((c, i) => ({ cierre: c, estado: i === 3 ? 'hueco' : 'completa' }));
  const r = T.canalDe(velas, 1, 5);
  cerca(r.pendiente, 2);
  cerca(r.ordenada, 3);
  cerca(r.sigma, 0);
  assert.strictEqual(r.n, 4);
  assert.strictEqual(T.canalDe(velas, 2, 4), null); // 5 y 9: dos con cierre
});

test('fibonacci: los siete precios, del 1er punto (0) al 2o (1)', () => {
  const f = T.fibonacci(100, 200);
  assert.deepStrictEqual(f.map((x) => x.razon), [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1]);
  [100, 123.6, 138.2, 150, 161.8, 178.6, 200].forEach((p, k) => cerca(f[k].precio, p));
  const g = T.fibonacci(200, 100);
  [200, 176.4, 161.8, 150, 138.2, 121.4, 100].forEach((p, k) => cerca(g[k].precio, p));
});

test('distSegmento: perpendicular, mas alla de un extremo y segmento degenerado', () => {
  cerca(T.distSegmento(5, 3, 0, 0, 10, 0), 3);
  cerca(T.distSegmento(13, 4, 0, 0, 10, 0), 5);
  cerca(T.distSegmento(-3, -4, 0, 0, 10, 0), 5);
  cerca(T.distSegmento(3, 4, 0, 0, 0, 0), 5);
  cerca(T.distSegmento(0, 10, 0, 0, 10, 10), Math.sqrt(50));
});

test('xDeInstante: un hueco en las velas no corre lo de despues; fuera, extrapola con el marco', () => {
  const M = 60000;
  const t0 = Date.parse('2026-11-01T10:00:00Z');
  // falta la vela de 10:02: el array salta de 10:01 a 10:03
  const ts = [t0, t0 + M, t0 + 3 * M, t0 + 4 * M];
  const x0 = 50;
  const bs = 10; // vela i centrada en 50 + 10 i
  cerca(T.xDeInstante(t0, ts, M, x0, bs), 45);
  cerca(T.xDeInstante(t0 + 3 * M, ts, M, x0, bs), 65); // borde izquierdo de la vela 2 (10:03), no 75
  cerca(T.xDeInstante(t0 + 3 * M + M / 2, ts, M, x0, bs), 70);
  cerca(T.xDeInstante(t0 + 2 * M + M / 2, ts, M, x0, bs), 65); // dentro del minuto que falta: borde de la anterior
  cerca(T.xDeInstante(t0 - 2 * M, ts, M, x0, bs), 25); // antes de la primera
  cerca(T.xDeInstante(t0 + 6 * M, ts, M, x0, bs), 95); // despues de la ultima (10:04 + 2 min)
  // la forma por indice ((t - t0) / marco) daria 75 para 10:03: el test la condena
  assert.notStrictEqual(T.xDeInstante(t0 + 3 * M, ts, M, x0, bs), x0 - bs / 2 + 3 * bs);
  assert.strictEqual(T.xDeInstante(t0, [], M, x0, bs), null);
});

test('instanteDeX: la inversa dentro y fuera de las velas', () => {
  const M = 60000;
  const t0 = Date.parse('2026-11-01T10:00:00Z');
  const ts = [t0, t0 + M, t0 + 3 * M, t0 + 4 * M];
  [t0, t0 + M / 4, t0 + 3 * M + 20000, t0 + 4 * M + 59000, t0 - 7 * M, t0 + 9 * M].forEach((t) => {
    assert.strictEqual(T.instanteDeX(T.xDeInstante(t, ts, M, 50, 10), ts, M, 50, 10), t);
  });
});

test('tramoDe: las velas que se solapan con el intervalo, en cualquier orden de los clics', () => {
  const M = 60000;
  const ts = [0, M, 3 * M, 4 * M];
  assert.deepStrictEqual(T.tramoDe(M / 2, 3 * M + 1, ts, M), [0, 2]);
  assert.deepStrictEqual(T.tramoDe(3 * M + 1, M / 2, ts, M), [0, 2]);
  assert.deepStrictEqual(T.tramoDe(2 * M + 1, 2 * M + 2, ts, M), null); // solo el minuto que falta
  assert.deepStrictEqual(T.tramoDe(-5 * M, 99 * M, ts, M), [0, 3]);
});

test('leeGuardado: basura, otra version y nada dan []; el trazo malo cae y los buenos se quedan', () => {
  assert.deepStrictEqual(T.leeGuardado('{no es json', 'BTC'), []);
  assert.deepStrictEqual(T.leeGuardado(null, 'BTC'), []);
  assert.deepStrictEqual(T.leeGuardado('42', 'BTC'), []);
  assert.deepStrictEqual(T.leeGuardado('[]', 'BTC'), []);
  const nivel = { tipo: 'nivel', id: 'a', puntos: [{ t: 1000, p: 50000 }] };
  const linea = { tipo: 'linea', id: 'c', puntos: [{ t: 1000, p: 1 }, { t: 2000, p: 2 }] };
  const ajena = JSON.stringify({ version: 99, activos: { BTC: [nivel] } });
  assert.deepStrictEqual(T.leeGuardado(ajena, 'BTC'), []);
  const sinPuntos = { tipo: 'fib', id: 'b' };
  const malos = [
    { tipo: 'fib', id: 'd', puntos: [{ t: 1, p: 2 }] }, // le falta un punto
    { tipo: 'pincel', id: 'e', puntos: [{ t: 1, p: 2 }] },
    { tipo: 'nivel', id: 'f', puntos: [{ t: 'x', p: 2 }] },
    { tipo: 'nivel', id: 'g', puntos: [{ t: 1, p: null }] },
    { tipo: 'nivel', puntos: [{ t: 1, p: 2 }] },
    null,
  ];
  const texto = JSON.stringify({ version: T.VERSION, activos: { BTC: [nivel, sinPuntos, ...malos, linea], ETH: 'x' } });
  assert.deepStrictEqual(T.leeGuardado(texto, 'BTC'), [nivel, linea]);
  assert.deepStrictEqual(T.leeGuardado(texto, 'ETH'), []);
  assert.deepStrictEqual(T.leeGuardado(texto, 'SOL'), []);
});

test('escribeGuardado: por ACTIVO (no por marco); lo de los otros activos se queda; basura previa se rehace', () => {
  const nivel = { tipo: 'nivel', id: 'a', puntos: [{ t: 1000, p: 50000 }], sel: true };
  let s = T.escribeGuardado(null, 'BTC', [nivel]);
  s = T.escribeGuardado(s, 'ETH', [{ tipo: 'nivel', id: 'z', puntos: [{ t: 5, p: 3000 }] }]);
  assert.deepStrictEqual(T.leeGuardado(s, 'BTC'), [{ tipo: 'nivel', id: 'a', puntos: [{ t: 1000, p: 50000 }] }]);
  assert.strictEqual(T.leeGuardado(s, 'ETH').length, 1);
  assert.deepStrictEqual(Object.keys(JSON.parse(s).activos).sort(), ['BTC', 'ETH']);
  assert.strictEqual(JSON.parse(s).version, T.VERSION);
  const r = T.escribeGuardado('basura', 'BTC', []);
  assert.deepStrictEqual(JSON.parse(r), { version: T.VERSION, activos: { BTC: [] } });
});
