# Coinalyze Operator Dashboard v1.5.0 · laboratorio de order-flow y derivados

Un laboratorio de lectura de mercado para **BTC, ETH y SOL**: recoge cada operación y el libro
de órdenes de nueve mercados, los derivados (open interest, funding, liquidaciones) y el flujo
spot contra perpetuos, y lo enseña en cuatro pantallas web y un bot de Telegram. **No ejecuta
órdenes** y no tiene ninguna ruta para hacerlo: todas sus rutas web son de lectura
([`ARQUITECTURA/INDICE.md`](ARQUITECTURA/INDICE.md)).

La versión de paquete (`pyproject.toml`) sigue en 1.5.0; lo que ha cambiado desde entonces está
en el código y en los commits. El historial de versiones v1.0–v1.5.0, entero, está en
[`docs/HISTORIAL.md`](docs/HISTORIAL.md).

## Dónde mirar primero

| si quieres saber… | mira |
|---|---|
| qué rutas hay y qué lee cada una | [`ARQUITECTURA/INDICE.md`](ARQUITECTURA/INDICE.md) → `ARQUITECTURA/rutas/<ruta>.md` |
| qué tablas hay, quién las escribe y qué rutas las leen | [`ARQUITECTURA/TABLAS.md`](ARQUITECTURA/TABLAS.md) |
| qué se rompe si tocas una función o una tabla | [`ARQUITECTURA/IMPACTO.md`](ARQUITECTURA/IMPACTO.md) |
| el esquema de la base | [`sql/schema.sql`](sql/schema.sql) |
| cómo se comprueba todo | `harness/checks/`, `tests/`, [`.github/workflows/`](.github/workflows) |

`ARQUITECTURA/` **se regenera desde el código** (`harness/bin/arquitectura`) y un check
(`K88`) se pone ROJO si lo commiteado no coincide: es la descripción que no puede quedarse vieja
([`ARQUITECTURA/LEEME.md`](ARQUITECTURA/LEEME.md)). `docs/` guarda la documentación de la época
1.x; donde contradiga al código, manda el código.

## Las pantallas

Las sirve `app/api.py` (funciones `index`, `mesa`, `panel`, `flujo`, `libro`) desde `static/`.

- **`/mesa`** (y `/`, que sirve los mismos bytes) — la mesa de operación
  ([`static/mesa.html`](static/mesa.html), `static/mesa/`). Marco *scalp / swing / largo* y
  activo en la URL (`#scalp/BTC`). Arriba, *scan* (lo que pide atención); debajo, **DECIDE**:
  la lectura del operador con su confianza y su edad, que se pinta primero con una sola
  petición a `/api/mesa/decide`; después la matriz de delta por horizonte, *follow* (los
  setups que se siguen) y *learn* (el replay, donde lo sabido en t0 nunca se mezcla con el
  resultado). En `#<marco>/<activo>/entradas` están los planes de entrada (abajo).
- **`/panel`** — el panel anterior ([`static/index.html`](static/index.html), `static/app.js`),
  entero: mesa, coste de estar dentro (funding), estructura, flujo, derivados, calidad de
  datos, replay y validación, contexto y, aparte, liquidez y ejecución.
- **`/flujo`** — el footprint ([`static/flujo.html`](static/flujo.html), `static/flujo/`, sobre
  `/api/orderflow/footprint`): por vela y nivel de precio, el volumen del agresor comprador y
  vendedor, delta, desequilibrios y apilados, POC y value area; perfiles de sesión, compuesto,
  dinámico y fijo, VWAP con bandas, TPO, indicadores y la cinta. Una vela a la que le faltan
  minutos se marca INCOMPLETA y una que nadie escuchó, HUECO: no se rellenan.
- **`/libro`** — el libro de órdenes ([`static/libro.html`](static/libro.html), `static/libro/`):
  la escalera en vivo (por websocket o, si no pasa, cada segundo) y el mapa de liquidez en el
  tiempo, con una capa honda más lejos del precio. Lo que ningún venue conoce se pinta como
  DESCONOCIDO, no como cero.

En `/flujo` y `/libro` las familias de mercado **no se suman** entre sí: perpetuos USDT, spot
USDT, Coinbase (USD) y Deribit, cada una por su lado, porque cotizan en monedas distintas.
Cada pantalla trae su propia ayuda («El ratón y el teclado», «Lo que se ve»).

## La API y su puerta

FastAPI en [`app/api.py`](app/api.py), con familias `/api/orderflow/*`, `/api/libro/*`,
`/api/scalp/*`, `/api/signals/*`, `/api/mesa/*`, `/api/entradas`, `/api/ai/*` y una ficha por
ruta en `ARQUITECTURA/rutas/`. Escucha solo en la máquina local; quien llega desde fuera pasa por
nginx con TLS y autenticación ([`deploy/nginx/coinalyze.conf`](deploy/nginx/coinalyze.conf)), y
la API exige además un token interno en cada petición (`valid_internal_token`). Swagger/OpenAPI
está deshabilitado.

## Colectores y tablas

Cada colector es un proceso aparte con su unidad systemd (`deploy/systemd/`, `deploy/140/`):

