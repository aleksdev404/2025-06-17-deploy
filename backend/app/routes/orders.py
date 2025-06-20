# backend/app/routes/orders.py

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import admin_required
from .. import crud, schemas
from ..services.insales import fetch_orders

from httpx import HTTPError, ConnectTimeout, ReadTimeout
from fastapi import HTTPException

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get(
    "/",
    response_model=list[schemas.OrderOut],
    dependencies=[Depends(admin_required)]
)
def read_orders(db: Session = Depends(get_db)):
    """
    Список всех заказов (только для админа).
    """
    return crud.list_orders(db)


@router.post(
    "/import",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(admin_required)]
)
async def import_orders(db: Session = Depends(get_db)):
    """
    Ручной импорт заказов кнопкой.
    502 — если InSales недоступен / таймаут.
    """
    try:
        orders = await fetch_orders(50)
    except (ConnectTimeout, ReadTimeout):
        raise HTTPException(status_code=502, detail="InSales API timeout")
    except HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"InSales error: {exc!s}")

    for o in orders:
        crud.upsert_order(db, o)

    return {"imported": len(orders)}


@router.delete(
    "/{order_id}",
    dependencies=[Depends(admin_required)]
)
def ignore_order(order_id: int, db: Session = Depends(get_db)):
    """
    DELETE → помечаем заказ ignored=True, списываем материалы.
    """
    crud.ignore_order(db, order_id, True)
    return {"ok": True}


@router.patch(
    "/{order_id}/enable",
    dependencies=[Depends(admin_required)]
)
def enable_order(order_id: int, db: Session = Depends(get_db)):
    """
    PATCH → снимаем флаг ignored, возвращаем материалы.
    """
    crud.ignore_order(db, order_id, False)
    return {"ok": True}
