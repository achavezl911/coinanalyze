'use strict';
// IND R1 (U-05 + fable-f12c I7 e I1) · los indicadores de /flujo en vivo: se vuelven a pedir con su PROPIO reloj
// (IND_REFRESCO_S) y no solo cuando nace una vela; lo pintado de otro activo o marco se tira al pedir el nuevo; y cada
// respuesta aceptada guarda cuando llego (IND.leido). Se cargan las tres hojas de verdad (flujo-calculo.js,
// flujo-indicadores.js, flujo-app.js) en un contexto vm, con el reloj y `pedir` de mentira, y se llama a late().

const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const FLUJO = path.join(__dirname, '..', '..', 'static', 'flujo');
const T0 = 1e6; // el reloj de la pagina (performance.now) al pedir la vista
const VELA = '2026-11-23T10:00:00Z';
const RUTA_IND = '/api/orderflow/indicadores';

function pagina(hash) {
  const sb = { console, setImmediate, document: { hidden: false } };
  sb.window = sb;
  sb.location = { hash };
  sb.T = T0;
  sb.performance = { now: () => sb.T };
  sb.requestAnimationFrame = (f) => f();
  vm.createContext(sb);
  ['flujo-calculo.js', 'flujo-indicadores.js', 'flujo-app.js'].forEach((f) =>
    vm.runInContext(fs.readFileSync(path.join(FLUJO, f), 'utf8'), sb, { filename: f }));
  vm.runInContext(`
    var PEDIDAS = [];
    var RESPONDE = null;
    pedir = (ruta, q) => { PEDIDAS.push({ ruta, q, t: T }); return RESPONDE(ruta, q); };
    pintaEstado = () => {};
    refrescaCapas = () => {};
    cargaVistaCinta = () => {};
    LIENZO = { actualiza() {}, pide() {} };
  `, sb);
  return sb;
}

const corre = (sb, js) => vm.runInContext(js, sb);
const sobre = (ruta, datos) => ({ ok: true, http: 200, ruta, ms: 1, datos });
const espera = () => new Promise((r) => setImmediate(r));

function vela(asOf) {
  return { ts: VELA, niveles: [], delta: '0', estado: 'abierta', as_of: asOf };
}

test('I7n: marco 1h, 119 latidos de 5 s dentro de la vela -> 9 peticiones de indicadores, no 0', async () => {
  const sb = pagina('#BTC/1h/perp/ind=delta,oi,liq');
  const base = Date.parse(VELA);
  corre(sb, `MODELO = { velas: [], paso: '1' }; ULTIMA = { asOfMs: ${base}, t: T };`);
  sb.MODELO_VELAS = [vela(VELA)];
  corre(sb, 'MODELO.velas = MODELO_VELAS.map((v) => Object.assign({}, v));');
  sb.RESPONDE = async (ruta) => {
    if (ruta === RUTA_IND) return sobre(ruta, { as_of: new Date(base + sb.T - T0).toISOString(), series: {} });
    const asOf = new Date(base + sb.T - T0).toISOString();
    return sobre(ruta, { as_of: asOf, velas: [vela(asOf)] });
  };
  corre(sb, 'cargaVistaIndicadores(CARGA);'); // la peticion inicial de la vista
  await espera();
  const inicial = sb.PEDIDAS.filter((p) => p.ruta === RUTA_IND).length;
  assert.strictEqual(inicial, 1);
  const leidos = [];
  for (let k = 1; k <= 119; k += 1) {
    sb.T = T0 + k * 5000;
    await corre(sb, 'late()');
    await espera();
    leidos.push(corre(sb, 'IND.leido'));
  }
  assert.strictEqual(corre(sb, 'MODELO.velas.length'), 1, 'los 119 latidos caen dentro de la misma vela de 1h');
  const ind = sb.PEDIDAS.filter((p) => p.ruta === RUTA_IND);
  assert.strictEqual(ind.length - inicial, 9, 'con main: 0 despues de la inicial (la edad llegaba al marco)');
  assert.deepStrictEqual([...ind.slice(1)].map((p) => (p.t - T0) / 1000), [60, 120, 180, 240, 300, 360, 420, 480, 540]);
  assert.ok(ind.every((p) => p.q.symbol === 'BTC' && p.q.marco === '1h'));
  // cada respuesta aceptada lleva su llegada: la edad nunca pasa del refresco
  assert.ok(leidos.every((t, k) => typeof t === 'number' && T0 + (k + 1) * 5000 - t < 60000), String(leidos.slice(0, 3)));
});

test('I1: pedida ETH y en vuelo, lo pintado ya no es lo de BTC; y la respuesta vieja no entra', async () => {
  const sb = pagina('#BTC/1h/perp/ind=oi');
  const w = { desde: '2026-11-13T00:00:00Z', hasta: '2026-11-23T00:00:00Z' };
  const colgadas = [];
  sb.RESPONDE = (ruta, q) => new Promise((r) => colgadas.push(() => r(sobre(ruta, { symbol: q.symbol, marco: q.marco }))));
  sb.W = w;
  const btc = corre(sb, 'cargaIndicadores(VISTA, W)');
  colgadas.shift()();
  await btc;
  assert.deepStrictEqual(corre(sb, 'IND.datos'), { symbol: 'BTC', marco: '1h' });
  sb.T += 1500;
  const leidoBtc = corre(sb, 'IND.leido');
  // otra peticion de BTC queda colgada; el operador cambia a ETH
  const btcTarde = corre(sb, 'cargaIndicadores(VISTA, W)');
  corre(sb, "VISTA = leeHash('#ETH/1h/perp/ind=oi')");
  const eth = corre(sb, 'cargaIndicadores(VISTA, W)');
  assert.strictEqual(corre(sb, 'IND.datos'), null, 'con main: sigue el dato de BTC mientras ETH esta en vuelo');
  assert.strictEqual(leidoBtc, T0, 'la llegada de BTC, en el reloj de la pagina');
  assert.strictEqual(corre(sb, 'IND.leido'), null);
  colgadas[1]();
  await eth;
  colgadas[0]();
  await btcTarde;
  assert.deepStrictEqual(corre(sb, 'IND.datos'), { symbol: 'ETH', marco: '1h' }, 'la respuesta vieja de BTC no entra');
  assert.strictEqual(corre(sb, 'IND.leido'), T0 + 1500);
  // y el marco cuenta como otra vista
  corre(sb, "VISTA = leeHash('#ETH/4h/perp/ind=oi')");
  corre(sb, 'cargaIndicadores(VISTA, W)');
  assert.strictEqual(corre(sb, 'IND.datos'), null, 'el dato de 1h no se pinta en 4h');
  colgadas[2]();
});
