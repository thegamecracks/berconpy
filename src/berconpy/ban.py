from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from . import utils

if TYPE_CHECKING:
    from .client import AsyncRCONClient


@dataclass(repr=False, slots=True, unsafe_hash=True)
class Ban:
    """Represents a GUID/IP ban on the server.

    Attributes
    ----------
    client: The client that created this object.
    index: The index assigned to this ban by the server.
           This is non-unique and is subject to change,
           so it cannot be reliably used for unbanning.
    id: The player identifier this ban affects, which is
        either a BattlEye GUID or an IP address.
    duration: The duration of the ban in minutes.
        This is -1 if expired or None for permanent bans.
    reason: The reason given for the ban.

    """
    client: "AsyncRCONClient" = field(compare=True, hash=True)
    index: int                = field(compare=True, hash=True)
    id: str                   = field(compare=False, hash=False)
    duration: int | None      = field(compare=False, hash=False)
    reason: str               = field(compare=False, hash=False)

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
