'use strict';
/* LA MESA · la vista ENTRADAS · `#<marco>/<activo>/entradas`  (campana 137, E2)
 * ---------------------------------------------------------------------------
 * ESTE FICHERO SOLO CALCULA DOS COSAS: UNA EDAD Y UNA CUENTA ATRAS, desde instantes servidos.
 * Todo lo demas -cada cifra, cada estado, cada frase que dice por que algo no esta o que
 * significa un plan- llega de `/api/mesa/entradas` y se pinta TAL CUAL (app/entradas/vista.py).
 * Si algo hace falta y no llega, se anade alli: aqui no se deduce.
 *
 * SON PLANES APUNTADOS ANTES DE SABER COMO ACABAN. No es una senal. Esta vista no pinta ninguna
 * fraccion ni tasa de aciertos. De lo que el precio hizo despues de cada DISPARADO pinta su RESULTADO
 * (E3, campana 139) tal como llega: es lo que le paso a UN plan, se escribe como texto, y ni el color
 * ni el orden de una fila dependen de el. Un DISPARADO que ya acabo no se pinta VIVO: su chip dice su
 * salida, servida.
 *
 * TODA LA PANTALLA SALE DE UNA RESPUESTA, la ultima buena. Por eso lo pintado se puede comparar
 * con ella nodo a nodo, y por eso un refresco que falla no deja media pantalla de otro instante.
 *
 * EL CONTRATO DE DOM, que es lo que lee la red (K106):
 *     data-k="<ruta>"           el texto del nodo es el valor servido en esa ruta de la respuesta
 *     data-cifra="<clase>"      ese valor es una CIFRA, de una de las clases que la red permite
 *     data-calc="edad|cuenta"   lo calcula el reloj de aqui, desde el instante de data-instante
 *     data-plan="<id>"          un plan; data-vivo dice si la pantalla lo esta dando por vivo
 *     data-resultado="vivo|acabado"  lo que dice su resultado servido; con «acabado», data-rotulo
 *     data-aviso="<cual>"       lo que se dice ARRIBA cuando no hay dato o el generador no late
 */

const ENT_REFRESCO_S = 45; // de reserva: la cadencia la sirve `frescura.refresco_s`

let _ent = null; // la ultima respuesta BUENA: { datos, tLlegada }
let _entFallo = null; // el ultimo intento, si no trajo dato: el sobre de `pedir`
let _entTic = null;
let _entRef = null;

function entReloj() {
  return (window.performance || Date).now();
}

function entPasado() {
  return _ent ? Math.max(0, (entReloj() - _ent.tLlegada) / 1000) : 0;
}

/* LAS DOS UNICAS CUENTAS DEL CLIENTE. Las dos restan DOS INSTANTES SERVIDOS entre si y suman lo
 * transcurrido aqui desde que llego la respuesta: el desfase entre el reloj del servidor y el del
 * navegador se cancela, y la cifra sigue corriendo aunque el refresco falle (A78). */
function entEdad(iso) {
  return (Date.parse(_ent.datos.as_of) - Date.parse(iso)) / 1000 + entPasado();
}

function entResta(iso) {
  return (Date.parse(iso) - Date.parse(_ent.datos.as_of)) / 1000 - entPasado();
}

function entDura(s) {
  const t = Math.max(0, Math.floor(s));
  const d = Math.floor(t / 86400);
  const h = Math.floor((t % 86400) / 3600);
  const m = Math.floor((t % 3600) / 60);
  if (d) return d + ' d ' + h + ' h';
  if (h) return h + ' h ' + m + ' min';
  if (m) return m + ' min ' + (t % 60) + ' s';
  return t + ' s';
}

/* La cuenta atras lleva SIEMPRE sus segundos: quien la mira tiene que verla correr. */
function entCuenta(s) {
  const t = Math.max(0, Math.floor(s));
  const d = Math.floor(t / 86400);
  const h = Math.floor((t % 86400) / 3600);
  const m = Math.floor((t % 3600) / 60);
  return (d ? d + ' d ' : '') + (d || h ? h + ' h ' : '') + (d || h || m ? m + ' min ' : '') + (t % 60) + ' s';
}

/* La hora de un instante servido, cortada de su texto (llegan todos en UTC). No se convierte. */
function entHora(iso, conSegundos) {
  if (esNada(iso)) return null;
  const t = String(iso);
  return t.slice(5, 10) + ' ' + t.slice(11, conSegundos ? 19 : 16) + 'Z';
}

function entPrecio(v) {
  return Number(v).toLocaleString('es-ES', { maximumFractionDigits: 8 });
}

/* ------------------------------------------------------- los nodos del contrato */

function sv(tag, clase, ruta, texto) {
  const n = el(tag, clase, texto);
  n.setAttribute('data-k', ruta);
  return n;
}

/* Una CIFRA servida. `fmt` solo le pone separadores y unidad: el redondeo ya viene hecho.
 * Si el valor no llega NO se pinta como 0: se dice que llega vacio. */
function cf(clase, ruta, valor, fmt) {
  if (esNada(valor)) {
    const v = sv('span', 'cifra', ruta, null);
    v.appendChild(noSe('nulo', null));
    return v;
  }
  const n = sv('span', 'cifra', ruta, fmt ? fmt(valor) : String(valor));
  n.setAttribute('data-cifra', clase);
  return n;
}

const FMT = {
  precio: entPrecio,
  pct: (v) => num(v, 2) + ' %',
  bps1: (v) => num(v, 1) + ' bps',
  bps2: (v) => num(v, 2) + ' bps',
  // Una fraccion del objetivo se pinta ENTERA, con los decimales que la ruta le dio (dos como minimo):
  // redondear aqui a dos convertia 0,002 en «x0,00 del objetivo», que se lee «no cuesta nada».
  x: (v) => 'x' + Number(v).toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 20 }) +
    ' del objetivo',
  r: (v) => num(v, 2),
  p: (v) => num(v, 3),
  dias: (v) => num(v, 1) + ' d',
  usd: (v) => num(v, 2) + ' USD',
};

