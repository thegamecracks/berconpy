Changelog
=========

.. contents::
  :depth: 2
  :local:

v3.0.0
------

This is a large rewrite of the library to allow using BattlEye RCON by itself
without Arma 3-specific features, and will break the majority of existing
code for users. For the time being, this will be the only way to use berconpy with
Arma Reforger. If you have any code using this library that you cannot migrate to
the new version for, please pin your version to ``berconpy~=2.1``. Sorry!

For contributors, nearly all abstract base classes have been removed, and the
asynchronous implementation has been hoisted to the top-level package.
Any alternative I/O implementations are now free to declare their own
caching, events, and data models for bans/players.

No changes were made to the Sans-I/O protocol at :py:mod:`berconpy.protocol`,
and its hoisted classes like :py:class:`berconpy.RCONClientProtocol` are preserved.

Renamed
^^^^^^^

* ``berconpy.AsyncEventDispatcher`` to :py:class:`berconpy.ArmaDispatcher`
* ``berconpy.AsyncRCONClient`` to :py:class:`berconpy.ArmaClient`
* ``berconpy.AsyncRCONClientCache`` to :py:class:`berconpy.ArmaCache`
* ``berconpy.ext.arma.AsyncArmaRCONClient`` to :py:class:`berconpy.ext.arma.ArmaClient`

To improve backwards compatibility, aliases are defined for old names which will
trigger a warning when used.

Removed
^^^^^^^

* ``berconpy.asyncio`` package
* ``berconpy.cache`` package and ``RCONClientCache``
* ``berconpy.RCONClient.cache`` parameter and attribute
* ``berconpy.RCONClient`` abstract methods related to Arma, like ``fetch_players()``
* ``berconpy.EventDispatcher`` events related to Arma, like ``on_player_message``
* ``berconpy.ConnectorConfig.players_interval`` attribute,
  only defined for :py:class:`berconpy.ArmaConnectorConfig`

Other Breaking Changes
^^^^^^^^^^^^^^^^^^^^^^

* Converted :py:class:`berconpy.RCONClient` to a concrete class,
  with implementations extracted from ``AsyncRCONClient``
* Converted :py:class:`berconpy.EventDispatcher` to a concrete class,
  with implementations extracted from ``AsyncEventDispatcher``
* Added :py:attr:`berconpy.RCONClient.protocol` parameter and attribute
* :py:class:`berconpy.AsyncClientConnector` no longer sends the ``players``
  command for keep alives, and this behaviour is now reserved for the new
  :py:class:`berconpy.ArmaConnector` class
* :py:class:`berconpy.Ban` and :py:class:`berconpy.Player` now work only with
  Arma-specific classes and cannot be used with :py:class:`berconpy.RCONClient`
* Switched build backend from ``setuptools`` to ``uv-build``

  This should not have any visible changes for end users, only contributors that
  want to work on the project. This also means the package will no longer use
  ``setuptools-scm`` for Git-based dynamic versioning.

* Removed all dependency extras: ``docs``, ``tests``, ``types``

  These extras provided dependencies that were only useful for development,
  such as docs generation and running tests. Now, attempting to install these
  extras (for example, ``pip install berconpy[docs]``) may result in a warning
  or an error message depending on your package manager.

  For contributors, these dependencies were moved to `Dependency Groups <https://packaging.python.org/en/latest/specifications/dependency-groups/>`__,
  and can be installed when working on the repository directly, for example,
  ``pip install . --group dev`` or ``uv sync --group dev``.

Added
^^^^^

* :py:class:`berconpy.LoginRefused` and :py:class:`berconpy.LoginTimeout`
  which subclasses :py:class:`berconpy.LoginFailure` to allow distinguishing
  when a server does not respond to a login attempt versus the server actively
  refusing it. :py:class:`berconpy.LoginTimeout` additionally inherits from
  :py:class:`asyncio.TimeoutError` (or :py:class:`TimeoutError` in Python 3.11+).

v2.1.4
------

Bug Fixes
^^^^^^^^^

