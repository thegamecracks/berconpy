Welcome to berconpy's documentation!
====================================

**berconpy** is an asynchronous Python wrapper over the BattlEye RCON protocol.

.. code:: python

   import asyncio
   from berconpy import AsyncRCONClient

   client = AsyncRCONClient()

   async def main():
       async with client.connect('ip', 9999, 'password'):
           await client.send('Hello world!')

   asyncio.run(main())

.. toctree::
   :maxdepth: 2
   :glob:

   intro
   api
   events
   ext/*

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
