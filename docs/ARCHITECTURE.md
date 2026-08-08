# Arquitectura DEV / CI-CD / Producción

Este documento describe el entorno **real** implementado para desarrollar y desplegar
Coinalyze con Codex y Claude Code, usando GitHub como única fuente de verdad.

## Diagrama

```
                              GitHub  (achavezl911/coinanalyze)
                                 │   main protegida · CI · PRs · Secrets
             ┌───────────────────┼───────────────────┐
             │ push/PR           │ CI (self-hosted)  │ workflow_dispatch (deploy)
             ▼                   ▼                    ▼
   ┌───────────────────────────────────────────────────────────────┐
   │  LXC 143  coin-cicd   (10.10.100.2, vlan10, Debian 13)         │
   │  DEV + IA + CI/CD  —  NO producción                            │
   │                                                                │
   │  usuario devops:                                               │
   │    /srv/coinanalyze/repo            (clon base de main)        │
   │    /srv/coinanalyze/worktrees/codex/<tarea>   (rama codex/*)   │
   │    /srv/coinanalyze/worktrees/claude/<tarea>  (rama claude/*)  │
   │    git · gh · Codex CLI · Claude Code · python3.13 · node20    │
   │                                                                │
   │  usuario github-runner:                                        │
   │    /opt/actions-runner  (GitHub Actions self-hosted runner)    │
   │    labels: self-hosted, linux, coinanalyze                     │
   └───────────────────────────────────────────────────────────────┘
                                 │
                                 │ SSH clave dedicada (coinalyze-deploy)
                                 │ artefacto coinalyze-<sha>.tgz + sha256
                                 ▼
   ┌───────────────────────────────────────────────────────────────┐
   │  LXC 140  coinalyze-final  (10.151.1.6 vlan151, Debian 13)     │
   │  PRODUCCIÓN                                                     │
   │                                                                │
   │  coinalyze-deploy ──sudo──> /usr/local/sbin/deploy-coinalyze   │
   │       (usuario mínimo)        (wrapper root = TRUST BOUNDARY,   │
   │                                fuera del repo)                  │
   │                                                                │
   │  /opt/coinalyze/releases/<sha>/   (código + .venv por release) │
   │  /opt/coinalyze/current  -> releases/<sha activo>              │
   │  servicios systemd (usuario coinalyze):                        │
   │    coinalyze-api (uvicorn 127.0.0.1:8000) · -ingest · -ws      │
   │    · -scalp · -daily · -ai-bridge                              │
   │  PostgreSQL 17 local · nginx (8090→8443)                       │
   │  secretos SOLO en /etc/coinalyze/coinalyze.env                 │
   │  estado: /var/lib/coinalyze/deployment.json                    │
   └───────────────────────────────────────────────────────────────┘
```

## Red (verificada)

| Origen | Destino | Resultado |
|---|---|---|
| Windows `10.10.100.101` | DEV `10.10.100.2:22` | ✓ (VS Code Remote-SSH directo) |
| DEV `10.10.100.2` | prod `10.151.1.6:22/8443/8090` | ✓ (deploy + smoke) |
| DEV `10.10.100.2` | prod `150.1.7.140` (red plana) | ✗ aislada — no se usa |
| DEV → Internet (GitHub/apt/npm) | vía gw `10.10.100.1` | ✓ |

`10.10.100.0/28` ya está en el allowlist de nginx/API de prod.

## Principios

1. **GitHub es la única fuente de verdad.** A prod solo llega lo mergeado a `main`.
2. **El código fuente manda** sobre cualquier herramienta auxiliar (p. ej. Graphify).
3. **Trust boundary en prod:** ningún script del repo (editable por agentes) corre como root.
   El único root ejecutable por el deploy es `/usr/local/sbin/deploy-coinalyze`, que no está
   en el repo.
4. **Releases inmutables por commit SHA** con symlink `current` y rollback.
5. **Mínimo privilegio:** usuarios dedicados (`devops`, `github-runner`, `coinalyze-deploy`),
   claves separadas, sudoers acotado, sin root SSH.

Ver también: [DEVELOPMENT_WORKFLOW.md](DEVELOPMENT_WORKFLOW.md), [DEPLOYMENT.md](DEPLOYMENT.md),
[ROLLBACK.md](ROLLBACK.md), [GITHUB_ACTIONS.md](GITHUB_ACTIONS.md), [OPERATIONS.md](OPERATIONS.md),
[AI_ENGINEERING_RULES.md](AI_ENGINEERING_RULES.md).
