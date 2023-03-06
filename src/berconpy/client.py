from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable, Type, TypeVar

from .cache import RCONClientCache
from .dispatch import EventDispatcher
from .events import (
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
    parse_players,
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
        cache_cls: Type[RCONClientCache],
        dispatch: EventDispatcher,
    ):
        self.cache = cache_cls(self)
        self.dispatch = dispatch
        self.dispatch.add_listener("on_message", self.on_message)

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
    def fetch_admins(self) -> list[tuple[int, str]] | Awaitable[list[tuple[int, str]]]:
        """Requests a list of RCON admins connected to the server,
        ordered by admin ID and IP address with port.
        """

    @abstractmethod
    def fetch_bans(self) -> list[Ban] | Awaitable[list[Ban]]:
        """Requests a list of bans on the server."""

    @abstractmethod
    def fetch_missions(self) -> list[str] | Awaitable[list[str]]:
        """Requests a list of mission files on the server."""

    @abstractmethod
    def fetch_players(self) -> list[Player] | Awaitable[Player]:
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

        """
        return self.send_command(f"kick {player_id:d} {reason}".rstrip())

    def send(self, message: str) -> str | Awaitable[str]:
        """Sends a message to all players in the server.

        :param message: The message to send.
        :returns: The response from the server, if any.

        """
        return self.send_command(f"say -1 {message}")

    def unban(self, ban_id: int) -> str | Awaitable[str]:
        """Removes the ban with the given ID from the server.

        :param ban_id: The ID of the ban to remove.
        :returns: The response from the server, if any.

        """
        return self.send_command(f"removeBan {ban_id:d}")

    def whisper(self, player_id: int, message: str) -> str | Awaitable[str]:
        """Sends a message to the player with the given ID.

        :py:meth:`Player.send()` is a shorthand for calling this method.

        :param player_id: The ID of the player to send to.
        :param message: The message to send.
        :returns: The response from the server, if any.

        """
        return self.send_command(f"say {player_id:d} {message}")

    def _is_disallowed_command(self, response: str) -> bool:
        return response == "Disallowed command"

    def _parse_admins(self, response: str) -> list[tuple[int, str]]:
        return [(admin["id"], admin["addr"]) for admin in parse_admins(response)]

    def _parse_bans(self, response: str, *, cls: Type[BanT]) -> list[BanT]:
        return [
            cls(self.cache, b["index"], b["ban_id"], b["duration"], b["reason"])
            for b in parse_bans(response)
        ]

    def _parse_missions(self, response: str) -> list[str]:
        lines = response.splitlines()
        lines.pop(0)  # "Missions on server:"
        return lines

    # Event dispatcher

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

    def on_message(self, response: str):
        if m := AdminConnect.try_from_message(response):
            self.dispatch("admin_login", m.id, m.addr)

        elif m := PlayerConnect.try_from_message(response):
            p = self.cache.add_connected_player(m)
            self.dispatch("player_connect", p)

        elif m := PlayerGUID.try_from_message(response):
            # NOTE: it might be possible to receive these events before
            # on_player_connect, in which case we cannot get a Player
            # object to dispatch
            if p := self.cache.set_player_guid(m):
                self.dispatch("player_guid", p)

        elif m := PlayerVerifyGUID.try_from_message(response):
            if p := self.cache.verify_player_guid(m):
                self.dispatch("player_verify_guid", p)

        elif m := PlayerDisconnect.try_from_message(response):
            if p := self.cache.remove_player(m.id):
                self.dispatch("player_disconnect", p)

        elif m := PlayerKick.try_from_message(response):
            if p := self.cache.remove_player(m.id):
                self.dispatch("player_kick", p, m.reason)

        elif m := RCONMessage.try_from_message(response):
            self.dispatch("admin_message", m.id, m.channel, m.message)

            if m.channel == "Global":
                self.dispatch("admin_announcement", m.id, m.message)
            elif m.channel.startswith("To "):
                name = m.channel.removeprefix("To ")
                p = utils.get(self.cache.players, name=name)
                if p is not None:
                    self.dispatch("admin_whisper", p, m.id, m.message)

        elif m := PlayerMessage.try_from_message(response):
            p = utils.get(self.cache.players, name=m.name)
            if p is not None:
                self.dispatch("player_message", p, m.channel, m.message)

        elif not is_expected_message(response):
            raise ValueError(f"unexpected server message: {response}")

    def _update_players(self, response: str) -> None:
        """Updates the cache from a server response to the "players" admin command."""
        current_ids = set()
        for player in parse_players(response):
            p = self.cache.get_player(player["id"])
            if p is None:
                self.cache.add_missing_player(player)
            else:
                p._update(**player)

            current_ids.add(player["id"])

        # Throw away players no longer in the server
        previous_ids = set(p.id for p in self.cache.players)
        for missing in previous_ids - current_ids:
            self.cache.remove_player(missing)
