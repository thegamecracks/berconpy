"""Kicks players that join with the "Survivor" name."""
import asyncio
import math
import re

import berconpy as rcon

IP_ADDR = "XXX.XXX.XXX.XXX"
PORT = 9999
PASSWORD = "ASCII_PASSWORD"

client = rcon.ArmaClient()


@client.dispatch.on_player_connect
async def on_player_connect(player: rcon.Player):
    if re.match(r"Survivor(?: \(\d+\))?", player.name) is not None:
        await player.kick("Name 'Survivor' not allowed")


async def main():
    async with client.connect(IP_ADDR, PORT, PASSWORD):
        await asyncio.sleep(math.inf)


if __name__ == "__main__":
    asyncio.run(main())
