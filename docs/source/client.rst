RCON Client API Reference
=========================

This page covers classes used for generic BattlEye RCON, like Arma Reforger.
For Arma 3 and DayZ-specific classes, see the :doc:`/ext/arma`.

Client Interface
----------------

This covers the most important classes for handling RCON.

.. autosummary::
   :toctree: generated
   :nosignatures:

   berconpy.RCONClient
   berconpy.EventDispatcher

Client Connector
----------------

These classes are generally not necessary to know about,
but may be desired if the default networking needs to be tweaked.

.. autosummary::
   :toctree: generated
   :nosignatures:

   berconpy.AsyncClientConnector
   berconpy.AsyncClientProtocol
   berconpy.AsyncCommander
   berconpy.ConnectorConfig

Exceptions
----------

These exceptions are raised by :py:class:`~berconpy.RCONClient`.

.. autosummary::
   :toctree: generated
   :nosignatures:

   berconpy.LoginFailure
   berconpy.RCONError
   berconpy.RCONCommandError
