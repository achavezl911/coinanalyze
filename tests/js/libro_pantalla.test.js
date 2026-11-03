'use strict';
// EL LIBRO EN PANTALLA (campana 145, OF-4b) · lo que la pagina calcula (static/libro/libro-calculo.js y la parte pura de
// libro-escalera.js): el hash, el `cada` de la historia, lo que conoce cada venue, la suma por familia con cuantos la
// conocen, el estado de cada instante, la escala de color y la escalera con su acumulada.
const test = require('node:test');
const assert = require('node:assert');

// las familias, `cifra` e `isoZ` son las de /flujo (la pagina carga flujo-calculo.js delante)
Object.assign(global, require('../../static/flujo/flujo-calculo.js'));
const C = require('../../static/libro/libro-calculo.js');
Object.assign(global, C);
const E = require('../../static/libro/libro-escalera.js');

test('el hash: una vista = una URL, y lo que no se entiende cae al defecto', () => {
  const e = C.leeHashLibro('#ETH/okx_swap/1/30m/unidad=usd/hasta=2026-10-18T03:30:00Z/ver=90');
  assert.deepStrictEqual([e.activo, e.familia, e.paso, e.ventana, e.unidad, e.hasta, e.ver],
    ['ETH', 'okx_swap', '1', '30m', 'usd', '2026-10-18T03:30:00Z', 90]);
  assert.strictEqual(C.escribeHashLibro(e), '#ETH/okx_swap/1/30m/unidad=usd/hasta=2026-10-18T03:30:00Z/ver=90');
  const d = C.leeHashLibro('#DOGE/nada/3/7h/hasta=ayer');
  assert.deepStrictEqual([d.activo, d.familia, d.paso, d.ventana, d.hasta], ['BTC', 'perp', '10', '1h', null]);
  assert.strictEqual(C.escribeHashLibro(d), '#BTC/perp');
  assert.strictEqual(C.leeHashLibro('#SOL/spot/0.1').paso, '0.1'); // 5 x 0.02: multiplo del guardado
  assert.strictEqual(C.leeHashLibro('#SOL/spot/0.03').paso, '0.02'); // no lo es: el guardado
});

test('el cada: el menor multiplo de 5 s con el que la historia cabe en 2000 fotos', () => {
  assert.strictEqual(C.cadaPara(4, 3600), 10); // perpetuos 1 h: 1440 fotos
  assert.strictEqual(C.cadaPara(4, 4 * 3600), 30); // 4 h: 1920
  assert.strictEqual(C.cadaPara(1, 3600), 5); // un venue 1 h: 720
  assert.strictEqual(C.cadaPara(3, 3600), 10); // spot 1 h: 1080
  const c = C.cadaPara(4, 3 * 86400);
  assert.ok(c % 5 === 0 && 4 * Math.ceil((3 * 86400) / c) <= 2000 && 4 * Math.ceil((3 * 86400) / (c - 5)) > 2000);
});

test('lo que conoce un venue: de su compra mas profunda a su venta mas profunda; lo de fuera no se sabe', () => {
  const L = C.libroDe('x', '81005', '81012', { desde: '81000', cantidades: ['1', '0', '3'] },
                      { desde: '81010', cantidades: ['4', '5'] }, '10');
  assert.deepStrictEqual([L.lo, L.hi, L.kc, L.kv], [8098, 8102, 8100, 8101]);
  assert.deepStrictEqual(C.enNivel(L, 8100), [1, 0]); // por debajo de la mejor venta: su venta es cero CONOCIDO
  assert.deepStrictEqual(C.enNivel(L, 8101), [0, 4]); // por encima de la mejor compra: su compra es cero CONOCIDO
  assert.deepStrictEqual(C.enNivel(L, 8102), [0, 5]);
  assert.strictEqual(C.enNivel(L, 8097), null); // mas alla de lo que conoce: null, no cero
  // del aviso vivo (pares), y un lado vacio: ni el mejor nivel entero, se conoce desde el siguiente
  const V = C.libroDe('y', '81005', '81012', [['81000', '2']], [], '10');
  assert.deepStrictEqual([V.lo, V.hi], [8100, 8100]);
});

