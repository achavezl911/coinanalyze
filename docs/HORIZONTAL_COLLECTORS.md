# Collectors horizontales

`ws` y `scalp` asignan cada símbolo con SHA-256 a exactamente un shard. PostgreSQL mantiene
un advisory lock por `servicio/índice/conteo`; dos procesos con el mismo ownership no pueden
arrancar. `ingest` y `daily` siguen siendo singleton y también mantienen lock durante toda su
vida.

Antes de cambiar el número de shards, detén **todas** las instancias del conteo anterior. No
ejecutes simultáneamente unidades legacy (`coinalyze-ws.service`,
`coinalyze-scalp.service`) y templates.

## Catálogo

El default vive una sola vez en `app/config.py`. Para extenderlo sin secretos, copia
`config/market_symbols.example.json` a `config/market_symbols.json` y cambia sus filas; esa
ruta versionada se detecta automáticamente. Para otra ruta, configura:

```text
MARKET_SYMBOL_CATALOG_FILE=/opt/coinalyze/config/market_symbols.json
```

El archivo tiene `version: 1` y `mode: extend` (o `replace`). Si `SYMBOLS` se omite, se usa
todo el catálogo; opcionalmente puede contener un subconjunto. El startup registra de forma
idempotente los activos, perpetuos y símbolos spot históricos en PostgreSQL.

## Migración y rollback

`sql/schema.sql` aplica el cambio idempotente durante el despliegue normal. La migración
aislada equivalente es `sql/migrations/20260809_horizontal_safe_collectors.sql`. Antes de
aplicarla, ejecuta el backup normal del proyecto; no requiere reescribir las filas BTC, ETH o
SOL existentes.

El rollback está en `sql/migrations/20260809_horizontal_safe_collectors.down.sql`. Debe
ejecutarse con collectors detenidos y después de un backup. Se niega explícitamente a volver
a los checks antiguos si existe cualquier fila de un cuarto activo; elimina la tabla de
eventos del limiter, por lo que solo debe usarse como rollback completo de esta versión.

## Un shard

En `/etc/coinalyze/coinalyze.env`:

```text
COLLECTOR_SHARD_COUNT=1
```

Luego:

```bash
systemctl disable --now coinalyze-ws coinalyze-scalp
systemctl enable --now coinalyze-ws@0 coinalyze-scalp@0
```

`@0` posee BTC, ETH y SOL; reproduce el comportamiento anterior.

## Dos shards

Primero detén el conteo anterior, cambia el env y arranca exactamente `@0` y `@1`:

```bash
systemctl stop 'coinalyze-ws@*' 'coinalyze-scalp@*'
sed -i 's/^COLLECTOR_SHARD_COUNT=.*/COLLECTOR_SHARD_COUNT=2/' /etc/coinalyze/coinalyze.env
systemctl daemon-reload
systemctl enable --now coinalyze-ws@0 coinalyze-ws@1 coinalyze-scalp@0 coinalyze-scalp@1
```

Con el catálogo actual, SHA-256 asigna los tres símbolos a `@1`; `@0` queda ocioso de forma
segura. No se debe mover manualmente un símbolo: la distribución cambia automáticamente al
crecer el catálogo.

## Tres shards

```bash
systemctl stop 'coinalyze-ws@*' 'coinalyze-scalp@*'
sed -i 's/^COLLECTOR_SHARD_COUNT=.*/COLLECTOR_SHARD_COUNT=3/' /etc/coinalyze/coinalyze.env
systemctl daemon-reload
systemctl enable --now coinalyze-ws@0 coinalyze-ws@1 coinalyze-ws@2 \
  coinalyze-scalp@0 coinalyze-scalp@1 coinalyze-scalp@2
```

Con el catálogo actual: `@0` posee BTC, `@1` ETH y `@2` SOL.

Para volver a una instancia, detén primero todas las unidades template, restaura
`COLLECTOR_SHARD_COUNT=1` y arranca solo `@0`. Si queda una instancia duplicada, el advisory
lock hace que la segunda falle antes de abrir WebSockets.
