from __future__ import annotations

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

    from .player import Player
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

    __slots__ = ("event",)

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
    unwrapped = inspect.unwrap(func)
    # Create a copy of TypedEvent with uniquely stored attributes
    new_event = type(
        "TypedEvent",
        (TypedEvent,),
        {
            "__annotations__": func.__annotations__,
            "__name__": func.__name__,
            "__qualname__": func.__qualname__,
            # Ideally we would set __unwrapped__ so it would work with unwrap(),
            # but it causes Sphinx to remove the first parameter from the signature
            "__globals__": unwrapped.__globals__,
            # __globals__ is needed for typing.get_type_hints() to work
            "__signature__": inspect.signature(func),
            # __signature__ is needed by inspect.signature()
        },
    )
    obj = new_event()
    # The documentation must be part of the object, otherwise Sphinx will
    # think it was inherited and ignore it
    obj.__doc__ = func.__doc__
    return obj


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

    @typed_event
    @staticmethod
    def on_admin_login(admin_id: int, addr: str, /) -> Any:
        """Fired when a RCON admin logs into the server.

        The first message received will be our client logging in.

        .. note::

            This event has no logout equivalent as the server does not
            send messages for admins logging out.

        :param admin_id: The ID of the admin that logged into the server.
        :param addr: The admin's IP and port.

        """

    @typed_event
    @staticmethod
    def on_player_connect(player: Player, /) -> Any:
        """Fired when a player connects to a server.

        .. note::

            The player's :py:attr:`Player.guid` will most likely be
            an empty string since the server sends the GUID in
            a separate message briefly afterwards. To wait for the GUID
            to be provided, see the :py:func:`on_player_guid` event.

        :param player: The player that connected to the server.

        """

    @typed_event
    @staticmethod
    def on_player_guid(player: Player, /) -> Any:
        """Fired when receiving the BattlEye GUID for a connecting player.

        The given player object will have the updated GUID.

        :param player: The player whose GUID was updated.

        """

    @typed_event
    @staticmethod
    def on_player_verify_guid(player: Player, /) -> Any:
        """Fired when the server has verified the BattlEye GUID
        for a connecting player.

        :param player: The player whose GUID was verified.

        """

    @typed_event
    @staticmethod
    def on_player_disconnect(player: Player, /) -> Any:
        """Fired when a player manually disconnects from the server.

        The :py:attr:`~berconpy.client.RCONClient.players` list will
        no longer contain the player provided here.

        This event does not fire when BattlEye kicks the player;
        for that, see the following event :py:func:`on_player_kick()`.

        :param player: The player that disconnected.

        """

    @typed_event
    @staticmethod
    def on_player_kick(player: Player, reason: str, /) -> Any:
        """Fired when BattlEye kicks a player, either automatically
        (e.g. ``"Client not responding"``) or by an admin
        (i.e. ``"Admin Kick"``).

        The :py:attr:`~berconpy.client.RCONClient.players` list will
        no longer contain the player provided here.

        :param player: The player that was kicked.
        :param reason: The reason for the player being kicked.

        """

    @typed_event
    @staticmethod
    def on_admin_message(admin_id: int, channel: str, message: str, /) -> Any:
        """Fired when an RCON admin sends a message.

        If the ``channel`` is ``"Global"``, the :py:meth:`on_admin_announcement()`
        event is dispatched alongside this event.

        If the ``channel`` starts with ``"To "``, the :py:meth:`on_admin_whisper()`
        event is also dispatched.

        :param admin_id: The ID of the admin that sent the message.
        :param channel: The name of the channel the message was sent to.
        :param message: The message that was sent by the admin.

        """

    @typed_event
    @staticmethod
    def on_admin_announcement(admin_id: int, message: str, /) -> Any:
        """Fired when an RCON admin sends a global message.

        :param admin_id: The ID of the admin that sent the message.
        :param message: The message that was sent by the admin.

        """

    @typed_event
    @staticmethod
    def on_admin_whisper(player: Player, admin_id: int, message: str, /) -> Any:
        """Fired when an RCON admin sends a message to a specific player.

        .. note::

            This event may potentially not get dispatched if the player's name
            could not be found in the client's cache.

        :param player: The player that the message was directed towards.
        :param admin_id: The ID of the admin that sent the message.
        :param message: The message that was sent by the admin.

        """

    @typed_event
    @staticmethod
    def on_player_message(player: Player, channel: str, message: str, /) -> Any:
        """Fired when a player sends a message.

        :param player: The player that the message was directed towards.
        :param channel: The name of the channel the message was sent to.
        :param message: The message that was sent by the admin.

        """
