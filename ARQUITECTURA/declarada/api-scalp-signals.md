# DECLARADA · `GET /api/scalp/signals`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-scalp-signals.md`](../rutas/api-scalp-signals.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **1** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P1.1** — ¿Hay una señal activa ahora y de qué lado?  
  <sub>`entregas/20260904-2100-bateria-trader.md:113`</sub>

## VENTANA

Familia **2** de K43 — coverage de su propia serie.

Derivado de su firma: pide ['limit']: coverage de su propia serie.

**MEDIDO en la foto de produccion** (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z, arco 37 387 ms).

El AST no le derivo ninguna clave temporal, pero **si publica marca de tiempo en el**
**cuerpo**. Son cosas distintas y aqui se separan: lo primero es un limite del
analisis estatico, lo segundo una afirmacion sobre el producto.

Claves **anidadas** (6), dentro de filas o bloques:

- `rows[].book_lag_seconds` (nombre)
- `rows[].diff_3m` (sufijo de periodo)
- `rows[].fut_delta_1m` (sufijo de periodo)
- `rows[].fut_delta_3m` (sufijo de periodo)
- `rows[].spot_delta_3m` (sufijo de periodo)
- `rows[].ts` (nombre)

**Y NO tiene ninguna de primer nivel.** O sea: la respuesta fecha sus FILAS pero
no se fecha a SI MISMA. Para K43 eso importa — un consumidor que quiera saber de
cuando es la foto entera tiene que deducirlo de la fila mas reciente, y eso es
adivinar. **Candidata a familia 1 con defecto declarado.**

<sub>Medido leyendo el cuerpo de la respuesta en la foto, no supuesto. 6 claves temporales en total.</sub>

## PROMESA


### Lo propio de esta ruta

**PROMESA · publica la serie con la que se puede AUDITAR el estado, con sus dos scores.**
En la foto: `rows = [200]` con `ts`, `long_score`, `short_score`, `state` y `confidence`.

Es la unica puerta por la que `state` se puede **recalcular desde sus insumos**: con
`long_score` y `short_score` en cada fila, la regla de `scalp_bias_label`
(`app/scalp_logic.py:301-313`: `edge < 12` -> No Trade, `>= 70` -> Momentum, `>= 58` ->
Pullback) se puede reproducir fuera del sistema. Eso contesta **P1.5** aplicado al scalp:
*"si el score no se puede recalcular desde sus componentes publicados, no es auditable"*.

*Que significa no cumplirlo:* que `state` viniera sin los dos scores. Entonces la unica
forma de comprobar la etiqueta seria creersela.

**Y aqui esta el otro extremo de K90:** esta serie, con `ts` por fila, es **la que permite
medir la persistencia** que `/api/scalp/summary` no promete. La ruta cumple; lo que no
cumple es el rotulo del panel.

**Ya la llama alguien** (2026-09-06): la pinta `static/app.js` en la pestaña `#replay`, que se
carga A DEMANDA — el resumen de arranque sigue sin pedirla. Hasta ese dia sus rastros eran solo
MENCIONES y la serie que hace auditable al scalp no la consumia nadie.

**Y desde ese dia publica su propio sobre.** Antes devolvia `{symbol, rows}` a secas: 200 filas
y ni una palabra sobre si habia mas detras. Ahora lleva `count`, `truncated`, `servida_desde`,
`servida_hasta` y `ventana_maxima_h`. El ultimo vale **null a proposito**, y el null dice "no
aplica", no "no lo se": esta ruta **no acepta `since` ni `until`**, asi que el tope de 24 h de
`LEDGER_MAX_WINDOW` no le toca. Su unico limite es de FILAS. La ventana que publica no es la
PEDIDA sino la SERVIDA — el `ts` de la fila mas vieja y el de la mas nueva de las que salieron.


## SUPERFICIE

**Instrumento interno**, medido.

- **readme**: `README.md:488`, `README.md:498`
