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

### Las tres de niveles comparten una promesa, y es la de la ventana

**PROMESA · la ventana del calculo es un PARAMETRO con limites declarados, no una constante
escondida.** Y los limites estan en la firma, validados por FastAPI:

```
/api/range/validate   days: ge=40 le=730 (def 180) · end_days_ago: ge=0 le=690 · start_date · end_date
/api/zone/analysis    days: ge=7  le=365 (def 365)
/api/level/breakout   direction: 'up' por defecto
```

Es **P2.7** —*"¿el nivel viene de mi marco o de otro?"*— resuelto por el lado del que
pregunta: el consumidor **elige** la ventana y la ruta la valida en vez de aceptarla y
recortarla en silencio. Un rango validado sobre 40 dias y otro sobre 730 son cosas
distintas, y aqui no se pueden confundir porque la ventana viaja en la peticion.

*Que significa no cumplirlo:* que `days` se aceptara fuera de rango y se recortara sin
avisar. Entonces dos consumidores que pidieran 900 dias recibirian 730 creyendo tener 900.

**NO estan en la foto de produccion**, y el motivo esta medido: el captador las omitio
porque exigen un parametro de precio (`low`/`high`/`level`) que **no se puede inventar**
(`entregas/20260904-foto-prod-1.json`, seccion `omitidas`). Es la decision correcta del
captador — inventar un precio habria producido una medida falsa con aspecto de buena.

### Lo propio de esta ruta

**PROMESA · el LADO es un parametro, no una deduccion.** `direction` con `'up'` por defecto
(`app/api.py:1702`). Que el consumidor tenga que decir si pregunta por una ruptura al alza o
a la baja es lo que permite contestar **S7** con simetria: *"un LARGO teme la cascada por
DEBAJO, un CORTO por ENCIMA"*.

*Que significa no cumplirlo:* que `direction` se ignorara y la respuesta fuera la misma para
los dos lados. Seria **S9** —*"si invierto la pregunta, ¿la magnitud es la misma con el signo
cambiado?"*— fallando en la forma mas barata de detectar: **la misma respuesta para dos
preguntas opuestas**.

**PENDIENTE · y esta es comprobable con DOS peticiones, no con una.** Es el control que S9
pide, y va escrito con los dos lados:

```sh
harness/bin/api '/api/level/breakout?symbol=BTCUSDT_PERP.A&level=80000&direction=up'   > /tmp/b_up.json
harness/bin/api '/api/level/breakout?symbol=BTCUSDT_PERP.A&level=80000&direction=down' > /tmp/b_down.json
diff /tmp/b_up.json /tmp/b_down.json | head -20
```

**Si el diff sale vacio, es K por S9**: la ruta acepta `direction` y no lo usa.
Y hay que imprimir los BYTES de las dos: dos respuestas de error tambien salen identicas, y
eso seria un falso K — la leccion del `symbol=BTCUSDT` de esta misma ronda.


## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:2765`
