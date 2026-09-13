'use strict';
// perfil de trading, OI, ejecucion, hipotesis y calidad
// Trozo 9 de 11 del panel. Sale de static/app.js SIN TOCAR UNA LINEA DE LOGICA
// (FASE 2, 2026-09-13): lineas 2029-2759 del fichero original.
// El orden de los <script defer> de index.html ES el orden de este fichero: no se
// reordena nada, porque en scripts clasicos un `const` de primer nivel solo existe a
// partir del script que lo declara.
function initTradingProfile() {
  const tabs = $('profile-tabs');
  if (!tabs) return;
  tabs.addEventListener('click', event => {
    const button = event.target.closest('button[data-profile]');
    if (!button || button.dataset.profile === state.tradingProfile) return;
    state.tradingProfile = button.dataset.profile;
    for (const b of tabs.querySelectorAll('button[data-profile]')) {
      b.classList.toggle('active', b === button);
    }
    // Solo cambia la lectura: se fuerza el tramo de contexto, no se recargan datos brutos.
    state.lastContextAt = 0;
    // El enfasis por capa vive en las tablas de estructura y flujo, que se pintan desde
    // loadSection y tienen cache de 30 s: sin invalidarla, cambiar de perfil dejaba el
    // resaltado del perfil anterior hasta el siguiente ciclo.
    state.viewLoadedAt = {};
    refreshOverview(true)
      .then(() => loadSection(state.activeSection, true))
      .catch(error => console.error(error));
  });
}

// Jerarquia de temporalidades del perfil activo. Muestra peso y aportacion de cada capa
// porque un sesgo que no se puede auditar no sirve para decidir.
function renderTfProfile(result) {
  const box = $('tfprofile-layers');
  if (!box) return;
  box.replaceChildren();
  const cls = b => b === 'alcista' ? 'positive' : (b === 'bajista' ? 'negative' : 'neutral');
  const sub = $('tfprofile-subtitle');
  if (sub) sub.textContent = result.profile_label
    ? `${result.profile_label} · cobertura ${number(result.coverage_pct, 0)}% · confianza ${result.confidence || '—'}`
    : 'Sin datos';
  const pill = $('tfprofile-bias');
  if (pill) {
    pill.textContent = (result.bias || '—').replace('_', ' ');
    pill.className = `live-pill ${cls(result.bias)}`;
  }
  for (const [name, layer] of Object.entries(result.layers || {})) {
    const card = document.createElement('div');
    card.className = 'tfprofile-layer';
    const h = document.createElement('h4');
    h.textContent = name;
    const meta = document.createElement('div');
    meta.className = 'layer-meta';
    // El dato ausente se cuenta, no se disfraza de neutral.
    meta.textContent = `peso ${layer.weight} · ${layer.bias} · aporta ${layer.contribution === null || layer.contribution === undefined ? 'N/D' : number(layer.contribution, 1)} · ${layer.measurable_timeframes}/${layer.expected_timeframes} marcos`;
    const ul = document.createElement('ul');
    for (const tf of safeArray(layer.timeframes)) {
      const li = document.createElement('li');
      const a = document.createElement('span');
      a.textContent = tf.timeframe;
      const b = document.createElement('span');
      b.textContent = tf.bias === 'sin_datos' ? 'sin datos' : tf.bias;
      b.className = cls(tf.bias);
      b.title = `${tf.detail || ''} (fuente: ${tf.source || '—'})`;
      li.append(a, b);
      ul.append(li);
    }
    card.append(h, meta, ul);
    box.append(card);
  }
  const notes = $('tfprofile-contradictions');
  if (notes) {
    notes.replaceChildren();
    for (const c of safeArray(result.contradictions)) {
      const p = document.createElement('p');
      p.className = `tfprofile-note ${c.efecto}`;
      p.textContent = `${c.efecto === 'invalida' ? 'INVALIDA' : 'ESPERAR'} · ${c.detalle} — ${c.motivo}`;
      notes.append(p);
    }
    if (!safeArray(result.contradictions).length && result.bias) {
      const p = document.createElement('p');
      p.className = 'tfprofile-note';
      p.textContent = 'Sin contradicciones entre capas.';
      notes.append(p);
    }
  }
  const foot = $('tfprofile-footnote');
  if (foot) {
    const missing = safeArray(result.missing_data).join(' · ');
    foot.textContent = [result.invalidation, result.weights_note, missing ? `Datos faltantes: ${missing}` : '']
      .filter(Boolean).join(' ');
  }
}


// ---------------- paneles de la reorganizacion ----------------
function renderOiChart(oi) {
  renderGapNote('oi-gaps', setGappedLine('oi', oi, r => ts(r.bucket), r => r.oi));
  try { state.charts['oi-chart'].timeScale().fitContent(); } catch (_) {}
}

