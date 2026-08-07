# Coinalyze v1.4.6 — perfil de volumen y delta por nivel de precio

## Qué responde

"En esta zona, ¿hubo más compra o más venta?" — la misma pregunta que contesta **Lectura de
zona**, pero sin teclear los bordes y para todos los niveles a la vez. El lector de zona sigue
siendo el que da veredicto razonado sobre una banda concreta; el perfil es el mapa que te dice
qué banda merece esa pregunta.

## `/api/delta-profile`

Nuevo endpoint (`symbol`, `interval`, `days`, `price`). Reparte el volumen y el delta de cada
vela entre los cubos de precio que cruza su rango low-high y suma por cubo. Publica las filas,
el POC, el área de valor del 70%, los nodos delgados, el delta neto y su fracción del volumen.

No sustituye a `/api/volume-profile`, que sigue alimentando el contexto de IA y resuelve otro
problema: la sesión UTC en curso con velas de 1 min asignadas al cubo de su cierre.

## Ventanas, según la cobertura que existe de verdad

| ventana | intervalo | cobertura medida |
|---|---|---|
| 30 d / 90 d / 300 d | 4h | 1.801 velas desde 2025-10-08 |
| Intradía | 5min | 2.512 velas desde 2026-07-27 |

No se ofrece 300 d en 5 min porque Coinalyze no sirve esa profundidad: prometería historia que
no existe. Pedir más días de los disponibles no falla, devuelve lo que hay y declara `bars`,
`from` y `to`.

## Dos límites que el panel declara

1. **El reparto dentro de la vela es uniforme, y por tanto aproximado.** Sabemos que se operaron
   N contratos entre `low` y `high`, no en qué punto. El perfil sirve para leer la forma —dónde
   se concentró el negocio y dónde no—, no para afirmar el importe exacto de un cubo.
2. **El delta es de futuros de Binance (`.A`), no del contado.** El CVD spot histórico solo
   existe agregado por sesión NYSE, que no tiene resolución de precio. Llamar a esto "compra" a
   secas repetiría el error de procedencia que se corrigió en v1.3.4.

## Defecto corregido al escribir las pruebas

El índice de cubo usaba `//` directo. `104 // 0.2` da **519**, no 520, porque 104/0.2 se
representa como 519.9999999999999: el volumen de una vela que arrancaba justo en un borde se
etiquetaba un cubo por debajo, y el cubo que contenía el máximo se perdía del reparto. Ahora el
índice se calcula con tolerancia.

## Verificación

- 233 pruebas automatizadas (222 previas + 11 nuevas).
- `ruff check app tests scripts` limpio.
- Perfil comprobado contra la base viva en BTC, ETH y SOL, en las cuatro ventanas.
