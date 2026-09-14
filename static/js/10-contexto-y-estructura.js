'use strict';
// barra global, estructura, macro externo, flujo pasivo y zona
// Trozo 10 de 11 del panel. Sale de static/app.js SIN TOCAR UNA LINEA DE LOGICA
// (FASE 2, 2026-09-13): lineas 2760-3623 del fichero original.
// El orden de los <script defer> de index.html ES el orden de este fichero: no se
// reordena nada, porque en scripts clasicos un `const` de primer nivel solo existe a
// partir del script que lo declara.
// Barra global: fuentes vivas, mayor latencia y ultimo error de endpoint.
function renderGlobalBar(health) {
  const services = safeArray(health.services);
  const sanos = services.filter(s => s.status === 'ok').length;
  const fuentes = $('live-sources');
  if (fuentes) {
    fuentes.textContent = `Fuentes ${sanos}/${services.length || 0}`;
    fuentes.className = `live-pill ${services.length && sanos === services.length ? 'estado-ok' : 'estado-malo'}`;
  }
  const lat = $('live-latency');
  if (lat) {
    // Una latencia DESCONOCIDA no es una latencia de 0 s. Antes `|| 0` la hacia pasar por la
    // mejor de todas y la barra mostraba "Lat 0 s" con el servicio mudo.
    const lags = services.map(s => asNumber(s.lag_seconds));
    const medidas = lags.filter(v => v !== null);
    const desconocidas = lags.length - medidas.length;
    const peor = medidas.length ? Math.max(...medidas) : null;
    lat.textContent = peor === null ? 'Lat N/D' : `Lat ${number(peor, 0)} s${desconocidas ? ` (+${desconocidas} N/D)` : ''}`;
    lat.className = `live-pill ${peor === null || desconocidas || peor > 120 ? 'estado-aviso' : 'neutral'}`;
    lat.title = desconocidas ? `${desconocidas} servicio(s) sin latencia publicada` : 'Mayor latencia entre servicios';
  }
  const err = $('live-error');
  if (err) {
    const ultimo = lastEndpointError();
    err.textContent = ultimo ? `Error: ${ultimo.path.split('?')[0]}${ultimo.count > 1 ? ` (+${ultimo.count - 1})` : ''}` : 'Sin errores';
    err.className = `live-pill ${ultimo ? 'estado-malo' : 'neutral'}`;
    err.title = ultimo ? `${ultimo.path} — ${ultimo.message}` : 'Ningún endpoint ha fallado';
  }
}

function renderStructure(result) { const body = $('structure-body'); if (!body) return; body.replaceChildren(); const names = { micro: 'Micro (1m-15m)', mid: 'Mid (30m-4h)', macro: 'Macro (1d-7d)' }; const cls = b => b === 'alcista' ? 'positive' : (b === 'bajista' ? 'negative' : 'neutral'); for (const l of safeArray(result.layers)) { const tr = document.createElement('tr'); const chips = Object.entries(l.components || {}).map(([k, v]) => `${v === true ? '\u25B2' : (v === false ? '\u25BC' : '\u00B7')} ${k}`).join('  '); const ps = l.price_structure || '\u2014'; [[names[l.layer] || l.layer, ''], [`${l.bias} ${l.votes_up}/${l.votes_total}`, cls(l.bias)], [ps, ps === 'HH/HL' ? 'positive' : (ps === 'LH/LL' ? 'negative' : 'neutral')], [chips, 'neutral']].forEach(([v, c]) => td(tr, v, c)); body.append(tr); } const note = document.getElementById('structure-align'); if (note && result.alignment) note.textContent = result.alignment.replace('_', ' '); }

function externalClass(stateName) { return stateName === 'favorable' || stateName === 'alineado' ? 'positive' : stateName === 'restrictivo' || stateName === 'conflicto' || stateName === 'esperar_evento' ? 'negative' : 'neutral'; }
function externalMetricValue(metric) {
  if (metric.value == null) return 'Sin dato';
  const value = metric.key === 'stablecoin_supply_usd' ? money(metric.value, 1)
    : ['treasury_2y', 'real_yield_10y'].includes(metric.key) ? `${number(metric.value, 2)}%`
      : number(metric.value, 2);
  const change = metric.change == null ? 'sin cambio comparable'
    : metric.change_kind === 'bps' ? `${asNumber(metric.change) >= 0 ? '+' : ''}${number(metric.change, 0)} bps` : pct(metric.change, 2);
  return `${value} · ${change}`;
}
function renderExternalMacro(result = {}) {
  const body = $('external-macro-body');
  const sub = $('external-macro-sub');
  const badge = $('external-macro-badge');
  if (!body || !sub || !badge) return;
  body.replaceChildren();
  badge.textContent = result.regime_label || 'Datos insuficientes';
  badge.className = `warning ${externalClass(result.regime)}`;
  sub.textContent = result.as_of
    ? `Corte ${result.as_of} · cobertura ${number(result.coverage_pct, 0)}% · confianza de datos ${result.data_confidence || '—'}`
    : 'Esperando primera actualización de fuentes externas';
  if (!result.available) {
    const empty = document.createElement('p');
    empty.className = 'zone-empty';
    empty.textContent = safeArray(result.limitations)[0] || 'Aún no hay cobertura suficiente para clasificar el régimen.';
    body.append(empty);
    return;
  }

  const hero = document.createElement('div');
  hero.className = 'external-macro-hero';
  const regime = document.createElement('div');
  regime.className = 'external-regime';
  const regimeKicker = document.createElement('span');
  regimeKicker.textContent = 'Filtro de varias sesiones';
  const regimeValue = document.createElement('strong');
  regimeValue.className = externalClass(result.regime);
  regimeValue.textContent = result.regime_label;
  const regimeNote = document.createElement('small');
  regimeNote.textContent = 'Contexto, no gatillo de entrada ni probabilidad.';
  regime.append(regimeKicker, regimeValue, regimeNote);

  const alignment = result.alignment || {};
  const alignmentNode = document.createElement('div');
  alignmentNode.className = 'external-alignment';
  const alignmentTitle = document.createElement('strong');
  alignmentTitle.className = externalClass(alignment.state);
  alignmentTitle.textContent = alignment.state === 'alineado' ? 'Macro e impulso alineados'
    : alignment.state === 'conflicto' ? 'Conflicto de horizonte'
      : alignment.state === 'esperar_evento' ? 'Esperar evento macro' : 'Confirmación parcial';
  const alignmentText = document.createElement('p');
  alignmentText.textContent = alignment.reading || 'Sin evaluación de alineación.';
  const alignmentMeta = document.createElement('small');
  alignmentMeta.textContent = `Sesgo interno ${alignment.internal_bias || '—'} · fuente actualizada ${dateTime(result.fetched_at)}`;
  alignmentNode.append(alignmentTitle, alignmentText, alignmentMeta);
  hero.append(regime, alignmentNode);
  body.append(hero);

  const pillars = document.createElement('div');
  pillars.className = 'external-pillars';
  for (const pillar of Object.values(result.pillars || {})) {
    const node = document.createElement('article');
    node.className = `external-pillar ${externalClass(pillar.state)}`;
    const stateLabel = document.createElement('span');
    stateLabel.textContent = pillar.state;
    const title = document.createElement('h4');
    title.textContent = pillar.label;
    const narrative = document.createElement('p');
    narrative.textContent = pillar.narrative;
    node.append(stateLabel, title, narrative);
    for (const metric of safeArray(pillar.metrics)) {
      const row = document.createElement('div');
      row.className = 'external-metric';
      const label = document.createElement('span');
      label.textContent = metric.label;
      const value = document.createElement('strong');
      value.className = externalClass(metric.state);
      value.textContent = externalMetricValue(metric);
      row.append(label, value);
      node.append(row);
    }
    pillars.append(node);
  }
  body.append(pillars);

  const details = document.createElement('div');
  details.className = 'external-details';
  const institutional = result.institutional_flows || {};
  const etf = document.createElement('article');
  etf.className = 'external-detail';
  const etfKicker = document.createElement('span');
  etfKicker.textContent = 'Flujo institucional BTC';
  const etfValue = document.createElement('strong');
  etfValue.className = institutional.available ? signClass(institutional.flow_5d_usd) : 'neutral';
  etfValue.textContent = institutional.available
    ? `ETF 1d ${money(institutional.flow_1d_usd)} · 5d ${money(institutional.flow_5d_usd)} · 20d ${money(institutional.flow_20d_usd)}`
    : 'Feed ETF opcional no conectado';
  const etfText = document.createElement('p');
  etfText.textContent = institutional.interpretation || 'Sin lectura institucional.';
  etf.append(etfKicker, etfValue, etfText);

  const eventRisk = result.event_risk || {};
  const event = document.createElement('article');
  event.className = 'external-detail';
  const eventKicker = document.createElement('span');
  eventKicker.textContent = `Riesgo de evento · ${eventRisk.level || '—'}`;
  const eventValue = document.createElement('strong');
  eventValue.className = ['alto', 'elevado'].includes(eventRisk.level) ? 'estado-aviso' : 'neutral';
  const next = eventRisk.next_event;
  eventValue.textContent = next ? `${next.title} · ${dateTime(next.event_at)}` : 'Sin evento próximo registrado';
  const eventText = document.createElement('p');
  eventText.textContent = eventRisk.narrative || 'Sin calendario disponible.';
  event.append(eventKicker, eventValue, eventText);
  details.append(etf, event);
  body.append(details);

  const limitations = safeArray(result.limitations);
  if (limitations.length) {
    const note = document.createElement('p');
    note.className = 'external-limit';
    note.textContent = `${limitations.join(' ')} Fuentes: ${safeArray(result.sources).join(' · ')}.`;
    body.append(note);
  }
}

