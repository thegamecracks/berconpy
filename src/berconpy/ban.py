from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from . import utils

if TYPE_CHECKING:
    from .client import AsyncRCONClient


@dataclass(repr=False, slots=True, unsafe_hash=True)
class Ban:
    """Represents a GUID/IP ban on the server."""

    client: "AsyncRCONClient" = field(compare=True, hash=True)
    """The client that created this object."""

    index: int                = field(compare=True, hash=True)
    """
    The index assigned to this ban by the server.

    This is non-unique and is subject to change, so it cannot
    be reliably used for unbanning.
    """

    id: str                   = field(compare=False, hash=False)
    """
    The player identifier this ban affects.

    This can be either a BattlEye GUID or an IP address.
    """

    duration: int | None      = field(compare=False, hash=False)
    """
    The duration of the ban in minutes.

    If the ban has expired, this will be ``-1``.
    If the ban is permanent, this will be ``None``.
    """

    reason: str               = field(compare=False, hash=False)
    """The reason given for the ban."""

    def __repr__(self):
        attrs = (
            (k, repr(getattr(self, k)))
            for k in ('id', 'duration', 'reason')
        )
        return '<{} {}>'.format(
            type(self).__name__,
            ' '.join('='.join(pair) for pair in attrs)
        )

    def __str__(self):
        return self.name

    async def unban(self):
        """Removes this ban from the server."""
        # Since ban indices are non-unique, we need to match the identifier
        # and remove the corresponding index (possible race condition)
        bans = await self.client.fetch_bans()
        b = utils.get(bans, id=self.id)
        if b is not None:
            await self.client.unban(b.index)
