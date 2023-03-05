from typing import TYPE_CHECKING

from ..ban import Ban as BaseBan
from ... import utils

if TYPE_CHECKING:
    from .cache import AsyncRCONClientCache
    from .client import AsyncRCONClient


class Ban(BaseBan):
    @property
    def cache(self) -> "AsyncRCONClientCache":
        return self._cache

    @property
    def client(self) -> "AsyncRCONClient":
        return self.cache.client

    async def unban(self) -> str:
        # Since ban indices are non-unique, we need to match the identifier
        # and remove the corresponding index (possible race condition)
        bans = await self.client.fetch_bans()

        b = utils.get(bans, id=self.id)
        if b is None:
            return ""

        return await self.client.unban(b.index)
