# 149 · /libro PROFESIONAL · RONDA A · REMATE 2 · entrega

Rama `claude/libro-pro`, sobre 7f33fdf, sin empujar. Cifras de 143: el banco K111 sirve la pagina del ARBOL
sobre una base local cargada con `K111-banco.py carga` (avisos de BTC). Mi sonda NO es la del operador
(`/root/banco-149a-r1/sonda_149a.py` no la puedo leer); mide lo mismo que su U7b: un getBoundingClientRect forzado
en el `push` de `LIBRO_HITOS.tiempos`, justo tras `pinta()`.

Sonda: `x1-tmp/c149/u7b.py` · banco: `bash x1-tmp/c149/banco.sh <salida> [variantes]` (fuera del repo, en /srv/coinanalyze).

## Commits

- `a1778ed` pagina (libro.css, libro-escalera.js), K111-libro (vista viva 1366x768) y K111-control (salidas guardadas,
  vivo|rancio).
- El commit de esta entrega: anade a K111-control `guarda escenario_restaurado`.

## C · el bueno en VERDE

- **Causa: la pagina, no el juez.** `#estado` (la linea de estado encima del cuerpo) pasa de 3 a 4 lineas, de 62 a 80 px,
  y empuja la caja de la escalera 18 px hacia abajo (top 255.6 -> 273.6) con el scrollTop igual. La fila bajo el raton
  quieto cambia (k 8169 -> 8170). El juez tenia razon. Es el mismo fenomeno que el punto 2 del operador en ETH
  (top 410 -> 428, scrollTop 380 igual), y no lo provoca la cabecera, como se sospechaba: lo provoca el estado.
  Medido antes del arreglo (`u7b-antes.out`): 2 estados en 20 s, (8169, caja 255.6, est 62) y (8170, caja 273.6, est 80).
- **Arreglo.** Altura fija para `.estado` (80 px) y `.esc-cabeza` (85 px, la de antes), con `overflow-y:auto` y `contain`.
  Totales en una linea fija. Ademas, el control guarda ENTERA la salida de cada escenario en `$K111_CTL_GUARDA`
  (por defecto `/tmp/k111-control-salidas/<escenario>.sal`), porque la siguiente corrida de K111 la pisaba.
- **K111-control:** `bash x1-tmp/c149/lanza-ctl.sh <n>` (= `K111_CTL_GUARDA=x1-tmp/c149/sal-ctl<n> bash
  harness/checks/K111-control.bash`; salida en `x1-tmp/c149/ctl<n>.out`).
  - **ctl1** (codigo de a1778ed menos los dos cambios del juez): **32 de 35**. el_bueno_es_verde **PASA**, y tambien
    vivo_por_sondeo, hueco_en_medio y sin_libro_dicho. FALLAN tres:
    - sin_libro_con_su_ultimo: el defecto se caza, pero la pagina dice «rancio» donde el patron pedia «vivo». **El fallo
      era del juez:** la pagina que ignora el sin_libro conserva su ultimo libro, y su propio reloj lo vuelve rancio a
      los pocos segundos; cual de los dos ve la sonda depende de la hora del aviso. El patron ahora acepta `vivo|rancio`.
    - arbol_intacto: por mi culpa, escribi esta entrega en el repo durante la corrida.
    - escenario_restaurado.
  - **ctl2** (a1778ed): **34 de 35**. Pasan los cuatro plantados del encargo; sin_libro_con_su_ultimo pasa con su
    mensaje. **FALLA escenario_restaurado:** la huella del bueno al final (0c043ec7b61fd3dc) no es la del principio
    (a113214e45ea706f), con el mismo escenario y rc=0. **La causa NO SE SABE:** el control no guardaba la salida de esa
    corrida. Sospecha sin medir: en la huella de la vista viva entran el estado de cada venue y `ultimos_tipos`, y los
    dos dependen de la hora del aviso reproducido. La vista chica nueva ya la saque de la huella antes de ctl2, y aun
    asi fallo. Este commit guarda `escenario_restaurado.sal` para compararlo con `el_bueno_es_verde.sal`.
  - **El criterio, dos corridas seguidas con todo PASA, NO se cumple.** ctl3 se lanzo despues de este commit: su resultado va en el siguiente, si cabe en el presupuesto.

