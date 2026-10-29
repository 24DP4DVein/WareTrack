import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database import engine, initialize_database
from app.routers import auth, company_inventory, company_management, users


@asynccontextmanager
async def lifespan(application: FastAPI):
    initialize_database(application.state.database_engine)
    yield


app = FastAPI(title="WareTrack API", version="1.0.0", description="WareTrack noliktavas vadÄ«bas REST API", lifespan=lifespan)
app.state.database_engine = engine
origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

app.include_router(auth.router, prefix="/api")
app.include_router(company_management.router, prefix="/api")
app.include_router(company_management.admin_router, prefix="/api")
app.include_router(company_inventory.router, prefix="/api")
app.include_router(company_inventory.legacy, prefix="/api")
app.include_router(users.router, prefix="/api")


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    errors = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": "IevadÄ«tie dati nav derÄ«gi", "errors": errors})


@app.get("/api/health")
def health():
    return {"status": "ok"}

