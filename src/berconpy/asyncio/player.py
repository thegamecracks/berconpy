from typing import TYPE_CHECKING

from ..player import Player as BasePlayer

if TYPE_CHECKING:
    from .cache import AsyncRCONClientCache
    from .client import AsyncRCONClient


class Player(BasePlayer):
    """
    An asynchronous implemenation of the :py:class:`~berconpy.player.Player` class.
    """

    @property
    def cache(self) -> "AsyncRCONClientCache":
        """The cache that created this object."""
        return super().cache  # type: ignore

    @property
    def client(self) -> "AsyncRCONClient | None":
        """Returns the client associated with the cache."""
        return self.cache.client

    async def ban_guid(self, duration: int | None = None, reason: str = "") -> str:
        """Bans the player from the server using their GUID."""
        assert self.client is not None
        # NOTE: ban #ID does the same as adding the player's GUID
        return await self.client.ban(self.guid, duration, reason)

    async def ban_ip(self, duration: int | None = None, reason: str = "") -> str:
        """Bans the player from the server using their IP."""
        assert self.client is not None
        ip = self.addr.split(":")[0]
        return await self.client.ban(ip, duration, reason)

    def is_connected(self) -> bool:
        """Checks if the player is still in the client's cache."""
        assert self.client is not None
        return self.id in self.client.cache._players

    async def kick(self, reason: str = "") -> str:
        """Kicks the player from the server.

        :param reason: An optional reason to display when kicking the player.

        """
        assert self.client is not None
        return await self.client.kick(self.id, reason)

    async def send(self, message: str) -> str:
        """Sends a message to the player.

        :param message: The string to use as the message.

        """
        assert self.client is not None
        return await self.client.whisper(self.id, message)
