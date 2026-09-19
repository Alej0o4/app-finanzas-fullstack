# Spec — Fase 23: Cierre de vulnerabilidad crítica — account takeover vía Google OAuth

> Plan de implementación detallado para los 3 ítems (checkboxes) de Fase 23 del
> [ROADMAP](../ROADMAP.md) (sección "Fase 23 — Cierre de vulnerabilidad crítica: account
> takeover vía Google OAuth 🔴 bloqueante", líneas 939–975, originada en la auditoría completa
> del 2026-09-15 — `CODE_REVIEW.md` raíz, `docs/TODO.md` sección Bloqueantes). Este documento no
> cambia el alcance ahí definido — lo desglosa en tareas ejecutables, con archivos concretos,
> snippets de código reales y decisiones de arquitectura numeradas, separadas explícitamente en
> Backend/Frontend por ítem, para que agentes `backend-engineer`/`frontend-engineer` distintos
> puedan tomar cada mitad en paralelo.
>
> **No implementa nada.** Ningún archivo del repositorio fuera de `docs/specs/fase_23_spec.md`
> fue modificado al producir este documento. Los hallazgos fueron verificados directamente contra
> el código el 2026-09-18: lectura completa de `backend/app/api/auth.py`,
> `backend/tests/test_auth.py` (clase `TestLoginGoogle`, líneas 478–627, incluida su corrida
> completa hasta `_login_google`), `backend/app/api/push.py`, `backend/tests/test_push.py`,
> `backend/app/models/models.py` (modelos `User` y `PushSubscription`),
> `backend/app/core/notification_dispatch.py` (antes `budget_alerts.py`, extraído en Fase 14
> §14.2 — es donde vive el envío real de push, no en `budget_alerts.py`), `backend/tests/
> conftest.py` (fixtures `register_and_login`/`test_user`/`other_user`/`auth_headers`),
> `backend/app/core/logging_config.py` y `backend/app/core/email.py` (convención de
> `logger.warning(..., extra={...})`), `frontend/components/auth/GoogleAuthButton.tsx`,
> `frontend/app/(auth)/login/page.tsx`, `backend/app/schemas/schemas.py` (`UserResponse.
> has_password`, ya en producción desde Fase 22), `CODE_REVIEW.md` raíz y `docs/TODO.md`
> (sección Bloqueantes) — no inferidos del texto del ROADMAP en aislado.

Estado del repo al momento de escribir esto (2026-09-18): Fases 7–22 completas. Fase 23 nace de
la auditoría completa del 2026-09-15, que encontró un account takeover confirmado y **codificado
como comportamiento esperado en un test** (`test_existing_unverified_password_account_is_
autolinked`, `backend/tests/test_auth.py:525` al momento de la auditoría) — no un descuido, sino
una decisión de diseño (`auth.py:90-93`, comentario "no es account takeover") cuyo análisis de
amenaza no contempló el escenario de un atacante plantando la fila a propósito. Es 🔴 bloqueante
de las Fases 24 y 25, y hoy ya hay al menos un usuario real fuera de la cuenta de pruebas
(`alejomaringomez2004@gmail.com`, vía Google) — esta spec prioriza corrección exacta sobre
alcance amplio, tal como pide el ROADMAP.

---

## Hallazgos de exploración que corrigen/precisan el ROADMAP

1. **El bug está exactamente donde dice el ROADMAP, con una precisión adicional: el orden de
   las dos mutaciones importa para cualquier fix ingenuo.** `backend/app/api/auth.py:89-97`:

   ```python
   if user:
       if not user.google_id:
           user.google_id = idinfo["sub"]
       if not user.email_verified:
           user.email_verified = True
   ```

   Un fix que condicionara la anulación de `password_hash` a `if not user.email_verified` **en
   el mismo punto donde hoy se lee esa condición para decidir verificar** funcionaría por
   casualidad (la lectura ocurre antes de la escritura, en la misma línea). Pero cualquier
   reordenamiento futuro de este bloque (p. ej. mover la anulación después del `if not user.
   email_verified: user.email_verified = True`) leería `user.email_verified` ya en `True` y
   nunca anularía nada — el mismo tipo de bug de "orden de lectura vs. escritura" que la Decisión
   D4 de `docs/specs/fase_22_spec.md` encontró para `has_password`. Ver Decisión G2 abajo: el fix
   captura el estado *antes* de mutar nada, en una variable explícita, precisamente para no
   depender de dónde quede la línea dentro del bloque.

2. **El test vulnerable existe exactamente como lo describe el ROADMAP, y su comentario explica
   la razón del error de diseño.** `backend/tests/test_auth.py:525-548`
   (`test_existing_unverified_password_account_is_autolinked`): registra una cuenta con
   contraseña y `email_verified=False` (estado real de un registro por contraseña sin verificar,
   `crear_usuario`), después hace login con Google con el mismo email, y asserta
   `user.password_hash is not None` con el comentario *"La contraseña sigue intacta — no se tocó
   el hash al vincular."* Esto es exactamente el comportamiento que permite el ataque: la
   contraseña que un atacante plantó sigue siendo válida después de que la víctima real
   "reclama" la cuenta vía Google.

3. **Ya existe un test hermano que prueba el caso donde la cuenta SÍ estaba verificada antes del
   login de Google — es el ancla correcta para el test de regresión que pide el ROADMAP.**
   `backend/tests/test_auth.py:550-562`
   (`test_existing_verified_password_account_is_idempotent_and_autolinked`): usa el fixture
   `register_and_login` (`backend/tests/conftest.py:104-144`), que marca `email_verified=True`
   **directo en la sesión de test** (`db_session.query(models.User)....update({"email_verified":
   True})`, línea 130) antes siquiera de loguear por contraseña — o sea, simula exactamente el
   caso "el dueño real ya probó control del email por el flujo normal" que la pregunta de
   arquitectura del ROADMAP quiere proteger de una regresión. Hoy este test no asserta nada sobre
   `password_hash` (no hacía falta, porque hoy nunca se toca) — es el punto de extensión natural
   para el test de "no romper este caso" que pide el ROADMAP, en vez de escribir un test nuevo
   desde cero.

