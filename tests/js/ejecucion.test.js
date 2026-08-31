'use strict';
// El estado visual de la ejecucion sale de la EVALUACION, no de comparar bps contra un 5.

const fs = require('node:fs');
const test = require('node:test');
const assert = require('node:assert/strict');
const { cargarApp, APP_JS } = require('./harness');

const app = cargarApp();
const FUENTE = fs.readFileSync(APP_JS, 'utf8');

// Sin plan de operacion no hay veredicto: es lo que devuelve el backend.
const SIN_EVALUAR = {
  profile: 'swing', profile_label: 'Swing varios días', status: 'SIN EVALUAR',
  verdict: 'SIN EVALUAR', total_cost_bps: null, spread_warning: null,
  cost_to_target_band: null, cost_to_risk_band: null,
  missing_inputs: ['entrada', 'objetivo', 'stop', 'comisión', 'tamaño'],
};
const evaluado = (target, risk, aviso = null) => ({
  profile: 'intradia', profile_label: 'Intradía ≤ 4 h', status: 'EVALUADO',
  verdict: 'x', total_cost_bps: 6, cost_to_target: 0.12, cost_to_risk: 0.2,
  cost_to_target_band: target, cost_to_risk_band: risk, spread_warning: aviso,
});

// ---------------- el literal 5 desaparecio de la capa visual ----------------

test('no queda ninguna comparacion visual del spread contra un 5', () => {
  for (const patron of [
    "(asNumber(scalp.spread_bps) || 0) > 5",
    "(asNumber(r.spread_bps) || 0) > 5",
    "(f.slippage_bps || 0) > 5",
    "spread_bps) > 5",
  ]) {
    assert.ok(!FUENTE.includes(patron), `app.js conserva \`${patron}\``);
  }
});

test('6 bps de spread no son automaticamente negativos', () => {
  // La fila del spread se pinta siempre en neutro: el numero informa, no clasifica.
  const bloque = FUENTE.slice(FUENTE.indexOf('function renderExecutionLevels'), FUENTE.indexOf('function renderDeltaMatrix'));
  assert.ok(bloque.includes("rowDL(levels, 'Spread'"), 'no se encontro la fila del spread');
  const fila = bloque.slice(bloque.indexOf("rowDL(levels, 'Spread'"));
  const cierre = fila.slice(0, fila.indexOf(');') + 2);
  assert.ok(cierre.includes("'neutral'"), 'el spread bruto deberia ir en neutro');
  assert.ok(!/>\s*5\b/.test(cierre), 'sigue habiendo un umbral literal en la fila del spread');
});

// ---------------- el color viene de la evaluacion ----------------

test('el veredicto se colorea con las bandas de coste, no con el spread', () => {
  assert.equal(app.executionClass(evaluado('aceptable', 'aceptable')), 'positive');
  assert.equal(app.executionClass(evaluado('ajustado', 'aceptable')), 'neutral');
  assert.equal(app.executionClass(evaluado('aceptable', 'prohibitivo')), 'negative');
  // Manda la PEOR de las dos lecturas.
  assert.equal(app.executionClass(evaluado('prohibitivo', 'aceptable')), 'negative');
});

test('un spread enorme con coste aceptable NO pinta negativo', () => {
  // 40 bps de spread, pero el objetivo es tan amplio que el coste sigue siendo aceptable.
  const e = evaluado('aceptable', 'aceptable', 'spread 40.00 bps por encima del aviso');
  assert.equal(app.executionClass(e), 'positive');
});

test('SIN EVALUAR es neutro: no saber no es lo mismo que saber que sale caro', () => {
  assert.equal(app.executionClass(SIN_EVALUAR), 'neutral');
  assert.equal(app.executionClass(null), 'neutral');
  assert.equal(app.executionClass(undefined), 'neutral');
  assert.equal(app.executionClass({}), 'neutral');
});

test('10 bps en swing no se etiquetan como problema intradia', () => {
  // El backend no emite aviso a 10 bps en swing; la capa visual no puede inventarlo.
  const e = { ...SIN_EVALUAR, spread_warning: null };
  assert.equal(app.spreadWarning(e), null);
  assert.equal(app.executionClass(e), 'neutral');
  const texto = JSON.stringify(e);
  assert.ok(!/intrad/i.test(texto), 'una tesis swing no puede recibir vocabulario intradia');
});

