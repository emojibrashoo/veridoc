from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pymongo.errors import PyMongoError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import Base, SessionLocal, engine
from app import models
from app.mongo import close_mongo, connect_mongo, ping_mongo
from app.routers.auth import router as auth_router
from app.routers.verify import router as verify_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(bind=engine)
    connect_mongo()
    try:
        yield
    finally:
        close_mongo()
        engine.dispose()


app = FastAPI(title="VeriDoc AI API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(verify_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    checks: dict[str, str] = {}
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except SQLAlchemyError as exc:
        checks["postgres"] = "unavailable"
        postgres_error = str(exc)
    else:
        postgres_error = ""

    try:
        ping_mongo()
        checks["mongodb"] = "ok"
    except PyMongoError as exc:
        checks["mongodb"] = "unavailable"
        mongo_error = str(exc)
    else:
        mongo_error = ""

    if any(value != "ok" for value in checks.values()):
        detail: dict[str, object] = {"status": "unhealthy", "checks": checks}
        if postgres_error:
            detail["postgres_error"] = postgres_error
        if mongo_error:
            detail["mongodb_error"] = mongo_error
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
        )
    return {"status": "ok", **checks}
