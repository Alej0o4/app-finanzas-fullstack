from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
import datetime

# Importamos la Clase Base que creamos en nuestro archivo de configuración
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    # 1. Columnas físicas en la base de datos
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # 2. Relaciones virtuales (La "Magia" del ORM)
    accounts = relationship("Account", back_populates="owner")
    categories = relationship("Category", back_populates="owner")
    transactions = relationship("Transaction", back_populates="owner")
    budgets = relationship("Budget", back_populates="owner")


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    type = Column(String) # Ej: "cash", "debit"
    balance = Column(Float, default=0.0)
    
    # 3. La Llave Foránea (El tornillo físico que une las tablas)
    user_id = Column(Integer, ForeignKey("users.id"))

    # Relación virtual de vuelta al usuario (hacia el padre)
    owner = relationship("User", back_populates="accounts")
    # Relación hacia los hijos (sus transacciones)
    transactions = relationship("Transaction", back_populates="account")

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    type = Column(String) # "income" o "expense"

    user_id = Column(Integer, ForeignKey("users.id"),nullable=True)

    owner = relationship("User", back_populates="categories")
    # Relación hacia los hijos (sus transacciones y presupuestos)
    transactions = relationship("Transaction", back_populates="category")
    budgets = relationship("Budget", back_populates="category")

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Float, nullable=False)
    type = Column(String) # "income" o "expense"
    date = Column(DateTime, default=datetime.datetime.utcnow)
    description = Column(String, nullable=True)

    user_id = Column(Integer, ForeignKey("users.id"))
    account_id = Column(Integer, ForeignKey("accounts.id"))
    category_id = Column(Integer, ForeignKey("categories.id"))

    owner = relationship("User", back_populates="transactions")
    account = relationship("Account", back_populates="transactions")
    category = relationship("Category", back_populates="transactions")


class Budget(Base):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, index=True)
    amount_limit = Column(Float, nullable=False)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"))
    category_id = Column(Integer, ForeignKey("categories.id"))

    owner = relationship("User", back_populates="budgets")
    category = relationship("Category", back_populates="budgets")




    