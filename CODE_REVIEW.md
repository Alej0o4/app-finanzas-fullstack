# Auditoría de Proyecto: Oikos — Finanzas Personales

**Fecha**: 19 de septiembre de 2026
**Analista**: Claude Code
**Tipo de Proyecto**: Fullstack, uso personal (post-pivote 2026-09-19, ver `docs/ROADMAP.md`)
**Stack**: FastAPI + SQLAlchemy + Alembic + PostgreSQL / Next.js 15 (App Router) + TanStack Query + Zustand + Tailwind

---

## 0. Nota de calibración

Esta auditoría se corre inmediatamente después del segundo pivote del proyecto (2026-09-19):
Oikos vuelve a ser una herramienta personal para un solo dueño/desarrollador, sin plan de
apertura a usuarios externos. Por eso:

- **Sí se evalúa con exigencia normal**: estructura, arquitectura, mantenibilidad, modularidad,
  testing, migraciones, versionado de API, documentación, UX de la app en sí. Estas cosas
  facilitan seguir construyendo features, con o sin otros usuarios.
- **No se penaliza** como si fuera un producto para usuarios externos: hardening de seguridad,
  robustez de auth más allá de lo ya construido, escalabilidad de rate limiting, TTL/scopes de
  API keys, resistencia a abuso. El baseline llegado a la Fase 26 (cookies `httpOnly` + CSRF,
  verificación de email, rate limiting básico en memoria, fix del account-takeover de Google
  OAuth) se trata como *suficiente* para un usuario de confianza — el score de Seguridad
  responde a "¿es razonable para este contexto?", no a "¿es production-grade para internet
  público?".
- Si algo es un bug real que afecta el uso diario del dueño (ej. login de Google caído en
  producción), se marca igual — no es "seguridad", es una feature del producto rota.

---

## 1. Resumen Ejecutivo

### Estado General: 7.6/10

**Veredicto**: BUENO. La auditoría anterior (2026-09-15, 6.3/10) encontró una vulnerabilidad
crítica confirmada y tres bugs de "falla silenciosa" en el flujo más usado de la app; las
Fases 23–26 (2026-09-16 a 2026-09-19) cerraron ambos frentes con evidencia verificable en el
código y en 251 tests backend en verde. El score sube no por relajar el criterio, sino porque
el trabajo real se hizo. La brecha que queda es más pareja: ningún área está en rojo, pero
`app/core/exceptions.py` sigue siendo un piloto de un solo router, `AGENTS.md` quedó
desactualizado en la misma pasada que actualizó `CLAUDE.md`/`ROADMAP.md`/`TODO.md`, y el login
de Google sigue caído en producción por un motivo ajeno al código.

### Top 3 Problemas Críticos

1. **Login con Google caído en producción (`disabled_client`)** — Impacto: Alto (afecta el uso
   diario real del único usuario del producto)
   - No es un bug de código — Google Cloud deshabilitó el OAuth Client ID, apelación pendiente
     desde 2026-09-19 (`docs/TODO.md`, sección 🟠). El workaround activo (reset de contraseña
     sobre una cuenta `password_hash IS NULL`) funciona pero es un efecto colateral no
     diseñado, no una feature.
   - Solución: nada que hacer en código mientras la apelación esté pendiente; si falla, recrear
     el Client ID y completar el consent screen con branding real (ya documentado como plan B).

2. **`AGENTS.md` quedó desactualizado mientras `CLAUDE.md`/`ROADMAP.md`/`TODO.md` se
   actualizaban hoy mismo** — Impacto: Medio
   - `AGENTS.md:3` dice "sin tests automatizados aún" (hay 251 tests backend pasando);
     `AGENTS.md:79` dice "`backend/app/services/` vacío (deuda técnica)" (existe
     `app/services/ledger.py` desde Fase 25); el aviso de cambio de enfoque en `AGENTS.md:5-12`
     sigue anclado al pivote del 2026-08-22, sin mención del pivote de vuelta del 2026-09-19.
     El propio `CLAUDE.md` (que sí está al día) documenta que `AGENTS.md` es un archivo
     paralelo dirigido a otros agentes — quedó fuera de la disciplina de "actualizar ambos
     docs en el mismo cambio" que el proyecto sí aplica a `API_REFERENCE.md`/`API_CONTRACT.md`.
   - Solución: sincronizar `AGENTS.md` con el estado actual (~30 min, es un resumen, no
     duplica todo `CLAUDE.md`).

