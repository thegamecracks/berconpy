import enum
import secrets
from typing import Iterable

from .base import RCONGenericProtocol
from .check import Check, NonceCheck
from .errors import InvalidStateError
from .events import (
    ServerAuthEvent,
    ServerCommandEvent,
    ServerEvent,
    ServerMessageEvent,
)
from .packet import *


class ServerState(enum.Enum):
    """Defines the current authentication state."""

    AUTHENTICATING = enum.auto()
    """The server is waiting for the client to authenticate itself."""
    LOGGED_IN = enum.auto()
    """The server has authenticated the client and can send/receive messages."""


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
        command_check: Check[ClientCommandPacket] | None = None,
        password: str,
        response_chunk_size: int = 512,
    ) -> None:
        if command_check is None:
            command_check = NonceCheck(5)

        self.command_check = command_check
        self.response_chunk_size = response_chunk_size
        self.password = password
        self.reset()

    def __repr__(self) -> str:
        return "<{} {}, {} event(s), {} packet(s) to send>".format(
            type(self).__name__,
            self.state.name.lower().replace("_", " "),
            len(self._events),
            len(self._to_send),
        )

    def receive_datagram(self, data: bytes) -> ClientPacket:
        """Handles a packet received by the server.

        :raises InvalidStateError:
            The given packet cannot be handled in the current state.
        :raises ValueError: Handling failed due to a malformed packet.

        """
        packet = Packet.from_bytes(data, from_client=True)
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
        """Attempts to authenticate the client with the given password.

        :returns: The payload indicating if the client is authenticated.
        :raises InvalidStateError:
            This method can only be called during authentication.

        """
        self._assert_state(ServerState.AUTHENTICATING)
        success = secrets.compare_digest(password, self.password.encode())
        if success:
            self.state = ServerState.LOGGED_IN
        else:
            self.state = ServerState.AUTHENTICATING

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
            # self._assert_state(ServerState.AUTHENTICATING)
            # Client may authenticate multiple times

            payload = self.try_authenticate(packet.message)
            return (ServerAuthEvent(payload.login_success),), (payload,)

        elif isinstance(packet, ClientCommandPacket):
            self._assert_state(ServerState.LOGGED_IN)

            if self.command_check(packet):
                events = (ServerCommandEvent(packet.sequence, packet.message.decode()),)
            else:
                events = ()

            return events, ()

        elif isinstance(packet, ClientMessagePacket):
            self._assert_state(ServerState.LOGGED_IN)

            try:
                self._message_queue.remove(packet.sequence)
            except KeyError:
                raise ValueError(
                    f"Unexpected message acknowledgement (sequence {packet.sequence})"
                )

            return (ServerMessageEvent(packet.sequence),), ()

        raise ValueError(f"unexpected packet received: {packet}")  # pragma: no cover
