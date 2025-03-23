from __future__ import annotations

import asyncio
import logging
import weakref
from typing import TYPE_CHECKING

from berconpy.errors import RCONCommandError

from .parser import (
    ParsedPlayer,
    PlayerConnect,
    PlayerGUID,
    PlayerVerifyGUID,
    parse_players,
)
from .player import Player

if TYPE_CHECKING:
    from .client import ArmaClient

log = logging.getLogger(__name__)


class ArmaCache:
    """A basic cache implementation for :py:class:`ArmaClient`.

    When a :py:attr:`client` is set, this will add an ``on_login`` listener
    which queries the :py:attr:`admin_id` and fetches the current player list
    to quickly update itself.

    """

    _client: ArmaClient | None = None
    _admin_id: int | None = None
    _players: dict[int, Player]
    _incomplete_players: dict[int, Player]

    def __init__(self) -> None:
        self._setup_cache()

    def _setup_cache(self) -> None:
        self._players = {}
        self._incomplete_players = {}
        self.admin_id = None

    @property
    def client(self) -> ArmaClient | None:
        """The client this cache is assigned to."""
        return self._client

    @client.setter
    def client(self, new_client: ArmaClient | None) -> None:
        old_client = self.client
        if new_client is not None:
            new_client.dispatch.on_login(self.on_login)
            if old_client is not None:
                old_client.dispatch.on_login.remove(self.on_login)

        if new_client is not None:
            new_client = weakref.proxy(new_client)
        self._client = new_client

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
    def players(self) -> list[Player]:
        """A list of players in the server."""
        return list(self._players.values())

    def get_player(self, player_id: int) -> Player | None:
        """Looks up a player from cache using their server-given ID.

        :param player_id: The ID of the player.
        :returns: The retrieved player or ``None`` if not found.

        """
        return self._players.get(player_id)

    # Cache maintenance

    async def on_login(self):
        assert self.client is not None
        self._setup_cache()

        try:
            admin_id, addr = await self.client.wait_for("admin_login", timeout=10)
        except asyncio.TimeoutError:
            log.warning(
                "did not receive admin_login event within 10 seconds; "
                "client id will not be available"
            )
        else:
            self.admin_id = admin_id

            if len(self._players) > 0:
                # The user had already fetched players before us
                return

            try:
                await self.client.fetch_players()
            except RCONCommandError:
                log.warning(
                    "failed to receive players from server; "
                    "player cache will not be available"
                )

    def _get_pending_player(self, player_id: int) -> Player | None:
        return self._incomplete_players.get(player_id) or self._players.get(player_id)

    def _push_to_cache(self, player_id: int):
        # We have a potential race condition where fetch_players() /
        # keep alive may occur just before player is added to cache;
        # in that case we can throw away the pending player
        p = self._incomplete_players.pop(player_id, None)
        if p is None or player_id in self._players:
            return

        self._players[player_id] = p

    async def _delayed_push_to_cache(self, player_id: int):
        # Give 5 seconds for events to come in before adding to self._players
        await asyncio.sleep(5)
        self._push_to_cache(player_id)

    def add_connected_player(self, payload: PlayerConnect) -> Player:
        """Adds a player to the cache after having connected.

        :returns: The player that was created.

        """
        # first message; start timer to cache
        p = Player(
            cache=self,
            id=payload.id,
            name=payload.name,
            guid="",
            addr=payload.addr,
            ping=None,
            in_lobby=False,
            is_guid_valid=False,
        )
        self._incomplete_players[payload.id] = p

        asyncio.create_task(
            self._delayed_push_to_cache(payload.id),
            name=f"berconpy-push-to-cache-{payload.id}",
        )

        return p

    def set_player_guid(self, payload: PlayerGUID) -> Player | None:
        """Sets the GUID of a cached player.

        :returns: The player that was updated, if any.

        """
        # second message
        p = self._get_pending_player(payload.id)
        if p is not None:
            p.guid = payload.guid
        return p

    def verify_player_guid(self, payload: PlayerVerifyGUID) -> Player | None:
        """Verifies the GUID of a cached player.

        :returns: The player that was updated, if any.

        """
        # last message, can push to cache early
        p = self._get_pending_player(payload.id)
        if p is not None:
            p.is_guid_valid = True
            self._push_to_cache(payload.id)
        return p

    def remove_player(self, player_id: int) -> Player | None:
        """Invalidates a player in the cache.

        :returns: The player that was removed, if any.

        """
        p = self._players.pop(player_id, None)
        p = p or self._incomplete_players.pop(player_id, None)
        return p

    def add_missing_player(self, payload: ParsedPlayer) -> Player:
        """Adds a player that was missing from the cache.

        :returns: The player that was created.

        """
        player = Player(self, **payload)
        self._players[player.id] = player
        return player

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
