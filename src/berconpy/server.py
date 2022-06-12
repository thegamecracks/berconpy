import asyncio
import logging
import math

from .client import AsyncRCONClient
from .packet import Packet, PacketType
from .protocol import RCONClientDatagramProtocol

log = logging.getLogger(__name__)


class RCONServerDatagramProtocol(RCONClientDatagramProtocol):
    def __init__(self, server: "AsyncRCONServer"):
        self.server = server

        self._transport: asyncio.DatagramTransport | None = None

    @property
    def name(self):
        return self.server.name

    async def run(self, ip: str, port: int):
        loop = asyncio.get_running_loop()
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: self,  # type: ignore
            local_addr=(ip, port)
        )

    # DatagramProtocol

    def connection_made(self, transport):
        log.info(f'{self.name}: ready to accept connections')

    def connection_lost(self, exc: Exception | None):
        if exc:
            log.error(f'{self.name}: connection has closed with error', exc_info=exc)
        else:
            log.info(f'{self.name}: connection has been closed')

    def datagram_received(self, data: bytes, addr):
        try:
            packet = Packet.from_bytes(data, from_client=True)
        except ValueError as e:
            return log.debug(f'{self.name}: failed to decode received data: {e}')

        log.debug(f'{self.name}: {packet.ptype.name} packet received')

        if packet.ptype is PacketType.LOGIN:
            ack = Packet(
                PacketType.LOGIN,
                packet.message == self.server.password,
                None, None, b''
            )
            self._send(ack, addr)
        elif packet.ptype is PacketType.COMMAND:
            self._send(packet, addr)

    def error_received(self, exc: OSError):
        log.error(f'{self.name}: unusual error occurred during session', exc_info=exc)


class AsyncRCONServer(AsyncRCONClient):
    """A mock server intended for testing."""
    def __init__(self, *args, password: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.password = password.encode('ascii')
        self._protocol = RCONServerDatagramProtocol(self)

    async def host(self, ip: str, port: int):
        await self._protocol.run(ip, port)
        await asyncio.sleep(math.inf)