// DE QUE VENUE ES ESTA SERIE · la tarjeta existe desde el primer commit del repo y nunca lo
// dijo. Ahora lo dice, y lo dice CON LO QUE EL BACKEND DECLARA, no con un literal:
//   · la serie: `data_gaps.exchanges` de /api/oi. Si manana la fuente cambia, cambia sola.
//   · el reparto: `oi_context.by_venue` del sobre, que trae los dos venues, su total y su
//     `note` con el ALCANCE -que venues cubre y cuales no-. El alcance se PUBLICA tal cual
//     lo declara el backend en vez de reescribirlo aqui, que seria volver al literal.
// SI NADIE LO DECLARA, LA TARJETA DICE QUE NO LO SABE. No se pone un venue por defecto: una
// serie atribuida al venue equivocado es peor que una serie sin atribuir.
function renderOiVenue(respuesta, contexto) {
  const cab = $('oi-venue');
  if (cab) {
    const ex = ((respuesta || {}).data_gaps || {}).exchanges;
    const venues = safeArray(ex).filter(Boolean);
    cab.textContent = venues.length
      ? `${venues.join(' + ')} · 15 min · eje UTC`
      : 'venue no declarado · 15 min · eje UTC';
    cab.title = venues.length
      ? `La fuente la declara /api/oi en data_gaps.exchanges: ${venues.join(', ')}`
      : '/api/oi no declara de que venue es la serie, asi que la tarjeta no lo afirma';
  }
  const pie = $('oi-venue-reparto');
  if (!pie) return;
  const bv = (contexto || {}).by_venue;
  if (!bv) {
    // AUSENTE SE VE COMO AUSENTE: ni vacio ni cero.
    pie.textContent = 'Reparto por venue: no servido.';
    return;
  }
  const partes = [];
  for (const [k, v] of Object.entries(bv)) {
    const m = /^(\w+)_oi_usd$/.exec(k);
    if (m && asNumber(v) !== null) partes.push(`${m[1]} ${money(v, 0)}`);
  }
  const share = asNumber(bv.bybit_share_of_two_venues_pct);
  const total = asNumber(bv.two_venue_total_usd);
  const cabeza = partes.length ? partes.join(' · ') : 'sin desglose por venue';
  const cola = [
    total === null ? null : `total ${money(total, 0)}`,
    share === null ? null : `bybit ${number(share, 1)} % de los dos`,
  ].filter(Boolean).join(' · ');
  pie.textContent = `Reparto: ${cabeza}${cola ? ' · ' + cola : ''}`;
  // EL ALCANCE, con las palabras del backend. Es lo que impide leer el reparto como si
  // fuera el mercado entero.
  if (bv.note) pie.textContent += ` — ${bv.note}`;
}

// Reparte la evidencia respecto de la hipotesis que puso el operador. No emite ordenes:
// solo dice que la apoya, que la contradice y que falta por ocurrir.
const HYP_BUCKETS = [
  ['a_favor', 'A favor', 'positive'],
  ['en_contra', 'En contra', 'negative'],
  ['pendiente', 'Pendiente', 'neutral'],
  ['neutral', 'Neutral', 'neutral'],
  ['no_evaluable', 'No evaluable', 'neutral'],
];
// La ejecucion ya no es una etiqueta binaria sacada de un umbral de spread: es el coste
// total de ida y vuelta comparado con el objetivo y con el riesgo de ESTA operacion. Sin
// objetivo, stop, comision ni tamano se dice SIN EVALUAR y se enumera lo que falta.
const EXEC_CLASS = { aceptable: 'positive', ajustado: 'neutral', prohibitivo: 'negative' };
// El estado visual de la ejecucion sale de la EVALUACION —las bandas de coste sobre objetivo
// y sobre riesgo—, nunca de comparar el spread bruto contra un literal. `SIN EVALUAR` es
// neutro a proposito: no saber si sale cara no es lo mismo que saber que sale cara.
function executionClass(execution) {
  if (!execution || typeof execution !== 'object' || execution.status !== 'EVALUADO') return 'neutral';
  const bandas = [execution.cost_to_target_band, execution.cost_to_risk_band].filter(Boolean);
  if (bandas.includes('prohibitivo')) return 'negative';
  if (bandas.includes('ajustado')) return 'neutral';
  // UN 'aceptable' SOBRE UN COSTE INCOMPLETO NO SE PINTA EN VERDE, y es la MISMA regla de
  // arriba aplicada un paso mas alla: el backend calcula cost_to_target y cost_to_risk
  // sumando SOLO las patas medidas (scalp_logic.py:4796-4812), asi que una pata que falta
  // baja el coste y sube la banda. Medido contra 140 el 2026-08-31 con el mismo plan y el
  // mismo mercado: sin slippage sale 8.013 bps y 'aceptable'; con slippage 10, 28.013 bps y
  // 'prohibitivo'. Verde es la unica clase que afirma algo bueno, y aqui no se sabe.
  if (bandas.includes('aceptable')) {
    return safeArray(execution.cost_components_missing).length ? 'neutral' : 'positive';
  }
  return 'neutral';
}
// El aviso de spread es SECUNDARIO: informa, no veta ni clasifica direccion. Se devuelve
// aparte para que nadie lo confunda con el veredicto.
function spreadWarning(execution) {
  return execution && execution.spread_warning ? String(execution.spread_warning) : null;
}
function renderExecutionRows(dl, execution) {
  if (!execution || typeof execution !== 'object') {
    rowDL(dl, 'Ejecución', 'N/D', 'neutral');
    return;
  }
  const veredicto = String(execution.verdict || 'SIN EVALUAR');
  rowDL(dl, `Ejecución (${execution.profile_label || execution.profile || '—'})`, veredicto, executionClass(execution));
  if (execution.status === 'SIN EVALUAR') {
    const faltan = safeArray(execution.missing_inputs).join(', ');
    rowDL(dl, 'Falta para evaluar', faltan || 'plan de operación', 'neutral');
    return;
  }
  // EL TOTAL SE ROTULA POR LO QUE ES. El backend publica cost_components_missing y hasta hoy
  // esta capa no lo leia: pintaba "Coste ida y vuelta" a secas sobre una suma de las patas
  // MEDIDAS, y el lector pone un cero donde no hay dato. No es cosmetico -- el veredicto de
  // la fila de arriba sale de ese mismo total parcial.
  const patasAusentes = safeArray(execution.cost_components_missing);
  rowDL(dl, patasAusentes.length ? 'Coste ida y vuelta (PARCIAL)' : 'Coste ida y vuelta',
    nd(execution.total_cost_bps, v => `${number(v, 2)} bps`), 'neutral');
  if (patasAusentes.length) {
    rowDL(dl, 'Patas de coste sin dato',
      `${patasAusentes.join(', ')} · el total y el veredicto salen solo de las medidas, así que ambos son un SUELO`,
      'negative');
  }
  const sobreObjetivo = asNumber(execution.cost_to_target);
  rowDL(dl, 'Coste / objetivo',
    sobreObjetivo === null ? 'N/D' : `${number(sobreObjetivo * 100, 1)}% del objetivo · ${execution.cost_to_target_band}`,
    EXEC_CLASS[execution.cost_to_target_band] || 'neutral');
  const sobreRiesgo = asNumber(execution.cost_to_risk);
  rowDL(dl, 'Coste / riesgo',
    sobreRiesgo === null ? 'N/D' : `${number(sobreRiesgo * 100, 1)}% del riesgo · ${execution.cost_to_risk_band}`,
    EXEC_CLASS[execution.cost_to_risk_band] || 'neutral');
  // Advertencia SECUNDARIA, siempre en neutro: no cambia el veredicto ni añade dirección.
  const aviso = spreadWarning(execution);
  if (aviso) rowDL(dl, 'Aviso de spread (secundario)', aviso, 'neutral');
}