3. **La capa de excepciones de dominio y la extracción de lógica a `app/services/` siguen
   siendo pilotos de un solo caso** — Impacto: Medio (deuda de arquitectura reconocida, no un
   hallazgo nuevo)
   - `app/core/exceptions.py` solo lo usa `transactions.py` (4 `raise`); quedan 65
     `raise HTTPException` repartidos en los otros 10 routers mezclando validación de negocio
     con la capa HTTP. Esto ya está documentado como deuda deliberada en `docs/TODO.md` —
     se repite acá porque sigue siendo el mayor bloque de deuda de modularidad real del
     backend, no para reabrir una decisión ya tomada.
   - Solución: seguir el plan ya escrito (incremental, router por router, la próxima vez que
     se toque cada uno por otra razón) — no requiere una fase dedicada.

### Fortalezas Destacadas

- ✅ **Los tres hallazgos críticos de la auditoría anterior están genuinamente resueltos, no
  solo reclasificados**: el auto-link de Google OAuth anula `password_hash` en cuentas no
  verificadas (`backend/app/api/auth.py:114-124`, con test de regresión hostil); las 4 queries
  del dashboard exponen `isError`/`refetch` con botón "Reintentar"
  (`frontend/app/(dashboard)/page.tsx:50-92`); el delta contable vive en un solo lugar
  (`backend/app/services/ledger.py`), consumido por los 3 call sites que antes lo duplicaban.
- ✅ **Disciplina de documentación y de historial técnico fuera de lo común para un proyecto
  de un solo desarrollador**: `docs/CHANGELOG.md` con 26 fases, cada una con spec propia en
  `docs/specs/`, y un `docs/TODO.md` que no solo lista deuda sino que registra cuándo y por qué
  cada ítem se resolvió o se cerró como fuera de scope — incluida la honestidad de marcar
  hallazgos previos como "ya no aplica por el pivote", no como "resuelto" cuando no lo fueron.
- ✅ **251 tests backend en verde, `ruff check` limpio, sin dependencias sueltas**: verificado
  ejecutando la suite completa en esta auditoría (no solo leído del changelog) — coincide
  exactamente con el número que reporta `docs/CHANGELOG.md` para Fase 26.

### Quick Wins (horas)

- Sincronizar `AGENTS.md` con el estado post-pivote 2026-09-19 (~0.5-1h)
- Extraer subcomponentes de `transactions/page.tsx` (646 líneas, sigue creciendo desde las 380
  de julio) la próxima vez que se toque (~2-3h)
- Nada de seguridad — ver nota de calibración arriba

---

## 2. Análisis por Área

### 2.1 Estructura
**Score**: 8/10 | **Prioridad**: Baja

**Hallazgos Positivos**:
- Separación backend/frontend clara, un router por dominio (`backend/app/api/{auth,transactions,accounts,...}.py`), route groups de Next.js bien usados (`(auth)` vs `(dashboard)` vs `capture/` standalone documentado explícitamente en `CLAUDE.md`).
- `schemas.py` (antes 462 líneas/48 clases, señalado como el archivo más forzado del repo en la auditoría 2026-09-15) se partió en 12 módulos por dominio bajo `backend/app/schemas/` en Fase 25, con `schemas.py` como shim de re-exports — cero call sites rotos, verificado (`backend/app/schemas/schemas.py`, 110 líneas de solo imports).
- Ningún archivo de backend supera las 500 líneas hoy (el más largo, `transactions.py`, 434 líneas); `models.py` se mantiene en un solo archivo a propósito, ya bien encapsulado por clase, y la propia auditoría anterior no lo marcaba urgente.

**Áreas de Mejora**:
- `frontend/app/(dashboard)/transactions/page.tsx` sigue creciendo: 380 líneas en julio → 646 hoy. Ya cruzó el umbral de alerta (>500 líneas) del checklist de estructura.
- Nomenclatura mixta español/inglés dentro del mismo módulo (`crear_transaccion` → `TransactionResponse`) — irrelevante en solitario para un repo de un solo dev, documentado ya como tal en `docs/TODO.md`.

**Recomendaciones**:
1. Extraer subcomponentes de `transactions/page.tsx` (filtros, tabla, paginación) la próxima vez que se toque ese archivo — no urgente aisladamente, pero ya está por encima del umbral.

---

