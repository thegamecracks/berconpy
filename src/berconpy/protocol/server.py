import enum
import secrets
from dataclasses import dataclass
from typing import Iterable

from .base import RCONGenericProtocol
from .check import Check, NonceCheck
from .errors import InvalidStateError
from .packet import *


class ServerEvent:
    """The base class for events received by the server from the client."""


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


class ServerState(enum.Enum):
    """Defines the current authentication state."""

    AUTHENTICATING = enum.auto()
    LOGGED_IN = enum.auto()


class RCONServerProtocol(RCONGenericProtocol):
    """A Sans-IO implementation of the server RCON protocol for one client.

    :param command_check:
        A :py:class:`Check` that determines if a :py:class:`ClientCommandEvent`
        should be dispatched when a :py:class:`ClientCommandPacket` is received.
        If ``None``, defaults to :py:class:`NonceCheck(5)`.
    :param password:
        The password to compare against when the client is authenticating.
        The protocol recommends this should be an ASCII-compatible string.
    :param response_chunk_size:
        Sets the size to use when chunking a command response into one
        or more packets to be returned by :py:meth:`respond_to_command()`.
    """

    state: ServerState
    """The current state of the protocol."""

    _events: list[ServerEvent]
    """A list of events waiting to be collected."""
    _message_queue: set[int]
    """A set of message sequences waiting to be acknowledged."""
    _next_sequence: int
    _to_send: list[ServerPacket]

    def __init__(
        self,
        *,
        command_check: Check[ServerCommandPacket] | None = None,
        password: str,
        response_chunk_size: int = 512,
    ) -> None:
        if command_check is None:
            command_check = NonceCheck(5)

        self.command_check = command_check
        self.response_chunk_size = response_chunk_size
        self.password = password
        self.reset()

    def receive_datagram(self, data: bytes) -> ClientPacket:
        """Handles a packet received by the server.

        :raises ValueError: Handling failed due to a malformed packet.

        """
        try:
            packet: Packet = Packet.from_bytes(data, from_client=True)
        except (IndexError, ValueError) as e:
            raise ValueError(str(e)) from e

        if not isinstance(packet, ClientPacket):
            raise ValueError(
                f"Expected a {type(ClientPacket).__name__}, "
                f"received {type(packet).__name__} instead"
            )

        events, to_send = self._handle_packet(packet)
        self._events.extend(events)
        self._to_send.extend(to_send)

        return packet

    def events_received(self) -> list[ServerEvent]:
        current_events = self._events
        self._events = []
        return current_events

    def packets_to_send(self) -> list[ServerPacket]:
        current_datagrams = self._to_send
        self._to_send = []
        return current_datagrams

    # Utility methods

    def reset(self) -> None:
        """Resets the protocol to the beginning state.

        This method should be invoked when the connection has timed out,
        meaning the client has either not sent a command within the last
        45 seconds, or the client has failed to acknowledge 5 repeats of
        the same message within 10 seconds.

        """
        self._events = []
        self._message_queue = set()
        self._next_sequence = 0
        self.state = ServerState.AUTHENTICATING
        self._to_send = []

    def respond_to_command(
        self,
        sequence: int,
        response: str,
    ) -> list[ServerCommandPacket]:
        """Returns a list of payloads for responding to the client's command."""
        response_bytes = response.encode()
        byte_chunks = [
            response_bytes[i : i + self.response_chunk_size]
            for i in range(0, len(response_bytes), self.response_chunk_size)
        ]

        return [
            ServerCommandPacket(
                sequence=sequence,
                total=len(byte_chunks),
                index=i,
                response=part,
            )
            for i, part in enumerate(byte_chunks)
        ]

    def send_message(self, message: str) -> ServerMessagePacket:
        """Returns a payload for sending a message.

        Each invocation of this method increments an internal sequence
        counter. When retrying a message, it is recommended to re-use
        the same payload to avoid having the client interpret each
        attempt as a new message.

        :raises InvalidStateError:
            This method can only be called after being logged in.

        """
        self._assert_state(ServerState.LOGGED_IN)
        sequence = self._get_next_sequence()
        self._message_queue.add(sequence)
        return ServerMessagePacket(sequence, message.encode())

    def try_authenticate(self, password: bytes) -> ServerLoginPacket:
        """Returns the payload needed to authenticate with the server.

        :raises InvalidStateError:
            This method can only be called during authentication.

        """
        self._assert_state(ServerState.AUTHENTICATING)
        success = secrets.compare_digest(password, self.password.encode())
        if success:
            self.state = ServerState.LOGGED_IN

        return ServerLoginPacket(success)

    def _assert_state(self, *states: ServerState) -> None:
        if self.state not in states:
            raise InvalidStateError(self.state, states)

    def _get_next_sequence(self) -> int:
        sequence = self._next_sequence
        self._next_sequence = (sequence + 1) % 256
        return sequence

    def _handle_packet(
        self,
        packet: ClientPacket,
    ) -> tuple[Iterable[ServerEvent], Iterable[ServerPacket]]:
        """Handles the given :py:class:`ClientPacket`.

        :returns: A tuple containing the events and payloads to send.
        :raises ValueError: An error occurred while handling the given packet.

        """
        if isinstance(packet, ClientLoginPacket):
            self._assert_state(ServerState.AUTHENTICATING)

            payload = self.try_authenticate(packet.message)
            return (ServerAuthEvent(payload.login_success),), (payload,)

        elif isinstance(packet, ClientCommandPacket):
            self._assert_state(ServerState.LOGGED_IN)
            return (ServerCommandEvent(packet.sequence, packet.message.decode()),), ()

        elif isinstance(packet, ClientMessagePacket):
            self._assert_state(ServerState.LOGGED_IN)

            try:
                self._message_queue.remove(packet.sequence)
            except KeyError:
                raise ValueError(
                    f"Unexpected message acknowledgement (sequence {packet.sequence})"
                )

            return (ServerMessageEvent(packet.sequence),), ()

        raise ValueError(f"unexpected packet received: {packet}")
