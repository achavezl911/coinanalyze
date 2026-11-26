# Coinalyze Operator Dashboard v1.5.0 · laboratorio de order-flow y derivados

Coinalyze es un laboratorio de lectura de mercado para **BTC, ETH y SOL**. Recoge cada operación
y el libro de órdenes de nueve mercados, los derivados (open interest, funding, liquidaciones) y
el flujo spot contra perpetuos; lo guarda en PostgreSQL sin inventar lo que no escuchó, y lo
enseña en pantallas web y en un bot de Telegram. **No ejecuta órdenes** y no tiene ninguna ruta
para hacerlo: todas sus rutas web son de lectura ([`ARQUITECTURA/INDICE.md`](ARQUITECTURA/INDICE.md)).
La versión de paquete (`pyproject.toml`) sigue en 1.5.0; el historial v1.0–v1.5.0 está en
[`docs/HISTORIAL.md`](docs/HISTORIAL.md) y lo posterior, en los commits y en [`entregas/`](entregas).

## Lo que este sistema no hace

**Describe, no predice.** Las mediciones fuera de muestra, con el protocolo commiteado antes de
mirar el resultado (liquidaciones y libro diarios a 1–3 días, flujo e interés abierto a 1 h,
reglas de barrera a 15 min–1 h, sobre BTC, ETH y SOL), **no han encontrado ninguna regla con
ventaja direccional después de costes**. Por eso el bot no da entradas, los planes de entrada se
registran para medirse y no para seguirse, y las cifras de acierto que publica la API se marcan
como cota optimista cuando lo son.

## Dónde leer más

| si quieres saber… | mira |
|---|---|
| qué rutas hay y qué lee cada una | [`ARQUITECTURA/INDICE.md`](ARQUITECTURA/INDICE.md) → `ARQUITECTURA/rutas/<ruta>.md` |
| qué tablas hay, quién las escribe y qué rutas las leen | [`ARQUITECTURA/TABLAS.md`](ARQUITECTURA/TABLAS.md) |
| qué se rompe si tocas una función o una tabla | [`ARQUITECTURA/IMPACTO.md`](ARQUITECTURA/IMPACTO.md) |
| el esquema de la base | [`sql/schema.sql`](sql/schema.sql) |
| la investigación de señales (régimen, replay, walk-forward, costes) | `docs/SIGNAL_*.md`, `docs/PR2*_*.md` |
| cómo se comprueba todo | `harness/checks/`, `tests/`, [`.github/workflows/`](.github/workflows) |

`ARQUITECTURA/` **se regenera desde el código** (`harness/bin/arquitectura`) y el check `K88` se
pone ROJO si lo commiteado no coincide ([`ARQUITECTURA/LEEME.md`](ARQUITECTURA/LEEME.md)).
`docs/` guarda la documentación de la época 1.x; donde contradiga al código, manda el código.

## Datos y colectores

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
`data_gap` y nunca se rellenan. La salud de cada proceso va a `pipeline_heartbeat` y
`market_feed_health`. El catálogo entero, con quién escribe cada tabla, en `ARQUITECTURA/TABLAS.md`.

## API y pantallas

FastAPI en [`app/api.py`](app/api.py), con familias `/api/orderflow/*`, `/api/libro/*`,
`/api/scalp/*`, `/api/signals/*`, `/api/mesa/*`, `/api/entradas` y `/api/ai/*` (el contexto del
mercado en JSON, para herramientas externas). Escucha solo en la máquina local; desde
fuera se entra por nginx con TLS y autenticación ([`deploy/nginx/coinalyze.conf`](deploy/nginx/coinalyze.conf)),
y la API exige además un token interno en cada petición. La documentación interactiva está apagada.

- **`/mesa`** (y `/`) — la mesa de operación: marco *scalp / swing / largo* y activo en la URL
  (`#scalp/BTC`); *scan*, el bloque **DECIDE**, la matriz de delta por horizonte, *follow* y
  *learn* (el replay, donde lo sabido en t0 nunca se mezcla con el resultado).
- **`/panel`** — el panel anterior, entero: funding, estructura, flujo, derivados, calidad de
  datos, replay y validación, liquidez y ejecución.
- **`/flujo`** — el footprint por vela y nivel de precio, perfiles, VWAP, TPO y la cinta. Una vela
  a la que le faltan minutos se marca INCOMPLETA y una que nadie escuchó, HUECO.
