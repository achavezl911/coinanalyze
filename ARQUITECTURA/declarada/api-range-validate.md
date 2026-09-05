# DECLARADA · `GET /api/range/validate`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-range-validate.md`](../rutas/api-range-validate.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **1** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P2.3** — ¿Es un rango válido o me lo estoy inventando?  
  <sub>`entregas/20260904-2100-bateria-trader.md:139`</sub>

## VENTANA

Familia **2** de K43 — coverage de su propia serie.

Derivado de su firma: pide ['days']: coverage de su propia serie.

Declara su ventana con estas claves, derivadas de los campos que publica:

- `from` — literal en app/scalp_logic.py:1599
- `to` — literal en app/scalp_logic.py:1600
- `window_days` — literal en app/scalp_logic.py:1598

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

**PROMESA · acepta la ventana de DOS formas y las dos son explicitas.**
Por desplazamiento (`days` + `end_days_ago`) o por fechas (`start_date` + `end_date`). No
hay una tercera forma implicita: si no se pide nada, son 180 dias terminando hoy, y el
defecto esta en la firma (`app/api.py:1668`), no en un comentario.

Contesta **P2.3** —*"¿es un rango valido o me lo estoy inventando?"*— y el criterio de la
bateria es *"re-derivar los bordes del rango desde OHLCV"*, que solo se puede hacer si la
ventana es conocida. Por eso la ventana explicita **es** la promesa.

**PENDIENTE · no he leido su cuerpo.** No se que publica como veredicto ni si declara cuantos
toques respaldan el rango. La peticion, con el simbolo real **comprobado** y un precio del
entorno de la foto (79 665 USD el 2026-09-04T22:33Z):

```sh
harness/bin/api '/api/range/validate?symbol=BTCUSDT_PERP.A&low=78000&high=81000' \
  | python3 -m json.tool | head -30
```

Lo que hay que mirar: **si el veredicto viene con el numero de toques de cada borde**. Sin
eso, "rango valido" es una opinion (P2.2).


## SUPERFICIE

**Superficie de producto**, medido.

- **checks**: `harness/checks/K76-la-ventana-que-pides.sh:97`
- **panel**: `static/app.js:2890`
