# DECLARADA · `GET /api/volume-profile`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-volume-profile.md`](../rutas/api-volume-profile.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **1** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P2.6** — Si me saltan el stop, ¿es estructura o es una mecha?  
  <sub>`entregas/20260904-2100-bateria-trader.md:142`</sub>

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

Declara su ventana con estas claves, derivadas de los campos que publica:

- `as_of` — literal en app/scalp_logic.py:3584

## PROMESA


### Lo que promete

**MEDIDO CONTRA 140 por el operador el 2026-09-05**, y con los bytes y las claves al lado
del veredicto, que es la contramedida que hacia falta:

```
/api/volume-profile?symbol=BTCUSDT_PERP.A   ->  626 B
claves de primer nivel: symbol · as_of · available · session · vwap · note
                        session.poc / session.vah / session.val
                        vwap.session_convention = 'dia UTC 00:00'
```

**PROMESA 1 · publica SU instante y LA CONVENCION de su sesion.**
`as_of` en primer nivel y `vwap.session_convention = "dia UTC 00:00"`. Un VWAP de sesion
depende enteramente de donde se corta el dia: dos rutas que corten distinto dan cifras
distintas del mismo mercado, y sin la convencion publicada no hay forma de saber cual es
cual.

**PROMESA 2 · hay UNA sola ventana y esta nombrada.**
`session.poc`, `session.vah`, `session.val` cuelgan todos del mismo bloque `session`. No hay
un POC de 24 h y otro de 7 dias compartiendo nombre.

**PROMESA 3 · `available` separa "no hay perfil" de "no se pudo calcular"** (P0.5).

### La sospecha que yo mismo abri, REFUTADA

En la version anterior de esta ficha escribi que habia que mirar *"si cada nivel del perfil
declara sobre que ventana se calculo"*, porque **un POC de 24 h y uno de 7 dias son niveles
distintos con el mismo nombre** — la trampa que **P2.7** describe para
`/api/reference-levels`.

**No aplica.** La ruta publica una unica ventana, con su convencion escrita en el cuerpo.
**No es K**, y que caiga la sospecha es el resultado bueno: esta ficha pasa de sospecha a
promesa cerrada con cita.

*Que significa no cumplirlo:* que apareciera un segundo bloque de niveles -de otra ventana-
al lado de `session`, sin nombre propio. Ahi si volveria P2.7.

## SUPERFICIE

**Instrumento interno**, medido.

- **readme**: `README.md:121`