function calc(tipo, iso) {
  const n = el('span', 'ent-calc');
  n.setAttribute('data-calc', tipo);
  n.setAttribute('data-instante', iso || '');
  return n;
}

function junta(padre, ...trozos) {
  trozos.forEach((t) => {
    if (t === null || t === undefined) return;
    padre.appendChild(t.nodeType || t.tagName ? t : document.createTextNode(String(t)));
  });
  return padre;
}

/* Un valor servido que puede venir vacio: si no llega, se pinta SU motivo servido, no un guion. */
function oMotivo(nodo, valor, ruta, motivo) {
  if (!esNada(valor)) return nodo();
  const m = sv('span', 'motivo', ruta, motivo);
  return junta(el('span'), el('span', 'no-se nulo', 'SIN DATO'), m);
}

/* Todos los nodos de la vista que casan, buscados en cada seccion (no se supone como anidan). */
function entBusca(R, sel) {
  return [R.cabeza, R.decide, R.vivo, R.reciente, R.papel, R.marco]
    .reduce((todos, n) => todos.concat(n ? Array.from(n.querySelectorAll(sel)) : []), []);
}

function entNodos() {
  const g = (id) => document.getElementById(id);
  return {
    raiz: g('vista-entradas'),
    aviso: g('ent-aviso'),
    cabeza: g('ent-cabeza'),
    decide: g('ent-decide'),
    vivo: g('ent-vivo'),
    reciente: g('ent-reciente'),
    papel: g('ent-papel'),
    marco: g('ent-marco'),
  };
}

/* ------------------------------------------------------------------ un plan */

function entZona(p, r) {
  return junta(
    el('span', 'ent-zona'),
    'zona ',
    cf('precio', r + '.zona.low', p.zona.low, FMT.precio),
    ' – ',
    cf('precio', r + '.zona.high', p.zona.high, FMT.precio)
  );
}

function entFila(p, r, tipo, papel) {
  const f = el('div', 'ent-plan ent-' + tipo);
  f.setAttribute('data-plan', p.registro_id);
  f.setAttribute('data-version', p.version);
  f.setAttribute('data-papel', papel);
  f.setAttribute('data-tipo', tipo);
  junta(
    f,
    sv('span', 'ent-ver', r + '.version', p.version),
    ' ',
    sv('span', 'ent-fam', r + '.familia', p.familia),
    ' '
  );
  return f;
}

function entVigilando(p, r, papel) {
  const f = entFila(p, r, 'vigilando', papel);
  const chip = el('span', 'ent-chip');
  chip.setAttribute('data-chip', 'vigilando');
  junta(f, chip, ' ', entZona(p, r), ' · precio ');
  junta(
    f,
    oMotivo(
      () => junta(
        el('span'),
        cf('distancia-pct', r + '.distancia.pct', p.distancia.pct, FMT.pct),
        ' ',
        sv('span', null, r + '.distancia.donde', p.distancia.donde)
      ),
      p.distancia.pct, r + '.distancia.motivo', p.distancia.motivo
    ),
    ' · registrado en la vela ',
    sv('span', 'mono', r + '.vela_cierre', entHora(p.vela_cierre)),
    ' (',
    calc('edad', p.vela_cierre),
    ')'
  );
  return f;
}

function entLinea(rotulo, ...trozos) {
  return junta(el('div', 'ent-linea'), el('span', 'rotulo', rotulo), ...trozos);
}

/* COMO ACABO UN DISPARADO (E3), tal como lo sirve la ruta: rotulo, firmeza, frase y cifras ya escritos.
 * Nada se deduce aqui, y la fila no cambia de color con el: el resultado es TEXTO (K106 E6). */
function entResultado(x, r) {
  const l = entLinea('resultado', sv('b', 'ent-res', r + '.rotulo', x.rotulo));
  if (x.firmeza) junta(l, ' · ', sv('span', 'ent-firmeza', r + '.firmeza', x.firmeza));
  if (x.frase) junta(l, ' · ', sv('span', 'motivo', r + '.frase', x.frase));
  if (x.entrada) {
    junta(l, ' · entrada real ', cf('precio', r + '.entrada.precio', x.entrada.precio, FMT.precio), ' a las ',
          sv('span', 'mono', r + '.entrada.instante', entHora(x.entrada.instante, true)));
  }
  if (!esNada(x.precio_salida)) junta(l, ' · salida ', cf('precio', r + '.precio_salida', x.precio_salida, FMT.precio));
  if (!esNada(x.r_neto)) junta(l, ' · R neto ', cf('r', r + '.r_neto', x.r_neto, FMT.r));
  if (!esNada(x.bps_netos)) junta(l, ' (', cf('bps-resultado', r + '.bps_netos', x.bps_netos, FMT.bps1), ' netos)');
  ['t2', 't3'].forEach((t) => {
    if (x[t]) {
      junta(l, ' · ', t.toUpperCase(), ' ', cf('precio', r + '.' + t + '.precio', x[t].precio, FMT.precio), ' ',
            sv('span', null, r + '.' + t + '.frase', x[t].frase));
    }
  });
  if (x.excursion) {
    junta(l, ' · excursión a favor ', cf('bps', r + '.excursion.favor_bps', x.excursion.favor_bps, FMT.bps1),
          ', en contra ', cf('bps', r + '.excursion.contra_bps', x.excursion.contra_bps, FMT.bps1));
  }
  if (x.a_favor) {
    const a = x.a_favor;
    junta(l, ' · caso a favor: ', sv('span', null, r + '.a_favor.rotulo', a.rotulo), ' a ',
          cf('precio', r + '.a_favor.precio', a.precio, FMT.precio), ', R ', cf('r', r + '.a_favor.r_neto', a.r_neto, FMT.r),
          ' — ', sv('span', 'motivo', r + '.a_favor.frase', a.frase));
  }
  return l;
}

/* Lo que el reloj de la vista lee de un DISPARADO: si su resultado servido dice que ya acabo, y su rotulo. */
function entMarcaResultado(f, x) {
  const res = x || {};
  f.setAttribute('data-resultado', res.vivo ? 'vivo' : 'acabado');
  f.setAttribute('data-rotulo', res.rotulo || '');
}