function renderMacro(result) { const body = $('macro-body'); if (!body) return; body.replaceChildren(); const cls = r => (r.indexOf('extremo') === 0) ? (r.indexOf('alto') >= 0 ? 'positive' : 'negative') : 'neutral'; for (const m of safeArray(result.metrics)) { const tr = document.createElement('tr'); const pval = m.percentile == null ? '\u2014' : (number(m.percentile, 0) + '%'); [[m.label, ''], [m.value == null ? '\u2014' : number(m.value, 2), 'neutral'], [pval, cls(m.regime)], [m.regime, cls(m.regime)]].forEach(([v, c]) => td(tr, v, c)); body.append(tr); } const sub = document.getElementById('macro-sub'); if (sub) sub.textContent = result.sessions ? ('percentil vs ' + result.sessions + ' sesiones \u00b7 tensi\u00f3n ' + (result.tension || 0)) : 'sin historia'; }

// La columna mostraba el diferencial spot-futuros con color por signo, que es el CVD de
// futuros invertido en ~93% de los casos. Ahora muestra el estado de las dos patas.
const PASSIVE_FLOW = {
  spot_y_futuros_compran: ['Ambas compran', 'positive'],
  spot_y_futuros_venden: ['Ambas venden', 'negative'],
  spot_compra_futuros_vende: ['Spot compra / Fut vende', 'neutral'],
  spot_vende_futuros_compra: ['Spot vende / Fut compra', 'neutral'],
  una_pata_plana: ['Una pata plana', 'neutral'],
  sin_datos: ['—', 'neutral'],
};
function renderPassive(result) { const body = $('passive-body'); if (!body) return; body.replaceChildren(); const cls = r => r === 'reacumulacion_silenciosa' ? 'positive' : (r === 'redistribucion_silenciosa' ? 'negative' : 'neutral'); const lbl = { reacumulacion_silenciosa: 'Reacum. silenciosa', redistribucion_silenciosa: 'Redistrib. silenciosa', neutral: '\u2014' }; for (const [hz, h] of Object.entries(result.horizons || {})) { const tr = document.createElement('tr'); [[hz, ''], [lbl[h.reading] + (h.confidence && h.reading !== 'neutral' ? ' (' + h.confidence + ')' : ''), cls(h.reading)], [h.absorption, h.absorption === 'ventas' ? 'positive' : (h.absorption === 'compras' ? 'negative' : 'neutral')], PASSIVE_FLOW[h.flow_state] || ['—', 'neutral'], [h.price_move_pct == null ? 's/d' : number(h.price_move_pct, 2) + '%', h.price_move_pct == null ? 'neutral' : signClass(h.price_move_pct)]].forEach(([v, c]) => td(tr, v, c)); body.append(tr); } const sub = document.getElementById('passive-sub'); if (sub) sub.textContent = (result.summary && result.summary !== 'neutral') ? (lbl[result.summary] + ' \u00b7 en ' + (result.location || 's/d')) : ('neutral \u00b7 ' + (result.location || 's/d')); }

// ---------------- Lectura de zona (fase 1) ----------------
// A diferencia del resto de paneles esto NO entra en el refresh de 15 s: el veredicto es de
// un tramo historico fijo, recalcularlo cada ciclo solo gastaria consultas.
const ZONE_LABEL = {
  acumulacion: ['Acumulación', 'positive'],
  distribucion: ['Distribución', 'negative'],
  sin_caracter: ['Sin carácter definido', 'neutral'],
  sin_datos: ['Sin datos suficientes', 'neutral'],
};
const ZONE_COMP_LABEL = {
  esfuerzo_resultado: 'Esfuerzo agresivo vs desplazamiento',
  cvd_spot: 'CVD spot de la zona',
  open_interest: 'Open interest',
  funding: 'Funding',
  rechazos: 'Cierres dentro de la barra',
};

function clearZone() {
  const body = $('zone-body');
  if (body) body.replaceChildren();
  const sub = $('zone-sub');
  if (sub) sub.textContent = 'Acumulación · distribución · rotación';
}

function zoneEmpty(text) {
  const body = $('zone-body');
  if (!body) return;
  const div = document.createElement('div');
  div.className = 'zone-empty';
  div.textContent = text;
  body.replaceChildren(div);
}

function renderZone(result) {
  const body = $('zone-body');
  if (!body) return;
  body.replaceChildren();
  const visits = safeArray(result.visits);
  if (!visits.length) {
    zoneEmpty('El precio no visitó esa zona en el periodo consultado.');
    return;
  }
  for (const visit of visits) {
    const card = document.createElement('article');
    card.className = 'zone-visit';

    if (!visit.available) {
      const head = document.createElement('div');
      head.className = 'zone-verdict neutral';
      head.textContent = 'Visita sin veredicto';
      const why = document.createElement('div');
      why.className = 'zone-meta';
      why.textContent = visit.reason || 'Cobertura insuficiente.';
      card.append(head, why);
      body.append(card);
      continue;
    }

    const [label, cls] = ZONE_LABEL[visit.character] || ['—', 'neutral'];
    const head = document.createElement('div');
    head.className = `zone-verdict ${cls}`;
    head.textContent = `${label} · ${visit.strength} · confianza ${visit.confidence}`;

    const meta = document.createElement('div');
    meta.className = 'zone-meta';
    meta.textContent = `${visit.from} → ${visit.to} · score ${number(visit.score, 0)}/100 · `
      + `evidencia medible ${number(visit.evidence_coverage_pct, 0)}% · `
      + `${visit.bars_4h} barras 4h · ${visit.sessions} sesiones`;
    card.append(head, meta);

    const evi = document.createElement('div');
    evi.className = 'zone-evi';
    for (const line of safeArray(visit.narrative)) {
      const row = document.createElement('div');
      row.className = 'zone-evi-line';
      const ico = document.createElement('span');
      ico.className = 'zone-evi-ico neutral';
      ico.textContent = '·';
      const text = document.createElement('span');
      text.textContent = line;
      row.append(ico, text);
      evi.append(row);
    }
    card.append(evi);

    const comps = document.createElement('div');
    comps.className = 'zone-comp';
    for (const c of safeArray(visit.components)) {
      const row = document.createElement('div');
      row.className = 'zone-comp-row';
      const name = document.createElement('span');
      name.className = 'zone-comp-name';
      name.textContent = (ZONE_COMP_LABEL[c.key] || c.label || c.key)
        + (c.status === 'unavailable' ? ' · sin dato' : '');
      const value = document.createElement('span');
      // Un componente sin dato muestra guion, nunca 0: un 0 se leeria como "medido y neutral".
      value.className = c.status === 'unavailable' ? 'neutral' : signClass(c.contribution);
      value.textContent = c.status === 'unavailable'
        ? '—'
        : `${c.contribution > 0 ? '+' : ''}${number(c.contribution, 1)} / ${number(c.weight, 0)}`;
      row.append(name, value);
      comps.append(row);
    }
    card.append(comps);

    const missing = safeArray((visit.method || {}).unavailable);
    if (missing.length) {
      const note = document.createElement('div');
      note.className = 'zone-missing';
      note.textContent = `No se pudo medir: ${missing.map(k => ZONE_COMP_LABEL[k] || k).join(', ')}. `
        + 'El score se reparte solo entre los componentes medibles.';
      card.append(note);
    }
    if (visit.warning) {
      const warn = document.createElement('div');
      warn.className = 'zone-missing';
      warn.textContent = visit.warning;
      card.append(warn);
    }
    body.append(card);
  }
  const sub = $('zone-sub');
  if (sub) {
    const scored = asNumber(result.scored_visits) || 0;
    sub.textContent = scored > 1 && String(result.summary).startsWith('La zona no')
      ? `${visits.length} visitas · carácter distinto entre ellas`
      : `${visits.length} visita(s) en ${result.lookback_days} días`;
  }
}

