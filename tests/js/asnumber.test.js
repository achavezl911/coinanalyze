'use strict';
// P0 — la ausencia de dato NO se convierte en cero en el frontend.

const test = require('node:test');
const assert = require('node:assert/strict');
const { cargarApp } = require('./harness');

const app = cargarApp();

// app.js corre en un contexto `vm`, asi que sus objetos llevan el Object.prototype de ESE
// realm y deepStrictEqual los rechazaria por prototipo aunque el contenido coincida. Se
// comparan por valor.
const plano = (valor) => JSON.parse(JSON.stringify(valor));

test('null, undefined y cadena vacia no son numeros', () => {
  for (const valor of [null, undefined, '', '   ', '\t\n']) {
    assert.equal(app.asNumber(valor), null, `asNumber(${JSON.stringify(valor)})`);
  }
});

test('un booleano nunca se convierte en numero', () => {
  // Number(false) === 0 y Number(true) === 1: ambos entrarian como datos medidos.
  assert.equal(app.asNumber(false), null);
  assert.equal(app.asNumber(true), null);
});

test('NaN, infinitos y texto no numerico dan null', () => {
  for (const valor of [NaN, Infinity, -Infinity, 'abc', '12abc', {}, [], [1], () => 1]) {
    assert.equal(app.asNumber(valor), null, `asNumber(${String(valor)})`);
  }
});

test('el cero REAL se conserva como cero', () => {
  assert.equal(app.asNumber(0), 0);
  assert.equal(app.asNumber(-0), -0);
  assert.equal(app.asNumber('0'), 0);
  assert.equal(app.asNumber('0.00'), 0);
});

test('los numeros y las cadenas numericas pasan intactos', () => {
  assert.equal(app.asNumber(42), 42);
  assert.equal(app.asNumber(-1.5), -1.5);
  assert.equal(app.asNumber('  -1.5  '), -1.5);
  assert.equal(app.asNumber('1e3'), 1000);
});

test('los formatos muestran hueco, no cero', () => {
  for (const valor of [null, undefined, '', false]) {
    assert.equal(app.money(valor), '—');
    assert.equal(app.number(valor), '—');
    assert.equal(app.pct(valor), '—');
    assert.equal(app.rate(valor), '—');
    assert.equal(app.nd(valor, app.pct), 'N/D');
  }
  // ...y un cero medido se sigue viendo como cero.
  assert.equal(app.money(0), '$0.0');
  assert.equal(app.pct(0), '+0.00%');
  assert.equal(app.nd(0, app.pct), '+0.00%');
});

test('signClass no pinta direccion sobre un hueco', () => {
  assert.equal(app.signClass(null), 'neutral');
  assert.equal(app.signClass(''), 'neutral');
  assert.equal(app.signClass(false), 'neutral');
  assert.equal(app.signClass(0), 'neutral');
  assert.equal(app.signClass(1), 'positive');
  assert.equal(app.signClass(-1), 'negative');
});

test('fundingClass no declara funding tranquilo cuando no hay funding', () => {
  assert.equal(app.fundingClass(null), 'neutral');
  assert.equal(app.fundingClass(0.05), 'negative');
  assert.equal(app.fundingClass(0.001), 'neutral');
});

// ---------------- series de graficas ----------------

test('seriesPoint devuelve null en vez de un punto en cero', () => {
  assert.equal(app.seriesPoint(10, null), null);
  assert.equal(app.seriesPoint(10, ''), null);
  assert.equal(app.seriesPoint(10, false), null);
  assert.deepEqual(plano(app.seriesPoint(10, 0)), { time: 10, value: 0 });
});

test('seriesPoints omite los puntos ausentes y cuenta el hueco', () => {
  const filas = [
    { t: 1, v: 5 },
    { t: 2, v: null },
    { t: 3, v: '' },
    { t: 4, v: 0 },
    { t: 5, v: 7 },
  ];
  const puntos = app.seriesPoints(filas, r => r.t, r => r.v);
  assert.deepEqual(plano(puntos), [
    { time: 1, value: 5 },
    { time: 4, value: 0 },
    { time: 5, value: 7 },
  ]);
  assert.equal(puntos.dropped, 2);
});

test('un hueco NO se rellena con un punto intermedio', () => {
  // La serie salta de t=1 a t=5: no aparece ningun punto en 2, 3 ni 4. Que el motor una
  // esos dos puntos con una recta es visible; inventar valores intermedios no lo seria.
  const puntos = app.seriesPoints(
    [{ t: 1, v: 100 }, { t: 2, v: null }, { t: 3, v: null }, { t: 4, v: null }, { t: 5, v: 100 }],
    r => r.t, r => r.v,
  );
  assert.equal(puntos.length, 2);
  assert.deepEqual(plano(puntos.map(p => p.time)), [1, 5]);
  assert.equal(puntos.dropped, 3);
});

test('seriesPoints tolera una entrada que no es lista', () => {
  for (const entrada of [null, undefined, {}, 'x']) {
    assert.deepEqual([...app.seriesPoints(entrada, r => r.t, r => r.v)], []);
  }
});
