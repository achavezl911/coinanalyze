# Bancos R2 · prediccion escrita ANTES de medir (sobre main@fd283d0, rama claude/bancos-r2)

P1 · De las 6 corridas de K113 suelto sobre el banco con la pagina de main, saldra un (R) del vivo (I-05 Fin o I-06
     PageUp) en 2 de 6. Razon: el operador vio 3 de 29 en K113-control (cada corrida de K113 recorre una vez el teclado
     de BTC 1m VIVO 1920x1080); 3/29 ~ 10 %, y en 6 corridas espero 0-2; digo 2 porque el juez de Fin compara `fin` de
     una cosecha con el numero de velas de OTRA (K113-raton.py:1199-1201) y el latido es cada 5 s.
     Si en 6 no sale ninguna, sigo hasta ver una o hasta 12.
P2 · K113-control en mi rama, con el plantado nuevo (R) fin_que_no_sigue: 30 de 30 en las dos corridas.

Criterio del juez (paso 2), fijado antes de medir: tras Fin y tras cada tecla de I-06, `fin`, `sigue` y n salen de la
MISMA cosecha; se sondea hasta VIVO_S + 2 = 7 s; si la pagina cumple dentro del plazo, VERDE; si no, ROJO con la frase
de hoy. Si n cambia durante el gesto, se juzga contra la n de despues (la de la cosecha que se juzga).
