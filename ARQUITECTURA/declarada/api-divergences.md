# DECLARADA · `GET /api/divergences`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-divergences.md`](../rutas/api-divergences.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **1** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P5.6** — ¿Hay divergencias activas y qué han valido históricamente?  
  <sub>`entregas/20260904-2100-bateria-trader.md:190`</sub>

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

**MEDIDO en la foto de produccion** (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z, arco 37 387 ms).

El AST no le derivo ninguna clave temporal, pero **si publica marca de tiempo en el**
**cuerpo**. Son cosas distintas y aqui se separan: lo primero es un limite del
analisis estatico, lo segundo una afirmacion sobre el producto.

Claves **anidadas** (16), dentro de filas o bloques:

- `intraday.anchored_at` (nombre)
- `intraday.lag_seconds` (nombre)
- `intraday.windows.15m.lag_seconds` (nombre)
- `intraday.windows.15m.window_seconds` (nombre)
- `intraday.windows.16h.lag_seconds` (nombre)
- `intraday.windows.16h.window_seconds` (nombre)
- `intraday.windows.1h.lag_seconds` (nombre)
- `intraday.windows.1h.window_seconds` (nombre)
- _… y 8 mas_

**Y NO tiene ninguna de primer nivel.** O sea: la respuesta fecha sus FILAS pero
no se fecha a SI MISMA. Para K43 eso importa — un consumidor que quiera saber de
cuando es la foto entera tiene que deducirlo de la fila mas reciente, y eso es
adivinar. **Candidata a familia 1 con defecto declarado.**

<sub>Medido leyendo el cuerpo de la respuesta en la foto, no supuesto. 16 claves temporales en total.</sub>

## PROMESA


### Lo que promete

**PENDIENTE, y el motivo no es el tiempo: no he leido su cuerpo en la foto.**

Lo que si esta medido y va en su ficha derivada: la bateria le asigna **P5.6** —*"¿hay
divergencias activas y que han valido historicamente?"*— junto a `/api/cvd/divergence`
(`entregas/20260904-2100-bateria-trader.md:190`).

**Y la pregunta tiene dos mitades que casi nunca vienen juntas:** *"hay divergencias
activas"* es un estado, y *"que han valido historicamente"* es una tasa base. Una ruta puede
contestar la primera perfectamente y no contestar la segunda en absoluto.

Peticion con parametros comprobados:

```sh
harness/bin/api '/api/divergences?symbol=BTCUSDT_PERP.A' | python3 -m json.tool | head -30
```

**Lo que hay que mirar, en este orden:**
1. ¿publica un instante de primer nivel? (P0.1)
2. ¿cada divergencia trae su **tasa base historica**, o solo su existencia? Si solo publica
   la existencia, **la mitad de P5.6 no la contesta nadie** y eso es material de K.
3. ¿distingue una divergencia **ausente** de una **no calculable**? (P0.5)


## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1638`
- **readme**: `README.md:281`
