Sans-IO API Reference
=====================

RCON Client
-----------

.. autosummary::
   :toctree: generated
   :nosignatures:

   berconpy.client.RCONClient
   berconpy.cache.RCONClientCache
   berconpy.dispatch.EventDispatcher

Data Models
^^^^^^^^^^^

.. autosummary::
   :toctree: generated
   :nosignatures:

   berconpy.ban.Ban
   berconpy.player.Player

Protocol Interface
------------------

.. autosummary::
   :toctree: generated
   :nosignatures:

   berconpy.RCONGenericProtocol

Protocol Implementations
^^^^^^^^^^^^^^^^^^^^^^^^

.. autosummary::
   :toctree: generated
   :nosignatures:

   berconpy.RCONClientProtocol
   berconpy.ClientEvent
   berconpy.ClientAuthEvent
   berconpy.ClientCommandEvent
   berconpy.ClientMessageEvent
   berconpy.ClientState

   berconpy.RCONServerProtocol
   berconpy.ServerEvent
   berconpy.ServerAuthEvent
   berconpy.ServerCommandEvent
   berconpy.ServerMessageEvent
   berconpy.ServerState

Packet Messages
^^^^^^^^^^^^^^^

.. autosummary::
   :toctree: generated
   :nosignatures:

   berconpy.protocol.Packet
   berconpy.protocol.PacketType
   berconpy.protocol.ClientPacket
   berconpy.protocol.ClientLoginPacket
   berconpy.protocol.ClientCommandPacket
   berconpy.protocol.ClientMessagePacket
   berconpy.protocol.ServerPacket
   berconpy.protocol.ServerLoginPacket
   berconpy.protocol.ServerCommandPacket
   berconpy.protocol.ServerMessagePacket

Packet Checks
^^^^^^^^^^^^^

.. autosummary::
   :toctree: generated
   :nosignatures:

   berconpy.protocol.check.Check
   berconpy.protocol.check.NonceCheck

Exceptions
----------

.. autosummary::
   :toctree: generated
   :nosignatures:

   berconpy.protocol.errors.InvalidStateError
