# DECLARADA · `GET /api/healthz`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-healthz.md`](../rutas/api-healthz.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **1** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P0.3** — ¿El colector que produce esto está vivo AHORA?  
  <sub>`entregas/20260904-2100-bateria-trader.md:95`</sub>

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

**MEDIDO en la foto de produccion** (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z, arco 37 387 ms).

El AST no le derivo ninguna clave temporal, pero **si publica marca de tiempo en el**
**cuerpo**. Son cosas distintas y aqui se separan: lo primero es un limite del
analisis estatico, lo segundo una afirmacion sobre el producto.

Claves **anidadas** (4), dentro de filas o bloques:

- `services[].lag_seconds` (nombre)
- `services[].updated_at` (nombre)
- `symbols[].lag_seconds` (nombre)
- `symbols[].latest_snapshot` (valor ISO)

**Y NO tiene ninguna de primer nivel.** O sea: la respuesta fecha sus FILAS pero
no se fecha a SI MISMA. Para K43 eso importa — un consumidor que quiera saber de
cuando es la foto entera tiene que deducirlo de la fila mas reciente, y eso es
adivinar. **Candidata a familia 1 con defecto declarado.**

<sub>Medido leyendo el cuerpo de la respuesta en la foto, no supuesto. 4 claves temporales en total.</sub>

## PROMESA


### Lo que promete

**PROMESA 1 · nombra a los que FALTAN, no solo a los que estan.**
En la foto (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z): `governed_services = [12]`, `missing_services = [0]`,
`missing_symbols = [0]`, y `services = [12]` con `service`, `updated_at`, `status`,
`detail` y `lag_seconds` cada uno.

`missing_services` es la clave: una lista de servicios vivos **no dice nada** sobre los que
deberian estar y no reportan. Publicar el conjunto GOBERNADO al lado del observado
convierte "faltan servicios" en una resta, no en una sospecha. Es **P0.5** aplicado al eje
de los servicios: un servicio ausente y uno que no existe se distinguen.

**PROMESA 2 · declara CONTRA QUE BASE responde.**
`database = {database, db_user, db_host, db_port, server_version, schema_fingerprint}`.
Con `schema_fingerprint`, dos instancias con el mismo nombre y esquemas distintos dejan de
ser indistinguibles — que es lo que vigila `harness/checks/K08-que-base.sh:33`.

**PROMESA 3 · cada servicio trae SU retraso, no uno global.**
`lag_seconds` por servicio y por simbolo. Un `status = "ok"` global con un colector a 40
minutos es exactamente el cero tranquilizador que este arnes persigue; con el lag por fila
no se puede ocultar.

*Que significa no cumplirlo:* que `status` fuera `ok` con algo en `missing_services`, o que
`lag_seconds` desapareciera. Lo vigila K05 en dos sitios (`:127` y `:388`).

**ESCRIBE en `pipeline_heartbeat`**, y es la unica ruta de las 68 que escribe una tabla.
Una ruta de salud que deja rastro de haber sido consultada tiene sentido, pero **conviene
saberlo**: pedir `/api/healthz` no es una operacion de solo lectura.


## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1494`, `static/app.js:1622`
- **readme**: `README.md:413`
