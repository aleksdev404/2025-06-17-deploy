from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Union
from backend.app.database import get_db
from backend.app import crud, schemas

router = APIRouter(prefix="/rules", tags=["Правила"])


@router.get("/", response_model=list[schemas.MaterialRule])
def get_rules(db: Session = Depends(get_db)):
    return crud.list_rules(db)


@router.post("/", response_model=list[schemas.MaterialRule])
def create_rule(payload: Union[schemas.MaterialRuleCreate,
                               list[schemas.MaterialRuleCreate]],
                db: Session = Depends(get_db)):
    items = payload if isinstance(payload, list) else [payload]
    items = [i for i in items if i.material_id]      # убираем пустые связанные
    if not items:
        raise HTTPException(400, "Нет валидных правил")
    return [crud.create_rule(db, r) for r in items]


@router.delete("/{rid}")
def delete_rule(rid: int, db: Session = Depends(get_db)):
    crud.delete_rule(db, rid)
    return {"ok": True}
