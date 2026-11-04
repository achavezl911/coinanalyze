'use strict';
/* EL LIBRO · lo que se CALCULA (campana 145, OF-4b). Funciones puras: las prueba `node --test` y K111 las recalcula
 * por su cuenta. Nada de aqui toca el DOM ni pide nada.
 *
 * LAS FAMILIAS son las de OF-2: FAMILIAS de static/flujo/flujo-calculo.js, que esta pagina carga delante (y de ahi
 * tambien `cifra` e `isoZ`). Nunca se suman dos. Tambien se puede mirar UN VENUE SOLO.
 *
 * LO QUE CONOCE UN VENUE, de una foto o de un libro vivo al paso P: la compra, desde su nivel mas profundo hacia arriba
 * (por encima de la mejor compra no hay compras: es un cero CONOCIDO); la venta, desde abajo hasta su nivel mas
 * profundo. Su tramo conocido es [nivel mas profundo de la compra, nivel mas profundo de la venta]; fuera, no se sabe.
 * POR NIVEL, LA FAMILIA: la suma de los venues que lo CONOCEN y cuantos son (n de N). Si no lo conoce ninguno, el nivel
 * es DESCONOCIDO: nunca se suma ni se pinta como cero. Un venue sin foto en ese instante, o sin libro vivo, no conoce
 * nada. Los niveles van por su indice entero k (nivel = k * P): sin errores de coma flotante al comparar.
 */

const LIBRO_ACTIVOS = ['BTC', 'ETH', 'SOL'];
const LIBRO_VENUES = ['binance_usdm', 'binance_spot', 'bybit_linear', 'bybit_spot', 'okx_swap', 'okx_spot',
  'bitget_usdt', 'deribit_perp', 'coinbase_spot'];
// El paso al que se guardan las fotos (app/libro.py PASOS): el mapa no puede ir mas fino; los pasos validos son sus
// multiplos enteros.
const LIBRO_PASO = { BTC: '10', ETH: '0.5', SOL: '0.02' };
const LIBRO_VENTANAS = { '30m': 30, '1h': 60, '4h': 240, '12h': 720, '1d': 1440, '3d': 4320 };
const LIBRO_VENTANA_DEFECTO = '1h';
const LIBRO_TOPE_FOTOS = 2000; // app/libro_lectura.py TOPE_FOTOS
const LIBRO_FOTO_S = 5; // app/libro.py FOTO_S
// La base escribe cada minuto a los 2 s de cerrarse (app/libro.py CIERRE_S): un instante cuyo minuto no hace 62 s que
// cerro puede no estar escrito todavia. Eso no es un hueco: es «sin escribir aun».
const LIBRO_ESCRITO_S = 62;
const LIBRO_REGISTRO_MIN = 30; // mas atras, el mapa es un REGISTRO (el aviso de /api/libro/referencia)

function libroVenues(familia) {
  if (Object.prototype.hasOwnProperty.call(FAMILIAS, familia)) return FAMILIAS[familia].venues.slice();
  return LIBRO_VENUES.includes(familia) ? [familia] : null;
}

function rotuloFamilia(familia) {
  return Object.prototype.hasOwnProperty.call(FAMILIAS, familia) ? FAMILIAS[familia].rotulo : familia + ' (un venue)';
}

/* ¿`t` es un multiplo entero positivo de `base`? En aritmetica exacta (texto decimal escalado a BigInt). */
function esMultiplo(t, base) {
  if (!/^\d+(\.\d+)?$/.test(String(t || ''))) return false;
  const d = Math.max((String(t).split('.')[1] || '').length, (String(base).split('.')[1] || '').length);
  const n = BigInt(String(t).replace('.', '') + '0'.repeat(d - (String(t).split('.')[1] || '').length));
  const b = BigInt(String(base).replace('.', '') + '0'.repeat(d - (String(base).split('.')[1] || '').length));
  return n > 0n && n % b === 0n;
}

/* ------------------------------------------------------------------ el hash
 * `#<activo>/<familia|venue>[/<paso>][/<ventana>]` y detras, en cualquier orden, `unidad=usd`, `hasta=<ISO>` (una
 * ventana fija del pasado) y `ver=<n>` (cuantas columnas a la vista; por omision, todas). Una vista = una URL. Lo que no
 * se entiende cae al defecto y la pagina reescribe el hash. */
