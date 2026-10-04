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

> **2026-09-26 — Primera pasada de QA** (agente `qa-engineer` + Playwright) sobre `bc9dcb9`, en un
> entorno aislado (SQLite, puertos 8001/3001, sin Docker — ver QA-001). Reporte completo con
> pasos de reproducción y capturas: `.scratch/qa-2026-09-26/REPORTE_QA.md` (no versionado).
> Ítems nuevos marcados `(QA 2026-09-26, QA-NNN)` abajo. Una tercera pasada el mismo día
> re-verificó contra un Postgres 16 desechable (contenedor suelto en 5433, tmpfs) los ítems que
> podían depender del motor: QA-003, QA-006 y QA-015 confirmados; los "artefactos de SQLite"
> (fechas sin zona, saldos REAL) no existen en Postgres; los KPIs de Analítica cuadran en todos
> los bordes de periodo. Aportó QA-019 a QA-022.

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

- [x] **Condición de carrera en `DELETE`/`PUT /transactions/{id}` descuadra el saldo de la
  cuenta (QA 2026-09-26, QA-003) — 🔴 crítico — resuelto.** *(2026-09-27, Fase 31, `docs/specs/fase_31_spec.md`)*
  - Resolución: `SELECT … FOR UPDATE` sobre la transacción como primera consulta de `PUT` y
    `DELETE`, borrado condicional (`UPDATE … WHERE deleted_at IS NULL`, `404` sin tocar el saldo
    si no afecta filas) y reversión del saldo solo después; `aplicar_edicion` ordena los
    `UPDATE` de cuentas por `account_id` (sin deadlock A→B/B→A). Tests: intercalado
    determinista en SQLite + `tests/test_concurrency_pg.py` (marker `postgres`,
    `reconcile.discrepancy == 0` en los 4 escenarios).
  - 8 `DELETE` paralelos sobre la misma transacción → 6 respuestas `200` y saldo final
    100.050,00 en vez de 100.000,00 (−50); 8 `PUT` paralelos → discrepancia 35,00.
  - Causa: `backend/app/api/transactions.py:278-297` (y el `PUT`) leen la transacción sin
    lock y aplican el delta de `services/ledger.py` sin condición; no hay `with_for_update`
    en todo el backend. El soft-delete no es condicional (`UPDATE ... WHERE deleted_at IS NULL`
    + chequeo de filas afectadas).
  - **Confirmado también en Postgres 16** (READ COMMITTED): 8 `DELETE` paralelos → de 1 a 5
    respuestas `200` por ronda, discrepancia siempre `(n200 − 1) × monto` (hasta +200 sobre un
    gasto de 50); 8 `PUT` paralelos → 8/8 `200` y discrepancias de −15 a −135 (deltas calculados
    sobre un `amount` viejo). Escenario mixto 4 `PUT` + 4 `DELETE`: ambos responden `200` y la
    transacción queda borrada con el monto editado, aplicando el delta de edición *y* la
    reversión. `POST /accounts/{id}/reconcile` detecta y corrige la discrepancia.
  - En la UI el doble clic manda un solo `DELETE`; el riesgo real es reintentos de red, dos
    pestañas o clientes con API key.
  - Fix probable: `with_for_update()` sobre la transacción (y la cuenta) + borrado condicional;
    test de regresión concurrente que corra contra Postgres (SQLite serializa distinto) — hoy
    `backend/tests/conftest.py` usa siempre SQLite en memoria, habría que aceptar algo como
    `TEST_DATABASE_URL` para ese test.