// Estado del SETUP con su propia lectura: cada tipo tiene requisitos e invalidaciones
// distintos, asi que se muestra cuantos se cumplen y cuantos no se pueden ni evaluar.
const SETUP_CLASS = {
  CONFIRMADO: 'positive', CANDIDATO: 'neutral', PENDIENTE: 'neutral',
  FALLIDO: 'negative', 'NO EVALUABLE': 'neutral',
};
function renderSetupRows(dl, setup) {
  if (!setup || setup.setup === 'ninguno') {
    rowDL(dl, 'Setup', 'Ninguno seleccionado', 'neutral');
    return;
  }
  rowDL(dl, `Setup · ${setup.label}`, String(setup.state), SETUP_CLASS[setup.state] || 'neutral');
  const cumplidos = safeArray(setup.cumplidos).length;
  const evaluables = asNumber(setup.requisitos_evaluables);
  rowDL(dl, 'Requisitos',
    evaluables === null ? 'N/D' : `${cumplidos}/${evaluables} cumplidos · ${safeArray(setup.no_evaluables).length} sin observable`,
    'neutral');
  if (safeArray(setup.faltantes).length) {
    rowDL(dl, 'No evaluable por', safeArray(setup.faltantes).join(', '), 'negative');
  }
}


// --- LA MESA DA PRECIO ---------------------------------------------------------------------
// Hasta el 2026-09-07 la tarjeta de decision daba la invalidacion en prosa -«el CVD spot gira
// vendedor»- y NINGUN numero. `/api/reference-levels` existia, contestaba y era correcta -los
// catorce niveles recalculados desde `ohlcv` 1min cuadran valor por valor- y no llegaba aqui.
//
// SON REFERENCIA, NO PREDICCION. No hay ninguna regla de entrada sobre ellos, ninguna puntuacion
// derivada y ningun setup que los use: esta medido que la señal no anticipa y que ninguna regla
// de entrada alcanzable le recupera la ventaja, asi que una regla sobre niveles seria una
// afirmacion nueva sin una sola medida detras.
function nivelesRows(dl, niveles) {
  if (!niveles) {
    rowDL(dl, 'Niveles', 'No llegaron en este snapshot', 'neutral');
    return;
  }
  const pd = niveles.previous_day || {};
  const cd = niveles.current_day || {};
  const op = niveles.opens || {};
  // El dia previo esta CERRADO: su maximo y su minimo ya no se mueven. Se dice, porque es la
  // diferencia con los de hoy.
  rowDL(dl, 'Día previo (cerrado)',
    `${precio(pd.high)} máx · ${precio(pd.low)} mín · ${precio(pd.close)} cierre${alcance(pd)}`, 'neutral');
  rowDL(dl, 'Hoy (en curso)',
    `${precio(cd.high)} máx · ${precio(cd.low)} mín · ${precio(cd.open)} apertura${alcance(cd)}`, 'neutral');
  // Las tres aperturas juntas: cuando dos coinciden no es un error, es que el periodo empieza el
  // mismo dia -la semanal y la diaria coinciden los lunes-.
  rowDL(dl, 'Aperturas D/S/M',
    `${precio(op.daily)} · ${precio(op.weekly)} · ${precio(op.monthly)}`, 'neutral');
  const ses = niveles.sessions_today_utc || {};
  for (const [clave, etiqueta] of [['asia', 'Asia'], ['london', 'Londres'], ['new_york', 'Nueva York']]) {
    const s = ses[clave];
    if (!s) continue;
    // EL ALCANCE VA PEGADO AL NIVEL Y NO EN UNA NOTA. Medido el 2026-09-07T17:15Z: Asia iba sobre
    // sus 480 velas, Londres sobre sus 540, y Nueva York sobre 215 de las 540 que dura. Un maximo
    // de sesion sacado de un puñado de velas y uno sacado de la sesion completa no son la misma
    // cifra, y hasta hoy la tarjeta los habria presentado igual.
    rowDL(dl, `${etiqueta} ${s.window_utc || ''} UTC`,
      `${precio(s.high)} máx · ${precio(s.low)} mín${alcance(s)}`,
      s.en_curso ? 'neutral' : 'positive');
  }
}

