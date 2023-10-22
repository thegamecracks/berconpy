from __future__ import annotations

import asyncio
import collections
import logging
from typing import TYPE_CHECKING, Any

from ..dispatch import EventDispatcher, typed_event
from ..utils import MaybeCoroFunc, copy_doc, maybe_coro

if TYPE_CHECKING:
    from .player import Player

log = logging.getLogger(__name__)


class AsyncEventDispatcher(EventDispatcher):
    """
    Implements the :py:class:`.EventDispatcher` interface for asyncio.
    See that class for details on registering event listeners.

    Unlike :py:class:`.EventDispatcher`, asynchronous functions can be
    added as listeners and will run in their own task when fired.

    """

    _event_listeners: dict[str, list[MaybeCoroFunc[..., Any]]]
    _temporary_listeners: dict[
        str, list[tuple[asyncio.Future, MaybeCoroFunc[..., Any]]]
    ]

    def __init__(self) -> None:
        self._event_listeners = collections.defaultdict(list)
        self._temporary_listeners = collections.defaultdict(list)

    def __call__(self, event: str, *args):
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
        self._event_listeners[event].append(func)

    def remove_listener(self, event: str, func: MaybeCoroFunc[..., Any]):
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
            check = lambda *args: True

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
    @copy_doc(EventDispatcher.on_player_connect)
    def on_player_connect(player: Player, /) -> Any:
        ...

    @typed_event
    @staticmethod
    @copy_doc(EventDispatcher.on_player_guid)
    def on_player_guid(player: Player, /) -> Any:
        ...

    @typed_event
    @staticmethod
    @copy_doc(EventDispatcher.on_player_verify_guid)
    def on_player_verify_guid(player: Player, /) -> Any:
        ...

    @typed_event
    @staticmethod
    @copy_doc(EventDispatcher.on_player_disconnect)
    def on_player_disconnect(player: Player, /) -> Any:
        ...

    @typed_event
    @staticmethod
    @copy_doc(EventDispatcher.on_player_kick)
    def on_player_kick(player: Player, reason: str, /) -> Any:
        ...

    @typed_event
    @staticmethod
    @copy_doc(EventDispatcher.on_admin_whisper)
    def on_admin_whisper(player: Player, admin_id: int, message: str, /) -> Any:
        ...

    @typed_event
    @staticmethod
    @copy_doc(EventDispatcher.on_player_message)
    def on_player_message(player: Player, channel: str, message: str, /) -> Any:
        ...