- [x] **Montos o saldos por encima de `Numeric(14,2)` dan `500` en vez de `422`
  (QA 2026-09-26, QA-015) — resuelto.** *(2026-09-27, Fase 31, `docs/specs/fase_31_spec.md`)*
  - Resolución: `max_digits=14` (`MAX_DIGITS_MONEY` en `schemas/common.py`) en los cuatro
    campos de dinero de entrada (incluido `amount_limit` de presupuestos) → `422` de Pydantic;
    el desborde del saldo en `POST`/`PUT`/`DELETE /transactions` → `422` de dominio con saldo
    intacto. Tests en `tests/test_money_limits.py` (SQLite + Postgres).
  - `POST`/`PUT /transactions` con 13 dígitos enteros (`1234567890123.45`,
    `1000000000000.00`) → `500` "Error interno al procesar la transacción contable.";
    `POST /accounts` con `balance` de 13 dígitos y `PATCH /users/me` con `monthly_income` de 13
    dígitos → `500` en texto plano (excepción no controlada en ASGI, no pasa por `DomainError`).
    12 dígitos (`999999999999.99`) pasa bien.
  - Variante: con la cuenta en 999.999.999.999,99, un ingreso válido de 1,00 también da `500`
    — desborda el `UPDATE accounts SET balance = balance + …`, no el monto en sí.
    Log: `psycopg2.errors.NumericValueOutOfRange: numeric field overflow`.
  - El rollback funciona (saldo intacto). Impacto práctico bajo (montos irreales), pero son
    `500` evitables: `max_digits=14, decimal_places=2` en los schemas + traducir el overflow
    del saldo a un `422`/`ValidationError`.

- [x] **Bucle infinito de recargas en `/login` con una cookie `csrf_token` huérfana
  (QA 2026-09-26, QA-021) — resuelto.** *(2026-09-27, Fase 31, `docs/specs/fase_31_spec.md`)*
  - Resolución: el `401` de `POST /auth/refresh` borra las tres cookies de sesión (siempre,
    B10), y el interceptor de `lib/api.ts` no redirige a `/login` desde una ruta de
    autenticación (F4). Revisado por `security-reviewer` sin hallazgos; verificado con
    Playwright (una sola carga, cookie borrada, login OK).
  - Con una `csrf_token` presente pero sin refresh token válido en la base, `/login` se recarga
    ~5 veces por segundo (157 `401` de `/auth/refresh` en el log) y es imposible iniciar sesión
    sin borrar las cookies a mano.
  - Causa: `UserPreferencesSync` (global) activa la query de preferencias si `haySesionActiva()`
    (`lib/authSession.ts`, solo mira si existe `csrf_token`) → `401` → `auth/refresh` `401` →
    el interceptor (`lib/api.ts:71`) hace `window.location.href = '/login'` aunque ya esté en
    `/login`. Además el `401` de `/auth/refresh` (`backend/app/api/auth.py`) no llama a
    `limpiar_cookies_de_sesion`, así que la cookie huérfana nunca se borra.
  - Disparador real sospechado (no reproducido): un reset de contraseña desde otro dispositivo
    revoca los refresh tokens pero la `csrf_token` (30 días) sobrevive en el otro navegador; al
    expirar el `access_token` (15 min) ese navegador cae en el bucle. Lo mismo tras restaurar o
    recrear la base.
  - Fix probable: no redirigir si ya está en `/login`, y limpiar cookies en el `401` de refresh.

- [x] **Un `422` con `detail` en forma de lista tumba la página entera (QA 2026-09-26,
  QA-004) — resuelto.** *(2026-09-27, Fase 31, `docs/specs/fase_31_spec.md`)*
  - Resolución: `getApiError` aplana cualquier `detail` (texto, lista de Pydantic, objeto) a
    texto (F1), y todos los formularios con montos validan decimales/dígitos antes de enviar
    con error de campo (`lib/validateAmount.ts`, F2).
  - Monto `0.001` en `/capture` o `12.345` en el modal de transacción → backend `422` con
    `detail: [...]` (formato Pydantic) → `getApiError` (`frontend/lib/utils.ts:3-6`) lo pasa
    tal cual a `toast.error` → "Objects are not valid as a React child" → "This page couldn't
    load". Se pierde lo escrito en el formulario.
  - `getApiError` se usa en 13 archivos: arreglarlo ahí (aplanar `detail` lista/objeto a texto)
    cubre todos. De paso, validar decimales en el cliente antes de enviar.

