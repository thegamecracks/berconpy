import binascii
import enum
import struct

from .utils import unpack_from

_BYTE = struct.Struct('!B')
_HEADER = struct.Struct('<2cI')  # b'BE' | CRC32 checksum
_TYPE_SEQ = struct.Struct('!BB')
_TOTAL_INDEX = struct.Struct('!xBB')


class PacketType(enum.Enum):
    LOGIN = 0x00
    COMMAND = 0x01
    MESSAGE = 0x02


class Packet:
    """A raw BattlEye RCON message packet.

    The protocol specification can be found here:
    https://www.battleye.com/downloads/BERConProtocol.txt

    :param ptype: The message type of the packet.
    :param sequence:
        For LOGIN packets, this is either -1 for a client login packet,
        0 for failure, or 1 for success (sent by server).
        For COMMAND and MESSAGE packets, this is sequence number
        of the message (in the range 0-255).
    :param total:
        The total number of packets being sent for the message
        (in the range 0-255), or None if not applicable.
    :param index:
        The 0-based index of the current packet associated with
        the total packets, or None if not applicable.
    :param message: An ASCII string.

    """
    __slots__ = ('ptype', 'sequence', 'total', 'index', 'message')

    def __init__(
        self,
        ptype: PacketType,
        sequence: int,
        total: int | None,
        index: int | None,
        message: bytes
    ):
        self.ptype = ptype
        self.sequence = sequence
        self.total = total
        self.index = index
        self.message = message

    def __repr__(self):
        return '{}({!r}, {!r}, {!r}, {!r}, {!r})'.format(
            type(self).__name__,
            self.ptype,
            self.sequence,
            self.total,
            self.index,
            self.message
        )

    @classmethod
    def from_bytes(cls, data: bytes, *, from_client=False):
        """Constructs a packet from the given data.

        :raises ValueError:
            The given data is malformed and does not match the
            packet specification.

        """
        (*be, crc), data = unpack_from(_HEADER, data)
        (ff,), data = unpack_from(_BYTE, data)
        if b''.join(be) != b'BE':
            raise ValueError('expected BE as start of header')
        elif ff != 255:
            raise ValueError('expected 0xFF at end of header')

        (ptype,), data = unpack_from(_BYTE, data)
        try:
            ptype = PacketType(ptype)
        except ValueError:
            raise ValueError(f'unknown packet type: {ptype}') from None

        if ptype is PacketType.LOGIN and from_client:
            sequence = -1
        else:
            (sequence,), data = unpack_from(_BYTE, data)

        total = index = None
        if ptype is PacketType.COMMAND and data.startswith(b'\x00'):
            (total, index), data = unpack_from(_TOTAL_INDEX, data)

        packet = cls(ptype, sequence, total, index, data)
        if packet.crc32 != crc:
            raise ValueError('CRC32 checksum does not match the given data')

        return packet

    @property
    def crc32(self):
        """Returns the CRC32 checksum of the message, excluding the header."""
        return binascii.crc32(self._encode_message())

    def _encode_header(self, message: bytes):
        crc = binascii.crc32(message)
        return _HEADER.pack(b'B', b'E', crc)

    def _encode_message(self):
        # NOTE: 0xFF byte is really part of the header, but it must
        # be included in checksum, so we're putting it here
        buffer = bytearray([0xFF])

        if self.ptype == PacketType.LOGIN:
            if self.sequence == -1:
                # Use message as password
                # NOTE: -1 is a non-standard marker for login packets
                buffer.append(self.ptype.value)
                buffer.extend(self.message)
            else:
                buffer.extend(_TYPE_SEQ.pack(self.ptype.value, self.sequence))

        else:
            buffer.extend(_TYPE_SEQ.pack(self.ptype.value, self.sequence))

            if self.total is not None or self.index is not None:
                buffer.extend(_TOTAL_INDEX.pack(self.total, self.index))

            buffer.extend(self.message)

        return bytes(buffer)

    def to_bytes(self):
        message = self._encode_message()
        header = self._encode_header(message)
        return header + message
