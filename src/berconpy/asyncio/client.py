import asyncio
import contextlib
import logging
from typing import Awaitable

from .ban import Ban
from .cache import AsyncRCONClientCache
from .dispatch import AsyncEventDispatcher
from .io import AsyncClientProtocol, AsyncClientConnector
from .player import Player
from ..client import RCONClient
from ..utils import MaybeCoroFunc

log = logging.getLogger(__name__)


def _add_cancel_callback(
    fut: asyncio.Future,
    current_task: asyncio.Task | None = None,
):
    """Adds a callback to a future to cancel the current task
    if the future completes with an exception.
    """
    def _actual_canceller(_):
        assert current_task is not None
        if fut.exception() is not None:
            current_task.cancel()

    # We need to cache the closing future here, so we're still able to
    # suppress the future exception if the protocol closed with one

    current_task = current_task or asyncio.current_task()
    fut.add_done_callback(_actual_canceller)


class AsyncRCONClient(RCONClient):
    """An implementation of the RCON client protocol using asyncio."""

    def __init__(
        self,
        *,
        cache: AsyncRCONClientCache | None = None,
        dispatch: AsyncEventDispatcher | None = None,
        protocol: AsyncClientProtocol | None = None,
    ):
        """
        :param cache:
            The cache to use for the client.
            Defaults to an instance of :py:class:`AsyncRCONClientCache`.
        :param dispatch:
            The dispatcher object to use for transmitting events.
            Defaults to an instance of :py:class:`AsyncEventDispatcher`.
        :param protocol:
            The protocol to use for handling connections.
            Defaults to an instance of :py:class:`AsyncClientConnector`.
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

            # Interrupt the current task if a fatal error occurs in the protocol
            _add_cancel_callback(task)

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
        self.check_disallowed_command(response)

        return response

    async def fetch_admins(self) -> list[tuple[int, str]]:
        response = await self.send_command("admins")
        return self.parse_admins(response)

    async def fetch_bans(self) -> list[Ban]:
        response = await self.send_command("bans")
        return self.parse_bans(response, cls=Ban)

    async def fetch_missions(self) -> list[str]:
        response = await self.send_command("missions")
        return self.parse_missions(response)

    async def fetch_players(self) -> list[Player]:
        response = await self.send_command("players")
        self.cache.update_players(response)
        return self.players

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

    # Cache

    @property
    def cache(self) -> AsyncRCONClientCache:
        return super().cache  # type: ignore

    @cache.setter
    def cache(self, new_cache: AsyncRCONClientCache) -> None:
        # super().cache doesn't work so we're invoking the descriptor directly
        super(AsyncRCONClient, type(self)).cache.__set__(self, new_cache)  # type: ignore

    def get_player(self, player_id: int) -> "Player | None":
        return super().get_player(player_id)  # type: ignore

    @property
    def players(self) -> list[Player]:
        return super().players  # type: ignore

    # Event dispatcher

    @property
    def dispatch(self) -> AsyncEventDispatcher:
        return super().dispatch  # type: ignore

    @dispatch.setter
    def dispatch(self, new_dispatch: AsyncEventDispatcher) -> None:
        # super().dispatch doesn't work so we're invoking the descriptor directly
        super(AsyncRCONClient, type(self)).dispatch.__set__(self, new_dispatch)  # type: ignore

    async def wait_for(
        self,
        event: str,
        *,
        check: MaybeCoroFunc | None = None,
        timeout: float | int | None = None,
    ):
        """A shorthand for :py:class:`AsyncEventDispatcher.wait_for()`."""
        return await self.dispatch.wait_for(event, check=check, timeout=timeout)