// `precio` y `alcance` son de formato, no de calculo: no derivan nada del nivel.
function precio(v) {
  const n = asNumber(v);
  return n === null ? 'N/D' : number(n, 1);
}
function alcance(s) {
  const v = asNumber(s && s.velas);
  const posibles = asNumber(s && s.velas_posibles);
  const dura = asNumber(s && s.duracion_min);
  if (v === null || posibles === null) return '';
  // Se dicen las TRES cifras y no una: cuantas velas hay, cuantas cabian ya, y cuanto dura la
  // ventana entera. Sin la tercera, «215 de 216» parece completo y es el 40 % de la sesion.
  const cola = dura !== null && posibles < dura ? ` de ${dura} que dura` : '';
  return ` · sobre ${v} de ${posibles} velas${cola}`;
}

// --- B · LA ETIQUETA DE CONFIANZA, CON LO QUE HA VALIDO -------------------------------------
// Medido sobre signal_observation ⋈ signal_outcome a 60 min, BTCUSDT_PERP.A periodicas, del
// 2026-08-10 al 2026-09-07. Las DOS cifras, porque una sola se lee mal en las dos direcciones:
// con solo la magnitud, «alta» se lee como «acierta mas»; con solo la frecuencia, se lee como
// «no vale para nada», cuando SI dice cuanto te juegas.
const CONFIANZA_MEDIDA = {
  alta:  { n: 619,   acierto: 45.1, mov: 0.3355 },
  media: { n: 13717, acierto: 48.6, mov: 0.2730 },
};
function confianzaRow(dl, etiqueta) {
  const e = String(etiqueta || '').toLowerCase();
  if (e === 'baja') {
    // `baja` NO es un peldaño mas de la escalera: es la AUSENCIA de apuesta. Medido: de sus
    // 23 560 observaciones, CERO traen direccion long o short -22 610 neutral y 950
    // unavailable-. Quien lea «confianza baja» entenderia «apuesta debil»; no hay apuesta.
    rowDL(dl, 'Confianza', 'baja — que aquí significa SIN dirección: no es una apuesta débil, es que no hay apuesta (0 de 23 560 con dirección)', 'neutral');
    return;
  }
  const m = CONFIANZA_MEDIDA[e];
  if (!m) { rowDL(dl, 'Confianza', etiqueta || 'N/D', 'neutral'); return; }
  rowDL(dl, 'Confianza',
    `${e} — ha acertado la dirección el ${number(m.acierto, 1)} % de las veces y el precio se movió ${number(m.mov, 3)} % de media, sobre ${m.n} observaciones a 60 min`,
    'neutral');
}

function renderHypothesis(result) {
  const box = $('hyp-evidence');
  if (!box) return;
  box.replaceChildren();
  const sub = $('hyp-subtitle');
  if (sub) {
    sub.textContent = result.label
      ? `${result.label} · perfil ${result.profile || '—'} · datos ${number(result.data_coverage_pct, 0)}% · marcos ${number(result.profile_coverage_pct, 0)}%`
      : 'Sin datos';
  }
  const pill = $('hyp-verdict');
  if (pill) {
    const c = result.counts || {};
    pill.textContent = `${c.a_favor || 0} a favor · ${c.en_contra || 0} en contra`;
    pill.className = `live-pill ${(c.a_favor || 0) > (c.en_contra || 0) ? 'positive' : (c.en_contra || 0) > (c.a_favor || 0) ? 'negative' : 'neutral'}`;
  }
  const dl = $('hyp-summary');
  if (dl) {
    dl.replaceChildren();
    rowDL(dl, 'Contexto', result.context || '—', result.context === 'alcista' ? 'positive' : result.context === 'bajista' ? 'negative' : 'neutral');
    rowDL(dl, 'Timing', result.timing || '—', result.timing === 'alcista' ? 'positive' : result.timing === 'bajista' ? 'negative' : 'neutral');
    const cobertura = asNumber(result.data_coverage_pct);
    rowDL(dl, 'Datos', cobertura === null ? 'N/D' : `${number(cobertura, 0)}% de la evidencia`, cobertura !== null && cobertura >= 80 ? 'positive' : 'negative');
    renderExecutionRows(dl, result.execution);
    renderSetupRows(dl, result.setup_evaluation);
    confianzaRow(dl, (state.desk.components && state.desk.components.scalp || {}).confidence);
    nivelesRows(dl, state.desk.components && state.desk.components.reference_levels);
  }
  for (const entry of HYP_BUCKETS) {
    const items = safeArray((result.evidence || {})[entry[0]]);
    if (!items.length) continue;
    const card = document.createElement('div');
    card.className = 'tfprofile-layer';
    const h = document.createElement('h4');
    h.textContent = `${entry[1]} (${items.length})`;
    h.className = entry[2];
    const ul = document.createElement('ul');
    for (const it of items) {
      const li = document.createElement('li');
      const a = document.createElement('span');
      a.textContent = it.signal;
      const b = document.createElement('span');
      b.textContent = it.detail;
      li.append(a, b);
      ul.append(li);
    }
    card.append(h, ul);
    box.append(card);
  }
  const notes = [];
  for (const c of safeArray(result.pending_conditions)) notes.push(`PENDIENTE · ${c}`);
  for (const c of safeArray(result.invalidations)) notes.push(`INVALIDA · ${c}`);
  const foot = $('hyp-note');
  if (foot) foot.textContent = [notes.join('   |   '), result.note].filter(Boolean).join('   ');
}

