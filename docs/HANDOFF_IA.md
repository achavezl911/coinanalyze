# Traspaso para IA — Coinalyze Operator Dashboard v1.3.7

Lee esto antes de tocar nada. Está escrito para que una IA (o una persona) entienda qué es
este sistema, qué se corrigió recientemente, y sobre todo **qué trampas ya se pisaron**
para no repetirlas. Todo lo que se afirma aquí se verificó contra datos reales; donde hay
incertidumbre, se dice.

---

## 1. Qué es

Dashboard interno de microestructura y scalping para perpetuos **BTC, ETH y SOL**. Corre en
el **LXC 140 (`coinalyze-final`)** del Proxmox `150.1.7.13`, IP interna `10.151.1.6`.

- Código: `/opt/coinalyze` (los servicios corren **directo del árbol**, con
  `WorkingDirectory=/opt/coinalyze`; `update.sh` además hace `pip install` en el venv).
- Config: `/etc/coinalyze/coinalyze.env` (systemd `EnvironmentFile`).
- Servicios: `coinalyze-{api,ingest,ws,scalp,daily}` + `nginx` + `coinalyze-ai-bridge`.
- PostgreSQL local. Acceso: `runuser -u postgres -- psql -d coinalyze`.
- La API exige cabecera `X-Internal-Token` (valor en el `.env`) para todo `/api/*` y
  `/metrics`. nginx la inyecta y añade Basic Auth en `:8443`.

## 2. De dónde salen los datos — **léelo, aquí se equivocó ya una IA**

| dato | tabla | fuente real |
|---|---|---|
| ohlcv, open interest, funding, liquidaciones históricas | `ohlcv`, `open_interest`, `funding_rate`, `liquidations` | **Coinalyze símbolo `.A` = BINANCE** |
| OI de Bybit | `oi_bybit` | Coinalyze `.6` = Bybit |
| trades spot | `spot_trades_agg`, `spot_trades_realtime` | WS **Binance + Bybit** spot |
| trades futuros, libro, liquidaciones en vivo | `futures_trades_*`, `orderbook_snapshot`, `liquidations_realtime` | WS **Binance + Bybit** futuros |

> **`.A` NO es un agregado multi-venue. Es Binance.** El código antiguo lo etiquetaba
> `coinalyze_aggregate` y eso indujo a error. Verificación: `/v1/exchanges` de Coinalyze
> devuelve `.A=Binance, .3=OKX, .4=Huobi, .6=Bybit, .Y=Gate.io, .S=Aster, .T=Lighter`; y
> `open_interest`(.A) = 6.90 B == OI real de Binance, `oi_bybit`(.6) = 3.65 B == Bybit.
> Hay un test (`test_no_module_still_claims_the_futures_leg_is_a_multi_venue_aggregate`)
> que falla si alguien vuelve a escribir "agregado" o "todos los venues" en `app/`.

### El sesgo del diferencial spot−futuros

`cvd_diff_usd = cvd_spot_usd − cvd_fut_usd` resta **spot de 2 venues** menos **futuros de
Binance**. Medido sobre 90 sesiones × 3 monedas:

- la pata de futuros pesa **4.8–5.9×** más
- `sign(diff) == −sign(cvd_fut)` en **92–95%** de las sesiones
- coincide con lo que hizo el spot solo en **30–36%** (peor que una moneda)

**La causa NO es un desajuste de venues; es que el perp mueve ~10× el spot** ($9.7 B vs
$1.0 B/24 h en BTC). Consecuencia práctica: `cvd_diff_2v_usd` (ambas patas en
Binance+Bybit) alinea venues pero **no corrige la asimetría de escala**. Lo escala-libre
sería normalizar cada pata por su propio volumen — **no está hecho**.

**Nunca leas el diferencial como "acumulación spot".** Para eso está `cvd_spot_usd` y su
acumulado. El panel clasifica por el signo de **ambas** patas (`flowQuadrant` en `app.js`):
acumulación / distribución / "solo cambió la magnitud".

## 3. Retención — condiciona qué se puede calcular

