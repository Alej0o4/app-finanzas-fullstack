# Spec — Fase 31: Corrección de los hallazgos de la QA 2026-09-26

> Sintetiza el `/grilling` del 2026-09-27, registrado en `docs/ROADMAP.md` §"Fase 31 — planeada"
> (decisiones **Q1–Q16** y 3 supuestos aceptados), y los ítems `QA-001`…`QA-022` de
> `docs/TODO.md` (reporte completo en `.scratch/qa-2026-09-26/REPORTE_QA.md`, no versionado).
> Esas decisiones las tomó el dueño y esta spec no las reabre. Las cita por su número y las baja a
> decisiones implementables **B** (backend), **F** (frontend), **I** (infra), **T** (testing) y
> **D** (docs), con la misma convención que `fase_29_spec.md` y `fase_30_spec.md`.
>
> Antes de escribirla se contrastó el grilling con el código real (2026-09-27, `main` @
> `0af4002`). Hay catorce hallazgos que precisan cómo se implementan varias decisiones; uno cambia
> un comportamiento de sesión que el dueño notaría y quedó como marcador (B10), resuelto por el
> dueño el mismo día (ver "Decisiones resueltas con el usuario"). El resto se resolvió como
> decisión. Ver "Hallazgos de exploración".
>
> **No implementa nada.** Solo se agregó este archivo.

**Estado:** spec escrita el 2026-09-27. El único marcador (B10) y los seams de testing los
confirmó el dueño el mismo día; sin marcadores abiertos. `/analyze-spec 31` (2026-09-27): sin
CRÍTICO/ALTO; los 4 MEDIO y 4 BAJO se aplicaron a esta spec. Siguiente paso: implementar.

---

## Problem Statement

La primera pasada de QA (2026-09-26) encontró 22 problemas. Varios rompen las dos garantías
centrales de Oikos:

- **El backend es la fuente de verdad de los saldos, y hoy no lo es bajo concurrencia.** Dos
  `DELETE` o dos `PUT` casi simultáneos sobre la misma transacción (un reintento de red, dos
  pestañas, un atajo por API key) mueven el saldo dos veces. En Postgres se reprodujo con
  discrepancias de hasta 200 sobre un gasto de 50, y en el caso mixto la transacción queda borrada
  con el monto editado. Montos o saldos por encima de `Numeric(14,2)` dan `500` en vez de un error
  de validación. El contador de `GET /transactions` cuenta las borradas y deja un "Cargar más"
  eterno. Un ingreso registrado en el último segundo del mes desaparece del dashboard de ese mes.
- **El dueño puede quedar afuera de su propia app.** Una cookie `csrf_token` huérfana (por
  ejemplo, después de resetear la contraseña desde otro dispositivo) deja `/login` recargándose
  cinco veces por segundo, sin forma de iniciar sesión sin borrar cookies a mano. Un `422` de
  Pydantic (`detail` en forma de lista) tumba la página entera y se pierde lo escrito.

A eso se suman montos que se muestran mal (todo redondeado a la unidad, también USD; un anillo de
presupuesto que dice 100% cuando va en 106%; "Te quedan" que no cuadra con "Ingresos del mes"), un
onboarding que nunca aparece para quien se registra con contraseña, errores de API disfrazados de
"no tenés movimientos", un modal de edición que muestra una categoría y envía otra, y un entorno
"dev" de Docker que, corrido en la máquina de despliegue, reemplaza los contenedores de producción
y escribe en la base real.

## Solution

- **Integridad contable.** `PUT` y `DELETE /transactions/{id}` bloquean la fila de la transacción
  al empezar, y el borrado es condicional: una segunda petición sobre una transacción ya borrada
  recibe `404` sin tocar el saldo. Los montos se validan contra el rango real de la columna (12
  dígitos enteros, 2 decimales) y un saldo que desbordaría responde `422`. El `total` del listado
  deja de contar las borradas. Los meses cerrados se acotan con un límite superior exclusivo. Una
  `Idempotency-Key` reusada con otro payload responde `409` también cuando pierde la carrera. La
  sesión de Postgres se fija en UTC.
- **Sesión que no se traba.** El `401` de `POST /auth/refresh` borra las cookies de sesión, y el
  interceptor del frontend no redirige a `/login` si ya está en una pantalla de autenticación.
- **Errores legibles.** Cualquier `detail` (texto, lista de Pydantic u objeto) se muestra como
  texto. Los formularios con montos validan decimales y dígitos antes de enviar, con error de
  campo visible. `/transactions` distingue "falló la consulta" de "no hay movimientos", no consulta
  un rango de fechas invertido y no esconde los filtros mientras reintenta.
- **Onboarding.** El login con contraseña y el de Google deciden el onboarding con el mismo
  criterio: sin historial → `/capture?onboarding=1`, y el wizard solo pide moneda e ingreso si el
  ingreso esperado todavía no está fijado.
- **Montos bien mostrados.** Decimales según la moneda (COP sin centavos salvo que los haya; USD
  y el resto siempre con dos). El balance del mes es siempre ingreso real − gasto real, con el
  ingreso declarado como referencia visual ("esperado"). El anillo de presupuesto muestra el
  porcentaje real y dibuja el exceso como una segunda vuelta. El detalle de cuenta y de categoría
  muestra los últimos 20 movimientos con un link a la lista completa filtrada.
- **Categorías.** El modal de edición gana el toggle "ver todas" del modal de creación; lo que se
  ve en el `<select>` siempre es lo que se envía.
- **Entorno dev aislado.** El override de Docker dev tiene nombre de proyecto, volumen de base y
  puertos propios (3001/8001), y no levanta el servicio de backup.

## User Stories

**Integridad de saldos (QA-003, QA-015, QA-006, QA-019, QA-020, QA-022)**

1. Como dueño, quiero que borrar dos veces la misma transacción (doble envío, reintento de red,
   dos pestañas) revierta el saldo una sola vez, para que el saldo de la cuenta siga siendo cierto.
2. Como dueño, quiero que el segundo borrado reciba "no existe" en vez de un "OK" falso, para
   saber que no pasó nada más.
3. Como dueño, quiero que dos ediciones simultáneas de la misma transacción se apliquen una
   después de la otra, cada una sobre el monto que dejó la anterior, para que el saldo final
   corresponda al último monto guardado.
4. Como dueño, quiero que editar una transacción que otra pestaña acaba de borrar dé "no existe",
   para no aplicar la edición sobre algo borrado.
5. Como dueño, quiero que una edición y un borrado simultáneos dejen la cuenta conciliada, sea
   cual sea el orden en que lleguen, para que `reconcile` nunca encuentre diferencias por esto.
6. Como dueño que usa atajos por API key, quiero que mis reintentos automáticos no puedan
   descuadrar un saldo, para confiar en el atajo del celular.
7. Como dueño, quiero que un monto de 13 dígitos enteros o con más de 2 decimales se rechace como
   dato inválido, para no ver "Error interno" por un error de tipeo.
8. Como dueño, quiero que un saldo inicial de cuenta, un ingreso esperado o un límite de
   presupuesto fuera de rango también se rechacen como dato inválido, para no ver una página de
   error en texto plano.
9. Como dueño, quiero que un ingreso que haría desbordar el saldo de una cuenta se rechace con un
   mensaje claro y sin tocar el saldo, para entender qué pasó.
10. Como dueño, quiero que "Cargar más" en `/transactions` desaparezca cuando ya vi todo, para no
    hacer clic en páginas vacías.
11. Como dueño, quiero que el contador "N de M" de `/transactions` no cuente las transacciones que
    borré, para que el número cuadre con la lista.
12. Como dueño, quiero que un movimiento registrado a las 23:59:59 y fracción del último día del
    mes cuente en ese mes, en el dashboard, en los presupuestos y en las alertas, para que el mes
    cerrado cuadre con Analítica y con la lista.
13. Como dueño, quiero que un movimiento de las 00:00 del día 1 cuente en su mes y no en el
    anterior, para que los bordes no se dupliquen.
14. Como cliente de la API, quiero que reusar una `Idempotency-Key` con otro payload responda
    `409` aunque las dos peticiones lleguen al mismo tiempo, para detectar el bug del cliente en
    vez de recibir una transacción ajena.
15. Como dueño, quiero que los gráficos por día y el resumen del mes no dependan de la zona
    horaria configurada en Postgres, para que restaurar la base en otro servidor no mueva mis
    totales.

**Sesión e inicio (QA-021, QA-005)**

16. Como dueño, quiero poder iniciar sesión aunque mi navegador tenga una cookie de sesión vieja,
    para no quedar atrapado en una pantalla que se recarga sola.
17. Como dueño, quiero que después de resetear la contraseña desde el celular, el navegador de la
    computadora me mande al login una vez y me deje entrar, para no tener que borrar cookies.
18. Como dueño, quiero que el login y el refresh sigan funcionando como hoy (cookies `httpOnly`,
    CSRF, una sola llamada de refresh aunque fallen varias requests a la vez), para no perder la
    base de la Fase 26.
19. Como usuario nuevo registrado con contraseña, quiero ver el onboarding (moneda e ingreso)
    después de verificar el correo e iniciar sesión, para configurar la app en tres minutos.
20. Como usuario nuevo con Google, quiero el mismo onboarding, decidido con el mismo criterio,
    para que las dos formas de entrar se comporten igual.
21. Como usuario que ya fijó su ingreso esperado pero todavía no registró dos movimientos, quiero
    que el login me lleve directo a la captura guiada sin volver a preguntarme moneda ni ingreso,
    para no repetir pasos.
22. Como dueño recurrente, quiero que el login me siga llevando al dashboard, como hoy.

**Errores y validación (QA-004, QA-010, QA-013)**

23. Como dueño, quiero que un error de validación del servidor aparezca como un mensaje legible,
    para no perder la página ni lo que escribí.
