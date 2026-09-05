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

**PROMESA · su ventana llega hasta un año y su minimo son 7 dias** (`days: ge=7 le=365`).
El rango de validacion mas ancho de las tres, y es coherente con lo que contesta: **P2.6**
—*"si me saltan el stop, ¿es estructura o es una mecha?"*— necesita historia larga para
distinguir una cosa de la otra.

**PENDIENTE · no he leido su cuerpo.** Peticion con parametros comprobados:

```sh
harness/bin/api '/api/zone/analysis?symbol=BTCUSDT_PERP.A&low=78000&high=81000' \
  | python3 -m json.tool | head -30
```

Lo que hay que mirar: **si distingue el tiempo DENTRO de la zona del numero de VISITAS**.
Una zona tocada 20 veces en un dia y otra tocada 20 veces en tres meses son estructuras
distintas, y la bateria lo pide en P2.2 como tasa base del nivel.


## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:2603`
