import os
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "480"))
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def validate_auth_configuration() -> str:
    secret_key = os.getenv("JWT_SECRET_KEY", "")
    if len(secret_key) < 32:
        raise RuntimeError("JWT_SECRET_KEY must be explicitly set to at least 32 characters")
    return secret_key


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(user_id: int) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_MINUTES)
    return jwt.encode(
        {"sub": str(user_id), "exp": expires},
        validate_auth_configuration(), algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> int:
    payload = jwt.decode(token, validate_auth_configuration(), algorithms=[ALGORITHM])
    return int(payload["sub"])

