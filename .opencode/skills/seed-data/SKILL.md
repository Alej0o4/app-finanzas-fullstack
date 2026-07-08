---
name: seed-data
description: Carga datos de prueba multi-moneda con 3 cuentas, 45 transacciones y 6 presupuestos
---

## Seed Data — Test User

Carga un usuario con datos financieros realistas para probar todas las funcionalidades.

### Requisitos

- Backend arrancado (después de `Base.metadata.create_all()`).
- BD SQLite vacía o con datos. El script limpia al usuario `test@test.com` si existe antes de recrearlo.

### Ejecución

```sh
cd backend && source venv/bin/activate && python -c "from app.core.seed import run_seed; run_seed()"
```

### Credenciales

| Campo | Valor |
|-------|-------|
| email | `test@test.com` |
| password | `testpass123` |

### Datos creados

| Entidad | Cantidad | Detalle |
|---------|----------|---------|
| **Cuentas** | 3 | Cuenta Principal (COP 14,478,000), Ahorros USD ($4,615), Tarjeta Crédito (COP -250,000) |
| **Transacciones** | 45 | May–Jul 2026, multi-moneda, multi-cuenta, recurrencias |
| **Presupuestos** (Jul 2026) | 6 | Alimentación 26%, Transporte 34%, Ocio 47%, Suscripción 75%, Cuidado personal 48%, **Servicios Públicos 93%** |
| **Categorías** | 2 custom | Freelance (income), Servicios Públicos (expense) |

### Edge cases cubiertos

- **Multi-moneda**: Cuentas COP + USD; transacciones heredan moneda de la cuenta
- **Presupuesto crítico**: Servicios Públicos al 93% (ring near-limit)
- **Saldo negativo**: Tarjeta Crédito con -$250,000 COP
- **Historial 3 meses**: Cashflow chart con May, Jun, Jul
- **Múltiples tx/misma categoría**: Alimentación con 5 transacciones en julio
- **Recurrencias**: Suscripciones (Netflix, Spotify, Crunchyroll a $25K c/u)

### Verificación

```sh
# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test@test.com&password=testpass123"

# Cuentas
curl http://localhost:8000/api/accounts/ -H "Authorization: Bearer $TOKEN"

# Dashboard
curl http://localhost:8000/api/dashboard/summary -H "Authorization: Bearer $TOKEN"

# Progreso presupuestos
curl http://localhost:8000/api/dashboard/budgets-progress -H "Authorization: Bearer $TOKEN"
```