/* EL PLAN ENTERO de un DISPARADO, tal como su foto lo guarda, y su resultado. `vivo` solo decide si
 * lleva la cuenta atras corriendo o la hora en que caduco. */
function entDisparado(p, r, papel, enVivo) {
  const f = entFila(p, r, 'disparado', papel);
  f.setAttribute('data-caduca', p.caduca_en || '');
  entMarcaResultado(f, p.resultado);
  const chip = el('span', 'ent-chip');
  chip.setAttribute('data-chip', 'disparado');
  junta(f, chip, ' ', sv('span', null, r + '.perfil', p.perfil), ' · ', sv('span', null, r + '.lado', p.lado), ' · ',
        entZona(p, r), ' · ');
  // Un DISPARADO que ya acabo no lleva cuenta atras: su reloj ya no dice nada de el, solo hasta cuando iba.
  if (p.resultado && !p.resultado.vivo) junta(f, 'su reloj iba hasta ', sv('span', 'mono', r + '.caduca_en', entHora(p.caduca_en)));
  else junta(f, calc('cuenta', p.caduca_en), ' (', sv('span', 'mono', r + '.caduca_en', entHora(p.caduca_en)), ')');
  junta(f, ' · vela ', sv('span', 'mono', r + '.vela_cierre', entHora(p.vela_cierre)),
        ' · registrado ', sv('span', 'mono', r + '.registered_at', entHora(p.registered_at, true)));
  if (!enVivo) f.setAttribute('data-ventana', p.vivo ? 'vivo' : 'caducado');
  if (p.resultado) f.appendChild(entResultado(p.resultado, r + '.resultado'));

  const ref = p.entrada.referencia || {};
  f.appendChild(entLinea(
    'entrada', sv('span', null, r + '.entrada.tipo', p.entrada.tipo), ': ',
    sv('span', null, r + '.entrada.regla', p.entrada.regla), ' · referencia ',
    cf('precio', r + '.entrada.referencia.precio', ref.precio, FMT.precio), ' (',
    sv('span', 'mono', r + '.entrada.referencia.instante', entHora(ref.instante, true)), ', ',
    sv('span', null, r + '.entrada.referencia.fuente', ref.fuente), ')'
  ));
  const niveles = entLinea(
    'stop', cf('precio', r + '.stop.precio', p.stop.precio, FMT.precio), ' a ',
    cf('bps', r + '.stop.distancia_bps', p.stop.distancia_bps, FMT.bps1), ' (',
    sv('span', null, r + '.stop.tipo_disparo', p.stop.tipo_disparo), ')'
  );
  (p.objetivos || []).forEach((o, i) => {
    junta(niveles, ' · ', sv('span', 'ent-t', r + '.objetivos[' + i + '].nombre', o.nombre), ' ',
          cf('precio', r + '.objetivos[' + i + '].precio', o.precio, FMT.precio));
    if (i === 0) junta(niveles, ' a ', cf('bps', r + '.t1_distancia_bps', p.t1_distancia_bps, FMT.bps1));
  });
  f.appendChild(niveles);
  const inv = p.invalidacion || {};
  f.appendChild(entLinea(
    'invalidación', 'nivel ', cf('precio', r + '.invalidacion.nivel', inv.nivel, FMT.precio), ' hasta ',
    sv('span', 'mono', r + '.invalidacion.hasta', entHora(inv.hasta)), ' · ',
    sv('span', null, r + '.invalidacion.regla', inv.regla), ' · ',
    sv('span', null, r + '.invalidacion.reloj', inv.reloj)
  ));
  f.appendChild(entLinea(
    'R neto', cf('r', r + '.r_neto', p.r_neto, FMT.r), ' (bruto ', cf('r', r + '.r_bruto', p.r_bruto, FMT.r),
    ') · p de equilibrio ', cf('p-equilibrio', r + '.p_equilibrio', p.p_equilibrio, FMT.p),
    ' — del plan, sale de su foto; no es un resultado'
  ));
  const costes = entLinea('coste');
  (p.costes || []).forEach((c, i) => {
    const rc = r + '.costes[' + i + ']';
    junta(costes, i ? ' · ' : '', sv('span', null, rc + '.pata', c.pata), ' ',
          cf('bps', rc + '.bps', c.bps, FMT.bps2), ' (',
          cf('x-objetivo', rc + '.x_objetivo', c.x_objetivo, FMT.x), ', ',
          sv('span', null, rc + '.venue', c.venue), ' ', sv('span', null, rc + '.tipo', c.tipo), ')');
  });
  junta(costes, ' · ida y vuelta a T1 ',
        cf('x-objetivo', r + '.coste_ida_y_vuelta_x_objetivo', p.coste_ida_y_vuelta_x_objetivo, FMT.x));
  f.appendChild(costes);
  const req = el('ul', 'ent-requisitos');
  (p.requisitos || []).forEach((q, i) => {
    const rq = r + '.requisitos[' + i + ']';
    const li = junta(el('li', 'req-' + q.estado), sv('span', 'mono', rq + '.nombre', q.nombre), ': ',
                     sv('span', 'ent-req-estado', rq + '.estado', String(q.estado).replace('_', ' ')));
    if (q.motivo) junta(li, ' — ', sv('span', 'motivo', rq + '.motivo', q.motivo));
    req.appendChild(li);
  });
  f.appendChild(junta(el('div', 'ent-linea'), el('span', 'rotulo', 'requisitos'), req));
  return f;
}

/* UN DISPARADO ANTERIOR A LA VENTANA: una fila corta con su resultado; su plan entero esta en /api/entradas. */
function entAnterior(p, r, papel) {
  const f = entFila(p, r, 'disparado', papel);
  f.setAttribute('data-caduca', p.caduca_en || '');
  f.setAttribute('data-ventana', p.resultado && p.resultado.vivo ? 'vivo' : 'caducado');
  f.setAttribute('data-anterior', 'si');
  entMarcaResultado(f, p.resultado);
  const chip = el('span', 'ent-chip');
  chip.setAttribute('data-chip', 'disparado');
  junta(f, chip, ' ', sv('span', null, r + '.perfil', p.perfil), ' · ', sv('span', null, r + '.lado', p.lado),
        ' · vela ', sv('span', 'mono', r + '.vela_cierre', entHora(p.vela_cierre)),
        ' · caduca ', sv('span', 'mono', r + '.caduca_en', entHora(p.caduca_en)));
  f.appendChild(entResultado(p.resultado || {}, r + '.resultado'));
  return f;
}

