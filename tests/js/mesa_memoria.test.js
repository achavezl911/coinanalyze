'use strict';
// LA PALABRA GRANDE Y LA DEL INSTANTE (campana 138). La cabecera de DECIDE pinta la palabra que el
// sistema SOSTIENE con SU edad, y la del instante pequena y rotulada, con sus cambios. Las dos frases
// llegan servidas: la pantalla no calcula ninguna edad ni cuenta ningun cambio (A86).

const test = require('node:test');
const assert = require('node:assert');
const { cargaMesa } = require('./harness-mesa.js');

function nodos(d) {
  const id = (x) => d.getElementById(x);
  return {
    caja: id('decide'), sesgo: id('decide-sesgo'), sello: id('decide-sello'), motivo: id('decide-motivo'),
    edadPalabra: id('decide-edad-palabra'), instante: id('decide-instante'), campos: id('decide-campos'),
    edad: id('decide-edad'), escalones: id('conf-escalones'), confPalabra: id('conf-palabra'),
    confFila: id('conf-fila'), confInstante: id('conf-instante'),
    confClave: id('conf-clave'), dcRelleno: id('dc-relleno'), dcValor: id('dc-valor'), dcClave: id('dc-clave'),
  };
}

const campo = (value, source_key) => ({ value, source_key, status: 'ok' });
// un campo de la evaluacion del INSTANTE, con el rotulo que la ruta le sirve (remate R1)
const delInstante = (value, source_key) => ({ ...campo(value, source_key), rotulo_instante: 'del instante' });
const MEMORIA = {
  regla: { ventana_s: 300, umbral: 0.6, minimo: 10, frescura_s: 60 },
  edad: { desde: '2026-10-14T21:12:05+00:00', s: 1043.2, al_menos: false,
          frase: 'desde las 21:12:05Z (17 min)', source_key: 'mesa.decide.memoria.edad' },
};
const INSTANTE = { value: 'NO OPERAR', source_key: 'operator_read.state', status: 'ok', motivo: null,
                   cambios_en_ventana: 9, frase: '9 cambios en 5 min', rotulo_instante: 'instante' };

// un sobre v3 de marco scalp: la grande LONG sostenida, el instante NO OPERAR
function sobre() {
  return {
    ok: true,
    datos: {
      schema_version: 'mesa.decide.v3', symbol: 'BTCUSDT_PERP.A', frame: 'scalp', max_age_s: 120,
      no_evaluable_under: 70,
      age: { snapshot_lag_seconds: campo(36.6, 'data_confidence.snapshot_lag_seconds'), stale: false },
      decide: {
        bias: { value: 'LONG', source_key: 'mesa.decide.memoria', status: 'ok',
                motivo: 'LONG en 15 de 22 evaluaciones de 5 min (umbral 60 %)' },
        instante: INSTANTE,
        memoria: MEMORIA,
        evaluable: { value: true, source_key: 'data_confidence.quality_score', status: 'ok', threshold: 70 },
        confidence: delInstante('media', 'operator_read.confidence'),
        state: delInstante('No Trade', 'operator_read.state'),
        reason: delInstante('ΔFut1m 103516, book ok/L5 0.33', 'scalp.reason'),
        edge: delInstante(11.0, 'operator_read.edge'),
        evidence: delInstante(100, 'scalp.evidence_coverage_pct'),
        evidence_balance: delInstante('Short', 'operator_read.bias'),
        zone_decision: campo('ESPERAR: zona en disputa', 'price_barriers.decision'),
        confirms: [campo('Rechazo confirmado sobre 100.99', 'price_barriers.long_case.rejection')],
        structural_horizon: campo('1h', 'structure_detail.horizons.1h'),
        data_confidence: campo(100, 'data_confidence.quality_score'),
      },
    },
  };
}

// Las marcas de instante QUE SON DE ESTA CELDA: las de dentro, sin bajar a otra celda anidada.
function marcasDe(celda) {
  const fuera = [];
  const anda = (x) => x.children.forEach((c) => {
    if (c.getAttribute('data-campo') !== null) return;
    if (c.getAttribute('data-rotulo-instante') !== null) fuera.push(c.textContent);
    anda(c);
  });
  anda(celda);
  return fuera;
}

test('la palabra grande es la servida en bias, con la clave de la memoria y su motivo', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  ctx.pintarDecide(sobre(), n);
  assert.strictEqual(n.sesgo.textContent, 'LONG');
  assert.strictEqual(n.sesgo.getAttribute('data-source-key'), 'mesa.decide.memoria');
  assert.match(n.motivo.textContent, /^LONG en 15 de 22 evaluaciones/);
});

test('la del instante va aparte, rotulada, con su color, su clave y su frase servida', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  ctx.pintarDecide(sobre(), n);
  assert.strictEqual(n.instante.getAttribute('data-campo'), 'instante');
  assert.strictEqual(n.instante.getAttribute('data-source-key'), 'operator_read.state');
  const valor = n.instante.children.find((c) => c.getAttribute('data-valor') !== undefined && c.getAttribute('data-valor') !== null);
  assert.strictEqual(valor.getAttribute('data-valor'), 'NO OPERAR');
  assert.ok(valor.className.includes('sesgo-SIN-LADO'));
  assert.deepStrictEqual(marcasDe(n.instante), ['instante'], 'su rotulo, el que sirve la ruta');
  assert.strictEqual(n.instante.textContent, 'instanteNO OPERAR · 9 cambios en 5 min');
  // y NO en el sitio de la grande
  assert.notStrictEqual(n.sesgo.textContent, 'NO OPERAR');
});

