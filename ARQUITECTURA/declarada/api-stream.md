# DECLARADA · `GET /api/stream`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-stream.md`](../rutas/api-stream.md).
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


### Lo que promete, y por que su promesa NO es de forma

**No publica JSON: es SSE** (`StreamingResponse`, `app/api.py:2852`). El captador la recoge
como texto y la capa derivada la marca PENDIENTE en sus campos por esa razon — no por un
limite del analisis, sino porque **no hay un cuerpo unico que describir**.

**PROMESA · entrega los tres bloques vivos por evento, y el panel los usa para lo que no
puede esperar al refresco de 15 s.**
Medido en el consumidor (`static/app.js:1654`): cada mensaje trae `rows` (precio y delta 5 s
por simbolo), `scalp` (delta de futuros 5 s) y `books` (desequilibrio y spread). El panel los
pinta en las tres pildoras `live-price`, `live-delta` y `live-book`.

**PROMESA 2 · el estado de la conexion es visible.** `source.onopen` pone «Streaming activo»
y `source.onerror` pone «Reconectando stream» (`app.js:1654`). Un stream caido **no se pinta
como un stream quieto**, que es la version de P0.9 para un canal continuo.

*Que significa no cumplirlo:* que el panel siguiera mostrando la ultima pildora recibida sin
marcar que la conexion se cayo. Entonces un precio de hace diez minutos y uno de hace un
segundo serian indistinguibles en pantalla.

**PENDIENTE · lo que NO puedo sostener y no es cuestion de tiempo.** No se **con que cadencia
emite** ni si cada evento lleva su propio instante. Una foto no sirve: hace falta escuchar el
stream un rato, y ese instrumento no existe.

```sh
# lo que haria falta, y no lo tengo: escuchar N segundos y contar eventos con su marca
curl -N --netrc-file "$NETRC" -k "$API_PROD/api/stream" | head -c 2000
```


## SUPERFICIE

**Superficie de producto**, medido.

- **checks**: `harness/checks/K20-cincoxx.sh:126`
- **panel**: `static/app.js:1654`
- **readme**: `README.md:412`
