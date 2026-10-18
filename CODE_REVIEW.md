# Auditoría de Proyecto: Oikos — Finanzas Personales

**Fecha**: 18 de octubre de 2026
**Analista**: Claude Code
**Tipo de Proyecto**: Fullstack, uso personal de un solo dueño (ver `AGENTS.md` y `docs/ROADMAP.md`)
**Stack**: FastAPI + SQLAlchemy + Alembic + PostgreSQL 16 / Next.js (App Router) + TanStack Query + Zustand + Tailwind

---

## 0. Nota de calibración

Igual que la auditoría del 2026-09-19: Oikos es una herramienta personal. Se evalúa con exigencia
normal estructura, arquitectura, mantenibilidad, modularidad, testing, documentación y UX; **no**
se penaliza hardening de seguridad más allá del baseline de la Fase 26 (cookies `httpOnly` + CSRF,
verificación de email, rate limit en memoria). Un bug que rompe el uso diario del dueño (login de
Google) se marca igual, como bug de producto.

Alcance de esta pasada: lectura de `AGENTS.md`, `docs/TODO.md` completo, estructura y tamaños de
código, manejo de excepciones, locking, estado de tests/lint del frontend. **No** se corrió la suite
del backend (requiere Docker/testcontainers; el `ruff` global no está instalado fuera del venv) ni
se revisó cada router línea a línea.

---

## 1. Resumen Ejecutivo

### Estado General: 8.1/10 (anterior: 7.6/10, 2026-09-19)

**Veredicto**: MUY BUENO. En un mes el proyecto pasó de las Fases 26 a 37 sin degradar la
disciplina: ~717 tests backend (contra 251 de la auditoría anterior), Postgres real como default
de la suite, guardia de `alembic check`, aritmética de calendario centralizada, y tres fases nuevas
(sobres, gasto contra sobre, recurrentes) construidas **sin tocar `ledger.py` ni `Transaction`**.
Las debilidades son ahora de escala interna, no de fundamentos: funciones de router largas,
frontend sin tests ni typecheck en el flujo, sin CI, y la deuda de decisiones sin `/grilling`
(Fases 35 y 37) que el dueño todavía debe cerrar.

### Top 3 Problemas Críticos

1. **Login con Google sigue caído en producción (`disabled_client`)** — Impacto: Alto (para el uso
   diario). Abierto desde 2026-09-19, hace casi un mes sin resolución visible en `docs/TODO.md`.
   No es código. Decisión pendiente: si la apelación no ha respondido, recrear el Client ID
   (plan B ya documentado) en vez de seguir dependiendo del reset de contraseña como workaround.
2. **Frontend sin red de seguridad automática** — Impacto: Medio. Cero tests (no hay runner),
   `tsc` no está en ningún script ni hook (hoy pasa limpio, pero nada lo exige), y sin CI nada
   corre `pnpm build`. Con la lógica de fechas en `lib/dates.ts`/`lib/dateRanges.ts` (367 líneas)
   verificada solo con Playwright manual, es la zona más expuesta a regresiones silenciosas.
3. **Funciones de router/servicio de gran tamaño en el camino de dinero** — Impacto: Medio.
   `actualizar_transaccion` ≈ 204 líneas, `crear_transaccion` ≈ 160, `obtener_resumen`
   (dashboard) ≈ 171, y `services/funds.py` 757 líneas. Cada fase añadió una rama (`fund_id`,
   idempotencia, replay con enlace, alertas) al mismo cuerpo. Están bien cubiertas por tests, pero
   son el siguiente lugar donde "el código duele al modificarlo".

### Fortalezas Destacadas

- ✅ **Invariantes financieras explícitas y testeadas**: libro append-only para sobres
  (`SUM(fund_entries.amount)`, sin columna `balance`), row-locks con orden definido
  (transacción → sobre → cuentas), tests de concurrencia dedicados (`test_concurrency.py`,
  `test_funds_concurrency.py`, `test_recurring_concurrency.py`), dinero siempre `Decimal`/`Numeric(14,2)`.
