'use strict';
// LA MESA · DECIDE. Lo que se prueba aqui es la PROMESA CENTRAL de la campana: que la pantalla
// pinta lo que el backend sirve, campo a campo, y que cuando el backend no sabe la pantalla lo
// dice con el motivo en vez de inventar un cero.

const test = require('node:test');
const assert = require('node:assert');
const { cargaMesa } = require('./harness-mesa.js');

function nodos(documento) {
  return {
    caja: documento.getElementById('decide'),
    sesgo: documento.getElementById('decide-sesgo'),
    motivo: documento.getElementById('decide-motivo'),
    campos: documento.getElementById('decide-campos'),
    edad: documento.getElementById('decide-edad'),
    escalones: documento.getElementById('conf-escalones'),
    confPalabra: documento.getElementById('conf-palabra'),
    confClave: documento.getElementById('conf-clave'),
    dcRelleno: documento.getElementById('dc-relleno'),
    dcValor: documento.getElementById('dc-valor'),
    dcClave: documento.getElementById('dc-clave'),
  };
}

function campo(value, source_key, extra) {
  return Object.assign({ value, source_key, status: 'ok' }, extra || {});
}

// Un sobre con la forma que sirve /api/mesa/decide. Los valores son de la medida real contra
// 140 del 2026-09-28, para que el test no invente una forma que el backend no tiene.
function sobreLong() {
  return {
    ok: true,
    datos: {
      schema_version: 'mesa.decide.v1',
      symbol: 'BTCUSDT_PERP.A',
      frame: 'scalp',
      max_age_s: 120.0,
      no_evaluable_under: 70.0,
      envelope_cut: { as_of: '2026-09-28T20:14:42Z', snapshot: 'repeatable_read', snapshot_reason: null },
      age: {
        snapshot_lag_seconds: campo(36.642, 'data_confidence.snapshot_lag_seconds'),
        price_cutoff_at: campo('2026-09-28T20:13:00+00:00', 'snapshot.price_cutoff_at'),
        metrics_cutoff_at: campo('2026-09-28T20:05:00+00:00', 'snapshot.metrics_cutoff_at'),
        stale: false,
        stale_rule: 'snapshot_lag_seconds > max_age_s (120 s)',
      },
      decide: {
        bias: { value: 'LONG', source_key: 'operator_read.bias', status: 'ok', raw: 'Long', motivo: null },
        evaluable: { value: true, source_key: 'data_confidence.quality_score', status: 'ok', threshold: 70.0 },
        state: campo('Long Pullback', 'operator_read.state'),
        reason: campo('ΔFut1m -742774, book ok/L5 0.47', 'scalp.reason'),
        zone: {
          center: campo(83751.5, 'price_barriers.active_zone.center'),
          low: campo(83357.8625, 'price_barriers.active_zone.low'),
          high: campo(83992.2375, 'price_barriers.active_zone.high'),
          difficulty: campo('fuerte', 'price_barriers.active_zone.difficulty'),
        },
        zone_decision: campo('ESPERAR: zona en disputa', 'price_barriers.decision'),
        confirms: [
          campo('Rechazo confirmado sobre 82736.46', 'price_barriers.long_case.rejection'),
          campo('breakout_up_score >= 70', 'price_barriers.long_case.flow_requirement'),
        ],
        invalidates: [
          campo('price_rejects_below_vwap', 'operator_read.invalidates_long[0]'),
        ],
        invalidation_level: campo(82930.61538462, 'price_barriers.nearest_support.center'),
        structural_invalidation: campo(82500.1, 'structure_detail.horizons.1h.invalidation_level'),
        structural_horizon: campo('1h', 'structure_detail.horizons.1h'),
        confidence: campo('media', 'operator_read.confidence'),
        data_confidence: campo(100.0, 'data_confidence.quality_score'),
        evidence: campo(100.0, 'scalp.evidence_coverage_pct'),
        edge: campo(23.6, 'operator_read.edge'),
        no_trade_reasons: campo([], 'operator_read.no_trade_reasons'),
        warnings: campo([], 'operator_read.warnings'),
        horizon: campo('mediana 1 min · p90 3 min', 'scalp_persistence.etiqueta', { outside_cut: true, dias: 30 }),
      },
    },
  };
}

