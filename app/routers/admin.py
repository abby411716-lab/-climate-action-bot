from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import crud
from app.config import settings
from app.database import get_db

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin_key(x_admin_key: str = Header(default="")):
    if not settings.admin_api_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Forbidden")


class SchoolCreate(BaseModel):
    school_name: str
    join_link_code: str


@router.post("/schools", dependencies=[Depends(require_admin_key)])
def create_school(payload: SchoolCreate, db: Session = Depends(get_db)):
    existing = crud.get_school_by_join_code(db, payload.join_link_code)
    if existing:
        return {"school_id": existing.school_id, "school_name": existing.school_name, "already_existed": True}

    from app import models

    school = models.School(school_name=payload.school_name, join_link_code=payload.join_link_code)
    db.add(school)
    db.commit()
    db.refresh(school)
    return {"school_id": school.school_id, "school_name": school.school_name, "already_existed": False}


@router.get("/schools", dependencies=[Depends(require_admin_key)])
def list_schools(db: Session = Depends(get_db)):
    return [
        {"school_id": s.school_id, "school_name": s.school_name, "join_link_code": s.join_link_code}
        for s in crud.list_schools(db)
    ]


class SchoolUpdate(BaseModel):
    school_name: str


@router.patch("/schools/{school_id}", dependencies=[Depends(require_admin_key)])
def update_school(school_id: int, payload: SchoolUpdate, db: Session = Depends(get_db)):
    school = crud.get_school_by_id(db, school_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    school.school_name = payload.school_name
    db.commit()
    db.refresh(school)
    return {"school_id": school.school_id, "school_name": school.school_name}