4. **El helper que efectivamente envía push (`enviar_push`) vive en `notification_dispatch.py`,
   no en `budget_alerts.py` — el ROADMAP nombra el módulo viejo.** `backend/app/core/
   budget_alerts.py:18` importa `crear_y_enviar_notificacion` de `app.core.notification_
   dispatch` (extraído en Fase 14 §14.2, ver comentario de módulo en `notification_dispatch.py:
   1-7`). `enviar_push()` (`notification_dispatch.py:49-118`) consulta `PushSubscription`
   filtrando por `models.PushSubscription.user_id == notificacion.user_id` (línea 70) — el
   `user_id` de la **notificación** (el dueño real del presupuesto/aviso), no el de la fila de
   suscripción per se. Esto acota el impacto real de "robar" una fila de `push_subscriptions`
   reasignándole `user_id`: la fila deja de aparecer en la consulta que arma los avisos de su
   dueño original (pierde ese canal, sin aviso) y empieza a aparecer en la del nuevo dueño — pero
   como el nuevo dueño (el atacante, si el escenario es hostil) fue quien envió `p256dh_key`/
   `auth_key` en el mismo request de reasignación (`suscribir()`, `backend/app/api/push.py:
   46-51`), el endpoint físico (que puede seguir siendo el navegador real de la víctima, si el
   atacante lo obtuvo de algún otro medio) no puede ser leído en claro por el atacante — Web Push
   cifra el payload con esas claves, así que enviar con claves que el atacante inventó solo
   produce un envío que el navegador de la víctima no puede descifrar (falla silenciosa del lado
   del navegador) o que la librería rechaza. **No hay exfiltración de contenido posible por esta
   vía** — el impacto real y máximo es una denegación de servicio del canal push para la víctima
   original (deja de recibir alertas de presupuesto hasta que vuelva a suscribirse), consistente
   con la severidad "baja" que el propio ROADMAP y `CODE_REVIEW.md:116` ya le asignan.

5. **No existe ningún test de "robo" cross-usuario para `POST /push/subscribe` — solo para
   `DELETE`.** `backend/tests/test_push.py:82-89`
   (`test_unsubscribe_foreign_subscription_returns_404`) cubre el ownership check que **ya
   existe** en `desuscribir()` (`backend/app/api/push.py:76`: `if not suscripcion or
   suscripcion.user_id != current_user.id: raise HTTPException(404, ...)`). No hay ningún test
   equivalente para `suscribir()` (`push.py:37-63`) — ni uno que documente el comportamiento
   actual de reasignación, ni uno que pruebe un fix. Confirma que el ROADMAP tiene razón en que
   "falta el chequeo de ownership igual" en el POST, distinto del DELETE que sí lo tiene.

6. **El docstring de `suscribir()` documenta la reasignación como intencional, y el modelo
   confirma por qué el `endpoint` es global, no por usuario.** `backend/app/api/push.py:42-45`:
   *"Si el endpoint ya existe — re-registro del mismo navegador/dispositivo, incluso tras un
   cierre de sesión con otro usuario — se actualiza la fila en vez de duplicar."*
   `backend/app/models/models.py:303-307` (comentario sobre `PushSubscription`): *"`endpoint` es
   único GLOBALMENTE (no por usuario): el estándar Web Push garantiza un endpoint único por
   navegador/instalación."* Cualquier fix tiene que preservar este caso: dispositivo compartido,
   usuario A cierra sesión, usuario B inicia sesión en el mismo navegador y vuelve a suscribirse
   — el mismo `endpoint`, dueño legítimamente distinto.

