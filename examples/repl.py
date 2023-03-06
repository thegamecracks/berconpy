"""Connects to an RCON server and allows typing in any command."""
import asyncio
import logging

import berconpy as rcon

IP_ADDR = "XXX.XXX.XXX.XXX"
PORT = 9999
PASSWORD = "ASCII_PASSWORD"

log = logging.getLogger("berconpy")
log.setLevel(logging.WARNING)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s"))
log.addHandler(handler)

client = rcon.AsyncRCONClient()


async def ainput():
    return await asyncio.to_thread(input)


@client.listen()
async def on_admin_login(admin_id: int, addr: str):
    print(f"Admin #{admin_id} logged in")


@client.listen()
async def on_player_connect(player: rcon.Player):
    print(f"Player #{player.id} {player.name} connected")


@client.listen()
async def on_player_disconnect(player: rcon.Player):
    print(f"Player #{player.id} {player.name} disconnected")


@client.listen()
async def on_player_kick(player: rcon.Player, reason: str):
    print(f"Player #{player.id} {player.name} was kicked: {reason}")


@client.listen()
async def on_admin_message(admin_id: int, channel: str, message: str):
    print(f"({channel}) Admin #{admin_id}: {message}")


@client.listen()
async def on_player_message(player: rcon.Player, channel: str, message: str):
    print(f"({channel}) {player.name}: {message}")


async def main():
    async with client.connect(IP_ADDR, PORT, PASSWORD):
        print(await client.send_command("commands"))

        while True:
            command = await ainput()

            if command.lower() == "#players":
                for p in client.cache.players:
                    print(repr(p))
            else:
                try:
                    response = await client.send_command(command)
                except rcon.RCONCommandError as e:
                    print(e)
                else:
                    print(response)


if __name__ == "__main__":
    asyncio.run(main())
