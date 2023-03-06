from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from .packet import Packet

__all__ = ("RCONGenericProtocol",)

T_co = TypeVar("T_co", covariant=True)


class RCONGenericProtocol(ABC, Generic[T_co]):
    """The base class for handling the RCON protocol between two computers."""

    @abstractmethod
    def receive_datagram(self, data: bytes) -> Packet:
        """Provides a packet from the remote computer to potentially
        be parsed into an event.

        If the given data is invalid, this method should raise an error.

        """

    @abstractmethod
    def events_received(self) -> list[T_co]:
        """Retrieves all events that have been parsed since this was last called."""

    @abstractmethod
    def packets_to_send(self) -> list[Packet]:
        """Returns a list of payloads that should be sent to the remote computer."""
