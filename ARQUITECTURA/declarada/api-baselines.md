# DECLARADA · `GET /api/baselines`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-baselines.md`](../rutas/api-baselines.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **1** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P5.8** — ¿Cuál es la línea base contra la que comparo?  
  <sub>`entregas/20260904-2100-bateria-trader.md:192`</sub>

## VENTANA

**PENDIENTE de familia.** parametros ['metric', 'symbol']: no encaja en 1/2/3 sin leerla

**MEDIDO en la foto de produccion** (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z, arco 37 387 ms).

El AST no le derivo ninguna clave temporal, pero **si publica marca de tiempo en el**
**cuerpo**. Son cosas distintas y aqui se separan: lo primero es un limite del
analisis estatico, lo segundo una afirmacion sobre el producto.

Claves **anidadas** (40), dentro de filas o bloques:

- `windows.15m.sample_end` (nombre)
- `windows.15m.sample_start` (nombre)
- `windows.15m.window_label` (nombre)
- `windows.15m.window_seconds` (nombre)
- `windows.18m.sample_end` (nombre)
- `windows.18m.sample_start` (nombre)
- `windows.18m.window_label` (nombre)
- `windows.18m.window_seconds` (nombre)
- _… y 32 mas_

**Y NO tiene ninguna de primer nivel.** O sea: la respuesta fecha sus FILAS pero
no se fecha a SI MISMA. Para K43 eso importa — un consumidor que quiera saber de
cuando es la foto entera tiene que deducirlo de la fila mas reciente, y eso es
adivinar. **Candidata a familia 1 con defecto declarado.**

<sub>Medido leyendo el cuerpo de la respuesta en la foto, no supuesto. 40 claves temporales en total.</sub>

## PROMESA


### NADIE LA LLAMA, y esta medido

Censo sobre `static/app.js`, `static/index.html`, `harness/checks`, `tests`, `tools` y
`README.md`, con limite de token y separando llamada de mencion: **cero llamadas y cero
menciones**. Es una de las **seis** rutas del sistema sin ningun rastro.

No prueba que este muerta -puede llamarla una IA por su nombre, o algo fuera del repo-,
pero es la forma exacta del patron que en esta casa se ha repetido nueve veces.

### Lo que promete

**PROMESA · publica el umbral y DE DONDE SALE, en el propio cuerpo.**
En la foto (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z): `metric = "delta_ratio"`, `fallback_min_ratio = 0.1`, `windows` con
**11 ventanas** (`1m`, `3m`, `5m`, `15m`, `18m`, `30m`, …) y
`note = "El umbral de magnitud es el p75 de …"`.

Contesta **P5.8** -"¿cual es la linea base contra la que comparo?"- y lo hace de la unica
forma que vale: **diciendo que es un p75 medido y no una constante**. La bateria avisa en
P0.10 de lo contrario: *"si es una constante o un COALESCE, no es confianza: es
decoracion"*.

**PROMESA · distingue el umbral MEDIDO del de RESERVA.** `fallback_min_ratio = 0.1` viaja
aparte de `windows`. Un consumidor puede saber cuando esta usando la linea base real y
cuando el valor de emergencia — y el codigo mide lo que cuesta confundirlos:
*"0.10 dejaba pasar el 78 % de las ventanas de 3 m y el 13 % de las de 4 h"*
(`app/scalp_logic.py:210`).

*Que significa no cumplirlo:* que `windows` viniera sin decir si cada ventana es medida o
de reserva. "Fuerte" dejaria de significar nada, que es literalmente P5.8.

**Y no la llama nadie**, aunque su umbral SI viaja al producto: `/api/scalp/absorption`
publica `min_ratio` por ventana, que sale de la misma `metric_baseline`.


## SUPERFICIE

**El recuento vive en la ficha derivada**, que se regenera: [`rutas/api-baselines.md`](../rutas/api-baselines.md), seccion *Superficie*. Aqui NO se copia el numero.

La primera version de estas fichas lo copiaba y envejecio el mismo dia: el andamio escribio "sin consumidor conocido" cuando el detector no veia `RUTA=/api/x` ni `$VAR/api/x`, y al arreglarlo la prosa quedo mintiendo mientras el JSON del mismo commit decia otra cosa. K88 lo caza ahora (brazo 5), y esto quita la causa.

Lo que si aporta esta capa: **no tener ningun rastro no prueba que este muerta** -puede llamarla algo fuera del repo, o una IA por su nombre-, pero es la forma del patron que en esta casa se ha repetido nueve veces, y por eso merece una mirada.
