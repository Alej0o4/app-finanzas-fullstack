# Spec — Fase 13: Presupuestos con alertas + infraestructura de notificaciones

> Plan de implementación detallado para los 5 ítems de Fase 13 del [ROADMAP](../ROADMAP.md).
> Fuente de verdad de alcance: `docs/ROADMAP.md` (sección "Fase 13 — Presupuestos con alertas +
> infraestructura de notificaciones"). Este documento no cambia el alcance ahí definido — lo
> desglosa en tareas ejecutables, con archivos concretos, esquemas de datos, decisiones de diseño
> numeradas y una estimación de horas revisada contra el código real.
>
> **No implementa nada.** Es el hand-off para quien vaya a codear (backend-engineer /
> frontend-engineer). Ningún archivo del repositorio fuera de `docs/specs/fase_13_spec.md` fue
> modificado al producir este documento.

Estado del repo en el momento de escribir esto (2026-09-05): Fases 7–12 están completas e
implementadas (Fase 12, pulido visual, verificada en este documento: `frontend/app/not-found.tsx`
existe y `tabular-nums` aparece en `SummaryCard.tsx`, entre otros). Fase 13 es la primera fase del MVP que
toca infraestructura nueva de verdad (push web, PWA) en vez de reorganizar lo ya construido — el
patrón "esto ya existe, solo hay que conectarlo" que dominó Fases 11/12 no aplica aquí: se confirmó
por exploración que **nada** de lo que pide esta fase existe today (ver hallazgos 1–4).

---

## Hallazgos de exploración que corrigen/precisan el ROADMAP

1. **No existe ningún artefacto de PWA hoy — confirmado, no asumido.** `find frontend -iname
   "*manifest*" -o -iname "*sw.js*" -o -iname "*service-worker*"` no devuelve nada;
   `frontend/package.json` no tiene `next-pwa`, `workbox-*` ni ningún paquete relacionado
   (`dependencies`/`devDependencies` completas: `@tanstack/react-query`, `axios`, `lucide-react`,
   `next`, `react`, `react-dom`, `recharts`, `sonner`, `zustand` + tooling); `frontend/app/
   layout.tsx:1-31` no declara `manifest` en `metadata` ni ningún `<link rel="manifest">`. La
   advertencia del ROADMAP sobre "prototiparlo temprano" no es retórica: literalmente no hay nada
   de qué partir.

2. **No existe ninguna tabla, modelo ni columna relacionada con push, suscripciones o avisos
   in-app.** `backend/app/models/models.py` tiene 9 modelos (`User`, `Account`, `Category`,
   `Transaction`, `Budget`, `RefreshToken`, `PasswordResetToken`, `EmailVerificationToken`,
   `IdempotencyKey`) — ninguno relacionado con notificaciones. `backend/requirements.txt` no
   incluye `pywebpush` ni ningún cliente VAPID/push. Confirma que el ítem 2 del ROADMAP parte de
   cero, sin ninguna pieza reutilizable.

3. **El motor de evaluación de presupuestos no tiene ningún punto de enganche existente — ni
   síncrono ni asíncrono.** `backend/app/api/transactions.py:23-141` (`crear_transaccion`) y
   `:225-321` (`actualizar_transaccion`) hacen todo el trabajo contable (mover saldo, idempotencia)
   dentro del mismo commit, pero no llaman a ningún hook de "evaluar presupuestos" tras guardar —
   grep de `budget` en `transactions.py` no devuelve nada. `budgets-progress`
   (`backend/app/api/dashboard.py:127-176`) calcula el progreso **on-demand**, cada vez que el
   dashboard lo pide, pero es puramente de lectura: no persiste "ya se avisó" en ningún lado. No
   hay ni scheduler (`APScheduler`, cron) ni cola de trabajo en el proyecto (confirmado por
   `requirements.txt` — Fase 14 es la que introduce scheduler, ver ROADMAP). El ROADMAP no
   especifica si el motor corre síncrono o por job — este documento lo resuelve (Decisión 13.3.1).

4. **`BudgetRing` (`frontend/components/charts/BudgetRing.tsx`) ya tiene coloreado por umbral, pero
   con cortes distintos a los 80%/100% que pide el ROADMAP.** Líneas 41-42: `isDanger =
   percentage >= 90`, `isWarning = percentage >= 75 && percentage < 90` — usa 75/90, no 80/100. El
   ROADMAP dice "adaptar al lenguaje visual del MVP" asumiendo que el indicador visual y el motor
   de alertas deben usar el mismo umbral (80/100) para que "el aro se puso rojo" y "llegó la
   notificación" sean la misma señal — hoy no lo son: un presupuesto al 92% ya se ve "en rojo" en
   el aro (`isDanger` en 90) pero el motor de este documento (Decisión 13.3.2) todavía no habría
   emitido el aviso de 100%. Se corrige a 80/100 en el propio ítem (§13.4), no como side-effect.

5. **`Budget.currency` puede ser distinto a `preferred_currency` del usuario, y el motor de
   alertas debe respetar eso — mismo defecto de fondo que Fase 11 §11.1 corrigió para la lectura,
   ahora aplica a la escritura.** `backend/app/models/models.py` (`Budget.currency`,
   default `"COP"` pero editable por presupuesto) y `dashboard.py:158-176`
   (`obtener_progreso_presupuestos`) ya agrupan `spent` por `(category_id, currency)` exactamente
   como corrigió Fase 11 — el motor de evaluación de este documento debe reutilizar esa misma
   agregación (no recalcular gasto de otra forma), evitando reintroducir el bug de mezclar monedas
   que ya se corrigió una vez (ver Decisión 13.3.2).

6. **Los presupuestos recurrentes (Fase 8 §3, `app/core/budget_recurrence.py`) generan la fila del
   período de forma perezosa — la primera vez que alguien pide `budgets-progress` o
   `GET /budgets?month=X&year=Y` en un mes nuevo.** Esto importa para el motor de alertas: si el
   motor corriera por job periódico sin pasar por `ensure_recurring_budgets_for_period` primero,
   evaluaría contra una tabla de presupuestos incompleta para usuarios que no visitaron el
   dashboard todavía ese mes. Ver Decisión 13.3.3.

7. **No hay rate limiting en ningún endpoint de `budgets.py` ni `dashboard.py` hoy** (confirmado,
   `grep -n "limiter" backend/app/api/budgets.py backend/app/api/dashboard.py` no devuelve nada) —
   coherente con el criterio ya establecido en el proyecto (`docs/ROADMAP.md` Fase 7: solo
   registro/login/password-reset están limitados, por ser los vectores de abuso obvios sin
   autenticación previa). Los endpoints nuevos de esta fase (`POST /push/subscribe`,
   `GET/PATCH /notifications`) son todos autenticados — no hay razón para desviarse de ese
   criterio y agregarles `slowapi` (ver §13.2/§13.5, "Seguridad").

8. **`User` no tiene ninguna columna de preferencia de notificaciones.** `PreferencesUpdate`
   (`backend/app/schemas/schemas.py:97-100`) solo cubre `preferred_currency/locale/theme`. El
   ROADMAP de Fase 13 no pide un toggle de usuario (a diferencia de Fase 14, que sí lo pide
   explícitamente: "Preferencia de usuario para activar/desactivar el resumen") — se documenta
   como fuera de alcance a propósito (Decisión 13.2.3): las alertas de presupuesto no tienen opt-out
   en esta fase, y agregar uno no pedido inflaría el alcance sin necesidad.

9. **El AGENTS/CLAUDE.md ya fija una regla directamente relevante para el motor de evaluación:**
   *"Backend is the source of truth for all financial calculations... The frontend must never
   recompute these."* El porcentaje de progreso, el umbral cruzado y la decisión de "ya se avisó"
   deben vivir enteramente en el backend — el frontend solo consume el resultado (progreso +
   avisos ya generados), igual que ya hace con `budgets-progress`.

---

## Orden de dependencia real (no el orden del ROADMAP)

El ROADMAP lista los 5 ítems en un orden que no es el de ejecución: el motor de presupuestos y su
indicador visual **no dependen de push ni de PWA** (pueden evaluar y mostrar "80% gastado" sin que
exista ningún canal de envío), pero **sí necesitan un destino a donde escribir el aviso** antes de
poder "avisar" de verdad. Ese destino mínimo es la bandeja in-app — no el push. Dependencia real:

```
1. Bandeja de avisos in-app (§13.5)         — tabla `notifications` + endpoints CRUD de lectura.
   Es la única pieza de la que las demás dependen: sin una tabla donde insertar un aviso, el motor
   de presupuestos (2) no tiene nada que escribir, y sin nada que escribir, push (3/4) no tiene
   nada que enviar.

2. Motor de evaluación de presupuestos (§13.3) — depende de (1) para persistir el aviso.
   Independiente de PWA/push: en este punto ya es una fase completa y demostrable (un usuario ve
   el aviso al abrir la app, sin necesitar push).

3. Indicador visual de BudgetRing (§13.4) — depende únicamente del cálculo de progreso que
   `budgets-progress` YA expone hoy (hallazgo 3/5). Es 100% independiente de (1) y (2); se puede
   hacer en paralelo desde el día 1, no al final como sugiere el orden del ROADMAP.

4. PWA instalable (§13.1) — prerrequisito técnico de push (5), sin relación de dependencia con
   1/2/3. Puede empezar en paralelo desde el día 1.

5. Infraestructura de push web (§13.2) — depende de (4) (necesita el service worker para recibir
   el evento `push`) y de (1) (el envío push, cuando el suscriptor no tiene la PWA instalada o
   revocó el permiso, debe seguir dejando el aviso en la bandeja — el push es un canal adicional
   sobre el mismo aviso, no un canal alternativo con su propio dato).
```

Orden de implementación recomendado: **13.5 → 13.3 (con 13.4 en paralelo) → 13.1 → 13.2**. Esto
invierte el orden del ROADMAP (que lista PWA primero) a propósito: PWA+push es la pieza de mayor
incertidumbre técnica (Safari/iOS, permisos del navegador) y la advertencia del propio ROADMAP dice
que puede fallar silenciosamente para una fracción de usuarios — enviar primero lo que **sí**
garantiza que todo usuario reciba el aviso (la bandeja in-app) reduce el riesgo de que, si push se
atrasa o no llega a funcionar en el tiempo estimado, la fase completa quede sin ningún resultado
entregable.

---

## 13.5 Bandeja de avisos in-app (implementar primero — ver "Orden de dependencia real")

### Backend

**Decisión 13.5.1 — tabla nueva `notifications`, no una vista derivada de `budgets-progress`.**
Un aviso debe persistir su propio estado de lectura (`read_at`) independientemente de que el
presupuesto subyacente cambie de porcentaje después — si se derivara en cada request de
`budgets-progress`, "marcar como leído" no tendría dónde guardarse. Modelo nuevo en
`backend/app/models/models.py`, mismo criterio que `IdempotencyKey` (bitácora técnica, sin
`SoftDeleteMixin` — se borra de verdad si algún día hace falta un job de limpieza, no se oculta):

```python
class Notification(Base):
    """Aviso persistido para la bandeja in-app (Fase 13 §13.5).

    Fuente única de avisos: tanto el motor de presupuestos (§13.3) como, en el futuro,
    el resumen semanal de Fase 14, insertan aquí. El envío push (§13.2) es un canal
    adicional sobre la misma fila, no una tabla paralela — evita que un aviso "exista"
    en push pero no en la bandeja, o viceversa.
    """

    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String(30), nullable=False)  # "budget_threshold_80" | "budget_threshold_100" (Fase 14 agrega "weekly_summary")
    title = Column(String(200), nullable=False)
    body = Column(String(500), nullable=False)
    # Referencia opcional a la entidad que originó el aviso, para que el frontend pueda
    # enlazar "Ver presupuesto" — nullable porque Fase 14 (resumen semanal) no apunta a
    # un presupuesto puntual.
    budget_id = Column(Integer, ForeignKey("budgets.id"), nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", backref="notifications")
    budget = relationship("Budget")

    __table_args__ = (Index("ix_notifications_user_id_created_at", "user_id", "created_at"),)
```

**Decisión 13.5.2 — `type` como `String(30)` libre, no un `Enum` de Postgres.** Un `Enum` de DB
obliga a una migración de esquema cada vez que Fase 14 agregue `"weekly_summary"` — el proyecto ya
evita esto en otros lados (`Transaction.payment_method` es `String(20)` validado solo en
Pydantic, `backend/app/models/models.py`, comentario "valida el enum en schemas"). Mismo patrón
aquí: el `Enum` vive en `schemas.py`, no en la columna.

**Nuevo router** `backend/app/api/notifications.py`, montado en `main.py` bajo
`/api/v1/notifications`:

- `GET /` — lista las notificaciones del usuario actual, más recientes primero, con paginación
  simple (`skip`/`limit`, mismo patrón que `transactions.py`). Incluye `unread_count` en un
  endpoint separado (ver abajo) en vez de en cada página, para que el badge del ícono de campana
  no dispare una query de lista completa.
- `GET /unread-count` — `{"count": N}`. Es la query que el frontend hace con `refetchInterval`
  corto (ver Decisión 13.5.4) para el badge — debe ser barata (`COUNT(*) WHERE user_id=? AND
  read_at IS NULL`, ya cubierta por el índice compuesto de arriba).
- `PATCH /{notification_id}/read` — marca una notificación como leída (`read_at = now()`);
  ownership check `notification.user_id == current_user.id` → 404 si no coincide (mismo patrón que
  `budgets.py`/`transactions.py`, nunca 403 que confirme existencia ajena).
- `PATCH /read-all` — marca todas las no leídas del usuario como leídas (acción "marcar todo como
  leído" de la bandeja).

Schemas nuevos en `schemas.py`:

```python
class NotificationType(str, Enum):
    budget_threshold_80 = "budget_threshold_80"
    budget_threshold_100 = "budget_threshold_100"


class NotificationResponse(BaseModel):
    id: int
    type: str
    title: str
    body: str
    budget_id: int | None = None
    read_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class UnreadCountResponse(BaseModel):
    count: int
```

**Migración Alembic:** `alembic revision --autogenerate -m "fase_13_tabla_notifications"` — una
tabla nueva, sin tocar ninguna existente. Revisar a mano que el índice compuesto se genere
correctamente (mismo criterio que Fase 8/10: nunca commitear el autogenerate sin revisión, ver
`CLAUDE.md`).

### Frontend

**Decisión 13.5.3 — ícono de campana en el shell del dashboard (`Sidebar.tsx`), no una página
nueva de primer nivel en el menú.** Los avisos son transitorios y de consulta rápida — no
justifican un ítem de navegación permanente compitiendo con Dashboard/Transacciones/Presupuestos
(el ROADMAP ya reorganizó el sidebar por prioridad en Fase 11 §11.7; agregar un séptimo ítem
permanente iría en contra de ese trabajo). Un botón de campana en el bloque superior del sidebar
(junto al toggle de tema, mismo nivel jerárquico) abre un popover con la lista — mismo patrón ya
usado por `ChartControlsPopover.tsx`, reutilizable como referencia de estructura (no de contenido).

**Decisión 13.5.4 — `useQuery` con `refetchInterval: 60_000` para `unread-count`, no WebSocket
ni Server-Sent Events.** El proyecto no tiene infraestructura de tiempo real en ningún otro punto
(todo es request/response vía Axios) y el caso de uso — "hay avisos nuevos, contalos" — tolera un
minuto de latencia sin degradar la experiencia. Introducir WebSockets para esto sería
infraestructura desproporcionada para el volumen actual (mismo criterio que el ROADMAP ya aplica al
rate limiting distribuido y a CI/CD: no construir para una escala que el proyecto no tiene).

**Archivos a crear:**
- `frontend/hooks/useNotifications.ts` — `useQuery(['notifications'], ...)`,
  `useQuery(['notifications-unread-count'], { refetchInterval: 60_000 })`, mutaciones
  `useMarkAsRead`/`useMarkAllAsRead` que invalidan ambas keys.
- `frontend/components/NotificationBell.tsx` — ícono + badge numérico + popover con la lista
  (`NotificationResponse[]`), cada fila con `title`/`body`/tiempo relativo y, si `budget_id` no es
  `null`, un link a `/budgets`.

**Archivos a modificar:**
- `frontend/components/Sidebar.tsx` — montar `<NotificationBell />` junto al `ThemeToggle`.
- `frontend/docs/STATE_AND_FETCHING.md` — agregar `notifications`, `notifications-unread-count` a
  la lista de query keys globales.

**Seguridad/cross-cutting:** todos los endpoints nuevos requieren `get_current_user` (igual que el
resto de la API); sin rate limiting (hallazgo 7 — autenticados, sin vector de abuso nuevo).
`backend/docs/API_REFERENCE.md` y `frontend/docs/API_CONTRACT.md` deben documentar los 4 endpoints
nuevos **cuando se implemente**, no en este documento.

**Estimación:** 1d (ROADMAP no lo dimensiona por separado — está embebido como "1d" en el propio
ítem "Bandeja de avisos in-app" del ROADMAP; ver tabla de estimación al final).

---

## 13.3 Motor de evaluación de presupuestos

### Backend

**Decisión 13.3.1 — evaluación síncrona, dentro del mismo commit de `crear_transaccion`/
`actualizar_transaccion`, no un job periódico.** El ROADMAP pide explícitamente que el aviso
llegue "al 80% y 100%" — un job periódico (cada hora, por ejemplo) introduciría un retraso entre
"el usuario gastó lo suficiente para cruzar el umbral" y "se enteró", sin ningún beneficio a cambio
(el volumen de transacciones por usuario es bajo; evaluar en el momento de guardar no es costoso:
ya se calcula `spent` agregado en el mismo query pattern que `budgets-progress`). Correr por job
periódico además requeriría el scheduler que **Fase 14 introduce explícitamente como su primer
ítem** ("Hoy no existe scheduler ni servicio de envío") — construirlo aquí adelantaría trabajo de
Fase 14 sin que el ROADMAP lo pida, y de tener que hacerlo, debería ser al revés: Fase 14 reutiliza
el scheduler para su propio caso de uso (cálculo semanal), no Fase 13 lo adelanta para el suyo. La
función de evaluación se ejecuta como último paso del `try` en ambos endpoints, después del
`db.commit()` contable — un fallo en la evaluación de presupuestos no debe revertir ni bloquear el
registro de la transacción (ver Decisión 13.3.4).

**Decisión 13.3.2 — la idempotencia ("un aviso por umbral por periodo") vive en la tabla
`notifications` misma, vía un `UNIQUE` parcial, no en una columna nueva de `Budget`.** Agregar
`Budget.alert_80_sent`/`alert_100_sent` acoplaría el estado de notificación al ciclo de vida del
presupuesto (¿qué pasa si el presupuesto es recurrente y genera una fila nueva cada mes, como ya
hace `ensure_recurring_budgets_for_period`? Cada fila mensual nueva empezaría en `False`
correctamente, así que en principio funcionaría — pero mezclaría una responsabilidad de dominio
("cuánto puedo gastar") con una de mensajería ("ya te avisé") en la misma tabla, y cualquier fix
futuro a `Budget` correría el riesgo de tocar sin querer el estado de alertas). Se prefiere
consultar la propia tabla `notifications`: antes de insertar un aviso de umbral, se verifica si ya
existe uno para `(user_id, budget_id, type)` en el período — como `budget_id` ya identifica un
período específico (una fila de `Budget` es un mes concreto, recurrente o no, ver
`budgets.py`/`budget_recurrence.py`), la unicidad natural es `(budget_id, type)`:

```python
Index(
    "uq_notifications_budget_type_active",
    "budget_id", "type",
    unique=True,
    postgresql_where=text("budget_id IS NOT NULL"),
    sqlite_where=text("budget_id IS NOT NULL"),
)
```

(Se agrega a la tabla `notifications` definida en §13.5 — mismo archivo, mismo `__table_args__`,
no una segunda migración.) Esto hace que "un aviso por umbral por periodo" sea una garantía de base
de datos, no solo de aplicación — dos transacciones concurrentes que empujan el mismo presupuesto
sobre el 100% al mismo tiempo no pueden generar dos avisos, la misma técnica que ya usa el proyecto
para presupuestos duplicados (`uq_budgets_user_category_period_active`,
`backend/app/models/models.py`) y para `IdempotencyKey`.

**Decisión 13.3.3 — la evaluación llama primero a `ensure_recurring_budgets_for_period` (hallazgo
6), reutilizando la función existente, no una copia.** Si un usuario registra un gasto el primer
día de un mes nuevo antes de haber abierto el dashboard, la fila recurrente de ese mes todavía no
existe — sin este paso, el motor no encontraría ningún presupuesto contra el cual evaluar y el
aviso de ese mes nunca se dispararía hasta que el usuario visite el dashboard (lo cual podría ser
después de ya haber excedido el presupuesto sin avisos).

**Decisión 13.3.4 — fallos en la evaluación de presupuestos (incluyendo fallos de push,
§13.2) nunca deben propagar una excepción que revierta la transacción contable ya confirmada.**
Igual que `app/core/email.py` documenta ("un fallo de email no debe tumbar el request HTTP"), la
función nueva se envuelve en su propio `try/except` con `logger.exception`, después del
`db.commit()` de la transacción — un bug en el motor de alertas no puede convertirse en "el usuario
no pudo registrar su gasto".

**Nueva función**, mismo lugar que `budget_recurrence.py` (vive en `app/core/`, no en un router,
porque ambos endpoints de `transactions.py` la llaman y ningún router importa otro router):

```python
# backend/app/core/budget_alerts.py
"""Motor de evaluación de umbrales de presupuesto (Fase 13 §13.3).

Se invoca después de confirmar el movimiento contable de una transacción de tipo
"expense" (crear o actualizar). Reutiliza exactamente el mismo cálculo de `spent` que
`dashboard.obtener_progreso_presupuestos` (agrupado por currency, Fase 11 §11.1) para
no reintroducir el bug de mezclar monedas que ya se corrigió una vez ahí.
"""

THRESHOLDS = [
    (100, "budget_threshold_100", "Superaste tu presupuesto de {category}"),
    (80, "budget_threshold_80", "Vas en el 80% de tu presupuesto de {category}"),
]


def evaluate_budget_thresholds_for_category(
    db: Session, user_id: int, category_id: int, month: int, year: int
) -> None:
    ensure_recurring_budgets_for_period(db, user_id, month, year)

    presupuesto = (
        db.query(models.Budget)
        .filter(
            models.Budget.user_id == user_id,
            models.Budget.category_id == category_id,
            models.Budget.month == month,
            models.Budget.year == year,
        )
        .first()
    )
    if not presupuesto or presupuesto.amount_limit <= 0:
        return  # sin presupuesto para esta categoría/período, nada que evaluar

    gastado = _spent_for_budget(db, presupuesto)  # mismo query pattern que dashboard.py
    porcentaje = float(gastado / presupuesto.amount_limit) * 100

    for umbral, tipo, plantilla_titulo in THRESHOLDS:
        if porcentaje < umbral:
            continue
        ya_existe = (
            db.query(models.Notification)
            .filter(models.Notification.budget_id == presupuesto.id, models.Notification.type == tipo)
            .first()
        )
        if ya_existe:
            continue  # ya se avisó este umbral en este período — no repetir
        _crear_notificacion(db, presupuesto, tipo, plantilla_titulo, porcentaje)
        break  # si ya cruzó el 100%, no evaluar también el 80% en la misma pasada
```

(`_spent_for_budget` factoriza el `group_by(category_id, currency)` que hoy vive inline en
`obtener_progreso_presupuestos` — se extrae a una función compartida en el mismo módulo o en
`dashboard.py` para que ambos la importen, evitando divergencia entre "cuánto gasté" del dashboard
y "cuánto gasté" del motor de alertas.)

`break` tras el primer umbral cruzado en la pasada (Decisión, arriba): si una sola transacción
grande empuja el gasto de 70% a 130% de una vez, el usuario recibe el aviso de 100% (el más
relevante), no ambos en la misma notificación — evita ruido. Si el mes siguiente hay una
transacción nueva, la unicidad de `(budget_id, type)` ya cubierta arriba sigue impidiendo
duplicados por separado para cada umbral cuando corresponda evaluarlos en pasadas distintas.

**Archivos a modificar:**
- `backend/app/core/budget_alerts.py` (nuevo, arriba).
- `backend/app/api/transactions.py` — en `crear_transaccion`, después de `db.commit()` y solo si
  `nueva_transaccion.type == "expense"`, llamar a
  `evaluate_budget_thresholds_for_category(db, current_user.id, transaccion.category_id, fecha.month, fecha.year)`
  dentro de un `try/except Exception: logger.exception(...)` propio (Decisión 13.3.4). Mismo
  patrón en `actualizar_transaccion`, evaluando la categoría **nueva** (y, si cambió de categoría,
  también la vieja — un gasto que se reclasifica puede hacer que la categoría anterior baje de
  umbral, pero el ROADMAP no pide "retirar" avisos ya emitidos, así que solo se evalúa si la
  categoría nueva cruza un umbral, no se revierte el aviso viejo).
- `backend/app/models/models.py` — `Notification.budget_id` + índice único parcial de Decisión
  13.3.2 (mismo archivo/migración que §13.5, no una migración separada).
- `backend/app/api/dashboard.py` — extraer el cálculo de `spent` agrupado a una función compartida
  (import cruzado desde `budget_alerts.py`, o mover ambas a `app/core/`) para que el motor de
  alertas y `budgets-progress` no diverjan.

**Testing:** este es código que decide si notificar a un usuario sobre dinero — mismo criterio de
riesgo que ya motivó los tests de Fase 7 sobre el módulo contable. `backend/tests/
test_budget_alerts.py` (nuevo): cruzar el 80% genera exactamente una notificación tipo
`budget_threshold_80`; cruzar el 100% en la misma transacción genera solo `budget_threshold_100`
(no ambas); una segunda transacción que mantiene el gasto sobre el 100% no genera una segunda
notificación (verifica la unicidad `(budget_id, type)`); un gasto en una categoría sin presupuesto
no genera nada; dos presupuestos en monedas distintas para la misma categoría (caso multi-moneda,
hallazgo 5) evalúan cada uno con su propio `spent` filtrado por moneda.

**Criterio de aceptación:**
- Un gasto que cruza el 80% de un presupuesto crea una fila en `notifications` una sola vez por
  período.
- Un gasto que cruza el 100% crea la notificación de 100%, no duplica la de 80% si ya existía.
- Un fallo en la evaluación no impide que la transacción se guarde (verificar con un test que
  fuerce una excepción dentro de `evaluate_budget_thresholds_for_category` vía mock).

**Estimación:** 2d en el ROADMAP → **2.5d ajustado**: el ROADMAP no contempla la extracción del
cálculo de `spent` compartido con `dashboard.py` ni la suite de tests dedicada (justificado arriba
por ser lógica que decide sobre dinero, mismo criterio que Fase 7).

---

## 13.4 Indicador visual de progreso (`BudgetRing`)

### Frontend

**Decisión 13.4.1 — alinear los cortes de color de `BudgetRing` a 80/100 (hallazgo 4), no
mantener 75/90.** Cambio de una línea en `frontend/components/charts/BudgetRing.tsx:41-42`:

```tsx
// Antes
const isDanger = percentage >= 90;
const isWarning = percentage >= 75 && percentage < 90;

// Después
const isDanger = percentage >= 100;
const isWarning = percentage >= 80 && percentage < 100;
```

Esto es, en sí mismo, la corrección que el ROADMAP pide ("cambia de color al acercarse al límite")
— el componente ya soporta 3 estados de color (`text-primary`/`text-warning`/`text-danger`) desde
Fase 11; el trabajo real es el realineamiento de umbrales para que coincida con el motor de
alertas de §13.3, no construir un sistema de color nuevo.

**Decisión 13.4.2 — sin cambio en el layout ni las props de `BudgetRing`.** No hace falta agregar
ninguna prop nueva: el componente ya recibe `spentAmount`/`budgetAmount` y calcula `percentage`
internamente — el mismo dato que ahora también alimenta el motor de alertas en el backend
(`obtener_progreso_presupuestos`), así que "el aro se puso rojo" y "llegó/llegaría el aviso de
100%" quedan garantizados como la misma condición, sin duplicar el cálculo (cumple la regla de
`CLAUDE.md` de no recomputar agregados financieros en el cliente — el `percentage` sigue viniendo
del backend, esto solo cambia en qué rango de ese valor se pinta cada color).

**Archivo a modificar:** `frontend/components/charts/BudgetRing.tsx:41-42`.

**Testing:** manual — un presupuesto con `percentage` entre 80 y 99 debe verse en `text-warning`;
100 o más, en `text-danger`; menos de 80, en `text-primary` (sin cambio).

**Criterio de aceptación:**
- Los cortes de color de `BudgetRing` son 80/100, coincidiendo exactamente con los umbrales que
  evalúa el motor de §13.3.

**Estimación:** 1d en el ROADMAP → **1h ajustado**. El ROADMAP dimensiona este ítem como si
hubiera que rediseñar el componente ("adaptar al lenguaje visual del MVP"), pero la exploración
(hallazgo 4) muestra que el coloreado por umbral ya existe desde Fase 11 y el único gap real es un
desajuste de dos constantes numéricas. Ninguna otra pieza del componente (tamaño, `AlertCircle` de
excedido, formato de moneda con `currency` propio de Fase 11 §11.1.2) necesita cambios.

---

## 13.1 PWA instalable

### Frontend

**Decisión 13.1.1 — manifest + service worker escritos a mano, sin `next-pwa` ni Workbox.**
`next-pwa` no está mantenido activamente para Next.js 15+/App Router (el proyecto usa Next 16.2.9,
`frontend/package.json:17`) y añade una capa de configuración (`withPWA(nextConfig)`, generación
de service worker en build) para un caso de uso que en Oikos es deliberadamente acotado: **cachear
el app shell para que sea instalable y reciba push**, no una estrategia de cache offline compleja
(el ROADMAP no pide funcionalidad offline — eso está en el backlog de "Sincronización offline",
marcado explícitamente "Baja" prioridad). Un service worker manual de ~40 líneas
(`frontend/public/sw.js`) que solo maneja `install`/`activate`/`push`/`notificationclick` es más
simple de auditar y depurar que una dependencia con generación de código, para el alcance real de
esta fase. Se documenta como decisión explícita: si Fase 16+ (o un post-MVP) necesita estrategias
de cache más sofisticadas (stale-while-revalidate por ruta, precache de assets), reevaluar Workbox
en ese momento — no antes.

**Archivos a crear:**
- `frontend/public/manifest.json`:
  ```json
  {
    "name": "Oikos — Finanzas Personales",
    "short_name": "Oikos",
    "start_url": "/capture",
    "display": "standalone",
    "background_color": "#0b1220",
    "theme_color": "#0b1220",
    "icons": [
      { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
      { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png" }
    ]
  }
  ```
  `start_url: "/capture"` a propósito, no `"/"`: coherente con la Decisión 10.1.4 de Fase 10 (el
  login ya redirige a `/capture` en todo inicio de sesión) — abrir la PWA instalada debe llevar al
  mismo punto de entrada que abrir la web y loguearse. `background_color`/`theme_color` toman el
  valor de `--color-background` del tema oscuro (`frontend/app/globals.css:6`), como color por
  defecto razonable mientras no exista detección de tema del sistema antes del primer render.
  **Los archivos de ícono (`icon-192.png`, `icon-512.png`) son un artefacto de diseño, no de
  código** — mismo caso que el favicon de Fase 12 §12.5; se documenta el requisito, no se produce
  el binario aquí.
- `frontend/public/sw.js` — service worker manual: cachea el app shell mínimo en `install`
  (`/`, `/capture`, `/manifest.json`, la fuente de `next/font`), sirve del cache en `fetch` con
  network-first + fallback a cache (no cache-first — los datos financieros no deben servirse
  obsoletos silenciosamente), y maneja el evento `push` (ver §13.2 — el `sw.js` de esta sección deja
  el handler de `push`/`notificationclick` ya presente pero vacío/comentado hasta que §13.2 lo
  complete, evitando escribir el mismo archivo dos veces en dos ítems distintos).
- `frontend/components/InstallPrompt.tsx` — escucha `beforeinstallprompt` (Chrome/Edge/Android),
  guarda el evento diferido, muestra un banner discreto ("Instala Oikos" + botón) tras un umbral de
  uso (ej. segunda visita autenticada, vía `localStorage`, mismo mecanismo simple que
  `usePersistedState`) — no en el primer render, para no competir con el flujo de onboarding de
  Fase 15. **iOS Safari no dispara `beforeinstallprompt`** (limitación de la plataforma, no del
  código): para iOS se muestra una instrucción estática ("Compartir → Agregar a pantalla de
  inicio"), detectada vía `navigator.userAgent` o `navigator.standalone` — mismo patrón que
  cualquier sitio que soporta instalación en iOS hoy, sin librería adicional.

**Archivos a modificar:**
- `frontend/app/layout.tsx` — agregar `manifest: '/manifest.json'` a `metadata` (Next.js App
  Router lee esto automáticamente, sin más configuración) y registrar el service worker en un
  `useEffect` de un componente cliente pequeño (`frontend/components/ServiceWorkerRegistration.tsx`,
  montado en `layout.tsx` junto a `UserPreferencesSync`) — `navigator.serviceWorker.register('/sw.js')`,
  con feature-detection (`if ('serviceWorker' in navigator)`) porque Safari de escritorio y
  navegadores viejos no lo soportan.

**Seguridad:** el service worker debe servirse desde la raíz (`/sw.js`, `frontend/public/sw.js`
mapea ahí automáticamente con `next`) para que su *scope* cubra toda la app — un service worker en
un subpath no puede interceptar rutas fuera de él, restricción del propio estándar, no una
decisión de este documento.

**Testing:** manual (Chrome DevTools → Application → Manifest/Service Workers) — el manifest se
detecta sin errores de validación; Lighthouse PWA audit pasa el check de instalabilidad; en Android
Chrome aparece el prompt nativo o el banner propio; en iOS Safari 16.4+, agregar a pantalla de
inicio produce un ícono funcional que abre en modo `standalone` sin la barra de direcciones.

**Criterio de aceptación:**
- La app pasa el check de instalabilidad de Lighthouse.
- Instalada en Android, abre en modo standalone en `/capture`.
- En iOS, el banner de instrucciones aparece solo en Safari (no en Chrome-iOS, que usa el motor de
  Safari pero no expone "Agregar a inicio" de la misma forma — documentar como limitación conocida
  si no se cubre, no bloqueante).

**Estimación:** 2d en el ROADMAP → **2.5d ajustado**: el ROADMAP no contempla el manejo explícito
de la limitación de iOS (banner de instrucciones estático, detección de plataforma) ni la
generación de los dos tamaños de ícono como tarea de coordinación con diseño (aunque el binario en
sí esté fuera de alcance de este documento, alguien debe producirlo antes de que el manifest sea
válido).

---

## 13.2 Infraestructura de push web

### Backend

**Decisión 13.2.1 — `pywebpush` para el envío, no una integración con un proveedor de terceros
(Firebase Cloud Messaging, OneSignal).** `pywebpush` implementa el protocolo Web Push estándar
(VAPID) sin depender de un servicio externo de mensajería ni credenciales de un tercero — coherente
con el criterio ya aplicado a `app/core/email.py` (SMTP directo, sin proveedor externo obligatorio,
aunque ahí se optó por dejar la opción de `smtp` real configurable). FCM/OneSignal añadirían una
cuenta externa, un SDK y un punto de fallo adicional para un volumen de envío que hoy es bajo (un
solo backend, sin necesidad de fan-out masivo) — mismo argumento que el ROADMAP ya usa contra
introducir infraestructura para una escala que el proyecto no tiene. Se agrega `pywebpush` a
`backend/requirements.txt`.

**Decisión 13.2.2 — tabla `push_subscriptions`, una fila por combinación
(usuario, dispositivo/navegador), no una columna en `User`.** Un usuario puede instalar la PWA en
más de un dispositivo (celular + laptop) y cada instalación genera su propia suscripción
(`endpoint`, `p256dh`, `auth` — el objeto `PushSubscription` estándar del navegador). Modelo nuevo:

```python
class PushSubscription(Base):
    """Suscripción push de un navegador/dispositivo (Fase 13 §13.2).

    Un usuario puede tener varias filas (multi-dispositivo). Sin SoftDeleteMixin — una
    suscripción revocada por el navegador (410 Gone al enviar) se borra de verdad, no
    tiene valor histórico (Decisión 6.3 de Fase 8, mismo criterio que RefreshToken).
    """

    __tablename__ = "push_subscriptions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    endpoint = Column(String(500), nullable=False)
    p256dh_key = Column(String(255), nullable=False)
    auth_key = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", backref="push_subscriptions")

    __table_args__ = (Index("uq_push_subscriptions_endpoint", "endpoint", unique=True),)
```

`endpoint` es único globalmente (no por usuario) porque el propio estándar Web Push lo garantiza
único por navegador/instalación — si el mismo endpoint se re-registra (usuario cierra sesión y
vuelve a entrar en el mismo dispositivo), se actualiza la fila en vez de duplicar (`ON CONFLICT` /
`upsert` por `endpoint`).

**Nuevo router** `backend/app/api/push.py`, montado en `main.py` bajo `/api/v1/push`:

- `GET /vapid-public-key` — devuelve la clave pública VAPID (`VAPID_PUBLIC_KEY` de entorno) sin
  autenticación (el frontend la necesita antes de poder generar una suscripción, en un contexto
  donde ya hay sesión iniciada de todos modos porque el prompt de push solo se muestra dentro del
  dashboard — pero el endpoint en sí no expone nada sensible, la clave pública es, por diseño del
  protocolo, pública).
- `POST /subscribe` (autenticado) — recibe `{endpoint, keys: {p256dh, auth}}` (el shape estándar de
  `PushSubscription.toJSON()`), upsert por `endpoint`.
- `DELETE /subscribe` (autenticado) — recibe `{endpoint}`, borra la fila (usuario desactiva
  notificaciones o el navegador invalida la suscripción).

**Decisión 13.2.3 — el envío push se dispara desde el mismo punto que crea la fila en
`notifications` (§13.3/§13.5), no desde un paso separado que el frontend tenga que orquestar.**
`_crear_notificacion` (helper interno de `budget_alerts.py`, §13.3) inserta la fila en
`notifications` y, en la misma función, itera las `push_subscriptions` del usuario y llama a
`pywebpush.webpush(...)` para cada una, envuelto en su propio `try/except` por suscripción (una
suscripción caducada — `WebPushException` con status 404/410 — dispara el borrado de esa fila
específica, no debe abortar el envío a las demás suscripciones del mismo usuario ni afectar la
notificación ya persistida). Esto garantiza la relación "push es un canal adicional sobre el mismo
aviso" de la Decisión de la sección "Orden de dependencia real": no hay manera de que un aviso
llegue por push sin existir también en la bandeja in-app.

**Variables de entorno nuevas** (mismo patrón que `SMTP_*` en `app/core/email.py`): `VAPID_PUBLIC_KEY`,
`VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` (mailto: de contacto, requerido por el estándar). Generación
de par de claves: `pywebpush` incluye una utilidad de línea de comandos para esto — se documenta el
comando exacto en el hand-off al backend-engineer, no se genera un par de ejemplo en este documento
(un par VAPID es tan sensible como `SECRET_KEY`, no debe aparecer en un doc de spec).

### Frontend

**Archivos a modificar:**
- `frontend/public/sw.js` (creado en §13.1) — completar el handler `push` (parsear
  `event.data.json()`, `self.registration.showNotification(title, {body, icon})`) y
  `notificationclick` (enfocar/abrir la ventana de la app en `/budgets` o la ruta del aviso,
  `event.notification.close()`).
- `frontend/components/InstallPrompt.tsx` o un componente nuevo `PushOptIn.tsx` — tras la
  instalación (o independientemente, en navegadores de escritorio que soportan push sin
  instalación, como Chrome), pide permiso (`Notification.requestPermission()`), obtiene la clave
  VAPID pública (`GET /push/vapid-public-key`), crea la suscripción
  (`registration.pushManager.subscribe({userVisibleOnly: true, applicationServerKey})`) y la
  envía a `POST /push/subscribe`.

**Seguridad:** `POST /push/subscribe` y `DELETE /push/subscribe` son autenticados (mismo criterio
que el resto de la API) y no requieren rate limiting por la misma razón que §13.5 (hallazgo 7).
`GET /push/vapid-public-key` es intencionalmente público —no expone nada sensible, es el mecanismo
estándar del protocolo Web Push, no una decisión de este proyecto.

**`backend/docs/API_REFERENCE.md` / `frontend/docs/API_CONTRACT.md`:** deben documentar los 3
endpoints de `push.py` y los 4 de `notifications.py` (§13.5) **cuando se implemente** esta fase —
explícito porque son 7 endpoints nuevos, el lote más grande agregado de una sola vez desde Fase 7.

**Testing:** `backend/tests/test_push.py` (nuevo) — suscribir/desuscribir, upsert por `endpoint`
duplicado, mock de `pywebpush.webpush` para verificar que una excepción 410 borra la suscripción
sin afectar el resto del flujo. El envío real a un navegador real queda fuera de lo que pytest
puede cubrir — se documenta como verificación manual (misma limitación que ya tiene el flujo de
email real de Fase 7, `docs/TODO.md`: sin credenciales reales, sin push real end-to-end verificado
hasta que alguien lo pruebe con un navegador de verdad).

**Criterio de aceptación:**
- Un usuario que otorga el permiso y tiene la PWA instalada recibe una notificación del sistema al
  cruzar un umbral de presupuesto, generada por el mismo evento que crea la fila en `notifications`.
- Una suscripción caducada se limpia automáticamente en el siguiente intento de envío, sin
  intervención manual.
- Ningún endpoint nuevo bloquea el flujo si `VAPID_PUBLIC_KEY`/`VAPID_PRIVATE_KEY` no están
  configuradas (mismo criterio de fallo silencioso con log que `app/core/email.py` aplica a SMTP
  sin credenciales — no debe romper la creación de transacciones si push no está configurado).

**Estimación:** 3d en el ROADMAP → **4d ajustado**: el ROADMAP no contempla el manejo de
suscripciones caducadas (410/404), la coordinación multi-dispositivo (upsert por `endpoint`), ni el
componente de opt-in explícito de permiso — piezas necesarias para que el envío no falle
silenciosamente el 100% de las veces en producción tras la primera suscripción caducada.

---

## Resumen de estimación de horas

| Ítem | ROADMAP | Ajustado | Motivo del ajuste |
|---|---|---|---|
| 13.5 Bandeja in-app | 1d (8h) | 1d (8h) | Sin cambio — alcance ya acotado por el propio ROADMAP y confirmado sin piezas reutilizables (hallazgo 2) |
| 13.3 Motor de presupuestos | 2d (16h) | 2.5d (20h) | Extracción de cálculo `spent` compartido con `dashboard.py` + suite de tests dedicada (código que decide sobre dinero) |
| 13.4 Indicador visual `BudgetRing` | 1d (8h) | 1h | El coloreado por umbral ya existe desde Fase 11 (hallazgo 4); el gap real es un cambio de 2 constantes, no un rediseño |
| 13.1 PWA instalable | 2d (16h) | 2.5d (20h) | Manejo explícito de la limitación de iOS (sin `beforeinstallprompt`) + coordinación de artefactos de ícono |
| 13.2 Push web | 3d (24h) | 4d (32h) | Manejo de suscripciones caducadas, upsert multi-dispositivo, componente de opt-in — sin esto el canal falla silenciosamente tras la primera suscripción vencida |
| **Total** | **9d (72h)** | **~10.1d (81h)** | |

El mayor ajuste a la baja es §13.4 (BudgetRing): la lectura literal del ROADMAP sugiere que hay que
"adaptar" el componente visual, pero la exploración muestra que Fase 11 ya construyó el coloreado
por umbral completo — solo quedaron desalineados los cortes numéricos respecto a los umbrales que
esta fase define para las alertas. El mayor ajuste al alza es §13.2 (push): es la pieza de mayor
incertidumbre operativa de la fase (suscripciones que caducan sin aviso del navegador, multi-
dispositivo) y el ROADMAP la dimensiona como si fuera solo "conectar VAPID + tabla + enviar".

---

## Resumen de archivos tocados por ítem

| Ítem | Archivos |
|---|---|
| 13.5 Bandeja in-app | `backend/app/models/models.py` (`Notification`), `backend/app/schemas/schemas.py`, `backend/app/api/notifications.py` (nuevo), `backend/app/main.py` (mount), migración Alembic nueva, `frontend/hooks/useNotifications.ts` (nuevo), `frontend/components/NotificationBell.tsx` (nuevo), `frontend/components/Sidebar.tsx`, `frontend/docs/STATE_AND_FETCHING.md` |
| 13.3 Motor de presupuestos | `backend/app/core/budget_alerts.py` (nuevo), `backend/app/api/transactions.py`, `backend/app/models/models.py` (índice único en `Notification`), `backend/app/api/dashboard.py` (extracción de `spent` compartido), `backend/tests/test_budget_alerts.py` (nuevo) |
| 13.4 `BudgetRing` | `frontend/components/charts/BudgetRing.tsx` |
| 13.1 PWA instalable | `frontend/public/manifest.json` (nuevo), `frontend/public/sw.js` (nuevo), `frontend/components/InstallPrompt.tsx` (nuevo), `frontend/components/ServiceWorkerRegistration.tsx` (nuevo), `frontend/app/layout.tsx` |
| 13.2 Push web | `backend/requirements.txt` (`pywebpush`), `backend/app/models/models.py` (`PushSubscription`), `backend/app/api/push.py` (nuevo), `backend/app/main.py` (mount), migración Alembic (misma tanda que 13.5 si se implementan juntos, o separada si no), `frontend/public/sw.js` (handler `push`/`notificationclick`), `frontend/components/PushOptIn.tsx` (nuevo), `backend/tests/test_push.py` (nuevo) |
| Cruzando toda la fase | `backend/docs/API_REFERENCE.md` + `frontend/docs/API_CONTRACT.md` (7 endpoints nuevos: 4 de `notifications.py`, 3 de `push.py`) — actualizar cuando se implemente, no ahora |

---

## Cierre

Este documento no implementa ningún cambio en el repositorio — es el desglose ejecutable de la
sección "Fase 13" de `docs/ROADMAP.md`, con archivos, esquemas de datos y decisiones de diseño
concretas para que backend-engineer/frontend-engineer puedan partir directamente de aquí. El
hallazgo central de la exploración (a diferencia de Fase 11/12, donde buena parte del trabajo ya
existía sin conectar) es el opuesto: **nada** de lo que pide esta fase —PWA, push, tabla de
avisos, motor de umbrales— existe hoy en el código (hallazgos 1–3), así que el valor de este
documento está sobre todo en fijar el orden de dependencia real (bandeja in-app antes que push,
motor de presupuestos y BudgetRing en paralelo, PWA como prerrequisito técnico de push) y en las
decisiones de idempotencia (Decisión 13.3.2: unicidad `(budget_id, type)` en `notifications`,
mismo mecanismo de índice único parcial que el proyecto ya usa para presupuestos duplicados) que
el ROADMAP deja abiertas. Todos los hallazgos fueron verificados contra el código real de
`backend/` y `frontend/` el 2026-09-05, no inferidos del texto del ROADMAP. Ningún archivo del
repositorio fuera de `docs/specs/fase_13_spec.md` fue modificado al producir este documento.
