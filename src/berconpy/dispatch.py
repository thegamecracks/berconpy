from __future__ import annotations

import asyncio
import collections
import logging
from typing import TYPE_CHECKING, Any, Callable, TypeVar

from ._typed_event import typed_event
from .utils import MaybeCoroFunc, maybe_coro

if TYPE_CHECKING:
    from .protocol.packet import ServerPacket

T = TypeVar("T")

log = logging.getLogger(__name__)


class EventDispatcher:
    """Provides an event handler system for use with asyncio.

    To listen for one of the following events, use the :py:meth:`add_listener()`
    method, the :py:meth:`listen()` decorator, or the type-safe ``on_*`` decorators::

        dispatch = EventDispatcher()
        dispatch.add_listener("on_login", event)

        @dispatch.listen()
        async def on_login():
            ...

        @dispatch.listen("on_login")
        async def my_listener():
            ...

        @dispatch.on_login
        async def my_listener():
            ...

    """

    _event_listeners: dict[str, list[MaybeCoroFunc[..., Any]]]
    _temporary_listeners: dict[
        str, list[tuple[asyncio.Future, MaybeCoroFunc[..., Any]]]
    ]

    def __init__(self) -> None:
        self._event_listeners = collections.defaultdict(list)
        self._temporary_listeners = collections.defaultdict(list)

    def __call__(self, event: str, *args):
        """Dispatches a message to the corresponding event listeners.

        The event name given should not be prefixed with "on_".

        """
        log.debug(f"dispatching event (on_){event}")
        event = "on_" + event

        for func in self._event_listeners[event]:
            asyncio.create_task(maybe_coro(func, *args), name=f"berconpy-{event}")

        for fut, check in self._temporary_listeners[event]:
            asyncio.create_task(
                self._try_dispatch_temporary(event, fut, check, *args),
                name=f"berconpy-temp-{event}",
            )

    def add_listener(self, event: str, func: MaybeCoroFunc[..., Any]):
        """Adds a listener for a given event, e.g. ``"on_login"``.

        :param event:
            The event to listen for.
        :param func:
            The function to dispatch when the event is received.

        """
        self._event_listeners[event].append(func)

    def listen(self, event: str | None = None) -> Callable[[T], T]:
        """A decorator shorthand to add a listener for a given event,
        e.g. ``"on_login"``.

        :param event:
            The event to listen for. If ``None``, the function name
            is used as the event name.

        """

        def decorator(func):
            self.add_listener(event or func.__name__, func)
            return func

        return decorator

    def remove_listener(self, event: str, func: MaybeCoroFunc[..., Any]):
        """Removes a listener from a given event, e.g. ``"on_login"``.

        This method should be a no-op if the given event and function
        does not match any registered listener.

        :param event: The event used by the listener.
        :param func: The function used by the listener.

        """
        try:
            self._event_listeners[event].remove(func)
        except ValueError:
            pass

    async def wait_for(
        self,
        event: str,
        *,
        check: MaybeCoroFunc[..., Any] | None = None,
        timeout: float | int | None = None,
    ):
        """Waits for a specific event to occur and returns the result.

        This allows handling one-shot events in a simpler manner than
        with persistent listeners.

        :param event: The event to wait for, e.g. ``"login"`` and ``"on_login"``.
        :param check:
            An optional predicate function to use as a filter.
            This can be either a regular or an asynchronous function.
            The function should accept the same arguments that the event
            normally takes.
        :param timeout:
            An optional timeout for the function. If this is provided
            and the function times out, an :py:exc:`asyncio.TimeoutError`
            is raised.
        :returns: The same arguments received in the event.
        :raises asyncio.TimeoutError:
            The timeout was exceeded while waiting.

        """
        if not event.startswith("on_"):
            event = "on_" + event
        if check is None:
            check = lambda *args: True  # noqa: E731

        fut = self._add_temporary_listener(event, check)

        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            fut.cancel()
            raise
        finally:
            self._remove_temporary_listener(event, fut, check)

    def _add_temporary_listener(
        self,
        event: str,
        check: MaybeCoroFunc[..., Any],
    ) -> asyncio.Future:
        fut = asyncio.get_running_loop().create_future()
        self._temporary_listeners[event].append((fut, check))
        return fut

    def _remove_temporary_listener(
        self,
        event: str,
        fut: asyncio.Future,
        check: MaybeCoroFunc[..., Any],
    ) -> None:
        listeners = self._temporary_listeners[event]
        e = (fut, check)

        try:
            listeners.remove(e)
        except ValueError:
            pass

    async def _try_dispatch_temporary(
        self,
        event: str,
        fut: asyncio.Future,
        check: MaybeCoroFunc[..., Any],
        *args,
    ):
        if fut.done():
            return

        try:
            check_accepted = await maybe_coro(check, *args)
        except Exception as e:
            if not fut.done():
                fut.set_exception(e)
        else:
            if check_accepted and not fut.done():
                fut.set_result(args)

    # Specific events to provide type inference

    @typed_event
    @staticmethod
    def on_raw_event(packet: ServerPacket, /) -> Any:
        """Fired for every parsable packet received by the server.

        :param packet: The packet that was received.

        """

    @typed_event
    @staticmethod
    def on_login() -> Any:
        """Fired after a successful login to the server."""

    @typed_event
    @staticmethod
    def on_command(response: str, /) -> Any:
        """Fired after receiving any command response from the server.

        This should only be used for debugging purposes as the
        :py:meth:`~berconpy.client.RCONClient.send_command()` method already
        returns the server's response.

        :param response: The response received by the server.

        """

    @typed_event
    @staticmethod
    def on_message(message: str, /) -> Any:
        """Fired for messages sent by the server, e.g. player connections.

        More specific events such as :py:func:`on_admin_login`
        are dispatched from this event.

        :param response: The message that was sent by the server.

        """
