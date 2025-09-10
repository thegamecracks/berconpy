from __future__ import annotations

import functools
import inspect
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

    from .dispatch import EventDispatcher

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
    ) -> "Self": ...

    @overload
    def __get__(
        self,
        instance: EventDispatcher,
        owner: Any = None,
    ) -> BoundTypedEvent[P, T]: ...

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