7. **`GoogleAuthButton.tsx` ya tiene, por diseño, "fallo silencioso" como patrón para todo el
   flujo — no hay ninguna superficie hoy para mostrar un mensaje post-link sin agregar una.**
   `frontend/components/auth/GoogleAuthButton.tsx:59-63`, comentario explícito: *"Fallo
   silencioso intencional: sin estado de error propio en este componente mínimo... no bloquea el
   flujo existente."* En éxito (líneas 42-58) el componente nunca distingue "usuario nuevo",
   "cuenta existente vinculada sin cambios" o "cuenta existente vinculada con contraseña
   anulada" — las tres rutas terminan en el mismo `router.push(...)` según `has_transaction_
   history`, sin ningún toast. `frontend/app/(auth)/login/page.tsx:88-100` maneja el error de
   `POST /auth/login` con un mensaje ya genérico ("Credenciales inválidas. Por favor verifica tus
   datos.") para cualquier `401`/`403` — que es exactamente lo que vería un atacante cuya
   contraseña plantada ya no sirve tras el fix, sin necesitar ningún cambio.

8. **El mecanismo de "cuenta Google-only" que este fix reutiliza ya está completo en producción
   desde Fase 22 — no hace falta construir nada nuevo, solo entrar en el mismo camino.**
   `backend/app/schemas/schemas.py:86-110` (`UserResponse.has_password`, computado vía
   `model_validator` sobre `password_hash is not None`, Decisión D4 de Fase 22) ya se sirve en
   `GET/PATCH /users/me`. El modal de borrado de cuenta en `frontend/app/(dashboard)/
   settings/page.tsx` (Decisión 22.4.2) ya oculta el campo de contraseña cuando `has_password ===
   false`, y "olvidé mi contraseña" (`reset-password/page.tsx`, Decisión 22.5.1) ya explica que
   completar ese flujo le agrega una contraseña a una cuenta que hasta ahora solo usaba Google.
   Anular `password_hash` en el auto-link hace que una cuenta afectada por este fix caiga,
   automáticamente y sin código nuevo, en el mismo camino que ya tienen las cuentas Google-only
   puras.

---

## Decisión de producto (ya tomada — no reabierta en esta spec)

Confirmado en el enunciado de esta tarea, con el dueño del proyecto: **Opción A del ROADMAP**
(anular `password_hash` al auto-linkear) es la elegida. La cuenta queda Google-only —mismo
estado que una cuenta creada directamente con Google— hasta que su dueño fije una contraseña
nueva desde Settings/forgot-password (Hallazgo 8). **Opción B** (exigir confirmar la contraseña
actual antes del auto-link) queda descartada: en el escenario de ataque real la víctima nunca
conoce la contraseña que el atacante plantó, así que pedir confirmarla bloquearía a la víctima
real sin proteger nada — no hay contraseña legítima que "confirmar".

Lo que esta spec sí resuelve, porque el ROADMAP lo deja abierto a propósito, es el **scoping
exacto de cuándo anular** (Decisión G1 abajo) y el mecanismo del ownership check de push
(Decisión P1 abajo) — ninguna decisión de producto nueva, solo las preguntas de implementación
necesarias para que Opción A sea ejecutable sin dejar huecos ni romper casos legítimos.

---

## Decisiones de arquitectura (evaluadas por `software-architect` el 2026-09-18)

### Cierre del account takeover (G1–G4)

**G1 — La anulación de `password_hash` aplica única y exactamente cuando `not user.
email_verified` en el momento en que `login_google` encuentra la fila — se confirma la hipótesis
del enunciado de esta tarea.** Razonamiento verificado contra el código real:

- Una cuenta con `email_verified=True` en el momento del login de Google llegó a ese estado por
  exactamente dos caminos posibles hoy: (a) verificó su email por el flujo normal de token
  (`verificar_email()`, `auth.py:296-323`, que exige poseer el correo real para clickear el
  enlace), o (b) se creó directamente por Google (`login_google`, rama `else`, `auth.py:99-105`,
  que siempre nace con `email_verified=True`). En ambos casos, quien controla `password_hash`
  (si existe) ya demostró control real del email antes de este login — el hash es confiable.
- Una cuenta con `email_verified=False` en ese mismo momento **nunca** demostró control del
  email por ningún medio hasta este preciso login de Google — es indistinguible, con los datos
  que el servidor tiene, entre "la dueña real se registró por contraseña y todavía no revisó su
  correo" y "un atacante plantó la fila con el email de la víctima y su propia contraseña,
  apostando a que la víctima algún día haga login con Google". El propio comentario que la
  auditoría marcó como el origen del bug (`auth.py:90-93`, "Google solo firma `email_verified=
  true`... capacidad equivalente al reset de contraseña por email") es correcto para el email
  pero nunca se extendió al `password_hash`: Google prueba control del *correo*, no valida en
  absoluto qué contraseña había quedado plantada ahí antes.
- **No queda ningún caso del escenario de ataque sin cubrir con este scoping.** El ataque
  requiere, por construcción, que la cuenta plantada nunca se verifique (si el atacante
  verificara el email él mismo, no tendría forma de hacerlo sin acceso al correo de la víctima) —
  así que el estado `email_verified=False` en el momento del login de Google real de la víctima
  es una propiedad *estructural* del ataque, no una casualidad del ejemplo del ROADMAP. Cualquier
  variante del ataque (contraseña distinta, `full_name` distinto, tiempo transcurrido distinto
  entre el pre-registro y el login real) sigue cayendo en `email_verified=False` en ese momento.
- **Aplicar la anulación también a cuentas ya verificadas sería una regresión de UX sin
  beneficio de seguridad.** Si `email_verified` ya era `True` antes de este login de Google, el
  `password_hash` existente ya fue probado por el dueño real (vía el flujo normal) — anularlo
  igual solo le rompería el login por contraseña a alguien que hizo todo bien, a cambio de cero
  reducción de superficie de ataque (el atacante ya no puede plantar nada en una cuenta que la
  víctima ya verificó).

**G2 — El fix captura el estado `email_verified` *antes* de mutar nada, en una variable
explícita, para que el bloque no dependa de en qué orden queden sus líneas (Hallazgo 1).**

```python
# backend/app/api/auth.py — login_google(), reemplaza el bloque `if user:` actual
if user:
    # Fase 23 (Decisión G1): capturar el estado ANTES de tocar `email_verified` — si se
    # leyera después de la línea que lo pone en True, la condición sería siempre falsa y
    # nunca anularía nada (mismo tipo de bug de orden lectura/escritura que la Decisión D4
    # de docs/specs/fase_22_spec.md encontró para has_password).
    cuenta_no_verificada_antes_de_este_login = not user.email_verified

    if not user.google_id:
        user.google_id = idinfo["sub"]

    if cuenta_no_verificada_antes_de_este_login:
        user.email_verified = True
        # Este login de Google es la primera prueba real de que esta cuenta controla el
        # email — cualquier password_hash preexistente nunca fue probado contra su dueño
        # real (pudo ser plantado por un atacante, ver docs/ROADMAP.md Fase 23 y
        # CODE_REVIEW.md). Se anula: la cuenta queda Google-only hasta que su dueño fije
        # una contraseña nueva (Settings/forgot-password, mismo flujo que Fase 22 ya
        # construyó para cuentas Google-only puras — Decisión D1-D3 de fase_22_spec.md).
        user.password_hash = None