async function submitZone(event) {
  if (event) event.preventDefault();
  const low = asNumber(($('zone-low') || {}).value);
  const high = asNumber(($('zone-high') || {}).value);
  if (low === null || high === null || low <= 0 || high <= low) {
    zoneEmpty('Introduce dos precios válidos, con el inferior por debajo del superior.');
    return;
  }
  zoneEmpty('Analizando…');
  const query = `symbol=${encodeURIComponent(state.symbol)}&low=${low}&high=${high}`;
  const result = await maybe(`/api/zone/analysis?${query}`, null);
  if (!result) {
    zoneEmpty('No se pudo calcular la zona. Revisa el panel de salud de datos.');
    return;
  }
  renderZone(result);
}

// ═══ PORTADA, COSTE Y LOS TRES HEATMAPS ═════════════════════════════════════════════════════
// El eje del panel pasa de la SEÑAL al COSTE. Para dias-a-semanas en perpetuos el funding no es
// un indicador de sentimiento: es el gasto, y se paga tres veces al dia se mire o no.
//
// NO HAY SUPERFICIE DE SEÑAL NUEVA AQUI. Ni una regla de entrada, ni una puntuacion, ni una
// probabilidad de que algo continue. Todo lo que se pinta ya lo calculaba una ruta.

// La ventana por defecto de la portada: SIETE DIAS, porque el horizonte declarado es
// dias-a-semanas. Se echa el instante que se uso, para que la lectura se pueda repetir.
const PORTADA_DIAS = 7;
// El inicio se ALINEA al minuto: una ventana que empieza en un instante con segundos no se
// puede volver a pedir igual, y entonces la portada no es auditable.
function desdePortada() {
  const d = new Date(Date.now() - PORTADA_DIAS * 86400000);
  d.setSeconds(0, 0);
  return d.toISOString();
}

function textoEn(id, texto, clase) {
  const el = $(id);
  if (!el) return;
  el.textContent = texto;
  if (clase !== undefined) el.className = clase;
}

// Un hueco NO es un cero. Cuando una celda no tiene dato se pinta vacia y se marca, para que
// nadie la lea como «ese dia no se pago funding»: no se midio, que es otra cosa.
function celdaHeat(valor, escala, sufijo, factor) {
  const div = document.createElement('div');
  div.className = 'heat-celda';
  if (valor === null || valor === undefined || valor.pct_8h === undefined && valor.chg_pct === undefined) {
    div.classList.add('heat-vacia');
    div.textContent = '';
    div.title = 'sin dato medido en esa sesión — no es un cero';
    return div;
  }
  const v = valor.pct_8h !== undefined ? valor.pct_8h : valor.chg_pct;
  const f = escala > 0 ? Math.max(-1, Math.min(1, v / escala)) : 0;
  div.style.background = f >= 0
    ? `rgba(47,213,138,${(0.10 + 0.55 * f).toFixed(3)})`
    : `rgba(255,105,120,${(0.10 + 0.55 * -f).toFixed(3)})`;
  // Se PINTA escalado -el FUNDING en milesimas de % por 8 h; el de OI entra con factor 1 y no
  // se escala- para que quepan pocos caracteres. El dato no cambia: el `title` lleva el valor
  // crudo con su unidad.
  //
  // DOS DECIMALES POR DEBAJO DE 10, Y NO UNO. Con uno, dias que valen cosas distintas se
  // pintaban con el MISMO texto. Medido el 2026-09-09 sobre el payload real de /api/carry/matriz
  // (15 dias x 3 simbolos = 45 celdas con dato en cada mapa):
  //     un decimal  -> funding 6 pares indistinguibles · OI 10
  //     dos         -> funding 0                       · OI  2
  // Se eligio DOS y no TRES a sabiendas: tres deja OI en 4 pares -no en 0- y cuesta un caracter
  // en TODAS las celdas. LO QUE SE SACRIFICA, dicho: sobreviven 2 pares en el mapa de OI, dias
  // que difieren en menos de 0.005 puntos porcentuales. Por encima de 10 se siguen pintando 0
  // decimales, que es lo que conserva el ancho cuando hay un pico.
  //
  // Y UN VALOR QUE NO ES CERO NO SE PINTA COMO UN CERO. Con un decimal, un funding de
  // -0.000025 % por 8 h salia «-0.0»: un cero pintado donde no hay un cero es una afirmacion
  // falsa sobre el mercado, no un redondeo. Ahora sale «≈0» y el signo lo sigue diciendo el
  // color de fondo, que ya lo decia. El crudo sigue entero en el `title`.
  const pintado = v * (factor || 1);
  const texto = pintado === 0 ? '0'
    : (Math.abs(pintado) >= 10 ? pintado.toFixed(0) : pintado.toFixed(2));
  div.textContent = Number(texto) === 0 && pintado !== 0 ? '≈0' : texto;
  div.title = `${v}${sufijo} sobre ${valor.muestras} muestras de 5 min`
    + (valor.completo ? '' : ' — DIA INCOMPLETO');
  if (!valor.completo) div.classList.add('heat-parcial');
  return div;
}

function pintaHeat(idCaja, filas, simbolos, campo, sufijo, factor) {
  const caja = $(idCaja);
  if (!caja) return { vacias: 0, total: 0 };
  caja.replaceChildren();
  const vals = [];
  for (const f of filas) for (const s of simbolos) {
    const v = f.valores[s];
    if (v) vals.push(Math.abs(v[campo]));
  }
  // La escala sale del percentil 90 de lo que HAY, no de un maximo fijo: un maximo inventado
  // pintaria de un color u otro segun el mes.
  vals.sort((a, b) => a - b);
  const escala = vals.length ? (vals[Math.floor(vals.length * 0.9)] || vals[vals.length - 1]) : 0;
  const tabla = document.createElement('div');
  tabla.className = 'heat-rejilla';
  // `minmax(min-content, 1fr)` y NO `minmax(0, 1fr)`: el cero es el permiso para que la
  // columna encoja por debajo de su contenido, y con `text-overflow: ellipsis` eso corta el
  // numero. `min-content` no es un ancho ajustado a la letra de hoy: es la primitiva que dice
  // «nunca mas estrecho que lo que hay dentro», asi que sigue valiendo si el texto crece. Si aun
  // asi no cabe, `.heatmap` se desplaza (overflow-x: auto).
  //
  // ESTA LINEA DECIA «cuando se corta, celdas que valen cosas distintas se ven iguales y el
  // heatmap deja de poder leerse», y era CIERTA DEL RECORTE Y FALSA DEL REDONDEO. Quien la leia
  // entendia que arreglado el recorte ya no habia dos celdas iguales, y no es lo que pasa: son
  // dos propiedades distintas y esta columna solo cierra una. Medido el 2026-09-09 con chromium
  // sobre la rejilla real: CERO celdas recortadas -o sea que esta parte funciona- y aun asi 16
  // pares de dias con valores distintos pintados con el mismo texto, 6 en funding y 10 en OI.
  // El recorte lo cierra este `min-content`; el redondeo lo cierra el formato de celdaHeat.
  tabla.style.gridTemplateColumns = `72px repeat(${filas.length}, minmax(min-content, 1fr))`;
  const cab = document.createElement('div');
  cab.className = 'heat-cab';
  tabla.append(cab);
  for (const f of filas) {
    const d = document.createElement('div');
    d.className = 'heat-cab';
    d.textContent = f.fecha.slice(5);
    tabla.append(d);
  }
  let vacias = 0, total = 0;
  for (const s of simbolos) {
    const et = document.createElement('div');
    et.className = 'heat-etiqueta';
    et.textContent = s.replace('USDT_PERP.A', '');
    tabla.append(et);
    for (const f of filas) {
      total++;
      const v = f.valores[s];
      if (!v) vacias++;
      tabla.append(celdaHeat(v, escala, sufijo, factor));
    }
  }
  caja.append(tabla);
  return { vacias, total };
}


