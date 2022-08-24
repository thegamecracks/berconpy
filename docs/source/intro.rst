Introduction
============

This guide will go through installing **berconpy** and using it to connect
to a server, send commands, and receive messages.

Requirements
------------

The minimum Python version required is **3.10**.
No other external dependencies are required.

Installation
------------

This library can be installed from PyPI using one of the following commands:

.. code-block:: sh

    # Linux/macOS
    python3 -m pip install berconpy

    # Windows
    py -m pip install berconpy

To install the development version of the library, you can download
it from GitHub directly:

.. code-block:: sh

    # Windows
    py -m pip install git+https://github.com/thegamecracks/berconpy

.. note::

    The above command requires Git_ to be installed.

.. _Git: https://git-scm.com/

Basic Usage
-----------

The primary class berconpy offers is the :py:class:`~berconpy.AsyncRCONClient`,
which provides an interface over the underlying protocol and allows you to
register event listeners and send commands to the BattlEye RCON server.

Sending commands
^^^^^^^^^^^^^^^^

Let's start with an example of how to send a command:

.. code:: python

    import asyncio
    import berconpy as rcon

    IP_ADDR = 'XXX.XXX.XXX.XXX'
    PORT = 9999
    PASSWORD = 'ASCII_PASSWORD'

    client = rcon.AsyncRCONClient()

    async def main():
        async with client.connect(IP_ADDR, PORT, PASSWORD):
            response = await client.send_command('players')
            print(response)

    asyncio.run(main())

.. note::

    The RCON IP address, port, and password can be found in your server's
    ``BEServer.cfg`` / ``BEServer_x64.cfg``.

1. ``client = rcon.AsyncRCONClient()`` creates the client instance.
   No arguments are necessary, but you can set up event listeners
   on the client before beginning any connection which will be
   demonstrated afterwards.

2. ``async with client.connect(IP_ADDR, PORT, PASSWORD)`` attempts to connect
   and log into the RCON server. The context manager also keeps the connection
   alive until you exit it, or an error occurs.

3. ``response = await client.send_command('players')`` requests the
   players currently connected to the server and returns a string.

:py:meth:`~berconpy.AsyncRCONClient.send_command()` provides a low-level
method for sending commands. Certain commands are already available as methods,
like :py:meth:`~berconpy.AsyncRCONClient.fetch_players()` and
:py:meth:`~berconpy.AsyncRCONClient.whisper()`.
The `BattlEye documentation`_ describes server-side commands that can
be sent with ``send_command()``.

Event listeners
^^^^^^^^^^^^^^^

There are several events you can listen to handle messages sent by the server
in real-time. Below is an example of displaying in-game messages from players:

.. code:: python

    import asyncio
    import math
    import berconpy as rcon

    IP_ADDR = 'XXX.XXX.XXX.XXX'
    PORT = 9999
    PASSWORD = 'ASCII_PASSWORD'

    client = rcon.AsyncRCONClient()

    @client.listen()
    async def on_player_message(player: rcon.Player, channel: str, message: str):
        print(f'({channel}) {player.name}: {message}')

    async def main():
        async with client.connect(IP_ADDR, PORT, PASSWORD):
            await asyncio.sleep(math.inf)  # Keep client alive indefinitely

    asyncio.run(main())

The :py:meth:`@client.listen() <berconpy.AsyncRCONClient.listen>` decorator
adds a function as a listener which the client dispatches when the appropriate
event is received from the server. The function name in this example determines
what event to listen to, but you can also specify the event as a string argument.
For a full list of events, see the :doc:`/events`.

You might have also noticed in the listener that it receives a
:py:class:`~berconpy.Player` instance as its first argument.
The client instance manages a cache of players which makes it easier to
perform operations on different players like whispering and kicking.
A list of players can be retrieved through the
:py:attr:`~berconpy.AsyncRCONClient.players` property.

Configuring Logging
-------------------

**berconpy** allows logging information about the protocol and the client
during runtime with the built-in :py:mod:`logging` module. By default,
no logging configuration is used. You can set up logging either by calling
:py:func:`logging.basicConfig()` (which configures the root logger)
or by adding your own handlers to the ``berconpy`` logger.

The following table describes what messages are shown in each level of logging:

======== =============================================================
Level    Messages
======== =============================================================
CRITICAL *Unused*
   ERROR Potentially fatal connection errors (e.g. incorrect password)
 WARNING Failed commands and consecutive reconnects
    INFO Connection attempts and timeouts
   DEBUG Events and packets transmitted/received
======== =============================================================

Example configurations
^^^^^^^^^^^^^^^^^^^^^^

Log all messages to stderr:

.. code:: python

    import logging

    logging.basicConfig(level=logging.DEBUG)

Log berconpy warnings to ``berconpy.log``:

.. code:: python

    import logging

    log = logging.getLogger('berconpy')
    log.setLevel(logging.WARNING)
    handler = logging.FileHandler('berconpy.log', 'w')
    handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
    log.addHandler(handler)

Next Steps
----------

This has covered the fundamentals of using berconpy. You can learn more about
the available methods by checking the :doc:`/api`, or if you're interested
in the technical details you can `check the source code`_.

.. _BattlEye documentation: https://www.battleye.com/support/documentation/
.. _check the source code: https://github.com/thegamecracks/berconpy/tree/main/src/berconpy
