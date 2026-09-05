# DECLARADA · `GET /api/cvd/divergence`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-cvd-divergence.md`](../rutas/api-cvd-divergence.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **1** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P5.6** — ¿Hay divergencias activas y qué han valido históricamente?  
  <sub>`entregas/20260904-2100-bateria-trader.md:190`</sub>

## VENTANA

Familia **2** de K43 — coverage de su propia serie.

Derivado de su firma: pide ['interval', 'limit']: coverage de su propia serie.

**MEDIDO en la foto de produccion** (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z, arco 37 387 ms).

El AST no le derivo ninguna clave temporal, pero **si publica marca de tiempo en el**
**cuerpo**. Son cosas distintas y aqui se separan: lo primero es un limite del
analisis estatico, lo segundo una afirmacion sobre el producto.

Claves **anidadas** (5), dentro de filas o bloques:

- `coverage.served_window` (nombre)
- `coverage.served_window.sources.ohlcv_1min` (sufijo de periodo)
- `coverage.served_window.window_end` (nombre)
- `coverage.served_window.window_start` (nombre)
- `rows[].bucket` (valor ISO)

**Y NO tiene ninguna de primer nivel.** O sea: la respuesta fecha sus FILAS pero
no se fecha a SI MISMA. Para K43 eso importa — un consumidor que quiera saber de
cuando es la foto entera tiene que deducirlo de la fila mas reciente, y eso es
adivinar. **Candidata a familia 1 con defecto declarado.**

<sub>Medido leyendo el cuerpo de la respuesta en la foto, no supuesto. 5 claves temporales en total.</sub>

## PROMESA


### Lo que promete

**MEDIDO en la foto (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z), 70 636 B**:

```
symbol · interval = '5min'
rows = [576] {bucket, cvd_fut, cvd_spot, cvd_diff}
coverage = {served_window, status}
```

**PROMESA 1 · publica las DOS series y su diferencia, no solo la diferencia.**
`cvd_fut`, `cvd_spot` y `cvd_diff` en cada uno de los 576 buckets. Es lo que hace la
divergencia **auditable**: `cvd_fut - cvd_spot` tiene que dar `cvd_diff`, y eso se comprueba
sin salir de la respuesta. Una ruta que publicara solo `cvd_diff` obligaria a creersela.

Y es lo que permite comprobar la afirmacion que la bateria ya midio en **P1.1** —*"el
diferencial spot-futuros NO vota direccion"*—: con las dos patas publicadas se puede
re-derivar, con una sola no.

**PROMESA 2 · su `coverage` trae `status`, y es la unica serie que lo hace.**
Las otras cuatro series de familia 2 (`ohlcv`, `cvd`, `oi`, `liquidations`) publican
`coverage = {served_window}` a secas. Esta anade **`status`**: no solo dice que ventana
sirvio, sino **si esa ventana es buena**. Un `served_window` completo con `status` malo es
una afirmacion que las otras cuatro no pueden hacer.

**PROMESA 3 · las dos patas comparten bucket por construccion.**
`interval = "5min"` es uno solo para las dos series. Un diferencial calculado con dos
series de distinto bucket no significa nada, y aqui no puede pasar porque van en la misma
fila.

### La comparacion con `/api/divergences`, y por que NO son redundantes

Las dos contestan **P5.6** y son **distintas**, no duplicadas:

```
/api/cvd/divergence   la SERIE: 576 buckets de 5 min, precio-CVD futuros contra spot
/api/divergences      el VEREDICTO: 7 ventanas de sesion, con summary y windows_confirming
```

Una publica el material y la otra la lectura. **La comparacion de P1.2 —"tres rutas hablan
de lo mismo"— aqui es legitima**: se puede re-derivar el veredicto de `/api/divergences`
desde la serie de esta, y si no cuadraran, la discrepancia seria un defecto y no una deriva
**porque las dos declaran su ventana**.

**PENDIENTE · esa re-derivacion no la he hecho**, y no es cuestion de tiempo: las dos
ventanas son distintas (576 buckets de 5 min contra 90 sesiones), asi que hace falta decidir
como se agregan los buckets a sesiones antes de comparar. El comando, con el simbolo real:

```sh
harness/bin/api '/api/cvd/divergence?symbol=BTCUSDT_PERP.A' > /tmp/serie.json
harness/bin/api '/api/divergences?symbol=BTCUSDT_PERP.A'    > /tmp/verd.json
wc -c /tmp/serie.json /tmp/verd.json
```

## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1547`
- **readme**: `README.md:405`
