# Segmento interno recomendado

Para proteger endpoints internos de FastAPI, el Dashboard valida `API_INTERNAL_ALLOWED_CIDRS` antes de aceptar `X-Internal-Token`.

Valor recomendado en `.env`:

```env
API_INTERNAL_ALLOWED_CIDRS='["127.0.0.1/32","::1/128","10.10.100.0/28"]'
```

Si el Bridge corre como LXC separado, asígnale IP dentro de `10.10.100.0/28` desde el host Proxmox, no desde un script dentro del contenedor. La configuración de red del LXC pertenece al host.
