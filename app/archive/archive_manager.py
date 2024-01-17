from .providers.base import BaseProvider
from .providers.dict import DictProvider


class ArchiveManager:
    def __init__(
        self,
        __provider: BaseProvider = DictProvider(),
    ):
        self.__provider = __provider

    def __getattr__(self, item):
        return getattr(self.__provider, item)
