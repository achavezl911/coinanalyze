'use strict';
/* EL FOOTPRINT · lo que se CALCULA (campana 142, OF-2). Funciones puras: las prueba `node --test` y K109 las
 * recalcula por su cuenta. Nada de aqui toca el DOM ni pide nada.
 *
 * LO QUE SE CALCULA AQUI Y NO EN EL SERVIDOR: los desequilibrios (por nivel; servidos, la respuesta engordaria) y el
 * estado de cada vela contra el reloj. Lo demas -niveles, compra, venta, delta, POC, value area, paso automatico y
 * cobertura- llega servido por /api/orderflow/footprint y se pinta TAL CUAL.
 *
 * EL DESEQUILIBRIO (P2 de la campana), DIAGONAL, en aritmetica EXACTA: BigInt sobre el texto decimal servido (en float,
 * 0.3 >= 3 * 0.1 es falso y en decimal es verdad):
 *   COMPRADOR en P  si compra(P) >= 3 x venta(P - paso)   y  compra(P) >= la media por nivel de su vela
 *   VENDEDOR  en P  si venta(P)  >= 3 x compra(P + paso)  y  venta(P)  >= la media por nivel de su vela
 * La media por nivel es (compra + venta de todos los niveles de la vela) / cuantos niveles. El vecino solo se mira
 * DENTRO de la vela (de su nivel mas bajo al mas alto) y, dentro, un nivel sin celda vale 0. APILADO: 3 o mas niveles
 * seguidos del mismo lado. Medido sobre celdas reales de produccion (x1-tmp/c142/p2.py): sin el minimo, el 89 % de
 * los niveles de BTC 1m salian desequilibrio; con el, del 13 al 25 % segun activo y marco.
 */

const FLUJO_ACTIVOS = ['BTC', 'ETH', 'SOL'];
const FLUJO_MARCOS = { '1m': 1, '5m': 5, '15m': 15, '1h': 60, '4h': 240, '1d': 1440 };
// Las velas que se piden de historia: 240, salvo donde no caben en los 30 dias que se guardan las celdas.
const FLUJO_HISTORIA = { '1m': 240, '5m': 240, '15m': 240, '1h': 240, '4h': 180, '1d': 30 };
// LAS FAMILIAS (decision del encargo, por la dispersion medida entre venues): nunca se suman dos.
const FAMILIAS = {
  perp: { rotulo: 'perpetuos USDT', venues: ['binance_usdm', 'bybit_linear', 'okx_swap', 'bitget_usdt'] },
  spot: { rotulo: 'spot USDT', venues: ['binance_spot', 'bybit_spot', 'okx_spot'] },
  coinbase: { rotulo: 'Coinbase spot (USD)', venues: ['coinbase_spot'] },
  deribit: { rotulo: 'Deribit perpetuo (USD; SOL en USDC)', venues: ['deribit_perp'] },
};
const DESEQ_RAZON = 3n;
const DESEQ_APILADO = 3;
// Una vela se juzga CERRADA 90 s despues de su ultimo minuto: el colector escribe un minuto a los 10 s de cerrarse y
// lo reescribe, definitivo, a los 70 s (app/orderflow.py). Antes de eso, sin filas no es un hueco: es que no ha llegado.
const CIERRE_S = 90;
const VER_DEFECTO = 40;
const VER_MAXIMO = 240;

function tiene(obj, k) {
  return Object.prototype.hasOwnProperty.call(obj, k);
}

function isoZ(ms) {
  return new Date(ms).toISOString().replace('.000Z', 'Z');
}

/* ------------------------------------------------------------------ el hash
 * `#<activo>/<marco>/<familia>[/<paso>][/clave=valor...]`: una vista = una URL (headless no pulsa). El paso es `auto`
 * (por omision) o un numero; detras, en cualquier orden: unidad=usd, min=<x>, esconde, grande=<x>, hasta=<ISO>, ver=<n>.
 * Lo que no se entiende NO se adivina: se cae al defecto y la pagina reescribe el hash. */