- [x] **El onboarding (moneda + ingreso) nunca aparece para registros con contraseña
  (QA 2026-09-26, QA-005) — resuelto.** *(2026-09-27, Fase 31, `docs/specs/fase_31_spec.md`)*
  - Resolución: `lib/postLoginDestination.ts`, compartido por login y Google: sin historial →
    `/capture?onboarding=1`; el wizard pide moneda e ingreso solo si `monthly_income` es
    `null`, con placeholder mientras carga el usuario (F5). Verificado con Playwright de punta
    a punta (registro → verificación → login → wizard).
  - Registro → auto-login `403 EMAIL_NOT_VERIFIED` → `/login?registered=true` → verificar →
    login → `/capture` **sin `?onboarding=1`**. El único push a `/capture?onboarding=1` está
    en `app/(auth)/register/page.tsx:71`, dentro del auto-login que siempre falla desde que la
    verificación es obligatoria (2026-09-12, ver Resueltos). `app/(auth)/login/page.tsx:85-87`
    manda a `/capture` sin el flag. Forzando `?onboarding=1` a mano el wizard funciona.
  - Fix probable: que el login decida el onboarding desde el estado del usuario (p. ej.
    `!has_transaction_history` y sin onboarding completado), no desde el flag de la URL.

- [x] **El entorno "dev" de Docker comparte base de datos, puertos y nombre de proyecto con
  producción (QA 2026-09-26, QA-001) — resuelto.** *(2026-09-27, Fase 31, `docs/specs/fase_31_spec.md`)*
  - Resolución: `docker-compose.dev.yml` con `name: oikos-dev`, volumen propio, puertos
    `!override` 3001/8001, `EMAIL_PROVIDER=console`, `restart: "no"` y `backup` detrás de
    `profiles: ["backup"]` (I1); `gen:types` contra `:8001` (I2); comandos de `CLAUDE.md`
    corregidos (seed solo en dev, `-p oikos-dev`).
  - `docker-compose.dev.yml` solo cambia `command`, `COOKIE_SECURE` y volúmenes del frontend:
    mismo volumen `pgdata`, mismos puertos 3000/8000, mismo proyecto `app-finanzas-fullstack`.
    Correr el comando dev de `CLAUDE.md` en la máquina de despliegue **reemplaza los
    contenedores de producción y escribe en la base real**. Probable origen del usuario
    semilla encontrado en producción (QA-002, ver Resueltos).
  - Fix: un override aislado (p. ej. `docker-compose.qa.yml` con `name: oikos-qa`, volumen
    Postgres propio, puertos 3001/8001/5433, `NEXT_PUBLIC_API_URL`/`ALLOWED_ORIGINS`/
    `FRONTEND_URL` ajustados) y corregir el comando dev de `CLAUDE.md`.

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

- [x] **Cambiar `preferred_currency` no invalida `dashboardSummary` ni `budgets-progress`
  (Fase 29, preexistente) — resuelto.** *(2026-09-26, Fase 30 F4, `docs/specs/fase_30_spec.md`)*
  - `useUserPreferences` invalida ahora las tres raíces del dashboard al cambiar la moneda:
    `dashboardSummary()` (todos los meses), `dashboard.categoryBreakdown()` (todos los
    meses/monedas), y `budgets.progress()` (todos los meses). Llamadas sin argumento matchean
    por prefijo. Analítica NO se invalida explícitamente (H2): su key ya lleva
    `effectiveCurrency` como segmento, y al cambiar la moneda preferida la key cambia y
    TanStack pide la nueva sola.

- [x] **El login redirige a `/dashboard`, que da 404 (encontrado en la verificación de la
  Fase 29, preexistente) — resuelto.** *(2026-09-26, Fase 30 F5, `docs/specs/fase_30_spec.md`)*
  - `app/(auth)/login/page.tsx` y `components/auth/GoogleAuthButton.tsx` ahora redirigen a
    `'/'` (el dashboard raíz) para usuarios con historial, y a `/capture` para nuevos.
    Fix de flujo corto: cambio de destino en ambos componentes.

- [x] **Hydration mismatch en el saludo del dashboard (preexistente, solo visible en dev)
  — resuelto.** *(2026-09-26, Fase 30 F6, `docs/specs/fase_30_spec.md`)*
  - Saludo dinámico con `useSyncExternalStore` (Fase 30 F6): SSR renderiza `"Hola"`; tras
    el montaje calcula la hora local y muestra `"Buenos días" / "Buenas tardes" /
    "Buenas noches"` con el primer nombre. Sin `useState` + `useEffect` (ni su
    `eslint-disable`) y sin warning de hydration en consola; React re-renderiza una vez al
    hidratar para pasar de "Hola" al saludo.

