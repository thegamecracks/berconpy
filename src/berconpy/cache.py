from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
import weakref

from .events import (
    ParsedPlayer,
    PlayerConnect,
    PlayerGUID,
    PlayerVerifyGUID,
)

if TYPE_CHECKING:
    from .client import RCONClient
    from .player import Player


class RCONClientCache(ABC):
    """A standard interface for implementing caching."""

    client: RCONClient

    def __init__(self, client: RCONClient) -> None:
        self.client = weakref.proxy(client)

    # Public methods

    @property
    @abstractmethod
    def admin_id(self) -> int | None:
        """The RCON admin ID this client was given or None
        if the client has not logged in.
        """

    @admin_id.setter
    @abstractmethod
    def admin_id(self, val: int | None) -> None:
        ...

    @property
    @abstractmethod
    def players(self) -> list[Player]:
        """A list of players in the server."""

    @abstractmethod
    def get_player(self, player_id: int) -> Player | None:
        """Looks up a player from cache using their server-given ID.

        :param player_id: The ID of the player.
        :returns: The retrieved player or ``None`` if not found.

        """

    # Cache maintenance

    @abstractmethod
    def add_connected_player(self, payload: PlayerConnect) -> Player:
        """Adds a player to the cache after having connected.

        :returns: The player that was created.

        """

    @abstractmethod
    def set_player_guid(self, payload: PlayerGUID) -> Player | None:
        """Sets the GUID of a cached player.

        :returns: The player that was updated, if any.

        """

    @abstractmethod
    def verify_player_guid(self, payload: PlayerVerifyGUID) -> Player | None:
        """Verifies the GUID of a cached player.

        :returns: The player that was updated, if any.

        """

    @abstractmethod
    def remove_player(self, player_id: int) -> Player | None:
        """Invalidates a player in the cache.

        :returns: The player that was removed, if any.

        """

    @abstractmethod
    def add_missing_player(self, payload: ParsedPlayer) -> Player:
        """Adds a player that was missing from the cache.

        :returns: The player that was created.

        """
