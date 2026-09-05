# DECLARADA · `GET /`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/raiz.md`](../rutas/raiz.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

**NINGUNA de las 66 preguntas de la bateria la nombra.**

Medido sobre `entregas/20260904-2100-bateria-trader.md`: ninguna fila de las 54 (P0.1..P5.9) ni de las 12
(S1..S12) cita esta ruta en su columna de destino ni en la de medicion.

Eso NO significa que no sirva: significa que **el trader no le ha formulado**
**una pregunta**. Si es un instrumento interno, lo normal es que no la haya.
Si es superficie de producto y no contesta ninguna pregunta, merece mirarse.

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

**MEDIDO en la foto de produccion** (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z): **no publica NINGUNA**
**marca temporal en el cuerpo.** Ni de primer nivel ni anidada.

Aqui el AST y la foto coinciden, asi que la afirmacion es firme: esta ruta no dice
de cuando es lo que publica. **Candidata a familia 4 de K43 (exenta), y la exencion
hay que escribirla con su cita** — o es un hueco, no una exencion.

<sub>Medido leyendo el cuerpo de la respuesta, no supuesto.</sub>

## PROMESA


### Lo que promete

**Sirve el panel.** Devuelve `FileResponse` (`app/api.py:2861`), o sea el `index.html`
estatico. No publica campos, y por eso su ficha derivada no deriva ninguno: **no hay
respuesta que describir, hay un fichero que se entrega**.

**PROMESA · es la puerta del producto y no promete ningun dato.** Todo lo que el trader ve
llega despues, por las llamadas que hace `static/app.js`. Esta ruta no participa en ninguna
de las 66 preguntas de la bateria, y eso es correcto: **es transporte, no contenido**.

*Que significa no cumplirlo:* que devolviera algo distinto de la aplicacion. Lo cubre el
humo del desplegador, no esta capa.

### Y sus consumidores no son medibles con este metodo, que ya esta declarado

Su ficha derivada lo explica con las cifras: el detector generico le acreditaba **505 citas**
—casi todas divisiones de python— y el criterio propio (barra entrecomillada y sola) baja a
**23**, de las que **cero** son una peticion HTTP. La barra entrecomillada es tan comun como
la division.

**Para saber quien consume la raiz hay que mirar el servidor, no el fuente:**

```sh
prod "grep -c ' / ' /var/log/nginx/access.log"
```

Es la unica de las 68 cuya superficie se mide fuera del repo, y queda dicho en vez de
rellenado.


## SUPERFICIE

**Superficie de producto**, medido.

- **checks**: `harness/checks/K05-control.bash:77`, `harness/checks/K05-latidos.sh:359`, `harness/checks/K05-latidos.sh:362`, `harness/checks/K13-vacio-o-rancio.sh:75`, `harness/checks/K52-el-minuto-corto.sh:189`, `harness/checks/K88-control.bash:105` _(+1)_
- **panel**: `static/app.js:66`
- **readme**: `README.md:294`, `README.md:296`
- **tests**: `tests/js/harness.js:127`, `tests/js/harness.js:147`, `tests/test_coinalyze_rate_limit.py:155`, `tests/test_data_gaps_postgres.py:89`, `tests/test_db.py:133`, `tests/test_metrics_endpoint.py:184` _(+5)_
