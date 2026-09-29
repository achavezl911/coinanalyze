'use strict';
/* LA MESA · DECIDE
 * ---------------------------------------------------------------------------
 * ESTE FICHERO NO DECIDE NADA, Y ESO ES EL PUNTO.
 *
 * El encargo pide que cada cosa que DECIDE ensena salga de una clave del backend que se pueda
 * nombrar, y que NINGUNA la deduzca el cliente. Asi que `/api/mesa/decide` no sirve datos
 * crudos para que el navegador los interprete: sirve el veredicto YA DECIDIDO, campo a campo,
 * y cada campo trae su `source_key` y su `status`. Lo unico que hace este fichero es:
 *
 *    1 · leer `campo.value`            (no lo calcula)
 *    2 · escribir `campo.source_key`   en la propia celda, para que se pueda auditar mirando
 *    3 · y si `status` no es `ok`, pintar el «no se» que toca CON SU MOTIVO
 *
 * EL CONTRATO DE DOM, QUE ES LO QUE HACE AUDITABLE LA PANTALLA
 * ---------------------------------------------------------------------------
 * Cada celda de DECIDE se marca con TRES atributos, y K102 los lee:
 *
 *     data-campo="<nombre>"        el nombre del campo dentro de `payload.decide`
 *     data-valor="<texto>"         EL TEXTO QUE SE ENSENA, en su propio elemento
 *     data-source-key="<clave>"    la clave del backend de la que salio
 *
 * Por que los tres y no solo el valor: un `grep` del valor en la pantalla no prueba nada
 * -«Long» esta en `bias`, en `state` («Long Pullback») y en `invalidates_long`, y una
 * coincidencia por homonimia absuelve sin medir-. Lo que K102 comprueba es que la PAREJA
 * (source_key, valor) coincide con lo servido EN LA MISMA celda: asi un intercambio entre dos
 * etiquetas que ya estan en pantalla tampoco cuela, porque cada una lleva su clave al lado.
 */

/* Del valor servido a la clase de color. Es un MAPA DE PRESENTACION sobre una palabra que
 * llega servida, no una deduccion: las cuatro palabras las decide el backend. */
const CLASE_SESGO = {
  LONG: 'sesgo-LONG',
  SHORT: 'sesgo-SHORT',
  NEUTRAL: 'sesgo-NEUTRAL',
  'NO EVALUABLE': 'sesgo-NOEVAL',
};

const ESCALON_CONFIANZA = { baja: 1, media: 2, alta: 3 };

/* El nodo del valor, con el contrato puesto. `texto` es lo que se ensena. */
function nodoValor(texto, cifra) {
  const v = el('div', 'valor' + (cifra ? ' cifra' : ''));
  v.setAttribute('data-valor', texto === null || texto === undefined ? '' : String(texto));
  if (texto !== null && texto !== undefined) v.textContent = String(texto);
  return v;
}

function nodoClave(source_key) {
  const k = el('span', 'clave mono', source_key);
  k.setAttribute('data-source-key', source_key);
  return k;
}

/* Pinta un campo servido. `campo` es {value, source_key, status, motivo}. */
function celda(nombre, rotulo, campo, opciones) {
  const o = opciones || {};
  const caja = el('div', 'campo' + (o.clase ? ' ' + o.clase : ''));
  caja.setAttribute('data-campo', nombre);
  caja.appendChild(el('span', 'rotulo', rotulo));

  if (!campo) {
    const v = nodoValor(null, o.cifra);
    v.appendChild(noSe('ausente', 'el backend no trae este bloque'));
    caja.appendChild(v);
    return caja;
  }

  const hayValor = !esNada(campo.value);
  const texto = hayValor ? (o.formato ? o.formato(campo.value) : String(campo.value)) : null;

  if (campo.status === 'rancio' && hayValor) {
    // RANCIO SI TIENE VALOR: se ensena el valor Y se dice que es viejo.
    const v = nodoValor(texto, o.cifra);
    v.appendChild(document.createTextNode(' '));
    v.appendChild(noSe('rancio', campo.motivo || null));
    caja.appendChild(v);
  } else if (campo.status && campo.status !== 'ok') {
    const v = nodoValor(null, o.cifra);
    v.appendChild(noSe(campo.status, campo.motivo || null));
    caja.appendChild(v);
  } else if (!hayValor) {
    const v = nodoValor(null, o.cifra);
    v.appendChild(noSe('nulo', campo.motivo || 'llega vacio'));
    caja.appendChild(v);
  } else {
    caja.appendChild(nodoValor(texto, o.cifra));
  }

  if (campo.source_key) caja.appendChild(nodoClave(campo.source_key));
  if (campo.venue) caja.appendChild(el('span', 'clave mono', 'venue: ' + campo.venue));
  return caja;
}