- [x] **Los KPIs de Analítica se suman en el navegador (encontrado en la Fase 29,
  preexistente) — resuelto.** *(2026-09-26, Fase 30 B1/F3, `docs/specs/fase_30_spec.md`)*
  - `GET /api/v1/dashboard/cashflow-series` ahora devuelve `CashflowSeries` con
    `total_income`, `total_expense`, `net` calculados en el backend (misma suma que los
    buckets). El frontend usa estos totales directamente; elimina el `useMemo` de `totals`.
    `AnalyticsSummary` recibe `net` por prop y ya no resta; `CategoryDonutChart` usa
    `total_income` del backend como denominador del modo `income-total`. Contrato de API
    roto a propósito (único consumidor es Analítica, no hay atajos ni scripts propios).

---

## 🟡 Integridad y escala

- [x] **Bugs de dinero/visualización de la QA 2026-09-26 (🟡) — resueltos todos.** *(2026-09-27, Fase 31, `docs/specs/fase_31_spec.md`)*
  QA-006 (B5), QA-007 (F7), QA-008 (B9/F8: balance = ingreso real − gasto real, "esperado"
  como referencia), QA-009 (F3: toggle "ver todas" en los dos modales; aceptar categorías de
  la otra naturaleza es intencional — reembolsos, ver `BUSINESS_RULES.md`), QA-011 (F10: 20 +
  "Ver todos"), QA-012 (F9: porcentaje real y segunda vuelta). Detalle y capturas en
  `.scratch/qa-2026-09-26/REPORTE_QA.md`.
  - **QA-006** — `GET /transactions` cuenta las borradas en `total`
    (`transactions.py:261`: `with_entities(func.count())` se salta el filtro global de
    soft-delete) → "Cargar más (12 de 17)" eterno, cada clic trae una página vacía.
  - **QA-007** — `formatters.ts` redondea todos los montos a la unidad, también USD/EUR: un
    gasto de 0,10 se ve "-US$ 0".
  - **QA-008** — "Te quedan" usa el ingreso *declarado* pero la tarjeta muestra "Ingresos del
    Mes" *real*: 3.200 − 106 ≠ 2.894 a simple vista.
  - **QA-009** — Editar un gasto a Ingreso muestra "Salario" en la UI pero envía el
    `category_id` de la categoría de gasto, y el backend lo acepta (no valida tipo de
    transacción vs naturaleza de la categoría). Tampoco impide cambiar la naturaleza de una
    categoría con movimientos.
  - **QA-011** — `/accounts/[id]` y `/categories/[id]` muestran solo 100 movimientos, sin
    paginación ni aviso.
  - **QA-012** — `BudgetRing` topa en "100% GASTADO" con 105,5% real (la notificación dice
    106%).
  - (QA-006 confirmado también en Postgres: con 9 borradas, `total` 110 vs 101 items reales.)