function entSombra(p, r, papel) {
  const f = entFila(p, r, 'sombra', papel);
  junta(f, sv('span', 'mono', r + '.vela_cierre', entHora(p.vela_cierre)), ' · ',
        sv('span', null, r + '.perfil', p.perfil), ' · ', sv('span', null, r + '.lado', p.lado), ' · ',
        entZona(p, r));
  if (p.tipo_sombra) junta(f, ' · sombra de ', sv('span', null, r + '.tipo_sombra', p.tipo_sombra));
  if ((p.fallan || []).length) {
    junta(f, ' · falló: ');
    p.fallan.forEach((n, i) => junta(f, i ? ', ' : '', sv('span', 'mono req-falla', r + '.fallan[' + i + ']', n)));
  }
  if ((p.no_evaluables || []).length) {
    junta(f, ' · no se pudo evaluar: ');
    p.no_evaluables.forEach((q, i) => {
      const rq = r + '.no_evaluables[' + i + ']';
      junta(f, i ? '; ' : '', sv('span', 'mono req-no_evaluable', rq + '.nombre', q.nombre));
      if (q.motivo) junta(f, ' (', sv('span', 'motivo', rq + '.motivo', q.motivo), ')');
    });
  }
  return f;
}

/* ------------------------------------------------------------- las secciones */

function entCabeza(R, d) {
  const c = vaciar(R.cabeza);
  junta(c, junta(el('h1'), 'Entradas · ', sv('span', null, 'activo', d.activo)));
  c.appendChild(sv('p', 'ent-que-es', 'que_es', d.que_es));
  junta(c, junta(el('p', 'pie'), 'servido a las ', sv('span', 'mono', 'as_of', entHora(d.as_of, true)),
                 ' (', calc('edad', d.as_of), ') · ', sv('span', null, 'frescura.regla', d.frescura.regla)));
}

/* LA PALABRA DE DECIDE, una por perfil, con lo que significa para un plan. El color es de la
 * PALABRA (el mismo mapa que DECIDE); NO EVALUABLE y SIN RESPUESTA van en neutro, porque no dicen
 * ni que si ni que no. */
function entDecide(R, d) {
  const caja = vaciar(R.decide);
  Object.keys(d.decide.perfiles).forEach((perfil) => {
    const x = d.decide.perfiles[perfil];
    const r = 'decide.perfiles.' + perfil;
    const t = el('section', 'tarjeta ent-decide');
    t.setAttribute('data-decide', perfil);
    // LA EDAD DEL DATO NO ES LA DE LA PALABRA (campana 138): la de la instantanea de debajo decide si
    // DECIDE esta RANCIO; la de la palabra -desde cuando dice lo que dice- llega servida por perfil.
    junta(t, junta(el('div', 'panel-rotulo'),
                   junta(el('h3'), 'planes ', el('b', null, perfil), ' · DECIDE de ', sv('span', null, r + '.marco', x.marco)),
                   junta(el('span', 'venue'), 'edad del dato de DECIDE: ',
                         esNada(d.decide.edad_s) ? sv('span', null, 'decide.edad_motivo', d.decide.edad_motivo)
                           : calc('edad-decide', ''))));
    const palabra = sv('div', 'ent-palabra ' + (CLASE_SESGO[x.palabra] || 'sesgo-NOEVAL'), r + '.rotulo', x.rotulo);
    palabra.setAttribute('data-palabra', x.palabra || '');
    t.appendChild(palabra);
    if (x.edad_de_la_palabra) t.appendChild(sv('p', 'pie', r + '.edad_de_la_palabra', x.edad_de_la_palabra));
    const viva = junta(el('div', 'ent-dec-viva'), sv('p', 'ent-frase', r + '.frase', x.frase));
    if (x.motivo && !x.frase.includes(x.motivo)) viva.appendChild(sv('p', 'motivo', r + '.motivo', x.motivo));
    const rancia = junta(el('div', 'ent-dec-rancia'),
                         sv('span', 'no-se rancio', 'decide.rancio.rotulo', d.decide.rancio.rotulo), ' ',
                         sv('span', 'ent-frase', 'decide.rancio.frase', d.decide.rancio.frase));
    rancia.hidden = true;
    junta(t, viva, rancia, sv('p', 'pie', r + '.por_que_este_marco', x.por_que_este_marco));
    caja.appendChild(t);
  });
}