/* Una celda con varias entradas servidas (CONFIRMA / INVALIDA). Cada entrada lleva su propia
 * pareja (valor, clave): una lista con UNA clave para todas no seria auditable entrada a
 * entrada, y es justo donde se esconde un intercambio. */
function celdaLista(nombre, rotulo, campos, opciones) {
  const o = opciones || {};
  const caja = el('div', 'campo' + (o.clase ? ' ' + o.clase : ''));
  caja.setAttribute('data-campo', nombre);
  caja.appendChild(el('span', 'rotulo', rotulo));
  const lista = (campos || []).filter(Boolean);
  if (!lista.length) {
    const v = nodoValor(null);
    v.appendChild(noSe('ausente', o.motivoVacio || 'el backend no trae ninguna entrada'));
    caja.appendChild(v);
    return caja;
  }
  lista.forEach((campo, i) => {
    const fila = el('div', 'campo');
    fila.setAttribute('data-campo', nombre + '[' + i + ']');
    const hay = !esNada(campo.value);
    if (campo.status && campo.status !== 'ok') {
      const v = nodoValor(null);
      v.appendChild(noSe(campo.status, campo.motivo || null));
      fila.appendChild(v);
    } else if (!hay) {
      const v = nodoValor(null);
      v.appendChild(noSe('nulo', campo.motivo || 'llega vacio'));
      fila.appendChild(v);
    } else {
      fila.appendChild(nodoValor(o.formato ? o.formato(campo.value) : String(campo.value)));
    }
    if (campo.source_key) fila.appendChild(nodoClave(campo.source_key));
    caja.appendChild(fila);
  });
  return caja;
}