function renderCarry(m) {
  if (!m || !m.coste) return;
  const cuerpo = $('carry-body');
  if (cuerpo) {
    cuerpo.replaceChildren();
    for (const c of m.coste) {
      const tr = document.createElement('tr');
      // El coste se pinta en el vocabulario de ESTADO y no en el de direccion: pagar mas no es
      // «bajista». Es gasto.
      const cel = (txt, cls) => { const td = document.createElement('td'); td.textContent = txt; if (cls) td.className = cls; tr.append(td); };
      cel(c.symbol.replace('USDT_PERP.A', ''));
      cel(c.por_8h === null ? 'NO MEDIDO' : `${c.por_8h.toFixed(5)} %`);
      cel(c.a_7d === null ? '—' : `${c.a_7d.toFixed(3)} %`);
      cel(c.a_30d === null ? '—' : `${c.a_30d.toFixed(3)} %`, 'carry-destacado');
      cel(c.anual === null ? '—' : `${c.anual.toFixed(2)} %`);
      cel(c.quien_paga);
      cel(String(c.dias_promediados));
      cuerpo.append(tr);
    }
  }
  // LA VENTANA QUE SE SIRVE, no la que se pidio, y en la propia tarjeta.
  const servido = `${m.dias_servidos} de ${m.dias_pedidos} días · ${m.desde || '—'} a ${m.hasta || '—'}`;
  textoEn('carry-sub', servido);
  textoEn('carry-note', `${m.unidades}. ${m.cobertura.nota} `
    + 'Sin componer: el funding se cobra sobre el nocional, no sobre el beneficio.');

  const simbolos = m.simbolos || [];
  // MILESIMAS DE % POR 8 H, y rotulado en el encabezado, en la ventana y en cada celda.
  const f = pintaHeat('heat-funding', m.funding_por_dia || [], simbolos, 'pct_8h',
                      ' % por 8 h', 1000);
  textoEn('heat-funding-sub', `milésimas de % por 8 h · ${servido}`);
  textoEn('heat-funding-note',
    `Cada celda es el funding medio del día en MILÉSIMAS DE % POR PERÍODO DE 8 H: «6.74» son `
    + `0.00674 %. «≈0» es un valor distinto de cero que redondea a cero, no un cero. `
    + `El valor crudo está en el título de cada celda. `
    + `${f.total - f.vacias} de ${f.total} celdas con dato; `
    + `${f.vacias} sin medir, y van vacías —no a cero—. Verde: pagan los largos.`);

  // El de OI NO se escala: sus valores ya son cortos y estan en % de verdad.
  const o = pintaHeat('heat-oi', m.oi_por_dia || [], simbolos, 'chg_pct', ' %', 1);
  textoEn('heat-oi-sub', `% de cambio · ${servido}`);
  textoEn('heat-oi-note',
    `Cambio de apertura a cierre de sesión. ${o.total - o.vacias} de ${o.total} celdas con dato; `
    + `${o.vacias} sin medir. Verde: se montan posiciones.`);
}

// EL TERCER HEATMAP no se construyo: /api/liquidation-map ya lo servia y su propio docstring ya
// decia que NO es un mapa proyectado. Aqui solo se le sube el sitio y se rotula su ventana.
function renderLiqPrecio(mapa) {
  const caja = $('heat-liq');
  if (!caja) return;
  caja.replaceChildren();
  if (!mapa || mapa.available === false) {
    textoEn('heat-liq-sub', 'NO MEDIDO');
    textoEn('heat-liq-note', 'La ruta no pudo servir el mapa en este ciclo.');
    return;
  }
  const filas = safeArray(mapa.levels);
  const ventana = mapa.window_minutes;
  // LA VENTANA QUE SIRVE, no la que se pidio: el diseño hablaba de 24 h y la ruta sirve 180
  // min. Ademas `liquidations_realtime` solo guarda 12.2 h, asi que rotular «24 h» seria
  // falso por partida doble. Se rotula lo que llega.
  textoEn('heat-liq-sub', ventana ? `últimas ${ventana} min · precio ${money(asNumber(mapa.current_price), 0)}`
                                  : 'ventana declarada por la ruta');
  if (!filas.length) {
    textoEn('heat-liq-note', 'Sin liquidaciones en la ventana servida. Es una lectura, no un hueco: '
      + 'la ruta contestó y no hubo eventos.');
    return;
  }
  const max = Math.max(...filas.map(f => Math.abs(asNumber(f.long_liq) || 0) + Math.abs(asNumber(f.short_liq) || 0)));
  const rej = document.createElement('div');
  rej.className = 'heat-precio-rejilla';
  for (const f of filas) {
    const l = asNumber(f.long_liq) || 0, s = asNumber(f.short_liq) || 0;
    const fila = document.createElement('div');
    fila.className = 'heat-precio-fila';
    const px = document.createElement('span');
    px.className = 'heat-precio-nivel';
    // `money()` ABREVIA -\$79.7K- y con cubos de 79 USD los doce niveles salian como dos
    // etiquetas repetidas: medido, 12 niveles y 2 textos distintos. La tarjeta existe para
    // decir EN QUE NIVEL revento, asi que aqui hace falta el numero entero.
    px.textContent = number(asNumber(f.price), 0);
    const barra = document.createElement('span');
    barra.className = 'heat-precio-barra';
    const bl = document.createElement('i');
    bl.className = 'heat-precio-long';
    bl.style.width = `${max ? (100 * l / max).toFixed(1) : 0}%`;
    const bs = document.createElement('i');
    bs.className = 'heat-precio-short';
    bs.style.width = `${max ? (100 * s / max).toFixed(1) : 0}%`;
    barra.append(bl, bs);
    fila.append(px, barra);
    fila.title = `${money(l, 0)} de largos y ${money(s, 0)} de cortos reventados en este nivel`;
    rej.append(fila);
  }
  caja.append(rej);
  // La nota la escribe la RUTA. Reescribirla con mis palabras seria arriesgarme a decir
  // algo distinto de lo que mide.
  textoEn('heat-liq-note',
    `${filas.length} de ${mapa.buckets_total} niveles con liquidaciones. ${mapa.note || ''}`);
}

