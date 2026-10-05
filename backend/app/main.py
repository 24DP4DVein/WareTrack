import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database import Base, engine
from app.routers import auth, dashboard, items, master_data, transfers, users

Base.metadata.create_all(bind=engine)

app = FastAPI(title="WareTrack API", version="1.0.0", description="WareTrack noliktavas vadības REST API")
origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

app.include_router(auth.router, prefix="/api")
app.include_router(items.router, prefix="/api")
app.include_router(master_data.categories, prefix="/api")
app.include_router(master_data.suppliers, prefix="/api")
app.include_router(master_data.locations, prefix="/api")
app.include_router(transfers.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(users.router, prefix="/api")


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    errors = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": "Ievadītie dati nav derīgi", "errors": errors})


@app.get("/api/health")
def health():
    return {"status": "ok"}
