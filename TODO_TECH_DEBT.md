# Deuda Técnica Consciente — Oikos

> Este archivo documenta atajos tomados a propósito durante la fase de MVP.
> No se resuelven ahora porque el costo de hacerlo hoy supera el beneficio mientras
> el proyecto es de un solo usuario, en un solo entorno, y en fase de validar features.
> Revisar esta lista completa antes de pasar a la fase de "hardening" (seguridad/escalabilidad).

Formato: `[ ]` pendiente · `[x]` resuelto — marcar con fecha al resolver.

---

## 🔴 Resolver antes de seguir acumulando datos reales

- [x] **Montos como `float` en vez de `Decimal`/enteros en centavos.** — resuelto, ver Historial.
  Afecta: `models.py` (Account.balance, Transaction.amount, Budget.amount_limit), `schemas.py`.
  Riesgo: errores de redondeo acumulativos en saldos y agregados del dashboard.
  Por qué ahora: mientras menos datos históricos tengas, más fácil es migrar sin script de conversión.

- [ ] **Sin backup automático de `finanzas.db`.**
  Riesgo: perder el historial financiero completo por un bug propio o error humano.
  Acción mínima: script o cron que copie el archivo SQLite antes de cada sesión de cambios grandes.

---

## 🟡 Revisar antes de exponer la app fuera de tu máquina local

- [ ] **JWT guardado en `localStorage` (frontend/lib/api.ts).**
  Riesgo: robo de token vía XSS. Alternativa: cookie `httpOnly` + `secure` + `sameSite`.

- [ ] **Sin rate limiting en `/api/auth/login`.**
  Riesgo: fuerza bruta de credenciales. Alternativa: `slowapi` o similar.

- [ ] **CORS hardcodeado en `main.py` (`origenes_permitidos`).**
  Riesgo: desplegar a producción con orígenes de desarrollo si se olvida actualizar el código.
  Alternativa: mover a variable de entorno `ALLOWED_ORIGINS`.

- [ ] **Sin refresh tokens — sesión expira a los 60 min sin renovación.**
  Para uso personal no importa; sí importa si otras personas empiezan a usar la app.

---

## 🟢 Revisar cuando el código empiece a doler al modificarlo

- [ ] **Lógica de negocio embebida directamente en los routers FastAPI** (ej. `transactions.py::actualizar_transaccion`).
  No hay capa de servicio separada; los routers hacen de controller + service + repository.
  Señal de que ya toca resolverlo: cuando quieras testear esta lógica sin levantar FastAPI,
  o cuando la misma lógica se necesite desde otro lugar (CLI, job batch, etc.).

- [ ] **`schemas.py` y `models.py` como archivos únicos.**
  Manejable a 5 entidades; conviene partir por dominio si se agregan 2-3 entidades más.

- [ ] **Sin capa de excepciones de dominio** — todo `raise HTTPException` vive mezclado con las reglas de negocio.

- [ ] **Frontend: lógica de fetching duplicada por página** (`useQuery` + `queryFn` inline repetido en accounts/budgets/transactions).
  Oportunidad: extraer a hooks compartidos (`useAccounts`, `useCategories`, etc.) y centralizar `queryKey`.

- [ ] **Tipos de dominio (`AccountType`, `CategoryType`) no compartidos entre backend (Pydantic enum) y frontend (string suelto en TS).**
  Riesgo de drift silencioso si el backend agrega un valor nuevo y el frontend no lo sabe.

---

## 🔵 Solo si el proyecto crece a múltiples entornos/usuarios/consumidores

- [ ] Migraciones con Alembic (hoy `Base.metadata.create_all()`).
- [ ] Migración de SQLite a PostgreSQL (ya hay `psycopg2-binary` en requirements, preparado para esto).
- [ ] Dockerización (backend + frontend + Postgres).
- [ ] Pipeline CI/CD (lint + test + build en cada cambio).
- [ ] Testing automatizado (pytest/httpx backend, Vitest/RTL frontend).
- [ ] Versionado de API (`/api/v1/...`).
- [ ] Esquema compartido cliente-servidor (OpenAPI codegen o similar) para eliminar drift de tipos de raíz.

---

## Historial de resolución

- [x] Montos como float → migrado a Decimal/Numeric(14,2) en models.py, schemas.py y dashboard.py.
  Base de datos recreada desde cero (sin datos previos que migrar).

<!-- Ejemplo de cómo marcar al resolver:
- [x] Montos como float → migrado a Decimal — 2026-07-03
-->