function renderFunding(result) {
  const dl = $('funding-list');
  if (!dl) return;
  dl.replaceChildren();
  rowDL(dl, 'Funding actual', result.current_pct == null ? 'Sin dato' : rate(result.current_pct), result.current_pct == null ? 'neutral' : signClass(-result.current_pct));
  rowDL(dl, 'Predicho', result.predicted_pct == null ? 'Sin dato' : rate(result.predicted_pct), 'neutral');
  rowDL(dl, 'Divergencia pred-actual', result.divergence_pred_minus_current == null ? '—' : rate(result.divergence_pred_minus_current), 'neutral');
  rowDL(dl, 'Media histórica', result.history_avg_pct == null ? '—' : rate(result.history_avg_pct), 'neutral');
  rowDL(dl, 'Anualizado', result.annualized_pct == null ? '—' : `${number(result.annualized_pct, 2)}%`, 'neutral');
  rowDL(dl, 'Próximo pago (UTC)', result.next_funding_time_utc || '—', 'neutral');
  rowDL(dl, 'Régimen', result.regime || '—', 'neutral');
}

function renderPositioning(result) {
  const dl = $('positioning-list');
  if (!dl) return;
  dl.replaceChildren();
  if (result.status === 'UNAVAILABLE' || result.ratio == null) {
    rowDL(dl, 'Estado', result.reason || 'Sin datos', 'negative');
    return;
  }
  rowDL(dl, 'Ratio long/short', number(result.ratio, 3), signClass(result.ratio - 1));
  rowDL(dl, 'Long / Short', `${number(result.long_pct, 2)}% / ${number(result.short_pct, 2)}%`, 'neutral');
  rowDL(dl, 'Cambio 24 h', result.ratio_change_24h == null ? '—' : number(result.ratio_change_24h, 4), signClass(result.ratio_change_24h));
  rowDL(dl, 'Mediana de la muestra', result.median_sample == null ? '—' : number(result.median_sample, 3), 'neutral');
  rowDL(dl, 'Percentil en la muestra', result.percentile_sample == null ? 'Muestra corta' : `${number(result.percentile_sample, 1)}%`, 'neutral');
  rowDL(dl, 'Muestra', `${number(result.sample_count, 0)} obs · ${number(result.sample_days, 1)} d${result.sample_is_full_month ? '' : ' (aún no es un mes)'}`, 'neutral');
  rowDL(dl, 'Advertencia', 'Cuenta cuentas, no notional', 'neutral');
}

function renderExecutionCost(result) {
  const body = $('execution-body');
  if (!body) return;
  body.replaceChildren();
  for (const v of safeArray(result.venues)) {
    for (const lado of ['buy', 'sell']) {
      const filas = v[lado];
      const etiqueta = lado === 'buy' ? 'Compra' : 'Venta';
      if (!filas) {
        const tr = document.createElement('tr');
        [[v.exchange, ''], [etiqueta, ''], ['—', ''], ['—', ''], ['—', ''], ['—', ''], [v.status || 'UNAVAILABLE', 'negative']].forEach(x => td(tr, x[0], x[1]));
        body.append(tr);
        continue;
      }
      for (const f of filas) {
        const tr = document.createElement('tr');
        [[v.exchange, ''], [etiqueta, ''],
         [money(f.size_usd, 0), ''],
         [f.avg_price == null ? '—' : money(f.avg_price, 2), ''],
         // Neutro: el slippage por si solo no dice si la operacion sale cara; entra al
         // coste total y ahi se compara contra el objetivo.
         [nd(f.slippage_bps, v2 => `${number(v2, 2)} bps`), 'neutral'],
         [`${f.levels_used}/${f.levels_available}`, ''],
         [f.insufficient_depth ? `Falta ${money(f.shortfall_usd, 0)}` : v.status, f.insufficient_depth ? 'negative' : 'positive']].forEach(x => td(tr, x[0], x[1]));
        body.append(tr);
      }
    }
  }
}

function renderMarketImpact(result) {
  const body = $('impact-body');
  if (!body) return;
  body.replaceChildren();
  for (const w of safeArray(result.windows)) {
    const ctx = w.context || {};
    const tr = document.createElement('tr');
    [[w.window, ''],
     [w.impact_bps_per_musd == null ? 'No evaluable' : `${number(w.impact_bps_per_musd, 3)} bps/M`, 'neutral'],
     [w.net_delta_musd == null ? '—' : `${number(w.net_delta_musd, 2)} M`, 'neutral'],
     [w.price_move_bps == null ? '—' : `${number(w.price_move_bps, 1)} bps`, 'neutral'],
     [ctx.band || 'sin baseline', (ctx.band === 'extremo' || ctx.band === 'alto') ? 'negative' : 'neutral'],
     [`${w.coverage}${w.coverage_complete ? '' : ' (parcial)'}`, w.coverage_complete ? 'estado-ok' : 'estado-aviso']].forEach(x => td(tr, x[0], x[1]));
    tr.title = w.reading || '';
    body.append(tr);
  }
}

