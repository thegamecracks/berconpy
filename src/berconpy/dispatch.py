from abc import ABC, abstractmethod
from typing import Callable, TypeVar

Hook = TypeVar("Hook", bound=Callable)


class RCONClientDispatch(ABC):
    """A standard interface for implementing an event handler system."""

    @abstractmethod
    def add_listener(self, event: str, func: Hook, /):
        """Adds a listener for a given event, e.g. ``"on_login"``.

        See the :doc:`/events` for a list of supported events.

        :param event:
            The event to listen for.
        :param func:
            The function to dispatch when the event is received.

        """

    @abstractmethod
    def remove_listener(self, event: str, func: Hook):
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

    def listen(self, event: str | None = None) -> Callable[[Hook], Hook]:
        """A decorator shorthand to add a listener for a given event,
        e.g. ``"on_login"``.

        Example usage::

            >>> client = AsyncRCONClient()
            >>> @client.listen()
            ... async def on_login():
            ...     print("We have logged in!")

        :param event:
            The event to listen for. If ``None``, the function name
            is used as the event name.

        """

        def decorator(func: Hook):
            self.add_listener(event or func.__name__, func)
            return func

        return decorator
