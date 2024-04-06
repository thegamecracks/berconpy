"""Connects to an RCON server and kicks players with "Survivor" as their name."""
import re, math
import asyncio

import berconpy as rcon

IP_ADDR = "XXX.XXX.XXX.XXX"
PORT = 9999
PASSWORD = "ASCII_PASSWORD"

client = rcon.AsyncRCONClient()


@client.dispatch.on_player_connect
async def on_player_connect(player: rcon.Player):
    if player.name == "Survivor" or re.match(r"^Survivor \(\d+\)$", player.name):
        await player.kick("Name 'Survivor' not allowed")


async def main():
    async with client.connect(IP_ADDR, PORT, PASSWORD):
        await asyncio.sleep(math.inf)


if __name__ == "__main__":
    asyncio.run(main())
