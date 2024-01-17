import motor.motor_asyncio
from bson import ObjectId

from .base import BaseProvider
from ...auth.schemas import User


class MongoDBProvider(BaseProvider):
    def __init__(self, url: str):
        self.__client = motor.motor_asyncio.AsyncIOMotorClient(url)
        self.__collection = self.__client.ispsystem_task.get_collection("archives")

    async def create(self, author: User, url: str | None = None) -> str:
        new_archive = await self.__collection.insert_one({"url": url, "author": author})

        _id = str(new_archive.inserted_id)
        return _id

    async def remove(self, _id: str):
        await self.__collection.delete_one({"_id": ObjectId(_id)})

    async def update(self, _id: str, data: dict):
        await self.__collection.find_one_and_update(
            {"_id": ObjectId(_id)}, {"$set": data}
        )

    async def get(self, _id: str):
        return await self.__collection.find_one({"_id": ObjectId(_id)})
