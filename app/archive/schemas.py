from enum import StrEnum

from pydantic import BaseModel, HttpUrl

from app.auth.schemas import User


class ArchiveIn(BaseModel):
    url: HttpUrl


class ArchiveOut(BaseModel):
    id: str


class ArchiveStatus(StrEnum):
    DOWNLOADING = "downloading"
    UNPACKING = "unpacking"
    FAILED = "failed"
    COMPLETED = "ok"


class ArchiveInfo(BaseModel):
    status: ArchiveStatus
    author: User
    progress: int | None = None
    files: list[str] | None = None
    detail: str | None = None