function entVivo(R, d) {
  const caja = vaciar(R.vivo);
  caja.appendChild(sv('p', 'pie', 'vivo.que_es', d.vivo.que_es));
  junta(caja, junta(
    el('p', 'ent-precio'), 'precio ',
    oMotivo(() => junta(el('span'), cf('precio', 'precio.valor', d.precio.valor, FMT.precio), ' a las ',
                        sv('span', 'mono', 'precio.instante', entHora(d.precio.instante, true)),
                        ' (', calc('edad', d.precio.instante), ')'),
            d.precio.valor, 'precio.motivo', d.precio.motivo),
    ' · ', sv('span', 'motivo', 'precio.fuente', d.precio.fuente)
  ));
  if (d.generador.pasada_en_curso) {
    caja.appendChild(sv('p', 'ent-en-curso', 'generador.pasada_en_curso', d.generador.pasada_en_curso));
  }
  const rejilla = el('div', 'ent-rejilla');
  d.vivo.celdas.forEach((c, i) => {
    const rc = 'vivo.celdas[' + i + ']';
    const rel = d.decide.perfiles[c.perfil].para[c.lado];
    const rd = 'decide.perfiles.' + c.perfil + '.para.' + c.lado;
    const t = el('section', 'tarjeta ent-celda');
    t.setAttribute('data-celda', c.perfil + '/' + c.lado);
    const viva = sv('span', 'ent-rel rel-' + rel.relacion, rd + '.etiqueta', rel.etiqueta);
    viva.setAttribute('data-relacion', rel.relacion);
    const rancia = sv('span', 'ent-rel rel-rancio', 'decide.rancio.etiqueta', d.decide.rancio.etiqueta);
    rancia.hidden = true;
    junta(t, junta(el('div', 'panel-rotulo'),
                   junta(el('h3'), sv('span', null, rc + '.perfil', c.perfil), ' · ', sv('span', null, rc + '.lado', c.lado)),
                   junta(el('span', 'ent-rel-caja'), viva, rancia)));
    c.por_version.forEach((v, j) => {
      const rv = rc + '.por_version[' + j + ']';
      const b = el('div', 'ent-bloque papel-' + String(v.papel).split(' ')[0]);
      b.setAttribute('data-bloque-version', v.version);
      b.setAttribute('data-papel', v.papel);
      junta(b, junta(el('div', 'ent-bloque-rotulo'), sv('span', null, rv + '.papel', v.papel), ' · ',
                     sv('span', 'ent-ver', rv + '.version', v.version)));
      v.disparados.forEach((p, n) => b.appendChild(entDisparado(p, rv + '.disparados[' + n + ']', v.papel, true)));
      v.vigilando.forEach((p, n) => b.appendChild(entVigilando(p, rv + '.vigilando[' + n + ']', v.papel)));
      if (v.sin_planes) b.appendChild(sv('p', 'motivo', rv + '.sin_planes', v.sin_planes));
      t.appendChild(b);
    });
    rejilla.appendChild(t);
  });
  caja.appendChild(rejilla);
}

function entReciente(R, d) {
  const caja = vaciar(R.reciente);
  const v0 = d.reciente.ventana;
  junta(caja, junta(el('p', 'pie'), 'ventana servida: de ', sv('span', 'mono', 'reciente.ventana.desde', entHora(v0.desde)),
                    ' a ', sv('span', 'mono', 'reciente.ventana.hasta', entHora(v0.hasta)), ' · ',
                    sv('span', 'ent-falta', 'reciente.que_es_el_resultado', d.reciente.que_es_el_resultado)));
  if (d.reciente.recortada) caja.appendChild(sv('p', 'motivo', 'reciente.recortada', d.reciente.recortada));
  d.reciente.por_version.forEach((v, j) => {
    const rv = 'reciente.por_version[' + j + ']';
    const b = el('section', 'tarjeta ent-bloque papel-' + String(v.papel).split(' ')[0]);
    b.setAttribute('data-bloque-version', v.version);
    b.setAttribute('data-papel', v.papel);
    junta(b, junta(el('div', 'panel-rotulo'),
                   junta(el('h3'), sv('span', null, rv + '.papel', v.papel), ' · ', sv('span', 'ent-ver', rv + '.version', v.version))));
    if (v.no_puede) b.appendChild(sv('p', 'ent-ancla', rv + '.no_puede.frase', v.no_puede.frase));
    v.disparados.forEach((p, n) => b.appendChild(entDisparado(p, rv + '.disparados[' + n + ']', v.papel, false)));
    // los DISPARADOS anteriores a la ventana, detras de los de la ventana y delante de las SOMBRAS: el orden es
    // por estado y por hora (K106 E6), y todos son mas viejos que los de la ventana
    if ((v.anteriores || []).length) {
      b.appendChild(sv('p', 'pie', rv + '.anteriores_que_es', v.anteriores_que_es));
      v.anteriores.forEach((p, n) => b.appendChild(entAnterior(p, rv + '.anteriores[' + n + ']', v.papel)));
    }
    v.sombras.forEach((p, n) => b.appendChild(entSombra(p, rv + '.sombras[' + n + ']', v.papel)));
    if (v.sin_planes) b.appendChild(sv('p', 'motivo', rv + '.sin_planes', v.sin_planes));
    caja.appendChild(b);
  });
}

