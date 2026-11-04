# 149 B r1 · P4 tiempo de cuadro con datos de produccion · criterio ESCRITO ANTES DE MEDIR

Rama claude/libro-pro-b. Este fichero se commitea antes de la primera medida de P4. Si algo no se puede medir como
aqui se dice, se entrega como NO SE SABE; no se cambia la vara.

## Sujeto y datos

- Rama: la pagina del ARBOL servida por K111-banco.py en 8121.
- Main: la pagina de main desde su worktree, servida por su propio banco en 8122.
- Las respuestas de /api/libro/fotos, /api/libro/honda y /api/orderflow/footprint se sirven por interceptacion
  CDP (Fetch.fulfillRequest), igual para los dos lados.
  - Salen de x1-tmp/prod-149b/: BTC perp, 4 venues, capturadas por el operador en 140.
  - indice.tsv da la URL de cada fichero.
  - 1 h: 11:00-12:00Z del 2026-11-04, cada 10. 4 h: 08:00-12:00Z, cada 30.
  - Lo demas lo contesta el banco.
- Vistas: `#BTC/perp/hasta=2026-11-04T12:00:00Z` y `#BTC/perp/4h/hasta=2026-11-04T12:00:00Z`.
- Entorno: 1920x1080, DPR 1, Chromium sin cabeza en 143.

## Medida (la misma sonda que el P1 de 6a89b16)

- Gestos:
  - ARRASTRE: 200 pasos de 3 px sobre el lienzo.
  - ZOOM: 200 ruedas, alternando acercar y alejar.
  - Una serie = 200 + 200 = los 400 gestos.
- Cuadro = `EL_MAPA.pinta()` llamado tras cada gesto, MAS un `getImageData` de 1 px que obliga al raster;
  performance.now() en la pagina.
- Tareas largas: PerformanceObserver('longtask') durante la serie, y cuadros > 50 ms.
- A/B alternado, rama y main, 3 + 3 series por vista sobre las MISMAS respuestas; se juntan las 600 muestras por
  lado, vista y gesto.

## CRITERIO

- 1 h: p95 de la rama <= 16.7 ms en arrastre Y en zoom, y 0 tareas > 50 ms (ni cuadros > 50 ms) en cada una de
  sus tres series de 400 gestos.
- 4 h: p95 de la rama <= p95 de main en arrastre Y en zoom.
- Una celda por encima = P4 NO PASA, y se da su cifra.

## Hipotesis a confirmar o refutar (Profiler de CDP, serie aparte, sin cronometro)

«El recalculo de cortes (como mucho 1/s al arrastrar) rehace el mapa de bits de TODA la ventana (mapaDeBits sobre
n columnas x todas las filas, capa honda incluida).»

- CONFIRMADA si, en una serie perfilada de la rama (1 h y 4 h, arrastre), mapaDeBits (tiempo inclusivo, muestreo a
  100 us) es >= 50 % del exceso de los cuadros sobre 16.7 ms de una serie cronometrada de la misma vista.
- REFUTADA si es < 25 %. Entre medias: PARCIAL, con la cifra y lo que se lleva el resto.

Prediccion (no vinculante): CONFIRMADA. Hoy 1 h no pasa; con el mapa de bits por tramos o rehecho solo en lo
visible, si.