### 2.2 Arquitectura
**Score**: 7.5/10 | **Prioridad**: Media

**Hallazgos Positivos**:
- `app/services/ledger.py` (Fase 25) es la primera extracción real a una capa de servicio, y resolvió exactamente el problema de mayor riesgo que señalaba la auditoría anterior: el signo del delta contable y el `UPDATE` atómico de `Account.balance` estaban copy-pasteados 3 veces en `transactions.py` (líneas 186/312/393-395); ahora viven una vez en `ledger.registrar_impacto`/`revertir_impacto`/`aplicar_edicion`, consumidos por los 3 call sites — verificado leyendo `backend/app/api/transactions.py:187-192,301-303,375`.
- Auth flow sigue siendo sólido y ahora más completo: JWT de 15 min + refresh opaco hasheado con rotación + cookies `httpOnly` (Fase 26) + CSRF double-submit, con el camino de API key (`Authorization: Bearer oikos_pat_...`) intacto para clientes no-browser — un diseño consistente, no dos sistemas de auth compitiendo.
- Migraciones con Alembic reemplazando el `create_all()`/`_ensure_*_column()` ad-hoc, API versionada bajo `/api/v1/` desde un único punto (`frontend/lib/api.ts`) — ambas eran deuda arquitectónica real del código pre-2026-08-22, ya cerradas.

**Áreas de Mejora**:
- `app/core/exceptions.py` (`DomainError` + 2 subclases) es un piloto acotado a `transactions.py` — los otros 10 routers de `app/api/` siguen usando `raise HTTPException` inline mezclado con validación de negocio (65 ocurrencias contadas en esta auditoría). Es deuda documentada y aceptada, no un hallazgo nuevo, pero sigue siendo el mayor bloque de acoplamiento HTTP↔dominio del backend.
- La arquitectura real del backend ya no es "todo en el router" — `app/core/` acumula 8 módulos consumidos por 2+ routers cada uno (`budget_alerts.py`, `budget_recurrence.py`, `notification_dispatch.py`, `weekly_summary.py`, `user_deletion.py`, `auth_cookies.py`, `csrf.py`, `default_categories.py`) — pero `CLAUDE.md` describe esto correctamente ahora ("thin layered structure with a nascent service layer"), a diferencia de la versión que auditó 2026-09-15.

**Recomendaciones**:
1. Seguir el plan ya escrito en `docs/TODO.md`: migrar `raise HTTPException` a `DomainError` router por router, la próxima vez que se toque cada uno por otra razón — no vale la pena una fase dedicada solo para esto a esta escala.

---

### 2.3 Mantenibilidad
**Score**: 7.5/10 | **Prioridad**: Baja

**Hallazgos Positivos**:
- La duplicación de mayor riesgo real (delta contable, ver 2.2) está resuelta con un test unitario dedicado (`test_ledger.py`, 6 tests).
- `frontend/docs/STATE_AND_FETCHING.md` — señalado como "congelado en Fase 16" en la auditoría anterior — está actualizado (última modificación hoy, 2026-09-19) con las query keys de Fases 17-25 (`monthlySummary`/`budgetsProgress` por cuenta, params `account_id`/`currency`, mutations de Settings).
- `ruff check .` corre limpio sobre todo el backend (verificado en esta auditoría, no solo asumido); lint/format configurados y usados en ambos lados.
- `docs/TODO.md` funciona como un tracker de deuda real, no decorativo: cada ítem resuelto tiene fecha, fase y commit; los que dejaron de aplicar por el pivote están marcados como tal (no como "resueltos" cuando no lo fueron) — es la clase de disciplina que hace que un audit futuro pueda confiar en el documento en vez de tener que re-verificar todo desde cero.

