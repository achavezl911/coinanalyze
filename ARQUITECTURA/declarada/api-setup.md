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

**PENDIENTE.** No se ha escrito que promete esta ruta ni que significa no cumplirlo.

Una promesa vale si es comprobable: "publica el instante de construccion", "no
publica un 0 sin testigo", "la senal dura al menos N minutos". Si la ruta no
promete nada comprobable, eso tambien se escribe.

## SUPERFICIE

**Instrumento interno**, medido.

- **checks**: `harness/checks/K88-control.bash:123`
- **readme**: `README.md:411`
