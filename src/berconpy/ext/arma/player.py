from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import AsyncArmaRCONClient


@dataclass(unsafe_hash=True, slots=True)
class Player:
    """Represents an Arma player in the server.

    Attributes
    ----------
    client: The client that created this player.
    id: The ID assigned to this player by the server.
    name: The player's name.
    guid:
        The player's GUID. It may be possible for this to be an empty
        string if the client does not receive that information from a packet.
    addr: The IP address and port this player connected from.
    is_guid_valid:
        Whether the server confirmed the validity of this player's GUID.
    in_lobby:
        Whether the player is in the server lobby or not.
        This data is only accurate after calling the client's
        `fetch_players()` method since it cannot be determined
        during connection.

    """
    client: "AsyncArmaRCONClient" = field(compare=True, repr=True, hash=True)
    id: int                       = field(compare=True, repr=True, hash=True)
    name: str                     = field(compare=False, repr=True, hash=False)
    guid: str                     = field(compare=False, repr=False, hash=False)
    addr: str                     = field(compare=False, repr=False, hash=False)
    is_guid_valid: bool           = field(compare=False, repr=True, hash=False)
    in_lobby: bool                = field(compare=False, repr=True, hash=False)

    @property
    def ping(self) -> int:
        """Retrieves the player's ping on the server.

        This information is only updated after a `fetch_players()` call
        and defaults to -1 if it is never called. However, by default,
        the client automatically calls fetch_players() on login
        and then periodically during the connection's lifetime.

        """
        return self.client._player_pings.get(self.id, -1)
