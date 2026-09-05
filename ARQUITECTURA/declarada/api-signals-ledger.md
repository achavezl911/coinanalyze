# DECLARADA · `GET /api/signals/ledger`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-signals-ledger.md`](../rutas/api-signals-ledger.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **4** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P1.11** — ¿Esta señal ya estaba antes de que yo mirara, o nació al mirar?  
  <sub>`entregas/20260904-2100-bateria-trader.md:123`</sub>
- **P1.6** — ¿La señal de ahora es la misma que hace 5 minutos?  
  <sub>`entregas/20260904-2100-bateria-trader.md:118`</sub>
- **P1.7** — ¿Cuántas señales de este tipo ha habido en 30 días?  
  <sub>`entregas/20260904-2100-bateria-trader.md:119`</sub>
- **S1** — ¿Cuántas señales LARGO y cuántas CORTO en 30 días?  
  <sub>`entregas/20260904-2100-bateria-trader.md:318`</sub>

## VENTANA

Familia **3** de K43 — su propio as_of bajo demanda.

Derivado de su firma: pide ['since']: el operador elige el momento.

Declara su ventana con estas claves, derivadas de los campos que publica:

- `since` — literal en app/api.py:2145
- `until` — literal en app/api.py:2146

## PROMESA

**PENDIENTE.** No se ha escrito que promete esta ruta ni que significa no cumplirlo.

Una promesa vale si es comprobable: "publica el instante de construccion", "no
publica un 0 sin testigo", "la senal dura al menos N minutos". Si la ruta no
promete nada comprobable, eso tambien se escribe.

## SUPERFICIE

**Sin consumidor conocido**, medido: no aparece en `static/app.js`,
`static/index.html`, `harness/checks`, `tests`, `tools` ni `README.md`.

No prueba que este muerta -puede llamarla algo fuera del repo-, pero es la
forma del patron que en esta casa se ha repetido nueve veces.