function leeHash(hash) {
  const partes = String(hash || '').replace(/^#/, '').split('/').filter(Boolean);
  const e = { activo: 'BTC', marco: '1m', familia: 'perp', paso: 'auto', unidad: 'base', min: null, esconde: false,
              grande: null, hasta: null, ver: VER_DEFECTO };
  // OF-3 (campana 143): las capas, la sesion y el modo TPO; sin sus claves, la vista es la del footprint de la 142
  Object.assign(e, { sesion: 'dia', capas: [], compuesto: null, fijo: null, modo: 'footprint', sesiones: TPO_SESIONES });
  const a = String(partes[0] || '').toUpperCase();
  if (FLUJO_ACTIVOS.includes(a)) e.activo = a;
  if (partes[1] && tiene(FLUJO_MARCOS, partes[1])) e.marco = partes[1];
  if (partes[2] && tiene(FAMILIAS, partes[2])) e.familia = partes[2];
  let resto = partes.slice(3);
  if (resto.length && !resto[0].includes('=') && resto[0] !== 'esconde') {
    if (resto[0] === 'auto' || (/^\d+(\.\d+)?$/.test(resto[0]) && Number(resto[0]) > 0)) e.paso = resto[0];
    resto = resto.slice(1);
  }
  const positivo = (v) => /^\d+(\.\d+)?$/.test(v || '') && Number(v) > 0;
  resto.forEach((p) => {
    const [k, v] = p.split('=');
    if (k === 'unidad' && (v === 'usd' || v === 'base')) e.unidad = v;
    else if (k === 'min' && positivo(v)) e.min = v;
    else if (k === 'grande' && positivo(v)) e.grande = v;
    else if (k === 'esconde' && v === undefined) e.esconde = true;
    else if (k === 'ver' && /^\d+$/.test(v || '') && Number(v) >= 5) e.ver = Math.min(VER_MAXIMO, Number(v));
    else if (k === 'hasta' && v) {
      const t = Date.parse(v);
      if (!Number.isNaN(t) && t % (FLUJO_MARCOS[e.marco] * 60000) === 0) e.hasta = isoZ(t);
    }
    else if (k === 'sesion' && leeSesion(v)) e.sesion = v;
    else if (k === 'capas' && v) e.capas = CAPAS.filter((c) => v.split(',').includes(c));
    else if (k === 'compuesto' && /^\d+$/.test(v || '') && Number(v) >= 2) e.compuesto = Math.min(COMPUESTO_MAXIMO, Number(v));
    else if (k === 'fijo' && v) {
      const [a, b] = v.split(',').map((x) => Date.parse(x));
      if (a < b && a % 60000 === 0 && b % 60000 === 0 && b - a <= 31 * DIA_MS) e.fijo = [isoZ(a), isoZ(b)];
    }
    else if (k === 'modo' && v === 'tpo') e.modo = 'tpo';
    else if (k === 'sesiones' && /^\d+$/.test(v || '') && Number(v) >= 1) e.sesiones = Math.min(TPO_MAXIMO, Number(v));
  });
  return e;
}

function escribeHash(e) {
  let h = '#' + e.activo + '/' + e.marco + '/' + e.familia;
  if (e.paso !== 'auto') h += '/' + e.paso;
  if (e.unidad === 'usd') h += '/unidad=usd';
  if (e.min) h += '/min=' + e.min;
  if (e.esconde) h += '/esconde';
  if (e.grande) h += '/grande=' + e.grande;
  if (e.hasta) h += '/hasta=' + e.hasta;
  if (e.ver !== VER_DEFECTO) h += '/ver=' + e.ver;
  if (e.sesion && e.sesion !== 'dia') h += '/sesion=' + e.sesion;
  if (e.capas && e.capas.length) h += '/capas=' + e.capas.join(',');
  if (e.compuesto) h += '/compuesto=' + e.compuesto;
  if (e.fijo) h += '/fijo=' + e.fijo.join(',');
  if (e.modo === 'tpo') h += '/modo=tpo';
  if (e.sesiones && e.sesiones !== TPO_SESIONES) h += '/sesiones=' + e.sesiones;
  return h;
}

/* La historia: FLUJO_HISTORIA velas que acaban en `hasta` (una ventana fija del pasado) o, sin `hasta`, en la vela en
 * curso incluida. Las velas empiezan en multiplos del marco desde las 00:00 UTC, como date_bin en el servidor. */
function ventana(e, ahoraMs) {
  const m = FLUJO_MARCOS[e.marco] * 60000;
  const fin = e.hasta ? Date.parse(e.hasta) : (Math.floor(ahoraMs / m) + 1) * m;
  return { desde: isoZ(fin - FLUJO_HISTORIA[e.marco] * m), hasta: isoZ(fin) };
}

/* El latido pide SOLO las velas que todavia pueden cambiar: de la que contiene «ahora - CIERRE_S» a la en curso. */
function ventanaViva(marco, ahoraMs) {
  const m = FLUJO_MARCOS[marco] * 60000;
  return { desde: isoZ(Math.floor((ahoraMs - CIERRE_S * 1000) / m) * m), hasta: isoZ((Math.floor(ahoraMs / m) + 1) * m) };
}

/* ------------------------------------------------------- el estado de una vela
 *   abierta     no ha cerrado (o no hace CIERRE_S): lo que falte todavia puede llegar
 *   hueco       cerrada y SIN una sola fila de cobertura: nadie la escucho. Se dice AUSENTE; no es cero
 *   incompleta  cerrada y con minutos-venue que no se escucharon enteros: `faltan` de `esperados`
 *   vacia       cerrada, escuchada entera y sin operaciones: ese cero si es un dato
 *   completa    cerrada, escuchada entera y con operaciones */
function estadoVela(v, asOfMs, marco) {
  const fin = Date.parse(v.ts) + FLUJO_MARCOS[marco] * 60000;
  const c = v.cobertura || {};
  const esperados = c.minutos_esperados === undefined ? null : c.minutos_esperados;
  if (fin + CIERRE_S * 1000 > asOfMs) return { estado: 'abierta', faltan: null, esperados };
  if (!c.minutos_con_fila) return { estado: 'hueco', faltan: esperados, esperados };
  if (!c.completa) return { estado: 'incompleta', faltan: esperados - c.minutos_completos, esperados };
  if (!(v.niveles || []).length) return { estado: 'vacia', faltan: 0, esperados };
  return { estado: 'completa', faltan: 0, esperados };
}

/* ------------------------------------------------------- aritmetica exacta */
function decimales(t) {
  const i = String(t).indexOf('.');
  return i < 0 ? 0 : String(t).length - i - 1;
}

function entero(t, e) {
  const s = String(t);
  const neg = s.startsWith('-');
  const [ent, fr = ''] = (neg ? s.slice(1) : s).split('.');
  const n = BigInt(ent + fr.padEnd(e, '0'));
  return neg ? -n : n;
}

/* Por nivel (en el orden servido, ascendente): {dc, dv, ac, av} = desequilibrio comprador / vendedor y si es parte de
 * un apilado de ese lado. `niveles` = [{nivel, compra, venta}] en texto decimal; `paso` en texto. */
function desequilibrios(niveles, paso) {
  const out = niveles.map(() => ({ dc: false, dv: false, ac: false, av: false }));
  const n = niveles.length;
  if (!n) return out;
  let e = decimales(paso);
  niveles.forEach((l) => { e = Math.max(e, decimales(l.nivel), decimales(l.compra), decimales(l.venta)); });
  const P = niveles.map((l) => entero(l.nivel, e));
  const C = niveles.map((l) => entero(l.compra, e));
  const V = niveles.map((l) => entero(l.venta, e));
  const s = entero(paso, e);
  const indice = new Map(P.map((p, i) => [p.toString(), i]));
  let suma = 0n;
  for (let i = 0; i < n; i++) suma += C[i] + V[i];
  const N = BigInt(n);
  const lo = P[0];
  const hi = P[n - 1];
  for (let i = 0; i < n; i++) {
    if (P[i] - s >= lo) {
      const j = indice.get((P[i] - s).toString());
      const abajo = j === undefined ? 0n : V[j];
      out[i].dc = C[i] > 0n && C[i] * N >= suma && C[i] >= DESEQ_RAZON * abajo;
    }
    if (P[i] + s <= hi) {
      const j = indice.get((P[i] + s).toString());
      const arriba = j === undefined ? 0n : C[j];
      out[i].dv = V[i] > 0n && V[i] * N >= suma && V[i] >= DESEQ_RAZON * arriba;
    }
  }
  ['dc', 'dv'].forEach((lado) => {
    const marca = lado === 'dc' ? 'ac' : 'av';
    let ini = 0;
    for (let i = 1; i <= n; i++) {
      const sigue = i < n && out[i][lado] && out[i - 1][lado] && P[i] - P[i - 1] === s;
      if (sigue) continue;
      if (out[i - 1][lado] && i - ini >= DESEQ_APILADO) for (let k = ini; k < i; k++) out[k][marca] = true;
      ini = i;
    }
  });
  return out;
}

/* ------------------------------------------------------- como se escribe una cifra
 * Compacta y SIN redondear a cero: lo que no es cero nunca se escribe «0». K109 relee el texto pintado y lo compara con
 * el valor servido a la precision con que se escribio. */
function cifra(t) {
  const x = Number(t);
  const a = Math.abs(x);
  if (x === 0) return '0';
  if (a >= 1e6) return (x / 1e6).toFixed(2) + 'M';
  if (a >= 1e4) return (x / 1e3).toFixed(1) + 'K';
  if (a >= 1e3) return (x / 1e3).toFixed(2) + 'K';
  if (a >= 100) return x.toFixed(0);
  if (a >= 10) return x.toFixed(1);
  if (a >= 1) return x.toFixed(2);
  return x.toPrecision(2);
}

/* El filtro por tamano: el total de la celda contra `min` (atenua, o esconde) y contra `grande` (resalta). */
function filtro(total, e) {
  if (e.min && Number(total) < Number(e.min)) return e.esconde ? 'escondida' : 'atenuada';
  if (e.grande && Number(total) >= Number(e.grande)) return 'grande';
  return 'normal';
}

/* ================================================================= OF-3 · LOS PERFILES (campana 143)
 * LAS SESIONES: la misma plantilla que el servidor (app/orderflow_lectura.py, SESIONES). Por omision el DIA UTC; si el
 * fin no es posterior al inicio, la sesion CRUZA la medianoche y es UNA (de un dia al siguiente). Lo que se pinta de
 * cada sesion (su perfil, su VWAP, su TPO) lo calcula y lo sirve el servidor; aqui solo se sabe DONDE empiezan, para
 * pedir el compuesto y el TPO de las N ultimas. */
const SESIONES = {
  dia: { rotulo: 'Día UTC', inicio: '00:00', fin: '24:00' },
  asia: { rotulo: 'Asia', inicio: '00:00', fin: '08:00' },
  europa: { rotulo: 'Europa', inicio: '07:00', fin: '16:00' },
  eeuu: { rotulo: 'EE.UU.', inicio: '13:30', fin: '20:00' },
};
const CAPAS = ['perfil', 'vwap', 'dinamico'];
// El tope de la ruta (app/orderflow_lectura.py RANGO_SESIONES, medido en P1): de la primera sesion a `hasta`, 7 dias.
const SESIONES_MAXIMO = 7;
const COMPUESTO_DEFECTO = 5;
const COMPUESTO_MAXIMO = SESIONES_MAXIMO;
const TPO_SESIONES = 3;
const TPO_MAXIMO = SESIONES_MAXIMO;
const DIA_MS = 86400000;

function minutoDelDia(t) {
  if (!/^\d\d:\d\d$/.test(t || '')) return null;
  const m = Number(t.slice(0, 2)) * 60 + Number(t.slice(3));
  return Number(t.slice(3)) < 60 && m <= 1440 ? m : null;
}

/* `dia`, `asia`, `europa`, `eeuu` o `HH:MM-HH:MM` -> { nombre, rotulo, inicio, fin, ini (minuto del dia), minutos,
 * cruza } o null si no se entiende (y entonces el hash cae al dia). */
function leeSesion(v) {
  const plantilla = tiene(SESIONES, v || '') ? SESIONES[v] : null;
  const partes = plantilla ? [plantilla.inicio, plantilla.fin] : String(v || '').split('-');
  if (partes.length !== 2) return null;
  const ini = minutoDelDia(partes[0]);
  const fin = minutoDelDia(partes[1]);
  if (ini === null || fin === null || ini === 1440) return null;
  const minutos = (((fin - ini) % 1440) + 1440) % 1440 || 1440;
  return { nombre: v, rotulo: plantilla ? plantilla.rotulo : 'propia', inicio: partes[0], fin: partes[1], ini, minutos,
           cruza: ini + minutos > 1440 };
}

/* El inicio de la ULTIMA sesion que empieza antes de `ms`. */
function inicioSesion(ms, ses) {
  const o = ses.ini * 60000;
  return Math.floor((ms - 1 - o) / DIA_MS) * DIA_MS + o;
}

/* Las N ultimas sesiones que empiezan antes de `hastaMs`: [desde, hasta) toca exactamente esas N. */
function ventanaSesiones(hastaMs, ses, n) {
  return { desde: isoZ(inicioSesion(hastaMs, ses) - (n - 1) * DIA_MS), hasta: isoZ(hastaMs) };
}

/* La ventana de las capas de sesion (perfil y VWAP): la del footprint, sin pasar de las SESIONES_MAXIMO ultimas (el
 * tope de la ruta). Con 1h, 4h o 1d la historia es mas larga: el desde se adelanta al primer borde de vela que lo
 * cumple, y la pantalla lo dice (`recortada`). */
function ventanaCapas(w, ses, marco) {
  const m = FLUJO_MARCOS[marco] * 60000;
  const tope = Math.ceil((inicioSesion(Date.parse(w.hasta), ses) - (SESIONES_MAXIMO - 1) * DIA_MS) / m) * m;
  return Date.parse(w.desde) >= tope ? { desde: w.desde, hasta: w.hasta, recortada: false }
    : { desde: isoZ(tope), hasta: w.hasta, recortada: true };
}

/* El estado de un RANGO de minutos [desde, hasta) servido por /perfil (el dinamico y el fijo): como una vela de
 * cualquier largo. Si no ha cerrado (hasta + CIERRE_S despues de as_of), «en curso»: lo que falta aun puede llegar. */
function estadoRango(desdeMs, hastaMs, c, asOfMs) {
  const cob = c || {};
  const esperados = cob.minutos_esperados === undefined ? null : cob.minutos_esperados;
  if (hastaMs + CIERRE_S * 1000 > asOfMs) return { estado: 'abierta', en_curso: true, faltan: null, esperados };
  if (!cob.minutos_con_fila) return { estado: 'hueco', en_curso: false, faltan: esperados, esperados };
  if (!cob.completa) {
    return { estado: 'incompleta', en_curso: false, faltan: esperados - cob.minutos_completos, esperados };
  }
  return { estado: 'completa', en_curso: false, faltan: 0, esperados };
}

/* El estado de una SESION servida (sesiones, vwap, tpo): el servidor dice si sigue en curso y su cobertura hasta su
 * corte; lo que falta se dice aunque siga en curso, y una sesion que acaba de empezar no echa nada en falta. */
function estadoSesion(s) {
  const c = s.cobertura || {};
  const esperados = c.minutos_esperados === undefined ? null : c.minutos_esperados;
  let estado = 'completa';
  if (esperados !== 0 && !c.minutos_con_fila) estado = 'hueco';
  else if (esperados !== 0 && !c.completa) estado = 'incompleta';
  return { estado, en_curso: !!s.en_curso, faltan: estado === 'completa' ? 0 : esperados - (c.minutos_completos || 0),
           esperados };
}

/* La marca que se escribe sobre una capa: en curso, hueco o cuantos minutos-venue faltan (nada si no hay nada que
 * decir). */
function marcaCapa(st) {
  const partes = [];
  if (st.en_curso) partes.push('en curso');
  if (st.estado === 'hueco') partes.push('hueco');
  else if (st.faltan) partes.push('faltan ' + st.faltan + '/' + st.esperados);
  return partes.join(' · ') || null;
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    FLUJO_MARCOS, FLUJO_HISTORIA, FAMILIAS, CIERRE_S, VER_DEFECTO, leeHash, escribeHash, ventana, ventanaViva,
    estadoVela, desequilibrios, cifra, filtro, isoZ,
  };
  Object.assign(module.exports, { SESIONES, CAPAS, SESIONES_MAXIMO, COMPUESTO_DEFECTO, TPO_SESIONES, leeSesion,
                                  inicioSesion, ventanaSesiones, ventanaCapas, estadoRango, estadoSesion, marcaCapa });
}
