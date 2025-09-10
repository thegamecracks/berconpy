from .client import RCONClient
from .dispatch import EventDispatcher
from .errors import (
    LoginFailure as LoginFailure,
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
    AsyncClientConnector,
    AsyncClientProtocol,
    AsyncCommander,
    ConnectorConfig,
)
from .ext.arma import (
    ArmaCache,
    ArmaClient,
    ArmaConnector,
    ArmaConnectorConfig,
    ArmaDispatcher,
    Ban,
    Player,
)


def _get_version() -> str:
    from importlib.metadata import version

    return version("berconpy")


__version__ = _get_version()
