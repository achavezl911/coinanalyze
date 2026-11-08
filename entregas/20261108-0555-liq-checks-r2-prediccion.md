# 150 · remate 2 · prediccion (escrita antes de medir, 2026-11-08 05:55Z, rama claude/liq-checks sobre 56a131d)

Sin medir nada todavia contra 140 en esta sesion. Base: la prediccion del r1 (P2: 'cinta' >= 95 %, 'sin_dato' <= 5 %
sin ap) y que el colector de binance guarda `ap` desde que la 150 llego a produccion (madrugada del 11-08).

## P1 · (E) de 140, ultimas 24 h, >= 10 k (K120 suelto, minuto NO multiplo de 5)
- (E) da su cuenta, no 422: la ventana termina en el borde de 5 min anterior.
- Por activo: BTC 40-200, ETH 30-150, SOL 10-80 liquidaciones >= 10 k en 24 h.
- 'ap' > 0 solo en binance y solo desde el despliegue (unas 4-5 h de 24): 10-25 % del total de cada activo.
- 'cinta' el resto salvo 'sin_dato' <= 5 % por activo. (E) no condena ninguna (ni ap ni cinta del otro lado).

## P2 · K104 contra produccion sobre liquidations_realtime
- Resuelve LIQ_REALTIME_RETENTION_DAYS = 30 (del default= de config.py del release si el env no la trae).
- Piso = date(ahora - 720 h) + 1 dia = 2026-10-10; juzga los dias cerrados 2026-10-10 .. 2026-11-07.
- Con filas solo 2026-11-07 (antes de la 150 la poda era de 12 h): un dia. Es el primer censo con la linea nueva,
  asi que esa pareja solo se siembra y hoy no puede condenar; la tabla deja de salir en «SIN DIA CERRADO».
- El veredicto global de K104 no cambia por esta linea (si era VERDE, sigue VERDE).
