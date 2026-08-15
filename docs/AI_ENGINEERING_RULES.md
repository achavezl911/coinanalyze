# AI Engineering Rules — coinanalyze

> **Documento maestro compartido.** Tanto Codex (ver [`AGENTS.md`](../AGENTS.md)) como
> Claude Code (ver [`CLAUDE.md`](../CLAUDE.md)) DEBEN leer y cumplir este documento antes de
> tocar el código. Si una instrucción de este archivo entra en conflicto con una petición
> puntual, gana este archivo salvo que el humano responsable lo autorice explícitamente.
>
> **Segundo documento obligatorio: [`HANDOFF_IA.md`](HANDOFF_IA.md)** — estado exacto del
> proyecto, SHAs, qué está bloqueado y próxima acción. Índice completo en
> [`README.md`](README.md); arquitectura científica en
> [`SCIENTIFIC_ARCHITECTURE.md`](SCIENTIFIC_ARCHITECTURE.md); decisiones vinculantes en
> [`ARCHITECTURE_DECISIONS.md`](ARCHITECTURE_DECISIONS.md); orden de trabajo en
> [`ROADMAP.md`](ROADMAP.md).

## Contexto de la plataforma

- **GitHub** (`github.com/achavezl911/coinanalyze`) es la **única fuente de verdad** del código.
- El desarrollo ocurre en el **LXC 143 `coin-cicd`** (`10.10.100.2`), NO en producción.
- Producción es el **LXC 140 `coinalyze-final`** (`10.151.1.6`): API FastAPI, colectores,
  PostgreSQL 17 y nginx. Los servicios corren como el usuario `coinalyze` desde `/opt/coinalyze`.
- Los secretos de producción viven **solo** en `/etc/coinalyze/coinalyze.env` (LXC 140) y
  **nunca** en el repositorio ni en el entorno de los agentes.
- El despliegue a producción se hace **exclusivamente** desde `main` mediante GitHub Actions
  (`workflow_dispatch`) → artefacto por commit SHA → wrapper root en producción. Ver
  [`DEPLOYMENT.md`](DEPLOYMENT.md) y [`ROLLBACK.md`](ROLLBACK.md).

## Las 20 reglas

1. **GitHub es la única fuente de verdad.** Nada llega a producción si no está en `main`.
2. **`main` representa código aprobado.** Solo entra vía Pull Request mergeado.
3. **Nunca modificar `main` directamente.** Ni commit ni push directo a `main`.
4. **Cada cambio requiere una rama independiente**, creada desde `origin/main` con un worktree
   propio: `codex/<tarea>` o `claude/<tarea>` (ver "Flujo de trabajo").
5. **Cada implementación requiere tests.** Código nuevo sin pruebas no se considera terminado.
6. **Ejecutar `pytest` antes de cada push** y dejar constancia del resultado.
7. **Ejecutar `ruff check .` antes de cada push.** El árbol debe quedar limpio de lint.
8. **Revisar `git diff` antes de cada commit.** No commitear cambios no intencionados.
9. **Nunca almacenar secretos** (tokens, contraseñas, claves) en el repositorio, en commits,
   en logs, ni en variables versionadas. Usar GitHub Secrets/Environments cuando aplique.
10. **Nunca modificar `/etc/coinalyze` ni los secretos productivos.**
11. **Nunca ejecutar comandos destructivos en el PostgreSQL productivo** (DROP, TRUNCATE,
    DELETE masivo, ALTER que pierda datos) sin control explícito y backup previo.
12. **Nunca hacer `git push --force`** (ni `--force-with-lease`) sobre ramas compartidas.
13. **Nunca hacer merge automático** a `main`. El merge lo aprueba un humano tras la review.
14. **Nunca editar manualmente código productivo vía SSH.** Todo cambio pasa por el repo.
15. **Todo cambio de producción debe corresponder a un commit de `main`** (trazabilidad por SHA).
16. **Toda modificación de esquema** (`sql/schema.sql`, migraciones) debe tener estrategia
    explícita de **migración y rollback**, ser idempotente cuando aplique, y respaldarse antes.
17. **Mantener compatibilidad con la arquitectura existente** salvo autorización explícita.
18. **No cambiar contratos JSON/API silenciosamente.** Un cambio de contrato se documenta y
    se versiona; añade pruebas de contrato.
19. **Añadir pruebas de regresión cuando se arregle un bug** (reproducir primero, luego corregir).
20. **Informar exactamente**: archivos modificados, tests ejecutados y sus resultados.

## Cómo se cierra un hallazgo

Las reglas 5 y 19 no se cumplen con documentación. El orden es obligatorio:

1. **Reproduce el defecto** con un test que falle sobre el commit señalado, y conserva su
   salida exacta. Sin evidencia roja no hay cierre.
2. **Corrige la arquitectura**, no el síntoma.
3. **Demuéstralo**: la mutación que causaba el defecto debe mover la identidad científica o
   quedar estructuralmente impedida antes de escribir. Añade mutation tests sobre las líneas
   exactas.
4. **Ancla la mutación por AST, en el punto de llamada real.** Reescribir la primera aparición
   textual de una expresión no prueba nada: si esa aparición está dentro de una región y la
   ejecutada está fuera, el digest se mueve y el defecto sigue vivo.
5. **No debilites un test existente** para que pase el tuyo. Si un test debe cambiar porque
   la estructura cambió, hazlo más estricto, no más laxo.
