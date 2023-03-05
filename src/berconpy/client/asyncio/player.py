from typing import TYPE_CHECKING

from ..player import Player as BasePlayer

if TYPE_CHECKING:
    from .cache import AsyncRCONClientCache
    from .client import AsyncRCONClient


class Player(BasePlayer):
    """Represents a player in the server."""

    @property
    def cache(self) -> "AsyncRCONClientCache":
        """The cache that created this object."""
        return self._cache

    @property
    def client(self) -> "AsyncRCONClient":
        """Returns the client associated with the cache."""
        return self.cache.client

    async def ban_guid(self, duration: int | None = None, reason: str = "") -> str:
        """Bans the player from the server using their GUID."""
        # NOTE: ban #ID does the same as adding the player's GUID
        return await self.client.ban(self.guid, duration, reason)

    async def ban_ip(self, duration: int | None = None, reason: str = "") -> str:
        """Bans the player from the server using their IP."""
        ip = self.addr.split(":")[0]
        return await self.client.ban(ip, duration, reason)

    def is_connected(self) -> bool:
        """Checks if the player is still in the client's cache."""
        return self.id in self.client.cache._players

    async def kick(self, reason: str = "") -> str:
        """Kicks the player from the server.

        :param reason: An optional reason to display when kicking the player.

        """
        return await self.client.kick(self.id, reason)

    async def send(self, message: str) -> str:
        """Sends a message to the player.

        :param message: The string to use as the message.

        """
        return await self.client.whisper(self.id, message)
