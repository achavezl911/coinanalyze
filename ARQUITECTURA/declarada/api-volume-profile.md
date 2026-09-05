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

**PENDIENTE, y el motivo es que no he leido su cuerpo.**

No esta entre las respuestas de la foto cuyo cuerpo he inspeccionado, y sus campos no se
derivan del AST lo bastante como para sostener una afirmacion. **No lo relleno con lo
plausible**: seria exactamente lo que este directorio existe para no hacer.

Lo que si se sabe, de su ficha derivada y de la bateria:

- La bateria le asigna **P2.6** —*"si me saltan el stop, ¿es estructura o es una mecha?"*—
  junto a `/api/zone/analysis` (`entregas/20260904-2100-bateria-trader.md:145`).
- **Nadie la llama**: sus rastros son MENCION. Es una de las 12 rutas sin ninguna llamada.

Comando para cerrarla, sin consulta a la base:

```sh
harness/bin/api '/api/volume-profile?symbol=BTCUSDT' | python3 -m json.tool | head -40
```

Lo que hay que mirar cuando responda: **si cada nivel del perfil declara sobre que ventana
se calculo**. Un POC de 24 h y uno de 7 dias son niveles distintos con el mismo nombre, y es
la misma trampa que P2.7 describe para `/api/reference-levels`.


## SUPERFICIE

**Instrumento interno**, medido.

- **readme**: `README.md:121`
