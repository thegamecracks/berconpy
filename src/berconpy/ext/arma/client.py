import logging

from berconpy import RCONClient, RCONCommandError

from .ban import Ban
from .cache import ArmaCache
from .dispatch import ArmaDispatcher
from .io import ArmaConnector
from .parser import parse_admins, parse_bans, parse_message
from .player import Player

log = logging.getLogger(__name__)


class ArmaClient(RCONClient):
    """An RCONClient subclass that adds more methods for handling Arma 3 RCON."""

    def __init__(
        self,
        *,
        cache: ArmaCache | None = None,
        dispatch: ArmaDispatcher | None = None,
        protocol: ArmaConnector | None = None,
    ):
        """
        :param cache:
            The cache to use for the client.
            Defaults to an instance of :py:class:`ArmaCache`.
        :param dispatch:
            The dispatcher object to use for transmitting events.
            Defaults to an instance of :py:class:`ArmaDispatcher`.
        :param protocol:
            The protocol to use for handling connections.
            Defaults to an instance of :py:class:`AsyncClientConnector`.
        """
        if cache is None:
            cache = ArmaCache()
        if dispatch is None:
            dispatch = ArmaDispatcher()
        if protocol is None:
            protocol = ArmaConnector()

        super().__init__(dispatch=dispatch, protocol=protocol)

        self.cache = cache
        self.dispatch = dispatch
        self.protocol = protocol
        self.protocol.client = self

        self.dispatch.on_message(self._handle_message)

    # Commands
    # (documentation: https://www.battleye.com/support/documentation/)

    async def send_command(self, command: str) -> str:
        response = await super().send_command(command)
        self._check_disallowed_command(response)
        return response

    async def fetch_admins(self) -> list[tuple[int, str]]:
        """Requests a list of RCON admins connected to the server,
        ordered by admin ID and IP address with port.
        """
        response = await self.send_command("admins")
        return self._parse_admins(response)

    async def fetch_bans(self) -> list[Ban]:
        """Requests a list of bans on the server."""
        response = await self.send_command("bans")
        return self._parse_bans(response)

    async def fetch_missions(self) -> list[str]:
        """Requests a list of mission files on the server."""
        response = await self.send_command("missions")
        return self._parse_missions(response)

    async def fetch_players(self) -> list[Player]:
        """Requests a list of players from the server.

        This method also updates the player cache.

        """
        response = await self.send_command("players")
        self.cache.update_players(response)
        return self.players

    async def ban(
        self,
        addr: int | str,
        duration: int | None = None,
        reason: str = "",
    ) -> str:
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
        return await self.send_command(f"{command} {duration:d} {reason}".rstrip())

    async def kick(self, player_id: int, reason: str = "") -> str:
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
        return await self.send_command(f"kick {player_id:d} {reason}".rstrip())

    async def send(self, message: str) -> str:
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
        return await self.send_command(f"say -1 {message}")

    async def unban(self, ban_id: int) -> str:
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
        return await self.send_command(f"removeBan {ban_id:d}")

    async def whisper(self, player_id: int, message: str) -> str:
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
        return await self.send_command(f"say {player_id:d} {message}")

    async def lock_server(self) -> str:
        """Locks the server and prevents new players from joining."""
        return await self.send_command("#lock")

    async def restart_and_reassign(self) -> str:
        """Restarts the mission and reassigns player roles."""
        return await self.send_command("#reassign")

    async def restart_mission(self) -> str:
        """Restarts the currently running mission."""
        return await self.send_command("#restart")

    async def restart_server(self) -> str:
        """Tells the server to restart.

        .. note::
            The client does not automatically close after this command
            is sent. If you need to prevent the client from indefinitely
            attempting to reconnect, you should call the
            :py:meth:`~berconpy.ArmaClient.close()` method.

        """
        return await self.send_command("#restartserver")

    async def select_mission(self, mission: str, difficulty: str = "") -> str:
        """Selects a new mission for the server to load.

        :param mission:
            The name of the mission to load without the file extension
            (e.g. ``"MP_Bootcamp_01.Altis"``).
        :param difficulty:
            The new difficulty to use on the server (e.g. Recruit,
            Regular, Veteran, Custom). If not provided, the current
            difficulty is reused.

        """
        return await self.send_command(f"#mission {mission} {difficulty}".rstrip())

    async def shutdown_server(self) -> str:
        """Tells the server to shut down.

        .. note::
            The client does not automatically close after this command
            is sent. If you need to prevent the client from indefinitely
            attempting to reconnect, you should call the
            :py:meth:`~berconpy.ArmaClient.close()` method.

        """
        return await self.send_command("#shutdown")

    async def unlock_server(self) -> str:
        """Unlocks the server and allows new players to join."""
        return await self.send_command("#unlock")

    # Cache

    @property
    def admin_id(self) -> int | None:
        """A shorthand for :py:attr:`ArmaCache.admin_id`."""
        return self.cache.admin_id

    @property
    def cache(self) -> ArmaCache:
        """The cache used by the client."""
        return self._cache

    @cache.setter
    def cache(self, new_cache: ArmaCache) -> None:
        self._cache = new_cache

    def get_player(self, player_id: int) -> "Player | None":
        """A shorthand for :py:meth:`ArmaCache.get_player()`."""
        return self.cache.get_player(player_id)

    @property
    def players(self) -> list[Player]:
        """A shorthand for :py:attr:`ArmaCache.players`."""
        return self.cache.players

    # Utilities

    def _check_disallowed_command(self, response: str) -> None:
        """Raises :py:exc:`RCONCommandError` if the server responded
        with "Disallowed command".

        This method should be used when implementing :py:meth:`send_command()`.

        """
        if response == "Disallowed command":
            raise RCONCommandError("server has disabled this command")

    def _handle_message(self, message: str) -> None:
        """Parses and dispatches events based on messages received from the server."""
        try:
            parse_message(self.cache, self.dispatch, message)
        except ValueError as e:
            log.warning(e)

    def _parse_admins(self, response: str) -> list[tuple[int, str]]:
        """Parses an "admins" command response into a list of (IP, port) tuples.

        This method should be used when implementing :py:meth:`fetch_admins()`.

        """
        return [(admin["id"], admin["addr"]) for admin in parse_admins(response)]

    def _parse_bans(self, response: str) -> list[Ban]:
        """Parses a "bans" command response into a list of
        :py:class:`~berconpy.ban.Ban` objects.

        This method should be used when implementing :py:meth:`fetch_bans()`.

        :param response: The server response to parse.
        :param cls: The :py:class:`~berconpy.ban.Ban` subclass to use.

        """
        return [
            Ban(self.cache, b["index"], b["ban_id"], b["duration"], b["reason"])
            for b in parse_bans(response)
        ]

    def _parse_missions(self, response: str) -> list[str]:
        """Parses a "missions" command response into a list of mission files.

        This method should be used when implementing :py:meth:`fetch_missions()`.

        """
        lines = response.splitlines()
        lines.pop(0)  # "Missions on server:"
        return lines
