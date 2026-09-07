# DECLARADA · `GET /api/reference-levels`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-reference-levels.md`](../rutas/api-reference-levels.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **3** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P2.1** — ¿Dónde está el soporte más cercano por debajo?  
  <sub>`entregas/20260904-2100-bateria-trader.md:137`</sub>
- **P2.2** — ¿Cuántas veces ese nivel ha aguantado?  
  <sub>`entregas/20260904-2100-bateria-trader.md:138`</sub>
- **P2.7** — ¿El nivel viene de mi marco o de otro?  
  <sub>`entregas/20260904-2100-bateria-trader.md:143`</sub>

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

Declara su ventana con estas claves, derivadas de los campos que publica:

- `current_day` — literal en app/scalp_logic.py:3237
- `previous_day` — literal en app/scalp_logic.py:3236

## PROMESA


### YA LA USA LA MESA, aunque no por esta puerta (2026-09-07)

Hasta el 2026-09-07 el censo no encontraba ni una llamada ni una mencion: era una de las seis
rutas del sistema a las que no apuntaba nadie. Y sin embargo contestaba, y sus catorce niveles
eran CORRECTOS
-recalculados valor por valor desde `ohlcv` 1min-. El hueco no estaba en la ruta: estaba entre la
ruta y la mesa, que daba la invalidacion en prosa y ningun numero.

Hoy el censo da **cero llamadas y una mencion**, y la diferencia es deliberada: los niveles llegan
a la tarjeta de decision **dentro de `/api/desk/state`** (`components.reference_levels`), no
pidiendo esta ruta. La razon es que la tarjeta se alimenta de un solo snapshot para que todos sus
componentes compartan el mismo `computed_at`; un nivel pedido aparte traeria su propio instante y
la tarjeta pintaria dos relojes como si fueran uno.

**Esta ruta sigue existiendo y sirve lo mismo**, para quien la quiera suelta. Que nadie la LLAME
ya no es señal de que este muerta: su calculo se usa en cada refresco de la Mesa.

### Lo que promete

**PROMESA · cada nivel declara SU MARCO temporal.**
En la foto: `previous_day` y `current_day` (con `high`/`low`/`close`/`open`), `opens` por
`daily`/`weekly`/`monthly`, `sessions_today_utc` por `asia`/`london`/`new_york`, y
`note = "niveles desde ohlcv 1min (retencion…)"`.

Es **P2.7** -"¿el nivel viene de mi marco o de otro?"-: un soporte diario no invalida un
scalp. Aqui el marco no hay que deducirlo, esta en el nombre de la clave.

**INCUMPLE parcialmente P2.1**, y esta medido. La bateria pide que *"cada nivel declare SU
procedencia"* porque el frontend maneja **seis fuentes distintas de niveles**. Esta ruta
declara el MARCO (`daily`, `weekly`, `asia`…) pero **no la FUENTE**: los seis grupos salen
todos de `ohlcv` -la unica tabla que lee- y no hay campo que distinga un nivel de sesion de
un open semanal mas alla de donde esta colgado.

*Que significa:* dos niveles del mismo precio en grupos distintos no se pueden deduplicar.
No lo abro como K porque el criterio -¿cuantos niveles duplicados hacen falta para que
importe?- no lo puedo fijar sin una medida sobre varios simbolos.


## SUPERFICIE

**El recuento vive en la ficha derivada**, que se regenera: [`rutas/api-reference-levels.md`](../rutas/api-reference-levels.md), seccion *Superficie*. Aqui NO se copia el numero.

La primera version de estas fichas lo copiaba y envejecio el mismo dia: el andamio escribio "sin consumidor conocido" cuando el detector no veia `RUTA=/api/x` ni `$VAR/api/x`, y al arreglarlo la prosa quedo mintiendo mientras el JSON del mismo commit decia otra cosa. K88 lo caza ahora (brazo 5), y esto quita la causa.

Lo que si aporta esta capa: **no tener ningun rastro no prueba que este muerta** -puede llamarla algo fuera del repo, o una IA por su nombre-, pero es la forma del patron que en esta casa se ha repetido nueve veces, y por eso merece una mirada.
