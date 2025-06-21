from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from ..database import get_db
from ..security import get_current_user, admin_required
from .. import crud, models, schemas

router = APIRouter(prefix="/materials", tags=["Материалы"])


# ------------------------------------------------
# Pydantic-модель для истории списаний
class MaterialHistory(BaseModel):
    order_id: Optional[int]
    order_number: Optional[str]
    qty: float
    dt: datetime

    model_config = {"from_attributes": True}
# ------------------------------------------------


# ---------- CRUD (admin only) ----------
@router.get(
    "/",
    response_model=List[schemas.Material],
    dependencies=[Depends(admin_required)]
)
def all_materials(db: Session = Depends(get_db)):
    return crud.list_materials(db)


@router.post(
    "/",
    response_model=schemas.Material,
    dependencies=[Depends(admin_required)]
)
def create(mat: schemas.MaterialCreate, db: Session = Depends(get_db)):
    return crud.create_or_add_material(db, mat)


@router.put(
    "/{mid}",
    response_model=schemas.Material,
    dependencies=[Depends(admin_required)]
)
def update(mid: int, mat: schemas.MaterialCreate, db: Session = Depends(get_db)):
    obj = crud.update_material(db, mid, mat)
    if not obj:
        raise HTTPException(404, "Материал не найден")
    return obj


@router.delete(
    "/{mid}",
    dependencies=[Depends(admin_required)]
)
def delete(mid: int, db: Session = Depends(get_db)):
    crud.delete_material(db, mid)
    return {"ok": True}


@router.patch(
    "/{mid}/min",
    dependencies=[Depends(admin_required)]
)
def set_min(mid: int, value: float, db: Session = Depends(get_db)):
    crud.update_min_qty(db, mid, value)
    return {"ok": True}


# ---------- Остатки / история (any role) ----------
@router.get(
    "/stock",
    dependencies=[Depends(get_current_user)]
)
def stock(db: Session = Depends(get_db)):
    return crud.stock_materials(db)


@router.get(
    "/{mid}/history",
    response_model=List[MaterialHistory],
    dependencies=[Depends(get_current_user)]
)
def history(
    mid: int,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """
    Возвращает до `limit` последних движений по материалу mid:
    • order_id     — ID заказа (или None)
    • order_number — Номер заказа (строка) или None для ручных движений
    • qty          — изменение (может быть ±)
    • dt           — время движения
    """
    # джоин на orders, чтобы получить order.number
    q = (
        db.query(
            models.StockMovement,
            models.Order.number.label("order_number")
        )
        .outerjoin(models.Order, models.Order.id == models.StockMovement.order_id)
        .filter(models.StockMovement.material_id == mid)
        .order_by(models.StockMovement.created_at.desc())
        .limit(limit)
        .all()
    )

    out: List[MaterialHistory] = []
    for mv, ord_num in q:
        out.append(MaterialHistory(
            order_id=mv.order_id,
            # приводим номер к строке, если он есть
            order_number=str(ord_num) if ord_num is not None else None,
            qty=mv.qty,
            dt=mv.created_at,
        ))
    return out


# ---------- Коррекция qty (any role) ----------
@router.patch(
    "/{mid}/adjust",
    dependencies=[Depends(get_current_user)]
)
def adjust(mid: int, delta: float, db: Session = Depends(get_db)):
    crud.add_adjustment(db, mid, delta)
    return {"ok": True}
