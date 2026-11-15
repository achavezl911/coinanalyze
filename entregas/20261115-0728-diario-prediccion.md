# Diario de entradas en sombra · lo que espero medir, ANTES (2026-11-15 07:28Z, rama claude/diario-entradas sobre main@f7d8da4)

Escrito antes de una linea de codigo del diario. Arbol: repo de 143. Las tasas historicas son de la rama claude/fable-be,
`git show claude/fable-be:entregas/20261114-2308-fable-be-confirma.tsv` (lineas 2 y 3), banco /root/banco-perfil.

RITMO (cuanto tarda cada fuente en dejar de ser «SIN N», N = 30 operaciones LLENADAS y CERRADAS):
- `D:imp1:v0:A`: 40 operaciones en la confirmacion (2026-01-01 a 2026-11, ~10.5 meses) -> ~3.8 al mes. Espero 30 en
  7-9 meses. Antes de eso el marcador dira SIN N y NO hay nada que concluir.
- `H:imp6:v1:D`: 25 en la confirmacion (2026-08-01 a 2026-11-14, ~3.5 meses) -> ~7 al mes. Espero 30 en 4-5 meses.
- REJILLA: 18 propuestas por dia (3 activos x 2 lados x 3 niveles). Llenado en 5 dias, con una vela diaria de BTC de
  ~2.5-3 % de rango: espero ~60-75 % a 2 %, ~30-45 % a 4 %, ~10-25 % a 6 % (mas en SOL). 30 cerradas en ~2 semanas
  (el plazo de 10 dias manda).
- FABLE: depende de cuantas deje en el buzon. NO SE SABE.

RESULTADO (lo que espero, no lo que deseo):
- La rejilla es el control: limites contra la tendencia, sin regla. Espero R medio cercano a cero menos el coste
  (~ -0.05 a -0.15 R por operacion: maker 2 pb + taker 5.5 pb + 10 pb del stop + funding sobre un stop de 300 pb), con
  mucha varianza segun el mes (un mes con tendencia castiga un lado entero).
- Las reglas: en la confirmacion `D:imp1:v0:A` dio R +0.20 (p 0.28) y `H:imp6:v1:D` R -0.17 (p 0.69). Mi prior es que
  ninguna de las dos tiene ventaja: espero que la diferencia contra la rejilla tenga un intervalo que cruza el cero
  durante TODO el primer ano. Si una sale con el intervalo entero por encima del cero con N >= 30, lo primero que
  sospechare es el diario (llenado, coste, hueco), no el mercado.
- La corrida de punta a punta de esta sesion (un directorio temporal, con las velas de 5 min y 4 h de 140 de los
  ultimos ~7 dias, reloj plantado hacia atras): espero 18 propuestas de rejilla por dia rejugado, 0-2 de reglas, y
  resueltas solo las que caducan o tocan stop/objetivo dentro de la ventana; la mayoria quedara PENDIENTE. Ninguna
  cifra de esa corrida mide nada: prueba el camino.

LO QUE PUEDE ROMPER LA MEDIDA (lo vigilo en la entrega):
- Las velas de 140 son de UN venue (binance perpetuo, 1 min agregado) y el banco de fable-be es el agregado de
  Coinalyze: la paridad es de la LOGICA de las reglas, no de los precios. Una senal puede encenderse en un sitio y no
  en el otro.
- La API de 140 solo da las ultimas 2000 velas: 143 apagado mas de ~7 dias deja huecos que no se rellenan y las
  entradas afectadas quedan PENDIENTES para siempre (asi debe ser: nunca se resuelve con datos que faltan).
- Sellar despues de que el precio llegue: el sello va SIEMPRE antes de la primera vela que cuenta (la entrada a mercado
  es la apertura de la primera vela de 5 min que empieza despues del sello).
