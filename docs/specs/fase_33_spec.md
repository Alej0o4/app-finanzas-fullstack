# Spec — Fase 33: corrección de la tercera pasada de QA (QA-034 a QA-042)

> Sintetiza el `/grilling` del 2026-10-04 (decisiones **Q1–Q13**, todas aceptadas por el dueño) y el
> reporte `.scratch/qa-2026-10-03/REPORTE_QA_3.md`. Esas decisiones no se reabren aquí: se citan por su
> número y se bajan a decisiones implementables **B** (backend), **F** (frontend), **X** (operativa),
> **T** (testing) y **D** (docs).
>
> Antes de escribirla se leyó el código afectado (ver "Hallazgos de exploración"); varios de esos
> hallazgos corrigen premisas del grilling (el conteo de voseo, `?onboarding=1`, el selector de
> cuenta de la captura rápida) y quedan registrados abajo.
>
> **No implementa nada.** Solo se agrega este archivo y los cambios de ROADMAP ya hechos.

**Estado:** spec escrita el 2026-10-04. El único marcador (F12) y la confirmación de seams se
resolvieron con el dueño ese mismo día, y el `/analyze-spec` pre-implementación (1 CRÍTICO, 2 ALTO,
3 MEDIO, 3 BAJO) se aplicó en esta versión. Sin marcadores vivos: **lista para implementar**
(`docs/WORKFLOW.md` paso 4), pendiente de una segunda corrida de `/analyze-spec` si el dueño la pide.
**QA-042** (el email del Sidebar mayusculizado) se agregó al alcance en esa corrida.

---

## Problem Statement

La tercera pasada de QA (stack dev aislado + Playwright, cubriendo lo que la segunda dejó sin
verificar) encontró ocho problemas que el dueño sí nota en el uso diario:

- **El resumen semanal miente cada lunes.** Llega "Esta semana no registraste gastos — ¿todo
  tranquilo?" aunque la semana que acaba de cerrar tuviera gasto, porque el job de las 07:00 resume
  la semana que *acaba de empezar* (QA-037). Además, cuando sí hay gasto, el límite de la semana está
  corrido 5 h y un gasto del domingo por la noche cae en la semana equivocada (QA-038).
- **Cuando el backend falla, tres pantallas mienten en silencio.** Cuentas muestra "Balance Total
  $ 0", Categorías una lista vacía y Analítica "Sin movimientos" y KPIs en 0 (QA-040): el dueño no
  puede distinguir "no tengo nada" de "no cargó".
- **En el celular, el canal de uso diario:** el aviso "Instalar" tapa el botón "Guardar" del modal
  (QA-034) y el panel de notificaciones se sale de la pantalla (QA-036).
- **Fricción y accesibilidad en la captura:** el modal de transacción no valida la cuenta y manda
  `account_id: 0` (QA-035); el confirm de borrado no es un diálogo accesible (QA-039).
- **Copy y detalles visuales inconsistentes** (QA-041, QA-042): voseo en medio de una app que
  tutea, fechas con "De"/"P. M." mayusculizados y el email del Sidebar mostrado como `Qa3@Test.com`.

## Solution

- El lunes a las 07:00 llega el resumen de la semana que realmente cerró, contada en hora de Bogotá,
  con un texto que dice "la semana pasada".
- Cualquier fallo de carga en Cuentas, Categorías, Analítica y las pantallas de detalle muestra el
  mismo estado de error con "Reintentar" que ya existe en Presupuestos y Transacciones, nunca un
  `$ 0` o una lista vacía falsos.
- En móvil, el banner de instalación se aparta mientras hay un modal o confirm abierto, y el panel
  de notificaciones es una hoja que cabe en pantalla.
- El modal de transacción pide la cuenta con un error claro (y la preselecciona si solo hay una); el
  confirm de borrado cumple el mismo estándar de accesibilidad que los demás modales.
- Toda la copy tutea, las fechas se ven como "03 de oct de 2026, 10:55 p. m." y el email aparece
  tal como se escribió.

## User Stories

**Resumen semanal (QA-037, QA-038)**

1. Como dueño, quiero recibir el lunes a las 07:00 el resumen de la semana que terminó el domingo,
   para saber en qué gasté sin tener que abrir la app.
