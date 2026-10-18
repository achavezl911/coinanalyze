'use strict';
// EL FOOTPRINT · lo que la pagina calcula (static/flujo/flujo-calculo.js): el hash, las ventanas, el estado de cada
// vela, los desequilibrios EXACTOS y como se escribe una cifra. Se llaman las funciones de verdad.

const test = require('node:test');
const assert = require('node:assert');
const F = require('../../static/flujo/flujo-calculo.js');

const nv = (nivel, compra, venta) => ({ nivel, compra, venta });

test('el hash: por omision BTC/1m/perp con paso auto, y lo que no se entiende cae al defecto', () => {
  assert.deepStrictEqual(F.leeHash(''), {
    activo: 'BTC', marco: '1m', familia: 'perp', paso: 'auto', unidad: 'base', min: null, esconde: false,
    grande: null, hasta: null, ver: F.VER_DEFECTO,
    // OF-3 (campana 143): la sesion, las capas y el modo, apagados por omision (flujo_perfiles.test.js)
    sesion: 'dia', capas: [], compuesto: null, fijo: null, modo: 'footprint', sesiones: F.TPO_SESIONES,
    // OF-5a (campana 146): los indicadores por omision y el filtro de la cinta (flujo_indicadores.test.js)
    ind: F.INDICADORES_DEFECTO, cinta: null,
  });
  const e = F.leeHash('#eth/5m/deribit/0.5/unidad=usd/min=2/esconde/grande=40/hasta=2026-10-17T11:30Z/ver=20');
  assert.deepStrictEqual([e.activo, e.marco, e.familia, e.paso, e.unidad, e.min, e.esconde, e.grande, e.hasta, e.ver],
    ['ETH', '5m', 'deribit', '0.5', 'usd', '2', true, '40', '2026-10-17T11:30:00Z', 20]);
  const malo = F.leeHash('#DOGE/2m/todos/-1/unidad=eur/hasta=2026-10-17T11:31Z/ver=3');
  assert.deepStrictEqual([malo.activo, malo.marco, malo.familia, malo.paso, malo.unidad, malo.hasta, malo.ver],
    ['BTC', '1m', 'perp', 'auto', 'base', '2026-10-17T11:31:00Z', F.VER_DEFECTO]);
  // un `hasta` que no cae en borde de vela no se adivina
  assert.strictEqual(F.leeHash('#BTC/5m/perp/hasta=2026-10-17T11:31Z').hasta, null);
  // «todos sumados» no es una familia
  assert.strictEqual(F.leeHash('#BTC/1m/todos').familia, 'perp');
});

test('el hash va y vuelve: una vista = una URL', () => {
  ['#BTC/1m/perp', '#SOL/1h/spot/0.05/unidad=usd/min=10/esconde/grande=500/hasta=2026-10-17T11:00:00Z/ver=30']
    .forEach((h) => assert.strictEqual(F.escribeHash(F.leeHash(h)), h));
  assert.strictEqual(F.escribeHash(F.leeHash('#BTC/1m/perp/auto/ver=40')), '#BTC/1m/perp');
});

test('la historia acaba en la vela en curso, o en `hasta`, con las velas de su marco', () => {
  const ahora = Date.parse('2026-10-17T12:07:31Z');
  assert.deepStrictEqual(F.ventana(F.leeHash('#BTC/5m/perp'), ahora),
    { desde: '2026-10-16T16:10:00Z', hasta: '2026-10-17T12:10:00Z' });
  assert.deepStrictEqual(F.ventana(F.leeHash('#BTC/1d/perp/hasta=2026-10-17T00:00Z'), ahora),
    { desde: '2026-09-17T00:00:00Z', hasta: '2026-10-17T00:00:00Z' });
  // el latido pide SOLO lo que todavia puede cambiar: 90 s atras hasta la vela en curso
  assert.deepStrictEqual(F.ventanaViva('1m', ahora), { desde: '2026-10-17T12:06:00Z', hasta: '2026-10-17T12:08:00Z' });
  assert.deepStrictEqual(F.ventanaViva('15m', ahora), { desde: '2026-10-17T12:00:00Z', hasta: '2026-10-17T12:15:00Z' });
});

