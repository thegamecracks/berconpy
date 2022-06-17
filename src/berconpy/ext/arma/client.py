import logging

from berconpy import *

log = logging.getLogger(__name__)


class AsyncArmaRCONClient(AsyncRCONClient):
    """An AsyncRCONClient subclass that adds more methods for handling Arma RCON."""
