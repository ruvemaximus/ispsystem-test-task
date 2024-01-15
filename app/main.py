from pathlib import Path

from fastapi import FastAPI

from . import archive
from . import config

app = FastAPI()

app.include_router(archive.router, prefix='/archive')


@app.on_event('startup')
def on_startup():
    Path.mkdir(config.DOWNLOADS_DIR, exist_ok=True)