2. Como dueño, quiero que el total y la categoría principal del resumen coincidan con lo que gasté
   de lunes a domingo (hora de Bogotá), para poder confiar en el número.
3. Como dueño, quiero que un gasto del domingo a las 20:00 cuente en esa semana y no en la
   siguiente, para que el borde domingo/lunes no distorsione el resumen.
4. Como dueño, quiero que un gasto del domingo anterior a las 22:00 no se sume a la semana
   siguiente, para que no se infle el total.
5. Como dueño, quiero que el texto diga "La semana pasada…", para no leer "esta semana" sobre algo
   que ya pasó.
6. Como dueño, quiero que el delta compare la semana que cerró contra la anterior a ella, para que
   el porcentaje tenga sentido.
7. Como dueño, quiero que cuando de verdad no gasté nada diga "La semana pasada no registraste
   gastos — ¿todo tranquilo?", para que ese mensaje sea cierto cuando aparece.
8. Como dueño, quiero que no me lleguen dos resúmenes de la misma semana ni quede bloqueado el
   resumen correcto por un aviso falso anterior, para no perder el primer resumen bueno.
9. Como dueño, quiero que mi bandeja no conserve avisos "no registraste gastos" que eran falsos,
   para que el historial no me desinforme.

**Estados de error (QA-040)**

10. Como dueño, quiero ver "No se pudieron cargar tus cuentas" con "Reintentar" cuando el backend
    falla, para saber que es un fallo y no que no tengo cuentas.
11. Como dueño, quiero que "Balance Total" no muestre `$ 0` mientras su carga falla, para no creer
    que mi saldo es cero.
12. Como dueño, quiero lo mismo en Categorías, para no pensar que perdí mis categorías.
13. Como dueño, quiero que Analítica muestre el error en los KPIs y los gráficos cuando falla, para
    no leer "Ingresos $ 0 / Gastos $ 0" como si fuera real.
14. Como dueño, quiero que el detalle de una cuenta, el de una categoría y Ajustes también muestren
    el error cuando falla su carga, para que el comportamiento sea el mismo en toda la app.
15. Como dueño, quiero que "Reintentar" vuelva a pedir solo lo que falló, para recuperar la pantalla
    sin recargar la página.
16. Como dueño, quiero que el estado de error se vea igual en todas las pantallas, para
    reconocerlo de inmediato.

**Móvil (QA-034, QA-036)**

17. Como dueño que usa Oikos en el celular, quiero poder tocar "Guardar" en el modal aunque el
    aviso de instalación esté activo, para registrar mi gasto sin descartar el aviso primero.
18. Como dueño, quiero que el aviso de instalación vuelva a aparecer al cerrar el modal, para no
    perder la oferta de instalar.
19. Como dueño, quiero que el aviso se aparte también con el confirm de borrado abierto, para que
    nada se superponga a una decisión destructiva.
20. Como dueño, quiero que el panel de notificaciones quepa completo en pantalla en un celular de
    390 px, para leer los títulos sin que se corten.
21. Como dueño, quiero que en pantallas anchas el panel siga siendo el popover de siempre, para no
    cambiar lo que ya funciona en desktop.
22. Como dueño, quiero poder cerrar el panel de notificaciones con un clic fuera de él o con
    Escape, tanto en móvil como en desktop, para no aprender dos interacciones.

**Captura y accesibilidad (QA-035, QA-039)**

23. Como dueño, quiero ver "Elige una cuenta." cuando intento guardar sin cuenta, para entender qué
    falta, igual que con el valor y la categoría.
24. Como dueño con una sola cuenta, quiero que el modal la traiga elegida, para registrar un gasto
    con un toque menos.
25. Como dueño con varias cuentas, quiero que el modal siga pidiéndome elegir, para no registrar en
    la cuenta equivocada por una preselección.
26. Como dueño, quiero que la app nunca envíe un movimiento con cuenta inválida, para no ver un
    error 404 incomprensible.
27. Como usuario de teclado o lector de pantalla, quiero que el confirm de borrado se anuncie como un
    diálogo y que el foco entre en él, para saber que debo decidir antes de seguir.
28. Como usuario de teclado, quiero que el foco empiece en "Cancelar", la opción segura, para no
    borrar por accidente al pulsar Enter.
29. Como usuario de teclado, quiero que Tab no se salga del confirm, para no actuar sobre la página
    de atrás sin verla.