- ✅ **Suite de pruebas seria**: ~717 tests, Postgres 16 desechable por defecto, abort explícito
  sin Docker, guarda contra bases sin "test" en el nombre, y `alembic check` que falla si
  `models.py` diverge de las migraciones.
- ✅ **Documentación y proceso excepcionales**: 32 specs con decisiones numeradas, `TODO.md` con
  fechas y causas raíz, `AGENTS.md` como fuente única para tres herramientas, flujo
  `grilling → spec → analyze → implementar → run-tests → review`.

---

## 2. Análisis por Área

### 2.1 Estructura
**Score**: 8.5/10

**Hallazgos**:
- Separación clara `api/` · `core/` · `services/` · `schemas/` (por dominio) · `models/`; frontend
  con route groups `(auth)`/`(dashboard)` y carpetas de componentes por dominio (`funds/`,
  `recurring/`, `transactions/`, `modals/`).
- `services/` ya no es "naciente": `ledger.py`, `funds.py`, `recurring.py` (atributos de dominio
  reales, 757 y 524 líneas).
- `AGENTS.md` describe `services/` como "naciente (ledger, funds)" y omite `recurring.py`; la
  lista de modelos dice 16 (verificar contra `models.py`, ahora 455 líneas).
- `frontend/types/generated/api.ts` (4.406 líneas) convive con `types/api.ts` manual (447) —
  deliberado (Decisión 16.3.2), pero es duplicación a medio migrar.

**Recomendaciones**:
- Actualizar la descripción de `services/` en `AGENTS.md` para incluir `recurring.py`.

---

### 2.2 Arquitectura
**Score**: 8.5/10

**Hallazgos**:
- La capa de "compromiso" (sobres) se montó como **capa de asignación** sobre las cuentas sin
  alterar `Account.balance` ni `ledger.py`: aislamiento correcto, cero regresión en cifras existentes.
- `core/periods.py` (funciones puras, zona inyectada, límite superior exclusivo) eliminó una
  familia entera de bugs de borde de periodo (QA-019, H11, QA-038).
- Excepciones de dominio uniformes: los únicos `HTTPException` restantes están en
  `core/security.py` (dependencia de auth, aceptable). En `transactions.py` quedan comentarios
  `# 🔁 antes: raise HTTPException(...)` (líneas 98, 208, 220, 524) — ruido de migración.
- Hay 11 bloques `except Exception` (transactions ×3, dashboard, recurring, budget_alerts, etc.).
  Los de "no tumbar la transacción por un fallo de alertas" están justificados y documentados;
  los de `dashboard.py:400` y `transactions.py:291/449/597` convierten cualquier error en 500
  genérico y ocultan bugs de programación detrás de un mensaje de dominio (se loguean con
  `logger.exception`, así que es visibilidad, no pérdida).
- Scheduler en proceso (solo resumen semanal) y rate limit en memoria: coherentes con un worker.

**Recomendaciones**:
- Dividir `actualizar_transaccion` y `crear_transaccion` en pasos de servicio
  (`resolver_cuenta_y_categoria`, `aplicar_enlace_sobre`, `evaluar_alertas`) dentro de
  `services/`, dejando el router como orquestador.
- Borrar los comentarios `🔁 antes:` — la historia vive en git y `CHANGELOG`.

---

### 2.3 Mantenibilidad
**Score**: 8/10

**Hallazgos**:
- Comentarios de decisión (`Fase 31 (Decisión B4, QA-015)…`) hacen trazable el porqué; costo:
  densidad alta de comentarios con numeración de fases dentro del código (se vuelven ruido cuando
  la fase deja de ser contexto vivo).
- Nomenclatura mezclada español/inglés en backend (`crear_transaccion` / `models.Account`) —
  consistente por convención (verbos de dominio en español), bajo impacto en solitario.
- Duplicación conocida y anotada: lista de invalidaciones de TanStack Query copiada en
  `useRecurring.ts`, `TransactionModal` y captura (`TODO` Fase 37). Es el patrón que históricamente
  produce "olvidé invalidar X" cuando se añade una query nueva (ya pasó con `preferred_currency`).
- `/accounts/[id]` (652 líneas) y `/categories/[id]` (414) tienen su propio modal de edición en
  línea, no `EditTransactionModal` (TODO 🟡 abierto desde Fase 31).
