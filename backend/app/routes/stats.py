from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, datetime, timedelta
from backend.app.database import get_db
from backend.app import models

router = APIRouter(prefix="/stats", tags=["Статистика"])


# начало месяца 12 месяцев назад
def cutoff_date() -> date:
    today = datetime.utcnow().date().replace(day=1)
    year  = today.year - 1      # ← 12 мес.
    month = today.month
    return date(year, month, 1)


@router.get("/totals")
def totals(year: int | None = Query(None, ge=2000),
           month: int | None = Query(None, ge=1, le=12),
           db: Session = Depends(get_db)):
    """
    Чистый расход по каждому материалу.
    • Без параметров — за последние 12 месяцев.
    • c year & month — за указанный календарный месяц.
    """
    q = (db.query(models.Material.name,
                  func.sum(models.StockMovement.qty).label("sum_qty"))
            .join(models.StockMovement,
                  models.Material.id == models.StockMovement.material_id))

    if year and month:
        start = date(year, month, 1)
        end   = date(year + (month == 12), (month % 12) + 1, 1)
    else:
        start = cutoff_date()
        end   = datetime.utcnow().date() + timedelta(days=1)

    q = q.filter(models.StockMovement.created_at >= start,
                 models.StockMovement.created_at <  end)

    rows = (q.group_by(models.Material.name)
              .order_by(func.sum(models.StockMovement.qty)).all())

    out = {}
    for name, sum_qty in rows:          # суммируются и списания, и возвраты
        spent = max(0, -sum_qty)        # чистый расход, не может быть < 0
        out[name] = spent
    return out
