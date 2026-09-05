# DECLARADA · `GET /api/signals/outcomes`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-signals-outcomes.md`](../rutas/api-signals-outcomes.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **6** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P1.14** — ¿Cuántas veces este setup ha funcionado en ESTE régimen?  
  <sub>`entregas/20260904-2100-bateria-trader.md:126`</sub>
- **P3.3** — ¿Cuánto tarda históricamente en llegar?  
  <sub>`entregas/20260904-2100-bateria-trader.md:154`</sub>
- **P3.4** — ¿Cuántas veces llegó al objetivo antes que al stop?  
  <sub>`entregas/20260904-2100-bateria-trader.md:155`</sub>
- **P5.1** — ¿Cuál es la expectativa histórica de este setup?  
  <sub>`entregas/20260904-2100-bateria-trader.md:185`</sub>
- **P5.2** — ¿Sobre cuántas operaciones se calcula?  
  <sub>`entregas/20260904-2100-bateria-trader.md:186`</sub>
- **S3** — ¿La expectativa histórica de los cortos se calcula igual que la de los largos?  
  <sub>`entregas/20260904-2100-bateria-trader.md:320`</sub>

## VENTANA

Familia **3** de K43 — su propio as_of bajo demanda.

Derivado de su firma: pide ['since']: el operador elige el momento.

Declara su ventana con estas claves, derivadas de los campos que publica:

- `since` — literal en app/api.py:2240
- `until` — literal en app/api.py:2241

## PROMESA

### Las cinco de `/api/signals/*` comparten contrato, y por eso se declaran juntas

Medido sobre la foto de produccion (`entregas/20260904-foto-prod-1.json`,
2026-09-04T22:34:11Z, arco 37 387 ms): las cinco publican **`symbol`, `since`, `until`,
`limit`, `count`, `truncated`** y su coleccion. No es un parecido: es el mismo contrato.

**PROMESA 1 · devuelve el ECO de la ventana que USO, no la que le pidieron.**
En la foto se pidieron sin `since` ni `until`, y las cinco contestaron con el par relleno
-`21:33:11Z` .. `22:33:11Z`, una hora exacta hacia atras desde el instante de la peticion-.
O sea que la ruta **no deja que el consumidor suponga la ventana por defecto**: la dice.

*Que significa no cumplirlo:* que `since`/`until` faltaran o no cuadraran con las filas
devueltas. Un consumidor que cuente eventos sobre una ventana que no conoce publica una
tasa sin denominador, que es la forma de error mas cara de esta bateria (P5.2).

**PROMESA 2 · NO devuelve una lista cortada sin decirlo.**
`truncated` viaja al lado de `count` y `limit` en las cinco. Con `limit` alcanzado y
`truncated` en `false`, o `count > limit`, la promesa esta rota.

*Que significa no cumplirlo:* exactamente el defecto de P5.2 -"¿sobre cuantas operaciones
se calcula?"-. Una lista truncada en silencio convierte cualquier agregado de aguas abajo
en una cifra plausible y falsa, y no hay forma de notarlo desde fuera.

**PROMESA 3 · valida la zona horaria en vez de suponerla.**
`422 · "since/until necesitan zona horaria explicita"` (`app/api.py:2112`, y su gemelo en
las otras cuatro). La ruta prefiere fallar a interpretar un instante ambiguo.

*Que significa no cumplirlo:* un `since` sin zona interpretado como local movería la
ventana entera y las cifras seguirian pareciendo razonables.

**LO QUE NINGUNA DE LAS CINCO PROMETE, y conviene tenerlo escrito:** ninguna publica su
propio instante de construccion. `until` es el borde de la ventana pedida, no "cuando se
armo esta respuesta". Con `since`/`until` rellenos por defecto los dos coinciden en la
practica, pero es una coincidencia del camino por defecto, no una promesa.

### Lo propio de esta ruta

**PROMESA 4 · el resultado va SIEMPRE atado a su observacion y a su horizonte.**
Cada fila trae `outcome_id`, `observation_id`, `direction` y `horizon_minutes`, y `horizon`
es un filtro explicito de la peticion. En la foto: **872 resultados en una hora**, con
`horizon = null` (sin filtrar).

*Que significa no cumplirlo:* mezclar horizontes en un mismo agregado. Es P3.4 y P1.14 a la
vez, y produce una expectativa que no es de ningun horizonte concreto.

**PENDIENTE · lo que NO puedo sostener desde aqui.** P5.1 exige que una media venga con su
error estandar al lado. **No he comprobado si esta ruta publica alguno**, porque los campos
de la coleccion no se derivan del AST y la foto solo trae una hora. Comando para cerrarlo:

```sh
harness/bin/api '/api/signals/outcomes?symbol=BTCUSDT&limit=5' | python3 -m json.tool | head -60
```


## SUPERFICIE

**Sin consumidor conocido**, medido: no aparece en `static/app.js`,
`static/index.html`, `harness/checks`, `tests`, `tools` ni `README.md`.

No prueba que este muerta -puede llamarla algo fuera del repo-, pero es la
forma del patron que en esta casa se ha repetido nueve veces.