- [ ] **UX, estados de error y accesibilidad de la QA 2026-09-26 (🟡/🟢).** Resueltos en la
  Fase 31 (`docs/specs/fase_31_spec.md`, 2026-09-27): QA-010 (F6), QA-013 (F2), QA-019 (B6),
  QA-020 (B7) y QA-022 (B8), marcados `[x]` abajo. Siguen abiertos, por flujo corto: QA-014,
  QA-016, QA-017 y QA-018.
  - [x] *(2026-09-27, Fase 31)* **QA-010** — `/transactions` muestra un error de API como "Aún no tienes movimientos"
    (misma clase de bug que Fase 24 arregló en el dashboard); permite rango de fechas
    invertido sin aviso; durante reintentos los filtros desaparecen tras el skeleton.
  - [x] *(2026-09-27, Fase 31)* **QA-013** — Paso de ingreso del onboarding: negativo o vacío → "Continuar" no hace nada,
    sin mensaje (mismo patrón que Fase 12 §12.8 / Fase 24 §24.2).
  - [x] *(2026-10-03, flujo corto)* **QA-014** — `ModalShell` sin `role="dialog"` ni gestión/trampa de foco; los botones
    editar/borrar categoría no son alcanzables visualmente con foco en escritorio.
  - [x] *(2026-10-03, flujo corto)* **QA-016** — `seed.py` deja las cuentas descuadradas contra `opening_balance`
    (2.519.000 COP, 2.735 USD, −150.000 COP) y crea 76 transacciones, no las 45 que dice
    `CLAUDE.md`. Además, sobre una base recién migrada, el seed corrido *antes* del primer
    arranque de uvicorn crea solo 1 presupuesto y 9 transacciones: las categorías del sistema
    las siembra `main.py` al arrancar. Documentar el orden (arrancar backend, luego seed) o que
    el seed las cree si faltan.
    Resuelto: el seed fija `opening_balance` y aplica cada transacción con `ledger.registrar_impacto`
    (balance == opening + neto), llama a `ensure_default_categories` (extraída de `main.py` a
    `core/default_categories.py`) y README/AGENTS.md dicen 76 transacciones. Test en `tests/test_seed.py`.
  - [x] *(2026-09-27, Fase 31)* **QA-019** 🟢 — El techo de un mes cerrado en `backend/app/core/periods.py:80` es
    `23:59:59` sin fracción: una transacción a las `23:59:59.xxx` UTC del último día desaparece
    de `summary` (y por lectura de código de `budgets-progress` y las alertas), mientras
    Analítica —que usa `23:59:59.999Z` desde el frontend— sí la cuenta. Confirmado en Postgres
    (`/?month=2025-12`: "Ingresos $0" con un ingreso de 3.300 visible en la lista de la misma
    página). Fix: límite superior exclusivo (`< primer día del mes siguiente`).
  - [x] *(2026-09-27, Fase 31)* **QA-020** 🟢 — Misma `Idempotency-Key` con payloads *distintos* en carrera: la rama
    `except IntegrityError` de `crear_transaccion` (`transactions.py:~198-207`) devuelve la
    transacción existente sin comparar `request_hash`, así que algunas peticiones reciben `200`
    con una transacción ajena en vez de `409` (Decisión 10.4.3). Con payload idéntico funciona
    bien; el saldo no se descuadra.
  - [x] *(2026-09-27, Fase 31)* **QA-022** 🟢 — Riesgo latente, no aplica hoy: `cashflow-series` (buckets vía
    `to_char(timestamptz)`) y `summary` (límites naive) asumen que la sesión Postgres está en
    UTC. Con `timezone='America/Bogota'` en la base los buckets se corren un día y `summary`
    cambia de totales. La imagen `postgres:16-alpine` usa UTC por defecto; blindarlo es barato
    (`connect_args={"options": "-c timezone=UTC"}` en `database.py`).
  - [x] *(2026-10-03, flujo corto)* **QA-017** 🟢 — Hydration mismatch en `/settings` (solo dev). Causa: `useUserPreferences` leía `document.cookie` en el render para `enabled`, distinto en server y cliente.
  - [x] *(2026-10-03, flujo corto; (d) resuelto como "descripción opcional en todo", 2026-10-03)* **QA-018** 🟢 — "Entretenimiento" desborda su casilla en `/capture` a 390 px; Flujo de Caja
    vacío sin mensaje; ~7 s en blanco ante un 404 de recurso ajeno; descripción obligatoria
    solo en el modal (no en `/capture`); "Último uso: Nunca" desactualizado en API keys.

- [ ] **Deuda nueva consciente de la Fase 31 (2026-09-27).**
  - Resuelto en la Fase 32 (2026-10-02): el insumo de T10, marcado `[x]` abajo. Siguen abiertos
    H11, el modal de edición propio de `/accounts/[id]` y `/categories/[id]`, y el de
    `decimal_places`.
  - **H11** 🟢 — El filtro "hasta el día X" de `/transactions` convierte la fecha final a
    `T23:59:59` sin fracción, y Analítica manda `23:59:59.999Z`: un movimiento a las
    `23:59:59,5` UTC queda fuera del filtro. Misma familia que QA-019; candidato a flujo corto
    (límite exclusivo "< día siguiente").
  - 🟡 `/accounts/[id]` y `/categories/[id]` tienen su **propio** modal de edición en línea
    (no `EditTransactionModal`), con los mismos problemas que F2/F3 corrigieron en los modales
    compartidos: validación nativa sin error de campo y categoría visible ≠ enviada. Reusar
    `EditTransactionModal` ahí lo cierra.
  - [x] *(2026-10-02, Fase 32)* **Insumo de la Fase 32 (inventario de T10)** 🟢 — con `TEST_DATABASE_URL` la suite daba 1 falla previa, solo en Postgres: `test_soft_delete.py::TestUpdatedAt::test_updated_at_changes_on_put_but_not_on_read` — `now()` de Postgres es la hora de inicio de la transacción, y el fixture `db_session` envuelve todo el test en una sola transacción, así que `updated_at` no cambia tras el `PUT`. No era un bug de producción (cada request es su propia transacción). Resuelto en `docs/specs/fase_32_spec.md` B6: `TestUpdatedAt` pasó al seam de sesión real por request (el `INSERT` y los 4 `PUT` salen por transacciones propias) y quedó marcado `concurrencia`, así que hoy pasa en el default de Postgres — y no corre en el opt-in de SQLite, que es la consecuencia asumida (10 skips en vez de 9).
  - 🟢 Pydantic ignora ceros finales en `decimal_places` (`12.340` pasa en el backend), pero
    `lib/validateAmount.ts` cuenta los decimales escritos y lo rechaza en el cliente. Más
    estricto a propósito; anotado por si molesta.

