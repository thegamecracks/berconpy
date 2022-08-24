API Reference
=============

Client Interface
----------------

.. autosummary::
   :toctree: generated
   :nosignatures:

   berconpy.AsyncRCONClient

Data Models
-----------

.. autosummary::
   :toctree: generated
   :nosignatures:

   berconpy.Ban
   berconpy.Player

Protocol Message Classes
------------------------

.. autosummary::
   :toctree: generated
   :nosignatures:

   berconpy.Packet
   berconpy.PacketType
   berconpy.ClientPacket
   berconpy.ClientLoginPacket
   berconpy.ClientCommandPacket
   berconpy.ClientMessagePacket
   berconpy.ServerPacket
   berconpy.ServerLoginPacket
   berconpy.ServerCommandPacket
   berconpy.ServerMessagePacket

Exceptions
----------

.. autosummary::
   :toctree: generated
   :nosignatures:

   berconpy.RCONError
   berconpy.RCONCommandError
   berconpy.LoginFailure
