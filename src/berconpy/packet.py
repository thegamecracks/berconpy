import binascii
import enum

__all__ = (
    'PacketType', 'Packet', 'ClientPacket', 'ServerPacket',
    'ClientLoginPacket', 'ClientCommandPacket', 'ClientMessagePacket',
    'ServerLoginPacket', 'ServerCommandPacket', 'ServerMessagePacket'
)


class PacketType(enum.Enum):
    LOGIN = 0x00
    COMMAND = 0x01
    MESSAGE = 0x02


class Packet:
    """The base class used for all messages sent between
    the BattlEye RCON server and client.

    The protocol specification can be found here:
    https://www.battleye.com/downloads/BERConProtocol.txt

    Several properties are defined here but are not implemented.
    In order to get an actual packet, one of the subclasses must be
    constructed or the `Packet.from_bytes()` method should be used
    to convert to one of the appropriate subtypes.

    Only a few properties are guaranteed:
    1. `checksum`
    2. `type`

    Every other property may return None if the subclass's usage
    does not require it.

    """
    __slots__ = ('data',)

    def __init__(self, data: bytes):
        over_size = len(data) - 65507
        if over_size > 0:
            raise ValueError(f'max packet size exceeded by {over_size} bytes')

        self.data = data

    def __repr__(self):
        return '{}({!r})'.format(type(self).__name__, self.data)

    @property
    def checksum(self) -> int:
        """Returns the CRC32 checksum included in the header."""
        return int.from_bytes(self.data[2:6], 'little')

    @property
    def type(self) -> PacketType:
        """Returns the packet type according to the protocol."""
        return PacketType(self.data[7])

    @property
    def login_success(self) -> bool | None:
        """Returns a boolean indicating if the server authenticated the client."""

    @property
    def sequence(self) -> int | None:
        """Returns the sequence number of the COMMAND or MESSAGE packet."""

    @property
    def total(self) -> int | None:
        """Returns the total number of packets associated with a
        COMMAND server response.

        If a sub-header is not provided with the response,
        this defaults to 1.

        """

    @property
    def index(self) -> int | None:
        """Returns the zero-based index of the packet associated with a
        COMMAND server response.

        If a sub-header is not provided with the response,
        this defaults to 0.

        """

    @property
    def message(self) -> str | None:
        """The message that was sent to the client/server.

        This will always be an ASCII-compatible string.

        For LOGIN, this would be the password sent to the server.
        For COMMAND, this would be the command string sent to the server.
        For MESSAGE, this would be the message sent to the client.

        """

    def assert_checksum(self, checksum: int):
        """Asserts that the packet has a given checksum.

        :returns: The same packet object, helpful for method chaining.
        :raises ValueError: The checksum was incorrect.

        """
        if checksum != self.checksum:
            raise ValueError('CRC32 checksum does not match the given data')
        return self

    @classmethod
    def from_bytes(cls, data: bytes, from_client=False):
        """Constructs a packet from the given data.

        :param data: The data to parse.
        :param from_client:
            Whether the packet came from the server or client.
            This is required for disambiguation of data.
        :returns: The corresponding subclass of Packet.
        :raises IndexError:
            The given data is too short to match the packet
            specification.
        :raises ValueError:
            The given data is malformed and does not match the
            packet specification.

        """
        if data[:2] != b'BE':
            raise ValueError('expected BE as start of header')
        elif data[6] != 255:
            raise ValueError('expected 0xFF at end of header')

        crc = int.from_bytes(data[2:6], 'little')

        try:
            ptype = PacketType(data[7])
        except ValueError:
            raise ValueError(f'unknown packet type: {data[7]}') from None

        if ptype is PacketType.LOGIN and from_client:
            if b'\x00' in data[8:]:
                raise ValueError('login password cannot have a null byte')
            return ClientLoginPacket(data[8:].decode('ascii')).assert_checksum(crc)

        elif ptype is PacketType.LOGIN and not from_client:
            if data[8] not in (0, 1):
                raise ValueError('authentication byte must be 0 or 1')
            elif len(data[8:]) != 1:
                raise ValueError('unexpected excess data after authentication byte')
            return ServerLoginPacket(bool(data[8])).assert_checksum(crc)

        elif ptype is PacketType.COMMAND and from_client:
            sequence = data[8]
            command = data[9:].decode('ascii')
            return ClientCommandPacket(sequence, command).assert_checksum(crc)

        elif ptype is PacketType.COMMAND and not from_client:
            sequence = data[8]
            if len(data) > 9 and data[9] == 0:
                total, index = data[10], data[11]
                response = data[12:].decode('ascii')
            else:
                total, index = 1, 0
                response = data[9:].decode('ascii')

            if index >= total:
                raise ValueError(f'index ({index}) cannot equal or exceed total ({total})')
            return ServerCommandPacket(sequence, total, index, response).assert_checksum(crc)

        elif ptype is PacketType.MESSAGE and from_client:
            sequence = data[8]
            return ClientMessagePacket(sequence).assert_checksum(crc)

        elif ptype is PacketType.MESSAGE and not from_client:
            sequence = data[8]
            message = data[9:].decode('ascii')
            return ServerMessagePacket(sequence, message).assert_checksum(crc)

        raise RuntimeError(f'unhandled PacketType enum: {ptype} (from_client: {from_client})')

    @staticmethod
    def _encode_header(message: bytes):
        crc = binascii.crc32(message).to_bytes(4, 'little')
        return b'BE' + crc

    @staticmethod
    def _get_checksum(message: bytes) -> bytes:
        """Returns the checksum bytes that should be included
        in the header based on the given message.
        """

    @staticmethod
    def _get_initial_message(packet_type: PacketType) -> bytearray:
        return bytearray((0xFF, packet_type.value))