else:
    ...  # sin cambios — rama de creación de usuario nuevo
```

- *Alternativa descartada:* condicionar la anulación a `if not user.email_verified:` en el mismo
  punto donde hoy está el `if`, sin variable intermedia. Funciona hoy porque la lectura ocurre
  antes de la escritura en la misma línea, pero dos ingenieros distintos tocando este bloque en
  el futuro (p. ej. reordenando para agrupar las dos actualizaciones de `google_id`) podrían
  introducir el mismo bug de orden que G2 previene explícitamente con la variable.

**G3 — El caso ya-verificado-y-ya-vinculado (login de Google repetido) no necesita ninguna rama
nueva — es consecuencia directa de G1, no un mecanismo aparte.** Una vez que una cuenta pasó por
G1 y quedó con `email_verified=True`, cualquier login de Google posterior encuentra
`cuenta_no_verificada_antes_de_este_login = False` y no vuelve a tocar `password_hash` — cubre
tanto "cuenta que nació verificada por Google" como "cuenta que se verificó por contraseña" como
"cuenta que ya fue afectada por G1 en un login anterior", sin necesitar distinguir entre esos
tres orígenes. `test_existing_verified_password_account_is_idempotent_and_autolinked` (Hallazgo
3) ya ejercita este camino — solo le falta el assert nuevo (ver Testing).

**G4 — Sin cambios de transacción/commit: el fix vive dentro del mismo `if user:` que ya se
resuelve en el único `db.commit()` existente al final de `login_google` (`auth.py:110`).** No
hay ventana TOCTOU que cerrar aquí (a diferencia de la cascada de cuentas de Fase 22, Decisión
A5) — todo el bloque corre secuencialmente dentro del mismo request, sin ninguna escritura
intermedia a la que otra request pueda intercalarse.

**G5 — Frontend: sin cambios.** Ver Hallazgo 7 (patrón de fallo/éxito silencioso ya establecido
en `GoogleAuthButton.tsx`) y Hallazgo 8 (el mecanismo Google-only de Fase 22 ya cubre el
"descubrimiento" del nuevo estado la próxima vez que la usuaria abre Settings, sin sorpresas —
exactamente el criterio que ya usa una cuenta Google-only pura). Motivos concretos para no
agregar un toast/mensaje "tu contraseña anterior fue invalidada por seguridad":

- **No hay ninguna señal en la respuesta de `POST /auth/google` hoy que distinga "cuenta nueva",
  "cuenta existente vinculada sin tocar nada" y "cuenta existente vinculada con contraseña
  anulada".** Las tres devuelven la misma forma (`TokenResponse`: `access_token`/`refresh_
  token`/`token_type`, sin cambios en esta fase). Agregar un campo nuevo (p. ej. `password_
  invalidated: bool`) sería un cambio de contrato de API que ninguno de los 3 ítems del ROADMAP
  pide, y esta fase es explícitamente de corrección, no de alcance ampliado ("priorizando
  corrección sobre alcance amplio", instrucción de esta tarea).
- **La población afectada por esta ambigüedad de UX es un subconjunto estrecho y ya aceptado
  como tal por G1**: solo alguien que (a) se registró por contraseña, (b) nunca verificó su
  email, y (c) más tarde hace login con Google con el mismo correo — sea la víctima real de un
  ataque (a quien el mensaje no le importa porque nunca supo de la contraseña plantada) o una
  usuaria legítima que se registró y genuinamente no revisó su correo antes de probar Google (a
  quien el mensaje sí podría ahorrarle una confusión futura, pero es el caso menos común y el
  costo de la ambigüedad ya fue aceptado explícitamente por el análisis de amenaza de G1 — no se
  puede distinguir ese caso del ataque real sin información que el servidor no tiene).
- **Si esa usuaria intenta loguear con la contraseña vieja más adelante**, `login()` ya devuelve
  un mensaje claro y accionable —"Credenciales inválidas. Por favor verifica tus datos."— que no
  la deja bloqueada sin salida: puede volver a usar Google, o pasar por "olvidé mi contraseña"
  (que ya explica, desde Fase 22, que eso le agrega una contraseña nueva utilizable junto con
  Google). No es una vía muerta, solo un mensaje genérico en vez de uno específico.

- *Alternativa descartada:* agregar un campo de respuesta nuevo + un toast condicional en
  `GoogleAuthButton.tsx`. Descartada por el costo de contrato de API frente al beneficio acotado
  (arriba) — queda anotada como mejora de UX opcional y NO urgente en "Out of scope", no como
  parte de esta fase bloqueante.

### Ownership check en `POST /push/subscribe` (P1–P2)

**P1 — Se agrega un log de auditoría (`logger.warning`) cuando la reasignación de `user_id`
cruza de un usuario a otro; el comportamiento de reasignación en sí NO cambia.** Verificado
contra el código real que un chequeo que *bloquee* la reasignación cross-usuario rompería el
caso legítimo que el propio docstring de `suscribir()` documenta a propósito (Hallazgo 6:
dispositivo compartido, logout de un usuario y login de otro en el mismo navegador) — con los
datos que trae el request (`endpoint` + claves + el usuario autenticado) **no hay ninguna forma
de distinguir, del lado del servidor, ese caso legítimo de alguien que obtuvo el `endpoint` de
otra cuenta por otro medio** (ambos llegan como el mismo shape de request). Bloquear
indiscriminadamente el caso cross-usuario rompería el dispositivo compartido; no bloquearlo deja
exactamente el estado actual. La auditoría (`CODE_REVIEW.md:116`, `docs/TODO.md:75-79`) y el
ROADMAP ya tasan la severidad como baja porque el `endpoint` no es adivinable (es un secreto de
~100+ bits generado por el navegador) — el Hallazgo 4 de esta spec refuerza que, incluso si
alguien obtiene un `endpoint` ajeno por otro medio (dispositivo compartido físicamente, un log
filtrado, o el riesgo ya aceptado de JWT-en-`localStorage`, ver `docs/TODO.md`), el máximo daño
posible es una denegación del canal push para la cuenta original, no una fuga de datos. Dado ese
techo de impacto y la imposibilidad de un chequeo que no rompa el caso legítimo, la decisión es
**visibilidad, no bloqueo**: un log estructurado (mismo patrón de `logger.warning(...,
extra={...})` que ya usa `backend/app/core/email.py:75-78`) deja un rastro auditable —
consistente con la escala actual del proyecto (deploy single-worker, sin dashboard de
seguridad, un solo operador con acceso a `docker compose logs -f backend`, ver `docs/TODO.md`) —
sin construir infraestructura de alertas que el proyecto no tiene y no necesita a este tamaño.

```python
# backend/app/api/push.py
import logging
# ...imports existentes sin cambios...

