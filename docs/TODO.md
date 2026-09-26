# Deuda Técnica Consciente — Oikos

> Este archivo documenta atajos tomados a propósito y hallazgos de auditoría pendientes.
> Repriorizado el **2026-08-22** tras el cambio de enfoque a producto multi-usuario, y de nuevo
> el **2026-09-19** tras la vuelta a uso personal (ver [ROADMAP.md](ROADMAP.md)).

Formato: `[ ]` pendiente · `[x]` resuelto — marcar con fecha al resolver.

> **2026-09-19 — vuelta a uso personal.** El supuesto "solo lo uso yo" que el párrafo de abajo
> daba por invalidado el 2026-08-22 vuelve a aplicar, esta vez de forma deliberada y permanente,
> no como default heredado. Los ítems de seguridad/producto multi-usuario que seguían abiertos
> (🟡 API keys TTL/scopes, rate limiting distribuido) se movieron a "Fuera de scope" en
> `ROADMAP.md` — no se van a implementar salvo que el contexto vuelva a cambiar. Los bugs que
> afectan el uso real del dueño del producto (ej. login de Google caído) siguen siendo
> prioritarios: esto no es "dejar de mantener el código", es dejar de invertir en hardening para
> una amenaza que ya no existe.

> **Contexto del cambio anterior (2026-08-22, histórico):** varios items estaban clasificados
> como baja prioridad bajo el supuesto "solo lo uso yo, en red privada Tailscale". Ese supuesto
> dejó de aplicar entonces por la apertura a multi-usuario — y volvió a aplicar el 2026-09-19,
> ver nota arriba.

> **2026-09-15 — Auditoría completa** (seguridad, arquitectura/mantenibilidad, UX/frontend)
> corrida a pedido del usuario. Ítems nuevos marcados `(auditoría 2026-09-15)` abajo. También
> corrigió una afirmación desactualizada en `CLAUDE.md` sobre `EMAIL_PROVIDER` (decía
> "console en todos lados"; en realidad `smtp` está configurado y verificado en el
> despliegue real desde 2026-09-12 — solo falta en `backend/.env` para correr sin Docker).

> **2026-09-06 — Tailscale Funnel activado para uso personal diario.** Oikos ahora es
> alcanzable en `https://<host>.<tailnet>.ts.net` desde fuera de la red privada (celular,
> datos móviles), no solo desde IPs `100.x.x.x` del tailnet. Sigue siendo de un solo usuario
> (vos), así que los bloqueantes de abajo no aplican todavía en el sentido estricto de
> "usuario que no seas vos" — pero el tráfico ya no está contenido a una VPN privada, así que
> vale la pena no postergar demasiado el envío real de email (recuperación de contraseña si
> perdés acceso) y el cron de backup.

---

## 🔴 Bloqueantes de seguridad (histórico — sin ítems abiertos desde el pivote a uso personal)

> Esta sección se mantiene por su historial (el account-takeover de abajo fue real y grave) pero
> ya no se alimenta activamente: con el pivote del 2026-09-19 no hay plan de abrir el producto a
> otros usuarios, así que no se está auditando en busca de nuevos bloqueantes de esta clase. Si
> el contexto cambia, retomar desde acá.

- [x] **Account takeover vía auto-link de Google OAuth (auditoría de seguridad 2026-09-15) —
  resuelto.** *(2026-09-18, Fase 23, `docs/specs/fase_23_spec.md`, commit `6e4d11a`)*
  - `login_google` ahora anula `password_hash` al auto-linkear una cuenta que todavía no
    estaba verificada (`not user.email_verified` capturado antes de mutar nada) — cualquier
    contraseña plantada por un atacante deja de ser válida contra `POST /auth/login` en
    cuanto la víctima real hace login con Google. Una cuenta ya verificada antes de vincular
    Google conserva su contraseña sin cambios.
  - Test de regresión del bug original (`test_existing_unverified_password_account_is_
    autolinked`) corregido + test nuevo del escenario hostil completo
    (`test_autolink_on_unverified_account_nullifies_attacker_planted_password`) +
    regresión sobre la cuenta ya verificada.
  - Nada pendiente de esta entrada — no quedó ningún ítem sin implementar de Fase 23 sobre
    este hallazgo.

---

## 🟠 Bugs confirmados (auditoría 2026-08-22 + 2026-09-15)

- [x] **El dashboard confunde "error de red" con "no hay datos" (auditoría 2026-09-15) —
  resuelto.** *(2026-09-18, Fase 24 §24.1, `docs/specs/fase_24_spec.md`, commit `529de0c`)*
  - Las 4 queries del dashboard (summary/budgets-progress/recent-transactions/category-
    breakdown) ahora exponen `isError`/`refetch`; cada sección muestra un mensaje
    específico + botón "Reintentar" independiente (reutilizando `EmptyState` con un slot
    `action` nuevo) en vez de caer en el mismo estado visual que "sin datos todavía".