function leeHashLibro(hash) {
  const partes = String(hash || '').replace(/^#/, '').split('/').filter(Boolean);
  const e = { activo: 'BTC', familia: 'perp', paso: null, ventana: LIBRO_VENTANA_DEFECTO, unidad: 'base', hasta: null,
              ver: null };
  const a = String(partes[0] || '').toUpperCase();
  if (LIBRO_ACTIVOS.includes(a)) e.activo = a;
  if (partes[1] && libroVenues(partes[1])) e.familia = partes[1];
  partes.slice(2).forEach((p) => {
    const [k, v] = p.split('=');
    if (v === undefined && Object.prototype.hasOwnProperty.call(LIBRO_VENTANAS, k)) e.ventana = k;
    else if (v === undefined && esMultiplo(k, LIBRO_PASO[e.activo])) e.paso = k;
    else if (k === 'unidad' && (v === 'usd' || v === 'base')) e.unidad = v;
    else if (k === 'ver' && /^\d+$/.test(v || '') && Number(v) >= 10) e.ver = Number(v);
    else if (k === 'hasta' && v) {
      const t = Date.parse(v);
      if (!Number.isNaN(t) && t % 60000 === 0) e.hasta = isoZ(t);
    }
  });
  if (!e.paso) e.paso = LIBRO_PASO[e.activo];
  return e;
}

function escribeHashLibro(e) {
  let h = '#' + e.activo + '/' + e.familia;
  if (e.paso !== LIBRO_PASO[e.activo]) h += '/' + e.paso;
  if (e.ventana !== LIBRO_VENTANA_DEFECTO) h += '/' + e.ventana;
  if (e.unidad === 'usd') h += '/unidad=usd';
  if (e.hasta) h += '/hasta=' + e.hasta;
  if (e.ver) h += '/ver=' + e.ver;
  return h;
}

/* ------------------------------------------------------------------ la ventana del mapa
 * EL CADA: el menor multiplo de 5 s con el que la historia cabe en el tope de fotos de la ruta (venues x instantes). */
function cadaPara(nVenues, ventanaS) {
  let c = LIBRO_FOTO_S;
  while (nVenues * Math.ceil(ventanaS / c) > LIBRO_TOPE_FOTOS) c += LIBRO_FOTO_S;
  return c;
}

/* La historia: `ventana` que acaba en `hasta` (fija) o, sin el, en el instante en curso incluido. Las columnas son los
 * instantes multiplos de `cada` (los que la ruta devuelve: extract(epoch) % cada = 0). */
function ventanaLibro(e, ahoraMs) {
  const s = LIBRO_VENTANAS[e.ventana] * 60;
  const cada = cadaPara(libroVenues(e.familia).length, s);
  const c = cada * 1000;
  const hasta = e.hasta ? Date.parse(e.hasta) : (Math.floor(ahoraMs / c) + 1) * c;
  const desde = hasta - s * 1000;
  const columnas = [];
  for (let t = Math.ceil(desde / c) * c; t < hasta; t += c) columnas.push(t);
  return { desde: isoZ(desde), hasta: isoZ(hasta), cada, columnas };
}

/* ------------------------------------------------------------------ lo que conoce un venue */
function kDe(t, P) {
  return Math.round(Number(t) / P);
}

function nivelTexto(k, paso) {
  const d = (String(paso).split('.')[1] || '').length;
  const s = (k * Number(paso)).toFixed(d);
  return d ? s.replace(/0+$/, '').replace(/\.$/, '') : s;
}

/* Un libro (una foto servida o un aviso vivo) al paso P -> lo que conoce:
 *   { venue, compra, venta (texto exacto), kc (nivel de la mejor compra), qc (cantidades hacia abajo desde kc), kv, qv
 *     (hacia arriba desde kv), lo, hi (su tramo conocido) }
 * `compras`/`ventas` llegan como { desde, cantidades } (foto) o como [[nivel, cantidad], ...] (vivo); null o vacio si
 * ni el mejor nivel se conoce entero a ese paso: entonces se conoce desde el nivel siguiente. */
function libroDe(venue, compra, venta, compras, ventas, paso) {
  const P = Number(paso);
  const lado = (x) => {
    if (!x) return null;
    if (Array.isArray(x)) return x.length ? { k: kDe(x[0][0], P), q: x.map((p) => Number(p[1])) } : null;
    return x.cantidades && x.cantidades.length ? { k: kDe(x.desde, P), q: x.cantidades.map(Number) } : null;
  };
  const c = lado(compras);
  const v = lado(ventas);
  const kc = c ? c.k : Math.floor(Number(compra) / P + 1e-9);
  const kv = v ? v.k : Math.floor(Number(venta) / P + 1e-9);
  return { venue, compra: String(compra), venta: String(venta), kc, qc: c ? c.q : [], kv, qv: v ? v.q : [],
           lo: c ? kc - c.q.length + 1 : kc + 1, hi: v ? kv + v.q.length - 1 : kv - 1 };
}

/* La cantidad de un libro en el nivel k: [compra, venta], o null si no lo conoce. */
function enNivel(L, k) {
  if (k < L.lo || k > L.hi) return null;
  const c = k > L.kc ? 0 : L.qc[L.kc - k] || 0;
  const v = k < L.kv ? 0 : L.qv[k - L.kv] || 0;
  return [c, v];
}

/* LA FAMILIA en un instante: por nivel k de [lo, hi] (la union de lo que conocen), la suma de los que lo conocen y
 * cuantos son. `libros` = los de los venues con libro en ese instante; N = los venues de la familia. */
function sumaFamilia(libros, N) {
  if (!libros.length) return null;
  const lo = Math.min(...libros.map((L) => L.lo));
  const hi = Math.max(...libros.map((L) => L.hi));
  if (hi < lo) return null;
  const filas = hi - lo + 1;
  const c = new Float64Array(filas);
  const v = new Float64Array(filas);
  const n = new Uint8Array(filas);
  libros.forEach((L) => {
    for (let k = Math.max(lo, L.lo); k <= L.hi; k++) {
      const x = enNivel(L, k);
      c[k - lo] += x[0];
      v[k - lo] += x[1];
      n[k - lo] += 1;
    }
  });
  let mc = null;
  let mv = null;
  libros.forEach((L) => {
    if (mc === null || Number(L.compra) > Number(mc)) mc = L.compra;
    if (mv === null || Number(L.venta) < Number(mv)) mv = L.venta;
  });
  return { lo, hi, c, v, n, N, venues: libros.map((L) => L.venue), mejorCompra: mc, mejorVenta: mv };
}

/* ------------------------------------------------------------------ el mapa: la rejilla de columnas
 * Por instante de la ventana: `foto` (algun venue de la familia tiene foto), `hueco` (ninguno: nadie la escucho, o el
 * libro no era valido) o `pendiente` (la base aun no ha escrito su minuto). Nunca se rellena ni se estira una columna. */
function estadoColumna(t, hayFoto, asOfMs) {
  if (hayFoto) return 'foto';
  return Math.floor(t / 60000) * 60000 + 60000 + LIBRO_ESCRITO_S * 1000 > asOfMs ? 'pendiente' : 'hueco';
}

function columnasDeFotos(d, venues, instantes, asOfMs) {
  const porTs = new Map();
  (d.fotos || []).forEach((f) => {
    if (!venues.includes(f.venue)) return;
    const t = Date.parse(f.ts);
    if (!porTs.has(t)) porTs.set(t, []);
    porTs.get(t).push(f);
  });
  return instantes.map((t) => {
    const fotos = porTs.get(t) || [];
    const libros = fotos.map((f) => libroDe(f.venue, f.compra, f.venta, f.compras, f.ventas, d.paso));
    return { ts: t, estado: estadoColumna(t, fotos.length > 0, asOfMs), origen: 'historia', fotos,
             suma: sumaFamilia(libros, venues.length) };
  });
}

/* Una foto servida como si fuera un aviso del vivo (la escalera de una ventana FIJA es la de su ultima foto). */
function fotoComoAviso(f) {
  return { tipo: 'libro', venue: f.venue, compra: f.compra, venta: f.venta, compras: f.compras, ventas: f.ventas,
           ts_libro_ms: Date.parse(f.ts_libro), foto: f.ts };
}

/* ------------------------------------------------------------------ la escalera
 * Por nivel k, de la venta conocida mas alta a la compra conocida mas baja: compra, venta (null si DESCONOCIDO),
 * cuantos lo conocen, las mejores marcadas y la ACUMULADA desde el medio: la compra desde el nivel de la mejor compra
 * hacia abajo, la venta desde el de la mejor venta hacia arriba. Un nivel que no conocen todos la hace PARCIAL (es un
 * minimo); uno que no conoce ninguno la corta: mas alla no se sabe. En USD, cada nivel vale su cantidad por el precio
 * del CENTRO del nivel (la foto y el relevo no guardan los precios de dentro: el error es como mucho medio paso). */
function enUnidad(q, k, paso, unidad) {
  return unidad === 'usd' ? q * (k + 0.5) * Number(paso) : q;
}

/* ------------------------------------------------------------------ la escala de color del mapa (149 B)
 * LOS DOS CORTES DE LO VISIBLE: sobre las cantidades > 0 de las celdas conocidas A LA VISTA (columnas j0..j1 con foto,
 * niveles lo..hi), el corte bajo es su percentil pLo y el alto su pHi (por omision 20 y 98; los mueve el mando de
 * intensidad). Percentil p de n valores ordenados: el de puesto floor(p / 100 * (n - 1)). Por debajo del corte bajo, el
 * fondo; entre los dos, lineal (indice 0..255); por encima del alto, saturado (255): un muro sale como una linea viva,
 * sin marca aparte. Un cero conocido es el fondo (-1). Antes (145 P2) era el percentil de la ventana entera: un muro de
 * otra hora apagaba lo que se mira. */
const MAPA_PERCENTILES = [20, 98];

function percentilDe(ord, p) {
  return ord.length ? ord[Math.min(ord.length - 1, Math.floor((p / 100) * (ord.length - 1)))] : null;
}

function escalaCortes(columnas, j0, j1, lo, hi, paso, unidad, pc) {
  const [pLo, pHi] = pc || MAPA_PERCENTILES;
  const xs = [];
  for (let j = Math.max(0, j0); j <= j1; j++) {
    const col = columnas[j];
    const s = col && col.estado === 'foto' ? col.suma : null;
    if (!s) continue;
    for (let k = Math.max(lo, s.lo); k <= Math.min(hi, s.hi); k++) {
      const i = k - s.lo;
      const q = s.n[i] ? enUnidad(s.c[i] + s.v[i], k, paso, unidad) : 0;
      if (q > 0) xs.push(q);
    }
  }
  const ord = Float64Array.from(xs).sort();
  const a = percentilDe(ord, pLo);
  const b = percentilDe(ord, pHi);
  return {
    n: ord.length,
    percentiles: [pLo, pHi],
    corte: [a, b],
    indice(q) {
      if (!(q > 0) || !ord.length || q < a) return -1;
      if (q >= b) return 255;
      return Math.min(255, Math.floor((255 * (q - a)) / (b - a)));
    },
  };
}

/* ------------------------------------------------------------------ la capa honda (149 B)
 * /api/libro/honda: por venue, una foto cada 30 s con la escalera al paso GUARDADO desde el borde del alcance vivo hacia
 * fuera (compras.desde hacia abajo, ventas.desde hacia arriba). Una columna en el instante t usa, por venue, su ULTIMA
 * foto honda con ts <= t y t - ts <= HONDA_RANCIA_S; sin ella, o rancia (sin niveles), ese venue no conoce esos
 * niveles. Dentro del alcance vivo DE ESE VENUE en esa columna manda el vivo: la honda solo ANADE niveles de fuera
 * (compras por debajo de su lo, ventas por encima de su hi). Al paso de la vista P = m x paso guardado, por suelo; un
 * paso que no es multiplo no se pinta (lo dice la linea de debajo del mapa). Cuenta en n como un venue mas que conoce. */
const HONDA_RANCIA_S = 75; // app/libro_honda.py RANCIA_S

function hondaPorVenue(d) {
  const m = new Map();
  ((d && d.fotos) || []).forEach((f) => {
    if (!m.has(f.venue)) m.set(f.venue, []);
    m.get(f.venue).push({ t: Date.parse(f.ts), f });
  });
  m.forEach((xs) => xs.sort((x, y) => x.t - y.t));
  return m;
}

/* La foto honda de un venue para el instante t: la ultima con ts <= t, si no tiene mas de HONDA_RANCIA_S y trae niveles. */
function hondaEn(porVenue, venue, t) {
  const xs = porVenue.get(venue);
  if (!xs || !xs.length) return null;
  let a = 0;
  let b = xs.length;
  while (a < b) {
    const m = (a + b) >> 1;
    if (xs[m].t <= t) a = m + 1;
    else b = m;
  }
  const x = a ? xs[a - 1] : null;
  if (!x || t - x.t > HONDA_RANCIA_S * 1000 || x.f.rancia || (!x.f.compras && !x.f.ventas)) return null;
  return { edad_s: (t - x.t) / 1000, f: x.f };
}

/* Los niveles (al paso de la vista) que una foto honda anade a un venue cuyo libro vivo es L (o null): Map k -> [c, v].
 * Aritmetica entera en pasos guardados: m = P / paso guardado. */
function nivelesHondos(f, L, paso, pasoGuardado) {
  const s = Number(pasoGuardado);
  const m = Math.round(Number(paso) / s);
  const out = new Map();
  const pon = (ks, lado, q) => {
    const k = Math.floor(ks / m);
    if (L && (lado === 0 ? k >= L.lo : k <= L.hi)) return;
    const x = out.get(k) || [0, 0];
    x[lado] += Number(q);
    out.set(k, x);
  };
  if (f.compras) {
    const k0 = Math.round(Number(f.compras.desde) / s);
    f.compras.cantidades.forEach((q, i) => pon(k0 - i, 0, q));
  }
  if (f.ventas) {
    const k0 = Math.round(Number(f.ventas.desde) / s);
    f.ventas.cantidades.forEach((q, i) => pon(k0 + i, 1, q));
  }
  return out;
}

/* La suma de la familia con los niveles hondos de `extras` ([{venue, edad_s, niveles}]): cada uno suma en c/v, cuenta
 * en n y en h (cuantos de los que lo conocen son de la capa honda). */
function sumaConHonda(s, extras) {
  let lo = s.lo;
  let hi = s.hi;
  extras.forEach((e) => e.niveles.forEach((_, k) => {
    lo = Math.min(lo, k);
    hi = Math.max(hi, k);
  }));
  const filas = hi - lo + 1;
  const c = new Float64Array(filas);
  const v = new Float64Array(filas);
  const n = new Uint8Array(filas);
  const h = new Uint8Array(filas);
  for (let i = 0; i < s.n.length; i++) {
    c[s.lo - lo + i] = s.c[i];
    v[s.lo - lo + i] = s.v[i];
    n[s.lo - lo + i] = s.n[i];
  }
  extras.forEach((e) => e.niveles.forEach((x, k) => {
    c[k - lo] += x[0];
    v[k - lo] += x[1];
    n[k - lo] += 1;
    h[k - lo] += 1;
  }));
  return Object.assign({}, s, { lo, hi, c, v, n, h,
                                honda: extras.map((e) => ({ venue: e.venue, edad_s: e.edad_s })) });
}

/* Junta la capa honda a las columnas con foto (en su sitio). -> {pinta, motivo, columnas: cuantas la llevan}.
 * Se puede volver a juntar (149 B r1, el vivo): la suma sin honda se guarda en `col.sinHonda` la primera vez y cada
 * junta parte de ella; `desdeMs` junta solo las columnas con ts >= desdeMs (las que una foto nueva puede cambiar). El
 * libro vivo de cada venue sale de `col.libros` (las columnas del vivo) o de `col.fotos` (las de la historia). */
function juntaHonda(columnas, d, venues, paso, pasoGuardado, desdeMs) {
  if (!d || !d.fotos) return { pinta: false, motivo: 'sin capa honda', columnas: 0 };
  if (!esMultiplo(paso, pasoGuardado)) {
    return { pinta: false, motivo: 'paso ' + paso + ' más fino que el guardado de la capa honda (' + pasoGuardado
      + '): no se pinta', columnas: 0 };
  }
  const por = hondaPorVenue(d);
  columnas.forEach((col) => {
    if (col.estado !== 'foto' || !col.suma || (desdeMs !== undefined && col.ts < desdeMs)) return;
    if (!col.sinHonda) col.sinHonda = col.suma;
    const extras = [];
    venues.forEach((venue) => {
      const x = hondaEn(por, venue, col.ts);
      if (!x) return;
      let L = (col.libros || []).find((y) => y.venue === venue) || null;
      if (!col.libros) {
        const f = (col.fotos || []).find((y) => y.venue === venue);
        L = f ? libroDe(f.venue, f.compra, f.venta, f.compras, f.ventas, paso) : null;
      }
      const niveles = nivelesHondos(x.f, L, paso, pasoGuardado);
      if (niveles.size) extras.push({ venue, edad_s: x.edad_s, niveles });
    });
    col.suma = extras.length ? sumaConHonda(col.sinHonda, extras) : col.sinHonda;
  });
  const cuantas = columnas.filter((col) => col.suma && col.suma.honda && col.suma.honda.length).length;
  return { pinta: true, motivo: null, columnas: cuantas };
}

/* Lo que conoce el libro vivo de cada venue en una columna con foto, {venue: [lo, hi]} (de `col.libros`, el vivo, o de
 * `col.fotos`, la historia): dentro manda el vivo y la capa honda no anade. Se guarda en la columna (se declara en cada
 * pintado). */
function alcanceColumna(col, paso) {
  if (col.estado !== 'foto') return null;
  if (!col.alcance) {
    const ls = col.libros || (col.fotos || []).map((f) => libroDe(f.venue, f.compra, f.venta, f.compras, f.ventas, paso));
    col.alcance = {};
    ls.forEach((L) => { col.alcance[L.venue] = [L.lo, L.hi]; });
  }
  return col.alcance;
}

function escaleraFamilia(s, paso, unidad) {
  if (!s) return [];
  const P = Number(paso);
  const kb = Math.floor(Number(s.mejorCompra) / P + 1e-9);
  const ka = Math.floor(Number(s.mejorVenta) / P + 1e-9);
  const filas = [];
  for (let k = s.hi; k >= s.lo; k--) {
    const i = k - s.lo;
    filas.push({ k, nivel: nivelTexto(k, paso), compra: s.n[i] ? enUnidad(s.c[i], k, paso, unidad) : null,
                 venta: s.n[i] ? enUnidad(s.v[i], k, paso, unidad) : null, n: s.n[i], N: s.N, mejor_compra: k === kb,
                 mejor_venta: k === ka, acum_compra: null, acum_venta: null, acum_parcial_compra: false,
                 acum_parcial_venta: false });
  }
  const porK = new Map(filas.map((f) => [f.k, f]));
  [['compra', kb, -1], ['venta', ka, 1]].forEach(([lado, k0, dir]) => {
    let acc = 0;
    let parcial = false;
    for (let k = k0; k >= s.lo && k <= s.hi; k += dir) {
      const f = porK.get(k);
      if (!f || !f.n) break;
      acc += f[lado];
      parcial = parcial || f.n < s.N;
      f['acum_' + lado] = acc;
      f['acum_parcial_' + lado] = parcial;
    }
  });
  return filas;
}

/* ------------------------------------------------------------------ la escalera profesional (campana 149, ronda A)
 * BARRAS (L-03): fraccion = min(1, cantidad / tope), con tope = p95 (rango mas cercano) de las cantidades > 0 de las
 * filas VISIBLES, los dos lados en UNA escala. GRANDES (L-05): cantidad >= ESC_GRANDE_X x la media de las cantidades > 0
 * de ese lado en las visibles. TOTALES (L-09): la profundidad visible de cada lado, la proporcion y el spread. */
const ESC_GRANDE_X = 3;

function p95(xs) {
  if (!xs.length) return null;
  const o = xs.slice().sort((a, b) => a - b);
  return o[Math.ceil(0.95 * o.length) - 1];
}

function medidasVisibles(filas) {
  const qc = [];
  const qv = [];
  filas.forEach((f) => {
    if (!f.n) return;
    if (f.compra > 0) qc.push(f.compra);
    if (f.venta > 0) qv.push(f.venta);
  });
  const media = (xs) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);
  return { tope: p95(qc.concat(qv)), media_compra: media(qc), media_venta: media(qv) };
}

