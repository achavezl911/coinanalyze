'use strict';
// LA MESA · el estado en el hash. Cada vista tiene su URL, y eso es lo que hace que una
// captura por Chromium headless -que no puede pulsar nada- pueda llegar a cualquier vista.

const test = require('node:test');
const assert = require('node:assert');
const { cargaMesa } = require('./harness-mesa.js');

// `aqui()` trae al realm de los tests lo que `leerHash` construyo DENTRO del vm: un objeto de
// otro contexto lleva otro `Object.prototype` y `deepStrictEqual` lo rechaza con los mismos
// valores delante. `evalua()` lee las constantes, que no llegan al global del contexto.
const { ctx, evalua, aqui } = cargaMesa();
const MARCOS = evalua('MARCOS');
const ACTIVOS = evalua('ACTIVOS');
const leer = (h) => aqui(ctx.leerHash(h));

test('las cinco formas del hash del handoff se leen', () => {
  assert.deepStrictEqual(leer('#scalp/BTC'), { marco: 'scalp', activo: 'BTC', vista: 'mesa' });
  assert.deepStrictEqual(leer('#swing/ETH'), { marco: 'swing', activo: 'ETH', vista: 'mesa' });
  assert.deepStrictEqual(leer('#largo/SOL'), { marco: 'largo', activo: 'SOL', vista: 'mesa' });
  assert.deepStrictEqual(leer('#scalp/BTC/status'), { marco: 'scalp', activo: 'BTC', vista: 'estado' });
  assert.deepStrictEqual(leer('#swing/SOL/status'), { marco: 'swing', activo: 'SOL', vista: 'estado' });
});

test('un hash vacio cae al defecto declarado, no a undefined', () => {
  assert.deepStrictEqual(leer(''), { marco: 'scalp', activo: 'BTC', vista: 'mesa' });
  assert.deepStrictEqual(leer('#'), { marco: 'scalp', activo: 'BTC', vista: 'mesa' });
  assert.deepStrictEqual(leer(undefined), { marco: 'scalp', activo: 'BTC', vista: 'mesa' });
});

test('LO QUE NO SE ENTIENDE NO SE ADIVINA: un marco o activo invalido cae al defecto', () => {
  // Si esto dejara pasar 'DOGE', `simbolo()` reventaria mas tarde y el fallo apareceria lejos
  // de su causa. Y un marco inventado se mandaria al backend, que contesta 422.
  assert.strictEqual(ctx.leerHash('#inventado/BTC').marco, 'scalp');
  assert.strictEqual(ctx.leerHash('#scalp/DOGE').activo, 'BTC');
  assert.strictEqual(ctx.leerHash('#scalp/BTC/inventado').vista, 'mesa');
});

test('el activo se normaliza a mayusculas: #scalp/btc es #scalp/BTC', () => {
  assert.strictEqual(ctx.leerHash('#scalp/btc').activo, 'BTC');
  assert.strictEqual(ctx.leerHash('#scalp/eth').activo, 'ETH');
});

test('las barras de sobra no rompen la lectura', () => {
  assert.deepStrictEqual(leer('#/scalp//BTC/'), { marco: 'scalp', activo: 'BTC', vista: 'mesa' });
});

test('todo hash leido produce un activo que `simbolo()` sabe resolver', () => {
  // La union de las dos piezas: el enrutador no puede producir un estado que la capa de datos
  // rechace. Es el par que producia S2 si alguien pasaba el nombre corto.
  ['#scalp/BTC', '#swing/eth', '#largo/SOL', '#basura', '', '#scalp/DOGE'].forEach((h) => {
    const e = ctx.leerHash(h);
    assert.doesNotThrow(() => ctx.simbolo(e.activo), `el hash ${h} produjo un activo irresoluble`);
    assert.match(ctx.simbolo(e.activo), /_PERP\.A$/);
  });
});

test('los nueve pares marco/activo del handoff se leen todos', () => {
  const vistos = new Set();
  MARCOS.forEach((m) => {
    ACTIVOS.forEach((a) => {
      const e = ctx.leerHash(`#${m}/${a}`);
      assert.strictEqual(e.marco, m);
      assert.strictEqual(e.activo, a);
      vistos.add(`${e.marco}/${e.activo}`);
    });
  });
  assert.strictEqual(vistos.size, 9);
});
