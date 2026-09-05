# DECLARADA · `GET /api/volatility`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-volatility.md`](../rutas/api-volatility.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **1** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P2.5** — ¿Qué distancia hay hasta mi stop en % y en ATR?  
  <sub>`entregas/20260904-2100-bateria-trader.md:141`</sub>

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

**MEDIDO en la foto de produccion** (`entregas/20260904-foto-prod-1.json`,
2026-09-04T22:34:11Z, arco 37 387 ms): **NO publica ninguna marca temporal.**

18 hojas en el cuerpo, **0 con nombre o valor temporal**: `symbol`, `atr`,
`realized_vol_annualized_pct`, `daily_range_percentile_1y`, `compression_score`,
`range_expansion`, `note`.

### El error que esta seccion tuvo, porque explica una distincion de K43

La primera version decia que **si** publicaba marca, y su unica prueba era
`daily_range_percentile_1y`: mi detector la marco por el sufijo `_1y`. **Un sufijo de
periodo declara la VENTANA DEL CALCULO, no el INSTANTE DE LA RESPUESTA**, y son cosas
distintas — es justo la distincion que K43 persigue. `_1y` dice *sobre cuanto historico se
calculo el percentil*; no dice *de cuando es este numero*.

Esa confusion hizo que la tabla de la entrega publicara **27 con marca · 7 sin ninguna**
cuando lo coherente es **26 · 8 · 2**, contradiciendo a la seccion PROMESA de esta misma
ficha, que ya decia que no publica ninguna.

**Familia 1 de K43 con defecto declarado**: es estado ambiente y **no dice de cuando es**.
Un ATR de hace seis horas se parece mucho a uno de ahora.

## PROMESA


### NADIE LA LLAMA, y esta medido

El recuento esta en [`rutas/api-volatility.md`](../rutas/api-volatility.md) y **no se
copia aqui**: esta misma frase afirmaba a mano un recuento de rastro nulo en el commit anterior
mientras `derivada.json` del **mismo commit** listaba una mencion — y la mencion era el
comentario que explicaba que se habia quitado esta ruta de un fixture. El arreglo quito el
fixture; la prosa que lo explicaba volvio a meterla.

No prueba que este muerta -puede llamarla una IA por su nombre, o algo fuera del repo-,
pero es la forma exacta del patron que en esta casa se ha repetido nueve veces.

### Lo que promete

**PROMESA · publica la volatilidad en las TRES formas que hacen falta para un stop.**
En la foto: `atr` por `5m`/`15m`/`1h`/`4h`/`1d`, `realized_vol_annualized_pct` por
`1h`/`24h`/`7d`, `daily_range_percentile_1y = 43.6`, `compression_score = 0.488`,
`range_expansion = false` y `note = "realized vol anualizada desde velas…"`.

Contesta **P2.5** -"¿que distancia hay hasta mi stop en % y en ATR?"- con el ATR de cinco
marcos, que es lo que permite decir si *"un stop a 0.3 % en un activo con ATR de 2 % es
ruido, no stop"*.

**PROMESA · el percentil trae SU ventana en el nombre.** `daily_range_percentile_1y`: el
`_1y` va en la clave, no en la documentacion. Un percentil sin ventana no es comparable
entre dias.

**NO publica ninguna marca temporal**, y aqui pesa: un ATR de hace seis horas se parece
mucho a uno de ahora, y no hay forma de distinguirlos desde la respuesta. **Candidata a la
misma familia que `/api/scalp/liquidation-levels`.**


## SUPERFICIE

**El recuento vive en la ficha derivada**, que se regenera: [`rutas/api-volatility.md`](../rutas/api-volatility.md), seccion *Superficie*. Aqui NO se copia el numero.

La primera version de estas fichas lo copiaba y envejecio el mismo dia: el andamio escribio "sin consumidor conocido" cuando el detector no veia `RUTA=/api/x` ni `$VAR/api/x`, y al arreglarlo la prosa quedo mintiendo mientras el JSON del mismo commit decia otra cosa. K88 lo caza ahora (brazo 5), y esto quita la causa.

Lo que si aporta esta capa: de lo que hay, **nada es una llamada**. Una ruta de la que solo se habla en comentarios no tiene consumidor: tiene quien la nombra.
