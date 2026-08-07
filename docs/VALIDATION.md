# Validación de la entrega

Validaciones ejecutadas sobre la versión 1.0.0:

- 14 pruebas unitarias: métricas, DST/NYSE, whale thresholds, setups, validación de trades,
  persistencia por revisión e ingesta OHLC.
- Ruff sin hallazgos.
- Compilación de todos los módulos Python.
- Validación sintáctica del JavaScript con Node.js.
- Parseo del esquema y 40 sentencias SQL estáticas mediante parser PostgreSQL.
- Construcción correcta del wheel Python.
- Resolución completa de dependencias y disponibilidad de wheels para CPython 3.11 x86_64.
- Verificación SHA-256 de la copia local de Lightweight Charts.

No se ejecutó una llamada real a Coinalyze porque la entrega no contiene una API key.
La comprobación WebSocket real se intentó, pero el entorno de construcción no permitió
resolución DNS saliente. Los contratos utilizados corresponden a los endpoints públicos
documentados y los consumidores incluyen reconexión, validación y estado degradado.

El instalador debe probarse finalmente dentro del LXC destino, porque networking, storage,
DNS, NTP, firewall, repositorios APT y PKI dependen de la infraestructura Proxmox del operador.
- Validación estructural de las unidades systemd mediante `systemd-analyze verify`.
- Parseo de la configuración Nginx dentro de contexto `http`.
