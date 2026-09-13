# Spec — Fase 22: Onboarding moneda-primero, salario editable y claridad de cuentas Google

> Plan de implementación detallado para los ítems de Fase 22 del [ROADMAP](../ROADMAP.md).
> Fuente de verdad de alcance: `docs/ROADMAP.md` (sección "Fase 22 — Onboarding moneda-primero,
> salario editable y claridad de cuentas Google", decidida en sesión de grilling del
> 2026-09-13). Este documento no cambia el alcance ahí definido — lo desglosa en tareas
> ejecutables, con archivos concretos y decisiones de diseño numeradas, separadas en
> Backend/Frontend por ítem para que agentes `backend-engineer`/`frontend-engineer` distintos
> puedan tomar cada mitad en paralelo.
>
> **No implementa nada.** Ningún archivo del repositorio fuera de `docs/ROADMAP.md` y
> `docs/specs/fase_22_spec.md` fue modificado al producir este documento. Los hallazgos fueron
> verificados directamente contra `backend/` y `frontend/` el 2026-09-13 (lectura de
> `models.py`, `schemas.py`, `users.py`, `auth.py`, `preferences.py`,
> `OnboardingIncomeStep.tsx`, `app/capture/page.tsx`, `TransactionCaptureForm.tsx`,
> `settings/page.tsx`, `types/api.ts`), no inferidos del texto del ROADMAP.

Estado del repo al momento de escribir esto (2026-09-13): Fases 7–21 completas. Fase 22 nace de
cuatro observaciones del dueño del proyecto tras usar el producto ya con login con Google
(Fase 20) y el selector de moneda de Settings (Fase 21) en producción.

---

## Hallazgos de exploración que corrigen/precisan el ROADMAP

1. **La categoría "no vi selección de categorías en el onboarding" no es un bug — es una
   decisión explícita de Fase 18 que el dueño del proyecto no recordaba.**
   `docs/specs/fase_18_spec.md` §18.2, Decisión 18.2.1 (Q2/Q3): *"no hay pantalla nueva; el
   registro pre-siembra `hidden_categories` con el complemento del set base"* y *"Ningún cambio
   (Decisión Q3 — `register/page.tsx` y `app/capture/page.tsx` no se tocan)."* La implementación
   real es server-only: `backend/app/api/users.py` (dentro de
   `inicializar_datos_usuario_nuevo`) siembra `HiddenCategory` para cada categoría de sistema
   fuera de `BASE_REGISTRATION_CATEGORY_NAMES` (`backend/app/core/default_categories.py`). El
   editor real vive en `frontend/app/(dashboard)/categories/page.tsx`
   (`CUSTOM_CATEGORY_EDITING_ENABLED = true` desde Fase 18) — una pantalla post-onboarding, no
   parte del wizard. Confirmado con el dueño del proyecto en la sesión de grilling: se reafirma
   la decisión de Fase 18 tal cual, sin ningún cambio de código para este punto.

2. **`monthly_income` no tiene moneda propia — se interpreta contra `User.preferred_currency`,
   que nunca se pregunta en el onboarding.** `backend/app/models/models.py`:
   `User.monthly_income = Column(Numeric(14, 2), nullable=True)` sin columna de moneda propia;
   `User.preferred_currency = Column(String(3), default="COP")` es el campo que ya existe y
   sirve para esto. `frontend/components/forms/OnboardingIncomeStep.tsx` pide el ingreso con
   `placeholder="Ej. 3000000"` (escala COP hardcodeada) sin ofrecer ni mencionar moneda en
   ningún punto del wizard (`frontend/app/capture/page.tsx`).

3. **No existe ninguna lista curada o `Enum` de monedas en el código — es 100% texto libre.**
   `grep` sobre `currency`/`preferred_currency` en `backend/app/schemas/schemas.py` (líneas
   88, 99, 135, 188, 229, 263, 284, 302): siempre `str`, nunca validado contra una lista. Mismo
   precedente que la Decisión 17.2.4 (selector de moneda de presupuestos, Fase 17) y el
   Hallazgo 6 de Fase 21: cuando existe una lista de opciones en la UI, se deriva de datos reales
   (cuentas del usuario) — pero al momento del onboarding el usuario todavía no tiene cuentas, así
   que no hay de dónde derivarla. Se decidió en la sesión de grilling una lista fija de 5:
   **COP, USD, EUR, MXN, ARS**.

4. **La cuenta por defecto ya lee `preferred_currency`, pero se crea *antes* de que el usuario
   pueda elegirla en el wizard — hay un desfase de timing real, no solo cosmético.**
   `backend/app/api/users.py`, función `inicializar_datos_usuario_nuevo` (compartida entre
   registro por contraseña y registro por Google, Fase 20 §20.3 Hallazgo 4):
   ```python
   cuenta_por_defecto = models.Account(
       name="Cuenta principal",
       type="debit",
       balance=Decimal("0.00"),
       currency=usuario.preferred_currency or "COP",
       user_id=usuario.id,
       highlighted=True,
   )
   ```
   Esto corre en el mismo commit que la creación del `User`, en el endpoint de registro — antes
   de que exista ninguna oportunidad de que el frontend le pregunte la moneda al usuario (el
   wizard de onboarding vive en una ruta aparte, `/capture?onboarding=1`, a la que se llega
   *después* del registro). Si el nuevo paso de moneda del onboarding solo hiciera `PATCH` de
   `preferred_currency`, la cuenta por defecto quedaría igual en el default `"COP"` sin importar
   qué elija el usuario.

5. **`UserResponse` no expone ninguna señal de que una cuenta sea Google-only.**
   `backend/app/schemas/schemas.py` (`UserResponse`): `id, email, full_name, preferred_currency,
   preferred_locale, preferred_theme, monthly_income, has_transaction_history` — sin `google_id`
   ni ningún booleano derivado. El modelo `User` sí tiene `google_id`
   (`backend/app/models/models.py`), pero nunca se serializa. `frontend/types/api.ts` (interfaz
   `UserResponse`) refleja exactamente los mismos campos — el frontend no tiene, hoy, ninguna
   forma de saber client-side si el usuario logueado es Google-only.

6. **El backend ya trata la contraseña como opcional para cuentas Google-only en las dos
   acciones que la piden — el frontend es el que no lo refleja.**
   - Login (`backend/app/api/auth.py`, `login()`): `if not user or user.password_hash is None:
     raise 403` — mensaje genérico, no revela el estado Google-only (anti-enumeración).
   - Borrado de cuenta (`backend/app/api/users.py`, alrededor de la línea 147): la contraseña
     solo se valida `if current_user.password_hash is not None and not verify_password(...)` —
     para una cuenta Google-only (`password_hash is None`) el chequeo se salta por completo,
     cualquier valor en el campo (incluido vacío) pasa. El único lugar del frontend con un campo
     de contraseña visible es exactamente ese modal de borrado
     (`frontend/app/(dashboard)/settings/page.tsx`, modal "Eliminar mi cuenta") — sin ninguna
     mención a Google ni chequeo de `google_id` en el archivo.

