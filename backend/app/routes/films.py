from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import ReadyFilm
from schemas import FilmOut
from security import get_current_user

router = APIRouter(prefix="/films", tags=["films"])


@router.get("/", response_model=list[FilmOut],
            dependencies=[Depends(get_current_user)])
def list_films(db: Session = Depends(get_db)):
    # ORDER BY для стабильного вывода
    return db.query(ReadyFilm).order_by(ReadyFilm.title).all()
