'use strict';
// resumen, delta, absorcion, libro y liquidaciones
// Trozo 4 de 11 del panel. Sale de static/app.js SIN TOCAR UNA LINEA DE LOGICA
// (FASE 2, 2026-09-13): lineas 340-672 del fichero original.
// El orden de los <script defer> de index.html ES el orden de este fichero: no se
// reordena nada, porque en scripts clasicos un `const` de primer nivel solo existe a
// partir del script que lo declara.
function renderTabs() { const tabs = $('symbol-tabs'); tabs.replaceChildren(); for (const item of state.symbols) { const button = document.createElement('button'); button.type = 'button'; button.textContent = item.asset; button.className = item.symbol === state.symbol ? 'active' : ''; button.addEventListener('click', () => selectSymbol(item.symbol)); tabs.append(button); } }
// Sparkline de la serie diaria ya descargada. Sin ejes ni escala: solo dice la forma del
// ultimo tramo. El numero grande sigue siendo el dato; esto es contexto.
function sparkline(values) {
  const points = safeArray(values).map(asNumber).filter(v => v !== null);
  if (points.length < 3) return null;
  const NS = 'http://www.w3.org/2000/svg';
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = (max - min) || Math.abs(max) || 1;
  const step = 100 / (points.length - 1);
  const coords = points.map((v, i) => `${(i * step).toFixed(2)},${(23 - ((v - min) / span) * 20).toFixed(2)}`);
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', '0 0 100 26');
  svg.setAttribute('preserveAspectRatio', 'none');
  svg.setAttribute('class', `spark ${points[points.length - 1] >= points[0] ? 'up' : 'down'}`);
  svg.setAttribute('aria-hidden', 'true');
  const area = document.createElementNS(NS, 'polygon');
  area.setAttribute('class', 'spark-area');
  area.setAttribute('points', `0,26 ${coords.join(' ')} 100,26`);
  const line = document.createElementNS(NS, 'polyline');
  line.setAttribute('class', 'spark-line');
  line.setAttribute('points', coords.join(' '));
  svg.append(area, line);
  return svg;
}
function card(label, value, sub, className = '', series = null, seriesTitle = '') {
  const node = document.createElement('article');
  node.className = 'summary-card';
  const l = document.createElement('div');
  l.className = 'label';
  l.textContent = label;
  const v = document.createElement('div');
  v.className = `value ${className}`;
  v.textContent = value;
  const s = document.createElement('div');
  s.className = 'sub';
  s.textContent = sub;
  node.append(l, v, s);
  const spark = sparkline(series);
  if (spark) { node.append(spark); node.title = seriesTitle; }
  return node;
}
function dailySeries(field) { return safeArray((state.daily || {}).rows).map(row => row[field]); }
// Funding ausente NO es funding tranquilo: sin dato la tarjeta queda neutra y lo dice el
// propio valor ('—'), pero nunca se afirma que este por debajo del umbral de tension.
function fundingClass(value) {
  const n = asNumber(value);
  return n !== null && Math.abs(n) >= .03 ? 'negative' : 'neutral';
}
function renderSummary(s, scalp, cvdSwing = {}) {
  const sessions = safeArray((state.daily || {}).rows).length;
  const note = sessions ? `Últimas ${sessions} sesiones` : '';
  $('summary').replaceChildren(
    card('Precio', money(s.price, 2), priceDirection1h(s.price_dir_1h), signClass(s.price_dir_1h), dailySeries('price_close'), `Cierre diario · ${note}`),
    card('CVD spot 24 h', money(s.cvd_spot_24h), 'Binance + Bybit', signClass(s.cvd_spot_24h), dailySeries('cumulative_spot'), `CVD spot acumulado · ${note}`),
    card('Open Interest', money(s.oi), `${pct(s.oi_chg_24h_pct)} / 24 h`, signClass(s.oi_chg_24h_pct), dailySeries('oi_close'), `Open interest al cierre · ${note}`),
    card('Funding / liquidez', rate(s.fr_avg), `${number(scalp.spread_bps, 2)} bps · book ${scalp.book_status || 'sin datos'}`, fundingClass(s.fr_avg), dailySeries('fr_avg'), `Funding medio por sesión · ${note}`),
  );
  $('price-context').textContent = `${money(s.price, 2)} · Δ3m ${money(s.delta_3min)}`;
}
function rowDL(container, name, value, cls = '') { const row = document.createElement('div'); const dt = document.createElement('dt'); const dd = document.createElement('dd'); dt.textContent = name; dd.textContent = value; dd.className = cls; row.append(dt, dd); container.append(row); }