**Áreas de Mejora**:
- `AGENTS.md` es la única pieza de documentación de referencia que quedó desactualizada en esta pasada (ver Resumen Ejecutivo #2) — afirma "sin tests automatizados" y "`services/` vacío", ambas falsas hoy.
- `transactions/page.tsx` sigue la tendencia de crecimiento que ya se señalaba en julio (2.1).

**Recomendaciones**:
1. Sincronizar `AGENTS.md` — es barato y evita que un agente que lo lea primero parta de una premisa falsa (exactamente el tipo de problema que esta skill pide detectar).

---

### 2.4 Modularidad
**Score**: 7/10 | **Prioridad**: Media

**Hallazgos Positivos**:
- `frontend/lib/hooks/{useAccounts,useCategories,useTransactions}.ts` (Fase 25) reemplazaron 19 `useQuery`+`queryFn` inline repetidos por página — la duplicación de fetching señalada en la auditoría anterior está resuelta para lecturas; mutaciones siguen inline a propósito (listas de invalidación demasiado heterogéneas para un hook único), decisión razonable y documentada.
- Routers siguen bien acotados por dominio, sin acoplamiento circular aparente entre ellos; los módulos de `app/core/` extraídos se consumen limpiamente desde múltiples call sites.
- Codegen de tipos desde OpenAPI (`frontend/types/generated/api.ts`, Fase 16) conviviendo deliberadamente con tipos manuales para código nuevo — sin fecha de deprecación fijada, pero es una decisión consciente, no deriva accidental.

**Áreas de Mejora**:
- Mismo punto que 2.2: sin capa de excepciones de dominio fuera de `transactions.py`, la lógica de negocio de los otros 10 routers sigue acoplada a `HTTPException` directamente.
- `ApiKey` sin scopes es una decisión de producto ya evaluada y cerrada (`models.py:315-318`, Decisión 16.1.1) — correcto no reabrirla bajo el modelo de amenaza actual de un solo usuario.

**Recomendaciones**:
1. Mismo plan incremental que 2.2 — no hay una recomendación nueva de modularidad que no sea ya la extensión de la capa de excepciones ya empezada.

---

### 2.5 Seguridad
**Score**: 8.5/10 | **Prioridad**: Baja

*(Evaluado contra "¿es razonable para un solo usuario de confianza en un deployment personal?", no contra un estándar de producto multi-usuario — ver nota de calibración.)*

**Hallazgos Positivos**:
- **El hallazgo crítico de la auditoría anterior está cerrado con evidencia verificable, no solo declarado**: `login_google` (`backend/app/api/auth.py:105-125`) ahora captura `cuenta_no_verificada_antes_de_este_login` *antes* de mutar `email_verified`, y anula `password_hash` si la cuenta no estaba verificada — cortando el vector de account-takeover por auto-link. Test de regresión hostil existe y pasa (`test_autolink_on_unverified_account_nullifies_attacker_planted_password`, confirmado en la corrida de 251 tests de esta auditoría).
- Baseline de auth sólido y suficiente para el contexto: JWT de 15 min + refresh opaco hasheado con rotación, cookies `httpOnly` + CSRF double-submit desde Fase 26 (sin JWT en `localStorage`), bcrypt, política de contraseñas, rate limiting real (5/min) en login/registro/reset, revocación de refresh tokens *y* API keys al resetear contraseña.
- `POST /push/subscribe` reasigna ownership entre usuarios con logging de auditoría en vez de bloquear (`backend/app/api/push.py:44-56`) — decisión correcta y documentada: bloquear rompería el caso legítimo de dispositivo compartido, y el riesgo real es bajo (el `endpoint` no es adivinable).
- Sin secrets committeados: `.gitignore` excluye `.env`/`backend/.env`/`backend/venv/`, verificado con `git ls-files` (ninguno trackeado).

**Áreas de Mejora (informativas, no bloqueantes bajo el modelo de amenaza actual)**:
- `docker-compose.yml:41,75` sigue publicando 8000/3000 en `0.0.0.0` sin especificar interfaz — ya evaluado y aceptado en `docs/TODO.md` (host sin otra ruta de red pública confirmada por el usuario el 2026-09-16); se mantiene como nota, no como hallazgo activo.
- Rate limiting en memoria y sin TTL/scopes en API keys — explícitamente movidos a "Fuera de scope" en `docs/ROADMAP.md` el 2026-09-19; no se recalculan acá porque el pivote ya cerró esa decisión con una justificación válida (un solo dueño de todas las keys).

**Recomendaciones**:
1. Ninguna nueva. El único ítem de seguridad activo en `docs/TODO.md` (el `disabled_client` de Google) no es de código — ver Resumen Ejecutivo #1.

---

### 2.6 Documentación
**Score**: 8.5/10 | **Prioridad**: Baja

**Hallazgos Positivos**:
- Cobertura amplia y activamente mantenida: `backend/docs/` (5 archivos), `frontend/docs/` (5 archivos), `docs/ROADMAP.md` + `docs/CHANGELOG.md` + `docs/TODO.md`, 26 specs por fase en `docs/specs/`.
- `CLAUDE.md` describe con precisión el estado actual verificado contra código: la afirmación sobre `app/services/` como "nascent... solo módulo hasta ahora" coincide con lo que hay en disco; la descripción del flujo de cookies httpOnly coincide con `auth_cookies.py`/`csrf.py`.
- `frontend/docs/STATE_AND_FETCHING.md`, señalado como el único punto débil real en la auditoría anterior, está al día (ver 2.3).
- `docs/TODO.md` mantiene un registro fechado de "Resueltos" desde julio — permite reconstruir por qué se tomó cada decisión sin tener que preguntar, y distingue con cuidado "resuelto" de "ya no aplica por el pivote" (ver 2.3).

**Áreas de Mejora**:
- `AGENTS.md` (99 líneas) no recibió la misma pasada de actualización que `CLAUDE.md`/`ROADMAP.md`/`TODO.md` el 2026-09-19 — ver Resumen Ejecutivo #2. Es el único documento de referencia con contenido verificablemente falso hoy (tests, capa de servicios, encabezado de pivote).

**Recomendaciones**:
1. Sincronizar `AGENTS.md` — único quick win real de esta área.

---

### 2.7 UX/Usabilidad
**Score**: 7.5/10 | **Prioridad**: Media

**Hallazgos Positivos**:
- Los 3 bugs de "falla silenciosa" de la auditoría anterior — todos en el flujo más transitado de la app — están resueltos con evidencia en código: dashboard con `isError`/`refetch` por sección (`frontend/app/(dashboard)/page.tsx:50-92`), formulario de ingreso mensual con `noValidate` + error de campo + foco (mismo archivo, Fase 24 §24.2), y el caso de "usuario nuevo sin cuentas" ya no aplica porque toda cuenta nueva recibe una cuenta por defecto en el registro desde Fase 8 (confirmado leyendo `QuickTransactionModal.tsx`, sin guard especial porque ya no hace falta).
- `PUT /accounts/{id}` ahora aplica cambios de `currency` en vez de ignorarlos en silencio, y de paso corrigió un bug relacionado (`highlighted` se reseteaba a `false` en cualquier PUT que lo omitiera) — verificado en `backend/app/api/accounts.py:211-218`.
- `category-distribution` expone `category_icon`, cerrando el bug de icono genérico en el desglose del dashboard.

**Áreas de Mejora**:
- Sigue sin haber tests de frontend (`Vitest`/RTL no configurado, cero archivos `*.test.*`/`*.spec.*`, confirmado con `find`) — riesgo real dado que 3 de los últimos bugs de UX fueron justo del tipo que un test de "la query falla → se ve un error" habría atrapado. `docs/TODO.md` ya lo tiene anotado en "🔵 Solo si el proyecto crece" — razonable para un solo dev, pero vale la pena no perder de vista si vuelve a aparecer un bug de la misma familia.
- Accesibilidad básica presente pero parcial: 32 usos de `aria-label`/`alt` en 57 componentes/páginas — no exhaustivo, sin auditoría campo por campo.
- Login con Google caído en producción es, ante todo, un problema de UX del día a día del único usuario (ver Resumen Ejecutivo #1) — el flujo de login por contraseña sigue funcionando como fallback, pero no es la experiencia diseñada.

**Recomendaciones**:
1. Si un cuarto bug de "falla silenciosa" aparece en el flujo principal, es la señal de bajar la prioridad de tests de frontend desde "solo si crece" a "ahora" — no antes.

---

## 3. Recomendaciones Priorizadas

### Quick Wins (Horas)

| # | Recomendación | Tiempo | Área |
|---|---------------|--------|------|
| 1 | Sincronizar `AGENTS.md` con el estado post-pivote 2026-09-19 (tests existen, `services/ledger.py` existe, cookies httpOnly) | 0.5-1h | Documentación |
| 2 | Completar el OAuth consent screen de Google Cloud Console (branding real) como parte del plan B si la apelación del `disabled_client` falla | 1h (una vez que aplique) | UX |

### Mejoras Medianas (Días)

| # | Recomendación | Tiempo | Área |
|---|---------------|--------|------|
| 1 | Extraer subcomponentes de `transactions/page.tsx` (646 líneas) | 0.5-1d | Estructura |
| 2 | Migrar 2-3 routers más de `raise HTTPException` a `DomainError`, aprovechando el próximo touch de cada uno | 0.5d por router | Arquitectura/Modularidad |

### Refactoring Mayor (Semanas)

| # | Recomendación | Tiempo | Área |
|---|---------------|--------|------|
| 1 | Completar la migración de excepciones de dominio a los 10 routers restantes, si en algún momento se junta con otro trabajo que ya los toque (no como proyecto aislado) | 1-2 semanas repartidas | Arquitectura |

Nota: a diferencia de la auditoría anterior, no hay refactorings mayores urgentes — Fases 23-26
ya absorbieron el trabajo de mayor impacto (seguridad crítica, UX del flujo principal,
arquitectura del código contable, cookies httpOnly).

---

## 4. Próximos Pasos Sugeridos

### Acciones Inmediatas (Esta semana)

1. **Sincronizar `AGENTS.md`**
   - Por qué: es el único documento de referencia con contenido verificablemente falso hoy, y
     lo consulta cualquier agente que no sea Claude Code.
   - Cómo: alinear con las 3 secciones desactualizadas identificadas (línea 3, 5-12, 79).
   - Resultado esperado: cualquier agente que arranque desde `AGENTS.md` parte de la misma
     premisa que uno que arranque desde `CLAUDE.md`.

2. **Seguir el workaround de Google OAuth mientras se resuelve la apelación**
   - Por qué: es el único bug que afecta el uso diario real hoy.
   - Cómo: nada que hacer en código — monitorear la respuesta de Google Cloud Console.
   - Resultado esperado: login de Google restaurado, o migración al plan B (nuevo Client ID +
     consent screen con branding) si la apelación falla.

### Roadmap de Mejoras (Próximo mes)

1. **Backlog priorizado ya definido en `docs/ROADMAP.md`** (filtros de fecha/categoría,
   automatización de recurrentes, sinking funds) — no hay nada en esta auditoría que deba
   competir con ese backlog; es la fuente de verdad para "qué construir después".
   - Impacto: Alto (valor de uso directo, ya priorizado por el propio dueño del producto)
   - Esfuerzo: días por feature
   - Beneficio: mejor trackeo/análisis de gastos, el objetivo explícito del pivote 2026-09-19.

2. **Migrar routers restantes a `DomainError` oportunistamente**
   - Impacto: Medio (reduce acoplamiento HTTP↔dominio)
   - Esfuerzo: horas por router, repartido
   - Beneficio: cuando se necesite lógica de negocio más compleja (ej. transferencias entre
     cuentas), ya no hay que decidir entre seguir el patrón viejo o el nuevo.

---

## 5. Métricas Clave

| Área | Score | Prioridad | Estado |
|------|-------|-----------|--------|
| Estructura | 8/10 | Baja | ✅ |
| Arquitectura | 7.5/10 | Media | ✅ |
| Mantenibilidad | 7.5/10 | Baja | ✅ |
| Modularidad | 7/10 | Media | ✅ |
| Seguridad | 8.5/10 | Baja | ✅ |
| Documentación | 8.5/10 | Baja | ⚠️ |
| UX/Usabilidad | 7.5/10 | Media | ✅ |

**Score General**: 7.6/10

---

## 6. Conclusión

Oikos entra a este segundo pivote (vuelta a uso personal) en mejor estado del que salió del
primero. La auditoría del 2026-09-15 encontró un bloqueante crítico real (account takeover) y
tres bugs de "falla silenciosa" en la pantalla más usada de la app; las cuatro fases siguientes
(23-26) los cerraron con evidencia verificable — no solo con una entrada en el changelog, sino
con código leído línea por línea y 251 tests corridos en esta misma auditoría. El único
documento que se quedó atrás en la actualización de hoy fue `AGENTS.md`, y el único bug activo
que afecta el uso real (`disabled_client` de Google) no es un problema de código. El mayor
espacio de mejora que queda — extender la capa de excepciones de dominio más allá de
`transactions.py` — ya tiene un plan escrito y aceptado; no necesita una fase dedicada, solo
paciencia para aplicarlo router por router.

**Siguiente paso recomendado**: sincronizar `AGENTS.md` (quick win de 30-60 min) y luego volver
al backlog priorizado de `docs/ROADMAP.md` — no hay deuda técnica pendiente que deba competir
con las features de análisis de gastos que el propio pivote puso como prioridad.

---

*Reporte generado por Code Review Skill*
