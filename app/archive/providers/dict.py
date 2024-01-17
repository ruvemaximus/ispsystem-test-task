from uuid import uuid4

from .base import BaseProvider


class DictProvider(BaseProvider):
    __data = {}

    @classmethod
    async def create(cls, url: str | None = None) -> str:
        _id = str(uuid4())
        cls.__data[_id] = {"url": url}
        return _id

    @classmethod
    async def remove(cls, _id: str):
        if cls.__data.get(_id):
            cls.__data.pop(_id)

    @classmethod
    async def update(cls, _id: str, data: dict):
        cls.__data[_id].update(data)

    @classmethod
    async def get(cls, _id: str):
        return cls.__data.get(_id)