logger = logging.getLogger(__name__)


@router.post("/subscribe", response_model=schemas.PushSubscriptionResponse)
def suscribir(
    payload: schemas.PushSubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Registra/actualiza una suscripción push del usuario autenticado (upsert por
    `endpoint`). Si el endpoint ya existe — re-registro del mismo navegador/dispositivo,
    incluso tras un cierre de sesión con otro usuario — se actualiza la fila en vez de
    duplicar (el estándar Web Push garantiza endpoint único por instalación).

    Fase 23 (Decisión P1): la reasignación cross-usuario sigue permitida a propósito (no
    hay forma de distinguir, solo con este request, el caso legítimo de dispositivo
    compartido de un endpoint obtenido por otro medio) — pero queda logueada para
    auditoría manual."""
    suscripcion = db.query(models.PushSubscription).filter(models.PushSubscription.endpoint == payload.endpoint).first()

    if suscripcion:
        if suscripcion.user_id != current_user.id:
            logger.warning(
                "Suscripción push reasignada entre usuarios distintos (mismo endpoint)",
                extra={
                    "push_subscription_id": suscripcion.id,
                    "previous_user_id": suscripcion.user_id,
                    "new_user_id": current_user.id,
                },
            )
        suscripcion.user_id = current_user.id
        suscripcion.p256dh_key = payload.keys.p256dh
        suscripcion.auth_key = payload.keys.auth
    else:
        suscripcion = models.PushSubscription(
            user_id=current_user.id,
            endpoint=payload.endpoint,
            p256dh_key=payload.keys.p256dh,
            auth_key=payload.keys.auth,
        )
        db.add(suscripcion)

    db.commit()
    db.refresh(suscripcion)
    return suscripcion
```

- *Alternativa descartada:* rechazar la reasignación con `403`/`409` cuando `suscripcion.user_id
  != current_user.id`. Rompe el caso legítimo documentado (Hallazgo 6) — un dispositivo
  compartido dejaría al segundo usuario sin poder activar push nunca, sin ninguna vía de
  recuperación salvo pedirle al primer usuario que se desuscriba primero (fricción no pedida por
  el ROADMAP, que solo pide "ownership check", no "bloqueo").
- *Alternativa descartada:* exigir un segundo factor (p. ej. reconfirmar con el `endpoint` más
  algún nonce firmado del lado del navegador) antes de permitir la reasignación. Es
  infraestructura nueva (esquema de firma, estado adicional) para mitigar un riesgo que el propio
  ROADMAP ya tasa como bajo y que no tiene, hoy, ningún reporte de explotación real —
  desproporcionado para el tamaño y la etapa actual del proyecto.
- *Alternativa descartada (statu quo puro, "documentar sin loguear"):* se consideró no cambiar
  nada y solo agregar un test que documente el comportamiento actual. Se descarta porque el
  costo del log es mínimo (una línea, patrón ya existente en el proyecto) y sí mejora la
  auditabilidad real sin ningún riesgo de romper el caso legítimo — a diferencia de un chequeo
  que bloquee, loguear no tiene contraindicación.

**P2 — El test nuevo se agrega a `backend/tests/test_push.py` (clase `TestPushSubscriptionEndpoints`,
ya existente — no hace falta archivo nuevo), usando el fixture `caplog` de pytest (sin precedente
en la suite hoy — `grep` confirma que ningún test usa `caplog` todavía, así que este es el primer
uso; si `caplog` no captura el registro por algún efecto del handler JSON de `configure_logging()`
inicializado a nivel de módulo en `main.py:36`, cae de vuelta a verificar solo el comportamiento
—la reasignación sigue ocurriendo— sin la aserción del mensaje de log, y se anota la limitación).**

---

## Orden de ejecución recomendado

```
1. Backend: login_google() — captura de estado + anulación de password_hash (G1/G2) (§23.1)
   ── Independiente de todo lo demás. Es el fix bloqueante real — máxima prioridad.

2. Backend: corrección de test_existing_unverified_password_account_is_autolinked +
   test del escenario hostil + regresión sobre la cuenta ya verificada (§23.1)
   ── Depende de (1): son tests contra el comportamiento que (1) implementa. Mismo PR/commit
      que (1) — un fix de seguridad sin su test no debe mergearse suelto.

3. Backend: ownership check (log) en POST /push/subscribe + test (§23.2)
   ── Completamente independiente de (1)-(2): archivo distinto (push.py vs auth.py), sin
      ninguna dependencia de datos ni de código compartido. Puede hacerse en paralelo desde
      el día 1, incluso por el mismo agente backend en un commit separado.

4. Frontend: sin tareas (Decisión G5)
   ── No hay paso 4. Se deja constancia de que se evaluó y se decidió no tocar nada — ver
      Decisión G5 para el razonamiento completo.
```

Los dos ítems de backend (23.1 Google OAuth, 23.2 push) no comparten ningún archivo — pueden
resolverse en paralelo por el mismo o distintos agentes `backend-engineer`, sin necesidad de
coordinar orden de merge entre ellos. Ninguno de los dos tiene contraparte de frontend en esta
fase.

---

## 23.1 Cierre del account takeover vía auto-link de Google OAuth

### Backend

**Decisión 23.1.1 — el bloque `if user:` de `login_google()` se reemplaza tal como muestra la
Decisión G2** (ver snippet completo arriba). Único cambio de lógica en `auth.py`.

**Archivo a modificar:** `backend/app/api/auth.py`, función `login_google()` (líneas 89-97 al
momento de escribir esto).

**Decisión 23.1.2 — corrección y extensión de `backend/tests/test_auth.py` (clase
`TestLoginGoogle`), tres cambios:**

a) **Corregir el test que hoy asserta el bug** (`test_existing_unverified_password_account_is_
autolinked`, líneas 525-548):

```python
# backend/tests/test_auth.py — dentro de TestLoginGoogle
def test_existing_unverified_password_account_is_autolinked(self, client, monkeypatch, db_session):
    # Cuenta con contraseña y email sin verificar (estado de un registro real).
    register_response = client.post(
        "/api/v1/users/",
        json={"email": "auto-link@example.com", "full_name": "Contraseña", "password": "Contrasena10"},
    )
    assert register_response.status_code == 200, register_response.text

    user = db_session.query(models.User).filter(models.User.email == "auto-link@example.com").first()
    assert user.email_verified is False
    user_id_before = user.id
    users_before = db_session.query(models.User).count()

    response = self._login_google(client, monkeypatch, email="auto-link@example.com")
    assert response.status_code == 200, response.text

    db_session.refresh(user)
    # P3: no se creó un segundo usuario — se vinculó el existente.
    assert user.id == user_id_before
    assert db_session.query(models.User).count() == users_before
    assert user.google_id == "google-sub:auto-link@example.com"
    # P4: el correo de Google ya estaba verificado por Google → la cuenta queda activa.
    assert user.email_verified is True
    # Fase 23 (Decisión G1, corrige el bug de la auditoría 2026-09-15): la cuenta estaba
    # SIN verificar antes de este login — cualquier password_hash preexistente nunca fue
    # probado contra el dueño real del email (pudo ser plantado por un atacante), así que
    # se anula al vincular. La cuenta queda Google-only hasta que su dueño fije una
    # contraseña nueva (Settings/forgot-password, mismo flujo que Fase 22 ya construyó
    # para cuentas Google-only puras).
    assert user.password_hash is None
```

b) **Agregar el test del escenario hostil completo:**

```python
    def test_autolink_on_unverified_account_nullifies_attacker_planted_password(
        self, client, monkeypatch, db_session
    ):
        """Escenario hostil completo (Fase 23, Decisión G1): un atacante se pre-registra
        con el email de la víctima y su propia contraseña, nunca verifica el correo (un
        solo POST, rate-limitado pero no bloqueado). Cuando la víctima real hace login con
        Google con ese mismo correo, el auto-link debe anular esa contraseña plantada — si
        no, quedaría válida para el atacante contra POST /auth/login (el bug original)."""
        victim_email = "victima@example.com"
        register_response = client.post(
            "/api/v1/users/",
            json={"email": victim_email, "full_name": "Atacante", "password": "PasswordDelAtacante1"},
        )
        assert register_response.status_code == 200, register_response.text

        # La cuenta plantada por el atacante nunca se verifica.
        user = db_session.query(models.User).filter(models.User.email == victim_email).first()
        assert user.email_verified is False

        # La víctima real hace login con Google usando el mismo correo.
        response = self._login_google(client, monkeypatch, email=victim_email)
        assert response.status_code == 200, response.text

        db_session.refresh(user)
        assert user.email_verified is True
        assert user.password_hash is None  # Fase 23 (G1): contraseña plantada, anulada
        assert user.google_id == f"google-sub:{victim_email}"

        # La contraseña que el atacante plantó ya NO sirve contra esta cuenta.
        ataque_login = client.post(
            "/api/v1/auth/login",
            data={"username": victim_email, "password": "PasswordDelAtacante1"},
        )
        assert ataque_login.status_code == 403
        assert ataque_login.json()["detail"] == "Credenciales Inválidas"
```

c) **Extender el test de idempotencia sobre cuenta ya verificada con el assert de regresión que
pide el ROADMAP** (`test_existing_verified_password_account_is_idempotent_and_autolinked`,
líneas 550-562 — se agregan las últimas 3 líneas, sin tocar el resto):

```python
    def test_existing_verified_password_account_is_idempotent_and_autolinked(
        self, client, monkeypatch, db_session, register_and_login
    ):
        user = register_and_login(email="auto-link-verificado@example.com")
        stored = db_session.query(models.User).filter(models.User.email == user["email"]).one()
        assert stored.email_verified is True

        response = self._login_google(client, monkeypatch, email=user["email"])
        assert response.status_code == 200, response.text

        stored = db_session.query(models.User).filter(models.User.email == user["email"]).one()
        assert stored.google_id == f"google-sub:{user['email']}"  # se setea igual
        assert stored.email_verified is True
        assert db_session.query(models.User).count() == 1  # sin duplicados, sin romper nada
        # Fase 23 (Decisión G1, regresión): la cuenta YA estaba verificada antes de este
        # login de Google — su password_hash ya era confiable (probado por el dueño real
        # vía el flujo normal de verificación), así que vincular Google no debe tocarlo.
        assert stored.password_hash is not None
        # La contraseña original sigue funcionando end-to-end, no solo el hash intacto.
        login_con_password = client.post(
            "/api/v1/auth/login",
            data={"username": user["email"], "password": user["password"]},
        )
        assert login_con_password.status_code == 200, login_con_password.text
```

**Archivo a modificar:** `backend/tests/test_auth.py` (los tres bloques a/b/c dentro de
`TestLoginGoogle`).

**Testing:** los tres casos de arriba (a, b, c) son la suite completa de este ítem — cubren,
respectivamente: el caso ya existente corregido, el escenario hostil end-to-end pedido
explícitamente por el ROADMAP, y la regresión de "no romper el caso legítimo ya verificado".
Correr `cd backend && pytest tests/test_auth.py -v -k TestLoginGoogle` tras el cambio.

**Criterio de aceptación:**
- Una cuenta con contraseña que nunca verificó su email, al vincularse vía Google, pierde esa
  contraseña (`password_hash` queda `None`) y no puede volver a loguearse con ella.
- Una cuenta con contraseña que ya había verificado su email antes de vincular Google conserva
  su contraseña sin cambios — puede seguir logueándose con cualquiera de los dos métodos.
- Ningún test de `TestLoginGoogle` queda asertando el comportamiento vulnerable como esperado.
- El fix no introduce ninguna ventana de tiempo nueva ni cambia la atomicidad de `login_google()`
  (sigue siendo un único `db.commit()` al final).

### Frontend

**Sin cambios (Decisión G5).** Ver razonamiento completo arriba. No se toca `GoogleAuthButton.
tsx`, `login/page.tsx`, ni ningún otro archivo de frontend para este ítem.

**Testing:** no aplica (sin cambios). Verificación manual opcional, no bloqueante: repetir el
escenario hostil a mano (registrar con contraseña sin verificar, luego login real con Google) y
confirmar que el mensaje que ve el atacante al intentar loguear con la contraseña vieja es el
genérico ya existente ("Credenciales inválidas. Por favor verifica tus datos."), sin ningún error
nuevo ni pantalla rota.

**Criterio de aceptación:**
- Ningún archivo de `frontend/` cambia por este ítem.
- El flujo de login con Google sigue funcionando exactamente igual para todos los casos que no
  involucran una cuenta previamente sin verificar (la gran mayoría de los logins reales).

---

## 23.2 Ownership check en `POST /push/subscribe`

### Backend

**Decisión 23.2.1 — log de auditoría en la reasignación cross-usuario (Decisión P1), sin
bloquear el caso legítimo.** Ver snippet completo en "Decisiones de arquitectura" arriba.

**Archivo a modificar:** `backend/app/api/push.py`, función `suscribir()` (líneas 37-63 al
momento de escribir esto) + import de `logging` al inicio del archivo.

**Decisión 23.2.2 — nuevo test en `backend/tests/test_push.py`, clase
`TestPushSubscriptionEndpoints` (ya existente):**

```python
# backend/tests/test_push.py — dentro de TestPushSubscriptionEndpoints
def test_subscribe_reassigns_ownership_across_users_and_logs_it(
    self, client, test_user, other_user, caplog, db_session
):
    """Fase 23 (Decisión P1): el docstring de `suscribir()` documenta la reasignación
    entre usuarios como intencional (dispositivo compartido) — este test confirma que
    sigue funcionando igual (no se bloquea) y que ahora queda un log de auditoría."""
    endpoint = "https://push.example.com/fcm/suscripcion-compartida"

    primera = client.post("/api/v1/push/subscribe", json=_payload(endpoint), headers=other_user["headers"])
    assert primera.status_code == 200, primera.text

    with caplog.at_level(logging.WARNING, logger="app.api.push"):
        segunda = client.post(
            "/api/v1/push/subscribe",
            json=_payload(endpoint, p256dh="p256dh-nuevo", auth="auth-nuevo"),
            headers=test_user["headers"],
        )
    assert segunda.status_code == 200, segunda.text

    # Comportamiento preservado: una sola fila, reasignada al segundo usuario (Hallazgo 6).
    fila = db_session.query(models.PushSubscription).filter(models.PushSubscription.endpoint == endpoint).first()
    assert fila.user_id == test_user["id"]
    assert _contar_suscripciones(db_session) == 1

    # Auditoría nueva: la reasignación cross-usuario queda logueada.
    mensajes = [r.message for r in caplog.records if r.name == "app.api.push"]
    assert any("reasignada" in m for m in mensajes)
```

Import nuevo al inicio de `test_push.py`: `import logging` (no está hoy — verificar antes de
duplicarlo).

**Archivo a modificar:** `backend/tests/test_push.py`.

**Testing:** `cd backend && pytest tests/test_push.py -v`. Si `caplog` no captura el registro por
algún efecto de `configure_logging()` (que agrega su propio handler al logger raíz a nivel de
import de `main.py`, ver Decisión P2), el test debe ajustarse para verificar solo el
comportamiento preservado (fila reasignada) y anotar la limitación en un comentario — no bloquear
el ítem por eso, dado que el comportamiento (lo único que el ROADMAP realmente exige no romper)
es lo esencial.

**Criterio de aceptación:**
- El caso legítimo de dispositivo compartido (`test_duplicate_endpoint_upserts_instead_of_
  duplicating`, ya existente) sigue pasando sin cambios.
- Una reasignación de `user_id` que cruza de un usuario a otro queda registrada en el log
  estructurado del backend, visible vía `docker compose logs -f backend`.
- Ningún comportamiento observable por el cliente HTTP cambia (mismo código de estado, misma
  forma de respuesta) — el fix es puramente de observabilidad server-side.

### Frontend

**Sin cambios.** El ROADMAP no pide ningún cambio de frontend para este ítem, y no hay ninguna
superficie de UI que dependa de este comportamiento (la suscripción push se gestiona
automáticamente al aceptar el permiso del navegador, sin ninguna pantalla que muestre el estado
de "a qué cuenta pertenece esta suscripción").

---

## Resumen de archivos tocados por ítem

| Ítem | Backend | Frontend |
|---|---|---|
| 23.1 account takeover Google OAuth | `api/auth.py` (`login_google()`, bloque `if user:`), `tests/test_auth.py` (`TestLoginGoogle`: 1 test corregido + 1 nuevo + 1 extendido) | — (Decisión G5: sin cambios) |
| 23.2 ownership check push | `api/push.py` (`suscribir()`, log de auditoría), `tests/test_push.py` (1 test nuevo) | — |
| Cruzando toda la fase | Sin cambios de contrato de API (`TokenResponse` y `PushSubscriptionResponse` no cambian de forma) — no aplica la convención de `CLAUDE.md` sobre actualizar `API_REFERENCE.md`/`API_CONTRACT.md` en este caso | — |

---

## Out of scope

- **Rol admin o cualquier mecanismo de moderación de cuentas**: no lo pide el ROADMAP para esta
  fase; ya fue descartado explícitamente para otra decisión de cuentas en Fase 21 (ver
  `docs/specs/fase_21_spec.md`, sección "Out of scope").
- **Campo de respuesta nuevo en `POST /auth/google` para distinguir "cuenta nueva" / "vinculada
  sin cambios" / "vinculada con contraseña anulada", y el toast correspondiente en
  `GoogleAuthButton.tsx`**: evaluado y descartado en la Decisión G5 — el costo de un cambio de
  contrato de API no se justifica frente al beneficio acotado, y esta fase prioriza corrección
  sobre alcance ampliado. Queda anotado como posible mejora de UX futura, no bloqueante.
- **Bloquear o exigir confirmación adicional en la reasignación cross-usuario de `POST /push/
  subscribe`**: descartado en la Decisión P1 — rompería el caso legítimo de dispositivo
  compartido que el propio docstring documenta a propósito, a cambio de cerrar un riesgo que la
  auditoría y el ROADMAP ya tasan como bajo.
- **Rate limiting en `POST /push/subscribe`**: no lo pide el ROADMAP para este ítem (el enunciado
  lo acota explícitamente a "ownership check... antes de reasignar user_id"), y el vector de
  ataque relevante (obtener un `endpoint` ajeno) no es de fuerza bruta contra este endpoint — un
  rate limit no mitigaría el riesgo real descrito en el Hallazgo 4. Podría revisitarse junto con
  el resto de endpoints sin rate limit si alguna vez se prioriza aparte.
- **Migración de Alembic**: ningún ítem de esta fase agrega ni cambia columnas — la anulación de
  `password_hash` usa una columna ya `nullable=True` desde Fase 20 (`models.py:23`), y el fix de
  push es puramente de lógica de aplicación + logging.
- **Reconstruir el análisis de amenaza completo de Google OAuth más allá de este bug puntual**:
  fuera de alcance — esta spec cierra exactamente el hallazgo confirmado por la auditoría
  2026-09-15, no reabre el diseño general del login social (Fase 20).

---

## Further notes

- **Los tres checkboxes de la sección "Fase 23" del ROADMAP (líneas 958-974) quedan cubiertos**:
  1. *"Invalidar/reconfirmar el `password_hash` existente al auto-linkear una cuenta de
     Google"* → §23.1, Decisiones G1/G2, con Opción A ya elegida por el dueño del proyecto y el
     scoping exacto (`not user.email_verified` capturado antes de mutar) confirmado contra el
     código real.
  2. *"Corregir `test_existing_unverified_password_account_is_autolinked`... + agregar un test
     explícito del escenario hostil"* → §23.1, Decisión 23.1.2 (a) corrige el test existente, (b)
     agrega el test hostil completo (pre-registro del atacante → login real de la víctima →
     contraseña del atacante ya no sirve), (c) agrega la regresión de la cuenta ya verificada que
     el ROADMAP no pedía explícitamente pero que el enunciado de esta tarea sí exige.
  3. *"Ownership check en `POST /push/subscribe`... antes de reasignar `user_id`"* → §23.2,
     Decisión P1: no se bloquea (rompería el caso legítimo documentado), se audita vía log
     estructurado — decisión justificada contra el código real (Hallazgos 4-6), no asumida.
- Este documento no implementa ningún cambio en el repositorio — es el desglose ejecutable de la
  sección "Fase 23" de `docs/ROADMAP.md`, con archivos, snippets y decisiones de arquitectura
  concretas para que un `backend-engineer` pueda partir directamente de acá. No hay tareas de
  `frontend-engineer` en esta fase (Decisiones G5 y la ausencia de superficie de UI en §23.2).
- La decisión más delicada de esta spec (G1) fue verificada estructuralmente, no solo contra el
  ejemplo del ROADMAP: se confirmó que "cuenta nunca verificada al momento del login de Google"
  es una propiedad necesaria de cualquier variante del ataque (no una casualidad del caso de
  prueba), y que excluir a las cuentas ya verificadas no deja ningún hueco — el dueño real de una
  cuenta ya verificada, por definición, ya demostró control del email antes de que Google entrara
  en juego.
- Ningún archivo del repositorio fuera de `docs/specs/fase_23_spec.md` fue modificado al producir
  este documento — sigue siendo, en su totalidad, un documento de planificación.
