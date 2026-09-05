# DECLARADA · `GET /api/scalp/liquidation-levels`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-scalp-liquidation-levels.md`](../rutas/api-scalp-liquidation-levels.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

Contesta **1** de las 66 preguntas de la bateria (`entregas/20260904-2100-bateria-trader.md`), segun la propia bateria:

- **S7** — ¿Las liquidaciones que me amenazan son las de mi lado?  
  <sub>`entregas/20260904-2100-bateria-trader.md:324`</sub>

## VENTANA

Familia **2** de K43 — coverage de su propia serie.

Derivado de su firma: pide ['limit']: coverage de su propia serie.

**MEDIDO en la foto de produccion** (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z): **no publica NINGUNA**
**marca temporal en el cuerpo.** Ni de primer nivel ni anidada.

Aqui el AST y la foto coinciden, asi que la afirmacion es firme: esta ruta no dice
de cuando es lo que publica. **Candidata a familia 4 de K43 (exenta), y la exencion
hay que escribirla con su cita** — o es un hueco, no una exencion.

<sub>Medido leyendo el cuerpo de la respuesta, no supuesto.</sub>

## PROMESA

### La promesa que comparte casi toda la familia `/api/scalp/*`

**Publica SU EDAD y EL UMBRAL con el que hay que juzgarla, en vez de dejar que el
consumidor lo suponga.** Medido en la foto (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z): las rutas de esta familia traen
`status` junto a alguna forma de `age`/`lag` y su `stale_after_seconds` o
`max_age_seconds`. Es lo que convierte "este numero es viejo" en una comprobacion y no en
una opinion.

*Que significa no cumplirlo:* publicar un valor rancio indistinguible de uno vivo. Es
**P0.9** de la bateria — *"si el proveedor esta caido, ¿me entero o veo el ultimo valor
congelado?"* — y su respuesta solo puede darla la propia ruta, porque nadie de fuera sabe
cuanto es demasiado para ESTE dato.

### Lo propio de esta ruta

**PROMESA · agrupa por PRECIO y publica el numero de eventos de cada cubo.**
En la foto: `rows = [3]` con `price_bucket`, `long_liq`, `short_liq`, `total_notional` y
`events`.

**FRESCURA · cumplia a medias y hoy cumple la mitad que faltaba.** Esta ficha decia
"INCUMPLE" hasta el 2026-09-05, cuando **la decision D2** -*publicar el instante y la
ventana en vez de dejar que el consumidor los suponga*- entro en produccion.

Medido hoy contra 140, no contra la foto de ayer:

```bash
harness/bin/api '/api/scalp/liquidation-levels?symbol=BTCUSDT_PERP.A'
#   as_of        = 2026-09-05T20:32:32.484479+00:00
#   window_start = 2026-09-05T19:32:32.484479+00:00
#   window_end   = 2026-09-05T20:32:32.484479+00:00
#   primer nivel = as_of, bucket_bps, minutes, rows, symbol, window_end, window_start
```

**Lo que ya cumple:** el consumidor puede fechar el dato (`as_of`) y sabe **sobre que
tramo** se agrego (`window_start`/`window_end`), que es mas de lo que pedia la promesa de
familia — un `as_of` a secas no habria dicho si el cubo resume una hora o un dia.

**Lo que SIGUE sin cumplir, y conviene no taparlo:** la promesa de familia tiene **dos
mitades** -*"publica SU EDAD **y EL UMBRAL** con el que hay que juzgarla"*- y esta ruta
solo trae la primera. No publica `stale_after_seconds` ni `max_age_seconds`, asi que el
consumidor puede fechar el dato pero **sigue teniendo que inventarse cuanto es demasiado
viejo para el**. La pregunta **P0.9** de la bateria queda a medias por eso.

*Por que se para aqui:* el umbral de estos niveles depende del uso -para **S7**,
*"¿las liquidaciones que me amenazan son las de mi lado?"*, un minuto es tarde; para
contexto de sesion, una hora vale- y ponerle un numero seria decidir por producto. Con
`window_start`/`window_end` publicados, **el consumidor ya tiene con que decidirlo el.**


## SUPERFICIE

**Superficie de producto**, medido.

- **panel**: `static/app.js:1606`
- **readme**: `README.md:488`, `README.md:500`
- **tests**: `tests/test_v121_hardening.py:29`
