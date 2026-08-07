# Brief técnico para IA — Coinalyze Operator Dashboard y AI Telegram Bridge

## Objetivo del sistema

El sistema está diseñado para operar como una plataforma interna de lectura de microestructura de mercado para perpetuos cripto, con visualización web, API privada para contexto IA y un bridge separado que permite solicitar análisis por Telegram bajo demanda.

## Aplicaciones

Existen dos aplicaciones desacopladas.

La primera es Coinalyze Operator Dashboard. Es el núcleo de datos. Recolecta información de mercado desde Coinalyze y fuentes websocket, normaliza métricas, persiste series temporales en PostgreSQL, calcula señales de microestructura y expone una interfaz web de solo lectura. También expone endpoints internos pensados para que un proceso IA obtenga contexto estructurado sin tener que leer directamente la base de datos.

La segunda es Coinalyze AI Telegram Bridge. Es un daemon externo. No recolecta mercado ni escribe en la base del Dashboard. Escucha comandos autorizados en Telegram, consulta el contexto del Dashboard mediante HTTPS, genera análisis con OpenAI y publica la respuesta en un canal Telegram. Su operación es bajo demanda, no automática por intervalo normal de trading.

## Separación de responsabilidades

El Dashboard es responsable de ingesta, persistencia, cálculo, API interna, UI web, health checks y seguridad de exposición local mediante nginx.

El Bridge es responsable de autenticación de comandos Telegram, selección de perfil IA, control de uso, consulta al Dashboard, llamada a OpenAI, formateo de respuestas y publicación en Telegram.

El Dashboard no depende del Bridge para funcionar. El Bridge sí depende del Dashboard porque necesita su API de contexto.

## Modelo de despliegue

Ambas aplicaciones están pensadas para Debian 12, ya sea en Proxmox LXC o en una VM Debian sobre ESXi. El Dashboard puede vivir en un LXC/VM con PostgreSQL local y nginx local. El Bridge puede vivir en otro LXC/VM o en el mismo host, aunque se recomienda separarlo para aislar secretos de Telegram/OpenAI.

El Dashboard escucha FastAPI solo en localhost. nginx es el único punto remoto y publica HTTPS en el puerto 8443. nginx inyecta el token interno hacia FastAPI y aplica Basic Auth, TLS y allowlist CIDR antes de entregar tráfico al backend.

## Seguridad

La protección tiene varias capas. El primer filtro remoto es la allowlist CIDR de nginx. Después se aplica Basic Auth. nginx reenvía al upstream local con `X-Internal-Token`. FastAPI valida ese token y conserva validación CIDR para accesos directos o despliegues no proxificados. Los secretos viven en archivos `.env` bajo `/etc`, con permisos restrictivos y usuarios systemd dedicados.

El Bridge valida el chat autorizado y, si se configura, también el `message.from.id`. Esto evita que un grupo autorizado permita comandos de usuarios no autorizados. Los tokens de Telegram, OpenAI y Dashboard se mantienen solo en el entorno del servicio.

## Datos y procesamiento

La base PostgreSQL almacena snapshots, OHLCV, open interest, funding, liquidaciones, trades spot/futuros agregados, orderbook agregado, señales scalp, alertas, health del pipeline y agregados diarios. Los servicios systemd separan responsabilidades para que una falla de ingesta, websocket o cálculo no implique rediseñar todo el proceso.

La UI consume endpoints `/api/*` y stream SSE. El modo scalp calcula contexto de corto plazo usando delta, orderbook, absorción, liquidaciones, basis y señales recientes. Los endpoints de IA entregan contexto ya normalizado para evitar que el Bridge replique lógica de mercado.

## IA

El Bridge usa perfiles de análisis. El perfil lite produce salida compacta y menor consumo. El perfil normal es el uso diario. El perfil pro permite más presupuesto de salida y razonamiento para escenarios relevantes. El comando `/preview` no consume OpenAI; publica el payload que se enviaría al modelo. Si el payload excede el límite de Telegram, se entrega como archivo JSON único.

## Criterios de implementación sin código

Para recrear el sistema, la IA debe construir primero el Dashboard como servicio FastAPI async con PostgreSQL y colectores systemd. Debe exponer únicamente nginx hacia la red, mantener FastAPI en localhost, aplicar allowlist CIDR en nginx y token interno en la API. Después debe construir el Bridge como daemon independiente con long polling de Telegram, autenticación estricta de chat/usuario, cliente HTTPS hacia el Dashboard, cliente OpenAI con perfiles y publicación controlada al canal Telegram.

La IA no debe fusionar Dashboard y Bridge. No debe permitir acceso remoto directo a FastAPI. No debe confiar en `X-Forwarded-For` sin proxies explícitamente confiables. No debe almacenar secretos en el repositorio. No debe dividir `/preview` en múltiples mensajes cuando el payload completo pueda entregarse como archivo único.
