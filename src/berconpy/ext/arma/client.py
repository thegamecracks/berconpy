import logging

from berconpy import AsyncRCONClient

log = logging.getLogger(__name__)


class AsyncArmaRCONClient(AsyncRCONClient):
    """An AsyncRCONClient subclass that adds more methods for handling Arma RCON."""

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
            :py:meth:`~berconpy.AsyncRCONClient.close()` method.

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
            :py:meth:`~berconpy.AsyncRCONClient.close()` method.

        """
        return await self.send_command("#shutdown")

    async def unlock_server(self) -> str:
        """Unlocks the server and allows new players to join."""
        return await self.send_command("#unlock")
