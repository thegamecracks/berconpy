from typing import Any, Sequence, Type, TypeVar, overload

import pytest

from berconpy.protocol import (
    ClientAuthEvent,
    ClientEvent,
    ClientPacket,
    ClientState,
    Packet,
    RCONClientProtocol,
    RCONGenericProtocol,
    RCONServerProtocol,
    ServerAuthEvent,
    ServerEvent,
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
) -> Sequence[ServerEvent]: ...


@overload
def communicate(
    proto_a: RCONServerProtocol,
    proto_b: RCONClientProtocol,
    *packets: ServerPacket,
) -> Sequence[ClientEvent]: ...


def communicate(
    proto_a: RCONGenericProtocol,
    proto_b: RCONGenericProtocol,
    *packets: Packet,
) -> Sequence[Any]:
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


def first_and_only_event(proto_a: RCONGenericProtocol, event_cls: Type[T]) -> T:
    events = proto_a.events_received()
    assert len(events) == 1
    first_event = events[0]
    assert isinstance(first_event, event_cls)
    return first_event


def first_and_only_packet(proto_a: RCONGenericProtocol, packet_cls: Type[T]) -> T:
    packets = proto_a.packets_to_send()
    assert len(packets) == 1
    first_packet = packets[0]
    assert isinstance(first_packet, packet_cls)
    return first_packet
