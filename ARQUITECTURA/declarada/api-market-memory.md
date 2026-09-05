# DECLARADA · `GET /api/market-memory`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-market-memory.md`](../rutas/api-market-memory.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **3** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P1.13** — ¿El régimen actual favorece este setup?  
  <sub>`entregas/20260904-2100-bateria-trader.md:125`</sub>
- **P2.2** — ¿Cuántas veces ese nivel ha aguantado?  
  <sub>`entregas/20260904-2100-bateria-trader.md:138`</sub>
- **P5.7** — ¿Qué dice la memoria de mercado de una situación como ésta?  
  <sub>`entregas/20260904-2100-bateria-trader.md:191`</sub>

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

**MEDIDO en la foto de produccion** (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z, arco 37 387 ms).

El AST no le derivo ninguna clave temporal, pero **si publica marca de tiempo en el**
**cuerpo**. Son cosas distintas y aqui se separan: lo primero es un limite del
analisis estatico, lo segundo una afirmacion sobre el producto.

Claves **anidadas** (7), dentro de filas o bloques:

- `analogs[].date` (nombre)
- `analogs[].state.volume_ratio_5d` (sufijo de periodo)
- `coverage.from` (nombre)
- `coverage.to` (nombre)
- `current.distance_from_high_pct` (nombre)
- `current.distance_from_low_pct` (nombre)
- `current.volume_ratio_5d` (sufijo de periodo)

**Y NO tiene ninguna de primer nivel.** O sea: la respuesta fecha sus FILAS pero
no se fecha a SI MISMA. Para K43 eso importa — un consumidor que quiera saber de
cuando es la foto entera tiene que deducirlo de la fila mas reciente, y eso es
adivinar. **Candidata a familia 1 con defecto declarado.**

<sub>Medido leyendo el cuerpo de la respuesta en la foto, no supuesto. 7 claves temporales en total.</sub>

## PROMESA


### Lo que promete

Medido en la foto (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z), **2 633 B**:

**PROMESA 1 · publica los ANALOGOS uno a uno, no solo su resumen.**
`analogs = [5]` con `date`, `similarity_score`, `state` y `forward` cada uno, mas
`analog_summary` con **`sample`**, tres medianas de retorno y `positive_20d_count`.

Es **P5.7** —*"¿que dice la memoria de mercado de una situacion como esta?"*— y, sobre todo,
**P5.2**: con `sample` y las cinco fechas publicadas, la n **no hay que suponerla**, y
`positive_20d_count` sobre `sample` es la tasa base sin tener que calcularla a ciegas.

**PROMESA 2 · el metodo esta escrito y es reproducible.**
`method = "5 vecinos no solapados por retorno…"` y `source = "OHLCV diario de futuros
Binance via…"`. **"No solapados"** es la palabra que importa: la bateria avisa en **P5.3**
de que *"si el muestreo solapa, la n efectiva es menor y el |t| real MAS PEQUEÑO que el
ingenuo"*. Aqui la ruta declara que no solapa.

**PROMESA 3 · declara su cobertura contra su objetivo.**
`coverage = {days, from, to, target_days}`. Los dias que hay **y** los que se querian, en
campos separados: una memoria de 2 años pedida y servida con 400 dias no se confunde con una
completa.

**PROMESA 4 · avisa de lo que un analogo NO es.**
`warning = "Los analogos describen lo que ocurrio…"`. Cinco vecinos historicos no son una
prediccion, y la ruta lo dice en su cuerpo.

*Que significa no cumplirlo:* que `analog_summary` viniera sin `sample`. Una mediana de 5
casos y una de 500 se pintarian igual, que es exactamente P5.2.


## SUPERFICIE

**Instrumento interno**, medido.

- **checks**: `harness/checks/K76-la-ventana-que-pides.sh:163`
- **readme**: `README.md:171`
