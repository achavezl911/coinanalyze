# DECLARADA · `GET /api/ai/context/bundle`

> **Capa DECLARADA · se escribe A MANO.** El generador la lee, no la escribe.
> La ficha derivada es [`rutas/api-ai-context-bundle.md`](../rutas/api-ai-context-bundle.md).
> Cada afirmacion lleva su cita. Lo que no se pueda sostener va PENDIENTE con su motivo.

## PREGUNTA

**NINGUNA de las 66 preguntas de la bateria la nombra.**

Medido sobre `entregas/20260904-2100-bateria-trader.md`: ninguna fila de las 54 (P0.1..P5.9) ni de las 12
(S1..S12) cita esta ruta en su columna de destino ni en la de medicion.

Eso NO significa que no sirva: significa que **el trader no le ha formulado**
**una pregunta**. Si es un instrumento interno, lo normal es que no la haya.
Si es superficie de producto y no contesta ninguna pregunta, merece mirarse.

## VENTANA

**PENDIENTE de familia.** parametros ['bucket_bps', 'profile', 'symbols']: no encaja en 1/2/3 sin leerla

Declara su ventana con estas claves, derivadas de los campos que publica:

- `generated_at` — literal en app/ai_context.py:992

## PROMESA


### Lo que promete

Medido en la foto (`entregas/20260904-foto-prod-1.json`, 2026-09-04T22:34:11Z):

```
/api/ai/context/bundle   295 256 B
  instante de RAIZ ....................... generated_at = 2026-09-04T22:33:19.779979+00:00
  bloques de primer nivel ................ 1   (symbols)
  instantes DISTINTOS en el cuerpo ....... 18
```

**PROMESA 1 · es el mismo contexto de `/api/ai/context` para LOS TRES simbolos, con una
sola marca de raiz.** `symbols` cuelga de `generated_at`, y cada simbolo trae el suyo.

**PROMESA 2 · el arco de armado es visible y NO es cero.** La raiz del bundle dice
`22:33:19.779979` y la de `/api/ai/context` para un simbolo dice `22:33:02.403024`: **17
segundos de diferencia** en la misma foto. No es un defecto — armar tres contextos lleva
tiempo — pero **es la cifra que hace comparable un bloque con otro**, y esta publicada.

*Que significa no cumplirlo:* que `generated_at` del bundle se tomara al empezar y no al
acabar, o al reves, sin decir cual. Entonces los 18 instantes del cuerpo no se podrian
situar respecto de el.

**Hereda el defecto de `/api/ai/context`**: los mismos 18 bloques por simbolo siguen sin
fecharse. Ver esa ficha.


## SUPERFICIE

**Instrumento interno**, medido.

- **readme**: `README.md:415`, `README.md:519`
