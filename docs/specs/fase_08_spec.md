# Spec — Fase 8: Modelo de datos del nuevo MVP

> Plan de implementación detallado para los 6 items de Fase 8 del [ROADMAP](../ROADMAP.md).
> Fuente de verdad de alcance: `docs/ROADMAP.md` (sección "Fase 8 — Modelo de datos del nuevo
> MVP", líneas ~126-156). Este documento no cambia el alcance ahí definido — lo desglosa en
> tareas ejecutables, con archivos concretos, pasos, dependencias y decisiones de diseño.
>
> **No implementa nada.** Es el hand-off para quien vaya a codear (backend-engineer /
> frontend-engineer).

Estado del repo en el momento de escribir esto (2026-08-23): Fase 7 está mergeada a `main`
(`33c93a8`) — Alembic adoptado con una migración baseline consolidada
(`backend/alembic/versions/0001_baseline_schema.py`) más una migración de Fase 7
(`57bde72b8117_password_reset_y_verificacion_de_email.py`), API versionada bajo `/api/v1/`,
suite de pytest+httpx cubriendo transacciones/presupuestos/auth (`backend/tests/`), TTL de
access token en 15 min, recuperación de contraseña y verificación de email funcionando
end-to-end (backend y frontend). El único usuario real que existe en cualquier entorno sigue
siendo `test@test.com` sembrado por `backend/app/core/seed.py` — **la misma condición que
justificó consolidar la migración baseline de Fase 7 sigue vigente aquí** (ver Decisión de
diseño 0.1 más abajo). Fase 8 depende de Fase 7 exclusivamente por Alembic (todas las columnas
nuevas de este documento se agregan vía migración, no vía `ALTER TABLE` ad-hoc); no depende de
ninguna otra pieza de Fase 7.

Fase 8 en sí no tiene código consumidor: `User.monthly_income` lo usa el onboarding de Fase 13
y el dashboard de flujo de Fase 10; `Transaction.payment_method` lo expone en UI la Fase 9;
los presupuestos recurrentes y la cuenta por defecto sí tienen impacto inmediato (son los dos
🔴 bloqueadores). Es decir: dos de los seis items (recurrencia de presupuestos, cuenta por
defecto) corrigen bugs que **ya rompen el producto hoy**; los otros cuatro son preparación de
esquema para fases futuras y no cambian el comportamiento observable por sí solos.

---

## Hallazgo de exploración que corrige/precisa suposiciones del encargo

El encargo pide verificar, para cada uno de los 6 items, si hay trabajo de frontend real y no
asumirlo. Verificado en el código:

1. **El registro de usuario vive en `backend/app/api/users.py::crear_usuario`
   (`POST /api/v1/users/`), no en `auth.py`.** `auth.py` solo tiene login/refresh/logout/reset
   de contraseña/verificación de email. Esto importa para el item 5 (cuenta por defecto): el
   punto de inserción correcto es `users.py`, no `auth.py`.

2. **No existe ninguna página de perfil/ajustes en el frontend.** `frontend/app/(dashboard)/`
   solo tiene `accounts/`, `analytics/`, `budgets/`, `categories/`, `transactions/` y la página
   raíz del dashboard — ningún `settings/` ni `profile/`. Las únicas preferencias editables hoy
   se hacen a través de `ThemeToggle.tsx` contra `PATCH /api/v1/users/me/preferences`
   (`backend/app/api/preferences.py`). Esto confirma que el item 1 (`monthly_income`) es
   correctamente backend-only en Fase 8 — no hay dónde mostrarlo todavía — pero significa que
   el campo será, durante el tiempo que medie hasta Fase 13, **solo alcanzable por API directa**
   (`curl`/Swagger), sin ninguna forma de que un usuario real lo edite. Ver Decisión 1.1.

3. **`budgets/page.tsx` sí tiene una superficie de frontend real y no trivial para el item 3**
   (presupuestos recurrentes) — contradice cualquier lectura de "Fase 8 es casi 100% backend".
   El formulario de creación/edición de presupuesto (`frontend/app/(dashboard)/budgets/page.tsx:84-111`)
   ya tiene un selector de mes (`<input type="month">`, línea ~244) y la lista
   (`useQuery` línea 37-40) trae **todos** los presupuestos de todos los períodos sin filtrar
   (`api.get('budgets/')` sin query params) y los renderiza todos con su etiqueta de mes
   (`getMonthName`, línea 18-21). Cualquier diseño de recurrencia que agregue una columna
   `is_recurring` necesita: un checkbox en el formulario, tipos actualizados en
   `frontend/types/api.ts` (`Budget`, `BudgetPayload`), y opcionalmente una señal visual en la
   lista para explicar por qué un presupuesto reaparece solo. Ver sección 3, "Frontend".

4. **Los íconos de categoría no requieren ningún cambio de frontend**, incluso agregando
   categorías nuevas. `frontend/components/ui/CategoryIcon.tsx` resuelve el nombre de ícono
   contra `import * as Icons from 'lucide-react'` dinámicamente (línea 14) — no hay un mapa/
   registro hardcodeado que actualizar. Cualquier nombre válido de export de `lucide-react`
   funciona con cero cambios de código. Esto simplifica el item 4 a un cambio de datos puro en
   el backend.

5. **El bug de fallo silencioso de `QuickTransactionModal.tsx:87`
   (`if (!effectiveAccountId || !categoryId || !amount) return;`) está confirmado en el código
   tal cual lo describe `docs/TODO.md`.** Pero su corrección de UX (mostrar un error al usuario)
   es explícitamente una tarea separada de Fase 9 ("Corregir el fallo silencioso del submit —
   2h"). Fase 8 solo necesita eliminar la *causa* (0 cuentas), no la señal de error — por eso el
   item 5 de este documento no toca ese archivo. Confirmar esto explícitamente evita que
   alguien intente "arreglar" `QuickTransactionModal.tsx` dentro de Fase 8 y duplique trabajo de
   Fase 9.

6. **El item 2 (`payment_method`) es explícitamente backend-only en Fase 8** — no por inferencia,
   sino porque el propio ROADMAP separa "Tag de método de pago en la captura" como una línea de
   Fase 9 (4h). Confirmado en el código: ni `TransactionModal.tsx` ni `QuickTransactionModal.tsx`
   tienen ningún campo relacionado con método de pago hoy. Aun así, hay un cambio de frontend
   barato y no controvertido que sí conviene hacer en Fase 8 (no en Fase 9): declarar el campo
   opcional en `frontend/types/api.ts` para que los tipos no diverjan del contrato del backend
   apenas se agregue la columna — ver sección 2, "Frontend".

---

## Decisión de diseño 0.1 — una sola migración consolidada para Fase 8, con la misma condición de Fase 7

El ROADMAP no dice si los cambios de esquema de Fase 8 deben ir en una migración por item o en
una sola. Igual que la Decisión 1.1.1 de `docs/specs/fase_07_spec.md`, el criterio es el costo
de romper compatibilidad con datos existentes: **sigue siendo efectivamente cero** — el único
usuario en cualquier entorno es `test@test.com` (3 cuentas, 45 transacciones, 6 presupuestos
sembrados por `seed.py`), y no hay lanzamiento público todavío (`CLAUDE.md` sigue documentando
el despliegue como Tailscale-only). Recomendación: **una sola migración Alembic para Fase 8**
(`backend/alembic/versions/XXXX_fase_08_modelo_datos_mvp.py`, `down_revision = "57bde72b8117"`),
que incluya:
- `User.monthly_income` (item 1)
- `Transaction.payment_method` (item 2)
- `Budget.is_recurring` + el cambio del `UniqueConstraint` a un índice único parcial (item 3,
  ver Decisión 3.2 — **debe diseñarse junto con el item 6** porque ambos tocan
  `Budget.__table_args__`)
- `updated_at`/`deleted_at` en los modelos que correspondan (item 6)
- Opcionalmente, el backfill de cuentas por defecto para usuarios existentes sin cuentas (item
  5, Decisión 5.2)

El item 4 (categorías default) **no genera ninguna migración** — es un cambio de datos en
`main.py` que ya corre en cada arranque (ver sección 4). El item 5 (cuenta por defecto al
registrarse) tampoco requiere DDL nueva — `Account` ya tiene todas las columnas necesarias.

**Riesgo igual al de Fase 7:** si para cuando esto se implemente ya hay usuarios reales
registrados (posible si pasan semanas entre el merge de Fase 7 y el de Fase 8), esta
consolidación deja de ser gratis — en particular, agregar `nullable=False` implícito a
cualquier columna nueva con datos ya existentes requeriría backfill previo. Ninguna columna de
este documento se propone como `NOT NULL` (todas son nullable o tienen default), así que el
riesgo real es bajo incluso si esa condición cambia, pero declararlo explícitamente en el PR
como hace el spec de Fase 7.

---

## Orden de ejecución recomendado

La dependencia real (no la importancia percibida):

```
1. Categorías default ampliadas (§4)              ── sin dependencias, sin migración; la
                                                        ganancia más barata, hacerla primero
2. Cuenta por defecto al registrarse (§5)          ── sin dependencia de esquema (Account ya
                                                        tiene todas las columnas); desbloquea
                                                        el onboarding de inmediato
3. Diseño conjunto de Presupuestos recurrentes
   (§3) + updated_at/borrado lógico (§6)           ── ambos tocan __table_args__ de Budget
                                                        (el UNIQUE constraint) — deben
                                                        resolverse en conjunto ANTES de generar
                                                        el autogenerate de Alembic, si no hay
                                                        que tocar la misma migración dos veces
4. Migración única de Fase 8 (§0.1)                ── incluye 1, 2 (columnas triviales), 3 y 6
                                                        (esquema), y opcionalmente el backfill
                                                        de cuentas de 5.2 — depende de (3)
5. Filtro global de borrado lógico
   (with_loader_criteria en database.py) (§6)      ── depende de que exista la columna
                                                        deleted_at (paso 4); es código de
                                                        aplicación, no DDL
6. Endpoints DELETE → borrado lógico (§6)          ── depende de (5): sin el filtro global,
                                                        marcar deleted_at sin filtrarlo en las
                                                        lecturas no borra nada de la vista del
                                                        usuario — sería peor que el estado
                                                        actual (el recurso "eliminado" seguiría
                                                        apareciendo en todos lados)
7. Frontend: checkbox `is_recurring` en
   budgets/page.tsx (§3)                            ── depende de (4): el campo debe existir en
                                                        el contrato de API antes de consumirse
```

Los items 1 y 2 de esta lista (categorías, cuenta por defecto) son los dos 🔴 bloqueadores del
ROADMAP y no dependen de nada del resto — pueden mergearse y desplegarse el mismo día,
independientemente de cuánto tarde el resto.

---

## 1. `User.monthly_income`

**Objetivo (ROADMAP):** columna `Numeric(14,2)` nullable. La captura el onboarding de Fase 13;
activa el balance de flujo del dashboard de Fase 10. En Fase 8 solo se agrega la columna y,
según la Decisión 1.1, un endpoint mínimo para poder escribirla antes de que exista onboarding.

### Backend

**Archivos a modificar:**
- `backend/app/models/models.py`, clase `User` (líneas 18-33): agregar
  ```python
  monthly_income = Column(Numeric(14, 2), nullable=True)
  ```
  junto a los demás campos de preferencia (después de `email_verified`, antes de `created_at` —
  mantiene el orden lógico de "datos de perfil" antes de metadatos de auditoría).
- `backend/app/schemas/schemas.py`:
  - `UserResponse` (líneas 86-93): agregar `monthly_income: Decimal | None = None`.
  - Nuevo schema `UserProfileUpdate`:
    ```python
    class UserProfileUpdate(BaseModel):
        monthly_income: Decimal | None = Field(None, ge=0, decimal_places=2)
    ```
    (`ge=0` — un ingreso mensual negativo no tiene sentido de dominio; ver Decisión 1.1 sobre
    por qué es un schema separado de `PreferencesUpdate`).
- `backend/app/api/users.py`: nuevo endpoint
  ```python
  @router.patch("/me", response_model=schemas.UserResponse)
  def actualizar_perfil(
      body: schemas.UserProfileUpdate,
      current_user: models.User = Depends(get_current_user),
      db: Session = Depends(get_db),
  ):
      update_data = body.model_dump(exclude_none=True)
      for field, value in update_data.items():
          setattr(current_user, field, value)
      db.commit()
      db.refresh(current_user)
      return current_user
  ```
  Ruta resultante: `PATCH /api/v1/users/me` (no colisiona con `GET /api/v1/users/me` ya
  existente, línea 63-65 — mismo path, distinto verbo).

**Migración:** incluida en la migración única de Fase 8 (§0.1): `ALTER TABLE users ADD COLUMN
monthly_income NUMERIC(14,2) NULL`.

### Frontend

**No aplica UI** — confirmado en el "Hallazgo de exploración" #2: no existe página de perfil.
**Excepción explícita** (no silenciar): `frontend/types/api.ts`, interfaz `UserResponse`
(líneas 73-80) debe agregar `monthly_income: number | null;` por consistencia de tipos con el
backend, aunque ningún componente lo consuma todavía — evita que Fase 13 tenga que descubrir
el desajuste de tipos desde cero. Costo: una línea, cero riesgo.

### Decisión de diseño 1.1 — endpoint de perfil separado de preferencias, no reutilizar `PreferencesUpdate`

`PreferencesUpdate`/`PATCH /api/v1/users/me/preferences` (`backend/app/schemas/schemas.py:96-99`,
`backend/app/api/preferences.py`) ya existe y sería la ruta de menor esfuerzo para colgar
`monthly_income`. Se descarta por esto: `preferred_currency`/`preferred_locale`/`preferred_theme`
son ajustes cosméticos de presentación (cómo se muestra la app), mientras que
`monthly_income` es un dato financiero de dominio (cuánto gana el usuario) que además
`CLAUDE.md` marca explícitamente como "siempre `Decimal`... el backend es la fuente de verdad
para todos los cálculos financieros". Mezclarlo en el endpoint de "preferencias" invita a que
mañana alguien agregue ahí otro dato financiero por comodidad, diluyendo la distinción. El
costo de separar es mínimo (un endpoint, un schema) y dexa `preferences.py` limpio para lo que
su nombre promete. Si en Fase 13 aparecen más campos de "perfil financiero" (ej. una fecha de
inicio de mes fiscal, si el producto lo necesitara), amplían `UserProfileUpdate`, no
`PreferencesUpdate`.

**Testing:** agregar a `backend/tests/test_auth.py` o un nuevo `test_users.py` (no existe
hoy — este sería el primer test de `users.py` fuera de registro): `PATCH /api/v1/users/me` con
`monthly_income` válido lo persiste y lo devuelve en `GET /api/v1/users/me`; valor negativo
devuelve 422; el endpoint requiere autenticación (401 sin token).

---

## 2. `Transaction.payment_method`

**Objetivo (ROADMAP):** nullable, valores `cash`/`card`/`transfer`. Tag ligero en la
transacción, no un módulo de configuración de métodos de pago. Distinto de `Account.type`.

### Backend

**Archivos a modificar:**
- `backend/app/models/models.py`, clase `Transaction` (líneas 63-80): agregar
  ```python
  payment_method = Column(String(20), nullable=True)
  ```
  Sin `CheckConstraint` a nivel de DB — mismo patrón que la columna `type` de la propia
  `Transaction` (línea 68) y `Category.type` (línea 54): la validación de valores permitidos
  vive en el schema Pydantic, no en la base de datos. Mantener la consistencia con el resto del
  archivo en vez de introducir un patrón nuevo solo para esta columna.
- `backend/app/schemas/schemas.py`:
  - Nuevo enum junto a `TransactionType` (línea 103-105):
    ```python
    class PaymentMethod(str, Enum):
        cash = "cash"
        card = "card"
        transfer = "transfer"
    ```
  - `TransactionBase` (líneas 108-115): agregar `payment_method: PaymentMethod | None = None`.
    Al estar en `TransactionBase`, se propaga automáticamente a `TransactionCreate` y
    `TransactionResponse` sin tocarlas.
- `backend/app/api/transactions.py`:
  - `crear_transaccion` (líneas 20-70): **no requiere cambio** — usa
    `transaccion.model_dump(exclude_none=True)` (línea 51) para construir `models.Transaction`,
    así que `payment_method` se incluye automáticamente si viene en el body y se omite si no.
  - `actualizar_transaccion` (líneas 150-232): **sí requiere un cambio explícito** — la función
    copia campo por campo (líneas 217-221) en vez de hacer `model_dump`, así que hay que agregar
    la línea `transaccion_db.payment_method = transaccion_actualizada.payment_method` junto a
    las demás asignaciones (después de la línea 219, `transaccion_db.description = ...`). Sin
    este paso, editar una transacción borraría silenciosamente cualquier `payment_method` que
    no se reenvíe explícitamente en cada PUT (el mismo tipo de bug de "campo que el schema
    hereda pero el router ignora" que ya existe hoy con `AccountUpdate.currency`, documentado en
    `docs/TODO.md`) — no repetirlo aquí.

**Migración:** incluida en la migración única de Fase 8: `ALTER TABLE transactions ADD COLUMN
payment_method VARCHAR(20) NULL`.

### Frontend

**No aplica UI de captura** — es explícitamente Fase 9 ("Tag de método de pago en la captura —
4h", ROADMAP). **Cambio menor recomendado, no bloqueante:** `frontend/types/api.ts` —
`Transaction` (líneas 11-21), `CreateTransactionPayload` (líneas 94-102) y
`UpdateTransactionPayload` (líneas 104-112) deberían declarar
`payment_method?: 'cash' | 'card' | 'transfer' | null;` por la misma razón que el item 1: evita
que Fase 9 empiece por descubrir el desajuste de tipos. No implica agregar ningún campo al
formulario todavía.

### Decisión de diseño 2.1 — colisión de nombres entre `Account.type` y `Transaction.payment_method`, no es un problema real

`AccountType` (`schemas.py:132-135`) ya incluye el valor `"cash"` como tipo de cuenta, y
`PaymentMethod` también usará `"cash"` como método de pago. Son columnas y enums distintos
(`accounts.type` vs `transactions.payment_method`), sin relación de FK entre sí, así que no hay
colisión técnica — pero vale la pena dejarlo explícito porque alguien leyendo el schema de
OpenAPI/Swagger podría confundirlos. No se recomienda renombrar ninguno de los dos (romper
`AccountType.cash` no tiene beneficio y ya está en producción de facto vía el seed y el
frontend); basta con que la documentación (`backend/docs/API_REFERENCE.md`,
`frontend/docs/API_CONTRACT.md`) explique la distinción la primera vez que se documente
`payment_method`, como ya exige `CLAUDE.md` para contratos de API compartidos.

**Testing:** agregar un caso a `backend/tests/test_transactions.py` (ya existe el archivo, con
casos de balance/ownership): crear una transacción con `payment_method="card"` lo persiste y lo
devuelve; editar una transacción cambiando `payment_method` lo actualiza (cubre el fix de
`actualizar_transaccion` de arriba); una transacción sin `payment_method` no rompe nada
(`None` es válido).

---

## 3. Presupuestos recurrentes

**Objetivo (ROADMAP):** 🔴 bloqueador de retención. Hoy `Budget` exige `month`+`year` fijos —
el presupuesto de enero desaparece en febrero. El ROADMAP menciona dos opciones: `is_recurring`
+ resolución del período en consulta, o generación perezosa del mes actual.

### Verificación del comportamiento actual

- `backend/app/api/dashboard.py::obtener_progreso_presupuestos` (líneas 112-168) filtra
  **estrictamente** `Budget.month == hoy.month and Budget.year == hoy.year` (líneas 118-124) —
  sin ningún presupuesto para el mes en curso, la lista vuelve vacía y el dashboard no muestra
  nada, exactamente el bug que describe `docs/TODO.md` ("Los presupuestos no sobreviven al
  cambio de mes").
- `backend/app/api/budgets.py::obtener_presupuestos` (líneas 59-73) sí acepta `month`/`year`
  como filtros **opcionales** — si no se pasan, devuelve **todos** los presupuestos de todos
  los períodos sin filtrar.
- `frontend/app/(dashboard)/budgets/page.tsx:37-40` llama `GET /budgets/` **sin** parámetros —
  la página de presupuestos ya muestra el historial completo, cada fila con su propia etiqueta
  de mes (`getMonthName`, línea 18-21). Esto importa para el diseño elegido abajo: la lista de
  presupuestos no necesita ningún cambio de fetching, solo de creación.

### Decisión de diseño 3.1 — generación perezosa por fila, no `is_recurring` puro con resolución en consulta

Se elige la opción de **generación perezosa**, con un matiz respecto a como la plantea el
ROADMAP: no se genera "el mes actual" de forma global en background, sino que se genera
**bajo demanda, por período consultado**, la primera vez que ese período se pide (dashboard o
`GET /budgets?month=X&year=Y`). Diseño concreto:

- `Budget` gana una columna `is_recurring: bool` (default `False`). Cada fila sigue
  representando **un período concreto** (como hoy) — no se vuelve "sin mes". Si
  `is_recurring=True`, esa fila actúa como *plantilla* para el siguiente período que se
  consulte y no exista todavía.
- Nueva función helper (ver ubicación en Decisión 3.3) que, dado `(user_id, month, year)`:
  1. Busca, por categoría, la fila `is_recurring=True` más reciente del usuario (la de mayor
     `(year, month)`) que **no** sea ya del período pedido.
  2. Para cada categoría con plantilla y sin fila ya existente en `(month, year)`, crea una
     fila nueva clonando `amount_limit`, `currency`, `is_recurring=True` (la copia también es
     recurrente — así sigue generando el mes siguiente sin intervención), `category_id`.
  3. Inserta con el mismo patrón de `try/except IntegrityError` que ya usa
     `crear_presupuesto` (`budgets.py:46-54`) — si dos requests concurrentes generan la misma
     fila, el `UNIQUE` de base de datos (ver Decisión 3.2) resuelve la carrera sin duplicados.
- Puntos de invocación: `obtener_progreso_presupuestos` (dashboard.py, siempre pide "hoy") y
  `obtener_presupuestos` (budgets.py, **solo cuando el caller pasa `month` y `year` explícitos**
  — si no los pasa, como hace hoy `budgets/page.tsx`, se sigue devolviendo el historial completo
  sin generar nada nuevo, porque no hay un período concreto que "asegurar").
- **Por qué esto resuelve el caso real sin trabajo extra del usuario:** el dashboard es la
  página de aterrizaje de la app (`app/(dashboard)/page.tsx`) — cualquier usuario que entre en
  febrero dispara `GET /dashboard/budgets-progress`, que genera las filas de febrero antes de
  que el usuario llegue a `/budgets`. La siguiente vez que visite `/budgets` (que pide *todos*
  los períodos sin filtro), las filas de febrero ya existen como datos reales y aparecen solas.
- **Por qué no la alternativa (`is_recurring` + resolución en consulta, sin filas nuevas):**
  esa opción evitaría escribir filas nuevas cada mes, pero obligaría a que **toda** consulta de
  presupuestos (dashboard, listado, futuras exportaciones) reconstruya "¿qué categorías tienen
  un presupuesto recurrente activo, aplicado a *qué* período?" en tiempo de lectura, sin que
  exista una fila física que se pueda editar/eliminar para *ese* mes en particular (si el
  usuario quiere subir el límite de comida solo en diciembre por las fiestas, no hay dónde
  guardar ese override sin, de todas formas, crear una fila para diciembre — con lo cual se
  termina construyendo el mismo mecanismo de filas-por-período, pero con más lógica condicional
  en cada lectura). La generación perezosa por fila reutiliza el modelo de datos actual sin
  ambigüedad: cada mes es una fila real, editable y borrable independientemente, con
  `is_recurring` decidiendo solamente si genera la siguiente.
- **Límite aceptado:** si un usuario no abre la app durante varios meses, al volver solo se
  genera el período que efectivamente consulta — no se rellenan retroactivamente los meses
  saltados. Se considera correcto (no incorrecto): esos meses nunca tuvieron una consulta real
  de progreso, así que no hay un "gasto vs. presupuesto" que mostrar de todas formas.
- **Semántica de edición:** si el usuario edita el `amount_limit` de la fila del mes en curso
  (vía `PUT /budgets/{id}`) y esa fila es `is_recurring=True`, el cambio se vuelve automáticamente
  la nueva plantilla para el mes siguiente, porque la plantilla siempre es "la fila recurrente
  más reciente" — no existe una tabla de plantillas separada. Esto es intencional y debe
  documentarse en la UI (ver "Frontend" abajo): editar el presupuesto de este mes cambia lo que
  se generará el próximo mes, no solo el mes actual.
- **Cómo se "apaga" la recurrencia:** cambiando `is_recurring` a `False` en la fila del período
  en curso (vía `PUT`), no borrándola. Si se borra (soft-delete, ver §6) sin apagar la
  recurrencia, la búsqueda de "última fila recurrente" seguirá encontrando la fila anterior
  (no borrada) y seguirá generando meses futuros — comportamiento deseado: borrar un mes
  puntual no debe cortar la recurrencia de los siguientes.

### Decisión de diseño 3.2 — el `UNIQUE(user_id, category_id, month, year)` de Fase 7 se mantiene sin cambios para este item

A diferencia de lo que podría parecer necesario, el constraint agregado en
`docs/specs/fase_07_spec.md §1.4` (`uq_budgets_user_category_period`,
`backend/app/models/models.py:97-99`) **no necesita tocarse por la recurrencia en sí** — cada
fila generada tiene su propio `(month, year)` distinto, así que nunca colisiona con la fila que
la originó. El único motivo para tocar este constraint es la interacción con borrado lógico
(§6) — ver Decisión 6.2, que si actualiza este `__table_args__`, y por eso ambos items deben
diseñarse juntos (ver "Orden de ejecución recomendado").

### Backend

**Archivos a crear:**
- `backend/app/core/budget_recurrence.py` — la función helper de generación perezosa (ver
  Decisión 3.3 sobre por qué vive en `app/core/` y no en un router).

**Archivos a modificar:**
- `backend/app/models/models.py`, clase `Budget` (líneas 83-99): agregar
  `is_recurring = Column(Boolean, nullable=False, default=False)`.
- `backend/app/schemas/schemas.py`, `BudgetBase` (líneas 187-192): agregar
  `is_recurring: bool = False`. Al vivir en `BudgetBase`, se propaga a `BudgetCreate` (línea
  195-196), `BudgetResponse` (línea 199-204) y al body de `actualizar_presupuesto`, que usa
  `BudgetBase` directamente (`budgets.py:92`).
- `backend/app/api/budgets.py`:
  - `crear_presupuesto` (líneas 14-56): sin cambios estructurales — `is_recurring` viaja en
    `presupuesto.model_dump()` (línea 45) automáticamente.
  - `obtener_presupuestos` (líneas 59-73): cuando `month` y `year` vienen ambos, llamar a
    `ensure_recurring_budgets_for_period(db, current_user.id, month, year)` antes de construir
    la query final (o justo después de aplicar los filtros — el orden no importa porque la
    función hace su propio commit).
  - `actualizar_presupuesto` (líneas 89-123): agregar
    `presupuesto_db.is_recurring = presupuesto_actualizado.is_recurring` junto a las demás
    asignaciones (línea 116-119) — mismo cuidado que en el item 2: un campo que el schema
    hereda pero el router no copia es un bug silencioso ya documentado en otro lado del
    proyecto (`AccountUpdate.currency`).
- `backend/app/api/dashboard.py::obtener_progreso_presupuestos` (líneas 112-168): llamar a
  `ensure_recurring_budgets_for_period(db, current_user.id, hoy.month, hoy.year)` como primer
  paso, antes de la query de la línea 118.

**Migración:** incluida en la migración única de Fase 8 (ver Decisión 0.1 y 3.2 en conjunto con
§6): `ALTER TABLE budgets ADD COLUMN is_recurring BOOLEAN NOT NULL DEFAULT false`.

### Decisión de diseño 3.3 — el helper de generación vive en `app/core/`, no se importa un router desde otro

`CLAUDE.md` documenta explícitamente que la arquitectura actual es "sin capa de servicios —
lógica de negocio vive directamente en los routers, por diseño a esta escala", y verificado en
el código: **ningún router importa de otro router** (`grep` sobre `backend/app/api/` no
encuentra ningún `from app.api.X import ...`). Este item necesita que tanto `budgets.py` como
`dashboard.py` disparen la misma lógica de generación — importar `budgets.py` desde
`dashboard.py` (o viceversa) rompería ese patrón sin necesidad. La alternativa correcta, y ya
usada en el proyecto para lógica compartida no ligada a un dominio de router específico
(`app/core/email.py`, `app/core/security.py`), es un módulo pequeño y enfocado en
`app/core/`. No se recomienda crear `app/services/` para esto — sería adoptar la capa de
servicios completa que `CLAUDE.md` marca como deuda técnica de prioridad 🟢 ("revisar cuando el
código duela al modificarlo"), para resolver un solo caso de reutilización entre dos funciones.
Ese refactor mayor, si se hace, debe ser deliberado y cubrir todo el código, no colarse como
efecto secundario de este item.

### Frontend

**Sí aplica** — confirmado en el "Hallazgo de exploración" #3.

**Archivos a modificar:**
- `frontend/types/api.ts`: `Budget` (líneas 31-39) y `BudgetPayload` (líneas 122-128) — agregar
  `is_recurring: boolean;` / `is_recurring?: boolean;` respectivamente.
- `frontend/app/(dashboard)/budgets/page.tsx`:
  - Nuevo estado `const [isRecurring, setIsRecurring] = useState(false);` junto a los demás
    (línea 29-35).
  - `handleSubmit` (líneas 84-94): incluir `is_recurring: isRecurring` en el objeto pasado a
    `saveMutation.mutate(...)`.
  - `openCreateModal` (líneas 96-102): resetear `setIsRecurring(false)`.
  - `openEditModal` (líneas 104-111): `setIsRecurring(budget.is_recurring)`.
  - Formulario: agregar un checkbox/toggle "Repetir cada mes" cerca del selector de monto/mes
    (dentro del `ModalShell`, no localizado en el fragmento leído — ubicar junto a los inputs
    de monto/categoría existentes). Texto de ayuda recomendado, dado el comportamiento descrito
    en la Decisión 3.1: *"Se creará automáticamente cada mes con el mismo monto. Editar el
    presupuesto de un mes también actualiza el monto de los meses futuros."* — evita que el
    usuario se sorprenda con la semántica de "la plantilla es la fila más reciente".
  - Lista de presupuestos (fragmento no incluido en la lectura parcial, pero la fila ya
    renderiza `getMonthName(budget.month, budget.year)`): agregar un ícono/badge (ej. `Repeat`
    de `lucide-react`, ya una dependencia) junto a los presupuestos con `is_recurring: true`,
    para que el usuario entienda por qué esa fila reaparece sola cada mes sin haberla recreado.

**Testing:** agregar a `backend/tests/test_budgets.py` (ya tiene una clase con casos de unique
constraint y de progreso — ver `_now_month_year()` helper, línea 14-16):
- Crear un presupuesto `is_recurring=True` para el mes actual, simular "avanzar" al mes
  siguiente (construir `month`/`year` del mes siguiente en el test, no viajar en el tiempo de
  verdad) y llamar `GET /api/v1/dashboard/budgets-progress` — o directamente
  `GET /api/v1/budgets/?month=X&year=Y` del mes siguiente — verificar que aparece una fila
  nueva con el mismo `amount_limit` y `is_recurring=True`.
- Dos requests concurrentes (o secuenciales simulando la carrera, mismo patrón que el test de
  Fase 7 para el unique constraint) pidiendo el mismo período no-generado-todavía no crean
  presupuestos duplicados.
- Un presupuesto con `is_recurring=False` **no** se regenera el mes siguiente.
- Editar el `amount_limit` de una fila recurrente y luego generar el mes siguiente usa el monto
  actualizado, no el original.

---

## 4. Categorías default ampliadas a 8–10

**Objetivo (ROADMAP):** agregar Vivienda, Salud, Educación; renombrar Ocio → Entretenimiento;
revisar categorías de ingreso (hoy solo Salario).

### Verificación del mecanismo actual

`backend/app/main.py::seed_default_categories()` (líneas 43-81) corre en **cada arranque**
(`initialize_shared_data`, línea 163-164) y ya tiene, de Fase 7, exactamente el mecanismo
necesario para renombrar una categoría base preservando su `id` (y por lo tanto sus
transacciones/presupuestos existentes): el diccionario `LEGACY_DEFAULT_CATEGORY_NAMES` (líneas
37-40) más la lógica de detección-y-rename (líneas 57-71). Hoy ese diccionario solo tiene las
dos entradas de la migración legacy de "Otro" (ya resueltas de una vez en
`0001_baseline_schema.py::_migrate_legacy_category_names()` — ver `docs/specs/fase_07_spec.md
§1.1.3`), así que en la práctica es un mecanismo genérico ya construido y sin usar.

**Consecuencia importante:** el rename Ocio → Entretenimiento **no necesita ninguna migración
de Alembic** — se resuelve reutilizando este mecanismo existente, que ya corre en cada arranque
y ya está documentado como comportamiento esperado en
`backend/docs/BUSINESS_RULES.md:24` ("Al iniciar la aplicación se siembran categorías base y
se corrigen nombres heredados de categorías base antiguas"). Las categorías nuevas
(Vivienda/Salud/Educación/una de ingreso) tampoco necesitan migración — el mismo loop las crea
si no existen (`main.py:76-77`).

### Backend

**Archivo a modificar:** `backend/app/main.py`, líneas 27-40.

**`DEFAULT_CATEGORIES` resultante** (reemplaza el arreglo actual de 7 entradas):
```python
DEFAULT_CATEGORIES = [
    {"name": "Alimentación", "type": "expense", "icon": "UtensilsCrossed"},
    {"name": "Transporte", "type": "expense", "icon": "Car"},
    {"name": "Vivienda", "type": "expense", "icon": "Home"},
    {"name": "Salud", "type": "expense", "icon": "HeartPulse"},
    {"name": "Educación", "type": "expense", "icon": "GraduationCap"},
    {"name": "Entretenimiento", "type": "expense", "icon": "Gamepad2"},
    {"name": "Cuidado personal", "type": "expense", "icon": "Heart"},
    {"name": "Suscripción", "type": "expense", "icon": "Radio"},
    {"name": "Otro", "type": "expense", "icon": "CircleEllipsis"},
    {"name": "Salario", "type": "income", "icon": "Wallet"},
    {"name": "Otros ingresos", "type": "income", "icon": "TrendingUp"},
]

LEGACY_DEFAULT_CATEGORY_NAMES = {
    ("expense", "Otro"): "Otro (Gasto)",
    ("income", "Otro"): "Otro (Ingreso)",
    ("expense", "Entretenimiento"): "Ocio",
}
```
Nombres de íconos verificados como exports válidos de `lucide-react` (misma librería ya usada
en el resto del proyecto: `Home`, `HeartPulse`, `GraduationCap`, `TrendingUp`) — confirmar la
versión instalada en `frontend/package.json` al implementar, por si alguno cambió de nombre
entre versiones de `lucide-react`.

**Total resultante: 11 categorías** (9 expense + 2 income) — ver Decisión 4.1 sobre por qué se
excede el rango "8–10" del ROADMAP.

### Frontend

**No aplica ningún cambio** — confirmado en el "Hallazgo de exploración" #4
(`CategoryIcon.tsx` resuelve íconos dinámicamente).

### Decisión de diseño 4.1 — 11 categorías, no 10, porque "revisar ingreso" expone un hueco real de producto

Sumando Vivienda, Salud y Educación a las 7 categorías actuales (sin contar el rename de
Ocio, que no agrega fila) da exactamente 10 — encajaría en el rango "8–10" del ROADMAP **sin**
tocar las categorías de ingreso. Pero el propio ROADMAP pide explícitamente "revisar categorías
de ingreso (hoy solo existe Salario)" como parte del mismo item, no como algo opcional. Se
verificó el motivo: `QuickTransactionModal.tsx:49-52` filtra las categorías mostradas por
`c.type === type` — un usuario con un ingreso que no sea salario (freelance, un reembolso, un
regalo) **no tiene ninguna categoría de ingreso disponible** salvo "Salario", y el modelo del
MVP dice explícitamente "curadas... sin editor en v1" (ROADMAP, "El MVP en cinco componentes",
punto 2) — es decir, un usuario real de v1 no tiene forma de crear una categoría propia para
ese caso. Agregar una categoría catch-all de ingreso ("Otros ingresos") no es un capricho de
cobertura, resuelve un flujo que hoy literalmente no se puede completar. Se prioriza resolver
el problema nombrado por el ROADMAP sobre cumplir el número exacto "8–10" — 11 es la cifra que
resulta de tomarse en serio ambas instrucciones del mismo ítem. Si se prefiere respetar el tope
de 10 a rajatabla, la alternativa es no agregar "Otros ingresos" y dejar el hueco de ingreso sin
resolver — pero eso contradice la instrucción explícita del propio ROADMAP, así que no se
recomienda.

**Testing:** no hay tests hoy sobre `seed_default_categories()` (es lógica de arranque, no
un endpoint) — no es necesario agregarlos para este item (el ROADMAP acota el testing a "lógica
que mueve dinero y la que da acceso", `docs/specs/fase_07_spec.md §4.2`). Verificación manual:
arrancar el backend contra una base limpia y contra la base con datos del seed
(`test@test.com`, que ya tiene una categoría personal llamada "Freelance" distinta de "Otros
ingresos" — confirmar que no colisionan, son categorías con `user_id` distinto: una es de
sistema `user_id=NULL`, la otra es del usuario) y verificar `GET /api/v1/categories/` devuelve
las 11 categorías base más las personales del usuario.

---

## 5. Cuenta por defecto al registrarse

**Objetivo (ROADMAP):** 🔴 bloqueador de onboarding. Un usuario nuevo tiene 0 cuentas,
`account_id` es obligatorio, y `QuickTransactionModal` falla en silencio. Auto-crear una cuenta
"Efectivo" en el registro.

### Verificación

- Registro vive en `backend/app/api/users.py::crear_usuario` (líneas 40-60), no en `auth.py`
  (ver "Hallazgo de exploración" #1).
- `AccountCreate` (`schemas.py:145-146`) exige `type: AccountType` (enum `cash`/`debit`/
  `credit`, sin default) y acepta `balance: Decimal = Field(0, ge=0, ...)` con default `0` — un
  saldo inicial de `0` es válido sin ningún ajuste de schema.
- `User.preferred_currency` (`models.py:24`) tiene default Python-side `"COP"` — después de
  `db.commit()` + `db.refresh(nuevo_usuario)` (líneas 52-54, ya existentes en `crear_usuario`),
  `nuevo_usuario.preferred_currency` está poblado y disponible para usar como moneda de la
  cuenta nueva. El registro (`UserCreate`, `schemas.py:77-83`) no pide moneda — no hay otra
  fuente de la que tomarla.

### Backend

**Archivo a modificar:** `backend/app/api/users.py::crear_usuario` (líneas 40-60).

**Diseño concreto** — reescribir la función para que la creación de usuario y de la cuenta por
defecto ocurran en la misma transacción (un solo `commit`), dejando el envío del email de
verificación fuera de esa transacción (no debe poder revertir la creación del usuario si el
email falla — y de hecho no puede, porque `send_email()` ya nunca lanza excepción,
`backend/app/core/email.py:27-38`, pero mantener la separación conceptual es más claro):

```python
@router.post("/", response_model=schemas.UserResponse)
@limiter.limit("5/minute")
def crear_usuario(request: Request, usuario: schemas.UserCreate, db: Session = Depends(get_db)):
    normalized_email = usuario.email.lower().strip()
    usuario_existente = db.query(models.User).filter(models.User.email == normalized_email).first()
    if usuario_existente:
        raise HTTPException(status_code=400, detail="Error: Este correo electrónico ya está registrado.")

    hashed_password = get_password_hash(usuario.password)
    nuevo_usuario = models.User(email=normalized_email, full_name=usuario.full_name, password_hash=hashed_password)
    db.add(nuevo_usuario)
    db.flush()  # asigna nuevo_usuario.id sin cerrar la transacción todavía

    cuenta_por_defecto = models.Account(
        name="Efectivo",
        type="cash",
        balance=Decimal("0.00"),
        currency=nuevo_usuario.preferred_currency or "COP",
        user_id=nuevo_usuario.id,
        highlighted=True,
    )
    db.add(cuenta_por_defecto)

    db.commit()
    db.refresh(nuevo_usuario)

    _enviar_email_verificacion(nuevo_usuario, db)

    return nuevo_usuario
```
Cambios respecto al código actual: `db.commit()` se mueve de justo después de `db.add(nuevo_usuario)`
a después de agregar también la cuenta (un solo commit en vez de dos), y se inserta
`db.flush()` en el medio para poder usar `nuevo_usuario.id` antes del commit final. Requiere
importar `Decimal` (`from decimal import Decimal`) — no está importado hoy en `users.py`.

`highlighted=True`: la primera cuenta de un usuario nuevo se marca destacada, porque
`obtener_resumen` (`dashboard.py:33-36`) filtra el dashboard por cuentas destacadas *si existe
al menos una* — sin esto, la cuenta "Efectivo" existiría pero el resumen del dashboard seguiría
comportándose igual (usa todas si no hay destacadas), así que no es estrictamente necesario,
pero deja al usuario en el mismo estado que si la hubiera destacado manualmente desde el primer
día, sin sorpresas cuando cree una segunda cuenta más adelante y "Efectivo" deje de aparecer
por default.

**Migración:** ninguna — `Account` ya tiene todas las columnas necesarias.

### Frontend

**No aplica ningún cambio de código.** El registro (`frontend/app/(auth)/register/page.tsx`)
ya redirige a `/login` sin mostrar ni consumir la respuesta del registro más allá del manejo de
errores (líneas 37-63) — no hay ningún lugar donde "mostrar la cuenta creada" en el flujo
actual. Cuando el usuario haga login y llegue al dashboard, `GET /api/v1/accounts/` ya
devolverá la cuenta "Efectivo" sin ningún cambio adicional. `QuickTransactionModal.tsx` queda
sin tocar, tal como establece el "Hallazgo de exploración" #5.

### Decisión de diseño 5.1 — no exponer la cuenta creada en la respuesta del registro

`UserResponse` no incluye una lista de cuentas y no se recomienda agregarla ahora — ampliaría
el contrato de un endpoint (`POST /api/v1/users/`) que hoy el frontend no usa para nada más que
confirmar éxito antes de redirigir a `/login` (ver arriba). Si Fase 13 (onboarding) necesita
mostrar "ya creamos tu primera cuenta" como parte del flujo de 3 minutos, en ese momento decide
si conviene devolver la cuenta en la respuesta del registro o simplemente pedirla vía
`GET /api/v1/accounts/` tras el login — es una decisión de flujo de onboarding, no de modelo de
datos, y corresponde a esa fase.

### Decisión de diseño 5.2 — backfill opcional para usuarios ya registrados sin cuentas

Hoy el único usuario real en cualquier entorno (`test@test.com`) ya tiene 3 cuentas por el
seed, así que el backfill no tiene ningún efecto inmediato. Pero a diferencia de la Decisión
0.1 (que asume cero usuarios reales), este caso concreto puede dejar de ser cierto **incluso
sin lanzamiento público**: cualquier persona que se haya registrado entre el despliegue de Fase
7 y el despliegue de Fase 8 (el propio desarrollador probando el flujo, por ejemplo) quedaría
con 0 cuentas y el bug original sin resolver para esa cuenta específica, con el agravante de
que ya pasó por verificación de email y no puede simplemente "volver a registrarse" (el email
ya está tomado). Recomendación: incluir en la misma migración de Fase 8 (§0.1) un paso de datos
que siga el mismo patrón que
`0001_baseline_schema.py::_migrate_legacy_category_names()` — iterar los `users` que no tengan
ninguna fila en `accounts` y crearles una cuenta "Efectivo" con `balance=0`,
`currency=preferred_currency` (o `'COP'` si es NULL), `highlighted=true`. Costo marginal (unas
20 líneas más en la misma migración), y cierra el caso borde sin depender de que nadie se
acuerde de correrlo manualmente. Sobre una base de datos verdaderamente vacía de usuarios (el
caso hoy) esto es un no-op.

**Testing:** agregar a `backend/tests/test_auth.py` (tiene la fixture `register_and_login`,
`conftest.py:93-130`, que ya asume `POST /api/v1/users/` devuelve 200 con solo
email/full_name/password — no rompe con este cambio porque `UserResponse` no cambia de forma):
registrar un usuario nuevo y verificar, vía `GET /api/v1/accounts/` con el token devuelto, que
existe exactamente una cuenta llamada "Efectivo", tipo `cash`, saldo `0.00`, moneda igual a
`preferred_currency` del usuario (`"COP"` por default), `highlighted=true`. Verificar además
que inmediatamente después se puede crear una transacción contra esa cuenta sin error 404 (el
síntoma exacto del bug original).

---

## 6. `updated_at` + borrado lógico en todas las entidades

**Objetivo (ROADMAP):** trivial ahora; habilita sincronización offline a futuro.

### Inventario de los 8 modelos

| Modelo | `created_at` hoy | `updated_at` propuesto | `deleted_at` propuesto | Razón |
|---|---|---|---|---|
| `User` | Sí (línea 28) | Sí | Sí* | Entidad de dominio principal; ver nota* |
| `Account` | No | Sí | Sí | Ya tiene endpoint `DELETE` hoy (hard delete) |
| `Category` | No | Sí | Sí | Ya tiene endpoint `DELETE` hoy (hard delete) |
| `Transaction` | Implícito vía `date` (línea 69, no es un timestamp de auditoría real) | Sí | Sí | Ya tiene endpoint `DELETE` hoy (hard delete) |
| `Budget` | No | Sí | Sí | Ya tiene endpoint `DELETE` hoy; interactúa con el UNIQUE (Decisión 6.2) |
| `RefreshToken` | Sí (línea 109) | **No** | **No** | Ver Decisión 6.3 |
| `PasswordResetToken` | Sí (línea 127) | **No** | **No** | Ver Decisión 6.3 |
| `EmailVerificationToken` | Sí (línea 145) | **No** | **No** | Ver Decisión 6.3 |

\* `User.deleted_at`: no existe hoy ningún endpoint de "eliminar mi cuenta" — se agrega la
columna igual, por uniformidad con el resto de entidades de dominio y porque es "trivial ahora"
(ROADMAP), pero queda sin ningún flujo que la use hasta que exista esa feature (fuera del
alcance de Fase 8 y no listada en ningún ítem del ROADMAP actual). Ver el límite conocido en la
Decisión 6.4.

### Decisión de diseño 6.1 — filtro global vía `with_loader_criteria`, no tocar cada `db.query(...)` a mano

El encargo señala correctamente el riesgo: hay decenas de `db.query(models.X)...` en
`accounts.py`, `categories.py`, `budgets.py`, `transactions.py`, `dashboard.py`, `users.py` y
`auth.py`. Agregar `.filter(Model.deleted_at.is_(None))` a mano en cada uno es mecánico, pero
un solo call site olvidado filtra datos "borrados" hacia un usuario — es exactamente el tipo de
error silencioso que un mecanismo automático evita. SQLAlchemy 2.0 (ya la versión instalada,
`SQLAlchemy==2.0.50` en `backend/requirements.txt:29`, confirmado) soporta
`sqlalchemy.orm.with_loader_criteria` combinado con el evento `do_orm_execute` de `Session`
para inyectar un criterio WHERE automáticamente en toda consulta ORM contra una clase marcada —
tanto `Session.query()` (API legacy, la que usa todo el proyecto hoy) como `select()` ejecutados
vía `Session.execute()` lo respetan, porque `Query` internamente delega a `Session.execute()` en
SQLAlchemy 1.4+/2.0.

**Diseño concreto:**
- `backend/app/models/models.py` — nuevo mixin:
  ```python
  class SoftDeleteMixin:
      deleted_at = Column(DateTime(timezone=True), nullable=True)
  ```
  Aplicado como mixin adicional en `User`, `Account`, `Category`, `Transaction`, `Budget`
  (`class Account(Base, SoftDeleteMixin):`, etc. — **no** en `RefreshToken`,
  `PasswordResetToken`, `EmailVerificationToken`, ver Decisión 6.3).
- `backend/app/core/database.py` — registrar el filtro global una sola vez, junto a la
  definición de `Base`/`SessionLocal` (para que aplique sin importar el entrypoint: app real,
  `seed.py`, o los tests que usan `TestClient`):
  ```python
  from sqlalchemy import event
  from sqlalchemy.orm import Session, with_loader_criteria
  from app.models.models import SoftDeleteMixin  # cuidado con el import circular — ver riesgo abajo

  @event.listens_for(Session, "do_orm_execute")
  def _filtrar_borrados_logicos(execute_state):
      if execute_state.is_select and not execute_state.is_column_load:
          execute_state.statement = execute_state.statement.options(
              with_loader_criteria(SoftDeleteMixin, lambda cls: cls.deleted_at.is_(None), include_aliases=True)
          )
  ```
  **Riesgo de import circular a resolver en la implementación:** `database.py` define `Base`,
  y `models.py` importa `Base` desde `database.py` — registrar el evento en `database.py`
  importando `SoftDeleteMixin` desde `models.py` invierte esa dependencia. Alternativas: (a)
  mover `SoftDeleteMixin` a `database.py` junto a `Base` (más simple, y `SoftDeleteMixin` no
  tiene ninguna razón de dominio para vivir en `models.py` en vez de al lado de `Base`); o (b)
  registrar el evento en `main.py` en vez de `database.py`, después de importar `models` —
  pero eso dejaría el filtro sin aplicar en cualquier script que use `SessionLocal` sin pasar
  por `main.py` (`seed.py`, y potencialmente los tests si no importan `app.main`). **Se
  recomienda (a):** mover `SoftDeleteMixin` a `database.py`.
- **Aplicación a UPDATE/DELETE vía Core, no solo SELECT:** las tres actualizaciones de saldo en
  `transactions.py` (`db.execute(update(models.Account).where(...).values(balance=...))`,
  líneas 59-63, 134-138, 200-215) son statements `update()` ORM-enabled ejecutados vía
  `db.execute()` — `with_loader_criteria` también aplica a UPDATE/DELETE ORM-enabled desde
  SQLAlchemy 1.4, no solo a SELECT. **Esto debe verificarse empíricamente con un test antes de
  confiar en ello** (ver "Testing" abajo) — es la pieza de mayor riesgo de este ítem: si por
  algún motivo no aplica en la versión/configuración exacta del proyecto, una transacción cuya
  cuenta fue soft-deleted seguiría mutando el saldo de una cuenta "borrada", lo cual sería un
  bug de integridad, no solo de visibilidad.
- **No se construye ningún mecanismo para *ver* registros borrados** (ej. un parámetro
  `include_deleted`) — no hay ningún caso de uso hoy (no hay panel de administración ni
  "papelera" en el ROADMAP). Igual que el `jti` sin usar de Fase 7 (`docs/specs/fase_07_spec.md
  §2.5.1`), se deja la puerta cerrada hasta que un requisito real lo pida — YAGNI.

### Decisión de diseño 6.2 — el UNIQUE de `budgets` pasa a índice único parcial

El `UniqueConstraint("user_id", "category_id", "month", "year", ...)` de Fase 7
(`models.py:97-99`) opera sobre **todas** las filas, incluidas las soft-deleted. Sin cambiarlo,
borrar (lógicamente) el presupuesto de una categoría en un mes y crear uno nuevo para la misma
categoría/mes/año fallaría con un 400 espurio — la fila "borrada" seguiría ocupando el slot de
unicidad. Cambio necesario en `backend/app/models/models.py`, clase `Budget`:
```python
__table_args__ = (
    Index(
        "uq_budgets_user_category_period_active",
        "user_id", "category_id", "month", "year",
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    ),
)
```
(reemplaza el `UniqueConstraint` actual; requiere `import sqlalchemy as sa` o el import
puntual de `text`). Tanto PostgreSQL como SQLite soportan índices únicos parciales con
`WHERE` — no es una función exclusiva de un dialecto, así que no rompe el fallback a SQLite que
usa el desarrollo local sin Docker. El `try/except IntegrityError` de `crear_presupuesto`
(`budgets.py:46-54`, agregado en Fase 7 §1.4) sigue funcionando sin cambios — sigue siendo un
`IntegrityError` el que se dispara, solo cambia qué filas cuentan para la violación.

### Decisión de diseño 6.3 — los 3 modelos de token quedan fuera del borrado lógico

`RefreshToken`, `PasswordResetToken`, `EmailVerificationToken` ya tienen su propio mecanismo de
"apagado" de una sola vez: `revoked_at` (`RefreshToken`) o `used_at`
(`PasswordResetToken`/`EmailVerificationToken`), más `expires_at` para el apagado automático
por tiempo. Agregar `deleted_at` a estas tablas introduciría **dos** señales de "esta fila ya no
es válida" sobre el mismo registro (`revoked_at IS NOT NULL` vs. `deleted_at IS NOT NULL`), sin
que ninguna parte del código sepa cuál mirar — cada verificación existente ya filtra
explícitamente por `revoked_at.is_(None)` / `used_at.is_(None)` / `expires_at > now()`
(`auth.py:57-61`, `166-169`, `199-204`) — un filtro global de `deleted_at` no las simplifica, y
sí las puede complicar (¿un token "revocado" pero no "borrado" debería seguir contando para el
filtro global? Ambigüedad innecesaria). Tampoco se agrega `updated_at`: cada fila de estas
tablas se escribe una vez y se muta como máximo una vez (`revoked_at`/`used_at`), un timestamp
de "última modificación" no aporta información que `revoked_at`/`used_at`/`expires_at` no den
ya. Se dejan estas 3 tablas exactamente como están.

### Decisión de diseño 6.4 — los guards de borrado existentes (cuenta/categoría con transacciones) no se relajan en Fase 8

Hoy `eliminar_cuenta` (`accounts.py:83-99`) y `eliminar_categoria` (`categories.py:72-99`)
bloquean el borrado si existen transacciones/presupuestos asociados — una restricción que
existe para no dejar filas huérfanas con una FK apuntando a nada, un problema real con hard
delete. Con borrado lógico, ese problema técnico desaparece (la fila "borrada" sigue
físicamente ahí, la FK sigue siendo válida) — pero **no se recomienda relajar estos guards en
este ítem**: una cuenta soft-deleted que sigue apareciendo referenciada en transacciones
visibles se mostraría en el frontend como una cuenta "fantasma" (`transactions/page.tsx` y
`accounts/[id]/page.tsx` no tienen hoy ningún manejo de "cuenta eliminada mostrada en el
historial de una transacción viva") — es trabajo de UI no trivial y no pedido por el ROADMAP.
Los 4 endpoints `DELETE` cambian de `db.delete(obj)` a `obj.deleted_at = datetime.now(UTC)`,
pero **mantienen exactamente los mismos guards previos** (mismas condiciones, mismos mensajes
de error). Relajarlos queda como una mejora de producto explícita a evaluar en una fase
posterior, no una consecuencia automática de este ítem.

### Backend

**Archivos a modificar:**
- `backend/app/models/models.py`:
  - `SoftDeleteMixin` se **mueve** a `database.py` (Decisión 6.1) — no se define aquí.
  - `User`, `Account`, `Category`, `Transaction`, `Budget`: heredar de `SoftDeleteMixin` además
    de `Base`, y agregar
    `updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())`
    a cada uno.
  - `Budget.__table_args__`: reemplazo descrito en Decisión 6.2.
- `backend/app/core/database.py`: mover `SoftDeleteMixin` aquí, registrar el evento
  `do_orm_execute` (Decisión 6.1).
- `backend/app/api/accounts.py::eliminar_cuenta` (líneas 83-99): cambiar
  `db.delete(cuenta); db.commit()` por `cuenta.deleted_at = datetime.now(UTC); db.commit()`
  (requiere importar `datetime, UTC` — no están importados hoy en este archivo). Mismos guards
  previos sin cambios (líneas 87-95).
- `backend/app/api/categories.py::eliminar_categoria` (líneas 72-99): mismo patrón —
  `categoria.deleted_at = datetime.now(UTC)` en vez de `db.delete(categoria)`. Mismos guards.
- `backend/app/api/budgets.py::eliminar_presupuesto` (líneas 76-86): mismo patrón —
  `presupuesto.deleted_at = datetime.now(UTC)`.
- `backend/app/api/transactions.py::eliminar_transaccion` (líneas 119-147): mismo patrón para
  la transacción — `transaccion.deleted_at = datetime.now(UTC)` en vez de `db.delete(transaccion)`
  (línea 141). **La reversión del saldo de la cuenta (líneas 128-138) no cambia** — sigue
  siendo un ajuste real sobre `Account.balance`, borrar lógicamente la transacción no debe
  dejar de revertir su impacto contable.

**Migración:** incluida en la migración única de Fase 8 (§0.1): agrega `updated_at` y
`deleted_at` a las 5 tablas de dominio, y reemplaza el índice único de `budgets` por el parcial
de la Decisión 6.2 (`op.drop_constraint("uq_budgets_user_category_period", ...)` +
`op.create_index(..., unique=True, postgresql_where=..., sqlite_where=...)`).

### Frontend

**No aplica ningún cambio.** El borrado lógico es invisible para el frontend por diseño — los
endpoints `DELETE` devuelven la misma respuesta (`{"estado": "OK", ...}`) y los recursos
"borrados" simplemente dejan de aparecer en cualquier `GET`, igual que hoy con el hard delete.
Ningún componente necesita saber que el mecanismo cambió por debajo.

**Testing:** este es el ítem con más riesgo real de este documento (filtro global aplicado
donde no se espera, o no aplicado donde sí se espera) — el suite debe cubrir ambas direcciones:
- Borrar (lógicamente) una cuenta/categoría/transacción/presupuesto hace que deje de aparecer
  en el `GET` correspondiente para ese usuario.
- **Verificación específica del riesgo señalado en la Decisión 6.1:** crear una transacción,
  borrarla lógicamente, y confirmar que el saldo de la cuenta sigue reflejando la reversión
  contable (es decir, que el `UPDATE` de balance en `eliminar_transaccion` no fue bloqueado ni
  alterado por el filtro global — el filtro debe aplicar a las *lecturas* de `Transaction`, no
  impedir el `UPDATE` sobre `Account`, que es una tabla distinta).
- Crear un presupuesto, borrarlo lógicamente, crear uno nuevo para la misma
  categoría/mes/año — debe funcionar sin 400 (verifica la Decisión 6.2, el índice parcial).
- Un usuario no puede ver, editar ni "revivir" un recurso borrado de otro usuario (no es un
  caso nuevo, pero vale la pena confirmarlo con el mecanismo nuevo activo).
- `updated_at` cambia al editar (`PUT`) una cuenta/categoría/transacción/presupuesto, y no
  cambia con operaciones de solo lectura.

---

## Resumen de archivos tocados por sección

| Sección | Backend | Migración | Frontend |
|---|---|---|---|
| 1. `monthly_income` | `models.py`, `schemas.py`, `api/users.py` (nuevo `PATCH /me`) | Incluida en migración única | `types/api.ts` (solo tipos) |
| 2. `payment_method` | `models.py`, `schemas.py`, `api/transactions.py` (`actualizar_transaccion`) | Incluida en migración única | `types/api.ts` (solo tipos) |
| 3. Presupuestos recurrentes | `models.py`, `schemas.py`, `core/budget_recurrence.py` (nuevo), `api/budgets.py`, `api/dashboard.py` | Incluida en migración única (junto con §6) | `types/api.ts`, `app/(dashboard)/budgets/page.tsx` |
| 4. Categorías default | `main.py` (`DEFAULT_CATEGORIES`, `LEGACY_DEFAULT_CATEGORY_NAMES`) | Ninguna | — |
| 5. Cuenta por defecto | `api/users.py::crear_usuario` | Incluida en migración única (backfill opcional, Decisión 5.2) | — |
| 6. `updated_at` + borrado lógico | `models.py` (mixin movido a `database.py`), `core/database.py` (evento global), `api/accounts.py`, `api/categories.py`, `api/budgets.py`, `api/transactions.py` | Migración única (junto con §3) | — |

---

## Cierre

Este documento no implementa ningún cambio en el repositorio — es el desglose ejecutable de la
sección "Fase 8" de `docs/ROADMAP.md`, con archivos, funciones, líneas y decisiones de diseño
concretas para que quien codee (backend-engineer para las secciones 1–6 backend/migración,
frontend-engineer para la sección 3 frontend y los ajustes de tipos de las secciones 1–2) pueda
partir directamente de aquí sin tener que re-explorar el código para tomar las mismas
decisiones. Ningún archivo del repositorio fuera de `docs/specs/fase_08_spec.md` fue modificado
al producir este documento.
