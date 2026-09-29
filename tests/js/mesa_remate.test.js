'use strict';
// LA MESA · lo que el remate de la campana 130 arreglo. Un test por cosa prometida.

const test = require('node:test');
const assert = require('node:assert');
const { cargaMesa } = require('./harness-mesa.js');

function nodos(documento) {
  return {
    caja: documento.getElementById('decide'),
    sesgo: documento.getElementById('decide-sesgo'),
    sello: documento.getElementById('decide-sello'),
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

const campo = (v, k, extra) =>
  Object.assign({ value: v, source_key: k, status: 'ok' }, extra || {});

/* Un sobre con la forma que sirve /api/mesa/decide. `frame` decide el reparto. */
function sobre(frame) {
  const esScalp = frame === 'scalp';
  const lectura = {
    state: campo('Long Pullback', 'operator_read.state'),
    reason: campo('ΔFut1m -742774', 'scalp.reason'),
    confidence: campo('media', 'operator_read.confidence'),
    edge: campo(80.2, 'operator_read.edge'),
    evidence: campo(71.429, 'scalp.evidence_coverage_pct'),
    confirms: [campo('Rechazo confirmado', 'price_barriers.long_case.rejection')],
    invalidates: [campo('price_rejects_below_vwap', 'operator_read.invalidates_long[0]')],
    invalidation_level: campo(63385.45, 'price_barriers.nearest_support.center'),
    horizon: campo('mediana 1 min · p90 3 min', 'scalp_persistence.etiqueta',
      { outside_cut: true, dias: 30 }),
    no_trade_reasons: campo([], 'operator_read.no_trade_reasons'),
    warnings: campo([], 'operator_read.warnings'),
  };
  const d = {
    schema_version: 'mesa.decide.v1',
    frame,
    max_age_s: 120.0,
    no_evaluable_under: 70.0,
    envelope_cut: { as_of: '2026-09-29T06:00:00Z', snapshot: 'repeatable_read' },
    age: {
      snapshot_lag_seconds: campo(5.0, 'data_confidence.snapshot_lag_seconds'),
      price_cutoff_at: campo('2026-09-29T06:00:00+00:00', 'snapshot.price_cutoff_at'),
      metrics_cutoff_at: campo('2026-09-29T06:00:00+00:00', 'snapshot.metrics_cutoff_at'),
      stale: false,
      stale_rule: 'snapshot_lag_seconds > max_age_s (120 s)',
    },
    decide: {
      bias: esScalp
        ? { value: 'LONG', source_key: 'operator_read.bias', status: 'ok' }
        : {
            value: 'NO EVALUABLE',
            source_key: 'mesa.decide.frame',
            status: 'ok',
            motivo: 'la lectura del operador se calcula sobre la ventana del SCALP',
          },
      evaluable: { value: true, source_key: 'data_confidence.quality_score', status: 'ok', threshold: 70 },
      zone: {
        center: campo(63244.77, 'price_barriers.active_zone.center'),
        low: campo(63067.46, 'price_barriers.active_zone.low'),
        high: campo(63509.14, 'price_barriers.active_zone.high'),
        difficulty: campo('fuerte', 'price_barriers.active_zone.difficulty'),
      },
      zone_decision: campo('ESPERAR: zona en disputa', 'price_barriers.decision'),
      structural_invalidation: campo(62999.99, 'structure_detail.horizons.1h.invalidation_level'),
      structural_horizon: campo('1h', 'structure_detail.horizons.1h'),
      data_confidence: campo(100.0, 'data_confidence.quality_score'),
    },
  };
  if (esScalp) Object.assign(d.decide, lectura);
  else d.lectura_scalp = Object.assign({ de_marco: 'scalp', donde: '/mesa#scalp/BTC' }, lectura);
  return { ok: true, datos: d, tLlegada: 0 };
}

const campos = (n) =>
  n.campos.querySelectorAll('[data-campo]').map((c) => c.getAttribute('data-campo'));

// --- R1 · la lectura del scalp no firma los otros marcos --------------------------------

test('R1 · en SCALP, la lectura del scalp ES el veredicto y se pinta dentro de DECIDE', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  ctx.pintarDecide(sobre('scalp'), n);
  assert.strictEqual(n.sesgo.textContent, 'LONG');
  const c = campos(n);
  ['state', 'reason', 'edge', 'evidence', 'horizon', 'invalidation_level'].forEach((k) => {
    assert.ok(c.includes(k), `${k} tiene que estar en DECIDE en el marco scalp`);
  });
});

['swing', 'largo'].forEach((marco) => {
  test(`R1 · en ${marco.toUpperCase()} el veredicto es NO EVALUABLE con su motivo`, () => {
    const { ctx, documento } = cargaMesa();
    const n = nodos(documento);
    ctx.pintarDecide(sobre(marco), n);
    assert.strictEqual(n.sesgo.textContent, 'NO EVALUABLE');
    assert.strictEqual(n.sesgo.getAttribute('data-source-key'), 'mesa.decide.frame');
    assert.match(n.motivo.textContent, /ventana del SCALP/);
  });

  test(`R1 · en ${marco.toUpperCase()} NINGUNA celda del scalp se pinta dentro de DECIDE`, () => {
    const { ctx, documento } = cargaMesa();
    const n = nodos(documento);
    ctx.pintarDecide(sobre(marco), n);
    const c = campos(n);
    // esto es lo que hacia que un minuto de libro se leyera como una tesis de semanas
    ['state', 'reason', 'edge', 'evidence', 'horizon', 'invalidation_level',
     'confirms[0]', 'invalidates[0]'].forEach((k) => {
      assert.ok(!c.includes(k), `${k} NO puede pintarse dentro de DECIDE en ${marco}`);
    });
  });

  test(`R1 · en ${marco.toUpperCase()} lo PROPIO del marco se queda`, () => {
    const { ctx, documento } = cargaMesa();
    const n = nodos(documento);
    ctx.pintarDecide(sobre(marco), n);
    const c = campos(n);
    ['structural_invalidation', 'structural_horizon', 'zone.low', 'zone.center', 'zone.high']
      .forEach((k) => assert.ok(c.includes(k), `${k} tiene que seguir en DECIDE en ${marco}`));
  });

  test(`R1 · en ${marco.toUpperCase()} la lectura del scalp se pinta, con su rotulo`, () => {
    const { ctx, documento } = cargaMesa();
    const n = nodos(documento);
    ctx.pintarDecide(sobre(marco), n);
    const caja = documento.getElementById('lectura-scalp');
    assert.strictEqual(caja.hidden, false, 'la tarjeta del scalp tiene que verse');
    const rot = documento.getElementById('lectura-scalp-rotulo').textContent;
    assert.match(rot, /SCALP/);
    assert.match(rot, new RegExp('NO es el veredicto de ' + marco.toUpperCase()));
    // y lleva las celdas que salieron de DECIDE
    const dentro = documento
      .getElementById('lectura-scalp-campos')
      .querySelectorAll('[data-campo]')
      .map((x) => x.getAttribute('data-campo'));
    ['state', 'reason', 'edge', 'evidence', 'horizon'].forEach((k) =>
      assert.ok(dentro.includes(k), `${k} tiene que estar en la tarjeta del scalp`));
  });
});

// --- R5 · la tarjeta del scalp ensena el LADO del scalp cuando lo tiene ------------------

['swing', 'largo'].forEach((marco) => {
  test(`R5 · en ${marco.toUpperCase()} la tarjeta del scalp ensena SU veredicto, no el del marco`, () => {
    const { ctx, documento } = cargaMesa();
    const s = sobre(marco);
    // el scalp SI tiene lado: es lo que la tarjeta tiene que decir
    s.datos.lectura_scalp.bias = {
      value: 'SHORT', source_key: 'operator_read.bias', status: 'ok', raw: 'Short', motivo: null,
    };
    ctx.pintarDecide(s, nodos(documento));
    // DECIDE sigue diciendo NO EVALUABLE por el marco
    assert.strictEqual(documento.getElementById('decide-sesgo').textContent, 'NO EVALUABLE');
    // y la tarjeta del scalp dice SHORT, en su rotulo y en su celda
    assert.match(documento.getElementById('lectura-scalp-rotulo').textContent, /SCALP: SHORT/);
    const c = documento.getElementById('lectura-scalp-campos')
      .querySelectorAll('[data-campo]')
      .find((x) => x.getAttribute('data-campo') === 'scalp.bias');
    assert.ok(c, 'la tarjeta del scalp tiene que traer su propio sesgo');
    assert.strictEqual(
      c.querySelectorAll('[data-source-key]')[0].getAttribute('data-source-key'),
      'operator_read.bias'
    );
    assert.match(c.textContent, /SHORT/);
  });

  test(`R5 · en ${marco.toUpperCase()} el lado del scalp NO se confunde con el del marco`, () => {
    const { ctx, documento } = cargaMesa();
    const s = sobre(marco);
    s.datos.lectura_scalp.bias = { value: 'SHORT', source_key: 'operator_read.bias', status: 'ok' };
    ctx.pintarDecide(s, nodos(documento));
    const rot = documento.getElementById('lectura-scalp-rotulo').textContent;
    // el rotulo tiene que decir las dos cosas: de quien es y de quien NO es
    assert.match(rot, /SCALP: SHORT/);
    assert.match(rot, new RegExp('NO es el veredicto de ' + marco.toUpperCase()));
  });
});

test('R5 · cuando el scalp NO tiene lado, la tarjeta lo dice y no inventa uno', () => {
  const { ctx, documento } = cargaMesa();
  const s = sobre('swing');
  // es el control: con data_confidence baja el scalp es NO EVALUABLE y «sin lado» es VERDAD
  s.datos.lectura_scalp.bias = {
    value: 'NO EVALUABLE', source_key: 'data_confidence.quality_score', status: 'ok',
    motivo: 'data_confidence 0.0 < 70',
  };
  s.datos.lectura_scalp.confirms = [
    { value: null, status: 'ausente', source_key: 'price_barriers.<lado>_case.rejection',
      motivo: 'sin lado: el sesgo no es LONG ni SHORT' },
  ];
  ctx.pintarDecide(s, nodos(documento));
  assert.match(documento.getElementById('lectura-scalp-rotulo').textContent, /SCALP: NO EVALUABLE/);
  const t = documento.getElementById('lectura-scalp-campos').textContent;
  assert.match(t, /data_confidence 0\.0 < 70/);
  assert.match(t, /sin lado/);
});

test('R1 · en SCALP la tarjeta de la lectura del scalp NO existe: seria un duplicado', () => {
  const { ctx, documento } = cargaMesa();
  ctx.pintarDecide(sobre('scalp'), nodos(documento));
  assert.strictEqual(documento.getElementById('lectura-scalp').hidden, true);
});

// --- R3 · la edad es verdad en cada instante --------------------------------------------

test('R3 · la edad AVANZA con el tiempo transcurrido, sin volver a pedir nada', () => {
  const { ctx } = cargaMesa();
  const d = sobre('scalp').datos;
  // El arnes tiene performance.now() clavado en 0; se le pasa un tLlegada negativo, que es
  // lo mismo que decir «esto llego hace N segundos».
  assert.strictEqual(ctx.edadViva(d, 0).s, 5);
  assert.strictEqual(ctx.edadViva(d, -10000).s, 15);
  assert.strictEqual(ctx.edadViva(d, -60000).s, 65);
});

test('R3 · pasado max_age_s la edad viva dice RANCIO, aunque el sobre dijera que no', () => {
  const { ctx } = cargaMesa();
  const d = sobre('scalp').datos;
  assert.strictEqual(d.age.stale, false, 'el sobre nacio no-rancio');
  assert.strictEqual(ctx.edadViva(d, 0).rancio, false);
  // 5 s servidos + 116 transcurridos = 121 > 120
  assert.strictEqual(ctx.edadViva(d, -116000).rancio, true);
});

test('R3 · la edad se marca DERIVADA en cuanto deja de ser la servida', () => {
  const { ctx } = cargaMesa();
  const d = sobre('scalp').datos;
  assert.strictEqual(ctx.edadViva(d, 0).derivada, false);
  assert.strictEqual(ctx.edadViva(d, -10000).derivada, true);
});

test('R3 · sin edad servida no se inventa una: null, y no rancio', () => {
  const { ctx } = cargaMesa();
  const d = sobre('scalp').datos;
  d.age.snapshot_lag_seconds = { value: null, status: 'ausente', source_key: 'x' };
  const v = ctx.edadViva(d, -60000);
  assert.strictEqual(v.s, null);
  assert.strictEqual(v.rancio, false);
});

test('R3 · el sello de RANCIO aparece en la tarjeta, no solo en el pie', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  const s = sobre('scalp');
  ctx.pintarDecide(s, n);
  assert.strictEqual(n.sello.hidden, true, 'recien llegado no es rancio');
  assert.strictEqual(n.caja.classList.contains('rancio'), false);
  // y ahora el mismo sobre, 200 s despues, SIN recargar
  ctx.refrescarEdad(s.datos, -200000, n);
  assert.strictEqual(n.sello.hidden, false);
  assert.match(n.sello.textContent, /RANCIO/);
  assert.ok(n.caja.classList.contains('rancio'));
  assert.match(n.edad.textContent, /RANCIO/);
});

