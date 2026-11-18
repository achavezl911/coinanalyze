# DIARIO R1 · PREDICCION (antes de medir) · rama claude/diario-r1 sobre main@60709d1

Lo que espero, escrito antes de tocar codigo ni bajar nada:

- D1 · la causa de las 280 filas sin precio y al 100 % es que la ruta calcula la cobertura con COUNT(*) sobre filas de 1 min
  y LUEGO mask_gapped_series_rows pone a null los precios de los cubos con hueco declarado, sin tocar sample_count,
  is_complete ni coverage_pct. Espero que la prueba con el doble de esas filas salga ROJA en main (coverage 100, is_complete
  true) y VERDE aqui. No espero tocar sql/.
- D2 · espero que la vela publica de 5 min (agregada de las de 1 min de data.binance.vision, BTCUSDT perpetuo USD-M) sea
  IDENTICA a la de la ruta en apertura/maximo/minimo/cierre en mas del 99 % de los cubos de un dia sano con las dos (la ruta
  sale de las velas de 1 min de binance que ingiere 140), con diferencias, si las hay, en el ultimo decimal o en cubos
  revisados. Si sale por debajo del 95 %, lo digo y no lo maquillo. El volcado diario aparece al dia siguiente, asi que el
  11-16 y el 11-17 deberian estar ya publicados y el 11-18 no.
- D3-D5 · pruebas puras con dobles: en main el dia sin rejilla da errores [] (ROJO), la orden llenada mas alla del stop sale
  «stop» con R > 0 (+0.79 R en el caso R1) y un dia da un intervalo de ancho cero. Aqui las tres VERDES.
- D6 · los casos L1 y L2 de R3b: en main verifica()=[] tras sellar con un --ahora anterior y tras quitar la ultima linea;
  aqui L1 se niega al sellar y L2 lo delata el historico de cabezas.
- D7 · espero que el metodo de fable_r3_foto.py recupere SOL en ~27 de 27 en main y en 0 de N aqui.
- D8 · en main el aviso «Bybit APAGADO» se intenta x1 con manda() fallando; aqui se reintenta hasta entregarse y x1 despues.
- Coste: espero acabar entre 10 y 14 USD de 16. La suite entera con -n 4: unos 10-20 min, sin CI a la vez.
