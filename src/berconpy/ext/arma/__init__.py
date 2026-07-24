"""Provides an asynchronous client tailored to Arma 3."""

from typing import TYPE_CHECKING

from .ban import Ban as Ban
from .cache import ArmaCache as ArmaCache
from .client import ArmaClient as ArmaClient
from .dispatch import ArmaDispatcher as ArmaDispatcher
from .io import (
    ArmaConnector as ArmaConnector,
    ArmaConnectorConfig as ArmaConnectorConfig,
)
from .player import Player as Player

if TYPE_CHECKING:
    from typing_extensions import deprecated

    @deprecated("Use ArmaClient instead")
    class AsyncArmaRCONClient(ArmaClient): ...

else:
    from warnings import warn

    def __getattr__(name):
        if name == "AsyncArmaRCONClient":
            warn("AsyncArmaRCONClient is deprecated, use ArmaClient instead")
            return ArmaClient

        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
