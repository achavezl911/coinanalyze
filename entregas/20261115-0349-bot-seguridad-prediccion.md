# BOT-SEGURIDAD · prediccion, escrita ANTES de tocar nada (rama claude/bot-seguridad sobre main@1a8d5e3)

Arbol: repo de 143. Fuente de lo que espero: las revisiones de claude/bot-fable (A1-A6) y claude/bot-fable2 (V2), y mi
lectura de app/bot/ en main. Cada prueba nueva va con dobles (sin red, sin base) y debe FALLAR en main por el defecto.

- B1 · en main, un «stop cerca» con Telegram caido se marca dado igual: 1 intento y 0 reintentos (tics [1, 0, 0]). En
  la rama espero [1, 1, 0] o mejor: reintenta hasta que sale y despues no repite. `carga()` relee de bot_evento los
  avisos SIN mirar `enviada`: tambien hay que filtrar ahi, o un reinicio vuelve a callar lo que no salio.
- B2 · en main, con SOL 300 min atrasado y BTC/ETH al dia, el centinela no ve ninguna rafaga de NINGUNO y da
  «velas» por bueno. En la rama: BTC y ETH siguen con su «hasta»; SOL avisa una vez (retraso > 10 min) y /estado lo dice.
  Sin columna nueva: el aviso va como evento `vigia` (el CHECK de bot_evento es cerrado y no lo amplio).
- B3 · en main HORA_SQL no mira simbolo ni venue: un minuto sin filas de SOL en una hora con filas de BTC vale 0. En la
  rama: «sin dato». La retirada entra en el JSON como clave aparte; la identidad de la candidata (sha de `congeladas`)
  NO cambia, asi las filas de bot_sombra siguen siendo suyas. Espero tener que tocar test_bot_sombra.py:29 y el NUEVA de
  K119-control (hashean el fichero entero): lo dire.
- B4 · en main el veredicto «solo lectura» no caduca, y un `null` en query-api o position/list lanza AttributeError y
  tumba el tic (sin avisos de stop). En la rama: >2 h sin lectura buena -> «clave sin verificar desde HH:MMZ», un
  aviso; el JSON raro es lectura fallida y `seguridad` sigue con las ultimas posiciones.
- B5 · en main el /calc por omision (10 USD x 50, stop 0.6 %) SIEMPRE avisa de que pasa del maximo (3.51 > 3). En la
  rama el tamano sale del riesgo: perdida al stop con 2 x 5.5 pb <= 3.6 USD tras redondear el paso hacia abajo. Espero
  que test_bot.py:37 (la forma de Alejandro) y las de calc de :47/:54 dejen de ser ciertas.
- B6 · no existe /prueba: la prueba falla por respuesta ausente (va a Opus).
- B7 · ci.yml sin `permissions` ni guarda de fork: lo compruebo leyendo el YAML, no hay prueba de python que lo ejecute.
- E1/E2 · no hay vela diaria cableada en el bot (centinela.py solo lee 1min): las pruebas fallan por ImportError. No se
  aun si la ingesta sella las velas `daily` por su inicio o su cierre: lo leo en app/ antes de escribir E1.

NO SE SABE antes de medir: si la ingesta escribe `4hour`/`daily` para los tres activos en el mismo simbolo que 1min, y
cuanto cuesta en tiempo el paso 4 (el commit de ARQUITECTURA pasa a veces de 120 s).
