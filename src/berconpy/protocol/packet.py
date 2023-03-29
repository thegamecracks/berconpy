"""
Defines the various packets that can be sent and received between
the client and server.
"""
import binascii
import enum
import functools
from typing import Literal, Type, overload

__all__ = (
    "PacketType",
    "Packet",
    "ClientPacket",
    "ServerPacket",
    "ClientLoginPacket",
    "ClientCommandPacket",
    "ClientMessagePacket",
    "ServerLoginPacket",
    "ServerCommandPacket",
    "ServerMessagePacket",
)


def _convert_exception(
    from_exc: Type[Exception],
    to_exc: Type[Exception],
    message: str | None = None,
):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except from_exc as e:
                if message is not None:
                    raise to_exc(message) from e
                raise to_exc from e

        return wrapper

    return decorator


class PacketType(enum.Enum):
    """The type of packet received by the server.

    Each :py:class:`Packet` instance falls under one of these types
    and can be checked through the :py:attr:`Packet.type` property.

    The :py:attr:`value` of this enum directly corresponds with the
    :download:`protocol specification </BERConProtocol.txt>`.

    .. note::

        This type can also be inferred from the packet's class as
        subclasses directly correspond to the message type they are
        representing in the protocol (a.k.a. typestates_).

    .. _typestates: https://en.wikipedia.org/wiki/Typestate_analysis

    """

    LOGIN = 0x00
    """Used for the login process initiated by the client."""

    COMMAND = 0x01
    """Used for command/response exchanges between the client and server."""

    MESSAGE = 0x02
    """
    Used for messages indicating activity on the server
    and acknowledgements by the client.
    """