* Fix possible (but minor) memory leak when using
  :py:meth:`AsyncRCONClient.wait_for() <berconpy.AsyncRCONClient.wait_for>`
  to wait on a non-predefined event
* Fix potential :py:exc:`~berconpy.InvalidStateError` while sending a command
  if :py:class:`~berconpy.AsyncRCONClient` disconnects before a response is received
* Fix players potentially being fetched more than once during login
  if cache is already populated
* Fix ``Config entry:`` server messages causing superfluous errors

v2.1.3
------

Bug Fixes
^^^^^^^^^

* Remove unnecessary ``wheel`` build dependency

* Add missing ``py.typed`` marker to comply with `PEP 561`_
  distribution of type information

Documentation
^^^^^^^^^^^^^

* Fix typo in :py:class:`berconpy.Ban` docstring

* Explicitly document coroutine listener support in
  :py:class:`~berconpy.EventDispatcher`

.. _PEP 561: https://peps.python.org/pep-0561/

v2.1.1
------

Bug Fixes
^^^^^^^^^

* Fix :py:class:`~berconpy.NonceCheck` not raising ValueError
  when ``max_size`` exceeds 255

* Ignore more known server messages in :py:class:`~berconpy.client.RCONClient`

  * Ban check timed out, no response from BE Master
  * Disconnected from BE Master
  * Failed to resolve BE Master DNS name(s)

v2.1.0
------

New Features
^^^^^^^^^^^^

* Add type-safe decorators to :py:class:`~berconpy.dispatch.EventDispatcher`
  for existing events

  This serves as an alternative interface to the existing
  :py:meth:`~berconpy.AsyncRCONClient.listen()`
  and :py:meth:`~berconpy.AsyncRCONClient.add_listener()` methods for those
  that want stronger type safety in their code (avoiding string typos and
  validating listener signatures).

Bug Fixes
^^^^^^^^^

* Hide stderr clutter from ``berconpy-keep-alive`` tasks failing to send
  commands

Documentation
^^^^^^^^^^^^^

* Document :py:meth:`~berconpy.RCONClientProtocol.receive_datagram()`
  for client/server protocols potentially raising :py:exc:`~berconpy.InvalidStateError`

v2.0.0
------

This is a major rewrite of the library to increase the flexibility and
re-usability of components. Many new abstractions have been introduced
between the protocol, I/O layers, and the client.

Breaking Changes
^^^^^^^^^^^^^^^^

* :py:class:`Packet <berconpy.protocol.Packet>` and its subclasses are now
  only available through the :doc:`berconpy.protocol </protocol>` package
* :py:attr:`Packet.message <berconpy.protocol.Packet.message>` property now
  returns bytes
* :py:meth:`Packet.from_bytes() <berconpy.protocol.Packet.from_bytes>`
  no longer raises :py:exc:`IndexError`
* :py:class:`ServerCommandPacket <berconpy.protocol.ServerCommandPacket>`
  now raises :py:exc:`ValueError` when ``total`` is 0 or ``index`` is out
  of bounds
* :py:attr:`AsyncRCONClient.client_id <berconpy.AsyncRCONClient.admin_id>`
  has been renamed to :py:attr:`~berconpy.AsyncRCONClient.admin_id`
* :py:class:`RCONClientDatagramProtocol` is now replaced with
  :py:class:`~berconpy.AsyncClientConnector`
* The ``protocol_cls`` parameter for :py:class:`~berconpy.AsyncRCONClient`
  has been replaced with ``protocol`` and must take an
  :py:class:`~berconpy.AsyncClientProtocol` instance

New Features
^^^^^^^^^^^^

* Add `Sans-I/O <https://sans-io.readthedocs.io/>`__ client and server
  implementations of the RCON protocol:

  * :py:class:`~berconpy.RCONGenericProtocol`
  * :py:class:`~berconpy.RCONClientProtocol`
  * :py:class:`~berconpy.RCONServerProtocol`

