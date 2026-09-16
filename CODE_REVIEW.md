# Auditoría de Proyecto: Oikos — Finanzas Personales

**Fecha**: 15 de septiembre de 2026
**Analista**: Claude Code
**Tipo de proyecto**: Fullstack multi-usuario (post-pivote 2026-08-22)
**Stack**: FastAPI + SQLAlchemy + Alembic + PostgreSQL / Next.js 15 (App Router) + TanStack Query + Zustand + Tailwind

**Nota de continuidad**: esta auditoría retoma y verifica hallazgos ya redactados (sin commitear) por una sesión anterior del mismo día, cortada antes de cerrar el reporte. Todos los hallazgos de esa sesión fueron re-verificados contra el código actual antes de incluirse aquí — ninguno se copió sin confirmar. El reporte de julio (`CODE_REVIEW.md` previo, commit `d4633a3`) queda obsoleto: es pre-pivote, cuando tests/Alembic/versionado de API todavía estaban fuera de alcance.

---

## 1. Resumen Ejecutivo

### Estado General: 6.3/10

**Veredicto**: ACEPTABLE CON UN BLOQUEANTE CRÍTICO. La base de Fases 7–22 es sólida — Alembic, tests de backend reales, versionado de API, rate limiting, verificación de email — y la documentación sigue siendo un punto fuerte genuino. Pero hay una vulnerabilidad de **account takeover confirmada y codificada como comportamiento esperado en un test** (no un descuido: el equipo la revisó y la validó con el razonamiento equivocado). Es bloqueante para cualquier usuario real que no seas vos, y hoy ya hay al menos un usuario real fuera de la cuenta de pruebas (`alejomaringomez2004@gmail.com`, vía Google).

### Top 3 problemas críticos

1. **Account takeover vía auto-link de Google OAuth** — Impacto: Crítico
   - `backend/app/api/auth.py:89-97` (`login_google`)
   - Un atacante registra la víctima por email+contraseña (nunca verifica). Cuando la víctima hace login con Google, el backend encuentra esa fila, la marca `email_verified=True` y linkea el `google_id` real **sin tocar el `password_hash` del atacante**. Resultado: la contraseña del atacante queda válida contra `/auth/login` para la cuenta ya verificada de la víctima.
   - El propio test `test_existing_unverified_password_account_is_autolinked` (`backend/tests/test_auth.py:525`) asserta `user.password_hash is not None` después del link como comportamiento *correcto* — confirma que la decisión de diseño (comentario "no es account takeover" en `auth.py:90-93`) se tomó, pero el análisis de amenaza que la sustenta no contempló el caso de un atacante plantando la fila a propósito.

2. **Tres bugs de "falla silenciosa" en el flujo de mayor tráfico** — Impacto: Alto
   - Dashboard (`frontend/app/(dashboard)/page.tsx:45-64`): las 4 queries destructuran `isLoading` pero ninguna `isError` — un fallo de red se ve idéntico a "sin datos todavía", sin aviso ni retry, en la pantalla que el usuario abre primero.
   - Ingreso mensual inline en el mismo archivo: input inválido hace `return` sin toast ni error de campo, y es el único formulario sin `noValidate` del proyecto (rompe el patrón de Fase 12 §12.8).
   - `QuickTransactionModal` (ya documentado en `docs/TODO.md`): usuario recién registrado sin cuentas → el botón "Registrar" no hace nada.

3. **La lógica que mueve la plata está triplicada, no la que menos riesgo tiene** — Impacto: Medio-Alto
   - El signo del delta (`income → +monto` / `expense → -monto`) está copiado en `backend/app/api/transactions.py:186`, `:312` y `:393-395` (crear/eliminar/actualizar). Mientras tanto sí se extrajo una capa de servicio ad-hoc en `app/core/` para notificaciones, alertas y recurrencia de presupuestos — todo código de menor riesgo que la contabilidad de transacciones, que sigue sin extraer.

### Fortalezas destacadas

