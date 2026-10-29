from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models import Company, CompanyJoinRequest, User
from app.schemas import LoginIn, RegisterIn, TokenOut, UserOut

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenOut, status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    email = data.email.lower()
    company = db.get(Company, data.company_id)
    if company is None:
        raise HTTPException(404, "Company not found")
    if not company.is_active:
        raise HTTPException(409, "Company is not active")
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(409, "User with this email already exists")

    user = User(
        name=data.name.strip(),
        email=email,
        password_hash=hash_password(data.password),
        role="USER",
    )
    try:
        db.add(user)
        db.flush()
        db.add(CompanyJoinRequest(company_id=company.id, user_id=user.id, status="PENDING"))
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Registration could not be completed") from None

    return TokenOut(access_token=create_access_token(user.id), user=user)


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == data.email.lower()))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(403, "User account is deactivated")
    return TokenOut(access_token=create_access_token(user.id), user=user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user