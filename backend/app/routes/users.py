from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from uuid import UUID

from database import get_db
from models import User, Role
from security import hash_password, admin_required

router = APIRouter(prefix="/users", tags=["users"])


# ---------- Pydantic-модели ----------

class UserCreate(BaseModel):
    username: str = Field(..., max_length=48)
    password: str = Field(..., min_length=6)
    role: Role = Role.collector


class UserOut(BaseModel):
    id: UUID
    username: str
    role: Role
    is_active: bool

    class Config:
        orm_mode = True


class PasswordChange(BaseModel):
    new_password: str = Field(..., min_length=6)


# ---------- CRUD-эндпоинты (только admin) ----------

@router.get(
    "/",
    response_model=list[UserOut],
    dependencies=[Depends(admin_required)]
)
def list_users(db: Session = Depends(get_db)):
    return db.query(User).all()


@router.post(
    "/",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(admin_required)]
)
def create_user(data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter_by(username=data.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    user = User(
        username=data.username,
        hashed_password=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch(
    "/{user_id}/state",
    dependencies=[Depends(admin_required)]
)
def toggle_active(user_id: UUID, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = not user.is_active
    db.commit()
    return {"ok": True, "is_active": user.is_active}


@router.patch(
    "/{user_id}/role",
    dependencies=[Depends(admin_required)]
)
def change_role(user_id: UUID, role: Role, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = role
    db.commit()
    return {"ok": True, "role": user.role}


@router.patch(
    "/{user_id}/password",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(admin_required)]
)
def change_password(
    user_id: UUID,
    body: PasswordChange,
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.hashed_password = hash_password(body.new_password)
    db.commit()
    return {"ok": True}
