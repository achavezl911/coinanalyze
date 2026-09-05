# DECLARADA · `GET /api/scalp/alerts`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-scalp-alerts.md`](../rutas/api-scalp-alerts.md).
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


### Esta ruta NO promete nada comprobable, y eso es lo que se escribe

En la foto devuelve `alerts = [1]` con `priority`, `side`, `message` y `detail`: **cuatro
campos, ninguno temporal, ninguno numerico auditable**. `message` y `detail` son prosa.

**No publica:** ni su instante, ni la ventana de la que sale la alerta, ni el umbral que la
disparo, ni cuantas veces se ha disparado antes. Es de las **7 rutas sin ninguna marca
temporal** de la foto.

**PROMESA declarada:** *emite alertas con prioridad y lado, y no promete nada sobre cuando
se generaron, sobre que ventana miran ni sobre su tasa base.*

*Que significa:* una alerta sin instante no se puede desduplicar, y sin tasa base no se
puede juzgar. **P1.7** -"¿cuantas senales de este tipo en 30 dias?"- no tiene respuesta
posible desde aqui.

**Y nadie la llama:** sus dos unicos rastros son MENCIONES en comentarios
(`harness/checks/K31-cubos.py:18` y `:187`). Una ruta de la que solo se habla.


## SUPERFICIE

**Sin consumidor conocido**, medido: no aparece en `static/app.js`,
`static/index.html`, `harness/checks`, `tests`, `tools` ni `README.md`.

No prueba que este muerta -puede llamarla algo fuera del repo-, pero es la
forma del patron que en esta casa se ha repetido nueve veces.
