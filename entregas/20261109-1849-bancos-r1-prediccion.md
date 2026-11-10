# Bancos R1 · prediccion, escrita ANTES de tocar el juez (rama claude/bancos-r1 sobre main@c1cea1f)

P1 · K113-control en la rama: 30 de 30 (los 28 de hoy + carril_en_los_dos + carril_ninguno). Veo al leer que el sed de
     cifra_que_no_sale (`if (wv + 4 <= w / 2 && wc + 4 <= w / 2)`) ya no existe en flujo-dibujo.js desde #231: no muerde;
     lo re-apunto a `+ 4 <= hueco[p[0]]` (linea 565) y cuenta dentro de los 30.
     K109-control en la rama: 29 de 29.
     En main@c1cea1f de control: K113-control 20 de 28 (FALLAN el_bueno_es_verde, cifra_que_no_sale, los dos sigpipe,
     las tres invocaciones y escenario_restaurado: todos piden VERDE o un sed que muerda); K109-control 28 de 29
     (FALLA poc_en_otro_nivel).
P2 · K113 con la pagina de main y mi juez sobre el banco de K113-control: 0 hallazgos (T).

Criterio: si el bueno no sale VERDE con mi juez, el juez esta mal (la pagina no esta acusada). Si (a) o (b) no muerden,
se dice con la medida (filas visibles con carril, y cuantas cambian de veredicto entre w/2 y w/2 - 10).