// --- R4a · la zona es un rango ----------------------------------------------------------

test('R4a · la zona pinta low, centro y high, cada uno con SU clave', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  ctx.pintarDecide(sobre('scalp'), n);
  const esperado = {
    'zone.low': 'price_barriers.active_zone.low',
    'zone.center': 'price_barriers.active_zone.center',
    'zone.high': 'price_barriers.active_zone.high',
    'zone.difficulty': 'price_barriers.active_zone.difficulty',
  };
  const celdas = n.campos.querySelectorAll('[data-campo]');
  Object.keys(esperado).forEach((nombre) => {
    const c = celdas.find((x) => x.getAttribute('data-campo') === nombre);
    assert.ok(c, `falta la celda ${nombre}`);
    const k = c.querySelectorAll('[data-source-key]')[0];
    assert.ok(k, `${nombre} no declara su clave`);
    assert.strictEqual(k.getAttribute('data-source-key'), esperado[nombre]);
  });
});

test('R4a · las tres cifras de la zona se leen, no solo el centro', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  ctx.pintarDecide(sobre('scalp'), n);
  const t = n.campos.textContent;
  // la entrega anterior decia que se ensenaban y solo llegaba el centro
  assert.match(t, /63\.067,5/);
  assert.match(t, /63\.244,8/);
  assert.match(t, /63\.509,1/);
});

test('R4a · si el backend no trae low, se dice: no se inventa un rango', () => {
  const { ctx, documento } = cargaMesa();
  const n = nodos(documento);
  const s = sobre('scalp');
  s.datos.decide.zone.low = { value: null, status: 'ausente', source_key: 'price_barriers.active_zone.low', motivo: 'no llega' };
  ctx.pintarDecide(s, n);
  const c = n.campos.querySelectorAll('[data-campo]')
    .find((x) => x.getAttribute('data-campo') === 'zone.low');
  assert.match(c.textContent, /AUSENTE/);
});
