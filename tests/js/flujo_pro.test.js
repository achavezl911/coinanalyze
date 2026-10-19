'use strict';
// EL FOOTPRINT PROFESIONAL (campana 148, OF-6a) · lo que la pagina calcula para escribir y colorear: E-04 (la
// abreviatura), F-04 (los 20 pasos de color y su p98), F-07 (el POC empatado), F-10 (el CVD de sesion y las filas de
// resumen) y las claves nuevas del hash. Se llaman las funciones de verdad (static/flujo/flujo-calculo.js).

const test = require('node:test');
const assert = require('node:assert');
const F = require('../../static/flujo/flujo-calculo.js');

test('E-04: 999 -> «999», 10000 -> «10.0K», 1234567 -> «1.2M»; y lo que no es cero nunca sale «0»', () => {
  assert.deepStrictEqual([999, 10000, 1234567].map((x) => F.cifraE04(x, 0)), ['999', '10.0K', '1.2M']);
  // por debajo de 1 000, los decimales del activo, uno menos por cada cifra entera de mas (BTC 3)
  assert.deepStrictEqual(['0.1234', '1.2345', '12.345', '123.45', '999.96', '0.0004'].map((x) => F.cifraE04(x, 3)),
    ['0.123', '1.234', '12.35', '123.5', '1.0K', '0.0004']);
  assert.deepStrictEqual([F.cifraE04('-1234.5', 2), F.cifraE04('999999', 0), F.cifraE04('0', 3)], ['-1.2K', '1.0M', '0']);
  assert.deepStrictEqual([F.decimalesDe('BTC', 'base'), F.decimalesDe('ETH', 'base'), F.decimalesDe('SOL', 'base'),
                          F.decimalesDe('BTC', 'usd')], [3, 2, 1, 0]);
});

test('F-04: la referencia es el p98 de lo no nulo; 20 pasos; lo que pasa del corte satura', () => {
  const xs = Array.from({ length: 100 }, (_, i) => i + 1); // 1..100: el p98 es 98
  assert.strictEqual(F.referencia(xs.concat([0, -0])), 98);
  assert.strictEqual(F.referencia([-5, 2]), 5);
  assert.strictEqual(F.pasoColor(98, 98), 19);
  assert.strictEqual(F.pasoColor(1000, 98), 19); // 10 veces el corte: el mismo color maximo
  assert.strictEqual(F.pasoColor(-49, 98), 10);
  assert.strictEqual(F.pasoColor(0, 98), -1);
  assert.strictEqual(F.PASOS_COLOR, 20);
});

test('F-07: el POC con empate son todos los empatados (en exacto: 0.3 y 0.1 + 0.2 no se confunden)', () => {
  const l = (nivel, total) => ({ nivel, total });
  assert.deepStrictEqual(F.pocsDe([l('100', '2.5'), l('101', '7'), l('102', '7.0'), l('103', '1')]), ['101', '102']);
  assert.deepStrictEqual(F.pocsDe([l('100', '0.3'), l('101', '0.30000000000000004')]), ['101']);
});

test('F-10: el CVD de sesion, exacto, desde su inicio; con su arranque si empezo antes; tras un hueco, incompleto', () => {
  const ses = F.leeSesion('dia');
  const v = (ts, delta, estado) => ({ ts, delta, estado: estado || 'completa' });
  // la primera vela es de las 23:58: su sesion empezo antes y su arranque (de /sesiones) es -1.5, incompleto
  const velas = [v('2026-10-17T23:58:00Z', '0.1'), v('2026-10-17T23:59:00Z', '0.2'), v('2026-10-18T00:00:00Z', '0.3'),
                 v('2026-10-18T00:01:00Z', '0', 'hueco'), v('2026-10-18T00:02:00Z', '1')];
  const ini = Date.parse('2026-10-17T00:00:00Z');
  const c = F.cvdSesion(velas, ses, { [ini]: { delta: '-1.5', estado: 'incompleta' } });
  assert.deepStrictEqual(c.map((x) => x.valor), ['-1.4', '-1.2', '0.3', null, '1.3']);
  assert.deepStrictEqual(c.map((x) => x.estado), ['incompleta', 'incompleta', 'completa', null, 'incompleta']);
  // sin arranque (la peticion fallo), la sesion que empezo antes no se escribe; la siguiente si, desde 0
  assert.deepStrictEqual(F.cvdSesion(velas, ses, {}).map((x) => x.valor), [null, null, '0.3', null, '1.3']);
  // un arranque sin una sola fila (la sesion entera sin escuchar hasta ahi): desde 0, incompleto
  assert.deepStrictEqual(F.cvdSesion(velas.slice(0, 2), ses, { [ini]: { delta: '0', estado: 'hueco' } })
    .map((x) => [x.valor, x.estado]), [['0.1', 'incompleta'], ['0.3', 'incompleta']]);
  // una plantilla de menos de 24 h: las 07:59 son de Asia (empezo a las 00:00); las 08:00, de ninguna sesion
  const asia = F.leeSesion('asia');
  assert.deepStrictEqual(F.cvdSesion([v('2026-10-18T07:59:00Z', '1'), v('2026-10-18T08:00:00Z', '1')], asia, {})
    .map((x) => x.sesion), [Date.parse('2026-10-18T00:00:00Z'), null]);
  assert.deepStrictEqual(F.resumenVela({ estado: 'completa', total: '4', delta: '-1', operaciones: 7 }, { valor: '2' }),
    { vol: '4', delta: '-1', deltap: '-25', cvd: '2', ops: '7' });
  assert.strictEqual(F.resumenVela({ estado: 'hueco', total: '0', delta: '0', operaciones: 0 }, null).vol, null);
});

test('el hash de OF-6a: la celda, el color, las filas y los dos ejes van y vuelven; lo que no se entiende, fuera', () => {
  const h = '#ETH/5m/perp/celda=delta/color=volumen/ref=sesion/numeros=no/filas=vol,cvd/rueda=desplaza/x=12.5/y=4012.35/fila=18';
  const e = F.leeHash(h);
  assert.deepStrictEqual([e.celda, e.color, e.ref, e.numeros, e.filas, e.rueda, e.x, e.y, e.fila],
    ['delta', 'volumen', 'sesion', false, ['vol', 'cvd'], 'desplaza', 12.5, '4012.35', 18]);
  assert.strictEqual(F.escribeHash(e), h);
  const malo = F.leeHash('#BTC/1m/perp/celda=nada/color=rojo/ref=dia/filas=ninguna/x=-3/y=abc/fila=2');
  assert.deepStrictEqual([malo.celda, malo.color, malo.ref, malo.filas, malo.x, malo.y, malo.fila],
    ['bidask', 'delta', 'vela', [], null, null, null]);
  assert.strictEqual(F.escribeHash(malo), '#BTC/1m/perp/filas=ninguna');
});