- ✅ **Documentación excepcional y viva**: 11+ documentos técnicos (`backend/docs/`, `frontend/docs/`, `docs/`), specs por fase, un `TODO.md` con historial de resueltos fechado desde julio. Pocos proyectos de este tamaño mantienen esta disciplina.
- ✅ **Cobertura de tests de backend real y mayor de lo que sugiere la narrativa**: 5.690 líneas de test contra 2.261 líneas de routers (`backend/tests/`, 15 archivos) — Google OAuth, API keys y push tienen suites dedicadas y prueban casos negativos (token inválido, rate limit, expiración).
- ✅ **Migraciones, versionado y seguridad básica ya resueltos de raíz**: Alembic reemplazó el `create_all()` ad-hoc, `/api/v1/` centralizado en un solo archivo (`lib/api.ts`), secrets sin default silencioso, rate limiting real en auth, headers de seguridad, CORS condicionado por env var.

### Quick wins (horas)

- Chequear ownership en `POST /push/subscribe` antes de reasignar `user_id` (~1-2h)
- Agregar manejo de `isError` + retry visible a las 4 queries del dashboard (~2-3h)
- `noValidate` + error visible en el formulario de ingreso mensual (~1-2h)
- Hacer que `PUT /accounts/{id}` respete cambios de `currency` (~1h)
- Exponer `category_icon` en `category-distribution` (~1h)

---

## 2. Análisis por área

### 2.1 Estructura
**Score**: 7.5/10

**Hallazgos**:
- Separación clara backend/frontend, un router por dominio (`api/auth.py`, `api/transactions.py`, etc.), route groups de Next.js bien usados (`(auth)` vs `(dashboard)` vs `capture/` standalone).
- `lib/api.ts` centraliza correctamente el prefijo de versión — ya paga dividendos: si mañana existe `/api/v2/`, es un solo archivo a tocar.
- Puntos de fricción ya reconocidos por el propio equipo en `docs/TODO.md`: `schemas.py` (462 líneas, 49 clases) mezcla auth/transacciones/push/API-keys sin separación por dominio; `models.py` (341 líneas, 14 clases) está mejor organizado y no es urgente partirlo; `transactions/page.tsx` llegó a 658 líneas (era 380 en julio — la tendencia importa más que el número absoluto).
- Nomenclatura mixta español/inglés dentro del mismo módulo (`crear_transaccion` → `TransactionResponse`) — irrelevante en solitario, sí sería fricción real si el repo se abre a más de una persona.

**Recomendaciones**:
- Priorizar partir `schemas.py` por dominio (auth/transactions/notifications/push/api-keys) antes que `models.py` — es el archivo real forzado.
- Vigilar `transactions/page.tsx` en el próximo touch; si cruza ~700 líneas, extraer subcomponentes.

---

### 2.2 Arquitectura
**Score**: 6.5/10

**Hallazgos**:
- Capas intencionalmente delgadas por decisión documentada (sin `app/services/` formal a esta escala) — pero ya emergió una capa ad-hoc en `app/core/` (`budget_alerts.py`, `budget_recurrence.py`, `notification_dispatch.py`, `weekly_summary.py`, `user_deletion.py`), cada uno consumido por 2+ routers o el scheduler. La arquitectura real ya no es "todo en el router"; es "todo en el router excepto lo que se volvió doloroso".
- El problema no es la ausencia de capa de servicio — es que se aplicó donde menos importaba. La lógica contable de `transactions.py` (la que mueve dinero real) sigue sin extraer, mientras que scheduling/notificaciones sí tienen su módulo.
- Auth flow es sólido arquitectónicamente: JWT de vida corta + refresh opaco hasheado en DB + rotación, verificación de email obligatoria para login, reset de contraseña que revoca todo lo activo (refresh tokens y API keys). El diseño es correcto; el bug de la sección de seguridad es una falla puntual en `login_google`, no un problema del auth flow en general.
- API versionada desde el día uno del pivote (`/api/v1/`), migraciones con Alembic reemplazando el `_ensure_*_column()` legacy — ambas eran deuda arquitectónica real, ya resueltas.