/* LA CUENTA DE PAPEL de cada version, tal como la sirve la ruta: no ejecuta nada ni mueve fondos. */
function entPapel(R, d) {
  const caja = vaciar(R.papel);
  if (!caja || !d.papel) return;
  caja.appendChild(sv('p', 'pie', 'papel.que_es', d.papel.que_es));
  (d.papel.por_version || []).forEach((c, j) => {
    const rc = 'papel.por_version[' + j + ']';
    const t = el('section', 'tarjeta ent-bloque papel-' + String(c.papel).split(' ')[0]);
    t.setAttribute('data-papel-version', c.version);
    junta(t, junta(el('div', 'panel-rotulo'), junta(el('h3'), 'cuenta de papel · ', sv('span', null, rc + '.papel', c.papel),
                                                     ' · ', sv('span', 'ent-ver', rc + '.version', c.version))));
    t.appendChild(entLinea('saldo', cf('usd', rc + '.saldo_usd', c.saldo_usd, FMT.usd), ' · capital ',
                           cf('usd', rc + '.capital_usd', c.capital_usd, FMT.usd), ' · ', sv('span', null, rc + '.firmeza', c.firmeza)));
    t.appendChild(entLinea('operaciones', 'cerradas ', cf('recuento', rc + '.n', c.n), ' · abiertas ',
                           cf('recuento', rc + '.abiertas', c.abiertas), ' · funding cobrado ',
                           cf('usd', rc + '.funding_usd', c.funding_usd, FMT.usd)));
    t.appendChild(entLinea('meta', cf('usd', rc + '.meta_usd', c.meta_usd, FMT.usd), ' · ', sv('span', 'motivo', rc + '.meta', c.meta)));
    if (c.no_dimensiona) t.appendChild(sv('p', 'ent-ancla', rc + '.no_dimensiona', c.no_dimensiona));
    if (c.recortada) t.appendChild(sv('p', 'motivo', rc + '.recortada', c.recortada));
    if ((c.operaciones || []).length) {
      const tabla = el('table', 'rejilla ent-cuentas');
      const cab = el('tr');
      ['registro', 'activo', 'vela', 'perfil', 'lado', 'salida', 'firmeza', 'lote', 'entrada', 'salida a', 'R neto',
       'P&L', 'comisión', 'funding'].forEach((x) => cab.appendChild(el('th', null, x)));
      tabla.appendChild(cab);
      c.operaciones.forEach((op, i) => {
        const ro = rc + '.operaciones[' + i + ']';
        const tr = el('tr');
        const td = (...x) => tr.appendChild(junta(el('td'), ...x));
        td(sv('span', 'mono', ro + '.registro_id', op.registro_id));
        td(sv('span', null, ro + '.activo', op.activo));
        td(sv('span', 'mono', ro + '.vela_cierre', entHora(op.vela_cierre)));
        td(sv('span', null, ro + '.perfil', op.perfil));
        td(sv('span', null, ro + '.lado', op.lado));
        td(sv('span', null, ro + '.rotulo', op.rotulo));
        td(sv('span', null, ro + '.firmeza', op.firmeza));
        td(cf('cantidad', ro + '.lote', op.lote, (v) => entPrecio(v) + ' ' + op.activo));
        td(cf('precio', ro + '.precio_entrada', op.precio_entrada, FMT.precio));
        td(cf('precio', ro + '.precio_salida', op.precio_salida, FMT.precio));
        td(cf('r', ro + '.r_neto', op.r_neto, FMT.r));
        td(cf('usd', ro + '.pnl_usd', op.pnl_usd, FMT.usd));
        td(cf('usd', ro + '.comision_usd', op.comision_usd, FMT.usd));
        td(cf('usd', ro + '.funding_usd', op.funding_usd, FMT.usd),
           op.funding_sin_medir ? junta(el('span', 'motivo'), ' sin medir: ',
                                        sv('span', 'mono', ro + '.funding_sin_medir', op.funding_sin_medir.join(', '))) : null);
        tabla.appendChild(tr);
      });
      t.appendChild(tabla);
    }
    [['saltados', 'saltado'], ['pendientes', 'pendiente'], ['sin_posicion', 'sin posición'],
     ['sin_resultado', 'sin resultado']].forEach(([lista, rotulo]) => {
      (c[lista] || []).forEach((s, i) => {
        const rs = rc + '.' + lista + '[' + i + ']';
        t.appendChild(entLinea(rotulo, sv('span', 'mono', rs + '.registro_id', s.registro_id), ' ',
                               sv('span', null, rs + '.activo', s.activo), ' · vela ',
                               sv('span', 'mono', rs + '.vela_cierre', entHora(s.vela_cierre)), ' · ',
                               sv('span', 'motivo', rs + '.motivo', s.motivo)));
      });
    });
    caja.appendChild(t);
  });
}

