'use strict';
/* EL ESPACIO (campana OF-6b, OF-6 segunda parte): varios graficos de /flujo a la vez.
 * ---------------------------------------------------------------------------
 * /flujo es UN grafico por pagina (VISTA, LIENZO, FLUJO_PINTADO y FLUJO_HITOS son globales): aqui no se toca. Varios
 * graficos = 1, 2 o 4 MARCOS (<iframe>) de /flujo#<vista>, cada uno con su /flujo entero, su raton, su teclado y sus
 * contratos. El raton y el teclado van solos al marco que los recibe (cada documento tiene los suyos); esta pagina solo
 * dice cual tiene el foco (un borde).
 *
 * UNA URL = UN ESPACIO: `#d=<disposicion>&v=<vista 1>&v=<vista 2>...`, la disposicion `1`, `2h` (lado a lado), `2v`
 * (uno encima de otro) o `4` (2x2) y cada vista el hash de su /flujo sin `#` (encodeURIComponent; `/`, `=`, `:` y `,`
 * se dejan legibles). Con menos vistas que marcos, los que faltan van a la vista por omision de /flujo (`v=` vacia).
 * Lo que no se entiende (otra clave, otra disposicion, mas vistas que marcos, una vista con algo que /flujo no
 * escribe) NO se adivina: el defecto (1 marco, la vista por omision) y el hash se reescribe, como /flujo.
 *
 * Cada VIGILA_MS esta pagina lee el hash de cada marco (mismo origen: contentWindow.location) y, si cambio, reescribe
 * el suyo con replaceState: tras un gesto en un marco, el hash del espacio lo lleva en menos de 1 s.
 *
 * Los trazos de dos marcos del mismo activo no se pisan: eso es de flujo-trazos.js (la fusion y el oyente de
 * `storage`), igual entre marcos que entre pestanas.
 */

const DISPOSICIONES = { 1: 1, '2h': 2, '2v': 2, 4: 4 };
const ESPACIO_DEFECTO = { disp: '1', vistas: [''] };
const VISTA_BUENA = /^[A-Za-z0-9/=.:,_+-]*$/;
const VIGILA_MS = 250;

const defecto = () => ({ disp: ESPACIO_DEFECTO.disp, vistas: ESPACIO_DEFECTO.vistas.slice() });