// --- el sesgo sale de la clave, no de una cuenta del cliente ---------------------------

test('el sesgo que se pinta es EL VALOR SERVIDO, y declara su clave', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  ctx.pintarDecide(sobreLong(), n);
  assert.strictEqual(n.sesgo.textContent, 'LONG');
  assert.strictEqual(n.sesgo.getAttribute('data-valor'), 'LONG');
  assert.strictEqual(n.sesgo.getAttribute('data-source-key'), 'operator_read.bias');
});

test('si el backend dijera SHORT, la pantalla dice SHORT: el cliente no recalcula', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  const s = sobreLong();
  // Se cambia SOLO el valor servido. Si el cliente dedujese el sesgo de long_score/short_score
  // -que aqui no viajan- este test no podria pasar.
  s.datos.decide.bias = { value: 'SHORT', source_key: 'operator_read.bias', status: 'ok' };
  ctx.pintarDecide(s, n);
  assert.strictEqual(n.sesgo.textContent, 'SHORT');
  assert.strictEqual(n.sesgo.className, 'sesgo-SHORT');
});

test('LA REGLA DEL HANDOFF · data_confidence < 70 sale NO EVALUABLE con su motivo', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  const s = sobreLong();
  // Es el caso que el ESPEJO produjo solo, con datos de verdad: quality_score 0.0.
  s.datos.decide.bias = {
    value: 'NO EVALUABLE',
    source_key: 'data_confidence.quality_score',
    status: 'ok',
    raw: 'Short',
    motivo: 'data_confidence 0.0 < 70',
  };
  s.datos.decide.evaluable = {
    value: false, source_key: 'data_confidence.quality_score', status: 'ok', threshold: 70.0,
  };
  s.datos.decide.data_confidence = campo(0.0, 'data_confidence.quality_score');
  ctx.pintarDecide(s, n);
  assert.strictEqual(n.sesgo.textContent, 'NO EVALUABLE');
  assert.strictEqual(n.sesgo.className, 'sesgo-NOEVAL');
  assert.match(n.motivo.textContent, /data_confidence 0\.0 < 70/);
  // y la tarjeta entera se marca como insuficiente, que es lo que pide el handoff
  assert.ok(n.caja.classList.contains('no-evaluable'));
});

test('con datos suficientes la tarjeta NO lleva la trama de insuficiente', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  ctx.pintarDecide(sobreLong(), n);
  assert.strictEqual(n.caja.classList.contains('no-evaluable'), false);
});

// --- los cuatro «no se», que no son cero -----------------------------------------------

test('AUSENTE · un campo que el backend no trae se dice AUSENTE con su motivo, no 0', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  const s = sobreLong();
  s.datos.decide.invalidation_level = {
    value: null, status: 'ausente', source_key: 'price_barriers.nearest_*.center',
    motivo: 'sin lado: el sesgo no es LONG ni SHORT',
  };
  ctx.pintarDecide(s, n);
  const celda = n.campos.querySelectorAll('[data-campo]')
    .find((c) => c.getAttribute('data-campo') === 'invalidation_level');
  assert.ok(celda, 'la celda de invalidation_level tiene que existir igual');
  assert.match(celda.textContent, /AUSENTE/);
  assert.match(celda.textContent, /sin lado/);
  assert.doesNotMatch(celda.textContent, /(^|[^\d])0([^\d]|$)/);
});

test('NULO y AUSENTE se pintan DISTINTO: el null es una respuesta, no una falta', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  const s = sobreLong();
  s.datos.decide.edge = { value: null, status: 'nulo', source_key: 'operator_read.edge', motivo: 'llega null' };
  ctx.pintarDecide(s, n);
  const celda = n.campos.querySelectorAll('[data-campo]')
    .find((c) => c.getAttribute('data-campo') === 'edge');
  assert.match(celda.textContent, /NULO/);
  assert.doesNotMatch(celda.textContent, /AUSENTE/);
});

