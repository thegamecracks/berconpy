"""Provides classes to be used as facades for :py:class`Packet` objects."""
from dataclasses import dataclass


class Event:
    """The base class for events produced by :py:class:`RCONGenericProtocol`
    subclasses.
    """


class ClientEvent(Event):
    """An event produced by the :py:class:`RCONClientProtocol` subclass."""


@dataclass
class ClientAuthEvent(ClientEvent):
    """Indicates if an authentication request was successful."""

    success: bool


@dataclass
class ClientCommandEvent(ClientEvent):
    """Represents the response to a given command."""

    sequence: int
    message: str


@dataclass
class ClientMessageEvent(ClientEvent):
    """Represents a message sent by the server.

    The protocol automatically generates an acknowledgement packet
    so nothing else needs to be done here.

    """

    message: str


class ServerEvent(Event):
    """An event produced by the :py:class:`RCONServerProtocol` subclass."""


@dataclass
class ServerAuthEvent(ServerEvent):
    """Indicates if an authentication request was successful.

    The protocol automatically generates an acknowledgement packet
    so nothing else needs to be done here.

    """

    success: bool


@dataclass
class ServerCommandEvent(ServerEvent):
    """Represents a command sent by the client."""

    sequence: int
    message: str


@dataclass
class ServerMessageEvent(ServerEvent):
    """Represents an acknowledgement of a message sent by the server."""

    sequence: int
