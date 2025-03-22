from __future__ import annotations

import functools
import inspect
from abc import ABC, abstractmethod
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generic,
    ParamSpec,
    Type,
    TypeVar,
    overload,
)

if TYPE_CHECKING:
    from typing_extensions import Self

    from .protocol.packet import ServerPacket

P = ParamSpec("P")
T = TypeVar("T")


class TypedEvent(Generic[P, T]):
    """A descriptor for a statically-typed event.

    On an :py:class:`EventDispatcher` instance, this descriptor returns
    a :py:class:`BoundTypedEvent` which can be called to add a function
    as a listener for a specific event. The listener must match the same
    signature as given in the two type arguments to this class.

    To remove the listener afterwards, call :py:meth:`BoundTypedEvent.remove()`
    with the same function.

    The :py:meth:`BoundTypedEvent.fire()` method is also provided for
    dispatching the event, statically enforcing that the arguments match
    the parameter spec in the first type argument.

    For better signature specification, it is recommended to use the
    :py:func:`typed_event` decorator instead of this class directly.

    """

    event: str
    """The name of the event that this is bound to."""

    def __set_name__(self, owner: Type[EventDispatcher], name: str) -> None:
        self.event = name

    # Look like a callable object so Sphinx can correctly document us
    def __call__(self):
        raise NotImplementedError

    @overload
    def __get__(
        self,
        instance: None,
        owner: Any = None,
    ) -> "Self":
        ...

    @overload
    def __get__(
        self,
        instance: EventDispatcher,
        owner: Any = None,
    ) -> BoundTypedEvent[P, T]:
        ...

    def __get__(
        self,
        instance: EventDispatcher | None,
        owner: Type[EventDispatcher] | None = None,
    ) -> BoundTypedEvent[P, T] | Self:
        if instance is None:
            return self

        assert self.event is not None
        return BoundTypedEvent(instance, self.event)


class BoundTypedEvent(Generic[P, T]):
    """
    An instance of :py:class:`TypedEvent`, bound to an :py:class:`EventDispatcher`.
    See TypeEvent's docstring for more information.
    """

    __slots__ = ("dispatch", "dispatch_event", "event")

    dispatch: "EventDispatcher"
    """The dispatch object that this is bound to."""
    dispatch_event: str
    """Same as :py:attr:`event` but without the "on_" prefix."""
    event: str
    """The name of the event that this is bound to."""

    def __init__(self, dispatch: EventDispatcher, event: str) -> None:
        self.dispatch = dispatch
        self.event = event
        self.dispatch_event = event.removeprefix("on_")

    def __call__(self, callback: Callable[P, T]) -> Callable[P, T]:
        self.dispatch.add_listener(self.event, callback)
        return callback

    def fire(self, *args: P.args, **kwargs: P.kwargs) -> None:
        return self.dispatch(self.dispatch_event, *args, **kwargs)

    def remove(self, callback: Callable[P, T]) -> None:
        return self.dispatch.remove_listener(self.event, callback)


def typed_event(func: Callable[P, T], /) -> TypedEvent[P, T]:
    """Returns a :py:class:`TypedEvent` that will add a function as a listener.
    The event name is derived from the input function, and the resulting
    decorator will assert that the listener's signature matches the input function.

    This decorator can only be applied on methods within an
    :py:class:`EventDispatcher` class.
    :py:func:`staticmethod()` should also be applied under this decorator.

    """
    new_event = TypedEvent[P, T]()
    functools.update_wrapper(new_event, func)

    unwrapped = inspect.unwrap(func)

    # Ideally we would set __wrapped__ so it would work with unwrap(),
    # but it causes Sphinx to remove the first parameter from the signature.
    # Removing this attribute breaks inspect.getsource().
    del new_event.__wrapped__  # type: ignore

    new_event.__annotations__ = func.__annotations__
    new_event.__name__ = func.__name__  # type: ignore
    new_event.__qualname__ = func.__qualname__  # type: ignore

    # Sphinx requires this to evaluate our TYPE_CHECKING block correctly
    # (sphinx_autodoc_typehints/__init__.py@_resolve_type_guarded_imports)
    new_event.__globals__ = unwrapped.__globals__  # type: ignore

    # Required for inspect.signature() due to __wrapped__ being unset
    new_event.__signature__ = inspect.signature(func)  # type: ignore

    return new_event


class EventDispatcher(ABC):
    """The base class for implementing an event handler system.

    To listen for one of the following events, use the :py:meth:`add_listener()`
    method, the :py:meth:`listen()` decorator, or the type-safe ``on_*`` decorators::

        dispatch: EventDispatcher

        dispatch.add_listener("on_login", event)

        @dispatch.listen()
        def on_login():
            ...

        @dispatch.listen("on_login")
        def my_listener():
            ...

        @dispatch.on_login
        def my_listener():
            ...

    """

    @abstractmethod
    def add_listener(self, event: str, func: Callable, /):
        """Adds a listener for a given event, e.g. ``"on_login"``.

        :param event:
            The event to listen for.
        :param func:
            The function to dispatch when the event is received.

        """

    @abstractmethod
    def remove_listener(self, event: str, func: Callable):
        """Removes a listener from a given event, e.g. ``"on_login"``.

        This method should be a no-op if the given event and function
        does not match any registered listener.

        :param event: The event used by the listener.
        :param func: The function used by the listener.

        """

    @abstractmethod
    def __call__(self, event: str, *args):
        """Dispatches a message to the corresponding event listeners.

        The event name given should not be prefixed with "on_".

        """

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
