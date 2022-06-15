"""A package that adds arma-specific event handlers and commands."""
import re

from berconpy import *

# Live messages
_IP = re.compile(r'(?P<ip>.*?):(?P<port>\d+)')
_LOGIN = re.compile(rf'RCon admin #(?P<id>\d+) (:\d+) \({_IP.pattern}\) logged in')
_CONNECTED = re.compile(rf'Player #(?P<id>\d+) (?P<name>.+) \({_IP.pattern}\) connected')
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

class AsyncArmaRCONClient(AsyncRCONClient):
    """An async client subclass designed for handling Arma RCON.

    Insert new events here:
        - ...

    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_listener('on_message', self._dispatch_arma_message)


    async def _dispatch_arma_message(self: "AsyncArmaRCONClient", response: str):
        pass
