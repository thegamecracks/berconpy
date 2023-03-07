from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Awaitable
import weakref

if TYPE_CHECKING:
    from .cache import RCONClientCache
    from .client import RCONClient


class Player(ABC):
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
    only provided when the :py:meth:`RCONClient.fetch_players()` is called.

    """

    is_guid_valid: bool
    """Whether the server has confirmed the validity of this player's GUID."""

    in_lobby: bool
    """
    Whether the player is in the server lobby or not.

    This data is only accurate after calling the :py:meth:`RCONClient.fetch_players()`
    method since it cannot be determined during connection.

    """

    def __init__(
        self,
        cache: "RCONClientCache",
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
    def cache(self) -> "RCONClientCache":
        """The cache that created this object."""
        return self._cache

    @property
    def client(self) -> "RCONClient | None":
        """Returns the client associated with the cache."""
        return self.cache.client

    @abstractmethod
    def ban_guid(
        self,
        duration: int | None = None,
        reason: str = "",
    ) -> str | Awaitable[str]:
        """Bans this player from the server using their GUID.

        :param duration:
            How long the player should be banned.
            Can be ``None`` to indicate a permanent ban.
        :param reason:
            The reason to display when the player is banned.
        :returns: The response from the server, if any.

        """
        # NOTE: ban #ID does the same as adding the player's GUID

    @abstractmethod
    def ban_ip(
        self,
        duration: int | None = None,
        reason: str = "",
    ) -> str | Awaitable[str]:
        """Bans this player from the server using their IP.

        :param duration:
            How long the player should be banned.
            Can be ``None`` to indicate a permanent ban.
        :param reason:
            The reason to display when the player is banned.
        :returns: The response from the server, if any.

        """

    @abstractmethod
    def is_connected(self) -> bool:
        """Checks if this player is still in the client's cache."""

    @abstractmethod
    def kick(self, reason: str = "") -> str | Awaitable[str]:
        """Kicks this player from the server.

        :param reason: The reason to display when kicking the player.
        :returns: The response from the server, if any.

        """

    @abstractmethod
    def send(self, message: str) -> str | Awaitable[str]:
        """Sends a message to this player.

        :param message: The string to use as the message.
        :returns: The response from the server, if any.

        """
