from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_admin
from app.auth.security import hash_password
from app.database import get_db
from app.models import Role, User
from app.schemas import UserCreate, UserOut, UserUpdate
from app.services.activity import log_activity

router = APIRouter(prefix="/users", tags=["Lietotāji"])


@router.get("", response_model=list[UserOut])
def user_list(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return list(db.scalars(select(User).order_by(User.created_at.desc())))


@router.get("/{user_id}", response_model=UserOut)
def user_get(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "Lietotājs nav atrasts")
    return user


@router.post("", response_model=UserOut, status_code=201)
def user_create(data: UserCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    email = data.email.lower()
    if db.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise HTTPException(409, "Lietotājs ar šādu e-pastu jau pastāv")
    user = User(name=data.name.strip(), email=email, password_hash=hash_password(data.password), role=data.role)
    db.add(user)
    try:
        db.flush()
        log_activity(db, admin, "create", "user", user.id, f"Izveidots lietotāja konts: {user.email}")
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise HTTPException(500, "Neizdevās izveidot lietotāju")
    return user


@router.patch("/{user_id}", response_model=UserOut)
def user_update(user_id: int, data: UserUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if not user: raise HTTPException(404, "Lietotājs nav atrasts")
    removing_admin = user.role == Role.ADMIN and (
        data.role is not None and data.role != Role.ADMIN or data.is_active is False
    )
    if removing_admin and user.id == admin.id:
        raise HTTPException(409, "Nevar deaktivizēt vai pazemināt pašreizējo administratora kontu")
    if removing_admin:
        admin_count = db.scalar(select(func.count(User.id)).where(User.role == "ADMIN", User.is_active.is_(True))) or 0
        if admin_count <= 1: raise HTTPException(409, "Sistēmā jāpaliek vismaz vienam aktīvam administratoram")
    if data.role is not None: user.role = data.role
    if data.is_active is not None: user.is_active = data.is_active
    if data.role is not None or data.is_active is not None:
        log_activity(db, admin, "update", "user", user.id, f"Atjaunināts lietotāja konts: {user.email}")
    db.commit(); db.refresh(user); return user