function renderPortada(res, matriz) {
  // LA TASA BASE SUBE, y se pinta aunque el veredicto no haya llegado: es lo que menos deberia
  // depender de que otra cosa conteste. Se leen los MISMOS campos que la tarjeta de siempre
  // (dashboard.signal_base_rate); aqui no se recalcula ni se reinterpreta nada.
  const tb = (state.dashboard || {}).signal_base_rate || {};
  textoEn('portada-tasa', tb.available
    ? `Lo que está medido que vale la señal: ventaja neta ${pct(tb.ventaja_neta_pct, 4)}`
      + (tb.t_neta === null || tb.t_neta === undefined ? '' : ` (t ${number(tb.t_neta, 2)})`)
      + ` sobre ${number(tb.n_efectiva, 0)} bloques distintos.`
      + ' Ninguna regla de entrada de esta pantalla se apoya en ella.'
    : 'La tasa base de la señal NO se pudo medir en este ciclo.');
  if (!res) return;
  const v = res.veredicto || {};
  const pruebas = safeArray(res.pruebas);
  const votan = pruebas.filter(p => p.vota).length;
  const nombre = (TRAMO_NOMBRE[v.estructura] || [String(v.estructura || '—'), 'neutral']);
  textoEn('portada-veredicto', nombre[0], `zone-verdict ${nombre[1]}`);
  const w = res.ventana || {};
  textoEn('portada-ventana', `${w.desde || '—'} → ${w.hasta || '—'}`
    + (res.fin_abierto ? ' · fin abierto' : ' · fin fijo'));
  // EL DENOMINADOR VA ARRIBA, no en una nota: «5 de 6» y «3 de 6» son veredictos distintos.
  textoEn('portada-porque', `Votaron ${votan} de ${pruebas.length} pruebas. ${v.porque || ''}`);

  const cifra = (clave) => pruebas.find(p => p.prueba === clave) || {};
  const precio = cifra('progreso_precio'), oi = cifra('interes_abierto'), liq = cifra('liquidaciones');
  textoEn('portada-precio', (w.precio_pct === null || w.precio_pct === undefined) ? 'NO MEDIDO' : `${w.precio_pct > 0 ? '+' : ''}${w.precio_pct} %`,
    `portada-valor ${w.precio_pct > 0 ? 'positive' : w.precio_pct < 0 ? 'negative' : 'neutral'}`);
  textoEn('portada-precio-pie', precio.cifra || `sobre ${w.velas_1min || 0} velas de 1 min`);
  textoEn('portada-oi', (w.oi_pct === null || w.oi_pct === undefined) ? 'NO MEDIDO' : `${w.oi_pct > 0 ? '+' : ''}${w.oi_pct} %`,
    `portada-valor ${w.oi_pct > 0 ? 'positive' : w.oi_pct < 0 ? 'negative' : 'neutral'}`);
  textoEn('portada-oi-pie', oi.cifra || `sobre ${w.muestras_oi || 0} muestras`);

  const c = matriz && safeArray(matriz.coste).find(x => x.symbol === state.symbol);
  textoEn('portada-carry', !c || c.a_30d === null ? 'NO MEDIDO' : `${c.a_30d.toFixed(3)} %`, 'portada-valor');
  textoEn('portada-carry-pie', !c || c.a_30d === null
    ? 'sin días medidos de funding'
    : `${c.quien_paga} · ${c.por_8h.toFixed(5)} % por 8 h sobre ${c.dias_promediados} días`);

  textoEn('portada-liq', liq.cifra ? liq.cifra.split(' sobre ')[0] : 'NO MEDIDO', 'portada-valor');
  textoEn('portada-liq-pie', liq.cifra ? liq.cifra.split(' sobre ').slice(1).join(' sobre ') : '');

  // LA CAPA DE HONESTIDAD, ARRIBA Y NO ABAJO. Es el mejor activo del producto.
  const mudas = pruebas.filter(p => !p.vota);
  // La frase de «no es predicción» la pone la RUTA. Yo solo añado lo que la ruta no sabe: qué
  // pruebas se quedaron sin medir. Repetir su frase con otras palabras sería ruido justo en la
  // línea que más importa.
  textoEn('portada-honestidad',
    (v.no_es_prediccion || '')
    + (mudas.length
        ? ` · ${mudas.length} de ${pruebas.length} prueba(s) NO se pudieron medir: `
          + mudas.map(p => `${p.prueba.replace(/_/g, ' ')} (${p.no_vota_porque || 'sin motivo declarado'})`).join(' · ')
        : ' · las ' + pruebas.length + ' pruebas se pudieron medir.'));
}

// ---------------- Que estructura estaba ocurriendo en un tramo ----------------
// NO ES SUPERFICIE DE SENAL. Es LECTURA de lo que ya paso: no hay regla de entrada, ni
// puntuacion, ni «probabilidad de que continue». La respuesta es un NOMBRE y sus pruebas.
//
// Y tiene que poder decir NINGUNA. Un veredicto que siempre elige una de las opciones que
// sabe nombrar no esta leyendo: esta repartiendo.
// Los mismos tres tonos que ya usa el analizador de zona (ZONE_LABEL): no hay clase nueva.
const TRAMO_TONO = {
  distribucion: 'negative', bajista: 'negative',
  acumulacion: 'positive', alcista: 'positive',
  cierre: 'neutral', posicionamiento: 'neutral',
};
const TRAMO_NOMBRE = {
  compatible_con_distribucion: ['Compatible con distribución', 'negative'],
  compatible_con_acumulacion: ['Compatible con acumulación', 'positive'],
  desapalancamiento: ['Desapalancamiento', 'negative'],
  equilibrio_sin_ventaja: ['Equilibrio sin ventaja', 'neutral'],
  ninguna: ['NINGUNA de las que la casa sabe nombrar', 'neutral'],
};
function tramoEmpty(text) {
  const body = $('tramo-body');
  if (!body) return;
  const div = document.createElement('div');
  div.className = 'zone-empty';
  div.textContent = text;
  body.replaceChildren(div);
}
function tramoLinea(padre, clase, texto) {
  const div = document.createElement('div');
  div.className = clase;
  div.textContent = texto;
  padre.append(div);
  return div;
}
// Un instante local escrito por el operador se manda con su desfase real, no «como si» fuese
// UTC: la ventana del viernes es 09:30Z y confundir la zona la mueve horas enteras.
function tramoISO(valor) {
  if (!valor) return null;
  const d = new Date(valor);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}
function renderTramo(res) {
  const body = $('tramo-body');
  if (!body) return;
  body.replaceChildren();
  const v = res.veredicto || {};
  const pruebas = safeArray(res.pruebas);
  const votan = pruebas.filter(p => p.vota);
  const ventana = res.ventana || {};

  const card = document.createElement('article');
  card.className = 'zone-visit';
  const [nombre, cls] = TRAMO_NOMBRE[v.estructura] || [String(v.estructura || '—'), 'neutral'];
  tramoLinea(card, `zone-verdict ${cls}`, nombre);
  // `fin_abierto` viene en la RAIZ de la respuesta, no dentro de `ventana`. Leerlo del sitio
  // equivocado no rompe nada: simplemente el aviso no sale nunca, que es peor.
  tramoLinea(card, 'zone-meta', `${ventana.desde || '—'} → ${ventana.hasta || '—'}`
    + (res.fin_abierto ? ' · fin abierto: este es el instante que se usó' : ' · fin fijo: auditable')
    + ' · contra el tramo anterior de igual duración');
  // EL DENOMINADOR VA DELANTE, no en una nota al pie: «5 de 6» y «3 de 6» son veredictos
  // distintos aunque salga el mismo nombre.
  tramoLinea(card, 'zone-meta', `Votaron ${votan.length} de ${pruebas.length} pruebas`);
  if (v.porque) tramoLinea(card, 'zone-meta', v.porque);
  body.append(card);

  // UNA POR UNA, y a favor de que vota cada una. Las que no se pudieron medir dicen por que:
  // un hueco relleno con un cero es la forma mas barata de que una prueba ausente parezca una
  // prueba en contra.
  for (const p of pruebas) {
    const fila = document.createElement('article');
    fila.className = 'zone-visit';
    const tono = p.vota ? (TRAMO_TONO[p.vota] || 'neutral') : 'neutral';
    tramoLinea(fila, `zone-verdict ${tono}`,
      `${String(p.prueba || '').replace(/_/g, ' ')} · ${p.vota ? `vota ${p.vota}` : 'NO VOTA'}`);
    if (p.dice) tramoLinea(fila, 'zone-meta', p.dice);
    if (!p.vota) {
      tramoLinea(fila, 'zone-meta', p.no_vota_porque || 'no se pudo medir en esta ventana');
    }
    body.append(fila);
  }
  // NO ES UNA PREDICCION, y se dice con las mismas letras que el resto.
  if (v.no_es_prediccion) {
    const pie = document.createElement('div');
    pie.className = 'zone-empty';
    pie.textContent = v.no_es_prediccion;
    body.append(pie);
  }
}
async function submitTramo(event) {
  if (event) event.preventDefault();
  const desde = tramoISO(($('tramo-desde') || {}).value);
  const hasta = tramoISO(($('tramo-hasta') || {}).value);
  if (!desde) { tramoEmpty('Introduce al menos el instante inicial.'); return; }
  if (hasta && hasta <= desde) { tramoEmpty('El final tiene que ser posterior al inicio.'); return; }
  tramoEmpty('Leyendo el tramo…');
  let query = `symbol=${encodeURIComponent(state.symbol)}&desde=${encodeURIComponent(desde)}`;
  if (hasta) query += `&hasta=${encodeURIComponent(hasta)}`;
  const res = await maybe(`/api/rango/estructura?${query}`, null);
  if (!res) { tramoEmpty('No se pudo leer el tramo. Revisa el panel de salud de datos.'); return; }
  renderTramo(res);
}

