from abc import ABC, abstractmethod
from typing import Any, Sequence

from .packet import Packet

__all__ = ("RCONGenericProtocol",)


class RCONGenericProtocol(ABC):
    """The base class for handling the RCON protocol between two computers."""

    @abstractmethod
    def receive_datagram(self, data: bytes) -> Packet:
        """Provides a packet from the remote computer to potentially
        be parsed into an event.

        If the given data is invalid, this method should raise an error.

        """

    @abstractmethod
    def events_received(self) -> Sequence[Any]:
        """Retrieves all events that have been parsed since this was last called."""

    @abstractmethod
    def packets_to_send(self) -> Sequence[Packet]:
        """Returns a list of payloads that should be sent to the remote computer."""
