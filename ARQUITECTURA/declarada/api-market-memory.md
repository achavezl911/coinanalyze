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

**PENDIENTE.** No se ha escrito que promete esta ruta ni que significa no cumplirlo.

Una promesa vale si es comprobable: "publica el instante de construccion", "no
publica un 0 sin testigo", "la senal dura al menos N minutos". Si la ruta no
promete nada comprobable, eso tambien se escribe.

## SUPERFICIE

**Instrumento interno**, medido.

- **checks**: `harness/checks/K76-la-ventana-que-pides.sh:163`
- **readme**: `README.md:171`