// ---------------- Frecuencia historica de ruptura (fase 3) ----------------
// Es un CONTEO de intentos historicos, no la salida de un modelo calibrado, asi que no se
// llama probabilidad. La cifra NUNCA se muestra sola: sin n e intervalo se leeria como una.
function clearBreakout() {
  const body = $('breakout-body');
  if (body) body.replaceChildren();
  const sub = $('breakout-sub');
  if (sub) sub.textContent = 'Tasa base histórica, no un modelo';
}

function breakoutEmpty(text) {
  const body = $('breakout-body');
  if (!body) return;
  const div = document.createElement('div');
  div.className = 'zone-empty';
  div.textContent = text;
  body.replaceChildren(div);
}

function rateBlock(entry, headline) {
  const wrap = document.createElement('div');
  if (!entry.available) {
    const none = document.createElement('div');
    none.className = 'zone-empty';
    none.textContent = `${entry.label}: ${entry.reason}`;
    wrap.append(none);
    return wrap;
  }
  const title = document.createElement('div');
  title.className = 'brk-headline';
  title.textContent = headline || entry.label;
  const rate = document.createElement('div');
  rate.className = 'brk-rate';
  rate.textContent = `${number(entry.rate_pct, 1)}%`;
  const lo = entry.ci95_pct ? entry.ci95_pct[0] : null;
  const hi = entry.ci95_pct ? entry.ci95_pct[1] : null;
  const ci = document.createElement('div');
  ci.className = 'brk-ci';
  ci.textContent = `${entry.sustained} de ${entry.n} intentos análogos`
    + (lo !== null ? ` · IC95 ${number(lo, 0)}–${number(hi, 0)}%` : '')
    + (entry.n < 30 ? ' · muestra pequeña' : '');
  wrap.append(title, rate, ci);

  if (lo !== null) {
    const band = document.createElement('div');
    band.className = 'brk-band';
    const span = document.createElement('span');
    span.className = 'brk-band-ci';
    span.style.left = `${lo}%`;
    span.style.width = `${Math.max(hi - lo, 0.5)}%`;
    const point = document.createElement('span');
    point.className = 'brk-band-pt';
    point.style.left = `${entry.rate_pct}%`;
    band.append(span, point);
    const scale = document.createElement('div');
    scale.className = 'brk-scale';
    for (const tick of ['0%', '50%', '100%']) {
      const s = document.createElement('span');
      s.textContent = tick;
      scale.append(s);
    }
    wrap.append(band, scale);
  }
  const split = document.createElement('div');
  split.className = 'zone-meta';
  split.textContent = `Sostenida ${number(entry.rate_pct, 0)}% · falsa ${number(entry.false_break_pct, 0)}% · rechazo ${number(entry.rejection_pct, 0)}%`;
  wrap.append(split);
  return wrap;
}

function renderBreakout(result) {
  const body = $('breakout-body');
  if (!body) return;
  body.replaceChildren();
  if (!result.available) {
    breakoutEmpty(result.reason || 'Sin muestra suficiente para estimar una tasa.');
    return;
  }
  body.append(rateBlock(result.base_rate,
    `Ruptura ${result.direction} de ${money(result.level, 2)} — todos los intentos análogos`));

  const condTitle = document.createElement('div');
  condTitle.className = 'brk-headline';
  condTitle.style.marginTop = '14px';
  condTitle.textContent = 'Con las condiciones actuales';
  body.append(condTitle);

  for (const entry of safeArray(result.conditional_rates)) {
    const row = document.createElement('div');
    row.className = 'brk-cond';
    const name = document.createElement('span');
    name.className = 'brk-cond-name';
    name.textContent = entry.label;
    const value = document.createElement('span');
    if (entry.available) {
      const lo = entry.ci95_pct ? entry.ci95_pct[0] : null;
      const hi = entry.ci95_pct ? entry.ci95_pct[1] : null;
      value.textContent = `${number(entry.rate_pct, 1)}% (n=${entry.n}`
        + (lo !== null ? `, IC95 ${number(lo, 0)}–${number(hi, 0)}%` : '') + ')';
    } else {
      value.className = 'neutral';
      value.textContent = `sin muestra (n=${entry.n})`;
    }
    row.append(name, value);
    body.append(row);
  }

  const nocombine = document.createElement('div');
  nocombine.className = 'range-note';
  nocombine.textContent = 'Estas tasas son marginales y NO se multiplican entre sí: las '
    + 'variables están correlacionadas y combinarlas fabricaría precisión que la muestra no sostiene.';
  body.append(nocombine);

  const conf = result.confirmation || {};
  const confTitle = document.createElement('div');
  confTitle.className = 'brk-headline';
  confTitle.style.marginTop = '14px';
  confTitle.textContent = `Confirmación en vivo: ${conf.met}/${conf.required} · ${conf.state}`;
  body.append(confTitle);
  for (const check of safeArray(conf.checks)) {
    const row = document.createElement('div');
    row.className = 'brk-check';
    const mark = document.createElement('span');
    mark.className = check.met ? 'positive' : 'negative';
    mark.textContent = check.met ? '✓' : '✗';
    const text = document.createElement('span');
    text.textContent = `${check.label} — ${check.detail}`;
    row.append(mark, text);
    body.append(row);
  }

  const warn = document.createElement('div');
  warn.className = 'range-note negative';
  warn.textContent = result.warning || '';
  body.append(warn);

  const sub = $('breakout-sub');
  if (sub) {
    sub.textContent = result.base_rate.available
      ? `${number(result.base_rate.rate_pct, 0)}% sobre ${result.base_rate.n} intentos`
      : 'muestra insuficiente';
  }
}

async function submitBreakout(event) {
  if (event) event.preventDefault();
  const level = asNumber(($('breakout-level') || {}).value);
  const direction = ($('breakout-direction') || {}).value || 'up';
  if (level === null || level <= 0) {
    breakoutEmpty('Introduce un nivel de precio válido.');
    return;
  }
  breakoutEmpty('Calculando…');
  const query = `symbol=${encodeURIComponent(state.symbol)}&level=${level}&direction=${direction}`;
  const result = await maybe(`/api/level/breakout?${query}`, null);
  if (!result) {
    breakoutEmpty('No se pudo calcular la tasa base. Revisa el panel de salud de datos.');
    return;
  }
  renderBreakout(result);
}