| tabla | retención | implicación |
|---|---|---|
| `daily_session_agg` | **infinita** (`DAILY_SESSION_RETENTION_DAYS=0`) | ~390 sesiones/símbolo desde 2025-07-09. **Es la única historia larga.** |
| `daily_verdict` | infinita | veredictos del modelo, desde 2026-08-02 |
| `ohlcv` 1min, OI, funding, `spot_trades_agg` | 14 días | detalle intradía |
| `ohlcv` daily | **730 días** | memoria estructural/análogos de 2 años; ~2,200 filas para 3 símbolos |
| `ohlcv` 5min | **400 días** | fuente compacta para pivotes 4h; no se infla a 2 años innecesariamente |
| `futures_trades_agg` | **36 h** (`SCALP_MINUTE_RETENTION_HOURS`) | subido a propósito para que el job diario cubra una sesión de 24 h |
| `futures_trades_realtime`, `liquidations_realtime` | 12 h | |
| `spot_trades_realtime` | 2 h | |
| `orderbook_snapshot` | 6 h | |
| `metrics_snapshot` | 30 días | |
| `scalp_signal_snapshot` | 72 h | **la capa scalp no es backtesteable** |

`spot_trades_agg` va **~250–300 s atrasado** (ventana de trades tardíos de 125 s + ciclo de
volcado) contra ~60 s de `ohlcv`. Por eso las divergencias intradía se anclan al último
minuto con **ambas** series, no a `now()`.

La columna **`inst_delta_usd` (whale) está vacía**: 1 de 390 sesiones en BTC. Los umbrales
por trade (5 M BTC / 1 M ETH / 200 k SOL) casi nunca se cruzan con dos venues. Se retiró
del dashboard. No la uses.

## 4. Qué se hizo en esta ronda (v1.3.1 → v1.3.7)

**v1.3.2 — auditoría.** `/metrics` devolvía 500 desde hacía versiones (`KeyError: 'detail'`:
el `SELECT` no pedía la columna que el render usaba) y el smoke test solo probaba 3
endpoints. El `.tar.gz` de despliegue traía solo `app/static/tests`, y como `update.sh` hace
`rsync --delete`, usarlo como decía el README borraba `sql/`, `deploy/`, `scripts/` y
abortaba. Además: `trend_matrix` medía el OI de `1d`/`3d` sobre ~60 sesiones; dos
definiciones distintas de "absorción"; lags saliendo como string en el JSON.

**v1.3.3 — semántica del flujo.** Panel "Flujo por sesión" clasificando por ambas patas;
`cvd_diff_2v_usd`; tabla `daily_verdict`; percentiles condicionales; `/api/divergences`
(15 ventanas: 9m→16h intradía y 1d→6 semanas por sesión); rollup diario ampliado;
procedencia y percentiles en la tabla diaria.

