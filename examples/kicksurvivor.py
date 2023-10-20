"""Connects to an RCON server and prevents players with the nickname 'Survivor' from logging in"""
import re, math
import asyncio

import berconpy as rcon

IP_ADDR = "XXX.XXX.XXX.XXX"
PORT = 9999
PASSWORD = "ASCII_PASSWORD"

kickReason = "Name 'Survivor' not allowed"
client = rcon.AsyncRCONClient()

@client.dispatch.on_message
async def on_message(message: str):
    match = re.match(r'Player #(\d+) (\w+(?: \(\d+\))?) \(\d+\.\d+\.\d+\.\d+:\d+\) connected', message)
    if match:
        player_id = match.group(1)
        player_name = match.group(2)
        if player_name == "Survivor" or re.match(r'^Survivor \(\d+\)$', player_name):
            await client.kick(int(player_id), kickReason)

async def main():
    async with client.connect(IP_ADDR, PORT, PASSWORD):
        await asyncio.sleep(math.inf)

if __name__ == "__main__":
    asyncio.run(main())