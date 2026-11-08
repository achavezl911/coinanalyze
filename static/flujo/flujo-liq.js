'use strict';
/* LAS LIQUIDACIONES SOBRE EL PRECIO (campana 150) · lo que comparten /flujo y /libro, puro (node --test y K120 lo
 * recalculan). Los datos son las sueltas de /api/orderflow/indicadores (liquidations_realtime): ninguna ruta nueva.
 *   lado 'long'  = largo liquidado = VENTA forzada -> color de venta de la pagina
 *   lado 'short' = corto liquidado = COMPRA forzada -> color de compra
 * Lo que la ruta no trae (antes de su retencion, despues del corte de TOPE_SUELTAS, un hueco de data_gap) se DICE: es
 * «sin dato», nunca «ninguna». */

// 10 mil USD por omision: en 12 h de 140 hubo ~625 liquidaciones (BTC+ETH+SOL) y casi todas son de cientos a pocos miles
// de USD: pintadas todas, el mapa se llena de puntos sin lectura. 10 k es el primer escalon que se lee en el libro.
const LIQ_UMBRAL_USD = 10000;
// el AREA proporcional a los USD con una escala FIJA (se comparan ventanas): r0 px a u0 USD, entre min y max
const LIQ_RADIO = { r0: 3, u0: 10000, min: 3, max: 18,
                    regla: 'r = min(18, max(3, 3 * sqrt(usd / 10000))) px: el área es proporcional a los USD' };
const LIQ_FICHA_MAX = 4;

function radioLiq(usd) {
  const r = LIQ_RADIO.r0 * Math.sqrt(Math.max(0, Number(usd)) / LIQ_RADIO.u0);
  return Math.min(LIQ_RADIO.max, Math.max(LIQ_RADIO.min, r));
}

/* los eventos de la ruta, en numeros y por orden de ts (la ruta ya los da asi). `precio` es la p de la orden forzada
 * (limite en binance, quiebra en bybit: ~0.4 % mas alla del mercado, remate 1); el circulo va en `ejecucion` (la ap de
 * binance, o la impresion de la cinta que la ruta eligio), y sin ella es null: no se pinta en el precio. */
function eventosLiq(sueltas) {
  if (!sueltas || !Array.isArray(sueltas.eventos)) return [];
  return sueltas.eventos.map((e) => {
    const x = e.ejecucion === null || e.ejecucion === undefined ? NaN : Number(e.ejecucion);
    const ok = Number.isFinite(x) && x > 0;
    return { ts: e.ts, t: Date.parse(e.ts), exchange: e.exchange, lado: e.lado, precio: Number(e.precio),
             usd: Number(e.usd), ejecucion: ok ? x : null, fuente: ok ? e.ejecucion_fuente : 'sin_dato',
             venue: ok && e.ejecucion_impresion ? e.ejecucion_impresion.venue : null };
  }).filter((e) => Number.isFinite(e.t) && Number.isFinite(e.precio) && Number.isFinite(e.usd));
}

// [con ejecucion, sin ejecucion]: las primeras se pintan en (ts, ejecucion); las segundas van a window.LIQ_SIN_PRECIO
function parteLiq(eventos) {
  return [eventos.filter((e) => e.ejecucion !== null), eventos.filter((e) => e.ejecucion === null)];
}

function ejecucionLiq(e) {
  if (e.ejecucion === null) return 'ejecución: sin dato · orden a ' + e.precio;
  const f = e.fuente === 'ap' ? 'ap de ' + e.exchange : 'cinta' + (e.venue ? ' de ' + e.venue : '');
  return 'ejecución ' + e.ejecucion + ' (' + f + ') · orden a ' + e.precio;
}

function sobreUmbralLiq(eventos, umbral) {
  const u = umbral === undefined ? LIQ_UMBRAL_USD : umbral;
  return eventos.filter((e) => e.usd >= u);
}

/* Los tramos de [desdeMs, hastaMs) de los que la ruta NO dice nada: [{desde, hasta, motivo}] en ms. */
function sinDatoLiq(sueltas, desdeMs, hastaMs) {
  if (!sueltas) return [{ desde: desdeMs, hasta: hastaMs, motivo: 'la ruta no trajo las liquidaciones' }];
  const out = [];
  const dd = Date.parse(sueltas.desde_dato);
  if (Number.isFinite(dd) && dd > desdeMs) {
    out.push({ desde: desdeMs, hasta: Math.min(dd, hastaMs),
               motivo: 'antes de la retención (' + sueltas.retencion_h + ' h): sin dato' });
  }
  if (sueltas.truncada) {
    const ev = sueltas.eventos || [];
    const ult = ev.length ? Date.parse(ev[ev.length - 1].ts) : desdeMs;
    out.push({ desde: ult, hasta: hastaMs, motivo: 'la ruta cortó en ' + ev.length + ' eventos: lo de después no está' });
  }
  (sueltas.huecos || []).filter((h) => h.estado !== 'recovered').forEach((h) => {
    out.push({ desde: Math.max(Date.parse(h.desde), desdeMs), hasta: Math.min(Date.parse(h.hasta), hastaMs),
               exchange: h.exchange, motivo: 'hueco de ' + h.exchange + ' (' + h.estado + '): sin dato' });
  });
  return out.filter((x) => x.hasta > x.desde);
}

function ladoLiq(lado) {
  return lado === 'long' ? 'largo liquidado (venta forzada)' : 'corto liquidado (compra forzada)';
}

function usdLiq(usd) {
  const v = Number(usd);
  if (v >= 1e6) return (v / 1e6).toFixed(2) + ' M';
  if (v >= 1e3) return (v / 1e3).toFixed(1) + ' k';
  return v.toFixed(0);
}

