# DECLARADA · `GET /api/funding-context`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-funding-context.md`](../rutas/api-funding-context.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **3** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P4.4** — ¿El funding me cobra o me paga por estar largo?  
  <sub>`entregas/20260904-2100-bateria-trader.md:171`</sub>
- **P4.5** — ¿Cuánto funding acumulo si aguanto una semana?  
  <sub>`entregas/20260904-2100-bateria-trader.md:172`</sub>
- **S5** — ¿El signo del funding cambia con el lado?  
  <sub>`entregas/20260904-2100-bateria-trader.md:322`</sub>

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

Declara su ventana con estas claves, derivadas de los campos que publica:

- `next_funding_time_utc` — literal en app/scalp_logic.py:3408

## PROMESA


### Lo que promete

**PROMESA 1 · la unidad va en el nombre Y en el `note`.**
En la foto (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z): `current_pct = 0.004455`, `annualized_pct = 4.878`, y
`note = "funding % por periodo 8h; anualizad…"`.

Es la respuesta directa a la trampa de **P4.4**, que la bateria ya midio:
*"`fr_close` ya viene en porcentaje; un ×100 lo multiplica por cien"*. Aqui el sufijo `_pct`
esta en las cuatro cifras y el periodo esta escrito: **un consumidor no tiene que adivinar
si multiplicar**.

**PROMESA 2 · publica el proximo cobro, no solo el actual.**
`next_funding_time_utc = "2026-09-05T00:00:00+00:00"`, con zona explicita. Contesta **P4.5**
—*"¿cuanto funding acumulo si aguanto una semana?"*— junto a `history_avg_pct` por `8h`,
`24h` y `7d`.

**PROMESA 3 · cada media viene con SU cobertura.** `coverage = {8h, 24h, 7d}` en paralelo
a `history_avg_pct`. Una media de 7 dias calculada con 3 no es una media de 7 dias, y aqui
se distingue sin preguntar.

*Que significa no cumplirlo:* que `annualized_pct` y `current_pct` usaran bases distintas
sin decirlo, o que `coverage` desapareciera. Lo primero es P4.4 otra vez; lo segundo, P0.4.

**PENDIENTE · S5 no la he comprobado.** *"¿el signo del funding cambia con el lado?"*: estar
largo con funding positivo **cuesta** y estar corto **cobra**. Esta ruta publica un signo
unico (`regime = "longs pagan…"`), asi que la simetria la tiene que aplicar el consumidor.
**No he mirado si el panel lo hace**, y ese es justo el sitio donde un error de una letra
cuesta dinero:

```sh
grep -n "funding" static/app.js | head -20
```

**La llama el panel** (`static/app.js:1607`).


## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1607`
