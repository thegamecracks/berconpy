import asyncio
import itertools
import logging
import time
import weakref
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..errors import LoginFailure, RCONCommandError
from ..protocol import (
    ClientAuthEvent,
    ClientEvent,
    ClientCommandPacket,
    ClientPacket,
    ClientCommandEvent,
    RCONClientProtocol,
    ClientMessageEvent,
)

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .client import AsyncRCONClient


def maybe_replace_future(fut: asyncio.Future | None) -> asyncio.Future:
    if fut is None or fut.done():
        return asyncio.get_running_loop().create_future()
    return fut


class AsyncClientProtocol(ABC):
    """
    Provides a bridge between :py:class:`AsyncRCONClient` and the underlying
    I/O implementations.
    """

    LAST_RECEIVED_TIMEOUT = 45  # don't change, specified by protocol

    _client: "AsyncRCONClient | None" = None

    @property
    def client(self) -> "AsyncRCONClient | None":
        return self._client

    @client.setter
    def client(self, new_client: "AsyncRCONClient | None") -> None:
        if new_client is not None:
            new_client = weakref.proxy(new_client)
        self._client = new_client

    @abstractmethod
    def close(self) -> None:
        """Notifies the protocol that it should begin closing."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Indicates if the client has a currently active connection
        with the server.
        """

    @abstractmethod
    def is_logged_in(self) -> bool | None:
        """Indicates if the client is currently authenticated with the server.

        :returns:
            True if authenticated or None if no
            response has been received from the server.
        :raises LoginFailure:
            The password given to the server was denied.

        """

    @abstractmethod
    def is_running(self) -> bool:
        """Indicates if the client is running. This may not necessarily
        mean that the client is connected.
        """

    @abstractmethod
    def run(self, ip: str, port: int, password: str) -> asyncio.Task[None]:
        """Starts maintaining a connection to the given server.

        :returns: A task that will handle connections to the server.
        :raises RuntimeError:
            This method was called while the protocol was already connected.

        """

    @abstractmethod
    def send(self, packet: ClientPacket) -> None:
        """Sends a packet to the server."""

    @abstractmethod
    async def send_command(self, command: str) -> str:
        """Attempts to send a command to the server and
        read the server's response.

        :param command: The command string to send.
        :returns: The server's response as a string.
        :raises RCONCommandError: The server failed to respond to all attempts.

        """

    @abstractmethod
    async def wait_for_login(self) -> bool:
        """Waits indefinitely until the client has received a login response
        or the connection has closed.

        This can also raise any exception when the connection finishes closing.

        :returns: True if authenticated, False otherwise.
        :raises LoginFailure:
            The password given to the server was denied.

        """


class AsyncCommander:
    """Handles sending commands and waiting for responses."""

    io_layer: AsyncClientProtocol | None
    proto_layer: RCONClientProtocol | None

    _command_futures: dict[int, asyncio.Future[str]]

    def __init__(
        self,
        *,
        command_attempts: int = 3,
        command_interval: float = 1.0,
    ) -> None:
        self.io_layer = None
        self.proto_layer = None

        self.command_attempts = command_attempts
        self.command_interval = command_interval
        self.reset()

    def cancel_command(self, sequence: int) -> None:
        """Cancels a command in the protocol along with its associated future.

        If the command sequence was not queued before, this is a no-op.

        """
        if self.proto_layer is None:
            raise RuntimeError("proto_layer must be assigned")

        self.proto_layer.invalidate_command(sequence)
        fut = self._command_futures.pop(sequence, None)
        if fut is not None:
            fut.cancel()

    def reset(self) -> None:
        self._command_futures = {}

    def set_command(self, sequence: int, message: str) -> None:
        """Notifies the future waiting on a command response packet.

        An alternative message may be given if the packet itself does
        not contain the full message (i.e. multipart packet).

        If no future was created for the packet, this is a no-op.

        """
        fut = self._command_futures.pop(sequence, None)
        if fut is not None:
            fut.set_result(message)

    async def send_command(self, command: str) -> str:
        if self.io_layer is None:
            raise RuntimeError("io_layer must be assigned")
        if self.proto_layer is None:
            raise RuntimeError("proto_layer must be assigned")

        packet = self.proto_layer.send_command(command)

        for _ in range(self.command_attempts):
            self.io_layer.send(packet)

            try:
                # NOTE: if we let wait_for() cancel the future, it is possible
                # for _set_command() to be called just before our finally
                # statement is reached, allowing _set_command() to throw
                # an InvalidStateError.
                return await asyncio.wait_for(
                    asyncio.shield(self.wait_for_command(packet.sequence)),
                    timeout=self.command_interval,
                )
            except asyncio.TimeoutError:
                pass
            finally:
                self.cancel_command(packet.sequence)

        log.warning(f"could not send command after {self.command_attempts} attempts")
        raise RCONCommandError(f"failed to send command: {command!r}")

    def wait_for_command(self, sequence: int) -> asyncio.Future[str]:
        """Returns a future waiting for a command response with
        the given sequence number.
        """
        fut = self._command_futures.get(sequence)
        if fut is None:
            loop = asyncio.get_running_loop()
            self._command_futures[sequence] = fut = loop.create_future()

        return fut