**Recomendaciones**:
- Cuando se cree `app/services/` formalmente, empezar por `ledger.py`/`transaction_accounting.py` con el delta de contabilidad — usar `budget_alerts.py` como plantilla de cómo ya funciona "core/-como-service" en este repo, no como excepción a evitar.
- Documentar explícitamente en `backend/docs/ARCHITECTURE.md` que `app/core/` ya cumple parcialmente el rol de capa de servicio — el CLAUDE.md actual ("no service layer") describe la intención original, no el estado real.

---

### 2.3 Mantenibilidad
**Score**: 6/10

**Hallazgos**:
- Duplicación real y de alto riesgo: el signo del delta contable en 3 puntos de `transactions.py` (líneas 186, 312, 393-395). Un cambio futuro en la regla (ej. transferencias entre cuentas) tiene 3 lugares para desincronizarse.
- `frontend/docs/STATE_AND_FETCHING.md` — el mapa de query keys que `CLAUDE.md` señala como autoritativo — está congelado en Fase 16. No menciona las query keys de Fases 17-22 (`monthlySummary`/`budgetsProgress` por cuenta, params `account_id`/`currency` en analytics, keys de categorías ocultas, mutations de settings). Es un documento que hoy engaña más de lo que ayuda si alguien confía en él en vez de grepear `lib/queryKeys.ts`.
- Fetching duplicado por página en frontend (`useQuery` + `queryFn` inline repetido en vez de hooks como `useAccounts`/`useCategories`).
- Lint/format configurados y usados (`ruff`, `eslint`, `prettier`) — reduce el riesgo de deriva de estilo con el tiempo, aunque no hay CI que lo haga cumplir automáticamente todavía.

**Recomendaciones**:
- Extraer el delta contable a una función pura testeada una sola vez, reutilizada en los 3 endpoints (quick win de mantenibilidad, no requiere `app/services/` formal para empezar).
- Actualizar `STATE_AND_FETCHING.md` en el próximo touch a cualquiera de esas áreas — mismo nivel de disciplina que ya se exige para `API_REFERENCE.md`/`API_CONTRACT.md`.

---

### 2.4 Modularidad
**Score**: 5.5/10

**Hallazgos**:
- Sin capa de excepciones de dominio: todo `raise HTTPException` mezclado con reglas de negocio en los routers — acopla la capa HTTP a la validación de negocio.
- `schemas.py` como archivo único de 49 clases es el mayor obstáculo real a la modularidad hoy (ver 2.1) — más que `models.py`, que está bien encapsulado por clase.
- Frontend: sin hooks reutilizables de fetching; cada página reimplementa su `useQuery`. Migración a tipos generados desde OpenAPI (`frontend/types/generated/api.ts`, Fase 16 §16.3) ya arrancó para código nuevo, conviviendo deliberadamente con tipos manuales en el código viejo — decisión razonable, sin fecha de deprecación fijada.
- Puntos positivos: routers ya están bien acotados por dominio (una responsabilidad por archivo), y los módulos de `app/core/` que sí se extrajeron son consumidos limpiamente por múltiples call sites sin acoplamiento circular aparente.

**Recomendaciones**:
- Partir `schemas.py` por dominio es el cambio de modularidad de mayor ROI disponible ahora mismo.
- Migrar oportunistamente los call sites de tipos manuales a los generados cuando se toque ese código, sin proyecto dedicado.

---

### 2.5 Seguridad
**Score**: 5/10

