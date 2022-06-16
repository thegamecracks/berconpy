import asyncio
import logging
import re
import time

from berconpy import *

from .player import Player

# Live messages
_LOGIN = re.compile(r'RCon admin #(?P<id>\d+) \((?P<addr>.*?:\d+)\) logged in')
_CONNECTED = re.compile(r'Player #(?P<id>\d+) (?P<name>.+) \((?P<addr>.*?:\d+)\) connected')
_GUID = re.compile(r'Player #(?P<id>\d+) (?P<name>.+) - BE GUID: (?P<guid>\w+)')
_VERIFIED_GUID = re.compile(r'Verified GUID \((?P<guid>\w+)\) of player #(?P<id>\d+) (?P<name>.+)')
# _UNVERIFIED_GUID = ?
_DISCONNECTED = re.compile(r'Player #(?P<id>\d+) (?P<name>.+) disconnected')
_BATTLEYE_KICK = re.compile(
    r'Player #(?P<id>\d+) (?P<name>.+) \((?P<guid>\w+)\) has been kicked '
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
_PLAYERS_ROW = re.compile(
    r'(?P<id>\d+) +(?P<addr>.*?:\d+) +(?P<ping>\d+) +'
    r'(?P<guid>\w+)\((?P<guid_status>\w+)\) +(?P<name>.+)'
)

log = logging.getLogger(__name__)


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


class ArmaRCONClientDatagramProtocol(RCONClientDatagramProtocol):
    """A customized protocol that can send the "players" command
    as part of keep alive packets and update the client's cache.
    """
    PLAYERS_INTERVAL = 60

    _last_players: float

    client: "AsyncArmaRCONClient"

    def reset(self):
        super().reset()

        self._last_players = time.monotonic()

    def _send_keep_alive(self):
        sequence = self._get_next_sequence()

        if time.monotonic() - self._last_players > self.PLAYERS_INTERVAL:
            self._last_players = time.monotonic()
            packet = ClientCommandPacket(sequence, 'players')
            self._send(packet)

            asyncio.create_task(
                self._wait_player_pings(sequence),
                name=f'berconpy-arma-players-{sequence}'
            )
        else:
            packet = ClientCommandPacket(sequence, '')
            self._send(packet)

    async def _wait_player_pings(self, sequence: int):
        try:
            response = await asyncio.wait_for(
                self._wait_for_command(sequence),
                timeout=5
            )
        except asyncio.TimeoutError:
            pass
        else:
            self.client._update_players(response)


class AsyncArmaRCONClient(AsyncRCONClient):
    """An async client subclass designed for handling Arma RCON.

    This class adds the following new events:
        - on_admin_login(admin_id: int, addr: str):
            Fired when a RCON admin logs into the server.
            The first message received will be our client
            logging in. Note that there is no logout equivalent
            for this event.

        - on_player_connect(player_id: int, name: str, addr: str):
            Fired when a player connects to a server.

        - on_player_guid(player_id: int, name: str, guid: str):
            Fired when receiving the BattlEye GUID for a connecting player.

        - on_player_verify_guid(guid: str, player_id: int, name: str):
            Fired when the server has verified the BattlEye GUID
            for a connecting player.

        - on_player_disconnect(player_id: int, name: str):
            Fired when a player manually disconnects from the server.
            This event does not fire when BattlEye kicks the player;
            see the following event `on_battleye_kick()`.

        - on_player_kick(player_id: int, name: str, guid: str, reason: str):
            Fired when BattlEye kicks a player either automatically
            (e.g. "Client not responding") or by an admin (i.e. "Admin Kick").

        - on_admin_message(admin_id: int, channel: str, message: str):
            Fired when an RCON admin sends a message. This event
            is further broken down into `on_admin_global_message()`
            and `on_admin_whisper()`. The corresponding event
            is dispatched alongside this event.

        - on_admin_announcement(admin_id: int, message: str):
            Fired when an RCON admin sends a global message.

        - on_admin_whisper(admin_id: int, name: str, message: str):
            Fired when an RCON admin sends a message to a specific player.

        - on_player_message(channel: str, name: str, message: str):
            Fired when a player sends a message.

    """

    _client_id: int
    _players: dict[int, Player]
    _incomplete_players: dict[int, Player]
    _player_pings: dict[int, int]

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args, protocol_cls=ArmaRCONClientDatagramProtocol, **kwargs
        )
        self.add_listener('on_login', self._cache_on_login)
        self.add_listener('on_message', self._dispatch_arma_message)
        self.add_listener('on_player_connect', self._cache_player)
        self.add_listener('on_player_guid', self._cache_player_guid)
        self.add_listener('on_player_verify_guid', self._verify_player_guid)
        self.add_listener('on_player_disconnect', self._invalidate_player)
        self._setup_cache()

    def _setup_cache(self):
        self._players = {}
        self._incomplete_players = {}
        self._player_pings = {}

    @property
    def client_id(self) -> int | None:
        """Returns the RCON admin ID this client was given or None
        if the client has not logged in.
        """
        return getattr(self, '_client_id', None)

    @property
    def players(self) -> list[Player]:
        """Returns a list of players in the server."""
        return list(self._players.values())

    async def fetch_players(self) -> list[Player]:
        """Requests a list of players from the server.

        This method also updates the player cache and pings of
        each player.

        """
        response = await self.send_command('players')
        self._update_players(response)
        return self.players

    def get_player(self, player_id: int) -> Player | None:
        """Gets a player using their server-given ID."""
        return self._players.get(player_id)

    async def _cache_on_login(self):
        admin_id, addr = await self.wait_for('admin_login', timeout=10)
        self._client_id = admin_id

        await self.fetch_players()

    # Listeners to handle keeping player cache up to date

    def _get_pending_player(self, player_id: int) -> Player | None:
        return self._incomplete_players.get(player_id) or self._players.get(player_id)

    async def _push_to_cache(self, player_id: int):
        # Give 5 seconds for events to come in before adding to self._players
        await asyncio.sleep(5)

        p = self._incomplete_players.pop(player_id, None)
        if p is not None:
            self._players[player_id] = p

    async def _cache_player(self, player_id: int, name: str, addr: str):
        # first message; start timer to cache
        p = Player(self, player_id, name, '', addr, False, False)
        self._incomplete_players[player_id] = p

        asyncio.create_task(
            self._push_to_cache(player_id),
            name=f'berconpy-arma-push-to-cache-{player_id}'
        )

    async def _cache_player_guid(self, player_id: int, name: str, guid: str):
        # second message
        p = self._get_pending_player(player_id)
        if p is not None:
            p.guid = guid

    async def _verify_player_guid(self, guid: str, player_id: int, name: str):
        # last message, can push to cache early
        p = self._get_pending_player(player_id)
        if p is not None:
            p.is_guid_valid = True
            if self._incomplete_players.pop(player_id, None):
                self._players[player_id] = p

    async def _invalidate_player(self, player_id: int, name: str):
        self._players.pop(player_id, None)
        self._incomplete_players.pop(player_id, None)
        self._player_pings.pop(player_id, None)

    # Event dispatcher

    async def _dispatch_arma_message(self: "AsyncArmaRCONClient", response: str):
        if m := _LOGIN.fullmatch(response):
            self._dispatch('admin_login', *_get_pattern_args(m))

        elif m := _CONNECTED.fullmatch(response):
            self._dispatch('player_connect', *_get_pattern_args(m))

        elif m := _GUID.fullmatch(response):
            self._dispatch('player_guid', *_get_pattern_args(m))

        elif m := _VERIFIED_GUID.fullmatch(response):
            self._dispatch('player_verify_guid', *_get_pattern_args(m))

        elif m := _DISCONNECTED.fullmatch(response):
            self._dispatch('player_disconnect', *_get_pattern_args(m))

        elif m := _BATTLEYE_KICK.fullmatch(response):
            self._dispatch('player_kick', *_get_pattern_args(m))

        elif m := _RCON_MESSAGE.fullmatch(response):
            admin_id, channel, message = _get_pattern_args(m)
            self._dispatch('admin_message', admin_id, channel, message)

            if channel == 'Global':
                self._dispatch('admin_announcement', admin_id, message)
            elif channel.startswith('To '):
                name = channel.removeprefix('To ')
                self._dispatch('admin_whisper', admin_id, name, message)

        elif m := _PLAYER_MESSAGE.fullmatch(response):
            self._dispatch('player_message', *_get_pattern_args(m))

        else:
            log.warning('unexpected message from server: %s', response)

    def _update_players(self, response: str):
        current_ids = set()
        for m in _PLAYERS_ROW.finditer(response):
            kwargs = _get_pattern_kwargs(m)

            kwargs['in_lobby'] = kwargs['name'].endswith(' (Lobby)')
            if kwargs['in_lobby']:
                kwargs['name'] = kwargs['name'].removesuffix(' (Lobby)')

            self._player_pings[kwargs['id']] = kwargs.pop('ping')

            # Create new player if necessary or otherwise update in-place
            p = self._players.get(kwargs['id'])
            if p is None:
                p = Player(client=self, **kwargs)
                self._players[kwargs['id']] = p
            else:
                for k, v in kwargs.items():
                    setattr(p, k, v)

            current_ids.add(kwargs['id'])

        # Throw away players no longer in the server
        for k in set(self._players) - current_ids:
            del self._players[k]
