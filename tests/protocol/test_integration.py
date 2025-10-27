from berconpy.protocol import (
    ClientMessageEvent,
    ClientMessagePacket,
    RCONClientProtocol,
    RCONServerProtocol,
    ServerCommandEvent,
)

from . import (
    authenticate,
    communicate,
    expected_password,
    first_and_only_packet,
    incorrect_password,
)


def test_auth_failure(client: RCONClientProtocol, server: RCONServerProtocol):
    """Asserts that the client and server correctly recognize when
    authentication is incorrect.
    """
    authenticate(client, server, incorrect_password, should_succeed=False)


def test_nonce_check_integration(
    client: RCONClientProtocol, server: RCONServerProtocol
):
    """Asserts that both the client and the server do not dispatch
    repeated events for messages and commands respectively.
    """
    authenticate(client, server, expected_password)

    # Normal commands
    #
    # The sequence number only goes up to 256 before overflowing
    # so the nonce check must be able to forget older sequences.
    for i in range(2**9):
        payload = client.send_command(str(i))
        assert isinstance(communicate(client, server, payload)[0], ServerCommandEvent)
        assert len(communicate(client, server, payload)) == 0

    # Normal messages
    #
    # Here we also verify that the client acknowledges each message,
    # even when the nonce check is preventing repeated events.
    for i in range(2**9):
        payload = server.send_message(str(i))
        assert isinstance(communicate(server, client, payload)[0], ClientMessageEvent)
        assert first_and_only_packet(client, ClientMessagePacket)

        assert len(communicate(server, client, payload)) == 0
        assert first_and_only_packet(client, ClientMessagePacket)