7. **"Olvidé mi contraseña" no tiene ningún caso especial para cuentas Google-only — y el efecto
   final es crear una cuenta híbrida sin avisar.** `backend/app/api/auth.py`:
   - `solicitar_restablecimiento_contrasena`: solo verifica que exista un `User` con ese email
     (sin mirar `password_hash`) y manda el correo de reset igual para cuentas Google-only.
   - `confirmar_restablecimiento_contrasena`: hace `user.password_hash =
     security.get_password_hash(body.new_password)` sin condicionar a si ya tenía una — para una
     cuenta Google-only, esto la convierte en cuenta híbrida (Google + password) sin ningún aviso
     en ningún punto del flujo.
   Esto es exactamente lo que `docs/specs/fase_20_spec.md` (sección "Fuera de alcance") dejó
   pendiente sin diseñar: *"un flujo para que una usuaria que se registró con Google, después,
   defina una contraseña"* — nunca se construyó explícitamente, pero ya ocurre como efecto
   secundario no documentado de "olvidé mi contraseña".

---

## Decisiones de diseño

### A — Onboarding moneda-primero

**A1. Nuevo micro-paso de moneda, antes de `OnboardingIncomeStep`, dentro del mismo wizard
(`app/capture/page.tsx`).** No se agrega a `register/page.tsx` — mantiene el registro
minimalista que Fase 15 diseñó a propósito (email + password + nombre, nada más). El paso
nuevo hace un solo `PATCH` de `preferred_currency` (mismo endpoint que ya usa el selector de
Settings de Fase 21, `PATCH /api/v1/users/me/preferences`) contra una lista fija: **COP, USD,
EUR, MXN, ARS** (Hallazgo 3).

- *Alternativa descartada:* preguntar la moneda en `register/page.tsx`. Rompe el principio de
  registro corto de Fase 15 sin necesidad — el wizard de `/capture` ya es el lugar donde vive
  toda la personalización post-registro (ingreso, primera transacción).

**A2. Cascada a la cuenta por defecto, resolviendo el desfase de timing del Hallazgo 4.** Al
completar el paso de moneda, además del `PATCH` de `preferred_currency`, actualizar la moneda
de la cuenta por defecto que ya se creó en el registro. Guardar la actualización a que la
cuenta:
- se llame `"Cuenta principal"` (el nombre fijo que le pone `inicializar_datos_usuario_nuevo`),
- tenga `balance == 0`,
- no tenga ninguna `Transaction` asociada,

para no tocar nunca una cuenta que el usuario ya haya usado de alguna forma entre el registro y
este paso (ventana corta, pero no nula — el flujo permite refrescar a mitad del wizard, Decisión
15.0.1/15.3.2 ya documentada). Si alguna de esas condiciones no se cumple, no tocar la cuenta y
dejar que el usuario la corrija manualmente en Cuentas — igual que hoy.

- *Alternativa descartada:* mover la pregunta de moneda al registro (evita el desfase de raíz,
  pero reabre el problema de A1). Se prefiere el guard sobre la cascada porque es una condición
  barata de verificar y la ventana de riesgo es mínima.

**A3. El placeholder/símbolo del paso de ingreso se ajusta a la moneda elegida.** En vez del
`"Ej. 3000000"` hardcodeado, `OnboardingIncomeStep.tsx` recibe la moneda ya elegida (del paso
anterior o de `user.preferred_currency`) y ajusta el placeholder a una escala razonable para esa
moneda (p. ej. `"Ej. 3000"` para USD/EUR). No hace falta un mapa de tasas de cambio — son solo
placeholders de UI, no cálculos.

### B — Categorías en el onboarding: sin cambios

**B1. Se reafirma la Decisión 18.2.1 de Fase 18 tal cual está.** Confirmado con el dueño del
proyecto en esta misma sesión de grilling (Hallazgo 1): no se agrega ninguna pantalla de
selección de categorías al wizard de onboarding. El mecanismo actual (pre-siembra silenciosa de
`hidden_categories` + editor en `/categories`) se mantiene sin cambios. No hay tareas de
implementación para este punto — se documenta aquí solo para que quede registrada la
reconsideración y su resultado.

### C — Salario editable en Configuración

**C1. Exponer `monthly_income` en `/settings`, reusando el endpoint y el hook existentes.** El
backend (`PATCH users/me`) y el hook de frontend (`useSetMonthlyIncome.ts`) ya existen — los usa
`OnboardingIncomeStep.tsx`. La tarea es agregar un campo/sección en
`frontend/app/(dashboard)/settings/page.tsx` que reutilice ese mismo hook para editar el valor
ya fijado.

**C2. Alcance: solo el valor actual, sin historial.** Decidido explícitamente en la sesión de
grilling — `monthly_income` sigue siendo un único valor sin versionar por mes, igual que hoy.
Un historial de ingresos por mes es una feature de alcance mucho mayor y no la que se pidió
("poder corregir el salario porque puede cambiar").

### D — Claridad de cuentas Google-only

**D1. Nuevo campo `has_password: bool` en `UserResponse`, computado (sin migración).** Se
agrega a `backend/app/schemas/schemas.py` (`UserResponse`) y se calcula en el endpoint
correspondiente (`GET/PATCH /users/me` en `backend/app/api/users.py`) como
`current_user.password_hash is not None` — no requiere ningún cambio de modelo ni de Alembic,
es puramente una proyección del campo que ya existe.

- *Alternativa descartada:* exponer `google_id` directamente. Es más información de la
  necesaria (el frontend no necesita saber el ID de Google, solo si hay contraseña) y acopla el
  contrato de la API a un detalle de implementación de un solo proveedor OAuth.

**D2. Usar `has_password` para ocultar/aclarar el campo de contraseña en el modal de "Eliminar
mi cuenta" (`settings/page.tsx`).** Cuando `has_password === false`, el modal no debe pedir ni
mostrar el campo de contraseña — el backend ya no lo valida en ese caso (Hallazgo 6), así que
pedirlo solo genera confusión sin aportar ninguna fricción real de seguridad.

**D3. "Olvidé mi contraseña" para cuentas Google-only: se deja funcionar como ya funciona,
con copy aclaratorio en la página de confirmación.** Decidido en la sesión de grilling, entre
tres opciones:
- **(a) — elegida.** Dejar el flujo tal cual (Hallazgo 7: ya crea `password_hash` y deja la
  cuenta como híbrida) y solo agregar texto explícito en `reset-password/page.tsx` explicando
  que se le está creando una contraseña a una cuenta que hasta ahora solo usaba Google, y que
  podrá usar cualquiera de los dos métodos de ahí en adelante. Sin cambios de backend — el texto
  puede ser genérico (no necesita `has_password`, porque en este punto el usuario ya está
  identificado por el token de reset, no por sesión).
