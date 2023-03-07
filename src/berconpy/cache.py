from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Sequence
import weakref

from .parser import (
    ParsedPlayer,
    PlayerConnect,
    PlayerGUID,
    PlayerVerifyGUID,
    parse_players,
)

if TYPE_CHECKING:
    from .client import RCONClient
    from .player import Player


class RCONClientCache(ABC):
    """The base class for implementing caching."""

    _client: RCONClient | None = None
    _admin_id: int | None = None

    @property
    def client(self) -> RCONClient | None:
        """The client this cache is assigned to."""
        return self._client

    @client.setter
    def client(self, new_client: RCONClient | None) -> None:
        if new_client is not None:
            new_client = weakref.proxy(new_client)
        self._client = new_client

    # Public methods

    @property
    def admin_id(self) -> int | None:
        """The RCON admin ID this client was given or None
        if the client has not logged in.
        """
        return self._admin_id

    @admin_id.setter
    def admin_id(self, new_id: int | None) -> None:
        self._admin_id = new_id

    @property
    @abstractmethod
    def players(self) -> Sequence[Player]:
        """A list of players in the server."""

    @abstractmethod
    def get_player(self, player_id: int) -> Player | None:
        """Looks up a player from cache using their server-given ID.

        :param player_id: The ID of the player.
        :returns: The retrieved player or ``None`` if not found.

        """

    # Cache maintenance (template methods)

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

    def update_players(self, response: str) -> None:
        """Updates the cache by parsing a response to the "players" command."""
        current_ids = set()
        for player in parse_players(response):
            p = self.get_player(player["id"])
            if p is None:
                self.add_missing_player(player)
            else:
                p._update(**player)

            current_ids.add(player["id"])

        # Throw away players no longer in the server
        previous_ids = set(p.id for p in self.players)
        for missing in previous_ids - current_ids:
            self.remove_player(missing)