- [x] **Formulario de ingreso mensual inline en el dashboard falla en silencio
  (auditoría 2026-09-15) — resuelto.** *(2026-09-18, Fase 24 §24.2, commit `529de0c`)*
  - El `<form>` ahora tiene `noValidate`, el guard custom setea un error de campo visible
    (prop `error` de `Input`) y mueve el foco al input en vez de hacer `return` silencioso
    — mismo patrón que Fase 12 §12.8.

- [x] **`POST /push/subscribe` no valida ownership del `endpoint` (auditoría 2026-09-15) —
  resuelto.** *(2026-09-18, Fase 23, commit `6e4d11a`)*
  - No se bloqueó la reasignación cross-usuario: bloquear rompería el caso legítimo, ya
    documentado a propósito en el propio docstring, de un dispositivo compartido entre dos
    usuarios distintos — y con los datos del request no hay forma de distinguir ambos casos
    del lado del servidor. En vez de eso, cada reasignación que cruza de un usuario a otro
    queda auditada con `logger.warning(...)`, visible vía `docker compose logs -f backend`.
    Severidad ya tasada como baja (el `endpoint` no es adivinable) — visibilidad, no bloqueo.
  - Test nuevo: `test_subscribe_reassigns_ownership_across_users_and_logs_it`
    (`backend/tests/test_push.py`).

- [ ] **Login con Google caído en producción — Google Cloud deshabilitó el proyecto/OAuth
  client (2026-09-19).**
  - Al intentar login con Google desde el celular: `Error 401: disabled_client`. Verificado
    que no es un bug de código — `POST /api/v1/auth/google` y `GoogleAuthButton.tsx` no
    cambiaron; `disabled_client` es un estado que pone Google Cloud sobre el OAuth Client ID
    en sí, no algo que dependa de la app. Confirmado por el usuario: es el **proyecto de
    Google Cloud Console** el deshabilitado (no la cuenta de Google personal) — al loguearse
    ahí salió la pantalla de apelación ("Dinos por qué se debería restaurar tu cuenta").
    Probable falso positivo de los sistemas antifraude automáticos de Google Cloud sobre
    proyectos nuevos/personales, no una violación real de política — el flujo implementado
    (`google.accounts.id.initialize`, Fase 20) solo pide el ID token estándar (email/nombre/
    foto), sin scopes sensibles.
  - Apelación enviada 2026-09-19, pendiente de respuesta de Google (puede tardar días).
  - **Workaround usado mientras tanto:** el flujo de "olvidé mi contraseña"
    (`POST /password-reset/request` + `/confirm`, Fase 7) no tiene ningún guard que impida
    setear contraseña sobre una cuenta con `password_hash = NULL` (cuenta originada en
    Google) — el usuario puede pedir el reset por email normal y quedar con login por
    contraseña utilizable en cualquier dispositivo hasta que Google resuelva la apelación.
    Esto no es una feature diseñada a propósito para este caso, es un efecto colateral de
    cómo coexisten los dos flujos (P3/P4, Fase 20) — vale la pena, cuando haya tiempo,
    decidir si además se quiere un botón explícito "agregar contraseña" en `/settings` para
    cuentas solo-Google en vez de depender del flujo de recuperación.
  - Si la apelación no prospera: recrear el proyecto/Client ID en Google Cloud Console y
    actualizar `GOOGLE_CLIENT_ID`/`NEXT_PUBLIC_GOOGLE_CLIENT_ID` en el `.env` del despliegue
    (ver Fase 20, `docs/specs/fase_20_spec.md`). De paso, completar bien el **OAuth consent
    screen** (nombre real "Oikos", ícono, política de privacidad) — una pantalla de
    consentimiento con branding genérico/incompleto es un factor plausible de por qué el
    proyecto pudo haber sido flageado.

