# DECLARADA · `GET /api/dashboard/state`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-dashboard-state.md`](../rutas/api-dashboard-state.md).
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

**MEDIDO en la foto de produccion** (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z, arco 37 387 ms).

El AST no le derivo ninguna clave temporal, pero **si publica marca de tiempo en el**
**cuerpo**. Son cosas distintas y aqui se separan: lo primero es un limite del
analisis estatico, lo segundo una afirmacion sobre el producto.

Claves **anidadas** (56), dentro de filas o bloques:

- `barriers.active_zone.age_days` (nombre)
- `barriers.active_zone.last_touch` (valor ISO)
- `barriers.live_pressure.absorption_15m` (sufijo de periodo)
- `barriers.live_pressure.delta_ratio_15m` (sufijo de periodo)
- `barriers.live_pressure.volume_multiple_15m` (sufijo de periodo)
- `barriers.nearest_resistance.age_days` (nombre)
- `barriers.nearest_resistance.last_touch` (valor ISO)
- `barriers.nearest_support.age_days` (nombre)
- _… y 48 mas_

**Y NO tiene ninguna de primer nivel.** O sea: la respuesta fecha sus FILAS pero
no se fecha a SI MISMA. Para K43 eso importa — un consumidor que quiera saber de
cuando es la foto entera tiene que deducirlo de la fila mas reciente, y eso es
adivinar. **Candidata a familia 1 con defecto declarado.**

<sub>Medido leyendo el cuerpo de la respuesta en la foto, no supuesto. 56 claves temporales en total.</sub>

## PROMESA


### Lo que promete, y lo que NO · aqui esta el peor caso de P0.1

Medido en la foto (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z):

```
/api/dashboard/state   12 512 B
  instante de RAIZ ....................... NINGUNO
  bloques de primer nivel ................ 6   (snapshot, scalp, setup, cvd_swing,
                                                barriers, market_memory)
  de esos, CON su propio instante ........ 1   (snapshot.ts)
  instantes DISTINTOS en el cuerpo ....... 5
```

**PROMESA · agrupa en una sola peticion los seis bloques que pinta la mesa.** Es su razon de
ser y la cumple: el panel la llama una vez (`static/app.js:1491`) en vez de seis.

### Y lo que NO promete, que es lo que importa

**NO publica ningun instante de raiz, y cinco de sus seis bloques tampoco.** Solo
`snapshot.ts` se fecha. `scalp`, `setup`, `cvd_swing`, `barriers` y `market_memory` llegan
**sin decir de cuando son**, y hay **5 instantes distintos** dentro del cuerpo.

**Esto es P0.1 en su forma mas cara, y por dos razones:**

1. **Es la ruta que alimenta el panel.** `app.js:1491` la carga y de ahi salen la tarjeta de
   corto (`dashboard.scalp`, `app.js:1362`) y las barreras.
2. **Es el otro extremo de K90.** El rotulo "1–15 minutos" cuelga de `scalp`, que es
   **precisamente uno de los cinco bloques sin fechar**. Un consumidor no puede saber si el
   `scalp.state` que esta viendo es de hace 2 segundos o de hace 4 minutos, **y la ruta no
   se lo dice**.

**PROMESA declarada, entonces:** *entrega seis bloques en una peticion y **no promete nada
sobre la frescura de cinco de ellos**.* No es que incumpla: es que no promete, y el panel
pinta como si prometiera.

**K candidata, con criterio ejecutable y control:**

> ROJO si `/api/dashboard/state` no publica un instante de raiz **o** si algun bloque de
> primer nivel llega sin marca temporal.
> **Medido hoy: sin raiz, 5 de 6 bloques sin marca.**
> Control en la misma medida: `/api/ai/context`, que **si** publica raiz y fecha 21 de 39
> bloques — o sea que **el sistema sabe hacerlo** y esta ruta no lo hace.

El control es lo que convierte esto de "seria bonito" en un defecto: no es una limitacion
del framework ni del dato, es una eleccion de esta ruta.

**PROMESA · `signal_base_rate` · la tasa base de la señal, con su ALCANCE pegado.**
Declarada el 2026-09-06 en la misma vuelta que la escribe. Es el primer bloque de esta ruta
que existe **para que un trader lo lea**, no para que otro proceso lo consuma.