**Hallazgos**:
- 🔴 **Crítico, confirmado**: account takeover vía auto-link de Google OAuth (ver Resumen Ejecutivo e ítem correspondiente en `docs/TODO.md`, sección Bloqueantes). Verificado leyendo `auth.py:62-122` y el test que lo codifica como esperado.
- 🟡 `POST /push/subscribe` (`backend/app/api/push.py:33-51`) hace upsert por `endpoint` y reasigna `user_id` sin verificar si ese endpoint ya pertenecía a otro usuario. El propio docstring justifica el upsert para el caso legítimo (mismo dispositivo, reinicio de sesión) pero no distingue ese caso de un endpoint robado — riesgo bajo (el endpoint no es adivinable) pero el chequeo de ownership falta igual.
- 🟡 `docker-compose.yml:39-40,73-74` publica los puertos 8000/3000 en `0.0.0.0` por defecto (sin especificar interfaz). Si el host tiene alguna otra ruta de red además del tailnet (IP pública, otra VPN, NAT de nube), la API queda expuesta sin pasar por la terminación TLS de Tailscale Funnel. No confirmado si el host real tiene esa exposición — verificar antes de repriorizar, y si la tiene, acotar el bind.
- 🟢 Lo que sí está bien: contraseñas con política de fuerza mínima, bcrypt, JWT de 15 min, refresh token opaco hasheado con rotación, revocación de refresh tokens *y* API keys en reset de contraseña, rate limiting real (5/min) en registro/login/reset, CORS condicionado a `ENABLE_TAILSCALE_CORS` (ya no incondicional), headers de seguridad (`X-Content-Type-Options`, `X-Frame-Options`), secrets obligatorios sin default silencioso en `docker compose up`.
- 🟡 Aceptado y documentado conscientemente (no es un hallazgo nuevo, pero pesa en el score dado el Funnel público desde 2026-09-06): JWT en `localStorage`, rate limiting en memoria (aceptable mientras sea un solo worker).

**Recomendaciones**:
- **Prioridad 1, antes de más usuarios reales**: en el auto-link de `login_google`, invalidar el `password_hash` existente al vincular (o exigir confirmación de la contraseña actual) en vez de confiar en una fila sin verificar. Agregar un test que cubra explícitamente el escenario hostil (atacante pre-registra, víctima hace login con Google, la contraseña del atacante *no* debe seguir siendo válida).
- Agregar el chequeo de ownership en `push.py` antes del upsert.
- Confirmar la topología de red real del host de despliegue; acotar el bind de puertos si corresponde.

---

### 2.6 Documentación
**Score**: 8/10

**Hallazgos**:
- Cobertura notable: `backend/docs/` (5 archivos: API_REFERENCE, ARCHITECTURE, BUSINESS_RULES, DEPLOYMENT, FRONTEND_INTEGRATION), `frontend/docs/` (5 archivos), `docs/ROADMAP.md` con historial de pivote y fases, `docs/TODO.md` con deuda técnica clasificada por urgencia y un registro de "Resueltos" fechado desde julio, 16 specs por fase en `docs/specs/`.
- `CLAUDE.md` describe con precisión el estado actual del proyecto en general, pero tenía dos afirmaciones desactualizadas detectadas en esta auditoría (ya corregidas en este mismo cambio): decía que `EMAIL_PROVIDER` seguía en `console` en todos lados cuando `smtp` está configurado y verificado en el despliegue real desde el 2026-09-12.
- Único punto débil real: `frontend/docs/STATE_AND_FETCHING.md` congelado en Fase 16 (ver 2.3) — es la excepción notable en un conjunto de documentación por lo demás disciplinado y activamente mantenido.

**Recomendaciones**:
- Actualizar `STATE_AND_FETCHING.md` (único documento con deriva real detectada).
- Considerar un check ligero (aunque sea manual, en la checklist de PR) de "¿esta fase tocó un doc que debía actualizarse?" dado que ya van dos veces que un doc de referencia queda desactualizado silenciosamente.

---

### 2.7 UX / Usabilidad
**Score**: 5.5/10

**Hallazgos**:
- Patrón de fallo silencioso repetido en 3 lugares (dashboard sin `isError`, formulario de ingreso mensual, `QuickTransactionModal`) — todos en el flujo más transitado de la app. El patrón correcto (`noValidate` + toast + error de campo) ya existe en el resto de los formularios desde Fase 12 §12.8; estos tres son la excepción, no la norma.
- Bug de bajo impacto pero visible: `category-distribution` no expone `icon`, así que el desglose de categorías en el dashboard cae siempre al ícono genérico (`Wallet`).
- `AccountUpdate` ignora silenciosamente cambios de `currency` — el usuario edita la moneda de una cuenta desde el frontend, la request sale, no hay error, y el cambio simplemente no se aplica.
- Accesibilidad básica presente pero no exhaustiva: 32 usos de `aria-label`/`alt` en 57 componentes/páginas `.tsx` — cobertura parcial, no auditada campo por campo.
- Cero tests de frontend confirmado (`Vitest`/RTL no configurado, sin archivos `*.test.*`/`*.spec.*`) — para una app que ya tuvo 3 bugs de UX de "silencio ante error" en producción, un test de "la query falla → se ve un mensaje de error" habría atrapado al menos uno de los tres.

