import asyncio
import contextlib
import logging
from typing import Awaitable, Type

from .ban import Ban
from .cache import AsyncRCONClientCache
from .dispatch import AsyncEventDispatch
from .player import Player
from ..client import RCONClient
from ...errors import RCONCommandError
from ...old_protocol import RCONClientDatagramProtocol

log = logging.getLogger(__name__)


def _prepare_canceller(
    protocol: RCONClientDatagramProtocol,
    running_task: asyncio.Task,
    current_task: asyncio.Task | None = None,
):
    """Adds a callback to the task running the protocol to cancel
    the current task if the running task completes with an exception.

    This should *only* be called after waiting for login, which is when the
    closing future exists for the canceller to suppress exceptions from it.

    """

    def _actual_canceller(_):
        if closing.exception() is not None:
            current_task.cancel()

    # We need to cache the closing future here, so we're still able to
    # suppress the future exception if the protocol closed with one
    closing = protocol._is_closing
    if closing is None:
        raise RuntimeError(
            "cannot set up canceller before/after protocol has finished running"
        )

    current_task = current_task or asyncio.current_task()
    running_task.add_done_callback(_actual_canceller)


class AsyncRCONClient(RCONClient):
    """An asynchronous interface for connecting to an BattlEye RCON server.

    .. note::

        Most of this class's methods for sending commands like
        :py:meth:`kick()` may raise :py:exc:`RCONCommandError` or
        :py:exc:`RuntimeError` since they rely on the :py:meth:`send_command()`
        method.

    """

    cache: AsyncRCONClientCache
    dispatch: AsyncEventDispatch

    def __init__(
        self,
        *,
        cache_cls: Type[AsyncRCONClientCache] | None = None,
        dispatch: AsyncEventDispatch | None = None,
        protocol_cls=RCONClientDatagramProtocol,
    ):
        if cache_cls is None:
            cache_cls = AsyncRCONClientCache
        if dispatch is None:
            dispatch = AsyncEventDispatch()

        super().__init__(cache_cls=cache_cls, dispatch=dispatch)
        self.dispatch.add_listener("on_login", self.cache.on_login)

        self._protocol = protocol_cls(self)
        self._protocol_task: asyncio.Task | None = None

    def is_logged_in(self) -> bool | None:
        """Indicates if the client is currently authenticated with the server.

        :returns:
            True if authenticated or None if no
            response has been received from the server.
        :raises LoginFailure:
            The password given to the server was denied.

        """
        return self._protocol.is_logged_in()

    def is_connected(self) -> bool:
        """Indicates if the client has a currently active connection
        with the server.
        """
        return self._protocol.is_connected()

    def is_running(self) -> bool:
        """Indicates if the client is running. This may not necessarily
        mean that the client is connected.
        """
        return self._protocol.is_running()

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
        if self._protocol.is_running():
            raise RuntimeError("connection is already running")

        # Establish connection
        try:
            self._protocol_task = asyncio.create_task(
                self._protocol.run(ip, port, password)
            )

            # it's important we wait for login here, otherwise the user
            # could attempt sending commands before a connection was made
            await self._protocol.wait_for_login()
            _prepare_canceller(self._protocol, self._protocol_task)
            yield self
        finally:
            self.close()

            # Propagate any exception from the task
            if not self._protocol_task.done():
                return

            exc = self._protocol_task.exception()
            if exc is not None:
                raise exc from None

    def close(self):
        """Closes the connection.

        This method is idempotent and can be called multiple times consecutively.

        .. versionchanged:: 1.1

            This method no longer causes the current task to be cancelled.

        """
        self._protocol.close()

    # Commands
    # (documentation: https://www.battleye.com/support/documentation/)

    async def send_command(self, command: str) -> str:
        if not self._protocol.is_running():
            raise RuntimeError("cannot send command when not connected")

        response = await self._protocol._send_command(command)
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