*Que publica:* `ventaja_bruta_pct`, `ventaja_neta_pct`, `t_neta`, `coste_entrada_pct`,
`coste_entrada_por_obs_pct`, `observaciones`, `n_efectiva`, `pares_bloque_lado`,
`arco_desde`/`arco_hasta`, `dias_de_arco`, `horizonte_min`, `lectura`, y un objeto `alcance`
con `percentil_de_la_ventana`, `ventanas_comparadas`, `mediana_historica_pct` y
`ventanas_negativas`.

*Y una precision que costo una correccion del operador el 2026-09-06:* **`n_efectiva` son
BLOQUES DE TIEMPO DISTINTOS**, no pares (bloque, lado). Los dos lados del mismo bloque de 60
minutos leen el **mismo tramo de mercado**: no son dos muestras independientes de tiempo.
Publicar los pares como n efectiva **doblaba la muestra** en la unica cifra cuyo proposito es
ser honesta sobre el tamaño de muestra —P5.2 «¿sobre cuantas operaciones se calcula?» y P5.3
«¿la muestra solapa ventanas?»—. Medido: **604 bloques contra 1 191 pares**, y el `t` pasa de
0.124 a 0.049. Por eso `pares_bloque_lado` viaja tambien: para que la distincion se pueda
auditar desde fuera sin creerse la etiqueta.

*Los DOS costes de entrada, y por que hay dos:* `coste_entrada_pct` va ponderado **por
bloque**, igual que la ventaja, y es el unico que se puede comparar con ella —dos medias
ponderadas de forma distinta no decomponen nada—. `coste_entrada_por_obs_pct` va por
**observacion**, que es lo que le cuesta a quien opera, porque cada entrada es una
observacion y no un bloque. Medido: **0.0531 frente a 0.0479**; la diferencia es ponderacion,
no señal.

*Que promete exactamente, y es lo que la separa de un numero bonito:*

1. **La cifra es reproducible.** Publica el arco que MIDIO —`arco_desde`/`arco_hasta`, que
   son el minimo y el maximo reales de `signal_observation` dentro de la ventana pedida, no
   la ventana pedida— para que cualquiera pueda repetir la consulta y salir en el mismo
   sitio. `harness/checks/K95-la-tasa-base-que-se-pinta.sh` hace justo eso.
2. **La lectura es sobre EJECUCION, no sobre acierto.** Medido en la campana de S3 sobre los
   tres simbolos, 42 celdas y su placebo: la señal **no anticipa nada, ni a favor ni en
   contra**, y **entra al peor precio de su propia ventana**. Por eso `lectura` dice «el
   coste de entrada se come la ventaja» y **no** «el sistema pierde». Son afirmaciones
   distintas y llevan a arreglos distintos.
3. **El alcance viaja como CAMPO.** La unica ventana en la que la señal existe son ~27 dias
   que caen en el **percentil 95.9** de 737 ventanas comparables, de las que **334 fueron
   negativas**. Una tasa base medida en el mejor 5 % de dos anos tiene que decir que lo es.
   Por eso `alcance` es un objeto y no una frase: una nota al pie se puede recortar al
   pintarla, un campo no.
4. **Cero bloques no es una ventaja de cero.** Sin muestra, `available: false` con su
   `motivo`. Es la misma regla de tres estados del arnes, aplicada a un payload.

*Que significa no cumplirlo:* que la cifra publicada difiera de la que sale de
`signal_outcome` sobre el arco que ella misma declara —eso lo caza K95—, o que `alcance`
desaparezca del payload y la tasa base quede sin contexto.

*Lo que NO promete:* no promete que la ventaja sea estable fuera de ese mes. No se puede
saber: `signal_observation` empieza el 2026-08-10 y no hay señal antes.


## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1491`
- **readme**: `README.md:195`, `README.md:488`, `README.md:502`
- **tests**: `tests/test_metrics_endpoint.py:162`, `tests/test_v121_hardening.py:27`, `tests/test_v150_desk_snapshot.py:126`
