import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from app.auth.security import hash_password
from app.database import Base, SessionLocal, engine
from app.models import Role, User
from app.routers import auth, dashboard, items, master_data, transfers, users


def bootstrap_admin(environment: str | None = None, session_factory=None):
    """Create a development admin only when the environment permits it.

    Production must not silently create a privileged user. In development/test,
    credentials can still be configured via environment variables.
    """
    env_name = (environment or os.getenv("WARETRACK_ENV") or os.getenv("ENVIRONMENT") or "development").lower()
    if env_name in {"production", "prod"}:
        return {"created": False, "environment": env_name, "reason": "production bootstrap disabled"}

    session_maker = session_factory or SessionLocal
    email = (os.getenv("WARETRACK_ADMIN_EMAIL") or "admin@waretrack.lv").lower()
    password = os.getenv("WARETRACK_ADMIN_PASSWORD") or "Admin123!"

    with session_maker() as db:
        existing = db.scalar(select(User).where(func.lower(User.email) == email))
        if existing is not None:
            return {"created": False, "environment": env_name, "email": email, "reason": "admin already exists"}

        admin = User(
            name="WareTrack Administrator",
            email=email,
            password_hash=hash_password(password),
            role=Role.ADMIN,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        return {"created": True, "environment": env_name, "email": email, "reason": "dev bootstrap"}


# Create database tables.
Base.metadata.create_all(bind=engine)

# Initialize the default administrator only in non-production environments.
bootstrap_admin()


# Initialize FastAPI.
app = FastAPI(
    title="WareTrack API",
    version="1.0.0",
    description="WareTrack noliktavas vadības REST API",
)


# Configure CORS.
origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Register API routers.
app.include_router(auth.router, prefix="/api")
app.include_router(items.router, prefix="/api")

app.include_router(
    master_data.categories,
    prefix="/api",
)

app.include_router(
    master_data.suppliers,
    prefix="/api",
)

app.include_router(
    master_data.locations,
    prefix="/api",
)

app.include_router(transfers.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(users.router, prefix="/api")


@app.exception_handler(RequestValidationError)
async def validation_error(
    request: Request,
    exc: RequestValidationError,
):
    errors = [
        {
            "field": ".".join(str(part) for part in error["loc"][1:]),
            "message": error["msg"],
        }
        for error in exc.errors()
    ]

    return JSONResponse(
        status_code=422,
        content={
            "detail": "Ievadītie dati nav derīgi",
            "errors": errors,
        },
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}
