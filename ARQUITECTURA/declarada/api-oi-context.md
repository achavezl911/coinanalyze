# DECLARADA · `GET /api/oi-context`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-oi-context.md`](../rutas/api-oi-context.md).
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

Declara su ventana con estas claves, derivadas de los campos que publica:

- `oi_latest_ts` — literal en app/scalp_logic.py:3118
- `price_latest_ts` — literal en app/scalp_logic.py:3119

## PROMESA


### Lo que promete · y es la unica que publica DOS relojes distintos

Medido en la foto (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z), **3 356 B**:

```
oi_latest_ts    = '2026-09-04T22:25:00+00:00'
price_latest_ts = '2026-09-04T22:32:00+00:00'      <- SIETE minutos de diferencia
```

**PROMESA 1 · el reloj del OI y el reloj del PRECIO son campos SEPARADOS.**
Y en la foto llevan **7 minutos de desfase**, que no es un fallo: el OI se publica cada 5
min y el precio cada minuto. Lo que importa es que **la ruta no finge que son el mismo
instante**. Cualquier cociente OI/precio calculado sin saberlo mezcla dos vendimias, que es
literalmente **P0.1**.

**PROMESA 2 · cada ventana trae su cobertura.** `windows = {5m,15m,1h,4h,24h}` y
`coverage` con las mismas cinco claves, en paralelo.

**PROMESA 3 · el reparto por venue con su nota.** `by_venue` con `binance_oi_usd`,
`bybit_oi_usd`, `two_venue_total_usd`, `bybit_share_of_two_venues_pct` y su `note`. El
total de dos venues va nombrado **`two_venue_total_usd`**, no `total`: quien lo lea sabe que
no es el OI del mercado entero.

**PROMESA 4 · marca lo que es interpretacion.**
`quadrant_note = "el cuadrante es interpretacion prob…"`. El cuadrante OI/precio es una
lectura, no una medida, y la ruta lo separa.

*Que significa no cumplirlo:* fundir los dos `*_latest_ts` en un `as_of` unico. Se perderia
exactamente el dato que hace comparable el cociente.


## SUPERFICIE

**Instrumento interno**, medido.

- **checks**: `harness/checks/K38-referencia-por-tiempo.sh:33`
