# Graphify — knowledge graph del repositorio

Graphify convierte el código, SQL, configs y docs del repo en un **grafo de conocimiento
consultable** para que Codex y Claude Code entiendan la arquitectura sin recorrer el repo entero
en cada sesión. **Es una herramienta auxiliar: el código fuente siempre tiene precedencia sobre
el grafo.** Si Graphify falla, los agentes deben seguir trabajando leyendo el source normalmente.

- Solo vive en el **LXC 143 `coin-cicd`** (dev). **Nunca** en producción (LXC 140).
- No forma parte del runtime de Coinalyze; el artefacto de despliegue **excluye** `graphify-out/`
  (ver `.github/workflows/deploy-production.yml`).

## Versión / instalación (como `devops`)

```bash
uv tool install "graphifyy[sql]"     # paquete graphifyy, CLI graphify; extra sql = tree-sitter-sql
graphify --version                   # 0.9.36
```

Registro project-scoped de la skill (ya versionado en el repo: `.claude/`, `.codex/`, y secciones
en `AGENTS.md`/`CLAUDE.md`):

```bash
graphify install --project --platform claude
graphify install --project --platform codex
```

## Generar / actualizar el grafo

```bash
graphify update . --force     # extracción AST determinista (sin coste LLM); reconstruye graph.json,
                              # GRAPH_REPORT.md y graph.html en graphify-out/
```

El naming semántico de comunidades (opcional) requiere backend LLM:
`graphify label .` (usa GEMINI_API_KEY / la sesión del asistente). No es necesario para consultar.

## Consultar (query-first)

```bash
graphify query "How is CVD calculated?"          # subgrafo BFS acotado (--budget N tokens)
graphify affected "cvd_matrix"                   # qué se ve impactado si cambio X (análisis de impacto)
graphify path "collectors" "PostgreSQL"          # ruta más corta entre dos nodos
graphify explain "compute_scalp_summary"         # explicación de un nodo y vecinos
graphify god-nodes --top 12                      # hubs arquitectónicos
```

`GRAPH_REPORT.md` sirve para orientación arquitectónica amplia; `query/affected/path/explain`
devuelven subgrafos pequeños (mucho más baratos en tokens que `grep` o leer decenas de archivos).

## Qué se versiona y qué no

`.gitignore` versiona **solo** `graphify-out/graph.json` y `graphify-out/GRAPH_REPORT.md`.
Se excluyen (regenerables/pesados/locales): `graph.html`, `manifest.json`, `cache/`, `cost.json`,
`.graphify_labels*`, backups de fecha. `.claudeignore` excluye `graphify-out/` del **contexto
directo** de Claude para no invalidar el prompt cache: Claude usa `graphify query` (que lee
`graph.json` por dentro y devuelve solo lo relevante), no carga el `graph.json` completo.

`.graphifyignore` excluye del grafo lo que no es arquitectura propia: `static/vendor/` (JS
minificado de terceros), `graphify-out/`, `.git/`, `.venv/`, `.claude/`, `.codex/`. Esto **no**
afecta runtime (vendor sigue versionado y sirviéndose en prod); solo limpia el grafo (sin él, los
god-nodes se llenan de símbolos minificados sin valor).

## Política de actualización

Reconstruir el grafo tras cambios **estructurales**: nuevas funciones/módulos importantes, nuevas
dependencias, cambios de SQL, o eliminación de componentes. Flujo:

```
cambio estructural → tests → graphify update . → git diff → commit → PR
```

La regla GRAPH-FIRST está en `docs/AI_ENGINEERING_RULES.md`, `AGENTS.md` y `CLAUDE.md`.

## Hooks y worktrees (decisión de diseño)

- Los hooks **PreToolUse de Claude Code** (`.claude/settings.json`) están en modo **normal (no
  strict)**: sugieren consultar el grafo antes de búsquedas amplias, **sin bloquear** lecturas. El
  modo `--strict` (bloquea la primera lectura hasta correr un `graphify query`) queda documentado
  como opción futura tras más pruebas.
- El hook de Codex (`.codex/hooks.json`) es un **no-op** intencional (Codex Desktop rechaza
  `additionalContext` en PreToolUse); la guía de Codex viene de `AGENTS.md`.
- **NO se instaló** el git hook `post-commit` de auto-rebuild (`graphify hook install`). Motivo:
  con múltiples worktrees (`codex/*`, `claude/*`) que comparten el git dir común, un rebuild
  automático por commit puede actuar sobre el working tree equivocado o mezclar ramas. En su lugar
  la actualización es **manual y por rama** (`graphify update .`), lo que garantiza que un commit de
  Codex no corrompe el grafo de Claude. Cada worktree regenera su propio `graph.json` bajo demanda.

## Merge driver para `graph.json`

Para evitar conflictos cuando dos ramas (p. ej. `codex/*` y `claude/*`) modifican `graph.json`,
Graphify ofrece un merge driver de unión. Registro **local** (una vez por clon):

```bash
git config merge.graphify.driver "graphify merge-driver %O %A %B"
```

`.gitattributes` ya marca `graphify-out/graph.json merge=graphify`. Si el driver no está
registrado, git usa el merge por defecto; ante conflicto, siempre se puede resolver regenerando
con `graphify update .` (el grafo es un artefacto derivado y determinista).

## Freshness en CI

La versión actual **no** expone un comando oficial de *freshness*. En vez de un mecanismo frágil
por timestamps, la recomendación (no bloqueante) es un job separado que ejecute
`graphify update . --force` y, si `git diff --quiet graphify-out/graph.json` detecta cambios, emita
un **warning** (nunca bloquee el PR). Se documenta como mejora opcional para no ralentizar ni
fragilizar el CI requerido (`lint-and-test`).

## Seguridad

Antes de versionar `graphify-out/` se escanea `graph.json` por secretos (`password`, `token`,
`api_key`, `secret`, `gho_`, `sk-`, patrones de token de bots). El grafo contiene solo
**identificadores** de código (nombres de funciones/tablas/archivos), no **valores**; el `.env`
real está fuera del repo y no se parsea. Nunca hacer commit de un grafo contaminado.

## Reinstalar / eliminar

```bash
graphify uninstall            # quita la skill de las plataformas detectadas
graphify uninstall --purge    # además borra graphify-out/
uv tool uninstall graphifyy   # quita el CLI
```

## Troubleshooting

- **`.sql` no aparece en el grafo:** falta el extra sql → `uv tool install "graphifyy[sql]" --force`.
- **god-nodes con símbolos raros (`Tn`, `hi()`):** JS minificado de vendor sin excluir → revisar
  `.graphifyignore`.
- **`graphify: command not found` en scripts no interactivos:** exportar
  `PATH="$HOME/.local/bin:$PATH"` (uv instala ahí).
- **Grafo desactualizado:** `graphify update . --force`.
- **MCP:** `graphify-mcp` existe pero **no se expone** en esta fase (decisión: mantener simple; ver
  MCP como mejora futura para herramientas estructuradas query_graph/get_node/affected).
