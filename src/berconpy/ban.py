from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Awaitable
import weakref

if TYPE_CHECKING:
    from .cache import RCONClientCache
    from .client import RCONClient


class Ban(ABC):
    """Represents a GUID/IP ban on the server."""

    __slots__ = (
        "_cache",
        "index",
        "id",
        "duration",
        "reason",
    )

    index: int
    """
    The index assigned to this ban by the server.

    This is non-unique and is subject to change, so it cannot
    be reliably used for unbanning.
    """

    id: str
    """
    The player identifier this ban affects.

    This can be either a BattlEye GUID or an IP address.
    """

    duration: int | None
    """
    The duration of the ban in minutes.

    If the ban has expired, this will be ``-1``.
    If the ban is permanent, this will be ``None``.
    """

    reason: str
    """The reason given for the ban."""

    def __init__(
        self,
        cache: "RCONClientCache",
        index: int,
        id: str,
        duration: int | None,
        reason: str,
    ) -> None:
        self._cache = weakref.proxy(cache)
        self.index = index
        self.id = id
        self.duration = duration
        self.reason = reason

    def __repr__(self):
        return "<{} id={!r} duration={!r} reason={!r}>".format(
            type(self).__name__,
            self.id,
            self.duration,
            self.reason,
        )

    @property
    def cache(self) -> "RCONClientCache":
        """The cache that created this object."""
        return self._cache

    @property
    def client(self) -> "RCONClient | None":
        """Returns the client associated with the cache."""
        return self.cache.client

    @abstractmethod
    def unban(self) -> str | Awaitable[str]:
        """Removes this ban from the server.

        :returns: The response from the server, if any.

        """
