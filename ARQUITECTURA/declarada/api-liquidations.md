# DECLARADA · `GET /api/liquidations`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-liquidations.md`](../rutas/api-liquidations.md).
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

### Las series de familia 2 comparten contrato, y se declaran juntas

Medido en la foto (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z): **336 buckets de 1 hora** publica `symbol`, `interval`, `rows`, y ademas
**`coverage`** y **`data_gaps`** — los dos ultimos son el contrato de la familia y valen
mas que las filas.

**PROMESA 1 · declara LA VENTANA QUE SIRVIO, no la que le pidieron.**
`coverage = {served_window}`. Un `limit` es una peticion; `served_window` es lo que
hay. La ruta no deja que el consumidor deduzca la ventana contando filas — que es lo que
haria si `rows` viniera solo.

*Que significa no cumplirlo:* que `coverage` desapareciera. Entonces una serie corta por
falta de dato y una serie corta porque se pidio poco serian indistinguibles, y cualquier
tasa calculada encima tendria un denominador supuesto. Es **P5.2** llevado a las series.

**PROMESA 2 · publica SUS HUECOS, no solo sus filas.**
`data_gaps` trae `feed`, `exchanges`, `market`, `symbol`, `window_start`, `window_end`… Es
la respuesta a **P0.2** —*"¿hay algun agujero en el historico que estoy mirando?"*— y la
bateria le pone un caso concreto: **las 38 h del 08-28/29**. Una serie que publica sus
huecos permite preguntar; una que los omite obliga a fiarse.

**PROMESA 3 · el hueco declarado ENMASCARA el valor, no lo maquilla.**
Es lo que hace `mask_gapped_series_rows` (`app/api.py:679-689`), y el codigo lo explica:

> *"Un bucket con hueco declarado no puede seguir devolviendo precios como si nada:
> `sample_count` y `coverage_pct` son material para ADIVINAR la cobertura, y adivinar es
> justo lo que el panel no debe tener que hacer. Aqui la vela entera se pone a null, que es
> una afirmacion y no una pista."*

*Que significa no cumplirlo:* devolver el ultimo valor conocido en un bucket con hueco. Es
**P0.9** —*"si el proveedor esta caido, ¿me entero o veo el ultimo valor congelado?"*— y la
diferencia entre `null` y un numero rancio es la diferencia entre saberlo y no saberlo.

### Lo propio de esta ruta

**PROMESA · es una serie de EVENTOS agregados, no un mapa de niveles.**
Es la distincion que la bateria marca en **P2.4** y que `/api/liquidation-map` declara en su
cuerpo con `type: historical_realized_density_3h`. Esta ruta es la serie temporal de lo
mismo: **cuando** se ejecutaron, no **donde**.

*Que significa no cumplirlo:* que un consumidor la use para responder *"¿donde hay
liquidaciones que puedan acelerar en mi contra?"*. La respuesta a esa pregunta no esta en
ninguna de las dos: ninguna ve las posiciones abiertas.

**PENDIENTE · S7 no la puedo cerrar desde aqui.** *"¿las liquidaciones que me amenazan son
las de mi lado?"* exige saber si las filas separan `long_liq` de `short_liq`. En la foto no
lei sus columnas:

```sh
harness/bin/api '/api/liquidations?symbol=BTCUSDT&limit=3' | python3 -m json.tool
```


## SUPERFICIE

**Instrumento interno**, medido.

- **readme**: `README.md:407`
