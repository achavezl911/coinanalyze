# DECLARADA · `GET /api/wyckoff`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-wyckoff.md`](../rutas/api-wyckoff.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **2** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P1.4** — ¿En qué fase de Wyckoff estamos?  
  <sub>`entregas/20260904-2100-bateria-trader.md:116`</sub>
- **S11** — ¿Wyckoff distingue acumulación de distribución, o sólo detecta una?  
  <sub>`entregas/20260904-2100-bateria-trader.md:328`</sub>

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

**MEDIDO en la foto de produccion** (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z, arco 37 387 ms).

El AST no le derivo ninguna clave temporal, pero **si publica marca de tiempo en el**
**cuerpo**. Son cosas distintas y aqui se separan: lo primero es un limite del
analisis estatico, lo segundo una afirmacion sobre el producto.

Claves **anidadas** (5), dentro de filas o bloques:

- `chart_bars[].time` (nombre)
- `events[].date` (nombre)
- `range.end_offset_bars` (nombre)
- `range.from` (nombre)
- `range.to` (nombre)

**Y NO tiene ninguna de primer nivel.** O sea: la respuesta fecha sus FILAS pero
no se fecha a SI MISMA. Para K43 eso importa — un consumidor que quiera saber de
cuando es la foto entera tiene que deducirlo de la fila mas reciente, y eso es
adivinar. **Candidata a familia 1 con defecto declarado.**

<sub>Medido leyendo el cuerpo de la respuesta en la foto, no supuesto. 5 claves temporales en total.</sub>

## PROMESA


### Lo que promete

**PROMESA 1 · separa "no hay fase" de "no se pudo calcular".** `available` es un campo de
primer nivel. Es **P0.5** en la familia de estructura: sin el, una fase vacia y un calculo
que fallo son el mismo hueco.

**PROMESA 2 · la fase viene con su EXPLICACION y sus EVENTOS.**
`phase = {code, state, explanation}`, `events = [1]` con `date`, `close`,
`volume_multiple`, `bars_ago`, `type` y `direction`, y `bias` con
**`evidence_coverage_pct`** y `agreement`.

`evidence_coverage_pct` es la respuesta a **P0.4** —*"¿que antigüedad tiene el dato mas
viejo que entra en este calculo?"*— por el lado de la cobertura: una fase decidida con el
40 % de la evidencia y otra con el 100 % no se pintan igual.

**PROMESA 3 · publica el rango del que sale.** `range = {available, from, to, low, high,
mid…}`: los bordes son datos, no una raya.

*Que significa no cumplirlo:* **P1.4 y S11 lo dicen y son la misma pregunta por dos lados**:
*"¿la fase cambia alguna vez, o es una etiqueta pegajosa?"* y *"¿Wyckoff distingue
acumulacion de distribucion, o solo detecta una?"*. Una fase que nunca cambia cumple todas
las promesas de forma y no vale nada.

**PENDIENTE · y el motivo NO es el tiempo: es que la fase no se guarda en ningun sitio.**

La version anterior de esta ficha pedia
`SELECT wyckoff_phase, COUNT(*) FROM daily_verdict`. **Esa columna no existe.** Comprobado
contra el esquema versionado antes de volver a pedir nada:

```sh
$ grep -c -i "wyckoff" sql/schema.sql
0
$ grep -n "def _phase" app/wyckoff.py
401:def _phase(
```

**Cero apariciones de `wyckoff` en las 40 tablas del esquema.** La fase se calcula al vuelo
en `app/wyckoff.py:401` y se devuelve en la respuesta; **no se persiste**.

Consecuencia para la bateria: **P1.4** —*"¿la fase cambia alguna vez, o es una etiqueta
pegajosa?"*— y **S11** —*"¿distingue acumulacion de distribucion?"*— **no se pueden medir
con ninguna consulta a la base**. Solo se pueden medir capturando `/api/wyckoff` en el
tiempo, que es un instrumento que hoy no existe:

```sh
# no hay serie: habria que capturar la ruta N veces y guardar phase.code
harness/bin/api '/api/wyckoff?symbol=BTCUSDT' | python3 -c "import json,sys;print(json.load(sys.stdin)['phase'])"
```

**Y esto es de la misma clase que el `ts` de K90 en F3c**: una consulta escrita contra un
esquema supuesto. La regla que sale de las dos: *antes de pedir una consulta, comprobar sus
columnas contra el esquema y pegar el comando*.

**La llama el panel** (`static/app.js:1481` y `:1583`).


## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1481`, `static/app.js:1583`
- **readme**: `README.md:149`
- **tests**: `tests/test_wyckoff.py:106`
