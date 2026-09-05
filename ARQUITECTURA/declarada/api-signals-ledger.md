# DECLARADA · `GET /api/signals/ledger`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-signals-ledger.md`](../rutas/api-signals-ledger.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **4** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P1.11** — ¿Esta señal ya estaba antes de que yo mirara, o nació al mirar?  
  <sub>`entregas/20260904-2100-bateria-trader.md:123`</sub>
- **P1.6** — ¿La señal de ahora es la misma que hace 5 minutos?  
  <sub>`entregas/20260904-2100-bateria-trader.md:118`</sub>
- **P1.7** — ¿Cuántas señales de este tipo ha habido en 30 días?  
  <sub>`entregas/20260904-2100-bateria-trader.md:119`</sub>
- **S1** — ¿Cuántas señales LARGO y cuántas CORTO en 30 días?  
  <sub>`entregas/20260904-2100-bateria-trader.md:318`</sub>

## VENTANA

Familia **3** de K43 — su propio as_of bajo demanda.

Derivado de su firma: pide ['since']: el operador elige el momento.

Declara su ventana con estas claves, derivadas de los campos que publica:

- `since` — literal en app/api.py:2145
- `until` — literal en app/api.py:2146

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

**PROMESA 4 · un evento del ledger existe ANTES de que se pregunte por el.**
Es la respuesta a **P1.11** ("¿esta senal ya estaba antes de que yo mirara, o nacio al
mirar?"): lee `signal_observation` (tabla, no calculo al vuelo) y cada fila trae
`observation_id`, `observed_at` y `observed_minute`. En la foto: **145 observaciones en una
hora** para BTCUSDT_PERP.A.

*Que significa no cumplirlo:* si las filas se generaran al consultar, no habria tasa base y
P1.7 ("¿cuantas senales de este tipo en 30 dias?") no tendria respuesta posible. Lo vigila
`harness/checks/K21-ledger-de-senales.sh:32`.


## SUPERFICIE

**El recuento vive en la ficha derivada**, que se regenera: [`rutas/api-signals-ledger.md`](../rutas/api-signals-ledger.md), seccion *Superficie*. Aqui NO se copia el numero.

La primera version de estas fichas lo copiaba y envejecio el mismo dia: el andamio escribio "sin consumidor conocido" cuando el detector no veia `RUTA=/api/x` ni `$VAR/api/x`, y al arreglarlo la prosa quedo mintiendo mientras el JSON del mismo commit decia otra cosa. K88 lo caza ahora (brazo 5), y esto quita la causa.