/* ------------------------------------------------------------------------- */
/* EL RENDER. Recibe el sobre de /api/mesa/decide TAL CUAL. */
function pintarDecide(sobre, nodos) {
  const caja = nodos.caja;
  const campos = vaciar(nodos.campos);

  // 1 · SI LA RUTA FALLO, SE DICE. No se pinta un DECIDE vacio que parezca NEUTRAL.
  if (!sobre || !sobre.ok) {
    caja.classList.add('no-evaluable');
    nodos.sesgo.textContent = 'SIN DATO';
    nodos.sesgo.className = 'sesgo-NOEVAL';
    nodos.sesgo.setAttribute('data-valor', '');
    nodos.sesgo.removeAttribute('data-source-key');
    vaciar(nodos.motivo).appendChild(
      noSe('error', (sobre && sobre.motivo) || 'no se pudo pedir /api/mesa/decide')
    );
    vaciar(nodos.edad);
    return;
  }

  const d = sobre.datos;
  const dec = d.decide || {};

  // 2 · EL SESGO. La palabra llega servida; aqui solo se elige el color y se dice de donde
  //     sale. Cuando no es evaluable, el motivo TAMBIEN llega servido.
  const sesgo = dec.bias || {};
  const palabra = esNada(sesgo.value) ? 'SIN DATO' : String(sesgo.value);
  nodos.sesgo.textContent = palabra;
  nodos.sesgo.className = CLASE_SESGO[palabra] || 'sesgo-NOEVAL';
  nodos.sesgo.setAttribute('data-campo', 'bias');
  nodos.sesgo.setAttribute('data-valor', palabra);
  nodos.sesgo.setAttribute('data-source-key', sesgo.source_key || '');

  const evaluable = dec.evaluable && dec.evaluable.value === true;
  caja.classList.toggle('no-evaluable', !evaluable);

  vaciar(nodos.motivo);
  if (sesgo.motivo) {
    nodos.motivo.textContent = sesgo.motivo;
  } else if (dec.no_trade_reasons && (dec.no_trade_reasons.value || []).length) {
    nodos.motivo.textContent = dec.no_trade_reasons.value.join(' · ');
  }

  // 3 · LA CONFIANZA ES UNA PALABRA. Tres escalones rotulados, no un % inventado.
  const conf = dec.confidence || {};
  const nivel = ESCALON_CONFIANZA[String(conf.value || '').toLowerCase()] || 0;
  Array.prototype.forEach.call(nodos.escalones.children, (n, i) => {
    n.classList.toggle('on', i < nivel);
  });
  // LA CONFIANZA ES DE LA LECTURA, asi que en un marco que no es scalp NO esta en `decide`:
  // el backend la movio a `lectura_scalp`. Aqui se dice por que falta en vez de pintar un
  // guion mudo, y se SUELTA el `data-campo` para que la unica celda con ese nombre sea la de
  // la tarjeta del scalp -si hubiera dos, K102 compararia contra la que le tocase-.
  const hayConf = Object.prototype.hasOwnProperty.call(dec, 'confidence');
  if (hayConf) {
    nodos.confPalabra.textContent = esNada(conf.value) ? '—' : String(conf.value);
    nodos.confPalabra.setAttribute('data-campo', 'confidence');
    nodos.confPalabra.setAttribute('data-valor', esNada(conf.value) ? '' : String(conf.value));
    nodos.confPalabra.setAttribute('data-source-key', conf.source_key || '');
  } else {
    nodos.confPalabra.textContent = 'la confianza es de la lectura del SCALP, abajo';
    nodos.confPalabra.removeAttribute('data-campo');
    nodos.confPalabra.removeAttribute('data-valor');
    nodos.confPalabra.removeAttribute('data-source-key');
  }
  nodos.confClave.textContent = conf.source_key || '';

  // 4 · data_confidence: el numero que decide NO EVALUABLE, con su umbral.
  const dc = dec.data_confidence || {};
  const umbral = (dec.evaluable && dec.evaluable.threshold) || d.no_evaluable_under;
  nodos.dcValor.setAttribute('data-campo', 'data_confidence');
  nodos.dcValor.setAttribute('data-source-key', dc.source_key || '');
  if (!esNada(dc.value)) {
    const v = Math.max(0, Math.min(100, Number(dc.value)));
    nodos.dcRelleno.style.width = v + '%';
    nodos.dcRelleno.classList.toggle('bajo', v < Number(umbral));
    const texto = num(dc.value, 1);
    nodos.dcValor.textContent = texto + ' / umbral ' + num(umbral, 0);
    nodos.dcValor.setAttribute('data-valor', texto);
  } else {
    nodos.dcRelleno.style.width = '0%';
    nodos.dcValor.setAttribute('data-valor', '');
    vaciar(nodos.dcValor).appendChild(noSe(dc.status || 'ausente', dc.motivo || null));
  }
  nodos.dcClave.textContent = dc.source_key || '';

  // 5 · LO QUE ES DEL MARCO, SIEMPRE: la zona (que `price_barriers` mide sobre 730 sesiones
  //     diarias y 720 barras de 4h, o sea que no es del scalp) y los niveles estructurales.
  campos.appendChild(celdaZonaRango(dec.zone));
  campos.appendChild(celda('zone_decision', 'razón de la zona', dec.zone_decision));
  campos.appendChild(
    celda('structural_invalidation', 'invalida · nivel estructural', dec.structural_invalidation, {
      cifra: true,
      clase: 'invalida',
      formato: (v) => num(v, 1),
    })
  );
  campos.appendChild(celda('structural_horizon', 'horizonte estructural', dec.structural_horizon));

  // 6 · LO QUE SALE DE LA LECTURA DEL SCALP. En el marco SCALP es DECIDE y va aqui; en los
  //     otros el backend lo saca de `decide` y lo sirve en `lectura_scalp`, y entonces se
  //     pinta en su propia tarjeta con su rotulo. Ni una ni otra lo pinta en el sitio del
  //     otro: la que no toca no existe en el sobre.
  pintarLecturaScalp(dec, campos);

  // 7 · LA EDAD Y SU TOPE, EN PANTALLA. El encargo pide que la edad maxima de lo que se
  //     ensena se DECLARE y se ENSENE; aqui esta, con los dos cortes del bloque.
  refrescarEdad(d, sobre.tLlegada, nodos);

  // 8 · y si el marco no es scalp, la lectura del scalp en su tarjeta aparte
  pintarTarjetaScalp(d);
}

