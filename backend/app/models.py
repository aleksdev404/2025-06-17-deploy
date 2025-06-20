import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    BigInteger,
    String,
    Float,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.app.database import Base


# ---------- User & Roles ----------

class Role(str, enum.Enum):
    admin     = "admin"
    collector = "collector"


class User(Base):
    __tablename__ = "users"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username        = Column(String(48), unique=True, nullable=False, index=True)
    hashed_password = Column(String(128), nullable=False)
    role            = Column(Enum(Role), default=Role.collector, nullable=False)
    is_active       = Column(Boolean, default=True, nullable=False)
    created_at      = Column(DateTime, default=datetime.utcnow, nullable=False)


# ---------- Materials & Rules ----------

class Material(Base):
    __tablename__ = "materials"

    id       = Column(Integer, primary_key=True)
    name     = Column(String, unique=True, nullable=False)
    unit     = Column(String, default="шт", nullable=False)
    base_qty = Column(Float, default=0.0, nullable=False)
    min_qty  = Column(Float, default=0.0, nullable=False)
    alerted  = Column(Boolean, default=False, nullable=False)  # уже слали TG-уведомление
    


class MaterialRule(Base):
    __tablename__ = "material_rules"

    id          = Column(Integer, primary_key=True)
    pattern     = Column(String, nullable=False)
    material_id = Column(Integer, ForeignKey("materials.id", ondelete="CASCADE"), nullable=False)
    qty         = Column(Float, default=1.0, nullable=False)

    material = relationship("Material")


# ---------- Orders & OrderLines ----------

class Order(Base):
    __tablename__ = "orders"

    id             = Column(Integer, primary_key=True)
    number         = Column(String, index=True, nullable=False)
    customer       = Column(String)
    created_at     = Column(DateTime, nullable=False)
    ignored        = Column(Boolean, default=False, nullable=False)
    ready_notified = Column(Boolean, default=False, nullable=False)  # уведомление о готовых плёнках отправлено?
    client_notified = Column(Boolean, default=False, nullable=False)

    lines = relationship("OrderLine", back_populates="order", cascade="all, delete-orphan")


class OrderLine(Base):
    __tablename__ = "order_lines"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    order_id      = Column(BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id    = Column(BigInteger, nullable=False)
    product_title = Column(String, nullable=False)
    quantity      = Column(Integer, nullable=False)

    order = relationship("Order", back_populates="lines")



# ---------- Stock Movements ----------

class StockMovement(Base):
    __tablename__ = "stock_movements"

    id          = Column(Integer, primary_key=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    order_id    = Column(BigInteger, ForeignKey("orders.id"), nullable=True)
    qty         = Column(Float, nullable=False)
    created_at  = Column(DateTime, default=datetime.utcnow, nullable=False)


# ---------- Ready Films (склад готовых плёнок) ----------

class ReadyFilm(Base):
    __tablename__ = "ready_films"

    sku        = Column(String, primary_key=True)   # артикул или уникальный ключ строки
    title      = Column(String, nullable=False)
    quantity   = Column(Integer, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