30. Como usuario de teclado, quiero que al cerrar el confirm el foco vuelva al botón que lo abrió,
    para no perder mi lugar.
31. Como usuario de teclado, quiero poder cerrar el confirm con Escape, para cancelar rápido (ya
    funciona; no debe romperse).

**Copy y detalles (QA-041, QA-042)**

32. Como dueño, quiero que toda la app me hable de "tú", para que el tono sea el mismo en onboarding,
    Ajustes y Analítica.
33. Como dueño, quiero leer las fechas como "03 de oct de 2026, 10:55 p. m.", para que se lean como
    español natural.
34. Como dueño, quiero ver mi email en el Sidebar exactamente como lo escribí (`test@test.com`), no
    con cada tramo en mayúscula, para reconocerlo y poder copiarlo bien.

## Implementation Decisions

### Backend — resumen semanal

- **B1 (Q1, QA-037).** `run_weekly_summary_job` invoca el resumen de cada usuario con
  `ahora − 7 días` como fecha de referencia. `build_weekly_summary` **no cambia** su contrato ("la
  semana ISO que contiene la fecha dada"). El `period_key` resultante es el de la semana que cerró.
  Se corrigen los docstrings y comentarios del módulo para decir qué semana resume el job.
- **B2 (Q2/Q10, QA-038).** `_limites_semana` devuelve límites **con zona horaria**
  (`America/Bogota`, la constante `SUMMARY_TIMEZONE` que ya existe). Se comparan contra
  `Transaction.date` (`timestamptz`) sin conversión implícita. Sin otros cambios de zona en la fase.
  La referencia **debe ser aware**: una fecha naive se rechaza con `ValueError` (el job siempre pasa
  `datetime.now(UTC)`; solo los tests usaban naive), para que nunca se interprete en silencio como
  hora del servidor. Un test fija ese rechazo (T4).
- **B3 (Q12).** El texto del resumen pasa a la semana pasada:
  - sin gasto: `La semana pasada no registraste gastos — ¿todo tranquilo?`
  - con gasto: `La semana pasada gastaste {total} {moneda} — el mayor gasto fue en {categoría}`
    seguido, si hay base de comparación, de ` ({delta:+.0f}% vs. la anterior).`
  - El título sigue siendo `Tu resumen semanal`.
- **B4.** El cron (lunes 07:00 `America/Bogota`), la idempotencia por `(user_id, type, period_key)`,
  el manejo del `IntegrityError` y el envío push no cambian.

### Operativa — datos existentes (Q11)

- **X1.** Una limpieza SQL puntual, **sin migración de Alembic**, borra todos los avisos
  `weekly_summary` existentes: todos describen la semana equivocada (casi siempre "no registraste
  gastos") y la clave de la semana 40 chocaría con el primer resumen correcto (el índice único se
  traga el `IntegrityError` en silencio y ese resumen no llegaría nunca).
  - El SQL exacto (tabla `notifications`; mismo script para dev y prod):

    ```sql
    -- 1) Qué se va a borrar (revisar antes):
    SELECT id, user_id, period_key, created_at, left(body, 60) AS body
      FROM notifications WHERE type = 'weekly_summary' ORDER BY created_at;
    -- 2) Limpieza:
    DELETE FROM notifications WHERE type = 'weekly_summary';
    ```

  - **Dev:** lo corre el agente (`docker compose -p oikos-dev exec postgres psql …`). **Prod:** lo
    corre el dueño a mano, con el `SELECT` previo a la vista.
  - **Cuándo:** después de desplegar el código corregido y antes del siguiente lunes 07:00 Bogotá.
    Si el cron del lunes ya corrió con el código viejo, se vuelve a ejecutar el `DELETE` tras
    desplegar (borra también ese aviso).
  - **Cómo se prueba (T5):** el stack dev no tiene avisos `weekly_summary`, así que la limpieza se
    prueba sembrando uno con la clave que choca.

### Frontend — estados de error (Q4, QA-040)

- **F1.** Un componente compartido de error de carga (`QueryErrorState`, en los componentes de UI)
  construido sobre `EmptyState` con el ícono de alerta, un mensaje específico por pantalla y el botón
  "Reintentar" que dispara el `refetch` de lo que falló. **Reemplaza** los cinco bloques copiados
  hoy (Presupuestos, dashboard, desglose por categoría, lista de transacciones, últimas
  transacciones). La alerta compacta del dashboard (`size 20`) se deja como está si no encaja sin una
  variante nueva: no se agrega una variante solo para ella.
- **F2.** **Cuentas:** si falla la lista de cuentas, la página muestra el estado de error en lugar
  de la lista; si falla el resumen de saldos, el estado de error ocupa el lugar de las tarjetas
  "Balance Total". El `$ 0` solo se muestra cuando el resumen cargó y vino vacío.
- **F3.** **Categorías:** si falla la carga, estado de error en lugar de la lista.
- **F4.** **Analítica:** los KPIs y los dos gráficos muestran error cuando su dato falla, y cuando
  falla la lista de cuentas (de la que dependen las demás queries). **Hipótesis de causa raíz, a
  confirmar antes de arreglar:** las queries de Analítica están deshabilitadas mientras las cuentas
  están pendientes o fallidas, así que `isError` nunca se activa y los gráficos caen en su estado
  vacío (los componentes de gráfico ya manejan `isError`). Los KPIs no manejan error en absoluto.
- **F5.** Se audita con el backend caído y se corrige con el mismo componente lo que falle en el
  detalle de cuenta, el detalle de categoría y Ajustes.

### Frontend — móvil y accesibilidad (Q5, Q6, Q7)

- **F6 (Q5, QA-034).** Un contador de diálogos abiertos en el store de UI (estado solo de UI: encaja
  con la regla de los tres estados). `ModalShell` y el confirm lo incrementan mientras están
  abiertos; el banner de instalación no se renderiza mientras el contador sea mayor que cero. La
  lógica de elegibilidad del banner (visitas, descartado, standalone) no cambia.
- **F7 (Q5, QA-036).** En pantallas menores a `sm`, el panel de notificaciones es una hoja fija
  (`fixed`, con márgenes laterales) que cabe entera en el viewport, incluidos los 390 px; desde `sm`
  sigue siendo el popover absoluto actual. Mismo contenido; se cierra con un clic fuera de él o con
  Escape en ambos formatos.
- **F8 (Q6, QA-039).** El confirm de borrado cumple el estándar de QA-014: `role="alertdialog"`,
  `aria-modal`, mensaje asociado como descripción, foco inicial en **"Cancelar"**, trampa de foco,
  restauración del foco al cerrar y Escape. La lógica de foco de `ModalShell` se **extrae a un hook
  compartido** que usan ambos (en vez de duplicarla o de forzar al confirm a usar el encabezado de
  `ModalShell`, que no tiene). El hook acepta cuál es el elemento de foco inicial y el seguimiento
  del elemento que abrió el diálogo debe reconocer también `alertdialog`.
  - A verificar al implementar: si algún flujo abre el confirm *encima* de un `ModalShell` abierto.
    Si existe, el confirm tiene prioridad en Tab/Escape y al cerrarlo el foco vuelve al modal.
- **F9 (Q7, QA-035).** El modal de nueva transacción valida la cuenta en línea (`Elige una
  cuenta.`) con el foco al campo, igual que Valor y Categoría, y **nunca** envía una cuenta no
  elegida. Si el usuario tiene exactamente una cuenta, el modal la trae preseleccionada; con varias,
  sigue en "Selecciona…". El modal de edición ya parte de la cuenta del movimiento.
  - **Alcance:** solo `TransactionModal`. El gasto rápido y `/capture` usan `TransactionCaptureForm`,
    que ya parte de la primera cuenta cuando no se elige ninguna y solo muestra selector con más de
    una; ese comportamiento (3 toques) **no cambia**, también con varias cuentas. Único ajuste ahí:
    si el usuario no tiene cuentas, el formulario no debe enviar `account_id: 0` (hoy
    `Number('')`), sino bloquear el guardado.

### Frontend — copy y detalles (Q8, QA-041, QA-042)

- **F10.** Tuteo en todo texto **visible al usuario**. Hoy son **8 textos en 3 archivos**: Ajustes
  (`Ingresá un nombre…`, `La moneda que usás…`, `Todavía no tenés API keys`, `Si la perdés…`,
  `Elegí un nombre…`), el paso de moneda del onboarding (`manejás`, `Podés`) y el gráfico de flujo
  (`aparecerán acá`). Los comentarios de código con "acá" **no se tocan**. Criterio: verbos en
  segunda persona singular de "tú" (`manejas`, `puedes`, `usas`, `tienes`, `Elige`, `pierdes`) y
  `aquí` en vez de `acá`. El cierre usa un grep más amplio que el de este análisis (también formas
  en `-ás/-és/-ís` e imperativos en `-á/-é`) sobre `app`, `components` y `lib`, descontando
  comentarios, y debe dar cero. El backend no tiene texto de usuario en voseo.
- **F11.** Las fechas de transacciones se muestran con solo la primera letra en mayúscula en lugar del
  `capitalize` de CSS (que mayusculiza "De" y "P. M."). Un helper de formato compartido, aplicado a
  los **cuatro** feeds que hoy usan `capitalize` sobre la fecha de un movimiento (detalle de cuenta,
  detalle de categoría, lista de transacciones y últimas transacciones). La etiqueta de mes de
  Presupuestos (`getMonthName`) se revisa: si ya viene bien formada, se deja con `capitalize`.
- **F13 (QA-042).** El email del usuario en el Sidebar deja de pasar por `capitalize` (hoy `qa3@test.com`
  se ve `Qa3@Test.com`). No es una fecha: se quita la clase y no se reemplaza por nada.
- **F12 (resuelta con el dueño, 2026-10-04).** `?onboarding=1` en la URL del dashboard **se deja como
  está** y sale del alcance de QA-041. No es una fuga: es el mecanismo de la Fase 15 (Decisión
  15.5.1) que hace aparecer el aviso "Has gastado US$ 50 de tus US$ 2.000 de ingreso mensual" sin
  estado extra y que desaparece solo al navegar. La premisa de Q8 ("se arrastra a la URL") era un
  error de clasificación del reporte de QA.

### Docs

- **D1.** Al implementar: entradas `QA-034` a `QA-042` en `docs/TODO.md` (resueltas con fecha), línea
  de la Fase 33 en `docs/CHANGELOG.md`, y actualizar `docs/ROADMAP.md` (la fase pasa a completada).
- **D2.** Documentar el componente de error y el hook de diálogos en
  `frontend/docs/COMPONENTS_GUIDE.md`, y la regla "el resumen del lunes es de la semana anterior" en
  `backend/docs/BUSINESS_RULES.md`. **No cambia ningún contrato de API**: no hay que tocar
  `API_REFERENCE.md` ni `API_CONTRACT.md` salvo que describan el texto del aviso.

## Testing Decisions

**Qué es un buen test aquí.** Prueba comportamiento observable desde el punto más alto posible: lo
que el dueño ve o recibe, no cómo está armado el código. En backend, el resultado de ejecutar el job
(avisos persistidos con su `period_key`, total y texto); en frontend, lo que muestra el navegador.

**Seams propuestos (a confirmar con el dueño — skill `to-spec`):**

1. **Backend: `run_weekly_summary_job`**, el entry point del cron. Es el seam más alto: cubre
   usuarios elegibles → semana → total → aviso persistido. Hoy los tests entran por debajo
   (`build_weekly_summary`, `run_weekly_summary_for_user`) con la fecha ya elegida, por eso QA-037
   pasó. Se usa el seam existente; no se agrega ninguno.
2. **Frontend: el navegador (Playwright) contra el stack dev aislado.** El repo no tiene tests de
   frontend y Vitest/RTL está explícitamente fuera de scope (ROADMAP), así que la verificación es
   una pasada guiada de Playwright, escrita como lista de pasos en esta spec (paso `[verif]`), no un
   framework nuevo.

**Backend (T1–T4):**

- **T1.** Test del job de punta a punta: `freeze_time` en lunes 12:00Z, usuario con gasto en la
  semana que cerró y ninguno en la nueva → un aviso con el `period_key` de la semana cerrada y el
  total correcto (no el mensaje de "sin gastos"). Falla con el código actual.
- **T2.** Dos casos de borde de domingo: un gasto del domingo 20:00 Bogotá (lunes 01:00Z) **dentro**
  de su semana, y un gasto del domingo 22:00 Bogotá de la semana anterior (03:00Z) **fuera** de la
  actual. Reproducen el 57 vs 60 de QA-038.
- **T3.** Ejecutar el job dos veces en la misma semana deja un solo aviso (el `IntegrityError` se
  traga).
- **T4.** Se actualizan los tests existentes: la referencia `REFERENCE` deja de ser un `datetime`
  naive (pasa a aware para no depender de la hora del sistema), los asserts de texto cambian a la
  copy nueva y un test nuevo comprueba que una fecha naive lanza `ValueError` (B2).
- **T5 (X1).** Prueba de la limpieza contra dev: sembrar un `weekly_summary` con la clave de la
  semana que cierra, correr el job (debe omitirse sin error), correr el `DELETE` de X1, correr el
  job otra vez (ahora debe crear el aviso) y comprobar que no queda ningún `weekly_summary` falso.
  Es un script de verificación, no un test de la suite.
- **Prior art (T1–T3).** Para el job: `test_weekly_summary.py` (`freeze_time`). Para un entry point
  que abre su propia sesión: `test_seed.py` (monkeypatch del `SessionLocal` del módulo con la
  `real_session_factory` / `db_session` de `conftest`). El job hace `close()` y `commit()`; el test
  debe neutralizar el cierre de la sesión de test o usar una factory propia, a resolver al implementar.

**Frontend (verificación Playwright, paso `[verif]`):** cada hallazgo se reproduce **antes** de
corregirlo y se vuelve a comprobar después, en 390×844 y 1280×800:

- **QA-040:** con el backend dev detenido, esperar a que termine el reintento: `/accounts`,
  `/categories`, `/analytics`, `accounts/[id]`, `categories/[id]` y `/settings` muestran error con
  "Reintentar" y ninguna muestra `$ 0` ni lista vacía como dato. Reanudar el backend y pulsar
  "Reintentar" carga los datos.
- **QA-034:** con el banner activo (instalación elegible), el botón "Guardar" del modal responde al
  clic; el banner no está en el DOM con un modal o confirm abierto y vuelve al cerrarlo.
- **QA-036:** a 390 px el panel completo queda dentro del viewport (`right ≤ 390`); a 1280 px sigue
  siendo popover; en ambos, un clic fuera y Escape lo cierran.
- **F6 (borde):** con el drawer del Sidebar abierto en móvil y el banner de instalación activo, se
  comprueba si se superponen; si es así, se decide si el drawer también registra el contador.
- **QA-039:** el confirm tiene `role="alertdialog"` y `aria-modal`, el foco inicial está en
  "Cancelar", Tab no sale, Escape cierra y el foco vuelve al botón de borrar.
- **QA-035:** guardar sin cuenta muestra "Elige una cuenta." y **no** hay `POST`; con una sola cuenta
  viene preseleccionada; con varias no.
- **QA-041:** el `grep` ampliado de F10 da cero textos de usuario en voseo en `frontend/app`,
  `frontend/components` y `frontend/lib`, y las fechas del feed muestran "de" y "p. m." en minúscula.
- **QA-042:** el email del Sidebar se ve en minúsculas, tal como está guardado.
- **Regresión:** `ModalShell` sigue con su trampa de foco (QA-014), Escape y restauración de foco.
- `/run-tests` (pytest, ruff, eslint, prettier) en verde.

## Out of Scope

- **Unificación de zonas horarias** (Fase 34): `timezone` por usuario, hora local del dispositivo,
  QA-032 (el gasto con fecha solo-día que se lista como el día anterior a las 19:00 y el modal de
  edición con la fecha UTC), la fecha por defecto del modal y la discrepancia entre el resumen
  (Bogotá) y Analítica / `/transactions` (semanas UTC). En esta fase solo se corrige la aritmética
  del resumen con la zona fija de Bogotá.
- **El hueco de 1 s al final del domingo** (`23:59:59` en lugar de un intervalo semiabierto): ya está
  en `docs/TODO.md` como candidato aparte y no se toca.
- **Tests de frontend** (Vitest/RTL) y CI: fuera de scope del proyecto.
- **Recuperar los resúmenes ya enviados:** se borran, no se reconstruyen.
- **Cambios de contrato de API o de esquema:** no hay migraciones ni endpoints nuevos.
- **QA-029, QA-030, QA-033** y el resto de decisiones de producto abiertas.

## Further Notes

- **Premisas del grilling corregidas durante la spec.** (1) `?onboarding=1` en el dashboard es un
  mecanismo deliberado de la Fase 15, no una fuga (F12, resuelta). (2) El voseo visible son 8
  textos en 3 archivos, no "24 en 9" (la mayoría eran comentarios de código; F10). (3) `account_id: 0`
  es del `TransactionModal`; la captura rápida ya parte de la primera cuenta (F9).
- **Plazo operativo.** El próximo cron es el **lunes 2026-10-05 07:00 Bogotá**. Si el código
  corregido no está desplegado para entonces, ese lunes llegará otra vez el resumen falso y habrá
  que repetir la limpieza X1 al desplegar. Mientras tanto, desactivar el resumen semanal en Ajustes
  (la preferencia `weekly_summary_enabled` existe) evita ese aviso falso.
- **Diagnóstico pendiente de Analítica (F4).** Si la hipótesis de las queries deshabilitadas por
  `useAccounts` resulta falsa, el paso de implementación documenta la causa real antes de arreglar.
- **Rama y PR.** Todo va en una sola PR sobre `fix/qa-tercera-pasada`, con el backend primero y el
  frontend en paralelo (Q9).

## Hallazgos de exploración

Verificados contra el código el 2026-10-04:

1. El job abre su propia sesión, consulta usuarios con `weekly_summary_enabled` y llama al resumen con
   `datetime.now(UTC)`; el cron es lunes 07:00 `America/Bogota`. Confirmado el origen de QA-037.
2. `_limites_semana` convierte la referencia a Bogotá pero construye `lunes`/`domingo` con
   `datetime(...)` **sin tzinfo**; la columna `Transaction.date` es `DateTime(timezone=True)`.
   Confirmado el origen de QA-038 (reproducido: 57 vs 60).
3. El test del módulo usa `REFERENCE = datetime(2026, 9, 7, 7, 0, 0)` **naive** con `freeze_time`;
   pasar a aware es necesario para que B2 no dependa de la zona del sistema.
4. El índice único `(user_id, type, period_key)` hace que el aviso falso del 28-sep (`2026-W40`)
   bloquee el correcto del 5-oct. Solo W40 choca: todas las claves futuras son ≥ W40.
5. `ModalShell` ya implementa foco inicial, trampa, restauración y Escape, pero rastrea el elemento
   previo con `closest('[role="dialog"]')`: un `alertdialog` necesita que ese selector lo incluya.
6. `ConfirmDialog` es un `div` sin ARIA ni manejo de foco, pero ya usa el hook de Escape.
7. El banner de instalación es `fixed z-50`, igual que los modales, y no conoce su estado; el store
   de UI hoy solo guarda el estado del sidebar.
8. El patrón de error "`EmptyState` + `AlertCircle` + Reintentar" está copiado en cinco lugares
   (Presupuestos, dashboard, desglose por categoría, lista de transacciones y últimas transacciones).
9. En Cuentas, el `else` final de las tarjetas de saldo renderiza `$ 0` tanto cuando el resumen vino
   vacío como cuando falló. Categorías no lee `isError`. Los gráficos de Analítica sí reciben
   `isError`, pero los KPIs no.
10. `QuickTransactionModal` delega en `TransactionCaptureForm` (el mismo que usa `/capture`), que
    parte de la primera cuenta si no se elige ninguna y solo muestra selector con más de una. El
    `account_id: 0` de QA-035 es exclusivo de `TransactionModal` (F9). Único hueco: sin cuentas,
    `Number('')` da 0.
11. Voseo visible: 8 textos en `settings/page.tsx` (5), `OnboardingCurrencyStep.tsx` (2) y
    `CashflowChart.tsx` (1). Los demás "acá" del repo son comentarios.
12. `capitalize` sobre fechas: 4 feeds (detalle de cuenta, detalle de categoría, lista de
    transacciones, últimas transacciones). Además el mes de Presupuestos (`getMonthName`) y **el
    email del Sidebar**, que se ve `Qa3@Test.com` (QA-042).
13. `ModalShell` lo usan los ocho modales/pantallas con diálogo y `ConfirmDialog` se monta una sola
    vez, en el layout del dashboard: el contador de F6 cubre todos los diálogos, salvo el drawer del
    Sidebar en móvil (`fixed inset-0`).

## Decisiones resueltas con el usuario (2026-10-04)

| # | Decisión | Resolución |
|---|---|---|
| Q1 | Cómo corregir QA-037 | El job pasa `ahora − 7 días`; `build_weekly_summary` no cambia |
| Q2/Q3 | Zonas horarias y QA-032 | Fase propia (Fase 34); en la 33, Bogotá fija |
| Q4 | QA-040 | Componente compartido, reemplaza los usos inline, auditar detalles y Ajustes |
| Q5 | Móvil | Banner se oculta con un modal abierto; panel como hoja fija en móvil |
| Q6 | QA-039 | Estándar de QA-014, foco inicial en "Cancelar", lógica compartida con `ModalShell` |
| Q7 | QA-035 | Validación + preselección con una sola cuenta |
| Q8 | QA-041 | Tuteo (8 textos en 3 archivos) y mayúsculas solo en la primera letra. `?onboarding=1` **se deja como está** (F12, resuelta el 2026-10-04) |
| — | Seams de test | Confirmados: `run_weekly_summary_job` en backend, Playwright en frontend |
| — | `/analyze-spec` | Aplicado: corrige F10 y F11, agrega el SQL de X1 y la decisión de B2, acota F9 y registra QA-042 (F13) |
| Q9 | Estructura | Una PR, backend primero, frontend `[P]`, cuarta pasada de verificación |
| Q10 | QA-038 en la 33 | Sí, con la zona fija de Bogotá |
| Q11 | Avisos existentes | SQL puntual, sin migración |
| Q12 | Texto | "La semana pasada…" |
| Q13 | Tests | Job de punta a punta, dos bordes de domingo, segunda corrida sin duplicar |

## Orden de ejecución

1. **[verif]** Reproducir cada hallazgo en el stack dev aislado (línea base con capturas) y confirmar
   la causa raíz de Analítica (F4).
   Depende de: —
2. **[backend]** Tests rojos T1–T3 en `backend/tests/test_weekly_summary.py` y ajuste de `REFERENCE`
   a aware (T4) — Decisiones T1–T4.
   Depende de: —
3. **[backend]** `backend/app/core/weekly_summary.py`: B1 (referencia del job), B2 (límites aware) y
   B3 (texto), hasta que T1–T4 pasen — Decisiones B1–B4.
   Depende de: 2
4. **[infra]** Probar la limpieza X1 contra dev (`-p oikos-dev`) con el aviso sembrado y dejar el SQL
   en el cierre del PR para que el dueño lo corra en prod — Decisión X1, prueba T5.
   Depende de: 3
5. **[frontend]** [P] Componente `QueryErrorState` y reemplazo de los cinco bloques inline —
   Decisión F1.
   Depende de: —
6. **[frontend]** Cuentas, Categorías, Analítica y pantallas de detalle/Ajustes con estado de error
   — Decisiones F2–F5.
   Depende de: 5
7. **[frontend]** [P] Hook de foco compartido, `ConfirmDialog` accesible y contador de diálogos en el
   store de UI — Decisiones F6, F8.
   Depende de: —
8. **[frontend]** `InstallPrompt` lee el contador — Decisión F6.
   Depende de: 7
9. **[frontend]** [P] Hoja fija del panel de notificaciones en `NotificationBell` — Decisión F7.
   Depende de: —
10. **[frontend]** [P] Validación y preselección de cuenta en `TransactionModal` — Decisión F9.
    Depende de: —
11. **[frontend]** Tuteo en los 3 archivos con voseo visible, helper de fecha con primera letra en
    mayúscula en los 4 feeds y quitar `capitalize` del email del Sidebar — Decisiones F10, F11, F13
    (F12 no requiere trabajo). No es `[P]`: comparte archivos con los pasos 5 y 6 (Ajustes, gráfico
    de flujo, detalle de cuenta y de categoría, lista de transacciones).
    Depende de: 5, 6
12. **[docs]** TODO, CHANGELOG, ROADMAP, `COMPONENTS_GUIDE.md` y `BUSINESS_RULES.md` — Decisiones
    D1–D2.
    Depende de: 3, 6, 8, 9, 10, 11
13. **[verif]** `/run-tests`, `/code-review`, `/analyze-spec` de cierre y la cuarta pasada de
    Playwright (lista de "Testing Decisions"), en 390×844 y 1280×800, contra el stack dev aislado.
    Depende de: 4, 6, 8, 9, 10, 11, 12
