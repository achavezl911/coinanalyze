'use strict';
/* LA MESA · capa de datos
 * ---------------------------------------------------------------------------
 * S2, ARREGLADO AQUI Y EN UN SOLO SITIO.
 * La mesa local del operador pedia `/api/cvd/spot?symbol=BTC` y la API contestaba
 * 404 `{"detail":"Unknown symbol"}` (3 de 3). Medido contra 140 el 2026-09-28:
 *     api "/api/cvd/spot?symbol=BTC"                -> HTTP 404 Unknown symbol
 *     api "/api/cvd/spot?symbol=BTCUSDT_PERP.A"     -> HTTP 200 con filas
 * El backend valida contra el ID CANONICO del simbolo, no contra el nombre del activo. El
 * arreglo no es parchear esa llamada: es que NINGUNA ruta se pida con el nombre del activo.
 * `simbolo()` es el unico sitio donde se traduce, y `pedir()` es el unico sitio que construye
 * una URL: si manana aparece un cuarto activo, se anade en un sitio.
 */

const ACTIVOS = ['BTC', 'ETH', 'SOL'];

const SIMBOLOS = {
  BTC: 'BTCUSDT_PERP.A',
  ETH: 'ETHUSDT_PERP.A',
  SOL: 'SOLUSDT_PERP.A',
};

const MARCOS = ['scalp', 'swing', 'largo'];

function simbolo(activo) {
  const s = SIMBOLOS[String(activo || '').toUpperCase()];
  // NO SE ADIVINA. Un activo que no esta en el mapa no se manda al backend "por si cuela":
  // eso es justo lo que producia el 404 de S2.
  if (!s) throw new Error('activo desconocido: ' + activo);
  return s;
}

/* ---------------------------------------------------------------------------
 * AUSENTE · NULO · RANCIO · ERROR son cuatro cosas, y ninguna es cero.
 * `pedir` no convierte un fallo en un dato: devuelve un sobre con `ok:false` y el motivo,
 * y quien pinta decide como decirlo. Un 422 disfrazado de dato viejo es peor que el 422.
 * ------------------------------------------------------------------------- */
async function pedir(ruta, params) {
  const url = new URL(ruta, window.location.origin);
  Object.keys(params || {}).forEach((k) => {
    if (params[k] !== undefined && params[k] !== null) url.searchParams.set(k, params[k]);
  });
  const t0 = (window.performance || Date).now();
  try {
    const r = await fetch(url.toString(), { credentials: 'same-origin' });
    const ms = (window.performance || Date).now() - t0;
    if (!r.ok) {
      let detalle = '';
      try {
        detalle = JSON.stringify(await r.json()).slice(0, 200);
      } catch (e) {
        detalle = '(cuerpo no legible)';
      }
      return { ok: false, estado: 'error', http: r.status, motivo: detalle, ms, ruta: url.pathname };
    }
    return { ok: true, datos: await r.json(), ms, http: r.status, ruta: url.pathname };
  } catch (e) {
    const ms = (window.performance || Date).now() - t0;
    return {
      ok: false,
      estado: 'error',
      http: 0,
      motivo: 'transporte: ' + (e && e.message ? e.message : e),
      ms,
      ruta: url.pathname,
    };
  }
}

/* ------------------------------------------------------- formato de cifras */

function esNada(v) {
  return v === null || v === undefined || v === '';
}

function num(v, dec) {
  if (esNada(v) || Number.isNaN(Number(v))) return null;
  const d = dec === undefined ? 2 : dec;
  return Number(v).toLocaleString('es-ES', {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  });
}

function usd(v) {
  if (esNada(v) || Number.isNaN(Number(v))) return null;
  const n = Number(v);
  const abs = Math.abs(n);
  const s = n < 0 ? '-' : '';
  if (abs >= 1e9) return s + '$' + (abs / 1e9).toFixed(2) + 'B';
  if (abs >= 1e6) return s + '$' + (abs / 1e6).toFixed(2) + 'M';
  if (abs >= 1e3) return s + '$' + (abs / 1e3).toFixed(1) + 'K';
  return s + '$' + abs.toFixed(0);
}

function pct(v, dec) {
  const n = num(v, dec === undefined ? 2 : dec);
  return n === null ? null : n + ' %';
}

/* La edad en palabras cortas. Devuelve null si no hay instante: un "hace 0 s" sobre un
 * campo que no llego seria un cero inventado. */
function edad(iso, ahoraMs) {
  if (esNada(iso)) return null;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return null;
  const s = Math.max(0, Math.round(((ahoraMs === undefined ? Date.now() : ahoraMs) - t) / 1000));
  if (s < 90) return s + ' s';
  const m = Math.round(s / 60);
  if (m < 90) return m + ' min';
  const h = Math.round(m / 60);
  if (h < 48) return h + ' h';
  return Math.round(h / 24) + ' d';
}

/* Clase de frescura contra un tope DECLARADO. Sin tope no hay veredicto: null. */
function claseFrescura(segundos, topeS) {
  if (esNada(segundos) || esNada(topeS)) return null;
  const s = Number(segundos);
  if (s > Number(topeS)) return 'viejo';
  if (s > Number(topeS) / 2) return 'tibio';
  return 'fresco';
}

/* ------------------------------------------------------------------ el DOM */

function el(tag, clase, texto) {
  const n = document.createElement(tag);
  if (clase) n.className = clase;
  if (texto !== undefined && texto !== null) n.textContent = String(texto);
  return n;
}

function vaciar(nodo) {
  while (nodo && nodo.firstChild) nodo.removeChild(nodo.firstChild);
  return nodo;
}

/* UN «NO SE» CON SU CLASE Y SU MOTIVO. Los cuatro estados se pintan DISTINTO a proposito:
 * quien mira la pantalla tiene que poder distinguir «el backend no trae esto» de «lo trae
 * y vale null» de «es viejo» de «no se pudo leer». Ninguno se pinta como 0 ni como «—». */
function noSe(estado, motivo) {
  const clases = { ausente: 'ausente', nulo: 'nulo', rancio: 'rancio', error: 'error' };
  const c = clases[estado] || 'ausente';
  const rotulos = {
    ausente: 'AUSENTE',
    nulo: 'NULO',
    rancio: 'RANCIO',
    error: 'ERROR',
  };
  const caja = el('span');
  caja.appendChild(el('span', 'no-se ' + c, rotulos[c]));
  if (motivo) caja.appendChild(el('span', 'motivo', motivo));
  return caja;
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    ACTIVOS,
    SIMBOLOS,
    MARCOS,
    simbolo,
    esNada,
    num,
    usd,
    pct,
    edad,
    claseFrescura,
  };
}
