# Guia de uso - Coinalyze Operator Dashboard v1.2.5

Version del documento: 1.0

Fecha: 2026-06-30

## 1. Objetivo

Este documento explica como usar el Dashboard ya desplegado. No es una guia de instalacion. Su proposito es ayudarte a leer el panel de forma consistente, detectar si los datos estan sanos y convertir las lecturas en una rutina operativa prudente.

El Dashboard es una herramienta de analisis de microestructura y derivados. No ejecuta ordenes, no administra cuentas de trading y no debe interpretarse como recomendacion financiera. La decision final siempre queda fuera del sistema.

## 2. Acceso

- URL operativa: https://10.151.1.6:8443
- Usuario: operator
- La contrasena es la definida en Basic Auth del despliegue.
- El certificado TLS es autofirmado; el navegador puede mostrar una advertencia.
- Si la pagina carga pero los datos aparecen vacios, revisa primero el indicador Pipeline y luego recarga con Ctrl+F5.

## 3. Primera lectura al abrir el panel

1. Verifica la barra superior.
2. Confirma que el estado diga Streaming activo o En linea.
3. Revisa el indicador Data. Un estado ok significa que hay snapshots, flujos spot/futuros y order book con lag aceptable.
4. Elige el simbolo: BTC, ETH o SOL.
5. Lee primero las tarjetas de resumen, despues Scalp score y finalmente las tablas de microestructura.

No empieces por una grafica aislada. La lectura correcta combina precio, CVD, order book, liquidaciones, basis, OI y contexto diario.

## 4. Barra superior

- BTC, ETH, SOL: cambia el simbolo activo.
- Px: ultimo precio recibido por streaming.
- Delta 5s: delta reciente. Ayuda a ver agresion inmediata.
- Book: imbalance y spread del order book.
- Data: calidad de datos por venues spot, futuros y book.
- Punto de conexion: indica si el stream esta vivo.
- Manual: manual tecnico de instalacion y operacion.
- Guia uso: este documento en PDF.

Si los datos no cambian durante varios minutos, revisa Pipeline. Si Pipeline sigue ok, puede ser una pausa de mercado/flujo; si aparece degraded, hay que revisar servicios o conectividad externa.

## 5. Tarjetas de resumen

Las tarjetas superiores condensan la foto del simbolo activo:

- Precio: ultimo precio consolidado y direccion corta.
- Scalp: comparacion Long / Short y estado operativo.
- CVD diff 24 h: diferencia entre presion spot y futuros.
- Basis: distancia entre perpetuo y spot.
- Whale: intensidad institucional detectada en spot.
- OI: open interest y cambio de 24 horas.
- Spread: costo/friccion de entrada.
- Liq 5 m: liquidaciones long y short recientes.
- BTR 15 m: buy-trade ratio de corto plazo.

Lectura rapida:

- Long score alto con book sano, spread bajo y CVD spot apoyando puede indicar impulso comprador util.
- Short score alto con futuros agresivos, spot debil y OI subiendo puede indicar presion bajista.
- Scores altos con book missing, stale o spread alto deben tratarse como No Trade.

## 6. Scalp score

El panel Scalp score resume una lectura de ejecucion rapida:

- Long: fuerza agregada de condiciones alcistas de microestructura.
- Short: fuerza agregada de condiciones bajistas.
- Estado: lectura operativa, por ejemplo Long Watch, Short Watch o No Trade.
- Razon: explica por que el sistema da ese estado.

Regla practica:

- No operes solo porque Long o Short sea alto.
- Exige que el book este fresco, el spread sea razonable y Data este ok.
- Si el sistema dice No Trade, interpreta que falta calidad de ejecucion o hay conflicto de senales.

## 7. Alertas activas

Las alertas P1/P2 destacan condiciones que pueden invalidar una entrada:

- P1: alerta critica. Normalmente implica esperar.
- P2: alerta importante. Requiere confirmacion extra.

Ejemplos:

- Order book no confiable: no usar lectura de imbalance.
- Spread alto: evita entradas finas de scalp.
- Book stale: el precio puede estar vivo, pero la profundidad no.

## 8. Niveles rapidos

Este panel resume niveles relevantes como VWAP, precio de referencia, spread e indicadores cercanos. Sirve para ubicar si el precio esta reaccionando sobre una zona tecnica de microestructura.

Uso sugerido:

