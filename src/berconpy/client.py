import asyncio
import collections
import contextlib
import logging
import re
import weakref

from .ban import Ban
from .errors import RCONCommandError
from .player import Player
from .protocol import RCONClientDatagramProtocol
from .utils import CoroFunc, MaybeCoroFunc, maybe_coro
from . import utils

log = logging.getLogger(__name__)


# Live messages
_LOGIN = re.compile(r'RCon admin #(?P<id>\d+) \((?P<addr>.*?:\d+)\) logged in')
_CONNECTED = re.compile(r'Player #(?P<id>\d+) (?P<name>.+) \((?P<addr>.*?:\d+)\) connected')
_GUID = re.compile(r'Player #(?P<id>\d+) (?P<name>.+) - BE GUID: (?P<guid>\w+)')
_VERIFIED_GUID = re.compile(r'Verified GUID \((?P<guid>\w+)\) of player #(?P<id>\d+) (?P<name>.+)')
# _UNVERIFIED_GUID = ?
_DISCONNECTED = re.compile(r'Player #(?P<id>\d+) (?P<name>.+) disconnected')
_BATTLEYE_KICK = re.compile(
    r'Player #(?P<id>\d+) (?P<name>.+) \((?P<guid>\w+|-)\) has been kicked '
    r'by BattlEye: (?P<reason>.+)'
)
_RCON_MESSAGE = re.compile(
    r'RCon admin #(?P<id>\d+): \((?P<channel>.+?)\) (?P<message>.+)'
    # If whispered to player, channel would say "To NAME"
)
_PLAYER_MESSAGE = re.compile(
    r'\((?P<channel>.+?)\) (?P<name>.+?): (?P<message>.+)'
    # NOTE: if names can have colons in them, this regex by itself
    # would be insufficient for handling ambiguity
)

# Command responses
_ADMINS_ROW = re.compile(r'(?P<id>\d+) +(?P<addr>.*?:\d+)')
_BANS_ROW = re.compile(
    r'(?P<index>\d+) +(?P<id>[\w.]+) +'
    r'(?P<duration>\d+|-|perm) +(?P<reason>.*)'
)
_PLAYERS_ROW = re.compile(
    r'(?P<id>\d+) +(?P<addr>.*?:\d+) +(?P<ping>\d+) +'
    r'(?P<guid>\w+)\((?P<guid_status>\w+)\) +(?P<name>.+)'
)


def _get_pattern_args(m: re.Match) -> tuple[int | str, ...]:
    return tuple(_get_pattern_kwargs(m).values())


def _get_pattern_kwargs(m: re.Match) -> dict[str, int | str]:
    int_keys = ('id', 'ping')
    kwargs = m.groupdict()

    for k in int_keys:
        v = kwargs.get(k)
        if v is not None:
            kwargs[k] = int(v)

    guid_status = kwargs.pop('guid_status', None)
    if guid_status is not None:
        kwargs['is_guid_valid'] = guid_status == 'OK'

    return kwargs


def _prepare_canceller(
    protocol: RCONClientDatagramProtocol,
    running_task: asyncio.Task,
    current_task: asyncio.Task = None
):
    """Adds a callback to the task running the protocol to cancel
    the current task once the running task is complete.

    This should *only* be called after waiting for login, which is when the
    closing future exists for the canceller to suppress exceptions from it.

    """
    def _actual_canceller(_):
        current_task.cancel()
        closing.exception()

    # We need to cache the closing future here, so we're still able to
    # suppress the future exception if the protocol closed with one
    closing = protocol._is_closing
    if closing is None:
        raise RuntimeError('cannot set up canceller before/after protocol has finished running')

    current_task = current_task or asyncio.current_task()
    running_task.add_done_callback(_actual_canceller)


