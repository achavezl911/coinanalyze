<!--
Antes de abrir la PR, lee docs/AI_ENGINEERING_RULES.md.
Si eres una IA: no mergeas, no despliegas, no tocas producción. Ver ADR-007.
Borra las secciones que no apliquen, pero NO borres "Validación" ni "Límites".
-->

## Qué cambia y por qué

<!-- Una o dos frases. El problema real, no el resumen del diff. -->

## Base y apilamiento

- Base de esta PR: `main` / `<rama>` ← **indícalo explícitamente**
- ¿Está apilada sobre otra PR sin mergear? sí / no. Si sí: **`Do not merge`** hasta que la
  base entre en `main`, e indica el orden obligatorio.

## Estado del trabajo

| Elemento | SHA | Estado |
|---|---|---|
| <!-- commit de código --> | | |
| <!-- commit documental --> | | |

Estados válidos: `CONFIRMED` · `DECIDED` · `PLANNED` · `BLOCKED` · `EXTERNAL_UNVERIFIED` ·
`MISSING_EXTERNAL_EVIDENCE`. No declares como confirmado lo que no reprodujiste.

## Reproducción del defecto (si esto corrige algo)

<!--
Regla 19: reproducir primero, corregir después.
Pega la salida REAL de las pruebas rojas antes del arreglo. No la parafrasees.
-->

```text

```

## Integridad científica

Marca sólo lo que aplique y **pega los valores**, no los describas.

- [ ] Identidad científica **sin cambios** · digest: `…`
- [ ] Identidad científica **recomputada** · anterior `…` → nuevo `…` · justificación de por
      qué la ventana de sustitución sigue abierta (sin manifest spec-v4 ni resultado
      autoritativo)
- [ ] Runtime contract digest **sin cambios**: `c9cbe967b1f256644c0caf1ec851ea5a73d67029286afe0bb04461f582a21b00`
- [ ] Hashes legacy spec v1/v2/v3 **sin cambios**: `e2f967bb…`, `2f21afe9…`, `7fd50764…`
- [ ] Componentes de identidad añadidos/eliminados: <!-- listar -->
- [ ] Nuevas mutation tests para las líneas exactas que este PR toca
- [ ] No se ha debilitado ningún test existente

## Contratos y esquema

- [ ] Sin cambios de contrato JSON/API
- [ ] Cambio de contrato **documentado y versionado**, con pruebas de contrato (regla 18)
- [ ] Sin cambios de esquema
- [ ] Cambio de esquema con estrategia explícita de **migración y rollback**, idempotente
      donde aplique (regla 16)

## Validación (ejecutada, con resultados reales)

Pega números, no adjetivos.

- `ruff check .` → 
- `python -m compileall -q app scripts tests` → 
- `pytest -q` con PostgreSQL 17 → `N passed, N failed, N skipped` (**skipped debe ser 0**)
- `node --test tests/js/` → 
- `git diff --check` → 
- `graphify update .` → 
- GitHub Actions: <!-- URL del run y su conclusión real -->

## Límites — confirmación explícita

- [ ] Sin merge
- [ ] Sin deploy
- [ ] Sin cambios en producción ni en `/etc/coinalyze`
- [ ] Sin manifest spec-v4
- [ ] Sin kernel-v2
- [ ] Sin migraciones ni backfill
- [ ] Sin calibración ni selección de parámetros
- [ ] Sin Trade Tape/Footprint
- [ ] Sin `push --force`
- [ ] Sin secretos en el diff

## Continuidad

- Documentación actualizada: <!-- ficheros --> 
- Si esto cambia el estado del proyecto, ¿está reflejado en `docs/HANDOFF_IA.md`,
  `docs/ROADMAP.md` y `docs/ARCHITECTURE_DECISIONS.md`? sí / no / no aplica
- **Próxima acción exacta** para quien retome esto:
