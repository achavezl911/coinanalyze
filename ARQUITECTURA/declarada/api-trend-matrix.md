# DECLARADA · `GET /api/trend-matrix`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-trend-matrix.md`](../rutas/api-trend-matrix.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **3** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **P1.2** — ¿Cuál es la tendencia en 15m, 1h, 4h y diario?  
  <sub>`entregas/20260904-2100-bateria-trader.md:114`</sub>
- **P1.3** — ¿Los marcos se contradicen entre sí?  
  <sub>`entregas/20260904-2100-bateria-trader.md:115`</sub>
- **S12** — ¿La matriz de tendencia produce «bajista» tantas veces como «alcista»?  
  <sub>`entregas/20260904-2100-bateria-trader.md:329`</sub>

## VENTANA

Familia **1** de K43 — ventana de construccion de la foto (estado ambiente).

Derivado de su firma: solo pide symbol (o nada): estado ambiente.

Declara su ventana con estas claves, derivadas de los campos que publica:

- `as_of` — literal en app/scalp_logic.py:5990

## PROMESA


### Lo que promete

**PROMESA 1 · publica SU instante en primer nivel.** `as_of` (en la foto,
`2026-09-04T22:33:12.133578+00:00`). Es de las pocas que se fecha a si misma y no solo a
sus filas.

**PROMESA 2 · declara el METODO en el cuerpo.**
`note = "sesgo por marco = estructura(pivote…"`. Un marco que dice "alcista" sin decir como
lo decidio no se puede re-derivar, y **P1.2** exige comparar esta ruta contra `/api/structure`
y `/api/structure-detail`: sin el metodo publicado, la comparacion es entre tres cajas
negras.

**PROMESA 3 · seis marcos, y la alineacion aparte.**
`timeframes = {15m, 1h, 4h, 8h, 1d, 3d}` y `medium_term_alignment = "alcista"` como campo
independiente. Que la alineacion sea un campo y no una deduccion es lo que permite
contestar **P1.3** —*"¿los marcos se contradicen entre si?"*—: `mixto` es una respuesta
publicada, no algo que el consumidor tenga que inferir.

*Que significa no cumplirlo:* que `medium_term_alignment` no fuera nunca contradictorio. La
bateria lo dice en P1.3: *"una matriz que nunca se contradice esta aplanando algo. Contar
contradicciones en 30 dias: si son 0, sospechar del metodo, no del mercado."*

**PENDIENTE · esa cuenta no la he hecho.** Necesita serie, no foto:

```sh
harness/bin/prodsql "SELECT COUNT(*) FILTER (WHERE swing_bias <> regime_bias), COUNT(*)
  FROM daily_verdict WHERE session_date >= now() - interval '30 days'"
```

**La llama el panel** (`static/app.js:1478` y `:1580`).


## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1478`, `static/app.js:1580`
- **tests**: `tests/test_v150_desk_snapshot.py:126`
