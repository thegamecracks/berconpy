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

The primary class berconpy offers is the :py:class:`~berconpy.RCONClient`,
which provides an interface over the underlying protocol and allows you to
register event listeners and send commands to the BattlEye RCON server.

Sending commands
^^^^^^^^^^^^^^^^

Let's start with an example of how to send a command:

.. code:: python

    import asyncio
    import berconpy as rcon

    IP_ADDR = "XXX.XXX.XXX.XXX"
    PORT = 9999
    PASSWORD = "ASCII_PASSWORD"

    client = rcon.RCONClient()

    async def main():
        async with client.connect(IP_ADDR, PORT, PASSWORD):
            response = await client.send_command("players")
            print(response)

    asyncio.run(main())

.. note::

    The RCON IP address, port, and password can be found in your server's
    ``BEServer.cfg`` / ``BEServer_x64.cfg``.

1. ``client = rcon.RCONClient()`` creates the client instance.
   No arguments are necessary, but you can set up event listeners
   on the client before beginning any connection which will be
   demonstrated afterwards.

2. ``async with client.connect(IP_ADDR, PORT, PASSWORD)`` attempts to connect
   and log into the RCON server. The context manager also keeps the connection
   alive until you exit it, or an error occurs.

3. ``response = await client.send_command("players")`` requests the
   players currently connected to the server and returns a string.

:py:meth:`~berconpy.RCONClient.send_command()` provides a simple
method for sending commands and awaiting their responses.
Commands can be found in the `BattlEye documentation`_ under the
"Server-side BE commands" section.

Event listeners
^^^^^^^^^^^^^^^

There are four basic events you can listen to handle messages sent
by the server in real-time:

.. code:: python

    import asyncio
    import berconpy as rcon

    IP_ADDR = "XXX.XXX.XXX.XXX"
    PORT = 9999
    PASSWORD = "ASCII_PASSWORD"

    client = rcon.RCONClient()

    @client.dispatch.on_raw_event
    async def on_raw_event(packet: rcon.protocol.ServerPacket):
        print(f"Raw event: {packet}")

    @client.dispatch.on_login
    async def on_login():
        print("We have logged in!")

    @client.dispatch.on_command
    async def on_command(response: str):
        print(f"Received command response: {response}")

    @client.dispatch.on_command
    async def on_message(message: str):
        print(f"Received message: {message}")

    async def main():
        async with client.connect(IP_ADDR, PORT, PASSWORD):
            # Keep client alive indefinitely:
            await asyncio.get_running_loop().create_future()

    asyncio.run(main())

Each decorator adds their function as a listener for that specific event
when it is received from the server. The ``on_*`` methods are provided by
the :py:class:`~berconpy.EventDispatcher` class, which has function signatures
that allow your type checker to ensure that your listener is correctly typed.

Usage with Arma 3 and DayZ
^^^^^^^^^^^^^^^^^^^^^^^^^^

For Arma 3 and DayZ specifically, there is also an :py:class:`~berconpy.ArmaClient`
class which has its own message parser and :py:class:`~berconpy.ArmaDispatcher` class,
allowing it to dispatch more granular events like :py:meth:`~berconpy.ArmaDispatcher.on_player_connect()`
and :py:meth:`~berconpy.ArmaDispatcher.on_player_message()`. It also manages a cache of
:py:class:`~berconpy.Player` and :py:class:`~berconpy.Ban` objects, providing helper methods
like :py:meth:`Player.ban_guid() <berconpy.Player.ban_guid>` and :py:meth:`Player.send() <berconpy.Player.send>`
which calls ``send_command()`` with the appropriate arguments.

Due to the parser relying on a specific message format followed by these two games,
it is strongly advised not to use :py:class:`~berconpy.ArmaClient` with any other
game like Arma Reforger, and instead use the generic :py:class:`~berconpy.RCONClient`
class.

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

    log = logging.getLogger("berconpy")
    log.setLevel(logging.WARNING)
    handler = logging.FileHandler("berconpy.log", "w")
    handler.setFormatter(logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s"))
    log.addHandler(handler)

Next Steps
----------

This has covered the fundamentals of using berconpy. You can learn more about
the available methods by checking the :doc:`/client`, or if you're interested
in the technical details you can `check the source code`_.

.. _BattlEye documentation: https://www.battleye.com/support/documentation/
.. _check the source code: https://github.com/thegamecracks/berconpy/tree/main/src/berconpy
