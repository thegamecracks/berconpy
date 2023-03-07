from dataclasses import asdict, dataclass
from typing import Iterable


class AsDict:
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Admin(AsDict):
    id: int
    ip: str
    port: int

    @staticmethod
    def make_message(admins: "Iterable[Admin]") -> str:
        header = (
            "Connected RCon admins:\n"
            "[#] [IP Address]:[Port]\n"
            "-----------------------------"
        )
        row = "{id} {ip}:{port}"

        rows = "\n".join(map(row.format, admins))
        return f"{header}\n{rows}"


@dataclass(frozen=True)
class Player(AsDict):
    id: int
    addr: str
    ping: int
    guid: str
    name: str
    is_guid_valid: bool = True
    in_lobby: bool = False

    @staticmethod
    def make_message(players: "Iterable[Player]") -> str:
        header = (
            "Players on server:\n"
            "[#] [IP Address]:[Port] [Ping] [GUID] [Name]\n"
            "--------------------------------------------------"
        )
        row = "{0.id:<2d} {0.addr:<29s} {0.ping:^5d} {0.guid}(OK) {0.name}"
        footer = "({total} players in total)"

        rows = "\n".join(map(row.format, players))
        return f"{header}\n{rows}\n{footer}".format(total=len(rows))


sample_admins = (
    Admin(0, "1.2.3.4", 1234),
    Admin(1, "2.3.4.5", 2345),
    Admin(2, "3.4.5.6", 3456),
)
sample_players = (
    Player(3, "1.2.3.4:1234", 140, "394e2c09af98b00fd4094f86c7921622", "Spam"),
    Player(2, "2.3.4.5:2345", 125, "d93ed2257011b47e67fa53e824b60ca5", "H8m"),
    Player(1, "1.2.3.4:1234", 47, "4f0c611d97e5379680d79f2f36b2e9e1", "3ggs456"),
)
