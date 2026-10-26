
import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from app.auth.security import hash_password
from app.database import Base, SessionLocal, engine
from app.models import User
from app.routers import auth, dashboard, items, master_data, transfers, users


# Create database tables.
Base.metadata.create_all(bind=engine)


# Create the initial administrator if it does not exist.
def ensure_admin():
    """Create the initial administrator if no administrator exists."""
    db = SessionLocal()

    try:
        admin = db.scalar(
            select(User).where(
                func.lower(User.email) == "admin@waretrack.lv"
            )
        )

        if admin is None:
            admin = User(
                name="WareTrack Administrator",
                email="admin@waretrack.lv",
                password_hash=hash_password("Admin123!"),
                role="ADMIN",
                is_active=True,
            )

            db.add(admin)
            db.commit()

            print("Initial administrator created.")
        else:
            print("Administrator already exists; no changes made.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# Initialize the administrator.
ensure_admin()


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


# Handle request validation errors.
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


# Health check endpoint.
@app.get("/api/health")
def health():
    return {"status": "ok"}
