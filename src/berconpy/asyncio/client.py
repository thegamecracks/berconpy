import contextlib
import logging
from typing import Awaitable, Type

from .ban import Ban
from .cache import AsyncRCONClientCache
from .dispatch import AsyncEventDispatcher
from .io import AsyncClientProtocol, AsyncClientConnector
from .player import Player
from ..client import RCONClient
from ..errors import RCONCommandError

log = logging.getLogger(__name__)


class AsyncRCONClient(RCONClient):
    """An implementation of the RCON client protocol using asyncio."""

    cache: AsyncRCONClientCache
    dispatch: AsyncEventDispatcher

    def __init__(
        self,
        *,
        cache: AsyncRCONClientCache | None = None,
        dispatch: AsyncEventDispatcher | None = None,
        protocol: AsyncClientProtocol | None = None,
    ):
        """
        :param cache: The cache to use for the client.
        :param dispatch: The dispatcher object to use for transmitting events.
        :param protocol: The protocol to use for handling connections.
        """
        if cache is None:
            cache = AsyncRCONClientCache()
        if dispatch is None:
            dispatch = AsyncEventDispatcher()
        if protocol is None:
            protocol = AsyncClientConnector()

        super().__init__(cache=cache, dispatch=dispatch)

        self.protocol = protocol
        self.protocol.client = self

    def is_connected(self) -> bool:
        """Indicates if the client has a currently active connection
        with the server.
        """
        return self.protocol.is_connected()

    def is_logged_in(self) -> bool | None:
        """Indicates if the client is currently authenticated with the server.

        :returns:
            True if authenticated or None if no
            response has been received from the server.
        :raises LoginFailure:
            The password given to the server was denied.

        """
        return self.protocol.is_logged_in()

    def is_running(self) -> bool:
        """Indicates if the client is running. This may not necessarily
        mean that the client is connected.
        """
        return self.protocol.is_running()

    # Connection methods

    @contextlib.asynccontextmanager
    async def connect(self, ip: str, port: int, password: str):
        """Returns an asynchronous context manager for logging into
        the given `IP` and `port` with `password`.

        Example usage::

            client = berconpy.AsyncRCONClient()
            async with client.connect(ip, port, password):
                print("Connected!")
            print("Disconnected!")

        If an unexpected error occurs after successfully logging in,
        the current task that the context manager is used in will be
        **cancelled** to prevent the script being stuck in an infinite loop.

        :raises LoginFailure:
            The password given to the server was denied.
        :raises RuntimeError:
            This method was called while the client is already connected.

        """
        # Establish connection
        task = None
        try:
            task = self.protocol.run(ip, port, password)

            # Wait for login here to avoid any commands being sent
            # by the user before a connection was made
            await self.protocol.wait_for_login()
            yield self
        finally:
            self.close()

            # Wait for the protocol to cleanly disconnect,
            # and also to propagate any exception
            if task is not None:
                await task

    def close(self):
        """Closes the connection.

        This method is idempotent and can be called multiple times consecutively.

        .. versionchanged:: 1.1

            This method no longer causes the current task to be cancelled.

        """
        self.protocol.close()

    # Commands
    # (documentation: https://www.battleye.com/support/documentation/)

    async def send_command(self, command: str) -> str:
        if not self.protocol.is_running():
            raise RuntimeError("cannot send command when not connected")

        response = await self.protocol.send_command(command)
        if self._is_disallowed_command(response):
            raise RCONCommandError("server has disabled this command")

        return response

    async def fetch_admins(self) -> list[tuple[int, str]]:
        response = await self.send_command("admins")
        return self._parse_admins(response)

    async def fetch_bans(self) -> list[Ban]:
        response = await self.send_command("bans")
        return self._parse_bans(response, cls=Ban)

    async def fetch_missions(self) -> list[str]:
        response = await self.send_command("missions")
        return self._parse_missions(response)

    async def fetch_players(self) -> list[Player]:
        response = await self.send_command("players")
        self._update_players(response)
        return self.cache.players

    def ban(
        self,
        addr: int | str,
        duration: int | None = None,
        reason: str = "",
    ) -> Awaitable[str]:
        return super().ban(addr, duration, reason)  # type: ignore

    def kick(self, player_id: int, reason: str = "") -> Awaitable[str]:
        return super().kick(player_id, reason)  # type: ignore

    def send(self, message: str) -> Awaitable[str]:
        return super().send(message)  # type: ignore

    def unban(self, ban_id: int) -> Awaitable[str]:
        return super().unban(ban_id)  # type: ignore

    def whisper(self, player_id: int, message: str) -> Awaitable[str]:
        return super().whisper(player_id, message)  # type: ignore
