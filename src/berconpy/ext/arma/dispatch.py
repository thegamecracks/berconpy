from typing import Any

from berconpy.dispatch import EventDispatcher, typed_event

from .player import Player


class ArmaDispatcher(EventDispatcher):
    """An event dispatcher for :py:class:`ArmaClient`."""

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

        The :py:attr:`~berconpy.client.ArmaClient.players` list will
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

        The :py:attr:`~berconpy.client.ArmaClient.players` list will
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
