"""
Provides utility functions for parsing messages sent by
the BattlEye server into objects and events.
"""
from dataclasses import dataclass
import re
from typing import TYPE_CHECKING, ClassVar, Iterator, TypedDict

if TYPE_CHECKING:
    from typing_extensions import Self

# Command responses
_ADMINS_ROW = re.compile(r"(?P<id>\d+) +(?P<addr>.*?:\d+)")
_BANS_ROW = re.compile(
    r"(?P<index>\d+) +(?P<ban_id>[\w.]+) +"
    r"(?P<duration>\d+|-|perm) +(?P<reason>.*)"
)
_PLAYERS_ROW = re.compile(
    r"(?P<id>\d+) +(?P<addr>.*?:\d+) +(?P<ping>\d+) +"
    r"(?P<guid>\w+)\((?P<guid_status>\w+)\) +(?P<name>.+)"
)


class MessageBase:
    _PATTERN: ClassVar[re.Pattern]

    @classmethod
    def try_from_message(cls, message: str) -> "Self | None":
        if m := cls._PATTERN.fullmatch(message):
            return cls(**_get_pattern_kwargs(m))  # type: ignore


@dataclass(frozen=True, slots=True)
class AdminConnect(MessageBase):
    id: int
    addr: str

    _PATTERN: ClassVar[re.Pattern] = re.compile(
        r"RCon admin #(?P<id>\d+) \((?P<addr>.*?:\d+)\) logged in"
    )


@dataclass(frozen=True, slots=True)
class PlayerConnect(MessageBase):
    id: int
    name: str
    addr: str

    _PATTERN: ClassVar[re.Pattern] = re.compile(
        r"Player #(?P<id>\d+) (?P<name>.+) \((?P<addr>.*?:\d+)\) connected"
    )


@dataclass(frozen=True, slots=True)
class PlayerGUID(MessageBase):
    id: int
    name: str
    guid: str

    _PATTERN: ClassVar[re.Pattern] = re.compile(
        r"Player #(?P<id>\d+) (?P<name>.+) - BE GUID: (?P<guid>\w+)"
    )


@dataclass(frozen=True, slots=True)
class PlayerVerifyGUID(MessageBase):
    id: int
    name: str
    guid: str

    _PATTERN: ClassVar[re.Pattern] = re.compile(
        r"Verified GUID \((?P<guid>\w+)\) of player #(?P<id>\d+) (?P<name>.+)"
    )

    # NOTE: does one exist for an unverified GUID?


@dataclass(frozen=True, slots=True)
class PlayerDisconnect(MessageBase):
    id: int
    name: str

    _PATTERN: ClassVar[re.Pattern] = re.compile(
        r"Player #(?P<id>\d+) (?P<name>.+) disconnected"
    )


@dataclass(frozen=True, slots=True)
class PlayerKick(MessageBase):
    id: int
    name: str
    guid: str | None
    reason: str

    _PATTERN: ClassVar[re.Pattern] = re.compile(
        r"Player #(?P<id>\d+) (?P<name>.+) \((?P<guid>\w+|-)\) has been kicked "
        r"by BattlEye: (?P<reason>.+)"
    )


@dataclass(frozen=True, slots=True)
class RCONMessage(MessageBase):
    id: int
    channel: str  # If whispered to player, channel would say "To NAME"
    message: str

    _PATTERN: ClassVar[re.Pattern] = re.compile(
        r"RCon admin #(?P<id>\d+): \((?P<channel>.+?)\) (?P<message>.+)"
    )


@dataclass(frozen=True, slots=True)
class PlayerMessage(MessageBase):
    channel: str
    name: str
    message: str

    _PATTERN: ClassVar[re.Pattern] = re.compile(
        r"\((?P<channel>.+?)\) (?P<name>.+?): (?P<message>.+)"
        # If names can have colons in them, this regex by itself
        # would be insufficient for handling ambiguity
    )


class ParsedAdmin(TypedDict):
    id: int
    addr: str


class ParsedBan(TypedDict):
    index: int
    ban_id: str
    duration: int | None
    reason: str


class ParsedPlayer(TypedDict):
    id: int
    name: str
    guid: str
    addr: str
    ping: int
    is_guid_valid: bool
    in_lobby: bool


def _get_pattern_kwargs(m: re.Match) -> dict:
    int_keys = ("id", "index", "ping")
    kwargs = m.groupdict()

    for k in int_keys:
        v = kwargs.get(k)
        if v is not None:
            kwargs[k] = int(v)

    return kwargs


def is_expected_message(message: str) -> bool:
    """Determines if a server message is expected."""
    return message in (
        "Ban check timed out, no response from BE Master",
        "Connected to BE Master",
        "Disconnected from BE Master",
        "Failed to resolve BE Master DNS name(s)",
    )


def parse_admins(response: str) -> Iterator[ParsedAdmin]:
    """Iteratively parses an "admins" command response into a list containing
    tuples of admin ID and IP address with port.
    """
    for m in _ADMINS_ROW.finditer(response):
        yield _get_pattern_kwargs(m)  # type: ignore


def parse_bans(response: str) -> Iterator[ParsedBan]:
    """Iteratively parses a "bans" command response into
    :py:class:`ParsedBan` objects.
    """
    for m in _BANS_ROW.finditer(response):
        kwargs = _get_pattern_kwargs(m)

        if kwargs["duration"] == "-":
            kwargs["duration"] = -1
        elif kwargs["duration"] == "perm":
            kwargs["duration"] = None
        else:
            kwargs["duration"] = int(kwargs["duration"])

        yield kwargs  # type: ignore


def parse_players(response: str) -> Iterator[ParsedPlayer]:
    """Iteratively parses a "players" command response into
    :py:class:`ParsedPlayer` objects.
    """
    for m in _PLAYERS_ROW.finditer(response):
        player = _get_pattern_kwargs(m)
        in_lobby = player["name"].endswith(" (Lobby)")
        if in_lobby:
            player["name"] = player["name"].removesuffix(" (Lobby)")
        player["is_guid_valid"] = player.pop("guid_status") == "OK"
        player["in_lobby"] = in_lobby
        yield player  # type: ignore
