# Diario de entradas en sombra · fase 2 (2026-11-15 07:47Z, rama claude/diario-entradas sobre main@f7d8da4, SIN empujar)

Arbol: repo de 143. R0: `calc.PERDIDA_MAX` ya valia 5.0 en main (app/bot/calc.py:20); tests/test_diario.py lo fija.
Corre en 143 (`python -m app.diario cuarto|diario`); de 140 solo LEE velas por harness/bin/api y deja el marcador en
/var/lib/coinalyze-bot/informes/diario-entradas.txt (camino de tools/bot/semanal.py). /entradas lo ensena; no avisa.

LIBRO (app/diario/libro.py): /srv/coinanalyze/diario/entradas.jsonl, solo-anadir, con flock. Cada linea es un JSON
canonico (claves ordenadas, sin espacios, ASCII) con `n`, `prev` (sha256 de los bytes de la linea anterior; la 0 lleva
64 ceros), `tipo`, `sello` y los campos de su tipo:
  propuesta  fuente id activo lado orden entrada stop objetivo caduca plazo_s riesgo_usd (+ porque)
  resultado  id llenada px_llenado t_llenado salida(objetivo|stop|plazo|caducada) px_salida t_salida r_neto usd_neto coste
  rechazo    fuente id motivo cruda
`verifica(ruta, cabeza)` dice que linea se toco, cuales faltan o sobran, y si hay resultados huerfanos o repetidos. La
ultima linea la protege la cabeza (n, sha256) que publica el marcador. Con el libro tocado, la corrida no escribe y da rc 2.
BUZON (app/diario/fuentes.py:15): /srv/coinanalyze/diario/buzon/*.json con
  {"formato":"diario-entradas/1","corrida":"..","propuestas":[{id,activo BTC|ETH|SOL,lado largo|corto,orden limite|mercado,
   entrada,stop,objetivo,caduca (s Unix o ISO UTC),plazo_h (240),riesgo_usd (<=5),porque}]}
Cada propuesta se sella como `fable:<id>` o se rechaza con motivo en el libro; el fichero pasa a buzon/leidos/.
PUNTA A PUNTA (x1-tmp/de2e.py; directorio temporal, ya borrado): velas reales de 140, 1999 de 5 min (11-08 09:05Z ..
11-15 07:35Z) y ~297 de 4 h por activo. Reloj plantado cada 15 min desde 11-08 12:00Z hasta 11-15 07:32Z: 655 pasadas
cuarto con rc 0 y 7 diarias. CLI `diario` rc 0. Libro intacto, n=212, sha256 605190a8e06ed883..
  libro: 132 propuestas, 79 resultados, 2 rechazos (los dos del buzon sintetico: «ya llena al sellar», «falta stop»)
  D:imp1:v0:A  3 propuestas, 1 resuelta (llenada), R -1.07
  H:imp6:v1:D  2 propuestas, 2 resueltas (llenadas), R medio +0.47; contra la rejilla +1.23 [-3.05, +3.08]
  fable        1 (sintetica, de2e-valida), resuelta en stop, R -1.07
  rejilla      126 (18 x 7 dias), 75 resueltas, 58 llenadas: R medio -0.86, -234.72 USD, 0 huecos
Fue la semana del desplome (cache de 140, x1-tmp/dsemana.py): BTC 75327 -> 61956 (-16 %), ETH -19 %, SOL -21 %.
Los largos se llenaron 55 de 55 resueltos y 54 salieron por stop (dniv.py). En cortos, 3 llenados al 2 %, los 3 al
objetivo. Contra la prediccion (entregas/20261115-0728): la rejilla esperaba R ~ -0.1 y dio -0.86; las reglas, 5 en
vez de 0-2. Una semana con tendencia castiga un lado entero (lo decia) y todas salen SIN N (<30): no mide nada.

UNIDADES (deploy/143/coinalyze-diario-*, LEEME-diario.txt): el cuarto, a los 20 s de cada cuarto de hora UTC; el dia,
a las 00:07Z (Persistent). Las instala el OPERADOR, y solo DESPUES de fusionar en main: corren el arbol de repo/.
NO SE SABE:
- Cuanto tarda la API de 140 en dar `is_closed` a la vela de 4 h: el aviso se sella a T+20 s o, si aun no llego, a
  T+15 min (la frescura admite < 1 h). Se pierde precio, no la propuesta.
- La paridad con fable-be es de la LOGICA (copia literal y banco sintetico). Las velas son de una venue de 140 y no del
  agregado del banco: una senal puede encenderse en uno y no en el otro.
- El ritmo real del buzon de Fable: nada lo escribe todavia.
- Con 143 apagado mas de ~6.9 dias (2000 velas de 5 min) quedan huecos: esas propuestas quedan PENDIENTES para siempre.