test('la familia suma solo lo que cada venue conoce, dice cuantos lo conocen y nunca suma un desconocido', () => {
  const a = C.libroDe('a', '81005', '81012', { desde: '81000', cantidades: ['1', '2', '3'] },
                      { desde: '81010', cantidades: ['4'] }, '10');
  const b = C.libroDe('b', '81001', '81015', { desde: '81000', cantidades: ['10'] },
                      { desde: '81010', cantidades: ['20', '30', '40'] }, '10');
  const s = C.sumaFamilia([a, b], 4);
  assert.deepStrictEqual([s.lo, s.hi, s.N], [8098, 8103, 4]);
  const n = (k) => s.n[k - s.lo];
  assert.deepStrictEqual([n(8098), n(8100), n(8101), n(8103)], [1, 2, 2, 1]); // 8098 y 8103: solo uno lo conoce
  assert.strictEqual(s.c[8098 - s.lo], 3); // solo a: 3, sin un «0» de b sumado
  assert.strictEqual(s.v[8103 - s.lo], 40);
  assert.deepStrictEqual([s.mejorCompra, s.mejorVenta], ['81005', '81012']);
  assert.strictEqual(C.sumaFamilia([], 4), null);
});

test('un instante sin foto es HUECO si su minuto ya se escribio, y «sin escribir aun» si no', () => {
  const t = Date.parse('2026-10-18T03:25:30Z');
  assert.strictEqual(C.estadoColumna(t, true, t), 'foto');
  assert.strictEqual(C.estadoColumna(t, false, Date.parse('2026-10-18T03:27:10Z')), 'hueco'); // 03:26 + 62 s < as_of
  assert.strictEqual(C.estadoColumna(t, false, Date.parse('2026-10-18T03:26:30Z')), 'pendiente');
  const d = { paso: '10', fotos: [{ ts: '2026-10-18T03:25:00.000Z', venue: 'okx_swap', compra: '81005', venta: '81012',
    compras: { desde: '81000', cantidades: ['1'] }, ventas: { desde: '81010', cantidades: ['2'] } }] };
  const cols = C.columnasDeFotos(d, ['okx_swap'], [Date.parse('2026-10-18T03:25:00Z'), Date.parse('2026-10-18T03:25:10Z')],
                                 Date.parse('2026-10-18T03:30:00Z'));
  assert.deepStrictEqual(cols.map((c) => c.estado), ['foto', 'hueco']); // el hueco no se rellena con la foto de antes
  assert.strictEqual(cols[1].suma, null);
});

test('la escala es el percentil: el puesto entre las celdas con cantidad de las columnas dadas; un cero es el fondo', () => {
  const col = (cs) => ({ estado: 'foto', suma: { lo: 0, c: Float64Array.from(cs), v: new Float64Array(cs.length),
                                                 n: Uint8Array.from(cs.map(() => 1)) } });
  const esc = C.escalaPercentil([col([1, 2, 3, 4]), col([0, 100])], 0, 1, '1', 'base');
  assert.strictEqual(esc.n, 5); // el cero conocido no cuenta
  assert.deepStrictEqual([esc.indice(1), esc.indice(3), esc.indice(100), esc.indice(0)], [0, 102, 204, -1]);
  assert.strictEqual(C.escalaPercentil([col([1, 2, 3, 4]), col([0, 100])], 0, 0, '1', 'base').indice(100), 255);
});

test('la escalera: las mejores marcadas, la acumulada desde el medio, «parcial» si no la conocen todos', () => {
  const a = C.libroDe('a', '81005', '81012', { desde: '81000', cantidades: ['1', '2', '3'] },
                      { desde: '81010', cantidades: ['4'] }, '10');
  const b = C.libroDe('b', '81001', '81015', { desde: '81000', cantidades: ['10'] },
                      { desde: '81010', cantidades: ['20', '30', '40'] }, '10');
  const f = C.escaleraFamilia(C.sumaFamilia([a, b], 2), '10', 'base');
  const k = (n) => f.find((x) => x.k === n);
  assert.ok(k(8100).mejor_compra && k(8101).mejor_venta);
  assert.deepStrictEqual([k(8100).acum_compra, k(8099).acum_compra, k(8098).acum_compra], [11, 13, 16]);
  assert.deepStrictEqual([k(8099).acum_parcial_compra, k(8100).acum_parcial_compra], [true, false]);
  assert.deepStrictEqual([k(8101).acum_venta, k(8102).acum_venta, k(8103).acum_venta], [24, 54, 94]);
  const usd = C.escaleraFamilia(C.sumaFamilia([a, b], 2), '10', 'usd');
  assert.strictEqual(usd.find((x) => x.k === 8100).compra, 11 * 81005); // al centro del nivel
});