test('la edad que se pinta es la de la PALABRA, no la de la instantanea', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  ctx.pintarDecide(sobre(), n);
  assert.strictEqual(n.edadPalabra.getAttribute('data-campo'), 'memoria.edad');
  assert.strictEqual(n.edadPalabra.textContent, 'desde las 21:12:05Z (17 min)');
  assert.strictEqual(n.edadPalabra.getAttribute('data-source-key'), 'mesa.decide.memoria.edad');
  assert.strictEqual(n.edadPalabra.getAttribute('data-valor'), n.edadPalabra.textContent);
  assert.ok(!n.edadPalabra.textContent.includes('36'));
});

test('si la ruta falla, ni edad de la palabra ni palabra del instante', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  ctx.pintarDecide(sobre(), n);
  ctx.pintarDecide({ ok: false, motivo: 'HTTP 502' }, n);
  assert.strictEqual(n.edadPalabra.textContent, '');
  assert.strictEqual(n.instante.textContent, '');
  assert.strictEqual(n.instante.getAttribute('data-campo'), null);
});

test('en SWING la cabecera no pinta memoria: viaja con la lectura del scalp y se pinta en su tarjeta', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  const s = sobre();
  s.datos.frame = 'swing';
  s.datos.decide = {
    bias: { value: 'NO EVALUABLE', source_key: 'mesa.decide.frame', status: 'ok', motivo: 'la lectura del operador es del SCALP, no de SWING' },
    evaluable: { value: true, source_key: 'data_confidence.quality_score', status: 'ok', threshold: 70 },
  };
  s.datos.lectura_scalp = { de_marco: 'scalp', bias: sobre().datos.decide.bias, instante: INSTANTE, memoria: MEMORIA };
  ctx.pintarDecide(s, n);
  assert.strictEqual(n.edadPalabra.textContent, '');
  assert.strictEqual(n.instante.textContent, '');
  const tarjeta = documento.getElementById('lectura-scalp-campos');
  const marcados = tarjeta.querySelectorAll('[data-campo]').map((c) => c.getAttribute('data-campo'));
  assert.ok(marcados.includes('scalp.memoria.edad') && marcados.includes('scalp.instante'), marcados.join(','));
});

test('remate R1 · lo que sale de la evaluacion del INSTANTE lleva su marca servida; lo de la grande y lo de las dos, no', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  ctx.pintarDecide(sobre(), n);
  const celdas = {};
  documento.getElementById('decide-campos').querySelectorAll('[data-campo]')
    .forEach((c) => { celdas[c.getAttribute('data-campo')] = marcasDe(c); });
  for (const k of ['state', 'reason', 'edge', 'evidence', 'evidence_balance', 'confidence']) {
    assert.deepStrictEqual(celdas[k], ['del instante'], k);
  }
  for (const k of ['zone_decision', 'confirms', 'confirms[0]', 'structural_horizon']) {
    assert.deepStrictEqual(celdas[k] || [], [], k);
  }
  // la fila de CONFIANZA bajo la palabra grande: la celda es la fila, y su marca es el span de la fila (en este DOM
  // minimo los nodos con id van planos; que la marca quede DENTRO de la celda lo mira K102 en un navegador, B11)
  assert.strictEqual(n.confFila.getAttribute('data-campo'), 'confidence');
  assert.strictEqual(n.confInstante.getAttribute('data-rotulo-instante'), 'del instante');
  assert.strictEqual(n.confInstante.textContent, 'del instante');
  assert.strictEqual(n.confPalabra.getAttribute('data-valor'), 'media');
  // y la palabra grande, su edad y data_confidence, sin marca
  assert.deepStrictEqual(marcasDe(n.sesgo), []);
  assert.deepStrictEqual(marcasDe(n.edadPalabra), []);
});

test('remate R1 · la marca no es una condicion de pintado: sigue cuando la grande y el instante dicen lo mismo', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  const s = sobre();
  s.datos.decide.instante = { ...INSTANTE, value: 'LONG' };
  s.datos.decide.state = delInstante('Long Pullback', 'operator_read.state');
  ctx.pintarDecide(s, n);
  assert.strictEqual(n.sesgo.textContent, 'LONG');
  const estado = documento.getElementById('decide-campos').querySelectorAll('[data-campo]')
    .find((c) => c.getAttribute('data-campo') === 'state');
  assert.deepStrictEqual(marcasDe(estado), ['del instante']);
  assert.deepStrictEqual(marcasDe(n.instante), ['instante']);
});

test('remate R1 · el motivo bajo la palabra grande es el SUYO: sin motivo servido no cae a la razon del instante', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  const s = sobre();
  delete s.datos.decide.bias.motivo;
  s.datos.decide.no_trade_reasons = delInstante(['libro stale'], 'operator_read.no_trade_reasons');
  ctx.pintarDecide(s, n);
  assert.strictEqual(n.motivo.textContent, '');
});

test('remate R1 · sin rotulo servido no hay marca: el cliente no la escribe', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  const s = sobre();
  delete s.datos.decide.state.rotulo_instante;
  delete s.datos.decide.confidence.rotulo_instante;
  ctx.pintarDecide(s, n);
  const estado = documento.getElementById('decide-campos').querySelectorAll('[data-campo]')
    .find((c) => c.getAttribute('data-campo') === 'state');
  assert.deepStrictEqual(marcasDe(estado), []);
  assert.strictEqual(n.confInstante.getAttribute('data-rotulo-instante'), null);
  assert.strictEqual(n.confInstante.textContent, '');
});
