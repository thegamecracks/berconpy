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


def test_command_validation(client: RCONClientProtocol):
    client.receive_datagram(ServerLoginPacket(success=True).data)
    client.events_received()

    # Unknown command
    packet = ServerCommandPacket(sequence=0, total=1, index=0, response=b"")
    with pytest.raises(ValueError):
        client.receive_datagram(packet.data)

    seq = client.send_command("").sequence

    # Allow out-of-order packets
    packet = ServerCommandPacket(sequence=seq, total=2, index=1, response=b"world!")
    client.receive_datagram(packet.data)

    # Mismatched total
    packet = ServerCommandPacket(sequence=seq, total=1, index=0, response=b"")
    with pytest.raises(ValueError):
        client.receive_datagram(packet.data)

    # Repeat packet
    packet = ServerCommandPacket(sequence=seq, total=2, index=1, response=b"")
    with pytest.raises(ValueError):
        client.receive_datagram(packet.data)

    packet = ServerCommandPacket(sequence=seq, total=2, index=0, response=b"Hello ")
    client.receive_datagram(packet.data)
    assert first_and_only_event(client, ClientCommandEvent).message == "Hello world!"
