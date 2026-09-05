# DECLARADA · `GET /metrics`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/metrics.md`](../rutas/metrics.md).
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

**No publica JSON: es texto de Prometheus** (`Response`, `app/api.py:2669`), y por eso la
capa derivada marca sus campos PENDIENTE. Su contrato no es un objeto: es un formato de
exposicion con su propio estandar.

**PROMESA · expone el estado del sistema en el formato que un recolector espera, y lee
`metrics_snapshot` y `pipeline_heartbeat` para hacerlo** (ver ficha derivada).

**Y no la llama nadie**: es una de las rutas cuyos unicos rastros son menciones. No hay
ningun Prometheus configurado en este repo que la recoja —`grep -rn "prometheus"` sobre
`deploy/` y `config/` es el comando que lo cerraria—, asi que hoy es **superficie preparada
para un consumidor que no existe**.

Eso NO es un defecto por si mismo: una ruta de metricas es lo primero que se escribe y lo
ultimo que se conecta. Pero es la forma del patron que en esta casa se ha repetido nueve
veces, y por eso queda escrito.

**PENDIENTE · una comprobacion barata que no he hecho:**

```sh
grep -rn "prometheus\|/metrics" deploy/ config/ 2>/dev/null | wc -l
```

Si sale 0, nadie la recoge y su promesa es solo potencial.


## SUPERFICIE

**Instrumento interno**, medido.

- **readme**: `README.md:290`, `README.md:291`, `README.md:319`, `README.md:503`
