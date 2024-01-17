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
    concurrency,
)

from .archive_manager import ArchiveManager
from .providers import DictProvider

# from .providers import MongoDBProvider
from .schemas import ArchiveOut, ArchiveInfo, ArchiveStatus
from ..auth.router import get_current_user, User
from ..config import DOWNLOADS_DIR

router = APIRouter()
archives = {}

# archive_manager_provider = MongoDBProvider("mongodb://root:example@mongo:27017/")
archive_manager_provider = DictProvider()
archive_manager = ArchiveManager(archive_manager_provider)


def remove_archive_from_disk(_id: str):
    try:
        os.remove(DOWNLOADS_DIR / f"{_id}.tar.gz")
        shutil.rmtree(DOWNLOADS_DIR / _id)
    except FileNotFoundError:
        pass


def _extract_tar_process(_id: str, archive: dict):
    destination_folder = DOWNLOADS_DIR / _id
    files = []

    with tarfile.open(DOWNLOADS_DIR / f"{_id}.tar.gz") as tar:
        archive.update(
            progress=0,
            not_compressed_size=sum([member.size for member in tar.getmembers()]),
        )

        members = tar.getmembers()

        for member in members:
            files.append(member.name)
            archive["progress"] += member.size
            tar.extract(member, destination_folder)
    return files


async def unpack(_id: str):
    try:
        await archive_manager.update(_id, {"status": ArchiveStatus.UNPACKING})
        files = await concurrency.run_in_threadpool(
            _extract_tar_process, _id, archives[_id]
        )
        await archive_manager.update(
            _id, {"status": ArchiveStatus.COMPLETED, "files": files}
        )

    except tarfile.ReadError:
        await archive_manager.update(
            _id,
            {
                "status": ArchiveStatus.FAILED,
                "detail": "File is not .tar.gz archive!",
            },
        )
        await concurrency.run_in_threadpool(remove_archive_from_disk, _id)

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
        background_tasks.add_task(unpack, _id)
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

        background_tasks.add_task(unpack, _id)
        return ArchiveOut(id=_id)


@router.get("/{_id}/", response_model=ArchiveInfo, response_model_exclude_none=True)
async def get_archive_info(_id: str, _: Annotated[User, Depends(get_current_user)]):
    if (archive := await archive_manager.get(_id=_id)) is None:
        raise HTTPException(status_code=404, detail=f"Archive {_id} not found!")

    match archive["status"]:
        case ArchiveStatus.DOWNLOADING.value:
            progress = int(archives[_id]["progress"] * 100 / archive["size"])
        case ArchiveStatus.UNPACKING.value:
            try:
                progress = int(
                    archives[_id]["progress"]
                    * 100
                    / archives[_id]["not_compressed_size"]
                )
            except KeyError:
                progress = 0
        case _:
            progress = None

    return ArchiveInfo(
        status=archive["status"],
        author=archive["author"],
        files=archive.get("files"),
        detail=archive.get("detail"),
        progress=progress,
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