- `docs/ROADMAP.md` encabezado dice "Fase 0 a Fase 32" cuando el CHANGELOG llega a la 37.

**Recomendaciones**:
- Extraer `invalidateAfterTransactionChange(queryClient)` (≈1–2 h) y reutilizarlo en las tres copias.
- Reusar `EditTransactionModal` en `/accounts/[id]` y `/categories/[id]`.

---

### 2.4 Modularidad
**Score**: 8/10

**Hallazgos**:
- Servicios con funciones puras separadas de casos de uso con lock (`funds.py`:
  ritmo/aporte requerido vs. operaciones) — testeables sin DB (`test_funds_logic.py`,
  `test_recurring_logic.py`).
- `models.py` sigue como archivo único (455 líneas, 16 modelos) — aún razonable.
- `funds.py` (757 líneas) mezcla cálculo de ritmo, disponibilidad, casos de uso, y enlace a gastos.
  Candidato a dividirse (`funds/pacing.py`, `funds/ledger.py`, `funds/spending.py`) cuando se
  vuelva a tocar.
- Frontend: páginas de 500–650 líneas (`accounts/[id]`, `settings`, dashboard raíz) siguen siendo
  orquestadores largos aunque `transactions/page.tsx` se descompuso bien (370).

**Recomendaciones**:
- No dividir `funds.py` preventivamente; hacerlo en la siguiente fase que lo modifique.
- Dividir `settings/page.tsx` (606) por secciones (zona horaria, API keys, moneda, baja).

---

### 2.5 Seguridad (contexto personal)
**Score**: 7.5/10

**Hallazgos**:
- Baseline sólido y vigente: cookies `httpOnly` + CSRF double-submit, refresh rotativo hasheado,
  verificación de email obligatoria, fix del auto-link de Google (Fase 23), `rclone.conf`, `.env`
  y `backups/` en `.gitignore` y fuera del índice de git (verificado).
- Sigue publicado a internet vía Funnel con un único usuario; el dueño decidió explícitamente no
  invertir más aquí. No se propone trabajo nuevo.
- El runtime `docker-compose.yml` publica `0.0.0.0:8000/3000`; confirmado con el dueño como
  riesgo teórico (host solo con Tailscale).
- Sin escáner de dependencias automatizado (no hay CI); riesgo aceptado.

**Recomendaciones**: ninguna nueva. Revalidar solo si cambia el modelo de despliegue.

---

### 2.6 Documentación
**Score**: 9/10

**Hallazgos**:
- Referencia por capa (`ARCHITECTURE`, `BUSINESS_RULES`, `API_REFERENCE`, `API_CONTRACT`,
  `STATE_AND_FETCHING`) y las dos últimas actualizadas con sobres y recurrentes.
- `README.md` es breve (103 líneas) y correcto; menciona sobres y semilla de Fase 37.
- Pequeños desfases: encabezado de `ROADMAP.md` (Fase 32), y `TODO.md` aún lista como "pendiente"
  la revisión D1–D20 de la Fase 37 aunque `AGENTS.md` dice que el dueño las revisó el 2026-10-18
  (la casilla debería cerrarse). `TODO.md` ya tiene 800 líneas: la sección "Resueltos" y las
  entradas `[x]` largas dificultan ver lo abierto.
- `.scratch/` (QA no versionado) guarda reportes con evidencia que `TODO.md` solo cita.

**Recomendaciones**:
- Mover los `[x]` de `TODO.md` a `docs/archive/TODO_resueltos.md` y dejar solo lo abierto (≈1 h).
- Sincronizar encabezado de `ROADMAP.md` y casilla D1–D20 de la Fase 37.

---

### 2.7 UX/Usabilidad
**Score**: 8/10

**Hallazgos**:
- Tres QA completos (2026-09-26, 10-03, 10-18) con fixes sistemáticos: estados de error con
  "Reintentar" (`QueryErrorState`), diálogos accesibles (`role`, trampa de foco), tuteo
  consistente, zona horaria del usuario en todas las vistas.
