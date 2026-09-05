# DECLARADA · `GET /api/context-metadata`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-context-metadata.md`](../rutas/api-context-metadata.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **1** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P0.1** — ¿De cuándo es cada número que estoy viendo?  
  <sub>`entregas/20260904-2100-bateria-trader.md:93`</sub>

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

Declara su ventana con estas claves, derivadas de los campos que publica:

- `generated_at` — literal en app/scalp_logic.py:3625

## PROMESA


### Lo que promete

**PROMESA · publica QUE VERSION de calculo produjo el contexto, y con que venues.**
Campos derivados del AST: `calc_version`, `feeds`, `generated_at`, `note`, `symbol`,
`venues_note`. **No lee ninguna tabla**: es metadato de codigo, no de datos.

Contesta **P0.1** —*"¿de cuando es cada numero que estoy viendo?"*— con `generated_at`, y
la mitad de **P5.5** —*"¿que version de la logica produjo estos resultados?"*— con
`calc_version`.

**Y la bateria le pone la advertencia mas exigente de P0.1**, que esta ruta **no** puede
cumplir sola: *"hay **27 instantes distintos** dentro de una foto y la etiqueta de la raiz
se toma a mitad del armado. [...] Una etiqueta unica sobre datos de vendimias distintas
miente MAS que 43 etiquetas."*

*Que significa:* `generated_at` de esta ruta es **el instante de ESTA respuesta**, no el de
los datos que otras rutas publican. Usarla como "la hora de la foto" es precisamente el
error que P0.1 describe. La promesa correcta es la estrecha: *dice cuando se armo este
metadato y con que version, y no dice nada sobre la frescura de ningun otro bloque.*

**PENDIENTE · lo que no puedo sostener.** Si `calc_version` cambia cuando cambia la logica
—o se queda pegada, como la fase de Wyckoff de P1.4—. Hace falta una serie, no una foto:

```sh
harness/bin/prodsql "SELECT DISTINCT calc_version FROM signal_replay_frame ORDER BY 1"
```


## SUPERFICIE

**El recuento vive en la ficha derivada**, que se regenera: [`rutas/api-context-metadata.md`](../rutas/api-context-metadata.md), seccion *Superficie*. Aqui NO se copia el numero.

La primera version de estas fichas lo copiaba y envejecio el mismo dia: el andamio escribio "sin consumidor conocido" cuando el detector no veia `RUTA=/api/x` ni `$VAR/api/x`, y al arreglarlo la prosa quedo mintiendo mientras el JSON del mismo commit decia otra cosa. K88 lo caza ahora (brazo 5), y esto quita la causa.

Lo que si aporta esta capa: de lo que hay, **nada es una llamada**. Una ruta de la que solo se habla en comentarios no tiene consumidor: tiene quien la nombra.