test('RANCIO ensena EL VALOR y ademas dice que es viejo (los otros tres no ensenan valor)', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  const s = sobreLong();
  s.datos.decide.reason = {
    value: 'book stale/L5 0.10', status: 'rancio', source_key: 'scalp.reason',
    motivo: 'mas viejo que el tope',
  };
  ctx.pintarDecide(s, n);
  const celda = n.campos.querySelectorAll('[data-campo]')
    .find((c) => c.getAttribute('data-campo') === 'reason');
  assert.match(celda.textContent, /book stale\/L5 0\.10/);
  assert.match(celda.textContent, /RANCIO/);
  // y el valor sigue siendo auditable en data-valor
  const v = celda.querySelectorAll('[data-valor]')[0];
  assert.strictEqual(v.getAttribute('data-valor'), 'book stale/L5 0.10');
});

test('ERROR · si la ruta falla, DECIDE lo dice y NO se queda en un NEUTRAL falso', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  ctx.pintarDecide({ ok: false, http: 502, motivo: 'transporte', ruta: '/api/mesa/decide' }, n);
  assert.strictEqual(n.sesgo.textContent, 'SIN DATO');
  assert.match(n.motivo.textContent, /ERROR/);
  // lo que NO puede pasar: que un fallo se lea como un veredicto del mercado
  assert.notStrictEqual(n.sesgo.textContent, 'NEUTRAL');
  assert.notStrictEqual(n.sesgo.textContent, 'LONG');
});

// --- la procedencia, que es lo que hace auditable la pantalla ---------------------------

test('CADA celda de DECIDE lleva su source_key, y es la que sirvio el backend', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  const s = sobreLong();
  ctx.pintarDecide(s, n);
  const dec = s.datos.decide;
  const esperado = {
    'zone.center': 'price_barriers.active_zone.center',
    zone_decision: 'price_barriers.decision',
    invalidation_level: 'price_barriers.nearest_support.center',
    structural_invalidation: 'structure_detail.horizons.1h.invalidation_level',
    state: 'operator_read.state',
    reason: 'scalp.reason',
    edge: 'operator_read.edge',
    evidence: 'scalp.evidence_coverage_pct',
    horizon: 'scalp_persistence.etiqueta',
  };
  const celdas = n.campos.querySelectorAll('[data-campo]');
  Object.keys(esperado).forEach((nombre) => {
    const c = celdas.find((x) => x.getAttribute('data-campo') === nombre);
    assert.ok(c, `falta la celda ${nombre}`);
    const k = c.querySelectorAll('[data-source-key]')[0];
    assert.ok(k, `la celda ${nombre} no declara su clave`);
    assert.strictEqual(k.getAttribute('data-source-key'), esperado[nombre]);
  });
  assert.ok(dec.state.source_key === esperado.state);
});

test('CADA entrada de una lista lleva SU clave, no una comun: si no, un intercambio cuela', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  ctx.pintarDecide(sobreLong(), n);
  const celdas = n.campos.querySelectorAll('[data-campo]');
  const c0 = celdas.find((x) => x.getAttribute('data-campo') === 'confirms[0]');
  const c1 = celdas.find((x) => x.getAttribute('data-campo') === 'confirms[1]');
  assert.ok(c0 && c1, 'las dos entradas de confirms tienen que ser celdas propias');
  assert.strictEqual(
    c0.querySelectorAll('[data-source-key]')[0].getAttribute('data-source-key'),
    'price_barriers.long_case.rejection'
  );
  assert.strictEqual(
    c1.querySelectorAll('[data-source-key]')[0].getAttribute('data-source-key'),
    'price_barriers.long_case.flow_requirement'
  );
});

// --- la confianza es una palabra -------------------------------------------------------