function entMarco(R, d) {
  const caja = vaciar(R.marco);
  const m = d.marco;
  const t = el('section', 'tarjeta');
  if (!m.disponible) t.appendChild(sv('p', 'motivo', 'marco.motivo', m.motivo));
  t.appendChild(entLinea('versiones', 'activa ', sv('b', 'ent-ver', 'marco.version_activa', m.version_activa),
                         ' · ancla ', sv('b', 'ent-ver', 'marco.ancla', m.ancla), ' · corren a la vez: ',
                         sv('span', null, 'marco.versiones_en_curso', (m.versiones_en_curso || []).join(', '))));
  Object.keys(m.familias || {}).forEach((f) => {
    t.appendChild(entLinea(f, sv('b', null, 'marco.familias.' + f + '.nombre', m.familias[f].nombre), ' — ',
                           sv('span', null, 'marco.familias.' + f + '.definicion', m.familias[f].definicion)));
  });
  const c = m.calendario || {};
  t.appendChild(entLinea(
    'calendario',
    oMotivo(() => junta(el('span'), sv('b', null, 'marco.calendario.revision', c.revision), ' · vigente desde ',
                        sv('span', 'mono', 'marco.calendario.vigente_desde', entHora(c.vigente_desde)), ' · cubre hasta ',
                        sv('span', 'mono', 'marco.calendario.cubre_hasta', entHora(c.cubre_hasta)), ' · ',
                        cf('recuento', 'marco.calendario.eventos', c.eventos), ' eventos · le quedan ',
                        cf('dias', 'marco.calendario.dias_que_le_quedan', c.dias_que_le_quedan, FMT.dias)),
            c.revision, 'marco.calendario.motivo', c.motivo)
  ));
  const h = m.hipotesis_activa || {};
  ['celdas', 'sentido', 'lectura'].forEach((k) => {
    t.appendChild(junta(el('div', 'ent-linea ent-larga'), el('span', 'rotulo', 'hipótesis de la activa · ' + k),
                        sv('p', 'ent-hipotesis', 'marco.hipotesis_activa.' + k, h[k])));
  });
  const lat = d.generador.ultimo_latido;
  t.appendChild(entLinea(
    'generador',
    oMotivo(() => junta(el('span'), 'último latido: vela ', sv('span', 'mono', 'generador.ultimo_latido.vela_cierre', entHora(lat.vela_cierre)),
                        ', escrito a las ', sv('span', 'mono', 'generador.ultimo_latido.registered_at', entHora(lat.registered_at, true)),
                        ' (', calc('edad', lat.registered_at), ') · ',
                        sv('span', 'lat-' + lat.estado, 'generador.ultimo_latido.estado', lat.estado),
                        lat.error ? ' · ' : null, lat.error ? sv('span', 'motivo', 'generador.ultimo_latido.error', lat.error) : null,
                        lat.motivo ? ' · ' : null, lat.motivo ? sv('span', 'motivo', 'generador.ultimo_latido.motivo', lat.motivo) : null),
            lat, 'generador.motivo', d.generador.motivo),
    ' · ', sv('span', 'motivo', 'generador.regla', d.generador.regla)
  ));
  caja.appendChild(t);

  const tc = el('section', 'tarjeta');
  // QUE CUENTA LA TABLA va antes de la tabla y con letra de leer: «VIGILANDO 264» se leia «264 planes
  // vigilados ahora» y son episodios abiertos desde que el registro existe. La frase y la cabecera de
  // cada columna las sirve la ruta: aqui las columnas ya no se llaman como el estado de un plan vivo.
  tc.appendChild(sv('p', 'ent-hipotesis', 'marco.cuentas_que_cuentan', m.cuentas_que_cuentan));
  const tabla = el('table', 'rejilla ent-cuentas');
  const cols = ['VIGILANDO', 'DISPARADO', 'SOMBRA', 'CERRADO_SIN_DISPARO'];
  const cab = el('tr');
  const th = (x) => cab.appendChild(junta(el('th'), x));
  ['familia', 'perfil', 'lado', 'versión'].forEach(th);
  cols.forEach((k) => th(sv('span', null, 'marco.cuentas_rotulos.' + k, (m.cuentas_rotulos || {})[k])));
  ['RESUELTOS', 'SIN ENTRADA', 'NO EVALUABLES', 'muestra'].forEach(th);
  tabla.appendChild(cab);
  (m.cuentas || []).forEach((q, i) => {
    const rq = 'marco.cuentas[' + i + ']';
    const tr = el('tr');
    ['familia', 'perfil', 'lado', 'version'].forEach((k) => tr.appendChild(junta(el('td'), sv('span', null, rq + '.' + k, q[k]))));
    cols.concat(['resueltos', 'sin_entrada', 'no_evaluables'])
      .forEach((k) => tr.appendChild(junta(el('td'), cf('recuento', rq + '.' + k, q[k]))));
    const mu = q.muestra || {};
    const td = el('td');
    if (mu.rotulo) {
      const n = sv('span', 'ent-muestra', rq + '.muestra.rotulo', mu.rotulo);
      n.setAttribute('data-cifra', 'muestra');
      td.appendChild(n);
    } else td.appendChild(sv('span', 'motivo', rq + '.muestra.motivo', mu.motivo));
    tr.appendChild(td);
    tabla.appendChild(tr);
  });
  tc.appendChild(tabla);
  // El motivo de «resueltos»: una vez si el servidor lo sirve comun, y si no el de cada celda.
  if (m.resueltos_motivo) {
    tc.appendChild(junta(el('p', 'pie'), 'resueltos: ', sv('span', null, 'marco.resueltos_motivo', m.resueltos_motivo)));
  }
  (m.cuentas || []).forEach((q, i) => {
    if (q.resueltos_motivo) tc.appendChild(sv('p', 'pie', 'marco.cuentas[' + i + '].resueltos_motivo', q.resueltos_motivo));
  });
  caja.appendChild(tc);

  const rs = m.resolutor;
  if (rs) {
    const tr = el('section', 'tarjeta');
    tr.appendChild(entLinea('resolutor', sv('b', 'mono', 'marco.resolutor.version', rs.version), ' · huella de sus convenciones ',
                            sv('span', 'mono', 'marco.resolutor.huella', rs.huella)));
    tr.appendChild(sv('p', 'ent-hipotesis', 'marco.resolutor.frase', rs.frase));
    const ul = el('ul', 'ent-convenciones');
    rs.convenciones.forEach((c, i) => {
      const rr = 'marco.resolutor.convenciones[' + i + ']';
      ul.appendChild(junta(el('li'), sv('span', 'mono', rr + '.nombre', c.nombre), ': ', sv('span', null, rr + '.regla', c.regla)));
    });
    tr.appendChild(ul);
    tr.appendChild(el('div', 'rotulo', 'lo que cambia de la propuesta E3 de la COLA'));
    rs.cambios_e3.forEach((c, i) => tr.appendChild(sv('p', 'pie', 'marco.resolutor.cambios_e3[' + i + '].que', c.que)));
    caja.appendChild(tr);
  }

  const tf = el('section', 'tarjeta');
  tf.appendChild(el('div', 'rotulo', 'lo que falta'));
  (m.faltan || []).forEach((f, i) => {
    const rf = 'marco.faltan[' + i + ']';
    tf.appendChild(junta(el('p', 'ent-falta'), sv('b', null, rf + '.etapa', f.etapa), ' · ',
                         sv('span', null, rf + '.que', f.que), ' — ', sv('span', 'motivo', rf + '.motivo', f.motivo)));
  });
  caja.appendChild(tf);
}

/* --------------------------------------------------- lo que corre con el reloj */

/* SE LLAMA CADA SEGUNDO Y DESPUES DE CADA RESPUESTA. Aqui vive todo lo que el reloj decide, y
 * nada mas: tres edades contra tres topes SERVIDOS y una cuenta atras.
 *   · sin dato        el ultimo intento fallo, o la ultima respuesta buena pasa de `sin_dato_s`
 *   · generador parado  su ultimo latido pasa de `generador.tope_s`
 *   · DECIDE rancio    su edad pasa de `decide.max_age_s`
 * Con cualquiera de los dos primeros se dice ARRIBA y nada sigue en pantalla como vivo. */