// ---------------- Lo que el sobre servia y no se veia (fase 3b) ----------------
// Las tres tarjetas de abajo leen del SOBRE YA CACHEADO (`state.sobre`): ninguna abre una
// peticion nueva. No se usa `delSobre`, que colapsa `undefined` y `null` en el mismo
// fallback, porque aqui la diferencia importa.
//
// AUSENTE, NULO, VACIO Y CERO NO SE PARECEN. Un campo que el backend no declara no es lo
// mismo que uno declarado sin valor, y ninguno de los dos es un cero. `cross_asset` de hoy
// sirve `relative_strength_vs_base_pct: {1h: null, 4h: null, 24h: null}`: pintarlo como
// «0.00%» o como «—» diria que la fuerza relativa es plana cuando lo que pasa es que no hay
// dato. Cada celda dice cual de los cuatro es.
function faltaDe(obj, clave) {
  if (!obj || !Object.hasOwn(obj, clave)) return 'no declarado';
  const v = obj[clave];
  if (v === null) return 'nulo';
  if (Array.isArray(v) ? !v.length : (v && typeof v === 'object' && !Object.keys(v).length)) return 'vacío';
  return null;                       // hay valor: lo pinta quien llama
}
// una fila de .metric-list: la casa la escribe como <div><dt>/<dd> dentro de un <dl>.
// `id` es OPCIONAL y existe para que la red pueda vigilar UNA FILA y no la tarjeta entera.
// Hizo falta porque una fila DERIVADA enmascara a las suyas: en la rafaga de liquidaciones,
// «Rafaga vs mediana» usa `total` y `baseline_5m`, asi que con la fila del Total sin su cifra
// el texto de la tarjeta SEGUIA moviendose al mutar `total` y el check no condenaba. Mi propio
// plantado C7 lo encontro.
function filaDl(dl, etiqueta, valor, clase, id) {
  const d = document.createElement('div');
  if (id) d.id = id;
  const k = document.createElement('dt'); k.textContent = etiqueta;
  const v = document.createElement('dd'); if (clase) v.className = clase; v.textContent = valor;
  d.append(k, v); dl.append(d);
}
// una celda de ventana: o el numero, o cual de los cuatro estados es
function celdaVentana(mapa, w, fmt) {
  if (mapa === undefined) return 'no declarado';
  if (mapa === null) return 'nulo';
  const f = faltaDe(mapa, w);
  return f === null ? fmt(mapa[w]) : f;
}

// LA UNIDAD NO SE SUPONE: se publica la nota que sirve el backend, tal cual.
function renderCrossAsset() {
  const body = $('cross-asset-body'); if (!body) return;
  body.replaceChildren();
  const sub = $('cross-asset-sub'); const nota = $('cross-asset-note');
  const ca = state.sobre ? state.sobre.cross_asset : undefined;
  if (!ca) {
    if (sub) sub.textContent = state.sobre ? (ca === null ? 'nulo en el sobre' : 'no declarado en el sobre') : 'sin sobre';
    if (nota) nota.textContent = 'Fuente: /api/ai/context · cross_asset';
    return;
  }
  const corr = ca.correlation, beta = ca.beta_vs_base, rs = ca.relative_strength_vs_base_pct;
  const ventanas = [...new Set([corr, beta, rs].flatMap(m => (m && typeof m === 'object') ? Object.keys(m) : []))];
  for (const w of ventanas) {
    const tr = document.createElement('tr');
    // correlation llega por activo -{eth, sol}-, no como escalar: se listan los activos.
    const c = celdaVentana(corr, w, v => (v && typeof v === 'object')
      ? Object.entries(v).map(([a, x]) => `${a} ${number(x, 2)}`).join(' · ')
      : number(v, 2));
    td(tr, w, '');
    td(tr, c, 'neutral');
    td(tr, celdaVentana(beta, w, v => number(v, 2)), 'neutral');
    td(tr, celdaVentana(rs, w, v => pct(v, 2)), typeof (rs || {})[w] === 'number' ? signClass(rs[w]) : 'neutral');
    body.append(tr);
  }
  if (!ventanas.length) { const tr = document.createElement('tr'); td(tr, 'Sin ventanas servidas', ''); body.append(tr); }
  if (sub) {
    // EL BASE ES EL PROPIO SIMBOLO en el sobre de hoy: entonces beta = 1 y fuerza relativa
    // nula son ARITMETICA, no lectura de mercado. Callarlo seria publicar un numero vacio.
    const mismo = ca.base && ca.symbol && ca.base === ca.symbol;
    sub.textContent = ca.available === false ? 'no disponible'
      : `base ${ca.base || 'no declarada'}${mismo ? ' · es el propio símbolo: beta 1 y fuerza relativa son triviales' : ''}`;
  }
  if (nota) nota.textContent = `${ca.note || 'el backend no declara nota'} · /api/ai/context · cross_asset`;
}

function renderVolatilidad() {
  const body = $('volatilidad-body'); if (!body) return;
  body.replaceChildren();
  const sub = $('volatilidad-sub'); const nota = $('volatilidad-note');
  const vo = state.sobre ? state.sobre.volatility : undefined;
  if (!vo) {
    if (sub) sub.textContent = state.sobre ? (vo === null ? 'nulo en el sobre' : 'no declarado en el sobre') : 'sin sobre';
    if (nota) nota.textContent = 'Fuente: /api/ai/context · volatility';
    return;
  }
  const fila = (etiqueta, valor, clase) => filaDl(body, etiqueta, valor, clase);
  // EL ATR SE PINTA. La primera version decia en el subtitulo «ATR se publica en su propia
  // tarjeta» y ERA FALSO: lo daba por visto un `grep atr` que casaba `matrix`, `matriz`,
  // `cuatro` y `atras`. La unica mencion real del panel es `reaction_atr` en
  // 06-perfiles-y-niveles.js:242, que es una reaccion medida EN MULTIPLOS de ATR -«reaccion
  // mediana de 1.83 ATR»-, no el ATR. Marcado: mutar volatility.atr.1h.atr no cambiaba ni un
  // texto de la pantalla. Ninguna tarjeta puede decir que un dato esta en otro sitio si una
  // marca no lo demuestra.
  //
  // LAS DOS UNIDADES SALEN DEL CODIGO QUE LAS PRODUCE, app/scalp_logic.py:3153-3154:
  //     "atr":     round(a, 4)                     -> en precio, la moneda del simbolo
  //     "atr_pct": round(a / close * 100, 3)       -> por ciento del cierre
  // Van en la MISMA fila y rotuladas, que es lo contrario de ponerlas lado a lado sin decir
  // que mide cada una.
  const atr = vo.atr;
  const faltaAtr = faltaDe(vo, 'atr');
  if (faltaAtr) fila('ATR', faltaAtr, 'neutral');
  else for (const tf of Object.keys(atr)) {
    const a = atr[tf] || {};
    const abs = faltaDe(a, 'atr') || number(a.atr, 2);
    const rel = faltaDe(a, 'atr_pct') || `${number(a.atr_pct, 3)}% del cierre`;
    fila(`ATR · ${tf}`, `${abs} · ${rel}`, 'neutral');
  }
  const rv = vo.realized_vol_annualized_pct;
  for (const w of (rv && typeof rv === 'object') ? Object.keys(rv) : []) {
    fila(`Vol. realizada anualizada · ${w}`, celdaVentana(rv, w, v => `${number(v, 1)}%`), 'neutral');
  }
  if (!rv || typeof rv !== 'object') fila('Vol. realizada anualizada', faltaDe(vo, 'realized_vol_annualized_pct') || '—', 'neutral');
  fila('Percentil de rango diario · 1 año', faltaDe(vo, 'daily_range_percentile_1y') || `${number(vo.daily_range_percentile_1y, 1)}%`, 'neutral');
  // compression_score: `# <1 comprimido` en app/scalp_logic.py:3186. El umbral es del backend,
  // no mio: por eso se rotula con el 1 y no con un adjetivo inventado.
  const comp = faltaDe(vo, 'compression_score');
  fila('Compresión ATR(5)/ATR(20) 1h', comp || `${number(vo.compression_score, 3)} · ${vo.compression_score < 1 ? 'comprimido (<1)' : 'sin comprimir (≥1)'}`,
    comp ? 'neutral' : (vo.compression_score < 1 ? 'positive' : 'neutral'));
  const re = faltaDe(vo, 'range_expansion');
  fila('Expansión de rango', re || (vo.range_expansion ? 'sí' : 'no'), re ? 'neutral' : (vo.range_expansion ? 'positive' : 'neutral'));
  if (sub) sub.textContent = `${Object.keys(atr && typeof atr === 'object' ? atr : {}).length} marcos de ATR`;
  if (nota) {
    nota.textContent = `${vo.note || 'el backend no declara nota'} · ATR: valor en precio y `
      + `% del cierre (app/scalp_logic.py:3153-3154) · /api/ai/context · volatility`;
  }
}

