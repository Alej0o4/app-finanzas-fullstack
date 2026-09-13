"""Catálogo de categorías base del sistema (Fase 18, §18.1/§18.2).

Vive fuera de `main.py` a propósito (Decisión 18.2, "Nota de implementación" de la spec):
`main.py` importa routers (incluido `api/users.py`), así que importar constantes desde
`main.py` en `users.py` crearía un import circular. Este módulo es el lugar neutral que
tanto `main.py` (seed de startup) como `api/users.py` (pre-siembra de ocultas en el
registro) importan.
"""

DEFAULT_CATEGORIES = [
    {"name": "Alimentación", "type": "expense", "icon": "UtensilsCrossed"},
    {"name": "Transporte", "type": "expense", "icon": "Car"},
    {"name": "Vivienda", "type": "expense", "icon": "House"},
    {"name": "Salud", "type": "expense", "icon": "HeartPulse"},
    {"name": "Educación", "type": "expense", "icon": "GraduationCap"},
    {"name": "Entretenimiento", "type": "expense", "icon": "Gamepad2"},
    {"name": "Cuidado personal", "type": "expense", "icon": "Heart"},
    {"name": "Suscripción", "type": "expense", "icon": "Radio"},
    {"name": "Otro", "type": "expense", "icon": "CircleEllipsis"},
    {"name": "Salario", "type": "income", "icon": "Wallet"},
    {"name": "Otros ingresos", "type": "income", "icon": "TrendingUp"},
    # Fase 18 §18.1 (Decisión Q5): 8 categorías nuevas, todas type=expense, íconos
    # verificados contra lucide-react instalado. Son altas puras (no renombres): ningún
    # nombre choca con uno existente bajo la comparación case/acento-insensible de
    # `_normalizar_nombre_categoria` — "Transporte" convive con "Transporte público"/
    # "Uber"/"Carro" como strings distintos (ROADMAP.md:635-636).
    {"name": "Mercado", "type": "expense", "icon": "ShoppingCart"},
    {"name": "Pareja", "type": "expense", "icon": "HeartHandshake"},
    {"name": "Regalos", "type": "expense", "icon": "Gift"},
    {"name": "Restaurantes", "type": "expense", "icon": "Utensils"},
    {"name": "Gastos hormiga", "type": "expense", "icon": "Coins"},
    {"name": "Uber", "type": "expense", "icon": "CarTaxiFront"},
    {"name": "Carro", "type": "expense", "icon": "Fuel"},
    {"name": "Transporte público", "type": "expense", "icon": "Bus"},
]

LEGACY_DEFAULT_CATEGORY_NAMES = {
    ("expense", "Otro"): "Otro (Gasto)",
    ("income", "Otro"): "Otro (Ingreso)",
    ("expense", "Entretenimiento"): "Ocio",
}
