# Flujo de trabajo — Oikos

> Cómo se lleva una idea desde "se me ocurrió" hasta `main`. Es el flujo spec-first que se fue
> formando entre las Fases 17 y 28, oficializado el **2026-09-25** junto con las tres piezas
> tomadas de GitHub spec-kit (marcadores `[NEEDS CLARIFICATION]`, `Orden de ejecución`
> etiquetado y `/analyze-spec`). spec-kit como herramienta se evaluó y se descartó, ver
> `docs/agents/issue-tracker.md`.
>
> Este archivo define la **secuencia**. El **formato** de specs y tickets vive en
> `docs/agents/issue-tracker.md`, y las reglas del código en `CLAUDE.md` y
> `backend/docs/BUSINESS_RULES.md`. Si difieren, mandan esos archivos.

---

## ¿Lleva spec o no?

| Cambio | Flujo |
|---|---|
| Bug, ajuste de UI, cambio de copy, deuda chica de `docs/TODO.md` | **Corto** (abajo) |
| Cualquier cosa que no se pueda describir en una frase | **Completo** |
| Toca backend **y** frontend a la vez | **Completo** |
| Cambia `models.py`, un contrato de API o una regla de `BUSINESS_RULES.md` | **Completo** |

En caso de duda, flujo completo: una spec de 50 líneas (como `fase_27_spec.md`) cuesta menos
que descubrir una decisión a mitad de implementación.

---

## Flujo completo (feature o fase)

### 1. Ubicar la idea

Revisar `docs/ROADMAP.md` (backlog priorizado y "Fuera de scope") para confirmar que la idea
encaja con el enfoque actual (análisis de gastos, uso personal) y asignarle **número de fase**:
el siguiente libre después del último `docs/specs/fase_NN_spec.md`, sin chocar con una fase ya
planeada en el roadmap.

### 2. `/grilling`

Entrevista sobre la idea hasta que no quede ninguna decisión asumida en silencio: alcance,
modelo de datos, contrato de API, UX, casos borde, qué queda fuera. Los hechos del código los
busca el agente, y las decisiones las toma el dueño.

**Pasar al paso 3 cuando:** el agente no tiene más preguntas en la frontera y el dueño confirma
que hay entendimiento compartido.

### 3. `/to-spec`

Sintetiza la conversación en `docs/specs/fase_NN_spec.md`, con las dos adiciones de Oikos
(`docs/agents/issue-tracker.md`):

- `[NEEDS CLARIFICATION: …]` en línea para lo que quedó abierto. Más de ~3 significa volver al
  paso 2.
- `## Orden de ejecución` con tags de área (`[backend]`/`[frontend]`/`[docs]`/`[infra]`/`[verif]`),
  `Depende de:`, `[P]` y los IDs de decisión que implementa cada paso.

### 4. Resolver los marcadores

El dueño responde cada `[NEEDS CLARIFICATION]`. Cada respuesta reemplaza su marcador y queda
registrada en `## Decisiones resueltas con el usuario (YYYY-MM-DD)`.

### 5. `/analyze-spec NN`

Chequeo de solo lectura antes de escribir código: invariantes del proyecto, consistencia
decisión ↔ paso ↔ test, referencias desactualizadas o impacto no previsto (el fallo que corrigió
"Hallazgos de exploración" en `fase_26_spec.md`) y tags del orden de ejecución.

**Pasar al paso 6 cuando:** no quedan hallazgos **CRÍTICO** ni **ALTO**. Los MEDIO/BAJO se
corrigen o se aceptan explícitamente.

### 6. Rama o worktree

Desde `main` actualizado (`git checkout main && git pull`). Una rama por fase; un worktree en
`.claude/worktrees/` cuando conviene trabajar en paralelo sin tocar el árbol principal.

### 7. Implementar

Siguiendo el `Orden de ejecución`, en orden de dependencias:

- Los pasos `[P]` se pueden repartir entre agentes: `[backend]` → `backend-engineer`,
  `[frontend]` → `frontend-engineer`, `[verif]` y tests → `qa-engineer`.
- `/tdd` si la fase se presta a escribir los tests primero.
- `/alembic-migration` si cambia `backend/app/models/models.py`. Nunca un cambio de schema sin
  migración revisada a mano.
- Una desviación de la spec (algo que la realidad del código obliga a cambiar) se anota en la
  spec o en la entrada del changelog, no se deja implícita. Precedente: las dos clases de
  excepción que la Fase 28 agregó durante la implementación.

### 8. `/run-tests`

pytest, ruff, eslint y prettier. Es el sustituto manual de CI (no hay CI configurado). Un test
que falla se reporta; no se "arregla" en silencio.

### 9. `/code-review`

Revisión del diff de la rama buscando bugs de correctitud. Si toca auth, cookies o CORS, pasar
también por `security-reviewer`: no para abrir trabajo de hardening nuevo, sino para no romper
la base existente.

### 10. `/analyze-spec NN cierre`

Spec vs diff real, decisión por decisión (implementada / parcial / falta / desviada), archivos
cambiados sin decisión que los explique, tests y docs faltantes.

### 11. Docs de cierre

- Entrada en `docs/CHANGELOG.md` (resumen de 3–5 líneas que apunta a la spec, la más reciente
  arriba).
- `docs/ROADMAP.md`: mover la fase a completada y ajustar el backlog.
- `docs/TODO.md`: marcar `[x]` con fecha lo que la fase resolvió y anotar la deuda nueva
  consciente.
- Si cambió un contrato de API, actualizar **ambos** `backend/docs/API_REFERENCE.md` y
  `frontend/docs/API_CONTRACT.md`.
- `backend/docs/BUSINESS_RULES.md` si cambió una regla, y `CLAUDE.md` si cambió un hecho
  operativo.
- `graphify update .` si cambió código.

### 12. Push, PR y merge

```sh
git push -u origin <rama>
gh pr create --base main          # o desde GitHub
# merge desde GitHub, y después:
git checkout main && git pull     # GitHub no actualiza el main local
```

---

## Flujo corto (bug o cambio chico)

Precedente: el popover de analítica fuera de pantalla en mobile (commits `8224739`, `e7a5d37`).

1. **Documentar** el bug en `docs/TODO.md`: cómo se reproduce, causa si se conoce y plan de
   arreglo. Puede ir en su propio commit antes del fix.
2. **Rama** desde `main` actualizado.
3. **Fix**, y verificarlo de verdad: test que reproduzca el bug si es backend, o prueba en el
   navegador (Playwright o manual, al viewport afectado) si es UI.
4. **`/run-tests`**.
5. **Marcar `[x]` con fecha** en `docs/TODO.md`.
6. **Push, PR, merge y `git pull`** en `main`, igual que el paso 12.

Si a mitad del fix aparece una decisión de diseño que no se puede resolver en una frase, se
cambia al flujo completo.

---

## Resumen de una línea

`ROADMAP` → `/grilling` → `/to-spec` → resolver marcadores → `/analyze-spec` → rama →
implementar → `/run-tests` → `/code-review` → `/analyze-spec cierre` → docs → PR → `git pull`.
