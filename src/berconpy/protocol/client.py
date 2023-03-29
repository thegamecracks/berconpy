import enum
from typing import Iterable

from .base import RCONGenericProtocol
from .check import Check, NonceCheck
from .errors import InvalidStateError
from .events import (
    ClientAuthEvent,
    ClientCommandEvent,
    ClientEvent,
    ClientMessageEvent,
)
from .packet import *


class ClientState(enum.Enum):
    """Defines the current state of the protocol."""

    AUTHENTICATING = enum.auto()
    """The client currently needs to be authenticated by the server."""
    LOGGED_IN = enum.auto()
    """The client is logged in and able to send/receive messages."""


class RCONClientProtocol(RCONGenericProtocol):
    """Implements the client-side portion of the protocol.

    :param message_check:
        A :py:class:`Check` that determines if a :py:class:`ServerMessageEvent`
        should be dispatched when a :py:class:`ServerMessagePacket` is received.
        If ``None``, defaults to :py:class:`NonceCheck(5)`.

    """

    state: ClientState
    """The current state of the protocol."""

    _events: list[ClientEvent]
    """A list of events waiting to be collected."""
    _command_queue: dict[int, dict[int, ServerCommandPacket]]
    """A mapping of command sequences to mappings of command indexes to their packets.

    When :py:meth:`send_command()` is used, an entry is added here to
    store the appropriate responses. Once all expected responses are
    received, they are joined into a single message and converted into
    a :py:class:`CommandResponseEvent`.

    """
    _next_sequence: int
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
            self.state.name.lower().replace("_", " "),
            len(self._events),
            len(self._to_send),
        )

    # Required methods

    def receive_datagram(self, data: bytes) -> ServerPacket:
        """Handles a packet received by the server.

        :raises InvalidStateError:
            The given packet cannot be handled in the current state.
        :raises ValueError: A malformed packet was provided.

        """
        packet = Packet.from_bytes(data, from_client=False)
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
        return ClientLoginPacket(password.encode())

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

        This method should be invoked when the connection has timed out,
        meaning the client has either not sent a command within the last
        45 seconds, or the client has failed to acknowledge 5 repeats of
        the same message within 10 seconds.

        """
        self._events = []
        self._command_queue = {}
        self._next_sequence = 0
        self.state = ClientState.AUTHENTICATING
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
        return ClientCommandPacket(sequence, command.encode())

    def _assert_state(self, *states: ClientState) -> None:
        if self.state not in states:
            raise InvalidStateError(self.state, states)

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
                self.state = ClientState.LOGGED_IN

            return (ClientAuthEvent(packet.login_success),), ()

        elif isinstance(packet, ServerCommandPacket):
            return self._handle_command_packet(packet)

        elif isinstance(packet, ServerMessagePacket):
            # Acknowledge the message
            self._assert_state(ClientState.LOGGED_IN)

            if self.message_check(packet):
                events = (ClientMessageEvent(packet.message.decode()),)
            else:
                events = ()

            return events, (ClientMessagePacket(packet.sequence),)

        raise ValueError(f"unexpected packet received: {packet}")  # pragma: no cover

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
        message_bytes = b"".join(rest[i].message for i in range(packet.total))
        message_str = message_bytes.decode()

        return (ClientCommandEvent(packet.sequence, message_str),), ()
