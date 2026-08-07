# PATCHES_APPLIED v1.2.4

## Objetivo

Paquete final de respaldo completo e implementación desde cero.

## Cambios

- Se agrega `scripts/configure_secrets.sh` para inyectar/rotar secretos y parámetros críticos en `/etc/coinalyze/coinalyze.env`.
- Se agrega `docs/IMPLEMENTACION_DESDE_CERO.md`.
- Se mantiene la API IA consolidada de v1.2.3:
  - `/api/ai/context`
  - `/api/ai/context/bundle`
  - `/api/ai/profiles`

## Compatibilidad

No introduce cambios de esquema adicionales sobre v1.2.3.
