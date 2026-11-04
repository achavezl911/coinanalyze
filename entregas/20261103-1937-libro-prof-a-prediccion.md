# 151 · LIBRO PROFUNDO · RONDA A · prediccion (escrita ANTES de medir, 2026-11-03 19:37Z)

Sobre main@b499cdc, rama claude/libro-prof. Las cifras del operador (2026-11-03 18:20-18:45Z) son suyas; esto es lo mio.

1. Entran okx_swap (books-full) y bitget_usdt (merge-depth) en BTC y ETH. En SOL predigo que okx entra y que bitget
   NO entra: su cubo de scale2/scale3 sera mayor que el paso base 0.02 (o no lo partira), y scale0-1 no doblan lo vivo.
2. El cubo de bitget scale2 en BTC es 10 USD (parte el paso base 10: entra); en ETH sera 1 USD y no parte 0.5 (no entra
   a scale2), y scale1 (0.1) parte 0.5 pero alcanza menos del doble de lo vivo. Confianza baja en ETH.
3. binance_usdm y bybit_linear no entran: su REST alcanza menos del doble de lo vivo (el venue no publica mas).
4. Red: okx BTC/ETH/SOL ~230 KB por foto cada 30 s = ~2 GB/dia solo okx a sz=5000 (3 x 2880 x 230 KB); con bitget
   (~4 KB) < 2.1 GB/dia: CABE en 3 GB sin bajar sz.
5. Disco: la escalera a +-2 % al paso base en BTC son ~70-150 niveles por lado; predigo ~2-4 KB por fila y ~5 filas
   por 30 s -> ~40-60 MB/dia de libro_honda: CABE en 600 MB con mucho margen.
6. El primer nivel hondo cae justo fuera del alcance vivo; no habra solape porque la foto se ancla al alcance vivo
   del mismo proceso en el instante de la foto.