function renderInvalida() {
  const body = $('invalida-body'); if (!body) return;
  body.replaceChildren();
  const sub = $('invalida-sub'); const nota = $('invalida-note');
  const op = state.sobre ? state.sobre.operator_read : undefined;
  if (!op) {
    if (sub) sub.textContent = state.sobre ? (op === null ? 'nulo en el sobre' : 'no declarado en el sobre') : 'sin sobre';
    if (nota) nota.textContent = 'Fuente: /api/ai/context · operator_read';
    return;
  }
  const grupo = (etiqueta, clave) => {
    const falta = faltaDe(op, clave);
    filaDl(body, etiqueta, falta || `${op[clave].length} condiciones`, 'neutral');
    // Los codigos se publican TAL CUAL los sirve el backend. No los traduzco: inventar un
    // rotulo para `book_l5_turns_offer_dominant` seria suponer que mide lo que me parece.
    (falta ? [] : op[clave]).forEach((c, i) => filaDl(body, `${i + 1}`, c, ''));
  };
  grupo('Invalida el largo', 'invalidates_long');
  grupo('Invalida el corto', 'invalidates_short');
  // `spread_warning_note` va en la nota al pie, abajo.
  if (sub) sub.textContent = op.bias ? `sesgo ${op.bias}` : 'sesgo no declarado';
  // ESTO NO ES UNA SENAL VIVA. Las dos listas son constantes en app/ai_context.py:750: el
  // backend sirve siempre las mismas tres por lado, no dependen del mercado de hoy. Pintarlas
  // como si cambiaran seria mentir por omision.
  const aviso = 'Lista fija del backend (app/ai_context.py:750): no cambia con el mercado, es el criterio de invalidación, no una medida.';
  if (nota) nota.textContent = `${aviso}${op.spread_warning_note ? ' · ' + op.spread_warning_note : ''}`;
}

// EL PERFIL DE VOLUMEN Y SU VWAP, que NO es el VWAP que ya se pinta. `04-flujo-y-libro.js:74`
// escribe `scalp.session_vwap`, y este bloque declara por si mismo que es OTRO en
// `vwap.distinct_from`: «scalp.session_vwap (usa sesion NYSE y trades en vivo; puede diferir
// ~1%)». Marcado: mutar volume_profile.vwap.utc_day o volume_profile.session.poc no cambiaba
// ni un texto de la pantalla. Que sean dos VWAP distintos es la razon de pintarlo CON SU
// CONVENCION al lado, no la razon de callarlo -que fue lo que dije en la entrega anterior-.
function renderPerfilVolumen() {
  const body = $('perfil-vol-body'); if (!body) return;
  body.replaceChildren();
  const sub = $('perfil-vol-sub'); const nota = $('perfil-vol-note');
  const vp = state.sobre ? state.sobre.volume_profile : undefined;
  if (!vp) {
    if (sub) sub.textContent = state.sobre ? (vp === null ? 'nulo en el sobre' : 'no declarado en el sobre') : 'sin sobre';
    if (nota) nota.textContent = 'Fuente: /api/ai/context · volume_profile';
    return;
  }
  const fila = (etiqueta, valor, clase) => filaDl(body, etiqueta, valor, clase);
  const ses = vp.session, vw = vp.vwap;
  const faltaSes = faltaDe(vp, 'session');
  if (faltaSes) fila('Perfil de sesión', faltaSes, 'neutral');
  else {
    for (const [k, r] of [['poc', 'POC'], ['vah', 'VAH'], ['val', 'VAL']]) {
      fila(r, faltaDe(ses, k) || money(ses[k], 2), 'neutral');
    }
    // HVN y LVN son LISTAS: vacia y ausente no son lo mismo, y ninguna es un cero.
    for (const [k, r] of [['hvn', 'HVN · nodos de alto volumen'], ['lvn', 'LVN · nodos de bajo volumen']]) {
      const f = faltaDe(ses, k);
      fila(r, f || ses[k].map(x => money(x, 2)).join(' · '), 'neutral');
    }
  }
  const faltaVw = faltaDe(vp, 'vwap');
  if (faltaVw) fila('VWAP', faltaVw, 'neutral');
  else {
    fila('VWAP día', faltaDe(vw, 'utc_day') || money(vw.utc_day, 2), 'neutral');
    fila('VWAP semana', faltaDe(vw, 'weekly') || money(vw.weekly, 2), 'neutral');
    const fb = faltaDe(vw, 'bands');
    if (fb) fila('Bandas σ', fb, 'neutral');
    else for (const [k, r] of [['plus_1sigma', '+1σ'], ['minus_1sigma', '−1σ'], ['plus_2sigma', '+2σ'], ['minus_2sigma', '−2σ']]) {
      fila(`VWAP ${r}`, faltaDe(vw.bands, k) || money(vw.bands[k], 2), 'neutral');
    }
  }
  if (sub) {
    // El mercado y la convencion NO se suponen: los declara el propio bloque.
    const m = vw && vw.market, c = vw && vw.session_convention;
    sub.textContent = vp.available === false ? 'no disponible'
      : `${m || 'mercado no declarado'} · ${c || 'convención no declarada'}`;
  }
  if (nota) {
    const d = vw && vw.distinct_from;
    nota.textContent = `${vp.note || 'el backend no declara nota'}`
      + `${d ? ` · NO es el mismo VWAP que «VWAP sesión»: ${d}` : ''} · /api/ai/context · volume_profile`;
  }
}

// LA RAFAGA DE LIQUIDACIONES. Unidades leidas de la consulta que las produce,
// app/scalp_logic.py:1701-1727: long_liq/short_liq/total son SUM(notional_usd) de los ultimos
// 5 minutos, `events` es COUNT(*) de eventos, y baseline_5m es la MEDIANA -percentile_cont
// (0.5)- del total por bucket de 5 min en las 3 horas anteriores. Por eso la comparacion que
// importa se rotula con esas dos ventanas y no con un adjetivo.
function renderLiqBurst() {
  const body = $('liq-burst-body'); if (!body) return;
  body.replaceChildren();
  const sub = $('liq-burst-sub'); const nota = $('liq-burst-note');
  const lb = state.sobre ? state.sobre.liq_burst : undefined;
  if (!lb) {
    if (sub) sub.textContent = state.sobre ? (lb === null ? 'nulo en el sobre' : 'no declarado en el sobre') : 'sin sobre';
    if (nota) nota.textContent = 'Fuente: /api/ai/context · liq_burst';
    return;
  }
  // Cada fila lleva su id: la de abajo es DERIVADA de `total` y `baseline_5m`, y sin ids la red
  // no sabria distinguir «el Total perdio su cifra» de «el Total sigue ahi».
  const fila = (etiqueta, valor, clase, id) => filaDl(body, etiqueta, valor, clase, id);
  fila('Largos liquidados', faltaDe(lb, 'long_liq') || money(lb.long_liq, 2), 'negative', 'fila-liq-largos');
  fila('Cortos liquidados', faltaDe(lb, 'short_liq') || money(lb.short_liq, 2), 'positive', 'fila-liq-cortos');
  fila('Total', faltaDe(lb, 'total') || money(lb.total, 2), 'neutral', 'fila-liq-total');
  fila('Eventos', faltaDe(lb, 'events') || number(lb.events, 0), 'neutral', 'fila-liq-eventos');
  fila('Mediana por 5 min en 3 h', faltaDe(lb, 'baseline_5m') || money(lb.baseline_5m, 2), 'neutral', 'fila-liq-mediana');
  // La razon contra la mediana es lo que dice si esto es una cascada; se calcula aqui y se
  // rotula con lo que compara. Si la mediana es 0 NO se divide: se dice.
  const t = lb.total, b = lb.baseline_5m;
  const razon = (typeof t === 'number' && typeof b === 'number')
    ? (b > 0 ? `${number(t / b, 2)}× la mediana` : 'sin mediana con la que comparar (0 en 3 h)')
    : 'no calculable';
  fila('Ráfaga vs mediana', razon, (typeof t === 'number' && typeof b === 'number' && b > 0 && t / b >= 3) ? 'negative' : 'neutral', 'fila-liq-razon');
  if (sub) sub.textContent = `ventana ${lb.window || 'no declarada'}`;
  if (nota) {
    nota.textContent = 'Nocional en USD de liquidaciones (SUM notional_usd); la mediana es '
      + 'percentile_cont(0.5) de los buckets de 5 min de las 3 h anteriores '
      + '(app/scalp_logic.py:1701-1727) · /api/ai/context · liq_burst';
  }
}

