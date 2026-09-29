'use strict';
// LA MESA · la capa de datos. Se llaman las funciones de verdad, no se grepea el fichero.

const test = require('node:test');
const assert = require('node:assert');
const { cargaMesa } = require('./harness-mesa.js');

// `evalua` hace falta para las CONSTANTES: un `const` de primer nivel no acaba en el global
// del contexto de `vm` (solo `var` y las funciones). Ver el comentario de harness-mesa.js.
// `aqui()` NO es adorno: un Array creado dentro del vm lleva otro `Array.prototype`, y
// `deepStrictEqual` compara prototipos. Sin esto el test falla con los valores correctos
// delante, que es la peor clase de rojo: el que acusa al sujeto de un defecto del arnes.
const { ctx, evalua, aqui } = cargaMesa();
const ACTIVOS = aqui(evalua('ACTIVOS'));
const MARCOS = aqui(evalua('MARCOS'));

test('S2 · el simbolo se resuelve al ID CANONICO, que es lo que la API valida', () => {
  // Medido contra 140 el 2026-09-28: `?symbol=BTC` -> HTTP 404 {"detail":"Unknown symbol"};
  // `?symbol=BTCUSDT_PERP.A` -> 200 con filas. Este test fija el arreglo.
  assert.strictEqual(ctx.simbolo('BTC'), 'BTCUSDT_PERP.A');
  assert.strictEqual(ctx.simbolo('ETH'), 'ETHUSDT_PERP.A');
  assert.strictEqual(ctx.simbolo('SOL'), 'SOLUSDT_PERP.A');
});

test('S2 · minusculas tambien resuelven: el mapa no depende de como venga el hash', () => {
  assert.strictEqual(ctx.simbolo('btc'), 'BTCUSDT_PERP.A');
});

test('S2 · un activo desconocido REVIENTA en vez de mandarse al backend "por si cuela"', () => {
  // Mandarlo era exactamente lo que producia el 404. Que falle aqui es el arreglo.
  assert.throws(() => ctx.simbolo('DOGE'), /activo desconocido/);
  assert.throws(() => ctx.simbolo(''), /activo desconocido/);
  assert.throws(() => ctx.simbolo(undefined), /activo desconocido/);
});

test('S2 · ningun activo del mapa se parece a lo que la API rechaza', () => {
  // El fallo era pedir el NOMBRE del activo. Ninguno de los tres valores servidos puede ser
  // igual a su nombre corto, o el arreglo no seria un arreglo.
  assert.strictEqual(ACTIVOS.length, 3);
  ACTIVOS.forEach((a) => {
    assert.notStrictEqual(ctx.simbolo(a), a);
    assert.match(ctx.simbolo(a), /_PERP\.A$/);
  });
});

test('esNada distingue vacio de cero: un 0 es un dato', () => {
  assert.strictEqual(ctx.esNada(null), true);
  assert.strictEqual(ctx.esNada(undefined), true);
  assert.strictEqual(ctx.esNada(''), true);
  // LO QUE IMPORTA: el cero NO es «nada».
  assert.strictEqual(ctx.esNada(0), false);
  assert.strictEqual(ctx.esNada(false), false);
});

test('num devuelve null -no "0"- cuando no hay numero', () => {
  // Un «N/D» pintado como 0 es un cero inventado. El formateador tiene que poder decir null
  // para que quien pinta elija el «no se» que toca.
  assert.strictEqual(ctx.num(null), null);
  assert.strictEqual(ctx.num(undefined), null);
  assert.strictEqual(ctx.num('no soy un numero'), null);
  assert.strictEqual(ctx.num(0, 0), '0');
});

test('usd abrevia con signo y no se come el negativo', () => {
  assert.strictEqual(ctx.usd(7759580165), '$7.76B');
  assert.strictEqual(ctx.usd(-1500000), '-$1.50M');
  assert.strictEqual(ctx.usd(0), '$0');
  assert.strictEqual(ctx.usd(null), null);
});

test('edad devuelve null sin instante: «hace 0 s» sobre un campo que no llego seria inventado', () => {
  assert.strictEqual(ctx.edad(null), null);
  assert.strictEqual(ctx.edad(''), null);
  assert.strictEqual(ctx.edad('no es una fecha'), null);
});

test('edad cuenta contra un ahora DADO, no contra el reloj de pared', () => {
  const t = Date.parse('2026-09-28T20:00:00Z');
  assert.strictEqual(ctx.edad('2026-09-28T20:00:00Z', t), '0 s');
  assert.strictEqual(ctx.edad('2026-09-28T19:59:30Z', t), '30 s');
  assert.strictEqual(ctx.edad('2026-09-28T19:30:00Z', t), '30 min');
  assert.strictEqual(ctx.edad('2026-09-28T10:00:00Z', t), '10 h');
});

test('claseFrescura NO opina sin un tope declarado', () => {
  // Es la regla de la campana: una edad sin tope no tiene veredicto. Si esto devolviera
  // «fresco» por omision, la mesa pintaria verde sobre un dato sin criterio.
  assert.strictEqual(ctx.claseFrescura(10, null), null);
  assert.strictEqual(ctx.claseFrescura(null, 120), null);
});

test('claseFrescura compara contra el tope, no contra un numero escrito a mano', () => {
  assert.strictEqual(ctx.claseFrescura(10, 120), 'fresco');
  assert.strictEqual(ctx.claseFrescura(90, 120), 'tibio');
  assert.strictEqual(ctx.claseFrescura(121, 120), 'viejo');
  // el mismo lag cambia de veredicto si el tope cambia: el tope es lo que manda
  assert.strictEqual(ctx.claseFrescura(90, 3600), 'fresco');
});

test('los tres marcos y los tres activos son los del handoff, sin sobras', () => {
  assert.deepStrictEqual(MARCOS, ['scalp', 'swing', 'largo']);
  assert.deepStrictEqual(ACTIVOS, ['BTC', 'ETH', 'SOL']);
});
