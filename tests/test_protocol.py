from typing import Any, overload

import pytest

from berconpy.protocol import (
    ClientAuthEvent,
    ClientCommandEvent,
    ClientEvent,
    ClientMessageEvent,
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


def test_auth_failure(client: RCONClientProtocol, server: RCONServerProtocol):
    """Asserts that the client and server correctly recognize when
    authentication is incorrect.
    """
    authenticate(client, server, incorrect_password, should_succeed=False)


def test_nonce_check(client: RCONClientProtocol, server: RCONServerProtocol):
    """Asserts that both the client and the server do not respond to repeated
    messages and commands respectively.
    """
    authenticate(client, server, expected_password)

    # Normal commands
    payload = client.send_command("first")
    assert isinstance(communicate(client, server, payload)[0], ServerCommandEvent)
    payload = client.send_command("second")
    assert isinstance(communicate(client, server, payload)[0], ServerCommandEvent)
    # Repeat commands
    for i in range(10):
        assert len(communicate(client, server, payload)) == 0

    # NOTE: No need to followup with responses

    # Normal messages
    payload = server.send_message("first")
    assert isinstance(communicate(server, client, payload)[0], ClientMessageEvent)
    payload = server.send_message("second")
    assert isinstance(communicate(server, client, payload)[0], ClientMessageEvent)
    # Repeat messages
    for i in range(10):
        assert len(communicate(server, client, payload)) == 0
