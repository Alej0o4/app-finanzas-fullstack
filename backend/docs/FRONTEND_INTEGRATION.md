# Guía de integración para Frontend

## Autenticación

1. Registrar usuario en `POST /api/users/`.
2. Hacer login con `POST /api/auth/login` usando formulario OAuth2.
3. Guardar el token en memoria o en cookie segura según la estrategia del Frontend.
4. Enviar el token en `Authorization: Bearer <token>` para todas las rutas protegidas.

## Datos que el Frontend no debe recalcular

- Saldos de cuentas.
- Progreso de presupuestos.
- Totales del dashboard.
- Reglas de borrado de entidades relacionadas.

## Contratos importantes

- No enviar `user_id` en cuentas, categorías, transacciones ni presupuestos.
- No enviar `balance` en edición de cuentas.
- No asumir que una categoría es editable si su `user_id` es `null`.
- No permitir transacciones sin cuenta y categoría válidas.

## Pantallas sugeridas y fuentes de datos

- Dashboard: `GET /api/dashboard/summary` y `GET /api/dashboard/budgets-progress`.
- Cuentas: `GET /api/accounts/`.
- Transacciones: `GET /api/transactions/`.
- Categorías: `GET /api/categories/`.
- Presupuestos: `GET /api/budgets/`.

## Manejo de errores

- `401`: token ausente o inválido.
- `403`: credenciales inválidas o acción no permitida.
- `404`: recurso inexistente o no perteneciente al usuario.
- `400`: validación de negocio fallida, como duplicados o relaciones bloqueadas.

## Recomendaciones para el equipo de Frontend

- Mostrar mensajes de error del backend de forma consistente.
- Deshabilitar formularios que dependan de entidades bloqueadas.
- No duplicar cálculos de saldo o progreso en el cliente.
- Tratar al dashboard como fuente de verdad para métricas agregadas.