* Add Sans-I/O base classes, inherited by their original asyncio components:

  * :py:class:`~berconpy.client.RCONClient`
  * :py:class:`~berconpy.ban.Ban`
  * :py:class:`~berconpy.player.Player`

* Allow customization of the client cache by using a subclass of
  :py:class:`~berconpy.cache.RCONClientCache`

* Allow customization of keep alive messages, reconnect parameters,
  and command handling for :py:class:`~berconpy.AsyncClientConnector`
  using :py:class:`~berconpy.ConnectorConfig`
  and :py:class:`~berconpy.AsyncCommander`

* Add send/receive support for UTF-8 encoding

  Despite the :download:`BattlEye RCON protocol </BERConProtocol.txt>`
  specifying that payloads be encoded in ASCII, RCON servers are willing
  to send UTF-8 encoded text back. As such, this library will begin
  processing strings in UTF-8.

* Improve validation of server responses to commands

  * Indexes must be within range
  * Indexes must not be repeated
  * Total must be consistent across associated packets

Bug Fixes
^^^^^^^^^

* Fix :py:attr:`Ban.index <berconpy.Ban.index>` not actually being stored
  as an integer

Miscellaneous
^^^^^^^^^^^^^

* Show full traceback for malformed data being received when
  using DEBUG logging level
* Add this changelog to the documentation

v1.1.1
------

Bug Fixes
^^^^^^^^^

* Fix :py:exc:`AttributeError` when attempting to convert a
  :py:class:`~berconpy.Ban` instance into a string

Miscellaneous
^^^^^^^^^^^^^

* Rename the *Getting Started* page to :doc:`/intro`
* Add section about logging in the :doc:`/intro` guide
* Clean up table of contents
* Fix docs/ Makefile building in the wrong directory

v1.1.0
------

Bug Fixes
^^^^^^^^^

* Fix the user's current task being cancelled when
  :py:meth:`AsyncRCONClient.close() <berconpy.AsyncRCONClient.close>` is called

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

* Remove the ``name`` parameter from :py:class:`~berconpy.AsyncRCONClient`

  This attribute is probably no longer necessary for logging purposes.

Bug Fixes
^^^^^^^^^

* Fix :py:meth:`AsyncRCONClient.wait_for() <berconpy.AsyncRCONClient.wait_for>`
  hanging when the predicate returns ``False``
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

* Add facade methods to :py:class:`~berconpy.AsyncRCONClient`:

  * :py:meth:`~berconpy.AsyncRCONClient.is_running()`
  * :py:meth:`~berconpy.AsyncRCONClient.is_connected()`
  * :py:meth:`~berconpy.AsyncRCONClient.is_logged_in()`

Miscellaneous
^^^^^^^^^^^^^

* Minor docstring tweaks for :py:class:`~berconpy.AsyncRCONClient`

v0.2.0
------

Breaking Changes
^^^^^^^^^^^^^^^^

* Refactor the :py:class:`~berconpy.protocol.Packet` into refinement types:

  * :py:class:`~berconpy.protocol.ClientPacket`
  * :py:class:`~berconpy.protocol.ClientLoginPacket`
  * :py:class:`~berconpy.protocol.ClientCommandPacket`
  * :py:class:`~berconpy.protocol.ClientMessagePacket`
  * :py:class:`~berconpy.protocol.ServerPacket`
  * :py:class:`~berconpy.protocol.ServerLoginPacket`
  * :py:class:`~berconpy.protocol.ServerCommandPacket`
  * :py:class:`~berconpy.protocol.ServerMessagePacket`

  These classes improve type inference, reduces their constructor signatures,
  and help self-document what kind of packets are expected to be sent around
  each internal method.

* :py:meth:`Packet.from_bytes() <berconpy.protocol.Packet.from_bytes>`
  can now raise :py:exc:`IndexError`
* :py:class:`~berconpy.protocol.Packet` constructor now raises
  :py:exc:`ValueError` when exceeding max packet size

New Features
^^^^^^^^^^^^

* Use sequence number from server messages to avoid re-triggering ``on_message``
  events in case of network instability
