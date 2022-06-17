from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import AsyncRCONClient


@dataclass(repr=False, slots=True, unsafe_hash=True)
class Player:
    """Represents an Arma player in the server.

    Attributes
    ----------
    client: The client that created this object.
    id: The ID assigned to this player by the server.
    name: The player's name.
    guid:
        The player's GUID. This may be an empty string if the client
        has not yet received the GUID from the server.
    addr: The IP address and port this player connected from.
    is_guid_valid:
        Whether the server confirmed the validity of this player's GUID.
    in_lobby:
        Whether the player is in the server lobby or not.
        This data is only accurate after calling the client's
        `fetch_players()` method since it cannot be determined
        during connection.

    """
    client: "AsyncRCONClient" = field(compare=True, hash=True)
    id: int                   = field(compare=True, hash=True)
    name: str                 = field(compare=False, hash=False)
    guid: str                 = field(compare=False, hash=False)
    addr: str                 = field(compare=False, hash=False)
    is_guid_valid: bool       = field(compare=False, hash=False)
    in_lobby: bool            = field(compare=False, hash=False)

    def __repr__(self):
        attrs = (
            (k, repr(getattr(self, k)))
            for k in ('client', 'id', 'name', 'is_guid_valid', 'in_lobby')
        )
        return '<{} {}>'.format(
            type(self).__name__,
            ' '.join('='.join(pair) for pair in attrs)
        )

    def __str__(self):
        return self.name

    @property
    def ping(self) -> int:
        """Retrieves the player's ping on the server.

        This information is only updated after a `fetch_players()` call
        and defaults to -1 if it is never called. However, by default,
        the client automatically calls fetch_players() on login
        and then periodically during the connection's lifetime.

        """
        return self.client._player_pings.get(self.id, -1)

    async def ban_guid(self, duration: int = None, reason: str = ''):
        """Bans the player from the server using their GUID."""
        # NOTE: ban #ID does the same as adding the player's GUID
        await self.client.ban(self.guid, duration, reason)

    async def ban_ip(self, duration: int = None, reason: str = ''):
        """Bans this player from the server using their IP."""
        ip = self.addr.split(':')[0]
        await self.client.ban(ip, duration, reason)

    def is_connected(self) -> bool:
        """Checks if the player is still in the client's cache."""
        return self.id in self.client._players

    async def kick(self, reason: str = ''):
        """Kicks this player from the server with an optional reason."""
        await self.client.kick(self.id, reason)

    async def send(self, message: str):
        """Sends a message to the player."""
        await self.client.whisper(self.id, message)
