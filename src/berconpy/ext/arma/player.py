from typing import TYPE_CHECKING
import weakref

if TYPE_CHECKING:
    from .cache import ArmaCache
    from .client import ArmaClient


class Player:
    """Represents a player in the server."""

    __slots__ = (
        "_cache",
        "id",
        "name",
        "guid",
        "addr",
        "ping",
        "is_guid_valid",
        "in_lobby",
    )

    id: int
    """The ID assigned to this player by the server."""

    name: str
    """The player's name."""

    guid: str
    """
    The player's GUID. This may be an empty string if the client
    has not yet received the GUID from the server.
    """

    addr: str
    """The IP address and port this player connected from."""

    ping: int | None
    """The player's ping on the server.

    This data may not be available or may be out-of-date since it is
    only provided when the :py:meth:`ArmaClient.fetch_players()` is called.

    """

    is_guid_valid: bool
    """Whether the server has confirmed the validity of this player's GUID."""

    in_lobby: bool
    """
    Whether the player is in the server lobby or not.

    This data is only accurate after calling the :py:meth:`ArmaClient.fetch_players()`
    method since it cannot be determined during connection.

    """

    def __init__(
        self,
        cache: "ArmaCache",
        id: int,
        name: str,
        guid: str,
        addr: str,
        ping: int | None,
        is_guid_valid: bool,
        in_lobby: bool,
    ):
        self._cache = weakref.proxy(cache)
        self._update(id, name, guid, addr, ping, is_guid_valid, in_lobby)

    def _update(
        self,
        id: int,
        name: str,
        guid: str,
        addr: str,
        ping: int | None,
        is_guid_valid: bool,
        in_lobby: bool,
    ):
        self.id = id
        self.name = name
        self.guid = guid
        self.addr = addr
        self.ping = ping
        self.is_guid_valid = is_guid_valid
        self.in_lobby = in_lobby

    def __repr__(self):
        return "<{} id={!r} name={!r} is_guid_valid={!r} in_lobby={!r}>".format(
            type(self).__name__,
            self.id,
            self.name,
            self.is_guid_valid,
            self.in_lobby,
        )

    def __str__(self):
        return self.name

    @property
    def ip(self) -> str:
        """Returns the IP address of the player.

        This property is derived from :py:attr:`addr`.

        """
        return self.addr.split(":")[0]

    @property
    def cache(self) -> "ArmaCache":
        """The cache that created this object."""
        return self._cache

    @property
    def client(self) -> "ArmaClient | None":
        """Returns the client associated with the cache."""
        return self.cache.client

    async def ban_guid(self, duration: int | None = None, reason: str = "") -> str:
        """Bans the player from the server using their GUID.

        :param duration:
            How long the player should be banned.
            Can be ``None`` to indicate a permanent ban.
        :param reason:
            The reason to display when the player is banned.
        :returns: The response from the server, if any.

        """
        assert self.client is not None
        # NOTE: ban #ID does the same as adding the player's GUID
        return await self.client.ban(self.guid, duration, reason)

    async def ban_ip(self, duration: int | None = None, reason: str = "") -> str:
        """Bans the player from the server using their IP.

        :param duration:
            How long the player should be banned.
            Can be ``None`` to indicate a permanent ban.
        :param reason:
            The reason to display when the player is banned.
        :returns: The response from the server, if any.

        """
        assert self.client is not None
        ip = self.addr.split(":")[0]
        return await self.client.ban(ip, duration, reason)

    def is_connected(self) -> bool:
        """Checks if the player is still in the client's cache."""
        assert self.client is not None
        return self.id in self.client.cache._players

    async def kick(self, reason: str = "") -> str:
        """Kicks the player from the server.

        :param reason: The reason to display when kicking the player.
        :returns: The response from the server, if any.

        """
        assert self.client is not None
        return await self.client.kick(self.id, reason)

    async def send(self, message: str) -> str:
        """Sends a message to the player.

        :param message: The string to use as the message.
        :returns: The response from the server, if any.

        """
        assert self.client is not None
        return await self.client.whisper(self.id, message)
