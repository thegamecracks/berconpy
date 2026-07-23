from typing import TYPE_CHECKING

from .client import RCONClient as RCONClient
from .dispatch import EventDispatcher as EventDispatcher
from .errors import LoginFailure as LoginFailure
from .errors import LoginRefused as LoginRefused
from .errors import LoginTimeout as LoginTimeout
from .errors import RCONCommandError as RCONCommandError
from .errors import RCONError as RCONError
from .ext.arma import ArmaCache as ArmaCache
from .ext.arma import ArmaClient as ArmaClient
from .ext.arma import ArmaConnector as ArmaConnector
from .ext.arma import ArmaConnectorConfig as ArmaConnectorConfig
from .ext.arma import ArmaDispatcher as ArmaDispatcher
from .ext.arma import Ban as Ban
from .ext.arma import Player as Player
from .io import AsyncClientConnector as AsyncClientConnector
from .io import AsyncClientProtocol as AsyncClientProtocol
from .io import AsyncCommander as AsyncCommander
from .io import ConnectorConfig as ConnectorConfig
from .protocol import Check as Check
from .protocol import ClientAuthEvent as ClientAuthEvent
from .protocol import ClientCommandEvent as ClientCommandEvent
from .protocol import ClientEvent as ClientEvent
from .protocol import ClientMessageEvent as ClientMessageEvent
from .protocol import ClientState as ClientState
from .protocol import InvalidStateError as InvalidStateError
from .protocol import NonceCheck as NonceCheck
from .protocol import RCONClientProtocol as RCONClientProtocol
from .protocol import RCONGenericProtocol as RCONGenericProtocol
from .protocol import RCONServerProtocol as RCONServerProtocol
from .protocol import ServerAuthEvent as ServerAuthEvent
from .protocol import ServerCommandEvent as ServerCommandEvent
from .protocol import ServerEvent as ServerEvent
from .protocol import ServerMessageEvent as ServerMessageEvent
from .protocol import ServerState as ServerState

if TYPE_CHECKING:
    from typing_extensions import deprecated

    @deprecated("Use ArmaDispatcher instead")
    class AsyncEventDispatcher(ArmaDispatcher): ...

    @deprecated("Use ArmaClient instead")
    class AsyncRCONClient(ArmaClient): ...

    @deprecated("Use ArmaCache instead")
    class AsyncRCONClientCache(ArmaCache): ...

else:
    from warnings import warn

    def __getattr__(name):
        if name == "AsyncEventDispatcher":
            warn("AsyncEventDispatcher is deprecated, use ArmaDispatcher instead")
            return ArmaDispatcher
        elif name == "AsyncRCONClient":
            warn("AsyncRCONClient is deprecated, use ArmaClient instead")
            return ArmaClient
        elif name == "AsyncRCONClientCache":
            warn("AsyncRCONClientCache is deprecated, use ArmaCache instead")
            return ArmaCache

        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _get_version() -> str:
    from importlib.metadata import version

    return version("berconpy")


__version__ = _get_version()
