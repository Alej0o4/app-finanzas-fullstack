# Roadmap — Oikos

> Visión de producto y qué sigue. Para el historial de fases ya completadas (Fase 0 a Fase 25),
> ver `docs/CHANGELOG.md` — cada fase tiene ahí un resumen de 3-5 líneas y un pointer a su spec
> en `docs/specs/fase_NN_spec.md`.
>
> Formato: `[ ]` pendiente · `[x]` resuelto (con fecha).

---

## Cambio de enfoque — 2026-08-22

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

## Pendientes abiertos

- [ ] **Rate limiting distribuido** (Fase 7) — diferido a propósito: `slowapi` en memoria no
      funciona con múltiples workers, pero el backend sigue en un solo worker sin réplicas.
      Diseño listo (Redis + `storage_uri`); implementar cuando el despliegue pase a
      `--workers > 1` o más de una réplica.
- [ ] **Evaluar reemplazar Lucide** por otra librería de íconos (Fase 12) — cambio de ~20 archivos
      para un beneficio principalmente estético, no bloqueante.
- [ ] **Acceder y verificar el flujo completo desde celular vía Tailscale** (heredado de Fase 4A).
- [ ] **Seed automático tras el primer startup en Docker** (heredado de Fase 4B).
- [ ] **Script `scripts/deploy.sh`** (git pull → `docker compose up --build -d`) (heredado de
      Fase 4B).
- [ ] **Generar credenciales reales de Google Cloud Console** para el despliegue (`GOOGLE_CLIENT_ID`
      / `NEXT_PUBLIC_GOOGLE_CLIENT_ID`) — el plumbing de Docker ya las propaga (Fase 20), solo
      falta crear las credenciales y setearlas en el `.env` de ese entorno.

Ver también `docs/TODO.md` para deuda técnica y bugs confirmados no ligados a una fase específica.

---

## Backlog priorizado (después del MVP)

| Prioridad | Feature | Nota |
|---|---|---|
| Alta | **Automatización de ingresos/gastos recurrentes** | Feature de retención del mes 2, no de adquisición del día 1. El scheduler ya existe desde Fase 14. |
| Alta | **Sinking funds** (gastos distribuidos en cuotas mensuales virtuales) | Diferenciador potencial para v1.1. Validado por YNAB. Feature de usuario avanzado. |
| Media | **Registro por nota de voz con IA** | v1.2. Feature de marketing / efecto "wow". Depende de la captura por nombre (Fase 16, ya lista). |
| Media | **Filtros de fecha y categoría en dashboard** | Iteración 2, cuando haya datos de uso reales que lo justifiquen. |
| Media | **App nativa iOS/Android** | Solo si se necesitan widgets de pantalla de inicio, push nativas o Face ID. La PWA de Fase 13 cubre el resto. |
| Baja | **Multi-moneda ampliado** (tasas de cambio) | El modelo ya soporta agrupación por moneda; la conversión no está y no se necesita. |
| Baja | **Sincronización offline** | Las columnas `updated_at` de Fase 8 la dejan preparada. |

---

## Fuera de scope (no hacer)

- ~~**Tracking de inversiones con vinculación de brokers**~~ — Es un producto distinto. Diluye la propuesta de valor. Como mucho, un campo manual de "patrimonio neto" en el futuro.
- ~~**Tarjetas de crédito avanzadas** (puntos, millas, intereses de mora, cuotas)~~ — Cada banco calcula distinto y las reglas cambian constantemente. Pesadilla operativa sin equipo dedicado.
- ~~**Temas visuales dinámicos**~~ — El modo claro/oscuro actual es suficiente. Ya implementado.
- ~~**Multi-idioma / i18n**~~ — Lanzamiento en español. Revisar solo si hay plan de mercados fuera de LATAM.
- ~~**CI/CD**~~ — Revisar cuando haya usuarios reales en producción.
- ~~**Apple Sign-In**~~ — Evaluado en Fase 20 y descartado: Developer Program pago (99 USD/año) y complejidad desproporcionada para un proyecto web-only.
- ~~**Rol admin en la API**~~ — Evaluado en Fase 21 y descartado: el proyecto no tiene ningún concepto de roles hoy (authz es siempre "¿sos el dueño del recurso?") y agregarlo solo para operaciones de mantenimiento es desproporcionado. Se usa un script de management en su lugar.
