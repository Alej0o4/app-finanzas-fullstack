# Auditoría de Proyecto: Oikos — Finanzas Personales

**Fecha**: 25 de octubre de 2026
**Analista**: Claude Code
**Tipo de Proyecto**: Fullstack, uso personal de un solo dueño (ver `AGENTS.md` y `docs/ROADMAP.md`)
**Stack**: FastAPI + SQLAlchemy + Alembic + PostgreSQL 16 / Next.js 16 (App Router) + TanStack Query + Zustand + Tailwind

---

## 0. Nota de calibración

Igual que las auditorías del 2026-09-19 y 2026-10-18: Oikos es una herramienta personal. Se evalúa
con exigencia normal estructura, arquitectura, mantenibilidad, modularidad, testing, documentación y
UX; **no** se penaliza hardening de seguridad más allá del baseline de la Fase 26.

Alcance: lectura de `AGENTS.md`, `docs/TODO.md`, la auditoría anterior (2026-10-18), métricas de
tamaño/funciones largas (AST), estado de CI/typecheck/tests de frontend y verificación puntual de
cada hallazgo anterior. **No** se corrió la suite del backend (requiere Docker/testcontainers) ni se
revisó cada router línea a línea. Esta pasada es un **delta** sobre la anterior: cubre las Fases 38
(CDT), 39 (transferencias) y 40 (dashboard navegable) y la limpieza de código muerto (#29).

---

## 1. Resumen Ejecutivo

### Estado General: 8.2/10 (anterior: 8.1/10, 2026-10-18)

**Veredicto**: MUY BUENO, estable. En una semana entraron tres fases que tocan dinero (CDT,
transferencias, dashboard por mes) sin romper el aislamiento de `ledger.py`/`Transaction` salvo
donde la Fase 39 lo decidió explícitamente (transferencias dentro del saldo, con un `/grilling`).
La suite creció de ~717 a **893 tests** en 46 archivos, y la limpieza #29 bajó funciones largas
(`actualizar_transaccion` 204→180, `crear_transaccion` 160→156). Pero **ninguno de los tres
problemas estructurales de la semana pasada se atacó**: sigue sin CI, sin typecheck ni tests de
frontend, y las funciones del camino de dinero siguen siendo las más largas del repo. La deuda ya
no es de fundamentos sino de *red de seguridad* justo cuando la superficie de dinero crece.

### Top 3 Problemas Críticos

1. **Sin CI, sin `tsc` en el flujo y sin tests de frontend** — Impacto: Medio-Alto. Idéntico a la
   semana pasada y sin movimiento, mientras la Fase 40 agregó `categories/[id]/page.tsx` (696
   líneas, ahora la página más grande) y la 39 más lógica de monedas/fechas en el cliente.
   `grep` no encuentra ningún runner (`vitest`/`jest`) ni script `typecheck` en `package.json`; el
   skill `run-tests` incluso instruye "no inventes uno". Un 893-tests backend con frontend a ciegas
   es una asimetría: los bugs de fecha/moneda que ya ocurrieron (QA-019, H11) vivían justo ahí.
2. **Login con Google sigue caído en producción (`disabled_client`)** — Impacto: Alto para el uso
   diario. Abierto desde 2026-09-19 (**5 semanas**). No es código; el plan B (recrear el Client ID)
   está documentado en `docs/TODO.md` y no se ha ejecutado.
3. **Funciones largas en el camino de dinero** — Impacto: Medio. `actualizar_transaccion` 180
   líneas, `obtener_resumen` (dashboard) 172, `crear_transaccion` 156, más `funds.py` (751) y
   `transactions.py` (645). Cada fase agrega una rama (`fund_id`, idempotencia, transferencias en
   `GET /movements`) al mismo cuerpo. Bien cubiertas por tests, pero es donde el próximo cambio dolerá.

### Fortalezas Destacadas

- ✅ **Disciplina de proceso intacta a ritmo alto**: Fases 38-40 con spec numerada, `/grilling` o
  revisión del dueño documentada, `analyze-spec` y code review (commit `1f0eecd` corrige hallazgos
  de revisión de la 40). 35 specs, CHANGELOG fase a fase.
- ✅ **Suite seria y creciente**: 893 tests, Postgres 16 desechable por defecto, guarda `alembic
  check`, tests de concurrencia dedicados. La caída de `test_cdt_concurrency` se diagnosticó y
  corrigió en 1 día (`aa62aed`, fixture con CDT ya vencido tras bloquear redención anticipada).
- ✅ **Invariantes financieras explícitas**: libro append-only de sobres, orden de locks
  documentado, transferencias que "no son flujo", `Decimal`/`Numeric(14,2)` siempre, `0` usos de
  `any`/`ts-ignore` en el frontend.

---

## 2. Estado de los hallazgos de la auditoría anterior (2026-10-18)

| Hallazgo | Estado hoy |
|---|---|
| Login de Google caído | ❌ Abierto (5 semanas) |
| `typecheck` en `package.json`/hook | ❌ Abierto |
| CI mínimo | ❌ Abierto (no existe `.github/workflows`) |
| Tests de frontend (Vitest) | ❌ Abierto |
| Comentarios `# 🔁 antes: raise HTTPException` | ❌ **11** ocurrencias en backend (antes: 4 citadas) |
| Helper `invalidateAfterTransactionChange` | ❌ Abierto: 21 archivos llaman `invalidateQueries`, ninguno usa un helper |
| Tope de 100 reglas recurrentes no atómico | ❌ Abierto (y el de 50 CDT tiene el mismo patrón) |
| Encabezado de `ROADMAP.md` ("Fase 0 a Fase 32") | ❌ Abierto (el CHANGELOG llega a la 40) |
| `crear_/actualizar_transaccion` demasiado largas | 🟡 Apenas recortadas (156/180 líneas) |
| `AGENTS.md` lista modelos | ✅ Correcto: 18 clases en `models.py`, coincide |
| `test_cdt_concurrency` 422 | 🟡 Arreglado en `aa62aed`, pero `docs/TODO.md:73` sigue como `[ ]` |
| `rclone.conf`/`.env`/`backups/` fuera de git | ✅ Verificado: ninguno está trackeado |

---

## 3. Análisis por Área

### 3.1 Estructura
**Score**: 8.5/10

**Hallazgos**:
- Separación clara `api/` · `core/` · `services/` · `schemas/` · `models/`; backend ≈ 10 mil líneas
  en `app/`. `services/` ya contiene `ledger`, `funds`, `recurring`, `cdt`, `transfers`: dejó de ser
  "naciente" (la sección de arquitectura de `AGENTS.md` aún lo llama así y lista solo
  `ledger`/`funds`, aunque los párrafos de fase sí citan los demás).
- Frontend con route groups, carpetas por dominio y 16 hooks de lectura/mutación en `lib/hooks/`.
- `types/generated/api.ts` (4.752 líneas) convive con `types/api.ts` manual (568) — deliberado pero
  a medio migrar; la duplicación crece con cada endpoint nuevo.

**Recomendaciones**:
- Actualizar la descripción de `services/` en `AGENTS.md` (incluir `recurring`, `cdt`, `transfers`).

---

### 3.2 Arquitectura
**Score**: 8.5/10

**Hallazgos**:
- La Fase 39 cambió una invariante antigua (saldo = ledger **más** transferencias) pero lo hizo
  declarado: `ledger.py` y `reconciliar_cuenta` incluyen transferencias, `GET /movements` hace UNION,
  y hay un script de corrección de datos con `--confirmo-copia`. Es el cambio de mayor riesgo del
  mes y se manejó con spec + `pg_dump` previo.
- `core/periods.py` sigue siendo el único sitio de aritmética de calendario.
- Excepciones de dominio uniformes; los 4 `HTTPException` restantes están en `core/security.py`
  (dependencias de auth), aceptable. 12 bloques `except Exception`, la mayoría justificados
  (alertas que no deben tumbar la transacción).
- `_resolver_fecha` (router de transacciones) e `instante_de_fecha` (transfers) duplican lógica de
  fecha (TODO Fase 38). Es precisamente el tipo de duplicación que la Fase 34 eliminó en otra
  forma: hay riesgo de divergir en el borde día-local/UTC.
- `services/cdt.py` duplica la construcción de `Transfer` de constitución/redención.

**Recomendaciones**:
- Unificar `_resolver_fecha`/`instante_de_fecha` en `core/periods.py` (1–2 h).
- Extraer a `services/` los pasos de `crear_/actualizar_transaccion`.

---

### 3.3 Mantenibilidad
**Score**: 8/10

**Hallazgos**:
- Funciones >90 líneas en backend: `actualizar_transaccion` (180), `obtener_resumen` (172),
  `crear_transaccion` (156), `run_seed` (140, datos de prueba, aceptable),
  `ensure_recurring_budgets_for_period` (121), `obtener_serie_flujo_caja` (93).
- Páginas de frontend de 450–700 líneas: `categories/[id]` 696, `accounts/[id]` 652, `settings` 606,
  dashboard raíz 510, `analytics` 502. `categories/[id]` creció con la Fase 40; la regla de
  "descomponer cuando se toque" no se aplicó esta vez.
- 11 comentarios `🔁 antes:` y comentarios con numeración de fase/decisión dentro del código: útiles
  hoy, ruido cuando la fase deje de ser contexto vivo.
- `docs/TODO.md` tiene 831 líneas con 45 ítems `[ ]` mezclados con historial `[x]` largo: ya no
  sirve de vista rápida de "qué está abierto".

**Recomendaciones**:
- Borrar los `🔁 antes:` (15 min).
- Archivar los `[x]` de `TODO.md` y cerrar la entrada de `test_cdt_concurrency` (1 h).

---

### 3.4 Modularidad
**Score**: 8/10

**Hallazgos**:
- Funciones puras separadas de casos de uso con lock (`funds`, `recurring`, `cdt`) y testeables sin
  DB. `models.py` único con 18 modelos (551 líneas): aún razonable.
- `funds.py` (751 líneas) concentra ritmo, disponibilidad, casos de uso y enlace a gastos; sigue
  siendo candidato a subpaquete, pero la recomendación vigente (no dividir preventivamente) es sensata.
- Frontend: helpers de presentación (`Chip`, `formatDay`, `money`) viven en
  `components/recurring/recurringPresentation` y los consumen otros dominios (CDT) — acoplamiento
  por ubicación equivocada (TODO Fase 38).
- La lista de invalidaciones de TanStack Query está copiada en 21 archivos; con transferencias
  (que mueven saldos) la lista de "qué invalidar tras un movimiento" ya tiene más claves que en la
  Fase 37, y olvidarse de una es el bug típico de este diseño.

**Recomendaciones**:
- `invalidateAfterMovementChange(queryClient)` central (1–2 h) — ahora con más justificación que
  hace una semana.
- Mover `Chip`/`formatDay`/`money` a `components/ui` o `lib/format`.

---

### 3.5 Seguridad (contexto personal)
**Score**: 7.5/10

**Hallazgos**:
- Baseline vigente (cookies `httpOnly` + CSRF, refresh rotativo, verificación de email); secretos
  fuera del índice de git (verificado). Sin `dangerouslySetInnerHTML`; `localStorage` solo para
  tema y flag de push (sin datos sensibles).
- Publicado vía Funnel con un único usuario; compose publica `0.0.0.0:8000/3000` (riesgo teórico
  aceptado). Sin escáner de dependencias (no hay CI).
- Los scripts de corrección de datos (`fase34_reporte_x1.py`, `fase39_corregir_bancolombia.py`)
  exigen `--confirmo-copia`: buena práctica para operaciones destructivas sobre datos reales.

**Recomendaciones**: ninguna nueva.

---

### 3.6 Documentación
**Score**: 9/10

**Hallazgos**:
- Doc por capa, 35 specs con decisiones numeradas, `AGENTS.md` como fuente única,
  `VISION_FINANZAS_RESPONSABLES.md` que ordena las fases. Las Fases 38-40 cerraron con CHANGELOG,
  ROADMAP, AGENTS y TODO actualizados en el mismo PR.
- Desfases menores: encabezado de `ROADMAP.md` ("Fase 0 a Fase 32"); `TODO.md:73` sigue abierto
  tras el fix; `ROADMAP.md` línea 101 aún dice "recurrentes como Fase 35 probable"; `AGENTS.md` es
  ya un documento de ~5 mil palabras con mucho contexto histórico por fase — útil, pero cada agente lo
  carga completo en cada sesión.

**Recomendaciones**:
- Sincronizar encabezados y cerrar casillas (30 min).
- Mover los párrafos "hecho operativo vigente" de Fases 34–39 de `AGENTS.md` a `docs/` y dejar en
  `AGENTS.md` solo punteros: reduce el costo de contexto por sesión.

---

### 3.7 UX/Usabilidad
**Score**: 8/10

**Hallazgos**:
- La Fase 40 cierra la queja histórica de navegación (dashboard por mes, detalle de categoría con
  presupuesto); `QueryErrorState`, diálogos accesibles y zona horaria del usuario se mantienen.
- Abiertos relevantes para el uso real: login de Google; calendario recurrente de 12 tarjetas
  apiladas en móvil; sugerencias descartadas que reaparecen; sin aviso de pendientes recurrentes ni
  de CDT por vencer (solo UI); decisión sobre cuentas `credit` en "disponible real" (TODO Fase 35 D1);
  contraste USD de "disponible real" con datos reales (A3).
- Sin tests de frontend, los fixes de UX dependen de pasadas manuales de QA con Playwright.

**Recomendaciones**:
- Cerrar A3 y D1 con el dueño antes de apoyar decisiones en la cifra de disponible.
- Plegar el calendario por mes en móvil.

---

## 4. Recomendaciones Priorizadas

### Quick Wins (Horas)
1. Añadir `"typecheck": "tsc --noEmit"` a `frontend/package.json`, al `pre-commit` y a la skill `run-tests` — 1 h
2. Eliminar los 11 comentarios `# 🔁 antes:` — 15 min
3. Cerrar `TODO.md:73` (fix `aa62aed`) y corregir encabezados de `ROADMAP.md` — 30 min
4. Unificar `_resolver_fecha`/`instante_de_fecha` — 1–2 h
5. Helper `invalidateAfterMovementChange` y reemplazar copias — 2 h
6. Topes de 100 reglas / 50 CDT atómicos (lock sobre el usuario) — 1–2 h

### Mejoras Medianas (Días)
1. CI mínimo (GitHub Actions): ruff + pytest con Postgres + eslint + tsc + build — 0,5–1 día
2. Vitest para `lib/dates.ts`, `lib/dateRanges.ts`, `validateAmount.ts` (solo funciones puras) — 1 día
3. Descomponer `crear_/actualizar_transaccion` y `obtener_resumen` en pasos de `services/` — 1–2 días
4. Reducir `AGENTS.md` a punteros + archivar historial de fases en `docs/` — 0,5 día
5. Archivar `[x]` de `TODO.md` (831 → vista de abiertos) — 1 h

### Refactoring Mayor (Semanas)
1. Migrar `types/api.ts` manual a `types/generated/api.ts` — ~1 semana, oportunista
2. Dividir `services/funds.py` en subpaquete en la próxima fase que lo toque — 2–3 días, no preventivo

---

## 5. Próximos Pasos Sugeridos

### Acciones Inmediatas (Esta semana)
1. Resolver el login de Google (apelación o recrear Client ID + consent screen).
2. Quick wins 1, 2 y 3 (< 2 h en total).
3. Antes de la Fase 41 ("págate primero"): CI mínimo + `typecheck`, para que la próxima fase entre
   con red de seguridad.

### Roadmap de Mejoras (Próximo mes)
1. Vitest sobre utilidades de fecha/moneda; el cliente ya concentra lógica de rangos y monedas.
2. Refactor de `crear_/actualizar_transaccion` antes de que la Fase 41/42 agregue otra rama.
3. Decidir con `/grilling` los puntos que las Fases 35, 37 y 38 tomaron sin él (crédito en
   disponible real, notificar pendientes y vencimientos).

---

## 6. Métricas Clave

| Área | Score | Prioridad |
|------|-------|-----------|
| Estructura | 8.5/10 | Baja |
| Arquitectura | 8.5/10 | Media |
| Mantenibilidad | 8/10 | Media |
| Modularidad | 8/10 | Media |
| Seguridad (contexto personal) | 7.5/10 | Baja |
| Documentación | 9/10 | Baja |
| UX/Usabilidad | 8/10 | Media |

**Score General**: 8.2/10 (promedio simple 8.21)

Datos de apoyo: 893 tests backend en 46 archivos; backend ≈ 10,1 mil líneas en `app/`; frontend
≈ 22 mil líneas de TS/TSX (4,7 mil son tipos generados), 0 tests, 0 usos de `any`/`ts-ignore`;
18 modelos; 35 specs; sin CI. No se ejecutaron `pytest`/`eslint`/`tsc` en esta pasada.
