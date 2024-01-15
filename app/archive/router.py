import os
import shutil
import tarfile
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, BackgroundTasks

from app.config import DOWNLOADS_DIR
from .schemas import ArchiveIn, ArchiveOut, ArchiveStatuses, ArchiveStatus

router = APIRouter()
archives = {}


def get_file_list(destination_folder):
    file_list = []
    for root, _, files in os.walk(destination_folder):
        for file in files:
            root = root.replace(destination_folder, '').replace('/', '', 1)
            file_list.append(os.path.join(root, file))
    return file_list


def unpack(uuid: UUID):
    destination_folder = DOWNLOADS_DIR / str(uuid)
    with tarfile.open(DOWNLOADS_DIR / f'{uuid}.tar.gz') as tar_gz_archive:
        tar_gz_archive.extractall(destination_folder)

    archives[uuid]['status'] = ArchiveStatuses.COMPLETED
    archives[uuid]['files'] = get_file_list(str(destination_folder))

    shutil.rmtree(destination_folder)


async def download(url: str, uuid: UUID):
    async with httpx.AsyncClient() as client:
        async with client.stream('GET', url=url) as response:
            archives[uuid] = {
                'size': int(response.headers.get('content-length')),
                'status': ArchiveStatuses.DOWNLOADING,
                'progress': 0
            }
            with open(DOWNLOADS_DIR / f'{uuid}.tar.gz', 'wb') as archive_file:
                async for chunk in response.aiter_bytes():
                    archives[uuid]['progress'] += len(chunk)
                    archive_file.write(chunk)

    archives[uuid]['status'] = ArchiveStatuses.UNPACKING

    unpack(uuid)


@router.post('', response_model=ArchiveOut)
async def download_archive(archive: ArchiveIn, background_tasks: BackgroundTasks):
    archive_uuid = uuid4()
    background_tasks.add_task(download, str(archive.url), archive_uuid)
    return ArchiveOut(
        uuid=archive_uuid
    )


@router.get('/{uuid}/', response_model=ArchiveStatus)
async def get_archive_info(uuid: UUID):
    a = archives[uuid]
    return ArchiveStatus(
        status=a['status'],
        files=a.get('files'),
        progress=int((a['progress'] / a['size']) * 100)
    )


@router.delete('/{uuid}/')
async def delete_archive(uuid: UUID):
    os.remove(DOWNLOADS_DIR / f'{uuid}.tar.gz')
    archives.pop(uuid)
    return {
        'ok': True,
        'message': f'Archive {uuid} successfully removed!'
    }
