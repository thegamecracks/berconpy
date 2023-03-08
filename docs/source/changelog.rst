Changelog
=========

.. contents::
  :depth: 2
  :local:

1.1.1
-----

Bug Fixes
^^^^^^^^^

* Fix :py:exc:`AttributeError` when attempting to convert a :py:class:`Ban`
  instance into a string

Miscellaneous
^^^^^^^^^^^^^

* Rename the *Getting Started* page to :doc:`/intro`
* Add section about logging in the :doc:`/intro` guide
* Clean up table of contents
* Fix docs/ Makefile building in the wrong directory

1.1.0
-----

Bug Fixes
^^^^^^^^^

* Fix the user's current task being cancelled when
  :py:meth:`AsyncRCONClient.close()` is called

Documentation
^^^^^^^^^^^^^

* Add Getting Started guide
* Add various clarifications and examples throughout the API reference

v1.0.0.post1
------------

This version comes with a new `online documentation`_ providing an
:py:class:`Event Reference <berconpy.dispatch.EventDispatcher>` and
API reference for the various classes and methods in the library.

.. _online documentation: https://github.com/thegamecracks/berconpy/commit/82405b5464dce90618d8973dd0c1d5e21f7d96c3

v1.0.0
------

This is the first release to be published on PyPI!

Breaking Changes
^^^^^^^^^^^^^^^^

* Cancel the current task when the connection stops

  This prevents the body of ``async with client.connect():`` continuing to run,
  even if the client is no longer running.

* Remove the ``name`` parameter from :py:class:`AsyncRCONClient`

  This attribute is probably no longer necessary for logging purposes.

Bug Fixes
^^^^^^^^^

* Fix :py:meth:`AsyncRCONClient.wait_for()` hanging when the predicate returns
  ``False``
* Fix potential :py:exc:`~asyncio.InvalidStateError` when a command times out
  and receives a response at the same time
* Fix protocol not resetting its own state when an error occurs
* Fix protocol silently failing due to an :py:exc:`OSError` (`GH-2`_)
* Fix BattlEye kicks for players without GUIDs not being parsed correctly

.. _GH-2: https://github.com/thegamecracks/berconpy/issues/2

Miscellaneous
^^^^^^^^^^^^^

* Tweak logging levels used during protocol's lifetime
* Wait for three seconds before applying exponential backoff during a
  connection (re)attempt

v0.2.1
------

New Features
^^^^^^^^^^^^

* Add facade methods to :py:class:`AsyncRCONClient` for
  :py:meth:`~AsyncRCONClient.is_running()`,
  :py:meth:`~AsyncRCONClient.is_connected()`,
  and :py:meth:`~AsyncRCONClient.is_logged_in()`.

Miscellaneous
^^^^^^^^^^^^^

* Minor docstring tweaks for :py:class:`AsyncRCONClient`

v0.2.0
------

Breaking Changes
^^^^^^^^^^^^^^^^

* Refactor the :py:class:`Packet` into refinement types::

  * :py:class:`ClientPacket`
  * :py:class:`ClientLoginPacket`
  * :py:class:`ClientCommandPacket`
  * :py:class:`ClientMessagePacket`
  * :py:class:`ServerPacket`
  * :py:class:`ServerLoginPacket`
  * :py:class:`ServerCommandPacket`
  * :py:class:`ServerMessagePacket`

  These classes improve type inference, reduces their constructor signatures,
  and help self-document what kind of packets are expected to be sent around
  each internal method.

* :py:meth:`Packet.from_bytes()` now can raise :py:exc:`IndexError`
* :py:class:`Packet` constructor now raises :py:exc:`ValueError`
  when exceeding max packet size

New Features
^^^^^^^^^^^^

* Use sequence number from server messages to avoid re-triggering ``on_message``
  events in case of network instability
* Add ``berconpy.ext`` namespace package for third-party extension support
* Add :py:mod:`berconpy.ext.arma` extension containing an
  :py:class:`~berconpy.ext.arma.AsyncArmaRCONClient` subclass with methods
  specific to the Arma game series

* Add new events::

  * ``on_admin_login(admin_id, addr)``
  * ``on_player_connect(player)``
  * ``on_player_guid(player)``
  * ``on_player_verify_guid(player)``
  * ``on_player_disconnect(player_id, name)``
  * ``on_player_kick(player, reason)``
  * ``on_admin_message(admin_id, channel, message)``
  * ``on_admin_announcement(admin_id, message)``
  * ``on_admin_whisper(player, admin_id, message)``
  * ``on_player_message(player, channel, message)``

* Add :py:class:`Player` class and player cache to the client, accessed with
  the :py:attr:`AsyncRCONClient.players` property
  and the :py:meth:`~AsyncRCONClient.get_player()` method
* After successfully connecting once, :py:class:`AsyncRCONClient`
  will indefinitely attempt to reconnect when the connection is lost
* Exponential backoff to reduce excessive connection attempts

* New exceptions have been added to replace :py:exc:`ValueError`
  and :py:exc:`RuntimeError` in various locations::

  * :py:exc:`RCONError`
  * :py:exc:`LoginFailure`
  * :py:exc:`RCONCommandError`

* Add :py:attr:`AsyncRCONClient.client_id` property

* Add new methods to :py:class:`AsyncRCONClient`::

  * :py:meth:`~AsyncRCONClient.ban()`
  * :py:meth:`~AsyncRCONClient.fetch_admins()`
  * :py:meth:`~AsyncRCONClient.fetch_bans()`
  * :py:meth:`~AsyncRCONClient.fetch_missions()`
  * :py:meth:`~AsyncRCONClient.fetch_players()`
  * :py:meth:`~AsyncRCONClient.kick()`
  * :py:meth:`~AsyncRCONClient.send()`
  * :py:meth:`~AsyncRCONClient.unban()`
  * :py:meth:`~AsyncRCONClient.whisper()`

* Add a :py:class:`Ban` dataclass which is returned by
  :py:meth:`AsyncRCONClient.fetch_bans()`

Bug Fixes
^^^^^^^^^

* Fix :py:exc:`RuntimeError` when sending a command fails on the first attempt
* Fix protocol hanging indefinitely when the server times out
* Fix temporary listeners not being removed after they are invoked
* Fix :py:exc:`AttributeError` when protocol closes before having connected
* Fix potential :py:exc:`asyncio.CancelledError` when calling
  :py:meth:`AsyncRCONClient.send_command()`
* Fix protocol parsing messages from addresses other than the connected server
* Fix protocol not acknowledging messages when reconnecting
* Fix ``on_command`` event potentially being called more than once for
  multiple responses to the same command

Miscellaneous
^^^^^^^^^^^^^

* Add logging configuration to
  `repl.py <https://github.com/thegamecracks/berconpy/blob/v0.2.0/examples/repl.py>`__
* Add repr to :py:class:`AsyncRCONClient`

v0.1.0
------

New Features
^^^^^^^^^^^^

* Finish implementation for :py:meth:`AsyncRCONClient.wait_for()`

Bug Fixes
^^^^^^^^^

* Fix :py:meth:`AsyncRCONClient.send_command()` returning :py:class:`bytes`
  instead of :py:class:`str`

Miscellaneous
^^^^^^^^^^^^^

* Add `repl.py <https://github.com/thegamecracks/berconpy/blob/v0.1.0/examples/repl.py>`__
  example

v0.0.1
------

This is the first version of berconpy, providing the initial implementation
for the :py:class:`AsyncRCONClient`, :py:class:`Packet`, and
``RCONClientDatagramProtocol`` classes.
