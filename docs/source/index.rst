Welcome to berconpy's documentation!
====================================

**berconpy** is an asynchronous Python wrapper over the BattlEye RCON protocol.

.. code:: python

   import asyncio
   from berconpy import RCONClient

   client = RCONClient()

   async def main():
       async with client.connect("ip", 9999, "password"):
           await client.send("Hello world!")

   asyncio.run(main())

Getting started
---------------

.. toctree::
   :maxdepth: 2

   intro

Reference
---------

.. toctree::
   :maxdepth: 1
   :glob:

   client
   protocol
   ext/*

Meta
----

.. toctree::
   :maxdepth: 1

   changelog

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