test('el estado de una vela: abierta, hueco, incompleta, vacia o completa; un hueco no es un cero', () => {
  const v = (cob, niveles) => ({ ts: '2026-10-17T11:13:00Z', cobertura: cob, niveles: niveles || [] });
  const cerrada = Date.parse('2026-10-17T11:20:00Z');
  const cob = (con, comp, esp) => ({ minutos_esperados: esp, minutos_con_fila: con, minutos_completos: comp,
                                     completa: comp === esp });
  // a los 60 s de cerrar todavia puede llegar: no se acusa
  assert.strictEqual(F.estadoVela(v(cob(0, 0, 4)), Date.parse('2026-10-17T11:15:00Z'), '1m').estado, 'abierta');
  assert.deepStrictEqual(F.estadoVela(v(cob(0, 0, 4)), cerrada, '1m'), { estado: 'hueco', faltan: 4, esperados: 4 });
  assert.deepStrictEqual(F.estadoVela(v(cob(4, 1, 4), [nv('1', '1', '0')]), cerrada, '1m'),
    { estado: 'incompleta', faltan: 3, esperados: 4 });
  assert.strictEqual(F.estadoVela(v(cob(1, 1, 1)), cerrada, '1m').estado, 'vacia');
  assert.strictEqual(F.estadoVela(v(cob(4, 4, 4), [nv('1', '1', '0')]), cerrada, '1m').estado, 'completa');
  // una vela de 5m que empezo a las 11:13 cierra a las 11:18 + 90 s
  assert.strictEqual(F.estadoVela(v(cob(20, 20, 20), [nv('1', '1', '0')]), Date.parse('2026-10-17T11:19:00Z'), '5m')
    .estado, 'abierta');
});

test('el desequilibrio diagonal es EXACTO: 0.3 >= 3 x 0.1 (en float seria falso)', () => {
  const d = F.desequilibrios([nv('100', '0', '0.1'), nv('101', '0.3', '0')], '1');
  assert.strictEqual(0.3 >= 3 * 0.1, false);
  assert.deepStrictEqual(d[1], { dc: true, dv: false, ac: false, av: false });
});

test('el desequilibrio: el vecino de fuera de la vela no se compara; dentro, un nivel sin celda vale 0', () => {
  // 100 es el nivel mas bajo: su compra no se compara con nada (debajo no hay vela)
  let d = F.desequilibrios([nv('100', '9', '0'), nv('101', '1', '1')], '1');
  assert.strictEqual(d[0].dc, false);
  // 102 no tiene celda (dentro de la vela): la compra de 103 se compara con 0
  d = F.desequilibrios([nv('100', '1', '1'), nv('101', '1', '1'), nv('103', '2', '0')], '1');
  assert.strictEqual(d[2].dc, true);
});

test('el desequilibrio pide la media por nivel de su vela: un nivel fino no marca', () => {
  // media por nivel = (1 + 0.1 + 10 + 0) / 3 = 3.7: el 1 de 101 no llega aunque sea 10 veces el 0.1 de debajo
  const d = F.desequilibrios([nv('100', '0', '0.1'), nv('101', '1', '0'), nv('102', '10', '0')], '1');
  assert.deepStrictEqual(d.map((x) => x.dc), [false, false, true]);
});

test('el desequilibrio vendedor mira la compra del nivel de ENCIMA', () => {
  const d = F.desequilibrios([nv('100', '0', '9'), nv('101', '3', '0')], '1');
  assert.strictEqual(d[0].dv, true); // 9 >= 3 x 3 y 9 >= la media (6)
  assert.strictEqual(d[1].dv, false); // el de arriba del todo no se compara
});

test('apilado: tres seguidos del mismo lado; dos no; un hueco de precio lo corta', () => {
  const sube = (n) => nv(String(n), '10', '0');
  let d = F.desequilibrios([nv('99', '0', '0.1'), sube(100), sube(101), sube(102), nv('103', '0', '1')], '1');
  assert.deepStrictEqual(d.map((x) => x.ac), [false, true, true, true, false]);
  d = F.desequilibrios([nv('99', '0', '0.1'), sube(100), sube(101), nv('102', '0', '1')], '1');
  assert.deepStrictEqual(d.map((x) => x.ac), [false, false, false, false]);
  d = F.desequilibrios([nv('99', '0', '1'), sube(100), sube(101), sube(103), sube(104)], '1');
  assert.ok(d.every((x) => !x.ac));
});

test('una cifra se escribe compacta y lo que no es cero nunca sale «0»', () => {
  assert.deepStrictEqual(['0', '0.00043', '0.523', '1.234', '12.34', '123.4', '1234.5', '12345', '2500000'].map(F.cifra),
    ['0', '0.00043', '0.52', '1.23', '12.3', '123', '1.23K', '12.3K', '2.50M']);
  assert.strictEqual(F.cifra('-0.711'), '-0.71');
});

test('el filtro por tamano atenua o esconde lo pequeno y resalta lo grande', () => {
  assert.strictEqual(F.filtro('0.5', { min: '1', esconde: false, grande: null }), 'atenuada');
  assert.strictEqual(F.filtro('0.5', { min: '1', esconde: true, grande: null }), 'escondida');
  assert.strictEqual(F.filtro('50', { min: '1', esconde: false, grande: '40' }), 'grande');
  assert.strictEqual(F.filtro('5', { min: null, esconde: false, grande: null }), 'normal');
});

test('las familias nunca se mezclan: ningun venue esta en dos', () => {
  const todos = Object.values(F.FAMILIAS).flatMap((f) => f.venues);
  assert.strictEqual(new Set(todos).size, todos.length);
  assert.strictEqual(todos.length, 9);
});
