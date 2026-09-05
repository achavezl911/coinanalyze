# DECLARADA · `GET /api/level/breakout`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-level-breakout.md`](../rutas/api-level-breakout.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

**NINGUNA de las 66 preguntas de la bateria la nombra.**

Medido sobre `entregas/20260904-2100-bateria-trader.md`: ninguna fila de las 54 (P0.1..P5.9) ni de las 12
(S1..S12) cita esta ruta en su columna de destino ni en la de medicion.

Eso NO significa que no sirva: significa que **el trader no le ha formulado**
**una pregunta**. Si es un instrumento interno, lo normal es que no la haya.
Si es superficie de producto y no contesta ninguna pregunta, merece mirarse.

## VENTANA

**PENDIENTE de familia.** parametros ['direction', 'level', 'symbol']: no encaja en 1/2/3 sin leerla

**PENDIENTE · no esta en la foto de produccion.** El captador la omitio porque
exige un parametro de precio (`level`, `low`/`high`) que **no se puede inventar**
(`entregas/20260904-foto-prod-1.json`, seccion `omitidas`).

El AST tampoco le deriva clave temporal. **No se sabe** si publica marca de tiempo:
hace falta una peticion con un precio real. Comando para cerrarlo:

```sh
harness/bin/api '/api/level/breakout?symbol=BTCUSDT&…'   # con el precio que corresponda
```

## PROMESA

**PENDIENTE.** No se ha escrito que promete esta ruta ni que significa no cumplirlo.

Una promesa vale si es comprobable: "publica el instante de construccion", "no
publica un 0 sin testigo", "la senal dura al menos N minutos". Si la ruta no
promete nada comprobable, eso tambien se escribe.

## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:2765`