/* `#d=..&v=..` -> {disp, vistas} con tantas vistas como marcos; lo que no se entiende, el defecto. */
function leeHashEspacio(hash) {
  const texto = String(hash || '').replace(/^#/, '');
  if (!texto) return defecto();
  let disp = null;
  const vistas = [];
  for (const parte of texto.split('&')) {
    const i = parte.indexOf('=');
    if (i < 0) return defecto();
    const k = parte.slice(0, i);
    let v;
    try {
      v = decodeURIComponent(parte.slice(i + 1));
    } catch (e) {
      return defecto();
    }
    if (k === 'd' && disp === null && Object.prototype.hasOwnProperty.call(DISPOSICIONES, v)) disp = v;
    else if (k === 'v' && VISTA_BUENA.test(v)) vistas.push(v);
    else return defecto();
  }
  if (disp === null || vistas.length > DISPOSICIONES[disp]) return defecto();
  while (vistas.length < DISPOSICIONES[disp]) vistas.push('');
  return { disp, vistas };
}

const codifica = (v) => encodeURIComponent(v).replace(/%2F/g, '/').replace(/%3D/g, '=').replace(/%3A/g, ':')
  .replace(/%2C/g, ',');

/* {disp, vistas} -> `#d=..&v=..` (las vistas de los marcos de la disposicion, ni una mas). */
function escribeHashEspacio(e) {
  const n = DISPOSICIONES[e.disp];
  const vs = [];
  for (let i = 0; i < n; i++) vs.push('&v=' + codifica(String((e.vistas && e.vistas[i]) || '').replace(/^#/, '')));
  return '#d=' + e.disp + vs.join('');
}

/* La src de un marco: /flujo con su vista (sin vista, la de por omision, que /flujo escribe en su hash). */
const srcMarco = (vista) => '/flujo' + (vista ? '#' + vista : '');

/* ------------------------------------------------------------ la pagina */
// e: lo que dice el hash; todas: la vista de los cuatro marcos (al pasar de 4 a 2 y volver, los de abajo no se
// pierden en esta pagina); foco: el indice del marco con el foco
const ESP = { e: null, todas: ['', '', '', ''], marcos: [], foco: 0 };

function vistaDeMarco(f) {
  try {
    const l = f.contentWindow.location;
    if (l.pathname !== '/flujo') return null; // aun cargando (about:blank)
    const v = l.hash.replace(/^#/, '');
    return v && VISTA_BUENA.test(v) ? v : null;
  } catch (e) {
    return null;
  }
}

function escribeMiHash() {
  const n = DISPOSICIONES[ESP.e.disp];
  ESP.e = { disp: ESP.e.disp, vistas: ESP.todas.slice(0, n) };
  const h = escribeHashEspacio(ESP.e);
  if (window.location.hash !== h) window.history.replaceState(null, '', h);
  window.ESPACIO = { disp: ESP.e.disp, vistas: ESP.e.vistas.slice(), foco: ESP.foco, hash: h };
}

function pintaFoco() {
  ESP.marcos.forEach((f, i) => f.classList.toggle('foco', i === ESP.foco));
}

function pintaBotonera() {
  document.querySelectorAll('#sel-disp button[data-disp]').forEach((b) => {
    b.setAttribute('aria-pressed', String(b.dataset.disp === ESP.e.disp));
  });
}

/* Los marcos de la disposicion: los que ya estaban se quedan como estan (no se recargan); los que sobran se van. */
/* El lienzo de /flujo hace preventDefault en mousedown (flujo-dibujo.js, para que el arrastre no seleccione texto) y
 * eso le quita al clic el paso del foco al marco: se le da aqui, en captura, antes que el lienzo. */
function tomaFoco(f) {
  try {
    f.contentWindow.addEventListener('mousedown', () => {
      if (document.activeElement !== f) f.contentWindow.focus();
      ESP.foco = ESP.marcos.indexOf(f);
      pintaFoco();
    }, true);
  } catch (e) { /* un marco de otro origen no es nuestro */ }
}

function montaMarcos() {
  const caja = document.getElementById('marcos');
  const n = DISPOSICIONES[ESP.e.disp];
  caja.className = 'd-' + ESP.e.disp;
  while (ESP.marcos.length > n) ESP.marcos.pop().remove();
  for (let i = ESP.marcos.length; i < n; i++) {
    const f = document.createElement('iframe');
    f.className = 'marco';
    f.title = 'Grafico ' + (i + 1);
    f.dataset.marco = String(i);
    f.src = srcMarco(ESP.todas[i]);
    f.addEventListener('load', () => tomaFoco(f));
    caja.appendChild(f);
    ESP.marcos.push(f);
  }
  if (ESP.foco >= n) ESP.foco = 0;
  pintaFoco();
  pintaBotonera();
}

/* El hash de esta pagina -> la disposicion y las vistas; lo que no se entiende se reescribe (como /flujo). Un marco
 * cuya vista cambio en el hash va a la nueva por SU hash (su /flujo la aplica sin recargar). */
function aplicaHashEspacio() {
  const e = leeHashEspacio(window.location.hash);
  ESP.e = e;
  e.vistas.forEach((v, i) => {
    ESP.todas[i] = v;
    const f = ESP.marcos[i];
    const actual = f ? vistaDeMarco(f) : null;
    if (f && v && actual !== null && actual !== v) f.contentWindow.location.hash = '#' + v;
  });
  montaMarcos();
  escribeMiHash();
}

/* Cada VIGILA_MS: la vista de cada marco (lo que su raton o su teclado dejaron en su hash) y quien tiene el foco. */
function vigila() {
  ESP.marcos.forEach((f, i) => {
    const v = vistaDeMarco(f);
    if (v !== null) ESP.todas[i] = v;
  });
  const i = ESP.marcos.indexOf(document.activeElement);
  if (i >= 0 && i !== ESP.foco) {
    ESP.foco = i;
    pintaFoco();
  }
  escribeMiHash();
}

function arrancaEspacio() {
  document.getElementById('sel-disp').addEventListener('click', (ev) => {
    const b = ev.target.closest('button[data-disp]');
    if (!b || b.dataset.disp === ESP.e.disp) return;
    vigila();
    window.location.hash = escribeHashEspacio({ disp: b.dataset.disp, vistas: ESP.todas });
  });
  window.addEventListener('hashchange', aplicaHashEspacio);
  window.addEventListener('blur', () => setTimeout(vigila, 0)); // un clic en un marco: el borde enseguida
  aplicaHashEspacio();
  const primero = ESP.marcos[0];
  primero.addEventListener('load', () => {
    if (document.activeElement === document.body) primero.contentWindow.focus();
  }, { once: true });
  setInterval(vigila, VIGILA_MS);
}

if (typeof document !== 'undefined' && document.addEventListener) {
  document.addEventListener('DOMContentLoaded', arrancaEspacio);
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { DISPOSICIONES, ESPACIO_DEFECTO, VIGILA_MS, leeHashEspacio, escribeHashEspacio, srcMarco };
}
