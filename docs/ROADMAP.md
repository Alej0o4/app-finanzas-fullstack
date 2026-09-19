# Roadmap — Oikos

> Visión de producto y qué sigue. Para el historial de fases ya completadas (Fase 0 a Fase 26),
> ver `docs/CHANGELOG.md` — cada fase tiene ahí un resumen de 3-5 líneas y un pointer a su spec
> en `docs/specs/fase_NN_spec.md`.
>
> Formato: `[ ]` pendiente · `[x]` resuelto (con fecha).

---

## Cambio de enfoque — 2026-09-19: vuelta a uso personal

Oikos deja de perseguir el objetivo de "producto que cualquier persona pueda usar" del
2026-08-22. No hay plan de publicarlo, comercializarlo ni abrirlo a usuarios externos en el
futuro cercano — vuelve a ser una herramienta personal para su único dueño/desarrollador.

**Qué NO cambia:** el listón de calidad de código. Alembic, tests automatizados, versionado de
API y la capa de arquitectura (`app/services/`, `app/schemas/`, `app/core/exceptions.py`)
siguen en scope — no porque haya un modelo de amenaza multi-usuario, sino porque hacen que sea
más fácil seguir agregando features sin que el código se pudra. Mantenibilidad, escalabilidad
(del código, no de infraestructura) y modularidad siguen siendo objetivos explícitos.

**Qué SÍ cambia:** dejar de invertir esfuerzo en seguridad, autenticación y resistencia a abuso
más allá de lo que ya existe. El baseline llegado a la Fase 26 (cookies `httpOnly` + CSRF,
verificación de email, rate limiting básico, la corrección del account-takeover de Google OAuth
en Fase 23) se considera suficiente para un solo usuario de confianza. No proponer trabajo nuevo
de seguridad/auth salvo que algo esté roto de verdad (ej. el login de Google caído en
producción, ver `docs/TODO.md`) o el usuario lo pida explícitamente. El esfuerzo por defecto va
a features que mejoren el trackeo y análisis de gastos — ver "Backlog priorizado" abajo,
reordenado en base a este criterio.

Consecuencia directa sobre la auditoría del 2026-09-15 (`CODE_REVIEW.md`, ver memoria del
agente): su score de Seguridad (5/10) y varios de sus hallazgos de alta prioridad estaban
calibrados para un modelo de amenaza multi-usuario que ya no aplica. La mayoría de esos
hallazgos igual se resolvieron (Fases 23-26, antes de este pivote) por buenas razones
independientes del paradigma — pero los que seguían abiertos como "producto" (TTL/scopes de API
keys, rate limiting distribuido) pasan de "pendiente" a "fuera de scope" con este cambio, ver
abajo.

---

## Cambio de enfoque — 2026-08-22 (histórico, ver arriba)

Oikos deja de ser una app personal de un solo usuario para convertirse en un producto que
cualquier persona pueda usar. Esto invalida tres decisiones que estaban documentadas como "fuera
de scope": **Alembic, testing y versionado de API**. Las tres volvieron a scope en la Fase 7 (ver
`docs/CHANGELOG.md`).

El MVP se redefinió alrededor de **cinco componentes funcionales** — todos implementados, ver
"El MVP en cinco componentes" abajo y Fases 8–15 en el changelog.

### El cambio conceptual más importante

El producto actual es de **stock**: las cuentas guardan un saldo y el dashboard responde
*"¿cuánto tengo?"*. El nuevo MVP es de **flujo**: el dashboard responde
*"¿cuánto gasté este mes y cuánto me queda?"*.

Ambos conviven, pero el **dato principal del dashboard pasa a ser el flujo mensual**
(`ingreso mensual − gastos del mes`). Los saldos de cuentas siguen visibles, en vista
secundaria.

### Decisiones tomadas (2026-08-22)

| Decisión | Resolución | Consecuencia |
|---|---|---|
| ¿Cuentas visibles en v1? | **Sí, visibles** | `Account.balance` sigue siendo dato de cara al usuario → su fiabilidad **sigue en scope** (idempotencia + reconciliación). Multi-moneda sigue alcanzable → los bugs de moneda debían corregirse (Fase 11). |
| ¿Balance del dashboard? | **Flujo mensual**, con vista secundaria de saldos | Tarjeta principal reemplazada; se agregó `User.monthly_income`. |
| ¿Autenticación? | **Solo email** al inicio | Google OAuth se sumó después (Fase 20). Recuperación de contraseña fue bloqueante desde el día 1 (Fase 7). |
| ¿Canal de notificaciones? | **Push web** | PWA instalable + service worker + VAPID (Fase 13). |

---

## El MVP en cinco componentes

Los cinco están implementados — ver Fases 8–15 en `docs/CHANGELOG.md` para el detalle de cada uno.

