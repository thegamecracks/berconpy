from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from berconpy import AsyncClientConnector, ConnectorConfig
from berconpy.io import AsyncCommander
from berconpy.protocol.client import RCONClientProtocol

if TYPE_CHECKING:
    from .client import ArmaClient


@dataclass
class ArmaConnectorConfig(ConnectorConfig):
    players_interval: float = 60.0
    """
    The amount of time in seconds from the last keep alive command
    before it should be replaced with a "players" RCON command to
    update the client's cache.

    When set to a value less than :py:attr:`keep_alive_interval`,
    keep alive will always be used to update the cache.
    """


class ArmaConnector(AsyncClientConnector):
    """A connector subclass whose keep alive handler has been overridden
    to periodically refresh the player cache.
    """

    client: ArmaClient | None
    config: ArmaConnectorConfig
    _last_players: float

    def __init__(
        self,
        *,
        commander: AsyncCommander | None = None,
        config: ArmaConnectorConfig | None = None,  # FIXME: LSP violation
        protocol: RCONClientProtocol | None = None,
    ):
        if config is None:
            config = ArmaConnectorConfig()

        super().__init__(commander=commander, config=config, protocol=protocol)

    async def _send_keep_alive(self) -> None:
        assert self.client is not None

        if time.monotonic() - self._last_players > self.config.players_interval:
            # Instead of an empty message, ask for players so we can
            # periodically update the client's cache
            self._last_players = time.monotonic()
            response = await self.send_command("players")
            self.client.cache.update_players(response)
        else:
            await self.send_command("")
