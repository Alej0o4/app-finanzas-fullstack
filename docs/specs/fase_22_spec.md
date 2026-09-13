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

## Notas para implementación (a futuro, no en este documento)

- A2 y D1/D2 tocan `backend/app/api/users.py` — si se implementan en paralelo con agentes
  distintos, coordinar para no pisarse en el mismo archivo.
- D3 es puramente frontend (`frontend/app/(auth)/reset-password/page.tsx`) y no depende de
  ningún otro ítem de esta fase — puede implementarse de forma completamente independiente.
- C1 y A1/A3 tocan componentes de formulario distintos (`settings/page.tsx` vs.
  `OnboardingIncomeStep.tsx` / `app/capture/page.tsx`) — sin solapamiento de archivos.
