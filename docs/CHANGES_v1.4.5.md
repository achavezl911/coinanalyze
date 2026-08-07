# Coinalyze v1.4.5 — presentación del operador

Cambio de presentación. No se añade ninguna fuente de datos ni ningún indicador nuevo: todo
lo que aparece sale de payloads que el dashboard ya descargaba.

## Ejes en dinero, no en floats crudos

El eje de CVD escribía `418951166.51` y el de open interest `7100000000.00`. Las cuatro series
en USD (CVD, OI, whale, diario) pasan por un formateador y ahora leen `$418.95M` y `$7.05B`.
El eje de precio recupera el separador de miles (`65,200.00`). El formateador cubre también la
etiqueta del crosshair y la de la línea de precio, que es donde se lee el número al operar.

## Perfil de liquidaciones por nivel

"Concentración por precio" deja de ser una tabla y pasa a ser un perfil: escalera de precios de
mayor a menor, barra roja a la izquierda para longs liquidados y verde a la derecha para shorts,
con el precio actual marcado sobre la escalera y los totales de la ventana al pie.

Se parece al mapa de liquidaciones de las herramientas comerciales, pero **no es lo mismo y el
panel lo dice**: aquellas estiman dónde reventarán posiciones a partir del apalancamiento
supuesto; esto es densidad **ya ejecutada** en los últimos 60 minutos. No tenemos el
apalancamiento del libro y no se finge tenerlo.

## Analizadores en un solo panel, con los campos precargados

Lectura de zona, ¿es un rango? y probabilidad de ruptura eran tres tarjetas apiladas, cada una
con un formulario vacío y el resto del panel en blanco. Ahora comparten un panel con pestañas y
los campos llegan precargados con lo que el propio dashboard ya detectó: la zona activa (o el
soporte más cercano), el rango de Wyckoff con sus fechas, y la resistencia más cercana como
nivel de ruptura. Un valor escrito a mano no se sobrescribe; al cambiar de activo todo vuelve a
ser recargable, porque un precio de BTC no significa nada en SOL.

## Sparklines en las tarjetas de cabecera

Precio, CVD spot, open interest y funding llevan la serie de las últimas 60 sesiones bajo el
número. Sale del rollup diario, que se pide en el tramo lento de refresco (una vez por minuto),
no en el ciclo de 15 s: el dato cambia una vez por sesión.

## Ausencia de whale: contada, no dibujada como cero

El panel de actividad institucional pintaba una línea plana en cero. Es una lectura válida —no
cruzó ninguna orden de ese tamaño—, pero gastaba un panel entero para decirlo. Con menos de dos
ventanas activas se resume en texto: cuántas de las 384 ventanas de 15 min tuvieron actividad y
cuál fue la última. Medido: BTC 1/384, ETH 0/384, SOL 2/384.

## Densidad

Los paneles ya no se estiran hasta la altura del vecino más alto, así que dejan de encerrar
franjas vacías dentro de su borde. La imbalance del order book se dibuja además como barra
dentro de la celda, centrada en 0.5.

## Verificación

- 222 pruebas automatizadas (211 previas + 11 nuevas de contrato de presentación).
- `ruff check app tests scripts` limpio.
- Las cinco vistas y los tres analizadores revisados contra payloads reales de producción
  (BTC, ETH y SOL) servidos en local, incluido el cambio de activo.
