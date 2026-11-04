# 149 B · /libro profesional, el mapa · criterio ESCRITO ANTES DE MEDIR

Rama claude/libro-pro-b. Commit de este fichero antes de la primera medida de P1, P2 o P3. Lo que no se pueda medir
como aqui se dice se entrega como NO SE SABE, no con otra vara.

## P1 · tiempo de cuadro (pinta) con todo lo de la ronda

- Sujeto: la pagina del ARBOL servida por K111-banco.py en 143 (las fotos de produccion del 2026-10-18, K111-fotos;
  la capa honda y el footprint del banco son SINTETICOS y deterministas: el fixture es de antes de libro_honda). Main,
  la misma pagina de main por su propio banco (un worktree), con las mismas fotos.
- Vistas: `#BTC/perp/hasta=2026-10-18T03:30:00Z` (1 h) y `#BTC/perp/4h/hasta=2026-10-18T06:00:00Z` (4 h), 1920x1080,
  DPR 1, Chromium sin cabeza en 143.
- Gestos: ARRASTRE (200 pasos de 3 px sobre el lienzo) y ZOOM (200 ruedas, alternando acercar y alejar).
- Cuadro = lo que tarda `EL_MAPA.pinta()` llamado a mano tras cada gesto, MAS un `getImageData` de 1 px que obliga
  al raster. performance.now() en la pagina. La misma sonda para main y la rama.
- A/B alternado: main, rama, main, rama, main, rama (3 + 3) por vista y gesto; se juntan las 600 muestras por lado.
- CRITERIO: p95 de la rama <= 16.7 ms en las CUATRO celdas (2 vistas x 2 gestos). Main se da como referencia, no
  como vara. Una celda por encima = P1 NO PASA, con su cifra.

## P2 · como se pinta lo parcial (n de N)

- Datos: las celdas conocidas (> 0) de la vista por defecto de BTC perp 1 h del banco (fotos REALES del 2026-10-18;
  la capa honda sintetica entra marcada aparte, porque en perp toda celda honda es parcial por construccion: 2 de 4).
- Se cuenta: p = celdas parciales / celdas conocidas a la vista, con y sin capa honda.
- (b) color atenuado por n/N: se RECHAZA si mas del 10 % de las parciales caen, atenuadas, a 26 o mas pasos (10 %
  de 256) de su propio color sin atenuar. Motivo: el color dejaria de ser UNA magnitud (cantidad) y pasaria a ser dos
  (cantidad x cobertura): un muro parcial se leeria como nivel flaco.
- (c) una marca fina: se RECHAZA si p > 25 % en cualquiera de las dos cuentas. Motivo: con mas de una celda de cada
  cuatro marcada, la marca vuelve a ser la textura que se quita (el damero).
- (a) mismo color y la cobertura dicha solo en la lectura: se elige si (b) y (c) se rechazan. Si (c) no se rechaza,
  se elige (c) (dice la cobertura sin tocar el color).
- Prediccion (no vinculante): (b) rechazado (con N=4 una parcial pierde al menos un 25 %); (c) rechazado con capa
  honda; elegida (a).

## P3 · lo que anade la capa honda

- Datos: PRODUCCION por `harness/bin/api` (GET), la vista por defecto de BTC perp y de ETH perp (1 h, paso por
  defecto), /api/libro/fotos y /api/libro/honda de la misma ventana, juntadas por la regla de la ronda (ultima foto
  honda con ts <= t y edad <= 75 s por venue; dentro del alcance vivo manda el vivo) por el juez de K111.
- Se cuenta: niveles conocidos por columna (mediana y p10 de la ventana, y la columna mas nueva), sin y con capa.
- CRITERIO: la capa honda AL MENOS TRIPLICA la mediana de niveles conocidos por columna en BTC perp y en ETH perp.
  Base de la cifra: la medida del operador (2026-11-04 05:41Z): el vivo guardado llega a +-55..210 USD en BTC perp
  (+-10..15 en ETH) y la capa honda a +-0.9..1.3 % (+-2.0 % en ETH).
- Si el canal a produccion no esta en la sesion: P3 = NO SE SABE, y se da la cifra del banco marcada SINTETICA.
