from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import create_db_and_tables
from app import models  # noqa: F401 — registers all SQLModel tables
from app.routers import auth, keys, texting


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(title="Moje API", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(texting.router)
app.include_router(keys.router)
