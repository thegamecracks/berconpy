from typing import TYPE_CHECKING

from .client import RCONClient as RCONClient
from .dispatch import EventDispatcher as EventDispatcher
from .errors import (
    LoginFailure as LoginFailure,
    LoginRefused as LoginRefused,
    LoginTimeout as LoginTimeout,
    RCONCommandError as RCONCommandError,
    RCONError as RCONError,
)
from .protocol import (
    Check as Check,
    ClientAuthEvent as ClientAuthEvent,
    ClientCommandEvent as ClientCommandEvent,
    ClientEvent as ClientEvent,
    ClientMessageEvent as ClientMessageEvent,
    ClientState as ClientState,
    InvalidStateError as InvalidStateError,
    NonceCheck as NonceCheck,
    RCONClientProtocol as RCONClientProtocol,
    RCONGenericProtocol as RCONGenericProtocol,
    RCONServerProtocol as RCONServerProtocol,
    ServerAuthEvent as ServerAuthEvent,
    ServerCommandEvent as ServerCommandEvent,
    ServerEvent as ServerEvent,
    ServerMessageEvent as ServerMessageEvent,
    ServerState as ServerState,
)
from .io import (
    AsyncClientConnector as AsyncClientConnector,
    AsyncClientProtocol as AsyncClientProtocol,
    AsyncCommander as AsyncCommander,
    ConnectorConfig as ConnectorConfig,
)
from .ext.arma import (
    ArmaCache as ArmaCache,
    ArmaClient as ArmaClient,
    ArmaConnector as ArmaConnector,
    ArmaConnectorConfig as ArmaConnectorConfig,
    ArmaDispatcher as ArmaDispatcher,
    Ban as Ban,
    Player as Player,
)

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
