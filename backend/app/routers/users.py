from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_admin
from app.database import get_db
from app.models import User
from app.schemas import UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["Lietot?üji"])


@router.get("", response_model=list[UserOut])
def user_list(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return list(db.scalars(select(User).order_by(User.created_at.desc())))


@router.get("/{user_id}", response_model=UserOut)
def user_get(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "Lietot?üjs nav atrasts")
    return user


@router.patch("/{user_id}", response_model=UserOut)
def user_update(user_id: int, data: UserUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if not user: raise HTTPException(404, "Lietot?üjs nav atrasts")
    removing_admin = user.role == "ADMIN" and (data.role == "USER" or data.is_active is False)
    if removing_admin:
        admin_count = db.scalar(select(func.count(User.id)).where(User.role == "ADMIN", User.is_active.is_(True))) or 0
        if admin_count <= 1: raise HTTPException(409, "Sist?ōm?ü j?üpaliek vismaz vienam akt?½vam administratoram")
    if data.role is not None: user.role = data.role
    if data.is_active is not None: user.is_active = data.is_active
    db.commit(); db.refresh(user); return user