class Packet:
    """The base class used for all messages sent between
    the BattlEye RCON server and client.

    For more details, see the :download:`official protocol specification </BERConProtocol.txt>`.

    Several properties are defined here but are not implemented.
    Those properties correspond to the built-in subclasses, which can be
    instantiated through either their custom constructors or from this
    class's :py:meth:`from_bytes()` method.

    Only a few properties are guaranteed:
        1. :py:attr:`checksum`
        2. :py:attr:`type`

    Every other property may return ``None`` if the subclass's usage
    does not require it.

    :param data: The binary data contained by the packet.

    """

    __slots__ = ("data",)

    def __init__(self, data: bytes):
        over_size = len(data) - 65507
        if over_size > 0:
            raise ValueError(f"max packet size exceeded by {over_size} bytes")

        self.data = data

    def __repr__(self):
        return "{}({!r})".format(type(self).__name__, self.data)

    @property
    def checksum(self) -> int:
        """The CRC32 checksum included in the header."""
        return int.from_bytes(self.data[2:6], "little")

    @property
    def type(self) -> PacketType:
        """The packet's type defined in the protocol.

        This property is computed from the :py:attr:`data` attribute
        of the packet which in typical cases should correspond
        with the type of the class itself.

        .. seealso:: :py:class:`PacketType`

        """
        return PacketType(self.data[7])

    @property
    def login_success(self) -> bool | None:
        """A boolean indicating if the server authenticated the client."""

    @property
    def sequence(self) -> int | None:
        """The sequence number of the COMMAND or MESSAGE packet."""

    @property
    def total(self) -> int | None:
        """The total number of packets associated with a
        COMMAND server response.

        If a sub-header is not provided with the response,
        this defaults to 1.

        """

    @property
    def index(self) -> int | None:
        """The zero-based index of the packet associated with a
        COMMAND server response.

        If a sub-header is not provided with the response,
        this defaults to 0.

        """

    @property
    def message(self) -> bytes | None:
        """The message that was sent to the client/server.

        While returned as bytes, this should be decodable as a UTF-8
        string, with the exception of :py:class:`ServerMessagePacket`
        objects which only need to be decodable when all of the messages
        are joined together.

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
            raise ValueError("CRC32 checksum does not match the given data")
        return self

    @classmethod
    @overload
    def from_bytes(cls, data: bytes, *, from_client: Literal[True]) -> "ClientPacket":
        ...

    @classmethod
    @overload
    def from_bytes(cls, data: bytes, *, from_client: Literal[False]) -> "ServerPacket":
        ...

    @classmethod
    @_convert_exception(IndexError, ValueError, "insufficient data provided")
    def from_bytes(cls, data: bytes, *, from_client: bool) -> "Packet":
        """Constructs a packet from the given data.

        :param data: The data to parse.
        :param from_client:
            Whether the packet came from the server or client.
            This is required for disambiguation of data.
        :returns: The corresponding subclass of Packet.
        :raises ValueError:
            The given data is malformed and does not match the
            packet specification.

        """
        if data[:2] != b"BE":
            raise ValueError("expected BE as start of header")
        elif data[6] != 255:
            raise ValueError("expected 0xFF at end of header")

        crc = int.from_bytes(data[2:6], "little")

        try:
            ptype = PacketType(data[7])
        except ValueError:
            raise ValueError(f"unknown packet type: {data[7]}") from None

        if ptype is PacketType.LOGIN and from_client:
            if b"\x00" in data[8:]:
                raise ValueError("login password cannot have a null byte")
            return ClientLoginPacket(data[8:]).assert_checksum(crc)

        elif ptype is PacketType.LOGIN and not from_client:
            if data[8] not in (0, 1):
                raise ValueError("authentication byte must be 0 or 1")
            elif len(data[8:]) != 1:
                raise ValueError("unexpected excess data after authentication byte")
            return ServerLoginPacket(bool(data[8])).assert_checksum(crc)

        elif ptype is PacketType.COMMAND and from_client:
            sequence = data[8]
            command = data[9:]
            return ClientCommandPacket(sequence, command).assert_checksum(crc)

        elif ptype is PacketType.COMMAND and not from_client:
            sequence = data[8]
            if len(data) > 9 and data[9] == 0:
                total, index = data[10], data[11]
                response = data[12:]
            else:
                total, index = 1, 0
                response = data[9:]

            if index >= total:
                raise ValueError(
                    f"index ({index}) cannot equal or exceed total ({total})"
                )
            packet = ServerCommandPacket(sequence, total, index, response)
            return packet.assert_checksum(crc)

        elif ptype is PacketType.MESSAGE and from_client:
            sequence = data[8]
            return ClientMessagePacket(sequence).assert_checksum(crc)

        elif ptype is PacketType.MESSAGE and not from_client:
            sequence = data[8]
            message = data[9:]
            return ServerMessagePacket(sequence, message).assert_checksum(crc)

        raise RuntimeError(  # pragma: no cover
            f"unhandled PacketType enum: {ptype} (from_client: {from_client})"
        )

    @staticmethod
    def _encode_header(message: bytes):
        crc = binascii.crc32(message).to_bytes(4, "little")
        return b"BE" + crc

    @staticmethod
    def _get_initial_message(packet_type: PacketType) -> bytearray:
        return bytearray((0xFF, packet_type.value))


class ClientPacket(Packet):
    """The base class for packets sent by the client.

    The subclasses of this packet are:

    - :py:class:`ClientLoginPacket`
    - :py:class:`ClientCommandPacket`
    - :py:class:`ClientMessagePacket`

    """


class ClientLoginPacket(ClientPacket):
    """The packet used to log in a client.

    :param password: The password to use when logging in.

    """

    def __init__(self, password: bytes):
        buffer = self._get_initial_message(PacketType.LOGIN)
        buffer.extend(password)

        payload = bytes(buffer)
        header = self._encode_header(payload)
        super().__init__(header + payload)

    def __repr__(self):
        return "{}({!r})".format(type(self).__name__, self.message)

    @property
    def login_success(self) -> None:
        ...

    @property
    def sequence(self) -> None:
        ...

    @property
    def total(self) -> None:
        ...

    @property
    def index(self) -> None:
        ...

    @property
    def message(self) -> bytes:
        return self.data[8:]


class ClientCommandPacket(ClientPacket):
    """The packet sent by the client issuing a command to the server.

    :param sequence: The sequence number identifying the packet.
    :param command: The command to send to the server.

    """

    def __init__(self, sequence: int, command: bytes):
        buffer = self._get_initial_message(PacketType.COMMAND)
        buffer.append(sequence)
        buffer.extend(command)

        payload = bytes(buffer)
        header = self._encode_header(payload)
        super().__init__(header + payload)

    def __repr__(self):
        return "{}({!r}, {!r})".format(type(self).__name__, self.sequence, self.message)

    @property
    def login_success(self) -> None:
        ...

    @property
    def sequence(self) -> int:
        return self.data[8]

    @property
    def total(self) -> None:
        ...

    @property
    def index(self) -> None:
        ...

    @property
    def message(self) -> bytes:
        return self.data[9:]


class ClientMessagePacket(ClientPacket):
    """The packet sent to acknowledge a given server message.

    :param sequence: The sequence number of the message being acknowledged.

    """

    def __init__(self, sequence: int):
        buffer = self._get_initial_message(PacketType.MESSAGE)
        buffer.append(sequence)

        payload = bytes(buffer)
        header = self._encode_header(payload)
        super().__init__(header + payload)

    def __repr__(self):
        return "{}({!r})".format(type(self).__name__, self.sequence)

    @property
    def login_success(self) -> None:
        ...

    @property
    def sequence(self) -> int:
        return self.data[8]

    @property
    def total(self) -> None:
        ...

    @property
    def index(self) -> None:
        ...

    @property
    def message(self) -> None:
        ...


class ServerPacket(Packet):
    """The base class used for packets sent by the server.

    The subclasses of this packet are:

    - :py:class:`ServerLoginPacket`
    - :py:class:`ServerCommandPacket`
    - :py:class:`ServerMessagePacket`

    """


class ServerLoginPacket(ServerPacket):
    """The packet indicating if login was successful.

    :param success: Indicates if the server has authenticated the client.

    """

    def __init__(self, success: bool):
        buffer = self._get_initial_message(PacketType.LOGIN)
        buffer.append(1 if success else 0)

        payload = bytes(buffer)
        header = self._encode_header(payload)
        super().__init__(header + payload)

    def __repr__(self):
        return "{}({!r})".format(type(self).__name__, self.login_success)

    @property
    def login_success(self) -> bool:
        return bool(self.data[8])

    @property
    def sequence(self) -> None:
        ...

    @property
    def total(self) -> None:
        ...

    @property
    def index(self) -> None:
        ...

    @property
    def message(self) -> None:
        ...


class ServerCommandPacket(ServerPacket):
    """The packet(s) sent in response to a command.

    :param sequence: The sequence number of the command being responded to.
    :param total: The number of packets included in the response.
    :param index: The packet's index in the response, starting at 0.
    :param response:
        The contents contained in the response,
        or part of the response if this content is split across
        multiple packets.
    :raises ValueError: Either the total was 0 or the index was out of bounds.

    """

    def __init__(self, sequence: int, total: int, index: int, response: bytes):
        buffer = self._get_initial_message(PacketType.COMMAND)
        buffer.append(sequence)
        if total < 1:
            raise ValueError(f"total must be 1 or higher, not {total!r}")
        elif index not in range(total):
            raise ValueError(f"index must be below {total - 1}, not {index}")
        elif total != 1:
            buffer.extend((0, total, index))
        buffer.extend(response)

        payload = bytes(buffer)
        header = self._encode_header(payload)
        super().__init__(header + payload)

    def __repr__(self):
        return "{}({!r}, {!r}, {!r}, {!r})".format(
            type(self).__name__, self.sequence, self.total, self.index, self.message
        )

    @property
    def login_success(self) -> None:
        ...

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
    def message(self) -> bytes:
        if len(self.data) > 9 and self.data[9] == 0:
            return self.data[12:]
        return self.data[9:]


class ServerMessagePacket(ServerPacket):
    """The packet sent to share a message to the client.

    :param sequence: The sequence number identifying the message.
    :param message: The contents contained in the message.

    """

    def __init__(self, sequence: int, message: bytes):
        buffer = self._get_initial_message(PacketType.MESSAGE)
        buffer.append(sequence)
        buffer.extend(message)

        payload = bytes(buffer)
        header = self._encode_header(payload)
        super().__init__(header + payload)

    def __repr__(self):
        return "{}({!r}, {!r})".format(type(self).__name__, self.sequence, self.message)

    @property
    def login_success(self) -> None:
        ...

    @property
    def sequence(self) -> int:
        return self.data[8]

    @property
    def total(self) -> None:
        ...

    @property
    def index(self) -> None:
        ...

    @property
    def message(self) -> bytes:
        return self.data[9:]