/* Las lineas de la ficha para [t0, t1): las pintadas y las sin precio (window.LIQ_SIN_PRECIO) que caen ahi (hora,
 * exchange, lado, ejecucion con su fuente, la p de la orden, USD), cuantas mas si no caben, y lo que no tiene dato. Sin
 * ninguna y con dato: «ninguna». */
function fichaLiq(pintadas, sinDato, t0, t1, umbral, max, sinPrecio) {
  const u = umbral === undefined ? LIQ_UMBRAL_USD : umbral;
  const n = max || LIQ_FICHA_MAX;
  const en = pintadas.concat(sinPrecio || []).filter((e) => e.t >= t0 && e.t < t1).sort((a, b) => a.t - b.t);
  const sin = sinDato.filter((x) => x.desde < t1 && x.hasta > t0);
  const out = en.slice(0, n).map((e) => 'liq ' + e.ts.slice(11, 19) + 'Z · ' + e.exchange + ' · ' + ladoLiq(e.lado)
    + ' · ' + ejecucionLiq(e) + ' · ' + usdLiq(e.usd) + ' USD');
  if (en.length > n) out.push('liq: y ' + (en.length - n) + ' más');
  if (!en.length && !sin.length) out.push('liq ≥ ' + usdLiq(u) + ' USD: ninguna');
  sin.forEach((x) => out.push('liq SIN DATO: ' + x.motivo));
  return out;
}

/* LA CASCADA M8 del estudio: n y s llegan en sueltas.cascada (app/anatomia.py, la MISMA constante que lee
 * anatomia_extrae); la pagina no lleva copia. Sin regla, null: no se pinta ninguna y se dice. Sobre TODOS los eventos
 * (sin umbral), por lado. Una liquidacion «cierra cascada» si hay >= n del mismo lado en [t - s, t] (las de su mismo
 * ts cuentan: el estudio las ordena y la ultima del minuto es la que manda). */
function marcasCascada(eventos, regla) {
  if (!regla || !Number.isFinite(Number(regla.n)) || !Number.isFinite(Number(regla.s))) return null;
  const n = Number(regla.n);
  const sMs = Number(regla.s) * 1000;
  const out = {};
  ['long', 'short'].forEach((lado) => {
    const a = eventos.filter((e) => e.lado === lado).sort((p, q) => p.t - q.t || p.usd - q.usd);
    let j0 = 0;
    out[lado] = a.map((e, k) => {
      while (a[j0].t < e.t - sMs) j0 += 1;
      let hi = k;
      while (hi + 1 < a.length && a[hi + 1].t === e.t) hi += 1;
      return { e, k, j0, hi, cierra: hi - j0 + 1 >= n };
    });
  });
  return out;
}

/* Los episodios: la union de las ventanas de las que cierran cascada, juntas si comparten eventos.
 * [{lado, desde, hasta (ms), n, usd}] por orden de desde; null sin regla. */
function cascadasLiq(eventos, regla) {
  const m = marcasCascada(eventos, regla);
  if (!m) return null;
  const out = [];
  ['long', 'short'].forEach((lado) => {
    const v = m[lado];
    let cur = null;
    v.filter((x) => x.cierra).forEach((x) => {
      if (cur && x.j0 <= cur.hi) { cur.hi = Math.max(cur.hi, x.hi); return; }
      if (cur) out.push(cur);
      cur = { j0: x.j0, hi: x.hi };
    });
    if (cur) out.push(cur);
    out.filter((c) => c.lado === undefined).forEach((c) => {
      const tramo = v.slice(c.j0, c.hi + 1).map((x) => x.e);
      c.lado = lado;
      c.desde = tramo[0].t;
      c.hasta = tramo[tramo.length - 1].t;
      c.n = tramo.length;
      c.usd = tramo.reduce((s, e) => s + e.usd, 0);
    });
  });
  return out.map((c) => ({ lado: c.lado, desde: c.desde, hasta: c.hasta, n: c.n, usd: c.usd }))
    .sort((p, q) => p.desde - q.desde || (p.lado < q.lado ? -1 : 1));
}

/* La columna liq_{l,s}_casc del estudio por minuto (epoch s del minuto -> {l, s}): la marca de la ULTIMA liquidacion
 * del minuto de ese lado. Solo para comprobar la regla contra anatomia_extrae (tests/test_liq_cascada.py). */
function cascadaMinutos(eventos, regla) {
  const m = marcasCascada(eventos, regla);
  const out = {};
  ['long', 'short'].forEach((lado) => m[lado].forEach((x) => {
    const min = Math.floor(x.e.t / 60000) * 60;
    out[min] = out[min] || {};
    out[min][lado[0]] = x.cierra ? 1 : 0;
  }));
  return out;
}

function textoCascada(c) {
  return 'cascada ' + (c.lado === 'long' ? 'de largos (venta forzada)' : 'de cortos (compra forzada)') + ' · '
    + new Date(c.desde).toISOString().slice(11, 19) + '–' + new Date(c.hasta).toISOString().slice(11, 19) + 'Z · '
    + c.n + ' liq · ' + usdLiq(c.usd) + ' USD';
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { LIQ_UMBRAL_USD, LIQ_RADIO, LIQ_FICHA_MAX, radioLiq, eventosLiq, parteLiq, ejecucionLiq, sobreUmbralLiq, sinDatoLiq, ladoLiq,
                     usdLiq, fichaLiq, cascadasLiq, cascadaMinutos, textoCascada };
}