function renderQuality(confidence, health) {
  const body = $('quality-body');
  if (!body) return;
  body.replaceChildren();
  for (const svc of safeArray(health.services)) {
    const tr = document.createElement('tr');
    const estado = svc.status || 'N/D';
    const lag = asNumber(svc.lag_seconds);
    // Una latencia DESCONOCIDA no puede pintarse como sana: `|| 0` la hacia pasar por 0 s.
    [[svc.service, ''],
     [estado, estado === 'ok' ? 'estado-ok' : 'estado-malo'],
     [dateTime(svc.updated_at), 'neutral'],
     [lag === null ? 'N/D' : `${number(lag, 1)} s`, lag === null || lag > 120 ? 'estado-aviso' : 'neutral'],
     [svc.detail || '—', 'neutral']].forEach(x => td(tr, x[0], x[1]));
    body.append(tr);
  }
  const rows = safeArray(confidence.rows);
  const row = rows.find(r => r.symbol === state.symbol) || rows[0] || {};
  const pill = $('quality-global');
  if (pill) {
    const score = asNumber(row.quality_score);
    pill.textContent = score === null ? 'Sin dato' : `Calidad ${number(score, 0)} · ${row.status || ''}`;
    // CALIDAD DE DATOS, no direccion. El propio title lo dice: es conectividad de colectores.
    pill.className = `live-pill ${score !== null && score >= 80 ? 'estado-ok' : 'estado-aviso'}`;
    pill.title = 'Conectividad de los colectores, no cobertura de los feeds';
  }
  const errores = $('quality-errors');
  if (errores) {
    errores.replaceChildren();
    const entradas = Object.entries(state.errors || {});
    if (!entradas.length) {
      const p = document.createElement('p');
      p.className = 'tfprofile-note';
      p.textContent = 'Ningún endpoint ha fallado en este ciclo.';
      errores.append(p);
    }
    for (const par of entradas) {
      const p = document.createElement('p');
      p.className = 'tfprofile-note invalida';
      p.textContent = `ERROR · ${par[0]} — ${par[1].message}`;
      errores.append(p);
    }
  }
}

// Calidad de FEEDS: un feed es venue + mercado + tipo de dato, no un proceso interno.
// Los campos que el sistema no puede medir para ese feed se dicen N/D; nunca cero.
const FEED_STATE_CLASS = { OK: 'estado-ok', PARTIAL: 'neutral', STALE: 'estado-aviso', DOWN: 'estado-malo', UNAVAILABLE: 'estado-malo' };
// ESTADO DE UN FEED, no direccion: un feed caido no es una venta.
function renderFeedQuality(result) {
  const body = $('feeds-body');
  if (!body) return;
  body.replaceChildren();
  const filas = safeArray(result.feeds);
  const sub = $('feeds-sub');
  if (sub) {
    const sanos = filas.filter(f => f.status === 'OK').length;
    sub.textContent = filas.length
      ? `${sanos}/${filas.length} feeds OK · ventana ${number(result.window_seconds, 0)} s`
      : 'Sin información de feeds';
  }
  for (const f of filas) {
    const tr = document.createElement('tr');
    const lat = asNumber(f.latency_seconds);
    const cob = asNumber(f.coverage_pct);
    const hueco = asNumber(f.max_internal_gap_seconds);
    const ausentes = safeArray(f.missing_sources);
    td(tr, f.exchange || 'N/D', '');
    td(tr, f.market || 'N/D', '');
    td(tr, f.symbol || 'N/D', '');
    td(tr, f.data_type || 'N/D', '');
    td(tr, f.status || 'N/D', FEED_STATE_CLASS[f.status] || 'neutral');
    td(tr, f.last_ts ? dateTime(f.last_ts) : 'N/D', 'neutral');
    td(tr, lat === null ? 'N/D' : `${number(lat, 1)} s`, 'neutral');
    // Sin cadencia esperada NO hay cobertura que calcular: se dice, no se inventa un 0%.
    td(tr, cob === null ? 'N/D' : `${number(cob, 0)}%`, cob !== null && cob < 90 ? 'estado-aviso' : 'neutral');
    td(tr, f.samples_observed == null ? 'N/D' : number(f.samples_observed, 0), 'neutral');
    td(tr, f.samples_expected == null ? 'N/D' : number(f.samples_expected, 0), 'neutral');
    td(tr, hueco === null ? 'N/D' : `${number(hueco, 0)} s`, 'neutral');
    td(tr, f.missing_sources == null ? 'N/D' : (ausentes.length ? ausentes.join(', ') : 'ninguna'),
      ausentes.length ? 'negative' : 'neutral');
    td(tr, f.last_error || '—', f.last_error ? 'negative' : 'neutral');
    body.append(tr);
  }
}
// Calidad por METRICA: un feed sano no garantiza que la ventana que se apoya en el este
// completa, ni que el basis sea utilizable con las dos patas vivas pero desfasadas.
function renderMetricQuality(result) {
  const body = $('metrics-quality-body');
  if (!body) return;
  body.replaceChildren();
  for (const m of safeArray(result.metrics)) {
    const tr = document.createElement('tr');
    const lat = asNumber(m.latency_seconds);
    const estado = String(m.status || 'UNAVAILABLE');
    td(tr, m.metric, '');
    td(tr, m.timeframe || 'N/D', 'neutral');
    td(tr, estado, FEED_STATE_CLASS[estado] || (estado === 'VALID' ? 'positive' : 'neutral'));
    td(tr, m.coverage == null ? 'N/D' : String(m.coverage), 'neutral');
    td(tr, m.source || 'N/D', 'neutral');
    td(tr, lat === null ? 'N/D' : `${number(lat, 1)} s`, 'neutral');
    body.append(tr);
  }
}

function renderReplay(result) {
  const body = $('replay-body');
  if (!body) return;
  body.replaceChildren();
  for (const r of safeArray(result.rows)) {
    const tr = document.createElement('tr');
    [[r.session_date, ''],
     [r.swing_bias || '—', r.swing_bias === 'LONG' ? 'positive' : r.swing_bias === 'SHORT' ? 'negative' : 'neutral'],
     [r.swing_score == null ? '—' : number(r.swing_score, 1), 'neutral'],
     [r.swing_conviction || '—', 'neutral'],
     [r.regime_label || '—', 'neutral'],
     [r.fwd_return_7s_pct == null ? 'Pendiente' : pct(r.fwd_return_7s_pct), signClass(r.fwd_return_7s_pct)],
     [r.fwd_return_14s_pct == null ? 'Pendiente' : pct(r.fwd_return_14s_pct), signClass(r.fwd_return_14s_pct)]].forEach(x => td(tr, x[0], x[1]));
    body.append(tr);
  }
}

// ---------------------------------------------------------------------------------------
// LA CAPA DE AUDITORIA · #replay
//
// CERO no es CERO DEFECTOS. `maybe` devuelve el fallback cuando la ruta falla, asi que una
// tabla vacia puede significar dos cosas que no se parecen en nada: "no hay filas en la
// ventana" y "no se pudo preguntar". `pedir` las separa, y la banda lo dice con todas las
// letras. Sin esto, un 502 se pinta igual que un mercado tranquilo.
async function pedir(path, fallback) {
  const data = await maybe(path, fallback);
  const fallo = state.errors && state.errors[path];
  return { ok: !fallo, data, error: fallo ? fallo.message : null };
}

// AQUI NO SE AGREGA NADA QUE EL SERVIDOR NO PUBLIQUE. Todo lo que sale en la banda es un
// campo del sobre -count, limit, truncated, since, until, ventana_maxima_h- o el nombre de
// la ruta. El tope se publica desde este mismo commit; antes no se podia decir, porque el
// panel no tenia forma de saber que pedir 48 h no recorta sino que RECHAZA.
function bandaAlcance(nombre, res) {
  if (!res.ok) return `${nombre}: NO SE PUDO PEDIR (${res.error}). Esto no es «no hay datos».`;
  const s = res.data || {};
  const trozos = [`${nombre}: ${s.count == null ? '—' : s.count} filas`];
  if (s.since && s.until) {
    const horas = (new Date(s.until) - new Date(s.since)) / 3600000;
    trozos.push(`ventana pedida ${dateTime(s.since)} → ${dateTime(s.until)} (${number(horas, 2)} h)`);
  } else if (s.servida_desde || s.servida_hasta) {
    trozos.push(`sin ventana de tiempo; lo servido va de ${dateTime(s.servida_desde)} a ${dateTime(s.servida_hasta)}`);
  }
  trozos.push(s.ventana_maxima_h == null
    ? 'sin tope de tiempo: el límite es de filas'
    : `tope ${s.ventana_maxima_h} h — pedir más devuelve 422 y CERO filas, no un recorte`);
  trozos.push(s.truncated === true
    ? `TRUNCADO en ${s.limit} filas: hay más y no se pidieron`
    : `sin truncar (límite ${s.limit == null ? '—' : s.limit})`);
  return trozos.join(' · ');
}

const auditoria = { obs: [], porObs: new Map(), sel: null };

function agrupaPorObs(filas, clave) {
  for (const fila of filas) {
    const id = fila.observation_id;
    if (id == null) continue;
    if (!auditoria.porObs.has(id)) auditoria.porObs.set(id, { frames: [], snapshots: [], certificates: [] });
    auditoria.porObs.get(id)[clave].push(fila);
  }
}

function renderAuditoria(ledger, replay, execution, visibility) {
  const banda = $('auditoria-alcance');
  if (banda) {
    banda.replaceChildren();
    for (const linea of [bandaAlcance('ledger', ledger), bandaAlcance('replay', replay),
                         bandaAlcance('execution', execution), bandaAlcance('visibility', visibility)]) {
      const p = document.createElement('span');
      p.className = 'auditoria-linea';
      p.textContent = linea;
      banda.append(p);
    }
  }
  auditoria.obs = safeArray(ledger.data && ledger.data.observations);
  auditoria.porObs = new Map();
  auditoria.sel = null;
  agrupaPorObs(safeArray(replay.data && replay.data.frames), 'frames');
  agrupaPorObs(safeArray(execution.data && execution.data.snapshots), 'snapshots');
  agrupaPorObs(safeArray(visibility.data && visibility.data.certificates), 'certificates');

  const body = $('auditoria-body');
  if (!body) return;
  body.replaceChildren();
  for (const o of auditoria.obs) {
    const anexos = auditoria.porObs.get(o.observation_id) || { frames: [], snapshots: [], certificates: [] };
    const frame = anexos.frames[0];
    const tr = document.createElement('tr');
    tr.className = 'auditoria-fila';
    tr.tabIndex = 0;
    td(tr, dateTime(o.observed_at), '');
    td(tr, o.direction || '—', o.direction === 'long' ? 'positive' : o.direction === 'short' ? 'negative' : 'neutral');
    // El hash del contexto NO se recalcula aqui: se ensenia el que la ruta publica, cortado
    // para que quepa. Recalcularlo en el navegador seria inventar una segunda verdad.
    td(tr, frame ? `${String(frame.context_hash || '').slice(0, 12) || '—'} v${frame.context_version ?? '—'}` : 'sin frame',
       frame ? 'neutral' : 'negative');
    td(tr, o.logic_version == null ? '—' : String(o.logic_version), 'neutral');
    td(tr, String(anexos.snapshots.length), anexos.snapshots.length ? 'neutral' : 'negative');
    td(tr, String(anexos.certificates.length), anexos.certificates.length ? 'neutral' : 'negative');
    const abre = () => { auditoria.sel = o.observation_id; renderAuditoriaDetalle(); };
    tr.addEventListener('click', abre);
    tr.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); abre(); } });
    body.append(tr);
  }
  renderAuditoriaDetalle();
}

