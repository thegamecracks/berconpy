import asyncio
import collections
import itertools
import logging
import time
from typing import TYPE_CHECKING, Any

from .errors import LoginFailure, RCONCommandError
from .packet import *
from .utils import EMPTY

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .client import AsyncRCONClient


def should_replace_future(fut: asyncio.Future | None) -> bool:
    return fut is None or fut.done()


class RCONClientDatagramProtocol:
    RUN_INTERVAL = 1
    KEEP_ALIVE_INTERVAL = 30
    PLAYERS_INTERVAL = 60
    LAST_RECEIVED_TIMEOUT = 45  # don't change, specified by protocol

    COMMAND_ATTEMPTS = 3
    COMMAND_INTERVAL = 1

    INITIAL_CONNECT_ATTEMPTS = 3
    CONNECTION_TIMEOUT = 3

    RECEIVED_SEQUENCES_SIZE = 5

    _multipart_packets: dict[int, list[ServerCommandPacket]]
    _next_sequence: int
    _received_sequences: collections.deque[int]
    _command_queue: dict[int, asyncio.Future[str]]

    _addr: tuple[str, int] | None
    _last_command: float
    _last_received: float
    _last_sent: float  # NOTE: unused
    _last_players: float

    _is_logged_in: asyncio.Future[bool] | None
    _is_closing: asyncio.Future | None

    def __init__(self, client: "AsyncRCONClient"):
        self.client = client

        self._running_event = asyncio.Event()
        self._transport: asyncio.DatagramTransport | None = None

        self.reset()

    def reset_cache(self):
        self._multipart_packets = collections.defaultdict(list)
        self._next_sequence = 0
        self._received_sequences = collections.deque((), self.RECEIVED_SEQUENCES_SIZE)
        self._command_queue = {}

    def reset(self):
        self.reset_cache()

        mono = time.monotonic()
        self._addr = None
        self._last_command = mono
        self._last_received = mono
        self._last_sent = mono
        self._last_players = mono

        self._is_logged_in = None
        self._is_closing = None

        self._running_event.clear()

    def is_logged_in(self) -> bool | None:
        if self._is_logged_in is not None and self._is_logged_in.done():
            return self._is_logged_in.result()
        return None

    def is_connected(self) -> bool:
        return self._transport is not None

    def is_running(self) -> bool:
        return self._running_event.is_set()

    # Event handling

    def _dispatch(self, event: str, *args):
        self.client._dispatch(event, *args)

    def _dispatch_packet(self, packet: ServerPacket):
        if isinstance(packet, ServerLoginPacket):
            assert packet.login_success
            self._dispatch('login')
        elif isinstance(packet, ServerCommandPacket):
            if packet.sequence in self._command_queue:
                self._dispatch('command', packet.message)
        elif isinstance(packet, ServerMessagePacket):
            # Ensure repeat messages are not redispatched
            if packet.sequence in self._received_sequences:
                return
            self._received_sequences.append(packet.sequence)
            self._dispatch('message', packet.message)
        else:
            raise RuntimeError(f'unhandled Packet type {type(packet)}')

    def _handle_multipart_packet(
        self, packet: ServerCommandPacket
    ) -> str | None:
        seq = self._multipart_packets[packet.sequence]
        seq.append(packet)

        if len(seq) < packet.total:
            return

        message = ''.join(p.message for p in seq)
        new_packet = ServerCommandPacket(
            packet.sequence, packet.total, packet.index, message
        )
        self._dispatch_packet(new_packet)

        del self._multipart_packets[packet.sequence]

        return message

    # Helper methods

    def _get_next_sequence(self) -> int:
        sequence = self._next_sequence
        self._next_sequence = (sequence + 1) % 256
        return sequence

    def _send(self, packet: ClientPacket, addr: Any = EMPTY):
        if addr is EMPTY:
            addr = self._addr
        self._transport.sendto(packet.data, addr)
        log.debug(f'sent {packet.type.name} packet')

        self._last_sent = time.monotonic()
        if isinstance(packet, ClientCommandPacket):
            self._last_command = self._last_sent

    def _send_keep_alive(self):
        sequence = self._get_next_sequence()

        if time.monotonic() - self._last_players > self.PLAYERS_INTERVAL:
            self._last_players = time.monotonic()
            packet = ClientCommandPacket(sequence, 'players')
            self._send(packet)

            asyncio.create_task(
                self._wait_for_player_ping(sequence),
                name=f'berconpy-ping-{sequence}'
            )
        else:
            packet = ClientCommandPacket(sequence, '')
            self._send(packet)

            # We don't care about the response itself, but we still
            # add it to _command_queue so `on_command` can ignore duplicates
            asyncio.create_task(
                self._wait_for_ping(sequence),
                name=f'berconpy-ping-{sequence}'
            )

    async def _wait_for_ping(self, sequence: int):
        try:
            return await asyncio.wait_for(
                self._wait_for_command(sequence),
                timeout=5
            )
        except asyncio.TimeoutError:
            pass

    async def _wait_for_player_ping(self, sequence: int):
        response = await self._wait_for_ping(sequence)
        if response is not None:
            self.client._update_players(response)

    def _tick(self):
        self._last_received = time.monotonic()

    async def wait_for_login(self) -> bool | None:
        """Waits indefinitely until the client has received a login response
        or the connection has closed.

        This can also raise any exception when the connection finishes closing.

        :returns:
            True if authenticated or None if the connection closed
            without an error.
        :raises LoginFailure:
            The password given to the server was denied.

        """
        # This method may be called before run() so we need to
        # make sure the futures are initialized with something
        loop = asyncio.get_running_loop()
        if self._is_logged_in is None:
            self._is_logged_in = loop.create_future()
        if self._is_closing is None:
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

    def _set_command(self, packet: ServerCommandPacket, message: str = None):
        """Notifies the future waiting on a command response packet.

        An alternative message may be given if the packet itself does
        not contain the full message (i.e. multipart packet).

        If no future was created for the packet, this is a no-op.

        """
        if message is None:
            message = packet.message

        fut = self._command_queue.pop(packet.sequence, None)
        if fut is not None:
            fut.set_result(message)

    async def _send_command(self, command: str) -> str:
        """Attempts to send a command to the server and
        read the server's response.

        :param command: The ASCII command string to send.
        :returns: The server's response as a string.
        :raises RuntimeError:
            The server failed to respond to all attempts

        """
        sequence = self._get_next_sequence()
        packet = ClientCommandPacket(sequence, command)

        for _ in range(self.COMMAND_ATTEMPTS):
            self._send(packet)

            try:
                # NOTE: if we let wait_for() cancel the future, it is possible
                # for _set_command() to be called just before our finally
                # statement is reached, allowing _set_command() to throw
                # an InvalidStateError.
                return await asyncio.wait_for(
                    asyncio.shield(self._wait_for_command(sequence)),
                    timeout=self.COMMAND_INTERVAL
                )
            except asyncio.TimeoutError:
                pass
            finally:
                self._cancel_command(sequence)

        log.warning(f'could not send command after {self.COMMAND_ATTEMPTS} attempts')
        raise RCONCommandError(f'failed to send command: {command}')

    def _wait_for_command(self, sequence: int) -> asyncio.Future[str]:
        """Returns a future waiting for a command response with
        the given sequence number.
        """
        fut = self._command_queue.get(sequence)
        if fut is None:
            loop = asyncio.get_running_loop()
            self._command_queue[sequence] = fut = loop.create_future()

        return fut

    # Connection methods

    async def _authenticate(self, password: str) -> bool | None:
        """Sends an authentication packet to the server and waits
        for a response.
        """
        packet = ClientLoginPacket(password)
        self._send(packet)

        return await self.wait_for_login()

    async def connect(self, password: str) -> bool | None:
        """Creates a connection to the given address.

        If necessary, any previous connection will be closed
        before creating a new connection.

        :returns:
            True if authenticated or None if the connection closed
            without an error.
        :raises LoginFailure:
            The password given to the server was denied.
        :raises OSError:
            An error occurred while attempting to connect to the server.

        """
        log.debug('attempting a new connection')
        if self.is_connected():
            self.disconnect()

        loop = asyncio.get_running_loop()
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: self,  # type: ignore
            remote_addr=self._addr
        )

        return await self._authenticate(password)

    def disconnect(self):
        if self._transport is not None:
            self._transport.close()
            self._transport = None

    def close(self, exc: Exception = None):
        if self._is_closing is None or self._is_closing.done():
            return
        elif exc is not None:
            self._is_closing.set_exception(exc)
        else:
            self._is_closing.set_result(None)

    async def run(self, ip: str, port: int, password: str):
        loop = asyncio.get_running_loop()
        first_iteration = True

        self._addr = (ip, port)
        self._running_event.set()
        if should_replace_future(self._is_closing):
            self._is_closing = loop.create_future()

        try:
            while not self._is_closing.done():
                if self._is_logged_in is None or not self._is_logged_in.done():
                    log.info('attempting to {re}connect to server'.format(
                        re='re' * (not first_iteration)
                    ))

                    if should_replace_future(self._is_logged_in):
                        self._is_logged_in = loop.create_future()

                    attempts = itertools.count()
                    if first_iteration:
                        attempts = range(self.INITIAL_CONNECT_ATTEMPTS)

                    for i in attempts:
                        try:
                            await asyncio.wait_for(
                                self.connect(password),
                                timeout=self.CONNECTION_TIMEOUT
                            )
                            break
                        except (asyncio.TimeoutError, OSError):
                            # NOTE: we don't want to retry after a LoginFailure
                            # since that indicates invalid credentials
                            if i % 10 == 0:
                                log.warning('failed {:,d} login attempt{s}'.format(
                                    i + 1, s='s' * (i != 0)
                                ))

                            # exponential backoff
                            self.disconnect()
                            await asyncio.sleep(2 ** (i % 11))

                    if not self._is_logged_in.done():
                        log.error('failed to connect to the server')
                        raise LoginFailure('could not connect to the server')
                    elif self._is_logged_in.exception():
                        log.error('password authentication was denied')
                        raise self._is_logged_in.exception()

                if (overtime := time.monotonic() - self._last_received) > self.LAST_RECEIVED_TIMEOUT:
                    log.info(f'server has timed out (last received {overtime:.0f} seconds ago)')
                    self.reset_cache()
                    self._is_logged_in = loop.create_future()
                    continue
                elif time.monotonic() - self._last_command > self.KEEP_ALIVE_INTERVAL:
                    log.debug('sending keep alive packet')
                    self._send_keep_alive()

                await asyncio.sleep(self.RUN_INTERVAL)
                first_iteration = False
        except Exception as e:
            self.close(e)
            raise
        else:
            self.close()
        finally:
            self.disconnect()
            self.reset()

    # DatagramProtocol

    def connection_made(self, transport):
        log.debug('protocol has connected')

    def connection_lost(self, exc: Exception | None):
        if exc:
            log.error('protocol has disconnected with error', exc_info=exc)
        else:
            log.debug('protocol has disconnected')

    def datagram_received(self, data: bytes, addr):
        if addr != self._addr:
            return log.debug(f'ignoring message from unknown address: {addr}')

        try:
            packet: ServerPacket = Packet.from_bytes(data)
        except (IndexError, ValueError) as e:
            return log.debug(f'ignoring malformed data with cause: {e}')

        self._tick()
        log.debug(f'{packet.type.name} received')
        self._dispatch('raw_event', packet)

        if isinstance(packet, ServerLoginPacket):
            if self._is_logged_in.done():
                return

            if packet.login_success:
                self._is_logged_in.set_result(True)
                self._dispatch_packet(packet)
            else:
                self._is_logged_in.set_exception(
                    LoginFailure('invalid password provided')
                )

        elif isinstance(packet, ServerCommandPacket):
            # NOTE: dispatch must happen before _set_command(),
            # otherwise the on_command event won't know we queued the command
            if packet.total is not None:
                message = self._handle_multipart_packet(packet)
                if message is not None:
                    self._set_command(packet, message)
            else:
                self._dispatch_packet(packet)
                self._set_command(packet)

        elif isinstance(packet, ServerMessagePacket):
            self._dispatch_packet(packet)

            ack = ClientMessagePacket(packet.sequence)
            self._send(ack, addr)

        else:
            raise RuntimeError(f'unhandled Packet type {type(packet)}')

    def error_received(self, exc: OSError):
        log.error('unusual error occurred during session', exc_info=exc)