- **`/libro`** — la escalera en vivo y el mapa de liquidez en el tiempo, con una capa honda; lo
  que ningún venue conoce se pinta como DESCONOCIDO, no como cero.

En `/flujo` y `/libro` las familias de mercado (perpetuos USDT, spot USDT, Coinbase en USD,
Deribit) **no se suman** entre sí. Cada pantalla trae su propia ayuda.

## Régimen y DECIDE

**DECIDE** es la lectura del operador para un activo y un marco: dirección, confianza y edad del
dato. La sirve `/api/mesa/decide` ya calculada, con las mismas funciones que el contexto completo
(`app/ai_context.py`), y la dirección que pinta se **importa** de la clasificación del registro de
señales (`app/signal_ledger.py`), para que pantalla y registro no puedan separarse. El régimen de
mercado (`app/signal_regime.py`, [`docs/SIGNAL_REGIMES.md`](docs/SIGNAL_REGIMES.md)) se mide con
lo que el sistema sabía en el instante de la decisión, no reconstruido después.

## Planes de entrada

`app/entradas/` genera, de forma mecánica, PLANES de entrada en largo y en corto con reglas
versionadas en `config/entradas/reglamento.json`. Cada plan se apunta en `entrada_registro`
(solo-añadir: un disparador rechaza UPDATE, DELETE y TRUNCATE) **antes** de saber cómo acaba, y su
resultado se resuelve después en `entrada_resultado`. Se leen en `#<marco>/<activo>/entradas`.
No son una señal ni una orden; `/api/entradas` avisa cuando una cifra medida es una cota optimista.

## Bot de Telegram (solo lectura)

`app/bot/` (`python -m app.bot`): **centinela** de ráfagas en velas de 1 min; **evaluación** de la
posición abierta en el exchange (A FAVOR, EN CONTRA, NO EVALUABLE); **riesgo**, calculadora de
tamaño con comisiones y precio de liquidación; **sesgo**, contexto diario sobre velas cerradas;
**sombra**, que cuenta en vivo una candidata congelada. La clave del exchange es de **solo
lectura**: `app/bot/bybit.py` solo hace GET a una lista cerrada de rutas, ninguna de órdenes,
retiros ni transferencias (lo comprueba `tests/test_bot.py`). **El bot no da entradas** mientras
no haya una ventaja medida (`ENTRADAS` en `app/bot/servicio.py`). `app/bot/vigia.py` avisa por otro
canal si el bot cae.

## Arnés y checks K

`harness/checks/K*` son comprobaciones ejecutables contra el sistema vivo, con **tres estados**:
0 VERDE, 1 ROJO (medido) y 2 NO MEDIDO (no pudo medir). `harness/bin/verify` las corre y cuenta.
Los `*-control.*` plantan el fallo y comprueban que el check lo condena, y que no condena el
sistema sano. El trabajo llega como encargos con criterio de ROJO a VERDE: primero el check en
ROJO, después el arreglo; cada encargo deja su entrega en [`entregas/`](entregas). El pre-commit
(`harness/hooks/`) rechaza un `ARQUITECTURA/` que no cuadre con el código.

## CI, despliegue y respaldos

- **CI** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)), en cada push y pull request:
  ruff, compilación, pytest contra una base desechable con `sql/schema.sql`, las pruebas de
  JavaScript (`tests/js/`) y checks del arnés.
- **Despliegue** ([`.github/workflows/deploy-production.yml`](.github/workflows/deploy-production.yml)):
  **solo manual** (`workflow_dispatch`), solo desde `main` y con un texto de confirmación. El
  envoltorio [`deploy/140/deploy-coinalyze`](deploy/140/deploy-coinalyze) baja el código del
  commit, respalda la base, aplica el esquema **antes** de cambiar de release, prueba humo y, si
  falla, vuelve solo al release anterior.
- **Respaldos**: uno completo y cifrado cada día y un volcado antes de cada despliegue, con poda
  por edad ([`scripts/backup.sh`](scripts/backup.sh)); el check `K01b` restaura el cifrado de
  verdad y lo cuadra contra la base viva.

## Desarrollo local

```bash
python3.11 -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
createdb coinalyze_dev && psql -d coinalyze_dev -f sql/schema.sql   # pytest necesita el esquema
ruff check . && TEST_DATABASE_URL=postgresql:///coinalyze_dev pytest
```