1. **Captura de transacción en 3 toques** — pantalla principal, no modal. (Fase 10)
2. **Categorías default curadas**, luego ampliadas y personalizables. (Fases 8, 18)
3. **Dashboard mensual simple** — gastado / ingresado / balance + barras por categoría. (Fase 11)
4. **Presupuestos por categoría con alertas** — avisos al 80% y 100%. (Fase 13)
5. **Resumen semanal automático** — push cada lunes, cero esfuerzo del usuario. (Fase 14)

Más el **onboarding de 3 minutos** que lleva al usuario a su primer gráfico (Fase 15).

---

## Fase 26 — completada (2026-09-19): JWT en cookies httpOnly

Retomó el diseño de Fase 25 (§25.5, decisiones J1–J8): `login`/`login_google`/`refresh` setean
`access_token`/`refresh_token`/`csrf_token` como cookies `httpOnly` (más CSRF double-submit)
además del body de siempre; `get_current_user` acepta el cookie como fallback detrás del
header; el camino de API keys (`Authorization: Bearer oikos_pat_...`, Atajos de iOS) queda
intacto. Producción se consolidó en el dominio HTTPS del Tailscale Funnel como único origen
soportado para login por cookie (`COOKIE_SECURE=true` por default) — el acceso por IP directa
de Tailscale queda deprecado para sesión de navegador, no para API keys. Dos correcciones
encontradas en la revisión final antes de mergear (Path del cookie de refresh demasiado
angosto para que el logout revocara server-side; deadlock en el interceptor de refresh del
frontend si el refresh mismo devolvía 401) — ver `docs/CHANGELOG.md` para el detalle completo.
Spec: `docs/specs/fase_26_spec.md`.

No hay una próxima fase planeada todavía — ver "Backlog priorizado" abajo para las candidatas.

---

## Fases 27–28 — completadas (2026-09-19): cierre de deuda de documentación/arquitectura/modularidad

Antes de retomar el backlog de features, se cerraron los últimos ítems de deuda de modularidad
que la auditoría 2026-09-19 (`CODE_REVIEW.md`) todavía marcaba como abiertos — a pedido explícito
del dueño del producto, revirtiendo la propia recomendación de la auditoría de tratarlos como
trabajo oportunista sin fase dedicada.

- **Fase 27** — `frontend/app/(dashboard)/transactions/page.tsx` (646 líneas, sobre el umbral de
  alerta) descompuesto en `TransactionFilters`/`TransactionList`/`EditTransactionModal`; la página
  queda en 313 líneas como orquestador. Refactor puro, sin cambio de comportamiento. Spec:
  `docs/specs/fase_27_spec.md`.
- **Fase 28** — `app/core/exceptions.py` deja de ser un piloto de `transactions.py` (Fase 25) y
  cubre los 65 `raise HTTPException` que quedaban en los 10 routers restantes, con una taxonomía
  genérica por status code (400–422, más 500/503 agregados durante la implementación). Cero
  cambio de contrato de API. Spec: `docs/specs/fase_28_spec.md`.

Con esto, la deuda de modularidad de `docs/TODO.md` 🟢 queda cerrada salvo la nomenclatura mixta
español/inglés (documentada como irrelevante en solitario) y la migración oportunista de call
sites a tipos generados desde OpenAPI (sin fecha, convivencia deliberada desde Fase 16 §16.3). La
próxima fase (29) retoma el backlog priorizado abajo.

---

## Pendientes abiertos

- [ ] **Login con Google caído en producción** (`disabled_client`) — sigue siendo prioritario
      porque afecta directamente el uso diario del dueño del producto, no porque sea
      "seguridad". Ver `docs/TODO.md` 🟠 para el estado de la apelación y el workaround activo.
- [ ] **Acceder y verificar el flujo completo desde celular vía Tailscale** (heredado de Fase 4A)
      — sigue siendo el canal de acceso diario real.
- [ ] **Seed automático tras el primer startup en Docker** (heredado de Fase 4B) — conveniencia
      personal, no bloqueante.
- [ ] **Script `scripts/deploy.sh`** (git pull → `docker compose up --build -d`) (heredado de
      Fase 4B) — conveniencia personal.
- [ ] **Generar credenciales reales de Google Cloud Console** para el despliegue
      (`GOOGLE_CLIENT_ID` / `NEXT_PUBLIC_GOOGLE_CLIENT_ID`) — el plumbing de Docker ya las
      propaga (Fase 20); depende de que se resuelva primero el `disabled_client` de arriba.
- [ ] **Evaluar reemplazar Lucide** por otra librería de íconos (Fase 12) — cambio de ~20
      archivos para un beneficio principalmente estético, sin prioridad.

Items que dejan de estar en esta lista tras el pivote del 2026-09-19 (rate limiting distribuido,
TTL/scopes de API keys como decisión de producto) pasaron a "Fuera de scope" abajo — ya no son
"pendientes", son decisiones cerradas mientras el proyecto sea de un solo usuario.

Ver también `docs/TODO.md` para deuda técnica y bugs confirmados no ligados a una fase específica.

---

## Backlog priorizado — reordenado 2026-09-19 para uso personal

