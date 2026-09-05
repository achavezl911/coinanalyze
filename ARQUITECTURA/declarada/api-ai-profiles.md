# DECLARADA · `GET /api/ai/profiles`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-ai-profiles.md`](../rutas/api-ai-profiles.md).
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


### Lo que promete

Devuelve los perfiles de analisis disponibles. No lee ninguna tabla: sale de codigo.

**No publica ninguna marca temporal**, y es de las **7 rutas de la foto sin ninguna**.
Igual que `/api/symbols`, aqui es **correcto**: son perfiles declarados en el codigo, no
una medida. **Familia 4 de K43 (exenta), con esta cita.**

**PROMESA · enumera los perfiles que el sistema acepta, y esa lista es la misma que valida
las peticiones.** Si divergiera, un perfil listado aqui seria rechazado por
`/api/ai/context`.

**PENDIENTE · no lo he comprobado.** Haria falta cruzar esta lista contra el validador de
`/api/ai/context`. Comando:

```sh
harness/bin/api /api/ai/profiles
harness/bin/api '/api/ai/context?symbol=BTCUSDT&profile=<uno de los listados>'
```

Consumidores: `harness/checks/K31-eslabon5.sh:60` la llama; `README.md:416` y `:520` la
mencionan. **No la llama el panel.**


## SUPERFICIE

**Instrumento interno**, medido.

- **readme**: `README.md:416`, `README.md:520`
