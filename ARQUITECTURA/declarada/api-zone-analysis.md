# DECLARADA · `GET /api/zone/analysis`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-zone-analysis.md`](../rutas/api-zone-analysis.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **1** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P2.6** — Si me saltan el stop, ¿es estructura o es una mecha?  
  <sub>`entregas/20260904-2100-bateria-trader.md:142`</sub>

## VENTANA

Familia **2** de K43 — coverage de su propia serie.

Derivado de su firma: pide ['days']: coverage de su propia serie.

**PENDIENTE · no esta en la foto de produccion.** El captador la omitio porque
exige un parametro de precio (`level`, `low`/`high`) que **no se puede inventar**
(`entregas/20260904-foto-prod-1.json`, seccion `omitidas`).

El AST tampoco le deriva clave temporal. **No se sabe** si publica marca de tiempo:
hace falta una peticion con un precio real. Comando para cerrarlo:

```sh
harness/bin/api '/api/zone/analysis?symbol=BTCUSDT&…'   # con el precio que corresponda
```

## PROMESA

**PENDIENTE.** No se ha escrito que promete esta ruta ni que significa no cumplirlo.

Una promesa vale si es comprobable: "publica el instante de construccion", "no
publica un 0 sin testigo", "la senal dura al menos N minutos". Si la ruta no
promete nada comprobable, eso tambien se escribe.

## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:2603`
