import os
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    if ENVIRONMENT in {"production", "prod"}:
        raise RuntimeError("JWT_SECRET_KEY must be configured in production")
    SECRET_KEY = "local-development-only-change-this-secret-waretrack"
if ENVIRONMENT in {"production", "prod"} and len(SECRET_KEY) < 32:
    raise RuntimeError("JWT_SECRET_KEY must contain at least 32 characters in production")
ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "480"))
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(user_id: int) -> str:
    issued = datetime.now(timezone.utc)
    expires = issued + timedelta(minutes=ACCESS_TOKEN_MINUTES)
    return jwt.encode(
        {"sub": str(user_id), "type": "access", "iat": issued, "exp": expires},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> int:
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("type") != "access":
        raise ValueError("Invalid token type")
    return int(payload["sub"])

