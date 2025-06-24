# backend/app/crud.py
from __future__ import annotations

import anyio
import asyncio
from typing import List

from passlib.context import CryptContext
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app import models, schemas, telegram
from backend.app.services.insales import fetch_orders

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ---------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------


def set_user_password(db: Session, user: models.User, raw_password: str) -> None:
    user.hashed_password = pwd_ctx.hash(raw_password)
    db.commit()


def _current_qty(db: Session, material_id: int) -> float:
    base = (
        db.query(models.Material.base_qty)
        .filter_by(id=material_id)
        .scalar()
        or 0.0
    )
    delta = (
        db.query(func.coalesce(func.sum(models.StockMovement.qty), 0.0))
        .filter_by(material_id=material_id)
        .scalar()
        or 0.0
    )
    return base + delta


# ---------------------------------------------------------------------
# materials
# ---------------------------------------------------------------------
def list_materials(db: Session) -> List[models.Material]:
    return db.query(models.Material).all()


def create_or_add_material(db: Session, data: schemas.MaterialCreate) -> models.Material:
    mat = db.query(models.Material).filter_by(name=data.name).first()
    if mat:
        mat.base_qty += data.base_qty or 0.0
    else:
        mat = models.Material(**data.dict())
        db.add(mat)
    db.commit()
    db.refresh(mat)
    return mat


def delete_material(db: Session, material_id: int) -> None:
    """
    Удаляем материал вместе со всеми зависимостями (rules, movements, suppliers),
    чтобы не получить ошибку внешнего ключа.
    """
    db.query(models.StockMovement).filter_by(material_id=material_id).delete()
    db.query(models.MaterialRule).filter_by(material_id=material_id).delete()
    db.query(models.Supplier).filter_by(material_id=material_id).delete()
    db.query(models.Material).filter_by(id=material_id).delete()
    db.commit()


def history_material(db: Session, mid: int, limit: int = 50):
    rows = (
        db.query(models.StockMovement)
        .filter(models.StockMovement.material_id == mid)
        .order_by(models.StockMovement.created_at.desc())
        .limit(limit)
        .all()
    )
    out = []
    for r in rows:
        ord_ = db.get(models.Order, r.order_id)
        number = ord_.number if ord_ else None
        dt = r.created_at.isoformat(timespec="seconds") + "Z"
        out.append({"order_number": number, "qty": r.qty, "dt": dt})
    return out


def add_adjustment(db: Session, material_id: int, delta: float) -> None:
    db.add(
        models.StockMovement(
            material_id=material_id,
            order_id=None,
            qty=delta,
        )
    )
    db.commit()


def stock_materials(db: Session) -> list[dict]:
    q = (
        db.query(
            models.Material.id,
            models.Material.name,
            models.Material.unit,
            models.Material.min_qty,
            (
                models.Material.base_qty
                + func.coalesce(func.sum(models.StockMovement.qty), 0.0)
            ).label("qty"),
        )
        .outerjoin(
            models.StockMovement,
            models.Material.id == models.StockMovement.material_id,
        )
        .group_by(models.Material.id)
        .all()
    )
    return [
        {
            "id": item.id,
            "name": item.name,
            "unit": item.unit,
            "min_qty": item.min_qty,
            "qty": item.qty,
        }
        for item in q
    ]


# ---------------------------------------------------------------------
# rules
# ---------------------------------------------------------------------
def list_rules(db: Session) -> List[models.MaterialRule]:
    return db.query(models.MaterialRule).all()


def create_rule(db: Session, data: schemas.MaterialRuleCreate) -> models.MaterialRule:
    rule = models.MaterialRule(**data.dict())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def delete_rule(db: Session, rule_id: int) -> None:
    db.query(models.MaterialRule).filter_by(id=rule_id).delete()
    db.commit()


# ---------------------------------------------------------------------
# internal: apply rules to an order (create StockMovement records)
# ---------------------------------------------------------------------
def _apply_rules(db: Session, order: schemas.OrderOut) -> None:
    """
    Сначала удаляем старые движения этого заказа, затем создаём новые
    в соответствии с материал-правилами.
    """
    db.query(models.StockMovement).filter_by(order_id=order.id).delete()

    if order.ignored:
        db.commit()
        return

    rules = db.query(models.MaterialRule).all()
    for ln in order.lines:
        title_lc = ln.product_title.lower()
        for r in rules:
            if r.pattern.lower() in title_lc:
                db.add(
                    models.StockMovement(
                        material_id=r.material_id,
                        order_id=order.id,
                        qty=-(r.qty * ln.quantity),
                    )
                )
    db.commit()


# ---------------------------------------------------------------------
# orders
# ---------------------------------------------------------------------
def upsert_order(db: Session, data: schemas.OrderOut) -> models.Order:
    order = db.get(models.Order, data.id)
    if not order:
        order = models.Order(
            id=data.id,
            number=data.number,
            created_at=data.created_at,
            total_price=data.total_price
        )
        db.add(order)
    # всегда обновляем изменяемые поля:
    order.customer = f"{data.surname} {data.name}".strip() if hasattr(data, "surname") else data.customer
    order.created_at = data.created_at
    order.ignored = data.ignored
    order.total_price = data.total_price
    db.commit()

    # replace order lines
    db.query(models.OrderLine).filter_by(order_id=data.id).delete()
    for line in data.lines:
        db.add(
            models.OrderLine(
                order_id=data.id,
                product_id=line.product_id,
                product_title=line.product_title,
                quantity=line.quantity,
            )
        )
    db.commit()

    # применяем правила списания
    _apply_rules(db, data)

    db.refresh(order)
    return order


def list_orders(db: Session) -> List[models.Order]:
    return db.query(models.Order).order_by(models.Order.created_at.desc()).all()


def ignore_order(db: Session, order_id: int, ignore: bool) -> None:
    """
    Помечаем/снимаем заказ как ignored и создаём компенсирующие движения.
    """
    order = db.get(models.Order, order_id)
    if not order or order.ignored == ignore:
        return

    # инвертируем уже созданные записи StockMovement
    for mv in db.query(models.StockMovement).filter_by(order_id=order_id).all():
        db.add(
            models.StockMovement(
                material_id=mv.material_id,
                order_id=None,
                qty=-mv.qty,
            )
        )
    order.ignored = ignore
    db.commit()


# ---------------------------------------------------------------------
# import from Insales (manual button & background)
# ---------------------------------------------------------------------
def import_orders(db: Session, limit: int = 50) -> int:
    """
    Скачиваем последние `limit` заказов и заносим их в БД.
    Возвращаем число успешно импортированных.
    """
    orders = asyncio.run(fetch_orders(limit))
    for o in orders:
        upsert_order(db, o)
    return len(orders)


def update_min_qty(db: Session, material_id: int, new_min: float) -> None:
    """
    Обновляем минимальный остаток для материала и,
    при необходимости, отправляем или снимаем телеграм-алёрт.
    """
    mat = db.get(models.Material, material_id)
    if not mat:                       # материал не найден
        return

    mat.min_qty = new_min
    current = _current_qty(db, material_id)

    # если опустились ниже минимума и ещё не слали оповещение
    if current <= mat.min_qty and not mat.alerted:
        anyio.from_thread.run(
            telegram.low_stock, mat.name, current, mat.min_qty
        )
        mat.alerted = True

    # если снова стало больше минимума — сбрасываем флаг
    elif current > mat.min_qty and mat.alerted:
        mat.alerted = False

    db.commit()