24. Como dueño, quiero que el formulario me avise antes de enviar si el monto tiene más de dos
    decimales o más de 12 dígitos enteros, con el error junto al campo, para corregirlo en el
    momento.
25. Como dueño, quiero ese mismo aviso en `/capture`, en los modales de crear y editar movimiento,
    en el ingreso esperado (onboarding, dashboard y ajustes), en el saldo inicial de una cuenta y
    en el límite de un presupuesto, para que todos los montos se comporten igual.
26. Como usuario en el onboarding, quiero que "Continuar" con el ingreso vacío o negativo me diga
    qué está mal, para no pensar que el botón no funciona.
27. Como dueño, quiero que si `/transactions` no puede cargar, me lo diga con un botón
    "Reintentar", para no creer que perdí mis movimientos.
28. Como dueño, quiero que los filtros de `/transactions` sigan visibles mientras la app
    reintenta, para poder cambiarlos sin esperar.
29. Como dueño, quiero que si pongo una fecha final anterior a la inicial me lo diga junto al
    campo y no consulte nada, para entender por qué no hay resultados.
30. Como dueño, quiero que el selector de fechas no me ofrezca, de entrada, una fecha final
    anterior a la inicial, para equivocarme menos.

**Montos (QA-007, QA-008, QA-011, QA-012)**

31. Como dueño, quiero ver los centavos de un gasto en USD o EUR (US$ 0,10, no US$ 0), para que
    los montos chicos no desaparezcan.
32. Como dueño, quiero que los montos en COP se sigan viendo sin centavos, salvo que el monto
    tenga centavos de verdad, para no llenar la pantalla de ",00".
33. Como dueño, quiero que los ejes y las etiquetas sobre las barras de los gráficos sigan sin
    decimales, para que no se amontonen.
34. Como dueño, quiero que el número grande de la tarjeta del dashboard sea "Balance de
    <mes>" = ingresos reales − gastos reales, igual en el mes en curso que en los meses cerrados,
    para que cuadre a simple vista con "Ingresos del mes" y "Gastos del mes".
35. Como dueño, quiero entender que un balance negativo a principio de mes es normal, viendo junto
    a "Ingresos del mes" cuánto espero cobrar ("esperado $3.000"), para no asustarme antes de
    cobrar.
36. Como dueño, quiero poder fijar mi ingreso esperado desde el dashboard si todavía no lo hice,
    para no tener que ir a Ajustes.
37. Como dueño, quiero que los textos del onboarding, de Ajustes y del dashboard no me prometan
    que el ingreso esperado calcula algo, para no confundirme.
38. Como dueño, quiero que el anillo de un presupuesto excedido diga el porcentaje real (106%), el
    mismo que la notificación, para no ver dos números distintos.
39. Como dueño, quiero ver el exceso dibujado como una segunda vuelta en un rojo más intenso, para
    notar de un vistazo cuánto me pasé.
40. Como dueño, quiero que un exceso enorme no deforme el anillo (tope visual en 200%), sin que el
    texto deje de mostrar el valor real.
41. Como dueño, quiero que el detalle de una cuenta o de una categoría me muestre los últimos 20
    movimientos y un link "Ver todos los movimientos", para llegar a la lista completa filtrada y
    paginada sin que nada quede cortado en silencio.

**Categorías (QA-009)**

42. Como dueño, quiero que al editar un movimiento la categoría que veo en el selector sea la que
    se guarda, para no reclasificar sin querer.
43. Como dueño, quiero poder editar un reembolso (un ingreso en "Restaurante") y que el modal
    arranque mostrando todas las categorías, para no perder la categoría original.
44. Como dueño, quiero que si cambio el tipo del movimiento y la categoría elegida deja de estar
    visible, el selector vuelva a "Selecciona…", para elegir a conciencia.
45. Como dueño, quiero que el modal de creación siga la misma regla al cambiar el tipo o apagar
    "ver todas", para que los dos modales se comporten igual.
46. Como dueño, quiero que la regla de reembolsos (un ingreso en una categoría de gasto) quede
    escrita, con su limitación actual, para recordar por qué la app lo permite.

**Entorno (QA-001)**

47. Como dueño, quiero que el comando dev de `CLAUDE.md` levante un stack aparte, con su propia
    base y en otros puertos, para no pisar producción en la máquina de despliegue.
48. Como dueño, quiero que el stack dev no suba backups al remoto de producción, para que la
    rotación de 30 días no desplace backups reales.
49. Como dueño, quiero que el stack dev no mande correos reales con links a producción, para no
    recibir mails de prueba que apuntan al dominio real.
50. Como dueño, quiero que el comando para sembrar datos de prueba diga explícitamente contra qué
    stack corre, para no volver a crear el usuario semilla en producción.

## Hallazgos de exploración

Contraste del grilling y de `docs/TODO.md` con el código del 2026-09-27. Las referencias
archivo:línea del ROADMAP y del TODO están vigentes, salvo donde se indica.

**H1. El `401` de refresh no puede limpiar cookies lanzando la excepción (afecta Q5).**
`refresh` (`backend/app/api/auth.py:163`) recibe un `response: Response` inyectado, pero sus dos
`401` se lanzan como `UnauthorizedError`. El handler de `DomainError` (`main.py:166`) construye un
`JSONResponse` nuevo y los headers del `Response` inyectado se pierden. Llamar a
`limpiar_cookies_de_sesion(response)` y después `raise` **no borra nada**. Hay que devolver el
`JSONResponse(401)` a mano con las cookies borradas (ver B10). Aplica a las dos ramas: sin cookie
ni body, y token desconocido/revocado/expirado.

**H2. Borrar cookies en el `401` de refresh tiene una carrera entre pestañas (afecta Q5).**
Si dos pestañas refrescan a la vez con el mismo refresh token, una rota (Set-Cookie nuevo) y la
otra recibe `401`. Con Q5, ese `401` borra las cookies; si su respuesta llega después, deja sin
sesión a **las dos** pestañas. Hoy la pestaña perdedora solo redirige a `/login`. Es poco
probable (el badge de notificaciones consulta cada 60 s por pestaña y los navegadores frenan los
timers de pestañas en segundo plano), pero es un cierre de sesión que el dueño notaría. Fue
marcador en B10; el dueño eligió aceptar la carrera (opción a).

**H3. El formulario inline de ingreso vive en la rama `null` que Q9 elimina (afecta Q9/Q14).**
En `app/(dashboard)/page.tsx` el formulario "Define tu ingreso mensual" solo se renderiza cuando
`monthly_flow_balance` es `null`. Con Q9 el balance nunca es `null`, así que el formulario
desaparecería en silencio, en contra de Q14. Se reubica (F8). Además, el banner "aha" del
onboarding (`?onboarding=1`) y el copy del paso de ingreso y de Ajustes prometen "cuánto te
queda", que Q14 pide ajustar.

**H4. `monthly_income` no se usa en ningún otro cálculo del backend (acota Q9).** Verificado:
fuera de `obtener_resumen` (`api/dashboard.py:184-193`), `monthly_income` solo aparece en el
modelo, los schemas de usuario y `seed.py`. El resumen semanal, las alertas de presupuesto, el push
y `monthly-summary` de cuenta no lo leen. El radio de Q9 es el endpoint `summary`, el dashboard del
frontend, sus tests y la documentación. Los comentarios de `schemas/accounts.py:54-57` y
`api/accounts.py:132`, que contrastan con el balance "nullable" del dashboard, quedan
desactualizados, igual que los comentarios de frontend que hacen el mismo contraste
(`components/charts/AccountMonthlyBalanceCard.tsx:16-20` y `app/(dashboard)/accounts/[id]/page.tsx:317`).

**H5. El onboarding ya siembra el ingreso declarado como transacción real (contexto de Q9).**
`OnboardingIncomeStep` crea una transacción de ingreso "Ingreso mensual declarado" en "Salario"
por el monto declarado. Para quien completa el onboarding, el balance real del primer mes ya
incluye ese ingreso y Q9 no le cambia el número. Además, esa transacción cuenta para
`has_transaction_history` (2 o más): onboarding + primera captura = historial, y el siguiente login
va al dashboard.

**H6. El paso de moneda parpadea mientras carga el usuario (afecta Q4).** Con la condición de Q4
(`monthly_income == null`), mientras `useCurrentUser` carga, `user` es `undefined` y
`undefined == null` es `true`: el paso de moneda se mostraría un instante a un usuario que ya fijó
su ingreso. El paso de ingreso ya tiene el mismo problema. El wizard espera al usuario (F5).

**H7. El overflow del saldo en `DELETE` escapa del `try` (afecta QA-015).** En
`eliminar_transaccion` (`api/transactions.py:292-293`) `ledger.revertir_impacto` corre **fuera**
del `try/except`. Revertir un gasto sobre una cuenta en el tope de `Numeric(14,2)` levanta un
`DataError` sin capturar: `500` en texto plano, no el `InternalServerError` de dominio. B1 cambia el
orden de todos modos y B4 cubre el caso.

**H8. Hay un cuarto campo de dinero sin `max_digits`: `BudgetBase.amount_limit` (amplía QA-015).**
La QA probó transacciones, cuentas y `users/me`. `amount_limit` (`schemas/budgets.py`) tiene la
misma forma (`gt=0, decimal_places=2`, sin `max_digits`) contra `Numeric(14,2)`. Son exactamente
cuatro campos de entrada con dinero, y los cuatro entran en B3. Verificado con Pydantic 2.13.4:
`max_digits=14, decimal_places=2` acepta `999999999999.99`, rechaza `1000000000000.00` y
`1E+12` (`decimal_whole_digits`) y `0.001` (`decimal_max_places`), y no se confunde con ceros
finales (`12.340` pasa). Los mensajes de Pydantic están en inglés; con la validación del cliente
(F2) solo los vería un cliente por API key.

