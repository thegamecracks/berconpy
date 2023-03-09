import pytest

from berconpy.protocol import (
    ClientAuthEvent,
    ClientCommandEvent,
    ClientCommandPacket,
    ClientEvent,
    ClientLoginPacket,
    ClientMessageEvent,
    ClientMessagePacket,
    ClientPacket,
    ClientState,
    InvalidStateError,
    RCONClientProtocol,
    ServerCommandPacket,
    ServerLoginPacket,
    ServerMessagePacket,
)

from . import client, first_and_only_event


def test_invalid_states(client: RCONClientProtocol):
    """Asserts the client will raise :py:exc:`InvalidStateError` where appropriate."""
    for _ in range(2):
        message = ServerMessagePacket(sequence=0, message=b"Hello world!")
        command_response = ServerCommandPacket(
            sequence=0,
            total=1,
            index=0,
            response=b"Hello world!",
        )

        # Test state before authentication
        with pytest.raises(InvalidStateError):
            client.receive_datagram(message.data)
        assert not client.events_received()

        with pytest.raises(InvalidStateError):
            client.receive_datagram(command_response.data)
        assert not client.events_received()

        with pytest.raises(InvalidStateError):
            client.send_command("too early")

        with pytest.raises(InvalidStateError):
            client.invalidate_command(0)

        packet = client.authenticate("password")

        client.receive_datagram(ServerLoginPacket(success=False).data)
        assert not first_and_only_event(client, ClientAuthEvent).success

        client.receive_datagram(ServerLoginPacket(success=True).data)
        assert first_and_only_event(client, ClientAuthEvent).success

        # Test state after authentication
        with pytest.raises(InvalidStateError):
            client.authenticate("already authenticated")

        client.receive_datagram(message.data)
        assert first_and_only_event(client, ClientMessageEvent)

        packet = client.send_command("Hello world!")
        assert packet.sequence == command_response.sequence
        client.receive_datagram(command_response.data)
        assert first_and_only_event(client, ClientCommandEvent)

        # Nothing to invalidate, just making sure it works without error
        client.invalidate_command(0)

        client.reset()
