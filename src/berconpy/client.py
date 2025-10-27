import asyncio
import contextlib
import logging
from typing import Any, Callable, TypeVar

from berconpy.utils import MaybeCoroFunc

from .dispatch import EventDispatcher
from .io import AsyncClientProtocol, AsyncClientConnector

T = TypeVar("T")

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


class RCONClient:
    """An implementation of the RCON client protocol using asyncio."""

    def __init__(
        self,
        *,
        dispatch: EventDispatcher | None = None,
        protocol: AsyncClientProtocol | None = None,
    ):
        """
        :param dispatch:
            The dispatcher object to use for transmitting events.
            Defaults to an instance of :py:class:`EventDispatcher`.
        :param protocol:
            The protocol to use for handling connections.
            Defaults to an instance of :py:class:`AsyncClientConnector`.
        """
        if dispatch is None:
            dispatch = EventDispatcher()
        if protocol is None:
            protocol = AsyncClientConnector()

        self.dispatch = dispatch
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
            The client failed to log into the server.

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

            client = berconpy.RCONClient()
            async with client.connect(ip, port, password):
                print("Connected!")
            print("Disconnected!")

        If an unexpected error occurs after successfully logging in,
        the current task that the context manager is used in will be
        **cancelled** to prevent the script being stuck in an infinite loop.

        :raises LoginFailure:
            The client failed to log into the server.
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

    async def send_command(self, command: str) -> str:
        """Sends a command to the server and waits for a response.

        :param command: The command to send.
        :returns: The server's response as a string.
        :raises RCONCommandError:
            The server has either disabled this command or failed to
            respond to our command.
        :raises RuntimeError:
            The client is either not connected or the server
            could/would not respond to the command.

        """
        if not self.protocol.is_running():
            raise RuntimeError("cannot send command when not connected")
        return await self.protocol.send_command(command)

    # Event dispatcher

    def add_listener(self, event: str, func: Callable) -> None:
        """A shorthand for the :py:meth:`EventDispatcher.add_listener()` method.

        See the :py:class:`EventDispatcher` for a list of supported events.

        :param event:
            The event to listen for.
        :param func:
            The function to dispatch when the event is received.

        """
        return self.dispatch.add_listener(event, func)

    def remove_listener(self, event: str, func: Callable) -> None:
        """A shorthand for the :py:meth:`EventDispatcher.remove_listener()` method.

        This method should be a no-op if the given event and function
        does not match any registered listener.

        :param event: The event used by the listener.
        :param func: The function used by the listener.

        """
        return self.dispatch.remove_listener(event, func)

    def listen(self, event: str | None = None) -> Callable[[T], T]:
        """A shorthand for the :py:meth:`EventDispatcher.listen()` decorator.

        Example usage::

            >>> client = RCONClient()
            >>> @client.listen()
            ... async def on_login():
            ...     print("We have logged in!")

        :param event:
            The event to listen for. If ``None``, the function name
            is used as the event name.

        """
        return self.dispatch.listen(event)

    async def wait_for(
        self,
        event: str,
        *,
        check: MaybeCoroFunc[..., Any] | None = None,
        timeout: float | int | None = None,
    ):
        """A shorthand for :py:class:`EventDispatcher.wait_for()`."""
        return await self.dispatch.wait_for(event, check=check, timeout=timeout)
