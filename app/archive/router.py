import os
import shutil
import tarfile

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException

from .archive_manager import ArchiveManager
from .providers import DictProvider

# from .providers import MongoDBProvider
from .schemas import ArchiveIn, ArchiveOut, ArchiveInfo, ArchiveStatus
from ..config import DOWNLOADS_DIR

router = APIRouter()
archives = {}

archive_manager_provider = DictProvider()
archive_manager = ArchiveManager(archive_manager_provider)


def get_file_list(_id: str):
    file_list = []
    unpacked_archive = str(DOWNLOADS_DIR / _id)
    for root, _, files in os.walk(unpacked_archive):
        for file in files:
            root = root.replace(unpacked_archive, "").replace("/", "", 1)
            file_list.append(os.path.join(root, file))
    return file_list


async def unpack(_id: str):
    await archive_manager.update(_id, {"status": ArchiveStatus.UNPACKING})

    destination_folder = DOWNLOADS_DIR / _id
    try:
        with tarfile.open(DOWNLOADS_DIR / f"{_id}.tar.gz") as tar_gz_archive:
            tar_gz_archive.extractall(destination_folder)
    except tarfile.ReadError:
        await archive_manager.update(
            _id,
            {
                "status": ArchiveStatus.FAILED,
                "detail": "File is not .tar.gz archive!",
            },
        )
        os.remove(DOWNLOADS_DIR / f"{_id}.tar.gz")
        return

    await archive_manager.update(
        _id, {"status": ArchiveStatus.COMPLETED, "files": get_file_list(_id)}
    )

    shutil.rmtree(destination_folder)
    os.remove(DOWNLOADS_DIR / f"{_id}.tar.gz")


async def download(url: str, _id: str):
    async with httpx.AsyncClient() as ac:
        try:
            async with ac.stream("GET", url=url) as response:
                archives[_id] = {"downloaded": 0}
                await archive_manager.update(
                    _id,
                    {
                        "size": int(response.headers.get("content-length")),
                        "status": ArchiveStatus.DOWNLOADING,
                    },
                )

                with open(DOWNLOADS_DIR / f"{_id}.tar.gz", "wb") as archive_file:
                    async for chunk in response.aiter_bytes():
                        archives[_id]["downloaded"] += len(chunk)
                        archive_file.write(chunk)
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

    archives.pop(_id)
    await unpack(_id)


@router.post("", response_model=ArchiveOut)
async def download_archive_by_url(
    archive: ArchiveIn, background_tasks: BackgroundTasks
):
    _id = await archive_manager.create(str(archive.url))

    background_tasks.add_task(download, str(archive.url), _id)
    return ArchiveOut(id=_id)


@router.get("/{_id}/", response_model=ArchiveInfo, response_model_exclude_none=True)
async def get_archive_info(_id: str):
    if (archive := await archive_manager.get(_id=_id)) is None:
        raise HTTPException(status_code=404, detail=f"Archive {_id} not found!")

    return ArchiveInfo(
        status=archive["status"],
        files=archive.get("files"),
        progress=int(archives[_id]["downloaded"] * 100 / archive["size"])
        if archives.get(_id)
        else None,
        detail=archive.get("detail"),
    )


@router.delete("/{_id}/")
async def delete_archive(_id: str):
    if archives.get(_id):
        archives.pop(_id)

    await archive_manager.remove(_id=_id)

    return {"ok": True, "message": f"Archive {_id} successfully removed!"}
