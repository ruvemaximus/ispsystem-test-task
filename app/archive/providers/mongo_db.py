import motor.motor_asyncio
from bson import ObjectId
from .base import BaseProvider


class MongoDBProvider(BaseProvider):
    __client = motor.motor_asyncio.AsyncIOMotorClient(
        "mongodb://root:example@localhost:27017/"
    )
    __collection = __client.ispsystem_task.get_collection("archives")

    @classmethod
    async def create(cls, url: str) -> str:
        new_archive = await cls.__collection.insert_one(
            {
                "url": url,
            }
        )

        _id = str(new_archive.inserted_id)
        return _id

    @classmethod
    async def remove(cls, _id: str):
        await cls.__collection.delete_one({"_id": ObjectId(_id)})

    @classmethod
    async def update(cls, _id: str, data: dict):
        await cls.__collection.find_one_and_update(
            {"_id": ObjectId(_id)}, {"$set": data}
        )

    @classmethod
    async def get(cls, _id: str):
        return await cls.__collection.find_one({"_id": ObjectId(_id)})
