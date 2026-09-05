# DECLARADA · `GET /api/liquidation-map`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-liquidation-map.md`](../rutas/api-liquidation-map.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **1** de las 66 preguntas de la bateria
(`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P2.4** — ¿Donde hay liquidaciones que puedan acelerar en mi contra?
  <sub>`entregas/20260904-2100-bateria-trader.md:141`</sub>

Y la bateria le pone la advertencia mas dura de las 66 (misma linea):

> `/api/liquidation-map` es `historical_realized_density_3h` — dice donde YA se ejecutaron,
> **NO donde reventarian posiciones abiertas**. Si la pantalla lo etiqueta como mapa de
> liquidaciones al estilo Coinglass, esta mintiendo sobre la naturaleza del dato.

Tambien la roza **S7** (`:318`): "¿las liquidaciones que me amenazan son las de mi lado?".

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide `symbol` (`app/api.py:1608`). No admite `as_of` ni ventana:
no se le puede pedir un instante pasado.

Declara su ventana con **cinco** claves, y es de las pocas rutas que la declara entera:

- `as_of` · `window_start` · `window_end` · `window_minutes` · `window_notional`

O sea que **publica su propio instante y los dos bordes de su ventana**. Eso la pone entre
las rutas que mejor cumplen K43, no entre las que lo evaden.

## PROMESA

### Lo que promete, y esta en el codigo

`"type": "historical_realized_density_3h"` (`app/scalp_logic.py:3479`) — el campo `type`
va **dentro de la respuesta**. La ruta declara, en su propio cuerpo, que lo que publica es
**densidad historica de liquidaciones YA EJECUTADAS en 3 horas**, no un mapa de posiciones
abiertas en riesgo.

El sistema lo tiene escrito en un segundo sitio, para la IA que lo consume:

> "Liquidaciones = feed de EVENTOS. `liquidation_map` es densidad HISTORICA ya ejecutada
> (type `historical_realized_density_3h`): un cluster puede quedar arriba o abajo del
> precio actual. Un lag alto o `long_liq`/`short_liq`=0 con
> `data_quality.collectors.ws.status="ok"` = mercado en calma, NO feed caido ni dato
> faltante."
> <sub>`app/analysis_prompt.py:12`</sub>

**Promesa declarada:** *publica donde se ejecutaron liquidaciones en las ultimas 3 horas,
con su ventana y su instante explicitos, y declara en el propio cuerpo que eso es lo que
es. No promete decir donde hay posiciones en riesgo, y un cero suyo con el colector `ok`
significa calma, no falta de dato.*

**Que significa no cumplirlo:** que `type` dejara de viajar en la respuesta, o que
apareciera un consumidor que lo pintara como mapa de posiciones abiertas. Lo primero lo
caza K88 por los campos; lo segundo no lo caza nadie hoy.

### ¿Lo cumple? SI, y el riesgo esta en otro sitio

La ruta **cumple**: dice lo que es, en su propio cuerpo, con su ventana y su `as_of`. El
riesgo que la bateria senala -"si la pantalla lo etiqueta al estilo Coinglass"- **no se
materializa hoy**, y esta medido:

```sh
$ grep -n "liquidation-map\|liquidationMap\|liquidation_map" static/app.js static/index.html
   (sin resultados)
```

**El panel no la consume en absoluto**, asi que hoy no hay ninguna pantalla que pueda
etiquetarla mal. El aviso de la bateria sigue siendo bueno como **condicion futura**: el
dia que alguien la enchufe al panel, el rotulo tiene que decir "ya ejecutadas", no
"posiciones en riesgo".

## SUPERFICIE

**Instrumento interno**, medido.

- **checks**: `harness/checks/K42-mapa-liquidaciones-cuadra.sh:43`

No aparece en `static/app.js`, `static/index.html`, `tests`, `tools` ni `README.md`. Su
unico consumidor es el check que la vigila. Su dato **si** llega al producto por otras
vias: lee `liquidations_realtime`, que leen 14 rutas.
