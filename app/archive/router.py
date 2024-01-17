import os
import shutil
import tarfile
from typing import Annotated

import aiofiles
import httpx
from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
    UploadFile,
    Form,
    File,
    Depends,
)

from .archive_manager import ArchiveManager
from .providers import DictProvider

# from .providers import MongoDBProvider
from .schemas import ArchiveOut, ArchiveInfo, ArchiveStatus
from ..auth.router import get_current_user, User
from ..config import DOWNLOADS_DIR

router = APIRouter()
archives = {}

# archive_manager_provider = MongoDBProvider("mongodb://root:example@localhost:27017/")
archive_manager_provider = DictProvider()
archive_manager = ArchiveManager(archive_manager_provider)


def remove_archive_from_disk(_id: str):
    try:
        shutil.rmtree(DOWNLOADS_DIR / _id)
        os.remove(DOWNLOADS_DIR / f"{_id}.tar.gz")
    except FileNotFoundError:
        pass


async def unpack(_id: str):
    await archive_manager.update(_id, {"status": ArchiveStatus.UNPACKING})

    destination_folder = DOWNLOADS_DIR / _id
    files = []
    try:
        with tarfile.open(DOWNLOADS_DIR / f"{_id}.tar.gz") as tar_gz_archive:
            members = tar_gz_archive.getmembers()
            for member in members:
                files.append(member.name)
                archives[_id]["progress"] += member.size
                tar_gz_archive.extract(member, destination_folder)
    except tarfile.ReadError:
        await archive_manager.update(
            _id,
            {
                "status": ArchiveStatus.FAILED,
                "detail": "File is not .tar.gz archive!",
            },
        )
        remove_archive_from_disk(_id)
        return

    await archive_manager.update(
        _id, {"status": ArchiveStatus.COMPLETED, "files": files}
    )
    archives.pop(_id)


async def download(url: str, _id: str):
    async with httpx.AsyncClient() as ac:
        try:
            async with ac.stream("GET", url=url) as response:
                archives[_id] = {"progress": 0}
                await archive_manager.update(
                    _id,
                    {
                        "size": int(response.headers.get("content-length")),
                        "status": ArchiveStatus.DOWNLOADING,
                    },
                )

                async with aiofiles.open(
                    DOWNLOADS_DIR / f"{_id}.tar.gz", "wb"
                ) as archive_file:
                    async for chunk in response.aiter_bytes():
                        archives[_id]["progress"] += len(chunk)
                        await archive_file.write(chunk)
        except httpx.ConnectError as e:
            await archive_manager.update(
                _id,
                {
                    "status": ArchiveStatus.FAILED,
                    "detail": f"Failed to connect {url}: {e}!",
                },
            )
            return
        except httpx.ConnectTimeout:
            await archive_manager.update(
                _id,
                {
                    "status": ArchiveStatus.FAILED,
                    "detail": f"Connection to {url} timed out!",
                },
            )
            return

    await unpack(_id)


@router.post("", response_model=ArchiveOut)
async def download_archive(
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    url: Annotated[str, Form()] = None,
    archive: Annotated[UploadFile, File(...)] = None,
):
    if url is None and archive is None:
        raise HTTPException(400, "Url OR archive file is required!")

    if url:
        _id = await archive_manager.create(url=url, author=current_user.model_dump())

        background_tasks.add_task(download, url, _id)

        return ArchiveOut(id=_id)

    if archive:
        _id = await archive_manager.create(author=current_user.model_dump())

        file_path = DOWNLOADS_DIR / f"{_id}.tar.gz"

        archives[_id] = {"progress": 0}
        await archive_manager.update(
            _id,
            {
                "size": int(archive.size),
                "status": ArchiveStatus.DOWNLOADING,
            },
        )

        async with aiofiles.open(file_path, "wb") as buffer:
            while chunk := await archive.read(1024):
                await buffer.write(chunk)

        await unpack(_id)

        return ArchiveOut(id=_id)


@router.get("/{_id}/", response_model=ArchiveInfo, response_model_exclude_none=True)
async def get_archive_info(_id: str, _: Annotated[User, Depends(get_current_user)]):
    if (archive := await archive_manager.get(_id=_id)) is None:
        raise HTTPException(status_code=404, detail=f"Archive {_id} not found!")

    return ArchiveInfo(
        status=archive["status"],
        author=archive["author"],
        files=archive.get("files"),
        progress=int(archives[_id]["progress"] * 100 / archive["size"])
        if archives.get(_id)
        else None,
        detail=archive.get("detail"),
    )


@router.delete("/{_id}/")
async def delete_archive(
    _id: str,
    background_tasks: BackgroundTasks,
    _: Annotated[User, Depends(get_current_user)],
):
    if archives.get(_id):
        archives.pop(_id)

    await archive_manager.remove(_id=_id)
    background_tasks.add_task(remove_archive_from_disk, _id)

    return {"ok": True, "message": f"Archive {_id} successfully removed!"}
