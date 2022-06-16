import asyncio
import collections
import contextlib
import logging
import uuid
from typing import Callable, Coroutine

from .protocol import RCONClientDatagramProtocol
from .utils import maybe_coro

log = logging.getLogger(__name__)

CoroFunc = Callable[[...], Coroutine]
MaybeCoroFunc = CoroFunc | Callable


class AsyncRCONClient:
    """An asynchronous interface for connecting to an BattlEye RCON server.

    This client supports adding event listeners for handling
    incoming data. To add an event listener, use the `add_listener()`
    method or the `listen()` decorator.

    Supported event names:
        - on_raw_event(packet: ServerPacket)
            Fired for every parsable packet received by the server.
        - on_login()
            Fired after a successful login to the server.
        - on_command(command: str)
            Fired after receiving a command response from the server.
            This event is usually not necessary and responses can more
            easily be received using the `send_command()` method.
        - on_message(response: str)
            Fired for messages sent by the server, e.g. player connections.

    :param name:
        An optional name used in logging messages.
        If not provided, a UUID is generated for the name.

    """
    def __init__(
        self,
        name: str = None,
        protocol_cls=RCONClientDatagramProtocol
    ):
        self.name: str = name or str(uuid.uuid4())

        self._protocol = protocol_cls(self)
        self._protocol_task: asyncio.Task | None = None

        self._event_listeners: dict[str, list[CoroFunc]] = collections.defaultdict(list)
        self._temporary_listeners: dict[
            str, list[tuple[asyncio.Future, MaybeCoroFunc]]
        ] = collections.defaultdict(list)

    def __repr__(self):
        return '<{} name={!r}>'.format(type(self).__name__, self.name)

    # Event handling

    def add_listener(self, event: str, func: CoroFunc):
        """Adds a listener for a given event (e.g. "on_login")."""
        self._event_listeners[event].append(func)

    def remove_listener(self, event: str, func: CoroFunc):
        """Removes a listener for a given event (e.g. "on_login")."""
        try:
            self._event_listeners[event].remove(func)
        except ValueError:
            pass

    def listen(self, event: str = None):
        """A decorator shorthand for adding a listener for a given event
        (e.g. "on_login").

        :param event:
            The event to listen for. If None, the function name
            is used as the event name.

        """
        def decorator(func: CoroFunc):
            self._event_listeners[event or func.__name__].append(func)
            return func

        return decorator

    def _add_temporary_listener(self, event: str, predicate: MaybeCoroFunc):
        """Adds a temporary listener for an event and returns a future.

        These listeners can be removed either with `_remove_temporary_listener()`
        or by cancelling the future that is returned.

        """
        fut = asyncio.get_running_loop().create_future()
        self._temporary_listeners[event].append((fut, predicate))
        return fut

    def _remove_temporary_listener(self, event: str, fut: asyncio.Future, pred: MaybeCoroFunc):
        listeners = self._temporary_listeners[event]
        e = (fut, pred)

        try:
            listeners.remove(e)
        except ValueError:
            pass

    async def wait_for(
        self, event: str, *,
        check: MaybeCoroFunc = None,
        timeout: float | int = None
    ):
        """Waits for a specific event to occur and returns the result.

        :param event: The event to listen for. (e.g. "login" or "on_login")
        :param check:
            An optional predicate function to use as a filter.
            This can be either a regular or an asynchronous function.
            The function should accept the same arguments that the event
            normally takes.
        :param timeout:
            An optional timeout for the function. If this is provided
            and the function times out, an `asyncio.TimeoutError` is raised.
        :returns: The arguments passed to the given event.
        :raises asyncio.TimeoutError:
            The function timed out while waiting for the event.

        """
        if not event.startswith('on_'):
            event = 'on_' + event
        if check is None:
            check = lambda *args: True

        fut = self._add_temporary_listener(event, check)

        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            fut.cancel()
            raise

    async def _try_dispatch_temporary(
        self, event: str, fut: asyncio.Future, pred: MaybeCoroFunc, *args
    ):
        if fut.done():
            return self._remove_temporary_listener(event, fut, pred)

        try:
            result = await maybe_coro(pred, *args)
        except Exception as e:
            if not fut.done():
                fut.set_exception(e)
        else:
            if result and not fut.done():
                fut.set_result(args)
        finally:
            self._remove_temporary_listener(event, fut, pred)

    def _dispatch(self, event: str, *args):
        """Dispatches a message to the corresponding event listeners.

        Note that the event name should not be prefixed with "on_".

        """
        log.debug(f'{self.name}: dispatching event {event}')
        event = 'on_' + event

        for func in self._event_listeners[event]:
            asyncio.create_task(
                func(*args),
                name=f'berconpy-{event}'
            )

        for fut, pred in self._temporary_listeners[event]:
            asyncio.create_task(
                self._try_dispatch_temporary(event, fut, pred, *args),
                name=f'berconpy-temp-{event}'
            )

    # Connection methods

    @contextlib.asynccontextmanager
    async def connect(self, ip: str, port: int, password: str):
        """Connect to the given IP and port with password.

        :raises RuntimeError:
            This method was called while the client is already connected.

        """
        if self._protocol.is_running():
            raise RuntimeError('connection is already running')

        # Establish connection
        try:
            self._protocol_task = asyncio.create_task(
                self._protocol.run(ip, port, password)
            )

            await self._protocol.wait_for_login()
            yield self
        finally:
            self.close()

            # Propagate any exception from the task
            # FIXME: if login fails then wait_for_login() raises
            #   the same exception, resulting in a dirtier traceback
            await self._protocol_task
            self._protocol_task.result()

    def close(self):
        """Closes the connection.

        Unlike connect(), this method is idempotent and can be
        called multiple times consecutively.

        """
        self._protocol.close()

    # Communication

    async def send_command(self, command: str) -> str:
        """Sends a command to the server and waits for a response.

        :param command: The command to send. Only ASCII characters are allowed.
        :returns: The server's response as a string.
        :raises RuntimeError:
            The client is either not connected or the server
            could/would not respond to the command.

        """
        if not self._protocol.is_running():
            raise RuntimeError('cannot send command when not connected')

        return await self._protocol._send_command(command)
