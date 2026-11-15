# Simulador ciego (fase 2b) · rama claude/simulador-ciego sobre claude/diario-entradas@a3363bb · sin empujar

CEGUERA (app/diario/ciego.py `foto`, app/diario/proponente.py `pide`; pruebas en tests/test_diario_ciego.py)
- Solo velas CERRADAS en t (cierre de 4 h): 90 diarias, 120 de 4 h y 288 de 5 min de /root/banco-perfil.
  test_s1_foto_sin_futuro pone a 999999.9 todo lo no cerrado y la foto no cambia un byte; tocar la ultima cerrada SI.
- Anonimizada. Tiempos relativos (0 = t), sin fechas ni sellos. Activo como letra A/B/C sorteada. Precio x factor que
  lleva el ultimo cierre a [5,20]: ningun numero de la foto es un precio crudo (test). Foto real de 18.4-18.7 mil
  caracteres. La clave (activo, t, letra, factor) va a claves/; al modelo no le llega.
- `claude -p --model claude-fable-5-2`, effort medium, foto e instrucciones por STDIN. `--tools ""`, --safe-mode,
  --strict-mcp-config, --disable-slash-commands, --no-session-persistence, system prompt propio, cwd vacio, sin
  ANTHROPIC_API_KEY. Si el init de stream-json trae tools o MCP, el instante se rechaza. Probado con un doble (S2) y
  en el humo: tools [] y mcp [] en las dos llamadas.
- Se desanonimiza al sellar en diario-ciego.jsonl (aparte del diario vivo; fuente fable-ciego), con la rejilla en el
  mismo t. Se resuelve con las 5 min posteriores (resuelve.py de la fase 2); el marcador empareja por dia contra la rejilla.
COSTE MEDIDO (humo 2026-11-15 12:00Z; campo coste_usd de /srv/coinanalyze/diario-ciego/respuestas/*.json)
- ETH-1785585600: 0.1155 USD; BTC-1785672000: 0.1204 USD. Unos 8 s y 12.9 mil tokens de entrada por llamada.
  Proyeccion: 80 x ~0.118 ≈ 9.5 USD (tope 18). Limites del plan tras el humo: 5 h 0.11, 7 d 0.11.
- Humo: 3 propuestas fable-ciego y 12 de rejilla selladas. 13 resueltas; 2 pendientes por el hueco del 08-07 13:20Z.
PLAN: 80 instantes en 64 dias (16 con dos activos), 2026-08-01..11-07, semilla 20261115, a horas de cierre de 4 h;
ETH 27, SOL 27, BTC 26. `python -m app.diario ciego plan` lo imprime siempre igual.
LANZAR (root, plan Max), deploy/143/LEEME-diario.txt seccion SIMULADOR CIEGO:
  nohup .venv/bin/python -m app.diario ciego corre --dir /srv/coinanalyze/diario-ciego --tope-usd 18 > .../corrida.log 2>&1 &
Reanuda sin repedir lo sellado. El tope es el gasto ACUMULADO de la carpeta (el humo ya cuenta 0.236).

NO SE SABE
- Si el modelo reconoce el periodo por la forma del precio, la volatilidad o la hora UTC (la foto la dice).
- La apertura de 5 min: el banco no la trae y se usa el cierre anterior recortado a [l,h] (entrada a mercado, saltos de stop).
- Los huecos del banco (08-07 13:20Z, 08-14 16:40Z, 10-26 23:55Z; SOL tambien 10-22 17:10Z) dejan pendientes para siempre.
- El banco acaba el 11-12 16:05Z: lo ultimo puede quedar sin cerrar. El CLI avisa `unrecognized_model` y aun asi
  responde. Con N=80 el IC del marcador es ancho.