**H9. `with_entities(func.count())` es el único conteo que se salta el filtro de borrado
lógico (acota QA-006).** El filtro global de `core/database.py` agrega `deleted_at IS NULL` a los
`SELECT` que tienen una entidad mapeada; `func.count()` solo no tiene entidad y el criterio no se
aplica. Hay dos usos en todo el backend: `api/transactions.py:261` (el bug) y
`api/notifications.py:36` (`Notification` no tiene `SoftDeleteMixin`, así que no aplica).

**H10. `limites_mes_utc` tiene cuatro consumidores y cinco comparaciones `<=` (afecta QA-019).**
`api/dashboard.py` (ingresos y gastos de `summary`, y `_monedas_con_gasto`),
`core/budget_alerts.py` (`spent_por_categoria_y_moneda`, que alimenta `budgets-progress` y las
alertas) y `api/accounts.py` (`monthly-summary`, que solo consulta el mes en curso). Pasar a un
límite exclusivo exige cambiar las cinco comparaciones a la vez: una que quede en `<=` contra "el
primer día del mes siguiente" contaría la medianoche del mes siguiente, en silencio. Por eso B6
renombra la función. `BUSINESS_RULES.md` (§Dashboard) también dice "hasta el último día a las
23:59:59".

**H11. La misma familia de QA-019 está en el filtro de `/transactions` (fuera de alcance).**
`transactions/page.tsx` convierte la fecha final a `T23:59:59` sin fracción y Analítica manda
`23:59:59.999Z`. Un movimiento a las 23:59:59,5 queda fuera del filtro "hasta el día X" de
`/transactions`. No está en la QA ni en Q1: queda anotado para flujo corto (ver Out of Scope).

**H12. `aplicar_edicion` puede generar un deadlock entre cuentas (amplía QA-003).** Cuando un
`PUT` mueve una transacción de cuenta, `ledger.aplicar_edicion` actualiza primero la cuenta vieja y
después la nueva. Dos `PUT` concurrentes que muevan transacciones distintas en sentidos opuestos
(A→B y B→A) toman los locks de las cuentas en orden inverso: Postgres aborta una con
`DeadlockDetected` y el usuario ve un `500` (el saldo queda bien por el rollback). Ordenar los dos
`UPDATE` por `account_id` lo elimina sin bloquear cuentas: los deltas conmutan. No contradice Q2
(no agrega locks, solo fija un orden). Ver B2.

**H13. Q10 también aplica al modal de creación (amplía QA-009).** `TransactionModal` no resetea
`categoryId` al cambiar el tipo ni al apagar "ver todas": el `<select>` queda con un valor que no
está entre las opciones visibles y el navegador muestra la primera, igual que el bug de edición.
`TransactionCaptureForm` sí resetea al cambiar el tipo. Además, `TransactionModal` valida con los
globos nativos del navegador (sin `noValidate` ni errores de campo), a diferencia del resto de los
formularios desde la Fase 12 §12.8. F2 y F11 lo alinean.

**H14. `pnpm gen:types` apunta a `http://localhost:8000`, que en esta máquina es producción
(afecta Q9 y Q13).** El script de `frontend/package.json` genera los tipos desde el backend de
producción, que no tiene los contratos nuevos de esta fase. Con el stack dev en `:8001` (Q13), el
script tiene que apuntar ahí (I2). `DashboardSummary` cambia de contrato (Q9), y regenerar contra
`:8000` dejaría el tipo viejo en silencio.

Otros datos que ubican el trabajo:

- **El `conftest.py` no sirve para el test concurrente tal cual.** El fixture `db_session` corre
  cada test dentro de una transacción externa sobre una sola conexión que se revierte al final:
  otra conexión nunca ve esos datos. El test concurrente de QA-003 necesita commits reales, una
  sesión por request y limpieza propia (T2).
- **`test_seed.py` crea su propio engine SQLite** y no se ve afectado por `TEST_DATABASE_URL`.
- **Compose instalado: v5.5.0.** `!override` existe desde Compose 2.24.4. Se verificó con
  `docker compose config` sobre una copia en `/tmp`: sin `!override` los puertos se suman
  (8000 **y** 8001); con `!override` queda solo 8001; `name: oikos-dev` convierte el volumen en
  `oikos-dev_pgdata`; y `profiles: ["backup"]` saca a `backup` de `config --services`.
- **El stack dev lee el `.env` de producción.** Con `EMAIL_PROVIDER=smtp` y `FRONTEND_URL` de
  producción, un registro en dev mandaría un correo real con un link al dominio real. I1 lo
  sobreescribe.
- **El comando de seed de `CLAUDE.md` corre contra producción.** `docker compose exec backend …
  run_seed()` sin `-f`/`-p` apunta al proyecto por defecto, que es el de producción. Es la causa
  más probable de QA-002. D3 lo corrige junto con el comando dev.
- **`BudgetRing` recalcula el porcentaje en el cliente** (`spent / limit`) aunque
  `BudgetProgress.percentage` ya viene del backend, en contra de la regla de `CLAUDE.md` de no
  recomputar agregados en el frontend. Los dos consumidores (dashboard y detalle de cuenta) tienen
  `percentage` a mano. F9 lo usa.
- **Referencia desactualizada del ROADMAP:** "los presupuestos solo suman gastos
  (`core/budget_alerts.py:29`)". El filtro `type == "expense"` está en la línea 60; la 29 es la
  tabla de umbrales. El hecho es correcto.
- **`getApiError` se usa en 12 archivos** (el TODO dice 13 contando `utils.ts`). Además,
  `reset-password` y `verify-email` tienen su propio extractor, y el de `verify-email` tiene el
  mismo bug de `detail` en lista. El `detail` objeto que existe hoy es el de
  `EMAIL_NOT_VERIFIED`, con claves `code` y **`mensaje`** (en español).
- **`frontend/` no tiene test runner.** La verificación del frontend es con Playwright, como en
  las Fases 29 y 30.

## Implementation Decisions

### Backend

**B1. `PUT` y `DELETE /transactions/{id}` se serializan sobre la fila de la transacción (Q2,
QA-003).**

- Las dos rutas leen la transacción con `SELECT … FOR UPDATE` como **primera** consulta, filtrando
  por `id`, `user_id` y `deleted_at IS NULL` (el filtro global ya lo agrega; se deja explícito en
  el `WHERE` porque es lo que hace que Postgres, al liberar el lock, reevalúe la fila y devuelva
  vacío si otra petición la borró). Sin fila → `404`, igual que hoy.
- `DELETE` pasa a este orden, todo dentro del `try`:
  1. `UPDATE transactions SET deleted_at = now WHERE id = :id AND user_id = :uid AND deleted_at IS
     NULL` (borrado condicional, segunda defensa de Q2).
  2. Si no afectó filas → rollback y `404` ("La transacción no existe o no tienes permisos."), sin
     tocar el saldo.
  3. Solo con una fila afectada, `ledger.revertir_impacto` sobre la cuenta (si la cuenta no está
     borrada, como hoy).
  4. Commit.
  Hoy el orden es el inverso (revierte el saldo y después marca `deleted_at` sin condición), que
  es justamente lo que permite revertir dos veces.
- `PUT` no cambia su lógica: el delta se calcula sobre el `amount`/`type`/`account_id` de la fila
  bloqueada, que en Postgres es la versión que dejó la petición anterior. La segunda defensa
  condicional aplica solo a `DELETE`: el `UPDATE` del ORM en `PUT` va por clave primaria, y su
  seguridad descansa en el lock.
- **No se bloquean las cuentas** (Q2): el `UPDATE accounts SET balance = balance + x` de
  `services/ledger.py` ya es atómico. Orden de locks resultante: transacción → cuenta(s), igual en
  `PUT` y `DELETE`; `POST` solo toca la cuenta. No hay ciclo.
- `ledger.py` no cambia de contrato (Decisión L2 de la Fase 25: el router es dueño del
  `commit`/`rollback`).
- En SQLite `with_for_update()` no genera nada y la suite sigue corriendo.

**B2. `aplicar_edicion` aplica sus dos `UPDATE` en orden de `account_id` (H12).**

- Cuando la cuenta vieja y la nueva son distintas, se ejecutan los dos `aplicar_delta` ordenados
  por `account_id` ascendente. El resultado es el mismo (los deltas conmutan). Evita el deadlock
  entre dos `PUT` que mueven transacciones en sentidos opuestos.
- Mismo `UPDATE` único cuando la cuenta no cambia.

**B3. Validación de rango en los cuatro campos de dinero de entrada (QA-015, H8).**

- `max_digits=14` (junto al `decimal_places=2` que ya tienen) en `TransactionBase.amount`,
  `AccountCreate.balance`, `UserProfileUpdate.monthly_income` y `BudgetBase.amount_limit`. Es el
  rango real de `Numeric(14,2)`: 12 dígitos enteros y 2 decimales.
- El número vive una sola vez: una constante en `app/schemas/common.py` (junto a un comentario
  que la ata a `Numeric(14,2)` de `models.py`) que usan los cuatro `Field`.
- Resultado: `422` de Pydantic, con `detail` en lista, antes de llegar a la base. El
  `500` en texto plano de `POST /accounts` y `PATCH /users/me` desaparece porque el dato ya no
  llega al `commit`.

**B4. El overflow del saldo es un `422` de dominio (QA-015, H7).**

- En `crear_transaccion`, `actualizar_transaccion` y `eliminar_transaccion`, un
  `sqlalchemy.exc.DataError` durante la escritura se captura **antes** del `except Exception`
  genérico, hace rollback y levanta `ValidationError` (la de `core/exceptions.py`, 422) con
  `detail` string: "La operación dejaría el saldo de la cuenta fuera del rango permitido."
