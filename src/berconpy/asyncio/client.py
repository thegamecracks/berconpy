import asyncio
import contextlib
import logging
from typing import Generator, TypeVar

from .ban import Ban
from .cache import AsyncRCONClientCache
from .dispatch import AsyncEventDispatcher
from .io import AsyncClientProtocol, AsyncClientConnector
from .player import Player
from ..client import RCONClient
from ..utils import MaybeCoroFunc

log = logging.getLogger(__name__)

T = TypeVar("T")


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
        return await self._run_commands(self._send_command(command))

    async def fetch_admins(self) -> list[tuple[int, str]]:
        return await self._run_commands(self._fetch_admins())

    async def fetch_bans(self) -> list[Ban]:
        return await self._run_commands(self._fetch_bans(cls=Ban))

    async def fetch_missions(self) -> list[str]:
        return await self._run_commands(self._fetch_missions())

    async def fetch_players(self) -> list[Player]:
        return await self._run_commands(self._fetch_players())  # type: ignore

    async def ban(
        self,
        addr: int | str,
        duration: int | None = None,
        reason: str = ""
    ) -> str:
        return await self._run_commands(self._ban(addr, duration, reason))

    async def kick(self, player_id: int, reason: str = "") -> str:
        return await self._run_commands(self._kick(player_id, reason))

    async def send(self, message: str) -> str:
        return await self._run_commands(self._send(message))

    async def unban(self, ban_id: int) -> str:
        return await self._run_commands(self._unban(ban_id))

    async def whisper(self, player_id: int, message: str) -> str:
        return await self._run_commands(self._whisper(player_id, message))

    async def _run_commands(self, gen: Generator[str, str, T]) -> T:
        if not self.protocol.is_running():
            raise RuntimeError("cannot send command when not connected")

        try:
            command = next(gen)
            while True:
                response = await self.protocol.send_command(command)
                command = gen.send(response)
        except StopIteration as e:
            return e.value

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