class AsyncRCONClient:
    """An asynchronous interface for connecting to an BattlEye RCON server."""
    _EXPECTED_MESSAGES: set[str] = frozenset(('Connected to BE Master',))

    _client_id: int
    _players: dict[int, Player]
    _incomplete_players: dict[int, Player]
    _player_pings: weakref.WeakKeyDictionary[Player, int]

    def __init__(
        self,
        protocol_cls=RCONClientDatagramProtocol
    ):
        self._protocol = protocol_cls(self)
        self._protocol_task: asyncio.Task | None = None

        self._event_listeners: dict[str, list[CoroFunc]] = collections.defaultdict(list)
        self._temporary_listeners: dict[
            str, list[tuple[asyncio.Future, MaybeCoroFunc]]
        ] = collections.defaultdict(list)

        self.add_listener('on_login', self._cache_on_login)
        self.add_listener('on_message', self._dispatch_message)
        self._setup_cache()

    def _setup_cache(self):
        self._players = {}
        self._incomplete_players = {}
        self._player_pings = weakref.WeakKeyDictionary()

    @property
    def client_id(self) -> int | None:
        """The RCON admin ID this client was given or None
        if the client has not logged in.
        """
        return getattr(self, '_client_id', None)

    @property
    def players(self) -> list[Player]:
        """The list of players in the server."""
        return list(self._players.values())

    def is_logged_in(self) -> bool | None:
        """Indicates if the client is currently authenticated with the server.

        :returns:
            True if authenticated or None if no
            response has been received from the server.
        :raises LoginFailure:
            The password given to the server was denied.

        """
        return self._protocol.is_logged_in()

    def is_connected(self) -> bool:
        """Indicates if the client has a currently active connection
        with the server.
        """
        return self._protocol.is_connected()

    def is_running(self) -> bool:
        """Indicates if the client is running. This may not necessarily
        mean that the client is connected.
        """
        return self._protocol.is_running()

    # Event handling

    def add_listener(self, event: str, func: CoroFunc):
        """Adds a listener for a given event (e.g. ``"on_login"``).

        :param event:
            The event to listen for.
            See the :doc:`/events` for a list of supported events.
        :param func:
            The coroutine function to dispatch when the event is received.

        """
        self._event_listeners[event].append(func)

    def remove_listener(self, event: str, func: CoroFunc):
        """Removes a listener for a given event (e.g. ``"on_login"``).

        This method is a no-op if the given event and function
        does not match any registered listener.

        :param event: The event used by the listener.
        :param func: The coroutine function used by the listener.

        """
        try:
            self._event_listeners[event].remove(func)
        except ValueError:
            pass

    def listen(self, event: str = None):
        """A decorator shorthand to add a listener for a given event
        (e.g. ``"on_login"``).

        Example usage:

        >>> client = AsyncRCONClient()
        >>> @client.listen()
        ... async def on_login():
        ...     print('We have logged in!')

        :param event:
            The event to listen for. If ``None``, the function name
            is used as the event name.

        """
        def decorator(func: CoroFunc):
            self._event_listeners[event or func.__name__].append(func)
            return func

        return decorator

    def _add_temporary_listener(self, event: str, predicate: MaybeCoroFunc):
        """Adds a temporary listener for an event and returns a future.

        These listeners can be removed either with `_remove_temporary_listener()`
        or by cancelling the future that is returned.

        """
        fut = asyncio.get_running_loop().create_future()
        self._temporary_listeners[event].append((fut, predicate))
        return fut

    def _remove_temporary_listener(self, event: str, fut: asyncio.Future, pred: MaybeCoroFunc):
        listeners = self._temporary_listeners[event]
        e = (fut, pred)

        try:
            listeners.remove(e)
        except ValueError:
            pass

    async def wait_for(
        self, event: str, *,
        check: MaybeCoroFunc = None,
        timeout: float | int = None
    ):
        """Waits for a specific event to occur and returns the result.

        :param event: The event to listen for. (e.g. ``"login"`` or ``"on_login"``)
        :param check:
            An optional predicate function to use as a filter.
            This can be either a regular or an asynchronous function.
            The function should accept the same arguments that the event
            normally takes.
        :param timeout:
            An optional timeout for the function. If this is provided
            and the function times out, an :py:exc:`asyncio.TimeoutError`
            is raised.
        :returns: The arguments passed to the given event.
        :raises asyncio.TimeoutError:
            The function timed out while waiting for the event.

        """
        if not event.startswith('on_'):
            event = 'on_' + event
        if check is None:
            check = lambda *args: True

        fut = self._add_temporary_listener(event, check)

        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            fut.cancel()
            raise

    async def _try_dispatch_temporary(
        self, event: str, fut: asyncio.Future, pred: MaybeCoroFunc, *args
    ):
        if fut.done():
            return self._remove_temporary_listener(event, fut, pred)

        try:
            result = await maybe_coro(pred, *args)
        except Exception as e:
            if not fut.done():
                fut.set_exception(e)
            self._remove_temporary_listener(event, fut, pred)
        else:
            if not result or fut.done():
                return

            fut.set_result(args)
            self._remove_temporary_listener(event, fut, pred)


    def _dispatch(self, event: str, *args):
        """Dispatches a message to the corresponding event listeners.

        Note that the event name should not be prefixed with "on_".

        """
        log.debug(f'dispatching event {event}')
        event = 'on_' + event

        for func in self._event_listeners[event]:
            asyncio.create_task(
                func(*args),
                name=f'berconpy-{event}'
            )

        for fut, pred in self._temporary_listeners[event]:
            asyncio.create_task(
                self._try_dispatch_temporary(event, fut, pred, *args),
                name=f'berconpy-temp-{event}'
            )

    # Connection methods

    @contextlib.asynccontextmanager
    async def connect(self, ip: str, port: int, password: str):
        """Connects to the given IP and port with password.

        If an unexpected error occurs after successfully logging in,
        the current task will be cancelled in order to prevent
        the script unintentionally being stuck indefinitely.

        :raises LoginFailure:
            The password given to the server was denied.
        :raises RuntimeError:
            This method was called while the client is already connected.

        """
        if self._protocol.is_running():
            raise RuntimeError('connection is already running')

        # Establish connection
        try:
            self._protocol_task = asyncio.create_task(
                self._protocol.run(ip, port, password)
            )

            # it's important we wait for login here, otherwise the user
            # could attempt sending commands before a connection was made
            await self._protocol.wait_for_login()
            _prepare_canceller(self._protocol, self._protocol_task)
            yield self
        finally:
            self.close()

            # Propagate any exception from the task
            if self._protocol_task.done() and self._protocol_task.exception():
                raise self._protocol_task.exception() from None

    def close(self):
        """Closes the connection.

        If this is used inside the :py:meth:`connect()` context manager,
        the current task will be cancelled to prevent the script
        unintentionally being stuck indefinitely.

        This method is idempotent and can be called multiple times consecutively.

        """
        self._protocol.close()

    # Commands
    # (documentation: https://www.battleye.com/support/documentation/)

    async def ban(self, addr: int | str, duration: int = None, reason: str = '') -> str:
        """Bans a given player ID, GUID, or IP address (without port).

        Note that the player ID cannot be used to ban players that
        are no longer in the server; a GUID or IP address must be provided.

        :param addr: The ID, GUID, or IP address to ban.
        :param duration:
            The duration of the ban in minutes. If ``None``, the ban
            will be permanent.
        :param reason: The reason for the ban.

        """
        command = 'ban' if isinstance(addr, int) else 'addBan'
        if duration is None:
            duration = 0
        return await self.send_command(f'{command} {duration:d} {reason}'.rstrip())

    async def fetch_admins(self) -> list[tuple[int, str]]:
        """Requests a list of RCON admins connected to the server,
        ordered by admin ID and IP address with port.
        """
        response = await self.send_command('admins')
        return [  # type: ignore
            _get_pattern_args(m)
            for m in _ADMINS_ROW.finditer(response)
        ]

    async def fetch_bans(self) -> list[Ban]:
        """Requests a list of bans on the server."""
        response = await self.send_command('bans')

        bans = []
        for m in _BANS_ROW.finditer(response):
            index, ban_id, duration, reason = _get_pattern_args(m)

            if duration == '-':
                duration = -1
            elif duration == 'perm':
                duration = None
            else:
                duration = int(duration)

            b = Ban(self, index, ban_id, duration, reason)
            bans.append(b)

        return bans

    async def fetch_missions(self) -> list[str]:
        """Requests a list of mission files on the server."""
        response = await self.send_command('missions')
        lines = response.splitlines()
        lines.pop(0)  # 'Missions on server:'
        return lines

    async def fetch_players(self) -> list[Player]:
        """Requests a list of players from the server.

        This method also updates the player cache and pings of
        each player.

        """
        response = await self.send_command('players')
        self._update_players(response)
        return self.players

    def get_player(self, player_id: int) -> Player | None:
        """Gets a player from cache using their server-given ID."""
        return self._players.get(player_id)

    async def kick(self, player_id: int, reason: str = '') -> str:
        """Kicks a player with the given ID from the server
        with an optional reason.
        """
        return await self.send_command(f'kick {player_id:d} {reason}'.rstrip())

    async def send(self, message: str) -> str:
        """Sends a message to all players in the server."""
        return await self.send_command(f'say -1 {message}')

    async def send_command(self, command: str) -> str:
        """Sends a command to the server and waits for a response.

        :param command: The command to send. Only ASCII characters are allowed.
        :returns: The server's response as a string.
        :raises RCONCommandError:
            The server has either disabled this command or failed to
            respond to our command.
        :raises RuntimeError:
            The client is either not connected or the server
            could/would not respond to the command.

        """
        if not self._protocol.is_running():
            raise RuntimeError('cannot send command when not connected')

        response = await self._protocol._send_command(command)
        if response == 'Disallowed command':
            raise RCONCommandError('server has disabled this command')

        return response

    async def unban(self, ban_id: int) -> str:
        """Removes the ban with the given ID from the server."""
        return await self.send_command(f'removeBan {ban_id:d}')

    async def whisper(self, player_id: int, message: str) -> str:
        """Sends a message to the player with the given ID."""
        return await self.send_command(f'say {player_id:d} {message}')

    # Methods to handle keeping player cache up to date

    async def _cache_on_login(self):
        self._setup_cache()
        try:
            admin_id, addr = await self.wait_for('admin_login', timeout=10)
        except asyncio.TimeoutError:
            log.warning(
                'did not receive admin_login event within 10 seconds; '
                'client id will not be available'
            )
        else:
            self._client_id = admin_id

            try:
                await self.fetch_players()
            except RCONCommandError:
                log.warning('failed to receive players from server; '
                            'player cache will not be available')

    def _get_pending_player(self, player_id: int) -> Player | None:
        return self._incomplete_players.get(player_id) or self._players.get(player_id)

    def _push_to_cache(self, player_id: int):
        # We have a potential race condition where fetch_players() /
        # keep alive may occur just before player is added to cache;
        # in that case we can throw away the pending player
        p = self._incomplete_players.pop(player_id, None)
        if p is None or player_id in self._players:
            return

        self._players[player_id] = p

    async def _delayed_push_to_cache(self, player_id: int):
        # Give 5 seconds for events to come in before adding to self._players
        await asyncio.sleep(5)
        self._push_to_cache(player_id)

    def _cache_player(self, player_id: int, name: str, addr: str) -> Player:
        # first message; start timer to cache
        p = Player(self, player_id, name, '', addr, False, False)
        self._incomplete_players[player_id] = p

        asyncio.create_task(
            self._delayed_push_to_cache(player_id),
            name=f'berconpy-arma-push-to-cache-{player_id}'
        )

        return p

    def _cache_player_guid(self, player_id: int, name: str, guid: str) -> Player | None:
        # second message
        p = self._get_pending_player(player_id)
        if p is not None:
            p.guid = guid
        return p

    def _verify_player_guid(self, guid: str, player_id: int, name: str) -> Player | None:
        # last message, can push to cache early
        p = self._get_pending_player(player_id)
        if p is not None:
            p.is_guid_valid = True
            self._push_to_cache(player_id)
        return p

    def _invalidate_player(self, player_id: int, *args) -> Player | None:
        p = self._players.pop(player_id, None)
        p = p or self._incomplete_players.pop(player_id, None)
        return p

    # Event dispatcher

    async def _dispatch_message(self, response: str):
        if m := _LOGIN.fullmatch(response):
            self._dispatch('admin_login', *_get_pattern_args(m))

        elif m := _CONNECTED.fullmatch(response):
            args = _get_pattern_args(m)
            p = self._cache_player(*args)
            self._dispatch('player_connect', p)

        elif m := _GUID.fullmatch(response):
            args = _get_pattern_args(m)
            # NOTE: it might be possible to receive these events before
            # on_player_connect, in which case we cannot get a Player
            # object to dispatch
            if p := self._cache_player_guid(*args):
                self._dispatch('player_guid', p)

        elif m := _VERIFIED_GUID.fullmatch(response):
            args = _get_pattern_args(m)
            if p := self._verify_player_guid(*args):
                self._dispatch('player_verify_guid', p)

        elif m := _DISCONNECTED.fullmatch(response):
            args = _get_pattern_args(m)
            if p := self._invalidate_player(*args):
                self._dispatch('player_disconnect', p)

        elif m := _BATTLEYE_KICK.fullmatch(response):
            args = _get_pattern_args(m)
            if p := self._invalidate_player(*args):
                self._dispatch('player_kick', p, m['reason'])

        elif m := _RCON_MESSAGE.fullmatch(response):
            admin_id, channel, message = _get_pattern_args(m)
            self._dispatch('admin_message', admin_id, channel, message)

            if channel == 'Global':
                self._dispatch('admin_announcement', admin_id, message)
            elif channel.startswith('To '):
                name = channel.removeprefix('To ')
                p = utils.get(self.players, name=name)
                if p is not None:
                    self._dispatch('admin_whisper', p, admin_id, message)

        elif m := _PLAYER_MESSAGE.fullmatch(response):
            channel, name, message = _get_pattern_args(m)
            p = utils.get(self.players, name=name)
            if p is not None:
                self._dispatch('player_message', p, channel, message)

        elif response not in self._EXPECTED_MESSAGES:
            log.warning('unexpected message from server: %s', response)

    def _update_players(self, response: str):
        current_ids = set()
        for m in _PLAYERS_ROW.finditer(response):
            kwargs = _get_pattern_kwargs(m)

            kwargs['in_lobby'] = kwargs['name'].endswith(' (Lobby)')
            if kwargs['in_lobby']:
                kwargs['name'] = kwargs['name'].removesuffix(' (Lobby)')

            ping = kwargs.pop('ping')

            # Create new player if necessary or otherwise update in-place
            p = self._players.get(kwargs['id'])
            if p is None:
                p = Player(client=self, **kwargs)
                self._players[kwargs['id']] = p
            else:
                for k, v in kwargs.items():
                    setattr(p, k, v)

            self._player_pings[p] = ping
            current_ids.add(kwargs['id'])

        # Throw away players no longer in the server
        for k in set(self._players) - current_ids:
            del self._players[k]
