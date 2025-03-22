import weakref
from typing import TYPE_CHECKING

from berconpy import utils

if TYPE_CHECKING:
    from .cache import ArmaCache
    from .client import ArmaClient


class Ban:
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
        cache: "ArmaCache",
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
    def cache(self) -> "ArmaCache":
        return super().cache  # type: ignore

    @property
    def client(self) -> "ArmaClient | None":
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
