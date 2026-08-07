# Prometheus scraping

`/metrics` está protegido igual que `/api/*` cuando `API_INTERNAL_TOKEN` está definido.

## Opción A — Scrape vía Nginx

```yaml
scrape_configs:
  - job_name: coinalyze
    scheme: https
    metrics_path: /metrics
    static_configs:
      - targets: ["IP_DEL_LXC:8443"]
    basic_auth:
      username: operator
      password: "PASSWORD_DASHBOARD"
    tls_config:
      insecure_skip_verify: true
```

## Opción B — Scrape directo con header interno

Usar solo si Prometheus puede alcanzar `127.0.0.1:8000` desde el mismo namespace/red local correspondiente.

```yaml
scrape_configs:
  - job_name: coinalyze-local
    scheme: http
    metrics_path: /metrics
    static_configs:
      - targets: ["127.0.0.1:8000"]
    authorization:
      type: "X-Internal-Token"
      credentials: "API_INTERNAL_TOKEN_VALUE"
```

Si tu versión de Prometheus no soporta headers arbitrarios de esa forma, usa Nginx como reverse proxy y Basic Auth.
