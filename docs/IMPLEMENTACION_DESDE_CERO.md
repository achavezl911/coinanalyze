# Manual — Coinalyze Operator Dashboard v1.2.5 final

## 1. Alcance

Este manual cubre la implementación desde cero del stack Coinalyze en dos escenarios soportados:

- Proxmox LXC Debian 12.
- ESXi v7/v8 con VM Debian 12.

El stack queda dividido en dos aplicaciones:

1. **Coinalyze Operator Dashboard**: API interna, dashboard web, colectores de mercado, persistencia PostgreSQL, Nginx con TLS, Basic Auth y allowlist CIDR.
2. **Coinalyze AI Telegram Bridge**: servicio externo que consulta el Dashboard, ejecuta análisis IA bajo demanda y publica resultados en Telegram.

La versión final corrige el defecto de CIDR detrás de proxy: nginx ahora aplica una allowlist real antes de reenviar tráfico a FastAPI. FastAPI conserva `API_INTERNAL_ALLOWED_CIDRS` como defensa para acceso directo a `127.0.0.1:8000` o despliegues sin proxy, pero el control efectivo para clientes remotos vive en nginx mediante `/etc/nginx/snippets/coinalyze-allowlist.conf`.

## 2. Arquitectura operativa

```text
Cliente admin / Bridge
        ↓ HTTPS 8443 + Basic Auth + CIDR nginx
Nginx Dashboard
        ↓ X-Internal-Token hacia localhost
FastAPI Dashboard 127.0.0.1:8000
        ↓ asyncpg
PostgreSQL local
        ↑
Colectores systemd: ingest, ws, scalp, daily
```

Flujo IA:

```text
Telegram privado autorizado
        ↓ getUpdates
Coinalyze AI Telegram Bridge
        ↓ HTTPS 8443 + Basic Auth + X-Internal-Token
Dashboard /api/ai/context
        ↓
OpenAI Responses API / fallback compatible
        ↓
Canal Telegram de salida
```

## 3. Requisitos base

### Hardware mínimo recomendado

- 2 vCPU.
- 4 GB RAM mínimo; 6–8 GB recomendado si se conserva mayor retención.
- 30 GB disco para Dashboard.
- 10 GB disco para Bridge.
- Debian 12 limpio.

### Red

Ejemplo usado en los scripts y documentación:

- VLAN/segmento de gestión: `10.10.100.0/28`.
- Dashboard: `10.10.100.4/28`.
- Gateway: `10.10.100.1`.
- Puerto web Dashboard: `8443/tcp`.
- Redirección HTTP opcional: `8090/tcp`.
- API FastAPI local: `127.0.0.1:8000`; no debe exponerse.

Ajusta los CIDR si tu red real no es `10.10.100.0/28`.

## 4. Preparación en Proxmox LXC

Crear LXC Debian 12 privilegiado o no privilegiado según tu estándar. Para esta aplicación no se requiere nesting ni Docker.

Parámetros recomendados:

```text
OS: Debian 12
vCPU: 2
RAM: 4096 MB
Disk: 30 GB
Network: bridge/VLAN de gestión
IP: estática
```

Si quieres configurar IP desde el host Proxmox usando el script incluido:

```bash
sudo deploy/proxmox/set_lxc_static_ip.sh <CTID> vmbr0 10.10.100.1 10.10.100.4/28
pct restart <CTID>
```

Ajusta `vmbr0`, gateway e IP al bridge/VLAN real.

## 5. Preparación en ESXi Debian VM

Crear VM Debian 12 estándar:

```text
Guest OS: Debian GNU/Linux 12 64-bit
vCPU: 2
RAM: 4 GB
Disk: 30 GB thin/thick según política
NIC: VMXNET3 en port group de gestión
```

Configura IP estática en Debian mediante `systemd-networkd`, NetworkManager o `/etc/network/interfaces`, según la plantilla usada. El instalador de aplicación no fuerza la configuración de red dentro de ESXi.

Validación previa:

```bash
ip addr
ip route
ping -c 3 1.1.1.1
curl -fsS https://api.coinalyze.net/v1/ || true
```

## 6. Instalación limpia del Dashboard

Copiar el paquete al servidor Debian/LXC/VM y ejecutar como root:

```bash
cd /tmp
tar -xzf coinalyze-operator-dashboard-v1.2.5-final.tar.gz
cd coinalyze-operator-dashboard-v1.2.5

sudo env \
  COINALYZE_API_KEY='API_KEY_COINALYZE' \
  DASHBOARD_USER='operator' \
  DASHBOARD_PASSWORD='PASSWORD_DASHBOARD' \
  NGINX_ALLOWED_CIDRS='["127.0.0.1/32","::1/128","10.10.100.0/28"]' \
  ./deploy/proxmox/install.sh
```

El instalador realiza:

- instalación de Python, PostgreSQL, Nginx y utilidades;
- creación de usuario/grupo systemd `coinalyze`;
- despliegue en `/opt/coinalyze`;
- creación de venv Python;
- instalación de dependencias bloqueadas;
- creación/ajuste de base `coinalyze` y rol PostgreSQL;
- carga idempotente de `sql/schema.sql`;
- escritura de `/etc/coinalyze/coinalyze.env`;
- instalación de units systemd;
- generación de certificado TLS autofirmado;
- configuración de Nginx en `8443/tcp`;
- escritura de `/etc/nginx/snippets/coinalyze-allowlist.conf`;
- smoke test local contra FastAPI.

## 7. Variables críticas del Dashboard

Archivo final:

```bash
sudo install -d -m 0750 /etc/coinalyze
sudo cat /etc/coinalyze/coinalyze.env
```

Variables críticas:

```env
API_KEY=<api_key_de_coinalyze>
PG_HOST=127.0.0.1
PG_PORT=5432
PG_DB=coinalyze
PG_USER=coinalyze
PG_PASSWORD=<secreto_generado>
PG_SSLMODE=disable
API_HOST=127.0.0.1
API_PORT=8000
API_INTERNAL_TOKEN=<secreto_generado>
API_INTERNAL_ALLOWED_CIDRS='["127.0.0.1/32","::1/128","10.10.100.0/28"]'
NGINX_ALLOWED_CIDRS='["127.0.0.1/32","::1/128","10.10.100.0/28"]'
TRUSTED_HOSTS='["127.0.0.1","localhost","10.10.100.4"]'
SYMBOLS='["BTCUSDT_PERP.A","ETHUSDT_PERP.A","SOLUSDT_PERP.A"]'
```

Diferencia relevante:

- `API_INTERNAL_ALLOWED_CIDRS`: aplica dentro de FastAPI para endpoints `/api/*` y `/metrics`.
- `NGINX_ALLOWED_CIDRS`: aplica en nginx y bloquea clientes reales antes de llegar al upstream.

Para topologías detrás de Cloudflare Access, VPN o reverse proxy adicional, filtra primero en ese punto y después ajusta `NGINX_ALLOWED_CIDRS` a las IP/CIDR que nginx realmente verá.

## 8. Validación del Dashboard

Estado systemd:

```bash
sudo systemctl status coinalyze-api --no-pager -l
sudo systemctl status coinalyze-ingest --no-pager -l
sudo systemctl status coinalyze-ws --no-pager -l
sudo systemctl status coinalyze-scalp --no-pager -l
sudo systemctl status coinalyze-daily --no-pager -l
sudo systemctl status nginx --no-pager -l
```

Health local:

```bash
sudo bash -lc '
set -a
source /etc/coinalyze/coinalyze.env
set +a
curl -fsS -H "X-Internal-Token: $API_INTERNAL_TOKEN" \
  http://127.0.0.1:8000/api/healthz | python3 -m json.tool
'
```

Health por nginx:

```bash
curl -k -u 'operator:PASSWORD_DASHBOARD' \
  https://10.10.100.4:8443/api/healthz | python3 -m json.tool
```

Validación de CIDR nginx:

```bash
sudo cat /etc/nginx/snippets/coinalyze-allowlist.conf
sudo nginx -t
```

Debe contener líneas similares a:

```nginx
allow 127.0.0.1/32;
allow ::1/128;
allow 10.10.100.0/28;
deny all;
```

Desde una IP fuera del CIDR permitido, nginx debe responder `403` antes de Basic Auth o upstream.