- [x] **QA-023** 🔴 — `GET /budgets/?month=&year=` sin validar creaba presupuestos recurrentes basura (`month=13`, `year=99999`) y dejaba `GET /budgets/` en 500 permanente (`ResponseValidationError` por `BudgetResponse.month/year` con `ge/le`). **Resuelto (2026-10-03, flujo corto QA 2ª pasada):** `Query(ge/le)` en `api/budgets.py` (`month` 1–12, `year` 2020–2100); guarda en `ensure_recurring_budgets_for_period`; `BudgetResponse` desacoplado de `BudgetBase` (sin `ge/le`, sin patrón de moneda); estado de error + "Reintentar" en `budgets/page.tsx`. Limpieza SQL para dev/prod provista. Tests: `test_budgets.py` + `test_budget_recurrence.py`.

- [x] **QA-024** 🔴 — Borrar un presupuesto recurrente del mes en curso reaparecía al recargar (se re-clonaba desde la plantilla). **Resuelto (2026-10-03, flujo corto QA 2ª pasada):** "lápida" del soft-delete — `select()` Core en `ensure_recurring_budgets_for_period` cuenta filas borradas como "período saltado"; borrar = saltea ese mes, la recurrencia sigue en los siguientes. Copy del confirm actualizado. Tests unit + HTTP en `test_budget_recurrence.py` y `test_budgets.py`.

- [x] **QA-025** 🟠 — `limit`/`skip` negativos daban 500; `limit` sin tope. `currency` libre (`varchar(3)`) → 500 por `StringDataRightTruncation`. **Resuelto (2026-10-03, flujo corto QA 2ª pasada):** `Query(ge/le)` en `transactions.py` (`le=1000`), `accounts.py` (`le=200`), `notifications.py` (`le=1000`). Patrón `^[A-Z]{3}$` en schemas de request (`AccountBase`, `TransactionBase`, `BudgetBase`, `PreferencesUpdate`); response models redeclarados sin patrón (tolerancia a filas heredadas). Tests de 422 en todos los endpoints.

- [x] **QA-026** 🟡 — `PUT /transactions` borraba `description` si el cliente no la reenviaba (distinto de `payment_method` y `date`). **Resuelto (2026-10-03, flujo corto QA 2ª pasada):** `model_fields_set` (mismo idioma que `accounts.py` Fase 24): ausente conserva, `null` explícito limpia. Aplicado a `description` **y** `payment_method` (unificación); `date` queda `is not None` porque `TransactionResponse.date` es `datetime` no opcional. Web sin cambios de comportamiento.

- [x] **QA-027** 🟡 — `PUT /categories` permitía cambiar el `type` con transacciones/presupuestos asociados. **Resuelto (2026-10-03, flujo corto QA 2ª pasada):** bloqueo con `ConflictError` 409 (mismo ámbito que el delete). Reembolsos cruzados previos intactos. Tests en `test_categories.py`.

- [x] **QA-028** 🟡 — Nombres en blanco (`"   "` pasaba `min_length=1`) y duplicados. **Resuelto (2026-10-03, flujo corto QA 2ª pasada):** validador `strip` + no-vacío en `CategoryBase.name` y `AccountBase.name` (compartido en `schemas/common.py`). Unicidad por usuario y `type` entre activas, comparando normalizado (NFKD→ascii→strip→lower); pre-chequeo en API, sin restricción en DB. Tests en `test_categories.py`.