function tabla(destino, titulo, cabeceras, filas) {
  const h4 = document.createElement('h4');
  h4.textContent = titulo;
  destino.append(h4);
  if (!filas.length) {
    const p = document.createElement('p');
    p.className = 'auditoria-vacio';
    p.textContent = 'La ruta no publica ninguna fila para esta observación.';
    destino.append(p);
    return;
  }
  const t = document.createElement('table');
  const thead = document.createElement('thead');
  const trh = document.createElement('tr');
  for (const c of cabeceras) { const th = document.createElement('th'); th.textContent = c; trh.append(th); }
  thead.append(trh); t.append(thead);
  const tb = document.createElement('tbody');
  for (const celdas of filas) { const tr = document.createElement('tr'); for (const c of celdas) td(tr, c, 'neutral'); tb.append(tr); }
  t.append(tb);
  const caja = document.createElement('div');
  caja.className = 'table-scroll';
  caja.append(t);
  destino.append(caja);
}

function renderAuditoriaDetalle() {
  const caja = $('auditoria-detalle');
  if (!caja) return;
  caja.replaceChildren();
  if (auditoria.sel == null) {
    const p = document.createElement('p');
    p.className = 'auditoria-vacio';
    p.textContent = 'Elige una observación de la tabla para reconstruirla.';
    caja.append(p);
    return;
  }
  const anexos = auditoria.porObs.get(auditoria.sel) || { frames: [], snapshots: [], certificates: [] };
  const cab = document.createElement('p');
  cab.className = 'auditoria-linea';
  cab.textContent = `observation_id ${auditoria.sel} · ${anexos.frames.length} frame(s) · ${anexos.snapshots.length} libro(s) · ${anexos.certificates.length} certificado(s)`;
  caja.append(cab);

  // POR QUE SE DIJO · las claves del contexto congelado, sin interpretarlas.
  tabla(caja, 'Con qué entradas se decidió', ['clave', 'valor'],
    anexos.frames.flatMap(f => Object.entries(f.context || {}).map(([k, v]) => [k, typeof v === 'object' ? JSON.stringify(v) : String(v)])));

  // QUE HABRIA COSTADO · una fila por libro. No se elige uno ni se promedian: son varios
  // porque hay varios mercados, y esconder cual es cual seria justo el resumen que sobra.
  tabla(caja, 'Qué habría costado ejecutarla', ['exchange', 'estado', 'spread bps', 'edad libro s', 'mid', 'captado'],
    anexos.snapshots.map(s => [s.exchange || '—', s.status || '—',
      s.spread_bps == null ? 'N/D' : number(s.spread_bps, 2),
      s.book_age_seconds == null ? 'N/D' : number(s.book_age_seconds, 1),
      s.mid_px == null ? 'N/D' : number(s.mid_px, 2), dateTime(s.captured_at)]));

  // LA PUERTA P5 · las dos horas que hay que comparar, publicadas las dos. La comparacion se
  // hace mirando: aqui no se calcula una diferencia que el servidor no publica.
  tabla(caja, '¿El desenlace ya se veía cuando se decidió?', ['horizonte min', 'estado origen', 'finalizado', 'verificado visible'],
    anexos.certificates.map(c => [c.horizon_minutes == null ? '—' : String(c.horizon_minutes),
      c.source_status || '—', dateTime(c.source_finalized_at), dateTime(c.verified_visible_at)]));
}

function renderScalpHistorial(res) {
  const banda = $('scalp-historial-alcance');
  if (banda) banda.textContent = bandaAlcance('scalp/signals', res);
  const body = $('scalp-historial-body');
  if (!body) return;
  body.replaceChildren();
  for (const r of safeArray(res.data && res.data.rows)) {
    const tr = document.createElement('tr');
    td(tr, dateTime(r.ts), '');
    td(tr, r.state || '—', 'neutral');
    td(tr, r.long_score == null ? 'N/D' : number(r.long_score, 2), 'neutral');
    td(tr, r.short_score == null ? 'N/D' : number(r.short_score, 2), 'neutral');
    td(tr, r.confidence == null ? 'N/D' : number(r.confidence, 2), 'neutral');
    td(tr, r.book_status || '—', 'neutral');
    td(tr, r.basis_bps == null ? 'N/D' : number(r.basis_bps, 2), 'neutral');
    td(tr, r.reason || '—', 'neutral');
    body.append(tr);
  }
}

// Valores guardados de la version anterior, cuando hipotesis y setup eran un solo selector.
const LEGACY_HYPOTHESIS = {
  long: ['long', 'ninguno'],
  short: ['short', 'ninguno'],
  neutral: ['neutral', 'ninguno'],
  esperando_ruptura: ['neutral', 'ruptura'],
  esperando_rechazo: ['neutral', 'rechazo'],
  esperando_reversion: ['neutral', 'reversion'],
  esperando_continuacion: ['neutral', 'continuacion'],
};
function initHypothesis() {
  const dirSel = $('direction-select');
  const setupSel = $('setup-select');
  if (!dirSel || !setupSel) return;
  // Si viene un valor viejo en el hash o en el almacenamiento, se traduce al par nuevo en
  // vez de quedarse en un estado que ya no existe.
  const legacy = LEGACY_HYPOTHESIS[state.hypothesis];
  if (legacy) [state.direction, state.setup] = legacy;
  dirSel.value = state.direction;
  setupSel.value = state.setup;
  const onChange = () => {
    state.direction = dirSel.value;
    state.setup = setupSel.value;
    state.lastContextAt = 0;
    refreshOverview(true).catch(error => console.error(error));
  };
  dirSel.addEventListener('change', onChange);
  setupSel.addEventListener('change', onChange);
}

