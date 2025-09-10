"""Listens to an RCON server for messages."""

import asyncio
import logging
import math

import berconpy as rcon

IP_ADDR = "XXX.XXX.XXX.XXX"
PORT = 9999
PASSWORD = "ASCII_PASSWORD"

log = logging.getLogger("berconpy")
log.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(
    logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
)
log.addHandler(handler)

client = rcon.RCONClient()


@client.dispatch.on_login
async def on_login():
    print("on_login")


@client.dispatch.on_message
async def on_message(message: str):
    print("on_message:", message)


@client.dispatch.on_command
async def server_response_to_command(response: str):
    print("on_command:", response or "<empty>")


async def main():
    async with client.connect(IP_ADDR, PORT, PASSWORD):
        await asyncio.sleep(math.inf)


if __name__ == "__main__":
    asyncio.run(main())
