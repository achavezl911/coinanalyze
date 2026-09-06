# DECLARADA · `GET /api/cvd/spot`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-cvd-spot.md`](../rutas/api-cvd-spot.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

**NINGUNA de las 66 preguntas de la bateria la nombra.**

Medido sobre `entregas/20260904-2100-bateria-trader.md`: ninguna fila de las 54 (P0.1..P5.9) ni de las 12
(S1..S12) cita esta ruta en su columna de destino ni en la de medicion.

Eso NO significa que no sirva: significa que **el trader no le ha formulado**
**una pregunta**. Si es un instrumento interno, lo normal es que no la haya.
Si es superficie de producto y no contesta ninguna pregunta, merece mirarse.

## VENTANA

Familia **2** de K43 — coverage de su propia serie.

Derivado de su firma: pide ['interval', 'limit']: coverage de su propia serie.

**MEDIDO en la foto de produccion** (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z, arco 37 387 ms).

El AST no le derivo ninguna clave temporal, pero **si publica marca de tiempo en el**
**cuerpo**. Son cosas distintas y aqui se separan: lo primero es un limite del
analisis estatico, lo segundo una afirmacion sobre el producto.

Claves **anidadas** (6), dentro de filas o bloques:

- `coverage.served_window` (nombre)
- `coverage.served_window.window_end` (nombre)
- `coverage.served_window.window_start` (nombre)
- `data_gaps.window_end` (nombre)
- `data_gaps.window_start` (nombre)
- `rows[].bucket` (valor ISO)

**Y NO tiene ninguna de primer nivel.** O sea: la respuesta fecha sus FILAS pero
no se fecha a SI MISMA. Para K43 eso importa — un consumidor que quiera saber de
cuando es la foto entera tiene que deducirlo de la fila mas reciente, y eso es
adivinar. **Candidata a familia 1 con defecto declarado.**

<sub>Medido leyendo el cuerpo de la respuesta en la foto, no supuesto. 6 claves temporales en total.</sub>

## PROMESA


### Lo que promete

Es **la gemela spot de `/api/cvd`** y comparte su contrato entero: `symbol`, `interval`,
`rows = [576]` con `bucket`/`delta_usd`/`cvd`, mas `coverage.served_window` y `data_gaps`.
Ver la ficha de `/api/cvd` para las tres promesas de la familia.

**PROMESA NUEVA · 2026-09-06 · cada cubo declara CUANTOS SEGUNDOS DE MERCADO lo sostienen.**
Sus filas traen ademas `covered_seconds_min`, `short_minutes`, `unknown_minutes` y
`minutes_present`, los cuatro con la misma forma y el mismo significado que en
`/api/whale/delta` — que hasta hoy era la unica de las siete series que los publicaba.

*Por que aqui y no en las otras seis:* esta ruta lee `spot_trades_agg` con el **mismo
`WHERE`** que `whale/delta` (`api.py:761` contra `:1029`), y esa es una de las **dos** tablas
del sistema que declaran cobertura por segundo. Las otras cinco series no leen ninguna de las
dos, asi que a ellas no se les puede exigir.

*Que significa no cumplirlo, y es lo que pasaba hasta hoy:* un cubo de 5 minutos construido
sobre minutos cortos —el colector se fue a mitad— era **indistinguible de uno completo**. Y
aqui no hay red debajo: `spot_trades` no tiene detector de huecos, asi que `data_gap` no
tiene ni una fila suya (medido en 140) y el enmascarado no puede taparlo por otra via. La
misma pregunta tenia dos respuestas segun se entrara por `whale/delta` o por aqui.

*Lo que NO promete, y hay que decirlo:* `covered_seconds` dice **QUE** falta, no **CUANTO**.
La ficha de `whale/delta` lo tiene medido: sobre 21 arranques, la fraccion declarada tiene
mediana 0.367 y la de volumen observada 0.182. Usar esta marca como factor de escala para
"reparar" el delta es pasarse.

**PROMESA propia · publica el CVD de spot como serie separada del de futuros, y esa
separacion es la que hace posible la pregunta.**
`/api/cvd` (futuros) y esta (spot) son dos rutas y no una con un parametro. La bateria mide
en **P1.1** que *"el diferencial spot-futuros NO vota direccion"*, y esa comprobacion solo se
puede hacer si las dos series se pueden pedir **por separado y con el mismo `interval`**.

*Que significa no cumplirlo:* fundirlas en una ruta con `market=spot|perp`. Se seguiria
pudiendo, pero se perderia la garantia de que las dos usan el mismo bucket — y el diferencial
de dos series con distinto bucket no significa nada.

**El PANEL no la pide, y por eso K31 la marca HUECO.** Pero hasta el 2026-09-06 esta ficha
decia ademas que nadie la nombraba en el repo, y eso era **falso**: la derivada del mismo
commit dice `llamadas=2 menciones=4`. La nombran como SUJETO suyo dos checks,
`K02-cobertura-hueco.sh:66` y `K03-hueco-declarado.sh:46`, mas `K31-cubos.py:40` y
`README.md:404`.

*Por que sobrevivio esa frase falsa:* el brazo 5 de K88 tiene una regla para ese caso, pero
**es sensible a mayusculas** y la ficha lo escribia en versales. Medido el 2026-09-06: con
`IGNORECASE` el brazo caza 11 fichas, de las cuales **9 solo CITAN la formula entre comillas**
narrando un fallo pasado —no afirman nada de su ruta— y 2 la afirman; y de esas 2, en una
(`api-snapshot.md`) el que se equivoca es el MAPA, que cuenta como llamada un literal
`@app.get(...)` dentro de un test que parsea `api.py`. Encenderlo a secas fabricaria nueve
falsos y uno mas, asi que **no se enciende hoy**: necesita descartar el texto entrecomillado,
igual que el clasificador de prosa de F3d necesito distinguir una cadena literal de un
comentario. Queda anotado para la marca de agua.

*Y una nota sobre esta misma frase:* esta escrita en rodeo a proposito. Reproducir aqui la
formula exacta que el brazo 5 busca haria enrojecer al check **por hablar de el**, que es la
version en prosa del mismo problema.

Su dato llega al producto por `/api/cvd/divergence` y por `spot_trades_agg`, que leen 10 rutas.


## SUPERFICIE

**Instrumento interno**, medido.

- **readme**: `README.md:404`
