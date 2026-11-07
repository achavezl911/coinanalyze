# 149 C · /libro profesional, el raton · criterio ESCRITO ANTES DE MEDIR

Rama claude/libro-pro-c. Commit de este fichero antes de la primera medida de P1, P2 o P3. Lo que no se pueda medir
como aqui se dice se entrega como NO SE SABE, no con otra vara.

## Sujeto, comun a las tres

- La pagina del ARBOL servida por K111-banco.py en 143 sobre una base cargada con `K111-banco.py carga` (las fotos de
  produccion del 2026-10-18 de K111-fotos; honda y footprint del banco, sinteticos y deterministas). Main (13712e0),
  la misma pagina de main por su propio banco (un worktree), las mismas fotos.
- Chromium sin cabeza en 143, 1920x1080, DPR 1. Vistas: `#BTC/perp/hasta=2026-10-18T03:30:00Z` (1 h) y
  `#BTC/perp/4h/hasta=2026-10-18T06:00:00Z` (4 h).
- Movimientos REALES: Input.dispatchMouseEvent por CDP, 200 por corrida, en un recorrido fijo que cruza el mapa (en
  diagonal, ida y vuelta, todo dentro del area de celdas).

## P1 · el cuadro con la cruz moviendose

- Medida por movimiento: un oyente de `mousemove` en `window` en fase de CAPTURA toma t0; otro en `document` en fase
  de burbuja (despues del manejador del lienzo, que pinta la cruz y escribe la ficha) fuerza el raster con un
  `getImageData` de 1 px de la capa de la cruz (en main, del mapa: main no tiene capa) y toma t1. Cuadro = t1 - t0.
- A/B alternado en la misma corrida: main, rama, main, rama, main, rama por vista; se juntan las 600 por lado.
- CRITERIO: p95 de la rama <= 16.7 ms en las DOS vistas. Main es referencia, no vara. Una vista por encima = P1 NO
  PASA, con su cifra.

## P2 · del movimiento a la ficha escrita

- Por movimiento: desde `ev.timeStamp` (la hora del evento de entrada) hasta el primer requestAnimationFrame despues de
  que #ficha cambie (un MutationObserver marca el cambio; el rAF es cuando lo escrito llega a pantalla). Solo la rama.
- CRITERIO: p95 <= 50 ms en las dos vistas, sobre los mismos 3 x 200 movimientos de P1.

## P3 · los gestos no piden

- La vista de 1 h del pasado (sin vivo: nada sondea), tras `listo`: 100 gestos dentro de lo cargado (rueda con y sin
  Mayus y Ctrl, arrastre del mapa y de los dos ejes, flechas, Re Pag / Av Pag, Inicio, Fin, doble clic en el eje),
  por CDP. Se cuentan las peticiones a /api/libro/fotos y /api/libro/honda vistas por Network.requestWillBeSent entre
  el primer gesto y 2 s despues del ultimo.
- CRITERIO: 0. Una sola = P3 NO PASA, con su URL.

## Prediccion (no vinculante)

- P1: rama p95 ~2-4 ms en 1 h y 4 h (la cruz no repinta el mapa de bits; la ficha es un innerHTML de ~8 lineas);
  main menos (no pinta nada al mover).
- P2: p95 ~16-25 ms (un cuadro; lo manda el rAF, no el calculo).
- P3: 0 (fin se acota a lo cargado; ningun gesto llama a pide() con algo fuera).
