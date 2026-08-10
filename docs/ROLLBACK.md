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
- `schema.sql` debe ser **idempotente y compatible hacia atrás** (regla 16 de
  `AI_ENGINEERING_RULES.md`): un rollback de código sobre el esquema nuevo debe seguir funcionando.
- Cambios de esquema **destructivos** (DROP/rename de columnas en uso) requieren estrategia
  explícita de migración/rollback en dos pasos (expand → migrate → contract), nunca en un solo
  deploy.
- Tras `20260809_temporal_partitioning`, el rollback de aplicación soportado es el release
  bridge `fix: prepare liquidation writes for partition migration`; el escritor raw de
  `5ed802f` no es compatible con la clave de la tabla particionada.
- Restauración de datos (último recurso): descomprimir el dump previo y restaurar con `psql`
  (operación manual y consciente, fuera del flujo automático).

## Verificación tras rollback

```bash
sudo -n /usr/local/sbin/deploy-coinalyze status     # (en prod)
# o desde el runner por SSH; comprobar servicios activos y el commit en deployment.json
```
