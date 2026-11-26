# Brief técnico para IA — Coinalyze Operator Dashboard

## Objetivo del sistema

El sistema está diseñado para operar como una plataforma interna de lectura de microestructura de mercado para perpetuos cripto, con visualización web y una API privada de contexto estructurado.

## Aplicaciones

La aplicación es Coinalyze Operator Dashboard. Es el núcleo de datos. Recolecta información de mercado desde Coinalyze y fuentes websocket, normaliza métricas, persiste series temporales en PostgreSQL, calcula señales de microestructura y expone una interfaz web de solo lectura. También expone endpoints internos pensados para que un proceso externo obtenga contexto estructurado sin tener que leer directamente la base de datos.

Los avisos deterministas de estructura y liquidaciones por Telegram los publica hoy un servicio aparte (del bridge, a mover al bot). No está versionado en este repo y no recolecta mercado ni escribe en la base del Dashboard.

## Separación de responsabilidades

El Dashboard es responsable de ingesta, persistencia, cálculo, API interna, UI web, health checks y seguridad de exposición local mediante nginx. No depende de ningún consumidor de su API para funcionar.

## Modelo de despliegue

El Dashboard está pensado para Debian 12, ya sea en Proxmox LXC o en una VM Debian sobre ESXi, con PostgreSQL local y nginx local.

El Dashboard escucha FastAPI solo en localhost. nginx es el único punto remoto y publica HTTPS en el puerto 8443. nginx inyecta el token interno hacia FastAPI y aplica Basic Auth, TLS y allowlist CIDR antes de entregar tráfico al backend.

## Seguridad

La protección tiene varias capas. El primer filtro remoto es la allowlist CIDR de nginx. Después se aplica Basic Auth. nginx reenvía al upstream local con `X-Internal-Token`. FastAPI valida ese token y conserva validación CIDR para accesos directos o despliegues no proxificados. Los secretos viven en archivos `.env` bajo `/etc`, con permisos restrictivos y usuarios systemd dedicados.

## Datos y procesamiento

La base PostgreSQL almacena snapshots, OHLCV, open interest, funding, liquidaciones, trades spot/futuros agregados, orderbook agregado, señales scalp, alertas, health del pipeline y agregados diarios. Los servicios systemd separan responsabilidades para que una falla de ingesta, websocket o cálculo no implique rediseñar todo el proceso.

La UI consume endpoints `/api/*` y stream SSE. El modo scalp calcula contexto de corto plazo usando delta, orderbook, absorción, liquidaciones, basis y señales recientes. Los endpoints `/api/ai/*` entregan contexto ya normalizado para que ningún consumidor replique lógica de mercado; sus perfiles (`lite`, `default`, `pro`, `max`) los describe `GET /api/ai/profiles`.

## Criterios de implementación sin código

Para recrear el sistema, la IA debe construir el Dashboard como servicio FastAPI async con PostgreSQL y colectores systemd. Debe exponer únicamente nginx hacia la red, mantener FastAPI en localhost, aplicar allowlist CIDR en nginx y token interno en la API.

La IA no debe permitir acceso remoto directo a FastAPI. No debe confiar en `X-Forwarded-For` sin proxies explícitamente confiables. No debe almacenar secretos en el repositorio.