6. **Si falta evidencia, decláralo** con `MISSING_EXTERNAL_EVIDENCE`. Nunca la sustituyas por
   una afirmación.

Precedentes, los tres de la misma serie:

- `c879bdec` declaró cerrado un hallazgo (A-02) que seguía abierto, apoyándose en una
  afirmación documental. Refutado con dos mutaciones. Ver ADR-008.
- `700f7695` y `450cf2fb` declararon el cierre con una suite verde cuyas mutaciones tocaban la
  primera aparición textual, no el punto de llamada real. Refutados con tres hallazgos P1. Ver
  [`HANDOFF_IA.md`](HANDOFF_IA.md) §6.1 y ADR-010.

## Aprobación: qué la constituye y qué no

`DECIDED` — ver [`HANDOFF_IA.md`](HANDOFF_IA.md) §2.1, que es la fuente completa.

- **ChatGPT Work siempre cuestiona y valida de forma independiente el código de Claude.**
  Revisa el árbol y ejecuta sus propias mutaciones; no revisa el informe.
- **Un informe de Claude no es una aprobación. Un CI en verde tampoco.** Una suite verde sólo
  demuestra que las mutaciones ya escritas se detectan.
- **Si Work refuta, entrega veredicto y prompt correctivo juntos**, en el mismo mensaje.
- **Todo prompt a Claude exige actualizar [`HANDOFF_IA.md`](HANDOFF_IA.md) en GitHub, sin
  excepción**, e incluye HEAD, alcance, invariantes, pruebas rojas, aceptación, validación,
  evidencia y prohibiciones.

## Continuidad

Si un cambio altera el estado del proyecto, actualizar [`HANDOFF_IA.md`](HANDOFF_IA.md),
[`ROADMAP.md`](ROADMAP.md) y [`ARCHITECTURE_DECISIONS.md`](ARCHITECTURE_DECISIONS.md) **es
parte del entregable**. `ARCHITECTURE_DECISIONS.md` es append-only: una decisión no se edita,
se supersede.

Usa estados explícitos —`CONFIRMED`, `DECIDED`, `PLANNED`, `BLOCKED`, `EXTERNAL_UNVERIFIED`,
`MISSING_EXTERNAL_EVIDENCE`— en vez de prosa ambigua.

## Restricciones específicas de Git para agentes

Permitido: leer/modificar código en el worktree propio, ejecutar tests y ruff, `git add/commit`,
`git push` de la **propia rama**, `gh pr create`, `gh pr review`/comentar.

Prohibido: trabajar sobre `main`; `push --force`; borrar ramas protegidas; merge a `main`;
tocar producción por SSH; manipular secretos productivos; reescribir historia compartida.

## Flujo de trabajo (resumen)

```
tarea → coin-worktree-create <codex|claude> <slug>   # rama desde origin/main
      → editar en /srv/coinanalyze/worktrees/<agent>/<slug>
      → ruff check .  &&  pytest
      → git diff → git add → git commit
      → git push -u origin <rama>
      → gh pr create        # NUNCA merge; lo hace un humano tras review + CI verde
```

Detalle completo en [`DEVELOPMENT_WORKFLOW.md`](DEVELOPMENT_WORKFLOW.md).

## Colaboración Codex + Claude

- Un worktree por agente y por tarea: **nunca** dos agentes en el mismo worktree a la vez.
- Si un agente implementa una feature, el otro puede actuar como **reviewer del PR**.
- GitHub (PRs, reviews, checks de CI) es el **único** mecanismo de coordinación entre ambos.

## Entorno y comandos del proyecto

- Python `>=3.11,<3.14` (producción usa 3.13). Dependencias runtime en `requirements.lock`;
  herramientas dev (`pytest`, `pytest-asyncio`, `ruff`) en el extra `[dev]` de `pyproject.toml`.
- **PostgreSQL 17 es la referencia actual**, en producción y en CI. La capa científica se
  prueba contra un clúster 17 aislado con `TEST_DATABASE_URL` exportada, como hace
  `.github/workflows/ci.yml`, y debe terminar con **0 failed y 0 skipped**.
- Preparar entorno local:
  ```bash
  python3 -m venv .venv && . .venv/bin/activate
  pip install -r requirements.lock && pip install -e '.[dev]'
  ```
- Lint: `ruff check .`  ·  Tests: `pytest -q`  ·  Sintaxis: `python -m compileall -q app`
- No introducir dependencias nuevas sin justificarlo y fijarlas en `requirements.lock`.

## GRAPH-FIRST POLICY (Graphify)

Para exploración de arquitectura, análisis de dependencias, análisis de impacto o localización
de código relevante:

1. **Consulta Graphify primero** (`graphify query "<pregunta>"`, `graphify affected "<X>"`,
   `graphify path "<A>" "<B>"`, `graphify explain "<concepto>"`).
2. Usa `graphify-out/GRAPH_REPORT.md` para orientación arquitectónica amplia.
3. Identifica el **conjunto mínimo** de archivos fuente relevantes.
4. Lee y **verifica esos archivos directamente**.
5. El **código fuente es la autoridad** cuando contradice al grafo.
6. Nunca tomes decisiones de implementación **solo** desde `graph.json`.
7. Actualiza el grafo tras cambios estructurales (`graphify update .`).

El objetivo no es impedir leer código, sino evitar exploración repetitiva e innecesaria y reducir
el consumo de contexto. Si Graphify falla o está ausente, continúa leyendo el source con
normalidad. Detalle completo en [GRAPHIFY.md](GRAPHIFY.md).
