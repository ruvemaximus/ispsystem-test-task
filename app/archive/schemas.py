from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, HttpUrl


class ArchiveIn(BaseModel):
    url: HttpUrl


class ArchiveOut(BaseModel):
    uuid: UUID


class ArchiveStatuses(StrEnum):
    DOWNLOADING = 'downloading'
    UNPACKING = 'unpacking'
    COMPLETED = 'ok'


class ArchiveStatus(BaseModel):
    status: ArchiveStatuses
    progress: int
    files: list[str] | None = None

