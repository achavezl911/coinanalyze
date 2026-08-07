# PATCHES_APPLIED v1.2.5

## Alcance

Cierre final posterior a la revisión `reviewed → resolved`.

## Cambios

- Se cerró el defecto de CIDR detrás de nginx.
- `deploy/nginx/coinalyze.conf` incluye `/etc/nginx/snippets/coinalyze-allowlist.conf` en los servidores `8090` y `8443`.
- `deploy/proxmox/install.sh`, `scripts/update.sh` y `scripts/configure_secrets.sh` generan la allowlist nginx desde `NGINX_ALLOWED_CIDRS`.
- Se agregó `NGINX_ALLOWED_CIDRS` a `.env.example` y al `.env` generado por instalación limpia.
- Se agregó prueba estática para confirmar que el template nginx y scripts escriben la allowlist.
- Se actualizó el manual HTML visible desde la UI en la sección `Manual`.
- Se agregó documentación de implementación 0 a 100 para Proxmox LXC y ESXi Debian.
- Se agregó brief técnico para IA sin código.

## Decisión

El filtrado por origen remoto queda en nginx porque es el componente que observa la IP real del cliente antes de reenviar a FastAPI por `127.0.0.1:8000`.
