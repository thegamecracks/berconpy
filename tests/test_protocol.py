from typing import Any, Type, TypeVar, overload

import pytest

from berconpy.protocol import (
    ClientAuthEvent,
    ClientCommandEvent,
    ClientEvent,
    ClientMessageEvent,
    ClientMessagePacket,
    ClientPacket,
    ClientState,
    Packet,
    RCONClientProtocol,
    RCONGenericProtocol,
    RCONServerProtocol,
    ServerAuthEvent,
    ServerCommandEvent,
    ServerEvent,
    ServerMessageEvent,
    ServerPacket,
    ServerState,
)

expected_password = "foobar2000"
incorrect_password = "abc123"

T = TypeVar("T")


@pytest.fixture
def client() -> RCONClientProtocol:
    return RCONClientProtocol()


@pytest.fixture
def server() -> RCONServerProtocol:
    return RCONServerProtocol(password=expected_password)


@overload
def communicate(
    proto_a: RCONClientProtocol,
    proto_b: RCONServerProtocol,
    *packets: ClientPacket,
) -> list[ServerEvent]:
    ...


@overload
def communicate(
    proto_a: RCONServerProtocol,
    proto_b: RCONClientProtocol,
    *packets: ServerPacket,
) -> list[ClientEvent]:
    ...


def communicate(
    proto_a: RCONGenericProtocol,
    proto_b: RCONGenericProtocol,
    *packets: Packet,
) -> list[Any]:
    """Sends the given packets alongside the packets returned from
    :py:meth:`RCONGenericProtocol.packets_to_send()` from one protocol
    to the other and returns the events received by the second protocol.
    """
    for packet in proto_a.packets_to_send():
        proto_b.receive_datagram(packet.data)

    for packet in packets:
        proto_b.receive_datagram(packet.data)

    return proto_b.events_received()


def authenticate(
    client: RCONClientProtocol,
    server: RCONServerProtocol,
    password: str,
    *,
    should_succeed: bool = True,
) -> None:
    """Authenticates the client and server with the given password."""
    payload = client.authenticate(password)
    server_event = communicate(client, server, payload)[0]
    client_event = communicate(server, client)[0]

    assert isinstance(client_event, ClientAuthEvent)
    assert isinstance(server_event, ServerAuthEvent)

    if should_succeed:
        assert client.state == ClientState.LOGGED_IN
        assert server.state == ServerState.LOGGED_IN
        assert client_event.success
        assert server_event.success
    else:
        assert client.state != ClientState.LOGGED_IN
        assert server.state != ServerState.LOGGED_IN
        assert not client_event.success
        assert not server_event.success


def first_and_only_packet(proto_a: RCONGenericProtocol, packet_cls: Type[T]) -> T:
    packets = proto_a.packets_to_send()
    assert len(packets) == 1
    first_packet = packets[0]
    assert isinstance(first_packet, packet_cls)
    return first_packet


def test_auth_failure(client: RCONClientProtocol, server: RCONServerProtocol):
    """Asserts that the client and server correctly recognize when
    authentication is incorrect.
    """
    authenticate(client, server, incorrect_password, should_succeed=False)


def test_nonce_check(client: RCONClientProtocol, server: RCONServerProtocol):
    """Asserts that both the client and the server do not dispatch
    repeated events for messages and commands respectively.
    """
    authenticate(client, server, expected_password)

    # Normal commands
    #
    # The sequence number only goes up to 256 before overflowing
    # so the nonce check must be able to forget older sequences.
    for i in range(2 ** 9):
        payload = client.send_command(str(i))
        assert isinstance(communicate(client, server, payload)[0], ServerCommandEvent)
        assert len(communicate(client, server, payload)) == 0

    # Normal messages
    #
    # Here we also verify that the client acknowledges each message,
    # even when the nonce check is preventing repeated events.
    for i in range(2 ** 9):
        payload = server.send_message(str(i))
        assert isinstance(communicate(server, client, payload)[0], ClientMessageEvent)
        assert first_and_only_packet(client, ClientMessagePacket)

        assert len(communicate(server, client, payload)) == 0
        assert first_and_only_packet(client, ClientMessagePacket)