- Si el precio esta lejos de VWAP y el CVD no confirma, evita perseguir.
- Si el precio prueba VWAP con absorcion y book apoya, busca confirmacion en delta matrix.

## 9. Matriz delta

La matriz delta compara flujo spot contra futuros en ventanas cortas. Es una de las lecturas mas importantes para separar impulso real de movimiento apalancado.

Interpretacion:

- Spot positivo y futuros positivos: compra amplia.
- Spot positivo y futuros negativo: spot absorbe o acumula mientras futuros presionan.
- Spot negativo y futuros positivo: posible long apalancado sin soporte spot.
- Diff creciente: spot domina futuros.
- Diff decreciente: futuros dominan spot.

No uses una sola ventana. Busca consistencia entre segundos, minutos y el contexto de 15 minutos.

## 10. Absorcion

Absorcion compara delta contra movimiento de precio. Detecta casos donde entra volumen agresivo pero el precio no avanza proporcionalmente.

Lecturas utiles:

- Delta comprador alto con poco avance: posible absorcion vendedora.
- Delta vendedor alto con poco retroceso: posible absorcion compradora.
- Delta y precio avanzando juntos: impulso mas limpio.

La absorcion es una senal de contexto, no una orden. Se confirma con order book, CVD y liquidaciones.

## 11. Order book

El panel order book muestra spread, imbalance L1/L5/L10 y paredes cercanas.

Campos clave:

- Spread: si es alto, la ejecucion se encarece.
- L1: presion inmediata.
- L5/L10: profundidad mas estable.
- Wall Up: liquidez por encima.
- Wall Down: liquidez por debajo.

Lectura practica:

- Imbalance comprador con spread bajo puede apoyar largos.
- Imbalance vendedor con spot debil puede apoyar cortos.
- Paredes visibles pueden actuar como zonas de freno o imanes de precio.

## 12. Liquidaciones RT

Muestra liquidaciones recientes por ventanas de 1, 5 y 15 minutos.

Interpretacion:

- Muchas liquidaciones short pueden acompanar squeezes al alza.
- Muchas liquidaciones long pueden acompanar capitulaciones o barridas bajistas.
- Si el precio no continua despues de liquidaciones grandes, puede haber absorcion.

No persigas liquidaciones tardias. Usalas para entender si el movimiento fue forzado o si aun tiene continuidad.

## 13. Basis perp-spot

Basis mide la diferencia entre perpetuo y spot.

Lecturas:

- Basis positivo: perpetuo por encima del spot, apetito long/apalancado.
- Basis negativo: perpetuo por debajo del spot, presion o descuento en perp.
- Basis extremo con OI creciente puede indicar exceso de apalancamiento.

Cuando basis se expande demasiado sin soporte spot, aumenta el riesgo de reversa.

## 14. Senales recientes

La tabla de senales recientes guarda snapshots del motor scalp:

- Hora: momento de la lectura.
- Estado: clasificacion operativa.
- Long / Short: puntajes.
- Book: calidad del order book.

Uso:

- Busca persistencia. Una senal repetida durante varios snapshots pesa mas que una senal aislada.
- Si el estado cambia rapidamente Long/Short, considera el mercado conflictivo.

## 15. Niveles de liquidacion

Agrupa liquidaciones por zona de precio. Ayuda a detectar clusters donde el mercado puede reaccionar.

Uso:

- Clusters arriba pueden actuar como objetivos si el precio rompe al alza.
- Clusters abajo pueden actuar como objetivos si el precio rompe a la baja.
- Clusters grandes cerca del precio requieren mas cuidado con entradas tardias.

## 16. Graficas principales

Precio:

- Confirma estructura y reaccion a niveles.
- No debe leerse sin CVD y order book.

CVD spot vs futuros:

- Spot muestra flujo mas organico.
- Futuros muestra agresion apalancada.
- Diff muestra cual domina.

Open Interest:

- OI subiendo con precio subiendo puede indicar construccion long.
- OI subiendo con precio bajando puede indicar construccion short.
- OI cayendo durante movimiento fuerte puede ser cierre de posiciones, no necesariamente entrada nueva.

Whale delta:

- Mide participacion institucional aproximada en spot.
- Su lectura es mas util como filtro de contexto que como trigger.

## 17. Lecturas combinadas

El panel Lecturas combinadas resume setups interpretativos. Tratalos como escenarios, no como instrucciones.

Ejemplos:

- Distribucion encubierta: precio sostiene, pero spot institucional se debilita.
- Acumulacion silenciosa: spot compra sin gran expansion de precio.
- Squeeze de shorts: liquidaciones short, futuros presionados y book favorable.
- Euforia o techo corto: basis/OI excesivo, spot no acompana.
- Capitulacion o suelo corto: liquidaciones long, ventas agresivas absorbidas.

La mejor lectura aparece cuando el setup coincide con Scalp score, CVD, book y contexto diario.

## 18. Contexto diario NYSE

Este panel agrega informacion por sesion. Sirve para separar ruido intradia de sesgo mayor.

Observa:

- Cambio porcentual de precio.
- CVD spot y futuros.
- Diff diario y acumulado.
- Whale delta.
- Cambio de OI.
- Funding promedio.

Uso:

- Si el intradia va contra el sesgo diario, reduce confianza.
- Si el intradia confirma el sesgo diario, la lectura tiene mas continuidad.
- Festivos y medias sesiones pueden distorsionar la lectura diaria.

## 19. Pipeline

Pipeline muestra salud de los servicios:

- api: FastAPI responde.
- ingest: REST de Coinalyze esta actualizando snapshots.
- ws: WebSockets spot activos.
- scalp: WebSockets futuros, book, liquidaciones y senales.
- daily: agregacion diaria.

Estado ok significa que no faltan servicios criticos ni simbolos. Si aparece degraded:

1. Espera uno o dos ciclos.
2. Recarga el panel.
3. Revisa si el lag de algun servicio supera el umbral.
4. Si persiste, revisar logs systemd del servicio indicado.

## 20. Rutina operativa recomendada

1. Confirmar Data ok y Pipeline ok.
2. Elegir simbolo.
3. Leer Precio, Scalp score, Spread y Book.
4. Revisar Matriz delta y Absorcion.
5. Confirmar con CVD spot vs futuros.
6. Revisar OI, Basis y Liquidaciones.
7. Ver contexto diario NYSE.
8. Solo entonces formar un escenario.

Si dos bloques principales se contradicen, baja confianza. Si tres o mas bloques coinciden, el escenario es mas robusto.

## 21. Uso con Telegram

El Bridge de Telegram permite consultar analisis bajo demanda.

Comandos:

- /status: estado del sistema.
- /usage: uso del Bridge/IA.
- /preview BTC: payload de contexto sin IA.
- /preview ETH: payload de contexto sin IA.
- /preview SOL: payload de contexto sin IA.
- /chatgpt-lite ETH: analisis breve.
- /chatgpt ETH: analisis normal.
- /chatgpt-pro ETH: analisis mas profundo.

Uso sugerido:

- Usa /status antes de pedir analisis.
- Usa /preview cuando quieras auditar datos crudos.
- Usa /chatgpt-lite para lectura rapida.
- Usa /chatgpt-pro solo cuando el mercado justifique mayor detalle.

## 22. Problemas comunes

Pagina abre pero no hay datos:

- El navegador puede estar cacheando JavaScript. Usa Ctrl+F5.
- Verifica que /api/symbols responda.
- Revisa API_INTERNAL_ALLOWED_CIDRS si el navegador entra desde una red nueva.

401:

- Credenciales Basic Auth incorrectas.

403:

- IP fuera del allowlist de nginx o de la API interna.

Pipeline degraded:

- Revisa el servicio con lag alto.
- Verifica conectividad externa hacia Coinalyze, Binance o Bybit.

Book missing o stale:

- No usar senales de book.
- Evitar scalp fino hasta que vuelva a ok.

## 23. Criterios de buena lectura

Una lectura de alta confianza normalmente tiene:

- Data ok.
- Pipeline ok.
- Book fresco.
- Spread bajo.
- CVD spot y futuros sin contradiccion fuerte.
- OI y basis coherentes con el escenario.
- Liquidaciones que explican el movimiento, no que lo contradicen.
- Contexto diario compatible.

Una lectura de baja confianza normalmente tiene:

- Pipeline degraded.
- Book stale.
- Spread alto.
- Scalp score cambiante.
- CVD spot contra futuros.
- Basis extremo sin soporte spot.
- Liquidaciones tardias despues de una vela extendida.

## 24. Recordatorio final

El Dashboard ayuda a ordenar informacion. No reemplaza gestion de riesgo, plan de entrada/salida ni control emocional. Si el panel no esta claro, la lectura correcta suele ser esperar.
