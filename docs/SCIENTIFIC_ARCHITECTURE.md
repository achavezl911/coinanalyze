# Arquitectura científica

Cómo un tick de un exchange llega a ser —o no— evidencia confirmatoria. Este documento
describe **la arquitectura vigente en esta rama**, no un objetivo. Cada afirmación es
verificable contra el código; donde algo no existe todavía, se dice.

Léelo junto a [`PR27_CONFIRMATORY_ENDPOINT_INTEGRITY.md`](PR27_CONFIRMATORY_ENDPOINT_INTEGRITY.md),
que contiene el detalle formal, y [`HANDOFF_IA.md`](HANDOFF_IA.md), que dice qué está hecho.

## 1. La idea en una frase

Un resultado científico sólo vale si puedes demostrar **qué código lo calculó** y **qué
insumos crudos seleccionó**. Hashear la fuente responde lo primero; el contrato de runtime
responde lo segundo; y el ruteo atestiguado garantiza que el productor aplicó de verdad ese
contrato.

## 2. Vista general

```mermaid
flowchart TD
    subgraph EX["Exchanges"]
        BIN["Binance<br/>futuros + spot"]
        BYB["Bybit<br/>futuros + spot"]
        CZE["Coinalyze REST<br/>ohlcv · OI · funding"]
    end

    subgraph PROD["Productores crudos (atestiguados)"]
        SCALP["scalp_collector<br/>clave interna: symbol"]
        WS["ws_collector<br/>clave interna: base_asset"]
        ING["ingest<br/>clave = id upstream"]
    end

    subgraph RAW["Persistencia cruda"]
        FUT["futures_trades_*<br/>orderbook_*<br/>liquidations_realtime"]
        SPOT["spot_trades_*"]
        HIST["ohlcv · open_interest<br/>funding_rate"]
    end

    subgraph SCI["Capa científica"]
        CTX["scalp_context<br/>+ compute_scalp_summary"]
        OBS["signal_observation<br/>append-only"]
        REP["signal_replay_frame"]
        OUT["signal_outcome"]
        VIS["visibilidad certificada"]
        WF["walk-forward v4"]
        RES["resultado autoritativo<br/>una fila por manifest"]
    end

    BIN --> SCALP & WS
    BYB --> SCALP & WS
    CZE --> ING
    SCALP --> FUT
    WS --> SPOT
    ING --> HIST
    FUT & SPOT & HIST --> CTX
    CTX --> OBS --> REP
    OBS --> OUT --> VIS --> WF --> RES
```

`.A` en Coinalyze **es Binance**, no un agregado multi-venue. Ver `HANDOFF_IA.md` §2.

## 3. Ruteo atestiguado — el corazón de PR27

El colector no graba "el mercado ETH": graba lo que el ruteo diga, bajo una **clave
interna**. Si el ruteo miente, el kernel lee datos de otro mercado bajo la clave correcta y
nada en la fila lo delata.

```mermaid
flowchart LR
    CAT["MARKET_SYMBOL_CATALOG"] --> PROJ["4 proyecciones<br/>(región de identidad)"]
    PROJ --> MAPS["WS_SYMBOL_MAP<br/>FUTURES_PAIR_MAP<br/>SPOT_PAIR_MAP<br/>PAIR_SYMBOL_MAP"]
    CAT --> CONTRACT["scientific_runtime_contract<br/>digest de valores resueltos"]
    CONTRACT -->|"registro append-only"| GATE{"attest_raw_market_producer"}
    MAPS -->|"deben coincidir"| GATE
    GATE -->|"falla"| STOP["el proceso no produce nada"]
    GATE -->|"pasa"| ROUTING["EffectiveMarketRouting<br/>frozen, una vez por proceso"]
    ROUTING --> IDX["FuturesRoutingIndex<br/>SpotRoutingIndex<br/>valida cada conversión"]
    IDX --> SUB["URL / topics<br/>conexión"]
    IDX --> CONV["par externo → clave interna"]
    CONV --> STORE["stores en memoria"]
    STORE --> DEL["deliver_*<br/>re-atestigua + valida claves"]
    DEL --> RAWT[("tablas crudas")]
```

Cuatro barreras, cada una fail-closed:

| Barrera | Qué impide |
|---|---|
| Contrato registrado | Que el catálogo resuelto sea distinto del congelado. |
| Mapas vs. contrato | Que los dicts derivados diverjan del catálogo (hallazgo A-01). |
| Índice ligado al ruteo | Que un índice forjado convierta un par externo en una clave interna ajena (hallazgo A-02). |
| `deliver_*` | Que una fila llegue al SQL con una clave fuera del ruteo atestiguado. |

**Qué está dentro de la identidad científica**: las cuatro proyecciones, los endpoints de
venue, la construcción del índice, URL/topics, la conexión, el despacho al handler, la
conversión, la inyección del ruteo desde `main()`/`run()` y el traspaso store → entrega.
**Qué queda fuera**: reconexión, backoff, logging, health de feeds y parámetros de
transporte WS. Ambas direcciones están fijadas por tests de mutación.

## 4. De observación a outcome

```mermaid
sequenceDiagram
    participant K as kernel (scalp_logic)
    participant O as signal_observation
    participant R as signal_replay_frame
    participant U as signal_outcome
    participant C as visibilidad

    K->>O: clasifica y persiste (append-only)
    Note over O: guarda identidad + procedencia de contrato
    K->>R: frame canónico (contexto + evidencia)
    U->>U: espera ventana completa
    U->>U: data_gap bloqueante ⇒ no finaliza
    U->>C: outcome final
    C->>C: SELECT → clock PostgreSQL → INSERT
    Note over C: verified_visible_at inmutable
```

