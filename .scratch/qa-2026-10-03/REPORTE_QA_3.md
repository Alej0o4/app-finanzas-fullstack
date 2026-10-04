# Reporte QA — 3.ª pasada (2026-10-03/04) @ ba5a8d4

Entorno: stack dev aislado (`-p oikos-dev`, `:3001`/`:8001`, seed + usuario `qa3@test.com`), Playwright MCP con
Chromium. Producción (`:3000`/`:8000`) no se tocó. Capturas en `screenshots/` (no versionadas).

Cubre lo que la 2.ª pasada dejó pendiente (ROADMAP "Pendiente de verificar").

## Resumen

| Área pendiente | Resultado |
|---|---|
| Escritura UI: crear / editar / borrar transacción | OK en lo contable (saldos cuadran en cada paso); 2 fallos de UX (QA-034, QA-035) |
| Onboarding con cuenta nueva (registro → verificación → moneda → ingreso → 1.er gasto) | OK; validaciones de negativo y categoría funcionan; saldo USD 2000 − 50 = 1950 |
| Modales | `ModalShell` con `role="dialog"` (QA-014 ok); **confirm de borrado no** (QA-039) |
| Estados de error y carga | Dashboard, Presupuestos y Transacciones OK; **Cuentas, Categorías y Analítica no** (QA-040) |
| Push de punta a punta | OK: suscripción FCM real → `POST push/subscribe` → alerta → el service worker mostró la notificación |
| Alertas de presupuesto | OK: 80 % y 100 % una sola vez cada una, también al cruzar por *edición* |
| Resumen semanal, borde domingo/lunes | **Dos bugs reales** (QA-037, QA-038) |

## Bugs

### 🔴 QA-037 — El resumen semanal del lunes resume la semana equivocada
- **Causa:** `backend/app/core/weekly_summary.py:160-163` pasa `ahora` a `run_weekly_summary_for_user`, y el cron
  corre **lunes 07:00 Bogotá** (`main.py:162`). `_limites_semana(ahora)` devuelve la semana que *acaba de empezar*.
- **Repro** (`test@test.com`, dev): referencia = lunes 2026-10-05 12:00Z → `period_key=2026-W41`, total `0.00`;
  la semana que cerró (`2026-W40`) tenía `1.850.000`.
- **Efecto:** todos los lunes llega "Esta semana no registraste gastos — ¿todo tranquilo?" y el delta compara contra
  la semana recién cerrada. La spec (Fase 14 §tests) pide sembrar "la semana anterior" con un lunes congelado, así que
  la intención era resumir la semana pasada; los tests no lo cazan porque llaman a la función con la fecha ya elegida.
- **Arreglo sugerido:** el job pasa `ahora - timedelta(days=7)`; test del job con `freeze_time` en lunes 12:00Z.

### 🟠 QA-038 — Ventana de la semana corrida 5 h (naive Bogotá vs `timestamptz` UTC)
- **Causa:** `_limites_semana` devuelve datetimes *naive* con la hora local de Bogotá y se comparan contra
  `Transaction.date` (`DateTime(timezone=True)`, UTC) sin convertir.
- **Repro** (`qa3`, en transacción con rollback, ref. domingo W40): gasto `+10` el domingo 20:00 Bogotá (lunes 01:00Z,
  pertenece a W40) y `+7` el domingo 22:00 Bogotá de la semana anterior (lunes 03:00Z del 28-sep, pertenece a W39).
  Total obtenido **57** (base 50 + 7); correcto **60** (50 + 10). Entra el de la semana anterior y se pierde el propio.
- **Arreglo sugerido:** construir `lunes`/`domingo` con `tzinfo=SUMMARY_TIMEZONE`; mismo test con esos dos bordes.

### 🟠 QA-040 — Cuentas, Categorías y Analítica no muestran error cuando el backend falla
- Con el backend dev detenido y 15 s de espera: `/accounts` → "Balance Total **$ 0**" y lista vacía; `/categories` →
  lista vacía; `/analytics` → "Ingresos $ 0 / Gastos $ 0 / Sin movimientos en este período". Ninguna tiene
  mensaje de error ni "Reintentar" (sí lo tienen `/`, `/budgets`, `/transactions`).
- Mismo patrón que QA-004/QA-010: un fallo se presenta como dato vacío, y aquí además como un saldo total falso en 0.

### 🟡 QA-034 — En móvil el aviso "Instalar" (PWA) tapa "Guardar" del modal
- 390×844: el banner fijo (`bottom-6`, `z-50`) intercepta los clics sobre "Guardar" (rect 681–717 vs banner 698–820).
  En 1280×800 no solapa. Móvil es el canal diario. Captura: `qa3-034-mobile-banner-tapa-guardar.png`.
- Sugerido: ocultar el banner mientras hay un modal abierto, o subir el z-index del modal.

### 🟡 QA-035 — "Nueva transacción" no valida la cuenta y manda `account_id: 0`
- Valor y Categoría muestran error en línea; Cuenta no. La UI envía `{"account_id":0,...}`, el backend responde
  404 y el toast dice "La cuenta especificada no existe o no te pertenece." en vez de "Elige una cuenta."

### 🟡 QA-036 — En móvil el panel de notificaciones se sale de la pantalla
- `absolute bottom-full left-0 w-80` anclado a la campana del sidebar: ancho 320, `right=458` con viewport 390
  (68 px recortados; títulos cortados "…de Alime"). Captura: `qa3-campana-alertas-mobile.png`.

### 🟡 QA-039 — El confirm de borrado no es accesible
- El overlay del `useConfirmStore` ("¿Borrar esta transacción?") no tiene `role="dialog"/"alertdialog"` ni
  `aria-modal`, y el foco no entra al diálogo tras abrirlo (`activeElement` fuera). Escape sí cierra.
  Misma carencia que QA-014, que se arregló solo en `ModalShell`.

### 🟢 QA-041 — Detalles de copy y limpieza
- Voseo en el onboarding y Ajustes ("manejás", "Podés", "usás", "acá") frente al tuteo del resto de la app.
- `?onboarding=1` se arrastra a la URL del dashboard tras el primer gasto.
- `innerText` del feed muestra "03 De Oct De 2026, 10:55 P. M." (CSS `capitalize` mayusculiza "De" y "P. M.").
- El gasto creado con fecha solo-día (modal) se lista como el día anterior 19:00 Bogotá y el modal de edición
  muestra la fecha UTC (04) — es el desfase UTC ya aceptado (QA-032), pero se nota en el flujo más común.

## Verificado sin hallazgos
- Alertas: `budget_threshold_80` a 93 %, `budget_threshold_100` a 107 %, sin duplicados con un tercer gasto;
  editar un gasto para cruzar el 100 % también dispara.
- Saldos tras crear/editar/borrar desde la UI cuadran (3.500.000 → … y 2000 → 1950 → 1890 → 1950).
- `PUT` con descripción vacía la limpia (QA-026) y `GET` de preferencias/onboarding consistente.
- Los 401 de `/login` y los 403 de Google GSI en consola son esperables (sondeo sin sesión; origen dev no
  autorizado para el client ID).

## Notas de proceso
- Playwright MCP ya tiene Chromium; permiso de notificaciones concedido por `grantPermissions` solo al origen dev.
- Sondas de la base dev en `$CLAUDE_JOB_DIR/tmp/ws_*.py` (no versionadas); las filas de prueba del borde horario
  se descartaron con rollback. Datos de dev creados: usuario `qa3@test.com` / `qapass12345` y su presupuesto de Mercado.
