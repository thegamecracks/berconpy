from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable, Sequence, Type, TypeVar

from .cache import RCONClientCache
from .dispatch import EventDispatcher
from .errors import RCONCommandError
from .parser import (
    AdminConnect,
    PlayerConnect,
    PlayerGUID,
    PlayerVerifyGUID,
    PlayerDisconnect,
    PlayerKick,
    RCONMessage,
    PlayerMessage,
    is_expected_message,
    parse_admins,
    parse_bans,
)
from . import utils

if TYPE_CHECKING:
    from typing import AsyncContextManager, Awaitable, ContextManager
    from typing_extensions import Self
    from .ban import Ban
    from .player import Player

BanT = TypeVar("BanT", bound="Ban")
T = TypeVar("T")


class RCONClient(ABC):
    """The base class for all client implementations of the RCON protocol."""

    def __init__(
        self,
        *,
        cache: RCONClientCache,
        dispatch: EventDispatcher,
    ):
        """
        :param cache: The cache to use for the client.
        :param dispatch: The dispatcher object to use for transmitting events.
        """
        self.cache = cache
        self.dispatch = dispatch

        # Side effects may occur while providing references to self
        # so all attributes need to be defined above
        self.cache.client = self

        self.dispatch.on_message(self.on_message)

    @abstractmethod
    def is_logged_in(self) -> bool | None:
        """Indicates if the client is currently authenticated with the server.

        :returns:
            True if authenticated or None if no
            response has been received from the server.
        :raises LoginFailure:
            The password given to the server was denied.

        """

    @abstractmethod
    def is_connected(self) -> bool:
        """Indicates if the client has a currently active connection
        with the server.
        """

    @abstractmethod
    def is_running(self) -> bool:
        """Indicates if the client is running. This may not necessarily
        mean that the client is connected.
        """

    # Connection methods

    @abstractmethod
    def connect(
        self,
        ip: str,
        port: int,
        password: str,
    ) -> ContextManager[Self] | AsyncContextManager[Self]:
        """Returns a context manager that connects and logs into an RCON server.

        :raises LoginFailure:
            The password given to the server was denied.
        :raises RuntimeError:
            This method was called while the client is already connected.

        """

    @abstractmethod
    def close(self) -> None | Awaitable[None]:
        """Closes the connection.

        This method should be idempotent, i.e. having no effect
        when called multiple times consecutively.

        """

    # Commands
    # (documentation: https://www.battleye.com/support/documentation/)

    @abstractmethod
    def fetch_admins(self) -> Sequence[tuple[int, str]] | Awaitable[Sequence[tuple[int, str]]]:
        """Requests a list of RCON admins connected to the server,
        ordered by admin ID and IP address with port.
        """

    @abstractmethod
    def fetch_bans(self) -> Sequence[Ban] | Awaitable[Sequence[Ban]]:
        """Requests a list of bans on the server."""

    @abstractmethod
    def fetch_missions(self) -> Sequence[str] | Awaitable[Sequence[str]]:
        """Requests a list of mission files on the server."""

    @abstractmethod
    def fetch_players(self) -> Sequence[Player] | Awaitable[Sequence[Player]]:
        """Requests a list of players from the server.

        This method also updates the player cache.

        """

    @abstractmethod
    def send_command(self, command: str) -> str | Awaitable[str]:
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

    def ban(
        self,
        addr: int | str,
        duration: int | None = None,
        reason: str = "",
    ) -> str | Awaitable[str]:
        """Bans a given player ID, GUID, or IP address (without port).

        Note that the player ID cannot be used to ban players that
        are no longer in the server; a GUID or IP address must be provided.

        :py:meth:`Player.ban_ip()` and :py:meth:`Player.ban_guid()`
        should be shorthands for calling this method.

        :param addr: The ID, GUID, or IP address to ban.
        :param duration:
            The duration of the ban in minutes. If ``None``, the ban
            will be permanent.
        :param reason: An optional reason to include with the ban.
        :returns: The response from the server, if any.
        :raises RCONCommandError:
            The server has either disabled this command or failed to
            respond to our command.
        :raises RuntimeError:
            The client is either not connected or the server
            could/would not respond to the command.

        """
        command = "ban" if isinstance(addr, int) else "addBan"
        if duration is None:
            duration = 0
        return self.send_command(f"{command} {duration:d} {reason}".rstrip())

    def kick(self, player_id: int, reason: str = "") -> str | Awaitable[str]:
        """Kicks a player with the given ID from the server
        with an optional reason.

        :py:meth:`Player.kick()` is a shorthand for calling this method.

        :param player_id: The ID of the player.
        :param reason: An optional reason to show when kicking.
        :returns: The response from the server, if any.
        :raises RCONCommandError:
            The server has either disabled this command or failed to
            respond to our command.
        :raises RuntimeError:
            The client is either not connected or the server
            could/would not respond to the command.

        """
        return self.send_command(f"kick {player_id:d} {reason}".rstrip())

    def send(self, message: str) -> str | Awaitable[str]:
        """Sends a message to all players in the server.

        :param message: The message to send.
        :returns: The response from the server, if any.
        :raises RCONCommandError:
            The server has either disabled this command or failed to
            respond to our command.
        :raises RuntimeError:
            The client is either not connected or the server
            could/would not respond to the command.

        """
        return self.send_command(f"say -1 {message}")

    def unban(self, ban_id: int) -> str | Awaitable[str]:
        """Removes the ban with the given ID from the server.

        :param ban_id: The ID of the ban to remove.
        :returns: The response from the server, if any.
        :raises RCONCommandError:
            The server has either disabled this command or failed to
            respond to our command.
        :raises RuntimeError:
            The client is either not connected or the server
            could/would not respond to the command.

        """
        return self.send_command(f"removeBan {ban_id:d}")

    def whisper(self, player_id: int, message: str) -> str | Awaitable[str]:
        """Sends a message to the player with the given ID.

        :py:meth:`Player.send()` is a shorthand for calling this method.

        :param player_id: The ID of the player to send to.
        :param message: The message to send.
        :returns: The response from the server, if any.
        :raises RCONCommandError:
            The server has either disabled this command or failed to
            respond to our command.
        :raises RuntimeError:
            The client is either not connected or the server
            could/would not respond to the command.

        """
        return self.send_command(f"say {player_id:d} {message}")

    # Utilities

    def check_disallowed_command(self, response: str) -> None:
        """Raises :py:exc:`RCONCommandError` if the server responded
        with "Disallowed command".

        This method should be used when implementing :py:meth:`send_command()`.

        """
        if response == "Disallowed command":
            raise RCONCommandError("server has disabled this command")

    def parse_admins(self, response: str) -> list[tuple[int, str]]:
        """Parses an "admins" command response into a list of (IP, port) tuples.

        This method should be used when implementing :py:meth:`fetch_admins()`.

        """
        return [(admin["id"], admin["addr"]) for admin in parse_admins(response)]

    def parse_bans(self, response: str, *, cls: Type[BanT]) -> list[BanT]:
        """Parses a "bans" command response into a list of
        :py:class:`~berconpy.ban.Ban` objects.

        This method should be used when implementing :py:meth:`fetch_bans()`.

        :param response: The server response to parse.
        :param cls: The :py:class:`~berconpy.ban.Ban` subclass to use.

        """
        return [
            cls(self.cache, b["index"], b["ban_id"], b["duration"], b["reason"])
            for b in parse_bans(response)
        ]

    def parse_missions(self, response: str) -> list[str]:
        """Parses a "missions" command response into a list of mission files.

        This method should be used when implementing :py:meth:`fetch_missions()`.

        """
        lines = response.splitlines()
        lines.pop(0)  # "Missions on server:"
        return lines

    # Cache

    @property
    def admin_id(self) -> int | None:
        """A shorthand for :py:attr:`RCONClientCache.admin_id`."""
        return self.cache.admin_id

    @property
    def cache(self) -> RCONClientCache:
        """The cache used by the client."""
        return self._cache

    @cache.setter
    def cache(self, new_cache: RCONClientCache) -> None:
        self._cache = new_cache

    def get_player(self, player_id: int) -> "Player | None":
        """A shorthand for :py:meth:`RCONClientCache.get_player()`."""
        return self.cache.get_player(player_id)

    @property
    def players(self) -> "Sequence[Player]":
        """A shorthand for :py:attr:`RCONClientCache.players`."""
        return self.cache.players

    # Event dispatcher

    @property
    def dispatch(self) -> EventDispatcher:
        """The event dispatcher used by the client."""
        return self._dispatch

    @dispatch.setter
    def dispatch(self, new_dispatch: EventDispatcher) -> None:
        self._dispatch = new_dispatch

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

            >>> client = AsyncRCONClient()
            >>> @client.listen()
            ... async def on_login():
            ...     print("We have logged in!")

        :param event:
            The event to listen for. If ``None``, the function name
            is used as the event name.

        """
        return self.dispatch.listen(event)

    def on_message(self, message: str):
        """Parses a message sent from the server into various events.

        This method is automatically added as a listener on initialization.

        """
        if m := AdminConnect.try_from_message(message):
            self.dispatch.on_admin_login.fire(m.id, m.addr)

        elif m := PlayerConnect.try_from_message(message):
            p = self.cache.add_connected_player(m)
            self.dispatch.on_player_connect.fire(p)

        elif m := PlayerGUID.try_from_message(message):
            # NOTE: it might be possible to receive these events before
            # on_player_connect, in which case we cannot get a Player
            # object to dispatch
            if p := self.cache.set_player_guid(m):
                self.dispatch.on_player_guid.fire(p)

        elif m := PlayerVerifyGUID.try_from_message(message):
            if p := self.cache.verify_player_guid(m):
                self.dispatch.on_player_verify_guid.fire(p)

        elif m := PlayerDisconnect.try_from_message(message):
            if p := self.cache.remove_player(m.id):
                self.dispatch.on_player_disconnect.fire(p)

        elif m := PlayerKick.try_from_message(message):
            if p := self.cache.remove_player(m.id):
                self.dispatch.on_player_kick.fire(p, m.reason)

        elif m := RCONMessage.try_from_message(message):
            self.dispatch.on_admin_message.fire(m.id, m.channel, m.message)

            if m.channel == "Global":
                self.dispatch.on_admin_announcement.fire(m.id, m.message)
            elif m.channel.startswith("To "):
                name = m.channel.removeprefix("To ")
                p = utils.get(self.players, name=name)
                if p is not None:
                    self.dispatch.on_admin_whisper.fire(p, m.id, m.message)

        elif m := PlayerMessage.try_from_message(message):
            p = utils.get(self.players, name=m.name)
            if p is not None:
                self.dispatch.on_player_message.fire(p, m.channel, m.message)

        elif not is_expected_message(message):
            raise ValueError(f"unexpected server message: {message}")
