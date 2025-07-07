import os
from datetime import datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from database import get_db
from models import User, Role

SECRET_KEY = os.getenv("SECRET_KEY", "CHANGEME_SUPER_SECRET")
ALGORITHM = "HS256"
ACCESS_TTL = timedelta(hours=8)

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# ------------------------------------------------------------------ #
# утилиты паролей


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


def hash_password(password: str) -> str:
    return pwd_ctx.hash(password)

# ------------------------------------------------------------------ #
# JWT


def create_access_token(subject: str, ttl: timedelta = ACCESS_TTL) -> str:
    now = datetime.utcnow()
    payload = {"sub": subject, "iat": now, "exp": now + ttl}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _credentials_exc() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

# ------------------------------------------------------------------ #
# зависимости


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str | None = payload.get("sub")
    except JWTError:
        raise _credentials_exc()
    if username is None:
        raise _credentials_exc()
    user = db.query(User).filter(User.username == username, User.is_active).first()
    if user is None:
        raise _credentials_exc()
    return user


def admin_required(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user
