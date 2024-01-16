import os
import shutil
import tarfile

import httpx
import motor.motor_asyncio
from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, HTTPException

from .schemas import ArchiveIn, ArchiveOut, ArchiveInfo, ArchiveStatus
from ..config import DOWNLOADS_DIR

router = APIRouter()
archives = {}

client = motor.motor_asyncio.AsyncIOMotorClient('mongodb://root:example@localhost:27017/')
db = client.ispsystem_task
archives_collection = db.get_collection('archives')


def get_file_list(_id: str):
    file_list = []
    unpacked_archive = str(DOWNLOADS_DIR / _id)
    for root, _, files in os.walk(unpacked_archive):
        for file in files:
            root = root.replace(unpacked_archive, '').replace('/', '', 1)
            file_list.append(os.path.join(root, file))
    return file_list


async def unpack(_id: str):
    await archives_collection.find_one_and_update(
        {'_id': ObjectId(_id)},
        {'$set': {'status': ArchiveStatus.UNPACKING}}
    )

    destination_folder = DOWNLOADS_DIR / _id
    with tarfile.open(DOWNLOADS_DIR / f'{_id}.tar.gz') as tar_gz_archive:
        tar_gz_archive.extractall(destination_folder)

    await archives_collection.find_one_and_update(
        {'_id': ObjectId(_id)},
        {'$set': {'files': get_file_list(_id), 'status': ArchiveStatus.COMPLETED}}
    )

    shutil.rmtree(destination_folder)
    os.remove(DOWNLOADS_DIR / f'{_id}.tar.gz')


async def download(url, _id):
    async with httpx.AsyncClient() as ac:
        async with ac.stream('GET', url=url) as response:
            await archives_collection.find_one_and_update(
                {'_id': ObjectId(_id)},
                {
                    '$set':
                        {
                            'size': int(response.headers.get('content-length')),
                            'status': ArchiveStatus.DOWNLOADING
                        }
                }
            )

            with open(DOWNLOADS_DIR / f'{_id}.tar.gz', 'wb') as archive_file:
                async for chunk in response.aiter_bytes():
                    archives[_id]['downloaded'] += len(chunk)
                    archive_file.write(chunk)

    archives.pop(_id)
    await unpack(_id)


@router.post('', response_model=ArchiveOut)
async def download_archive(archive: ArchiveIn, background_tasks: BackgroundTasks):
    new_archive = await archives_collection.insert_one({
        'url': str(archive.url),
    })

    _id = str(new_archive.inserted_id)

    archives[_id] = {'downloaded': 0}
    background_tasks.add_task(download, str(archive.url), _id)
    return ArchiveOut(
        id=_id
    )


@router.get('/{id}/', response_model=ArchiveInfo)
async def get_archive_info(_id: str):
    if (
            archive := await archives_collection.find_one({'_id': ObjectId(_id)})
    ) is None:
        raise HTTPException(status_code=404, detail=f'Archive {_id} not found!')

    return ArchiveInfo(
        status=archive['status'],
        files=archive.get('files'),
        progress=int(archives[_id]['downloaded'] * 100 / archive['size']) if archives.get(_id) else None
    ).model_dump(exclude_none=True)


@router.delete('/{id}/')
async def delete_archive(_id: str):
    if archives.get(_id):
        archives.pop(_id)
    await archives_collection.delete_one({'_id': ObjectId(_id)})
    return {
        'ok': True,
        'message': f'Archive {_id} successfully removed!'
    }
