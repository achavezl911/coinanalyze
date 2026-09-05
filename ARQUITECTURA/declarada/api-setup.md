# DECLARADA · `GET /api/setup`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-setup.md`](../rutas/api-setup.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **7** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P1.1** — ¿Hay una señal activa ahora y de qué lado?  
  <sub>`entregas/20260904-2100-bateria-trader.md:113`</sub>
- **P1.10** — ¿El setup de largo contradice al de corto?  
  <sub>`entregas/20260904-2100-bateria-trader.md:122`</sub>
- **P1.12** — ¿Qué me haría cambiar de opinión ahora mismo?  
  <sub>`entregas/20260904-2100-bateria-trader.md:124`</sub>
- **P3.1** — ¿Cuál es el objetivo y de dónde sale?  
  <sub>`entregas/20260904-2100-bateria-trader.md:152`</sub>
- **P3.2** — ¿Cuál es el R:R real, ya con coste?  
  <sub>`entregas/20260904-2100-bateria-trader.md:153`</sub>
- **S2** — ¿Cuántas veces dijo NO ENTRAR?  
  <sub>`entregas/20260904-2100-bateria-trader.md:319`</sub>
- **S6** — ¿El objetivo y el stop están del lado correcto del precio?  
  <sub>`entregas/20260904-2100-bateria-trader.md:323`</sub>

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

Declara su ventana con estas claves, derivadas de los campos que publica:

- `snapshot_ts` — literal en app/api.py:2017

## PROMESA


### Lo que promete

**PROMESA 1 · publica el instante del SNAPSHOT del que sale, no el suyo.**
En la foto (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z): `snapshot_ts = "2026-09-04T22:33:05.548107Z"`. La ruta se arma despues,
y lo que fecha es **el dato del que depende**. Para P0.1 eso es lo correcto: importa de
cuando es el snapshot, no de cuando se formateo la respuesta.

**PROMESA 2 · publica TODOS los setups evaluados, no solo el que gana.**
`primary` mas `setups = [5]`, cada uno con `id`, `name`, `bias`, `horizon`, `confidence` y
`state`. Es lo que hace posible **P1.10** —*"¿el setup de largo contradice al de corto?"*—:
con solo `primary`, la contradiccion seria invisible por construccion.

**PROMESA 3 · declara la fuente del flujo diario por su nombre.**
`daily_flow_source = "cvd_spot_usd (Binance+Bybit)"`. No es un detalle: el mismo `slope`
calculado sobre otra fuente es otro numero, y **P1.1** ya midio que *"el diferencial
spot-futuros NO vota direccion"*.

**PROMESA 4 · dice que es un sesgo y no un consejo.** `warning = "Sesgo probabilistico. No
constituye…"`. Es la unica de las 68 que trae un descargo en el cuerpo.

*Que significa no cumplirlo:* que `setups` se recortara a los que apoyan a `primary`.
Entonces el producto seria un generador de razones, que es lo que **P5.9** persigue.

**Nadie la llama** salvo un fixture de control: su unico rastro de codigo es
`harness/checks/K88-control.bash:133`, que la usa como caso de prueba. Contesta **siete**
preguntas de la bateria —mas que ninguna otra ruta— y el panel no la consume.


## SUPERFICIE

**Instrumento interno**, medido.

- **checks**: `harness/checks/K88-control.bash:123`
- **readme**: `README.md:411`
