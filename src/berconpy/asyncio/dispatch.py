import asyncio
import collections
import logging

from ..dispatch import RCONClientDispatch
from ..utils import MaybeCoroFunc, maybe_coro

log = logging.getLogger(__name__)


class AsyncEventDispatch(RCONClientDispatch):
    """Implements the :py:class:`RCONClientDispatch` interface for asyncio."""

    _event_listeners: dict[str, list[MaybeCoroFunc]]
    _temporary_listeners: dict[str, list[tuple[asyncio.Future, MaybeCoroFunc]]]

    def __init__(self) -> None:
        self._event_listeners = collections.defaultdict(list)
        self._temporary_listeners = collections.defaultdict(list)

    def __call__(self, event: str, *args):
        log.debug(f"dispatching event (on_){event}")
        event = "on_" + event

        for func in self._event_listeners[event]:
            asyncio.create_task(maybe_coro(func, *args), name=f"berconpy-{event}")

        for fut, pred in self._temporary_listeners[event]:
            asyncio.create_task(
                self._try_dispatch_temporary(event, fut, pred, *args),
                name=f"berconpy-temp-{event}",
            )

    def add_listener(self, event: str, func: MaybeCoroFunc):
        """Adds a listener for a given event, e.g. ``"on_login"``.

        See the :doc:`/events` for a list of supported events.

        :param event:
            The event to listen for.
        :param func:
            The coroutine function to dispatch when the event is received.

        """
        self._event_listeners[event].append(func)

    def remove_listener(self, event: str, func: MaybeCoroFunc):
        """Removes a listener from a given event, e.g. ``"on_login"``.

        This method is a no-op if the given event and function
        does not match any registered listener.

        :param event: The event used by the listener.
        :param func: The coroutine function used by the listener.

        """
        try:
            self._event_listeners[event].remove(func)
        except ValueError:
            pass

    async def wait_for(
        self,
        event: str,
        *,
        check: MaybeCoroFunc | None = None,
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
            check = lambda *args: True

        fut = self._add_temporary_listener(event, check)

        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            fut.cancel()
            raise

    def _add_temporary_listener(
        self,
        event: str,
        predicate: MaybeCoroFunc,
    ) -> asyncio.Future:
        fut = asyncio.get_running_loop().create_future()
        self._temporary_listeners[event].append((fut, predicate))
        return fut

    def _remove_temporary_listener(
        self,
        event: str,
        fut: asyncio.Future,
        pred: MaybeCoroFunc,
    ) -> None:
        listeners = self._temporary_listeners[event]
        e = (fut, pred)

        try:
            listeners.remove(e)
        except ValueError:
            pass

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
            self._remove_temporary_listener(event, fut, pred)
        else:
            if not result or fut.done():
                return

            fut.set_result(args)
            self._remove_temporary_listener(event, fut, pred)