## 9. Instalación limpia del Bridge

Ejecutar en otro LXC/VM Debian 12 o en el mismo host si así lo decides. Separarlo es preferible.

```bash
cd /tmp
tar -xzf coinalyze-ai-telegram-bridge-v0.1.8-final.tar.gz
cd coinalyze-ai-telegram-bridge-v0.1.8
sudo ./scripts/install.sh /tmp/coinalyze-ai-telegram-bridge-v0.1.8
```

Usuario systemd por defecto:

```text
coinalyze-ai
```

Si ya tienes una instalación con otro usuario:

```bash
sudo env SERVICE_USER='barbagorda' SERVICE_GROUP='barbagorda' \
  ./scripts/install.sh /tmp/coinalyze-ai-telegram-bridge-v0.1.8
```

## 10. Configuración del Bridge

Ejecutar el configurador:

```bash
cd /opt/coinalyze-ai-bridge
sudo ./scripts/configure_secrets.sh
```

Valores mínimos:

```env
COINALYZE_API_BASE="https://10.10.100.4:8443"
COINALYZE_API_TOKEN="API_INTERNAL_TOKEN_DEL_DASHBOARD"
COINALYZE_BASIC_AUTH_USER="operator"
COINALYZE_BASIC_AUTH_PASSWORD="PASSWORD_DASHBOARD"
COINALYZE_TLS_VERIFY="false"
USE_DASHBOARD_AI_CONTEXT="true"

OPENAI_API_KEY="sk-..."
OPENAI_MODEL="gpt-5.5"
OPENAI_LITE_MODEL="gpt-5.5"
OPENAI_PRO_MODEL="gpt-5.5-pro"

TELEGRAM_BOT_TOKEN="TOKEN_BOTFATHER"
TELEGRAM_COMMAND_CHAT_IDS='["628219977"]'
TELEGRAM_ALLOWED_USER_IDS='["628219977"]'
TELEGRAM_OUTPUT_CHAT_ID="-1004321749618"
TELEGRAM_CHAT_ID="-1004321749618"
SEND_MODE="telegram_command"
```

`TELEGRAM_ALLOWED_USER_IDS` acepta JSON de strings o números. En grupos autorizados valida también `message.from.id`.

## 11. Validación del Bridge

```bash
sudo -u coinalyze-ai -g coinalyze-ai \
  /opt/coinalyze-ai-bridge/.venv/bin/coinalyze-ai-bridge \
  --env-file /etc/coinalyze-ai-bridge/coinalyze-ai-bridge.env \
  health
```

```bash
sudo -u coinalyze-ai -g coinalyze-ai \
  /opt/coinalyze-ai-bridge/.venv/bin/coinalyze-ai-bridge \
  --env-file /etc/coinalyze-ai-bridge/coinalyze-ai-bridge.env \
  test-telegram
```

Activar servicio:

```bash
sudo systemctl enable --now coinalyze-ai-bridge
sudo journalctl -u coinalyze-ai-bridge -f -o cat
```

## 12. Comandos Telegram

Desde chat privado autorizado:

```text
/status
/usage
/preview BTC
/preview ETH
/preview SOL
/preview ALL
/chatgpt-lite ETH
/chatgpt ETH
/chatgpt-pro ETH
```

`/preview` publica el payload completo en una sola entrega:

- mensaje único si cabe en el límite de Telegram;
- archivo JSON adjunto si excede el límite.

## 13. Operación diaria

Logs Dashboard:

```bash
sudo journalctl -u coinalyze-api -f -o cat
sudo journalctl -u coinalyze-ingest -f -o cat
sudo journalctl -u coinalyze-ws -f -o cat
sudo journalctl -u coinalyze-scalp -f -o cat
```

Logs Bridge:

```bash
sudo journalctl -u coinalyze-ai-bridge -f -o cat
```

Backups Dashboard:

```bash
sudo /opt/coinalyze/scripts/backup.sh
ls -lah /var/backups/coinalyze
```

Verificación de base:

```bash
sudo -u postgres psql -d coinalyze -c '\dt'
sudo -u postgres psql -d coinalyze -c "select service,status,ts from pipeline_heartbeat order by service;"
```

## 14. Actualización controlada