function renderExecutionLevels(scalp) {
  const levels = $('levels');
  levels.replaceChildren();
  rowDL(levels, 'VWAP sesión', money(scalp.session_vwap, 2), 'neutral');
  // Sin basis utilizable se dice POR QUE, no se pinta un guion mudo.
  rowDL(levels, 'Basis perp-spot',
    scalp.basis_bps === null || scalp.basis_bps === undefined
      ? (scalp.basis_status === 'STALE' ? 'Desfasado' : scalp.basis_status === 'UNAVAILABLE' ? 'Sin datos' : '—')
      : `${number(scalp.basis_bps, 2)} bps`,
    scalp.basis_bps === null || scalp.basis_bps === undefined ? 'negative' : signClass(scalp.basis_bps));
  // Estos tres SOLIAN publicar 0 cuando faltaba el insumo: "sobre el VWAP", "OI plano" y
  // "0 USD liquidados" son afirmaciones, no huecos. Ahora el hueco se dice N/D.
  rowDL(levels, 'Dist VWAP', nd(scalp.vwap_dist_pct, pct), signClass(scalp.vwap_dist_pct));
  // El spread BRUTO se muestra en NEUTRO. Colorearlo de rojo al pasar de 5 bps era el mismo
  // umbral universal que se retiró del backend: 5 bps se comen un cuarto de un scalp de 20 y
  // son ruido en un swing de 400. El color lo decide `execution.verdict`, que compara el
  // coste total contra el objetivo de ESTA operación.
  rowDL(levels, 'Spread', nd(scalp.spread_bps, v => `${number(v, 2)} bps`), 'neutral');
  // No es un "imbalance" en -1..+1: es la fraccion bid/(bid+ask), 0-1 centrada en 0.5.
  const bidShare = asNumber(scalp.imbalance_l5);
  rowDL(levels, 'Bid share L1/L5/L10 (0-1)', `${number(scalp.imbalance_l1, 2)} / ${number(scalp.imbalance_l5, 2)} / ${number(scalp.imbalance_l10, 2)}`, bidShare === null ? 'neutral' : signClass(bidShare - .5));
  rowDL(levels, 'OI 15m', nd(scalp.oi_chg_15m_pct, pct), signClass(scalp.oi_chg_15m_pct));
  const liqMedida = scalp.liquidations_measured === true;
  rowDL(levels, 'Liquidaciones 5m (L/S)',
    liqMedida ? `${money(scalp.long_liq_5m)} / ${money(scalp.short_liq_5m)}` : 'N/D · feed no medido',
    liqMedida ? 'neutral' : 'negative');
  rowDL(levels, 'Absorción', scalp.absorption || 'N/D', scalp.absorption && scalp.absorption.includes('ventas') ? 'positive' : scalp.absorption && scalp.absorption.includes('compras') ? 'negative' : 'neutral');
}
// Los cuatro cuadrantes de flujo. La clasificacion sale del signo de AMBAS patas, que es la
// lectura que informa: dos mercados con escalas distintas no se restan para sacar direccion.
const FLOW_QUADRANTS = {
  ambos_compran: ['Spot compra / futuros compran', 'positive'],
  ambos_venden: ['Spot vende / futuros venden', 'negative'],
  spot_compra: ['Spot compra / futuros venden', 'neutral'],
  spot_vende: ['Spot vende / futuros compran', 'neutral'],
  plano: ['Una pata plana', 'neutral'],
  sin_datos: ['Sin datos', 'neutral'],
};
// ---------------- jerarquia visual del perfil ----------------
// El perfil NO cambia ningun dato bruto: cambia que temporalidad manda la lectura. Aqui se
// traduce la jerarquia publicada por /api/profile a una clase CSS por fila, de forma que en
// intradia destaquen 4h/1h y 18m/15m/5m, y en swing 3d/1d/8h y 4h/1h.
const LAYER_RANK = { contexto: 1, confirmacion: 2, entrada: 3, gatillo: 3, ejecucion: 4 };
function profileLayerOf(timeframe) {
  const layers = (state.tfProfile || {}).layers || {};
  for (const [name, layer] of Object.entries(layers)) {
    for (const entry of safeArray(layer.timeframes)) {
      if (entry.timeframe === timeframe) return name;
    }
  }
  return null;
}
// Ancla temporal del snapshot de Mesa. Se publica para que se vea que todos los paneles de
// la pestana describen el MISMO instante, y para que un snapshot viejo se note.
function renderDeskAsOf(desk) {
  const pill = $('desk-asof');
  if (!pill) return;
  const asOf = desk && desk.as_of;
  if (!asOf) {
    pill.textContent = 'Snapshot N/D';
    // ESTADO, no direccion: «no llego snapshot» no es una venta. Ver el bloque del vocabulario
    // de estado en app.css.
    pill.className = 'live-pill estado-malo';
    pill.title = 'La Mesa no recibió snapshot coherente en este ciclo';
    return;
  }
  const edad = Math.max(0, Math.round((Date.now() - new Date(asOf).getTime()) / 1000));
  const parcial = desk.partial || {};
  const faltan = safeArray(parcial.scalp_missing_components).length + safeArray(parcial.profile_missing_data).length;
  pill.textContent = `Snapshot ${dateTime(asOf)} · ${edad}s${faltan ? ` · ${faltan} parcial(es)` : ''}`;
  pill.className = `live-pill ${edad > 180 || faltan ? 'estado-aviso' : 'neutral'}`;
  pill.title = `Todos los paneles de la Mesa comparten este ancla. `
    + `Evidencia scalp ${number(parcial.scalp_coverage_pct, 0)}% · marcos ${number(parcial.profile_coverage_pct, 0)}%`;
}