- [x] **En mobile, el popover "Configurar visualización" de los gráficos de Analítica
  (`ChartControlsPopover`) se abre fuera de la pantalla — no se pueden tocar varias de sus
  opciones — resuelto.** *(2026-09-24)*
  - **Reproducido y medido** con Playwright a 390×844 (viewport de celular real), logueado
    con el usuario de prueba, en `/analytics`: al tocar el botón "Configurar visualización"
    de cualquiera de los dos gráficos (`CashflowChart` o `CategoryDonutChart`), el panel
    (`ChartControlsPopover.tsx:39`, `absolute top-full right-0 ... min-w-[180px]`) se
    renderiza con `boundingBox().x = -105` sobre un ancho de 180px — más de la mitad del
    panel queda fuera del viewport a la izquierda, incluyendo, en el caso de la dona
    (sección "Referencia" con 3 grupos de opciones), varios botones que quedan
    completamente inalcanzables al tacto.
  - **Causa raíz:** `ChartControlsPopover` ancla el panel con `right: 0` relativo al propio
    botón disparador — asume que el botón vive pegado al borde derecho de la tarjeta. Eso es
    cierto en desktop porque el header de `CashflowChart.tsx`/`CategoryDonutChart.tsx` usa
    `flex flex-col ... sm:flex-row sm:items-center sm:justify-between` (el `justify-between`
    empuja el botón a la derecha). Pero por debajo del breakpoint `sm` (640px) el header cae
    a `flex-col`: el `div` que envuelve al botón (`className="flex flex-wrap items-center
    gap-2"`, sin alineación propia) hereda `align-items: stretch` del padre y el botón queda
    pegado al borde **izquierdo** de la tarjeta — confirmado por el propio
    `boundingBox()` del botón (`x: 41`, cerca del borde izquierdo de un viewport de 390px).
    Con el ancla `right-0` todavía apuntando a ese botón corrido a la izquierda, el panel
    (~180-220px de ancho) no tiene espacio para desplegarse hacia la izquierda y sale del
    viewport. Mismo bug en ambos gráficos porque ambos comparten el mismo componente
    (`ChartControlsPopover`) y el mismo patrón de header — no es un problema de un chart en
    particular.
  - **Fix aplicado:** `self-end sm:self-auto` agregado al `div` que envuelve a
    `ChartControlsPopover` en `CashflowChart.tsx:72` y `CategoryDonutChart.tsx:138` — en vez
    de tocar la lógica de anclaje genérica de `ChartControlsPopover.tsx`, que queda igual.
    Restaura, en mobile, el mismo supuesto ("el botón está pegado al borde derecho de la
    tarjeta") que ya valía en desktop vía `sm:justify-between`, sin agregar clamping dinámico
    por `getBoundingClientRect`/JS a un componente compartido que hoy solo tiene estos dos
    usos (overkill para 2 call sites idénticos; reconsiderar si un tercer uso futuro
    introduce un layout distinto donde este arreglo no alcance).
  - **Verificado** re-midiendo con Playwright a 390×844 después del cambio: el botón pasa de
    `x: 41` a `x: 300` (pegado al borde derecho de la tarjeta) y el panel pasa de
    `x: -105` a `x: 154` — completamente dentro del viewport `[0, 390]` en ambos gráficos.
    Repetido a 1280×900 (desktop) para confirmar que no cambió el comportamiento previo ahí
    (`sm:self-auto` resetea el `self-end` por encima del breakpoint `sm`). `pnpm lint`,
    `pnpm format` y `pnpm build` limpios.
  - Archivos tocados: `frontend/components/CashflowChart.tsx`,
    `frontend/components/CategoryDonutChart.tsx`. `frontend/components/
    ChartControlsPopover.tsx` no cambió.
  - **Nota al margen, sin relación con este bug:** durante la verificación se detectó que el
    contenedor `backend` de este despliegue corre una imagen Docker más vieja que el HEAD del
    repo — construida 2026-09-19 08:41, **antes** del commit de Fase 26 (`ecbfe22`,
    2026-09-19 11:22) que agregó `app/core/auth_cookies.py`. Con esa imagen, `POST
    /auth/login` no setea ningún cookie de sesión (confirmado con `curl`, sin `Set-Cookie` en
    la respuesta) y el frontend actual (que ya no manda `Authorization: Bearer`, solo cookies)
    no puede loguearse contra ese backend — el login parece "no hacer nada" en vez de fallar
    con un error visible. No se tocó nada de esto (está fuera del alcance de este ítem);
    recomendable reconstruir/redeployar el backend (`docker compose up -d --build backend`)
    cuando el dueño del proyecto lo confirme, ya que es una acción sobre el despliegue real.

- [ ] **`docker-compose.yml` publica backend (8000) y frontend (3000) en todas las
  interfaces, no solo Tailscale (auditoría 2026-09-15).**
  - Los puertos se publican como `"8000:8000"`/`"3000:3000"` (bind a `0.0.0.0`).
  - **Verificado con el usuario (2026-09-16): el host no tiene ninguna otra interfaz de red
    pública** (solo Tailscale) — el riesgo queda confirmado como teórico/bajo por ahora. Se
    deja anotado, sin tarea de fase: revisar de nuevo si el despliegue alguna vez gana otra
    ruta de red (IP pública directa, otra VPN, NAT de nube).

- [x] **Un usuario nuevo no puede registrar nada — obsoleto, ya resuelto.** *(detectado como
  desactualizado el 2026-09-16, al convertir el audit en fases del ROADMAP)*
  - Este ítem quedó sin marcar tras la Fase 8 (2026-08-23, "Cuenta por defecto al registrarse"):
    `inicializar_datos_usuario_nuevo` (`backend/app/api/users.py:48-90`) ya crea una cuenta por
    defecto en el registro desde esa fecha. Verificado contra el código actual — el bug no
    existe más.

- [x] **Los presupuestos no sobreviven al cambio de mes — obsoleto, ya resuelto.** *(detectado
  como desactualizado el 2026-09-16, misma pasada que el ítem anterior)*
  - `Budget.is_recurring` (`backend/app/models/models.py:107`) y `budget_recurrence.py`
    (`ensure_recurring_budgets_for_period`) ya resuelven esto desde Fase 8 (2026-08-23,
    "Presupuestos recurrentes"). Verificado contra el código actual. El único gap real
    relacionado es la falta de test directo sobre esa función — ver Fase 25 del ROADMAP.

- [x] **`Account PUT` ignora cambios de `currency` silenciosamente — resuelto.** *(2026-09-18,
  Fase 24 §24.3, commit `529de0c`)*
  - `actualizar_cuenta` ahora aplica `currency` cuando cambia de verdad y la cuenta no tiene
    transacciones activas; si las tiene, responde `400` (mismo criterio que `eliminar_cuenta`)
    en vez de ignorar el campo en silencio. De paso pasó a actualización parcial real
    (`model_fields_set`), lo que también corrigió un bug encontrado en el camino: un `PUT`
    que omitía `highlighted` lo reseteaba a `false` en cada edición de nombre/tipo.
  - Verificado que hoy ningún caller de la UI web envía `currency` en este endpoint (el modal
    de edición no tiene selector de moneda) — el efecto observable es para callers directos
    de la API por ahora.

- [ ] **Cambiar `preferred_currency` no invalida `dashboardSummary` ni `budgets-progress`
  (Fase 29, preexistente).**
  - `useUserPreferences` (`frontend/lib/hooks/useUserPreferences.ts`) invalida `currentUser` y
    `dashboard.categoryBreakdown` al cambiar la moneda, pero no las dos queries que arman la
    tarjeta de flujo y los anillos de presupuesto: siguen sirviendo desde cache montos
    calculados con la moneda anterior hasta que el `staleTime` (1 min) las refresca.
  - Con la navegación por mes el síntoma es el mismo: la tarjeta se rotula en la moneda nueva y
    muestra sumas de la vieja. Es un bug de invalidación, no de contrato — la Fase 29 lo
    mantuvo fuera de alcance y lo dejó anotado acá.

---

## 🟡 Integridad y escala

- [ ] **El filtro de cuentas destacadas no es el mismo en todo el dashboard (Fase 29,
  aceptado).**
  - `GET /dashboard/summary` filtra `balances`, `monthly_income_by_currency` y
    `monthly_expense_by_currency` por `highlighted`; en cambio las barras de
    `category-distribution`, el `spent` de los presupuestos y los campos nuevos
    `first_transaction_month` / `expense_currencies` cuentan **todas** las cuentas.
  - Consecuencia visible: la tarjeta de flujo puede no cuadrar con las barras, y una cuenta no
    destacada aporta a las barras pero no a la tarjeta. Todo usuario nace con su cuenta por
    defecto destacada, así que el caso "no hay ninguna" es raro.
  - La Fase 29 lo mantiene a propósito (Decisión Q16) y lo dejó escrito en
    `backend/docs/BUSINESS_RULES.md`. Unificarlo es una decisión de producto: qué hacer con las
    cuentas no destacadas (agregarlas al filtro, o sacarlas del filtro y sumar todo).

- [ ] **Mes UTC contra hora Bogotá, y la semana del resumen semanal contra la de Analítica
  (Fase 29, aceptado).**
  - El "mes actual" se resuelve en UTC (Decisión B1), así que desde las 19:00 hora Bogotá del
    último día el backend ya está en el mes siguiente. Es preexistente y la fase no lo empeora;
    el desfase se acepta como supuesto 1 de la spec, documentado en
    `backend/docs/API_REFERENCE.md`.
  - `core/weekly_summary.py` calcula la semana en `America/Bogota` mientras que la semana
    calendario de Analítica (lunes–domingo) es UTC: los totales de ambos pueden diferir en el
    borde del domingo noche / lunes.

- [ ] **Techo inconsistente en `GET /accounts/{id}/monthly-summary` (Fase 29, aceptado).**
  - `api/accounts.py` acota el mes hasta el último día a las 23:59:59 aunque esté en curso,
    mientras que `dashboard/summary` lo acota a "ahora" (`core/periods.limites_mes_utc`): una
    transacción con fecha futura del mismo mes cuenta en la tarjeta de la cuenta y no en la del
    dashboard.
  - Unificarlo (y darle período consultable, como el summary) quedó fuera de alcance en la
    Fase 29.

- [ ] **`GET /budgets/?month=&year=` sigue generando presupuestos recurrentes en meses
  cerrados (Fase 29, aceptado).**
  - El guard de la Decisión B5 acota al mes actual la generación tanto en
    `dashboard/budgets-progress` como en el motor de alertas, pero este tercer caller quedó
    fuera a propósito: listar un mes pasado por la API crea las filas que la plantilla
    recurrente habría generado, igual que antes de la fase.
  - Ningún call site del frontend lo usa con período, así que no hay efecto en la app; queda
    anotado para que no se lea como un descuido cuando se toque `budgets.py`.

- [x] **API keys: TTL opcional y scopes — cerrado como fuera de scope.** *(2026-09-19, pivote a
  uso personal, ver `docs/ROADMAP.md`)*
  - Eran decisiones de producto pensadas para un catálogo de usuarios con distintos niveles de
    confianza entre sí. Con un solo dueño de todas las keys emitidas, el riesgo que TTL/scopes
    mitigarían (una key de un usuario comprometiendo a otro, o key vieja de un tercero) no
    aplica. Ver detalle previo en el historial de este archivo antes del 2026-09-19 si se
    reconsidera en el futuro.

- [x] **Rate limiting en memoria (`slowapi`), sin backend distribuido — cerrado como fuera de
  scope.** *(2026-09-19, pivote a uso personal, ver `docs/ROADMAP.md`)*
  - Estaba "diferido a propósito" desde Fase 7 a la espera de que el despliegue escalara a
    múltiples workers/réplicas. Con el pivote a uso personal permanente, esa escala no está
    planeada — deja de ser "pendiente" y pasa a "no se va a hacer". Diseño (Redis +
    `storage_uri`) sigue documentado en `docs/specs/fase_07_spec.md` §2.6.1 por si el contexto
    cambia.

- [x] **`frontend/docs/STATE_AND_FETCHING.md` (el mapa de query keys/invalidación) estaba
  congelado en Fase 16 (auditoría 2026-09-15) — resuelto.** *(2026-09-18, Fase 25 §25.6,
  `docs/specs/fase_25_spec.md`, commit `6debfc1`)*
  - Documenta ahora `userPreferences`, las keys por-cuenta (`monthlySummary`/
    `budgetsProgress`/`categoryBreakdown`), los params `account_id`/`currency` de
    analítica, las invalidaciones de mutations de Settings, y los 3 hooks compartidos
    nuevos de §25.4. Corrección de precisión hecha en el mismo cierre: no existe ninguna
    query key separada para "categorías ocultas" — `is_hidden` es un campo más de
    `GET /categories/`, filtrado client-side.

- [x] ~~**JWT guardado en `localStorage`** (`frontend/lib/api.ts`)~~ — **resuelto.** *(2026-09-19,
  Fase 26, `docs/specs/fase_26_spec.md`)* — migración a cookies `httpOnly`
  (`access_token`/`refresh_token`/`csrf_token`) con CSRF double-submit (`X-CSRF-Token` en
  mutaciones), fallback de `get_current_user` a cookie con el camino de API key
  (`oikos_pat_...`) intacto, refresh/logout sin body, y producción consolidada en el dominio
  HTTPS del Funnel (`COOKIE_SECURE=true` por default). Backend: 251 tests verdes; frontend:
  tsc + eslint limpios. Corregido durante la revisión final: el Path del cookie
  `refresh_token` era demasiado angosto (`/api/v1/auth/refresh`) y nunca llegaba a
  `POST /auth/logout` (ruta hermana, no subruta), así que el logout desde el navegador no
  revocaba nada server-side — se amplió a `/api/v1/auth` (cubre login/google/refresh/logout/
  password-reset/verify-email), con un test de regresión nuevo
  (`test_logout_via_cookie_only_revokes_refresh_token_server_side`).

---

## 🟢 Modularidad — revisar cuando el código duela al modificarlo

- [x] **Lógica de negocio embebida en routers FastAPI — y la excepción ya existente apuntaba
  al lado equivocado (actualizado 2026-09-15) — resuelto para el código de mayor riesgo.**
  *(2026-09-18, Fase 25 §25.1, `docs/specs/fase_25_spec.md`, commit `6debfc1`)*
  - `app/services/ledger.py` nace como el primer módulo real de `app/services/` — 4
    funciones puras que reemplazan la lógica contable (signo del delta + `UPDATE` atómico)
    que estaba copy-pasteada tres veces en `transactions.py` (`crear_transaccion`/
    `actualizar_transaccion`/`eliminar_transaccion`), justo el código de mayor riesgo que
    esta entrada señalaba como el que debía extraerse primero. Sigue el mismo patrón
    "función pura + `db: Session`" que ya usaba `budget_alerts.py`.
  - Los routers siguen siendo dueños de la transacción SQL (commit/rollback) — `ledger.py`
    solo ejecuta los `UPDATE`, no comitea. Nuevo `test_ledger.py` (6 tests unit-level).
  - No resuelto (a propósito, fuera de alcance de esta entrada): el resto de la lógica de
    negocio de los otros 10 routers sigue viviendo inline — esta entrada solo apuntaba al
    código contable de `transactions.py`.

- [x] **`schemas.py` (462 líneas, 49 clases) estaba más forzado que `models.py` (341 líneas,
  14 clases) — priorizar partir schemas primero (auditoría 2026-09-15) — resuelto.**
  *(2026-09-18, Fase 25 §25.2, `docs/specs/fase_25_spec.md`, commit `6debfc1`)*
  - `schemas.py` tenía en realidad 48 clases, no 49 (corrección de precisión hecha en el
    spec). Partido en 12 módulos por dominio bajo `app/schemas/`; `schemas.py` queda como
    shim de re-exports (`from app.schemas import schemas` sigue funcionando igual en los
    11 routers, cero archivos de `app/api/` tocados). `models.py` (en realidad 13 clases,
    no 14) sigue sin partir — la propia auditoría ya lo marcaba como no urgente.

- [x] **`budget_recurrence.py` sin test dedicado para la lógica de generación de períodos
  (auditoría 2026-09-15) — resuelto.** *(2026-09-18, Fase 25 §25.7,
  `docs/specs/fase_25_spec.md`, commit `6debfc1`)*
  - `test_budget_recurrence.py` nuevo, 5 tests directos sobre
    `ensure_recurring_budgets_for_period`: salto de año, plantilla más reciente con un gap
    de varios meses, skip de una fila editada a mano, dos categorías independientes en el
    mismo período, y la rama de `IntegrityError`/rollback bajo carrera. `test_budgets.py`
    no cambió — sigue cubriendo el round-trip de `is_recurring` vía HTTP.

- [x] **Sin capa de excepciones de dominio — resuelto como piloto acotado, no como
  cobertura completa.** *(2026-09-18, Fase 25 §25.3, `docs/specs/fase_25_spec.md`,
  commit `6debfc1`)*
  - `app/core/exceptions.py` (`DomainError` + `AccountNotFoundError`/
    `CategoryNotFoundError`) + un único `exception_handler` en `main.py` que devuelve el
    mismo shape `{"detail": ...}` que `HTTPException` ya devolvía — sin cambio de contrato
    de API. Solo los 4 `raise HTTPException` con strings duplicados de `transactions.py`
    migraron; los ~59 `raise HTTPException` restantes de los otros 10 routers quedan como
    trabajo incremental, router por router, la próxima vez que se toquen por otra razón —
    decisión explícita para no forzar una reescritura de 63 sitios en esta fase.

- [x] **Extensión completa de `DomainError` a los 10 routers restantes — resuelto.**
  *(2026-09-19, Fase 28, `docs/specs/fase_28_spec.md`)*
  - Los 65 `raise HTTPException` que quedaban en `app/api/` (14 en `transactions.py` + los 10
    routers restantes) migraron a `DomainError` y subclases, traducción mecánica 1:1 (mismo
    `status_code`, mismo `detail`) — cero cambio de contrato de API. Taxonomía ampliada con
    `BadRequestError`/`UnauthorizedError`/`ForbiddenError`/`NotFoundError`/`ConflictError`/
    `ValidationError`/`InternalServerError`/`ServiceUnavailableError`. 251 tests en verde,
    `ruff` limpio. Cierra el ítem de arriba: ya no es un piloto de un solo router.

- [x] **`schemas.py` y `models.py` como archivos únicos — resuelto para `schemas.py`.**
  *(2026-09-18, Fase 25 §25.2 — mismo ítem que la entrada de arriba sobre `schemas.py`,
  entrada duplicada preexistente que apuntaba a la misma tarea)*
  - `models.py` sigue como archivo único — explícitamente fuera de alcance de Fase 25 (ver
    entrada de arriba): ya está bien encapsulado por clase y la propia auditoría no lo
    marcaba como urgente.

- [x] **Frontend: fetching duplicado por página — resuelto.** *(2026-09-18, Fase 25 §25.4,
  `docs/specs/fase_25_spec.md`, commit `6debfc1`)*
  - `frontend/lib/hooks/{useAccounts,useCategories,useTransactions}.ts` reemplazan el
    `useQuery` + `queryFn` inline en 19 call sites (10 de cuentas, 8 de categorías, 1 de
    transacciones). Solo lecturas — las mutaciones (crear/editar/borrar) siguen inline por
    página, porque sus listas de invalidación son demasiado heterogéneas para un hook
    único sin perder precisión.

- [x] **`transactions/page.tsx` creció a 604 líneas — resuelto.** *(2026-09-19, Fase 27,
  `docs/specs/fase_27_spec.md`)*
  - Descompuesto en `components/transactions/{TransactionFilters,TransactionList}.tsx` +
    `components/modals/EditTransactionModal.tsx`. La página queda en 313 líneas como
    orquestador (estado de filtros URL-synced, paginación, mutaciones). Refactor puro, sin
    cambio de comportamiento — `pnpm lint`/`pnpm build` limpios.

- [ ] **Tipos de dominio no compartidos backend→frontend.**
  - Enums en Python vs string unions en TS, mantenidos a mano.
  - Resuelto a medias en Fase 16 §16.3: ya existe codegen desde OpenAPI
    (`frontend/types/generated/api.ts` + script `pnpm gen:types`), usado para código nuevo
    (API keys, reconciliación). Pendiente: migrar oportunistamente los call sites existentes
    que usan los tipos manuales (Decisión 16.3.2, convivencia deliberada sin fecha de
    deprecación).

- [ ] **Nomenclatura mezclada español/inglés** dentro del mismo módulo.
  - `crear_transaccion` devuelve `TransactionResponse`; variables `cuenta`/`transaccion`
    junto a `models.Account`. Irrelevante en solitario, molesto si el proyecto se abre.

- [x] **`category-distribution` no expone `icon` — resuelto.** *(2026-09-18, Fase 24 §24.4,
  commit `529de0c`)*
  - `CategoryDistributionData`/`category-distribution` ahora exponen `category_icon` (mismo
    campo que `BudgetProgress`), y `CategoryBreakdownBars` lo consume — el desglose por
    categoría del dashboard muestra el ícono real en vez de caer siempre al fallback `Wallet`.

---

## 🔵 Solo si el proyecto crece

- [ ] CI/CD (lint + test + build en cada cambio).
- [ ] Tests de frontend (Vitest + React Testing Library).
- [ ] Sincronización offline (las columnas `updated_at` de la Fase 8 la dejan preparada).

---

## Resueltos

| Fecha | Item |
|-------|------|
| 2026-09-13 | `NEXT_PUBLIC_GOOGLE_CLIENT_ID` no llegaba al bundle del frontend en Docker — `docker-compose.yml` solo pasaba `NEXT_PUBLIC_API_URL` como build arg del servicio `frontend`, y `frontend/Dockerfile` no tenía el `ARG`/`ENV` correspondiente para `NEXT_PUBLIC_GOOGLE_CLIENT_ID`. Efecto: aunque se configurara la variable en `.env`, `GoogleAuthButton` nunca la vería y el botón de Google no aparecía en `login`/`register`. Corregido: build arg agregado en `docker-compose.yml` (prod) y `docker-compose.dev.yml` (dev, vía `environment:`), `ARG`/`ENV` agregado en `frontend/Dockerfile`. Sigue pendiente generar el Client ID real en Google Cloud Console y setearlo en el `.env` de despliegue — sin eso, el botón sigue sin aparecer aunque el plumbing ya esté arreglado |
| 2026-09-13 | Login con Google (Fase 20 §20.3, ítem 3) — `POST /api/v1/auth/google` con ID token de Google Identity Services: `users.password_hash` pasa a nullable + nueva columna `users.google_id` (migración `5b79ad1d27e4`), auto-link de cuentas existentes por email y `email_verified=true` de inmediato (Decisión P4), cuenta por defecto + categorías ocultas vía helper compartido `inicializar_datos_usuario_nuevo`, botón `GoogleAuthButton` en login/register (oculto si falta `NEXT_PUBLIC_GOOGLE_CLIENT_ID`). Nota P4 sobre el bloqueo de SMTP (ver entrada 2026-09-12): ya **no es un bloqueo total** — el login con Google es una vía de registro que funciona de punta a punta incluso con `EMAIL_PROVIDER=console`; el registro por contraseña sigue dependiendo de SMTP real. Ver `docs/specs/fase_20_spec.md` |
| 2026-09-13 | Plantilla de correo con marca (Fase 20) — los correos de verificación/reset ya no son un `<p>` con link pelado; ahora usan `render_email_html()` (header "Oikos", botón real, link de respaldo en texto) — ver `docs/ROADMAP.md` Fase 20 |
| 2026-09-12 | `EMAIL_PROVIDER=smtp` configurado y verificado de punta a punta contra el `.env` real de despliegue (Gmail + contraseña de aplicación): registro → email real entregado → click en el link → `email_verified=true` → login que antes daba `403 EMAIL_NOT_VERIFIED` ahora da `200`. Las credenciales viven solo en el `.env` del despliegue (gitignored, no en el repo) — `backend/.env` (modo sin Docker) sigue sin estas variables, así que correr sin Docker sigue cayendo a `EMAIL_PROVIDER=console` salvo que se agreguen ahí también |
| 2026-09-12 | Login ahora exige `email_verified` (reversa la decisión original de Fase 7 §2.2 de no bloquear el login): `POST /api/v1/auth/login` responde `403` con `detail.code == "EMAIL_NOT_VERIFIED"` para un usuario sin verificar; nuevo `POST /api/v1/auth/resend-verification` (enumeration-safe, 5 req/min) reenvía el link. `seed.py` marca el usuario de prueba como verificado para no romper el seed. Efecto secundario: el auto-login post-registro (Decisión 15.0.3) ahora falla para todo usuario nuevo y cae al fallback existente (`/login?registered=true`) — el onboarding instantáneo post-registro queda pausado hasta que el usuario verifique, ver bloqueante de envío real de correo arriba |
| 2026-09-12 | Fase 17 — presupuestos multi-moneda y analítica por cuenta: índice único de `budgets` ensanchado a `(user_id, category_id, month, year, currency)` (migración `b5a09d0bed5e`) + `actualizar_presupuesto` ahora asigna `currency` con `try/except IntegrityError` (antes el campo se ignoraba en silencio y editar la moneda a una ocupada daba 500, mismo patrón que el gap de `AccountUpdate.currency`) + filtro por moneda en `dashboard/budgets-progress` (filtra filas, no recalcula `spent`) + motor de alertas evaluado con `.all()` por presupuesto (antes `.first()` dejaba sin avisar al segundo presupuesto por categoría/período en otra moneda) + `account_id` en `dashboard/category-distribution` + nuevo `GET /accounts/{id}/monthly-summary` — ver `docs/specs/fase_17_spec.md` §17.1/17.2 |
| 2026-09-06 | Saldos de cuenta sin reconciliación posible — resuelto en Fase 16 §16.4: `opening_balance` inmutable (con backfill en la migración `e460a42926d7`) + `POST /accounts/{id}/reconcile`. Nota: el backfill solo establece línea de base hacia adelante, no audita desviaciones históricas (ver `BUSINESS_RULES.md`) |
| 2026-09-06 | API keys personales revocables (Fase 16 §16.1): tabla `api_keys` (migración `6c9bbf3564cc`), auth alternativa `oikos_pat_*` en `get_current_user`, CRUD `/api/v1/api-keys/`, UI en `/settings` |
| 2026-09-06 | Revisión de seguridad de API keys (Decisión 16.1.8) corrida y sus hallazgos accionables corregidos: reset de contraseña ahora revoca también las API keys activas (antes solo revocaba refresh tokens, dejando una key minteada durante un compromiso viva para siempre — `auth.py`); el rate limit de `POST /transactions` pasó de clavear por hash de la key a clavear por `user_id` resuelto en DB (antes un usuario con N keys multiplicaba por N su cuota real de 60/min — `rate_limit.py`); `POST /api-keys/` ganó rate limit `5/minute` + tope de 20 keys activas por usuario (antes no tenía ninguno de los dos — `api_keys.py`). TTL obligatorio y scopes quedan como recomendaciones de producto sin implementar, ver 🟡 |
| 2026-08-23 | Idempotencia en `POST /transactions` (`Idempotency-Key` + tabla `idempotency_keys`) — resuelto en Fase 10, ver `docs/ROADMAP.md` §10.4. Entrada corregida el 2026-09-06 al detectarse desactualizada durante el análisis de la Fase 16 (`docs/specs/fase_16_spec.md`, hallazgo 12) |
| 2026-08-23 | Fase 11 — bugs multi-moneda del dashboard: `budgets-progress` agrupa el gasto por `(categoría, moneda)` y expone `currency`; `cashflow-series` y `category-distribution` filtran por una sola moneda (param `currency`, default la preferida) — ver `docs/specs/fase_11_spec.md` §11.1 |
| 2026-08-23 | Bug `actualizar_transaccion` no actualizaba `currency`: ahora siempre hereda la moneda de la cuenta destino, igual que en la creación (Fase 11 §11.2) |
| 2026-08-22 | Fase 7 completa — ver `docs/specs/fase_07_spec.md` para el detalle de cada ítem: |
| 2026-08-22 | Migraciones versionadas con Alembic (reemplaza `create_all()` + `_ensure_*_column()` ad-hoc) |
| 2026-08-22 | Bug `preferred_theme` nunca se agregaba a DBs existentes (resuelto por la migración baseline) |
| 2026-08-22 | Índices en `transactions` (`user_id`+`date` compuesto, `account_id`, `category_id`) |
| 2026-08-22 | Constraint `UNIQUE(user_id, category_id, month, year)` en `budgets` |
| 2026-08-22 | FKs de `transactions` con `nullable=False` |
| 2026-08-22 | Migración legacy de categorías retirada de `seed_default_categories()` (corría en cada arranque) |
| 2026-08-22 | Secretos fuera de `docker-compose.yml` — `POSTGRES_PASSWORD`/`SECRET_KEY` obligatorias, sin default silencioso |
| 2026-08-22 | Versionado de API bajo `/api/v1/` (backend + frontend, `lib/api.ts` centraliza el prefijo) |
| 2026-08-22 | Tests del módulo contable y de autenticación (pytest + httpx, `backend/tests/`) |
| 2026-08-22 | Recuperación de contraseña y verificación de email (código completo — ver bloqueante de envío real arriba) |
| 2026-08-22 | Política de contraseñas (`min_length=10` + validación de fuerza) |
| 2026-08-22 | Rate limiting en registro y en recuperación de contraseña |
| 2026-08-22 | Logout invalida efectivamente el access token (TTL bajado de 60 a 15 min) |
| 2026-08-22 | Regex CORS de Tailscale condicional a `ENABLE_TAILSCALE_CORS`, ya no incondicional |
| 2026-08-22 | Logging estructurado (JSON a stdout) + `X-Request-ID` |
| 2026-08-22 | `scripts/backup.sh` con rotación de 7 días (falta programar el cron, ver bloqueante arriba) |
| 2026-09-13 | Backup automático programado — servicio `backup` en docker-compose.yml (dispara en cada `docker compose up`, no cron de host) + subida cifrada a Google Drive (cuenta de Oikos) vía rclone crypt, retención 7d local / 30d nube. Ver docs/BACKUPS.md. Reemplaza el bloqueante de arriba |
| 2026-07-14 | datetime.utcnow() migrado a datetime.now(timezone.utc) |
| 2026-07-14 | Formularios migrados de raw input/select a componentes UI |
| 2026-07-14 | Bug multi-moneda en `/dashboard/summary` (agrupación por moneda) |
| 2026-07-14 | Headers de seguridad vía middleware FastAPI |
| 2026-07-14 | Sanitización de errores en `cashflow-series` |
| 2026-07-11 | Migración SQLite → PostgreSQL via Docker |
| 2026-07-10 | Rate limiting en login verificado y documentado |
| 2026-07-10 | CSS bug dashboard corregido (max-w-[1600px] no se aplicaba) |
| 2026-07-10 | finanzas.db excluido de git (*.db en .gitignore) |
| 2026-07-08 | Montos float → Decimal/Numeric(14,2) |
| 2026-07-08 | Refresh tokens implementados |
| 2026-07-06 | CORS → variable de entorno ALLOWED_ORIGINS |
| 2026-07-06 | SECRET_KEY regenerada criptográficamente |
| 2026-07-06 | EmailStr + normalización email |
| 2026-07-06 | .dict() → model_dump() |
