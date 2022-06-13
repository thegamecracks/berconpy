import asyncio
import collections
import logging
import time
from typing import TYPE_CHECKING, Any

from .packet import Packet, PacketType
from .utils import EMPTY

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .client import AsyncRCONClient


def should_replace_future(fut: asyncio.Future | None):
    return fut is None or fut.done()


class RCONClientDatagramProtocol:
    RUN_INTERVAL = 1
    KEEP_ALIVE_INTERVAL = 30  # NOTE: server times out after 45 seconds

    COMMAND_ATTEMPTS = 3
    COMMAND_INTERVAL = 1

    LAST_RECEIVED_TIMEOUT = 45

    RECONNECT_ATTEMPTS = 3
    RECONNECT_INTERVAL = 2

    def __init__(self, client: "AsyncRCONClient"):
        self.client = client

        self._multipart_packets: dict[int, list[Packet]] = collections.defaultdict(list)
        self._next_sequence = 0  # 0-255
        self._command_queue: dict[int, asyncio.Future[str]] = {}

        mono = time.monotonic()
        self._last_command = mono
        self._last_received = mono
        self._last_sent = mono

        self._is_logged_in: asyncio.Future[bool] | None = None
        self._is_closing: asyncio.Future | None = None

        self._running_event = asyncio.Event()

        self._transport: asyncio.DatagramTransport | None = None

    def is_logged_in(self):
        """Indicates if the client is currently authenticated with the server.

        :returns:
            True if authenticated or None if no
            response has been received from the server.
        :raises ValueError:
            The password given to the server was denied.

        """
        if self._is_logged_in is not None and self._is_logged_in.done():
            return self._is_logged_in.result()
        return None

    def is_connected(self):
        """Indicates if the client has a currently active connection
        with the server.
        """
        return self._transport is not None

    def is_running(self):
        """Indicates if the client is running. This may not necessarily
        mean that the client is connected.
        """
        return self._running_event.is_set()

    @property
    def name(self):
        return self.client.name

    # Event handling

    def _dispatch(self, event: str, *args):
        self.client._dispatch(event, *args)

    def _dispatch_packet(self, packet: Packet):
        if packet.ptype is PacketType.LOGIN:
            return self._dispatch(packet.ptype.name.lower())

        self._dispatch(
            packet.ptype.name.lower(),
            packet.message.decode('ascii')
        )

    def _handle_multipart_packet(self, packet: Packet):
        seq = self._multipart_packets[packet.sequence]
        seq.append(packet)

        if len(seq) < packet.total:
            return

        message = b''.join(p.message for p in seq)
        self._dispatch(packet.ptype.name.lower(), message)

        del self._multipart_packets[packet.sequence]

        return message

    # Helper methods

    def _get_next_sequence(self):
        sequence = self._next_sequence
        self._next_sequence = (sequence + 1) % 256
        return sequence

    def _send(self, packet: Packet, addr: Any = EMPTY):
        if addr is not EMPTY:
            self._transport.sendto(packet.to_bytes(), addr)
        else:
            self._transport.sendto(packet.to_bytes())
        log.debug(f'{self.name}: sent {packet.ptype.name} packet')

        self._last_sent = time.monotonic()
        if packet.ptype == PacketType.COMMAND:
            self._last_command = self._last_sent

    def _send_keep_alive(self):
        packet = Packet(
            PacketType.COMMAND, self._get_next_sequence(), None, None, b''
        )
        self._send(packet)

    def _tick(self):
        self._last_received = time.monotonic()

    async def wait_for_login(self):
        """Waits indefinitely until the client has received a login response
        or the connection has closed.

        This can also raise any exception when the connection finishes closing.

        :returns:
            True if authenticated or None if the connection closed
            without an error.
        :raises ValueError:
            The password given to the server was denied.

        """
        loop = asyncio.get_running_loop()
        if should_replace_future(self._is_logged_in):
            self._is_logged_in = loop.create_future()
        if should_replace_future(self._is_closing):
            self._is_closing = loop.create_future()

        done, pending = await asyncio.wait(
            (self._is_logged_in, self._is_closing),
            return_when=asyncio.FIRST_COMPLETED
        )

        return done.pop().result()

    # Command methods

    def _cancel_command(self, sequence: int):
        """Cancels the future waiting on a particular command.

        If no future was created, this is a no-op.

        """
        fut = self._command_queue.pop(sequence, None)
        if fut is not None:
            fut.cancel()

    def _set_command(self, packet: Packet, message: str = None):
        """Notifies the future waiting on a command response packet.

        An alternative message may be given if the packet itself does
        not contain the full message (i.e. multipart packet).

        If no future was created for the packet, this is a no-op.

        """
        if message is None:
            message = packet.message.decode('ascii')

        fut = self._command_queue.pop(packet.sequence, None)
        if fut is not None:
            fut.set_result(message)

    async def _send_command(self, command: str):
        """Attempts to send a command to the server and
        read the server's response.

        :param command: The ASCII command string to send.
        :returns: The server's response as a string.
        :raises RuntimeError:
            The server failed to respond to all attempts

        """
        command_bytes = command.encode('ascii')

        # TODO test max packet size
        over_size = len(command_bytes) - 65498  # 65507 - 9 byte header
        if over_size > 0:
            raise ValueError(f'max packet size exceeded by {over_size} bytes')

        sequence = self._get_next_sequence()
        packet = Packet(PacketType.COMMAND, sequence, None, None, command_bytes)

        for _ in range(self.COMMAND_ATTEMPTS):
            self._send(packet)

            try:
                return await asyncio.wait_for(
                    self._wait_for_command(sequence),
                    timeout=self.COMMAND_INTERVAL
                )
            except asyncio.TimeoutError:
                pass

        self._cancel_command(sequence)
        log.warning(f'{self.name}: could not send command '
                    f'after {self.COMMAND_ATTEMPTS} attempts')
        raise RuntimeError(f'failed to send command: {command}')

    def _wait_for_command(self, sequence: int) -> asyncio.Future[str]:
        """Returns a future waiting for a command response with
        the given sequence number.
        """
        if sequence in self._command_queue:
            raise RuntimeError(f'command {sequence} has already been queued')

        loop = asyncio.get_running_loop()
        self._command_queue[sequence] = fut = loop.create_future()
        return fut

    # Connection methods

    async def _authenticate(self, password: bytes):
        """Sends an authentication packet to the server and waits
        for a response.
        """
        packet = Packet(PacketType.LOGIN, -1, None, None, password)
        self._send(packet)

        return await self.wait_for_login()

    async def connect(self, ip: str, port: int, password: bytes):
        """Creates a connection to the given address.

        Note that this does not keep the connection alive,
        and `run()` must be called afterwards to continue
        receiving messages.

        :returns:
            A boolean indicating if the client successfully authenticated
            with the given password.

        """
        loop = asyncio.get_running_loop()

        self.disconnect()
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: self,  # type: ignore
            remote_addr=(ip, port)
        )

        return await self._authenticate(password)

    def disconnect(self):
        if self._transport is not None:
            self._transport.close()
            self._transport = None

    def close(self, exc: Exception = None):
        if self._is_closing.done():
            return
        elif exc is not None:
            self._is_closing.set_exception(exc)
        else:
            self._is_closing.set_result(True)

    async def run(self, ip: str, port: int, password: bytes):
        loop = asyncio.get_running_loop()

        self._running_event.set()
        if should_replace_future(self._is_closing):
            self._is_closing = loop.create_future()

        while not self._is_closing.done():
            if self._is_logged_in is None or not self._is_logged_in.done():
                log.info(f'{self.name}: attempting to (re)connect to server')

                for _ in range(self.RECONNECT_ATTEMPTS):
                    try:
                        if should_replace_future(self._is_logged_in):
                            self._is_logged_in = loop.create_future()

                        await asyncio.wait_for(
                            self.connect(ip, port, password),
                            timeout=self.RECONNECT_INTERVAL
                        )
                        break
                    except asyncio.TimeoutError:
                        pass

                if not self._is_logged_in.done():
                    log.warning(f'{self.name}: failed to (re)connect to the server')
                    self.close(RuntimeError('could not connect to the server'))
                    continue
                elif self._is_logged_in.exception():
                    log.warning(f'{self.name}: password authentication was denied')
                    self.close(self._is_logged_in.exception())
                    continue

            if time.monotonic() - self._last_received > self.LAST_RECEIVED_TIMEOUT:
                log.debug(f'{self.name}: server has timed out')
                self._is_logged_in = loop.create_future()
            elif time.monotonic() - self._last_command > self.KEEP_ALIVE_INTERVAL:
                log.debug(f'{self.name}: sending keep alive packet')
                self._send_keep_alive()

            await asyncio.sleep(self.RUN_INTERVAL)

        # Cleanup and raise any exception
        log.debug(f'{self.name}: disconnecting')
        self.disconnect()
        self._running_event.clear()
        self._is_closing.result()

    # DatagramProtocol

    def connection_made(self, transport):
        log.info(f'{self.name}: connected to server')

    def connection_lost(self, exc: Exception | None):
        if exc:
            log.error(f'{self.name}: connection has closed with error', exc_info=exc)
        else:
            log.info(f'{self.name}: connection has been closed')

    def datagram_received(self, data: bytes, addr):
        try:
            packet = Packet.from_bytes(data)
        except ValueError as e:
            return log.debug(f'{self.name}: failed to decode received data: {e}')

        self._tick()
        log.debug(f'{self.name}: {packet.ptype.name} packet received')
        self._dispatch('raw_event', packet)

        if packet.ptype is PacketType.LOGIN:
            if self._is_logged_in.done():
                return

            if packet.sequence == 1:
                self._is_logged_in.set_result(True)
                self._dispatch_packet(packet)
            else:
                self._is_logged_in.set_exception(
                    ValueError('invalid password provided')
                )

        elif packet.ptype is PacketType.COMMAND:
            if packet.total is not None:
                message = self._handle_multipart_packet(packet)
                if message is not None:
                    self._set_command(packet, message.decode('ascii'))
            else:
                self._dispatch_packet(packet)
                self._set_command(packet)
        elif packet.ptype is PacketType.MESSAGE:
            self._dispatch_packet(packet)

            ack = Packet(PacketType.MESSAGE, packet.sequence, None, None, b'')
            self._send(ack, addr)

    def error_received(self, exc: OSError):
        log.error(f'{self.name}: unusual error occurred during session', exc_info=exc)