El replay recomputa la observación desde el frame y compara **campo a campo**. Cualquier
ausencia, versión no soportada, hash distinto o evidencia distinta levanta
`ConfirmatoryScientificIntegrityError` **dentro** de la transacción autoritativa, antes del
INSERT. No se convierte en cero ni en `INCONCLUSIVE`, y no se elimina del denominador.

## 5. Walk-forward confirmatorio y resultado autoritativo

```mermaid
flowchart TD
    MAN["manifest spec-v4<br/>congelado ANTES del OOS"] --> FOLDS["folds + cutoffs"]
    MAN --> FROZEN["identidad científica<br/>+ runtime contract<br/>congelados en el manifest"]
    FOLDS --> POP["población OOS<br/>certificada y visible al cutoff<br/>utc_nonoverlap"]
    POP --> REPLAY["replay batch obligatorio"]
    REPLAY --> INF["endpoint-v2 + inferencia pareada<br/>bloques · bootstrap · CI"]
    FROZEN -->|"debe reproducirse en runtime"| INF
    INF --> DEC{"maduro?"}
    DEC -->|"no"| NR["not_ready — no se persiste"]
    DEC -->|"sí"| RES["PASS / FAIL / INCONCLUSIVE<br/>una sola fila, append-only"]
    RES --> REPRO["recomputación posterior<br/>compara bytes canónicos"]
```

El resultado se persiste **una vez**. `UPDATE`, `DELETE` y `TRUNCATE` están bloqueados por
triggers; un `CHECK` nativo recalcula el SHA-256 sobre los bytes UTF-8 del payload, así que
ni un INSERT SQL directo puede declarar un hash falso.

## 6. Las dos identidades y para qué sirve cada una

```mermaid
flowchart LR
    SRC["regiones de código<br/>marcadas por comentario"] -->|"AST canónico<br/>sin comentarios ni formato"| IDENT["scientific identity v1<br/>digest"]
    RESOLVED["symbol · base_asset<br/>futures_pair · spot_pair"] -->|"JSON canónico"| CONTRACT["runtime contract v1<br/>digest"]
    IDENT --> MANIFEST["manifest spec-v4"]
    CONTRACT --> MANIFEST
    MANIFEST --> AUTH["evaluación autoritativa<br/>falla cerrada si no reproduce"]
```

| | Identidad científica | Contrato de runtime |
|---|---|---|
| Responde | qué calcula el código | qué insumos seleccionó |
| Se calcula de | AST de regiones marcadas | valores resueltos del catálogo |
| Insensible a | comentarios, formato, docstrings, ubicación | orden y ortografía de `SYMBOLS` |
| Cambia si | cambia la semántica cubierta | cambia el ruteo resuelto |
| Registro | append-only por versión | append-only por versión |

Un commit Git **no** sirve como identidad: incluye cambios de UI y documentación que no
alteran el resultado.

## 7. Límites entre operación, investigación y evidencia confirmatoria

```mermaid
flowchart TB
    subgraph OP["Operación — puede cambiar cualquier día"]
        O1["dashboard, alertas, perfiles"]
        O2["reconexión, backoff, health"]
        O3["retención, sharding, deploy"]
    end
    subgraph RES["Investigación — exploratoria, no publicable como resultado"]
        R1["backtests diarios"]
        R2["percentiles, analogías 2Y"]
        R3["calibración pre-OOS"]
    end
    subgraph CONF["Evidencia confirmatoria — congelada antes de mirar"]
        C1["manifest spec-v4"]
        C2["población OOS + replay"]
        C3["resultado autoritativo"]
    end
    OP -.->|"NO puede alterar"| CONF
    RES -->|"sólo antes del OOS,<br/>y sólo a través del manifest"| CONF
```

Reglas que sostienen la separación:

- Un cambio en OP **no debe** mover la identidad científica. Si la mueve, o está mal
  clasificado o la región es demasiado ancha (fue exactamente el caso de
  `whale_threshold_usd`).
- RES nunca escribe en las tablas de CONF. Sus parámetros entran sólo congelándolos en un
  manifest **antes** de que exista el periodo OOS.
- CONF no elige parámetros. PR27 instala la maquinaria; no selecciona símbolo, horizonte,
  MES, bloques, duración OOS, fees, cobertura ni settlement grace.

## 8. Fuera de alcance: Trade Tape / Footprint

`ESTADO: PLANNED — fuera de PR27.`

Hoy los trades se guardan como **agregados de 1 minuto y de 5 segundos**, así que no existe
footprint, volumen-a-precio real ni clusters de órdenes; el libro sólo llega a L1/L5/L10.
Una capa Trade Tape/Footprint requeriría persistencia tick a tick, su propio esquema, su
propia retención y su propia identidad científica.

**No forma parte de PR27 ni de la evidencia confirmatoria spec-v4.** Se registra como
iniciativa posterior en [`ROADMAP.md`](ROADMAP.md) §11 y como decisión en
[`ARCHITECTURE_DECISIONS.md`](ARCHITECTURE_DECISIONS.md). Cualquier trabajo en ella empieza
por un PR propio, después del resultado autoritativo.
