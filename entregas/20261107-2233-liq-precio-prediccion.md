# Campana 150 · liquidaciones en el precio · criterio escrito ANTES de medir (2026-11-07 22:33Z)

Umbral por omision: 10 000 USD. Por que: en 140 hubo ~625 liquidaciones en 12 h (medida del operador,
19:40Z); la mayoria son de centenares a pocos miles de USD y llenarian el mapa de puntos sin lectura. 10 k es
el primer escalon que se ve en el libro de BTC (una orden de 10 k mueve poco; una cascada de varias si).
Se puede bajar a 1 k o subir a 50 k/100 k desde el mando de cada pagina.

Regla del radio: r = clamp(3 * sqrt(usd / 10 000), 3, 18) px, AREA proporcional a USD con escala FIJA
(comparable entre ventanas): 10 k -> 3 px, 100 k -> 9.5 px, 298 k -> 16.4 px, >= 360 k -> 18 px.

## P1 · lo pintado es lo que trae la ruta
En BTC 1 m de /flujo y BTC de /libro, sobre 140 (ultimas 6 h): numero de circulos que pinta cada pagina
(window.LIQ_PINTADAS.length, sin recortar por la vista) == numero de eventos de
/api/orderflow/indicadores (sueltas.eventos) con usd >= umbral en esa misma ventana.
Criterio: IGUALES, en las dos paginas. Cualquier diferencia es un fallo.
Prediccion: iguales; del orden de 20-80 por encima de 10 k en 6 h (NO SE SABE la cifra; se mide).

## P2 · el coste del pintado
p95 del tiempo de pintado por fotograma (pintaMapa) en /libro vivo BTC 1 h, con liquidaciones encendidas
contra apagadas, misma ventana y mismo numero de fotogramas.
Criterio: p95 con ellas <= 16.7 ms. Prediccion: la diferencia es < 1 ms (decenas de arcos por fotograma).

## P3 · cascadas M8 en 140
Cascada M8 = por lado, >= CASCADA_N=5 liquidaciones en CASCADA_S=60 s (scripts/anatomia_*), sin umbral
de USD. Ultimas 12 h de 140, BTC + ETH + SOL, binance + bybit juntos.
Se mide: cuantas cascadas y la mayor en USD (suma de sus liquidaciones), por la regla de la pagina
sobre las filas de la ruta. Prediccion: entre 3 y 30; la mayor, BTC, del orden de 10^5-10^6 USD.
NO es un criterio de VERDE/ROJO: es la cifra que se publica, con su comando.
