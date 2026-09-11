# Rollback

El rollback vuelve `current` al release anterior registrado en `deployment.json`
(`previous_commit`), reinicia servicios y hace smoke test. **No** revierte migraciones de
base de datos automáticamente (ver abajo).

## Cómo hacer rollback

Vía GitHub Actions (recomendado, mismo mecanismo que el deploy):

```bash
gh workflow run "Deploy production" -f action=rollback --ref main
gh run watch
```

Internamente ejecuta en prod:

```bash
sudo -n /usr/local/sbin/deploy-coinalyze rollback
```

Que hace:

```
lee deployment.json.previous_commit
        ↓
current -> releases/<previous>
        ↓
systemctl restart (5 servicios)
        ↓
smoke test (/api/healthz, /api/symbols, /api/ai/profiles)
        ↓
escribe deployment.json (commit=<previous>, previous=<el que estaba>, source=manual-rollback)
```

Como `previous_commit` se intercambia, ejecutar rollback de nuevo **rueda hacia adelante** al
release que estaba activo. Así el rollback es bidireccional y no deja prod inconsistente.

El estado vive en **`/var/lib/coinalyze/deployment.json`** (0644, lo escribe `write_state` del
wrapper). Si necesitas saber a dónde va a ir el rollback antes de dispararlo, ese fichero lo dice.

**El árbol al que vuelves también se poda: sólo quedan los CINCO releases más recientes**
(`KEEP_RELEASES=5` en el wrapper, `prune_releases` corre en cada despliegue). Los `legacy-*`
están exentos. Con el ritmo de despliegue de esta casa eso son menos de dos días de historia de
código: **no se puede volver seis despliegues atrás**, y el rollback fallará con
`no previous_commit recorded` o con el directorio ausente. Lo que sí queda siempre es
reconstruir el release desde git.

## Rollback automático en un deploy fallido

Si el smoke test post-deploy falla, el wrapper hace rollback **solo**, al release anterior,
reinicia y verifica, y devuelve código de error a GitHub Actions:

```
CURRENT: releases/A
NUEVO:   releases/B  (build → schema → switch → restart → smoke)
smoke B falla → current -> A → restart → smoke A → estado registrado → job falla
```

## Base de datos (IMPORTANTE)

Restaurar el código **no** revierte cambios de esquema. Por eso:

- El wrapper hace `pg_dump` **antes** de cada deploy en `/var/backups/coinalyze/predeploy-<sha>-<ts>.sql.gz`.
  El `<sha>` es el del release que **entra**, así que `predeploy-<current>` es la foto de la base
  justo antes de que lo que corre ahora se pusiera a correr. **Ese volcado VIVE TRES DÍAS**
  (`PREDEPLOY_RETENTION_DAYS=3` en `scripts/backup.sh`, decisión de Alejandro del 2026-09-08;
  pesa ~419 MB y sin poda crecía a 1.17 GB/día). Lo borra el servicio diario
  `coinalyze-backup.timer`, a las 03:15 hora de 140. **No hay excepción para el release vivo:**
  la poda casa por nombre y edad, y el volcado del release que está corriendo se borra igual que
  los demás al cuarto día. Ver la tabla de abajo antes de contar con él.
- `schema.sql` debe ser **idempotente y compatible hacia atrás** (regla 16 de
  `AI_ENGINEERING_RULES.md`): un rollback de código sobre el esquema nuevo debe seguir funcionando.
- Cambios de esquema **destructivos** (DROP/rename de columnas en uso) requieren estrategia
  explícita de migración/rollback en dos pasos (expand → migrate → contract), nunca en un solo
  deploy.
- Tras `20260809_temporal_partitioning`, el rollback de aplicación soportado es el release
  bridge `fix: prepare liquidation writes for partition migration`; el escritor raw de
  `5ed802f` no es compatible con la clave de la tabla particionada.
- Restauración de datos (último recurso): descomprimir el dump previo y restaurar con `psql`
  (operación manual y consciente, fuera del flujo automático). **Qué dump te queda depende de
  cuánto haya pasado desde el despliegue: la tabla siguiente.**

## Qué te queda, según cuánto haya pasado

Son tres redes con tres vidas distintas. **Usa la primera que siga viva.**

| red | qué recupera | cuánto vive | quién la poda |
|---|---|---|---|
| `releases/<sha>` | el **código** anterior | los **5** más recientes | `prune_releases`, en cada despliegue |
| `predeploy-<sha>-<ts>.sql.gz` | la base **justo antes de ese despliegue**, sin cifrar | **3 días** | `backup.sh`, a diario a las 03:15 |
| `coinalyze-full-<ts>.tar.gz.enc` | la base entera + rootfs, **cifrada** | **14 días** | `backup.sh`, a diario a las 03:15 |

```
día 0-3 desde el despliegue   predeploy-<sha> exacto. Pierdes sólo lo escrito desde el deploy.
día 4 en adelante             ese volcado YA NO ESTÁ. Te queda el cifrado del día, que es de
                              las ~03:15: pierdes hasta 24 h y necesitas /etc/coinalyze/backup.key
más de 14 días                no queda nada de la base. Sólo el código, si está entre los 5.
```

**La consecuencia incómoda, y es la razón de esta tabla:** cuanto más estable ha sido un
release, menos red tiene. Un release que lleva una semana corriendo **ya no tiene su
`predeploy`**; el rollback de código funcionará igual, pero si además hubo un cambio de esquema,
lo que te queda es un cifrado de hasta 24 h antes. Por eso `schema.sql` tiene que ser compatible
hacia atrás: **la compatibilidad no es una buena práctica, es la red que de verdad sostiene el
día cinco.**

Esto **declara** la retención, no la propone ni la cambia: los 3 días son una decisión fechada
del 2026-09-08 y se revisa aparte.

## Lo que este documento describe y el repositorio NO versiona

Casi todo lo de arriba —el `pg_dump` previo, el intercambio de `previous_commit`, el smoke test,
`KEEP_RELEASES`, `prune_releases`— vive en **`/usr/local/sbin/deploy-coinalyze`**, en 140, y
**ese fichero no está en este repositorio**: no tiene revisión, ni CI, ni historia aquí. Lo mismo
vale para el drop-in `/etc/systemd/system/coinalyze-backup.service.d/10-current.conf`, que es lo
único que hace que el servicio diario ejecute el `backup.sh` del release en vez de una copia
congelada del árbol legacy —y con él, lo único que hace que la poda de 3 días exista—.

**Consecuencia práctica al leer esto de madrugada:** las vidas de `scripts/backup.sh` se pueden
comprobar en git; las del wrapper, no. Y hoy **no coinciden**: el wrapper trae su propia poda de
`predeploy-*.sql.gz` a **14 días**, que quedó sin actualizar el 2026-09-08. No cambia el
resultado —manda la más estricta, que corre a diario— pero **el día que el servicio diario falle,
la vida efectiva pasa a ser 14 sin que nadie lo diga.**

## Verificación tras rollback

```bash
sudo -n /usr/local/sbin/deploy-coinalyze status     # (en prod)
# o desde el runner por SSH; comprobar servicios activos y el commit en deployment.json
```
