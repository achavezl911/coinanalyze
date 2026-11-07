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

// los eventos de la ruta, en numeros y por orden de ts (la ruta ya los da asi)
function eventosLiq(sueltas) {
  if (!sueltas || !Array.isArray(sueltas.eventos)) return [];
  return sueltas.eventos.map((e) => ({ ts: e.ts, t: Date.parse(e.ts), exchange: e.exchange, lado: e.lado,
                                       precio: Number(e.precio), usd: Number(e.usd) }))
    .filter((e) => Number.isFinite(e.t) && Number.isFinite(e.precio) && Number.isFinite(e.usd));
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

/* Las lineas de la ficha para [t0, t1): las pintadas que caen ahi (hora, exchange, lado, precio, USD), cuantas mas si
 * no caben, y lo que no tiene dato. Sin pintadas y con dato: «ninguna». */
function fichaLiq(pintadas, sinDato, t0, t1, umbral, max) {
  const u = umbral === undefined ? LIQ_UMBRAL_USD : umbral;
  const n = max || LIQ_FICHA_MAX;
  const en = pintadas.filter((e) => e.t >= t0 && e.t < t1);
  const sin = sinDato.filter((x) => x.desde < t1 && x.hasta > t0);
  const out = en.slice(0, n).map((e) => 'liq ' + e.ts.slice(11, 19) + 'Z · ' + e.exchange + ' · ' + ladoLiq(e.lado)
    + ' · ' + e.precio + ' · ' + usdLiq(e.usd) + ' USD');
  if (en.length > n) out.push('liq: y ' + (en.length - n) + ' más');
  if (!en.length && !sin.length) out.push('liq ≥ ' + usdLiq(u) + ' USD: ninguna');
  sin.forEach((x) => out.push('liq SIN DATO: ' + x.motivo));
  return out;
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { LIQ_UMBRAL_USD, LIQ_RADIO, LIQ_FICHA_MAX, radioLiq, eventosLiq, sobreUmbralLiq, sinDatoLiq, ladoLiq,
                     usdLiq, fichaLiq };
}