| proceso | qué recoge | tablas principales |
|---|---|---|
| `app.ingest` | API REST de Coinalyze cada 60 s: velas, OI, funding, liquidaciones, long/short | `ohlcv`, `open_interest`, `oi_bybit`, `funding_rate`, `liquidations` |
| `app.ws_collector` | operaciones spot de Binance y Bybit por websocket | `spot_trades_agg`, `spot_trades_realtime` |
| `app.scalp_collector` | operaciones de futuros, libro y liquidaciones en tiempo real | `futures_trades_*`, `orderbook_snapshot`, `liquidations_realtime`, `scalp_signal_snapshot` |
| `app.daily_agg` | sesiones diarias y velas diaria/4 h | `daily_session_agg`, `daily_verdict*` |
| `app.orderflow` | cada operación de nueve mercados (spot y perpetuos de Binance, Bybit y OKX, Coinbase spot, Bitget USDT, Deribit) | `orderflow_celda`, `orderflow_cinta`, `orderflow_grande`, `orderflow_cobertura` |
| `app.libro` | el libro de esos nueve mercados, reconstruido en local; foto cada pocos segundos | `libro_foto`, `libro_cobertura`, `libro_honda` |

Lo que no se escuchó **no se inventa**: los minutos sin cobertura completa se apuntan en
`data_gap` y nunca se rellenan (docstrings de `app/orderflow.py` y `app/libro.py`). La salud de
cada proceso va a `pipeline_heartbeat` y `market_feed_health`. El catálogo completo, con quién
escribe cada tabla, está en `ARQUITECTURA/TABLAS.md`.

## Planes de entrada

`app/entradas/` genera, de forma mecánica, PLANES de entrada en largo y en corto con reglas
versionadas en `config/entradas/reglamento.json`. Cada plan se apunta en un registro
(`entrada_registro`, solo-añadir: un disparador rechaza UPDATE, DELETE y TRUNCATE)
**antes** de saber cómo acaba, y su resultado se resuelve
después (`entrada_resultado`); se leen en la mesa, en `#<marco>/<activo>/entradas`. No son una
señal ni una orden.

## El bot de Telegram

`app/bot/` (`python -m app.bot`, unidad `deploy/140/coinalyze-bot.service`):

- **centinela** (`centinela.py`) — detecta ráfagas en las velas de 1 min de BTC, ETH y SOL y avisa.
- **evaluación** — lee la posición abierta en el exchange y da un veredicto (A FAVOR, EN CONTRA,
  NO EVALUABLE) con los datos del laboratorio; las cuentas de cada posición las reconstruye
  `vidas.py`.
- **riesgo** (`calc.py`) — calculadora del tamaño de una operación a partir de la pérdida
  máxima hasta el stop, con comisiones y precio de liquidación.
- **sesgo** (`sesgo.py`) — el contexto diario de cada activo sobre velas cerradas. Es contexto,
  no una entrada.
- **sombra** (`sombra.py`) — cuenta en vivo una candidata congelada, sin avisar por defecto.

La clave del exchange es de **solo lectura**: `app/bot/bybit.py` solo hace GET a una lista
cerrada de rutas, ninguna de órdenes, retiros ni transferencias, y lee los permisos de la clave
en vez de probarlos (lo comprueba `tests/test_bot.py`). **El bot no da entradas** mientras no
haya una ventaja medida, y hoy no la hay (`ENTRADAS` en `app/bot/servicio.py`). Un proceso
aparte, `app/bot/vigia.py`, avisa por otro canal si el bot cae.

## El arnés

`harness/checks/` son comprobaciones ejecutables contra el sistema vivo. Cada una sale con
**tres estados**: 0 VERDE, 1 ROJO (medido) y 2 NO MEDIDO (no pudo medir), porque un check que no
pudo medir no es un fallo medido. `harness/bin/verify` las corre todas y cuenta. Los
`*-control.bash` / `*-control.py` son los controles de los checks: plantan el fallo y comprueban
que el check lo condena (y que no condena el sistema sano). `harness/hooks/` tiene el
pre-commit, que entre otras cosas no acepta un `ARQUITECTURA/` que no cuadre con
`arquitectura --comprueba`.

## CI y despliegue

- **CI** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)), en cada push y pull request:
  ruff, compilación, pytest contra una base desechable con `sql/schema.sql`, las pruebas de
  JavaScript (`tests/js/`) y checks del arnés.
- **Despliegue** ([`.github/workflows/deploy-production.yml`](.github/workflows/deploy-production.yml)):
  **solo manual** (`workflow_dispatch`), solo desde `main` y con un texto de confirmación.
  El envoltorio [`deploy/140/deploy-coinalyze`](deploy/140/deploy-coinalyze) baja de GitHub el código del commit (no se fía del artefacto), respalda la base,
  aplica el esquema **antes** de cambiar de release, prueba humo y, si falla, vuelve solo al
  release anterior.

## Respaldos

Un respaldo completo cifrado cada día y un volcado de la base antes de cada despliegue, con poda
por edad de cada clase ([`scripts/backup.sh`](scripts/backup.sh); la poda la prueba
`tests/test_poda_respaldos.py`), y un archivo horario, verificado y con manifiesto, del
historial fino (`deploy/nodo/`). Un check del arnés (`K01b`) restaura el respaldo cifrado de
verdad y lo cuadra contra la base viva.

## El método

- **Encargos.** El trabajo llega como encargos con un criterio de ROJO a VERDE: primero se
  escribe el check y se ve ROJO, después se arregla. Cada encargo deja su entrega en
  [`entregas/`](entregas).
- **Predicción sellada.** Antes de medir, se commitea lo que se espera ver
  (`entregas/*-prediccion.md`) y la entrega cita ese commit: lo que salió no puede reescribir
  lo que se predijo.
- **Auditoría desde un clon.** El operador audita las entregas desde un clon del commit exacto
  que se entregó; sus hallazgos vuelven como remates del encargo.

## Desarrollo local

```bash
python3.11 -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
createdb coinalyze_dev && psql -d coinalyze_dev -f sql/schema.sql   # pytest necesita el esquema
ruff check . && TEST_DATABASE_URL=postgresql:///coinalyze_dev pytest
```