- Con B3 el monto en sí ya es válido, así que en estas tres rutas el único `DataError` posible es
  el desborde del `UPDATE` del saldo (`NumericValueOutOfRange`). En SQLite no ocurre (no aplica
  `Numeric`).
- `ledger.py` no captura nada (Decisión L2).
- Contrato de error (Q6): `422` con `detail` string, la misma forma que ya usan los 422 de dominio
  de `core/periods.py`. El frontend lo muestra con `getApiError` (F1).

**B5. `total` de `GET /transactions` sin las borradas (QA-006, H9).**

- La consulta base del listado lleva `Transaction.deleted_at.is_(None)` explícito, así el conteo
  y la página comparten exactamente los mismos filtros. Se deja un comentario con el motivo
  (el filtro global no alcanza a `func.count()`).

**B6. Los meses se acotan con límite superior exclusivo (QA-019, H10).**

- `core/periods.limites_mes_utc` pasa a devolver un rango semiabierto `[inicio, fin)`:
  - mes cerrado o futuro: `fin` = primer día del mes siguiente a las 00:00 (diciembre → 1 de enero
    del año siguiente);
  - mes en curso: `fin` = `ahora` (como hoy).
- Se renombra a `rango_mes_utc` para que cada consumidor deje de compilar hasta que se revise su
  comparación. Las cinco comparaciones de H10 pasan de `<=` a `<`: `summary` (ingresos y gastos),
  `_monedas_con_gasto`, `spent_por_categoria_y_moneda` y `monthly-summary`.
- Todo lo demás de la función queda igual: naive UTC, no valida, no lanza por mes futuro (el
  motivo está en su docstring y no cambia).
- `resolver_mes` no cambia. `cashflow-series` y `category-distribution` no usan este módulo
  (reciben `start_date`/`end_date` del cliente) y no cambian.

**B7. `Idempotency-Key` con otro payload en carrera → `409` (QA-020).**