**v1.3.4 — procedencia y contexto para IA.** Corrección de `.A` (ver §2); arreglo de
`oi_context.by_venue` (publicaba `other_venues = total − bybit` describiéndolo como "todos
los venues menos Bybit"; era Binance − Bybit); nuevo bloque **`daily_history`** y perfil
**`max`**.

**v1.3.5 — interpretación CVD 90 sesiones.** Nuevo `cvd_swing_90d`: compara el rango
empírico del CVD spot y del retorno de precio de 3 sesiones contra las 90 sesiones
anteriores, opera un horizonte de 2 sesiones y se autoevalúa walk-forward. El panel lo
cruza con estructura, swing, divergencias, setup y calidad de datos. Los setups y la racha
diaria dejaron de usar el diferencial dominado por futuros y ahora usan CVD spot. También
se corrigió `current_nyse_start`: en cripto los fines de semana son sesiones normales, no
una ventana continua desde el viernes.

**v1.3.6 — barreras y volumen de ruptura.** Nuevo `/api/price-barriers`, también en
`dashboard/state` y el contexto IA. Agrupa pivotes 4h/diarios en zonas y puntúa dificultad
por toques, reacción ATR, volumen relativo, absorción CVD y recencia. La capa viva compara
volumen perp de 15m con su mediana de 36h y combina delta, desplazamiento y book L5. El
score no es probabilidad ni revela órdenes ocultas: una ruptura exige cierre 15m y retest.
Para sostenerlo se guardan velas 5min durante 400 días y existe un backfill idempotente.
Después del backfill, las velas recientes se consolidan localmente desde 1min; no consumen
una llamada adicional a Coinalyze en cada ciclo ni elevan el riesgo de HTTP 429.

**v1.3.7 — arquitectura de decisión y memoria 2Y.** La portada cruza los algoritmos ya
existentes en tres horizontes y obliga a declarar confirmación/invalidation. Las secciones
son vistas exclusivas con carga bajo demanda; se retiraron alertas scalp desfasadas y
duplicados visuales. `market_memory_2y` conserva 730 velas diarias y compara cinco episodios
no solapados mediante distancia robusta sobre retorno, rango/drawdown, volatilidad y volumen.
Informa qué ocurrió a 5/10/20 días, pero su salida es analogía descriptiva, no probabilidad.
El CVD táctico sigue usando 90 sesiones. Además se corrigió funding: `0.005` en Coinalyze
significa `0.005%`, no `0.5%`.

### El payload para IA

`GET /api/ai/context/bundle?profile=max` → **~446 KB, ~106 k tokens**, 3 símbolos × 37
bloques, con 90 sesiones de `daily_history` cada uno.

| perfil | sesiones diarias | divergencias intradía | uso |
|---|---|---|---|
| `lite` | 0 | no | `/chatgpt-lite` |
| `default` | 0 | no | `/chatgpt`, alertas automáticas |
| `pro` | 30 | sí | `/chatgpt-pro` |
| `max` | 90 | sí | **`/preview`** → documento JSON en Telegram, para pegar en una IA web |

El bridge (`/opt/coinalyze-ai-bridge`) **no recorta** el `ai_context`:
`summarize_for_prompt` lo deja pasar íntegro si `schema_version` empieza por `ai_context`.
`/preview` no gasta tokens de OpenAI y entrega el JSON como documento único cuando supera
los 4096 caracteres de Telegram (límite de documento: 50 MB).

## 5. Trampas ya pisadas — no las repitas

1. **`update.sh` que se ejecuta es el de `/opt/coinalyze`, no el del paquete.** Cualquier
   corrección al propio `update.sh` surte efecto **una versión después**. Esto ya borró
   `.deploy-backups` una vez (se recuperó del backup cifrado).
2. **Editar `.py` desde Windows con Python los convierte a CRLF.** Normaliza a LF antes de
   empaquetar o el diff sale de miles de líneas.
3. **`.context-grid` es de 12 columnas: todo panel nuevo DEBE declarar `grid-column`** o cae
   a `span 1` y sale aplastado.
4. **Repintado**: `refresh()` corre cada 15 s. Toda función `render*` debe **reemplazar** su
   contenedor, no hacer `append`. Un `replaceChildren()` dentro de una guarda de salida
   temprana **no cuenta**. Hay test que lo vigila.
5. **El bridge se instala como COPIA en site-packages**: tras editar
   `/opt/coinalyze-ai-bridge/src` hay que `pip install --no-deps .` y reiniciar.
6. **No pongas texto dentro del SVG de las barras**: usa `preserveAspectRatio="none"` y
   deforma el texto ~12×. Las etiquetas van en una rejilla HTML aparte.
7. **Verifica antes de afirmar.** El comentario `coinalyze_aggregate` llevaba versiones en
   el código y era falso. Los números están a una consulta de distancia.
8. **Aplicar `schema.sql` a la BD de producción requiere autorización del usuario** (el
   clasificador de permisos lo bloquea, y con razón). `update.sh` sí lo hace como parte de
   su flujo normal.

## 6. Límites duros — no se pueden salvar sin feeds nuevos

- Solo **2 venues** (Binance, Bybit) para trades y libro.
- Trades guardados como **agregados de 1 minuto** → sin footprint, volumen-a-precio real ni
  clusters de órdenes.
- Libro solo **L1/L5/L10** → sin profundidad, spoofing ni cancelaciones.
- Sin opciones/gamma ni on-chain. El calendario macro ya cubre CPI/NFP/PPI/JOLTS/FOMC;
  las series externas guardan 800 días. Flujos ETF BTC quedan disponibles solo cuando se
  configura `COINGLASS_API_KEY` (no se raspa una web inestable como sustituto).
- **Backtest del scalp imposible** (72 h de historia).
- Se descartó añadir **SOXL/SOXS**: los perps existen y con volumen (SOXL $1.7 B/24 h en
  Binance, más que SOL) pero **no hay mercado spot en ninguno de los dos venues**
  (`SOXLBUSDT` de Binance tiene base `SOXLB`, otro token) y Coinalyze no tiene `.A` para
  ellos. Media plataforma quedaría muerta o, peor, puntuando sobre ceros.

## 7. Pendiente / ofrecido y no hecho

- **Backtest de la capa diaria** (`scripts/backtest_daily.py`): con las ~390 sesiones,
  medir hit-rate, retorno medio e *information coefficient* por componente, y sustituir los
  pesos elegidos a mano (25/15/20/10/15/10/5). El README ya admite que no están calibrados.
  Ofrecido, el usuario lo dejó fuera. **`daily_verdict` existe precisamente para hacerlo
  posible**, pero necesita semanas de acumulación.
- **Normalizar las patas de CVD por su volumen** para que el diferencial sea escala-libre.
- **Divergencias intradía frescas**: 9m sale siempre `stale` porque `spot_trades_agg` va
  ~4 min atrasado. Se arreglaría alimentando las ventanas ≤2 h desde `spot_trades_realtime`
  (lag ~10 s, retención 2 h).
- `cvd_diff_2v_usd` solo se puebla **hacia adelante** (primera sesión con dato: 2026-08-04).
- Alerta macro edge-triggered al entrar a percentil extremo.
- El bloque intradía de divergencias solo va al perfil `pro`/`max` (cuesta ~1.9 k tokens y
  solapa con `delta_matrix`/`cvd_matrix`).

## 8. Cómo desplegar y verificar

```bash
# desde un árbol COMPLETO (update.sh aborta si falta algo: REQUIRED_PATHS)
sudo /opt/coinalyze/scripts/update.sh /ruta/al/arbol
```

Hace backup cifrado, para servicios, rsync `--delete` (excluye `.venv`, `.env`,
`.deploy-backups`), reinstala deps, aplica `sql/schema.sql`, instala units y nginx,
reinicia y **no da por bueno el despliegue hasta que pasa `scripts/smoke_test.sh`**.

Comprobación rápida:

```bash
cd /opt/coinalyze && .venv/bin/python -m pytest -q     # 132 tests (requiere extras dev)
scripts/smoke_test.sh                                   # incluye /metrics
curl -H "X-Internal-Token: $TOKEN" localhost:8000/api/healthz
```

Rollback: `/opt/coinalyze/.deploy-backups/<stamp>/app` o el backup cifrado de
`/var/backups/coinalyze` (`openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass
file:/etc/coinalyze/backup.key`; el árbol vive bajo `rootfs/` dentro del tar).

## 9. Prompt sugerido para arrancar una IA con este contexto

> Vas a trabajar sobre el Coinalyze Operator Dashboard v1.3.7 (LXC 140 en Proxmox
> 150.1.7.13). Lee `docs/HANDOFF_IA.md` completo antes de proponer nada. Reglas de la casa:
> (1) verifica contra los datos reales antes de afirmar cualquier cosa sobre procedencia o
> semántica — en este proyecto ya se propagó un error por fiarse de un comentario;
> (2) nunca presentes un número sin su universo de venues y su frescura; (3) si un dato no
> existe, devuelve `unavailable`, jamás cero — el sistema puntúa sobre lo que recibe y un
> cero se convierte en una señal falsa; (4) cualquier función de render debe reemplazar su
> contenedor, no acumularlo; (5) tras cambiar código, corre `ruff` y los 132 tests, y
> verifica contra la BD viva antes de desplegar.