- Features nuevas bien pensadas para el flujo real: aviso antes de borrar un sobre con gastos,
  "Cuota de {mes} cumplida ✓", pendientes recurrentes en el dashboard.
- Abiertos y relevantes para el uso real: calendario recurrente de 12 tarjetas apiladas en móvil;
  sugerencias descartadas que reaparecen (D15); sin notificación de pendientes recurrentes (D2);
  "disponible real" sin decisión sobre cuentas `credit` (TODO Fase 35 D1).
- Pendiente del dueño: contrastar el cuadre USD de "Disponible real" con datos reales (TODO A3).

**Recomendaciones**:
- Cerrar A3 con datos reales antes de confiar en la cifra de disponible.
- Plegar el calendario por mes en móvil.

---

## 3. Recomendaciones Priorizadas

### Quick Wins (Horas)
1. Añadir `"typecheck": "tsc --noEmit"` a `frontend/package.json` y al `pre-commit`/`run-tests` — 1 h
2. Extraer `invalidateAfterTransactionChange(queryClient)` y usarlo en 3 sitios — 1–2 h
3. Eliminar comentarios `# 🔁 antes: raise HTTPException` en `transactions.py` — 15 min
4. Corregir encabezado de `ROADMAP.md` y cerrar casilla D1–D20 en `TODO.md` — 30 min
5. Archivar los `[x]` de `TODO.md` — 1 h
6. Hacer atómico el tope de 100 reglas recurrentes (lock sobre el usuario o `COUNT` en la misma sentencia) — 1–2 h

### Mejoras Medianas (Días)
1. Descomponer `crear_/actualizar_transaccion` en pasos de `services/` — 1–2 días
2. Tests de frontend para `lib/dates.ts`, `lib/dateRanges.ts`, `validateAmount.ts` (Vitest, solo funciones puras) — 1 día
3. CI mínimo (GitHub Actions): ruff + pytest con servicio Postgres + eslint + tsc + build — 0,5–1 día
4. Reusar `EditTransactionModal` en `/accounts/[id]` y `/categories/[id]` — 0,5–1 día
5. Decisión de producto + implementación: excluir lo pagado con sobre de alertas de presupuesto (Fase 36 D8) — 1 día

### Refactoring Mayor (Semanas)
1. Migrar los call sites de `types/api.ts` manual a `types/generated/api.ts` — 1 semana, oportunista
2. Dividir `services/funds.py` en subpaquete cuando se toque en la próxima fase — ~2–3 días, no preventivo

---

## 4. Próximos Pasos Sugeridos

### Acciones Inmediatas (Esta semana)
1. Resolver el login de Google (consultar apelación; si no hay respuesta, recrear Client ID + consent screen real).
2. Cerrar los pendientes del dueño: contraste de A3 (USD en "Disponible real") y `pg_dump` + reporte X1 si aún no se desplegó Fase 34.
3. Quick wins 1, 3 y 4 (< 2 h en total).

### Roadmap de Mejoras (Próximo mes)
1. CI mínimo + tests Vitest de utilidades de fecha antes de la Fase 38 (CDT), que volverá a tocar fechas y dinero.
2. Refactor de `crear_/actualizar_transaccion` antes de agregar la próxima rama (p. ej. transferencias QA-030).
3. Decidir con `/grilling` los puntos que las Fases 35 y 37 tomaron sin él y que condicionan las siguientes (cuentas de crédito en disponible real, notificar pendientes).

---

## 5. Métricas Clave

| Área | Score | Prioridad |
|------|-------|-----------|
| Estructura | 8.5/10 | Baja |
| Arquitectura | 8.5/10 | Media |
| Mantenibilidad | 8/10 | Media |
| Modularidad | 8/10 | Media |
| Seguridad (contexto personal) | 7.5/10 | Baja |
| Documentación | 9/10 | Baja |
| UX/Usabilidad | 8/10 | Media |

**Score General**: 8.1/10

Datos de apoyo: ~717 tests backend en 35 archivos; backend ≈ 8,5 mil líneas en `app/`; frontend
`tsc --noEmit` y `eslint` limpios al momento de la auditoría; 361 commits; 32 specs de fase.