function fraccionBarra(q, tope) {
  return tope > 0 ? Math.min(1, q / tope) : 0;
}

function esGrande(q, media) {
  return media !== null && q > 0 && q >= ESC_GRANDE_X * media;
}

function decimales(x) {
  return (String(x).split('.')[1] || '').length;
}

function totalesVisibles(filas, mejorCompra, mejorVenta) {
  let c = 0;
  let v = 0;
  let n = 0;
  filas.forEach((f) => {
    if (!f.n) return;
    c += f.compra;
    v += f.venta;
    n += 1;
  });
  const spread = mejorCompra === null || mejorVenta === null ? null
    : (Number(mejorVenta) - Number(mejorCompra)).toFixed(Math.max(decimales(mejorCompra), decimales(mejorVenta)));
  if (!n) return { filas: 0, compra: null, venta: null, pct_compra: null, spread };
  return { filas: n, compra: c, venta: v, pct_compra: c + v > 0 ? (100 * c) / (c + v) : null, spread };
}

/* EL VOLUMEN RECIENTE @bid / @ask (L-07), de las paginas de /api/orderflow/cinta EN EL ORDEN EN QUE LLEGAN. Sin reloj:
 * todo sale de las horas de las operaciones y del as_of de cada pagina. Devuelve un estado NUEVO.
 *   La PRIMERA pagina solo marca lo visto (la escalera empieza vacia): cuenta lo que llega despues.
 *   Se deduplica por venue e id. Nivel = el de la escalera. «venta» suma a @bid y «compra» a @ask, en base y en USD.
 *   Un nivel se reinicia si el precio (la ultima operacion) estaba en otro y vuelve tras mas de RECIENTE_VUELVE_MS.
 *   FALTAN OPERACIONES si una pagina truncada no solapa con lo ya visto, o si entre dos paginas buenas pasaron mas de
 *   RECIENTE_HUECO_MS (la pagina cubre 1 min): la marca se queda hasta limpiaReciente. */
const RECIENTE_VUELVE_MS = 2500;
const RECIENTE_HUECO_MS = 55000;
const RECIENTE_OLVIDO_MS = 180000;

function recienteVacio() {
  return { primado: false, corte: null, vistos: new Map(), niveles: new Map(), ultimoK: null, ultima: null,
           falta: null, paginas: 0, asOf: null, dia: null, kmin: null, kmax: null, maxMs: null };
}

function ordenOps(x, y) {
  if (x.ms !== y.ms) return x.ms - y.ms;
  if (x.o.venue !== y.o.venue) return x.o.venue < y.o.venue ? -1 : 1;
  const a = String(x.o.id);
  const b = String(y.o.id);
  return a < b ? -1 : a > b ? 1 : 0;
}

function sumaReciente(prev, pagina, paso) {
  const P = Number(paso);
  const s = Object.assign({}, prev, { primado: true, vistos: new Map(prev.vistos), niveles: new Map(),
                                      paginas: prev.paginas + 1 });
  prev.niveles.forEach((x, k) => s.niveles.set(k, Object.assign({}, x)));
  const ops = (pagina.operaciones || []).map((o) => ({ o, ms: Date.parse(o.ts), clave: o.venue + '|' + o.id }));
  const nuevas = ops.filter((x) => !s.vistos.has(x.clave));
  const asOf = Date.parse(pagina.as_of);
  if (prev.primado && !s.falta) {
    if (pagina.truncada && nuevas.length === ops.length) s.falta = { motivo: 'truncada', pagina: s.paginas };
    else if (prev.asOf !== null && asOf - prev.asOf > RECIENTE_HUECO_MS) s.falta = { motivo: 'hueco', pagina: s.paginas };
  }
  s.asOf = asOf;
  nuevas.sort(ordenOps);
  nuevas.forEach(({ o, ms, clave }) => {
    s.vistos.set(clave, ms);
    if (s.maxMs === null || ms > s.maxMs) s.maxMs = ms;
    const k = Math.floor(Number(o.precio) / P + 1e-9);
    const dia = o.ts.slice(0, 10);
    if (s.dia === null || dia > s.dia) Object.assign(s, { dia, kmin: k, kmax: k });
    else if (dia === s.dia) Object.assign(s, { kmin: Math.min(s.kmin, k), kmax: Math.max(s.kmax, k) });
    if (!s.ultima || ms >= s.ultima.ms) {
      s.ultima = { k, ms, ts: o.ts, venue: o.venue, id: o.id, precio: o.precio, base: Number(o.base),
                   usd: Number(o.usd), agresor: o.agresor };
    }
    if (prev.primado && (s.corte === null || ms > s.corte)) {
      let x = s.niveles.get(k);
      if (x && s.ultimoK !== k && ms - x.ultMs > RECIENTE_VUELVE_MS) Object.assign(x, { b: 0, bu: 0, a: 0, au: 0 });
      if (!x) {
        x = { b: 0, bu: 0, a: 0, au: 0, nb: 0, na: 0, ultMs: ms };
        s.niveles.set(k, x);
      }
      const lado = o.agresor === 'venta' ? 'b' : o.agresor === 'compra' ? 'a' : null;
      if (lado) {
        x[lado] += Number(o.base);
        x[lado + 'u'] += Number(o.usd);
        x['n' + lado] += 1;
      }
      x.ultMs = Math.max(x.ultMs, ms);
    }
    s.ultimoK = k;
  });
  if (!prev.primado) s.corte = s.maxMs;
  if (s.maxMs !== null) s.vistos.forEach((ms, c) => { if (ms < s.maxMs - RECIENTE_OLVIDO_MS) s.vistos.delete(c); });
  return s;
}