**Recomendaciones**:
- Los 3 fixes de "falla silenciosa" son quick wins de alto impacto relativo — la pantalla más usada de la app hoy no distingue "sin datos" de "algo se rompió".
- Priorizar los primeros tests de frontend sobre exactamente estos casos (loading/error/empty state del dashboard) antes que cobertura general — es donde ya se probó que fallan features reales.

---

## 3. Recomendaciones priorizadas

### Quick wins (horas)

1. Chequear ownership antes de reasignar `user_id` en `POST /push/subscribe` (1-2h)
2. Agregar manejo de `isError` + retry visible a las 4 queries del dashboard (2-3h)
3. `noValidate` + error de campo visible en el formulario de ingreso mensual del dashboard (1-2h)
4. Hacer que `PUT /accounts/{id}` aplique cambios de `currency` en vez de ignorarlos (1h)
5. Exponer `category_icon` en el schema/query de `category-distribution` (1h)
6. Actualizar `frontend/docs/STATE_AND_FETCHING.md` con las query keys de Fases 17-22 (2-3h)
7. Confirmar topología de red del host y, si corresponde, acotar el bind de puertos en `docker-compose.yml` (30min-1h una vez confirmado)

### Mejoras medianas (días)

1. **Fix del account takeover de Google OAuth**: invalidar/reconfirmar contraseña al auto-linkear + test del escenario hostil (1-2 días — requiere decisión de producto sobre el flujo de re-confirmación, no solo código)
2. Extraer el delta contable de `transactions.py` a una función pura compartida y testeada (1 día)
3. Partir `schemas.py` por dominio (1-2 días)
4. Cuenta por defecto al registrarse + fix de `QuickTransactionModal` (1 día)
5. Test dedicado para `ensure_recurring_budgets_for_period` (0.5-1 día)
6. Setup mínimo de Vitest + React Testing Library con los primeros tests sobre loading/error/empty state del dashboard (2-3 días)

### Refactoring mayor (semanas)

1. `app/services/` formal, empezando por `ledger.py` (2-3 semanas, incluye migrar la lógica ya extraída en `app/core/` bajo una convención consistente)
2. Capa de excepciones de dominio para desacoplar reglas de negocio de `HTTPException` (1-2 semanas)
3. JWT en cookie `httpOnly` en vez de `localStorage` (1-2 semanas — toca todo el flujo de auth del frontend)
4. CI/CD (lint + test + build por push) (~1 semana)

---

## 4. Próximos pasos sugeridos

### Acciones inmediatas (esta semana)

1. Diseñar y aplicar el fix del account takeover de Google OAuth — es lo único de esta lista con severidad crítica confirmada.
2. Los quick wins de UX del dashboard (isError + formulario de ingreso) — es la pantalla más visitada y ya tiene 3 bugs de la misma familia.
3. Actualizar `STATE_AND_FETCHING.md` — barato y evita que el próximo cambio se apoye en información falsa.

### Roadmap de mejoras (próximo mes)

1. Extraer la lógica contable a una función compartida antes de que se le sume una cuarta copia (ej. transferencias entre cuentas, si entra al roadmap).
2. Primeros tests de frontend, enfocados en los casos que ya se probó que fallan.
3. Confirmar y, si corresponde, corregir la exposición de puertos de `docker-compose.yml`.

---

## 5. Métricas clave

| Área | Score | Prioridad |
|------|-------|-----------|
| Estructura | 7.5/10 | Baja |
| Arquitectura | 6.5/10 | Media |
| Mantenibilidad | 6/10 | Media |
| Modularidad | 5.5/10 | Media |
| Seguridad | 5/10 | **Alta** |
| Documentación | 8/10 | Baja |
| UX/Usabilidad | 5.5/10 | Alta |

**Score general**: 6.3/10