test('un venue sin libro valido se dice con su motivo y no suma; uno con el aviso viejo es RANCIO', () => {
  const ahora = 1000000;
  const libro = { tipo: 'libro', venue: 'a', compra: '81005', venta: '81012', compras: [['81000', '1']],
                  ventas: [['81010', '4']], emitido_ms: 7 };
  const M = E.modeloEscalera(['a', 'b', 'c', 'd'], {
    a: { m: libro, llegadaMs: ahora - 1000 },
    b: { m: { tipo: 'sin_libro', venue: 'b', motivo: 'cruzado' }, llegadaMs: ahora },
    c: { m: Object.assign({}, libro, { venue: 'c' }), llegadaMs: ahora - 11000 },
  }, '10', 'base', ahora);
  assert.deepStrictEqual(M.venues.map((v) => v.estado), ['vivo', 'sin_libro', 'rancio', 'sin_dato']);
  assert.strictEqual(M.venues[1].motivo, 'cruzado');
  assert.deepStrictEqual(M.suma.venues, ['a']); // solo el vivo suma
  assert.deepStrictEqual([M.venues[0].conoce_compra, M.venues[0].conoce_venta], [1, 1]);
});

test('cada celda, al menos 2x2 pixeles de pantalla: lo que no cabe no se aleja, y los niveles van en banda', () => {
  const Mp = require('../../static/libro/libro-mapa.js');
  // el lienzo en 1920x1080 mide 1496x818 (CSS): el mapa, 1420x798, y caben 710 columnas y 399 niveles (al doble con DPR 2)
  assert.deepStrictEqual(Mp.cabenEn(1496, 818, 1), [710, 399]);
  assert.deepStrictEqual(Mp.cabenEn(1496, 818, 2), [1420, 798]);
  assert.strictEqual(Mp.verEfectivo(720, 720, 710), 710); // la vista del operador: 720 pedidas, 710 a la vista
  assert.strictEqual(Mp.verEfectivo(360, 360, 710), 360);
  assert.strictEqual(Mp.verEfectivo(720, 90, 710), 90);
  assert.strictEqual(Mp.verEfectivo(720, 3, 710), 10); // al menos 10
  assert.strictEqual(Mp.verEfectivo(720, 100.4, 710), 100); // un numero entero de columnas
  // los niveles: todos si caben; si no, los que caben alrededor de la mejor compra, dentro de lo conocido
  assert.deepStrictEqual(Mp.bandaDe(100, 150, 60, 120), [100, 150]);
  assert.deepStrictEqual(Mp.bandaDe(100, 400, 101, 250), [200, 300]);
  assert.deepStrictEqual(Mp.bandaDe(100, 400, 101, 120), [100, 200]);
  assert.deepStrictEqual(Mp.bandaDe(100, 400, 101, 390), [300, 400]);
});

// ------------------------------------------------------------------ la escalera profesional (campana 149, ronda A)
test('las barras: p95 de lo visible en UNA escala para los dos lados, y min(1, q/tope)', () => {
  assert.strictEqual(C.p95([]), null);
  assert.strictEqual(C.p95([5, 1, 3]), 5);
  const xs = Array.from({ length: 20 }, (_, i) => i + 1);
  assert.strictEqual(C.p95(xs), 19);
  const filas = [{ n: 2, compra: 0, venta: 4 }, { n: 1, compra: 2, venta: 0 }, { n: 0 }, { n: 2, compra: 6, venta: 8 }];
  const m = C.medidasVisibles(filas);
  assert.strictEqual(m.tope, 8);
  assert.strictEqual(m.media_compra, 4);
  assert.strictEqual(m.media_venta, 6);
  assert.strictEqual(C.fraccionBarra(4, 8), 0.5);
  assert.strictEqual(C.fraccionBarra(20, 8), 1);
  assert.strictEqual(C.fraccionBarra(3, null), 0);
});

test('una orden grande: >= 3x la media de su lado en lo visible, sin umbral absoluto', () => {
  assert.strictEqual(C.ESC_GRANDE_X, 3);
  assert.strictEqual(C.esGrande(3.1, 1), true);
  assert.strictEqual(C.esGrande(2.9, 1), false);
  assert.strictEqual(C.esGrande(3, 1), true);
  assert.strictEqual(C.esGrande(5, null), false);
});

test('los totales: la profundidad visible de cada lado, la proporcion y el spread', () => {
  const t = C.totalesVisibles([{ n: 1, compra: 3, venta: 1 }, { n: 0 }, { n: 2, compra: 1, venta: 3 }], '100.5', '101');
  assert.deepStrictEqual(t, { filas: 2, compra: 4, venta: 4, pct_compra: 50, spread: '0.5' });
  const v = C.totalesVisibles([{ n: 0 }], '10', '11');
  assert.deepStrictEqual(v, { filas: 0, compra: null, venta: null, pct_compra: null, spread: '1' });
});

function pag(asOf, ops, truncada) {
  return { as_of: asOf, truncada: !!truncada,
           operaciones: ops.map(([s, v, id, precio, base, agresor]) => ({ ts: '2026-11-03T01:00:' + s + 'Z', venue: v,
             id, precio, base, usd: base * precio, agresor })) };
}

