from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import archive, auth
from . import config


@asynccontextmanager
async def lifespan(_app: FastAPI):
    config.DOWNLOADS_DIR.mkdir(exist_ok=True)
    yield


app = FastAPI(title="ISPsystem Test Task", lifespan=lifespan)

app.include_router(archive.router, prefix="/archive")
app.include_router(auth.router, prefix="/auth")