test('el aviso de spread se expone aparte y nunca como veredicto', () => {
  const aviso = 'spread 12.00 bps por encima del aviso de 5 bps para perfil intradia';
  const e = evaluado('aceptable', 'aceptable', aviso);
  assert.equal(app.spreadWarning(e), aviso);
  // Existe el aviso, pero el color sigue saliendo de las bandas.
  assert.equal(app.executionClass(e), 'positive');
});

// ---------------- null no es 0 ----------------

test('un spread null no se interpreta como 0 ni se colorea', () => {
  assert.equal(app.asNumber(null), null);
  assert.equal(app.nd(null, v => `${v} bps`), 'N/D');
  assert.equal(app.nd(undefined, v => `${v} bps`), 'N/D');
  // ...y un 0 medido sigue siendo 0.
  assert.equal(app.nd(0, v => `${v} bps`), '0 bps');
});

test('el aviso de spread no aporta direccion', () => {
  const e = evaluado('aceptable', 'aceptable', 'spread alto');
  for (const clase of ['positive', 'negative']) {
    assert.notEqual(app.spreadWarning(e), clase);
  }
  assert.equal(typeof app.spreadWarning(e), 'string');
});

// ---------------- un coste al que le faltan patas no se pinta en verde ----------------
//
// El backend suma SOLO las patas medidas (scalp_logic.py:4796-4812) y publica cuales faltan
// en cost_components_missing; de ese total parcial salen cost_to_target y cost_to_risk, o
// sea el veredicto. Hasta el 2026-08-31 esta capa no leia ese campo: pintaba "Coste ida y
// vuelta" a secas y coloreaba en VERDE un 'aceptable' calculado sobre media medicion.
// MEDIDO contra 140, mismo plan y mismo mercado: sin slippage 8.013 bps y 'aceptable'; con
// slippage 10, 28.013 bps y 'prohibitivo'. Es la misma regla que ya gobierna SIN EVALUAR,
// un paso mas alla: no saber si sale cara no es lo mismo que saber que sale barata.

const conPatasAusentes = (target, risk, ausentes) => ({
  ...evaluado(target, risk), cost_components_missing: ausentes,
});

test('un aceptable con patas de coste ausentes NO se pinta en verde', () => {
  assert.equal(app.executionClass(conPatasAusentes('aceptable', 'aceptable', ['slippage_bps'])), 'neutral');
  assert.equal(
    app.executionClass(conPatasAusentes('aceptable', 'aceptable', ['slippage_bps', 'funding_bps'])),
    'neutral',
  );
});

test('CONTROL POSITIVO: con las cuatro patas medidas, el aceptable SIGUE en verde', () => {
  // Sin esto, la regla de arriba se podria satisfacer matando el verde para siempre, que es
  // un check que no distingue nada.
  assert.equal(app.executionClass(conPatasAusentes('aceptable', 'aceptable', [])), 'positive');
  assert.equal(app.executionClass(evaluado('aceptable', 'aceptable')), 'positive');
});

test('la degradacion solo toca a la clase que AFIRMA algo bueno', () => {
  // prohibitivo y ajustado ya no afirman nada bueno: una pata ausente solo puede empeorarlos,
  // asi que su color no cambia y el mensaje no se diluye.
  assert.equal(app.executionClass(conPatasAusentes('prohibitivo', 'aceptable', ['slippage_bps'])), 'negative');
  assert.equal(app.executionClass(conPatasAusentes('ajustado', 'aceptable', ['slippage_bps'])), 'neutral');
});

test('renderExecutionRows CONSULTA cost_components_missing', () => {
  // De texto fuente por necesidad: lo que la pantalla pinta no deja huella en ninguna
  // respuesta de la API. Mismo motivo que el brazo C de K76.
  const i = FUENTE.indexOf('function renderExecutionRows');
  assert.ok(i >= 0, 'no se encontro renderExecutionRows en app.js');
  const cuerpo = FUENTE.slice(i, FUENTE.indexOf('\n}', i));
  assert.ok(
    cuerpo.includes('cost_components_missing'),
    'renderExecutionRows volvio a pintar el coste sin mirar que patas faltan',
  );
});
