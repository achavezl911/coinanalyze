'use strict';
// Los huecos temporales tienen que VERSE. Quitar el punto ausente no basta: el motor une
// los dos que quedan a los lados con una recta, y esa recta se lee como dato.
//
// Medido contra lightweight-charts 5.2.0 (`scratchpad/gapexp.html`): ni whitespace ni
// `value: null` rompen un LineSeries; lo unico que produce discontinuidad es UNA SERIE POR
// TRAMO. Estas pruebas fijan el troceado, que es lo que alimenta esas series.

const test = require('node:test');
const assert = require('node:assert/strict');
const { cargarApp } = require('./harness');

const app = cargarApp();
const plano = v => JSON.parse(JSON.stringify(v));
const T = i => 1700000000 + i * 60;
// Fila del minuto i con valor v (undefined = la fila existe pero sin valor).
const f = (i, v) => ({ t: T(i), v });
const trocear = filas => app.seriesSegments(filas, r => r.t, r => r.v);
const tiempos = info => info.segments.map(s => s.map(p => p.time));

// ---------------- hueco de una muestra ----------------

test('un hueco de UNA muestra parte la serie en dos tramos', () => {
  const info = trocear([f(0, 100), f(1, 101), f(2, null), f(3, 108)]);
  assert.equal(info.segments.length, 2);
  assert.deepEqual(plano(tiempos(info)), [[T(0), T(1)], [T(3)]]);
  assert.equal(info.gaps.length, 1);
  assert.equal(info.gaps[0].samples, 1);
  assert.equal(info.gaps[0].seconds, 120);      // de t=1 a t=3
  assert.equal(info.missing, 1);
});

test('el hueco NO se rellena: ni interpolado, ni cero, ni precio inventado', () => {
  const info = trocear([f(0, 100), f(1, 101), f(2, null), f(3, null), f(4, 108)]);
  const valores = info.segments.flat().map(p => p.value);
  assert.deepEqual(plano(valores), [100, 101, 108]);
  assert.ok(!valores.includes(0), 'aparecio un cero fabricado');
  // Ningun punto cae dentro del intervalo ausente.
  const dentro = info.segments.flat().filter(p => p.time > T(1) && p.time < T(4));
  assert.deepEqual(plano(dentro), []);
});

// ---------------- hueco de varias muestras ----------------

test('un hueco de varias muestras se cuenta entero y conserva los timestamps', () => {
  const info = trocear([f(0, 100), f(1, 101), f(2, null), f(3, null), f(4, 108), f(5, 109)]);
  assert.equal(info.segments.length, 2);
  assert.deepEqual(plano(tiempos(info)), [[T(0), T(1)], [T(4), T(5)]]);
  assert.equal(info.gaps[0].samples, 2);
  assert.equal(info.gaps[0].seconds, 180);      // de t=1 a t=4
  // La linea de tiempo conserva TODOS los instantes, tambien los ausentes: es lo que
  // reserva el ancho del hueco en el eje.
  assert.deepEqual(plano(info.timeline), [T(0), T(1), T(2), T(3), T(4), T(5)]);
  assert.equal(info.total, 6);
  assert.equal(info.present, 4);
  assert.equal(info.missing, 2);
});

test('dos huecos separados dan tres tramos', () => {
  const info = trocear([f(0, 1), f(1, null), f(2, 3), f(3, null), f(4, 5)]);
  assert.equal(info.segments.length, 3);
  assert.equal(info.gaps.length, 2);
  assert.equal(info.gap_seconds, 120 + 120);
});

// ---------------- huecos en los bordes ----------------

test('hueco INICIAL: no se inventa un extremo izquierdo', () => {
  const info = trocear([f(0, null), f(1, null), f(2, 100), f(3, 101)]);
  assert.equal(info.segments.length, 1);
  assert.deepEqual(plano(tiempos(info)), [[T(2), T(3)]]);
  assert.equal(info.gaps.length, 1);
  assert.equal(info.gaps[0].from, null, 'el hueco inicial no tiene punto anterior');
  assert.equal(info.gaps[0].to, T(2));
  assert.equal(info.gaps[0].seconds, null);
  assert.equal(info.gaps[0].samples, 2);
});

test('hueco FINAL: no se inventa un extremo derecho', () => {
  const info = trocear([f(0, 100), f(1, 101), f(2, null), f(3, null)]);
  assert.equal(info.segments.length, 1);
  assert.deepEqual(plano(tiempos(info)), [[T(0), T(1)]]);
  assert.equal(info.gaps.length, 1);
  assert.equal(info.gaps[0].from, T(1));
  assert.equal(info.gaps[0].to, null, 'el hueco final no tiene punto posterior');
  assert.equal(info.gaps[0].samples, 2);
});

test('una serie entera ausente no produce ningun tramo', () => {
  const info = trocear([f(0, null), f(1, null)]);
  assert.deepEqual(plano(info.segments), []);
  assert.equal(info.present, 0);
  assert.equal(info.missing, 2);
});

// ---------------- que cuenta como ausencia y que no ----------------

test('el CERO real no abre hueco: es un dato medido', () => {
  const info = trocear([f(0, 100), f(1, 0), f(2, 108)]);
  assert.equal(info.segments.length, 1, 'un 0 medido no puede partir la serie');
  assert.deepEqual(plano(info.segments[0].map(p => p.value)), [100, 0, 108]);
  assert.equal(info.gaps.length, 0);
  assert.equal(info.missing, 0);
});

test('null, undefined, cadena vacia y booleano SI abren hueco', () => {
  for (const ausente of [null, undefined, '', '   ', false, true, NaN, Infinity]) {
    const info = trocear([f(0, 100), f(1, ausente), f(2, 108)]);
    assert.equal(info.segments.length, 2, `${String(ausente)} deberia abrir hueco`);
    assert.equal(info.missing, 1, String(ausente));
  }
});

test('una fila sin timestamp valido se ignora sin romper el troceado', () => {
  const info = trocear([{ t: null, v: 1 }, f(0, 100), { t: undefined, v: 2 }, f(1, 101)]);
  assert.equal(info.total, 2);
  assert.equal(info.segments.length, 1);
});

test('una entrada que no es lista no revienta', () => {
  for (const entrada of [null, undefined, {}, 'x', 3]) {
    const info = app.seriesSegments(entrada, r => r.t, r => r.v);
    assert.deepEqual(plano(info.segments), []);
    assert.deepEqual(plano(info.gaps), []);
    assert.equal(info.total, 0);
  }
});

// ---------------- lo que se le cuenta al operador ----------------

test('el pie declara cuantos huecos hay y cuanto suman', () => {
  const info = trocear([f(0, 100), f(1, 101), f(2, null), f(3, null), f(4, 108)]);
  const texto = app.gapCaption(info);
  assert.match(texto, /1 hueco/);
  assert.match(texto, /2 muestras ausentes/);
  assert.match(texto, /3 min sin datos/);
});

test('sin huecos el pie lo dice explicitamente', () => {
  const texto = app.gapCaption(trocear([f(0, 1), f(1, 2), f(2, 3)]));
  assert.match(texto, /sin huecos/);
  assert.ok(!/hueco\(s\)/.test(texto));
});

test('el troceado limita cuantas series se crean, y lo declara', () => {
  // Serie alternante: mas tramos que el maximo -> no se dibuja una linea enganosa.
  const filas = [];
  for (let i = 0; i < 200; i++) filas.push(f(i, i % 2 === 0 ? i : null));
  const info = trocear(filas);
  assert.ok(info.segments.length > 40, 'el caso patologico deberia superar el maximo');
  assert.equal(info.missing, 100);
});
