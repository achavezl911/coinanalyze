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

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { DISPOSICIONES, ESPACIO_DEFECTO, VIGILA_MS, leeHashEspacio, escribeHashEspacio, srcMarco };
}
