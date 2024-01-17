from abc import ABC, abstractmethod

from app.auth.schemas import User


class BaseProvider(ABC):
    @classmethod
    @abstractmethod
    def create(cls, author: User, url: str | None = None):
        ...

    @classmethod
    @abstractmethod
    def remove(cls, _id: str):
        ...

    @classmethod
    @abstractmethod
    def update(cls, _id: str, data: dict):
        ...

    @classmethod
    @abstractmethod
    def get(cls, _id: str):
        ...
