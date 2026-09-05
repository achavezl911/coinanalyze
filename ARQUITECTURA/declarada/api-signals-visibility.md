# DECLARADA · `GET /api/signals/visibility`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-signals-visibility.md`](../rutas/api-signals-visibility.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **2** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P5.4** — ¿Esto se midió antes o después de conocer el resultado?  
  <sub>`entregas/20260904-2100-bateria-trader.md:188`</sub>
- **P5.5** — ¿Qué versión de la lógica produjo estos resultados?  
  <sub>`entregas/20260904-2100-bateria-trader.md:189`</sub>

## VENTANA

Familia **3** de K43 — su propio as_of bajo demanda.

Derivado de su firma: pide ['since']: el operador elige el momento.

Declara su ventana con estas claves, derivadas de los campos que publica:

- `since` — literal en app/api.py:2499
- `until` — literal en app/api.py:2500

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

**PROMESA 4 · separa "evaluado" de "no evaluable", y no los suma.**
`status` solo admite dos valores -`422 · "status tiene que ser evaluado o not_evaluable"`,
`app/api.py:2454`- y cada certificado trae `final_visibility_id`, `horizon_minutes` y
`visibility_version`. En la foto: **850 certificados en una hora** con `status = null`.

*Que significa no cumplirlo:* contar un "no evaluable" como un fallo, o al reves. Es
**P5.4** -"¿esto se midio antes o despues de conocer el resultado?"- y es la pregunta que
separa evidencia de narrativa: sin el certificado, una tasa de acierto se puede construir
eligiendo que casos entran.
Lo vigila `harness/checks/K25-visibilidad-de-lo-final.sh:110`.


## SUPERFICIE

**Sin consumidor conocido**, medido: no aparece en `static/app.js`,
`static/index.html`, `harness/checks`, `tests`, `tools` ni `README.md`.

No prueba que este muerta -puede llamarla algo fuera del repo-, pero es la
forma del patron que en esta casa se ha repetido nueve veces.
