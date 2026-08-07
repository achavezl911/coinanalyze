# Parche del bridge de Telegram — v1.3.4

El bridge (`/opt/coinalyze-ai-bridge`) es **otro proyecto**: `update.sh` de coinalyze no lo
toca. Estos cambios viven aquí para que no se pierdan si el bridge se reinstala desde cero.

## Qué hace

Que `/preview` pida el perfil **`max`** del dashboard en vez de `default`. El bridge ya
pasaba el `ai_context` íntegro y ya lo entregaba como documento JSON único cuando excede
los 4096 caracteres de Telegram; lo único que faltaba era pedir el perfil completo.

Resultado: ~446 KB / ~106 k tokens con 90 sesiones de `daily_history` por símbolo, para
pegar en una IA por web. No consume tokens de OpenAI.

## Aplicar

**El LXC no trae instalado `patch`** (comprobado: `command not found`), así que el
`.patch` de esta carpeta sirve para *revisar* el cambio, no para aplicarlo. Usa `apply.py`,
que no depende de nada externo, aborta sin escribir si el fuente no es el esperado, y es
idempotente:

```bash
cd /opt/coinalyze-ai-bridge && cp -a src ".bak.$(date -u +%Y%m%dT%H%M%SZ)" && ./.venv/bin/python /opt/coinalyze/deploy/ai-bridge/apply.py
```

Añadir al `.env` (`/etc/coinalyze-ai-bridge/coinalyze-ai-bridge.env`):

```
TELEGRAM_PREVIEW_PROFILE="max"
```

**El bridge se instala como copia, no editable**, así que hay que reinstalar y reiniciar:

```bash
cd /opt/coinalyze-ai-bridge && ./.venv/bin/pip install --no-deps .
systemctl restart coinalyze-ai-bridge
```

## Verificar sin publicar en el canal

`/preview` publica en Trading_Barbagorda. Para comprobar sin enviar nada, construye el
documento a mano: carga `Settings.from_env()`, crea el `CoinalyzeClient` con
`settings.coinalyze_api_token`, llama a `collect_payload(..., ai_context_profile=
settings.telegram_preview_profile)` y luego `build_preview_json(payload, pretty=True)`.
Comprueba que cada símbolo trae `daily_history.sessions == 90`.

## Dependencia

Requiere dashboard **>= v1.3.4**: el perfil `max` no existe antes. Con una versión
anterior, `normalize_profile` devuelve 422 y `collect_payload` cae al camino legacy
silenciosamente (payload mucho más pobre, sin error visible).