// Cabecera de la Mesa: dice EXPLICITAMENTE que temporalidades manda el perfil activo, para
// que el enfasis de las tablas no sea un efecto visual sin explicacion.
function renderProfileEmphasis(result) {
  const layers = (result || {}).layers || {};
  const listar = nombre => safeArray((layers[nombre] || {}).timeframes).map(t => t.timeframe).join(' · ');
  const set = (id, texto) => { const el = $(id); if (el) el.textContent = texto || 'N/D'; };
  set('emphasis-contexto', listar('contexto'));
  set('emphasis-confirmacion', listar('confirmacion'));
  set('emphasis-entrada', listar('entrada') || listar('gatillo'));
  const nota = $('emphasis-note');
  if (nota) {
    const ejecucion = listar('ejecucion');
    nota.textContent = ejecucion
      ? `${ejecucion} solo ejecutan: no invalidan la tesis en ${result.profile_label || result.profile || 'este perfil'}.`
      : (result.invalidation || '');
  }
}
// Marca la fila con su capa. `data-layer` permite al CSS destacar contexto/confirmacion y
// atenuar la capa de ejecucion, que en swing no debe robar atencion.
function markProfileLayer(tr, timeframe) {
  // Sin jerarquia cargada todavia no se marca NADA: atenuar toda la tabla porque el perfil
  // aun no ha llegado seria un artefacto de carga, no una lectura.
  if (!Object.keys((state.tfProfile || {}).layers || {}).length) return null;
  const layer = profileLayerOf(timeframe);
  if (!layer) { tr.dataset.layer = 'fuera'; return null; }
  tr.dataset.layer = layer;
  tr.dataset.rank = String(LAYER_RANK[layer] || 9);
  tr.title = `Capa ${layer} del perfil ${state.tradingProfile}`;
  return layer;
}
// Ojo con el nombre: `flowQuadrant` (sin prefijo) ya existe mas abajo y clasifica SESIONES
// diarias. Esta trabaja sobre las ventanas de la matriz de delta.
function deltaFlowQuadrant(spotDelta, futDelta) {
  const s = asNumber(spotDelta);
  const f = asNumber(futDelta);
  if (s === null || f === null) return 'sin_datos';
  if (s === 0 || f === 0) return 'plano';
  if (s > 0 && f > 0) return 'ambos_compran';
  if (s < 0 && f < 0) return 'ambos_venden';
  return s > 0 ? 'spot_compra' : 'spot_vende';
}
// Delta normalizado por su PROPIO volumen: es lo unico que permite comparar las dos patas
// entre si sin que la escala del perp aplaste al spot.
function deltaShare(delta, volume) {
  const d = asNumber(delta);
  const v = asNumber(volume);
  return d === null || v === null || v === 0 ? null : d / v;
}
function initDiffToggle() {
  const box = $('show-diff');
  if (!box) return;
  const apply = () => {
    for (const cell of document.querySelectorAll('.diff-col')) cell.hidden = !box.checked;
    const note = $('delta-diff-note');
    if (note) note.hidden = !box.checked;
  };
  box.addEventListener('change', apply);
  apply();
}
function renderDeltaMatrix(rows) {
  const body = $('delta-matrix');
  body.replaceChildren();
  const verDiff = !!($('show-diff') && $('show-diff').checked);
  for (const r of safeArray(rows)) {
    const tr = document.createElement('tr');
    markProfileLayer(tr, r.window);
    const complete = r.coverage_status === 'complete';
    const coverage = complete ? 'Completa' : (r.coverage_status === 'unavailable' ? 'Sin datos' : 'Parcial');
    td(tr, r.window, '');
    // COBERTURA, no direccion: «Parcial» en rojo se leia como una venta. Ese era el
    // ejemplo con el que Alejandro pidio separar los dos vocabularios.
    const statusCell = td(tr, coverage, complete ? 'estado-ok' : 'estado-aviso');
    statusCell.title = `Spot: ${r.spot_source || 'sin fuente'} · lag ${number(r.spot_end_gap_seconds, 0)} s`;
    // Lo direccional son las DOS patas y su cuadrante. El diferencial spot-futuros no lo es
    // (medido: su signo es el del CVD de futuros invertido en 93-94% de las sesiones), asi
    // que baja a columna de auditoria, sin color y oculta por defecto.
    td(tr, nd(r.spot_delta, money), signClass(r.spot_delta));
    td(tr, nd(r.fut_delta, money), signClass(r.fut_delta));
    const spotShare = deltaShare(r.spot_delta, r.spot_volume);
    const futShare = deltaShare(r.fut_delta, r.fut_volume);
    td(tr, spotShare === null ? 'N/D' : number(spotShare, 3), signClass(spotShare));
    td(tr, futShare === null ? 'N/D' : number(futShare, 3), signClass(futShare));
    const quadrant = FLOW_QUADRANTS[deltaFlowQuadrant(r.spot_delta, r.fut_delta)];
    td(tr, quadrant[0], quadrant[1]);
    td(tr, nd(r.fut_volume, money), 'neutral');
    td(tr, r.oi_change_pct == null ? 'N/D' : `${number(r.oi_change_pct, 2)}%`, signClass(r.oi_change_pct));
    const diffCell = td(tr, nd(r.diff, money), 'neutral');
    diffCell.className = 'neutral diff-col';
    diffCell.hidden = !verDiff;
    diffCell.title = 'Resta de dos mercados con escalas distintas: no indica direcci\u00f3n';
    body.append(tr);
  }
}
// Absorcion con la evidencia a la vista: el ratio medido, el umbral que tuvo que superar,
// DE DONDE sale ese umbral, la banda contra su propia distribucion y el tamano de muestra.
function renderAbsorption(rows) {
  const body = $('absorption-matrix');
  body.replaceChildren();
  for (const r of safeArray(rows)) {
    const tr = document.createElement('tr');
    const ctx = r.context || {};
    const cls = r.score > 0 ? 'positive' : r.score < 0 ? 'negative' : 'neutral';
    td(tr, r.window, '');
    td(tr, nd(r.fut_delta, money), signClass(r.fut_delta));
    td(tr, nd(r.delta_ratio, v => number(v, 3)), 'neutral');
    td(tr, nd(r.min_ratio, v => number(v, 3)), 'neutral');
    td(tr, r.threshold_source || 'N/D', r.threshold_source === 'baseline_p75_medido' ? 'positive' : 'neutral');
    td(tr, ctx.band || 'sin baseline', ctx.band === 'extremo' || ctx.band === 'alto' ? 'negative' : 'neutral');
    td(tr, ctx.sample_count == null ? 'N/D' : `n=${number(ctx.sample_count, 0)}`, 'neutral');
    td(tr, nd(r.price_move_pct, pct), signClass(r.price_move_pct));
    const estado = td(tr, r.absorption || 'N/D', cls);
    // La cobertura de la ventana viaja en el tooltip: "Absorción fuerte" medida sobre dos
    // buckets sueltos no vale lo mismo que sobre la ventana entera.
    const cov = r.coverage || {};
    estado.title = cov.buckets == null
      ? 'Sin cobertura declarada'
      : `Cobertura: ${cov.buckets} buckets · ${number(cov.span_seconds, 0)} s de ${cov.window_seconds} s`;
    body.append(tr);
  }
}
// La imbalance es una fraccion 0-1 centrada en 0.5: la barra la hace legible de un vistazo
// sin quitar el numero, que es lo que se compara entre venues.
function imbalanceCell(tr, value) {
  const share = asNumber(value);
  const cell = td(tr, share === null ? '—' : number(share, 2), signClass((share === null ? .5 : share) - .5));
  if (share === null) return cell;
  const gauge = document.createElement('span');
  gauge.className = 'imb-gauge';
  const fill = document.createElement('i');
  const offset = Math.min(Math.max(share, 0), 1) - .5;
  fill.className = offset >= 0 ? 'positive' : 'negative';
  fill.style.left = offset >= 0 ? '50%' : `${(0.5 + offset) * 100}%`;
  fill.style.width = `${Math.abs(offset) * 100}%`;
  gauge.append(fill);
  cell.append(gauge);
  return cell;
}
// El spread por venue tambien va en NEUTRO: comparar bps sueltos contra un literal no dice
// si la operacion sale cara. Eso lo responde `execution_assessment` con objetivo y riesgo.
// Vacio y rancio no se pueden ver igual. El endpoint filtra ts >= now()-30s, asi que un
// libro viejo llega como CERO filas y en la tabla no queda nada de donde deducir si el
// libro no existe o si es que es viejo. La respuesta lo dice fuera de rows (K13) y aqui
// se pinta: un hecho que el servidor declara y el panel calla sigue sin llegar a quien
// decide. Son TRES casos y no dos, y el cuarto es que no hubo respuesta.
function orderbookNote(freshness, filas) {
  const estado = freshness && typeof freshness === 'object' ? freshness.status : null;
  const edad = asNumber(freshness && freshness.age_seconds);
  const tope = asNumber(freshness && freshness.max_age_seconds);
  const antiguedad = edad === null ? 'sin decir de cuando' : `${number(edad, 1)} s de antiguedad`;
  if (estado === 'empty') return 'Sin libro: no hay ninguna instantanea de este simbolo';
  if (estado === 'stale') {
    const corte = tope === null ? '' : `, corte ${number(tope, 0)} s`;
    return `Libro RANCIO: ${antiguedad}${corte}. La tabla esta vacia porque el dato es viejo, no porque no exista`;
  }
  if (estado === 'fresh') return `${filas} venue${filas === 1 ? '' : 's'} · ${antiguedad}`;
  return 'No hay lectura del libro: el servidor no respondio o no declara su frescura';
}
function renderOrderbook(result) {
  const body = $('orderbook-body');
  body.replaceChildren();
  const filas = safeArray(result.rows);
  for (const r of filas) { const tr = document.createElement('tr'); td(tr, r.exchange, ''); td(tr, nd(r.spread_bps, v => `${number(v, 2)} bps`), 'neutral'); imbalanceCell(tr, r.imbalance_l1); imbalanceCell(tr, r.imbalance_l5); imbalanceCell(tr, r.imbalance_l10); td(tr, pct(r.wall_up_pct), 'neutral'); td(tr, pct(r.wall_down_pct), 'neutral'); body.append(tr); }
  const nota = $('orderbook-note');
  if (!nota) return;
  const fresco = result.freshness && result.freshness.status === 'fresh';
  nota.textContent = orderbookNote(result.freshness, filas.length);
  nota.className = `source-note${fresco ? '' : ' has-gaps'}`;
}
// null !== 0: "no se midio" y "no hubo liquidaciones" son lecturas distintas y el operador
// necesita distinguirlas. Solo se calcula el ratio cuando AMBAS patas existen.
function renderLiquidations(result) {
  const body = $('liq-matrix');
  body.replaceChildren();
  for (const r of safeArray(result.matrix)) {
    const longV = asNumber(r.long_liq);
    const shortV = asNumber(r.short_liq);
    const known = longV !== null && shortV !== null;
    const ratio = known && shortV > 0 ? longV / shortV : null;
    const tr = document.createElement('tr');
    // QUE VENUES CUBRE LA FILA, dicho y no supuesto. Hasta el 2026-08-31 esta tabla mezclaba
    // dos fuentes: 1m/5m/15m traian binance y bybit, y 30m/1h/4h solo binance, con las mismas
    // columnas y sin nada que lo dijera. Ya salen las seis de la misma fuente; el rotulo
    // existe para que volver a mezclarlas no pueda pasar desapercibido.
    const venues = safeArray(r.venues);
    tr.title = venues.length ? `Cubre ${venues.join(' + ')}` : 'Cobertura de venues no declarada';
    [[r.window, ''],
     [longV === null ? 'Sin dato' : money(longV), longV === null ? 'neutral' : 'negative'],
     [shortV === null ? 'Sin dato' : money(shortV), shortV === null ? 'neutral' : 'positive'],
     [ratio === null ? '\u2014' : number(ratio, 2), known ? signClass(shortV - longV) : 'neutral'],
     [r.events == null ? '\u2014' : number(r.events, 0), 'neutral']].forEach(([v, c]) => td(tr, v, c));
    body.append(tr);
  }
}
function td(tr, value, cls = '') { const cell = document.createElement('td'); cell.textContent = value ?? '—'; cell.className = cls || ''; tr.append(cell); return cell; }