class ClientPacket(Packet):
    """The base class for packets sent by the client."""


class ClientLoginPacket(ClientPacket):
    """The packet used to log in a client."""
    def __init__(self, password: str):
        buffer = self._get_initial_message(PacketType.LOGIN)
        buffer.extend(password.encode('ascii'))

        message = bytes(buffer)
        header = self._encode_header(message)
        super().__init__(header + message)

    def __repr__(self):
        return '{}({!r})'.format(type(self).__name__, self.message)

    @property
    def login_success(self) -> None: ...

    @property
    def sequence(self) -> None: ...

    @property
    def total(self) -> None: ...

    @property
    def index(self) -> None: ...

    @property
    def message(self) -> str:
        return self.data[8:].decode('ascii')


class ClientCommandPacket(ClientPacket):
    """The packet sent by the client issuing a command to the server."""
    def __init__(self, sequence: int, command: str):
        buffer = self._get_initial_message(PacketType.COMMAND)
        buffer.append(sequence)
        buffer.extend(command.encode('ascii'))

        message = bytes(buffer)
        header = self._encode_header(message)
        super().__init__(header + message)

    def __repr__(self):
        return '{}({!r}, {!r})'.format(type(self).__name__, self.sequence, self.message)

    @property
    def login_success(self) -> None: ...

    @property
    def sequence(self) -> int:
        return self.data[8]

    @property
    def total(self) -> None: ...

    @property
    def index(self) -> None: ...

    @property
    def message(self) -> str:
        return self.data[9:].decode('ascii')


class ClientMessagePacket(ClientPacket):
    """The packet sent to acknowledge a given server message."""
    def __init__(self, sequence: int):
        buffer = self._get_initial_message(PacketType.MESSAGE)
        buffer.append(sequence)

        message = bytes(buffer)
        header = self._encode_header(message)
        super().__init__(header + message)

    def __repr__(self):
        return '{}({!r})'.format(type(self).__name__, self.sequence)

    @property
    def login_success(self) -> None: ...

    @property
    def sequence(self) -> int:
        return self.data[8]

    @property
    def total(self) -> None: ...

    @property
    def index(self) -> None: ...

    @property
    def message(self) -> None: ...


class ServerPacket(Packet):
    """The base class used for packets sent by the server."""


class ServerLoginPacket(ServerPacket):
    """The packet indicating if login was successful."""
    def __init__(self, success: bool):
        buffer = self._get_initial_message(PacketType.LOGIN)
        buffer.append(1 if success else 0)

        message = bytes(buffer)
        header = self._encode_header(message)
        super().__init__(header + message)

    def __repr__(self):
        return '{}({!r})'.format(type(self).__name__, self.login_success)

    @property
    def login_success(self) -> bool:
        return bool(self.data[8])

    @property
    def sequence(self) -> None: ...

    @property
    def total(self) -> None: ...

    @property
    def index(self) -> None: ...

    @property
    def message(self) -> None: ...


class ServerCommandPacket(ServerPacket):
    """The packet(s) sent in response to a command."""
    def __init__(self, sequence: int, total: int, index: int, response: str):
        buffer = self._get_initial_message(PacketType.COMMAND)
        buffer.append(sequence)
        if total != 1:
            buffer.extend((0, total, index))
        buffer.extend(response.encode('ascii'))

        message = bytes(buffer)
        header = self._encode_header(message)
        super().__init__(header + message)

    def __repr__(self):
        return '{}({!r}, {!r}, {!r}, {!r})'.format(
            type(self).__name__,
            self.sequence,
            self.total,
            self.index,
            self.message
        )

    @property
    def login_success(self) -> None: ...

    @property
    def sequence(self) -> int:
        return self.data[8]

    @property
    def total(self) -> int:
        if len(self.data) > 9 and self.data[9] == 0:
            return self.data[10]
        return 1

    @property
    def index(self) -> int:
        if len(self.data) > 9 and self.data[9] == 0:
            return self.data[11]
        return 0

    @property
    def message(self) -> str:
        if len(self.data) > 9 and self.data[9] == 0:
            return self.data[12:].decode('ascii')
        return self.data[9:].decode('ascii')


class ServerMessagePacket(ServerPacket):
    """The packet sent to share a message to the client."""
    def __init__(self, sequence: int, message: str):
        buffer = self._get_initial_message(PacketType.MESSAGE)
        buffer.append(sequence)
        buffer.extend(message.encode('ascii'))

        message = bytes(buffer)
        header = self._encode_header(message)
        super().__init__(header + message)

    def __repr__(self):
        return '{}({!r}, {!r})'.format(type(self).__name__, self.sequence, self.message)

    @property
    def login_success(self) -> None: ...

    @property
    def sequence(self) -> int:
        return self.data[8]

    @property
    def total(self) -> None: ...

    @property
    def index(self) -> None: ...

    @property
    def message(self) -> str:
        return self.data[9:].decode('ascii')
