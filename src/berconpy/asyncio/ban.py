from typing import TYPE_CHECKING

from ..ban import Ban as BaseBan
from .. import utils

if TYPE_CHECKING:
    from .cache import AsyncRCONClientCache
    from .client import AsyncRCONClient


class Ban(BaseBan):
    """An asynchronous implemenation of the :py:class:`~berconpy.ban.Ban` class."""

    @property
    def cache(self) -> "AsyncRCONClientCache":
        return super().cache  # type: ignore

    @property
    def client(self) -> "AsyncRCONClient | None":
        return self.cache.client

    async def unban(self) -> str:
        assert self.client is not None

        # Since ban indices are non-unique, we need to match the identifier
        # and remove the corresponding index (possible race condition)
        bans = await self.client.fetch_bans()

        b = utils.get(bans, id=self.id)
        if b is None:
            return ""

        return await self.client.unban(b.index)
