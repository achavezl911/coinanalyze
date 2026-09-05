# DECLARADA · `GET /api/scalp/summary`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-scalp-summary.md`](../rutas/api-scalp-summary.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

**Ninguna de las 66 preguntas de la bateria la nombra**
(`entregas/20260904-2100-bateria-trader.md`; medido con el mapeo de las 54 P + 12 S).

Y eso es un hallazgo, no un hueco del mapeo. La pregunta que **de hecho** contesta es la de
la tarjeta de corto del panel -"¿de que lado estoy en el intradia?"-, y la mas cercana en
la bateria es **P1.6 · "¿La senal de ahora es la misma que hace 5 minutos?"**
(`entregas/20260904-2100-bateria-trader.md:121`), que la bateria dirige a
`/api/signals/ledger`, no aqui. La seccion PROMESA de abajo es la que contesta P1.6 para
esta ruta, y la respuesta medida es que **no**.

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide `symbol` (`app/api.py:1083`). No admite `as_of`, ni
`limit`, ni `days`: **no se le puede pedir un instante pasado**. Lo que publica es el
estado en el momento en que se construyo la foto, y nada mas.

Claves temporales entre los campos que publica: **ninguna derivable** — la respuesta la
compone `compute_scalp_summary` y el generador no resuelve sus campos estaticamente. La
foto de produccion es la que lo decide: `entregas/20260904-foto-prod-1.json`.

**PENDIENTE**: con que clave declara su instante. No se ha leido en la foto.

## PROMESA

### Lo que la ruta promete sobre persistencia: NADA. Y esta medido.

`scalp_bias_label` (`app/scalp_logic.py:292-313`) es una **funcion pura de los dos scores
del instante**. Su decision entera:

```
edge = abs(long_score - short_score)
if edge < 12:            -> "No Trade", baja      (scalp_logic.py:302)
long_score >= 70         -> "Long Momentum", alta (:305)
long_score >= 58         -> "Long Pullback", media(:307)
short_score >= 70/58     -> simetrico             (:310, :312)
```

Los dos scores **suman 100** -`score_component` devuelve `bull` y `bear=1-bull`
(`:319-324`) y los pesos se renormalizan por cobertura (`:818-821`)-, asi que
`long_score >= 58` equivale a `short_score <= 42`: es el **umbral 50±8**. `edge < 12` deja
la banda 44..56 como "No Trade".

**No hay ningun mecanismo de duracion.** Censo completo, sin `head`:

```sh
$ grep -cniE "persist|parpade|flicker|hysteresis|histeresis|debounce|min_duration|dwell|sticky|cooldown|estabil" app/scalp_logic.py
1
$ grep -niE "…mismo patron…" app/scalp_logic.py
211:    # ponytail: la puerta es una ratio; ubicacion estructural y persistencia las cubre
```

**Una sola coincidencia en 6170 lineas, y es un comentario** que delega la persistencia en
`passive_flow`, no en el estado. Ni histeresis, ni umbral de duracion minima, ni cooldown,
ni memoria del estado anterior. Y el colector recalcula cada **10 segundos**
(`SCALP_SIGNAL_INTERVAL_SECONDS = 10`, `app/config.py:188`).

**Promesa declarada, entonces:** *esta ruta publica el lado del intradia en el instante de
la foto, y no promete que ese lado siga ahi en el siguiente instante.* Que no lo cumpla no
significa nada, porque no lo promete.

### Pero el panel SI promete un horizonte, y ahi esta el K

La tarjeta de corto se rotula **`time: '1–15 minutos'`** (`static/app.js:1435`) y su lado
sale de `scalp.state` (`app.js:1370`). Ese `scalp` **no viene de esta ruta**: viene de
`dashboard.scalp` (`app.js:1362`), cargado desde `/api/dashboard/state` (`app.js:1491`).
Pero es **el mismo calculo**: las dos rutas llaman a `app.scalp_logic.compute_scalp_summary`
(24 funciones comunes en sus cierres, ver la capa derivada).

Medido en 140 sobre **33 995 minutos periodicos** de `signal_observation`, 25 dias
(`entregas/20260904-2230-bateria-r5-140.md:136-155`):

```
                episodios  minutos  medio  mediano  p90  maximo
accionable         7422     12947    1.7      1       3     17
no accionable      7423     21048    2.8      2       6     85
```

**~290 cambios de accionable a no accionable al dia; uno cada cinco minutos.**

### ¿La mediana de 1 minuto cumple o incumple? INCUMPLE. Con una precision que importa.

**No incumple por la mediana.** 1 minuto esta *dentro* del rango literal "1–15", y decir
"la mediana de 1 lo incumple" seria un argumento tramposo: el rango incluye el 1.

Incumple por el otro extremo: **el p90 es 3 minutos, un quinto del horizonte declarado**, y
el maximo en 25 dias es 17. Un rotulo que anuncia "1–15 minutos" describe un horizonte
sobre el que se puede operar; lo que se publica **no llega a 3 minutos el 90 % de las
veces**, y el sistema que lo produce no tiene memoria: recalcula desde cero cada 10 s. La
duracion que se observa no es una propiedad disenada, es **el tiempo que tarda el ruido en
cruzar la banda 44..56**.

**El defecto no es de la ruta: es del par ruta + rotulo.** La ruta es honesta -publica un
instante y no promete mas-; el panel promete un horizonte que el calculo no sostiene.

### K · criterio ejecutable

> **K90 · la senal de corto no persiste lo que su rotulo declara.**
>
> **ROJO** si, sobre los episodios accionables de `signal_observation` con `is_periodic`
> de los ultimos **30 dias**, agrupados **por simbolo**, el **p90 de duracion en minutos es
> menor que 8** — el punto medio del rango rotulado "1–15".
>
> El umbral sale **del propio rotulo**, no de una opinion sobre trading: si el producto
> anuncia hasta 15 minutos, que el 90 % no alcance ni la mitad del rango es incumplimiento
> medible. Un episodio es una racha de minutos periodicos seguidos con el mismo
> `actionable`.
>
> **Medido el 2026-09-04 sobre 7422 episodios / 25 dias: p90 = 3. ROJO.**
>
> Control obligatorio en la misma consulta: el mismo p90 para los episodios **no**
> accionables (medido: 6). Si los dos salieran igual de cortos, el sujeto no seria la senal
> sino el muestreo, y el hallazgo no se sostendria.
>
> **Se cierra de dos maneras, y las dos valen:** dando persistencia al estado (histeresis o
> duracion minima en `scalp_bias_label`) o **cambiando el rotulo** para que diga lo que el
> calculo hace. Lo que no vale es dejar el rotulo prometiendo 15 minutos.

## SUPERFICIE

**Instrumento interno**, medido. No aparece en `static/app.js` ni en `static/index.html`:
el panel menciona 37 rutas distintas y esta no esta entre ellas.

- **checks**: `harness/checks/K62-una-version-dos-reglas.sh:271`

Su calculo, en cambio, **si es superficie de producto**: `compute_scalp_summary` alimenta
la tarjeta de corto a traves de `/api/dashboard/state`. O sea que esta ruta es una **puerta
de instrumentacion sobre logica de producto** — util para medirla sin pasar por el panel, y
es exactamente lo que la hace el sitio correcto donde declarar el K de arriba.
