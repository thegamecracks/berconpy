"""
Provides utility functions for parsing messages sent by
the BattlEye server into objects and events.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Iterator, TypedDict

from berconpy import utils

if TYPE_CHECKING:
    from typing_extensions import Self

    from .cache import ArmaCache
    from .dispatch import ArmaDispatcher

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
    prefixes = (
        "Config entry:",
        "Failed to receive from BE Master",
    )
    exact = (
        "Ban check timed out, no response from BE Master",
        "Connected to BE Master",
        "Disconnected from BE Master",
        "Failed to resolve BE Master DNS name(s)",
        "Master query timed out, no response from BE Master",
    )
    return message.startswith(prefixes) or message in exact


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


def parse_message(cache: ArmaCache, dispatch: ArmaDispatcher, message: str) -> None:
    if m := AdminConnect.try_from_message(message):
        dispatch.on_admin_login.fire(m.id, m.addr)

    elif m := PlayerConnect.try_from_message(message):
        p = cache.add_connected_player(m)
        dispatch.on_player_connect.fire(p)

    elif m := PlayerGUID.try_from_message(message):
        # NOTE: it might be possible to receive these events before
        # on_player_connect, in which case we cannot get a Player
        # object to dispatch
        if p := cache.set_player_guid(m):
            dispatch.on_player_guid.fire(p)

    elif m := PlayerVerifyGUID.try_from_message(message):
        if p := cache.verify_player_guid(m):
            dispatch.on_player_verify_guid.fire(p)

    elif m := PlayerDisconnect.try_from_message(message):
        if p := cache.remove_player(m.id):
            dispatch.on_player_disconnect.fire(p)

    elif m := PlayerKick.try_from_message(message):
        if p := cache.remove_player(m.id):
            dispatch.on_player_kick.fire(p, m.reason)

    elif m := RCONMessage.try_from_message(message):
        dispatch.on_admin_message.fire(m.id, m.channel, m.message)

        if m.channel == "Global":
            dispatch.on_admin_announcement.fire(m.id, m.message)
        elif m.channel.startswith("To "):
            name = m.channel.removeprefix("To ")
            p = utils.get(cache.players, name=name)
            if p is not None:
                dispatch.on_admin_whisper.fire(p, m.id, m.message)

    elif m := PlayerMessage.try_from_message(message):
        p = utils.get(cache.players, name=m.name)
        if p is not None:
            dispatch.on_player_message.fire(p, m.channel, m.message)

    elif not is_expected_message(message):
        raise ValueError(f"Unexpected server message: {message!r}")
