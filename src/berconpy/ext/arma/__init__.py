"""A package that adds arma-specific event handlers and commands."""
import logging
import re

from berconpy import *

__ALL__ = (
    'AsyncArmaRCONClient',
)

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

log = logging.getLogger(__name__)


def _get_pattern_args(m: re.Match) -> tuple[int | str, ...]:
    kwargs = m.groupdict()
    id_ = kwargs.get('id')
    if id_ is not None:
        kwargs['id'] = int(id_)
    return tuple(kwargs.values())


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

        - on_player_verify_guid(player_id: int, name: str, guid: str):
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_listener('on_message', self._dispatch_arma_message)

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