/* Repinta SOLO lo que depende del reloj. La llama el render y la llama el latido de 1 s de
 * `mesa-app.js`, asi que lo que la pantalla dice de la edad es verdad en cada instante. */
function refrescarEdad(d, tLlegada, nodos) {
  const v = edadViva(d, tLlegada);
  pintarEdad(d, nodos.edad, v);

  // LA TARJETA ENTERA LO DICE, no solo la linea de abajo: pasado el tope, el veredicto que
  // hay encima ya no se sostiene y quien mire tiene que verlo sin leer la letra pequena.
  nodos.caja.classList.toggle('rancio', Boolean(v.rancio));
  if (nodos.sello) {
    if (v.rancio) {
      nodos.sello.hidden = false;
      nodos.sello.textContent =
        'RANCIO · ' + num(v.s, 0) + ' s sin refrescar, por encima del tope de '
        + num(d.max_age_s, 0) + ' s';
    } else {
      nodos.sello.hidden = true;
      nodos.sello.textContent = '';
    }
  }
  return v;
}

/* LOS CAMPOS QUE SALEN DE LA LECTURA DEL SCALP. `origen` es `decide` (marco scalp) o
 * `lectura_scalp` (los otros). Si el campo no esta en el origen, NO se pinta: no es un hueco
 * que declarar, es que en ese marco no le corresponde estar ahi. */
function pintarLecturaScalp(origen, campos) {
  const hay = (k) => Object.prototype.hasOwnProperty.call(origen, k);

  if (hay('confirms')) {
    campos.appendChild(
      celdaLista('confirms', 'confirma', origen.confirms, {
        motivoVacio: 'sin lado: el sesgo no es LONG ni SHORT',
      })
    );
  }
  if (hay('invalidation_level')) {
    campos.appendChild(
      celda('invalidation_level', 'invalida · nivel de barrera', origen.invalidation_level, {
        cifra: true,
        clase: 'invalida',
        formato: (v) => num(v, 1),
      })
    );
  }
  if (hay('invalidates')) {
    campos.appendChild(
      celdaLista('invalidates', 'invalida · qué lo rompe', origen.invalidates, {
        clase: 'invalida',
        motivoVacio: 'sin lado: el sesgo no es LONG ni SHORT',
      })
    );
  }
  // HORIZONTE · sale de la persistencia MEDIDA, no de una cadena escrita a mano. Es el
  // defecto que D1 midio en `static/app.js:1435` y que K90 vigila.
  if (hay('horizon')) {
    const hor = origen.horizon || {};
    const cajaHor = celda('horizon', 'horizonte', hor);
    if (hor.outside_cut) {
      cajaHor.appendChild(
        el(
          'span',
          'motivo',
          'fuera del corte: agregado de ' + (hor.dias || '?') + ' d con su propio as_of'
        )
      );
    }
    campos.appendChild(cajaHor);
  }
  if (hay('state')) campos.appendChild(celda('state', 'estado', origen.state));
  if (hay('reason')) campos.appendChild(celda('reason', 'razón', origen.reason));
  if (hay('edge')) {
    campos.appendChild(
      celda('edge', 'ventaja (edge)', origen.edge, { cifra: true, formato: (v) => num(v, 2) })
    );
  }
  if (hay('evidence')) {
    campos.appendChild(
      celda('evidence', 'evidencia', origen.evidence, {
        cifra: true,
        formato: (v) => num(v, 0) + ' %',
      })
    );
  }
  if (hay('confidence')) {
    campos.appendChild(celda('confidence', 'confianza', origen.confidence));
  }
}