function entTicTac() {
  const R = entNodos();
  if (!R.raiz) return;
  const d = _ent && _ent.datos;
  const avisos = [];
  if (_entFallo && _entFallo.ok) {
    avisos.push(['no-disponible', 'SIN DATO · ', _entFallo.datos.motivo || 'la ruta no dice por qué']);
  } else if (_entFallo) {
    avisos.push(['sin-dato', (d ? d.frescura.sin_dato_frase : 'SIN DATO · no se pudo pedir /api/mesa/entradas.') + ' ',
                 _entFallo.http ? 'HTTP ' + _entFallo.http : _entFallo.motivo]);
  } else if (d && entPasado() > d.frescura.sin_dato_s) {
    avisos.push(['sin-dato', d.frescura.viejo_frase + ' ', 'última respuesta hace ' + entDura(entPasado())]);
  }
  if (d) {
    const lat = d.generador.ultimo_latido;
    if (!lat) avisos.push(['generador-parado', 'SIN DATO · ', d.generador.motivo]);
    else if (entEdad(lat.registered_at) > d.generador.tope_s) {
      avisos.push(['generador-parado', d.generador.parado_frase + ' ', 'último latido hace ' + entDura(entEdad(lat.registered_at))]);
    }
  }
  const caja = vaciar(R.aviso);
  avisos.forEach(([cual, frase, detalle]) => {
    const p = junta(el('p', 'ent-aviso-linea'), frase, el('span', 'ent-aviso-detalle', detalle));
    p.setAttribute('data-aviso', cual);
    caja.appendChild(p);
  });
  R.aviso.hidden = !avisos.length;
  const noSeSabe = avisos.length > 0;
  R.raiz.classList.toggle('ent-no-se-sabe', noSeSabe);
  if (!d) return;

  entBusca(R, '[data-calc]').forEach((n) => {
    const tipo = n.getAttribute('data-calc');
    const iso = n.getAttribute('data-instante');
    if (tipo === 'edad') n.textContent = 'hace ' + entDura(entEdad(iso));
    else if (tipo === 'edad-decide') {
      n.textContent = entDura(d.decide.edad_s + entPasado()) + ' (tope ' + num(d.decide.max_age_s, 0) + ' s)';
    } else if (tipo === 'cuenta') {
      const r = entResta(iso);
      n.textContent = r > 0 ? 'caduca en ' + entCuenta(r) : 'caducó hace ' + entDura(-r);
    }
  });

  const rot = d.vivo.rotulos;
  // UN DISPARADO QUE YA ACABO NO SE LLAMA VIVO: si su resultado servido lo dice, su chip es su salida
  // (data-rotulo, servido), y ni la cuenta atras ni la falta de dato lo devuelven a la vida.
  R.vivo.querySelectorAll('[data-plan]').forEach((f) => {
    const disparado = f.getAttribute('data-tipo') === 'disparado';
    const acabado = disparado && f.getAttribute('data-resultado') === 'acabado';
    const caducado = disparado && entResta(f.getAttribute('data-caduca')) <= 0;
    const vivo = noSeSabe ? 'no-se-sabe' : acabado || caducado ? 'no' : 'si';
    f.setAttribute('data-vivo', vivo);
    const chip = f.querySelector('[data-chip]');
    if (chip) {
      chip.textContent = acabado ? f.getAttribute('data-rotulo') : noSeSabe ? rot.no_se_sabe
        : !disparado ? rot.vigilando : caducado ? rot.disparado_caducado : rot.disparado_vivo;
    }
  });
  R.reciente.querySelectorAll('[data-chip]').forEach((chip) => {
    const f = chip.parentNode;
    if (f.getAttribute('data-resultado') === 'acabado') {
      chip.textContent = f.getAttribute('data-rotulo');
      return;
    }
    const vivo = f.getAttribute('data-ventana') === 'vivo' && entResta(f.getAttribute('data-caduca')) > 0;
    chip.textContent = vivo && !noSeSabe ? rot.disparado_vivo : vivo ? rot.no_se_sabe : rot.disparado_caducado;
  });

  const rancio = !esNada(d.decide.edad_s) && !esNada(d.decide.max_age_s)
    && d.decide.edad_s + entPasado() > d.decide.max_age_s;
  R.raiz.classList.toggle('ent-decide-rancio', rancio);
  entBusca(R, '.ent-dec-viva').forEach((n) => { n.hidden = rancio; });
  entBusca(R, '.ent-dec-rancia').forEach((n) => { n.hidden = !rancio; });
  entBusca(R, '.ent-rel').forEach((n) => {
    n.hidden = n.classList.contains('rel-rancio') ? !rancio : rancio;
  });
}

/* ------------------------------------------------------------- pedir y pintar */

function pintarEntradas(sobre) {
  const R = entNodos();
  if (sobre.ok && sobre.datos && sobre.datos.disponible) {
    _ent = { datos: sobre.datos, tLlegada: sobre.tLlegada };
    _entFallo = null;
    const d = sobre.datos;
    entCabeza(R, d);
    entDecide(R, d);
    entVivo(R, d);
    entReciente(R, d);
    entPapel(R, d);
    entMarco(R, d);
  } else {
    // LA RUTA NO CONTESTA, O CONTESTA QUE NO ESTA DISPONIBLE. Lo ultimo que se supo se queda en
    // pantalla -sigue siendo informacion- pero deja de darse por vivo: lo dice `entTicTac`.
    _entFallo = sobre;
  }
  entTicTac();
}

async function olaEntradas() {
  const pedida = ESTADO.activo;
  const sobre = await pedir('/api/mesa/entradas', { symbol: simbolo(pedida) });
  apuntar(sobre);
  sobre.tLlegada = entReloj();
  // Si mientras tanto se cambio de vista o de activo, esta respuesta ya no es de esta pantalla.
  if (ESTADO.vista !== 'entradas' || ESTADO.activo !== pedida) return sobre;
  pintarEntradas(sobre);
  return sobre;
}

function pararEntradas() {
  if (_entTic !== null) { clearInterval(_entTic); _entTic = null; }
  if (_entRef !== null) { clearInterval(_entRef); _entRef = null; }
}

/* Lo de otro activo no puede quedarse en pantalla mientras llega lo del nuevo. */
function vaciarEntradas() {
  _ent = null;
  _entFallo = null;
  const R = entNodos();
  [R.aviso, R.cabeza, R.decide, R.vivo, R.reciente, R.papel, R.marco].forEach((n) => n && vaciar(n));
  if (R.aviso) R.aviso.hidden = true;
}

async function arrancarEntradas() {
  pararEntradas();
  vaciarEntradas();
  const sobre = await olaEntradas();
  if (ESTADO.vista !== 'entradas') return;
  pararEntradas();
  _entTic = setInterval(entTicTac, 1000);
  const cada = (sobre.ok && sobre.datos && sobre.datos.frescura && sobre.datos.frescura.refresco_s) || ENT_REFRESCO_S;
  _entRef = setInterval(() => {
    // Si la pestana no se ve, no se pide: es la misma regla que el refresco de DECIDE.
    if (document.hidden || ESTADO.vista !== 'entradas') return;
    olaEntradas();
  }, cada * 1000);
  marca('mesa:completo');
  window.MESA_HITOS.completo = entReloj();
}

if (typeof document !== 'undefined' && document.addEventListener) {
  // Al volver a una pestana que estaba oculta no se espera al siguiente turno: se pide ya.
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && typeof ESTADO !== 'undefined' && ESTADO.vista === 'entradas' && _entRef !== null) olaEntradas();
  });
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { entDura, entCuenta, entHora };
}