- [x] **QA-031** 🟢 — Guarda defensiva: `PUT /transactions` con cuenta anterior borrada haría `AttributeError` (hoy inalcanzable). **Resuelto (2026-10-03, flujo corto QA 2ª pasada):** eliminada query redundante de `cuenta_vieja`; se pasa `transaccion_db.account_id` (mismo efecto, `ledger` ya no-opera sobre soft-deleted). Test en `test_transactions.py`.

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

- [x] **Techo inconsistente en `GET /accounts/{id}/monthly-summary` (Fase 29, aceptado)
  — resuelto.** *(2026-09-26, Fase 30 B2, `docs/specs/fase_30_spec.md`)*
  - `api/accounts.py` ahora usa `core.periods.limites_mes_utc` (techo = "ahora" en mes en
    curso), igual que `dashboard/summary`. Una transacción con fecha futura del mismo mes ya
    no cuenta en la tarjeta de la cuenta, cuadre con la tarjeta del dashboard. Los tests
    (`TestMonthlySummaryCurrentMonthCeiling`) validan que la transacción de hoy sí cuenta.

- [ ] **`GET /budgets/?month=&year=` sigue generando presupuestos recurrentes en meses
  cerrados (Fase 29, aceptado).**
  - El guard de la Decisión B5 acota al mes actual la generación tanto en
    `dashboard/budgets-progress` como en el motor de alertas, pero este tercer caller quedó
    fuera a propósito: listar un mes pasado por la API crea las filas que la plantilla
    recurrente habría generado, igual que antes de la fase.
  - Ningún call site del frontend lo usa con período, así que no hay efecto en la app; queda
    anotado para que no se lea como un descuido cuando se toque `budgets.py`.
  - *(2026-10-03, flujo corto de recurrencia)* parcialmente mitigado: la plantilla ahora solo
    sale de períodos anteriores, así que pedir un mes anterior al inicio de la serie ya no
    genera filas hacia atrás. Sigue habiendo escritura al pedir meses posteriores.

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
- [ ] Paralelizar la suite del backend (`pytest-xdist`) — no instalado y bloqueado, no es falta de
  ganas: `ALTER DATABASE … SET timezone` de los dos tests de timezone es **a nivel de base** y no
  se aísla ni con esquemas por worker, el teardown del seam de sesiones reales hace `TRUNCATE` de
  tablas globales y hay una sola base compartida. Paralelizar obligaría a un contenedor o un
  `CREATE DATABASE` por worker, y ~2,5 min es tolerable para un gate manual. Decisión Q9 del
  `/grilling` de la Fase 32 (`docs/specs/fase_32_spec.md`).
- [ ] 🟢 Detector de fugas entre tests del seam real (Fase 32, review): es posicional —
  `test_soft_delete.py:94` es hoy el único conteo global que delata una fuga de filas—, así que
  un test nuevo que commitee datos sin pasar por `real_client`/`real_session` (cuyo teardown
  trunca) contaminaría a los demás sin que nada lo avise. Un fixture `autouse` que verifique las
  tablas vacías tras cada test `concurrencia` lo haría explícito. Sin urgencia: hoy no hay fuga.
- [ ] Sincronización offline (las columnas `updated_at` de la Fase 8 la dejan preparada).

---

## Resueltos

| Fecha | Item |
|-------|------|
| 2026-09-26 | Usuario semilla `test@test.com` / `testpass123` presente en la base de **producción** (id 18, creado 2026-09-25, 3 cuentas / 75 transacciones / 6 presupuestos) — alcanzable desde internet vía Funnel con contraseña pública en `CLAUDE.md` (QA 2026-09-26, QA-002). Borrado con `delete_user_by_email`; en producción quedan solo los ids 15 y 17. Causa probable: QA-001 (el comando dev apunta a la base real) — sigue abierto en 🟠 |
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

- [x] **Apagar la recurrencia de un presupuesto** *(2026-10-03, flujo corto)* — desmarcar
  "Repetir cada mes" corta la serie (categoría + moneda) hacia adelante; spec en
  `docs/specs/corto_recurrencia_presupuestos_spec.md`. Verificado a mano con Playwright contra
  `oikos-dev` el 2026-10-03.
