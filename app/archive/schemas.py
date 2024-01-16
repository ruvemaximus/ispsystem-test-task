from enum import StrEnum

from pydantic import BaseModel, HttpUrl


class ArchiveIn(BaseModel):
    url: HttpUrl


class ArchiveOut(BaseModel):
    id: str


class ArchiveStatus(StrEnum):
    DOWNLOADING = 'downloading'
    UNPACKING = 'unpacking'
    COMPLETED = 'ok'


class ArchiveInfo(BaseModel):
    status: ArchiveStatus
    progress: int | None = None
    files: list[str] | None = None