Con las Fases 27–28 cerradas (arriba), este backlog retoma la numeración desde **Fase 29**: el
primer candidato de la tabla de abajo (filtros de fecha/categoría) es el siguiente a especificar.

Criterio de prioridad: ¿esto hace que trackear y entender mis propios gastos sea más fácil o más
claro? Ya no hay criterio de "adquisición", "retención de usuarios" ni "efecto wow" de
marketing — se reformulan abajo en términos de valor de uso personal directo.

| Prioridad | Feature | Nota |
|---|---|---|
| Alta | **Filtros de fecha y categoría en dashboard** | Subida de prioridad (antes "Media, cuando haya datos de uso reales" — ya hay ~2 meses de datos reales). Es la feature de *análisis* más directa: sin poder recortar por rango/categoría, "análisis de gastos" se queda en el resumen mensual fijo. |
| Alta | **Automatización de ingresos/gastos recurrentes** | El scheduler ya existe desde Fase 14. Reduce fricción de captura, que es tiempo que se puede invertir en mirar los datos en vez de cargarlos. |
| Alta | **Sinking funds** (gastos distribuidos en cuotas mensuales virtuales) | Validado por YNAB para presupuesto personal serio. Encaja directo con "cuánto me queda" del dashboard de flujo. |
| Media | **Vistas de tendencia / comparación entre meses** (nueva candidata) | No estaba en el backlog anterior porque el enfoque previo priorizaba features de producto sobre profundidad analítica. Encaja con el objetivo explícito de "que me facilite el análisis de mi dinero" — a definir alcance en una próxima sesión de spec. |
| Media | **Registro por nota de voz con IA** | Reencuadrada como conveniencia de captura personal, no "efecto wow" de marketing. Depende de la captura por nombre (Fase 16, ya lista). |
| Baja | **Multi-moneda ampliado** (tasas de cambio) | El modelo ya soporta agrupación por moneda; la conversión no está y no se necesita todavía. |
| Baja | **Sincronización offline** | Las columnas `updated_at` de Fase 8 la dejan preparada. |

`App nativa iOS/Android` se retira del backlog — ver "Fuera de scope" abajo, ya no tiene
justificación de distribución a otros usuarios.

---

## Fuera de scope (no hacer)

- ~~**Tracking de inversiones con vinculación de brokers**~~ — Es un producto distinto. Diluye la propuesta de valor. Como mucho, un campo manual de "patrimonio neto" en el futuro.
- ~~**Tarjetas de crédito avanzadas** (puntos, millas, intereses de mora, cuotas)~~ — Cada banco calcula distinto y las reglas cambian constantemente. Pesadilla operativa sin equipo dedicado.
- ~~**Temas visuales dinámicos**~~ — El modo claro/oscuro actual es suficiente. Ya implementado.
- ~~**Multi-idioma / i18n**~~ — Lanzamiento en español. Ya no aplica: sin plan de usuarios fuera de LATAM ni de usuarios externos en absoluto.
- ~~**CI/CD**~~ — Sin equipo ni usuarios externos que protejan de una regresión ajena; `run-tests` manual sigue siendo suficiente.
- ~~**Apple Sign-In**~~ — Evaluado en Fase 20 y descartado: Developer Program pago (99 USD/año) y complejidad desproporcionada para un proyecto web-only.
- ~~**Rol admin en la API**~~ — Evaluado en Fase 21 y descartado: el proyecto no tiene ningún concepto de roles hoy (authz es siempre "¿sos el dueño del recurso?") y agregarlo solo para operaciones de mantenimiento es desproporcionado. Se usa un script de management en su lugar.
- ~~**Rate limiting distribuido**~~ *(2026-09-19, antes "diferido")* — `slowapi` en memoria alcanza mientras el backend siga en un worker único, y con el pivote a uso personal no hay razón para escalar a múltiples réplicas. Diseño (Redis + `storage_uri`) queda documentado en `docs/specs/fase_07_spec.md` §2.6.1 por si algún día cambia el contexto, pero no es trabajo planeado.
- ~~**TTL obligatorio y scopes en API keys**~~ *(2026-09-19, antes "pendiente de decisión de producto")* — eran decisiones de "producto" pensadas para múltiples usuarios con distintos niveles de confianza. Con un solo dueño de todas las keys, el riesgo que mitigarían no aplica.
- ~~**App nativa iOS/Android**~~ *(2026-09-19, movida desde el backlog)* — la única justificación real (widgets, push nativas, Face ID) era secundaria incluso bajo el enfoque de producto; sin necesidad de distribución a otros usuarios, no justifica el esfuerzo frente a la PWA ya existente (Fase 13).
- ~~**Endurecimiento de seguridad adicional más allá de la Fase 26**~~ *(2026-09-19)* — el baseline actual (cookies httpOnly + CSRF, verificación de email, rate limiting básico, fix del account-takeover de Google OAuth) se considera suficiente para un solo usuario de confianza. No se audita ni se invierte tiempo de desarrollo en esto salvo que algo esté roto de verdad.