* Add ``berconpy.ext`` namespace package for third-party extension support
* Add :doc:`berconpy.ext.arma </ext/arma>` extension containing an
  :py:class:`~berconpy.ext.arma.ArmaClient` subclass with methods
  specific to the Arma game series

* Add new events:

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

* Add :py:class:`~berconpy.Player` class and player cache to the client,
  accessed with the :py:attr:`AsyncRCONClient.players <berconpy.AsyncRCONClient.players>`
  property and the :py:meth:`~berconpy.AsyncRCONClient.get_player()` method
* After successfully connecting once, :py:class:`~berconpy.AsyncRCONClient`
  will indefinitely attempt to reconnect when the connection is lost
* Exponential backoff to reduce excessive connection attempts

* New exceptions have been added to replace :py:exc:`ValueError`
  and :py:exc:`RuntimeError` in various locations:

  * :py:exc:`~berconpy.RCONError`
  * :py:exc:`~berconpy.LoginFailure`
  * :py:exc:`~berconpy.RCONCommandError`

* Add :py:attr:`AsyncRCONClient.client_id <berconpy.AsyncRCONClient.client_id>` property

* Add new methods to :py:class:`~berconpy.AsyncRCONClient`:

  * :py:meth:`~berconpy.AsyncRCONClient.ban()`
  * :py:meth:`~berconpy.AsyncRCONClient.fetch_admins()`
  * :py:meth:`~berconpy.AsyncRCONClient.fetch_bans()`
  * :py:meth:`~berconpy.AsyncRCONClient.fetch_missions()`
  * :py:meth:`~berconpy.AsyncRCONClient.fetch_players()`
  * :py:meth:`~berconpy.AsyncRCONClient.kick()`
  * :py:meth:`~berconpy.AsyncRCONClient.send()`
  * :py:meth:`~berconpy.AsyncRCONClient.unban()`
  * :py:meth:`~berconpy.AsyncRCONClient.whisper()`

* Add a :py:class:`~berconpy.Ban` dataclass which is returned by
  :py:meth:`AsyncRCONClient.fetch_bans() <berconpy.AsyncRCONClient.fetch_bans>`

Bug Fixes
^^^^^^^^^

* Fix :py:exc:`RuntimeError` when sending a command fails on the first attempt
* Fix protocol hanging indefinitely when the server times out
* Fix temporary listeners not being removed after they are invoked
* Fix :py:exc:`AttributeError` when protocol closes before having connected
* Fix potential :py:exc:`asyncio.CancelledError` when calling
  :py:meth:`AsyncRCONClient.send_command() <berconpy.AsyncRCONClient.send_command>`
* Fix protocol parsing messages from addresses other than the connected server
* Fix protocol not acknowledging messages when reconnecting
* Fix ``on_command`` event potentially being called more than once for
  multiple responses to the same command

Miscellaneous
^^^^^^^^^^^^^

* Add logging configuration to
  `repl.py <https://github.com/thegamecracks/berconpy/blob/v0.2.0/examples/repl.py>`__
* Add repr to :py:class:`~berconpy.AsyncRCONClient`

v0.1.0
------

New Features
^^^^^^^^^^^^

* Finish implementation for :py:meth:`AsyncRCONClient.wait_for() <berconpy.AsyncRCONClient.wait_for>`

Bug Fixes
^^^^^^^^^

* Fix :py:meth:`AsyncRCONClient.send_command() <berconpy.AsyncRCONClient.send_command>`
  returning :py:class:`bytes` instead of :py:class:`str`

Miscellaneous
^^^^^^^^^^^^^

* Add `repl.py <https://github.com/thegamecracks/berconpy/blob/v0.1.0/examples/repl.py>`__
  example

v0.0.1
------

This is the first version of berconpy, providing the initial implementation
for the :py:class:`~berconpy.AsyncRCONClient`, :py:class:`~berconpy.protocol.Packet`,
and :py:class:`~berconpy.RCONClientDatagramProtocol` classes.