/* El boton Limpiar: lo acumulado y la marca de faltan, fuera; lo visto se queda (no se vuelve a contar). */
function limpiaReciente(prev) {
  return Object.assign({}, prev, { niveles: new Map(), falta: null, corte: prev.primado ? prev.maxMs : null });
}

/* Lo reciente de un nivel en la unidad de la vista: [@bid, @ask], o null si ninguna operacion contada cayo en el. */
function recienteEn(rec, k, unidad) {
  const x = rec && rec.niveles.get(k);
  if (!x) return null;
  return unidad === 'usd' ? [x.bu, x.au] : [x.b, x.a];
}

/* MAXIMO Y MINIMO DE LA SESION UTC: los niveles extremos de /api/orderflow/perfil desde las 00:00Z (`perfil` =
 * { dia, niveles }), ampliados por la cinta del mismo dia. Un dia nuevo en la cinta deja atras lo del perfil. */
function extremosSesion(perfil, rec, paso) {
  const P = Number(paso);
  let lo = null;
  let hi = null;
  let dia = null;
  if (perfil && perfil.niveles.length) {
    const ks = perfil.niveles.map((n) => kDe(n.nivel, P));
    lo = Math.min(...ks);
    hi = Math.max(...ks);
    dia = perfil.dia;
  }
  if (rec && rec.dia !== null && (dia === null || rec.dia >= dia)) {
    if (dia !== null && rec.dia > dia) lo = hi = null;
    dia = rec.dia;
    lo = lo === null ? rec.kmin : Math.min(lo, rec.kmin);
    hi = hi === null ? rec.kmax : Math.max(hi, rec.kmax);
  }
  return lo === null ? null : { lo, hi, dia, de_perfil: !!(perfil && perfil.niveles.length) };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    LIBRO_ACTIVOS, LIBRO_VENUES, LIBRO_PASO, LIBRO_VENTANAS, LIBRO_ESCRITO_S, libroVenues, rotuloFamilia, esMultiplo,
    leeHashLibro, escribeHashLibro, cadaPara, ventanaLibro, kDe, nivelTexto, libroDe, enNivel, sumaFamilia,
    estadoColumna, columnasDeFotos, fotoComoAviso, enUnidad, MAPA_PERCENTILES, percentilDe, escalaCortes,
    HONDA_RANCIA_S, hondaPorVenue, hondaEn, nivelesHondos, sumaConHonda, juntaHonda, alcanceColumna, escaleraFamilia,
    ESC_GRANDE_X, RECIENTE_VUELVE_MS, RECIENTE_HUECO_MS, p95, medidasVisibles, fraccionBarra, esGrande,
    totalesVisibles, recienteVacio, sumaReciente, limpiaReciente, recienteEn, extremosSesion,
  };
}
