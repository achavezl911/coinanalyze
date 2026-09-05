# DECLARADA · `GET /api/delta-profile`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-delta-profile.md`](../rutas/api-delta-profile.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

**NINGUNA de las 66 preguntas de la bateria la nombra.**

Medido sobre `entregas/20260904-2100-bateria-trader.md`: ninguna fila de las 54 (P0.1..P5.9) ni de las 12
(S1..S12) cita esta ruta en su columna de destino ni en la de medicion.

Eso NO significa que no sirva: significa que **el trader no le ha formulado**
**una pregunta**. Si es un instrumento interno, lo normal es que no la haya.
Si es superficie de producto y no contesta ninguna pregunta, merece mirarse.

## VENTANA

Familia **2** de K43 — coverage de su propia serie.

Derivado de su firma: pide ['days', 'interval']: coverage de su propia serie.

**MEDIDO en la foto de produccion** (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z, arco 37 387 ms).

El AST no le derivo ninguna clave temporal, pero **si publica marca de tiempo en el**
**cuerpo**. Son cosas distintas y aqui se separan: lo primero es un limite del
analisis estatico, lo segundo una afirmacion sobre el producto.

Claves de **primer nivel** — la respuesta declara su propio instante o periodo:

- `from` (nombre)
- `to` (nombre)

Claves **anidadas** (3), dentro de filas o bloques:

- `coverage.served_window` (nombre)
- `coverage.served_window.window_end` (nombre)
- `coverage.served_window.window_start` (nombre)

<sub>Medido leyendo el cuerpo de la respuesta en la foto, no supuesto. 5 claves temporales en total.</sub>

## PROMESA


### Lo que promete

**PROMESA 1 · separa lo PEDIDO de lo SERVIDO, con los dos en el cuerpo.**
En la foto: `requested_days = 90` junto a `from = "2026-06-07"`, `to = "2026-09-04"`,
`bars = 539` e `interval = "4hour"`. Se pidieron 90 dias y se sirvieron **89**, y la ruta lo
dice sin que haya que restar fechas.

Es la forma mas limpia de **P0.4** —*"¿que antigüedad tiene el dato mas viejo que entra en
este calculo?"*— de las 68: no publica un `coverage_pct`, publica los dos bordes y el
recuento de barras.

**PROMESA 2 · `available` separa "no hay perfil" de "no se pudo calcular".** Es **P0.5**.

**PENDIENTE · una sospecha que NO puedo cerrar y que no es mia.** El operador midio que esta
ruta es una de **tres** cuyas marcas temporales salieron **identicas en las dos capturas de
su foto** (junto a `/api/baselines` y `/api/price-barriers`). 34 s de arco **no prueban
congelacion** —un perfil de 90 dias no tiene por que moverse en 34 s—, asi que es una
candidata, no un hallazgo. Se cierra con dos capturas separadas por horas:

```sh
harness/bin/api '/api/delta-profile?symbol=BTCUSDT_PERP.A' > /tmp/dp1.json
# esperar 2 h
harness/bin/api '/api/delta-profile?symbol=BTCUSDT_PERP.A' > /tmp/dp2.json
diff <(python3 -c "import json;print(json.load(open('/tmp/dp1.json'))['to'])") \
     <(python3 -c "import json;print(json.load(open('/tmp/dp2.json'))['to'])")
```

Si `to` no cambia en dos horas de mercado abierto, es K.


## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1137`
- **readme**: `README.md:111`
- **tests**: `tests/test_dashboard_presentation.py:122`