@dataclass
class ConnectorConfig:
    """Specifies the configuration used for the :py:class:`AsyncClientConnector`."""

    run_interval: float = 1.0
    """
    The amount of time in seconds to wait between each run loop iteration
    (which handles re-connecting and sending keep alive packets).
    """
    keep_alive_interval: float = 30.0
    """
    The amount of time in seconds should the connection wait from the last
    command before sending another command to keep the connection alive.

    For optimal stability, this interval should be below 45 seconds.
    """
    players_interval: float = 60.0
    """
    The amount of time in seconds from the last keep alive command
    before it should be replaced with a "players" RCON command to
    update the client's cache.

    When set to a value less than :py:attr:`keep_alive_interval`,
    keep alive will always be used to update the cache.
    """

    initial_connect_attempts: int = 3
    """
    The number of attempts that should be done when the RCON client is
    first connecting.

    After a successful connection, this value is ignored and the connector
    will indefinitely attempt to reconnect unless authentication is denied.
    """
    connection_timeout: float = 3.0
    """
    The amount of time in seconds to wait after a login attempt before retrying.
    """


class AsyncClientConnector(AsyncClientProtocol):
    """An asyncio implementation of the :py:class:`AsyncClientProtocol`."""

    _addr: tuple[str, int] | None
    _last_command: float
    _last_received: float
    _last_sent: float  # NOTE: unused
    _last_players: float

    _is_logged_in: asyncio.Future[bool] | None
    _task: asyncio.Task | None

    def __init__(
        self,
        *,
        commander: AsyncCommander | None = None,
        config: ConnectorConfig | None = None,
        protocol: RCONClientProtocol | None = None,
    ):
        if config is None:
            config = ConnectorConfig()
        if protocol is None:
            protocol = RCONClientProtocol()
        if commander is None:
            commander = AsyncCommander()

        super().__init__()
        self.commander = commander
        self.commander.io_layer = weakref.proxy(self)
        self.commander.proto_layer = weakref.proxy(protocol)
        self.config = config
        self.protocol = protocol

        self._close_event = asyncio.Event()
        self._transport: asyncio.DatagramTransport | None = None
        self._reset()

    def close(self) -> None:
        self._close_event.set()

    def is_connected(self) -> bool:
        return self._transport is not None

    def is_logged_in(self) -> bool:
        if self._is_logged_in is not None and self._is_logged_in.done():
            return self._is_logged_in.result()
        return False

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def run(self, ip: str, port: int, password: str) -> asyncio.Task[None]:
        if self.is_running():
            raise RuntimeError("connection is already running")

        self._task = asyncio.create_task(
            self._run_and_handle(ip, port, password),
            name="berconpy-run",
        )
        return self._task

    def send(self, packet: ClientPacket):
        assert self._transport is not None
        self._transport.sendto(packet.data, self._addr)
        log.debug(f"sent {packet.type.name} packet")

        self._last_sent = time.monotonic()
        if isinstance(packet, ClientCommandPacket):
            self._last_command = self._last_sent

    async def send_command(self, command: str) -> str:
        return await self.commander.send_command(command)

    async def wait_for_login(self) -> bool:
        # This method may be called before run() so we need to
        # make sure the futures are initialized with something
        loop = asyncio.get_running_loop()
        if self._is_logged_in is None:
            self._is_logged_in = loop.create_future()

        close_task = asyncio.create_task(
            self._close_event.wait(),
            name="berconpy-wait-for-login",
        )
        done, _ = await asyncio.wait(
            (self._is_logged_in, close_task),
            return_when=asyncio.FIRST_COMPLETED,
        )

        fut = done.pop()
        if fut is self._is_logged_in:
            close_task.cancel()
            return self._is_logged_in.result()
        else:
            # Closed without having connected
            return False

    def _reset(self):
        self._reset_protocol()

        mono = time.monotonic()
        self._addr = None
        self._last_command = mono
        self._last_received = mono
        self._last_sent = mono
        self._last_players = mono

        self._is_logged_in = None
        self._close_event.clear()
        self._task = None

    def _reset_protocol(self):
        self.commander.reset()
        self.protocol.reset()

    # Connection methods

    async def connect(self, password: str) -> bool:
        """Creates a connection to the given address.

        If necessary, any previous connection will be closed
        before creating a new connection.

        :returns:
            True if authenticated or False if the connection closed
            without an error.
        :raises LoginFailure:
            The password given to the server was denied.
        :raises OSError:
            An error occurred while attempting to connect to the server.

        """
        log.debug("attempting a new connection")
        if self.is_connected():
            self.disconnect()

        loop = asyncio.get_running_loop()
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: self,  # type: ignore
            remote_addr=self._addr,
        )

        packet = self.protocol.authenticate(password)
        self.send(packet)

        return await self.wait_for_login()

    def disconnect(self) -> None:
        """Disconnects the protocol from the server."""
        if self._transport is not None:
            self._transport.close()
            self._transport = None

    async def _run_and_handle(self, ip: str, port: int, password: str) -> None:
        self._addr = (ip, port)
        self._close_event.clear()

        try:
            await self._run_loop(password)
        finally:
            self.disconnect()
            self._reset()

    async def _run_loop(self, password: str) -> None:
        loop = asyncio.get_running_loop()
        first_iteration = True

        while not self._close_event.is_set():
            if not self.is_logged_in():
                logged_in = await self._try_connect(
                    password,
                    first_iteration=first_iteration,
                )
                assert self._is_logged_in is not None

                if not logged_in and self._close_event.is_set():
                    return
                elif not logged_in:
                    log.error("failed to connect to the server")
                    raise LoginFailure("could not connect to the server")
                elif (exc := self._is_logged_in.exception()) is not None:
                    log.error("password authentication was denied")
                    raise exc
                else:
                    log.info("successfully connected to the server")

            elapsed_time = time.monotonic() - self._last_received
            if elapsed_time > self.LAST_RECEIVED_TIMEOUT:
                log.info(
                    f"server has timed out (last received {elapsed_time:.0f} seconds ago)"
                )
                self._reset_protocol()
                self._is_logged_in = loop.create_future()
                continue

            elapsed_time = time.monotonic() - self._last_command
            if elapsed_time > self.config.keep_alive_interval:
                log.debug("sending keep alive packet")
                # NOTE: may result in "Task destroyed but it is pending!"
                #       TaskGroup would be a good idea here
                keep_alive_task = self._begin_keep_alive()

            try:
                coro = self._close_event.wait()
                await asyncio.wait_for(coro, timeout=self.config.run_interval)
            except asyncio.TimeoutError:
                pass

            first_iteration = False

    async def _try_connect(
        self,
        password: str,
        *,
        first_iteration: bool,
    ) -> bool:
        """Attempts to connect to the server, potentially multiple times.

        Connection attempts are spaced out using an exponential backoff
        algorithm.

        :param password: The password to use when authenticating.
        :param first_iteration:
            If ``True``, the number of connection attempts will be limited
            to :py:attr:`INITIAL_CONNECT_ATTEMPTS`. Otherwise, this method
            will attempt to connect indefinitely.
        :returns:
            True if successfully authenticated, and False if all connection
            attempts failed or the protocol was asked to close itself.

        """
        log.info(
            "attempting to {re}connect to server".format(
                re="re" * (not first_iteration)
            )
        )
        self._is_logged_in = maybe_replace_future(self._is_logged_in)

        attempts = itertools.count()
        if first_iteration:
            attempts = range(self.config.initial_connect_attempts)

        for i in attempts:
            try:
                timeout = self.config.connection_timeout
                return await asyncio.wait_for(self.connect(password), timeout=timeout)
            except LoginFailure:
                raise  # credentials may be invalid, or server changed it
            except (asyncio.TimeoutError, OSError):
                if i % 10 == 0:
                    log.warning(
                        "failed {:,d} login attempt{s}".format(i + 1, s="s" * (i != 0))
                    )

                # exponential backoff
                self.disconnect()
                await asyncio.sleep(2 ** (i % 11))

        return False

    def _begin_keep_alive(self) -> asyncio.Task[None]:
        def done_callback(task: asyncio.Task):
            if not isinstance(task.exception(), RCONCommandError):
                task.result()  # unexpected error

        task = asyncio.create_task(
            self._send_keep_alive(),
            name="berconpy-keep-alive",
        )
        task.add_done_callback(done_callback)
        return task

    async def _send_keep_alive(self) -> None:
        assert self.client is not None

        if time.monotonic() - self._last_players > self.config.players_interval:
            # Instead of an empty message, ask for players so we can
            # periodically update the client's cache
            self._last_players = time.monotonic()
            response = await self.send_command("players")
            self.client.cache.update_players(response)
        else:
            await self.send_command("")

    # RCONClientProtocol handling

    def _handle_event(self, event: ClientEvent) -> None:
        assert self.client is not None

        if isinstance(event, ClientAuthEvent):
            assert self._is_logged_in is not None
            if self._is_logged_in.done():
                return

            if event.success:
                self._is_logged_in.set_result(True)
                self.client.dispatch("login")
            else:
                self._is_logged_in.set_exception(
                    LoginFailure("invalid password provided")
                )

        elif isinstance(event, ClientCommandEvent):
            self.commander.set_command(event.sequence, event.message)
            self.client.dispatch("command", event.message)

        elif isinstance(event, ClientMessageEvent):
            self.client.dispatch("message", event.message)

        else:
            raise RuntimeError(f"unhandled event type {type(event)}")

    # DatagramProtocol

    def connection_made(self, transport):
        """Logs when the protocol has connected.

        .. seealso:: :py:meth:`asyncio.BaseProtocol.connection_made()`

        """
        log.debug("protocol has connected")

    def connection_lost(self, exc: Exception | None):
        """Logs when the protocol has disconnected.

        .. seealso:: :py:meth:`asyncio.BaseProtocol.connection_lost()`

        """
        if exc:
            log.error("protocol has disconnected with error", exc_info=exc)
        else:
            log.debug("protocol has disconnected")

    def datagram_received(self, data: bytes, addr):
        """Handles a datagram from the server.

        .. seealso:: :py:meth:`asyncio.DatagramProtocol.datagram_received()`

        """
        assert self.client is not None

        if addr != self._addr:
            return log.debug(f"ignoring message from unknown address: {addr}")

        try:
            packet = self.protocol.receive_datagram(data)
        except ValueError as e:
            return log.debug(f"ignoring malformed data with cause:", exc_info=e)

        log.debug(f"{packet.type.name} received")
        self._last_received = time.monotonic()
        self.client.dispatch("raw_event", packet)

        for event in self.protocol.events_received():
            self._handle_event(event)
        for packet in self.protocol.packets_to_send():
            self.send(packet)

    def error_received(self, exc: OSError):
        """Handles an exceptional error from the protocol.

        .. seealso:: :py:meth:`asyncio.DatagramProtocol.error_received()`

        """
        log.error("unusual error occurred during session", exc_info=exc)