/* La tarjeta de la lectura del SCALP, que solo existe cuando el marco NO es scalp. */
function pintarTarjetaScalp(d) {
  const caja = document.getElementById('lectura-scalp');
  if (!caja) return;
  const ls = d.lectura_scalp;
  if (!ls) {
    caja.hidden = true;
    vaciar(document.getElementById('lectura-scalp-campos'));
    return;
  }
  caja.hidden = false;
  const suSesgo = (ls.bias && !esNada(ls.bias.value)) ? String(ls.bias.value) : null;
  document.getElementById('lectura-scalp-rotulo').textContent =
    'lectura del ' + String(ls.de_marco || 'scalp').toUpperCase()
    + (suSesgo ? ': ' + suSesgo : '')
    + ' — NO es el veredicto de ' + String(d.frame || '').toUpperCase();
  document.getElementById('lectura-scalp-aviso').textContent =
    (ls.ventana || '') + (ls.donde ? ' · se ve como lo que es en ' + ls.donde : '');

  const campos = vaciar(document.getElementById('lectura-scalp-campos'));
  // SU VEREDICTO PRIMERO, con su clave. `confirms` e `invalidates` sin decir de que lado son
  // es medio dato, y era lo que esta tarjeta ensenaba.
  if (ls.bias) {
    const c = celda('scalp.bias', 'sesgo del scalp', ls.bias);
    c.classList.add('sesgo-de-la-lectura');
    if (ls.bias.motivo) c.appendChild(el('span', 'motivo', ls.bias.motivo));
    campos.appendChild(c);
  }
  pintarLecturaScalp(ls, campos);
}

/* LA ZONA ES UN RANGO, Y SE PINTA COMO UN RANGO.
 * La entrega anterior decia que DECIDE ensenaba «zona · centro / low / high / dificultad» y
 * la pantalla solo pintaba el CENTRO: marcando las hojas servidas, low, high y difficulty no
 * llegaban. Una zona de la que solo se ve el centro no es una zona, es un precio.
 * Las tres cifras van cada una en SU celda -con su `data-campo` y su `data-source-key`- para
 * que K102 las verifique una a una, y a la vez se leen juntas como el rango que son. */
function celdaZonaRango(zona) {
  const z = zona || {};
  const caja = el('div', 'campo zona-rango');
  caja.appendChild(el('span', 'rotulo', 'zona · rango (low – centro – high)'));
  const fila = el('div', 'valor cifra zona-fila');

  const trozo = (nombre, campo) => {
    const sub = el('span', 'campo zona-trozo');
    sub.setAttribute('data-campo', nombre);
    const hay = campo && campo.status === 'ok' && !esNada(campo.value);
    const v = el('span', 'valor');
    v.setAttribute('data-valor', hay ? num(campo.value, 1) : '');
    if (hay) v.textContent = num(campo.value, 1);
    else v.appendChild(noSe((campo && campo.status) || 'ausente', (campo && campo.motivo) || null));
    sub.appendChild(v);
    if (campo && campo.source_key) sub.appendChild(nodoClave(campo.source_key));
    return sub;
  };

  fila.appendChild(trozo('zone.low', z.low));
  fila.appendChild(el('span', 'zona-sep', ' – '));
  fila.appendChild(trozo('zone.center', z.center));
  fila.appendChild(el('span', 'zona-sep', ' – '));
  fila.appendChild(trozo('zone.high', z.high));
  caja.appendChild(fila);
  caja.appendChild(celda('zone.difficulty', 'dificultad de la zona', z.difficulty));
  return caja;
}

/* LA EDAD VIVA, y por que no es la servida a secas.
 *
 * `age.snapshot_lag_seconds` es el lag EN EL INSTANTE EN QUE EL BACKEND ARMO LA RESPUESTA.
 * Pintarlo tal cual y no volver a tocarlo -que es lo que esta pantalla hacia- deja la linea
 * diciendo «5,0 s» para siempre: medido por el operador el 2026-09-29, cargada a las 06:05:24Z
 * y releida a las 06:07:34Z -130 s, pasado el tope de 120- seguia diciendo «5,0 s», sin RANCIO
 * y sin volver a pedir nada. Una mesa abierta una hora ensenaba como de 5 s un veredicto de
 * hace una hora.
 *
 * SE CUENTA CON EL RELOJ LOCAL, NO CON EL DEL SERVIDOR: `lag_servido + (ahora - cuando_llego)`.
 * Restar dos instantes de relojes distintos -el `build_finished_at` del servidor contra el
 * `Date.now()` del navegador- meteria el desfase entre las dos maquinas dentro de la cifra.
 * Con el tiempo TRANSCURRIDO aqui, el desfase se cancela.
 *
 * Y NO ES UN CONTADOR QUE SUBE SOLO: la cifra se recalcula, pero ademas `mesa-app.js` vuelve a
 * PEDIR DECIDE cada MESA_REFRESCO_S. Un numero que crece sin preguntar otra vez seria el mismo
 * defecto con otro disfraz.
 */
