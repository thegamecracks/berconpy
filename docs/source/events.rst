Event Reference
===============

All events dispatched by :py:class:`~AsyncRCONClient` are documented here.
To listen for one of the following events, use the :py:meth:`~AsyncRCONClient.add_listener()`
method or the :py:meth:`~AsyncRCONClient.listen()` decorator.

.. py:function:: on_raw_event(packet: ServerPacket)

    Fired for every parsable packet received by the server.

    :param ServerPacket packet:
        The packet that was received.
        This will be one of the three subclasses of
        :py:class:`~protocol.ServerPacket`.

.. py:function:: on_login()

    Fired after a successful login to the server.

.. py:function:: on_command(response: str)

    Fired after receiving any command response from the server.
    This should only be used for debugging purposes as the
    :py:meth:`~AsyncRCONClient.send_command()` method already
    returns the server's response.

    :param str response: The response received by the server.

.. py:function:: on_message(message: str)

    Fired for messages sent by the server, e.g. player connections.
    More specific events such as :py:func:`on_admin_login`
    are dispatched from this event.

    :param str response: The message that was sent by the server.

.. py:function:: on_admin_login(admin_id: int, addr: str)

    Fired when a RCON admin logs into the server.
    The first message received will be our client
    logging in.

    .. note::

        This event has no logout equivalent as the server does not
        send messages for admins logging out.

    :param int admin_id: The ID of the admin that logged into the server.
    :param str addr: The admin's IP and port.

.. py:function:: on_player_connect(player: ~player.Player)

    Fired when a player connects to a server.

    .. note::

        The player's :py:attr:`~player.Player.guid` will most likely be
        an empty string since the server sends the GUID in
        a separate message briefly afterwards. To wait for the GUID
        to be provided, see the :py:func:`on_player_guid` event.

    :param ~player.Player player: The player that connected to the server.

.. py:function:: on_player_guid(player: ~player.Player)

    Fired when receiving the BattlEye GUID for a connecting player.
    The given player object will have the updated GUID.

    :param ~player.Player player: The player whose GUID was updated.

.. py:function:: on_player_verify_guid(player: ~player.Player)

    Fired when the server has verified the BattlEye GUID
    for a connecting player.

    :param ~player.Player player: The player whose GUID was verified.

.. py:function:: on_player_disconnect(player: ~player.Player)

    Fired when a player manually disconnects from the server.

    The :py:attr:`~AsyncRCONClient.players` list will
    no longer contain the player provided here.

    This event does not fire when BattlEye kicks the player;
    for that, see the following event :py:func:`on_player_kick()`.

    :param ~player.Player player: The player that disconnected.

.. py:function:: on_player_kick(player: ~player.Player, reason: str)

    Fired when BattlEye kicks a player either automatically
    (e.g. ``"Client not responding"``) or by an admin (i.e. ``"Admin Kick"``).

    The :py:attr:`~AsyncRCONClient.players` list will
    no longer contain the player provided here.

    :param ~player.Player player: The player that was kicked.
    :param str reason: The reason for the player being kicked.

.. py:function:: on_admin_message(admin_id: int, channel: str, message: str)

    Fired when an RCON admin sends a message.

    If the ``channel`` is ``"Global"``, the :py:func:`on_admin_announcement()`
    event is dispatched alongside this event.

    If the ``channel`` starts with ``"To "``, the :py:func:`on_admin_whisper()`
    event is also dispatched.

    :param int admin_id: The ID of the admin that sent the message.
    :param str channel: The name of the channel the message was sent to.
    :param str message: The message that was sent by the admin.

.. py:function:: on_admin_announcement(admin_id: int, message: str)

    Fired when an RCON admin sends a global message.

    :param int admin_id: The ID of the admin that sent the message.
    :param str message: The message that was sent by the admin.

.. py:function:: on_admin_whisper(player: ~player.Player, admin_id: int, message: str)

    Fired when an RCON admin sends a message to a specific player.

    .. note::

        This event may potentially not get dispatched if the player's name
        could not be found in the client's cache.

    :param ~player.Player player: The player that the message was directed towards.
    :param int admin_id: The ID of the admin that sent the message.
    :param str message: The message that was sent by the admin.

.. py:function:: on_player_message(player: ~player.Player, channel: str, message: str)

    Fired when a player sends a message.

    :param ~player.Player player: The player that the message was directed towards.
    :param str channel: The name of the channel the message was sent to.
    :param str message: The message that was sent by the admin.
