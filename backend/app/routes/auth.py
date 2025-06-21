from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel


from ..database import get_db
from ..models import Role, User
from ..security import verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenOut)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user: User | None = (
        db.query(User).filter(User.username == form.username, User.is_active).first()
    )
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    return TokenOut(access_token=create_access_token(user.username))


class MeOut(BaseModel):
    username: str
    role: Role


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)):
    return {"username": user.username, "role": user.role}