function edadViva(d, tLlegada) {
  const a = (d && d.age) || {};
  const lag = a.snapshot_lag_seconds || {};
  if (esNada(lag.value)) return { s: null, rancio: false, derivada: false };
  const ahora = (window.performance || Date).now();
  const transcurrido = tLlegada === undefined || tLlegada === null ? 0 : (ahora - tLlegada) / 1000;
  const s = Number(lag.value) + Math.max(0, transcurrido);
  const tope = Number(d.max_age_s);
  return { s, rancio: !Number.isNaN(tope) && s > tope, derivada: transcurrido > 0.5 };
}

function pintarEdad(d, nodo, viva) {
  const caja = vaciar(nodo);
  const a = d.age || {};
  const lag = a.snapshot_lag_seconds || {};
  const v = viva || edadViva(d, null);

  const trozo = (rotulo, texto, clase) => {
    const s = el('span', clase || null);
    s.appendChild(el('b', null, rotulo + ': '));
    if (texto && texto.nodeType) s.appendChild(texto);
    else s.appendChild(document.createTextNode(texto));
    return s;
  };

  const tope = d.max_age_s;
  if (v.s !== null) {
    const cls = claseFrescura(v.s, tope);
    caja.appendChild(
      trozo(
        'edad del snapshot',
        num(v.s, 1) + ' s (tope declarado ' + num(tope, 0) + ' s)'
          + (v.derivada ? ' · DERIVADA: ' + num(lag.value, 1) + ' s servidos + lo transcurrido' : ''),
        cls === 'viejo' ? 'rancio-aviso' : null
      )
    );
  } else {
    caja.appendChild(trozo('edad del snapshot', noSe(lag.status || 'ausente', lag.motivo)));
  }

  // EL VEREDICTO DE EDAD SALE DE LA EDAD VIVA, no del `stale` que el backend calculo al
  // armar: ese ya era pasado en el instante en que llego.
  if (v.rancio || a.stale) {
    caja.appendChild(
      trozo('veredicto de edad', 'RANCIO · ' + (a.stale_rule || ''), 'rancio-aviso')
    );
  }

  [a.price_cutoff_at, a.metrics_cutoff_at].forEach((c, i) => {
    const rotulo = i === 0 ? 'precio recortado a' : 'métricas recortadas a';
    if (c && c.status === 'ok' && !esNada(c.value)) {
      caja.appendChild(trozo(rotulo, String(c.value).replace('T', ' ').slice(0, 19) + ' UTC'));
    } else {
      caja.appendChild(trozo(rotulo, noSe((c && c.status) || 'ausente', c && c.motivo)));
    }
  });

  // LA DIFERENCIA ENTRE LAS DOS VENDIMIAS DEL MISMO BLOQUE, dicha con todas las letras, y
  // marcada como DERIVADA: no es una clave servida, es una resta de dos que si lo son.
  const p = a.price_cutoff_at && a.price_cutoff_at.value;
  const m = a.metrics_cutoff_at && a.metrics_cutoff_at.value;
  if (p && m) {
    const dif = Math.abs(Date.parse(p) - Date.parse(m)) / 1000;
    if (!Number.isNaN(dif)) {
      caja.appendChild(
        trozo('diferencia entre las dos vendimias', num(dif, 0) + ' s (DERIVADO de los dos cortes)')
      );
    }
  }

  const cut = d.envelope_cut || {};
  caja.appendChild(
    trozo(
      'corte',
      cut.snapshot === 'repeatable_read'
        ? 'UNA instantánea declarada (repeatable_read)'
        : 'SIN instantánea · ' + (cut.snapshot_reason || cut.snapshot)
    )
  );
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { CLASE_SESGO, ESCALON_CONFIANZA };
}
