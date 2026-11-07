# BOT-5 · la candidata en sombra · PREDICCION (escrita y commiteada ANTES de medir)

Rama claude/bot-sombra, paso 1 en e4b48bf. Candidata: congeladas-20261103.json (sha256 be13350c09e7c993687a...),
SOL corto si ds100k_60 <= -479834.70166359004, E1 (1 % / 0.6 %, 240 min, 5.5 bps por lado), capa B.

## El banco de K119 (lo que se medira)
La muestra no dispara: en sus 2 horas (2026-10-21 04-05Z) la suma de 60 min de impresos de contado de SOL >= 100k va de
0 a +478219 USD (un solo minuto con impreso grande, de compra; x1-tmp/explora.py). Una comparacion sobre ella diria
«0 = 0» y no mediria nada. Por eso el banco es la muestra REAL + horas SINTETICAS de SOL antes y despues
(00-03Z y 06-18Z del 10-21), con estos sucesos plantados a proposito:
  F1  un impreso de venta de EXACTAMENTE 479834.70166359004 a las 01:10 -> decision 01:14, camino por la muestra real
      (SOL entre -0.13 % y +0.39 % de 105.7): VENCE sin tocar. Las decisiones 01:19..02:09 tambien cumplen: bloqueadas.
  F2  -300k a las 09:40 y -200k a las 10:39 -> solo la decision 10:39 suma 60 min (con 59 no): EXITO
  F5  -500k a las 12:40 -> decision 12:44; el precio sube 0.6 %: FRACASO por stop antes de 13:19
  F6  la misma ventana de F5, en la primera decision >= la salida de F5: EXITO (el hueco se libera al tocar)
  F4  -500k a las 16:40 -> decision 16:44; falta el minuto de binance_usdm de 18:20 dentro del camino: SIN DATO
  senuelos que NO deben disparar: -600k de PERPETUO (06:10), 6 x 99999 de contado (07:20), -479834.70 (08:30).

## P1 · el camino vivo y el estudio dan los mismos disparos y resultados
Prediccion: el estudio (anatomia_extrae + estudio numpy sobre los mismos TSV) da 4 operaciones tomadas
(F1 vence, F2 exito, F5 stop, F6 exito) y la decision F4 que cumple sin etiqueta valida; el bot da esas 4 filas con el
mismo minuto, entrada, resultado y neto (|neto| a 1e-12), y una fila SIN DATO en F4. Criterio: igualdad exacta.
Si sale distinto, lo digo con la fila que difiere: no se ajusta el banco a lo que salga.

## P2 · coste por tic
Prediccion: p95 del tiempo EXTRA por tic en la base del banco ~ 50 ms (una consulta por minuto nuevo, con cache de
barras). Criterio: p95 <= 2 s.

## P3 · lo que diria /entrada hoy en 140 (solo lectura)
Prediccion: en las 48 h de orderflow_cinta de 140, entre 3 y 20 disparos con sin_solape (el descubrimiento dio 78 en
~16 dias de capa B: ~10 por 48 h). Es un recuento, no un juicio: n < 30 = SIN CALIBRAR.
Criterio: sale una cifra con su comando; si el canal falla, NO MEDIDO.
