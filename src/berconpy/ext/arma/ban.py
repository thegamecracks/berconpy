from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import AsyncArmaRCONClient


@dataclass(repr=False, slots=True, unsafe_hash=True)
class Ban:
    """Represents a GUID/IP ban on the server.

    Attributes
    ----------
    client: The client that created this object.
    id: The ID assigned to this ban by the server.
        Note that this is not the same as a player ID.
    addr: The player identifier this ban affects,
        either a BattlEye GUID or an IP address.
    duration: The duration of the ban in minutes.
        This is -1 if expired or None for permanent bans.
    reason: The reason given for the ban.

    """
    client: "AsyncArmaRCONClient" = field(compare=True, hash=True)
    id: int                       = field(compare=True, hash=True)
    addr: str                     = field(compare=False, hash=False)
    duration: int | None          = field(compare=False, hash=False)
    reason: str                   = field(compare=False, hash=False)

    def __repr__(self):
        attrs = (
            (k, repr(getattr(self, k)))
            for k in ('client', 'id', 'duration', 'reason')
        )
        return '<{} {}>'.format(
            type(self).__name__,
            ' '.join('='.join(pair) for pair in attrs)
        )

    def __str__(self):
        return self.name

    async def unban(self):
        """Removes this ban from the server."""
        await self.client.unban(self.id)
