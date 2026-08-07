# Coinalyze v1.4.8 — lectura rápida del flujo

## Objetivo

Convertir el contexto diario en una lectura que responda en segundos:

- ¿Hay compra o venta spot excepcional frente a la historia conocida?
- ¿El precio acompaña ese esfuerzo o alguien parece absorberlo?
- ¿Es una observación aislada, una defensa o una posible reversión en confirmación?
- ¿Qué debe ocurrir después y qué invalida la hipótesis?

## Método

`daily_flow_read` usa únicamente datos ya existentes:

1. CVD spot de Binance+Bybit y su percentil histórico.
2. Dirección de la agresión en futuros Binance.
3. Cambio del precio durante la sesión NYSE.
4. Secuencia de hasta cuatro sesiones cerradas.

El cuartil superior (`p ≥ 75`) significa compra spot fuerte y el inferior (`p ≤ 25`), venta
spot fuerte. Una venta fuerte sin caída se trata como posible defensa. Sólo se publica
“posible reversión” cuando, después de esa defensa, spot y futuros compran y el precio avanza.

La salida incluye hecho, interpretación, acción de vigilancia, confirmación e invalidación.
La confluencia expresa cuántas evidencias concuerdan; no es una probabilidad de ganancia.

## Replay sin información futura

`GET /api/daily?symbol=BTCUSDT_PERP.A&days=60&as_of=2026-07-01`

El filtro `as_of` se aplica tanto al conjunto usado para calcular percentiles como a las filas
devueltas. Así, la lectura de una fecha histórica sólo conoce las sesiones disponibles hasta
ese cierre. Sin `as_of`, el endpoint conserva el comportamiento normal y usa la última sesión.

## Presentación

La tarjeta **Lectura rápida del flujo** aparece en el resumen operativo. Mantiene visibles los
cuatro datos que justifican el texto: CVD spot y percentil, CVD futuros, respuesta del precio y
cambio de open interest. No oculta la metodología ni sustituye confirmación técnica, gestión de
riesgo o ejecución del operador.
