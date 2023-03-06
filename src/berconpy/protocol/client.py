import enum
from dataclasses import dataclass
from typing import Iterable

from .base import RCONGenericProtocol
from .check import Check, NonceCheck
from .errors import InvalidStateError
from .packet import *

__all__ = (
    "ClientEvent",
    "AuthEvent",
    "CommandResponseEvent",
    "ServerMessageEvent",
    "ClientState",
    "RCONClientProtocol",
)


class ClientEvent:
    """The base class for events received by the client from the server."""


@dataclass
class AuthEvent(ClientEvent):
    """Indicates if an authentication request was successful."""

    success: bool


@dataclass
class CommandResponseEvent(ClientEvent):
    """Represents the response to a given command."""

    sequence: int
    message: str


@dataclass
class ServerMessageEvent(ClientEvent):
    """Represents a message sent by the server."""

    message: str


class ClientState(enum.Enum):
    """Defines the current state of the protocol."""

    AUTHENTICATING = enum.auto()
    LOGGED_IN = enum.auto()


class RCONClientProtocol(RCONGenericProtocol):
    """Implements the client-side portion of the protocol.

    :param message_check:
        A :py:class:`Check` that determines if a :py:class:`ServerMessageEvent`
        should be dispatched when a :py:class:`ServerMessagePacket` is received.
        If ``None``, defaults to :py:class:`NonceCheck(5)`.

    """

    _events: list[ClientEvent]
    """A list of events waiting to be collected."""
    _command_queue: dict[int, dict[int, ServerCommandPacket]]
    """A mapping of command sequences to mappings of command indexes to their packets.

    When :py:meth:`send_command()` is used, an entry is added here to
    store the appropriate responses. Once all expected responses are received,"""
    _next_sequence: int
    _state: ClientState
    _to_send: list[ClientPacket]

    def __init__(
        self,
        *,
        message_check: Check[ServerMessagePacket] | None = None,
    ) -> None:
        if message_check is None:
            message_check = NonceCheck(5)

        self.message_check = message_check
        self.reset()

    def __repr__(self) -> str:
        return "<{} {}, {} event(s), {} packet(s) to send>".format(
            type(self).__name__,
            self._state.name.lower().replace("_", " "),
        )

    # Required methods

    def receive_datagram(self, data: bytes) -> ServerPacket:
        """Handles a packet received by the server.

        :raises ValueError: Handling failed due to a malformed packet.

        """
        try:
            packet: Packet = Packet.from_bytes(data)
        except (IndexError, ValueError) as e:
            raise ValueError(str(e)) from e

        if not isinstance(packet, ServerPacket):
            raise ValueError(
                f"Expected a {type(ServerPacket).__name__}, "
                f"received {type(packet).__name__} instead"
            )

        events, to_send = self._handle_packet(packet)
        self._events.extend(events)
        self._to_send.extend(to_send)

        return packet

    def events_received(self) -> list[ClientEvent]:
        current_events = self._events
        self._events = []
        return current_events

    def packets_to_send(self) -> list[ClientPacket]:
        current_datagrams = self._to_send
        self._to_send = []
        return current_datagrams

    # Utility methods

    def authenticate(self, password: str) -> ClientLoginPacket:
        """Returns the payload needed to authenticate with the server.

        :raises InvalidStateError:
            This method can only be called during authentication.

        """
        self._assert_state(ClientState.AUTHENTICATING)
        return ClientLoginPacket(password)

    def invalidate_command(self, sequence: int) -> None:
        """Invalidates any messages received for a response to a given command.

        This should be called whenever a command times out.

        If the command sequence was not queued before, this is a no-op.

        :raises InvalidStateError:
            This method can only be called after being logged in.

        """
        self._assert_state(ClientState.LOGGED_IN)
        self._command_queue.pop(sequence, None)

    def reset(self) -> None:
        """Resets the protocol to the beginning state.

        This method should be invoked when the connection has timed out.

        """
        self._events: list[ClientEvent] = []
        self._command_queue = {}
        self._next_sequence = 0
        self._state = ClientState.AUTHENTICATING
        self._to_send = []

        self.message_check.reset()

    def send_command(self, command: str) -> ClientCommandPacket:
        """Returns a payload for sending a command.

        Each invocation of this method increments an internal sequence
        counter. When retrying a command, it is recommended to re-use
        the same payload to avoid triggering the same command multiple times.

        :raises InvalidStateError:
            This method can only be called after being logged in.

        """
        self._assert_state(ClientState.LOGGED_IN)
        sequence = self._get_next_sequence()
        self._command_queue[sequence] = {}
        return ClientCommandPacket(sequence, command)

    def _assert_state(self, *states: ClientState) -> None:
        if self._state not in states:
            raise InvalidStateError(self._state, states)

    def _get_next_sequence(self) -> int:
        sequence = self._next_sequence
        self._next_sequence = (sequence + 1) % 256
        return sequence

    def _handle_packet(
        self,
        packet: ServerPacket,
    ) -> tuple[Iterable[ClientEvent], Iterable[ClientPacket]]:
        """Handles the given :py:class:`ServerPacket`.

        :returns: A tuple containing the events and payloads to send.
        :raises ValueError: An error occurred while handling the given packet.

        """
        if isinstance(packet, ServerLoginPacket):
            self._assert_state(ClientState.AUTHENTICATING)

            if packet.login_success:
                self._state = ClientState.LOGGED_IN

            return (AuthEvent(packet.login_success),), ()

        elif isinstance(packet, ServerCommandPacket):
            return self._handle_command_packet(packet)

        elif isinstance(packet, ServerMessagePacket):
            # Acknowledge the message
            self._assert_state(ClientState.LOGGED_IN)

            if self.message_check(packet):
                events = (ServerMessageEvent(packet.message),)
            else:
                events = ()

            return events, (ClientMessagePacket(packet.sequence),)

        raise ValueError(f"unexpected packet received: {packet}")

    def _handle_command_packet(
        self,
        packet: ServerCommandPacket,
    ) -> tuple[Iterable[ClientEvent], Iterable[ClientPacket]]:
        """Specifically handles a :py:class:`ServerCommandPacket`.

        :returns: A tuple containing the events and payloads to send.
        :raises ValueError: An error occurred while handling the given packet.

        """
        self._assert_state(ClientState.LOGGED_IN)

        rest = self._command_queue.get(packet.sequence)
        if rest is None:
            raise ValueError(
                f"Unexpected command response (sequence {packet.sequence})"
            )
        if packet.index not in range(packet.total):
            raise ValueError(
                f"Command response index {packet.index} exceeds the expected "
                f"maximum of {packet.total - 1} (sequence {packet.sequence})"
            )
        if packet.index in rest:
            raise ValueError(
                f"Command response index {packet.index} already received "
                f"(sequence {packet.sequence})"
            )
        if rest and packet.total != (expected_total := next(iter(rest.values())).total):
            raise ValueError(
                f"Command response total {packet.total} for index {packet.index} "
                f"does not match the previously defined total of {expected_total} "
                f"(sequence {packet.sequence})"
            )

        # NOTE: despite the above checks, we have not asserted any specific
        #       order in which the packets should arrive

        rest[packet.index] = packet
        if len(rest) < packet.total:
            return (), ()

        self.invalidate_command(packet.sequence)

        # This should be guaranteed to work
        message = "".join(rest[i].message for i in range(packet.total))

        return (CommandResponseEvent(packet.sequence, message),), ()