- La lógica de "ya existe una clave" se extrae a un helper privado del router que usan las dos
  ramas (la consulta previa y el `except IntegrityError`):
  - `request_hash` distinto → `ConflictError` ("Esta Idempotency-Key ya se usó con datos
    distintos.");
  - transacción original borrada → `ConflictError` ("La transacción original de esta
    Idempotency-Key ya no existe.");
  - si no, devuelve la transacción original.
- Hoy la rama `except IntegrityError` devuelve la transacción sin comparar el hash, y si la
  original estaba borrada devuelve `None` (un `500` de validación de respuesta). El helper cierra
  los dos casos (Decisión 10.4.3 de la Fase 10).

**B8. La sesión de Postgres siempre en UTC (QA-022).**

- `core/database.py` expone una función que arma los `kwargs` del engine según la URL:
  `check_same_thread=False` para SQLite (como hoy) y `connect_args={"options": "-c
  timezone=UTC"}` para Postgres. El engine de la app la usa, y el `conftest.py` también (T1), así
  la suite contra Postgres corre con la misma sesión que producción.
- Alembic (`alembic/env.py`) arma su propio engine y no se toca: las migraciones no dependen de la
  zona horaria de la sesión.

**B9. El balance del mes es siempre ingreso real − gasto real (Q9, Q14, H4).**

- En `obtener_resumen`, `monthly_flow_balance` se calcula igual en el mes en curso que en un mes
  cerrado: ingresos reales del período en la moneda preferida menos gastos reales en la moneda
  preferida, desde las mismas filas agrupadas (mismas cuentas destacadas, mismo rango de B6). Nunca
  `null`: sin filas vale `0.00`. Puede ser negativo, y es correcto (Q9).
- `User.monthly_income` deja de participar en cualquier cálculo del backend. El campo, su
  `PATCH /users/me` y su validación (B3) se quedan: es la referencia visual de Q14.
- Contrato de `DashboardSummary`:
  - `monthly_flow_balance: Decimal`, sin `| None`.
  - `monthly_flow_basis` se conserva, siempre `"actual"`. El tipo se estrecha a
    `Literal["actual"]` y el campo se marca `deprecated` en el schema (sale como
    `deprecated: true` en OpenAPI). Sigue sin default, por el mismo motivo que documenta el
    schema (Fase 29 B2/B6).
- Se actualizan los comentarios desactualizados de H4 (`schemas/dashboard.py`,
  `schemas/accounts.py`, `api/accounts.py`, y en el frontend
  `components/charts/AccountMonthlyBalanceCard.tsx` y `app/(dashboard)/accounts/[id]/page.tsx`).

**B10. El `401` de `POST /auth/refresh` borra las cookies de sesión (Q5, H1, H2).**

- Las dos ramas de `401` de `refresh` devuelven un `JSONResponse(status_code=401, content={"detail":
  "Refresh token inválido o expirado"})` construido a mano, sobre el que se llama
  `auth_cookies.limpiar_cookies_de_sesion`, en vez de lanzar `UnauthorizedError` (que perdería el
  `Set-Cookie`, H1). El cuerpo es idéntico al de hoy.
- El resto de `refresh` no cambia: rotación, revocación del token usado, cookies nuevas en el
  éxito, body opcional para clientes no-browser.
- `haySesionActiva()` no cambia (Q5).
- El `401` borra las cookies **siempre**, también cuando el token presentado se acaba de revocar
  por una rotación legítima de otra pestaña (H2): en esa carrera, rara, las dos pestañas pierden
  la sesión y se vuelve a iniciar sesión. Se descarta la excepción por umbral de revocación
  reciente (una consulta más y un umbral fijo). Resuelto por el dueño el 2026-09-27 (opción a).
- Pasa por `security-reviewer` antes de cerrar (Q5, paso 9 de `docs/WORKFLOW.md`), junto con F4.

### Frontend

**F1. `getApiError` aplana cualquier `detail` a texto (Q6, QA-004).**

- `lib/utils.ts`:
  - `detail` string → tal cual;
  - lista (Pydantic) → los `msg` unidos con un espacio, sin el prefijo "Value error, " que agrega
    Pydantic a los `ValueError` de validadores propios;
  - objeto → `mensaje` (la clave que usa el backend en `EMAIL_NOT_VERIFIED`, ver "Otros datos"
    en Hallazgos), o `message`, o `msg`;
  - cualquier otra cosa, o vacío → el fallback de hoy ("Ocurrió un error inesperado").
- Nunca devuelve algo que no sea `string`: es lo que evita el "Objects are not valid as a React
  child".
- Los extractores propios de `verify-email/page.tsx` (con el mismo bug) y
  `reset-password/page.tsx` (ya correcto) pasan a usar `getApiError`, con su fallback como segundo
  argumento opcional. `login` y `register` no cambian: leen `detail.code` y el `status` para
  decidir el mensaje, y no pasan `detail` crudo a JSX.

**F2. Validación de montos antes de enviar, con error de campo (Q6, QA-013).**

- Un helper puro nuevo en `lib/` valida el **texto** del input (no el `Number`, para contar
  decimales exactos): vacío, no numérico, negativo (o cero, según el campo), más de 2 decimales,
  más de 12 dígitos enteros. Devuelve el mensaje en español o `null`. Los límites son los de B3.
- Se usa en todos los formularios que envían dinero, con el patrón de la Fase 12 §12.8 / Fase 24
  §24.2 (error bajo el campo, foco en el primer campo con error, `noValidate`):
  - `TransactionCaptureForm` (`/capture`), `TransactionModal`, `EditTransactionModal`
    (monto > 0);
  - `OnboardingIncomeStep`, el formulario inline del dashboard y el de Ajustes (ingreso ≥ 0);
  - el modal de creación de cuenta en `/accounts` (saldo inicial ≥ 0);
  - el formulario de `/budgets` (límite > 0).
- `TransactionModal` pasa a `noValidate` con errores de campo, como el resto (H13).
- Un error del servidor sigue yendo a `toast.error(getApiError(error))` y el formulario conserva lo
  escrito (el modal no se cierra ni se resetea en `onError`, como hoy).
- QA-013: el paso de ingreso del onboarding y el formulario de Ajustes dejan de hacer `return`
  silencioso con un valor vacío o negativo: muestran el error bajo el campo. Además, el
  `mutateAsync` del paso de ingreso se envuelve para que un error del servidor se muestre y el
  paso no avance.

**F3. Categoría visible = categoría enviada, en los dos modales (Q10, QA-009, H13).**

- `EditTransactionModal` gana el toggle "+ Mostrar todas las categorías / ← Solo del tipo" de
  `TransactionModal`, con el mismo rótulo "(Ingreso)/(Gasto)" en las opciones cuando está activo.
- El toggle arranca **activado** si la categoría actual de la transacción es de la otra
  naturaleza que su tipo (un reembolso).
- Regla común a los dos modales: si al cambiar el tipo o al apagar el toggle la categoría elegida
  deja de estar entre las opciones visibles, se resetea a "Selecciona…" y el error de campo pide
  elegir una.
- Las categorías ocultas ("oculta para mí", Fase 18) no se listan, salvo la categoría actual de
  la transacción en edición, que siempre aparece.
- La regla vive en una función pura compartida (lista visible según tipo, toggle y categoría
  actual), para que los dos modales no la dupliquen.
- Sin cambios en el backend: sigue aceptando cualquier combinación tipo/categoría (Q10).

**F4. El interceptor no redirige desde una pantalla de autenticación (Q5, QA-021).**

- `lib/authSession.ts` exporta la lista de rutas del grupo `(auth)` (`/login`, `/register`,
  `/forgot-password`, `/reset-password`, `/verify-email`) y un predicado sobre el `pathname`.
- En `lib/api.ts`, cuando falla el refresh: se rechaza la cola (`processQueue(error)`) y la request
  original como hoy, pero `window.location.href = '/login'` solo se ejecuta si la ruta actual **no**
  es de autenticación.
- No cambia nada más del interceptor: el guard de `auth/refresh`, el mutex `isRefreshing`, la cola
  `failedQueue`, el `_retry`, ni el header CSRF (Fase 26, Hallazgo 3).
- Con B10 la cookie huérfana se borra en el primer `401` de refresh y `haySesionActiva()` pasa a
  `false`; con F4, aunque B10 fallara, `/login` ya no entra en bucle.

**F5. Un solo criterio de onboarding tras el login (Q4, QA-005, H6).**

- Un helper compartido en un módulo nuevo de `lib/` recibe el `UserResponse` y devuelve el
  destino: `has_transaction_history` → `/`; si no → `/capture?onboarding=1`.
- `login/page.tsx` y `GoogleAuthButton` lo usan. El fallback cuando falla `GET /users/me` sigue
  siendo `/capture` (sin flag). `register/page.tsx` no cambia (su auto-login ya manda con el flag
  y falla siempre por la verificación obligatoria; queda como camino de degradación).
- `/capture`: con `?onboarding=1`, el paso de moneda se muestra solo si
  `user.monthly_income == null` (Q4), igual que el de ingreso. Mientras el usuario carga, el
  wizard no muestra ningún paso (un placeholder del tamaño de la tarjeta), para evitar el parpadeo
  de H6.
- Con el ingreso ya fijado y `?onboarding=1`, se salta directo a la captura guiada con el copy
  "Ya casi…", como hoy.
- Sin migración y sin flag persistido (Q4).

**F6. `/transactions`: errores, rango invertido y filtros siempre visibles (Q7, QA-010).**

- Los filtros se renderizan siempre. El skeleton de carga inicial ocupa solo el área de la lista,
  no la página entera, así los filtros siguen visibles durante los reintentos.
- Un error de la consulta sin ítems cargados muestra, en el área de la lista, un `EmptyState` con
  "No se pudieron cargar los movimientos." y un botón "Reintentar" (`refetch`), el patrón de la
  Fase 24 §24.1. Un error al pedir **otra página** ("Cargar más") no borra lo ya cargado: toast con
  `getApiError` y el botón queda disponible.
- Rango invertido (`start > end`, venga de los inputs o de la URL): error bajo "Fecha final" ("La
  fecha final es anterior a la inicial") y la consulta no se ejecuta (`enabled: false` vía las
  opciones que `useTransactions` ya acepta). El área de la lista queda vacía, sin ítems de la
  consulta anterior (se limpian `allItems` y `total`, como hace `resetPagination`) y sin el
  mensaje de "Aún no tienes movimientos": solo se ve el error del campo.
- `max={endDate}` en "Fecha inicial" y `min={startDate}` en "Fecha final", como ayuda (Q7).
- "Aún no tienes movimientos registrados." queda solo para una respuesta exitosa sin ítems.

**F7. Decimales según la moneda (Q8, QA-007).**

- `formatCurrency` fija `minimumFractionDigits` en 0 para COP y en 2 para el resto de las monedas,
  y `maximumFractionDigits` en 2 siempre. COP sin centavos se ve igual que hoy; COP con centavos
  los muestra; USD/EUR/MXN/ARS siempre con dos.
- COP se lista explícito (no se usa el default de `Intl`, que para COP es 2 decimales por ISO 4217).
- `formatCurrency` acepta una opción para formatear en unidades enteras (mínimo y máximo 0). La
  usan solo el eje Y de `CashflowChart`, el cálculo de su ancho y las etiquetas sobre las barras
  (`LabelList`), para que "ejes y etiquetas compactas no cambien" (Q8). Los tooltips y el resto de
  la app muestran los decimales.

**F8. Tarjeta "Balance de <mes>" con el ingreso esperado como referencia (Q9, Q14, H3).**

- Tipos: `DashboardSummary.monthly_flow_balance: number` (sin `null`) y `monthly_flow_basis:
  'actual'` (marcado obsoleto en el comentario), en `types/api.ts`; `types/generated/api.ts` se
  regenera contra el backend dev (I2).
- Rótulo: siempre "Balance de <mes>", también en el mes en curso. Desaparece "Te quedan…" y la
  rama que dibujaba un guion para un balance ausente.
- Color y tendencia: salen del signo del balance, como hoy. Un balance negativo se pinta con el
  color de peligro y es un dato, no un error.
- Referencia "esperado" (Q14), **solo en el mes en curso** (el ingreso declarado no tiene
  historial, Fase 29 User Story 14):
  - con `user.monthly_income` fijado: junto a "Ingresos del mes", en la línea de la moneda
    preferida, "· esperado <monto>". Sin cálculo: no se resta ni se compara;
  - sin `monthly_income`: debajo de las cifras secundarias, el formulario inline de hoy
    reubicado, con copy nuevo ("¿Cuánto esperas ganar al mes? Es solo una referencia.") y la
    validación de F2.
- Copy que deja de prometer un cálculo:
  - paso de ingreso del onboarding: "¿Cuál es tu ingreso mensual aproximado?" se mantiene; el
    subtítulo pasa a decir que es una referencia que se muestra junto a los ingresos del mes;
  - Ajustes → "Ingreso mensual": misma idea;
  - banner "aha" del dashboard (`?onboarding=1`): la rama sin ingreso deja de decir "para ver
    cuánto te queda cada mes"; la rama con ingreso ("Has gastado X de tus Y de ingreso mensual")
    se mantiene, porque es una referencia y no un cálculo.
- El `useSetMonthlyIncome` y sus invalidaciones no cambian.

**F9. `BudgetRing` con porcentaje real y segunda vuelta (Q12, Q16, QA-012).**

- `BudgetRing` recibe el `percentage` que ya calcula el backend (`BudgetProgress.percentage`) y
  deja de calcularlo con `spent / limit`. Los dos consumidores (dashboard y detalle de cuenta) lo
  pasan.
- Texto: el porcentaje real redondeado a entero (106%), sin tope.
- Anillo:
  - primera vuelta = `min(percentage, 100)`, con los colores de hoy (primario, warning desde 80%,
    danger desde 100%);
  - segunda vuelta superpuesta = `min(percentage − 100, 100)` cuando pasa de 100, en un rojo más
    intenso. Tope visual en 200% (Q16).
- Token nuevo `--color-danger-strong` en `app/globals.css`, para los dos temas, más intenso que
  `--color-danger` en cada uno. Se documenta en `UI_SYSTEM.md`.
- El ícono de alerta de "presupuesto excedido" se mantiene.

**F10. Detalle de cuenta y de categoría: últimos 20 y "Ver todos" (Q11, QA-011).**

- `/accounts/[id]` y `/categories/[id]` piden `GET /transactions/` con `limit: 20` (el endpoint
  ya ordena por fecha descendente).
- Debajo de la lista, si hay al menos un movimiento: link "Ver todos los movimientos (N)" (con
  `N = total`) a `/transactions?account=<id>` o `/transactions?category=<id>`, que ya filtran y
  paginan.
- Las keys de las queries (`transactions.byAccount(id)`, `transactions.byCategory(id)`) no
  cambian, y las invalidaciones existentes siguen valiendo.

### Infra

**I1. `docker-compose.dev.yml` aislado de producción (Q13, QA-001).**

- `name: oikos-dev` en el nivel superior. El volumen de la base pasa a `oikos-dev_pgdata`, los
  contenedores y las imágenes son otros, y los volúmenes del frontend también (`oikos-dev_…`).
- Puertos con `!override` (Compose ≥ 2.24.4; instalado v5.5.0, verificado): backend `8001:8000`,
  frontend `3001:3000`. Postgres no publica puertos, como hoy.
- Servicio `backup` fuera del stack dev con `profiles: ["backup"]` en el override: no se levanta
  salvo que alguien active ese perfil a propósito. Producción (`docker compose up` sin override)
  no cambia.
- Variables de entorno dev que pisan las del `.env` de producción:
  - backend: `COOKIE_SECURE=false` (como hoy), `ALLOWED_ORIGINS=http://localhost:3001`,
    `FRONTEND_URL=http://localhost:3001`, `EMAIL_PROVIDER=console`;
  - frontend: `NEXT_PUBLIC_API_URL=http://localhost:8001`.
- `restart: "no"` en `postgres`, `backend` y `frontend` del stack dev (`postgres` hereda
  `unless-stopped` de `docker-compose.yml`; `backup` ya tiene `"no"`), para que un reinicio de la máquina no vuelva a levantar el
  stack dev.
- El comando para levantarlo no cambia (`docker compose -f docker-compose.yml -f
  docker-compose.dev.yml up`); cambia lo que hace. Se corrige su descripción en `CLAUDE.md` (D3).
- Las cookies no distinguen puertos: si el dueño abre dev y producción en el mismo navegador,
  **ambos en `localhost`**, las sesiones se pisan. Producción se usa por el dominio de Funnel, así
  que no aplica en la práctica; se anota en `CLAUDE.md`.

**I2. `gen:types` apunta al backend dev (H14).**

- El script `gen:types` de `frontend/package.json` genera desde `http://localhost:8001/openapi.json`
  por defecto, con una variable de entorno para cambiarlo. Nunca desde `:8000`.

### Docs

**D1. Contratos de API, en `backend/docs/API_REFERENCE.md` y `frontend/docs/API_CONTRACT.md` en
el mismo cambio.**

- `GET /dashboard/summary`: `monthly_flow_balance` siempre ingreso real − gasto real, nunca
  `null`, puede ser negativo; `monthly_flow_basis` siempre `"actual"` y obsoleto (B9). El mes
  cerrado se acota hasta el primer instante del mes siguiente, exclusivo (B6).
- `POST`/`PUT /transactions`, `POST /accounts`, `PATCH /users/me`, `POST`/`PUT /budgets`: rango de
  los montos (12 dígitos enteros, 2 decimales) y `422` con `detail` en lista (B3).
- `POST`/`PUT`/`DELETE /transactions`: `422` con `detail` string si el saldo de la cuenta se
  desbordaría (B4).
- `DELETE /transactions/{id}`: una segunda petición sobre la misma transacción, también
  concurrente, recibe `404` y no vuelve a mover el saldo. `PUT` sobre una transacción borrada:
  `404` (B1).
- `GET /transactions`: `total` excluye las borradas (B5).
- `POST /transactions` con `Idempotency-Key`: `409` también en carrera (B7).
- `POST /auth/refresh`: el `401` borra las tres cookies de sesión, siempre (B10).
- `API_CONTRACT.md` §"Errores esperados": un `422` puede traer `detail` en lista (validación de
  esquema) o string (dominio), y el frontend los muestra con `getApiError` (F1). §"Usuario
  autenticado": `monthly_income` ya no alimenta ningún cálculo.

**D2. Reglas de negocio, en `backend/docs/BUSINESS_RULES.md`.**

- §Dashboard (Q9): el balance del mes es ingreso real − gasto real en la moneda preferida, en
  cualquier mes; `monthly_income` es una referencia visual sin cálculo. Reemplaza el párrafo de
  las dos bases.
- §Dashboard (B6): el mes es el rango `[día 1 00:00, día 1 del mes siguiente 00:00)` UTC, con techo
  "ahora" en el mes en curso. Reemplaza "hasta el último día a las 23:59:59".
- §Transacciones o §Categorías (Q10): una categoría acepta transacciones de los dos tipos; un
  ingreso en una categoría de gasto se interpreta como reembolso. Limitación actual: solo la dona
  de Analítica con `?neto=true` lo netea; la tarjeta del dashboard y los KPIs de Analítica lo
  cuentan como ingreso, y los presupuestos y alertas solo suman gastos. Netearlo en toda la app es
  una fila del backlog (Q15).
- §Transacciones (B1): editar y borrar una transacción se serializan por transacción; un segundo
  borrado es `404` y no mueve el saldo.

**D3. Docs operativos y de frontend.**

- `CLAUDE.md` §Commands (Q13, I1): el comando dev levanta el proyecto `oikos-dev` en
  `:3001`/`:8001` con su propia base y sin backup; los comandos `exec` contra dev llevan `-p
  oikos-dev` (o los dos `-f`), y el de seed se documenta **para dev**, con la advertencia de que
  sin `-p` corre contra producción. Nota de cookies compartidas por `localhost` (I1).
- `CLAUDE.md` §Test (Q3, T1): receta del Postgres desechable en tmpfs y cómo correr la suite con
  `TEST_DATABASE_URL`; el marker `postgres`.
- `frontend/docs/COMPONENTS_GUIDE.md`: prop `percentage` y segunda vuelta de `BudgetRing` (F9);
  opción de unidades enteras de `formatCurrency` (F7); toggle de categorías de los modales (F3).
- `frontend/docs/UI_SYSTEM.md`: token `--color-danger-strong` (F9).
- `frontend/docs/STATE_AND_FETCHING.md`: `/transactions` no consulta con rango invertido
  (`enabled`) y el detalle de cuenta/categoría pide 20 (F6, F10). Las keys no cambian.
- `frontend/docs/ARCHITECTURE.md`: el criterio del wizard de `/capture` (F5).

**D4. Cierre de la fase.**

- `docs/TODO.md`: marcar `[x]` con fecha QA-001, QA-003, QA-004, QA-005, QA-006, QA-007, QA-008,
  QA-009, QA-010, QA-011, QA-012, QA-013, QA-015, QA-019, QA-020, QA-021 y QA-022, con puntero a
  esta spec. Anotar H11 como deuda nueva y el inventario de T10 como insumo de la Fase 32.
- `docs/CHANGELOG.md`: entrada de 3–5 líneas. `docs/ROADMAP.md`: Fase 31 completada; fila de
  backlog de Q15 si no está.
- `graphify update .`

## Testing Decisions

Un buen test acá prueba comportamiento observable desde afuera: la respuesta HTTP y el saldo que
queda en la cuenta después de una secuencia de requests, o lo que ve el usuario en la pantalla. No
prueba cómo se implementa por dentro (por ejemplo, que se use `FOR UPDATE` o que el `total` salga
de una query y no de otra).

Seams, del más alto al más bajo:

- **Backend: la API HTTP vía `TestClient`**, con los fixtures existentes (`client`,
  `auth_headers`, `make_account`, `make_category`, `other_user`). Es el seam de todos los tests de
  `test_transactions.py`, `test_dashboard.py` y `test_auth.py`. Para verificar saldos se usa
  `GET /accounts/{id}` y, en los tests concurrentes, `POST /accounts/{id}/reconcile`, cuya
  `discrepancy` es el invariante exacto del bug ("el saldo guardado es el saldo de apertura más las
  transacciones vivas").
- **Backend, funciones puras:** `core/periods.py` ya se prueba directo (`tests/test_periods.py`).
- **Un seam nuevo, solo de infraestructura de test:** un cliente con commits reales y una sesión
  por request contra Postgres, para el test concurrente (T2). No hay otra forma de probar
  concurrencia real.
- **Frontend: la app real con Playwright**, en el entorno aislado (supuesto 1): desktop y 390×844.
  **Nunca** contra el stack Docker de `:3000`/`:8000`, que es producción. Sin tests unitarios de
  frontend (no hay runner).

Cada fix de backend lleva su test de regresión, y se indica si falla antes del fix.

**T1. `conftest.py` acepta `TEST_DATABASE_URL` (Q3, B8).**

- Sin la variable, todo igual que hoy (SQLite en memoria, `StaticPool`).
- Con la variable: engine con los `kwargs` de B8, `drop_all` + `create_all` al empezar la sesión y
  `drop_all` al terminar. `db_session`/`client` siguen igual (transacción externa + savepoints).
- **Guarda de seguridad:** si el nombre de la base de `TEST_DATABASE_URL` no contiene `test`, la
  suite aborta antes de conectarse. El fixture hace `drop_all`; la lección de QA-001 es no confiar
  en que nadie apunte a producción por error.
- Marker `postgres` registrado en `[tool.pytest.ini_options]` de `pyproject.toml`, y un `skip`
  automático de los tests con ese marker cuando no hay `TEST_DATABASE_URL`.
- Receta documentada (D3): `postgres:16-alpine` suelto en `127.0.0.1:5433`, datos en `--tmpfs`,
  base `oikos_test`, igual que la pasada 3 de la QA.

**T2. QA-003 (B1, B2).**

- SQLite, en `tests/test_transactions.py`:
  - segundo `DELETE` → `404` y saldo intacto;
  - `PUT` sobre una transacción borrada → `404` y saldo intacto.
  Estos dos **pasan también antes del fix** (el filtro global ya oculta la borrada en una secuencia
  sin carrera). Son guardas, no reproducen el bug; se dice en su docstring.
- SQLite, reproducción determinista del borrado condicional: la "otra petición" se intercala entre
  la lectura de la transacción y la escritura, con un listener de SQLAlchemy sobre la sesión de
  test que, justo después del `SELECT` de la transacción, la marca borrada y revierte su impacto
  como lo haría un `DELETE` ganador. Resultado esperado: `404` y el saldo revertido **una** vez.
  Falla antes del fix (el código de hoy revierte otra vez y responde `200`). Prior art del
  intercalado: `test_race_condition_integrity_error_rolls_back_without_raising`
  (`tests/test_budget_recurrence.py`).
- Postgres (marker `postgres`), en un archivo nuevo `tests/test_concurrency_pg.py`, con el seam
  nuevo: override de `get_db` que abre una sesión real por request sobre el engine de
  `TEST_DATABASE_URL`, usuario/cuenta/categoría creados por la API con commits reales, requests
  lanzadas desde hilos con una `threading.Barrier`, y limpieza con `TRUNCATE … CASCADE` al final.
  Tres escenarios, los de la QA:
  - 8 `DELETE` paralelos → exactamente un `200` y siete `404`; `reconcile.discrepancy == 0`;
  - 8 `PUT` paralelos con montos distintos → todos `200`; `reconcile.discrepancy == 0`;
  - 4 `PUT` + 4 `DELETE` → la transacción queda borrada; `reconcile.discrepancy == 0`.
  - B2: dos `PUT` concurrentes que mueven transacciones distintas en sentidos opuestos entre dos
    cuentas (A→B y B→A), repetidos varias veces, nunca responden `500` y dejan
    `reconcile.discrepancy == 0` en las dos cuentas. Obligatorio: es la única verificación de B2.

**T3. QA-015 (B3, B4)**, en un archivo nuevo `tests/test_money_limits.py` (para no chocar con los
cambios de `test_transactions.py`):

- SQLite: 13 dígitos enteros → `422` con `detail` en lista en `POST`/`PUT /transactions`,
  `POST /accounts`, `PATCH /users/me` y `POST`/`PUT /budgets`; 12 dígitos con 2 decimales pasa.
  Falla antes del fix para los cuatro recursos (hoy la validación deja pasar el dato).
- Postgres (marker `postgres`): con la cuenta en 999.999.999.999,99, un ingreso de 1,00 →
  `422` con `detail` string y saldo intacto; mismo desborde provocado por un `PUT` y por un
  `DELETE` de gasto → `422`, saldo intacto.

**T4. QA-006 (B5)**, en `tests/test_soft_delete.py` junto a
`test_soft_deleted_transaction_not_in_list_nor_in_progress_aggregates`: crear 3, borrar 1 →
`total == 2 == len(items)`; con `limit=1`, la suma de las páginas termina. Falla antes del fix,
también en SQLite.

**T5. QA-019 (B6).**

- `tests/test_periods.py`: los tests de `TestLimitesMesUtc` pasan a esperar el primer día del mes
  siguiente (incluido diciembre → enero); el del mes en curso sigue esperando `ahora`.
- `tests/test_dashboard.py`: un ingreso a `2025-12-31T23:59:59.500` cuenta en `summary` de
  `?year=2025&month=12`; un gasto a esa hora cuenta en `budgets-progress` del mismo mes; y uno a
  `2026-01-01T00:00:00` **no** cuenta en diciembre. El primero falla antes del fix (SQLite compara
  los timestamps como texto y reproduce el corte).

**T6. QA-020 (B7)**, en `tests/test_transactions.py` (`TestIdempotencyKeyHeader`): la petición
pierde la carrera contra otra con la misma clave y **otro** payload → `409`, con el mismo
intercalado dentro del `commit` que usa `test_race_condition_integrity_error_rolls_back_without_
raising`. Y el caso de la original borrada en esa misma rama → `409`. Fallan antes del fix.

**T7. QA-022 (B8)**, marker `postgres`: con `ALTER DATABASE <test> SET timezone TO
'America/Bogota'` (revertido al final), una conexión del engine de la suite reporta `SHOW
timezone` = `UTC`, y un ingreso a las `2026-03-01T02:00:00Z` cae en el bucket `2026-03-01` de
`cashflow-series` (en `tests/test_concurrency_pg.py`, que concentra los tests `postgres`). Más una
prueba simple de la función de B8, sin marker, en un archivo nuevo `tests/test_database.py`:
`options` solo para URLs de Postgres.

**T8. Q9 (B9)**, en `tests/test_dashboard.py`: se reescriben `TestMonthlyFlowBalance` y los tests
de Fase 29 que esperan `"declared"` o `null` en el mes en curso. Casos:

- mes en curso con `monthly_income` fijado y sin ingresos registrados → balance = −gasto (negativo)
  y `monthly_flow_basis == "actual"`;
- mes en curso con ingresos y gastos → ingreso real − gasto real;
- `monthly_income` distinto no cambia el balance;
- sin transacciones y sin `monthly_income` → `"0.00"`, no `null`;
- solo cuenta la moneda preferida, como hoy.

**T9. Q5 (B10)**, en `tests/test_auth.py` junto a `test_logout_clears_all_three_cookies`: `POST
/auth/refresh` sin cookie ni body y con un refresh token inválido → `401`, mismo `detail`, y los
tres `Set-Cookie` con `Max-Age=0` en sus paths. Fallan antes del fix. `test_refresh_rotates_cookie
_without_body` sigue pasando. Además, un token recién revocado por rotación → `401` **con** las
cookies borradas (B10, opción a: sin excepción por umbral).

**T10. Suite completa contra Postgres antes de cerrar (Q3).**

- `pytest` sin variable (SQLite) y `TEST_DATABASE_URL=… pytest` (Postgres desechable).
- Criterio de cierre: todo test agregado o modificado por esta fase pasa en los dos motores, y la
  suite SQLite pasa completa. Un test **previo** que falle solo en Postgres por diferencias de
  motor no bloquea la fase: se inventaría (nombre y causa) como insumo de la Fase 32. Si la falla
  revela un bug real de producción, se anota en `docs/TODO.md` y se decide aparte.

**T11. Verificación con Playwright**, desktop y 390×844, contra el stack dev de I1 (`:3001`/`:8001`)
o el entorno aislado de la QA:

- `/login` con una `csrf_token` huérfana (inyectada a mano) → una sola carga, se puede iniciar
  sesión, la cookie desaparece (QA-021).
- Monto `0.001` en `/capture`, `12.345` y 13 dígitos en los modales → error de campo, la página
  no se cae, lo escrito se conserva (QA-004).
- Registro con contraseña → verificar → login → wizard de moneda e ingreso; login de un usuario
  con ingreso fijado y un solo movimiento → captura guiada sin pasos (QA-005). Google, revisado en
  código (el cliente OAuth sigue deshabilitado).
- `/transactions`: backend caído o respuesta forzada con error → "Reintentar" y filtros visibles;
  rango invertido → error de campo sin consulta (QA-010).
- Onboarding: ingreso vacío o negativo → mensaje (QA-013).
- Gasto de US$ 0,10 → "US$ 0,10"; COP sin centavos igual que hoy; ejes del flujo de caja sin
  decimales (QA-007).
- Dashboard: "Balance de <mes>" = ingresos − gastos a simple vista, "esperado", formulario inline
  sin ingreso fijado (QA-008).
- Presupuesto al 106% → "106%" y segunda vuelta; al 250% → anillo topado en 200% (QA-012).
- Detalle de cuenta con más de 20 movimientos → 20 + "Ver todos (N)" lleva a `/transactions`
  filtrado (QA-011).
- Editar un gasto a Ingreso → la categoría se resetea; editar un reembolso → toggle activo y
  categoría original visible (QA-009).
- `docker compose -f docker-compose.yml -f docker-compose.dev.yml config --services` no lista
  `backup`; `docker compose ls` muestra `oikos-dev` aparte de producción (QA-001).

**T12. Segunda pasada corta del `qa-engineer`** sobre los ítems resueltos (supuesto 2), antes del
cierre de docs.

## Orden de ejecución

```
1. [infra] [P] docker-compose.dev.yml + frontend/package.json (gen:types) — Decisiones I1, I2 (Q13).
   Depende de: —
2. [backend] [P] app/core/database.py + tests/conftest.py + pyproject.toml (marker) +
   tests/test_database.py (prueba simple de la función de B8, sin marker) — Decisiones B8, T1,
   T7 (parte SQLite) (Q3, QA-022).
   Depende de: —
3. [backend] app/api/transactions.py (PUT/DELETE) + app/services/ledger.py + tests/test_transactions.py
   (guardas + intercalado) — Decisiones B1, B2, T2 (SQLite) (Q2, QA-003).
   Depende de: 2
4. [backend] app/api/transactions.py (DataError, total, idempotencia) + tests/test_transactions.py
   (T6) + tests/test_soft_delete.py (T4) — Decisiones B4, B5, B7, T4, T6 (QA-015, QA-006, QA-020).
   Depende de: 3   (mismo archivo)
5. [backend] [P] app/schemas/{common,transactions,accounts,users,budgets}.py + tests/test_money_limits.py
   (SQLite) — Decisiones B3, T3 (QA-015).
   Depende de: 2
6. [backend] [P] app/core/periods.py + app/core/budget_alerts.py + app/api/accounts.py +
   app/api/dashboard.py (comparaciones) + tests/test_periods.py + tests/test_dashboard.py (T5)
   — Decisiones B6, T5 (QA-019).
   Depende de: 2
7. [backend] app/api/dashboard.py (summary) + app/schemas/dashboard.py + app/schemas/accounts.py
   (comentarios) + tests/test_dashboard.py (T8) + comentarios de frontend
   components/charts/AccountMonthlyBalanceCard.tsx y app/(dashboard)/accounts/[id]/page.tsx
   — Decisiones B9, T8 (Q9).
   Depende de: 5, 6   (mismos archivos: api/dashboard.py y test_dashboard.py con 6,
   schemas/accounts.py con 5)
8. [backend] [P] app/api/auth.py (refresh) + tests/test_auth.py — Decisiones B10, T9 (Q5, QA-021).
   Depende de: —
9. [verif] tests/test_concurrency_pg.py (T2 + B2 + caso Postgres de T7) + casos postgres de
   test_money_limits.py — Decisiones T2 (Postgres, incluido B2), T3 (Postgres), T7 (Postgres).
   Depende de: 2, 4, 5
10. [docs] backend/docs/API_REFERENCE.md + frontend/docs/API_CONTRACT.md + backend/docs/BUSINESS_RULES.md
   — Decisiones D1, D2.
   Depende de: 4, 5, 6, 7, 8
11. [frontend] [P] lib/utils.ts + app/(auth)/verify-email/page.tsx + app/(auth)/reset-password/page.tsx
   — Decisión F1 (Q6, QA-004).
   Depende de: —
12. [frontend] [P] lib/api.ts + lib/authSession.ts — Decisión F4 (Q5, QA-021).
   Depende de: —   (verificable de punta a punta con 8)
13. [frontend] [P] lib/ (helper de destino, módulo nuevo) + app/(auth)/login/page.tsx +
   components/auth/GoogleAuthButton.tsx + app/capture/page.tsx — Decisión F5 (Q4, QA-005).
   Depende de: —
14. [frontend] [P] lib/formatters.ts + components/CashflowChart.tsx — Decisión F7 (Q8, QA-007).
   Depende de: —
15. [frontend] [P] app/(dashboard)/transactions/page.tsx + components/transactions/TransactionFilters.tsx
   + components/transactions/TransactionList.tsx — Decisión F6 (Q7, QA-010).
   Depende de: 11
16. [frontend] lib/ (validador de montos + regla de categorías visibles, módulos nuevos) +
   components/forms/{TransactionCaptureForm,OnboardingIncomeStep}.tsx +
   components/modals/{TransactionModal,EditTransactionModal}.tsx + app/(dashboard)/page.tsx (form inline)
   + app/(dashboard)/settings/page.tsx + app/(dashboard)/accounts/page.tsx + app/(dashboard)/budgets/page.tsx
   — Decisiones F2, F3 (Q6, Q10, QA-004, QA-009, QA-013).
   Depende de: 11
17. [frontend] types/api.ts + types/generated/api.ts (pnpm gen:types contra :8001) +
   app/(dashboard)/page.tsx (tarjeta) + components/forms/OnboardingIncomeStep.tsx (copy) +
   app/(dashboard)/settings/page.tsx (copy) — Decisión F8 (Q9, Q14, QA-008).
   Depende de: 1, 7, 16   (mismos archivos que 16; gen:types necesita el backend de 7 en :8001)
18. [frontend] components/charts/BudgetRing.tsx + app/globals.css + app/(dashboard)/page.tsx +
   app/(dashboard)/accounts/[id]/page.tsx — Decisión F9 (Q12, Q16, QA-012).
   Depende de: 17   (app/(dashboard)/page.tsx)
19. [frontend] app/(dashboard)/accounts/[id]/page.tsx + app/(dashboard)/categories/[id]/page.tsx
   — Decisión F10 (Q11, QA-011).
   Depende de: 18   (app/(dashboard)/accounts/[id]/page.tsx)
20. [docs] CLAUDE.md + frontend/docs/{COMPONENTS_GUIDE,UI_SYSTEM,STATE_AND_FETCHING,ARCHITECTURE}.md
   — Decisión D3.
   Depende de: 1, 2, 13, 14, 15, 16, 18, 19
21. [verif] /run-tests (pytest SQLite + ruff + pnpm lint + pnpm format) y pytest contra Postgres
   desechable con inventario — Decisión T10.
   Depende de: 3, 4, 5, 6, 7, 8, 9, 11–19   (/run-tests también corre pnpm lint y pnpm format)
22. [verif] /code-review + security-reviewer sobre B10 + F4 (base de la Fase 26) — Decisiones B10, F4.
   Depende de: 8, 12, 21
23. [verif] Playwright desktop y 390×844 sobre el stack dev (:3001/:8001) — Decisión T11.
   Depende de: 1, 11–19, 22
24. [verif] Segunda pasada corta del qa-engineer + /analyze-spec 31 cierre — Decisión T12.
   Depende de: 23
25. [docs] docs/TODO.md + docs/CHANGELOG.md + docs/ROADMAP.md + graphify update . — Decisión D4.
   Depende de: 10, 20, 24
```

El paso 2 va primero en el backend porque todos los tests nuevos dependen del `conftest.py`. Los
pasos 3 y 4 son secuenciales (los dos editan `api/transactions.py` y `test_transactions.py`); el 5
y el 6 corren en paralelo con ellos porque no comparten archivos (por eso los tests de QA-015 van a
un archivo nuevo). El 6 y el 7 son secuenciales por `api/dashboard.py` y `test_dashboard.py`. En el
frontend, `app/(dashboard)/page.tsx` lo tocan 16, 17 y 18, y `accounts/[id]/page.tsx` lo tocan 18 y
19: van en cadena. 11–15 no comparten archivos entre sí; 15 y 16 esperan a 11 solo porque usan el
`getApiError` nuevo. El 7 espera también al 5 porque los dos tocan `schemas/accounts.py`, y el 21
espera al frontend porque `/run-tests` corre también `pnpm lint` y `pnpm format`.

## Resumen de archivos tocados

| Decisión | Backend | Frontend / infra |
|---|---|---|
| B1, B2 | `app/api/transactions.py`, `app/services/ledger.py` | — |
| B3 | `app/schemas/{common,transactions,accounts,users,budgets}.py` | — |
| B4, B5, B7 | `app/api/transactions.py` | — |
| B6 | `app/core/periods.py`, `app/core/budget_alerts.py`, `app/api/accounts.py`, `app/api/dashboard.py` | — |
| B8 | `app/core/database.py` | — |
| B9 | `app/api/dashboard.py`, `app/schemas/dashboard.py`, `app/schemas/accounts.py`, `app/api/accounts.py` (comentarios) | `components/charts/AccountMonthlyBalanceCard.tsx`, `app/(dashboard)/accounts/[id]/page.tsx` (comentarios) |
| B10 | `app/api/auth.py` | — |
| F1 | — | `lib/utils.ts`, `app/(auth)/verify-email/page.tsx`, `app/(auth)/reset-password/page.tsx` |
| F2, F3 | — | módulos nuevos en `lib/`, `components/forms/{TransactionCaptureForm,OnboardingIncomeStep}.tsx`, `components/modals/{TransactionModal,EditTransactionModal}.tsx`, `app/(dashboard)/{page,settings/page,accounts/page,budgets/page}.tsx` |
| F4 | — | `lib/api.ts`, `lib/authSession.ts` |
| F5 | — | módulo nuevo en `lib/`, `app/(auth)/login/page.tsx`, `components/auth/GoogleAuthButton.tsx`, `app/capture/page.tsx` |
| F6 | — | `app/(dashboard)/transactions/page.tsx`, `components/transactions/{TransactionFilters,TransactionList}.tsx` |
| F7 | — | `lib/formatters.ts`, `components/CashflowChart.tsx` |
| F8 | — | `types/api.ts`, `types/generated/api.ts`, `app/(dashboard)/page.tsx`, `components/forms/OnboardingIncomeStep.tsx`, `app/(dashboard)/settings/page.tsx` |
| F9 | — | `components/charts/BudgetRing.tsx`, `app/globals.css`, `app/(dashboard)/page.tsx`, `app/(dashboard)/accounts/[id]/page.tsx` |
| F10 | — | `app/(dashboard)/accounts/[id]/page.tsx`, `app/(dashboard)/categories/[id]/page.tsx` |
| I1, I2 | — | `docker-compose.dev.yml`, `frontend/package.json` |
| T1–T9 | `tests/conftest.py`, `pyproject.toml`, `tests/test_{transactions,soft_delete,periods,dashboard,auth}.py`, nuevos `tests/test_money_limits.py`, `tests/test_concurrency_pg.py` y `tests/test_database.py` | — |
| D1–D4 | `backend/docs/{API_REFERENCE,BUSINESS_RULES}.md` | `frontend/docs/{API_CONTRACT,COMPONENTS_GUIDE,UI_SYSTEM,STATE_AND_FETCHING,ARCHITECTURE}.md`, `CLAUDE.md`, `docs/{TODO,CHANGELOG,ROADMAP}.md` |

Sin migraciones: ningún cambio toca `models.py`. B3 valida contra `Numeric(14,2)` sin cambiar la
columna.

## Out of Scope

- **Por flujo corto, después de la fase (Q1):** QA-016 (seed descuadrado y conteo de `CLAUDE.md`),
  QA-014 (accesibilidad de `ModalShell` y botones de categoría), QA-017 (hydration en `/settings`),
  QA-018 (detalles cosméticos).
- **H11:** el corte `T23:59:59` del filtro de fechas de `/transactions` y el `.999Z` de Analítica.
  Misma familia que QA-019, pero no está en la QA ni en Q1. Candidato a flujo corto.
- **Suite de tests en Postgres por defecto:** Fase 32 (Q3). Esta fase solo agrega
  `TEST_DATABASE_URL`, el marker y el inventario de fallas.
- **Reembolsos como gasto negativo en toda la app** (tarjeta, KPIs, presupuestos, alertas,
  resumen semanal): backlog, con su propio `/grilling` (Q15).
- **`POST /accounts/{id}/reconcile` bajo concurrencia.** Es un read-modify-write sobre
  `Account.balance` que puede pisar un `POST`/`PUT`/`DELETE` simultáneo. Es la herramienta de
  corrección manual, no se dispara sola, y no está en la QA.
- **Deuda ya aceptada que la QA confirmó vigente:** filtro de cuentas destacadas inconsistente,
  mes/semana en UTC frente a hora Bogotá (incluida la fecha por defecto del modal después de las
  19:00) y `GET /budgets/?month=&year=` en meses cerrados.
- **Observaciones de la QA que no son bugs** (aviso de reinterpretación del ingreso al cambiar la
  moneda, transferencias como tipo propio, cobertura de `email.py`/`user_deletion.py`/
  `weekly_summary.py`, warnings de pytest, `pnpm.onlyBuiltDependencies`).
- Login con Google caído (externo), tests de frontend y CI.
- QA-002 ya está resuelto (usuario semilla borrado de producción el 2026-09-26). D3 corrige el
  comando que probablemente lo causó.

## Decisiones resueltas con el usuario (2026-09-27)

Q1–Q16 vienen del `/grilling` (`docs/ROADMAP.md` §Fase 31) y no se reabren. Esta spec abrió una
pregunta nueva, a partir de H2, y el dueño confirmó además los seams de testing:

- **B10** — comportamiento del `401` de refresh ante una rotación legítima de otra pestaña:
  **(a)** borrar las cookies siempre, como dice Q5, y aceptar que en esa carrera las dos pestañas
  pierdan la sesión. Descartada (b), no borrar si el token se revocó hace menos de ~60 s.
- **Seams de testing** (T1–T12) — confirmados tal como están: tests de API con `TestClient` como
  seam principal (invariante `reconcile` → `discrepancy == 0`), intercalado determinista en
  SQLite para QA-003/QA-020, `tests/test_concurrency_pg.py` solo en Postgres (marker `postgres`,
  `TEST_DATABASE_URL`), y Playwright contra el stack dev aislado (`:3001`/`:8001`).

## Further Notes

- **Riesgo principal: B10 + F4 tocan la base de la Fase 26.** Por eso los dos pasan por
  `security-reviewer` (paso 22), y el alcance de F4 es deliberadamente mínimo: una condición antes
  del `window.location.href`, sin tocar mutex, cola ni CSRF.
- **Riesgo secundario: B6 cambia la semántica de una función compartida por cuatro módulos.** El
  rename convierte un olvido en un `ImportError` en vez de una medianoche contada dos veces, y T5
  prueba los dos bordes.
- **B1 solo protege de verdad en Postgres.** En SQLite `FOR UPDATE` no existe; lo que la suite
  SQLite prueba es el borrado condicional (T2, intercalado). La protección real bajo concurrencia
  la prueba el test `postgres` de T2, y por eso T10 exige correrlo antes de cerrar.
- **Q9 cambia el número que el dueño mira todos los días.** Para quien completó el onboarding no
  cambia en el primer mes (H5). Para el resto, a principio de mes el balance puede ser negativo
  hasta cobrar; la referencia "esperado" (F8) está para dar ese contexto.