Dashboard:

```bash
cd /tmp
tar -xzf coinalyze-operator-dashboard-v1.2.5-final.tar.gz
cd coinalyze-operator-dashboard-v1.2.5
sudo ./scripts/update.sh /tmp/coinalyze-operator-dashboard-v1.2.5
```

Bridge:

```bash
cd /tmp
tar -xzf coinalyze-ai-telegram-bridge-v0.1.8-final.tar.gz
cd coinalyze-ai-telegram-bridge-v0.1.8
sudo ./scripts/update.sh /tmp/coinalyze-ai-telegram-bridge-v0.1.8
```

Ambos scripts conservan secretos existentes, reinstalan units systemd y reinician servicios necesarios.

## 15. Rotación de secretos antes de producción

Dashboard:

```bash
cd /opt/coinalyze
sudo ./scripts/configure_secrets.sh
sudo systemctl restart coinalyze-api coinalyze-ingest coinalyze-ws coinalyze-scalp coinalyze-daily nginx
```

Bridge:

```bash
cd /opt/coinalyze-ai-bridge
sudo ./scripts/configure_secrets.sh
sudo systemctl restart coinalyze-ai-bridge
```

Rotar obligatoriamente:

- `COINALYZE_API_KEY`;
- `API_INTERNAL_TOKEN`;
- contraseña Basic Auth del Dashboard;
- `OPENAI_API_KEY`;
- `TELEGRAM_BOT_TOKEN`.

## 16. Controles de seguridad finales

- `API_PORT=8000` debe escuchar solo en `127.0.0.1`.
- Nginx debe ser el único punto de entrada remoto.
- `NGINX_ALLOWED_CIDRS` debe contener solo VLAN de gestión, IP del Bridge o red VPN autorizada.
- `API_INTERNAL_TOKEN` no debe estar vacío.
- `/etc/coinalyze/coinalyze.env` debe quedar `0640 root:coinalyze`.
- `/etc/coinalyze-ai-bridge/coinalyze-ai-bridge.env` debe quedar restringido al usuario/grupo del servicio.
- No publiques logs con tokens de Telegram, OpenAI ni Coinalyze.
- Si se usa certificado autofirmado, el Bridge puede usar `COINALYZE_TLS_VERIFY=false`; en producción formal usa CA interna y cambia a `true`.

## 17. Troubleshooting mínimo

FastAPI no responde:

```bash
sudo journalctl -u coinalyze-api -n 200 --no-pager -o cat
sudo bash -lc 'set -a; source /etc/coinalyze/coinalyze.env; set +a; env | grep -E "^(PG_|API_)"'
```

Nginx responde 403:

```bash
ip route get <IP_CLIENTE>
sudo cat /etc/nginx/snippets/coinalyze-allowlist.conf
sudo tail -n 100 /var/log/nginx/access.log
```

Bridge no publica:

```bash
sudo journalctl -u coinalyze-ai-bridge -n 200 --no-pager -o cat
sudo -u coinalyze-ai -g coinalyze-ai /opt/coinalyze-ai-bridge/.venv/bin/coinalyze-ai-bridge --env-file /etc/coinalyze-ai-bridge/coinalyze-ai-bridge.env health
```

Telegram no acepta comandos:

- valida `TELEGRAM_COMMAND_CHAT_IDS`;
- valida `TELEGRAM_ALLOWED_USER_IDS`;
- valida que el bot tenga permisos en el canal de salida;
- revisa que no exista otro proceso consumiendo `getUpdates` del mismo bot.

## 18. Criterio de cierre

La instalación se considera funcional cuando:

- `coinalyze-api`, `coinalyze-ingest`, `coinalyze-ws`, `coinalyze-scalp`, `coinalyze-daily` están activos;
- `nginx -t` pasa;
- `/etc/nginx/snippets/coinalyze-allowlist.conf` contiene `deny all;`;
- `/api/healthz` responde por `127.0.0.1:8000` con token;
- el Dashboard abre por `https://IP:8443` desde una IP permitida;
- el Bridge pasa `health`;
- `/status` y `/preview ETH` responden desde Telegram;
- `/chatgpt-lite ETH` genera análisis y publica en el canal configurado.