test('lo reciente: la primera pagina no cuenta, se deduplica por venue e id, venta a @bid y compra a @ask', () => {
  let r = C.sumaReciente(C.recienteVacio(), pag('2026-11-03T01:00:10Z', [['05.000', 'a', 1, '100', 1, 'venta']]), '10');
  assert.strictEqual(r.niveles.size, 0);
  assert.strictEqual(r.ultima.k, 10);
  r = C.sumaReciente(r, pag('2026-11-03T01:00:11Z', [['10.500', 'a', 2, '104', 2, 'compra'],
    ['10.000', 'b', 1, '105', 0.5, 'venta'], ['05.000', 'a', 1, '100', 1, 'venta']]), '10');
  assert.deepStrictEqual(C.recienteEn(r, 10, 'base'), [0.5, 2]);
  assert.deepStrictEqual(C.recienteEn(r, 10, 'usd'), [52.5, 208]);
  // la misma pagina otra vez: nada nuevo
  const r2 = C.sumaReciente(r, pag('2026-11-03T01:00:12Z', [['10.500', 'a', 2, '104', 2, 'compra']]), '10');
  assert.deepStrictEqual(C.recienteEn(r2, 10, 'base'), [0.5, 2]);
  assert.strictEqual(r2.falta, null);
  // Limpiar: vacio, y lo ya visto no vuelve a contar
  const r3 = C.sumaReciente(C.limpiaReciente(r2), pag('2026-11-03T01:00:13Z', [['10.500', 'a', 2, '104', 2, 'compra']]), '10');
  assert.strictEqual(C.recienteEn(r3, 10, 'base'), null);
});

test('lo reciente: un nivel se reinicia si el precio se fue y vuelve tras mas de 2500 ms; no si vuelve antes', () => {
  let r = C.sumaReciente(C.recienteVacio(), pag('2026-11-03T01:00:01Z', []), '10');
  r = C.sumaReciente(r, pag('2026-11-03T01:00:20Z', [['10.000', 'a', 1, '100', 1, 'venta'],
    ['11.000', 'a', 2, '110', 1, 'venta'], ['12.000', 'a', 3, '101', 1, 'compra']]), '10');
  assert.deepStrictEqual(C.recienteEn(r, 10, 'base'), [1, 1]);
  r = C.sumaReciente(r, pag('2026-11-03T01:00:21Z', [['13.000', 'a', 4, '110', 1, 'venta'],
    ['15.600', 'a', 5, '100', 2, 'compra']]), '10');
  assert.deepStrictEqual(C.recienteEn(r, 10, 'base'), [0, 2]);
});

test('lo reciente: una pagina truncada que no solapa dice FALTAN y la marca queda hasta Limpiar', () => {
  let r = C.sumaReciente(C.recienteVacio(), pag('2026-11-03T01:00:01Z', [['01.000', 'a', 1, '100', 1, 'venta']]), '10');
  r = C.sumaReciente(r, pag('2026-11-03T01:00:30Z', [['30.000', 'a', 9, '100', 1, 'venta']], true), '10');
  assert.strictEqual(r.falta.motivo, 'truncada');
  r = C.sumaReciente(r, pag('2026-11-03T01:00:31Z', [['31.000', 'a', 10, '100', 1, 'venta'],
    ['30.000', 'a', 9, '100', 1, 'venta']], true), '10');
  assert.strictEqual(r.falta.motivo, 'truncada');
  assert.strictEqual(C.limpiaReciente(r).falta, null);
  // truncada pero solapa: no falta nada
  let s = C.sumaReciente(C.recienteVacio(), pag('2026-11-03T01:00:01Z', [['01.000', 'a', 1, '100', 1, 'venta']]), '10');
  s = C.sumaReciente(s, pag('2026-11-03T01:00:02Z', [['02.000', 'a', 2, '100', 1, 'venta'],
    ['01.000', 'a', 1, '100', 1, 'venta']], true), '10');
  assert.strictEqual(s.falta, null);
});

test('maximo y minimo de la sesion: los del perfil, ampliados por la cinta del mismo dia', () => {
  const r = C.sumaReciente(C.recienteVacio(), pag('2026-11-03T01:00:01Z', [['01.000', 'a', 1, '130', 1, 'venta']]), '10');
  const e = C.extremosSesion({ dia: '2026-11-03', niveles: [{ nivel: '100' }, { nivel: '120' }] }, r, '10');
  assert.deepStrictEqual(e, { lo: 10, hi: 13, dia: '2026-11-03', de_perfil: true });
  assert.deepStrictEqual(C.extremosSesion(null, r, '10'), { lo: 13, hi: 13, dia: '2026-11-03', de_perfil: false });
  assert.strictEqual(C.extremosSesion(null, C.recienteVacio(), '10'), null);
});