- (b) descartada: bloquear el reset para cuentas Google-only. Le quita al usuario una capacidad
  que hoy ya tiene y que es legítima (agregar un segundo método de acceso a su cuenta), sin
  ningún beneficio de seguridad claro.
- (c) descartada: construir un flujo explícito de "definir contraseña" desde Settings en lugar
  de reusar "olvidé mi contraseña". Es más trabajo para lograr el mismo resultado que (a), a
  menos que en el futuro se prefiera iniciarlo desde Settings en vez del login — no es el caso
  pedido en esta sesión.

---

## Decisiones de arquitectura (evaluadas por `software-architect` el 2026-09-13)

Las Decisiones de diseño A1–D3 fijaron el alcance de producto. Quedaron cuatro preguntas de
implementación sin resolver, que esta sección cierra contra el código real — se numeran A4–A6 y
D4 porque extienden directamente a A2/A1/A3 y D1 respectivamente, no porque abran una línea de
producto nueva.

**A4 — El gating del nuevo paso de moneda es estado local efímero del wizard (`useState`,
sin señal de servidor), igual que ya hace `OnboardingIncomeStep`.** `User.preferred_currency`
tiene `default="COP"` (`backend/app/models/models.py:25`) — nunca es `NULL`, así que la condición
que usa hoy `OnboardingIncomeStep` (`user?.monthly_income == null`, `frontend/app/capture/
page.tsx:26`) no tiene equivalente para moneda: no existe ningún valor de `preferred_currency`
que signifique "todavía no lo eligió". No hace falta inventar uno: el propio `page.tsx:22-24`
ya documenta y acepta el mismo riesgo para el paso de ingreso ("un refresh a mitad del wizard
puede volver a mostrar el paso... edge case aceptado") — el paso de moneda es idéntico en
naturaleza (una pantalla más del mismo wizard de un solo uso, no una decisión que sobreviva
sesiones) y hereda el mismo criterio: un `useState` local (`currencyStepDone`) que se pierde en
un refresh, sin persistir nada en el backend. Esto es deliberadamente distinto del mecanismo de
`has_transaction_history` (Fase 19, Decisión 19.1.1): ese campo decide el destino de un
**login futuro, en una sesión distinta** (por eso necesita sobrevivir en el backend), mientras
que el paso de moneda solo necesita no repetirse **dentro de la misma visita** al wizard — un
problema de alcance mucho más chico que no justifica un campo nuevo en `UserResponse` ni un
`PATCH` adicional solo para marcarlo "visto".

**A5 — La cascada es un solo `PATCH /api/v1/users/me/preferences`, con el guard y la escritura
de la cuenta en la misma transacción del handler — no una segunda llamada HTTP.** La Decisión A1
ya fija "un solo `PATCH`" como parte del alcance; lo que faltaba resolver es cómo ese único
`PATCH` también cascadea sin convertirse en dos escrituras separables. Se agrega un campo opcional
a `PreferencesUpdate` (`backend/app/schemas/schemas.py:98-102`), `apply_to_default_account: bool
= False`, que por defecto es `False` — el selector de Settings (`frontend/app/(dashboard)/
settings/page.tsx:214-231`, ya en producción desde Fase 21) sigue llamando el mismo endpoint sin
este campo y su comportamiento no cambia en absoluto. Cuando el body lo trae en `True`, el mismo
handler (`backend/app/api/preferences.py:22-38`) evalúa el guard de la Decisión A2 (nombre
`"Cuenta principal"`, `balance == 0`, sin `Transaction` asociada) y aplica el `UPDATE` de
`Account.currency` **antes** del único `db.commit()` que ya existe al final de la función — mismo
criterio de atomicidad que `delete_user_cascade` (Fase 21, Decisión A6: "todos los `.delete()`
seguidos de un único `db.commit()` final, sin commits intermedios"). Evaluar el guard y escribir
en el mismo request, antes del mismo commit, cierra la ventana TOCTOU que pedía la pregunta de
arquitectura: no hay ningún punto entre "leer si la cuenta todavía es virgen" y "escribirle la
moneda" donde otra request pueda colarse a mitad de camino.

- *Alternativa descartada:* un segundo endpoint (`PATCH /api/v1/accounts/{id}`) llamado desde el
  frontend después del `PATCH` de preferencias. Reabre exactamente el problema que la pregunta de
  arquitectura señala: dos requests HTTP no comparten transacción, así que un fallo de red entre
  ambas deja `preferred_currency` actualizado y la cuenta por defecto en la moneda vieja — un
  estado a medias que el guard de un solo handler evita por construcción.

**A6 — El frontend no espera a que la invalidación de cache repueble `preferred_currency` para
pintar el paso de ingreso; el wizard pasa la moneda elegida como prop explícita entre pasos, y
la invalidación solo sirve para que el resto de la app (fuera del wizard) quede consistente.**
Encontrado al diseñar el flujo: `useUserPreferences.ts:43-58` invalida con `invalidateQueries`
(asíncrono — dispara un refetch, no escribe la cache de inmediato), así que si
`OnboardingIncomeStep` leyera `user?.preferred_currency` de `useCurrentUser()` inmediatamente
después de que el paso de moneda hace `onDone()`, podría renderizar todavía con el valor viejo
por una fracción de segundo (mismo tipo de carrera que el propio Hallazgo 8 de Fase 21 describe
para `categoryBreakdown`, aplicado ahora a un prop en vez de a un gráfico). En vez de depender de
esa carrera, `OnboardingCurrencyStep` devuelve la moneda elegida directamente al padre
(`onDone(currency: string)`), y `app/capture/page.tsx` la guarda en un `useState` propio
(`selectedCurrency`) que se pasa como prop a `OnboardingIncomeStep` — mismo patrón que el wizard
ya usa para pasar `incomeStepDone` entre pasos, sin cache de por medio. La invalidación de
`queryClient` sigue haciendo falta, pero para un problema distinto: que **otras pantallas**
(Settings, el dashboard al que se llega después del wizard) vean la cuenta y la preferencia
actualizadas sin depender del estado efímero del wizard. Ver Decisión 22.1.4 para el detalle de
qué keys invalidar.

**D4 — `has_password` se computa en `UserResponse` vía un `model_validator(mode="before")`, no
copiando el patrón de asignación manual por endpoint que ya usa `has_transaction_history`.** La
Decisión D1 (ya settled) dice en una frase que se calcula "en el endpoint correspondiente", pero
seguir esa frase al pie de la letra reproduce un bug: `has_transaction_history` puede confiar en
un `default=False` en el schema (`schemas.py:92`) porque la Decisión 19.1.3 verificó que **para
los tres endpoints que devuelven `UserResponse`** (`crear_usuario`, `obtener_usuario_actual`,
`actualizar_perfil`, `backend/app/api/users.py:79,104,116`) un usuario recién creado o que solo
actualiza su perfil nunca tiene 2+ transacciones — el default es semánticamente correcto incluso
sin calcularlo ahí. Esa garantía no existe para `has_password`: un usuario que se acaba de
registrar por contraseña (`crear_usuario`) **sí tiene** `password_hash` desde el primer instante
(`users.py:87`), así que un default `False` sin cómputo explícito devolvería `has_password: false`
para la respuesta del registro mismo — exactamente al revés de la realidad, no una limitación
documentada como la de 19.1.3, sino un dato incorrecto en el primer response que ve un usuario
nuevo. Como `password_hash` (a diferencia del conteo de transacciones) ya está cargado en el
objeto `User` sin ninguna query adicional, no hay motivo para repetir la asignación en cada
endpoint: un validador a nivel de schema lo resuelve una sola vez para los tres callers actuales
y para cualquier endpoint futuro que devuelva `UserResponse` desde un objeto `User` ORM, sin
volver a tocar `users.py`.

```python
# backend/app/schemas/schemas.py — UserResponse
class UserResponse(UserBase):
    id: int
    preferred_currency: str = "COP"
    preferred_locale: str = "es-CO"
    preferred_theme: str = "dark"
    monthly_income: Decimal | None = None
    has_transaction_history: bool = False
    has_password: bool = False  # 🆕 Fase 22 §22.4 (Decisión D4)

    @model_validator(mode="before")
    @classmethod
    def _compute_has_password(cls, data):
        # Solo cubre el path real hoy: los tres endpoints de users.py devuelven el objeto
        # ORM `User` directamente (from_attributes=True), nunca un dict armado a mano —
        # mismo path que ya usa `TransactionResponse._categoria_relacion_orm_a_none`
        # (schemas.py:163-175) como precedente de validador "before" sobre datos crudos
        # del ORM, aunque ahí es field_validator porque solo lee el campo que transforma;
        # acá hace falta model_validator porque lee un atributo (`password_hash`) distinto
        # del que expone (`has_password`).
        if hasattr(data, "password_hash"):
            data.has_password = data.password_hash is not None
        return data

    class Config:
        from_attributes = True
```

- *Alternativa descartada:* asignar `current_user.has_password = current_user.password_hash is
  not None` en cada uno de los tres endpoints de `users.py`, calcada de `has_transaction_history`.
  Descartada por la razón de arriba: para este campo específico, ese patrón produce un dato
  incorrecto en `crear_usuario` si alguien lo olvida ahí (a diferencia de
  `has_transaction_history`, donde el default ya es correcto sin cómputo). Un validador de
  schema no depende de que cada caller recuerde asignarlo.

Consecuencia directa: **ningún archivo de `backend/app/api/users.py` cambia por D1/D2 en esta
fase** — el único cambio de backend para "claridad de cuentas Google" es `schemas.py`. Esto
disuelve la colisión que anticipaba la nota de coordinación del documento original ("A2 y D1/D2
tocan `backend/app/api/users.py`"): A2/A5 terminan en `backend/app/api/preferences.py`, D1/D4
terminan en `backend/app/schemas/schemas.py` — ningún ítem de esta fase vuelve a tocar
`users.py`. El único archivo de backend que dos ítems tocan a la vez es `schemas.py` (A1 agrega un
campo a `PreferencesUpdate`, D4 agrega uno a `UserResponse`) — ver "Orden de ejecución" para cómo
secuenciarlo.

---

## Orden de ejecución recomendado

```
1. Backend: PreferencesUpdate.apply_to_default_account + cascada en preferences.py (§22.1)
   ── Independiente de todo lo demás. Toca schemas.py (PreferencesUpdate) y preferences.py.

2. Backend: UserResponse.has_password vía model_validator (§22.4)
   ── Independiente de (1) a nivel lógico — pero AMBOS tocan schemas.py. Si es el mismo
      agente backend, no importa el orden (son clases distintas del mismo archivo). Si son
      dos agentes backend en paralelo, no hace falta serializarlos en dos PRs — alcanza con
      que el segundo en mergear haga un rebase trivial (los cambios están en clases distintas
      de schemas.py, sin solapamiento de líneas real). No hace falta el "mismo PR secuencial"
      que sí exige, por ejemplo, la cascada de A5 dentro de preferences.py.

3. Frontend: OnboardingCurrencyStep.tsx + wiring en app/capture/page.tsx +
   ajuste de placeholder en OnboardingIncomeStep.tsx (§22.1)
   ── Depende de (1): sin `apply_to_default_account` en el contrato, no hay cascada que
      disparar. Puede empezarse en paralelo y dejar el `PATCH` real para el final.

4. Frontend: invalidación de accounts.all() en useUserPreferences.ts (§22.1, Decisión 22.1.4)
   ── Depende de (1) por el mismo motivo que (3); trivial una vez que el campo existe.
      Puede ir en el mismo cambio que (3).

5. Frontend: salario editable en settings/page.tsx (§22.3)
   ── Independiente de todo lo demás — reusa PATCH users/me y useSetMonthlyIncome.ts, que
      ya existen sin cambios. Puede hacerse en paralelo desde el día 1.

6. Frontend: campo has_password en types/api.ts + modal de borrado en settings/page.tsx (§22.4)
   ── Depende de (2): sin el campo real en el contrato, el frontend no tiene nada que leer.

7. Frontend: copy aclaratorio en reset-password/page.tsx (§22.5)
   ── Completamente independiente de todo lo demás — texto estático, sin dependencia de
      ningún campo nuevo (Decisión D3(a) ya fijó que es genérico). Puede hacerse en
      cualquier momento, incluso antes que el resto.
```

22.2 (categorías) no tiene tareas — ver sección propia. Resumen de dependencias reales: el
backend de 22.1 (paso 1) bloquea el frontend de 22.1 (pasos 3-4), igual que el backend de 22.4
(paso 2) bloquea su frontend (paso 6) — mismo patrón que Fase 19 estableció entre 19.1 backend y
frontend. 22.3, 22.5 y el backend de 22.1/22.4 no comparten ningún archivo entre sí y pueden
avanzar en paralelo desde el día 1.

---

## 22.1 Onboarding moneda-primero + cascada a la cuenta por defecto

### Backend

**Decisión 22.1.1 — `PreferencesUpdate` gana un campo opcional `apply_to_default_account: bool =
False` (Decisión A5).**

```python
# backend/app/schemas/schemas.py
class PreferencesUpdate(BaseModel):
    preferred_currency: str | None = None
    preferred_locale: str | None = None
    preferred_theme: str | None = None
    weekly_summary_enabled: bool | None = None
    apply_to_default_account: bool = False  # 🆕 Fase 22 §22.1 (Decisión A5) — no persiste
```

`apply_to_default_account` no es un campo de `User` ni de `Account`: es una instrucción de
"además, cascadeá" para esta request puntual — se excluye explícitamente de
`model_dump(exclude_none=True)` antes de iterar `setattr` sobre `current_user` (si no,
`setattr(current_user, "apply_to_default_account", True)` crearía un atributo fantasma en el
ORM sin efecto, ruido silencioso a evitar).

**Decisión 22.1.2 — el guard de la Decisión A2 se evalúa con una sola query, dentro del mismo
handler, antes del commit único que ya existe.**

```python
# backend/app/api/preferences.py
@router.patch("/me/preferences")
def update_preferences(
    prefs: schemas.PreferencesUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    update_data = prefs.model_dump(exclude={"apply_to_default_account"}, exclude_none=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)

    # Fase 22 §22.1 (Decisiones A2/A5): cascada opcional a la cuenta por defecto, en la
    # misma transacción — sin ventana entre "leer si la cuenta sigue virgen" y "escribirle
    # la moneda" (evita el TOCTOU que tendría una segunda request HTTP separada).
    if prefs.apply_to_default_account and prefs.preferred_currency:
        cuenta_virgen = (
            db.query(models.Account)
            .filter(
                models.Account.user_id == current_user.id,
                models.Account.name == "Cuenta principal",
                models.Account.balance == 0,
            )
            .first()
        )
        if cuenta_virgen is not None:
            tiene_transacciones = (
                db.query(models.Transaction.id)
                .filter(models.Transaction.account_id == cuenta_virgen.id)
                .first()
            )
            if tiene_transacciones is None:
                cuenta_virgen.currency = prefs.preferred_currency
        # Si el guard no pasa (nombre distinto, saldo != 0, o ya tiene transacciones):
        # no se toca la cuenta y no se informa error — `preferred_currency` del usuario
        # igual queda actualizado (Decisión A2: "dejar que el usuario la corrija
        # manualmente en Cuentas, igual que hoy").

    db.commit()
    db.refresh(current_user)
    return {
        "preferred_currency": current_user.preferred_currency,
        "preferred_locale": current_user.preferred_locale,
        "preferred_theme": current_user.preferred_theme,
        "weekly_summary_enabled": current_user.weekly_summary_enabled,
    }
```

Nótese que el selector de moneda de Settings (`frontend/app/(dashboard)/settings/page.tsx:214-
231`) sigue llamando este mismo endpoint sin `apply_to_default_account` en el body — Pydantic lo
completa con su default `False`, así que el bloque de cascada nunca se ejecuta para ese caller y
su comportamiento (ya en producción desde Fase 21) no cambia.

**Archivos a modificar:**
- `backend/app/schemas/schemas.py` (`PreferencesUpdate.apply_to_default_account`).
- `backend/app/api/preferences.py` (`update_preferences`, bloque de cascada).

**Testing:** no existe hoy `backend/tests/test_preferences.py` — crear uno nuevo (verificado:
`preferences.py` no tiene ningún test propio todavía, a diferencia de `users.py`/`auth.py`).
Casos, todos contra un usuario recién registrado (cuenta por defecto virgen del seed de
`inicializar_datos_usuario_nuevo`):
- `PATCH /users/me/preferences` con `preferred_currency` y `apply_to_default_account=true` sobre
  una cuenta que sigue siendo `"Cuenta principal"`, `balance=0`, sin transacciones: la cuenta por
  defecto (`GET /accounts/`) queda en la nueva moneda.
- Mismo caso pero la cuenta fue renombrada antes del PATCH: la cuenta **no** cambia de moneda,
  y la respuesta sigue siendo `200` con `preferred_currency` actualizado igual.
- Mismo caso pero la cuenta tiene una transacción asociada: la cuenta no cambia de moneda.
- Mismo caso pero `balance != 0` (ej. una transacción que después se borró y dejó saldo): la
  cuenta no cambia de moneda.
- `PATCH /users/me/preferences` con `preferred_currency` sin `apply_to_default_account` (o en
  `false`, el caso de Settings): la cuenta por defecto nunca cambia, aunque cumpla el guard —
  regresión explícita para que Settings nunca dispare la cascada sin pedirlo.
- Sin `preferred_currency` en el body pero `apply_to_default_account=true`: no revienta, no hace
  nada (el `if prefs.preferred_currency` de la Decisión 22.1.2 lo cubre).

### Frontend

**Decisión 22.1.3 — nuevo componente `frontend/components/forms/OnboardingCurrencyStep.tsx`,
mismo shape que `OnboardingIncomeStep.tsx` (props `{ onDone }`, mismo layout de
`Button`/`Input`/`ghost`+`primary`), con una lista fija de 5 monedas (Hallazgo 3):**

```tsx
// frontend/components/forms/OnboardingCurrencyStep.tsx
'use client';
import { useState } from 'react';
import Select from '@/components/ui/Select';
import Button from '@/components/ui/Button';
import { useUserPreferences } from '@/lib/hooks/useUserPreferences';

const CURRENCY_OPTIONS = ['COP', 'USD', 'EUR', 'MXN', 'ARS'] as const;

export default function OnboardingCurrencyStep({
  onDone,
}: {
  onDone: (currency: string) => void; // 🆕 Decisión A6 — el padre recibe el valor elegido
}) {
  const [currency, setCurrency] = useState<string>('COP');
  const { updatePreferences } = useUserPreferences();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await updatePreferences.mutateAsync({
      preferred_currency: currency,
      apply_to_default_account: true, // 🆕 única diferencia con el uso de Settings
    });
    onDone(currency);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      <h1 className="text-text font-sans text-xl font-bold tracking-tight">
        ¿En qué moneda manejás tus finanzas?
      </h1>
      <p className="text-text-muted text-sm">Podés cambiarla después desde Configuración.</p>
      <Select
        label="Moneda principal"
        value={currency}
        onChange={(e) => setCurrency(e.target.value)}
        className="bg-background"
      >
        {CURRENCY_OPTIONS.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </Select>
      <div className="flex gap-3 pt-2">
        <Button type="button" variant="ghost" onClick={() => onDone('COP')} className="flex-1">
          Omitir por ahora
        </Button>
        <Button
          type="submit"
          variant="primary"
          loading={updatePreferences.isPending}
          className="flex-1"
        >
          Continuar
        </Button>
      </div>
    </form>
  );
}
```

"Omitir por ahora" no hace `PATCH` — `preferred_currency` ya está en `"COP"` por default de
`User` (`models.py:25`), así que omitir es literalmente no escribir nada, mismo criterio que
`OnboardingIncomeStep` usa para su propio botón de omitir (no hace `setIncomeMutation` si se
omite).

**Decisión 22.1.4 — wiring en `app/capture/page.tsx`: el paso de moneda corre antes que el de
ingreso, y el valor elegido se pasa por prop (Decisión A6), no por cache.**

```tsx
// frontend/app/capture/page.tsx
import OnboardingCurrencyStep from '@/components/forms/OnboardingCurrencyStep'; // 🆕

function CaptureScreen() {
  // ...router, searchParams, isOnboarding, user sin cambios...

  const [currencyStepDone, setCurrencyStepDone] = useState(false); // 🆕
  const [selectedCurrency, setSelectedCurrency] = useState<string | null>(null); // 🆕
  const [incomeStepDone, setIncomeStepDone] = useState(false);

  const showCurrencyStep = isOnboarding && !currencyStepDone; // 🆕
  const showIncomeStep =
    isOnboarding && !showCurrencyStep && user?.monthly_income == null && !incomeStepDone;

  return (
    <div className="...">
      {showCurrencyStep ? (
        <OnboardingCurrencyStep
          onDone={(currency) => {
            setSelectedCurrency(currency);
            setCurrencyStepDone(true);
          }}
        />
      ) : showIncomeStep ? (
        <OnboardingIncomeStep
          currency={selectedCurrency ?? user?.preferred_currency ?? 'COP'} // 🆕
          onDone={() => setIncomeStepDone(true)}
        />
      ) : (
        // ...TransactionCaptureForm sin cambios...
      )}
    </div>
  );
}
```

**Decisión 22.1.5 — `OnboardingIncomeStep` recibe `currency` como prop nueva y ajusta el
placeholder (Decisión A3), sin mapa de tasas de cambio.**

```tsx
// frontend/components/forms/OnboardingIncomeStep.tsx
const PLACEHOLDER_BY_CURRENCY: Record<string, string> = {
  COP: 'Ej. 3000000',
  USD: 'Ej. 3000',
  EUR: 'Ej. 2800',
  MXN: 'Ej. 50000',
  ARS: 'Ej. 900000',
};

export default function OnboardingIncomeStep({
  currency, // 🆕
  onDone,
}: {
  currency: string; // 🆕
  onDone: () => void;
}) {
  // ...resto sin cambios...
  return (
    // ...
    <Input
      // ...resto de props sin cambios...
      placeholder={PLACEHOLDER_BY_CURRENCY[currency] ?? 'Ej. 3000000'}
    />
    // ...
  );
}
```

**Decisión 22.1.6 (invalidación, Decisión A6/A4) — `useUserPreferences.ts` invalida
`queryKeys.accounts.all()` cuando la cascada se pidió, además de lo que ya invalida hoy:**

```ts
// frontend/lib/hooks/useUserPreferences.ts
onSuccess: (_data, body) => {
  queryClient.invalidateQueries({ queryKey: queryKeys.userPreferences() });

  if (body.preferred_currency) {
    queryClient.invalidateQueries({ queryKey: queryKeys.currentUser() });
    queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.categoryBreakdown() });
  }
  if (body.apply_to_default_account) {
    // 🆕 Fase 22 §22.1 — la cuenta por defecto pudo cambiar de moneda server-side;
    // `accounts.all()` alimenta tanto el selector de Settings (Decisión 21.1.1) como
    // `OnboardingIncomeStep`/`TransactionCaptureForm`, que la leen del mismo cache
    // inmediatamente después de este paso.
    queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all() });
  }
  if (body.preferred_theme) {
    updateConfig({ theme: body.preferred_theme });
  }
},
```

**Archivos a modificar:**
- `frontend/components/forms/OnboardingCurrencyStep.tsx` (nuevo).
- `frontend/components/forms/OnboardingIncomeStep.tsx` (prop `currency` + placeholder).
- `frontend/app/capture/page.tsx` (wiring de los dos pasos).
- `frontend/lib/hooks/useUserPreferences.ts` (invalidación de `accounts.all()`).
- `frontend/types/api.ts`: `PreferencesUpdatePayload` — agregar
  `apply_to_default_account?: boolean;`.

**Testing:** sin suite de frontend (`docs/TODO.md`, sigue en backlog). Verificación manual: un
registro nuevo completo (`register/page.tsx` → `/capture?onboarding=1`) muestra primero el paso
de moneda, después el de ingreso con placeholder ajustado a la moneda elegida, después la captura
guiada; `GET /accounts/` tras completar ambos pasos muestra la cuenta "Cuenta principal" en la
moneda elegida (no en COP); elegir "Omitir por ahora" en el paso de moneda dejó la cuenta en COP
(sin cambios) y el paso de ingreso muestra el placeholder de COP; refrescar el navegador a mitad
del paso de moneda vuelve a mostrarlo (edge case aceptado, Decisión A4).

**Criterio de aceptación:**
- Un usuario nuevo elige su moneda antes de declarar su ingreso mensual, con una lista fija de 5
  opciones.
- La cuenta por defecto queda en la moneda elegida al terminar el wizard, salvo que ya haya sido
  modificada (renombrada, con saldo, o con transacciones) entre el registro y este paso.
- El selector de moneda de Settings (Fase 21) no cambia de comportamiento: sigue sin cascadear a
  ninguna cuenta.
- El placeholder del paso de ingreso refleja la moneda elegida, sin ningún cálculo de tasa de
  cambio.

---

## 22.2 Categorías en el onboarding: sin cambios

Ver Decisión B1 (ya settled): se reafirma la Decisión 18.2.1 de Fase 18 tal cual está. No hay
tareas de Backend ni de Frontend para este ítem — ningún archivo se toca. Se lista acá solo para
que el desglose de ítems de esta fase quede completo frente al checklist de 5 puntos del
ROADMAP.

---

## 22.3 Salario mensual editable en Configuración

### Backend

**Sin cambios de backend.** `PATCH /api/v1/users/me` (`actualizar_perfil`,
`backend/app/api/users.py:115-126`) ya acepta y persiste `monthly_income` sin restricciones
adicionales a las que ya valida `schemas.UserProfileUpdate` (`ge=0, decimal_places=2`,
`schemas.py:112`) — es el mismo endpoint que usa `useSetMonthlyIncome.ts` desde el onboarding
(Fase 15 §15.3.1) y desde la card inline del dashboard (Fase 11, Decisión 11.3.2). No hace falta
tocar `users.py` ni `schemas.py` para este ítem.

### Frontend

**Decisión 22.3.1 — nueva sección en `settings/page.tsx`, reusando literalmente
`useSetMonthlyIncome.ts` sin ningún cambio al hook.** A diferencia del selector de moneda y el
switch de resumen semanal (ambos "cambio = guardado" sin botón, Decisión 21.1.2), el salario es
un campo numérico de texto libre — pedir un `PATCH` en cada tecla sería ruidoso y generaría
`invalidateQueries` de sobra. Se usa el mismo patrón que el propio formulario de
`OnboardingIncomeStep.tsx` (`Input` + botón de submit explícito), no el patrón de los otros dos
controles de esta misma página.

```tsx
// frontend/app/(dashboard)/settings/page.tsx
import { useCurrentUser } from '@/lib/hooks/useCurrentUser'; // 🆕
import { useSetMonthlyIncome } from '@/lib/hooks/useSetMonthlyIncome'; // 🆕

// dentro de SettingsPage():
const { data: currentUser } = useCurrentUser(); // 🆕
const setMonthlyIncome = useSetMonthlyIncome(); // 🆕
const [incomeValue, setIncomeValue] = useState(''); // 🆕 — inicializado en un useEffect
// o con `key` remount cuando currentUser.monthly_income cambia de undefined a un valor,
// mismo problema ya resuelto en OnboardingIncomeStep con un input controlado simple.

const handleIncomeSubmit = (e: React.FormEvent) => {
  e.preventDefault();
  const parsed = Number(incomeValue);
  if (!incomeValue.trim() || Number.isNaN(parsed) || parsed < 0) return;
  setMonthlyIncome.mutate(parsed, {
    onSuccess: () => toast.success('Ingreso mensual actualizado.'),
    onError: (err) => toast.error(getApiError(err)),
  });
};
```

Nueva `<section>` (mismo patrón visual `bg-surface border-border/70` que las demás), ubicada
entre "Cuenta" (moneda, Fase 21) y "API keys" — agrupa los dos datos financieros de perfil del
usuario en secciones contiguas en vez de intercalarlos con ajustes técnicos:

```tsx
<section className="bg-surface border-border/70 rounded-2xl border p-4 sm:p-5">
  <div className="mb-4">
    <h2 className="text-text font-sans text-base font-semibold">Ingreso mensual</h2>
    <p className="text-text-muted mt-0.5 text-xs sm:text-sm">
      Se usa para calcular cuánto te queda cada mes en el dashboard.
    </p>
  </div>
  <form onSubmit={handleIncomeSubmit} className="flex items-end gap-3">
    <Input
      type="number"
      inputMode="decimal"
      min={0}
      step="0.01"
      label="Monto mensual aproximado"
      value={incomeValue}
      onChange={(e) => setIncomeValue(e.target.value)}
      className="bg-background"
    />
    <Button type="submit" variant="secondary" loading={setMonthlyIncome.isPending}>
      Guardar
    </Button>
  </form>
</section>
```

Sin historial (Decisión C2 ya settled): un único valor, sobreescrito, exactamente el mismo dato
que hoy fija `OnboardingIncomeStep`.

**Archivos a modificar:**
- `frontend/app/(dashboard)/settings/page.tsx` (nueva sección).

**Testing:** sin suite de frontend. Verificación manual: un usuario con `monthly_income` ya
fijado (ej. `test@test.com` del seed) ve el valor actual precargado en `/settings`, lo cambia y
`Guardar` actualiza tanto la card del dashboard como el propio campo sin recargar la página
(`useSetMonthlyIncome.ts:14-15` ya invalida `currentUser()` y `dashboard.summary()`).

**Criterio de aceptación:**
- Un usuario puede ver y corregir su ingreso mensual declarado desde `/settings`, con el mismo
  endpoint y el mismo hook que ya usa el onboarding.
- No se introduce ningún concepto de historial de ingresos por mes.

---

## 22.4 Campo `has_password` y claridad del modal de borrado de cuenta

### Backend

**Decisión 22.4.1 — `has_password: bool` en `UserResponse`, computado vía `model_validator`
(Decisión D4).** Ver snippet completo en "Decisiones de arquitectura" arriba. Único archivo de
backend para este ítem: `backend/app/schemas/schemas.py`. No se toca `users.py`.

**Testing:** extender `backend/tests/test_users.py` (ya existe una clase `TestHasTransactionHistory`
con el mismo perfil — se agrega un bloque análogo, no un archivo nuevo):
- `POST /users/` (registro por contraseña) seguido de `GET /users/me`: `has_password: true`.
- Login con Google (mismo mock que `TestEliminarCuenta.test_delete_me_on_google_only_account_
  skips_password_check`, `tests/test_users.py:266-290`) seguido de `GET /users/me`:
  `has_password: false`.
- `PATCH /users/me` (`actualizar_perfil`, ej. cambiando `monthly_income`) sobre una cuenta con
  contraseña: la respuesta sigue trayendo `has_password: true` — regresión directa contra la
  alternativa descartada en la Decisión D4 (el bug que tendría el patrón de asignación manual por
  endpoint no aparece acá porque no depende de que cada handler lo asigne).

### Frontend

**Decisión 22.4.2 — el modal de "Eliminar mi cuenta" en `settings/page.tsx` oculta el campo de
contraseña cuando `has_password === false`, y envía `password: ''` en ese caso sin pedirla.**

```tsx
// frontend/app/(dashboard)/settings/page.tsx
import { useCurrentUser } from '@/lib/hooks/useCurrentUser'; // ya importado por 22.3

const { data: currentUser } = useCurrentUser();
const requiresPassword = currentUser?.has_password !== false; // default seguro mientras carga

const handleDeleteSubmit = (e: React.FormEvent) => {
  e.preventDefault();
  if (requiresPassword && !password) return;
  deleteAccount.mutate(requiresPassword ? password : '');
};
```

```tsx
// dentro del <ModalShell isOpen={isDeleteOpen} ...>
{requiresPassword ? (
  <Input
    label="Contraseña"
    type="password"
    // ...resto sin cambios...
  />
) : (
  <p className="text-text-muted text-xs leading-relaxed">
    Tu cuenta usa Google para iniciar sesión — no hace falta contraseña para confirmar esta
    acción.
  </p>
)}
```

El botón de submit se deshabilita con `!password` solo cuando `requiresPassword` es verdadero
(`disabled={requiresPassword && !password}`) — para una cuenta Google-only queda habilitado de
inmediato, sin campo que llenar.

**Archivos a modificar:**
- `frontend/types/api.ts`: `UserResponse` — agregar `has_password: boolean;`.
- `frontend/app/(dashboard)/settings/page.tsx` (modal de borrado, Decisión 22.4.2).

**Testing:** sin suite de frontend. Verificación manual: una cuenta con contraseña ve el campo de
contraseña en el modal igual que hoy (Fase 21, sin regresión); una cuenta Google-only (login vía
`GoogleAuthButton`) abre el modal y ve el texto aclaratorio sin campo de contraseña, y el borrado
funciona con un solo clic en "Eliminar definitivamente".

**Criterio de aceptación:**
- El frontend distingue cuentas Google-only de cuentas con contraseña sin adivinar nada
  client-side (vía `has_password`, no vía heurísticas sobre el email o el flujo de login usado).
- El modal de borrado no le pide una contraseña a un usuario que nunca definió una.
- Ninguna cuenta con contraseña ve un cambio de comportamiento en el modal de borrado.

---

## 22.5 "Olvidé mi contraseña" — copy aclaratorio para cuentas Google-only

### Backend

**Sin cambios de backend** (Decisión D3(a), ya settled: "sin cambios de backend — el texto puede
ser genérico"). `solicitar_restablecimiento_contrasena` y `confirmar_restablecimiento_contrasena`
(`backend/app/api/auth.py:196-241` y `:244-292`) siguen funcionando exactamente igual para
cualquier cuenta, con o sin `password_hash` previo.

### Frontend

**Decisión 22.5.1 — banner de texto fijo (no condicional) en `reset-password/page.tsx`, arriba
del formulario.** No hace falta `has_password` ni ningún dato del usuario: en este punto del
flujo la identidad viene del token de la URL, no de una sesión (Decisión D3, ya settled) — el
texto es el mismo para todos, explica la posibilidad de que la cuenta sea Google-only sin
afirmar que lo es.

```tsx
// frontend/app/(auth)/reset-password/page.tsx — dentro de ResetPasswordForm, antes del <form>
<div className="bg-surface-elevated/70 border-border/50 mb-6 rounded-xl border p-3">
  <p className="text-text-muted text-xs leading-relaxed">
    Si tu cuenta se creó con Google, esta acción le agrega una contraseña — de ahí en adelante
    vas a poder iniciar sesión con cualquiera de los dos métodos.
  </p>
</div>
```

**Archivos a modificar:**
- `frontend/app/(auth)/reset-password/page.tsx` (banner nuevo).

**Testing:** sin suite de frontend. Verificación manual: completar el flujo de "olvidé mi
contraseña" para una cuenta Google-only (usando el link real que llega por email/consola) muestra
el banner, y el reset sigue funcionando igual que hoy — la cuenta queda híbrida sin ningún error
ni bloqueo.

**Criterio de aceptación:**
- Cualquier persona que llega a `/reset-password` ve una aclaración de que definir una
  contraseña ahí no reemplaza el login con Google, solo agrega una alternativa.
- Ningún comportamiento de backend cambia.

---

## Resumen de archivos tocados por ítem

| Ítem | Backend | Frontend |
|---|---|---|
| 22.1 moneda-primero + cascada | `schemas/schemas.py` (`PreferencesUpdate.apply_to_default_account`), `api/preferences.py` (cascada), `tests/test_preferences.py` (nuevo) | `components/forms/OnboardingCurrencyStep.tsx` (nuevo), `components/forms/OnboardingIncomeStep.tsx` (prop `currency`), `app/capture/page.tsx` (wiring), `lib/hooks/useUserPreferences.ts` (invalidación de `accounts.all()`), `types/api.ts` (`PreferencesUpdatePayload.apply_to_default_account`) |
| 22.2 categorías (no-op) | — | — |
| 22.3 salario editable | — (endpoint ya existe) | `app/(dashboard)/settings/page.tsx` (sección nueva, reusa `useSetMonthlyIncome.ts` sin cambios) |
| 22.4 `has_password` + modal | `schemas/schemas.py` (`UserResponse.has_password` + `model_validator`), `tests/test_users.py` (extendido) | `types/api.ts` (`UserResponse.has_password`), `app/(dashboard)/settings/page.tsx` (modal condicional) |
| 22.5 copy Google-only | — | `app/(auth)/reset-password/page.tsx` (banner) |
| Cruzando toda la fase | — | `backend/docs/API_REFERENCE.md` + `frontend/docs/API_CONTRACT.md` — documentar `PreferencesUpdate.apply_to_default_account` y `UserResponse.has_password` (convención de `CLAUDE.md` sobre contratos de API compartidos); ninguno de los dos se edita en este documento de planificación |

---

## Out of scope

- **Migraciones de Alembic**: ningún ítem de esta fase agrega columnas — `apply_to_default_account`
  es un campo de request, no persistido; `has_password` es un campo computado de response, no
  persistido. Ambos consistentes con la Decisión D1 ya settled ("no requiere ningún cambio de
  modelo ni de Alembic").
- **Lista de monedas configurable o `Enum` real en el backend**: la lista de 5 (Hallazgo 3, ROADMAP)
  vive solo en el frontend, en `OnboardingCurrencyStep.tsx` — el backend sigue aceptando
  `preferred_currency` como `str` libre, sin validación nueva, mismo criterio que la Decisión
  17.2.1 de Fase 17 (no agregar validación de moneda no solicitada).
- **Historial de ingresos mensuales** (Decisión C2, ya settled): fuera de alcance explícito.
- **Bloquear o rediseñar "olvidé mi contraseña" para cuentas Google-only** (Decisión D3, ya
  settled: se descartaron las opciones (b) y (c)).
- **Selector de categorías en el wizard de onboarding** (Decisión B1, ya settled): se reafirma
  Fase 18 sin cambios.
- **Cascadear la moneda a cuentas que no sean la cuenta por defecto**, o a cuentas que ya
  incumplen el guard de la Decisión A2: el usuario las corrige manualmente en `/accounts`, mismo
  criterio ya aceptado por la Decisión A2.

---

## Further notes

- Este documento no implementa ningún cambio en el repositorio — es el desglose ejecutable de la
  sección "Fase 22" de `docs/ROADMAP.md`, con archivos, snippets y decisiones de arquitectura
  concretas para que un `backend-engineer`/`frontend-engineer` puedan partir directamente de acá.
  Las cuatro decisiones de arquitectura (A4-A6, D4) resuelven las preguntas de implementación que
  la sesión de grilling dejó abiertas a propósito — evaluadas contra el código real de `backend/`
  y `frontend/` el 2026-09-13, no contra el texto del ROADMAP o de las Decisiones de diseño en
  aislado.
- Dos hallazgos de esta sección van más allá de lo que anticipaba la nota de coordinación
  original del documento: (1) la colisión de archivo entre A2 y D1/D2 sobre `backend/app/api/
  users.py` se disuelve por completo una vez resueltas las Decisiones A5 y D4 — ningún ítem de
  Fase 22 vuelve a tocar `users.py`; el único archivo de backend compartido entre dos ítems pasa a
  ser `schemas.py` (A1 y D4, en clases distintas, sin colisión de líneas real); (2) la Decisión D1
  ("se calcula en el endpoint correspondiente") tenía una lectura literal con un bug real
  (`has_password: false` en la respuesta del registro con contraseña) — la Decisión D4 lo corrige
  con un mecanismo distinto sin reabrir el alcance de producto que D1 ya fijó.
- Ningún archivo del repositorio fuera de `docs/specs/fase_22_spec.md` fue modificado al producir
  este documento — sigue siendo, en su totalidad, un documento de planificación.