test('la confianza se pinta como PALABRA con tres escalones, no como porcentaje', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  ctx.pintarDecide(sobreLong(), n);
  assert.strictEqual(n.confPalabra.textContent, 'media');
  const encendidos = n.escalones.children.filter((x) => x.classList.contains('on')).length;
  assert.strictEqual(encendidos, 2, 'media = 2 de 3 escalones');
  // y NO aparece un % inventado junto a la palabra
  assert.doesNotMatch(n.confPalabra.textContent, /%/);
});

test('los tres niveles de confianza encienden 1, 2 y 3 escalones', () => {
  [['baja', 1], ['media', 2], ['alta', 3]].forEach(([palabra, esperado]) => {
    const { ctx, documento } = cargaMesa();
    const n = nodos(documento);
    const s = sobreLong();
    s.datos.decide.confidence = campo(palabra, 'operator_read.confidence');
    ctx.pintarDecide(s, n);
    const on = n.escalones.children.filter((x) => x.classList.contains('on')).length;
    assert.strictEqual(on, esperado, `${palabra} -> ${esperado}`);
  });
});

// --- la edad y su tope, en pantalla ----------------------------------------------------

test('la EDAD y su TOPE DECLARADO se ensenan los dos', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  ctx.pintarDecide(sobreLong(), n);
  const t = n.edad.textContent;
  assert.match(t, /36,6 s|36\.6 s/);
  assert.match(t, /tope declarado 120 s/);
});

test('cuando el snapshot pasa del tope, la edad dice RANCIO con su regla', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  const s = sobreLong();
  s.datos.age.snapshot_lag_seconds = campo(3984650.03, 'data_confidence.snapshot_lag_seconds');
  s.datos.age.stale = true;
  ctx.pintarDecide(s, n);
  assert.match(n.edad.textContent, /RANCIO/);
  assert.match(n.edad.textContent, /snapshot_lag_seconds > max_age_s/);
});

test('la diferencia entre las dos vendimias se ensena y se marca DERIVADA', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  ctx.pintarDecide(sobreLong(), n);
  // 20:13:00 contra 20:05:00 = 480 s, que es lo que el operador midio el 09-11.
  assert.match(n.edad.textContent, /480 s/);
  assert.match(n.edad.textContent, /DERIVADO/);
});

test('el corte se declara: la garantia de la 129 llega a la pantalla', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  ctx.pintarDecide(sobreLong(), n);
  assert.match(n.edad.textContent, /UNA instantánea declarada \(repeatable_read\)/);
});

test('un sobre SIN instantanea lo dice, en vez de prometer un corte que no tuvo', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  const s = sobreLong();
  s.datos.envelope_cut = {
    as_of: '2026-09-28T20:14:42Z', snapshot: 'none',
    snapshot_reason: 'la conexion no ofrece transaction(): es un doble',
  };
  ctx.pintarDecide(s, n);
  assert.match(n.edad.textContent, /SIN instantánea/);
  assert.match(n.edad.textContent, /es un doble/);
});

test('el horizonte declara que va FUERA del corte y con que ventana', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  ctx.pintarDecide(sobreLong(), n);
  const c = n.campos.querySelectorAll('[data-campo]')
    .find((x) => x.getAttribute('data-campo') === 'horizon');
  assert.match(c.textContent, /mediana 1 min/);
  assert.match(c.textContent, /fuera del corte/);
  assert.match(c.textContent, /30 d/);
});

test('sin episodios, el horizonte sale AUSENTE con motivo: cero no es un horizonte', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  const s = sobreLong();
  s.datos.decide.horizon = {
    value: null, status: 'ausente', source_key: 'scalp_persistence.etiqueta',
    motivo: 'sin episodios accionables en la ventana', outside_cut: true, dias: 30,
  };
  ctx.pintarDecide(s, n);
  const c = n.campos.querySelectorAll('[data-campo]')
    .find((x) => x.getAttribute('data-campo') === 'horizon');
  assert.match(c.textContent, /AUSENTE/);
  assert.match(c.textContent, /sin episodios accionables/);
});
