# DECLARADA · `GET /api/symbols`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-symbols.md`](../rutas/api-symbols.md).
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


### Lo que promete, y es poco a proposito

En la foto (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z) devuelve **una lista de 3 elementos** con `symbol` y `asset`. No lee
ninguna tabla: sale de `SETTINGS.SYMBOLS` y `WS_SYMBOL_MAP` (`app/api.py:609-611`).

**PROMESA · es la lista de simbolos CONFIGURADOS, no la de simbolos con datos.**
Que una ruta la nombre no garantiza que haya una fila suya en ninguna tabla.

*Que significa:* usarla como universo para un recuento produce denominadores que incluyen
simbolos sin dato. Es la forma de **P0.5** aplicada al eje de los simbolos.

**No publica marca temporal, y aqui SI es correcto**: es configuracion, no medida.
**Familia 4 de K43 (exenta), y esta es la cita de la exencion.**

Consumidores: `static/app.js:1804` (**la llama el panel**),
`harness/checks/K43-foto-unica.sh:106`, `tests/test_deploy_health_gate.py:180`.


## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1804`
- **tests**: `tests/test_deploy_health_gate.py:180`
