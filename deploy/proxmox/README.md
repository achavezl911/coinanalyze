# Despliegue en Proxmox VE

## Perfil del contenedor

- Debian 12.
- LXC no privilegiado.
- 2 vCPU.
- 2 GB RAM y 512 MB swap.
- 24 GB SSD; aumente a 40 GB si conservará más de 30 días de snapshots.
- IP estática en una VLAN interna.
- Sin Docker, nesting ni AppArmor unconfined. La aplicación usa systemd y PostgreSQL nativos.

## Creación de referencia

Ajuste storage, bridge, VLAN, gateway y template a su entorno:

```bash
pct create 220 local:vztmpl/debian-12-standard_<VERSION>_amd64.tar.zst \
  --hostname derivatives-operator \
  --unprivileged 1 \
  --cores 2 --memory 2048 --swap 512 \
  --rootfs local-lvm:24 \
  --net0 name=eth0,bridge=vmbr0,tag=30,ip=192.0.2.20/24,gw=192.0.2.1,type=veth \
  --features nesting=0,keyctl=0 \
  --onboot 1 --start 1
```

No copie las direcciones del ejemplo. Use la VLAN y el direccionamiento reales.

## Instalación

Copie el proyecto al contenedor y ejecute:

```bash
cd coinalyze-operator-dashboard
COINALYZE_API_KEY='SU_API_KEY' \
DASHBOARD_PASSWORD='UNA_CLAVE_LARGA' \
./deploy/proxmox/install.sh
```

El instalador configura PostgreSQL, esquema, entorno Python, Nginx con Basic Auth,
cuatro servicios, backup diario y retención.

## Exposición

El puerto publicado es TCP/8443. Permita únicamente las subredes o hosts de operación.
La API Uvicorn escucha exclusivamente en `127.0.0.1:8000`. No publique PostgreSQL ni
Uvicorn directamente.

## Verificación

```bash
systemctl --no-pager --full status coinalyze-{api,ingest,ws,daily}
curl -k -u operator https://IP_LXC:8443/api/healthz
journalctl -u coinalyze-ingest -u coinalyze-ws -f
```

Los primeros datos aparecen tras el ciclo de ingesta y los WebSockets. El histórico
diario se construye hacia adelante; no puede reconstruir periodos anteriores a la
retención local si no existían datos locales.

## TLS

El instalador genera un certificado TLS autofirmado con SAN para la IP y hostname del
contenedor. Importe `coinalyze.crt` en el trust store del equipo operador o sustitúyalo
por un certificado de su PKI interna. Nginx redirige TCP/8090 a HTTPS/8443.