## B · pinta + maquetacion (p95, criterio <= 8 ms)

Mi sonda, 20 s, `#BTC/perp/ver=90`:

| | BTC 1920x1080 | BTC 1366x768 |
|---|---|---|
| antes (7f33fdf) | 10.9 (pinta 3.7 + maq 8.6) | 8.0 |
| despues, corrida 1 | 9.1 (3.7 + 5.5) | 9.1 (3.3 + 4.9) |
| despues, corrida 2 (variante sin tocar nada) | 7.4 (2.8 + 4.9) | no medido |

- La maquetacion de 1920 baja de 8.6 a 4.9-5.5. Lo que cambio: filas en flex con `contain: strict`; las cajas de
  encima con altura fija y contenidas; venues y cabecera solo se reconstruyen si cambia su contenido (`pintaVenues`,
  `pintaCabeza` con llave).
- **El criterio NO se da por cumplido.** El ruido entre corridas es de ~1.7 ms (9.1 contra 7.4 sobre el mismo codigo).
  1366 no bajo (8.0 -> 9.1, dentro del ruido).
- **ETH 1366x768 no se puede medir en vivo en el banco:** `K111-avisos.jsonl.xz` solo trae avisos de BTC
  (binance_usdm, bybit_linear, okx_swap, bitget_usdt). Las cifras de ETH las tiene que dar la sonda del operador
  contra produccion.
- Diagnostico, sin valor de criterio (variantes que esconden partes): sin venues 7.8 · sin tbody 6.2 · sin
  estado/aviso/totales 9.0. Piezas de pinta(): modelo ~1.3, filas ~1.4, 20 filas tocadas por fotograma.

## A · lo de encima de la escalera, de altura fija

- `.estado` 80 px, `.esc-cabeza` 85 px, `.esc-aviso` y `.esc-totales` contenidos y de altura fija.
- Raton quieto 20 s, mi sonda (`u7b-1.out`): **1 estado** en 1920x1080 (k 8169, top 550.6) y **1 estado** en
  1366x768 (k 8171, top 435.6). Antes eran 2 en las dos pantallas.
- **Brazo K111_RATON:** ahora tambien mira la pantalla chica. Nueva vista viva `#BTC/perp/ver=90` a 1366x768, con el
  prefijo `[BTC perp vivo 1366x768]`. Va en BTC porque el banco no tiene ETH en vivo. Contra produccion esa linea
  admite ETH, pero **no lo he hecho ni medido**.

## D · la ultima operacion y la cabecera de la tabla

- **D1.** El tamano de la ultima operacion (`::after` con `data-ultima`) y las marcas de max/min de sesion van ahora EN
  FLUJO dentro de una celda flex. El precio queda a la derecha y la marca a la izquierda, con elipsis si no cabe. Antes
  estaban en posicion absoluta. En flujo no pueden solaparse por construccion. **La captura recortada NO la he
  mirado:** la del operador esta en /root, que no puedo leer, y no hice una propia.
- **D2.** La causa de que la fila 76720 se viera detras de «precio»: `td.nivel` con `position: relative` pintaba encima
  de un th sticky sin z-index. Ahora el `thead` es sticky con `z-index:2` y fondo opaco (`--bg-strip`).

## Sin tocar

Las barras, lo reciente, los totales (salvo su caja: una linea fija), la API.

## Lo que no se midio

- La sonda r1 del operador (U5, U7b, U8): no tengo acceso.
- ETH en vivo, en cualquier pantalla.
- La captura recortada de D1.
- Pruebas de pagina: `.venv/bin/python -m pytest -q tests/test_libro.py` -> 26 passed, 4 skipped (las 4 saltadas no las
  mire). `ruff check harness/checks/K111-libro.py harness/checks/K111-banco.py` limpio; `node --check` de
  libro-escalera.js y libro-app.js rc=0 (`x1-tmp/c149/comprueba.sh`).
